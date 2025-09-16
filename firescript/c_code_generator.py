# firescript/c_code_generator.py
from enums import NodeTypes  # [firescript/enums.py]
from parser import ASTNode  # [firescript/parser.py]
import logging

# A simple type mapping from firescript types to C types.
FIRETYPE_TO_C: dict[str, str] = {
    "int": "int64_t",
    "float": "float",
    "double": "double",
    "bool": "bool",
    "string": "char*",
    "tuple": "struct tuple",
}

class CCodeGenerator:
    def __init__(self, ast: ASTNode):
        self.ast = ast
        self.symbol_table: dict[str, tuple[str, bool]] = {}  # (type, is_array)
        self.array_temp_counter = 0  # Counter for generating unique array variable names

    def _handle_array_index(self, index_expr):
        """Helper function to properly handle array indices in C"""
        # After removing big number support, just return the expression string
        return str(index_expr)

    def generate(self) -> str:
        """Generate C code from the AST"""
        header = '#include <stdio.h>\n#include <stdbool.h>\n#include <stdint.h>\n#include <string.h>\n'
        header += '#include "firescript/runtime/runtime.h"\n'
        header += '#include "firescript/runtime/conversions.h"\n'
        header += '#include "firescript/runtime/varray.h"\n'
        # Emit function definitions first, then the main body statements
        function_defs: list[str] = []
        main_lines: list[str] = []

        for child in self.ast.children:
            if child.node_type == NodeTypes.FUNCTION_DEFINITION:
                func_code = self._emit_function_definition(child)
                if func_code:
                    function_defs.append(func_code)
            else:
                stmt_code = self.emit_statement(child)
                if stmt_code:
                    main_lines.append(stmt_code)

        functions_code = ("\n\n".join(function_defs) + "\n\n") if function_defs else ""

        main_code = "int main(void) {\n"
        if main_lines:
            indented_body = "\n".join("    " + line for line in "\n".join(main_lines).split("\n"))
            main_code += f"{indented_body}\n"
        main_code += "    firescript_cleanup();\n"
        main_code += "    return 0;\n"
        main_code += "}\n"

        return header + functions_code + main_code

    def _map_type_to_c(self, t: str) -> str:
        if t == "void":
            return "void"
        return FIRETYPE_TO_C.get(t, t)

    def _emit_function_definition(self, node: ASTNode) -> str:
        # node.return_type holds the firescript return type (e.g., 'void')
        ret_fs = node.return_type or "void"
        is_array_return = False
        if ret_fs and ret_fs.endswith("[]"):
            is_array_return = True
            ret_fs = ret_fs[:-2]
        ret_c = "VArray*" if is_array_return else self._map_type_to_c(ret_fs)

        # Parameters are all children except the last one, which is the body scope
        params = []
        body_node = None
        for child in node.children:
            if child.node_type == NodeTypes.PARAMETER:
                base_type = child.var_type or "int"
                is_array_param = child.is_array
                ctype = "VArray*" if is_array_param else self._map_type_to_c(base_type)
                params.append(f"{ctype} {child.name}")
            elif child.node_type == NodeTypes.SCOPE:
                body_node = child

        params_sig = ", ".join(params) if params else "void"

        # Save and prepare symbol table for function scope (register params)
        prev_symbols = self.symbol_table.copy()
        for child in node.children:
            if child.node_type == NodeTypes.PARAMETER:
                self.symbol_table[child.name] = (child.var_type or "int", child.is_array)

        body_code = self._visit(body_node) if body_node else "{ }"

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
        # Only add semicolon if the code doesn't already end with one,
        # isn't a block, and isn't a preprocessor directive.
        if code and not code.strip().endswith(";") and not code.strip().endswith("}") and not code.strip().startswith("#"):
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
            lines = []
            for child in node.children:
                # In scopes, each child is a statement.
                stmt_code = self.emit_statement(child)
                if stmt_code:
                    lines.append(stmt_code)
            return "{\n" + "\n".join("    " + line for line in lines) + "\n}"
        elif node.node_type == NodeTypes.ARRAY_LITERAL:
            # Handle array literals
            fire_type = node.var_type or "int"  # Default to int if var_type is not set
            c_type = FIRETYPE_TO_C.get(fire_type, "int")
            array_size = len(node.children)

            temp_var = f"temp_array_{self.array_temp_counter}"
            self.array_temp_counter += 1

            # Create the VArray and populate it with elements
            lines = [
                f"VArray* {temp_var} = varray_create({array_size}, sizeof({c_type}));"
            ]

            for i, elem in enumerate(node.children):
                elem_code = self._visit(elem)
                elem_var = f"{temp_var}_elem{i}"

                if fire_type == "string":
                    # elem_code already includes quotes if it's a string literal
                    lines.append(f"char* {elem_var} = {elem_code};")
                    lines.append(f"varray_append({temp_var}, &{elem_var});")
                else:
                    lines.append(f"{c_type} {elem_var} = {elem_code};")
                    lines.append(f"varray_append({temp_var}, &{elem_var});")

            return temp_var

        elif node.node_type == NodeTypes.VARIABLE_DECLARATION:
            var_type_fs = node.var_type or "int"
            var_type_c = FIRETYPE_TO_C.get(var_type_fs, f"/* unknown_type_{var_type_fs} */")
            self.symbol_table[node.name] = (var_type_fs, node.is_array)

            if node.is_array:
                init_node = node.children[0] if node.children else None
                # If initializer is an array literal, materialize it element by element.
                if init_node and init_node.node_type == NodeTypes.ARRAY_LITERAL:
                    array_node = init_node
                    fire_type = var_type_fs
                    c_type = FIRETYPE_TO_C.get(fire_type, "int")
                    elements = array_node.children
                    lines = [f"VArray* {node.name} = varray_create({len(elements)}, sizeof({c_type}));"]
                    for i, elem in enumerate(elements):
                        elem_code = self._visit(elem)
                        elem_var = f"{node.name}_elem{i}"
                        if fire_type == "string":
                            lines.append(f"char* {elem_var} = {elem_code};")
                            lines.append(f"varray_append({node.name}, &{elem_var});")
                        else:
                            lines.append(f"{c_type} {elem_var} = {elem_code};")
                            lines.append(f"varray_append({node.name}, &{elem_var});")
                    return "\n".join(lines)
                else:
                    # Otherwise, assume initializer expression returns a VArray* (e.g., function or method call)
                    init_expr = self._visit(init_node) if init_node else "NULL"
                    # If the generated code contains newlines (e.g., a multi-line method call), wrap in a block then assign.
                    if "\n" in init_expr:
                        temp_var = f"__init_arr_{self.array_temp_counter}"
                        self.array_temp_counter += 1
                        return f"VArray* {node.name};\n{{\n{init_expr}\n{node.name} = {init_node.name if init_node else 'NULL'};\n}}"
                    return f"VArray* {node.name} = {init_expr};"
            else:
                init_value = self._visit(node.children[0]) if node.children else "0"
                return f"{var_type_c} {node.name} = {init_value};"
        elif node.node_type == NodeTypes.ARRAY_ACCESS:
            # Handle array access: arr[idx]
            array_node = node.children[0]
            index_node = node.children[1]

            array_name = self._visit(array_node)
            index_code = self._visit(index_node)

            # Determine the type of the array elements
            fire_type = self.symbol_table.get(array_name, ("int", False))[0]
            c_type = FIRETYPE_TO_C.get(fire_type, "int")

            # Generate code for accessing the array element
            return f"(({c_type}*)({array_name}->data))[{index_code}]"
        elif node.node_type == NodeTypes.METHOD_CALL:
            # Handle method call: obj.method(args)
            object_node = node.children[0]
            object_code = self._visit(object_node) # C name of the object/array
            method_name = node.name

            args_code = [self._visit(child) for child in node.children[1:]]

            if object_node.var_type and self.symbol_table.get(object_node.name, (None, False))[1]: # If it's an array
                elem_type, _ = self.symbol_table.get(object_node.name, ("int", False))

                if method_name == "pop":
                    if elem_type == "int":
                        temp_popped = f"__popped_val_{self.array_temp_counter}"
                        self.array_temp_counter += 1
                        
                        # Handle the index differently if it's a literal integer
                        if args_code and len(node.children) > 1:
                            c_idx_expr_str = args_code[0]
                        else:
                            c_idx_expr_str = f"{object_code}->size - 1"
                            
                        return f"({{ int64_t {temp_popped} = ((int64_t*)({object_code}->data))[{c_idx_expr_str}]; {object_code} = varray_remove({object_code}, {c_idx_expr_str}); {temp_popped}; }})"
                    
                    else:
                        return "/* Pop on non-int array element type not fully specialized yet */"
                elif method_name == "append":
                    if args_code:
                        element = args_code[0]
                        tmp = f"_tmp_elem_{self.array_temp_counter}"
                        self.array_temp_counter += 1
                        lines = []
                        if elem_type == "int":
                            lines.append(f"int64_t {tmp} = {element};")
                            lines.append(f"{object_code} = varray_append({object_code}, &{tmp});")
                        elif elem_type == "string":
                            lines.append(f"char* {tmp} = {element};")
                            lines.append(f"{object_code} = varray_append({object_code}, &{tmp});")
                        
                        else:
                            lines.append(f"{elem_type} {tmp} = {element};")
                            lines.append(f"{object_code} = varray_append({object_code}, &{tmp});")
                        return "\n".join(lines)
                elif method_name == "insert":
                    if len(args_code) >= 2 and len(node.children) >= 3:
                        index_node = node.children[1]  # First arg is index
                        index = args_code[0]
                        element = args_code[1]
                        
                        # Handle literal integer differently
                        idx = index  # Index already an integer expression
                            
                        tmp2 = f"_tmp_elem_{self.array_temp_counter}"
                        self.array_temp_counter += 1
                        lines = []
                        if elem_type == "int":
                            lines.append(f"int64_t {tmp2} = {element};")
                            lines.append(f"{object_code} = varray_insert({object_code}, {idx}, &{tmp2});")
                        elif elem_type == "string":
                            lines.append(f"char* {tmp2} = {element};")
                            lines.append(f"{object_code} = varray_insert({object_code}, {idx}, &{tmp2});")
                        
                        else:
                            lines.append(f"{elem_type} {tmp2} = {element};")
                            lines.append(f"{object_code} = varray_insert({object_code}, {idx}, &{tmp2});")
                        return "\n".join(lines)
                elif method_name == "clear":
                    # clear() - Remove all elements
                    return f"varray_clear({object_code})"
                    
                elif method_name == "length" or method_name == "size":
                    # Return the size of the array
                    return f"{object_code}->size"
            
            # Default case for unknown methods
            return f"{object_code}.{method_name}({', '.join(args_code)})"
            
        elif node.node_type == NodeTypes.VARIABLE_ASSIGNMENT:
            expr_code = self._visit(node.children[0]) if node.children else ""
            return f"{node.name} = {expr_code}"
        elif node.node_type == NodeTypes.BINARY_EXPRESSION:
            left = self._visit(node.children[0])
            right = self._visit(node.children[1])

            # Use native arithmetic for float and double
            if node.return_type == "float" or node.return_type == "double":
                op = node.name
                return f"({left} {op} {right})"

            # Use native arithmetic for standard int (int64_t)
            if node.return_type == "int":
                op = node.name
                return f"({left} {op} {right})"
            if (node.children[0].token and node.children[0].token.type == "STRING_LITERAL") or node.children[0].return_type == "string" or node.children[0].var_type == "string":
                if node.children[1] is not None and ((node.children[1].token is not None and node.children[1].token.type == "STRING_LITERAL") or node.children[1].return_type == "string" or node.children[1].var_type == "string"):
                    node.return_type = "string"
                    return f"firescript_strcat({left}, {right})"
                else:
                    raise ValueError("temp: Cannot concatenate string with non-string type")
            
            op = node.name
            return f"({left} {op} {right})"
        elif node.node_type == NodeTypes.LITERAL:
            # Integer literal initialization (default to int64_t)
            if node.token and node.token.type == "INTEGER_LITERAL":
                val = node.token.value
                
                # Otherwise, return a regular integer literal (int64_t)
                return val
            if node.token is None:
                raise ValueError("Literal node missing token")
            return node.token.value
        elif node.node_type == NodeTypes.IDENTIFIER:
            return node.name
        elif node.node_type == NodeTypes.RETURN_STATEMENT:
            # Return with or without expression
            if node.children:
                expr_code = self._visit(node.children[0]) if node.children[0] is not None else ""
                return f"return {expr_code}"
            return "return"
        elif node.node_type == NodeTypes.FUNCTION_CALL:
            if node.name == "print":
                arg = node.children[0]
                arg_code = self._visit(arg)
                # Array length/size methods return native size_t
                if arg.node_type == NodeTypes.METHOD_CALL and arg.name in ("length", "size"):
                    return f'printf("%zu\\n", {arg_code})'

                # Detect arrays early and print using runtime helper
                is_arr = False
                elem_type_for_array = None
                if arg.node_type == NodeTypes.IDENTIFIER:
                    elem_type_for_array, is_arr = self.symbol_table.get(arg.name, (None, False))
                    if is_arr:
                        return f'firescript_print_array({arg.name}, "{elem_type_for_array}")'

                arg_type = getattr(arg, 'return_type', None)

                if arg_type is None:
                    if arg.node_type == NodeTypes.LITERAL and arg.token: # Check token exists
                        if arg.token.type == "BOOLEAN_LITERAL": arg_type = "bool"
                        elif arg.token.type == "STRING_LITERAL": arg_type = "string"
                        elif arg.token.type == "INTEGER_LITERAL": arg_type = "int"
                        elif arg.token.type == "FLOAT_LITERAL": arg_type = "float"
                        elif arg.token.type == "DOUBLE_LITERAL": arg_type = "double"
                    elif arg.node_type == NodeTypes.IDENTIFIER:
                        arg_type, _ = self.symbol_table.get(arg.name, (None, False))
                    elif arg.node_type == NodeTypes.ARRAY_ACCESS:
                        arr_node = arg.children[0]
                        # Ensure arr_node.var_type is populated by type resolution
                        arg_type = arr_node.var_type if hasattr(arr_node, 'var_type') else None

                # Fix all printf/gmp_printf calls to ensure newlines are properly escaped
                # and string literals don't contain actual newlines
                if arg_type == "bool":
                    return f'printf("%s\\n", {arg_code} ? "true" : "false")'
                if arg_type == "int":
                    return f'printf("%ld\\n", {arg_code})'
                
                if arg_type in ("float", "double"):
                    return f'printf("%f\\n", {arg_code})'
                if arg_type == "float":
                    return f'firescript_print_float({arg_code})'
                if arg_type == "double":
                    return f'firescript_print_double({arg_code})'
                if arg_type == "string":
                    return f'printf("%s\\n", {arg_code})'

                return f'printf("%s\\n", {arg_code})' # Last resort
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
            left_type = getattr(leftNode, 'var_type', None) or (self.symbol_table.get(leftNode.name, (None, False))[0] if leftNode.node_type == NodeTypes.IDENTIFIER else getattr(leftNode, 'return_type', None))
            right_type = getattr(rightNode, 'var_type', None) or (self.symbol_table.get(rightNode.name, (None, False))[0] if rightNode.node_type == NodeTypes.IDENTIFIER else getattr(rightNode, 'return_type', None))

            if left_type in ("int","float","double") or right_type in ("int","float","double"):
                op = node.name
                return f"({left} {op} {right})"

            # String comparison unchanged
            if leftNode.token and leftNode.token.type == "STRING_LITERAL" or leftNode.return_type == "string" or leftNode.var_type == "string":
                if rightNode.token and rightNode.token.type == "STRING_LITERAL" or rightNode.return_type == "string" or rightNode.var_type == "string":
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
            return "break"
        elif node.node_type == NodeTypes.CONTINUE_STATEMENT:
            return "continue"
        elif node.node_type == NodeTypes.RELATIONAL_EXPRESSION:
            leftNode, rightNode = node.children
            left = self._visit(leftNode)
            right = self._visit(rightNode)
            op = node.name
            # Get the types properly from symbol table or return_type
            left_type = getattr(leftNode, 'var_type', None) or self.symbol_table.get(leftNode.name, (None, False))[0] if leftNode.node_type == NodeTypes.IDENTIFIER else getattr(leftNode, 'return_type', None)
            right_type = getattr(rightNode, 'var_type', None) or self.symbol_table.get(rightNode.name, (None, False))[0] if rightNode.node_type == NodeTypes.IDENTIFIER else getattr(rightNode, 'return_type', None)
            
            # Copyable numeric or fallback comparison
            return f"({left} {op} {right})"
        elif node.node_type == NodeTypes.COMPOUND_ASSIGNMENT:
            identifier = node.name
            op = getattr(node.token, 'type', None)
            value = self._visit(node.children[0])
            var_type = self.symbol_table.get(identifier, (None, False))[0]
            # Map firescript compound assignment operators to C operators (Copyable only)
            op_map = {
                "ADD_ASSIGN": "+=",
                "SUBTRACT_ASSIGN": "-=",
                "MULTIPLY_ASSIGN": "*=",
                "DIVIDE_ASSIGN": "/=",
                "MODULO_ASSIGN": "%="
            }
            c_op = op_map.get(op or "", "+=")  # Default to += if unknown or op is None
            return f"{identifier} {c_op} {value};"
            
        elif node.node_type == NodeTypes.UNARY_EXPRESSION:
            if not node.token or not hasattr(node.token, 'value'):
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
