import logging
from typing import Optional

from enums import NodeTypes
from .ast_node import ASTNode
from .expressions import ExpressionsMixin


class StatementsMixin(ExpressionsMixin):
    def _parse_braceless_body(self, fallback_tok, scope_name="scope") -> ASTNode:
        """Parse a single statement and wrap it in a SCOPE node.

        Used for braceless single-statement bodies in if/while/for.
        fallback_tok is used for token/index when the statement is absent.
        """
        stmt = self._parse_statement()
        tok = stmt.token if stmt else fallback_tok
        idx = stmt.index if stmt else (fallback_tok.index if fallback_tok else 0)
        body = ASTNode(NodeTypes.SCOPE, tok, scope_name, [stmt] if stmt else [], idx)
        if stmt:
            stmt.parent = body
        return body

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
            then_branch_node = self._parse_braceless_body(
                expected_then_body_token, scope_name="scope_then"
            )

        # Optional else branch (single level)
        else_branch_node: Optional[ASTNode] = None
        if self.current_token and self.current_token.type == "ELSE":
            self.consume("ELSE")
            if self.current_token and self.current_token.type == "OPEN_BRACE":
                else_branch_node = self.parse_scope()
            else:
                else_branch_node = self._parse_braceless_body(
                    expected_then_body_token, scope_name="scope_else"
                )

        children = [condition, then_branch_node]
        if else_branch_node:
            children.append(else_branch_node)

        if_node = ASTNode(NodeTypes.IF_STATEMENT, if_token, "if", children, if_token.index)
        # Set parent for all children
        if condition:
            condition.parent = if_node
        if then_branch_node:
            then_branch_node.parent = if_node
        if else_branch_node:
            else_branch_node.parent = if_node
        return if_node

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
        is_deferred_generic = (
            self.defer_undefined_identifiers
            and self.current_token is not None
            and self.current_token.type == "IDENTIFIER"
            and bool(self.current_token.value.strip())
            and self.peek() is not None
            and self.peek().type == "LESS_THAN"
        )
        if not (self.current_token and (self._is_type_token(self.current_token) or is_deferred_generic)):
            self.error("Expected type in variable declaration", self.current_token)
            return None
        type_token = self.current_token
        self.advance()

        # Check for generic class instantiation: TypeName<T1, T2>
        composite_type: Optional[str] = None
        if (
            type_token.type == "IDENTIFIER"
            and (
                type_token.value in self.generic_class_templates
                or (
                    self.defer_undefined_identifiers
                    and self.current_token
                    and self.current_token.type == "LESS_THAN"
                )
            )
            and self.current_token
            and self.current_token.type == "LESS_THAN"
        ):
            # Parse type arguments
            self.advance()  # consume <
            type_args: list[str] = []
            while True:
                if not (self.current_token and self._is_type_token(self.current_token)):
                    self.error("Expected type argument in generic class instantiation", self.current_token)
                    return None
                targ_tok = self.current_token
                self.advance()
                type_arg_name = self._normalize_type_name(targ_tok)
                # Recursively handle nested generic type args: e.g. Pair<Pair<int32,int32>, string>
                if (
                    targ_tok.type == "IDENTIFIER"
                    and targ_tok.value in self.generic_class_templates
                    and self.current_token
                    and self.current_token.type == "LESS_THAN"
                ):
                    self.advance()  # consume nested <
                    nested_args: list[str] = []
                    while True:
                        if not (self.current_token and self._is_type_token(self.current_token)):
                            self.error("Expected type argument in nested generic class instantiation", self.current_token)
                            return None
                        ntarg_tok = self.current_token
                        self.advance()
                        nested_args.append(self._normalize_type_name(ntarg_tok))
                        if self.current_token and self.current_token.type == "COMMA":
                            self.advance()
                            continue
                        break
                    if not (self.current_token and self.current_token.type == "GREATER_THAN"):
                        self.error("Expected '>' to close nested generic type arguments", self.current_token)
                        return None
                    self.advance()  # consume >
                    type_arg_name = self._register_generic_class_instance(targ_tok.value, nested_args)
                type_args.append(type_arg_name)
                if self.current_token and self.current_token.type == "COMMA":
                    self.advance()
                    continue
                break
            if not (self.current_token and self.current_token.type == "GREATER_THAN"):
                self.error("Expected '>' to close generic type arguments", self.current_token)
                return None
            self.advance()  # consume >
            composite_type = self._register_generic_class_instance(type_token.value, type_args)

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

        effective_type = composite_type if composite_type is not None else self._normalize_type_name(type_token)
        node = ASTNode(
            NodeTypes.VARIABLE_DECLARATION,
            identifier,
            identifier.value,
            [value],
            identifier.index,
            effective_type,
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

        arguments = self._parse_argument_list()

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
            body = self._parse_braceless_body(while_token)
        while_node = ASTNode(
            NodeTypes.WHILE_STATEMENT,
            while_token,
            "while",
            [condition, body],
            while_token.index,
        )
        # Set parent for all children
        if condition:
            condition.parent = while_node
        if body:
            body.parent = while_node
        return while_node

    def parse_for_statement(self):
        """Parse a for loop: either C-style for (init; condition; increment) or for item in collection."""
        for_token = self.consume("FOR")
        if not for_token:
            return None
        
        if not self.consume("OPEN_PAREN"):
            self.error("Expected '(' after 'for'", self.current_token or for_token)
            return None
        
        # Try to determine if this is a C-style for or for-in loop
        # We need to look ahead to see if there's an 'in' keyword
        # Check for pattern: type identifier in expression
        is_for_in = False
        if self.current_token and self.current_token.type in self.TYPE_TOKEN_NAMES:
            # Check if there's IDENTIFIER then IN
            next_token = self.peek(1)
            next_next_token = self.peek(2)
            if (next_token and next_token.type == "IDENTIFIER" and
                next_next_token and next_next_token.type == "IN"):
                is_for_in = True
        
        if is_for_in:
            # Parse for-in loop: for (type item in collection)
            # Expect a type declaration first
            if not self.current_token or self.current_token.type not in self.TYPE_TOKEN_NAMES:
                self.error("Expected type for loop variable", self.current_token or for_token)
                return None
            
            var_type = self.current_token
            self.advance()
            
            if not self.current_token or self.current_token.type != "IDENTIFIER":
                self.error("Expected loop variable name after type", self.current_token or for_token)
                return None
            
            loop_var = self.current_token
            self.advance()
            
            if not self.consume("IN"):
                self.error("Expected 'in' after loop variable", self.current_token or loop_var)
                return None
            
            collection = self.parse_expression()
            if collection is None:
                self.error("Expected collection expression after 'in'", self.current_token or for_token)
                return None
            
            if not self.consume("CLOSE_PAREN"):
                self.error("Expected ')' after for-in header", self.current_token or for_token)
                return None
            
            # Parse body
            if self.current_token and self.current_token.type == "OPEN_BRACE":
                body = self.parse_scope()
                if body is None:
                    return None
            else:
                body = self._parse_braceless_body(for_token)
            
            # Create a variable declaration node for the loop variable
            # Store type info as attributes, not as child nodes (following parse_variable_declaration pattern)
            identifier_node = ASTNode(
                NodeTypes.IDENTIFIER,
                loop_var,
                loop_var.value,
                [],
                loop_var.index,
            )
            
            # Create a variable declaration for the loop variable
            var_decl = ASTNode(
                NodeTypes.VARIABLE_DECLARATION,
                loop_var,
                loop_var.value,
                [identifier_node],  # The identifier is the child
                var_type.index,
                self._normalize_type_name(var_type),  # var_type as attribute
                False,  # is_nullable
                False,  # is_const
                None,   # return_type
                False,  # is_array
                False,  # is_ref_counted
            )
            identifier_node.parent = var_decl
            
            for_in_node = ASTNode(
                NodeTypes.FOR_IN_STATEMENT,
                for_token,
                "for_in",
                [var_decl, collection, body],
                for_token.index,
            )
            # Set parent for all children
            var_decl.parent = for_in_node
            if collection:
                collection.parent = for_in_node
            if body:
                body.parent = for_in_node
            return for_in_node
        else:
            # Parse C-style for loop: for (init; condition; increment)
            # Parse init (can be variable declaration or expression statement)
            init = None
            if self.current_token and self.current_token.type != "SEMICOLON":
                # Check if it's a variable declaration
                if self.current_token.type in self.TYPE_TOKEN_NAMES:
                    init = self.parse_variable_declaration()
                else:
                    init = self.parse_expression()
            
            if not self.consume("SEMICOLON"):
                self.error("Expected ';' after for loop init", self.current_token or for_token)
                return None
            
            # Parse condition
            condition = None
            if self.current_token and self.current_token.type != "SEMICOLON":
                condition = self.parse_expression()
            
            if not self.consume("SEMICOLON"):
                self.error("Expected ';' after for loop condition", self.current_token or for_token)
                return None
            
            # Parse increment
            increment = None
            if self.current_token and self.current_token.type != "CLOSE_PAREN":
                increment = self.parse_expression()
            
            if not self.consume("CLOSE_PAREN"):
                self.error("Expected ')' after for loop header", self.current_token or for_token)
                return None
            
            # Parse body
            if self.current_token and self.current_token.type == "OPEN_BRACE":
                body = self.parse_scope()
                if body is None:
                    return None
            else:
                body = self._parse_braceless_body(for_token)
            
            # Build children list, using empty LITERAL nodes as placeholders for omitted parts
            empty = lambda: ASTNode(NodeTypes.LITERAL, None, "empty", [], for_token.index)
            children = [
                init if init is not None else empty(),
                condition if condition is not None else empty(),
                increment if increment is not None else empty(),
                body,
            ]
            
            for_node = ASTNode(
                NodeTypes.FOR_STATEMENT,
                for_token,
                "for",
                children,
                for_token.index,
            )
            # Set parent for all children
            for child in children:
                if child:
                    child.parent = for_node
            return for_node

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
        # Handle compiler directives: directive <name>;
        if self.current_token and self.current_token.type == "DIRECTIVE":
            return self._parse_directive()
        # Unknown token recovery: emit error and advance
        if self.current_token and self.current_token.type == "UNKNOWN":
            bad_tok = self.current_token
            self.advance()
            self.error(f"Unexpected character '{bad_tok.value}'", bad_tok)
            return None
        # Handle while loops
        if self.current_token and self.current_token.type == "WHILE":
            return self.parse_while_statement()
        # Handle for loops
        if self.current_token and self.current_token.type == "FOR":
            return self.parse_for_statement()
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

        # Deferred-import mode: IDENT<TYPE_ARGS> var_name = ...  is a generic class var declaration
        # even when the class is not yet known (it comes from an imported module).
        elif (
            self.defer_undefined_identifiers
            and token_type == "IDENTIFIER"
            and next_token
            and next_token.type == "LESS_THAN"
            and self._looks_like_generic_var_decl()
        ):
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
