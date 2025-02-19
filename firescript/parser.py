import logging
from typing import Union, Optional

from lexer import Token
from utils.file_utils import get_line_and_coumn_from_index, get_line
from enums import NodeTypes


class ASTNode:
    def __init__(
        self,
        node_type: NodeTypes,
        token: Optional[Token],
        name,
        children,
        position,
        var_type: Optional[str] = None,
        is_nullable: bool = False,
        is_const: bool = False,
    ):
        self.node_type: NodeTypes = node_type
        self.token = token
        self.name = name
        self.children = children or []
        self.position = position
        self.is_nullable = is_nullable
        self.is_const = is_const
        self.var_type = var_type

    def tree(self, prefix: str = "", is_last: bool = True) -> str:
        # Build the display line differently for variable declarations.
        if self.node_type == NodeTypes.VARIABLE_DECLARATION:
            pre = []
            if self.is_nullable:
                pre.append("nullable")
            if self.is_const:
                pre.append("const")
            if self.var_type:
                pre.append(self.var_type)
            
            post = []
            # TODO: add post modifiers

            line_content = f"{self.node_type}"
            if pre:
                line_content += f" {' '.join(pre)} {self.name}"
            if post:
                line_content += f" {' '.join(post)}"
        else:
            line_content = f"{self.node_type} {self.name}"

        lines = []
        if prefix == "":
            lines.append(line_content)
        else:
            connector = "└── " if is_last else "├── "
            lines.append(prefix + connector + line_content)
        new_prefix = prefix + ("    " if is_last else "│   ")
        childs = [child for child in self.children if child is not None]
        for i, child in enumerate(childs):
            is_last_child = i == (len(childs) - 1)
            lines.append(child.tree(new_prefix, is_last_child))
        return "\n".join(lines)

    def __str__(self, level: int = 0) -> str:
        return self.tree()

    def __repr__(self):
        return self.__str__()


class Parser:
    builtin_functions: list[str] = [
        "print",
        "input",
    ]

    def __init__(self, tokens: list[Token], file: str, filename: str):
        self.tokens: list[Token] = tokens

        self.current_token: Optional[Token] = self.tokens[0]

        self.ast = ASTNode(NodeTypes.ROOT, None, "program", [], 0)

        self.file: str = file
        self.filename: str = filename

        self.errors: list[tuple[str, int, int]] = []

    def advance(self):
        """Advance the current token to the next non-whitespace token."""
        current_index = self.tokens.index(self.current_token)
        new_index = current_index + 1
        while new_index < len(self.tokens) and self.tokens[new_index].type == "IDENTIFIER" and self.tokens[new_index].value.strip() == "":
            new_index += 1
        self.current_token = self.tokens[new_index] if new_index < len(self.tokens) else None

    def peek(self, offset: int = 1) -> Optional[Token]:
        """Peek at the non-whitespace token at the given offset."""
        count = 0
        start_index = self.tokens.index(self.current_token) + 1
        for token in self.tokens[start_index:]:
            if token.type == "IDENTIFIER" and token.value.strip() == "":
                continue
            count += 1
            if count == offset:
                return token
        return None

    def consume(self, token_type: str) -> Optional[Token]:
        """Consume the current token if it is of the given type."""
        if self.current_token.type == token_type:
            token = self.current_token
            self.advance()
            return token
        return None

    def expect(self, token_type: str) -> Optional[Token]:
        """Expect the current token to be of the given type."""
        if self.current_token.type == token_type:
            token = self.current_token
            self.advance()
            return token
        self.error(
            f"Expected {token_type} but got {self.current_token.type}",
            self.current_token,
        )
        return None

    def error(self, text: str, token: Optional[Token] = None):
        if self.file is None or token is None:
            logging.error(text)
            return

        line_num, column_num = get_line_and_coumn_from_index(self.file, token.index)
        line_text = get_line(self.file, line_num)
        logging.error(
            text
            + f"\n> {line_text.strip()}\n"
            + " " * (column_num + 2)
            + "^"
            + f"\n({self.filename}:{line_num}:{column_num})"
        )
        self.errors.append((text, line_num, column_num))

    def parse_expression(self):
        """Parse an expression using additive operators."""
        return self.parse_additive()

    def parse_additive(self):
        """Parse additive expressions (handles + and -)."""
        node = self.parse_multiplicative()
        while self.current_token and self.current_token.type in ("ADD", "SUBTRACT"):
            op_token = self.current_token
            self.advance()
            right = self.parse_multiplicative()
            node = ASTNode(
                NodeTypes.BINARY_EXPRESSION,
                op_token,
                op_token.value,
                [node, right],
                op_token.index,
            )
        return node

    def parse_multiplicative(self):
        """Parse multiplicative expressions (handles *, /, and %)."""
        node = self.parse_primary()
        while self.current_token and self.current_token.type in (
            "MULTIPLY",
            "DIVIDE",
            "MODULO",
        ):
            op_token = self.current_token
            self.advance()
            right = self.parse_primary()
            node = ASTNode(
                NodeTypes.BINARY_EXPRESSION,
                op_token,
                op_token.value,
                [node, right],
                op_token.index,
            )
        return node

    def parse_primary(self):
        """Parse primary expressions such as literals, identifiers, or a parenthesized expression."""
        token = self.current_token
        if token.type == "OPEN_PAREN":
            # Grouping: ( expression )
            self.advance()  # skip '('
            expr = self.parse_expression()
            if self.current_token.type != "CLOSE_PAREN":
                self.error("Expected closing parenthesis", self.current_token)
                return expr
            self.advance()  # skip ')'
            return expr
        elif token.type in (
            "BOOLEAN_LITERAL",
            "INTEGER_LITERAL",
            "DOUBLE_LITERAL",
            "FLOAT_LITERAL",
            "STRING_LITERAL",
        ):
            self.advance()
            return ASTNode(NodeTypes.LITERAL, token, token.value, [], token.index)
        elif token.type == "IDENTIFIER":
            self.advance()
            return ASTNode(NodeTypes.IDENTIFIER, token, token.value, [], token.index)
        else:
            self.error(f"Unexpected token {token.value}", token)
            self.advance()
            return None

    def parse_typed_variable_declaration(self):
        logging.debug("Parsing typed variable declaration...")
        is_nullable = False
        is_const = False

        while self.current_token and self.current_token.type in ("NULLABLE", "CONST"):
            if self.current_token.type == "NULLABLE":
                self.advance()
                is_nullable = True
            elif self.current_token.type == "CONST":
                self.advance()
                is_const = True

        if self.current_token and self.current_token.type in ("INT", "FLOAT", "DOUBLE", "BOOL", "STRING", "TUPLE"):
            type_token = self.consume(self.current_token.type)
        else:
            self.error("Expected type declaration", self.current_token)
            self._sync_to_semicolon()
            return None

        identifier = self.consume("IDENTIFIER")
        if identifier is None:
            self.error("Expected identifier", self.current_token)
            self._sync_to_semicolon()
            return None

        assign_token = self.consume("ASSIGN")
        if assign_token is None:
            self.error("Expected assignment operator", self.current_token)
            self._sync_to_semicolon()
            return None

        value = self.parse_expression()
        if value is None:
            self.error("Expected expression after assignment operator", self.current_token)
            self._sync_to_semicolon()
            return None

        semicolon_token = self.consume("SEMICOLON")
        if semicolon_token is None:
            self.error("Expected semicolon", self.current_token)
            return None

        node = ASTNode(
            NodeTypes.VARIABLE_DECLARATION,
            identifier,
            identifier.value,
            [value],
            identifier.index,
            type_token.value,
            is_nullable,
            is_const,
        )
        return node
    
    def parse_variable_assignment(self):
        logging.debug("Parsing variable assignment...")
        identifier = self.consume("IDENTIFIER")
        if identifier is None:
            self.error("Expected identifier", self.current_token)
            self._sync_to_semicolon()
            return None

        assign_token = self.consume("ASSIGN")
        if assign_token is None:
            self.error("Expected assignment operator", self.current_token)
            self._sync_to_semicolon()
            return None

        value = self.parse_expression()
        if value is None:
            self.error("Expected expression after assignment operator", self.current_token)
            self._sync_to_semicolon()
            return None

        semicolon_token = self.consume("SEMICOLON")
        if semicolon_token is None:
            self.error("Expected semicolon", self.current_token)
            return None

        node = ASTNode(
            NodeTypes.VARIABLE_ASSIGNMENT,
            identifier,
            identifier.value,
            [value],
            identifier.index,
        )
        return node
    
    def parse_function_call(self):
        """Parse a function call: functionName(argument, ...)."""
        function_name_token = self.consume("IDENTIFIER")
        if function_name_token is None:
            self.error("Expected function name for function call", self.current_token)
            return None
        
        open_paren = self.consume("OPEN_PAREN")
        if open_paren is None:
            self.error("Expected '(' after function name", self.current_token)
            return None

        arguments = []
        if self.current_token and self.current_token.type != "CLOSE_PAREN":
            while True:
                arg = self.parse_expression()
                if arg is not None:
                    arguments.append(arg)
                if self.current_token and self.current_token.type == "COMMA":
                    self.consume("COMMA")
                    continue
                break

        close_paren = self.consume("CLOSE_PAREN")
        if close_paren is None:
            self.error("Expected ')' after function arguments", self.current_token)
            return None

        return ASTNode(
            NodeTypes.FUNCTION_CALL,  # Ensure NodeTypes.FUNCTION_CALL exists in your enums.
            function_name_token,
            function_name_token.value,
            arguments,
            function_name_token.index,
        )
    
    def _sync_to_semicolon(self):
        """Advance tokens until we reach a semicolon or run out of tokens."""
        while self.current_token and self.current_token.type != "SEMICOLON":
            self.advance()
        self.consume("SEMICOLON")

    def parse(self):
        logging.debug("Parsing tokens...")
        while self.current_token:
            if self.current_token.type in (
                "INT",
                "FLOAT",
                "DOUBLE",
                "BOOL",
                "STRING",
                "TUPLE",
                "NULLABLE",
                "CONST",
            ):
                node = self.parse_typed_variable_declaration()
                if node is not None:
                    self.ast.children.append(node)
            elif self.current_token.type == "IDENTIFIER":
                if self.peek().type == "ASSIGN":
                    node = self.parse_variable_assignment()
                    if node is not None:
                        self.ast.children.append(node)
                elif self.peek().type == "OPEN_PAREN":
                    node = self.parse_function_call()
                    if node is not None:
                        self.ast.children.append(node)
                else:
                    self.error(
                        f"Unexpected token '{self.current_token.value}'", self.current_token
                    )
                    self.advance()
            else:
                self.error(
                    f"Unexpected token '{self.current_token.value}'", self.current_token
                )
                self.advance()
        return self.ast
