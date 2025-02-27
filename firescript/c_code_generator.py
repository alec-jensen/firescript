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
        self.symbol_table: dict[str, str] = {}

    def generate(self) -> str:
        header = '#include <stdio.h>\n#include <stdbool.h>\n#include <string.h>\n#include "firescript/runtime/runtime.h"\n#include "firescript/runtime/conversions.h"\n'
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
            self.symbol_table[node.name] = node.var_type
            fire_type = node.var_type
            if fire_type not in FIRETYPE_TO_C:
                raise ValueError(f"Unknown type: {fire_type}")
            c_type = FIRETYPE_TO_C.get(fire_type)
            expr_code = self._visit(node.children[0]) if node.children else ""
            qualifiers = []
            if node.is_const:
                qualifiers.append("const")
            qualifiers.append(c_type)
            qualified_type = " ".join(qualifiers)
            # Note: do not add semicolon here; leave that to emit_statement.
            return f"{qualified_type} {node.name} = {expr_code}"
        elif node.node_type == NodeTypes.VARIABLE_ASSIGNMENT:
            expr_code = self._visit(node.children[0]) if node.children else ""
            return f"{node.name} = {expr_code}"
        elif node.node_type == NodeTypes.BINARY_EXPRESSION:
            left = self._visit(node.children[0])
            right = self._visit(node.children[1])

            if node.children[0].token.type == "STRING_LITERAL" or node.children[0].return_type == "string" or node.children[0].var_type == "string":
                if node.children[1].token.type == "STRING_LITERAL" or node.children[1].return_type == "string" or node.children[1].var_type == "string":
                    node.return_type = "string"
                    return f"firescript_strcat({left}, {right})"
                else:
                    raise ValueError("temp: Cannot concatenate string with non-string type")
            
            op = node.name
            return f"({left} {op} {right})"
        elif node.node_type == NodeTypes.LITERAL:
            return node.token.value
        elif node.node_type == NodeTypes.IDENTIFIER:
            return node.name
        elif node.node_type == NodeTypes.FUNCTION_CALL:
            if node.name == "print":
                arg = node.children[0]
                arg_code = self._visit(arg)
                if arg.node_type == NodeTypes.LITERAL:
                    if arg.token.type == "STRING_LITERAL":
                        statement = f'printf("%s\\n", {arg_code})'
                    elif arg.token.type in ("INTEGER_LITERAL", "BOOLEAN_LITERAL"):
                        statement = f'printf("%d\\n", {arg_code})'
                    elif arg.token.type == "FLOAT_LITERAL":
                        statement = f'printf("%ff\\n", {arg_code})'
                    elif arg.token.type == "DOUBLE_LITERAL":
                        statement = f'printf("%f\\n", {arg_code})'
                    else:
                        statement = f'printf("%s\\n", {arg_code})'
                elif arg.node_type == NodeTypes.IDENTIFIER:
                    arg_type = self.symbol_table.get(arg_code, "int")
                    if arg_type == "int":
                        statement = f'printf("%d\\n", {arg_code})'
                    elif arg_type == "float":
                        statement = f'printf("%f\\n", {arg_code})'
                    elif arg_type == "double":
                        statement = f'printf("%f\\n", {arg_code})'
                    elif arg_type == "char*":
                        statement = f'printf("%s\\n", {arg_code})'
                    else:
                        statement = f'printf("%s\\n", {arg_code})'
                elif arg.node_type == NodeTypes.FUNCTION_CALL:
                    if arg.return_type == "int":
                        statement = f'printf("%d\\n", {arg_code})'
                    elif arg.return_type == "float":
                        statement = f'printf("%f\\n", {arg_code})'
                    elif arg.return_type == "double":
                        statement = f'printf("%f\\n", {arg_code})'
                    elif arg.return_type == "string":
                        statement = f'printf("%s\\n", {arg_code})'
                    elif arg.return_type == "bool":
                        statement = f'printf("%d\\n", {arg_code})'
                    else:
                        statement = f'printf("%d\\n", {arg_code})'
                elif arg.node_type == NodeTypes.BINARY_EXPRESSION:
                    if arg.return_type == "int":
                        statement = f'printf("%d\\n", {arg_code})'
                    elif arg.return_type == "float":
                        statement = f'printf("%f\\n", {arg_code})'
                    elif arg.return_type == "double":
                        statement = f'printf("%f\\n", {arg_code})'
                    elif arg.return_type == "string":
                        statement = f'printf("%s\\n", {arg_code})'
                    elif arg.return_type == "bool":
                        statement = f'printf("%d\\n", {arg_code})'
                    else:
                        statement = f'printf("%d\\n", {arg_code})'
                else:
                    statement = f'printf("%d\\n", {arg_code})'
                return statement
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
