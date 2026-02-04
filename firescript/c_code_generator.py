# firescript/c_code_generator.py
from enums import NodeTypes  # [firescript/enums.py]
from parser import ASTNode, get_line_and_coumn_from_index, get_line  # [firescript/parser.py]
from utils.type_utils import is_copyable, is_owned, register_class
from typing import Optional
import logging
import sys
import os

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
    def __init__(self, ast: ASTNode, source_file: Optional[str] = None):
        self.ast = ast
        self.source_file = source_file
        self.source_code: Optional[str] = None
        self.symbol_table: dict[str, tuple[str, bool]] = {}  # (type, is_array)
        # Fixed-size array lengths by variable name
        self.array_lengths: dict[str, int] = {}
        self.array_temp_counter = (
            0  # Counter for generating unique array variable names
        )
        # Track owned values (strings, arrays, non-copyable classes) declared per lexical scope
        # to free them at scope exit. Each element is a list of (var_name, var_type) tuples.
        self.scope_stack: list[list[tuple[str, str]]] = [[]]
        # Track whether we're currently visiting inside a function body
        self._in_function: bool = False
        
        # Get the entry file path from the root AST (set during import merge)
        entry_file = getattr(self.ast, "entry_file", None)
        
        # Build per-file directive maps
        # Map: file_path -> set of enabled directive names
        # Normalize paths to ensure consistent lookups regardless of how the file was specified
        self.file_directives: dict[str, set[str]] = {}
        for c in (self.ast.children or []):
            if c.node_type == NodeTypes.DIRECTIVE:
                directive_name = getattr(c, "name", "")
                source_file = getattr(c, "source_file", entry_file or source_file)
                # Normalize the path for consistent lookup (use abspath to handle relative vs absolute)
                normalized_source = os.path.abspath(source_file) if source_file else source_file
                if normalized_source not in self.file_directives:
                    self.file_directives[normalized_source] = set()
                self.file_directives[normalized_source].add(directive_name)
        
        # For backward compatibility, check entry file directives
        normalized_entry = os.path.abspath(entry_file or source_file) if (entry_file or source_file) else None
        entry_directives = self.file_directives.get(normalized_entry, set()) if normalized_entry else set()
        self.drops_enabled: bool = "enable_drops" in entry_directives
        self.stdout_enabled: bool = "enable_lowlevel_stdout" in entry_directives
        
        # Name mangling support: map original names to mangled names
        self.name_counter = 0
        self.mangled_names: dict[str, str] = {}
        # Stack of name scopes for nested functions/blocks
        self.name_scope_stack: list[dict[str, str]] = [{}]
        # Built-in functions that shouldn't be mangled
        self.builtin_names = {"stdout", "input", "drop"}
        
        # Collect class names and metadata for constructors and methods
        self.class_names: set[str] = set()
        self.class_fields: dict[str, list[tuple[str, str]]] = {}
        self.class_methods: dict[str, list[ASTNode]] = {}
        for c in (self.ast.children or []):
            if c.node_type == NodeTypes.CLASS_DEFINITION:
                self.class_names.add(c.name)
                # Register class with type_utils
                is_copyable_class = getattr(c, "is_copyable", False)
                register_class(c.name, is_copyable_class)
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

    def error(self, text: str, node: Optional[ASTNode] = None):
        """Report a compilation error with source location"""
        if node is None:
            logging.error(text)
            return
        
        # Get source file and source code for this node
        node_source_file = getattr(node, 'source_file', self.source_file)
        source_map = getattr(self.ast, 'source_map', {})
        node_source_code = source_map.get(node_source_file) if source_map else None
        
        # Fall back to main source if not in map
        if node_source_code is None:
            node_source_code = self.source_code
            node_source_file = self.source_file
        
        if node_source_file is None or node_source_code is None:
            logging.error(text)
            return

        try:
            line_num, column_num = get_line_and_coumn_from_index(node_source_code, node.index)
            line_text = get_line(node_source_code, line_num)
            logging.error(
                text
                + f"\n> {line_text.strip()}\n"
                + " " * (column_num + 1)
                + "^"
                + f"\n({node_source_file}:{line_num}:{column_num})"
            )
        except (IndexError, ValueError):
            # Node index is out of range - just show the error without source location
            logging.error(text)

    def _free_arrays_in_current_scope(self) -> list[str]:
        """Return lines to free owned values declared in the current scope (no pop)."""
        if not self.scope_stack:
            return []
        
        cleanup_lines = []
        # Current scope is the last element in scope_stack
        for var_name, var_type in self.scope_stack[-1]:
            # Generate firescript_free call for each owned value
            cleanup_lines.append(f"firescript_free({var_name});")
        
        return cleanup_lines

    def _free_arrays_in_all_active_scopes(self, exclude_var: str = None) -> list[str]:
        """Return lines to free owned values declared in all active scopes (for early returns).
        
        Args:
            exclude_var: Optional mangled variable name to exclude from cleanup (e.g., the returned value)
        """
        if not self.scope_stack:
            return []
        
        cleanup_lines = []
        # Free from innermost to outermost scope (reverse order of allocation)
        for scope in reversed(self.scope_stack):
            for var_name, var_type in reversed(scope):
                # Skip the variable being returned (ownership transfers to caller)
                if exclude_var and var_name == exclude_var:
                    continue
                cleanup_lines.append(f"firescript_free({var_name});")
        
        return cleanup_lines

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
        # Replace [] with _arr for C-safe names
        safe_types = [t.replace("[]", "_arr") for t in type_args]
        type_suffix = "$".join(safe_types)
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
            logging.debug(f"Processing arg: {arg.node_type}, name={getattr(arg, 'name', None)}, is_array={getattr(arg, 'is_array', None)}")
            # Try to get the type from the argument node
            arg_type = getattr(arg, 'return_type', None) or getattr(arg, 'var_type', None)
            # Check if it's an array identifier
            if arg.node_type == NodeTypes.IDENTIFIER and getattr(arg, 'is_array', False):
                # It's an array - append []
                arg_type = f"{arg_type}[]"
            
            # Apply type parameter substitution if we're in a monomorphization context
            if arg_type:
                type_map = getattr(self, '_current_type_map', {})
                logging.debug(f"  Trying to substitute arg_type={arg_type}, type_map={type_map}")
                if type_map and arg_type in type_map:
                    original_arg_type = arg_type
                    arg_type = type_map[arg_type]
                    logging.debug(f"  Substituted arg_type from {original_arg_type} to {arg_type}")
            
            if arg_type:
                logging.debug(f"  Got arg_type from node: {arg_type}")
                arg_types.append(arg_type)
            else:
                # For literals, infer from the literal value
                if arg.node_type == NodeTypes.LITERAL:
                    lit_val = str(getattr(arg, 'value', ''))
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
                    logging.debug(f"Looking up {arg.name} in symbol table: {sym_info}")
                    if sym_info:
                        # sym_info is (type, is_array, [optional_size])
                        base_type = sym_info[0]
                        is_arr = sym_info[1] if len(sym_info) > 1 else False
                        
                        # Apply type parameter substitution if we're in a monomorphization context
                        type_map = getattr(self, '_current_type_map', {})
                        logging.debug(f"Type map for substitution: {type_map}, base_type: {base_type}")
                        if type_map and base_type in type_map:
                            base_type = type_map[base_type]
                            logging.debug(f"Substituted to: {base_type}")
                        
                        if is_arr:
                            arg_types.append(f"{base_type}[]")
                        else:
                            arg_types.append(base_type)
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
        """Recursively collect all generic function calls that need monomorphization.
        
        Skip collecting from inside generic function templates during initial pass,
        since type parameters haven't been substituted yet. They'll be collected
        during instantiation when the type_map is active.
        """
        # Skip generic function templates during initial pass (when type_map is not set)
        if node.node_type == NodeTypes.FUNCTION_DEFINITION:
            if hasattr(node, 'type_params') and node.type_params:
                # Only collect from template if we're in an instantiation context (type_map is active)
                if not getattr(self, '_current_type_map', {}):
                    logging.debug(f"Skipping collection from generic template {node.name} (no type_map)")
                    return
        
        if node.node_type == NodeTypes.FUNCTION_CALL:
            func_name = node.name
            logging.debug(f"Function call to '{func_name}', in templates: {func_name in self.generic_templates}, type_args: {getattr(node, 'type_args', None)}")
            if func_name in self.generic_templates:
                # This is a generic function call
                type_args = getattr(node, 'type_args', [])
                
                # If type arguments weren't set during parsing, try to infer them now
                # Always re-infer if we're in a monomorphization context (type_map is set)
                # since the same generic function in different instantiations may have different concrete types
                if not type_args or getattr(self, '_current_type_map', {}):
                    inferred = self._infer_type_args_from_call(func_name, node)
                    logging.debug(f"Inferred type args for {func_name}: {inferred}")
                    if inferred:
                        type_args = inferred
                        logging.debug(f"Using inferred type args for {func_name}: {type_args}")
                
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
                # For arrays, pass pointer to first element
                ctype = f"{self._map_type_to_c(base_type)}*" if is_array_param else self._map_type_to_c(base_type)
                params.append(f"{ctype} {self._mangle_name(child.name)}")
            elif child.node_type == NodeTypes.SCOPE:
                body_node = child
        
        params_sig = ", ".join(params) if params else "void"
        
        # Save and prepare symbol table for function scope
        prev_symbols = self.symbol_table.copy()
        # Store array sizes from call site
        array_size_map = {}
        for child in template.children:
            if child.node_type == NodeTypes.PARAMETER:
                base_type = substitute_type(child.var_type or "int32")
                # Check if the substituted type is an array
                param_is_array = base_type.endswith("[]")
                if param_is_array:
                    # Remove [] from base_type for element type
                    elem_type = base_type[:-2]
                    # For now, we can't know the size of array parameters
                    # Store with no size (None)
                    self.symbol_table[child.name] = (elem_type, True, None)
                else:
                    self.symbol_table[child.name] = (base_type, child.is_array)
        
        # Save current type substitution context
        prev_type_map = getattr(self, '_current_type_map', {})
        self._current_type_map = type_map
        
        # Track current function name for error messages
        prev_function_name = getattr(self, '_current_function_name', None)
        self._current_function_name = func_name
        
        # Generate body
        prev_in_fn = self._in_function
        self._in_function = True
        prev_scope_stack = self.scope_stack
        self.scope_stack = [[]]
        
        # Collect generic instances within the body while type_map is active
        # This handles nested generic calls like println(T) inside swap<T>
        if body_node:
            self._collect_generic_instances(body_node)
        
        body_code = self._visit(body_node) if body_node else "{ }"
        
        # Add cleanup code for owned values before function exits
        # Inject cleanup before the closing brace of the function body
        cleanup_lines = self._free_arrays_in_current_scope()
        if cleanup_lines and body_code.startswith("{") and body_code.endswith("}"):
            # Extract the body content (without braces)
            inner = body_code[1:-1].rstrip()
            # Add cleanup before the closing brace
            cleanup_code = "\n".join("    " + line for line in cleanup_lines)
            body_code = "{\n" + inner + "\n" + cleanup_code + "\n}"
        
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
        
        # First pass: collect all generic function instantiations needed
        for child in self.ast.children:
            self._collect_generic_instances(child)
        
        # Emit class typedefs, then constant declarations, then function definitions, then the main body statements
        typedefs: list[str] = []
        constants: list[str] = []
        function_defs: list[str] = []
        monomorphized_funcs_code: list[str] = []  # Keep monomorphized functions separate
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
        
        # Emit monomorphized generic function instances BEFORE regular functions
        # Keep instantiating until no new instances are discovered
        instantiated_keys = set()
        iteration = 0
        while True:
            iteration += 1
            logging.debug(f"Monomorphization iteration {iteration}, total instances: {len(self.monomorphized_funcs)}, instantiated: {len(instantiated_keys)}")
            keys_to_instantiate = [k for k in self.monomorphized_funcs.keys() if k not in instantiated_keys]
            logging.debug(f"  Keys to instantiate this iteration: {keys_to_instantiate}")
            if not keys_to_instantiate:
                break
            for key in keys_to_instantiate:
                func_name, type_args = key
                logging.debug(f"  Instantiating {func_name} with {type_args}")
                mono_code = self._instantiate_generic_function(func_name, type_args)
                if mono_code:
                    monomorphized_funcs_code.append(mono_code)
                instantiated_keys.add(key)
        
        # Generate forward declarations for all monomorphized functions
        # This allows them to call each other regardless of definition order
        forward_decls: list[str] = []
        for mono_code in monomorphized_funcs_code:
            # Extract function signature (first line before the opening brace)
            if ' {' in mono_code:
                signature = mono_code.split(' {')[0]
                forward_decls.append(f"{signature};")
        
        # Add the main() function if it was defined
        if main_function_code:
            function_defs.append(main_function_code)

        typedefs_code = ("\n\n".join(typedefs) + "\n\n") if typedefs else ""
        constants_code = ("\n".join(constants) + "\n\n") if constants else ""
        
        # Emit forward declarations for monomorphized functions
        forward_decls_code = ("\n".join(forward_decls) + "\n\n") if forward_decls else ""
        
        # Emit monomorphized functions first, then regular functions
        all_functions = monomorphized_funcs_code + function_defs
        functions_code = ("\n\n".join(all_functions) + "\n\n") if all_functions else ""

        # Only generate wrapper main() if user didn't define one
        if not main_function_code:
            main_code = "int main(void) {\n"
            if main_lines:
                indented_body = "\n".join(
                    "    " + line for line in "\n".join(main_lines).split("\n")
                )
                main_code += f"{indented_body}\n"
            # Add cleanup for owned values declared at top level
            cleanup_lines = self._free_arrays_in_current_scope()
            if cleanup_lines:
                cleanup_code = "\n".join("    " + line for line in cleanup_lines)
                main_code += f"{cleanup_code}\n"
            # Fixed-size arrays on stack, no cleanup needed
            main_code += "    firescript_cleanup();\n"
            main_code += "    return 0;\n"
            main_code += "}\n"
        else:
            main_code = ""

        return header + typedefs_code + constants_code + forward_decls_code + functions_code + main_code

    def _map_type_to_c(self, t: str) -> str:
        if t == "void":
            return "void"
        if t.endswith("[]"):
            # Arrays map to pointer to element type
            elem_type = t[:-2]
            return f"{FIRETYPE_TO_C.get(elem_type, elem_type)}*"
        # Check if this is an owned (non-copyable) class
        if t in self.class_names and is_owned(t, False):
            # Owned classes are heap-allocated and use pointers
            return f"{t}*"
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
            # Check if this is an owned (non-copyable) class
            class_is_owned = is_owned(class_name, False)
            
            if class_is_owned:
                # Owned classes: allocate on heap with malloc, return pointer
                init_line = f"    {class_name}* this = malloc(sizeof({class_name}));"
                zero_init = f"    *this = ({class_name}){{0}};"
            else:
                # Copyable classes: stack allocation
                init_line = f"    {class_name} this = ({class_name}){{0}};"
                zero_init = ""

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
                if zero_init:
                    lines.append(zero_init)
                if inner:
                    lines.append(inner)
                # Add cleanup before return
                cleanup_lines = self._free_arrays_in_current_scope()
                if cleanup_lines:
                    lines.extend("    " + line for line in cleanup_lines)
                if add_implicit_return:
                    lines.append("    return this;")
                lines.append("}")
                body_code = "\n".join(lines)
            else:
                # Fallback: wrap the generated body in a new block.
                cleanup_lines = self._free_arrays_in_current_scope()
                cleanup_code = "\n".join("    " + line for line in cleanup_lines) if cleanup_lines else ""
                ret_line = "\n    return this;" if add_implicit_return else ""
                init_lines = f"{init_line}\n{zero_init}\n" if zero_init else f"{init_line}\n"
                body_code = f"{{\n{init_lines}    {body_code}\n{cleanup_code}{ret_line}\n}}"
        else:
            # Regular method - add cleanup before function exits
            cleanup_lines = self._free_arrays_in_current_scope()
            if cleanup_lines and body_code.startswith("{") and body_code.endswith("}"):
                # Extract the body content (without braces)
                inner = body_code[1:-1].rstrip()
                # Add cleanup before the closing brace
                cleanup_code = "\n".join("    " + line for line in cleanup_lines)
                body_code = "{\n" + inner + "\n" + cleanup_code + "\n}"
        
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
                # For arrays, pass pointer to first element
                ctype = f"{self._map_type_to_c(base_type)}*" if is_array_param else self._map_type_to_c(base_type)
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
        
        # Add cleanup code for owned values before function exits
        # Inject cleanup before the closing brace of the function body
        cleanup_lines = self._free_arrays_in_current_scope()
        if cleanup_lines and body_code.startswith("{") and body_code.endswith("}"):
            # Extract the body content (without braces)
            inner = body_code[1:-1].rstrip()
            # Add cleanup before the closing brace
            cleanup_code = "\n".join("    " + line for line in cleanup_lines)
            body_code = "{\n" + inner + "\n" + cleanup_code + "\n}"
        
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
            # Enter new scope for tracking owned values
            self.scope_stack.append([])
            lines = []
            for child in node.children:
                # In scopes, each child is a statement.
                stmt_code = self.emit_statement(child)
                if stmt_code:
                    lines.append(stmt_code)
            # Generate cleanup code for owned values in this scope
            cleanup_lines = self._free_arrays_in_current_scope()
            if cleanup_lines:
                lines.extend(cleanup_lines)
            # Pop the scope
            self.scope_stack.pop()
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
                # Arrays are Owned types - allocate on heap
                init_node = node.children[0] if node.children else None
                elem_c = self._map_type_to_c(var_type_fs)
                mangled_name = self._mangle_name(node.name)
                if init_node and init_node.node_type == NodeTypes.ARRAY_LITERAL:
                    elements = init_node.children or []
                    n = len(elements)
                    # Store array size for length() method
                    self.symbol_table[node.name] = (var_type_fs, node.is_array, n)
                    # Track array for cleanup at scope exit
                    if self.scope_stack:
                        self.scope_stack[-1].append((mangled_name, var_type_fs))
                    # Generate heap allocation for array
                    elem_codes = [self._visit(elem) for elem in elements]
                    lines = []
                    # Allocate array on heap
                    lines.append(f"{elem_c}* {mangled_name} = malloc({n} * sizeof({elem_c}));")
                    # Initialize elements
                    for i, elem_code in enumerate(elem_codes):
                        lines.append(f"{mangled_name}[{i}] = {elem_code};")
                    return "\n".join(lines)
                # Allow initializing from an expression (would need additional handling)
                self.error("Array initialization from expressions not yet supported for fixed-size arrays", node.token)
                return ""
            elif var_type_fs == "string":
                # Strings are Owned (heap-allocated)
                # String literals need to be duplicated to heap
                init_node = node.children[0] if node.children else None
                mangled_name = self._mangle_name(node.name)
                
                # Only track for cleanup if this creates a NEW allocation (not a borrow)
                # Track if: literal, function call, or no initializer (default empty string)
                should_track = (
                    init_node is None or  # Default empty string
                    init_node.node_type == NodeTypes.LITERAL or  # String literal
                    init_node.node_type == NodeTypes.FUNCTION_CALL  # Function returns new string
                )
                if should_track and self.scope_stack:
                    self.scope_stack[-1].append((mangled_name, "string"))
                
                if init_node and init_node.node_type == NodeTypes.LITERAL and init_node.token and init_node.token.type == "STRING_LITERAL":
                    # String literal - use strdup to allocate on heap
                    literal_value = init_node.token.value
                    return f"{var_type_c} {mangled_name} = strdup({literal_value});"
                else:
                    # Expression result (already should be heap-allocated)
                    init_value = self._visit(init_node) if init_node else "strdup(\"\")"
                    return f"{var_type_c} {mangled_name} = {init_value};"
            else:
                # Non-array, non-string variable
                mangled_name = self._mangle_name(node.name)
                init_node = node.children[0] if node.children else None
                
                # Track owned (non-copyable) classes for cleanup ONLY if allocated (not borrowed)
                # Track if: 
                # 1. CONSTRUCTOR_CALL (new ClassName(...))
                # 2. FUNCTION_CALL that is a constructor or returns an owned type
                # 3. NOT an identifier (which would be a borrow/copy)
                is_class_type = is_owned(var_type_fs, False)
                should_track = False
                if is_class_type and init_node is not None:
                    if init_node.node_type == NodeTypes.CONSTRUCTOR_CALL:
                        # new ClassName(...) always creates a new allocation
                        should_track = True
                    elif init_node.node_type == NodeTypes.FUNCTION_CALL:
                        # Either constructor or function returning owned type
                        should_track = True
                    # Don't track if it's just copying from another variable (borrow)
                    elif init_node.node_type == NodeTypes.IDENTIFIER:
                        should_track = False
                
                if should_track and self.scope_stack:
                    self.scope_stack[-1].append((mangled_name, var_type_fs))
                
                init_value = self._visit(init_node) if init_node else "0"
                return f"{var_type_c} {mangled_name} = {init_value};"
        elif node.node_type == NodeTypes.ARRAY_ACCESS:
            # Fixed-size array access: arr[idx]
            array_node = node.children[0]
            index_node = node.children[1]
            array_code = self._visit(array_node)
            index_code = self._visit(index_node)
            # Direct array indexing
            return f"{array_code}[{index_code}]"  
        elif node.node_type == NodeTypes.LITERAL:
            return self._literal_to_c(node)
        elif node.node_type == NodeTypes.CAST_EXPRESSION:
            expr_node = node.children[0] if node.children else None
            expr_code = self._visit(expr_node) if expr_node is not None else ""
            target_fs = node.name
            
            # Special handling for casting to string
            if target_fs == "string":
                # Check if source is an array
                expr_type = (
                    getattr(expr_node, "return_type", None)
                    or getattr(expr_node, "var_type", None)
                    or (self.symbol_table.get(getattr(expr_node, "name", ""), (None, False))[0]
                       if expr_node and expr_node.node_type == NodeTypes.IDENTIFIER else None)
                )
                is_array = (
                    getattr(expr_node, "is_array", False)
                    or (self.symbol_table.get(getattr(expr_node, "name", ""), (None, False))[1]
                       if expr_node and expr_node.node_type == NodeTypes.IDENTIFIER else False)
                )
                
                # Also check if expr_type ends with [] (for monomorphized type parameters)
                if is_array or (expr_type and isinstance(expr_type, str) and expr_type.endswith("[]")):
                    # Array to string conversion - generate inline code
                    # Get element type and size
                    if expr_type and expr_type.endswith("[]"):
                        elem_type = expr_type[:-2]
                    else:
                        elem_type = expr_type or "int32"
                    
                    # Try to get array size from symbol table
                    array_size = None
                    if expr_node and expr_node.node_type == NodeTypes.IDENTIFIER:
                        sym_info = self.symbol_table.get(expr_node.name)
                        if sym_info and len(sym_info) >= 3:
                            array_size = sym_info[2]
                    
                    if array_size is None:
                        # Can't determine size - this happens with array parameters
                        # For now, just return a simple representation
                        return "strdup(\"[...]\")"
                    
                    # Generate inline array-to-string code
                    temp_var = f"__arr_str_{self.array_temp_counter}"
                    self.array_temp_counter += 1
                    elem_c = self._map_type_to_c(elem_type)
                    
                    # Generate code that builds the string representation
                    # Use format instead of f-strings to handle complex brace escaping
                    code = "({ " + elem_c + "* " + temp_var + "_arr = " + expr_code + "; "
                    code += "size_t " + temp_var + "_size = " + str(array_size) + "; "
                    code += "size_t " + temp_var + "_bufsize = 1024; "
                    code += "char* " + temp_var + " = malloc(" + temp_var + "_bufsize); "
                    code += "size_t " + temp_var + "_len = 0; "
                    code += temp_var + "[" + temp_var + "_len++] = '['; "
                    code += "for (size_t " + temp_var + "_i = 0; " + temp_var + "_i < " + temp_var + "_size; " + temp_var + "_i++) { "
                    code += "if (" + temp_var + "_i > 0) { " + temp_var + "[" + temp_var + "_len++] = ','; " + temp_var + "[" + temp_var + "_len++] = ' '; } "
                    code += "char* " + temp_var + "_elem = firescript_toString(" + temp_var + "_arr[" + temp_var + "_i]); "
                    code += "size_t " + temp_var + "_elem_len = strlen(" + temp_var + "_elem); "
                    code += "while (" + temp_var + "_len + " + temp_var + "_elem_len + 2 >= " + temp_var + "_bufsize) { " + temp_var + "_bufsize *= 2; " + temp_var + " = realloc(" + temp_var + ", " + temp_var + "_bufsize); } "
                    code += "memcpy(" + temp_var + " + " + temp_var + "_len, " + temp_var + "_elem, " + temp_var + "_elem_len); "
                    code += temp_var + "_len += " + temp_var + "_elem_len; "
                    code += "free(" + temp_var + "_elem); "
                    code += "} "
                    code += temp_var + "[" + temp_var + "_len++] = ']'; "
                    code += temp_var + "[" + temp_var + "_len] = '\\0'; "
                    code += temp_var + "; })"
                    return code
                else:
                    # Primitive to string conversion
                    return f"firescript_toString({expr_code})"
            
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
                var_name = node.token.value if node.token and hasattr(node.token, 'value') else ""
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
                    # For fixed-size arrays, return compile-time size
                    if object_node.node_type == NodeTypes.IDENTIFIER:
                        sym_info = self.symbol_table.get(object_node.name)
                        if sym_info and len(sym_info) >= 3:
                            array_size = sym_info[2]
                            return f"(int32_t){array_size}"
                    self.error("Cannot determine array size at compile time", node.token)
                    return "0"
                # Fixed-size arrays don't support mutation methods
                self.error(f"Fixed-size arrays don't support method '{method_name}'. Arrays are immutable.", node.token)
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
            # Emit obj.field or obj->field depending on whether obj is a pointer (owned class)
            obj_node = node.children[0] if node.children else None
            obj_code = self._visit(obj_node) if obj_node else ""
            
            # Determine if the object is an owned class (pointer type)
            obj_type = None
            if obj_node and obj_node.node_type == NodeTypes.IDENTIFIER:
                obj_type = self.symbol_table.get(obj_node.name, (None, False))[0]
            elif obj_node:
                obj_type = getattr(obj_node, "return_type", None) or getattr(obj_node, "var_type", None)
            
            # Use -> for owned classes, . for copyable classes and primitives
            if obj_type and obj_type in self.class_names and is_owned(obj_type, False):
                return f"{obj_code}->{node.name}"
            else:
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
                expr_node = node.children[0]
                expr_code = (
                    self._visit(expr_node)
                    if expr_node is not None
                    else ""
                )
                # For owned values being returned, ownership transfers to caller - don't free them
                # Check if we're returning a simple variable (identifier) - if so, exclude it from cleanup
                exclude_var = None
                if expr_node and expr_node.node_type == NodeTypes.IDENTIFIER:
                    # Returning a variable - exclude it from cleanup (ownership transfers)
                    exclude_var = self._mangle_name(expr_node.name)
                
                # Cleanup other owned values in scope
                cleanup_lines = []
                if self._in_function:
                    cleanup_lines = self._free_arrays_in_all_active_scopes(exclude_var)
                
                if cleanup_lines:
                    cleanup = "\n".join(cleanup_lines)
                    return f"{{\n{cleanup}\nreturn {expr_code};\n}}"
                return f"return {expr_code}"
            # bare return - no value being returned, safe to cleanup all
            cleanup_lines = []
            if self._in_function:
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
                
                # Check if this is an owned (non-copyable) class
                if is_owned(node.name, False):
                    # Owned classes need heap allocation
                    # Generate inline compound statement that allocates and initializes
                    tmp_var = f"__tmp_class_{self.array_temp_counter}"
                    self.array_temp_counter += 1
                    return f"({{ {node.name}* {tmp_var} = malloc(sizeof({node.name})); *{tmp_var} = ({node.name}){{ {init_str} }}; {tmp_var}; }})"
                else:
                    # Copyable classes use stack allocation with compound literal
                    return f"({node.name}){{ {init_str} }}"
            if node.name == "stdout":
                # Check if stdout is enabled in the file where this call is made
                node_source_file = getattr(node, 'source_file', self.source_file)
                # Normalize path for consistent lookup (use abspath to handle relative vs absolute)
                normalized_source = os.path.abspath(node_source_file) if node_source_file else node_source_file
                node_file_directives = self.file_directives.get(normalized_source, set())
                
                logging.debug(f"stdout() call: node_source_file={node_source_file}, normalized={normalized_source}, file_directives={self.file_directives}, node_directives={node_file_directives}")
                
                if "enable_lowlevel_stdout" not in node_file_directives:
                    self.error(
                        "stdout() is not available. Use 'directive enable_lowlevel_stdout;' "
                        "in this file to enable it.",
                        node
                    )
                    sys.exit(1)
                # stdout only accepts strings - no special formatting
                arg = node.children[0]
                arg_code = self._visit(arg)
                return f'printf("%s", {arg_code})'
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
                
                # Re-infer if in monomorphization context, since type parameters may have been substituted
                # OR if type_args not set at all, try to infer them
                if func_name in self.generic_templates:
                    if getattr(self, '_current_type_map', {}) or not type_args:
                        inferred = self._infer_type_args_from_call(func_name, node)
                        if inferred:
                            type_args = inferred
                
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
            
            # Check if parent class is owned (returns pointer) or copyable (returns value)
            parent_is_owned = is_owned(super_class, False)
            
            if parent_is_owned:
                # Parent constructor returns a pointer - dereference to copy fields
                lines.append(f"{super_class}* {tmp} = {call};")
                for fname, _ftype in fields:
                    # this is also a pointer for owned classes, use ->
                    lines.append(f"this->{fname} = {tmp}->{fname};")
                # Free the temporary parent object after copying fields
                lines.append(f"firescript_free({tmp});")
            else:
                # Parent constructor returns a value - copy directly
                lines.append(f"{super_class} {tmp} = {call};")
                for fname, _ftype in fields:
                    # this is a value for copyable classes, use .
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
