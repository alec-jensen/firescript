# firescript/c_code_generator.py
from enums import NodeTypes  # [firescript/enums.py]
from parser import ASTNode  # [firescript/parser.py]
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

    def generate(self) -> str:
        """Generate C code from the AST"""
        header = "#include <stdio.h>\n#include <stdbool.h>\n#include <stdint.h>\n#include <inttypes.h>\n#include <string.h>\n"
        header += '#include "firescript/runtime/runtime.h"\n'
        header += '#include "firescript/runtime/conversions.h"\n'
        # No dynamic array runtime needed for fixed-size arrays
        # Emit class typedefs, then function definitions, then the main body statements
        typedefs: list[str] = []
        function_defs: list[str] = []
        main_lines: list[str] = []

        # Ensure outer (main) scope exists for tracking arrays declared at top-level
        self.scope_stack = [[]]

        for child in self.ast.children:
            if child.node_type == NodeTypes.FUNCTION_DEFINITION:
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
            else:
                stmt_code = self.emit_statement(child)
                if stmt_code:
                    main_lines.append(stmt_code)

        typedefs_code = ("\n\n".join(typedefs) + "\n\n") if typedefs else ""
        functions_code = ("\n\n".join(function_defs) + "\n\n") if function_defs else ""

        main_code = "int main(void) {\n"
        if main_lines:
            indented_body = "\n".join(
                "    " + line for line in "\n".join(main_lines).split("\n")
            )
            main_code += f"{indented_body}\n"
        # Free any arrays declared at the top level (outermost scope)
        if (not self.drops_enabled) and self.scope_stack and self.scope_stack[0]:
            # Fixed-size arrays don't require explicit frees
            pass
        main_code += "    firescript_cleanup();\n"
        main_code += "    return 0;\n"
        main_code += "}\n"

        return header + typedefs_code + functions_code + main_code

    def _map_type_to_c(self, t: str) -> str:
        if t == "void":
            return "void"
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
        """Emit a C function for a class method: ClassName_methodName(ClassName self, ...) { ... }"""
        ret_fs = node.return_type or "void"
        if ret_fs.endswith("[]"):
            raise NotImplementedError("Array returns are not supported in methods")
        ret_c = self._map_type_to_c(ret_fs)

        params = []
        body_node = None
        for child in node.children:
            if child.node_type == NodeTypes.PARAMETER:
                base_type = child.var_type or "int32"
                if child.is_array:
                    raise NotImplementedError("Array parameters are not supported in methods")
                ctype = self._map_type_to_c(base_type)
                params.append(f"{ctype} {child.name}")
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
        self.scope_stack = prev_scope_stack
        self._in_function = prev_in_fn
        self.symbol_table = prev_symbols

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

    def _emit_function_definition(self, node: ASTNode) -> str:
        # node.return_type holds the firescript return type (e.g., 'void')
        ret_fs = node.return_type or "void"
        is_array_return = False
        if ret_fs and ret_fs.endswith("[]"):
            is_array_return = True
            ret_fs = ret_fs[:-2]
        if is_array_return:
            raise NotImplementedError("Returning arrays is not supported for fixed-size arrays")
        ret_c = self._map_type_to_c(ret_fs)

        # Parameters are all children except the last one, which is the body scope
        params = []
        body_node = None
        for child in node.children:
            if child.node_type == NodeTypes.PARAMETER:
                base_type = child.var_type or "int32"
                is_array_param = child.is_array
                if is_array_param:
                    raise NotImplementedError("Array parameters are not supported for fixed-size arrays")
                ctype = self._map_type_to_c(base_type)
                params.append(f"{ctype} {child.name}")
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

        return f"{ret_c} {node.name}({params_sig}) {body_code}"

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
                # Blocks shouldn't get semicolons, but return statements returning
                # compound literals like '(Type){...}' end with '}' and still need one.
                needs_semicolon = (node.node_type == NodeTypes.RETURN_STATEMENT)
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
            to_free = list(self.scope_stack.pop())
            # No cleanup needed for fixed-size arrays
            return "{\n" + "\n".join("    " + line for line in lines) + "\n}"
        elif node.node_type == NodeTypes.ARRAY_LITERAL:
            # Only supported as part of variable initialization for fixed-size arrays
            # If evaluated as an expression directly, return a comment placeholder
            return "/* array literal */"

        elif node.node_type == NodeTypes.VARIABLE_DECLARATION:
            var_type_fs = node.var_type or "int32"
            var_type_c = self._map_type_to_c(var_type_fs)
            self.symbol_table[node.name] = (var_type_fs, node.is_array)

            if node.is_array:
                init_node = node.children[0] if node.children else None
                # Fixed-size arrays: support only literal initialization
                if init_node and init_node.node_type == NodeTypes.ARRAY_LITERAL:
                    elements = init_node.children
                    elem_exprs = [self._visit(elem) for elem in elements]
                    fire_type = var_type_fs
                    c_type = FIRETYPE_TO_C.get(fire_type, "int32_t")
                    n = len(elem_exprs)
                    self.array_lengths[node.name] = n
                    init_list = ", ".join(elem_exprs)
                    return f"{c_type} {node.name}[{n}] = {{ {init_list} }};"
                else:
                    raise NotImplementedError("Fixed-size arrays must be initialized with a literal")
            else:
                init_value = self._visit(node.children[0]) if node.children else "0"
                return f"{var_type_c} {node.name} = {init_value};"
        elif node.node_type == NodeTypes.ARRAY_ACCESS:
            # Fixed-size array access: arr[idx]
            array_node = node.children[0]
            index_node = node.children[1]
            array_name = self._visit(array_node)
            index_code = self._visit(index_node)
            return f"{array_name}[{index_code}]"
        elif node.node_type == NodeTypes.LITERAL:
            return self._literal_to_c(node)
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
                return f"firescript_strcat({left}, {right})"
            # Numeric or generic binary op fallback
            return f"({left} {op} {right})"
        elif node.node_type == NodeTypes.METHOD_CALL:
            # Fixed-size array methods: only length()/size()
            object_node = node.children[0]
            object_code = self._visit(object_node)
            method_name = node.name
            if (
                object_node.var_type
                and self.symbol_table.get(getattr(object_node, "name", ""), (None, False))[1]
            ):
                if method_name in ("length", "size"):
                    n = self.array_lengths.get(object_node.name)
                    if n is not None:
                        return f"{n}"
                    return f"(sizeof({object_code})/sizeof({object_code}[0]))"
                raise NotImplementedError(
                    f"Array method '{method_name}' is not supported for fixed-size arrays"
                )
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
            return node.name
        elif node.node_type == NodeTypes.VARIABLE_ASSIGNMENT:
            # Simple assignment to identifier from expression
            name = node.name
            value_code = self._visit(node.children[0]) if node.children else "0"
            return f"{name} = {value_code}"
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

                # Detect fixed-size arrays and print inline
                is_arr = False
                elem_type_for_array = None
                if arg.node_type == NodeTypes.IDENTIFIER:
                    elem_type_for_array, is_arr = self.symbol_table.get(
                        arg.name, (None, False)
                    )
                    if is_arr:
                        n = self.array_lengths.get(arg.name)
                        length_expr = (
                            str(n) if n is not None else f"(sizeof({arg.name})/sizeof({arg.name}[0]))"
                        )
                        lines = []
                        lines.append('printf("[");')
                        lines.append(f"for (size_t __i = 0; __i < {length_expr}; ++__i) {{")
                        if elem_type_for_array == "bool":
                            lines.append(f'    printf("%s", {arg.name}[__i] ? "true" : "false");')
                        elif elem_type_for_array == "string":
                            lines.append(f'    printf("%s", {arg.name}[__i]);')
                        elif elem_type_for_array == "int8":
                            lines.append(f'    printf("%" PRId8, (int8_t){arg.name}[__i]);')
                        elif elem_type_for_array == "int16":
                            lines.append(f'    printf("%" PRId16, (int16_t){arg.name}[__i]);')
                        elif elem_type_for_array == "int32":
                            lines.append(f'    printf("%" PRId32, (int32_t){arg.name}[__i]);')
                        elif elem_type_for_array == "int64":
                            lines.append(f'    printf("%" PRId64, (int64_t){arg.name}[__i]);')
                        elif elem_type_for_array == "uint8":
                            lines.append(f'    printf("%" PRIu8, (uint8_t){arg.name}[__i]);')
                        elif elem_type_for_array == "uint16":
                            lines.append(f'    printf("%" PRIu16, (uint16_t){arg.name}[__i]);')
                        elif elem_type_for_array == "uint32":
                            lines.append(f'    printf("%" PRIu32, (uint32_t){arg.name}[__i]);')
                        elif elem_type_for_array == "uint64":
                            lines.append(f'    printf("%" PRIu64, (uint64_t){arg.name}[__i]);')
                        elif elem_type_for_array in ("float32", "float64"):
                            lines.append(f'    printf("%f", {arg.name}[__i]);')
                        elif elem_type_for_array == "float128":
                            lines.append(f'    printf("%Lf", {arg.name}[__i]);')
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
                    return f'printf("%Lf\\n", {arg_code})'
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
                args = ", ".join(self._visit(arg) for arg in node.children)
                return f"{node.name}({args})"
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
            return f"{identifier} {c_op} {value};"

        elif node.node_type == NodeTypes.UNARY_EXPRESSION:
            if not node.token or not hasattr(node.token, "value"):
                raise ValueError("Missing token value in unary expression")
            identifier = node.token.value
            op = node.name
            var_type = self.symbol_table.get(identifier, (None, False))[0]
            if op == "++":
                return f"{identifier}++"
            elif op == "--":
                return f"{identifier}--"
            else:
                raise ValueError(f"Unrecognized unary operator '{op}' for {identifier}")
        else:
            return ""
