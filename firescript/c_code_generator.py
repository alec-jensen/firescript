# firescript/c_code_generator.py
from enums import NodeTypes  # [firescript/enums.py]
from parser import ASTNode  # [firescript/parser.py]

# A simple type mapping from Firescript types to C types.
FIRETYPE_TO_C: dict[str, str] = {
    "int": "int",
    "float": "float",
    "double": "double",
    "bool": "bool",       # Assumes stdbool.h is included in the generated code.
    "string": "char*",    # A basic mapping for strings.
    "tuple": "struct tuple",  # Placeholder for tuple types.
}

class CCodeGenerator:
    def __init__(self, ast: ASTNode):
        self.ast = ast
        self.symbol_table: dict[str, tuple[str, bool]] = {}  # (type, is_array)
        self.array_temp_counter = 0  # Counter for generating unique array variable names

    def generate(self) -> str:
        header = '#include <stdio.h>\n#include <stdbool.h>\n#include <string.h>\n#include "firescript/runtime/runtime.h"\n#include "firescript/runtime/conversions.h"\n#include "firescript/runtime/varray.h"\n'
        body = self._visit(self.ast)
        main_code = "int main(void) {\n"
        if body:
            indented_body = "\n".join("    " + line for line in body.split("\n"))
            main_code += f"{indented_body}\n"
        main_code += "    firescript_cleanup();\n"
        main_code += "    return 0;\n"
        main_code += "}\n"
        return header + main_code

    def emit_statement(self, node: ASTNode) -> str:
        """
        Generate code for a node that represents a statement.
        Automatically appends a semicolon if one is not already present.
        """
        code = self._visit(node)
        # Only add semicolon if the code doesn't already end with one
        if code and not code.strip().endswith(";") and not code.strip().endswith("}"):
            code += ";"
        return code

    def _visit(self, node: ASTNode) -> str:
        if node.node_type == NodeTypes.ROOT:
            lines = []
            for child in node.children:
                # Assume all top-level nodes are statements.
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
        elif node.node_type == NodeTypes.VARIABLE_DECLARATION:
            if node.var_type is None:
                raise ValueError("Variable type cannot be None for symbol " + node.name)
            self.symbol_table[node.name] = (node.var_type, node.is_array)
            fire_type = node.var_type
            if fire_type not in FIRETYPE_TO_C:
                raise ValueError(f"Unknown type: {fire_type}")
            
            # Handle array declarations differently
            if node.is_array:
                c_type = FIRETYPE_TO_C.get(fire_type)
                value_node = node.children[0] if node.children else None
                
                # If initializing with an array literal
                if value_node and value_node.node_type == NodeTypes.ARRAY_LITERAL:
                    array_elements = value_node.children
                    array_size = len(array_elements)
                    
                    lines = [
                        f"VArray* {node.name} = varray_create({array_size}, sizeof({c_type}))"
                    ]
                    
                    # Handle each array element separately
                    for i, elem in enumerate(array_elements):
                        elem_value = self._visit(elem)
                        # For string arrays, need to remove the quotes from element values
                        lines.append(f"{c_type} {node.name}_elem{i} = {elem_value}")
                        lines.append(f"{node.name} = varray_append({node.name}, &{node.name}_elem{i})")
                    
                    return "; ".join(lines)
                    
                # Empty array initialization
                else:
                    return f"VArray* {node.name} = varray_create(0, sizeof({c_type}))"
            else:
                c_type = FIRETYPE_TO_C.get(fire_type)
                expr_code = self._visit(node.children[0]) if node.children else ""
                qualifiers = []
                if node.is_const:
                    qualifiers.append("const")
                qualifiers.append(c_type)
                qualified_type = " ".join(qualifiers)
                # Note: do not add semicolon here; leave that to emit_statement.
                return f"{qualified_type} {node.name} = {expr_code}"
                
        elif node.node_type == NodeTypes.ARRAY_LITERAL:
            # Handle array literals without a specific array type
            # For standalone array literals (not part of a variable declaration)
            
            # Check if this is a string array by examining the first child token
            is_string_array = False
            fire_type = "int"  # Default to int if we can't determine the type
            
            if node.children and len(node.children) > 0:
                first_child = node.children[0]
                if first_child.token and first_child.token.type == "STRING_LITERAL":
                    is_string_array = True
                    fire_type = "string"
                elif first_child.var_type:
                    fire_type = first_child.var_type
            
            c_type = FIRETYPE_TO_C.get(fire_type, "int")
            array_size = len(node.children)
            
            temp_var = f"temp_array_{self.array_temp_counter}"
            self.array_temp_counter += 1
            
            lines = [
                f"VArray* {temp_var} = varray_create({array_size}, sizeof({c_type}))"
            ]
            
            # Use unique variable names for each element
            for i, elem in enumerate(node.children):
                elem_value = self._visit(elem)
                lines.append(f"{c_type} {temp_var}_elem{i} = {elem_value}")
                lines.append(f"{temp_var} = varray_append({temp_var}, &{temp_var}_elem{i})")
                
            return "; ".join(lines)
                
        elif node.node_type == NodeTypes.ARRAY_ACCESS:
            # Handle array access: arr[idx]
            array_node = node.children[0]
            index_node = node.children[1]
            
            array_name = self._visit(array_node)
            index_expr = self._visit(index_node)
            
            # Get the type of the array
            array_type_info = self.symbol_table.get(array_name, ("int", True))
            c_type = FIRETYPE_TO_C.get(array_type_info[0], "int")
            
            # Access the element in the VArray
            # Note: This is a simplification. VArray access would actually be more complex
            return f"(({c_type}*)({array_name}->data))[{index_expr}]"
            
        elif node.node_type == NodeTypes.METHOD_CALL:
            # Handle method call: obj.method(args)
            object_node = node.children[0]
            object_code = self._visit(object_node)
            method_name = node.name
            
            # Process method arguments (skip the first child which is the object itself)
            args = []
            for i in range(1, len(node.children)):
                args.append(self._visit(node.children[i]))
                
            # Handle array methods
            if object_node.var_type and self.symbol_table.get(object_node.name, (None, False))[1]:
                if method_name == "pop":
                    # pop(index) - Remove and return element at index
                    if args:
                        index = args[0]
                        arr_type_info = self.symbol_table.get(object_node.name, ("int", True))
                        c_type = FIRETYPE_TO_C.get(arr_type_info[0], "int")
                        
                        # Create a temporary variable to hold the popped value
                        temp_var = f"popped_value_{self.array_temp_counter}"
                        self.array_temp_counter += 1
                        
                        # Generate code to get the element, remove it, and return it
                        # Fix: Add semicolon before the closing brace
                        return f"({{{c_type} {temp_var} = (({c_type}*)({object_code}->data))[{index}]; {object_code} = varray_remove({object_code}, {index}); {temp_var};}})"
                    else:
                        # Default to popping the last element if no index is provided
                        arr_type_info = self.symbol_table.get(object_node.name, ("int", True))
                        c_type = FIRETYPE_TO_C.get(arr_type_info[0], "int")
                        
                        temp_var = f"popped_value_{self.array_temp_counter}"
                        self.array_temp_counter += 1
                        
                        # Fix: Add semicolon before the closing brace
                        return f"({{{c_type} {temp_var} = (({c_type}*)({object_code}->data))[{object_code}->size - 1]; {object_code} = varray_remove({object_code}, {object_code}->size - 1); {temp_var};}})"
                        
                elif method_name == "append":
                    # append(element) - Add element to the end of array
                    if args:
                        element = args[0]
                        arr_type_info = self.symbol_table.get(object_node.name, ("int", True))
                        c_type = FIRETYPE_TO_C.get(arr_type_info[0], "int")
                        
                        return f"{object_code} = varray_append({object_code}, &({c_type}){{{element}}})"
                        
                elif method_name == "insert":
                    # insert(index, element) - Insert element at index
                    if len(args) >= 2:
                        index = args[0]
                        element = args[1]
                        arr_type_info = self.symbol_table.get(object_node.name, ("int", True))
                        c_type = FIRETYPE_TO_C.get(arr_type_info[0], "int")
                        
                        return f"{object_code} = varray_insert({object_code}, {index}, &({c_type}){{{element}}})"
                
                elif method_name == "clear":
                    # clear() - Remove all elements
                    return f"varray_clear({object_code})"
                    
                elif method_name == "length" or method_name == "size":
                    # Return the size of the array
                    return f"{object_code}->size"
            
            # Default case for unknown methods
            return f"{object_code}.{method_name}({', '.join(args)})"
            
        elif node.node_type == NodeTypes.VARIABLE_ASSIGNMENT:
            expr_code = self._visit(node.children[0]) if node.children else ""
            return f"{node.name} = {expr_code}"
        elif node.node_type == NodeTypes.BINARY_EXPRESSION:
            left = self._visit(node.children[0])
            right = self._visit(node.children[1])

            if node.children[0].token is None or node.children[1].token is None:
                raise ValueError("temp: Cannot concatenate non-string type")

            if node.children[0].token.type == "STRING_LITERAL" or node.children[0].return_type == "string" or node.children[0].var_type == "string":
                if node.children[1].token.type == "STRING_LITERAL" or node.children[1].return_type == "string" or node.children[1].var_type == "string":
                    node.return_type = "string"
                    return f"firescript_strcat({left}, {right})"
                else:
                    raise ValueError("temp: Cannot concatenate string with non-string type")
            
            op = node.name
            return f"({left} {op} {right})"
        elif node.node_type == NodeTypes.LITERAL:
            if node.token is None:
                raise ValueError("temp: Cannot concatenate non-string type")
            return node.token.value
        elif node.node_type == NodeTypes.IDENTIFIER:
            return node.name
        elif node.node_type == NodeTypes.FUNCTION_CALL:
            if node.name == "print":
                arg = node.children[0]
                # Special handling for print of method call with side effects (like pop)
                if arg.node_type == NodeTypes.METHOD_CALL:
                    obj = arg.children[0]
                    if obj.node_type == NodeTypes.IDENTIFIER:
                        obj_name = obj.name
                        elem_type, is_arr = self.symbol_table.get(obj_name, (None, False))
                        if is_arr:
                            temp_var = f"print_tmp_{self.array_temp_counter}"
                            self.array_temp_counter += 1
                            # Generate the pop code as assignment and update
                            pop_code = self._visit(arg)
                            # pop_code is a statement expression, so extract the type and value
                            if elem_type == "string":
                                assign = f"char* {temp_var} = {pop_code};"
                                print_stmt = f'printf("%s\\n", {temp_var})'
                            elif elem_type in ("int", "bool"):
                                assign = f"int {temp_var} = {pop_code};"
                                print_stmt = f'printf("%d\\n", {temp_var})'
                            elif elem_type in ("float", "double"):
                                assign = f"{elem_type} {temp_var} = {pop_code};"
                                print_stmt = f'printf("%f\\n", {temp_var})'
                            else:
                                assign = f"int {temp_var} = {pop_code};"
                                print_stmt = f'printf("%d\\n", {temp_var})'
                            return assign + "\n" + print_stmt
                # ...existing IDENTIFIER and ARRAY_ACCESS handling...
                arg_code = self._visit(arg)
                if arg.node_type == NodeTypes.IDENTIFIER:
                    arg_type_info = self.symbol_table.get(arg_code, ("int", False))
                    if arg_type_info[1]:  # is_array
                        return f'firescript_print_array({arg_code}, "{arg_type_info[0]}")'
                if arg.node_type == NodeTypes.ARRAY_ACCESS:
                    array_node = arg.children[0]
                    array_name = self._visit(array_node)
                    array_type_info = self.symbol_table.get(array_name, ("int", False))
                    if array_type_info[0] == "int":
                        return f'printf("%d\\n", {arg_code})'
                    elif array_type_info[0] == "float":
                        return f'printf("%f\\n", {arg_code})'
                    elif array_type_info[0] == "double":
                        return f'printf("%f\\n", {arg_code})'
                    elif array_type_info[0] == "string":
                        return f'printf("%s\\n", {arg_code})'
                    else:
                        return f'printf("%d\\n", {arg_code})'
                # ...existing code for literals, identifiers, etc...
                return f'printf("%s\\n", {arg_code})'
            elif node.name == "input":
                return f"firescript_input({self._visit(node.children[0])})"
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
        elif node.node_type == NodeTypes.EQUALITY_EXPRESSION:
            leftNode = node.children[0]
            rightNode = node.children[1]
            left = self._visit(leftNode)
            right = self._visit(rightNode)

            if leftNode.token is None or rightNode.token is None:
                raise ValueError("temp: Cannot compare non-string type")

            if leftNode.token.type == "STRING_LITERAL" or leftNode.return_type == "string" or leftNode.var_type == "string":
                if rightNode.token.type == "STRING_LITERAL" or rightNode.return_type == "string" or rightNode.var_type == "string":
                    node.return_type = "bool"
                    return f"firescript_strcmp({left}, {right})"
                else:
                    raise ValueError("temp: Cannot compare string with non-string type")
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
            left = self._visit(node.children[0])
            right = self._visit(node.children[1])
            op = node.name
            return f"({left} {op} {right})"
        else:
            return ""
