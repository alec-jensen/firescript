# firescript/c_code_generator.py
from enums import NodeTypes  # [firescript/enums.py]
from parser import ASTNode  # [firescript/parser.py]
import logging

# A simple type mapping from firescript types to C types.
FIRETYPE_TO_C: dict[str, str] = {
    # Use GMP arbitrary precision integers
    "int": "mpz_t",
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
        header = '#include <stdio.h>\n#include <stdbool.h>\n#include <string.h>\n#include <gmp.h>\n#include "firescript/runtime/runtime.h"\n#include "firescript/runtime/conversions.h"\n#include "firescript/runtime/varray.h"\n'
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
        # Handle big-int (mpz_t) assignments
        if node.node_type == NodeTypes.VARIABLE_ASSIGNMENT \
           and self.symbol_table.get(node.name, (None, False))[0] == "int":
            expr_code = self._visit(node.children[0]) if node.children else "0"
            return f"mpz_set({node.name}, {expr_code});"

        # Only do ref-count adjustments for string assignments
        elif node.node_type == NodeTypes.VARIABLE_ASSIGNMENT and self.symbol_table.get(node.name, (None, False))[0] == "string":
            # Emit code to decrement the old reference and increment the new one
            expr_code = self._visit(node.children[0]) if node.children else "NULL"
            return f"decrement_ref_count({node.name}); {node.name} = {expr_code}; increment_ref_count({node.name});"

        # Handle pop used as a standalone statement: remove element
        elif node.node_type == NodeTypes.METHOD_CALL and node.name == "pop":
            obj_node = node.children[0]
            obj_name = obj_node.name if obj_node.node_type == NodeTypes.IDENTIFIER else None
            # Determine index: mpz_t expression or default last element
            if len(node.children) > 1:
                idx_expr = self._visit(node.children[1])
                idx_code = f"mpz_get_ui({idx_expr})"
            else:
                idx_code = f"{obj_name}->size - 1"
            return f"{obj_name} = varray_remove({obj_name}, {idx_code});"

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
                    lines = [f"VArray* {node.name} = varray_create({array_size}, sizeof({c_type}))"]
                    for i, elem in enumerate(array_elements):
                        elem_code = self._visit(elem)
                        # Handle element types
                        if fire_type == "string":
                            # string array: store char*
                            lines.append(f"char* {node.name}_elem{i} = {elem_code}")
                            lines.append(f"{node.name} = varray_append({node.name}, &{node.name}_elem{i})")
                        else:
                            # big-int element
                            lines.append(f"mpz_t {node.name}_elem{i}")
                            lines.append(f"mpz_init({node.name}_elem{i})")
                            lines.append(f"mpz_set({node.name}_elem{i}, {elem_code})")
                            lines.append(f"{node.name} = varray_append({node.name}, &{node.name}_elem{i})")
                    return "; ".join(lines)
                    
                # Empty array initialization
                else:
                    return f"VArray* {node.name} = varray_create(0, sizeof({c_type}))"
            else:
                # Big integer variable initialization
                if fire_type == "int":
                    child = node.children[0] if node.children else None
                    # Special handling for initialization with pop()
                    if child and child.node_type == NodeTypes.METHOD_CALL and child.name == "pop":
                        obj_node_of_pop = child.children[0]
                        # Assuming obj_node_of_pop is an IDENTIFIER for simplicity here
                        obj_code_of_pop = obj_node_of_pop.name 
                        
                        pop_args_nodes = child.children[1:]
                        pop_args_code = [self._visit(arg_node) for arg_node in pop_args_nodes]

                        c_idx_expr_str_for_pop = ""
                        if pop_args_code: # Index provided for pop
                            index_expr_code_for_pop = pop_args_code[0]
                            c_idx_expr_str_for_pop = f"mpz_get_ui({index_expr_code_for_pop})"
                        else: # No index for pop
                            c_idx_expr_str_for_pop = f"{obj_code_of_pop}->size - 1"
                        
                        # varray_pop will mpz_init(node.name)
                        return f"mpz_t {node.name}; varray_pop({node.name}, &{obj_code_of_pop}, {c_idx_expr_str_for_pop});"
                    # Regular int initializer: literal via set_si, others via mpz_set
                    elif child and child.token and child.token.type == "INTEGER_LITERAL":
                        val = child.token.value
                        return f"mpz_t {node.name}; mpz_init({node.name}); mpz_set_si({node.name}, {val});"
                    else: # Non-literal, non-pop expression
                        expr = self._visit(child) if child else "0" # Default to 0 if no initializer
                        return f"mpz_t {node.name}; mpz_init({node.name}); mpz_set({node.name}, {expr});"
                # Default for other types
                c_type = FIRETYPE_TO_C.get(fire_type)
                expr_code = self._visit(node.children[0]) if node.children else ""
                qualifiers = []
                if node.is_const:
                    qualifiers.append("const")
                qualifiers.append(c_type)
                qualified_type = " ".join(qualifiers)
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
                elem_code = self._visit(elem)
                lines.append(f"mpz_t {temp_var}_elem{i}")
                lines.append(f"mpz_init({temp_var}_elem{i})")
                lines.append(f"mpz_set({temp_var}_elem{i}, {elem_code})")
                lines.append(f"{temp_var} = varray_append({temp_var}, &{temp_var}_elem{i})")
                
            return "; ".join(lines)
                
        elif node.node_type == NodeTypes.ARRAY_ACCESS:
            # Handle array access: arr[idx]
            array_node = node.children[0]
            index_node = node.children[1]
            
            array_name = self._visit(array_node) # Should be the C variable name of the array
            index_expr_code = self._visit(index_node) # C code for the index expression (mpz_t)
            
            # Determine if index_node's type is 'int' (meaning mpz_t) to decide on mpz_get_ui
            index_firescript_type = getattr(index_node, 'return_type', None)
            if index_firescript_type is None: # Fallback for literals or simple identifiers
                if index_node.node_type == NodeTypes.LITERAL and index_node.token.type == "INTEGER_LITERAL":
                    index_firescript_type = "int"
                elif index_node.node_type == NodeTypes.IDENTIFIER:
                    index_firescript_type, _ = self.symbol_table.get(index_node.name, ("unknown", False))

            c_index_access_expr = index_expr_code
            if index_firescript_type == "int":
                c_index_access_expr = f"mpz_get_ui({index_expr_code})"
            
            element_c_type = FIRETYPE_TO_C.get(array_node.var_type or 'int', 'int') # Default to int if var_type is None
            return f"(({element_c_type}*)({array_name}->data))[{c_index_access_expr}]"
            
        elif node.node_type == NodeTypes.METHOD_CALL:
            # Handle method call: obj.method(args)
            object_node = node.children[0]
            object_code = self._visit(object_node) # C name of the object/array
            method_name = node.name

            args_code = [self._visit(child) for child in node.children[1:]]

            if object_node.var_type and self.symbol_table.get(object_node.name, (None, False))[1]: # If it's an array
                elem_type, _ = self.symbol_table.get(object_node.name, ("int", False))

                if method_name == "pop":
                    if elem_type != "int":
                        # Placeholder for future support of pop on other array types
                        return "/* Pop on non-int array not fully supported yet */"

                    temp_popped_mpz = f"__popped_val_{self.array_temp_counter}"
                    self.array_temp_counter += 1
                    
                    c_idx_expr_str = ""
                    if args_code: # Index is provided: e.g., pop(i)
                        index_mpz_expr_code = args_code[0]
                        c_idx_expr_str = f"mpz_get_ui({index_mpz_expr_code})"
                    else: # No index: pop last element
                        c_idx_expr_str = f"{object_code}->size - 1"
                    
                    # varray_pop initializes the mpz_t it's given.
                    # The block expression declares the temp mpz_t, calls varray_pop into it, then yields the temp mpz_t.
                    node.return_type = "int" # Pop returns an int (mpz_t)
                    return f"({{ mpz_t {temp_popped_mpz}; varray_pop({temp_popped_mpz}, &{object_code}, {c_idx_expr_str}); {temp_popped_mpz}; }})"
                elif method_name == "append":
                    if args_code:
                        element = args_code[0]
                        # Get element type from symbol table
                        tmp = f"_tmp_elem_{self.array_temp_counter}"
                        self.array_temp_counter += 1
                        lines = []
                        if elem_type == "string":
                            # append string
                            lines.append(f"char* {tmp} = {element};")
                            lines.append(f"{object_code} = varray_append({object_code}, &{tmp});")
                        else:
                            # append big-int or other primitives
                            lines.append(f"mpz_t {tmp}; mpz_init({tmp}); mpz_set({tmp}, {element});")
                            lines.append(f"{object_code} = varray_append({object_code}, &{tmp});")
                        return "\n".join(lines)
                elif method_name == "insert":
                    if len(args_code) >= 2:
                        index = args_code[0]
                        element = args_code[1]
                        # Convert big-int index to size_t and prep element
                        idx = f"mpz_get_ui({index})"
                        tmp2 = f"_tmp_elem_{self.array_temp_counter}"
                        self.array_temp_counter += 1
                        lines = []
                        if elem_type == "string":
                            lines.append(f"char* {tmp2} = {element}")
                            lines.append(f"{object_code} = varray_insert({object_code}, {idx}, &{tmp2})")
                        else:
                            lines.append(f"mpz_t {tmp2}; mpz_init({tmp2}); mpz_set({tmp2}, {element});")
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

            # Use GMP functions for big int operations
            if node.return_type == "int":
                op = node.name
                if op == "+":
                    return f"({{ mpz_t tmp; mpz_init(tmp); mpz_add(tmp, {left}, {right}); tmp; }})"
                if op == "-":
                    return f"({{ mpz_t tmp; mpz_init(tmp); mpz_sub(tmp, {left}, {right}); tmp; }})"
                if op == "*":
                    return f"({{ mpz_t tmp; mpz_init(tmp); mpz_mul(tmp, {left}, {right}); tmp; }})"
                if op == "/":
                    return f"({{ mpz_t tmp; mpz_init(tmp); mpz_fdiv_q(tmp, {left}, {right}); tmp; }})"
                if op == "%":
                    return f"({{ mpz_t tmp; mpz_init(tmp); mpz_fdiv_r(tmp, {left}, {right}); tmp; }})"
            if (node.children[0].token and node.children[0].token.type == "STRING_LITERAL") or node.children[0].return_type == "string" or node.children[0].var_type == "string":
                if node.children[1] is not None and ((node.children[1].token is not None and node.children[1].token.type == "STRING_LITERAL") or node.children[1].return_type == "string" or node.children[1].var_type == "string"):
                    node.return_type = "string"
                    return f"firescript_strcat({left}, {right})"
                else:
                    raise ValueError("temp: Cannot concatenate string with non-string type")
            
            op = node.name
            return f"({left} {op} {right})"
        elif node.node_type == NodeTypes.LITERAL:
            # Big integer literal initialization
            if node.token and node.token.type == "INTEGER_LITERAL":
                val = node.token.value
                return f"({{ mpz_t tmp; mpz_init(tmp); mpz_set_str(tmp, \"{val}\", 10); tmp; }})"
            # Other literals unchanged
            if node.token is None:
                raise ValueError("Literal node missing token")
            return node.token.value
        elif node.node_type == NodeTypes.IDENTIFIER:
            return node.name
        elif node.node_type == NodeTypes.FUNCTION_CALL:
            if node.name == "print":
                arg = node.children[0]
                arg_code = self._visit(arg)
                # Array length/size methods return native size_t
                if arg.node_type == NodeTypes.METHOD_CALL and arg.name in ("length", "size"):
                    return f'printf("%zu\\n", {arg_code})'
                
                arg_type = getattr(arg, 'return_type', None)
                is_arr = False
                
                if arg_type is None:
                    if arg.node_type == NodeTypes.LITERAL and arg.token: # Check token exists
                        if arg.token.type == "BOOLEAN_LITERAL": arg_type = "bool"
                        elif arg.token.type == "STRING_LITERAL": arg_type = "string"
                        elif arg.token.type == "INTEGER_LITERAL": arg_type = "int"
                        elif arg.token.type == "FLOAT_LITERAL": arg_type = "float"
                        elif arg.token.type == "DOUBLE_LITERAL": arg_type = "double"
                    elif arg.node_type == NodeTypes.IDENTIFIER:
                        arg_type, is_arr = self.symbol_table.get(arg.name, (None, False))
                    elif arg.node_type == NodeTypes.ARRAY_ACCESS:
                        arr_node = arg.children[0]
                        # Ensure arr_node.var_type is populated by type resolution
                        arg_type = arr_node.var_type if hasattr(arr_node, 'var_type') else None


                # Fix all printf/gmp_printf calls to ensure newlines are properly escaped
                # and string literals don't contain actual newlines
                if arg_type == "bool":
                    return f'printf("%s\\n", {arg_code} ? "true" : "false")'
                if arg_type == "int": # This will handle mpz_t expressions from pop()
                    return f'gmp_printf("%Zd\\n", {arg_code})'
                if arg_type in ("float", "double"):
                    return f'printf("%f\\n", {arg_code})'
                if arg_type == "string":
                    return f'printf("%s\\n", {arg_code})'
                
                if arg.node_type == NodeTypes.IDENTIFIER and is_arr: # Check original is_arr from symbol table
                    # Ensure arg.name is used for array printing if arg_code is complex
                    array_print_name = arg.name if arg.node_type == NodeTypes.IDENTIFIER else arg_code
                    return f'firescript_print_array({array_print_name}, "{arg_type}")'
                
                return f'printf("%s\\n", {arg_code})' # Last resort
            elif node.name == "input":
                return f"firescript_input({self._visit(node.children[0])})"
            elif node.name == "int":
                # Cast string or number to a GMP big integer (mpz_t)
                arg_code = self._visit(node.children[0])
                temp_var = f"__int_temp_{self.array_temp_counter}"
                self.array_temp_counter += 1
                
                # Create a block that initializes an mpz_t, sets its value from the converted int, and yields it
                return f"({{ mpz_t {temp_var}; mpz_init({temp_var}); mpz_set_si({temp_var}, firescript_toInt({arg_code})); {temp_var}; }})"
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

            # Big-int comparison for ints
            if leftNode.var_type == "int" or rightNode.var_type == "int":
                if node.name == "==":
                    return f"(mpz_cmp({left}, {right}) == 0)"
                elif node.name == "!=":
                    return f"(mpz_cmp({left}, {right}) != 0)"

            # String comparison unchanged
            if leftNode.token and leftNode.token.type == "STRING_LITERAL" or leftNode.return_type == "string" or leftNode.var_type == "string":
                if rightNode.token and rightNode.token.type == "STRING_LITERAL" or rightNode.return_type == "string" or rightNode.var_type == "string":
                    node.return_type = "bool"
                    return f"firescript_strcmp({left}, {right})"
                else:
                    raise ValueError("temp: Cannot compare string with non-string type")
            # Default comparison for primitives
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
            # Use GMP for int comparison, direct for others
            if self.symbol_table.get(leftNode.name, (None, False))[0] == "int" and rightNode.token and rightNode.token.type == "INTEGER_LITERAL":
                op = node.name
                comp_value = rightNode.token.value
                if op == "<":
                    return f"(mpz_cmp_si({left}, {comp_value}) < 0)"
                elif op == ">":
                    return f"(mpz_cmp_si({left}, {comp_value}) > 0)"
                elif op == "<=":
                    return f"(mpz_cmp_si({left}, {comp_value}) <= 0)"
                elif op == ">=":
                    return f"(mpz_cmp_si({left}, {comp_value}) >= 0)"
                else:
                    return f"(mpz_cmp({left}, {right}) {op} 0)"
            elif leftNode.var_type == "int" or rightNode.var_type == "int":
                op = node.name
                return f"(mpz_cmp({left}, {right}) {op} 0)"
            op = node.name
            return f"({left} {op} {right})"
        elif node.node_type == NodeTypes.COMPOUND_ASSIGNMENT:
            # Handle compound assignments like += -= *= /= %=
            identifier = node.name
            op = node.token.type
            value = self._visit(node.children[0])
            
            # Check if this is a big-int (mpz_t) variable from symbol table
            is_mpz = self.symbol_table.get(identifier, (None, False))[0] == "int"
            
            if is_mpz:
                # Generate GMP code for the operation
                if op == "ADD_ASSIGN":
                    return f"mpz_add({identifier}, {identifier}, {value});"
                elif op == "SUBTRACT_ASSIGN":
                    return f"mpz_sub({identifier}, {identifier}, {value});"
                elif op == "MULTIPLY_ASSIGN":
                    return f"mpz_mul({identifier}, {identifier}, {value});"
                elif op == "DIVIDE_ASSIGN":
                    return f"mpz_fdiv_q({identifier}, {identifier}, {value});"
                elif op == "MODULO_ASSIGN":
                    return f"mpz_fdiv_r({identifier}, {identifier}, {value});"
                else:
                    # Default to addition if unsupported
                    return f"mpz_add({identifier}, {identifier}, {value});"
            else:
                # Map firescript compound assignment operators to C operators for non-mpz_t types
                op_map = {
                    "ADD_ASSIGN": "+=",
                    "SUBTRACT_ASSIGN": "-=",
                    "MULTIPLY_ASSIGN": "*=",
                    "DIVIDE_ASSIGN": "/=",
                    "MODULO_ASSIGN": "%="
                }
                c_op = op_map.get(op, "+=")  # Default to += if unknown
                return f"{identifier} {c_op} {value};"
            
        elif node.node_type == NodeTypes.UNARY_EXPRESSION:
            # Handle increment/decrement operators
            identifier = node.token.value  # The identifier is in the token value
            op = node.name  # The operator (++ or --) is stored in the name
            
            # Check if this is a big-int (mpz_t) variable from symbol table
            is_mpz = self.symbol_table.get(identifier, (None, False))[0] == "int"
            
            logging.debug(f"is_mpz: {is_mpz}")
            logging.debug(f"Unary expression: {op} {identifier}")
            if is_mpz:
                # Generate GMP code for the operation
                if op == "++":
                    return f"mpz_add_ui({identifier}, {identifier}, 1)"
                elif op == "--":
                    return f"mpz_sub_ui({identifier}, {identifier}, 1)"
                else:
                    # Unrecognized operator, probably a syntax error
                    raise ValueError(f"Unrecognized unary operator '{op}' for {identifier}")
            else:
                # The operator (++ or --) for non-mpz_t types
                if op == "++":
                    return f"{identifier}++"
                elif op == "--":
                    return f"{identifier}--"
                else:
                    # Shouldn't reach here with proper parsing
                    raise ValueError(f"Unrecognized unary operator '{op}' for {identifier}")
        else:
            return ""
