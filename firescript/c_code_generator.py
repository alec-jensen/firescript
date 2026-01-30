# firescript/c_code_generator.py
from enums import NodeTypes  # [firescript/enums.py]
from parser import ASTNode  # [firescript/parser.py]
from typing import Optional
import logging

# A simple type mapping from firescript types to C types.
FIRETYPE_TO_C: dict[str, str] = {
    # integers
    "int8": "int8_t",
    "int16": "int16_t",
    "int32": "int32_t",
    "int64": "int64_t",
    "uint8": "uint8_t",
    "uint16": "uint16_t",
    "uint32": "uint32_t",
    "uint64": "uint64_t",
    # floats (explicit only)
    "float32": "float",
    "float64": "double",
    "float128": "long double",
    # future: "float128": "__float128",
    # others
    "bool": "bool",
    "string": "char*",
    "tuple": "struct tuple",
}


class CCodeGenerator:
    def __init__(self, ast: ASTNode):
        self.ast = ast
        self.symbol_table: dict[str, tuple[str, bool]] = {}  # (type, is_array)
        # Fixed-size array lengths by variable name
        self.array_lengths: dict[str, int] = {}
        self.array_temp_counter = (
            0  # Counter for generating unique array variable names
        )
        # Track arrays declared per lexical scope to free them at scope exit
        # Each element is a list of variable names for that scope
        self.scope_stack: list[list[str]] = [[]]
        # Track whether we're currently visiting inside a function body
        self._in_function: bool = False
        # Detect if drop() insertion is enabled via directive in AST
        self.drops_enabled: bool = any(
            c.node_type == NodeTypes.DIRECTIVE and getattr(c, "name", "") == "enable_drops"
            for c in (self.ast.children or [])
        )
        
        # Name mangling support: map original names to mangled names
        self.name_counter = 0
        self.mangled_names: dict[str, str] = {}
        # Stack of name scopes for nested functions/blocks
        self.name_scope_stack: list[dict[str, str]] = [{}]
        # Built-in functions that shouldn't be mangled
        self.builtin_names = {"print", "input", "drop"}
        
        # Collect class names and metadata for constructors and methods
        self.class_names: set[str] = set()
        self.class_fields: dict[str, list[tuple[str, str]]] = {}
        self.class_methods: dict[str, list[ASTNode]] = {}
        for c in (self.ast.children or []):
            if c.node_type == NodeTypes.CLASS_DEFINITION:
                self.class_names.add(c.name)
                fields: list[tuple[str, str]] = []
                methods: list[ASTNode] = []
                for ch in c.children:
                    if ch.node_type == NodeTypes.CLASS_FIELD:
                        fields.append((ch.name, ch.var_type or "int32"))
                    elif ch.node_type == NodeTypes.CLASS_METHOD_DEFINITION:
                        methods.append(ch)
                self.class_fields[c.name] = fields
                self.class_methods[c.name] = methods
        
        # Generics support: track monomorphized instances
        # Maps (func_name, tuple of concrete types) -> mangled function name
        self.monomorphized_funcs: dict[tuple[str, tuple[str, ...]], str] = {}
        # Track which generic functions need to be instantiated
        self.generic_templates: dict[str, ASTNode] = {}
        # Collect generic function templates
        for c in (self.ast.children or []):
            if c.node_type == NodeTypes.FUNCTION_DEFINITION:
                if hasattr(c, 'type_params') and c.type_params:
                    self.generic_templates[c.name] = c
                    logging.debug(f"Found generic template: {c.name} with type params {c.type_params}")

    def _free_arrays_in_current_scope(self) -> list[str]:
        """Return lines to free arrays declared in the current scope (no pop)."""
        # Fixed-size arrays require no dynamic cleanup
        return []

    def _free_arrays_in_all_active_scopes(self) -> list[str]:
        """Return lines to free arrays declared in all active scopes (outer to inner)."""
        return []

    def _handle_array_index(self, index_expr):
        """Helper function to properly handle array indices in C"""
        # After removing big number support, just return the expression string
        return str(index_expr)
    
    def _mangle_name(self, name: str) -> str:
        """Generate a unique mangled name for a user symbol to avoid C collisions."""
        # Don't mangle built-in functions
        if name in self.builtin_names:
            return name
        
        # Check current scope first, then parent scopes
        for scope in reversed(self.name_scope_stack):
            if name in scope:
                return scope[name]
        
        # Not found in any scope - create new mangled name in current scope
        mangled = f"{name}_{self.name_counter}"
        self.name_counter += 1
        self.name_scope_stack[-1][name] = mangled
        return mangled
    
    def _mangle_generic_name(self, func_name: str, type_args: tuple[str, ...]) -> str:
        """Generate a mangled name for a monomorphized generic function."""
        # Simple mangling: func_name$type1$type2$...
        type_suffix = "$".join(type_args)
        return f"{func_name}${type_suffix}"
    
    def _infer_type_args_from_call(self, func_name: str, call_node: ASTNode) -> Optional[list[str]]:
        """Infer type arguments for a generic function call based on argument types."""
        if func_name not in self.generic_templates:
            return None
        
        template = self.generic_templates[func_name]
        type_params = getattr(template, 'type_params', [])
        if not type_params:
            return []
        
        # Get parameter types from template
        param_types = []
        for child in template.children:
            if child.node_type == NodeTypes.PARAMETER:
                param_types.append(child.var_type or "")
        
        # Get argument types from call
        arg_types = []
        for arg in (call_node.children or []):
            # Try to get the type from the argument node
            arg_type = getattr(arg, 'return_type', None) or getattr(arg, 'var_type', None)
            if arg_type:
                arg_types.append(arg_type)
            else:
                # For literals, infer from the literal value
                if arg.node_type == NodeTypes.LITERAL:
                    lit_val = str(arg.value)
                    if lit_val.endswith('i8'):
                        arg_types.append('int8')
                    elif lit_val.endswith('i16'):
                        arg_types.append('int16')
                    elif lit_val.endswith('i32') or (lit_val.isdigit() and not any(x in lit_val for x in ['.', 'e', 'E'])):
                        arg_types.append('int32')
                    elif lit_val.endswith('i64'):
                        arg_types.append('int64')
                    elif lit_val.endswith('u8'):
                        arg_types.append('uint8')
                    elif lit_val.endswith('u16'):
                        arg_types.append('uint16')
                    elif lit_val.endswith('u32'):
                        arg_types.append('uint32')
                    elif lit_val.endswith('u64'):
                        arg_types.append('uint64')
                    elif lit_val.endswith('f32'):
                        arg_types.append('float32')
                    elif lit_val.endswith('f64') or any(x in lit_val for x in ['.', 'e', 'E']):
                        arg_types.append('float64')
                    elif lit_val.endswith('f128'):
                        arg_types.append('float128')
                    else:
                        arg_types.append('int32')  # Default
                elif arg.node_type == NodeTypes.IDENTIFIER:
                    # Look up in symbol table
                    sym_info = self.symbol_table.get(arg.name)
                    if sym_info:
                        arg_types.append(sym_info[0])
                    else:
                        return None
                else:
                    return None
        
        # Build type mapping
        type_map: dict[str, str] = {}
        for param_type, arg_type in zip(param_types, arg_types):
            if param_type in type_params:
                if param_type in type_map:
                    if type_map[param_type] != arg_type:
                        # Conflicting inference
                        return None
                else:
                    type_map[param_type] = arg_type
        
        # Return inferred types in parameter order
        inferred = []
        for tp in type_params:
            if tp not in type_map:
                return None
            inferred.append(type_map[tp])
        
        return inferred
    
    def _collect_generic_instances(self, node: ASTNode):
        """Recursively collect all generic function calls that need monomorphization."""
        if node.node_type == NodeTypes.FUNCTION_CALL:
            func_name = node.name
            logging.debug(f"Function call to '{func_name}', in templates: {func_name in self.generic_templates}, type_args: {getattr(node, 'type_args', None)}")
            if func_name in self.generic_templates:
                # This is a generic function call
                type_args = getattr(node, 'type_args', [])
                
                # If type arguments weren't set during parsing, try to infer them now
                if not type_args:
                    inferred = self._infer_type_args_from_call(func_name, node)
                    if inferred:
                        type_args = inferred
                        node.type_args = type_args  # Set it on the node for later
                        logging.debug(f"Inferred type args for {func_name}: {type_args}")
                
                if type_args:
                    key = (func_name, tuple(type_args))
                    if key not in self.monomorphized_funcs:
                        # Generate mangled name
                        mangled = self._mangle_generic_name(func_name, tuple(type_args))
                        self.monomorphized_funcs[key] = mangled
                        logging.debug(f"Added monomorphized {func_name} with types {type_args} as {mangled}")
        
        # Recurse into children
        for child in (node.children or []):
            if child:
                self._collect_generic_instances(child)
    
    def _instantiate_generic_function(self, func_name: str, type_args: tuple[str, ...]) -> str:
        """Generate C code for a monomorphized instance of a generic function."""
        template = self.generic_templates[func_name]
        type_params = getattr(template, 'type_params', [])
        
        # Build type substitution map
        type_map = dict(zip(type_params, type_args))
        
        # Substitute types in the function definition
        def substitute_type(t: str) -> str:
            return type_map.get(t, t)
        
        # Get return type and substitute
        ret_type_fs = template.return_type or "void"
        if template.is_array:
            ret_type_fs = ret_type_fs + "[]"
        
        # Substitute type parameters in return type
        for tp, concrete in type_map.items():
            ret_type_fs = ret_type_fs.replace(tp, concrete)
        
        ret_c = self._map_type_to_c(ret_type_fs)
        
        # Get mangled name
        mangled_name = self.monomorphized_funcs[(func_name, type_args)]
        
        # Push a new name scope for this function BEFORE building params
        self.name_scope_stack.append({})
        
        # Build parameters with substituted types
        params = []
        body_node = None
        for child in template.children:
            if child.node_type == NodeTypes.PARAMETER:
                base_type = child.var_type or "int32"
                # Substitute type parameters
                base_type = substitute_type(base_type)
                is_array_param = child.is_array
                ctype = "VArray*" if is_array_param else self._map_type_to_c(base_type)
                params.append(f"{ctype} {self._mangle_name(child.name)}")
            elif child.node_type == NodeTypes.SCOPE:
                body_node = child
        
        params_sig = ", ".join(params) if params else "void"
        
        # Save and prepare symbol table for function scope
        prev_symbols = self.symbol_table.copy()
        for child in template.children:
            if child.node_type == NodeTypes.PARAMETER:
                base_type = substitute_type(child.var_type or "int32")
                self.symbol_table[child.name] = (base_type, child.is_array)
        
        # Save current type substitution context
        prev_type_map = getattr(self, '_current_type_map', {})
        self._current_type_map = type_map
        
        # Generate body
        prev_in_fn = self._in_function
        self._in_function = True
        prev_scope_stack = self.scope_stack
        self.scope_stack = [[]]
        body_code = self._visit(body_node) if body_node else "{ }"
        
        # Restore state
        self.scope_stack = prev_scope_stack
        self._in_function = prev_in_fn
        self.symbol_table = prev_symbols
        self._current_type_map = prev_type_map
        
        # Pop the name scope for this function
        self.name_scope_stack.pop()
        
        return f"{ret_c} {mangled_name}({params_sig}) {body_code}"

    def generate(self) -> str:
        """Generate C code from the AST"""
        header = "#include <stdio.h>\n#include <stdbool.h>\n#include <stdint.h>\n#include <inttypes.h>\n#include <string.h>\n"
        header += '#include "firescript/runtime/runtime.h"\n'
        header += '#include "firescript/runtime/conversions.h"\n'
        header += '#include "firescript/runtime/varray.h"\n'
        
        # First pass: collect all generic function instantiations needed
        for child in self.ast.children:
            self._collect_generic_instances(child)
        
        # Emit class typedefs, then constant declarations, then function definitions, then the main body statements
        typedefs: list[str] = []
        constants: list[str] = []
        function_defs: list[str] = []
        main_lines: list[str] = []
        main_function_code: str | None = None  # Store the main() function separately

        # Ensure outer (main) scope exists for tracking arrays declared at top-level
        self.scope_stack = [[]]

        for child in self.ast.children:
            if child.node_type == NodeTypes.FUNCTION_DEFINITION:
                # Skip generic templates - they'll be instantiated on demand
                if hasattr(child, 'type_params') and child.type_params:
                    continue
                # Check if this is the main() function
                if child.name == "main":
                    main_function_code = self._emit_function_definition(child)
                else:
                    func_code = self._emit_function_definition(child)
                    if func_code:
                        function_defs.append(func_code)
            elif child.node_type == NodeTypes.CLASS_DEFINITION:
                typedefs.append(self._emit_class_typedef(child))
                # Emit method functions for this class
                for m in self.class_methods.get(child.name, []):
                    mcode = self._emit_method_definition(child.name, m)
                    if mcode:
                        function_defs.append(mcode)
            elif child.node_type == NodeTypes.VARIABLE_DECLARATION and getattr(child, 'is_const', False):
                # Emit const declarations as global constants
                const_code = self._emit_const_declaration(child)
                if const_code:
                    constants.append(const_code)
            else:
                stmt_code = self.emit_statement(child)
                if stmt_code:
                    main_lines.append(stmt_code)
        
        # Emit monomorphized generic function instances BEFORE main() function
        for (func_name, type_args), mangled_name in self.monomorphized_funcs.items():
            mono_code = self._instantiate_generic_function(func_name, type_args)
            if mono_code:
                function_defs.append(mono_code)
        
        # Add the main() function if it was defined
        if main_function_code:
            function_defs.append(main_function_code)

        typedefs_code = ("\n\n".join(typedefs) + "\n\n") if typedefs else ""
        constants_code = ("\n".join(constants) + "\n\n") if constants else ""
        functions_code = ("\n\n".join(function_defs) + "\n\n") if function_defs else ""

        # Only generate wrapper main() if user didn't define one
        if not main_function_code:
            main_code = "int main(void) {\n"
            if main_lines:
                indented_body = "\n".join(
                    "    " + line for line in "\n".join(main_lines).split("\n")
                )
                main_code += f"{indented_body}\n"
            # Free any arrays declared at the top level (outermost scope)
            if (not self.drops_enabled) and self.scope_stack and self.scope_stack[0]:
                for arr_name in self.scope_stack[0]:
                    main_code += f"    varray_free({arr_name});\n"
            main_code += "    firescript_cleanup();\n"
            main_code += "    return 0;\n"
            main_code += "}\n"
        else:
            main_code = ""

        return header + typedefs_code + constants_code + functions_code + main_code

    def _map_type_to_c(self, t: str) -> str:
        if t == "void":
            return "void"
        if t.endswith("[]"):
            return "VArray*"
        return FIRETYPE_TO_C.get(t, t)

    def _normalize_integer_literal(self, s: str) -> str:
        """Convert firescript integer literal (with optional suffix/underscores) to valid C."""
        # strip underscores
        s2 = s.replace("_", "")
        # strip width/unsigned suffixes
        for suf in ("i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64"):
            if s2.lower().endswith(suf):
                return s2[: -len(suf)]
        return s2

    def _normalize_float_literal(self, s: str, ftype: str | None) -> str:
        """Convert firescript float literal (with optional suffix/underscores) to valid C.
        ftype can be 'float32' | 'float64' | 'float128' or None if unknown.
        """
        s2 = s.replace("_", "")
        # Remove explicit suffix from literal text if present
        for suf in ("f128", "f64", "f32", "f"):
            if s2.lower().endswith(suf):
                s2 = s2[: -len(suf)]
                break
        # Apply C-specific suffix based on target type
        if ftype == "float32":
            return s2 + "f"
        if ftype == "float128":
            # Map to long double with L suffix
            return s2 + "L"
        # float64 (double) default: no suffix
        return s2

    def _emit_class_typedef(self, node: ASTNode) -> str:
        """Emit a C typedef struct for a class definition."""
        lines = [f"typedef struct {node.name} {{"]
        for field in node.children:
            if field.node_type == NodeTypes.CLASS_FIELD:
                ctype = self._map_type_to_c(field.var_type or "int32")
                lines.append(f"    {ctype} {field.name};")
        lines.append(f"}} {node.name};")
        return "\n".join(lines)

    def _emit_method_definition(self, class_name: str, node: ASTNode) -> str:
        """Emit a C function for a class method: ClassName_methodName(ClassName this, ...) { ... }.

        Constructors are emitted as: ClassName_ClassName(<args>) { ClassName this = (ClassName){0}; ...; return this; }
        so that `new ClassName(...)` maps cleanly to the generated function.
        """
        ret_fs = node.return_type or "void"
        if ret_fs.endswith("[]"):
            raise NotImplementedError("Array returns are not supported in methods")
        ret_c = self._map_type_to_c(ret_fs)

        is_constructor = bool(getattr(node, "is_constructor", False))

        # Push a new name scope for this method BEFORE building params
        self.name_scope_stack.append({})

        params = []
        body_node = None
        for child in node.children:
            if child.node_type == NodeTypes.PARAMETER:
                base_type = child.var_type or "int32"
                if child.is_array:
                    raise NotImplementedError("Array parameters are not supported in methods")
                ctype = self._map_type_to_c(base_type)
                if is_constructor and child.name == "this":
                    # Constructors synthesize a local `this` instance rather than taking it as a parameter.
                    # Register 'this' in the name scope without mangling since it will be a local variable
                    self.name_scope_stack[-1]["this"] = "this"
                    continue
                params.append(f"{ctype} {self._mangle_name(child.name)}")
            elif child.node_type == NodeTypes.SCOPE:
                body_node = child

        params_sig = ", ".join(params) if params else "void"

        # Prepare symbol table for method scope (register params)
        prev_symbols = self.symbol_table.copy()
        for child in node.children:
            if child.node_type == NodeTypes.PARAMETER:
                self.symbol_table[child.name] = (
                    child.var_type or "int32",
                    child.is_array,
                )

        prev_in_fn = self._in_function
        self._in_function = True
        prev_scope_stack = self.scope_stack
        self.scope_stack = [[]]
        body_code = self._visit(body_node) if body_node else "{ }"

        if is_constructor:
            # Inject a local instance for `this` and implicitly return it when the body has no explicit return.
            init_line = f"    {class_name} this = ({class_name}){{0}};"

            def _contains_return(n: ASTNode | None) -> bool:
                if n is None:
                    return False
                if n.node_type == NodeTypes.RETURN_STATEMENT:
                    return True
                for ch in (n.children or []):
                    if ch is not None and _contains_return(ch):
                        return True
                return False

            add_implicit_return = not _contains_return(body_node)

            # body_code is expected to be a '{\n...\n}' block; splice in our lines.
            if body_code.startswith("{\n") and body_code.endswith("\n}"):
                inner = body_code[len("{\n") : -len("\n}")].rstrip("\n")
                lines = ["{", init_line]
                if inner:
                    lines.append(inner)
                if add_implicit_return:
                    lines.append("    return this;")
                lines.append("}")
                body_code = "\n".join(lines)
            else:
                # Fallback: wrap the generated body in a new block.
                ret_line = "\n    return this;" if add_implicit_return else ""
                body_code = f"{{\n{init_line}\n    {body_code}{ret_line}\n}}"
        self.scope_stack = prev_scope_stack
        self._in_function = prev_in_fn
        self.symbol_table = prev_symbols

        # Pop the name scope for this method
        self.name_scope_stack.pop()

        cname = class_name
        mname = node.name
        return f"{ret_c} {cname}_{mname}({params_sig}) {body_code}"

    def _literal_to_c(self, node: ASTNode) -> str:
        """Turn a LITERAL node into a valid C expression string."""
        tok = node.token
        if tok is None:
            return ""
        t = tok.type
        # Booleans, null, and strings can be used as-is (string includes quotes)
        if t == "BOOLEAN_LITERAL":
            return tok.value
        if t == "NULL_LITERAL":
            return "NULL"
        if t == "STRING_LITERAL":
            return tok.value
        # Numbers
        if t == "INTEGER_LITERAL":
            return self._normalize_integer_literal(tok.value)
        if t in ("FLOAT_LITERAL", "DOUBLE_LITERAL"):
            # Choose target float type if known from parser
            ftype = getattr(node, "return_type", None)
            return self._normalize_float_literal(tok.value, ftype)
        return tok.value or ""

    def _emit_const_declaration(self, node: ASTNode) -> str:
        """Emit a global constant declaration in C."""
        var_type_fs = node.var_type or "float64"
        var_type_c = self._map_type_to_c(var_type_fs)
        
        # Get initializer value
        init_value = self._visit(node.children[0]) if node.children else "0"
        
        # In C, we use 'const' keyword
        return f"const {var_type_c} {self._mangle_name(node.name)} = {init_value};"

    def _emit_function_definition(self, node: ASTNode) -> str:
        # node.return_type holds the firescript return type (e.g., 'void')
        ret_fs = node.return_type or "void"
        ret_c = self._map_type_to_c(ret_fs)
        
        # Mangle the function name BEFORE pushing new scope so recursive calls can find it
        mangled_func_name = self._mangle_name(node.name)

        # Parameters are all children except the last one, which is the body scope
        params = []
        body_node = None
        
        # Push a new name scope for this function
        self.name_scope_stack.append({})
        
        for child in node.children:
            if child.node_type == NodeTypes.PARAMETER:
                base_type = child.var_type or "int32"
                is_array_param = child.is_array
                ctype = "VArray*" if is_array_param else self._map_type_to_c(base_type)
                params.append(f"{ctype} {self._mangle_name(child.name)}")
            elif child.node_type == NodeTypes.SCOPE:
                body_node = child

        params_sig = ", ".join(params) if params else "void"

        # Save and prepare symbol table for function scope (register params)
        prev_symbols = self.symbol_table.copy()
        for child in node.children:
            if child.node_type == NodeTypes.PARAMETER:
                self.symbol_table[child.name] = (
                    child.var_type or "int32",
                    child.is_array,
                )

        # Mark we are in a function for return cleanup logic
        prev_in_fn = self._in_function
        self._in_function = True
        # Reset scope stack for the function body (fresh nested scopes inside function)
        prev_scope_stack = self.scope_stack
        self.scope_stack = [[]]
        body_code = self._visit(body_node) if body_node else "{ }"
        # At function end, append frees if drops are not enabled
        if (not self.drops_enabled) and body_code.startswith("{") and body_code.endswith("}") and self.scope_stack and self.scope_stack[0]:
            # No dynamic array cleanup needed for fixed arrays
            body_code = body_code
        # Restore state
        self.scope_stack = prev_scope_stack
        self._in_function = prev_in_fn

        # Restore symbol table after emitting function
        self.symbol_table = prev_symbols

        # Pop the name scope for this function
        self.name_scope_stack.pop()

        return f"{ret_c} {mangled_func_name}({params_sig}) {body_code}"

    def emit_statement(self, node: ASTNode) -> str:
        """
        Generate code for a node that represents a statement.
        Automatically appends a semicolon if one is not already present.
        """
        # (Previously special handling for big number assignments removed)

        code = self._visit(node)
        # Only add semicolon if needed. Special-case return statements whose expression may end with '}'
        if code:
            stripped = code.strip()
            needs_semicolon = True
            if stripped.endswith(";"):
                needs_semicolon = False
            elif stripped.endswith("}"):
                # Do not add semicolons after blocks, but ensure assignment statements
                # that produce compound literals do get a semicolon.
                if node.node_type in (NodeTypes.SCOPE, NodeTypes.IF_STATEMENT, NodeTypes.ELSE_STATEMENT, NodeTypes.ELIF_STATEMENT, NodeTypes.WHILE_STATEMENT):
                    needs_semicolon = False
                elif node.node_type in (NodeTypes.VARIABLE_ASSIGNMENT, NodeTypes.ASSIGNMENT, NodeTypes.RETURN_STATEMENT):
                    needs_semicolon = True
                else:
                    needs_semicolon = True
            elif stripped.startswith("#"):
                needs_semicolon = False
            if needs_semicolon:
                code += ";"
        return code

    def _visit(self, node: ASTNode) -> str:
        if node.node_type == NodeTypes.ROOT:
            lines = []
            for child in node.children:
                # Assume all top-level nodes are statements.
                if child.node_type == NodeTypes.FUNCTION_DEFINITION:
                    # Functions are emitted separately by generate()
                    continue
                stmt_code = self.emit_statement(child)
                if stmt_code:
                    lines.append(stmt_code)
            return "\n".join(lines)
        elif node.node_type == NodeTypes.SCOPE:
            # Enter new scope for tracking arrays
            self.scope_stack.append([])
            lines = []
            for child in node.children:
                # In scopes, each child is a statement.
                stmt_code = self.emit_statement(child)
                if stmt_code:
                    lines.append(stmt_code)
            # Append frees for arrays declared in this scope only when drops not enabled
            _ = list(self.scope_stack.pop())
            # NOTE: arrays are only freed at the top level to avoid premature frees when arrays escape via returns.
            return "{\n" + "\n".join("    " + line for line in lines) + "\n}"
        elif node.node_type == NodeTypes.ARRAY_LITERAL:
            # Array literals are typically handled in variable declarations for correct element typing.
            # If evaluated as an expression directly, return a placeholder.
            return "/* array literal */"

        elif node.node_type == NodeTypes.VARIABLE_DECLARATION:
            var_type_fs = node.var_type or "int32"
            # Apply type substitution if we're in a generic function
            if hasattr(self, '_current_type_map') and self._current_type_map:
                var_type_fs = self._current_type_map.get(var_type_fs, var_type_fs)
            var_type_c = self._map_type_to_c(var_type_fs)
            self.symbol_table[node.name] = (var_type_fs, node.is_array)

            if node.is_array:
                # Dynamic array (VArray*)
                self.scope_stack[-1].append(node.name)
                init_node = node.children[0] if node.children else None
                elem_c = self._map_type_to_c(var_type_fs)
                if init_node and init_node.node_type == NodeTypes.ARRAY_LITERAL:
                    elements = init_node.children or []
                    n = len(elements)
                    lines: list[str] = []
                    mangled_name = self._mangle_name(node.name)
                    lines.append(f"VArray* {mangled_name} = varray_create({n}, sizeof({elem_c}));")
                    for idx, elem in enumerate(elements):
                        elem_code = self._visit(elem)
                        tmp_name = f"{mangled_name}_elem{idx}"
                        lines.append(f"{elem_c} {tmp_name} = {elem_code};")
                        lines.append(f"varray_append({mangled_name}, &{tmp_name});")
                    return "\n".join(lines)
                # Allow initializing from an expression (e.g., function returning an array)
                init_value = self._visit(node.children[0]) if node.children else "NULL"
                return f"VArray* {self._mangle_name(node.name)} = {init_value};"
            else:
                init_value = self._visit(node.children[0]) if node.children else "0"
                return f"{var_type_c} {self._mangle_name(node.name)} = {init_value};"
        elif node.node_type == NodeTypes.ARRAY_ACCESS:
            # Dynamic array access: ((T*)(arr->data))[idx]
            array_node = node.children[0]
            index_node = node.children[1]
            array_code = self._visit(array_node)
            index_code = self._visit(index_node)

            elem_fs: str | None = getattr(array_node, "var_type", None)
            if not (getattr(array_node, "is_array", False) and elem_fs):
                rt = getattr(array_node, "return_type", None)
                if isinstance(rt, str) and rt.endswith("[]"):
                    elem_fs = rt[:-2]

            elem_c = self._map_type_to_c(elem_fs or "int32")
            return f"(({elem_c}*)({array_code}->data))[{index_code}]"
        elif node.node_type == NodeTypes.LITERAL:
            return self._literal_to_c(node)
        elif node.node_type == NodeTypes.CAST_EXPRESSION:
            expr_node = node.children[0] if node.children else None
            expr_code = self._visit(expr_node) if expr_node is not None else ""
            target_fs = node.name
            target_c = self._map_type_to_c(target_fs)
            return f"(({target_c})({expr_code}))"
        elif node.node_type == NodeTypes.BINARY_EXPRESSION:
            # Generic arithmetic or string concatenation
            left_node, right_node = node.children
            left = self._visit(left_node)
            right = self._visit(right_node)
            op = node.name
            # String concatenation with '+'
            left_t = (
                getattr(left_node, "return_type", None)
                or getattr(left_node, "var_type", None)
                or (self.symbol_table.get(getattr(left_node, "name", ""), (None, False))[0]
                   if left_node.node_type == NodeTypes.IDENTIFIER else None)
            )
            right_t = (
                getattr(right_node, "return_type", None)
                or getattr(right_node, "var_type", None)
                or (self.symbol_table.get(getattr(right_node, "name", ""), (None, False))[0]
                   if right_node.node_type == NodeTypes.IDENTIFIER else None)
            )
            if op == "+" and (left_t == "string" or right_t == "string"):
                lcode = left
                rcode = right
                if left_t != "string":
                    lcode = f"firescript_toString({left})"
                if right_t != "string":
                    rcode = f"firescript_toString({right})"
                return f"firescript_strcat({lcode}, {rcode})"
            # Numeric or generic binary op fallback
            return f"({left} {op} {right})"
        
        elif node.node_type == NodeTypes.UNARY_EXPRESSION:
            op = node.name
            
            # Increment/decrement operators (++/--) have no children
            if op in ("++", "--"):
                var_name = node.token.value if hasattr(node.token, 'value') else ""
                mangled_var_name = self._mangle_name(var_name)
                return f"{mangled_var_name}{op}"
            
            # Unary +/- operators have a child operand
            if not node.children:
                return ""  # Shouldn't happen, but safety check
                
            operand_node = node.children[0]
            operand = self._visit(operand_node)
            # Unary operators: + is no-op, - negates
            if op == "-":
                return f"(-{operand})"
            elif op == "+":
                return f"(+{operand})"
            else:
                return operand  # Fallback
        
        elif node.node_type == NodeTypes.METHOD_CALL:
            object_node = node.children[0]
            object_code = self._visit(object_node)
            method_name = node.name
            obj_type = (
                getattr(object_node, "return_type", None)
                or (
                    f"{getattr(object_node, 'var_type', None)}[]"
                    if getattr(object_node, "is_array", False) and getattr(object_node, "var_type", None)
                    else getattr(object_node, "var_type", None)
                )
            )
            if isinstance(obj_type, str) and obj_type.endswith("[]"):
                if method_name in ("length", "size"):
                    return f"(int32_t)({object_code}->size)"
                # Minimal support for common mutators (used by some examples)
                if method_name == "append":
                    arg = node.children[1] if len(node.children) > 1 else None
                    elem_fs = obj_type[:-2]
                    elem_c = self._map_type_to_c(elem_fs)
                    tmp = f"__tmp_{self.array_temp_counter}"
                    self.array_temp_counter += 1
                    arg_code = self._visit(arg) if arg is not None else "0"
                    return f"({{{elem_c} {tmp} = {arg_code}; {object_code} = varray_append({object_code}, &{tmp}); {object_code};}})"
                if method_name == "insert":
                    arg_idx = node.children[1] if len(node.children) > 1 else None
                    arg_val = node.children[2] if len(node.children) > 2 else None
                    elem_fs = obj_type[:-2]
                    elem_c = self._map_type_to_c(elem_fs)
                    tmp = f"__tmp_{self.array_temp_counter}"
                    self.array_temp_counter += 1
                    idx_code = self._visit(arg_idx) if arg_idx is not None else "0"
                    val_code = self._visit(arg_val) if arg_val is not None else "0"
                    return f"({{{elem_c} {tmp} = {val_code}; {object_code} = varray_insert({object_code}, (size_t)({idx_code}), &{tmp}); {object_code};}})"
                if method_name == "clear":
                    return f"(varray_clear({object_code}), ({object_code}))"
                raise NotImplementedError(f"Array method '{method_name}' is not supported")
            # Class instance method call -> dispatch to free function Class_method(self, ...)
            # Determine class name from object expression type
            obj_type = (
                getattr(object_node, "var_type", None)
                or getattr(object_node, "return_type", None)
            )
            if obj_type in self.class_names:
                args_code = [self._visit(child) for child in node.children[1:]]
                return f"{obj_type}_{method_name}({object_code}{(', ' + ', '.join(args_code)) if args_code else ''})"
            # Fallback (shouldn't happen if type checking is correct)
            args_code = [self._visit(child) for child in node.children[1:]]
            return f"{object_code}.{method_name}({', '.join(args_code)})"
        elif node.node_type == NodeTypes.FIELD_ACCESS:
            # Emit obj.field
            obj_code = self._visit(node.children[0]) if node.children else ""
            return f"{obj_code}.{node.name}"
        elif node.node_type == NodeTypes.IDENTIFIER:
            return self._mangle_name(node.name)
        elif node.node_type == NodeTypes.VARIABLE_ASSIGNMENT:
            # Simple assignment to identifier from expression
            name = node.name
            mangled_name = self._mangle_name(name)
            value_code = self._visit(node.children[0]) if node.children else "0"
            # If variable not yet declared, attempt implicit declaration using RHS type
            if name not in self.symbol_table:
                rhs = node.children[0] if node.children else None
                rhs_type_fs = getattr(rhs, "return_type", None) if rhs is not None else None
                if rhs_type_fs is None and rhs is not None and rhs.node_type == NodeTypes.FUNCTION_CALL and rhs.name in getattr(self, "class_names", set()):
                    rhs_type_fs = rhs.name
                if isinstance(rhs_type_fs, str) and rhs_type_fs.endswith("[]"):
                    elem_fs = rhs_type_fs[:-2]
                    self.symbol_table[name] = (elem_fs, True)
                    self.scope_stack[-1].append(name)
                    return f"VArray* {mangled_name} = {value_code}"
                # If still unknown, fall back to int32
                fs_type = rhs_type_fs or "int32"
                c_type = self._map_type_to_c(fs_type)
                # Record in symbol table for subsequent uses
                self.symbol_table[name] = (fs_type, False)
                return f"{c_type} {mangled_name} = {value_code}"
            return f"{mangled_name} = {value_code}"
        elif node.node_type == NodeTypes.ASSIGNMENT:
            # General assignment: lhs can be identifier, field access, or array access
            lhs = node.children[0] if node.children else None
            rhs = node.children[1] if node.children and len(node.children) > 1 else None
            lhs_code = self._visit(lhs) if lhs else ""
            rhs_code = self._visit(rhs) if rhs else "0"
            return f"{lhs_code} = {rhs_code}"
        elif node.node_type == NodeTypes.RETURN_STATEMENT:
            # Return with or without expression
            if node.children:
                expr_code = (
                    self._visit(node.children[0])
                    if node.children[0] is not None
                    else ""
                )
                # Free arrays in all active scopes before returning from a function
                cleanup_lines = []
                if (not self.drops_enabled) and self._in_function:
                    cleanup_lines = self._free_arrays_in_all_active_scopes()
                if cleanup_lines:
                    cleanup = "\n".join(cleanup_lines)
                    return f"{{\n{cleanup}\nreturn {expr_code};\n}}"
                return f"return {expr_code}"
            # bare return
            cleanup_lines = []
            if (not self.drops_enabled) and self._in_function:
                cleanup_lines = self._free_arrays_in_all_active_scopes()
            if cleanup_lines:
                cleanup = "\n".join(cleanup_lines)
                return f"{{\n{cleanup}\nreturn;\n}}"
            return "return"
        elif node.node_type == NodeTypes.FUNCTION_CALL:
            # Positional constructors for classes (no zero-arg default): map args by field order
            if node.name in getattr(self, "class_names", set()):
                args = [self._visit(arg) for arg in node.children]
                fields = self.class_fields.get(node.name, [])
                inits = []
                for (fname, _ftype), val in zip(fields, args):
                    inits.append(f".{fname} = {val}")
                init_str = ", ".join(inits)
                return f"({node.name}){{ {init_str} }}"
            if node.name == "print":
                arg = node.children[0]
                arg_code = self._visit(arg)
                # Array length/size prints as integer
                if arg.node_type == NodeTypes.METHOD_CALL and arg.name in ("length", "size"):
                    return f'printf("%d\\n", {arg_code})'

                # Detect dynamic arrays (VArray*) and print inline
                is_arr = False
                elem_type_for_array = None
                if arg.node_type == NodeTypes.IDENTIFIER:
                    elem_type_for_array, is_arr = self.symbol_table.get(arg.name, (None, False))
                    if is_arr:
                        elem_c = self._map_type_to_c(elem_type_for_array or "int32")
                        length_expr = f"{arg_code}->size"
                        elem_expr = f"(({elem_c}*)({arg_code}->data))[__i]"
                        lines = []
                        lines.append('printf("[");')
                        lines.append(f"for (size_t __i = 0; __i < {length_expr}; ++__i) {{")
                        if elem_type_for_array == "bool":
                            lines.append(f'    printf("%s", {elem_expr} ? "true" : "false");')
                        elif elem_type_for_array == "string":
                            lines.append(f'    printf("%s", {elem_expr});')
                        elif elem_type_for_array == "int8":
                            lines.append(f'    printf("%" PRId8, (int8_t){elem_expr});')
                        elif elem_type_for_array == "int16":
                            lines.append(f'    printf("%" PRId16, (int16_t){elem_expr});')
                        elif elem_type_for_array == "int32":
                            lines.append(f'    printf("%" PRId32, (int32_t){elem_expr});')
                        elif elem_type_for_array == "int64":
                            lines.append(f'    printf("%" PRId64, (int64_t){elem_expr});')
                        elif elem_type_for_array == "uint8":
                            lines.append(f'    printf("%" PRIu8, (uint8_t){elem_expr});')
                        elif elem_type_for_array == "uint16":
                            lines.append(f'    printf("%" PRIu16, (uint16_t){elem_expr});')
                        elif elem_type_for_array == "uint32":
                            lines.append(f'    printf("%" PRIu32, (uint32_t){elem_expr});')
                        elif elem_type_for_array == "uint64":
                            lines.append(f'    printf("%" PRIu64, (uint64_t){elem_expr});')
                        elif elem_type_for_array in ("float32", "float64"):
                            lines.append(f'    printf("%f", {elem_expr});')
                        elif elem_type_for_array == "float128":
                            buf_name = f"__ldbuf_{self.array_temp_counter}"
                            self.array_temp_counter += 1
                            lines.append(f"    char {buf_name}[128];")
                            lines.append(f"    firescript_format_long_double({buf_name}, sizeof({buf_name}), {elem_expr});")
                            lines.append(f"    printf(\"%s\", {buf_name});")
                        else:
                            lines.append('    printf("%s", "<unknown>");')
                        lines.append(f'    if (__i + 1 < {length_expr}) printf(", ");')
                        lines.append("}")
                        lines.append('printf("]\\n");')
                        return "\n".join(lines)

                arg_type = getattr(arg, "return_type", None)

                if arg_type is None:
                    if (
                        arg.node_type == NodeTypes.LITERAL and arg.token
                    ):  # Check token exists
                        if arg.token.type == "BOOLEAN_LITERAL":
                            arg_type = "bool"
                        elif arg.token.type == "STRING_LITERAL":
                            arg_type = "string"
                        elif arg.token.type == "INTEGER_LITERAL":
                            arg_type = "int32"  # default inference
                        elif arg.token.type == "FLOAT_LITERAL":
                            arg_type = "float32"
                        elif arg.token.type == "DOUBLE_LITERAL":
                            arg_type = "float64"
                    elif arg.node_type == NodeTypes.IDENTIFIER:
                        arg_type, _ = self.symbol_table.get(arg.name, (None, False))
                    elif arg.node_type == NodeTypes.ARRAY_ACCESS:
                        arr_node = arg.children[0]
                        # Ensure arr_node.var_type is populated by type resolution
                        arg_type = (
                            arr_node.var_type if hasattr(arr_node, "var_type") else None
                        )

                # Fix all printf/gmp_printf calls to ensure newlines are properly escaped
                # and string literals don't contain actual newlines
                if arg_type == "bool":
                    return f'printf("%s\\n", {arg_code} ? "true" : "false")'
                # Width-correct integer printing
                if arg_type == "int8":
                    return f'printf("%" PRId8 "\\n", (int8_t){arg_code})'
                if arg_type == "int16":
                    return f'printf("%" PRId16 "\\n", (int16_t){arg_code})'
                if arg_type == "int32":
                    return f'printf("%" PRId32 "\\n", (int32_t){arg_code})'
                if arg_type == "int64":
                    return f'printf("%" PRId64 "\\n", (int64_t){arg_code})'
                if arg_type == "uint8":
                    return f'printf("%" PRIu8 "\\n", (uint8_t){arg_code})'
                if arg_type == "uint16":
                    return f'printf("%" PRIu16 "\\n", (uint16_t){arg_code})'
                if arg_type == "uint32":
                    return f'printf("%" PRIu32 "\\n", (uint32_t){arg_code})'
                if arg_type == "uint64":
                    return f'printf("%" PRIu64 "\\n", (uint64_t){arg_code})'

                if arg_type in ("float32", "float64"):
                    return f'printf("%f\\n", {arg_code})'
                if arg_type == "float128":
                    return f'firescript_print_long_double({arg_code})'
                if arg_type == "string":
                    return f'printf("%s\\n", {arg_code})'

                return f'printf("%s\\n", {arg_code})'  # Last resort
            elif node.name == "drop":
                # Fixed-size arrays are copyable; drop is a no-op
                return "/* drop noop */"
            elif node.name == "input":
                return f"firescript_input({self._visit(node.children[0])})"
            elif node.name == "int":
                # Cast to a native C integer
                arg_code = self._visit(node.children[0])
                return f"firescript_toInt({arg_code})"

            elif node.name == "toInt":
                return f"firescript_toInt({self._visit(node.children[0])})"
            elif node.name == "toFloat":
                return f"firescript_toFloat({self._visit(node.children[0])})"
            elif node.name == "toDouble":
                return f"firescript_toDouble({self._visit(node.children[0])})"
            elif node.name == "toString":
                return f"firescript_toString({self._visit(node.children[0])})"
            elif node.name == "toChar":
                return f"firescript_toChar({self._visit(node.children[0])})"
            elif node.name == "toBool":
                return f"firescript_toBool({self._visit(node.children[0])})"
            else:
                # Check if this is a generic function call
                func_name = node.name
                type_args = getattr(node, 'type_args', [])
                
                if type_args and func_name in self.generic_templates:
                    # Use the mangled name for generic function
                    key = (func_name, tuple(type_args))
                    if key in self.monomorphized_funcs:
                        mangled_name = self.monomorphized_funcs[key]
                        args = ", ".join(self._visit(arg) for arg in node.children)
                        return f"{mangled_name}({args})"
                
                # Regular function call
                args = ", ".join(self._visit(arg) for arg in node.children)
                return f"{self._mangle_name(node.name)}({args})"
        elif node.node_type == NodeTypes.TYPE_METHOD_CALL:
            # Dispatch to generated constructor/static function: Class_method(args)
            class_name = getattr(node, "class_name", "")
            args = ", ".join(self._visit(arg) for arg in node.children)
            return f"{class_name}_{node.name}({args})"
        elif node.node_type == NodeTypes.CONSTRUCTOR_CALL:
            # new Class(args) -> call generated function Class_Class(args)
            args = [self._visit(arg) for arg in node.children]
            cname = node.name
            arglist = ", ".join(args)
            return f"{cname}_{cname}({arglist})"
        elif node.node_type == NodeTypes.SUPER_CALL:
            super_class = getattr(node, "super_class", None)
            if not super_class:
                return "/* invalid super call */"
            args_code = [self._visit(arg) for arg in (node.children or [])]

            # `this.super(...)` constructor chaining: call base constructor and copy base fields onto derived `this`
            tmp = f"__super_tmp_{self.array_temp_counter}"
            self.array_temp_counter += 1
            fields = self.class_fields.get(super_class, [])
            call = f"{super_class}_{super_class}({', '.join(args_code)})"
            lines: list[str] = []
            lines.append(f"{super_class} {tmp} = {call};")
            for fname, _ftype in fields:
                lines.append(f"this.{fname} = {tmp}.{fname};")
            inner = "\n".join("    " + l for l in lines)
            return "{\n" + inner + "\n}"
        elif node.node_type == NodeTypes.IF_STATEMENT:
            # The first child is the condition, the second is the then-branch,
            # and the optional third child is the else-branch.
            condition_code = self._visit(node.children[0])
            then_code = self._visit(node.children[1])
            code = f"if ({condition_code}) {then_code}"
            if len(node.children) > 2 and node.children[2]:
                else_code = self._visit(node.children[2])
                code += f" else {else_code}"
            return code
        elif node.node_type == NodeTypes.ELIF_STATEMENT:
            # The first child is the condition, the second is the then-branch.
            condition_code = self._visit(node.children[0])
            then_code = self._visit(node.children[1])
            code = f"else if ({condition_code}) {then_code}"
            return code
        elif node.node_type == NodeTypes.ELSE_STATEMENT:
            # The only child is the else-branch.
            return f"else {self._visit(node.children[0])}"
        elif node.node_type == NodeTypes.EQUALITY_EXPRESSION:  # ==, !=
            leftNode = node.children[0]
            rightNode = node.children[1]
            left = self._visit(leftNode)
            right = self._visit(rightNode)

            # Get the types properly from symbol table or return_type (Copyable only now)
            left_type = getattr(leftNode, "var_type", None) or (
                self.symbol_table.get(leftNode.name, (None, False))[0]
                if leftNode.node_type == NodeTypes.IDENTIFIER
                else getattr(leftNode, "return_type", None)
            )
            right_type = getattr(rightNode, "var_type", None) or (
                self.symbol_table.get(rightNode.name, (None, False))[0]
                if rightNode.node_type == NodeTypes.IDENTIFIER
                else getattr(rightNode, "return_type", None)
            )

            if left_type in ("int", "float", "double") or right_type in (
                "int",
                "float",
                "double",
            ):
                op = node.name
                return f"({left} {op} {right})"

            # String comparison unchanged
            if (
                leftNode.token
                and leftNode.token.type == "STRING_LITERAL"
                or leftNode.return_type == "string"
                or leftNode.var_type == "string"
            ):
                if (
                    rightNode.token
                    and rightNode.token.type == "STRING_LITERAL"
                    or rightNode.return_type == "string"
                    or rightNode.var_type == "string"
                ):
                    node.return_type = "bool"
                    return f"firescript_strcmp({left}, {right})"
                else:
                    raise ValueError("temp: Cannot compare string with non-string type")
            # Default comparison for Copyables
            op = node.name
            return f"({left} {op} {right})"
        elif node.node_type == NodeTypes.WHILE_STATEMENT:
            condition_code = self._visit(node.children[0])
            body_code = self._visit(node.children[1])
            return f"while ({condition_code}) {body_code}"
        elif node.node_type == NodeTypes.BREAK_STATEMENT:
            # On break, free arrays declared in current scope so far
            cleanup_lines = self._free_arrays_in_current_scope()
            if cleanup_lines:
                cleanup = "\n".join(cleanup_lines)
                return f"{{\n{cleanup}\nbreak;\n}}"
            return "break"
        elif node.node_type == NodeTypes.CONTINUE_STATEMENT:
            # On continue, free arrays declared in current scope so far
            cleanup_lines = self._free_arrays_in_current_scope()
            if cleanup_lines:
                cleanup = "\n".join(cleanup_lines)
                return f"{{\n{cleanup}\ncontinue;\n}}"
            return "continue"
        elif node.node_type == NodeTypes.RELATIONAL_EXPRESSION:
            leftNode, rightNode = node.children
            left = self._visit(leftNode)
            right = self._visit(rightNode)
            op = node.name
            # Get the types properly from symbol table or return_type
            left_type = (
                getattr(leftNode, "var_type", None)
                or self.symbol_table.get(leftNode.name, (None, False))[0]
                if leftNode.node_type == NodeTypes.IDENTIFIER
                else getattr(leftNode, "return_type", None)
            )
            right_type = (
                getattr(rightNode, "var_type", None)
                or self.symbol_table.get(rightNode.name, (None, False))[0]
                if rightNode.node_type == NodeTypes.IDENTIFIER
                else getattr(rightNode, "return_type", None)
            )

            # Copyable numeric or fallback comparison
            return f"({left} {op} {right})"
        elif node.node_type == NodeTypes.COMPOUND_ASSIGNMENT:
            identifier = node.name
            mangled_identifier = self._mangle_name(identifier)
            op = getattr(node.token, "type", None)
            value = self._visit(node.children[0])
            var_type = self.symbol_table.get(identifier, (None, False))[0]
            # Map firescript compound assignment operators to C operators (Copyable only)
            op_map = {
                "ADD_ASSIGN": "+=",
                "SUBTRACT_ASSIGN": "-=",
                "MULTIPLY_ASSIGN": "*=",
                "DIVIDE_ASSIGN": "/=",
                "MODULO_ASSIGN": "%=",
            }
            c_op = op_map.get(op or "", "+=")  # Default to += if unknown or op is None
            return f"{mangled_identifier} {c_op} {value};"

        elif node.node_type == NodeTypes.UNARY_EXPRESSION:
            if not node.token or not hasattr(node.token, "value"):
                raise ValueError("Missing token value in unary expression")
            identifier = node.token.value
            mangled_identifier = self._mangle_name(identifier)
            op = node.name
            var_type = self.symbol_table.get(identifier, (None, False))[0]
            if op == "++":
                return f"{mangled_identifier}++"
            elif op == "--":
                return f"{mangled_identifier}--"
            else:
                raise ValueError(f"Unrecognized unary operator '{op}' for {identifier}")
        else:
            return ""
