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
        return_type: Optional[str] = None,
    ):
        self.node_type: NodeTypes = node_type
        self.token = token
        self.name = name
        self.children: list[ASTNode] = children or []
        self.position = position
        self.is_nullable = is_nullable
        self.is_const = is_const
        self.return_type: Optional[str] = return_type
        self.var_type = var_type
        self.parent: Optional[ASTNode] = None

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
    builtin_functions: dict[str, str] = {
        "print": "void",
        "input": "string",
    }

    def __init__(self, tokens: list[Token], file: str, filename: str):
        self.tokens: list[Token] = tokens

        self.current_token: Optional[Token] = self.tokens[0]

        self.ast = ASTNode(NodeTypes.ROOT, None, "program", [], 0)

        self.file: str = file
        self.filename: str = filename

        self.errors: list[tuple[str, int, int]] = []

    def advance(self):
        """Advance the current token to the next non-whitespace token."""
        if self.current_token is None:
            return

        current_index = self.tokens.index(self.current_token)
        new_index = current_index + 1
        while (
            new_index < len(self.tokens)
            and self.tokens[new_index].type == "IDENTIFIER"
            and self.tokens[new_index].value.strip() == ""
        ):
            new_index += 1
        self.current_token = (
            self.tokens[new_index] if new_index < len(self.tokens) else None
        )

    def peek(self, offset: int = 1) -> Optional[Token]:
        """Peek at the non-whitespace token at the given offset."""
        if self.current_token is None:
            return None

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
        if self.current_token is None:
            return None

        if self.current_token.type == token_type:
            token = self.current_token
            self.advance()
            return token
        return None

    def expect(self, token_type: str) -> Optional[Token]:
        """Expect the current token to be of the given type."""
        if self.current_token is None:
            return None

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
            + " " * (column_num + 1)
            + "^"
            + f"\n({self.filename}:{line_num}:{column_num})"
        )
        self.errors.append((text, line_num, column_num))

    def parse_expression(self):
        """Parse an expression using equality and additive operators."""
        return self.parse_equality()

    def parse_equality(self):
        """Parse equality expressions (handles '==')."""
        node = self.parse_additive()
        while self.current_token and self.current_token.type == "EQUALS":
            op_token = self.current_token
            self.advance()
            right = self.parse_additive()
            node = ASTNode(
                NodeTypes.EQUALITY_EXPRESSION,
                op_token,
                op_token.value,
                [node, right],
                op_token.index,
            )
        return node

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
        token = self.current_token
        if token is None:
            return None
        if token.type == "OPEN_PAREN":
            self.advance()  # skip '('
            expr = self.parse_expression()
            if not self.current_token or self.current_token.type != "CLOSE_PAREN":
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
            "NULL_LITERAL",
        ):
            self.advance()
            return ASTNode(NodeTypes.LITERAL, token, token.value, [], token.index)
        elif token.type == "IDENTIFIER":
            self.advance()
            node = ASTNode(NodeTypes.IDENTIFIER, token, token.value, [], token.index)
            if self.current_token and self.current_token.type == "OPEN_PAREN":
                # Process function call arguments
                open_paren = self.consume("OPEN_PAREN")
                arguments = []
                if self.current_token and self.current_token.type != "CLOSE_PAREN":
                    while True:
                        arg = self.parse_expression()
                        if arg:
                            arguments.append(arg)
                        if self.current_token and self.current_token.type == "COMMA":
                            self.consume("COMMA")
                            continue
                        break
                close_paren = self.consume("CLOSE_PAREN")
                if not close_paren:
                    self.error("Expected ')' after function arguments", token)
                node = ASTNode(
                    NodeTypes.FUNCTION_CALL, token, token.value, arguments, token.index
                )
                if token.value in self.builtin_functions:
                    node.return_type = self.builtin_functions[token.value]
            return node
        else:
            self.error(f"Unexpected token {token.value}", token)
            self.advance()
            return None

    def parse_variable_declaration(self):
        logging.debug("Parsing variable declaration...")
        is_nullable = False
        is_const = False

        while self.current_token and self.current_token.type in ("NULLABLE", "CONST"):
            if self.current_token.type == "NULLABLE":
                self.advance()
                is_nullable = True
            elif self.current_token.type == "CONST":
                self.advance()
                is_const = True

        if self.current_token and self.current_token.type in (
            "INT",
            "FLOAT",
            "DOUBLE",
            "BOOL",
            "STRING",
            "TUPLE",
        ):
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
            self.error(
                "Expected expression after assignment operator", self.current_token
            )
            self._sync_to_semicolon()
            return None

        if type_token is None:
            self.error("Expected type declaration", self.current_token)
            self._sync_to_semicolon()
            return None

        if type_token.type == "NULL_LITERAL" and not is_nullable:
            self.error(f"Variable '{identifier.value}' is not nullable", identifier)
            return None

        # TODO: Check if var is already declared in the current scope or parent scopes

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
            self.error(
                "Expected expression after assignment operator", self.current_token
            )
            self._sync_to_semicolon()
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
            self._sync_to_semicolon()
            return None

        open_paren = self.consume("OPEN_PAREN")
        if open_paren is None:
            self.error("Expected '(' after function name", self.current_token)
            self._sync_to_semicolon()
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
            self._sync_to_semicolon()
            return None

        if function_name_token.value not in self.builtin_functions:
            self.error(
                f"Function '{function_name_token.value}' is not defined",
                function_name_token,
            )
            return None

        node = ASTNode(
            NodeTypes.FUNCTION_CALL,
            function_name_token,
            function_name_token.value,
            arguments,
            function_name_token.index,
        )

        node.return_type = self.builtin_functions[function_name_token.value]

        return node

    def _sync_to_semicolon(self):
        """Advance tokens until we reach a semicolon or run out of tokens."""
        while self.current_token and self.current_token.type != "SEMICOLON":
            self.advance()
        self.consume("SEMICOLON")

    def resolve_variable_types(self, node: ASTNode, current_scope=None):
        """
        Recursively traverse the AST to annotate Identifier nodes with the variable type.
        """
        if current_scope is None:
            current_scope = {}

        # When encountering a variable declaration, add the variable's type to the scope.
        if node.node_type == NodeTypes.VARIABLE_DECLARATION:
            current_scope[node.name] = node.var_type

        # If this node is an Identifier, attempt to resolve its type from the current scope.
        if node.node_type == NodeTypes.IDENTIFIER:
            if node.name in current_scope:
                node.var_type = current_scope[node.name]

        # Traverse the children.
        for child in node.children:
            # For new scopes (like a block enclosed in braces), copy the current scope to avoid leaking variables.
            if child.node_type == NodeTypes.SCOPE:
                new_scope = current_scope.copy()
                self.resolve_variable_types(child, new_scope)
            else:
                self.resolve_variable_types(child, current_scope)

    def parse_statement(self):
        """Parse a single statement."""
        if self.current_token is None:
            return None

        if self.current_token.type == "OPEN_BRACE":
            return self.parse_scope()
        elif self.current_token.type in (
            "INT",
            "FLOAT",
            "DOUBLE",
            "BOOL",
            "STRING",
            "TUPLE",
            "NULLABLE",
            "CONST",
        ):
            return self.parse_variable_declaration()
        elif self.current_token.type == "IDENTIFIER":
            next_tok = self.peek()
            if next_tok and next_tok.type == "ASSIGN":
                return self.parse_variable_assignment()
            elif next_tok and next_tok.type == "OPEN_PAREN":
                return self.parse_function_call()
            else:
                self.error(
                    f"Unexpected token '{self.current_token.value}' in statement",
                    self.current_token,
                )
                self.advance()
                return None
        elif self.current_token.type == "IF":
            return self.parse_if_chain()
        elif self.current_token.type in ("ELIF", "ELSE"):
            self.error(
                f"Unexpected token '{self.current_token.value}' without preceding 'if'",
                self.current_token,
            )
            self.advance()
            return None
        elif self.current_token.type == "SEMICOLON":
            self.advance()
            return None
        elif self.current_token.type == "WHILE":
            return self.parse_while_statement()
        elif self.current_token.type == "BREAK":
            break_token = self.consume("BREAK")
            if break_token is None:
                self.error("Expected 'break' keyword", self.current_token)
                return None
            return ASTNode(NodeTypes.BREAK_STATEMENT, break_token, "break", [], 0)
        elif self.current_token.type == "CONTINUE":
            continue_token = self.consume("CONTINUE")
            if continue_token is None:
                self.error("Expected 'continue' keyword", self.current_token)
                return None
            return ASTNode(
                NodeTypes.CONTINUE_STATEMENT, continue_token, "continue", [], 0
            )
        else:
            self.error(
                f"Unrecognized statement starting with '{self.current_token.value}'",
                self.current_token,
            )
            self.advance()
            return None

    def parse_if_statement(self):
        # Old implementation removed
        return self.parse_if_chain()

    def parse_if_chain(self):
        if_node = self.parse_if_statement_no_chain()
        if if_node is None:
            return None
        current = if_node
        while self.current_token and self.current_token.type in ("ELIF", "ELSE"):
            if self.current_token.type == "ELIF":
                elif_node = self.parse_elif_statement_no_chain()
                if elif_node is None:
                    break
                current.children.append(elif_node)
                current = elif_node
            elif self.current_token.type == "ELSE":
                else_branch = self.parse_else_statement()
                if else_branch is not None:
                    current.children.append(else_branch)
                break
        return if_node

    def parse_if_statement_no_chain(self):
        if_token = self.consume("IF")
        if if_token is None:
            self.error("Expected 'if' keyword", self.current_token)
            return None
        open_paren = self.expect("OPEN_PAREN")
        if open_paren is None:
            return None
        condition = self.parse_expression()
        close_paren = self.expect("CLOSE_PAREN")
        if close_paren is None:
            return None
        then_branch = self.parse_scope()
        if then_branch is None:
            return None
        # Build if node without attaching else branch.
        return ASTNode(
            NodeTypes.IF_STATEMENT,
            if_token,
            "if",
            [condition, then_branch],
            if_token.index,
        )

    def parse_elif_statement_no_chain(self):
        elif_token = self.consume("ELIF")
        if elif_token is None:
            self.error("Expected 'elif' keyword", self.current_token)
            return None
        open_paren = self.expect("OPEN_PAREN")
        if open_paren is None:
            return None
        condition = self.parse_expression()
        close_paren = self.expect("CLOSE_PAREN")
        if close_paren is None:
            return None
        then_branch = self.parse_scope()
        if then_branch is None:
            return None
        # Build elif node without handling following else.
        return ASTNode(
            NodeTypes.IF_STATEMENT,
            elif_token,
            "elif",
            [condition, then_branch],
            elif_token.index,
        )

    def parse_else_statement(self):
        else_token = self.consume("ELSE")
        if else_token is None:
            self.error("Expected 'else' keyword", self.current_token)
            return None
        branch = self.parse_scope()
        if branch is None:
            return None
        return branch

    def parse_while_statement(self):
        while_token = self.consume("WHILE")
        if while_token is None:
            self.error("Expected 'while' keyword", self.current_token)
            return None
        open_paren = self.expect("OPEN_PAREN")
        if open_paren is None:
            return None
        condition = self.parse_expression()
        close_paren = self.expect("CLOSE_PAREN")
        if close_paren is None:
            return None
        body = self.parse_scope()
        if body is None:
            return None
        return ASTNode(
            NodeTypes.WHILE_STATEMENT,
            while_token,
            "while",
            [condition, body],
            while_token.index,
        )

    def parse_scope(self):
        logging.debug("Parsing scope...")

        # Expect an opening brace for a new scope
        open_brace = self.expect("OPEN_BRACE")
        if open_brace is None:
            self.error("Expected opening brace for scope", self.current_token)
            self._sync_to_semicolon()
            return None

        # Use the open_brace token for the scope's position
        scope_node = ASTNode(NodeTypes.SCOPE, open_brace, "scope", [], open_brace.index)

        # Keep parsing statements until we reach the corresponding closing brace
        while self.current_token and self.current_token.type != "CLOSE_BRACE":
            statement = self.parse_statement()
            if statement is not None and isinstance(statement, ASTNode):
                statement.parent = scope_node
                scope_node.children.append(statement)
        # Consume the closing brace
        end_brace = self.expect("CLOSE_BRACE")
        if end_brace is None:
            self.error("Expected closing brace for scope", self.current_token)
            self._sync_to_semicolon()
            return None

        return scope_node

    def parse(self):
        logging.debug("Parsing tokens...")
        # Top-level: parse until all tokens are consumed.
        while self.current_token:
            stmt = self.parse_statement()
            if stmt is None:
                continue
            # Flatten if a list of statements is returned.
            if isinstance(stmt, list):
                for s in stmt:
                    s.parent = self.ast
                    self.ast.children.append(s)
            else:
                stmt.parent = self.ast
                self.ast.children.append(stmt)

        self.resolve_variable_types(self.ast)

        return self.ast
