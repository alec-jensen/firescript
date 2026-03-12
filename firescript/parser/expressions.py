from typing import Optional

from enums import NodeTypes
from .ast_node import ASTNode
from .base import ParserBase


class ExpressionsMixin(ParserBase):
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

        # Handle ==, !=, >, <, >=, <=
        while self.current_token and self.current_token.type in (
            "EQUALS",
            "NOT_EQUALS",
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
            if op_token.type in ("EQUALS", "NOT_EQUALS"):
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
        # Java-like constructor: new ClassName(args)  or  new Generic<T1,T2>(args)
        if token.type == "NEW":
            self.advance()
            cls_tok = self.consume("IDENTIFIER")
            if cls_tok is None:
                self.error("Expected class name after 'new'", self.current_token)
                return None
            # Generic class constructor: new Pair<int32, string>(args)
            composite_class_name: Optional[str] = None
            if (
                cls_tok.value in self.generic_class_templates
                and self.current_token
                and self.current_token.type == "LESS_THAN"
            ):
                self.advance()  # consume <
                type_args: list[str] = []
                while True:
                    if not (self.current_token and self._is_type_token(self.current_token)):
                        self.error("Expected type argument", self.current_token)
                        return None
                    targ_tok = self.current_token
                    self.advance()
                    type_args.append(self._normalize_type_name(targ_tok))
                    if self.current_token and self.current_token.type == "COMMA":
                        self.advance()
                        continue
                    break
                if not (self.current_token and self.current_token.type == "GREATER_THAN"):
                    self.error("Expected '>' after generic type arguments", self.current_token)
                    return None
                self.advance()  # consume >
                composite_class_name = self._register_generic_class_instance(cls_tok.value, type_args)
            else:
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
            used_name = composite_class_name if composite_class_name else cls_tok.value
            node = ASTNode(NodeTypes.CONSTRUCTOR_CALL, cls_tok, used_name, args, cls_tok.index)
            node.return_type = used_name
            return node
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
                
                # Explicit generic type arguments: func<T1, T2>(...)  or  GenericClass<T1,T2>(args)
                elif self.current_token and self.current_token.type == "LESS_THAN":
                    # Check if this is a generic class positional constructor
                    if token.value in self.generic_class_templates:
                        self.advance()  # consume <
                        type_args = []
                        while True:
                            if not (self.current_token and self._is_type_token(self.current_token)):
                                self.error("Expected type argument in generic class constructor", self.current_token)
                                break
                            targ_tok = self.current_token
                            self.advance()
                            type_args.append(self._normalize_type_name(targ_tok))
                            if self.current_token and self.current_token.type == "COMMA":
                                self.advance()
                                continue
                            break
                        if not (self.current_token and self.current_token.type == "GREATER_THAN"):
                            self.error("Expected '>' to close generic type arguments", self.current_token)
                        else:
                            self.advance()  # consume >
                        
                        composite_name = self._register_generic_class_instance(token.value, type_args)
                        
                        # Now parse constructor argument list
                        if not (self.current_token and self.current_token.type == "OPEN_PAREN"):
                            self.error("Expected '(' after generic class type arguments", self.current_token)
                            break
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
                        self.consume("CLOSE_PAREN")
                        node = ASTNode(NodeTypes.FUNCTION_CALL, token, composite_name, arguments, token.index)
                        node.return_type = composite_name
                        continue
                    # Check if this is a generic function call
                    elif token.value in self.generic_functions:
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
                    elif self.defer_undefined_identifiers and self._looks_like_generic_constructor_call():
                        # Deferred-import mode: the identifier is not yet known as a generic class
                        # or function (it comes from an imported module).  Parse it as a generic
                        # class constructor call so parsing can succeed; the semantic checks will
                        # be completed after imports are merged.
                        self.advance()  # consume <
                        type_args = []
                        while True:
                            if not (self.current_token and self._is_type_token(self.current_token)):
                                break
                            targ_tok = self.current_token
                            self.advance()
                            type_args.append(self._normalize_type_name(targ_tok))
                            if self.current_token and self.current_token.type == "COMMA":
                                self.advance()
                                continue
                            break
                        if not (self.current_token and self.current_token.type == "GREATER_THAN"):
                            self.error("Expected '>' to close generic type arguments", self.current_token)
                        else:
                            self.advance()  # consume >
                        composite_name = self._register_generic_class_instance(token.value, type_args)
                        if not (self.current_token and self.current_token.type == "OPEN_PAREN"):
                            self.error("Expected '(' after generic type arguments", self.current_token)
                            break
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
                        self.consume("CLOSE_PAREN")
                        node = ASTNode(NodeTypes.FUNCTION_CALL, token, composite_name, arguments, token.index)
                        node.return_type = composite_name
                        continue
                    else:
                        # Not a generic function or class, this is a comparison operator
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
                # Postfix increment/decrement: x++ or x--
                elif self.current_token and self.current_token.type in ("INCREMENT", "DECREMENT"):
                    op_token = self.current_token
                    self.advance()
                    node = ASTNode(
                        NodeTypes.UNARY_EXPRESSION,
                        node.token if node else op_token,
                        op_token.value,  # "++" or "--"
                        [],  # No children for postfix increment/decrement
                        op_token.index,
                    )
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
