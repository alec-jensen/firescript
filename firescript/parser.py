import logging
import copy
from typing import Union, Optional

from lexer import Token
from utils.type_utils import is_owned, is_copyable
from utils.file_utils import get_line_and_coumn_from_index, get_line
from enums import NodeTypes, CompilerDirective


class ASTNode:
    # Optional semantic metadata for semantic passes
    value_category: Optional[str]
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
        # Optional semantic metadata; populated by analysis passes
        self.value_category = None
        # Generic function metadata
        self.type_params: list[str] = []  # Type parameter names for generic functions
        self.type_constraints: dict[str, str] = {}  # Type param -> constraint
        self.type_args: list[str] = []  # Concrete type arguments for generic calls

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
        "stdout": "void",
        "input": "string",
        "drop": "void",
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

    # Register for user-defined methods (className -> methodName -> signature)
    user_methods = {}

    def __init__(
        self,
        tokens: list[Token],
        file: str,
        filename: str,
        defer_undefined_identifiers: Optional[bool] = None,
    ):
        self.tokens: list[Token] = tokens
        self.current_token: Optional[Token] = self.tokens[0]
        self.ast = ASTNode(NodeTypes.ROOT, None, "program", [], 0)
        self.file = file
        self.filename = filename
        self.errors = []
        if defer_undefined_identifiers is None:
            self.defer_undefined_identifiers = any(t.type == "IMPORT" for t in tokens)
        else:
            self.defer_undefined_identifiers = defer_undefined_identifiers
        # Track identifier uses we deferred checking (typically because imports are present).
        self.deferred_undefined_identifiers: list[tuple[str, Optional[Token]]] = []
        # Registry for user-defined functions discovered during parsing
        # Maps function name -> return type string (e.g., "int", "void")
        self.user_functions = {}
        # Collected compiler directives in this file
        self.directives: set[str] = set()
        # User-defined class registry and type names
        self.user_classes: dict[str, dict[str, str]] = {}
        self.user_types: set[str] = set()
        # className -> methodName -> {"return": str, "params": [str, ...]}
        self.user_methods = {}

        # Inheritance metadata: class -> base class (single inheritance)
        self.user_class_bases: dict[str, Optional[str]] = {}
        # Keep parsed class field/method nodes around so we can synthesize inherited members.
        self._class_field_nodes: dict[str, list[ASTNode]] = {}
        self._class_method_nodes: dict[str, list[ASTNode]] = {}

        # Parsing context for class bodies (used for `super.*` parsing)
        self._class_context_stack: list[tuple[str, bool, Optional[str]]] = []  # (class_name, in_constructor, base_class)
        
        # Generic function tracking
        # Maps function name -> list of type parameter names
        self.generic_functions: dict[str, list[str]] = {}
        # Maps function name -> dict of type param -> constraint
        self.generic_constraints: dict[str, dict[str, str]] = {}
        # Track monomorphized instances: (func_name, tuple of concrete types) -> mangled name
        self.monomorphized_functions: dict[tuple[str, tuple[str, ...]], str] = {}
        # Track type parameters in current scope (for parsing inside generic functions)
        self._current_type_params: list[str] = []
        
        # Custom type constraint aliases: constraint_name -> type_union_string
        self.constraint_aliases: dict[str, str] = {}

    def _current_class_context(self) -> tuple[Optional[str], bool, Optional[str]]:
        if not self._class_context_stack:
            return (None, False, None)
        return self._class_context_stack[-1]

    def _is_type_token(self, tok: Optional[Token]) -> bool:
        """Return True if the token denotes a type keyword."""
        if tok is None:
            return False
        if tok.type in self.TYPE_TOKEN_NAMES:
            return True
        # Allow user-defined class names as types
        if tok.type == "IDENTIFIER" and tok.value in self.user_types:
            return True
        # Allow type parameters in current generic function scope
        if tok.type == "IDENTIFIER" and tok.value in self._current_type_params:
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

    def _parse_postfix_cast(self, node: Optional[ASTNode]) -> Optional[ASTNode]:
        """Parse Rust-style postfix cast: <expr> as <type>."""
        if node is None:
            return None
        while self.current_token and (
            self.current_token.type == "AS"
            or (self.current_token.type == "IDENTIFIER" and self.current_token.value == "as")
        ):
            self.advance()  # consume 'as'
            t_tok = self.current_token
            if t_tok is None:
                self.error("Expected type after 'as'", node.token)
                break
            if not (self._is_type_token(t_tok) or t_tok.type == "IDENTIFIER"):
                self.error("Expected type after 'as'", t_tok)
                break
            self.advance()

            # Normalize built-in type tokens; allow user-defined types via IDENTIFIER.
            if self._is_type_token(t_tok):
                target_type = self._normalize_type_name(t_tok)
            else:
                target_type = t_tok.value

            cast_node = ASTNode(
                NodeTypes.CAST_EXPRESSION,
                t_tok,
                target_type,
                [node],
                t_tok.index,
            )
            cast_node.return_type = target_type
            node = cast_node
        return node

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
        node = self.parse_unary()
        if node is None:  # If LHS is not parsable
            return None

        while self.current_token and self.current_token.type in (
            "MULTIPLY",
            "DIVIDE",
            "MODULO",
        ):
            op_token = self.current_token
            self.advance()
            right = self.parse_unary()
            if right is None:  # If RHS is not parsable
                # Error already logged by parse_unary.
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

    def parse_unary(self):
        """Parse unary expressions (handles unary - and +).""" 
        if self.current_token and self.current_token.type in ("SUBTRACT", "ADD"):
            op_token = self.current_token
            self.advance()
            operand = self.parse_unary()  # Right-associative for chained unary ops
            if operand is None:
                self.error(f"Expected expression after unary '{op_token.value}'", op_token)
                return None
            return ASTNode(
                NodeTypes.UNARY_EXPRESSION,
                op_token,
                op_token.value,
                [operand],
                op_token.index,
            )
        return self.parse_primary()

    def parse_primary(self):
        token = self.current_token
        if token is None:
            return None
        # Java-like constructor: new ClassName(args)
        if token.type == "NEW":
            self.advance()
            cls_tok = self.consume("IDENTIFIER")
            if cls_tok is None:
                self.error("Expected class name after 'new'", self.current_token)
                return None
            if cls_tok.value not in self.user_types:
                self.error(f"Unknown type '{cls_tok.value}' in constructor", cls_tok)
            if not self.consume("OPEN_PAREN"):
                self.error("Expected '(' after constructor type", self.current_token)
                return None
            args = []
            if self.current_token and self.current_token.type != "CLOSE_PAREN":
                while True:
                    arg = self.parse_expression()
                    if arg:
                        args.append(arg)
                    if self.current_token and self.current_token.type == "COMMA":
                        self.consume("COMMA")
                        continue
                    break
            if not self.consume("CLOSE_PAREN"):
                self.error("Expected ')' after constructor arguments", self.current_token)
                return None
            return ASTNode(NodeTypes.CONSTRUCTOR_CALL, cls_tok, cls_tok.value, args, cls_tok.index)
        if token.type == "OPEN_PAREN":
            self.advance()  # skip '('
            expr = self.parse_expression()
            if not self.current_token or self.current_token.type != "CLOSE_PAREN":
                self.error("Expected closing parenthesis", self.current_token)
                return self._parse_postfix_cast(expr)
            self.advance()  # skip ')'
            return self._parse_postfix_cast(expr)
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
            return self._parse_postfix_cast(node)
        elif token.type == "IDENTIFIER" or token.value in self.builtin_functions:
            self.advance()
            # Special-case: type-level method call like Type.method(...)
            if token.value in self.user_types and self.current_token and self.current_token.type == "DOT":
                self.consume("DOT")
                method_name = self.consume("IDENTIFIER")
                if not method_name:
                    self.error("Expected method name after type '.'", self.current_token)
                    return None
                if not self.consume("OPEN_PAREN"):
                    self.error("Expected '(' after type method name", self.current_token)
                    return None
                args = []
                if self.current_token and self.current_token.type != "CLOSE_PAREN":
                    while True:
                        arg = self.parse_expression()
                        if arg:
                            args.append(arg)
                        if self.current_token and self.current_token.type == "COMMA":
                            self.consume("COMMA")
                            continue
                        break
                if not self.consume("CLOSE_PAREN"):
                    self.error("Expected ')' after arguments", self.current_token)
                    return None
                node = ASTNode(NodeTypes.TYPE_METHOD_CALL, method_name, method_name.value, args, method_name.index)
                setattr(node, "class_name", token.value)
                return node

            node = ASTNode(NodeTypes.IDENTIFIER, token, token.value, [], token.index)
            # Handle postfix operations in a loop: array access, field access, method call, function call
            while True:
                # Array access
                if self.current_token and self.current_token.type == "OPEN_BRACKET":
                    node = self.parse_array_access(node)
                    if node is None:
                        return None
                    continue
                # Field access or method call starting with '.'
                elif self.current_token and self.current_token.type == "DOT":
                    if node is None:
                        return None
                    # Lookahead to distinguish field vs method call
                    dot_tok = self.consume("DOT")
                    ident_tok = self.consume("IDENTIFIER")
                    if not ident_tok:
                        self.error("Expected identifier after '.'", self.current_token or dot_tok)
                        break
                    # Method call if next is '('
                    if self.current_token and self.current_token.type == "OPEN_PAREN":
                        # Parse arguments
                        self.consume("OPEN_PAREN")
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
                        if not self.consume("CLOSE_PAREN"):
                            self.error("Expected ')' after method arguments", self.current_token)

                        # Special-case: `this.super(...)` inside constructors.
                        cls_name, in_ctor, super_class = self._current_class_context()
                        if (
                            ident_tok.value == "super"
                            and in_ctor
                            and node.node_type == NodeTypes.IDENTIFIER
                            and node.name == "this"
                        ):
                            super_node = ASTNode(NodeTypes.SUPER_CALL, ident_tok, "super", arguments, ident_tok.index)
                            setattr(super_node, "enclosing_class", cls_name)
                            setattr(super_node, "super_class", super_class)
                            setattr(super_node, "in_constructor", True)
                            return super_node

                        node = ASTNode(
                            NodeTypes.METHOD_CALL,
                            ident_tok,
                            ident_tok.value,
                            [node] + arguments,
                            ident_tok.index,
                        )
                        # Array methods: handled in type checker later
                    else:
                        # Field access: chainable
                        node = ASTNode(
                            NodeTypes.FIELD_ACCESS,
                            ident_tok,
                            ident_tok.value,
                            [node],
                            ident_tok.index,
                        )
                        # Continue loop to allow chaining a.b.c
                        continue
                # Function call (identifier followed by '(')
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
                    # Allow zero-arg constructor call for user-defined classes
                    elif token.type == "IDENTIFIER" and token.value in self.user_types:
                        # Constructor call: validate in type checker; return type will be set there
                        pass
                    continue
                
                # Explicit generic type arguments: func<T1, T2>(...)
                elif self.current_token and self.current_token.type == "LESS_THAN":
                    # Check if this is a generic function call
                    if token.value in self.generic_functions:
                        self.advance()  # consume <
                        type_args = []
                        while True:
                            if not (self.current_token and self._is_type_token(self.current_token)):
                                self.error("Expected type argument", self.current_token)
                                break
                            targ_tok = self.current_token
                            self.advance()
                            type_args.append(self._normalize_type_name(targ_tok))
                            
                            if self.current_token and self.current_token.type == "COMMA":
                                self.advance()
                                continue
                            break
                        
                        if not (self.current_token and self.current_token.type == "GREATER_THAN"):
                            self.error("Expected '>' to close type arguments", self.current_token)
                        else:
                            self.advance()  # consume >
                        
                        # Now parse the function call
                        if not (self.current_token and self.current_token.type == "OPEN_PAREN"):
                            self.error("Expected '(' after generic type arguments", self.current_token)
                            break
                        
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
                        node.type_args = type_args
                        node.return_type = self.user_functions.get(token.value, "void")
                        continue
                    else:
                        # Not a generic function, this is a comparison operator
                        break

                # Postfix cast: <expr> as <type>
                elif self.current_token and (
                    self.current_token.type == "AS"
                    or (
                        self.current_token.type == "IDENTIFIER" and self.current_token.value == "as"
                    )
                ):
                    node = self._parse_postfix_cast(node)
                    continue
                break
            return self._parse_postfix_cast(node)
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
        # Set return type for array methods (fixed-size: only length/size allowed)
        if object_node.is_array:
            if method_name.value in ("length", "size"):
                node.return_type = "int"
            else:
                self.error(
                    f"Unsupported array method '{method_name.value}' for fixed-size arrays",
                    method_name,
                )
                node.return_type = None
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

        # Allow built-in functions and user-defined functions.
        # If imports are present, defer undefined-function checks until after import merge.
        if (
            function_name_token.value not in self.builtin_functions
            and function_name_token.value not in getattr(self, "user_functions", {})
        ):
            if not self.defer_undefined_identifiers:
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
                    # Annotate parameter node with value category
                    try:
                        child.value_category = (
                            "Owned" if is_owned(param_type, is_array) else (
                                "Copyable" if is_copyable(param_type, is_array) else None
                            )
                        )
                    except Exception:
                        pass
            # Traverse body with parameter scope
            body = node.children[-1] if node.children else None
            if body:
                self.resolve_variable_types(body, new_scope)
            return

        # Class method definition: similar to function but includes receiver parameter
        if node.node_type == NodeTypes.CLASS_METHOD_DEFINITION:
            new_scope = current_scope.copy()
            for child in node.children[:-1]:  # params (including receiver)
                if child.node_type == NodeTypes.PARAMETER:
                    param_type = child.var_type
                    param_name = child.name
                    is_array = child.is_array
                    if param_name in new_scope:
                        self.error(
                            f"Parameter '{param_name}' already declared in an outer scope; shadowing not allowed",
                            child.token,
                        )
                    new_scope[param_name] = (param_type, is_array)
                    try:
                        child.value_category = (
                            "Owned" if is_owned(param_type, is_array) else (
                                "Copyable" if is_copyable(param_type, is_array) else None
                            )
                        )
                    except Exception:
                        pass
            # Inject implicit alias 'this' to the class type for method/constructor bodies,
            # so 'this.x' resolves even if receiver param was named differently or synthetic.
            cls_name = getattr(node, "class_name", None)
            if cls_name and "this" not in new_scope:
                new_scope["this"] = (cls_name, False)
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
            # Annotate declaration with value category
            try:
                node.value_category = (
                    "Owned" if is_owned(node.var_type, node.is_array) else (
                        "Copyable" if is_copyable(node.var_type, node.is_array) else None
                    )
                )
            except Exception:
                pass
            # Resolve initializer expression
            for child in node.children:
                self.resolve_variable_types(child, current_scope)
            return

        # Variable assignment: allow implicit declaration for class-typed RHS
        if node.node_type == NodeTypes.VARIABLE_ASSIGNMENT:
            # Resolve RHS first to allow identifiers inside it to be typed
            for child in node.children:
                self.resolve_variable_types(child, current_scope)
            if node.name not in current_scope:
                inferred_type = None
                rhs = node.children[0] if node.children else None
                if rhs is not None:
                    # Constructor-style call: ClassName(...)
                    if rhs.node_type == NodeTypes.FUNCTION_CALL and rhs.name in self.user_types:
                        inferred_type = rhs.name
                    # Instance method call: obj.method(...)
                    elif rhs.node_type == NodeTypes.METHOD_CALL and rhs.children:
                        obj = rhs.children[0]
                        obj_type = getattr(obj, "var_type", None)
                        if obj_type is None and isinstance(obj, ASTNode) and obj.node_type == NodeTypes.IDENTIFIER:
                            obj_type = current_scope.get(obj.name, (None, False))[0]
                        if obj_type and (obj_type in self.user_methods) and (rhs.name in self.user_methods[obj_type]):
                            inferred_type = self.user_methods[obj_type][rhs.name].get("return")
                current_scope[node.name] = (inferred_type, False)
            return

        # Identifier usage: ensure variable defined
        if node.node_type == NodeTypes.IDENTIFIER:
            if node.name not in current_scope:
                if self.defer_undefined_identifiers:
                    self.deferred_undefined_identifiers.append((node.name, node.token))
                else:
                    self.error(f"Variable '{node.name}' not defined", node.token)
            else:
                node.var_type, node.is_array = current_scope[node.name]
                # Annotate identifier with value category
                try:
                    node.value_category = (
                        "Owned" if is_owned(node.var_type, node.is_array) else (
                            "Copyable" if is_copyable(node.var_type, node.is_array) else None
                        )
                    )
                except Exception:
                    pass
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
        elif node.node_type == NodeTypes.SUPER_CALL:
            base_type = node.return_type
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
    
    def _infer_generic_type_args(self, func_name: str, arg_types: list[str]) -> Optional[list[str]]:
        """Infer type arguments for a generic function call based on argument types.
        Returns a list of concrete types for each type parameter, or None if inference fails.
        """
        if func_name not in self.generic_functions:
            return None
        
        type_params = self.generic_functions[func_name]
        if not type_params:
            return []
        
        # Get the function definition to examine parameter types
        func_def = None
        for child in self.ast.children:
            if child.node_type == NodeTypes.FUNCTION_DEFINITION and child.name == func_name:
                func_def = child
                break
        
        if not func_def:
            return None
        
        # Extract parameter types from function definition
        param_types = []
        for child in func_def.children:
            if child.node_type == NodeTypes.PARAMETER:
                param_types.append(child.var_type or "")
        
        # Build a mapping from type parameters to inferred concrete types
        type_map: dict[str, str] = {}
        
        for param_type, arg_type in zip(param_types, arg_types):
            if param_type in type_params:
                # Direct type parameter match
                if param_type in type_map:
                    if type_map[param_type] != arg_type:
                        # Conflicting inference
                        return None
                else:
                    type_map[param_type] = arg_type
        
        # Check if all type parameters were inferred
        inferred_types = []
        for tp in type_params:
            if tp not in type_map:
                # Could not infer this type parameter
                return None
            inferred_types.append(type_map[tp])
        
        return inferred_types

    def _type_check_node(self, node: ASTNode, symbol_table: dict) -> Optional[str]:
        """Recursively checks types in the AST node and returns the node's expression type."""
        node_type_str = None  # The type of the expression this node represents

        # Special handling for generic function definitions: set type parameter context
        if node.node_type == NodeTypes.FUNCTION_DEFINITION and hasattr(node, 'type_params') and node.type_params:
            prev_type_params = self._current_type_params
            self._current_type_params = node.type_params.copy()
            child_types = [
                self._type_check_node(child, symbol_table) for child in node.children
            ]
            self._current_type_params = prev_type_params
        else:
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
            assigned_type = child_types[0] if child_types else None
            if not var_info:
                # Implicit declaration on first assignment: register with inferred type
                if assigned_type is not None:
                    # assigned_type may be 'Type[]'; identify array-ness
                    is_arr = assigned_type.endswith("[]")
                    base_t = assigned_type[:-2] if is_arr else assigned_type
                    symbol_table[node.name] = (base_t, is_arr)
                else:
                    self.error(f"Variable '{node.name}' not defined", node.token)
                    return None
            else:
                var_type, is_array = var_info
                expected_type = f"{var_type}[]" if is_array else var_type
                if assigned_type:
                    if assigned_type == "null":
                        # TODO: enforce nullability on existing variable types
                        pass
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
            
            # Check if a type is a type parameter (in current generic function scope)
            is_left_type_param = left_type in self._current_type_params
            is_right_type_param = right_type in self._current_type_params

            node_type_str: Optional[str] = None

            # String concatenation stays allowed for string + string
            if op == "+":
                # Allow string concatenation with any type (converted in codegen)
                if left_type == "string" or right_type == "string":
                    node_type_str = "string"
                elif left_type == right_type and left_type in integer_types:
                    node_type_str = left_type
                elif left_type == right_type and left_type in float_types:
                    node_type_str = left_type
                # Allow if both are the same type parameter (assumed to be numeric via constraints)
                elif left_type == right_type and is_left_type_param:
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
                # Allow if both are the same type parameter (assumed to be numeric via constraints)
                elif left_type == right_type and is_left_type_param:
                    node_type_str = left_type
                else:
                    self.error(
                        f"Operator '{op}' not supported between types {left_type} and {right_type}",
                        node.token,
                    )
            elif op == "%":
                if left_type == right_type and left_type in integer_types:
                    node_type_str = left_type
                # Allow if both are the same type parameter (assumed to be numeric via constraints)
                elif left_type == right_type and is_left_type_param:
                    node_type_str = left_type
                else:
                    self.error(
                        f"Operator '{op}' requires integer operands of the same type, got {left_type} and {right_type}",
                        node.token,
                    )
            else:
                self.error(f"Unsupported binary operator '{op}'", node.token)

            node.return_type = node_type_str

        elif node.node_type == NodeTypes.UNARY_EXPRESSION:
            op = node.name
            
            # Increment/decrement operators (++/--) have no children - they operate on the identifier stored in node.token
            if op in ("++", "--"):
                # The variable being incremented/decremented is in node.token
                var_name = node.token.value if node.token and hasattr(node.token, 'value') else None
                if var_name:
                    var_info = symbol_table.get(var_name)
                    if var_info:
                        var_type, is_array = var_info
                        # Increment/decrement only work on integer types
                        if var_type in self.INTEGER_TYPES:
                            node_type_str = var_type
                        else:
                            self.error(f"Operator '{op}' requires an integer variable, got {var_type}", node.token)
                    else:
                        self.error(f"Variable '{var_name}' not defined", node.token)
                return node_type_str
            
            # Unary +/- operators have a child operand
            if not child_types:
                self.error(f"Unary operator '{op}' missing operand", node.token)
                return None
                
            operand_type = child_types[0]

            if operand_type is None:
                return None

            integer_types = self.INTEGER_TYPES
            float_types = {"float", "double", "float32", "float64", "float128"}
            
            # Unary + and - work on numeric types and type parameters
            if op in ("+", "-"):
                is_numeric = operand_type in integer_types or operand_type in float_types
                is_type_param = operand_type in self._current_type_params
                
                if is_numeric or is_type_param:
                    node_type_str = operand_type  # Same type as operand
                else:
                    self.error(
                        f"Unary operator '{op}' requires numeric operand, got {operand_type}",
                        node.token,
                    )
                    node_type_str = None
            else:
                self.error(f"Unsupported unary operator '{op}'", node.token)
                node_type_str = None

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
            
            # Allow comparisons if both types are the same, and either:
            # 1. They are known numeric types, OR
            # 2. They are type parameters (assumed to be constrained to numeric types)
            is_numeric = left_type in integer_types or left_type in float_types
            is_type_param = left_type in self._current_type_params
            
            if left_type == right_type and (is_numeric or is_type_param):
                node_type_str = "bool"
            else:
                self.error(
                    f"Operator '{op}' requires same-type numeric operands, got {left_type} and {right_type}",
                    node.token,
                )

            node.return_type = node_type_str

        elif node.node_type == NodeTypes.CAST_EXPRESSION:
            expr_type = child_types[0] if child_types else None
            target_type = getattr(node, "name", None)

            if expr_type is None or target_type is None:
                return None

            # Allow casting arrays to string
            if isinstance(expr_type, str) and expr_type.endswith("[]"):
                if target_type == "string":
                    # Array to string is allowed
                    node_type_str = "string"
                    node.return_type = "string"
                else:
                    self.error(
                        f"Cannot cast array type {expr_type} to {target_type}",
                        node.token,
                    )
                    return None
            elif isinstance(target_type, str) and target_type.endswith("[]"):
                self.error(
                    f"Cannot cast to array type {target_type}",
                    node.token,
                )
                return None

            integer_types = self.INTEGER_TYPES
            float_types = {"float32", "float64", "float128"}
            
            # Allow casting to string from any type
            if target_type == "string":
                node_type_str = "string"
                node.return_type = "string"
            elif target_type not in integer_types and target_type not in float_types:
                self.error(
                    f"Cannot cast to unknown or non-numeric type {target_type}",
                    node.token,
                )
                return None
            elif expr_type not in integer_types and expr_type not in float_types and expr_type != "bool" and expr_type != "string":
                self.error(
                    f"Cannot cast non-numeric type {expr_type} to {target_type}",
                    node.token,
                )
                return None
            else:
                node_type_str = target_type
                node.return_type = target_type

        elif node.node_type == NodeTypes.FUNCTION_CALL:
            # Basic check for built-ins
            func_name = node.name
            
            # Check if this is a generic function call
            if func_name in self.generic_functions:
                # Check if type arguments are explicitly provided
                if hasattr(node, 'type_args') and node.type_args:
                    # Explicit type arguments provided
                    type_params = self.generic_functions[func_name]
                    if len(node.type_args) != len(type_params):
                        self.error(
                            f"Generic function '{func_name}' expects {len(type_params)} type arguments, got {len(node.type_args)}",
                            node.token,
                        )
                else:
                    # Infer type arguments from call arguments
                    inferred = self._infer_generic_type_args(func_name, [t for t in child_types if t is not None])
                    if inferred is None:
                        self.error(
                            f"Could not infer type arguments for generic function '{func_name}'",
                            node.token,
                        )
                        node.type_args = []
                    else:
                        node.type_args = inferred
                
                # Validate type constraints if we have type arguments
                if hasattr(node, 'type_args') and node.type_args:
                    constraints = self.generic_constraints.get(func_name, {})
                    type_params = self.generic_functions[func_name]
                    for tp, concrete_type in zip(type_params, node.type_args):
                        if tp in constraints:
                            constraint = constraints[tp]
                            # Parse constraint (simple version: just check if type is in union)
                            allowed_types = [t.strip() for t in constraint.split("|")]
                            if concrete_type not in allowed_types and constraint not in ["Numeric", "Comparable", "SignedInt", "UnsignedInt", "Float", "Integer"]:
                                self.error(
                                    f"Type '{concrete_type}' does not satisfy constraint '{constraint}' for type parameter '{tp}'",
                                    node.token,
                                )
                    
                    # Set return type by substituting type parameters
                    generic_return_type = self.user_functions.get(func_name)
                    if generic_return_type:
                        # Create type substitution map
                        type_subst = dict(zip(type_params, node.type_args))
                        # Substitute return type if it's a type parameter
                        if generic_return_type in type_subst:
                            node.return_type = type_subst[generic_return_type]
                            node_type_str = node.return_type
                        else:
                            node.return_type = generic_return_type
                            node_type_str = generic_return_type
            
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
            # Constructors: calling a class name acts as a constructor with positional args matching field order
            if func_name in self.user_types:
                # Validate against class fields order
                fields_map = self.user_classes.get(func_name, {})
                field_order = list(fields_map.items())  # [(name, type), ...] insertion order preserved
                if len(child_types) != len(field_order):
                    self.error(
                        f"Constructor '{func_name}' expected {len(field_order)} args, got {len(child_types)}",
                        node.token,
                    )
                else:
                    for i, (arg_t, (_, exp_t)) in enumerate(zip(child_types, field_order)):
                        if arg_t != exp_t:
                            self.error(
                                f"Constructor '{func_name}' arg {i+1} expected {exp_t}, got {arg_t}",
                                node.children[i].token if i < len(node.children) else node.token,
                            )
                node_type_str = func_name
                node.return_type = func_name
            else:
                # For non-generic functions, use the stored return type
                if func_name not in self.generic_functions and not hasattr(node, 'return_type'):
                    node.return_type = self.user_functions.get(func_name)
                node_type_str = node.return_type

        elif node.node_type == NodeTypes.METHOD_CALL:
            object_type = child_types[0]
            method_name = node.name
            arg_types = child_types[1:]

            if object_type is None:
                return None  # Error in object expression

            node.return_type = None  # Reset before check

            if isinstance(object_type, str) and object_type.endswith("[]"):  # It's an array method
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
                # Class instance methods
                if object_type in self.user_methods and method_name in self.user_methods[object_type]:
                    sig = self.user_methods[object_type][method_name]
                    expected_params = sig.get("params", [])
                    if len(arg_types) != len(expected_params):
                        self.error(
                            f"Method '{method_name}' for '{object_type}' expected {len(expected_params)} args, got {len(arg_types)}",
                            node.token,
                        )
                    else:
                        for i, (arg_t, exp_t) in enumerate(zip(arg_types, expected_params)):
                            if arg_t != exp_t:
                                self.error(
                                    f"Argument {i+1} for method '{method_name}' expected type {exp_t}, got {arg_t}",
                                    node.children[i+1].token if len(node.children) > i+1 else node.token,
                                )
                    node.return_type = sig.get("return")
                else:
                    self.error(
                        f"Methods not supported for type {object_type}",
                        node.children[0].token,
                    )

        elif node.node_type == NodeTypes.SUPER_CALL:
            enclosing_class = getattr(node, "enclosing_class", None)
            super_class = getattr(node, "super_class", None)
            in_ctor = bool(getattr(node, "in_constructor", False))

            if not enclosing_class:
                self.error("'super' can only be used inside a class method", node.token)
                return None
            if not super_class:
                self.error(f"Class '{enclosing_class}' has no base class; cannot use 'super'", node.token)
                return None

            if not in_ctor:
                self.error("'this.super(...)' is only valid inside a constructor", node.token)
                return None

            # Validate constructor exists on base
            if super_class not in self.user_methods or super_class not in self.user_methods[super_class]:
                self.error(f"No constructor defined for base type '{super_class}'", node.token)
                return None
            sig = self.user_methods[super_class][super_class]
            expected_params = sig.get("params", [])
            if len(child_types) != len(expected_params):
                self.error(
                    f"Super constructor '{super_class}' expected {len(expected_params)} args, got {len(child_types)}",
                    node.token,
                )
            else:
                for i, (arg_t, exp_t) in enumerate(zip(child_types, expected_params)):
                    if arg_t != exp_t:
                        self.error(
                            f"Super constructor '{super_class}' arg {i+1} expected {exp_t}, got {arg_t}",
                            node.children[i].token if i < len(node.children) else node.token,
                        )

            node.return_type = "void"
            node_type_str = "void"
        elif node.node_type == NodeTypes.TYPE_METHOD_CALL:
            class_name = getattr(node, "class_name", None)
            method_name = node.name
            if not class_name or class_name not in self.user_methods or method_name not in self.user_methods[class_name]:
                self.error(f"Unknown constructor or static method '{method_name}' for type '{class_name}'", node.token)
                return None
            sig = self.user_methods[class_name][method_name]
            # Require constructor to return the class type
            if sig.get("return") != class_name:
                self.error(f"'{method_name}' is not a constructor for type '{class_name}'", node.token)
                return None
            # Validate args
            expected_params = sig.get("params", [])
            if len(child_types) != len(expected_params):
                self.error(
                    f"Constructor '{class_name}.{method_name}' expected {len(expected_params)} args, got {len(child_types)}",
                    node.token,
                )
            else:
                for i, (arg_t, exp_t) in enumerate(zip(child_types, expected_params)):
                    if arg_t != exp_t:
                        self.error(
                            f"Constructor '{class_name}.{method_name}' arg {i+1} expected {exp_t}, got {arg_t}",
                            node.children[i].token if i < len(node.children) else node.token,
                        )
            node.return_type = class_name
            node_type_str = class_name

            node_type_str = node.return_type
        elif node.node_type == NodeTypes.CONSTRUCTOR_CALL:
            class_name = node.name
            # Look up a constructor method whose name equals the class name
            if class_name not in self.user_methods or class_name not in self.user_methods[class_name]:
                self.error(f"No constructor defined for type '{class_name}'", node.token)
                return None
            sig = self.user_methods[class_name][class_name]
            expected_params = sig.get("params", [])
            if len(child_types) != len(expected_params):
                self.error(
                    f"Constructor '{class_name}' expected {len(expected_params)} args, got {len(child_types)}",
                    node.token,
                )
            else:
                for i, (arg_t, exp_t) in enumerate(zip(child_types, expected_params)):
                    if arg_t != exp_t:
                        self.error(
                            f"Constructor '{class_name}' arg {i+1} expected {exp_t}, got {arg_t}",
                            node.children[i].token if i < len(node.children) else node.token,
                        )
            node.return_type = class_name
            node_type_str = class_name

        elif node.node_type == NodeTypes.FIELD_ACCESS:
            # Field access: left child is the object expression
            obj_type = child_types[0]
            field_name = node.name
            if obj_type is None:
                return None
            # Only support user-defined classes for now
            if obj_type in self.user_classes:
                fields = self.user_classes[obj_type]
                if field_name in fields:
                    node.return_type = fields[field_name]
                    node_type_str = fields[field_name]
                else:
                    self.error(f"Type '{obj_type}' has no field '{field_name}'", node.token)
                    node_type_str = None
            else:
                self.error(f"Field access on non-class type '{obj_type}'", node.token)
                node_type_str = None

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
        # Imports are top-level only; error if seen in a statement context (inside scopes)
        if self.current_token and self.current_token.type == "IMPORT":
            tok = self.current_token
            self.error("Imports must appear at top level", tok)
            # Simple recovery: consume until semicolon or brace
            while self.current_token and self.current_token.type not in ("SEMICOLON", "CLOSE_BRACE", "OPEN_BRACE"):
                self.advance()
            if self.current_token and self.current_token.type == "SEMICOLON":
                self.consume("SEMICOLON")
            return None
        # Handle compiler directives: directive <name> [<arg1>, ...];
        if self.current_token and self.current_token.type == "DIRECTIVE":
            dir_tok = self.current_token
            self.advance()
            name_tok = self.consume("IDENTIFIER")
            if name_tok is None:
                self.error("Expected directive name after 'directive'", self.current_token or dir_tok)
                return None
            # Validate directive name against known directives
            directive_value = name_tok.value
            try:
                directive_enum = CompilerDirective(directive_value)
            except Exception:
                self.error(f"Unknown directive '{directive_value}'", name_tok)
                directive_enum = None
            # Consume optional simple comma-separated arguments until semicolon (currently ignored)
            while self.current_token and self.current_token.type not in ("SEMICOLON",):
                if self.current_token.type == "COMMA":
                    self.advance()
                    # Optionally accept IDENTIFIER or literals as args but ignore their values
                    if self.current_token and self.current_token.type in (
                        "IDENTIFIER",
                        "INTEGER_LITERAL",
                        "FLOAT_LITERAL",
                        "DOUBLE_LITERAL",
                        "STRING_LITERAL",
                        "BOOLEAN_LITERAL",
                    ):
                        self.advance()
                    continue
                # Any unexpected token before semicolon: bail and sync
                self.error("Unexpected token in directive arguments", self.current_token)
                break
            if self.current_token and self.current_token.type == "SEMICOLON":
                self.consume("SEMICOLON")
            # Record directive name and emit a node
            if directive_enum is not None:
                self.directives.add(directive_enum.value)
                node_name = directive_enum.value
            else:
                node_name = directive_value
            directive_node = ASTNode(NodeTypes.DIRECTIVE, dir_tok, node_name, [], dir_tok.index)
            # Mark the directive with the source file so we can filter by file later
            directive_node.source_file = self.filename
            return directive_node
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
                # Could be a method call or field access; parse the primary expression first
                lhs = self.parse_primary()
                if lhs is None:
                    return None
                # If it's a method call used as a statement, return it
                if lhs.node_type in (NodeTypes.METHOD_CALL, NodeTypes.SUPER_CALL):
                    return lhs
                # If it's a field access followed by assignment, handle assignment
                if self.current_token and self.current_token.type == "ASSIGN":
                    assign_tok = self.consume("ASSIGN")
                    rhs = self.parse_expression()
                    if rhs is None:
                        self.error("Expected expression after '='", self.current_token)
                        self._sync_to_semicolon()
                        return None
                    # Safe token index fallback for typing
                    idx = assign_tok.index if assign_tok else (lhs.token.index if lhs and lhs.token else 0)
                    return ASTNode(NodeTypes.ASSIGNMENT, assign_tok, "=", [lhs, rhs], idx)
                # Otherwise, field access alone is not a valid statement
                self.error("Expected assignment after field access", self.current_token)
                self._sync_to_semicolon()
                return None
            elif next_token and next_token.type == "OPEN_BRACKET":
                # Could be an array access followed by assignment (arr[0] = ...)
                # This case needs careful handling. Let's parse it as an expression first.
                expr = self.parse_expression()
                # Check if the *next* token after the expression is ASSIGN
                if self.current_token and self.current_token.type == "ASSIGN":
                    # This looks like an assignment to an array element or similar complex l-value
                    assign_tok = self.consume("ASSIGN")
                    rhs = self.parse_expression()
                    if rhs is None:
                        self.error("Expected expression after '='", self.current_token)
                        self._sync_to_semicolon()
                        return None
                    if expr is None:
                        self.error("Invalid assignment target", assign_tok)
                        self._sync_to_semicolon()
                        return None
                    idx = assign_tok.index if assign_tok else (expr.token.index if expr and expr.token else 0)
                    return ASTNode(NodeTypes.ASSIGNMENT, assign_tok, "=", [expr, rhs], idx)
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
        # Return type - can be a known type OR an IDENTIFIER (for generic type parameters)
        # Check if this is a type token, or an IDENTIFIER followed by another IDENTIFIER and LESS_THAN (generic pattern)
        is_valid_return_type = self._is_type_token(self.current_token)
        
        # Also allow IDENTIFIER if it could be a type parameter (will be validated after parsing type params)
        if not is_valid_return_type and self.current_token and self.current_token.type == "IDENTIFIER":
            # Peek ahead to see if this looks like a generic function: T funcName<...>
            next_tok = self.peek(1)
            second_tok = self.peek(2)
            if next_tok and next_tok.type == "IDENTIFIER" and second_tok and second_tok.type == "LESS_THAN":
                is_valid_return_type = True
        
        if not is_valid_return_type:
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
        
        # Parse optional generic type parameters: <T, U, ...>
        type_params: list[str] = []
        type_constraints: dict[str, str] = {}
        
        if self.current_token and self.current_token.type == "LESS_THAN":
            self.advance()  # consume <
            # Parse type parameters
            while True:
                if not (self.current_token and self.current_token.type == "IDENTIFIER"):
                    self.error("Expected type parameter name", self.current_token)
                    return None
                tparam_tok = self.consume("IDENTIFIER")
                if tparam_tok is None:
                    return None
                type_params.append(tparam_tok.value)
                
                # Parse optional constraint: T: Comparable or T: int32 | float64 or T: NumericPrimitive (alias)
                if self.current_token and self.current_token.type == "COLON":
                    self.advance()  # consume :
                    constraint_parts = []
                    while True:
                        # Constraints can be type names (int32, float64) or interface names (Comparable)
                        # or constraint aliases (NumericPrimitive)
                        # Type names come as TYPE tokens, interface names as IDENTIFIER tokens
                        if not (self.current_token and (self._is_type_token(self.current_token) or self.current_token.type == "IDENTIFIER")):
                            self.error("Expected constraint type or interface", self.current_token)
                            return None
                        
                        constraint_tok = self.current_token
                        self.advance()
                        if constraint_tok is None:
                            return None
                        
                        # Check if this is a constraint alias and expand it
                        if constraint_tok.value in self.constraint_aliases:
                            # Expand the alias inline
                            alias_expansion = self.constraint_aliases[constraint_tok.value]
                            constraint_parts.append(alias_expansion)
                        else:
                            constraint_parts.append(constraint_tok.value)
                        
                        # Check for union operator |
                        if self.current_token and self.current_token.type == "PIPE":
                            self.advance()  # consume |
                            continue
                        # Check for intersection operator &
                        elif self.current_token and self.current_token.type == "AMPERSAND":
                            self.advance()  # consume &
                            constraint_parts.append("&")
                            continue
                        break
                    
                    type_constraints[tparam_tok.value] = " | ".join(constraint_parts)
                
                if self.current_token and self.current_token.type == "COMMA":
                    self.advance()  # consume ,
                    continue
                break
            
            if not (self.current_token and self.current_token.type == "GREATER_THAN"):
                self.error("Expected '>' to close type parameters", self.current_token)
                return None
            self.advance()  # consume >
        
        # Validate return type if it was an IDENTIFIER (type parameter)
        if ret_type_token and ret_type_token.type == "IDENTIFIER" and ret_type_token.value not in self.TYPE_TOKEN_NAMES:
            # It must be a declared type parameter
            if ret_type_token.value not in type_params:
                self.error(f"Return type '{ret_type_token.value}' is not a declared type parameter", ret_type_token)
                return None
        
        if not self.consume("OPEN_PAREN"):
            self.error("Expected '(' after function name", self.current_token)
            return None

        # Set current type parameters for parsing function body
        prev_type_params = self._current_type_params
        self._current_type_params = type_params.copy()

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
        # Attach generic metadata
        func_node.type_params = type_params
        func_node.type_constraints = type_constraints
        
        # Restore previous type parameters
        self._current_type_params = prev_type_params
        
        if ret_type_token and name_token:
            self.user_functions[name_token.value] = return_type_value
            if type_params:
                self.generic_functions[name_token.value] = type_params
                self.generic_constraints[name_token.value] = type_constraints
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
            # Top-level import statements
            if self.current_token.type == "IMPORT":
                imp = self._parse_import()
                if imp:
                    imp.parent = self.ast
                    self.ast.children.append(imp)
                # Optional semicolon
                if self.current_token and self.current_token.type == "SEMICOLON":
                    self.consume("SEMICOLON")
                continue
            # Compiler directives
            if self.current_token.type == "DIRECTIVE":
                dir_tok = self.current_token
                self.advance()
                name_tok = self.consume("IDENTIFIER")
                if name_tok is None:
                    self.error("Expected directive name after 'directive'", self.current_token or dir_tok)
                    continue
                # Validate directive name against known directives
                directive_value = name_tok.value
                try:
                    directive_enum = CompilerDirective(directive_value)
                except Exception:
                    self.error(f"Unknown directive '{directive_value}'", name_tok)
                    directive_enum = None
                # Consume semicolon
                if self.current_token and self.current_token.type == "SEMICOLON":
                    self.consume("SEMICOLON")
                else:
                    self.error("Expected semicolon after directive", self.current_token or name_tok)
                # Record directive name and emit a node
                if directive_enum is not None:
                    self.directives.add(directive_enum.value)
                    node_name = directive_enum.value
                else:
                    node_name = directive_value
                directive_node = ASTNode(NodeTypes.DIRECTIVE, dir_tok, node_name, [], dir_tok.index)
                # Mark the directive with the source file so we can filter by file later
                directive_node.source_file = self.filename
                directive_node.parent = self.ast
                self.ast.children.append(directive_node)
                continue
            # Class definition
            if self.current_token.type == "CLASS":
                cls = self._parse_class_definition()
                if cls:
                    cls.parent = self.ast
                    self.ast.children.append(cls)
                continue
            # Constraint declaration
            if self.current_token.type == "CONSTRAINT":
                self._parse_constraint_declaration()
                # Optional semicolon
                if self.current_token and self.current_token.type == "SEMICOLON":
                    self.consume("SEMICOLON")
                continue
            # Try function definition first: <type> <identifier> '(' ... ')'{ ... }
            # Also handle generic functions where return type might be a type parameter
            stmt = None
            # Check for function definition patterns
            can_be_func = False
            if self._is_type_token(self.current_token):
                can_be_func = True
            elif self.current_token and self.current_token.type == "IDENTIFIER":
                # Could be a generic function with type parameter as return type
                # Look for pattern: IDENTIFIER IDENTIFIER '<' ...
                # Need to peek ahead more carefully to handle constraints with PIPE tokens
                idx_cur = self.tokens.index(self.current_token)
                if idx_cur + 2 < len(self.tokens):
                    next1 = self.tokens[idx_cur + 1]
                    next2 = self.tokens[idx_cur + 2]
                    if next1.type == "IDENTIFIER" and next2.type == "LESS_THAN":
                        can_be_func = True  # Likely a generic function
            
            if can_be_func:
                idx_cur = self.tokens.index(self.current_token)
                # Gather next few meaningful tokens to detect patterns
                look = []
                m = idx_cur + 1
                while m < len(self.tokens) and len(look) < 30:  # Increased for generics with long constraints
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
                # 3) TYPE IDENTIFIER '<' ... '>' '('  (generic function)
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
                elif (
                    len(look) >= 3
                    and look[0].type == "IDENTIFIER"
                    and look[1].type == "LESS_THAN"
                ):
                    # Generic function: TYPE IDENTIFIER '<' ...
                    # Look for matching '>' followed by '('
                    angle_depth = 1
                    i = 2
                    while i < len(look) and angle_depth > 0:
                        if look[i].type == "LESS_THAN":
                            angle_depth += 1
                        elif look[i].type == "GREATER_THAN":
                            angle_depth -= 1
                        i += 1
                    # Check if we have '(' after the closing '>'
                    if i < len(look) and look[i].type == "OPEN_PAREN":
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

    def _parse_import(self) -> Optional[ASTNode]:
        """Parse an import statement in one of the accepted forms.
        Forms:
          - import module.path
          - import module.path as Alias
          - import module.path.symbol [as alias]
          - import module.path.{a [as x]?, b [as y]?}
          - import module.path.*
          - import @user/package (external; parse then error)
        """
        start_tok = self.consume("IMPORT")
        if start_tok is None:
            return None

        kind: Optional[str] = None
        module_path = ""
        alias: Optional[str] = None
        symbols: list[dict] = []

        # External package form begins with '@'
        if self.current_token and self.current_token.type == "AT":
            # Collect '@' + path tokens (IDENTIFIER separated by '/'), until non-path token
            segs: list[str] = []
            at_tok = self.consume("AT")
            if not (self.current_token and self.current_token.type == "IDENTIFIER"):
                self.error("Expected package name after '@'", self.current_token or at_tok)
                return None
            idtok = self.consume("IDENTIFIER")
            if idtok is None:
                self.error("Expected identifier after '@'", self.current_token or at_tok)
                return None
            segs.append(idtok.value)
            # Accept sequence of '/' IDENTIFIER (slash tokenized as DIVIDE)
            while self.current_token and self.current_token.type == "DIVIDE":
                self.advance()
                if not (self.current_token and self.current_token.type == "IDENTIFIER"):
                    self.error("Expected identifier after '/' in external package name", self.current_token)
                    break
                nxtok = self.consume("IDENTIFIER")
                if nxtok is None:
                    self.error("Expected identifier after '/' in external package name", self.current_token)
                    break
                segs.append(nxtok.value)
            
            # Check if this is @firescript/ (standard library)
            if segs and segs[0] == "firescript":
                # This is a standard library import, treat as internal module
                # @firescript/std.math -> firescript.std.math
                # Continue parsing dotted path after the / part
                module_segs = segs.copy()
                
                # Parse any additional .IDENTIFIER parts
                iteration = 0
                while self.current_token and self.current_token.type == "DOT":
                    iteration += 1
                    if iteration > 20:
                        self.error(f"Too many iterations parsing dotted path. Current token: {self.current_token}, module_segs: {module_segs}", self.current_token)
                        break
                    # Lookahead to see if this is part of module path or symbol syntax
                    nxt = self.peek(1)
                    if not nxt:
                        break
                    if nxt.type == "OPEN_BRACE":
                        # This is .{symbols} syntax, stop module path parsing
                        break
                    if nxt.type == "MULTIPLY":
                        # This is .* syntax, stop module path parsing
                        break
                    if nxt.type == "IDENTIFIER" or self._is_type_token(nxt):
                        # Check what comes after the identifier
                        nxt2 = self.peek(2)
                        # If followed by {, *, or end of tokens, this is symbol syntax
                        if nxt2 and nxt2.type in ("OPEN_BRACE", "MULTIPLY"):
                            # The identifier after DOT is part of symbol syntax, stop here
                            break
                        # Otherwise, this identifier is part of module path
                        self.advance()  # consume '.'
                        id_tok = self.current_token
                        self.advance()  # consume identifier
                        module_segs.append(id_tok.value)
                        # Continue to check if there's more path
                    else:
                        # Unknown token after DOT, stop
                        break
                
                module_path = ".".join(module_segs)
                kind = None  # Will be determined later (module, symbols, wildcard)
                
                # Now parse any symbol syntax: .{symbols}, .*, or .symbol
                if self.current_token and self.current_token.type == "DOT":
                    self.advance()
                    if self.current_token and self.current_token.type == "OPEN_BRACE":
                        # Group of symbols: {a [as x]?, b [as y]?}
                        self.advance()
                        while self.current_token and self.current_token.type != "CLOSE_BRACE":
                            if not (self.current_token and self.current_token.type == "IDENTIFIER"):
                                self.error("Expected identifier in import symbol list", self.current_token)
                                break
                            sname_tok = self.consume("IDENTIFIER")
                            salias = None
                            # Support contextual 'as' even if it's lexed as IDENTIFIER
                            if self.current_token and (
                                self.current_token.type == "AS"
                                or (self.current_token.type == "IDENTIFIER" and self.current_token.value == "as")
                            ):
                                self.advance()  # consume 'as'
                                al = self.consume("IDENTIFIER")
                                if al is None:
                                    self.error("Expected alias name after 'as'", self.current_token)
                                    return None
                                salias = al.value
                            if sname_tok is None:
                                self.error("Expected identifier in import symbol list", self.current_token)
                                break
                            symbols.append({"name": sname_tok.value, "alias": salias})
                            if self.current_token and self.current_token.type == "COMMA":
                                self.advance()
                                continue
                            else:
                                break
                        if not self.consume("CLOSE_BRACE"):
                            self.error("Expected '}' to close import symbol list", self.current_token)
                            return None
                        kind = "symbols"
                    elif self.current_token and self.current_token.type == "MULTIPLY":
                        # Wildcard import
                        self.advance()
                        kind = "wildcard"
                    elif self.current_token and self.current_token.type == "IDENTIFIER":
                        # Single symbol
                        sname_tok = self.consume("IDENTIFIER")
                        if sname_tok is None:
                            self.error("Expected symbol name after '.' in import", self.current_token)
                            return None
                        salias = None
                        if self.current_token and (
                            self.current_token.type == "AS"
                            or (self.current_token.type == "IDENTIFIER" and self.current_token.value == "as")
                        ):
                            self.advance()  # consume 'as'
                            al = self.consume("IDENTIFIER")
                            if al is None:
                                self.error("Expected alias name after 'as'", self.current_token)
                                return None
                            salias = al.value
                        symbols.append({"name": sname_tok.value, "alias": salias})
                        kind = "symbols"
                    else:
                        self.error("Expected symbol name, '*', or '{' after '.' in import", self.current_token)
                        return None
                else:
                    # No symbol syntax, just module import
                    kind = "module"
            else:
                # External package (not supported)
                module_path = "@" + "/".join(segs)
                kind = "external"
        else:
            # Parse dotted module path: IDENTIFIER ('.' IDENTIFIER)*
            # Note: type keywords (like 'string') can appear in module names
            segs: list[str] = []
            if not (self.current_token and (self.current_token.type == "IDENTIFIER" or self._is_type_token(self.current_token))):
                self.error("Expected module name after 'import'", self.current_token or start_tok)
                return None
            idtok = self.current_token
            self.advance()
            segs.append(idtok.value)
            while self.current_token and self.current_token.type == "DOT":
                # Lookahead to decide whether this dot continues the module path or begins symbol/wildcard/group
                nxt = self.peek(1)
                if nxt and (nxt.type == "IDENTIFIER" or self._is_type_token(nxt)):
                    # Check if there's another DOT after this identifier to decide if it's part of module path
                    nxt2 = self.peek(2)
                    if nxt2 and nxt2.type == "DOT":
                        # More path segments coming, so this identifier is part of module path
                        self.advance()  # consume '.'
                        id2 = self.current_token
                        self.advance()
                        segs.append(id2.value)
                        continue
                    else:
                        # No more dots after next identifier, so treat as: module.symbol
                        # Don't consume the dot yet - let the symbol handling logic below process it
                        break
                break
            module_path = ".".join(segs)

            # Optional: .symbol / .{a,b} / .* or module alias
            # Skip for external packages (already marked)
            if kind != "external" and self.current_token and self.current_token.type == "DOT":
                self.advance()
                if self.current_token and self.current_token.type == "OPEN_BRACE":
                    # Group of symbols: {a [as x]?, b [as y]?}
                    self.advance()
                    while self.current_token and self.current_token.type != "CLOSE_BRACE":
                        if not (self.current_token and self.current_token.type == "IDENTIFIER"):
                            self.error("Expected identifier in import symbol list", self.current_token)
                            break
                        sname_tok = self.consume("IDENTIFIER")
                        salias = None
                        # Support contextual 'as' even if it's lexed as IDENTIFIER
                        if self.current_token and (
                            self.current_token.type == "AS"
                            or (self.current_token.type == "IDENTIFIER" and self.current_token.value == "as")
                        ):
                            self.advance()  # consume 'as'
                            al = self.consume("IDENTIFIER")
                            if al is None:
                                self.error("Expected alias name after 'as'", self.current_token)
                                return None
                            salias = al.value
                        if sname_tok is None:
                            self.error("Expected identifier in import symbol list", self.current_token)
                            break
                        symbols.append({"name": sname_tok.value, "alias": salias})
                        if self.current_token and self.current_token.type == "COMMA":
                            self.advance()
                            continue
                        else:
                            break
                    if not self.consume("CLOSE_BRACE"):
                        self.error("Expected '}' to close import symbol list", self.current_token)
                        return None
                    kind = "symbols"
                elif self.current_token and self.current_token.type == "MULTIPLY":
                    # Wildcard import
                    self.advance()
                    kind = "wildcard"
                elif self.current_token and self.current_token.type == "IDENTIFIER":
                    # Single symbol
                    sname_tok = self.consume("IDENTIFIER")
                    if sname_tok is None:
                        self.error("Expected symbol name after '.' in import", self.current_token)
                        return None
                    salias = None
                    if self.current_token and (
                        self.current_token.type == "AS"
                        or (self.current_token.type == "IDENTIFIER" and self.current_token.value == "as")
                    ):
                        self.advance()  # consume 'as'
                        al = self.consume("IDENTIFIER")
                        if al is None:
                            self.error("Expected alias name after 'as'", self.current_token)
                            return None
                        salias = al.value
                    symbols.append({"name": sname_tok.value, "alias": salias})
                    kind = "symbols"
                else:
                    self.error("Expected symbol name, '*', or '{' after '.' in import", self.current_token)
                    return None
            else:
                # Module import with optional alias: import module.path [as Alias]
                if self.current_token and (
                    self.current_token.type == "AS"
                    or (self.current_token.type == "IDENTIFIER" and self.current_token.value == "as")
                ):
                    self.advance()  # consume 'as'
                    al = self.consume("IDENTIFIER")
                    if al is None:
                        self.error("Expected alias name after 'as'", self.current_token)
                        return None
                    alias = al.value
                kind = "module"

        # Build node
        node = ASTNode(NodeTypes.IMPORT_STATEMENT, start_tok, "import", [], start_tok.index)
        setattr(node, "module_path", module_path)
        setattr(node, "kind", kind)
        setattr(node, "alias", alias)
        setattr(node, "symbols", symbols)
        end_tok = self.current_token or start_tok
        setattr(node, "span", (start_tok.index, end_tok.index))

        # For external imports, produce an error now
        if kind == "external":
            self.error("External packages are not supported", start_tok)

        return node

    def _parse_constraint_declaration(self):
        """Parse a constraint declaration: constraint Name = type1 | type2 | ...; """
        constraint_tok = self.consume("CONSTRAINT")
        if constraint_tok is None:
            return None
        
        name_tok = self.consume("IDENTIFIER")
        if name_tok is None:
            self.error("Expected constraint name after 'constraint'", self.current_token)
            return None
        
        if not self.consume("ASSIGN"):
            self.error("Expected '=' after constraint name", self.current_token)
            return None
        
        # Parse the type union: type1 | type2 | type3 | ...
        type_parts = []
        while True:
            # Accept IDENTIFIER (for interface names or aliases) or type tokens (int32, float64, etc.)
            if not (self.current_token and (self.current_token.type == "IDENTIFIER" or self._is_type_token(self.current_token))):
                self.error("Expected type name in constraint definition", self.current_token)
                return None
            
            type_tok = self.current_token
            self.advance()
            if type_tok is None:
                return None
            
            # Normalize type token names (convert INT32 -> int32, etc.)
            type_name = self._normalize_type_name(type_tok) if self._is_type_token(type_tok) else type_tok.value
            
            # If it's a constraint alias, expand it recursively
            if type_name in self.constraint_aliases:
                # Recursively expand the alias
                type_parts.append(self.constraint_aliases[type_name])
            else:
                type_parts.append(type_name)
            
            # Check for pipe operator (union)
            if self.current_token and self.current_token.type == "PIPE":
                self.advance()  # consume |
                continue
            # Check for ampersand (intersection - for combining with interfaces)
            elif self.current_token and self.current_token.type == "AMPERSAND":
                self.advance()  # consume &
                type_parts.append("&")
                continue
            break
        
        # Store the constraint alias
        constraint_string = " | ".join(type_parts)
        self.constraint_aliases[name_tok.value] = constraint_string
        
        # Constraint declarations don't produce AST nodes, they just update the constraint map
        return None

    def _parse_class_definition(self):
        """Parse a class definition: class Name [from Base] { <type> <field>; ... }"""
        class_tok = self.consume("CLASS")
        if class_tok is None:
            return None
        name_tok = self.consume("IDENTIFIER")
        if name_tok is None:
            self.error("Expected class name after 'class'", self.current_token)
            return None

        base_class: Optional[str] = None
        if self.current_token and self.current_token.type == "FROM":
            self.advance()  # consume 'from'
            base_tok = self.consume("IDENTIFIER")
            if base_tok is None:
                self.error("Expected base class name after 'from'", self.current_token)
                return None
            base_class = base_tok.value
            if base_class == name_tok.value:
                self.error("A class cannot inherit from itself", base_tok)

        if not self.consume("OPEN_BRACE"):
            self.error("Expected '{' to start class body", self.current_token)
            return None
        fields: list[ASTNode] = []
        methods: list[ASTNode] = []
        field_types: dict[str, str] = {}
        while self.current_token and self.current_token.type != "CLOSE_BRACE":
            # Skip comments and empty statements inside class body
            if self.current_token.type in (
                "SINGLE_LINE_COMMENT",
                "MULTI_LINE_COMMENT_START",
            ):
                self._skip_comment()
                continue
            if self.current_token.type == "SEMICOLON":
                self.advance()
                continue
            # Accept types that are either known types or the current class name (for methods/fields/constructors)
            if not (self._is_type_token(self.current_token) or (
                self.current_token.type == "IDENTIFIER" and self.current_token.value == name_tok.value
            )):
                self.error("Expected field or method return type in class body", self.current_token)
                # recover to ';' or '}'
                while self.current_token and self.current_token.type not in ("SEMICOLON", "CLOSE_BRACE"):
                    self.advance()
                if self.current_token and self.current_token.type == "SEMICOLON":
                    self.advance()
                continue
            ftype_tok = self.current_token
            self.advance()

            # Special-case: constructor without explicit return type
            # Pattern: ClassName(<params>) { ... }
            if (
                ftype_tok.type == "IDENTIFIER"
                and ftype_tok.value == name_tok.value
                and self.current_token
                and self.current_token.type == "OPEN_PAREN"
            ):
                # Treat ftype_tok as the method name (constructor) and set return type to class name
                method_name_tok = ftype_tok
                # Parse parameters
                self.consume("OPEN_PAREN")
                params: list[ASTNode] = []
                seen_receiver = False
                if self.current_token and self.current_token.type != "CLOSE_PAREN":
                    while True:
                        # Borrowed receiver syntax: &this
                        if (not seen_receiver) and self.current_token and self.current_token.type == "AMPERSAND":
                            amp_tok = self.current_token
                            self.advance()
                            th_tok = self.consume("IDENTIFIER")
                            if th_tok is None or th_tok.value != "this":
                                self.error("Expected 'this' after '&' for receiver", th_tok or amp_tok)
                                return None
                            recv = ASTNode(
                                NodeTypes.PARAMETER,
                                th_tok,
                                "this",
                                [],
                                th_tok.index,
                                self._normalize_type_name(name_tok),
                                False,
                                False,
                                None,
                                False,
                                False,
                            )
                            setattr(recv, "is_borrowed", True)
                            setattr(recv, "is_receiver", True)
                            params.append(recv)
                            seen_receiver = True
                        else:
                            # Parameter type: allow known types or current class name
                            if not (self.current_token and (self._is_type_token(self.current_token) or (
                                self.current_token.type == "IDENTIFIER" and self.current_token.value == name_tok.value
                            ))):
                                self.error("Expected parameter type in method", self.current_token)
                                return None
                            ptype_tok = self.current_token
                            self.advance()
                            p_is_array = False
                            if self.current_token and self.current_token.type == "OPEN_BRACKET":
                                self.error("Array parameters are not supported for methods", self.current_token)
                                # try to recover
                                while self.current_token and self.current_token.type != "CLOSE_PAREN":
                                    self.advance()
                                break
                            p_is_borrowed = False
                            if self.current_token and self.current_token.type == "AMPERSAND":
                                p_is_borrowed = True
                                self.advance()
                            pname_tok = self.consume("IDENTIFIER")
                            if pname_tok is None:
                                self.error("Expected parameter name in method", self.current_token)
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
                            if p_is_borrowed:
                                setattr(param_node, "is_borrowed", True)
                            params.append(param_node)
                        if self.current_token and self.current_token.type == "COMMA":
                            self.advance()
                            continue
                        break
                if not self.consume("CLOSE_PAREN"):
                    self.error("Expected ')' after method parameters", self.current_token)
                    return None
                if not (self.current_token and self.current_token.type == "OPEN_BRACE"):
                    self.error("Expected '{' to start method body", self.current_token)
                    return None

                self._class_context_stack.append((name_tok.value, True, base_class))
                try:
                    body_node = self.parse_scope()
                finally:
                    self._class_context_stack.pop()
                if body_node is None:
                    return None
                # Constructor: no synthetic 'self' parameter
                method_node = ASTNode(
                    NodeTypes.CLASS_METHOD_DEFINITION,
                    method_name_tok,
                    method_name_tok.value,
                    [*params, body_node],
                    method_name_tok.index,
                    None,
                    False,
                    False,
                    name_tok.value,  # return type is the class itself
                    False,
                    False,
                )
                setattr(method_node, "class_name", name_tok.value)
                setattr(method_node, "is_constructor", True)
                methods.append(method_node)
                continue
            # Look ahead: IDENTIFIER then '(' => method; IDENTIFIER then ';' => field
            name_tok2 = self.consume("IDENTIFIER")
            if name_tok2 is None:
                self.error("Expected identifier after type in class body", self.current_token)
                break
            # Method definition
            if self.current_token and self.current_token.type == "OPEN_PAREN":
                # Determine if this is a constructor: method name equals class name
                is_constructor = (name_tok2.value == name_tok.value)
                # Parse parameters
                self.consume("OPEN_PAREN")
                params: list[ASTNode] = []
                seen_receiver = False
                if self.current_token and self.current_token.type != "CLOSE_PAREN":
                    while True:
                        # Borrowed receiver syntax: &this (only allowed as first parameter)
                        if (not seen_receiver) and self.current_token and self.current_token.type == "AMPERSAND":
                            amp_tok = self.current_token
                            self.advance()
                            th_tok = self.consume("IDENTIFIER")
                            if th_tok is None or th_tok.value != "this":
                                self.error("Expected 'this' after '&' for receiver", th_tok or amp_tok)
                                return None
                            recv = ASTNode(
                                NodeTypes.PARAMETER,
                                th_tok,
                                "this",
                                [],
                                th_tok.index,
                                self._normalize_type_name(name_tok),
                                False,
                                False,
                                None,
                                False,
                                False,
                            )
                            setattr(recv, "is_borrowed", True)
                            setattr(recv, "is_receiver", True)
                            params.append(recv)
                            seen_receiver = True
                        else:
                            # Parameter type: allow known types or current class name
                            if not (self.current_token and (self._is_type_token(self.current_token) or (
                                self.current_token.type == "IDENTIFIER" and self.current_token.value == name_tok.value
                            ))):
                                self.error("Expected parameter type in method", self.current_token)
                                return None
                            ptype_tok = self.current_token
                            self.advance()
                            p_is_array = False
                            if self.current_token and self.current_token.type == "OPEN_BRACKET":
                                self.error("Array parameters are not supported for methods", self.current_token)
                                # try to recover
                                while self.current_token and self.current_token.type != "CLOSE_PAREN":
                                    self.advance()
                                break
                            p_is_borrowed = False
                            if self.current_token and self.current_token.type == "AMPERSAND":
                                p_is_borrowed = True
                                self.advance()
                            pname_tok = self.consume("IDENTIFIER")
                            if pname_tok is None:
                                self.error("Expected parameter name in method", self.current_token)
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
                            if p_is_borrowed:
                                setattr(param_node, "is_borrowed", True)
                            params.append(param_node)
                        if self.current_token and self.current_token.type == "COMMA":
                            self.advance()
                            continue
                        break
                if not self.consume("CLOSE_PAREN"):
                    self.error("Expected ')' after method parameters", self.current_token)
                    return None
                if not (self.current_token and self.current_token.type == "OPEN_BRACE"):
                    self.error("Expected '{' to start method body", self.current_token)
                    return None

                self._class_context_stack.append((name_tok.value, bool(is_constructor), base_class))
                try:
                    body_node = self.parse_scope()
                finally:
                    self._class_context_stack.pop()
                if body_node is None:
                    return None
                param_nodes = params
                if not is_constructor and not (params and params[0].name == "this"):
                    # Inject synthetic receiver named 'this' if not explicitly provided
                    self_param = ASTNode(
                        NodeTypes.PARAMETER,
                        name_tok2,
                        "this",
                        [],
                        name_tok2.index,
                        self._normalize_type_name(name_tok),
                        False,
                        False,
                        None,
                        False,
                        False,
                    )
                    setattr(self_param, "is_receiver", True)
                    param_nodes = [self_param, *params]

                method_node = ASTNode(
                    NodeTypes.CLASS_METHOD_DEFINITION,
                    name_tok2,
                    name_tok2.value,
                    [*param_nodes, body_node],
                    name_tok2.index,
                    None,
                    False,
                    False,
                    self._normalize_type_name(ftype_tok),
                    False,
                    False,
                )
                # Tag class name on node for downstream passes
                setattr(method_node, "class_name", name_tok.value)
                setattr(method_node, "is_constructor", is_constructor)
                methods.append(method_node)
            else:
                # Field declaration path
                if not self.consume("SEMICOLON"):
                    self.error("Expected ';' after field declaration", self.current_token)
                    while self.current_token and self.current_token.type not in ("SEMICOLON", "CLOSE_BRACE"):
                        self.advance()
                    if self.current_token and self.current_token.type == "SEMICOLON":
                        self.advance()
                field_type = self._normalize_type_name(ftype_tok)
                field_node = ASTNode(NodeTypes.CLASS_FIELD, name_tok2, name_tok2.value, [], name_tok2.index, var_type=field_type)
                fields.append(field_node)
                field_types[name_tok2.value] = field_type
        # consume closing brace if present
        if self.current_token and self.current_token.type == "CLOSE_BRACE":
            self.consume("CLOSE_BRACE")

        # Inheritance: synthesize inherited fields/methods (single inheritance)
        inherited_fields: list[ASTNode] = []
        inherited_methods: list[ASTNode] = []
        if base_class:
            base_fields_map = self.user_classes.get(base_class)
            if base_fields_map is not None:
                for fname, ftype in base_fields_map.items():
                    if fname in field_types:
                        self.error(
                            f"Field '{fname}' in '{name_tok.value}' conflicts with inherited field from '{base_class}'",
                            name_tok,
                        )
                        continue
                    inherited_node = ASTNode(
                        NodeTypes.CLASS_FIELD,
                        name_tok,
                        fname,
                        [],
                        name_tok.index,
                        var_type=ftype,
                    )
                    inherited_fields.append(inherited_node)
                    field_types[fname] = ftype

            base_method_nodes = self._class_method_nodes.get(base_class, [])
            existing_method_names = {m.name for m in methods if m.node_type == NodeTypes.CLASS_METHOD_DEFINITION}
            for bm in base_method_nodes:
                if getattr(bm, "is_constructor", False):
                    continue
                if bm.name in existing_method_names:
                    continue
                dm = copy.deepcopy(bm)
                setattr(dm, "class_name", name_tok.value)
                setattr(dm, "is_constructor", False)
                for ch in dm.children:
                    if ch.node_type == NodeTypes.PARAMETER and ch.name == "this":
                        ch.var_type = name_tok.value
                        break
                inherited_methods.append(dm)

        all_fields = [*inherited_fields, *fields]
        all_methods = [*methods, *inherited_methods]

        # register class type
        self.user_types.add(name_tok.value)
        self.user_classes[name_tok.value] = field_types
        self.user_class_bases[name_tok.value] = base_class
        self._class_field_nodes[name_tok.value] = all_fields
        self._class_method_nodes[name_tok.value] = all_methods

        # register methods meta
        if name_tok.value not in self.user_methods:
            self.user_methods[name_tok.value] = {}

        # Merge base method signatures into derived lookup (override by derived if present)
        if base_class and base_class in self.user_methods:
            for mname, sig in self.user_methods[base_class].items():
                if mname not in self.user_methods[name_tok.value]:
                    self.user_methods[name_tok.value][mname] = sig

        for m in all_methods:
            # Gather parameter nodes (exclude trailing body scope)
            param_nodes = [p for p in m.children[:-1] if p.node_type == NodeTypes.PARAMETER]
            # Exclude receiver (explicit &this or synthetic) from external signature
            if getattr(m, "is_constructor", False):
                effective_params = (
                    param_nodes[1:] if (param_nodes and param_nodes[0].name == "this") else param_nodes
                )
            else:
                effective_params = (
                    param_nodes[1:] if (param_nodes and param_nodes[0].name == "this") else param_nodes
                )
            params_types = [p.var_type for p in effective_params]
            self.user_methods[name_tok.value][m.name] = {"return": m.return_type, "params": params_types}

        cls_node = ASTNode(NodeTypes.CLASS_DEFINITION, name_tok, name_tok.value, [*all_fields, *all_methods], name_tok.index)
        setattr(cls_node, "base_class", base_class)
        return cls_node

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
