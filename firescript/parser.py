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
        name: str,
        children: list["ASTNode"],
        index: int,
        var_type: Optional[str] = None,
        is_nullable: bool = False,
        is_const: bool = False,
        return_type: Optional[str] = None,
        is_array: bool = False,
        is_ref_counted: bool = False,
    ):
        self.node_type: NodeTypes = node_type
        self.token: Optional[Token] = token
        self.name: str = name

        # Strict check: ensure no None children are passed by callers.
        if any(child is None for child in children):
            logging.error(
                f"ASTNode constructor received None in children. Node: {node_type} {name}, Children: {children}"
            )
            raise ValueError(
                "ASTNode constructor received None in children list. This indicates a bug in a parser rule."
            )

        self.children: list[ASTNode] = children

        self.index: int = index
        self.var_type: Optional[str] = var_type
        self.is_nullable: bool = is_nullable
        self.is_const: bool = is_const
        self.return_type: Optional[str] = return_type
        self.is_array: bool = is_array
        self.is_ref_counted: bool = is_ref_counted
        self.parent: Optional[ASTNode] = None  # Parent is typically set externally

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
    # Recognized type token names emitted by the lexer
    TYPE_TOKEN_NAMES = {
        "INT8", "INT16", "INT32", "INT64",
        "UINT8", "UINT16", "UINT32", "UINT64",
        "FLOAT32", "FLOAT64", "FLOAT128",
        "BOOL", "STRING", "TUPLE", "VOID",
    }

    # No legacy type aliases: require explicit widths like 'float32' and 'float64'.
    LEGACY_TYPE_ALIASES = {}

    # Integer family types accepted for indices and similar contexts
    INTEGER_TYPES = {
        "int8",
        "int16",
        "int32",
        "int64",
        "uint8",
        "uint16",
        "uint32",
        "uint64",
    }

    builtin_functions: dict[str, str] = {
        "print": "void",
        "input": "string",
        # type constructor builtins (pending explicit cast design): keep names but map to canonical firescript types
        "int": "int32",
        "int32": "int32",
        # remove legacy float/double constructors; require explicit float32/64/128
        "float32": "float32",
        "float64": "float64",
        "float128": "float128",
        "bool": "bool",
        "string": "string",
        "char": "char",
        "typeof": "string",
    }

    def __init__(self, tokens: list[Token], file: str, filename: str):
        self.tokens: list[Token] = tokens
        self.current_token: Optional[Token] = self.tokens[0]
        self.ast = ASTNode(NodeTypes.ROOT, None, "program", [], 0)
        self.file = file
        self.filename = filename
        self.errors = []
        # Registry for user-defined functions discovered during parsing
        # Maps function name -> return type string (e.g., "int", "void")
        self.user_functions = {}

    def _is_type_token(self, tok: Optional[Token]) -> bool:
        """Return True if the token denotes a type keyword."""
        if tok is None:
            return False
        if tok.type in self.TYPE_TOKEN_NAMES:
            return True
        return False

    def _normalize_type_name(self, tok: Token) -> str:
        """Normalize token.value to canonical firescript type name (handles legacy aliases)."""
        val = tok.value
        return self.LEGACY_TYPE_ALIASES.get(val, val)

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
        """Parse equality and relational expressions (handles '==', '>', '<', etc)."""
        node = self.parse_additive()
        if node is None:  # If LHS is not parsable
            return None

        # Handle ==, >, <, >=, <=
        while self.current_token and self.current_token.type in (
            "EQUALS",
            "GREATER_THAN",
            "LESS_THAN",
            "GREATER_THAN_OR_EQUAL",
            "LESS_THAN_OR_EQUAL",
        ):
            op_token = self.current_token
            self.advance()
            right = self.parse_additive()
            if right is None:  # If RHS is not parsable
                # Error already logged by parse_additive or its children.
                return None  # Propagate failure.

            # Both node and right are valid ASTNodes here.
            if op_token.type == "EQUALS":
                node = ASTNode(
                    NodeTypes.EQUALITY_EXPRESSION,
                    op_token,
                    op_token.value,
                    [node, right],
                    op_token.index,
                )
            else:
                node = ASTNode(
                    NodeTypes.RELATIONAL_EXPRESSION,
                    op_token,
                    op_token.value,
                    [node, right],
                    op_token.index,
                )
        return node

    def parse_additive(self):
        """Parse additive expressions (handles + and -)."""
        node = self.parse_multiplicative()
        if node is None:  # If LHS is not parsable
            return None

        while self.current_token and self.current_token.type in ("ADD", "SUBTRACT"):
            op_token = self.current_token
            self.advance()
            right = self.parse_multiplicative()
            if right is None:  # If RHS is not parsable
                # Error already logged by parse_multiplicative or its children.
                return None  # Propagate failure.

            # Both node and right are valid ASTNodes here.
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
        if node is None:  # If LHS is not parsable
            return None

        while self.current_token and self.current_token.type in (
            "MULTIPLY",
            "DIVIDE",
            "MODULO",
        ):
            op_token = self.current_token
            self.advance()
            right = self.parse_primary()
            if right is None:  # If RHS is not parsable
                # Error already logged by parse_primary.
                return None  # Propagate failure.

            # Both node and right are valid ASTNodes here.
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
        elif token.type == "OPEN_BRACKET":
            # Parse an array literal [elem1, elem2, ...]
            return self.parse_array_literal()
        elif token.type in (
            "BOOLEAN_LITERAL",
            "INTEGER_LITERAL",
            "DOUBLE_LITERAL",
            "FLOAT_LITERAL",
            "STRING_LITERAL",
            "NULL_LITERAL",
        ):
            self.advance()
            node = ASTNode(NodeTypes.LITERAL, token, token.value, [], token.index)
            # Set precise type for literals where applicable
            if token.type == "BOOLEAN_LITERAL":
                node.return_type = "bool"
            elif token.type == "STRING_LITERAL":
                node.return_type = "string"
            elif token.type == "NULL_LITERAL":
                node.return_type = "null"
            elif token.type in ("INTEGER_LITERAL", "FLOAT_LITERAL", "DOUBLE_LITERAL"):
                node.return_type = self._infer_literal_type(token)
            return node
        elif token.type == "IDENTIFIER" or token.value in self.builtin_functions:
            self.advance()
            node = ASTNode(NodeTypes.IDENTIFIER, token, token.value, [], token.index)
            # Array access
            if self.current_token and self.current_token.type == "OPEN_BRACKET":
                return self.parse_array_access(node)
            # Method call
            elif self.current_token and self.current_token.type == "DOT":
                return self.parse_method_call(node)
            # Function call
            elif self.current_token and self.current_token.type == "OPEN_PAREN":
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
                elif token.value in getattr(self, "user_functions", {}):
                    node.return_type = self.user_functions[token.value]
            return node
        else:
            self.error(f"Unexpected token {token.value}", token)
            self.advance()
            return None

    def parse_array_literal(self):
        """Parse an array literal expression like [1, 2, 3]"""
        open_bracket = self.consume("OPEN_BRACKET")
        if not open_bracket:
            self.error("Expected '[' to start array literal", self.current_token)
            return None

        elements = []
        # Parse comma-separated expressions until closing bracket
        if self.current_token and self.current_token.type != "CLOSE_BRACKET":
            while True:
                element = self.parse_expression()
                if element:
                    elements.append(element)

                if self.current_token and self.current_token.type == "COMMA":
                    self.consume("COMMA")
                    continue
                break

        close_bracket = self.consume("CLOSE_BRACKET")
        if not close_bracket:
            self.error("Expected ']' to end array literal", self.current_token)
            return None

        return ASTNode(
            NodeTypes.ARRAY_LITERAL, open_bracket, "array", elements, open_bracket.index
        )

    def parse_array_access(self, array_node):
        """Parse array access expression like arr[0]"""
        open_bracket = self.consume("OPEN_BRACKET")
        if not open_bracket:
            self.error("Expected '[' for array access", self.current_token)
            return None

        index_expr = self.parse_expression()
        if not index_expr:
            self.error("Expected expression for array index", self.current_token)
            return None

        close_bracket = self.consume("CLOSE_BRACKET")
        if not close_bracket:
            self.error("Expected ']' to close array access", self.current_token)
            return None

        return ASTNode(
            NodeTypes.ARRAY_ACCESS,
            open_bracket,
            "arrayAccess",
            [array_node, index_expr],
            open_bracket.index,
        )

    def parse_method_call(self, object_node):
        """Parse method call expression like arr.pop()"""
        dot_token = self.consume("DOT")
        if not dot_token:
            self.error("Expected '.' for method call", self.current_token)
            return None

        method_name = self.consume("IDENTIFIER")
        if not method_name:
            self.error("Expected method name after '.'", self.current_token)
            return None

        open_paren = self.consume("OPEN_PAREN")
        if not open_paren:
            self.error("Expected '(' after method name", self.current_token)
            return None

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
            self.error("Expected ')' after method arguments", self.current_token)
            return None

        # Create a node for the method call with the object as the first child
        node = ASTNode(
            NodeTypes.METHOD_CALL,
            method_name,
            method_name.value,
            [object_node] + arguments,
            method_name.index,
        )
        # Set return type for array methods
        if object_node.is_array:
            elem_type = object_node.var_type
            if method_name.value == "pop":
                node.return_type = elem_type
            elif method_name.value in ("append", "insert"):
                node.return_type = elem_type + "[]"
            elif method_name.value == "clear":
                node.return_type = None
            elif method_name.value in ("length", "size"):
                node.return_type = "int"
        return node

    def parse_if_statement(self):
        """Parse an if (...) { ... } statement, including optional else or elif."""
        if_token = self.consume("IF")
        if not if_token:
            return None

        if not self.consume("OPEN_PAREN"):
            self.error("Expected '(' after 'if'", self.current_token or if_token)
            return None

        condition = self.parse_expression()
        if condition is None:
            # Error for invalid condition already logged by parse_expression or sub-parser.
            if self.current_token and self.current_token.type == "CLOSE_PAREN":
                self.consume("CLOSE_PAREN")
            return None  # IF statement parsing failed due to invalid condition.

        if not self.consume("CLOSE_PAREN"):
            self.error(
                "Expected ')' after if condition", self.current_token or condition.token
            )
            return None

        # 'condition' is a valid ASTNode here.

        then_branch_node: Optional[ASTNode] = None
        expected_then_body_token = self.current_token or condition.token

        if self.current_token and self.current_token.type == "OPEN_BRACE":
            then_branch_node = self.parse_scope()
            if then_branch_node is None:
                self.error(
                    "Invalid 'then' block (scope) for if statement",
                    expected_then_body_token,
                )
                return None
        else:
            then_stmt = self._parse_statement()
            then_children = [then_stmt] if then_stmt else []

            scope_token_for_then = (
                then_stmt.token if then_stmt else expected_then_body_token
            )
            scope_index_for_then = (
                then_stmt.index
                if then_stmt
                else (
                    expected_then_body_token.index
                    if expected_then_body_token
                    else if_token.index
                )
            )

            then_branch_node = ASTNode(
                NodeTypes.SCOPE,
                scope_token_for_then,
                "scope_then",
                then_children,
                scope_index_for_then,
            )

        # Optional else branch (single level)
        else_branch_node: Optional[ASTNode] = None
        if self.current_token and self.current_token.type == "ELSE":
            self.consume("ELSE")
            if self.current_token and self.current_token.type == "OPEN_BRACE":
                else_branch_node = self.parse_scope()
            else:
                else_stmt = self._parse_statement()
                else_children = [else_stmt] if else_stmt else []
                else_token = else_stmt.token if else_stmt else expected_then_body_token
                else_index = (
                    else_stmt.index
                    if else_stmt
                    else (
                        expected_then_body_token.index
                        if expected_then_body_token
                        else if_token.index
                    )
                )
                else_branch_node = ASTNode(
                    NodeTypes.SCOPE, else_token, "scope_else", else_children, else_index
                )

        children = [condition, then_branch_node]
        if else_branch_node:
            children.append(else_branch_node)

        return ASTNode(NodeTypes.IF_STATEMENT, if_token, "if", children, if_token.index)

    def parse_variable_declaration(self):
        """Parse variable declarations like: [nullable] [const] type [ [] ] name = expr"""
        is_nullable = False
        is_const = False
        # Modifiers
        if self.current_token and self.current_token.type == "NULLABLE":
            is_nullable = True
            self.advance()
        if self.current_token and self.current_token.type == "CONST":
            is_const = True
            self.advance()

        # Type
        if not (self.current_token and self._is_type_token(self.current_token)):
            self.error("Expected type in variable declaration", self.current_token)
            return None
        type_token = self.current_token
        self.advance()

        # Optional array suffix []
        is_array = False
        if self.current_token and self.current_token.type == "OPEN_BRACKET":
            # Expect a matching CLOSE_BRACKET
            self.advance()
            if not self.consume("CLOSE_BRACKET"):
                self.error(
                    "Expected ']' after '[' in array type declaration",
                    self.current_token,
                )
                return None
            is_array = True

        # Identifier
        identifier = self.consume("IDENTIFIER")
        if identifier is None:
            self.error("Expected variable name after type", self.current_token)
            return None

        # Assignment
        if not self.consume("ASSIGN"):
            self.error("Expected '=' in variable declaration", self.current_token)
            return None

        # Initializer expression
        value = self.parse_expression()
        if value is None:
            self.error(
                "Expected initializer expression in variable declaration",
                self.current_token,
            )
            return None

        node = ASTNode(
            NodeTypes.VARIABLE_DECLARATION,
            identifier,
            identifier.value,
            [value],
            identifier.index,
            self._normalize_type_name(type_token),
            is_nullable,
            is_const,
            None,  # return_type
            is_array,
            is_ref_counted=(
                True if (type_token.value in ("string",) or is_array) else False
            ),
        )
        return node

    def parse_variable_assignment(self):
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
            is_ref_counted=True,  # Mark assignments as ref-counted
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

        # Allow built-in functions and user-defined functions
        if (
            function_name_token.value not in self.builtin_functions
            and function_name_token.value not in getattr(self, "user_functions", {})
        ):
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

        if function_name_token.value in self.builtin_functions:
            node.return_type = self.builtin_functions[function_name_token.value]
        elif function_name_token.value in getattr(self, "user_functions", {}):
            node.return_type = self.user_functions[function_name_token.value]

        return node

    def _sync_to_semicolon(self):
        """Advance tokens until we reach a semicolon or run out of tokens."""
        while self.current_token and self.current_token.type != "SEMICOLON":
            self.advance()
        self.consume("SEMICOLON")

    def resolve_variable_types(self, node: ASTNode, current_scope=None):
        """
        Recursively traverse the AST to annotate Identifier nodes with the variable type,
        enforce no shadowing and undefined variable usage.
        """
        if current_scope is None:
            current_scope = {}

        # New scope node: copy parent scope
        if node.node_type == NodeTypes.SCOPE:
            new_scope = current_scope.copy()
            for child in node.children:
                self.resolve_variable_types(child, new_scope)
            return

        # Function definition: parameters introduce a new scope level
        if node.node_type == NodeTypes.FUNCTION_DEFINITION:
            # Children layout: [params..., body_scope]
            new_scope = current_scope.copy()
            # Register parameters (prevent shadowing outer vars)
            for child in node.children[
                :-1
            ]:  # all except last which should be body scope
                if child.node_type == NodeTypes.PARAMETER:
                    # PARAMETER nodes store type in var_type field (5th arg when constructed)
                    param_type = child.var_type
                    param_name = child.name
                    is_array = child.is_array
                    if param_name in new_scope:
                        self.error(
                            f"Parameter '{param_name}' already declared in an outer scope; shadowing not allowed",
                            child.token,
                        )
                    new_scope[param_name] = (param_type, is_array)
            # Traverse body with parameter scope
            body = node.children[-1] if node.children else None
            if body:
                self.resolve_variable_types(body, new_scope)
            return

        # Variable declaration: enforce no shadowing
        if node.node_type == NodeTypes.VARIABLE_DECLARATION:
            if node.name in current_scope:
                self.error(
                    f"Variable '{node.name}' already declared in an outer scope; shadowing not allowed",
                    node.token,
                )
            current_scope[node.name] = (node.var_type, node.is_array)
            # Resolve initializer expression
            for child in node.children:
                self.resolve_variable_types(child, current_scope)
            return

        # Identifier usage: ensure variable defined
        if node.node_type == NodeTypes.IDENTIFIER:
            if node.name not in current_scope:
                self.error(f"Variable '{node.name}' not defined", node.token)
            else:
                node.var_type, node.is_array = current_scope[node.name]
            return

        # Recurse into children for all other nodes
        for child in node.children:
            self.resolve_variable_types(child, current_scope)

    def type_check(self):
        """Initiates the type checking process on the AST."""
        logging.debug("Starting type checking...")
        symbol_table = (
            {}
        )  # Build initial symbol table if needed, or rely on resolved types
        self._type_check_node(self.ast, symbol_table)
        logging.debug("Type checking finished.")

    def _get_node_type(self, node: ASTNode, symbol_table: dict) -> Optional[str]:
        """Helper to get the full type string (e.g., 'int', 'string[]')."""
        base_type = None
        is_array = False

        if node.node_type == NodeTypes.LITERAL:
            # Ensure token exists before accessing its type
            if node.token:
                # Prefer an explicitly annotated return_type from parse_primary
                if getattr(node, 'return_type', None):
                    base_type = node.return_type
                else:
                    # Fallback defaults consistent with new numeric model
                    if node.token.type == "INTEGER_LITERAL":
                        base_type = "int32"
                    elif node.token.type == "FLOAT_LITERAL":
                        base_type = "float32"
                    elif node.token.type == "DOUBLE_LITERAL":
                        base_type = "float64"
                    elif node.token.type == "BOOLEAN_LITERAL":
                        base_type = "bool"
                    elif node.token.type == "STRING_LITERAL":
                        base_type = "string"
                    elif node.token.type == "NULL_LITERAL":
                        base_type = "null"  # Special case for null
            is_array = False
        elif node.node_type == NodeTypes.IDENTIFIER:
            # Types should be resolved by resolve_variable_types
            base_type = node.var_type
            is_array = node.is_array
        elif node.node_type == NodeTypes.ARRAY_LITERAL:
            # Determine type from elements, assume consistent type for now
            if not node.children:
                # Cannot determine type of empty array literal yet
                # self.error("Cannot determine type of empty array literal", node.token)
                return None  # Or a special "empty_array" type?
            # Check the type of the first element to infer array type
            first_elem_type_node = node.children[0]
            # Ensure the first element node itself has a token before checking type
            if first_elem_type_node:
                first_elem_type = self._type_check_node(
                    first_elem_type_node, symbol_table
                )
                if first_elem_type is None:
                    return None  # Error in element
                if first_elem_type.endswith("[]"):
                    self.error(
                        "Array literals cannot directly contain arrays", node.token
                    )
                    return None
                base_type = first_elem_type
                is_array = True
            else:
                # Handle case where first element node is somehow None (shouldn't happen in valid AST)
                return None

        elif node.node_type == NodeTypes.FUNCTION_CALL:
            # Return type is pre-defined for built-ins
            base_type = node.return_type  # May include '[]' if function returns array
            # Check if base_type is not None before checking endswith and slicing
            if base_type:
                is_array = base_type.endswith("[]")
                if is_array:
                    base_type = base_type[:-2]
            else:
                is_array = False  # Cannot be an array if base_type is None
        elif node.node_type == NodeTypes.METHOD_CALL:
            # Return type determined during method call check
            base_type = node.return_type
            # Check if base_type is not None before checking endswith and slicing
            if base_type:
                is_array = base_type.endswith("[]")
                if is_array:
                    base_type = base_type[:-2]
            else:
                is_array = False
        elif node.node_type == NodeTypes.ARRAY_ACCESS:
            # Type is the element type of the array
            array_expr_node = node.children[0]
            # Ensure the array expression node exists
            if array_expr_node:
                array_type = self._type_check_node(array_expr_node, symbol_table)
                if array_type and array_type.endswith("[]"):
                    base_type = array_type[:-2]
                    is_array = False
                else:
                    # Error handled in _type_check_node or array_type is None
                    return None
            else:
                # Handle case where array expression node is None
                return None
        elif node.node_type in (
            NodeTypes.BINARY_EXPRESSION,
            NodeTypes.EQUALITY_EXPRESSION,
            NodeTypes.RELATIONAL_EXPRESSION,
        ):
            # Type determined during expression check
            base_type = node.return_type
            is_array = False  # These expressions don't return arrays directly

        if base_type is None:
            # If after all checks, base_type is still None, return None
            # This can happen for nodes that don't evaluate to a value (like ROOT, SCOPE)
            # or if an error occurred determining the type.
            return None

        return f"{base_type}[]" if is_array else base_type

    def _infer_literal_type(self, token: Token) -> str:
        """Infer type for numeric literal based on suffix and defaults.
        INTEGER_LITERAL default: int32. Supports i8/i16/i32/i64/u8/u16/u32/u64 suffixes.
    FLOAT_LITERAL supports f|f32|f64|f128; DOUBLE_LITERAL default: float64.
        """
        val = token.value
        if token.type == "INTEGER_LITERAL":
            for suf, tname in (
                ("i8", "int8"), ("i16", "int16"), ("i32", "int32"), ("i64", "int64"),
                ("u8", "uint8"), ("u16", "uint16"), ("u32", "uint32"), ("u64", "uint64"),
            ):
                if val.endswith(suf):
                    return tname
            return "int32"
        if token.type == "FLOAT_LITERAL":
            if val.endswith("f128"):
                return "float128"
            if val.endswith("f64"):
                return "float64"
            if val.endswith("f32") or val.endswith("f"):
                return "float32"
            return "float32"
        if token.type == "DOUBLE_LITERAL":
            return "float64"
        return ""

    def _type_check_node(self, node: ASTNode, symbol_table: dict) -> Optional[str]:
        """Recursively checks types in the AST node and returns the node's expression type."""
        node_type_str = None  # The type of the expression this node represents

        # First, recursively check children to determine their types
        child_types = [
            self._type_check_node(child, symbol_table) for child in node.children
        ]

        # --- Type Checking Logic based on Node Type ---
        if node.node_type == NodeTypes.ROOT or node.node_type == NodeTypes.SCOPE:
            # Scopes don't have a type themselves, just check children
            pass  # Children already checked

        elif node.node_type == NodeTypes.VARIABLE_DECLARATION:
            declared_type = f"{node.var_type}[]" if node.is_array else node.var_type
            initializer_type = child_types[0] if child_types else None

            if initializer_type:
                # Special case: initializing with null
                if initializer_type == "null":
                    if not node.is_nullable:
                        self.error(
                            f"Cannot initialize non-nullable variable '{node.name}' with null",
                            node.token,
                        )
                # General case: types must match
                elif declared_type != initializer_type:
                    # Strict: no implicit coercions between numeric families
                    self.error(
                        f"Type mismatch for variable '{node.name}'. Expected {declared_type}, got {initializer_type}",
                        node.token,
                    )
            # Add variable to symbol table for current scope (if not already done by resolve)
            symbol_table[node.name] = (node.var_type, node.is_array)

        elif node.node_type == NodeTypes.VARIABLE_ASSIGNMENT:
            var_info = symbol_table.get(node.name)
            if not var_info:
                # This should ideally be caught by resolve_variable_types if identifier is used before declaration
                self.error(f"Variable '{node.name}' not defined", node.token)
                return None  # Cannot proceed

            var_type, is_array = var_info
            expected_type = f"{var_type}[]" if is_array else var_type
            assigned_type = child_types[0] if child_types else None

            if assigned_type:
                if assigned_type == "null":
                    # Need to check nullability of the variable type (requires enhancement to symbol table or ASTNode)
                    # For now, assume resolve_variable_types handles basic declaration checks
                    pass  # Assume nullable check happened at declaration if applicable
                elif expected_type != assigned_type:
                    # TODO: Implement type coercion rules
                    self.error(
                        f"Type mismatch assigning to variable '{node.name}'. Expected {expected_type}, got {assigned_type}",
                        node.token,
                    )

        elif node.node_type == NodeTypes.BINARY_EXPRESSION:
            left_type = child_types[0]
            right_type = child_types[1]
            op = node.name

            if left_type is None or right_type is None:
                return None

            integer_types = self.INTEGER_TYPES
            float_types = {"float", "double", "float32", "float64", "float128"}

            node_type_str: Optional[str] = None

            # String concatenation stays allowed for string + string
            if op == "+":
                if left_type == "string" and right_type == "string":
                    node_type_str = "string"
                elif left_type == right_type and left_type in integer_types:
                    node_type_str = left_type
                elif left_type == right_type and left_type in float_types:
                    node_type_str = left_type
                else:
                    self.error(
                        f"Operator '{op}' not supported between types {left_type} and {right_type}",
                        node.token,
                    )
            elif op in ("-", "*", "/"):
                if left_type == right_type and left_type in integer_types:
                    node_type_str = left_type
                elif left_type == right_type and left_type in float_types:
                    node_type_str = left_type
                else:
                    self.error(
                        f"Operator '{op}' not supported between types {left_type} and {right_type}",
                        node.token,
                    )
            elif op == "%":
                if left_type == right_type and left_type in integer_types:
                    node_type_str = left_type
                else:
                    self.error(
                        f"Operator '{op}' requires integer operands of the same type, got {left_type} and {right_type}",
                        node.token,
                    )
            else:
                self.error(f"Unsupported binary operator '{op}'", node.token)

            node.return_type = node_type_str

        elif node.node_type == NodeTypes.EQUALITY_EXPRESSION:  # ==, !=
            left_type = child_types[0]
            right_type = child_types[1]
            op = node.name

            if left_type is None or right_type is None:
                return None

            # Allow comparison between same-type numerics, string==string, bool==bool, or with null
            integer_types = self.INTEGER_TYPES
            float_types = {"float32", "float64", "float128"}
            if (
                (left_type == right_type and (left_type in integer_types or left_type in float_types))
                or (left_type == right_type and left_type in {"string", "bool"})
                or (left_type == "null" or right_type == "null")
            ):
                node_type_str = "bool"
            else:
                self.error(
                    f"Cannot compare types {left_type} and {right_type} with '{op}'",
                    node.token,
                )

            node.return_type = node_type_str

        elif node.node_type == NodeTypes.RELATIONAL_EXPRESSION:  # >, <, >=, <=
            left_type = child_types[0]
            right_type = child_types[1]
            op = node.name

            if left_type is None or right_type is None:
                return None

            integer_types = self.INTEGER_TYPES
            float_types = {"float32", "float64", "float128"}
            if (left_type == right_type and (left_type in integer_types or left_type in float_types)):
                node_type_str = "bool"
            else:
                self.error(
                    f"Operator '{op}' requires same-type numeric operands, got {left_type} and {right_type}",
                    node.token,
                )

            node.return_type = node_type_str

        elif node.node_type == NodeTypes.FUNCTION_CALL:
            # Basic check for built-ins
            func_name = node.name
            expected_arg_count = -1  # Use -1 for variable args like print
            expected_arg_types = []  # Define expected types for builtins

            if func_name == "print":
                expected_arg_count = 1  # Simplified: assumes 1 arg for now
                # Allow printing any basic type
            elif func_name == "input":
                expected_arg_count = 1
                expected_arg_types = ["string"]
            elif func_name in ("toInt", "toBool", "toString", "toChar"):
                expected_arg_count = 1
                # Allow conversion from reasonable types (simplified check)
            elif func_name == "typeof":
                expected_arg_count = 1

            if expected_arg_count != -1 and len(child_types) != expected_arg_count:
                self.error(
                    f"Function '{func_name}' expected {expected_arg_count} arguments, got {len(child_types)}",
                    node.token,
                )
            elif expected_arg_types:
                for i, arg_type in enumerate(child_types):
                    if (
                        i < len(expected_arg_types)
                        and expected_arg_types[i] != "T"
                        and arg_type != expected_arg_types[i]
                    ):
                        # TODO: Add coercion checks for conversions
                        self.error(
                            f"Argument {i+1} for function '{func_name}' expected type {expected_arg_types[i]}, got {arg_type}",
                            node.children[i].token,
                        )

            # Return type is already set in the node for builtins during parsing
            node_type_str = node.return_type

        elif node.node_type == NodeTypes.METHOD_CALL:
            object_type = child_types[0]
            method_name = node.name
            arg_types = child_types[1:]

            if object_type is None:
                return None  # Error in object expression

            node.return_type = None  # Reset before check

            if object_type.endswith("[]"):  # It's an array method
                elem_type = object_type[:-2]
                if method_name == "append":
                    if len(arg_types) == 1:
                        if arg_types[0] == elem_type:
                            node.return_type = object_type  # append returns the array itself (or void?) - let's say array type for chaining
                        else:
                            self.error(
                                f"Method 'append' for {object_type} expected element type {elem_type}, got {arg_types[0]}",
                                node.children[1].token,
                            )
                    else:
                        self.error(
                            f"Method 'append' expected 1 argument, got {len(arg_types)}",
                            node.token,
                        )
                elif method_name == "insert":
                    if len(arg_types) == 2:
                        if arg_types[0] in self.INTEGER_TYPES:
                            if arg_types[1] == elem_type:
                                node.return_type = object_type
                            else:
                                self.error(
                                    f"Method 'insert' for {object_type} expected element type {elem_type}, got {arg_types[1]}",
                                    node.children[2].token,
                                )
                        else:
                            self.error(
                                f"Method 'insert' expected integer index as first argument, got {arg_types[0]}",
                                node.children[1].token,
                            )
                    else:
                        self.error(
                            f"Method 'insert' expected 2 arguments (index, element), got {len(arg_types)}",
                            node.token,
                        )
                elif method_name == "pop":
                    if len(arg_types) == 0:  # Pop last
                        node.return_type = elem_type
                    elif len(arg_types) == 1:  # Pop at index
                        if arg_types[0] in self.INTEGER_TYPES:
                            node.return_type = elem_type
                        else:
                            self.error(
                                f"Method 'pop' expected integer index, got {arg_types[0]}",
                                node.children[1].token,
                            )
                    else:
                        self.error(
                            f"Method 'pop' expected 0 or 1 argument, got {len(arg_types)}",
                            node.token,
                        )
                elif method_name == "clear":
                    if len(arg_types) == 0:
                        node.return_type = (
                            "void"  # Or None? Let's use void consistently
                        )
                    else:
                        self.error(
                            f"Method 'clear' expected 0 arguments, got {len(arg_types)}",
                            node.token,
                        )
                elif method_name in ("length", "size"):
                    if len(arg_types) == 0:
                        node.return_type = "int32"
                    else:
                        self.error(
                            f"Method '{method_name}' expected 0 arguments, got {len(arg_types)}",
                            node.token,
                        )
                else:
                    self.error(
                        f"Unknown method '{method_name}' for array type {object_type}",
                        node.token,
                    )
            else:
                # TODO: Handle methods for other object types when classes are implemented
                self.error(
                    f"Methods not supported for type {object_type}",
                    node.children[0].token,
                )

            node_type_str = node.return_type

        elif node.node_type == NodeTypes.ARRAY_ACCESS:
            array_type = child_types[0]
            index_type = child_types[1]

            if array_type is None or index_type is None:
                return None

            if not array_type.endswith("[]"):
                self.error(
                    f"Cannot apply index operator [] to non-array type {array_type}",
                    node.children[0].token,
                )
            elif index_type not in self.INTEGER_TYPES:
                self.error(
                    f"Array index must be an integer type, got {index_type}",
                    node.children[1].token,
                )
            else:
                node_type_str = array_type[:-2]  # The element type

            node.return_type = node_type_str

        elif (
            node.node_type == NodeTypes.IF_STATEMENT
            or node.node_type == NodeTypes.WHILE_STATEMENT
        ):
            condition_type = child_types[0]
            if condition_type is None:
                return None
            if condition_type != "bool":
                self.error(
                    f"Condition for '{node.name}' statement must be a boolean, got {condition_type}",
                    node.children[0].token,
                )
            # Body/branches are checked recursively, statement itself has no type

        elif (
            node.node_type == NodeTypes.BREAK_STATEMENT
            or node.node_type == NodeTypes.CONTINUE_STATEMENT
        ):
            # Validate placement: must be inside a loop (while for now)
            cur = node.parent
            in_loop = False
            while cur is not None:
                if cur.node_type == NodeTypes.WHILE_STATEMENT:
                    in_loop = True
                    break
                cur = cur.parent
            if not in_loop:
                self.error(f"'{node.name}' statement not within a loop", node.token)

        # --- Determine node's type string based on checks ---
        # If node_type_str wasn't set explicitly, try getting it generally
        if node_type_str is None:
            node_type_str = self._get_node_type(node, symbol_table)

        return node_type_str

    def _parse_statement(self):
        """Determine the kind of statement and parse it."""
        # Unknown token recovery: emit error and advance
        if self.current_token and self.current_token.type == "UNKNOWN":
            bad_tok = self.current_token
            self.advance()
            self.error(f"Unexpected character '{bad_tok.value}'", bad_tok)
            return None
        # Handle while loops
        if self.current_token and self.current_token.type == "WHILE":
            return self.parse_while_statement()
        # Handle break / continue
        if self.current_token and self.current_token.type in ("BREAK", "CONTINUE"):
            tok = self.current_token
            self.advance()
            node_type = (
                NodeTypes.BREAK_STATEMENT
                if tok.type == "BREAK"
                else NodeTypes.CONTINUE_STATEMENT
            )
            ast = ASTNode(node_type, tok, tok.value, [], tok.index)
            # Expect semicolon after break/continue
            if self.current_token and self.current_token.type == "SEMICOLON":
                self.consume("SEMICOLON")
            else:
                self.error(
                    "Expected semicolon after statement", self.current_token or tok
                )
            return ast
        # Handle return statements
        if self.current_token and self.current_token.type == "RETURN":
            ret_tok = self.current_token
            self.advance()
            expr = None
            if self.current_token and self.current_token.type != "SEMICOLON":
                expr = self.parse_expression()
            return ASTNode(
                NodeTypes.RETURN_STATEMENT,
                ret_tok,
                "return",
                [expr] if expr else [],
                ret_tok.index,
            )
        # Skip comments in statements
        if self.current_token and self.current_token.type in (
            "SINGLE_LINE_COMMENT",
            "MULTI_LINE_COMMENT_START",
        ):
            self._skip_comment()
            return None
        if self.current_token is None:
            return None

        # Handle block scopes
        if self.current_token.type == "OPEN_BRACE":
            return self.parse_scope()

        # Handle if statements
        if self.current_token.type == "IF":
            return self.parse_if_statement()

        # Dangling else (no preceding if handled this token)
        if self.current_token.type == "ELSE":
            tok = self.current_token
            self.advance()
            self.error("Unexpected 'else' without matching 'if'", tok)
            # Attempt to parse its following statement/block to continue
            if self.current_token and self.current_token.type == "OPEN_BRACE":
                self.parse_scope()
            else:
                # Skip a single statement form
                _ = self._parse_statement()
            return None

        # Look ahead to determine statement type
        token_type = self.current_token.type
        next_token = self.peek()

        # Variable Declaration: type tokens or nullable/const modifiers can start a declaration
        if self._is_type_token(self.current_token) or token_type in ("NULLABLE", "CONST"):
            return self.parse_variable_declaration()

        # Compound Assignment (e.g., x += y)
        elif (
            token_type == "IDENTIFIER"
            and next_token
            and next_token.type
            in (
                "ADD_ASSIGN",
                "SUBTRACT_ASSIGN",
                "MULTIPLY_ASSIGN",
                "DIVIDE_ASSIGN",
                "MODULO_ASSIGN",
            )
        ):
            return self.parse_compound_assignment()

        # Increment/Decrement (e.g., x++, x--)
        elif (
            token_type == "IDENTIFIER"
            and next_token
            and next_token.type in ("INCREMENT", "DECREMENT")
        ):
            return self.parse_increment_or_decrement()

        # Variable Assignment (e.g., x = ...) or Function Call (e.g., print(...))
        elif token_type == "IDENTIFIER":
            if next_token and next_token.type == "ASSIGN":
                return self.parse_variable_assignment()
            elif next_token and next_token.type == "OPEN_PAREN":
                # Could be a standalone function call statement
                return self.parse_function_call()
            elif next_token and next_token.type == "DOT":
                # Could be a method call used as a statement (e.g., list.clear();)
                # Need to parse the primary expression which handles method calls
                expr = self.parse_primary()
                # If it parsed successfully as a method call, return it.
                # Otherwise, it might be just an identifier (which isn't a valid statement alone)
                # or an error occurred during parsing.
                if expr and expr.node_type == NodeTypes.METHOD_CALL:
                    return expr
                else:
                    # If it wasn't a method call, it's likely an error or just an expression
                    # not allowed as a standalone statement here.
                    self.error(
                        "Expected assignment, function call, or method call",
                        self.current_token,
                    )
                    self.advance()  # Consume the identifier to avoid loops
                    return None
            elif next_token and next_token.type == "OPEN_BRACKET":
                # Could be an array access followed by assignment (arr[0] = ...)
                # This case needs careful handling. Let's parse it as an expression first.
                expr = self.parse_expression()
                # Check if the *next* token after the expression is ASSIGN
                if self.current_token and self.current_token.type == "ASSIGN":
                    # This looks like an assignment to an array element or similar complex l-value
                    # We need a specific parsing function for this kind of assignment.
                    # For now, let's report an error as it's not fully handled.
                    self.error(
                        "Array element assignment not yet fully implemented",
                        self.current_token,
                    )
                    self._sync_to_semicolon()
                    return None
                return expr
            else:
                # If it's just an identifier without assignment, function call, etc.
                # it's not a valid statement
                self.error(
                    "Expected assignment, function call, or method call",
                    self.current_token,
                )
                self.advance()  # Advance to avoid loops
                return None

    def _parse_function_definition(self):
        """Parse a function definition with optional array types: <type>[[]] <name>(<type>[[]] name, ...) { ... }"""
        # Return type
        if not self._is_type_token(self.current_token):
            self.error("Expected return type at function definition", self.current_token)
            return None
        ret_type_token = self.current_token
        self.advance()

        # Optional array suffix for return type
        ret_is_array = False
        if self.current_token and self.current_token.type == "OPEN_BRACKET":
            self.advance()
            if not self.consume("CLOSE_BRACKET"):
                self.error(
                    "Expected ']' after '[' in array return type", self.current_token
                )
                return None
            ret_is_array = True

        name_token = self.consume("IDENTIFIER")
        if name_token is None:
            self.error("Expected function name after return type", self.current_token)
            return None
        if not self.consume("OPEN_PAREN"):
            self.error("Expected '(' after function name", self.current_token)
            return None

        params: list[ASTNode] = []
        if self.current_token and self.current_token.type != "CLOSE_PAREN":
            while True:
                if not (self.current_token and self._is_type_token(self.current_token)):
                    self.error("Expected parameter type", self.current_token)
                    return None
                ptype_tok = self.current_token
                self.advance()
                # Optional array suffix for parameter type
                p_is_array = False
                if self.current_token and self.current_token.type == "OPEN_BRACKET":
                    self.advance()
                    if not self.consume("CLOSE_BRACKET"):
                        self.error(
                            "Expected ']' after '[' in array parameter type",
                            self.current_token,
                        )
                        return None
                    p_is_array = True
                pname_tok = self.consume("IDENTIFIER")
                if pname_tok is None:
                    self.error("Expected parameter name", self.current_token)
                    return None
                param_node = ASTNode(
                    NodeTypes.PARAMETER,
                    pname_tok,
                    pname_tok.value,
                    [],
                    pname_tok.index,
                    self._normalize_type_name(ptype_tok),
                    False,
                    False,
                    None,
                    p_is_array,
                    p_is_array,
                )
                params.append(param_node)
                if self.current_token and self.current_token.type == "COMMA":
                    self.advance()
                    continue
                break
        if not self.consume("CLOSE_PAREN"):
            self.error("Expected ')' after parameters", self.current_token)
            return None
        if not (self.current_token and self.current_token.type == "OPEN_BRACE"):
            self.error("Expected '{' to start function body", self.current_token)
            return None
        body_node = self.parse_scope()
        if body_node is None:
            return None
        base_ret_type = self._normalize_type_name(ret_type_token) if ret_type_token else None
        return_type_value = (
            (base_ret_type + "[]")
            if (base_ret_type and ret_is_array)
            else base_ret_type
        )
        func_node = ASTNode(
            NodeTypes.FUNCTION_DEFINITION,
            name_token,
            name_token.value,
            [*params, body_node],
            name_token.index,
            None,
            False,
            False,
            return_type_value,
            ret_is_array,
            ret_is_array,
        )
        if ret_type_token and name_token:
            self.user_functions[name_token.value] = return_type_value
        return func_node

    def parse_scope(self):
        """
        Parse a block enclosed in braces { ... } as a new scope.
        """
        open_brace = self.consume("OPEN_BRACE")
        if open_brace is None:
            # Error if no opening brace
            self.error("Expected '{' to start scope", self.current_token)
            return None
        scope_node = ASTNode(NodeTypes.SCOPE, open_brace, "scope", [], open_brace.index)
        # Parse statements until closing brace
        while self.current_token and self.current_token.type != "CLOSE_BRACE":
            if self.current_token.type == "SEMICOLON":
                self.advance()
                continue
            stmt = self._parse_statement()
            if stmt:
                stmt.parent = scope_node
                scope_node.children.append(stmt)
            if self.current_token and self.current_token.type == "SEMICOLON":
                self.consume("SEMICOLON")
        self.consume("CLOSE_BRACE")
        return scope_node

    def parse(self):
        logging.debug("Parsing tokens...")
        # Top-level: parse until all tokens are consumed.
        while self.current_token:
            # Skip comments and empty lines represented by certain tokens
            if self.current_token.type in (
                "SINGLE_LINE_COMMENT",
                "MULTI_LINE_COMMENT_START",
            ):
                self._skip_comment()
                continue
            if self.current_token.type == "SEMICOLON":  # Skip empty statements
                self.advance()
                continue
            # Handle potential whitespace/newline tokens if lexer produces them
            if (
                self.current_token.type == "IDENTIFIER"
                and not self.current_token.value.strip()
            ):
                self.advance()
                continue
            # Try function definition first: <type> <identifier> '(' ... ')'{ ... }
            stmt = None
            if self._is_type_token(self.current_token):
                idx_cur = self.tokens.index(self.current_token)
                # Gather next few meaningful tokens to detect patterns
                look = []
                m = idx_cur + 1
                while m < len(self.tokens) and len(look) < 5:
                    if self.tokens[m].type not in (
                        "SINGLE_LINE_COMMENT",
                        "MULTI_LINE_COMMENT_START",
                        "MULTI_LINE_COMMENT_END",
                    ):
                        look.append(self.tokens[m])
                    m += 1
                # Patterns:
                # 1) TYPE IDENTIFIER '('
                # 2) TYPE '[' ']' IDENTIFIER '('
                is_func = False
                if (
                    len(look) >= 2
                    and look[0].type == "IDENTIFIER"
                    and look[1].type == "OPEN_PAREN"
                ):
                    is_func = True
                elif (
                    len(look) >= 4
                    and look[0].type == "OPEN_BRACKET"
                    and look[1].type == "CLOSE_BRACKET"
                    and look[2].type == "IDENTIFIER"
                    and look[3].type == "OPEN_PAREN"
                ):
                    is_func = True
                if is_func:
                    stmt = self._parse_function_definition()
            if stmt is None:
                stmt = (
                    self._parse_statement()
                )  # Changed to call internal _parse_statement
            if stmt is None:
                # If _parse_statement returned None but didn't advance past an error token,
                # advance manually to prevent infinite loops.
                # This might happen if _sync_to_semicolon was called or an error occurred early.
                # Check if the token that caused the error is still the current one.
                # A more robust error recovery might be needed here.
                if self.current_token:  # Check if we haven't reached the end
                    logging.debug(
                        f"Advancing after _parse_statement returned None for token: {self.current_token}"
                    )
                    # A simple recovery: skip until next semicolon or brace
                    # self._sync_to_semicolon_or_brace() # Needs implementation
                    self.advance()  # Simplest: just advance one token
                continue

            # Flatten if a list of statements is returned (shouldn't happen with current structure).
            if isinstance(stmt, list):
                for s in stmt:
                    if s:  # Ensure statement is not None
                        s.parent = self.ast
                        self.ast.children.append(s)
            elif isinstance(stmt, ASTNode):  # Ensure it's a valid node
                stmt.parent = self.ast
                self.ast.children.append(stmt)

            # Consume semicolon after simple statements (not blocks, loops, or function defs)
            if isinstance(stmt, ASTNode):
                if not (
                    stmt.node_type
                    in (
                        NodeTypes.IF_STATEMENT,
                        NodeTypes.WHILE_STATEMENT,
                        NodeTypes.SCOPE,
                        NodeTypes.FUNCTION_DEFINITION,
                    )
                ):
                    if self.current_token and self.current_token.type == "SEMICOLON":
                        self.consume("SEMICOLON")
                    else:
                        self.error(
                            "Expected semicolon after statement",
                            self.current_token
                            or (stmt.token if isinstance(stmt, ASTNode) else None),
                        )
                        # Sync forward to first semicolon or brace to avoid duplicate errors
                        while self.current_token and self.current_token.type not in (
                            "SEMICOLON",
                            "CLOSE_BRACE",
                            "OPEN_BRACE",
                        ):
                            self.advance()
                        if (
                            self.current_token
                            and self.current_token.type == "SEMICOLON"
                        ):
                            self.consume("SEMICOLON")

        logging.debug("Resolving variable types...")
        self.resolve_variable_types(self.ast)
        logging.debug("Variable type resolution finished.")

        # Perform type checking after resolving types
        self.type_check()

        return self.ast

    def _skip_comment(self):
        """Advances past single or multi-line comments."""
        if self.current_token is None:
            return

        if self.current_token.type == "SINGLE_LINE_COMMENT":
            self.advance()
        elif self.current_token.type == "MULTI_LINE_COMMENT_START":
            while (
                self.current_token
                and self.current_token.type != "MULTI_LINE_COMMENT_END"
            ):
                self.advance()
            if (
                self.current_token
                and self.current_token.type == "MULTI_LINE_COMMENT_END"
            ):
                self.advance()  # Consume the end comment token

    def parse_compound_assignment(self):
        """Parse compound assignment statements like x += y, x -= y, etc."""
        identifier = self.consume("IDENTIFIER")
        if identifier is None:
            self.error("Expected identifier", self.current_token)
            self._sync_to_semicolon()
            return None

        # Check for compound assignment operators
        if self.current_token and self.current_token.type in (
            "ADD_ASSIGN",
            "SUBTRACT_ASSIGN",
            "MULTIPLY_ASSIGN",
            "DIVIDE_ASSIGN",
            "MODULO_ASSIGN",
        ):
            op_token = self.current_token
            self.advance()
            value = self.parse_expression()
            if value is None:
                self.error(
                    "Expected expression after compound assignment operator",
                    self.current_token,
                )
                self._sync_to_semicolon()
                return None

            node = ASTNode(
                NodeTypes.COMPOUND_ASSIGNMENT,
                identifier,
                identifier.value,
                [value],
                identifier.index,
                is_ref_counted=True,
            )
            node.token = op_token  # Store the operator token for code generation
            return node
        else:
            self.error(
                f"Expected compound assignment operator, got {self.current_token.type if self.current_token else 'None'}",
                self.current_token or identifier,
            )
            return None

    def parse_increment_or_decrement(self):
        """Parse increment (x++) or decrement (x--) operations."""
        identifier = self.consume("IDENTIFIER")
        if identifier is None:
            self.error("Expected identifier", self.current_token)
            self._sync_to_semicolon()
            return None

        if self.current_token and self.current_token.type in ("INCREMENT", "DECREMENT"):
            op_token = self.current_token
            op_value = op_token.value  # This will be "++" or "--"
            self.advance()

            # Create a node with identifier as token and "++" as name
            node = ASTNode(
                NodeTypes.UNARY_EXPRESSION,
                identifier,  # Store the identifier token here
                op_value,  # Store the operator value (++ or --) as the name
                [],  # No children for a simple increment/decrement
                identifier.index,
            )
            return node
        else:
            self.error(
                f"Expected increment or decrement operator, got {self.current_token.type if self.current_token else 'None'}",
                self.current_token or identifier,
            )
            return None

    def parse_while_statement(self):
        """Parse a while (...) { ... } statement."""
        while_token = self.consume("WHILE")
        if not while_token:
            return None
        if not self.consume("OPEN_PAREN"):
            self.error("Expected '(' after 'while'", self.current_token or while_token)
            return None
        condition = self.parse_expression()
        if condition is None:
            if self.current_token and self.current_token.type == "CLOSE_PAREN":
                self.consume("CLOSE_PAREN")
            return None
        if not self.consume("CLOSE_PAREN"):
            self.error(
                "Expected ')' after while condition",
                self.current_token or condition.token,
            )
            return None
        # Parse body
        if self.current_token and self.current_token.type == "OPEN_BRACE":
            body = self.parse_scope()
            if body is None:
                return None
        else:
            stmt = self._parse_statement()
            body = ASTNode(
                NodeTypes.SCOPE,
                stmt.token if stmt else None,
                "scope",
                [stmt] if stmt else [],
                stmt.index if stmt else while_token.index,
            )
            if stmt:
                stmt.parent = body
        return ASTNode(
            NodeTypes.WHILE_STATEMENT,
            while_token,
            "while",
            [condition, body],
            while_token.index,
        )
