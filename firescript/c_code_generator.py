# firescript/c_code_generator.py
from enums import NodeTypes  # [firescript/enums.py](firescript/enums.py)
from parser import ASTNode  # [firescript/parser.py](firescript/parser.py)

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
        self.symbol_table: dict[str, str] = {}

    def generate(self) -> str:
        # Optionally include some standard headers.
        header = '#include <stdio.h>\n#include <stdbool.h>\n\n'
        body = self._visit(self.ast)
        main_code = "int main(void) {\n"
        if body:
            indented_body = "\n".join("    " + line for line in body.split("\n"))
            main_code += f"{indented_body}\n"
        main_code += "    return 0;\n"
        main_code += "}\n"
        return header + main_code

    def _visit(self, node: ASTNode) -> str:
        # Dispatch based on node type.
        if node.node_type == NodeTypes.ROOT:
            # Generate code for all children.
            lines = []
            for child in node.children:
                code = self._visit(child)
                if code:
                    lines.append(code)
            return "\n".join(lines)
        elif node.node_type == NodeTypes.VARIABLE_DECLARATION:
            self.symbol_table[node.name] = node.var_type
            # Get C type from the Firescript type.
            fire_type = node.var_type
            if fire_type not in FIRETYPE_TO_C:
                raise ValueError(f"Unknown type: {fire_type}")
            c_type = FIRETYPE_TO_C.get(fire_type)
            expr_code = self._visit(node.children[0]) if node.children else ""
            # For const, prepend "const" keyword.
            qualifiers = []
            if node.is_const:
                qualifiers.append("const")
            qualifiers.append(c_type)
            qualified_type = " ".join(qualifiers)
            return f"{qualified_type} {node.name} = {expr_code};"
        elif node.node_type == NodeTypes.VARIABLE_ASSIGNMENT:
            expr_code = self._visit(node.children[0]) if node.children else ""
            return f"{node.name} = {expr_code};"
        elif node.node_type == NodeTypes.BINARY_EXPRESSION:
            # Assume a binary expression with two children.
            left = self._visit(node.children[0])
            right = self._visit(node.children[1])
            # The operator is stored in node.name.
            op = node.name
            return f"({left} {op} {right})"
        elif node.node_type == NodeTypes.LITERAL:
            # For literals, output the value directly.
            return node.token.value if node.token else str(node.name)
        elif node.node_type == NodeTypes.IDENTIFIER:
            return node.name
        elif node.node_type == NodeTypes.FUNCTION_CALL:
            if node.name == "print":
                arg = node.children[0]
                arg_code = self._visit(arg)

                # If literal, check arg.token.type:
                if arg.node_type == NodeTypes.LITERAL:
                    if arg.token.type == "STRING_LITERAL":
                        statement = f'printf("%s\\n", {arg_code});'
                    elif arg.token.type in ("INTEGER_LITERAL", "BOOLEAN_LITERAL"):
                        statement = f'printf("%d\\n", {arg_code});'
                    elif arg.token.type == "FLOAT_LITERAL":
                        statement = f'printf("%ff\\n", {arg_code});'
                    elif arg.token.type == "DOUBLE_LITERAL":
                        statement = f'printf("%f\\n", {arg_code});'
                    else:
                        statement = f'printf("%s\\n", {arg_code});'

                # If identifier, look up its type in symbol_table and map to specifier:
                elif arg.node_type == NodeTypes.IDENTIFIER:
                    arg_type = self.symbol_table.get(arg_code, "int")
                    if arg_type == "int":
                        statement = f'printf("%d\\n", {arg_code});'
                    elif arg_type == "float":
                        statement = f'printf("%f\\n", {arg_code});'
                    elif arg_type == "double":
                        statement = f'printf("%f\\n", {arg_code});'
                    elif arg_type == "char*":  # string
                        statement = f'printf("%s\\n", {arg_code});'
                    else:
                        statement = f'printf("%s\\n", {arg_code});'
                else:
                    # For expressions like BINARY_EXPRESSION, just print the evaluated result
                    statement = f'printf("%d\\n", {arg_code});'

                return statement
            else:
                # Handle other function calls
                args = ", ".join(self._visit(arg) for arg in node.children)
                return f"{node.name}({args});"
        else:
            # For any unsupported cases, return an empty string.
            return ""