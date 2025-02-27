from enum import Enum

class NodeTypes(Enum):
    ROOT = "Root"
    IF_STATEMENT = "IfStatement"
    ELIF_STATEMENT = "ElifStatement"
    ELSE_STATEMENT = "ElseStatement"
    WHILE_STATEMENT = "WhileStatement"
    BREAK_STATEMENT = "BreakStatement"
    CONTINUE_STATEMENT = "ContinueStatement"
    VARIABLE_DECLARATION = "VariableDeclaration"
    VARIABLE_ASSIGNMENT = "VariableAssignment"
    BINARY_EXPRESSION = "BinaryExpression"
    EQUALITY_EXPRESSION = "EqualityExpression"
    LITERAL = "Literal"
    IDENTIFIER = "Identifier"
    FUNCTION_CALL = "FunctionCall"
    SCOPE = "Scope"