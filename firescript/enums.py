from enum import Enum

class NodeTypes(Enum):
    ROOT = "Root"
    IF_STATEMENT = "IfStatement"
    VARIABLE_DECLARATION = "VariableDeclaration"
    VARIABLE_ASSIGNMENT = "VariableAssignment"
    BINARY_EXPRESSION = "BinaryExpression"
    LITERAL = "Literal"
    IDENTIFIER = "Identifier"
    FUNCTION_CALL = "FunctionCall"