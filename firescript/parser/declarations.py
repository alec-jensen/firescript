import copy
import logging
from typing import Optional

from enums import NodeTypes, CompilerDirective
from .ast_node import ASTNode
from .type_system import TypeSystemMixin


class DeclarationsMixin(TypeSystemMixin):
    def _parse_directive(self) -> Optional[ASTNode]:
        """Parse a compiler directive statement: directive <name> ;"""
        dir_tok = self.current_token
        self.advance()  # consume 'directive'
        name_tok = self.consume("IDENTIFIER")
        if name_tok is None:
            self.expected_token_error("directive name after 'directive'", self.current_token or dir_tok)
            return None
        directive_value = name_tok.value
        try:
            directive_enum = CompilerDirective(directive_value)
        except Exception:
            self.invalid_expression_error(f"Unknown directive '{directive_value}'", name_tok)
            directive_enum = None
        if self.current_token and self.current_token.type == "SEMICOLON":
            self.consume("SEMICOLON")
        else:
            self.expected_token_error("semicolon after directive", self.current_token or name_tok)
        if directive_enum is not None:
            self.directives.add(directive_enum.value)
            node_name = directive_enum.value
            if directive_enum == CompilerDirective.ENABLE_SYSCALLS:
                self.user_types.add("SyscallResult")
                self.user_classes["SyscallResult"] = {"status": "int32", "data": "string"}
        else:
            node_name = directive_value
        node_index = dir_tok.index if dir_tok is not None else 0
        node = ASTNode(NodeTypes.DIRECTIVE, dir_tok, node_name, [], node_index)
        setattr(node, "source_file", self.filename)
        return node

    def _parse_generic_type_param_list(self) -> Optional[tuple[list[str], dict[str, str]]]:
        """Parse an optional '<' T [':' Constraint] (',' ...)* '>' type-parameter list.

        Assumes current_token is whatever follows the declaration name. Returns
        ([], {}) if no '<' is present (no type parameters), or None on a parse error.
        """
        type_params: list[str] = []
        type_constraints: dict[str, str] = {}
        if not (self.current_token and self.current_token.type == "LESS_THAN"):
            return type_params, type_constraints
        self.advance()  # consume <
        while True:
            if not (self.current_token and self.current_token.type == "IDENTIFIER"):
                self.expected_token_error("type parameter name", self.current_token)
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
                    if not (self.current_token and (self._is_type_token(self.current_token) or self.current_token.type == "IDENTIFIER")):
                        self.expected_token_error("constraint type or interface", self.current_token)
                        return None
                    constraint_tok = self.current_token
                    self.advance()
                    if constraint_tok.value in self.constraint_aliases:
                        constraint_parts.append(self.constraint_aliases[constraint_tok.value])
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
            self.expected_token_error("'>' to close type parameters", self.current_token)
            return None
        self.advance()  # consume >
        return type_params, type_constraints

    def _parse_param_list(
        self,
        allow_receiver: bool = False,
        allow_owned_receiver: bool = False,
        receiver_class_name: Optional[str] = None,
        allow_array: bool = True,
        local_is_static: bool = False,
    ) -> Optional[list[ASTNode]]:
        """Parse a comma-separated parameter list: [owned | & ['mut']] name ':' TypeExpr, ...

        Assumes current_token is the first token after '(' (or ')'). Consumes up
        to but not including the closing ')'. If allow_receiver, the first
        parameter may instead be a receiver: '&this', '&mut this', or (if
        allow_owned_receiver) 'owned this'. A leading 'owned' is treated as the
        ownership modifier unless immediately followed by ':' (in which case
        the parameter is literally named 'owned').
        """
        params: list[ASTNode] = []
        seen_receiver = False
        if self.current_token and self.current_token.type != "CLOSE_PAREN":
            while True:
                if (
                    allow_receiver and not seen_receiver
                    and self.current_token and self.current_token.type == "AMPERSAND"
                    and (
                        (self.peek(1) and self.peek(1).type == "IDENTIFIER" and self.peek(1).value == "this")
                        or (
                            self.peek(1) and self.peek(1).type == "MUT"
                            and self.peek(2) and self.peek(2).type == "IDENTIFIER" and self.peek(2).value == "this"
                        )
                    )
                ):
                    self.advance()  # consume '&'
                    is_mutable_borrow = False
                    if self.current_token and self.current_token.type == "MUT":
                        is_mutable_borrow = True
                        self.advance()
                    th_tok = self.consume("IDENTIFIER")
                    if local_is_static:
                        self.invalid_expression_error("Static methods cannot declare receiver parameter 'this'", th_tok)
                        return None
                    recv = ASTNode(
                        NodeTypes.PARAMETER, th_tok, "this", [], th_tok.index,
                        receiver_class_name, False, False, None, False, False,
                    )
                    setattr(recv, "is_borrowed", True)
                    setattr(recv, "is_mutable_borrow", is_mutable_borrow)
                    setattr(recv, "is_receiver", True)
                    params.append(recv)
                    seen_receiver = True
                elif (
                    allow_receiver and allow_owned_receiver and not seen_receiver
                    and self.current_token and self.current_token.type == "OWNED"
                    and self.peek(1) and self.peek(1).type == "IDENTIFIER" and self.peek(1).value == "this"
                ):
                    self.advance()  # consume 'owned'
                    th_tok = self.consume("IDENTIFIER")  # 'this'
                    recv = ASTNode(
                        NodeTypes.PARAMETER, th_tok, "this", [], th_tok.index,
                        receiver_class_name, False, False, None, False, False,
                    )
                    setattr(recv, "is_owned", True)
                    setattr(recv, "is_receiver", True)
                    params.append(recv)
                    seen_receiver = True
                else:
                    is_owned = False
                    is_borrowed = False
                    is_mutable_borrow = False
                    if self.current_token and self.current_token.type == "AMPERSAND":
                        is_borrowed = True
                        self.advance()
                        if self.current_token and self.current_token.type == "MUT":
                            is_mutable_borrow = True
                            self.advance()
                    elif (
                        self.current_token and self.current_token.type == "OWNED"
                        and not (self.peek(1) and self.peek(1).type == "COLON")
                    ):
                        is_owned = True
                        self.advance()

                    pname_tok = self.consume_name()
                    if pname_tok is None:
                        self.expected_token_error("parameter name", self.current_token)
                        return None
                    if not self.consume("COLON"):
                        self.expected_token_error("':' after parameter name", self.current_token)
                        return None
                    parsed = self._parse_type_expression()
                    if parsed is None:
                        return None
                    if parsed.is_array and not allow_array:
                        self.invalid_expression_error("Array parameters are not supported for methods", parsed.token)
                        return None
                    param_node = ASTNode(
                        NodeTypes.PARAMETER,
                        pname_tok,
                        pname_tok.value,
                        [],
                        pname_tok.index,
                        parsed.base,
                        parsed.is_nullable,
                        False,
                        None,
                        parsed.is_array,
                        parsed.is_array,
                        array_size=parsed.array_size,
                    )
                    setattr(param_node, "is_borrowed", is_borrowed)
                    setattr(param_node, "is_mutable_borrow", is_mutable_borrow)
                    if is_owned:
                        setattr(param_node, "is_owned", True)
                    params.append(param_node)
                if self.current_token and self.current_token.type == "COMMA":
                    self.advance()
                    continue
                break
        return params

    def _parse_decorator_list(self) -> Optional[list[dict]]:
        """Parse zero or more '@' IDENTIFIER '(' DecoratorArg,* ')' immediately
        preceding a top-level declaration.

        DecoratorArg := STRING_LITERAL | IDENTIFIER '=' (BOOLEAN_LITERAL | INTEGER_LITERAL)

        Decorator arguments are compile-time-only metadata (not runtime
        expressions), so they get a small purpose-built grammar rather than
        going through the full expression parser. Accepted unconditionally
        here (mirrors the directive-gated-intrinsic precedent at the top of
        this file: the parser accepts the syntax, semantic legality --
        directive present, file under std/internal/ -- is checked separately
        so a decorator appearing before its file's `directive` statement
        isn't penalized for source-order).
        """
        decorators: list[dict] = []
        while self.current_token and self.current_token.type == "AT":
            at_tok = self.current_token
            self.advance()  # consume '@'
            name_tok = self.consume("IDENTIFIER")
            if name_tok is None:
                self.expected_token_error("decorator name after '@'", self.current_token or at_tok)
                return None
            if not self.consume("OPEN_PAREN"):
                self.expected_token_error("'(' after decorator name", self.current_token or name_tok)
                return None
            positional: list[str] = []
            kwargs: dict[str, object] = {}
            if self.current_token and self.current_token.type != "CLOSE_PAREN":
                while True:
                    if (
                        self.current_token
                        and self.current_token.type == "IDENTIFIER"
                        and self.peek(1) is not None
                        and self.peek(1).type == "ASSIGN"
                    ):
                        kw_tok = self.consume("IDENTIFIER")
                        self.consume("ASSIGN")
                        if self.current_token and self.current_token.type == "BOOLEAN_LITERAL":
                            val_tok = self.consume("BOOLEAN_LITERAL")
                            kwargs[kw_tok.value] = val_tok.value == "true"
                        elif self.current_token and self.current_token.type == "INTEGER_LITERAL":
                            val_tok = self.consume("INTEGER_LITERAL")
                            kwargs[kw_tok.value] = int(val_tok.value)
                        else:
                            self.expected_token_error("boolean or integer literal after '='", self.current_token)
                            return None
                    elif self.current_token and self.current_token.type == "STRING_LITERAL":
                        str_tok = self.consume("STRING_LITERAL")
                        positional.append(self._decode_decorator_string(str_tok.value))
                    else:
                        self.expected_token_error("decorator argument", self.current_token)
                        return None
                    if self.current_token and self.current_token.type == "COMMA":
                        self.advance()
                        continue
                    break
            if not self.consume("CLOSE_PAREN"):
                self.expected_token_error("')' to close decorator arguments", self.current_token)
                return None
            decorators.append({"name": name_tok.value, "positional": positional, "kwargs": kwargs, "token": at_tok})
        return decorators

    @staticmethod
    def _decode_decorator_string(raw: str) -> str:
        """Strip the surrounding quotes from a STRING_LITERAL token's raw text
        (decorator argument strings are plain identifiers/names -- no escape
        processing needed)."""
        if raw.startswith('"') and raw.endswith('"'):
            return raw[1:-1]
        return raw

    def _validate_builtin_method_decorators(self, func_node: ASTNode, decorators: list[dict]) -> None:
        """Enforce that @builtin_method decorators only appear in files under
        std/internal/ -- the only directory auto-linked into every compiled
        program without a user import. The directive-presence requirement
        (`directive enable_builtin_methods;`) is checked later, during the
        registry pre-scan (see std/builtin_methods.py), since it must be
        checked once per file after the whole file has been parsed, not
        token-by-token here."""
        for dec in decorators:
            if dec["name"] != "builtin_method":
                continue
            normalized = (self.filename or "").replace("\\", "/")
            if "std/internal/" not in normalized:
                self.invalid_expression_error(
                    "@builtin_method may only be used on functions in firescript/std/internal/",
                    dec["token"],
                )

    def _validate_owns_elements_decorator(self, class_node: ASTNode, decorators: list[dict]) -> None:
        """Enforce @owns_elements(array_field, length_field[, state_field])'s
        contract: a compiler-internal hint (stdlib use only, e.g.
        std.collections.Vec<T>/HashMap<K,V>) telling the generated
        destructor that `array_field` is an unsized array field holding up
        to `length_field` live elements, so owned elements must be dropped
        before the buffer itself is freed (see
        flir/lowering.py::ensure_destructor). A class may carry more than
        one @owns_elements decorator (HashMap<K,V> needs one for `keys` and
        one for `values`). The optional 3rd argument names a parallel
        `uint8[]` occupancy field (HashMap-style open addressing, where the
        live slots are scattered across the whole capacity rather than a
        contiguous `0..length` prefix like Vec<T>'s): the destructor only
        frees `array_field[i]` when `state_field[i] == 1` (the hardcoded
        "occupied" sentinel these classes use). All fields must already be
        declared on this exact class (not inherited -- generic containers
        like Vec<T>/HashMap<K,V> don't use inheritance) with the expected
        shapes."""
        for dec in decorators:
            if dec["name"] != "owns_elements":
                continue
            normalized = (self.filename or "").replace("\\", "/")
            if "std/" not in normalized:
                self.invalid_expression_error(
                    "@owns_elements may only be used on classes in firescript/std/",
                    dec["token"],
                )
                continue
            positional = dec["positional"]
            if len(positional) not in (2, 3):
                self.invalid_expression_error(
                    "@owns_elements requires 2 or 3 positional arguments (array field name, length field name[, state field name])",
                    dec["token"],
                )
                continue
            array_field_name, length_field_name = positional[0], positional[1]
            fields_by_name = {
                c.name: c for c in class_node.children if c.node_type == NodeTypes.CLASS_FIELD
            }
            array_field = fields_by_name.get(array_field_name)
            if array_field is None or not array_field.is_array or array_field.array_size is not None:
                self.invalid_expression_error(
                    f"@owns_elements: '{array_field_name}' must be an unsized array field ('{array_field_name}: T[]') declared on '{class_node.name}'",
                    dec["token"],
                )
            length_field = fields_by_name.get(length_field_name)
            if length_field is None or length_field.is_array or length_field.var_type != "int32":
                self.invalid_expression_error(
                    f"@owns_elements: '{length_field_name}' must be an int32 field declared on '{class_node.name}'",
                    dec["token"],
                )
            if len(positional) == 3:
                state_field_name = positional[2]
                state_field = fields_by_name.get(state_field_name)
                if state_field is None or not state_field.is_array or state_field.array_size is not None or state_field.var_type != "uint8":
                    self.invalid_expression_error(
                        f"@owns_elements: '{state_field_name}' must be an unsized 'uint8[]' field declared on '{class_node.name}'",
                        dec["token"],
                    )

    def _parse_function_definition(self):
        """Parse: 'fn' name ['<' TypeParamList '>'] '(' ParamList ')' '->' TypeExpr '{' body '}'"""
        fn_tok = self.consume("FN")
        if fn_tok is None:
            return None

        name_token = self.consume("IDENTIFIER")
        if name_token is None:
            self.expected_token_error("function name after 'fn'", self.current_token)
            return None

        type_param_result = self._parse_generic_type_param_list()
        if type_param_result is None:
            return None
        type_params, type_constraints = type_param_result

        if not self.consume("OPEN_PAREN"):
            self.expected_token_error("'(' after function name", self.current_token)
            return None

        # Set current type parameters for parsing the parameter list, return type, and body
        prev_type_params = self._current_type_params
        self._current_type_params = type_params.copy()

        params = self._parse_param_list(allow_array=True)
        if params is None:
            self._current_type_params = prev_type_params
            return None

        if not self.consume("CLOSE_PAREN"):
            self.expected_token_error("')' after parameters", self.current_token)
            self._current_type_params = prev_type_params
            return None

        if not self.consume("ARROW"):
            self.expected_token_error("'->' return type after ')'", self.current_token)
            self._current_type_params = prev_type_params
            return None
        ret_parsed = self._parse_type_expression()
        if ret_parsed is None:
            self._current_type_params = prev_type_params
            return None
        if self._validate_return_type(ret_parsed):
            self._current_type_params = prev_type_params
            return None
        # Validate an IDENTIFIER-based return type is a declared type parameter or user class
        if (
            ret_parsed.token
            and ret_parsed.token.type == "IDENTIFIER"
            and ret_parsed.token.value not in self.TYPE_TOKEN_NAMES
            and ret_parsed.token.value not in type_params
            and ret_parsed.token.value not in self.user_types
            and not self.defer_undefined_identifiers
        ):
            self.invalid_expression_error(
                f"Return type '{ret_parsed.token.value}' is not a declared type parameter", ret_parsed.token
            )
            self._current_type_params = prev_type_params
            return None
        return_type_value = ret_parsed.base + ("[]" if ret_parsed.is_array else "")
        if ret_parsed.is_nullable and not ret_parsed.is_array:
            return_type_value += "?"
        ret_is_array = ret_parsed.is_array

        if not (self.current_token and self.current_token.type == "OPEN_BRACE"):
            self.expected_token_error("'{' to start function body", self.current_token)
            self._current_type_params = prev_type_params
            return None
        body_node = self.parse_scope()
        if body_node is None:
            self._current_type_params = prev_type_params
            return None

        is_generator = ret_parsed.base.startswith("generator<")
        node_type = NodeTypes.GENERATOR_DEFINITION if is_generator else NodeTypes.FUNCTION_DEFINITION
        func_node = ASTNode(
            node_type,
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
        if is_generator:
            func_node.yield_type = ret_parsed.base[len("generator<"):-1]

        # Restore previous type parameters
        self._current_type_params = prev_type_params

        self.user_functions[name_token.value] = return_type_value
        if type_params:
            self.generic_functions[name_token.value] = type_params
            self.generic_constraints[name_token.value] = type_constraints
        return func_node

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
                if getattr(self, "_pending_export", False):
                    self.invalid_expression_error("export can only be applied to top-level declarations", self.current_token)
                    self._pending_export = False
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
                if getattr(self, "_pending_export", False):
                    self.invalid_expression_error("export can only be applied to top-level declarations", self.current_token)
                    self._pending_export = False
                directive_node = self._parse_directive()
                if directive_node is not None:
                    directive_node.parent = self.ast
                    self.ast.children.append(directive_node)
                continue
            if self.current_token.type == "EXPORT":
                self.advance()
                # A trailing comment (e.g. a //~ diagnostic annotation) right
                # after 'export' must not mask the "nothing follows" case --
                # skip it before checking for EOF, same as the top-level
                # loop does before dispatching on token type.
                while self.current_token and self.current_token.type in (
                    "SINGLE_LINE_COMMENT",
                    "MULTI_LINE_COMMENT_START",
                ):
                    self._skip_comment()
                if not self.current_token:
                    self.expected_token_error("declaration after 'export'", self.current_token)
                    self._pending_export = False
                    continue
                if self.current_token.type == "CONSTRAINT":
                    self.invalid_expression_error("Constraint exports are not supported yet", self.current_token)
                    self._pending_export = False
                    continue
                self._pending_export = True
                continue
            # Class definition (with optional 'copyable' annotation)
            if self.current_token.type == "CLASS" or self.current_token.type == "COPYABLE":
                cls = self._parse_class_definition()
                if cls:
                    if getattr(self, "_pending_export", False):
                        setattr(cls, "is_exported", True)
                        self._pending_export = False
                    cls.parent = self.ast
                    self.ast.children.append(cls)
                continue
            # Enum definition
            if self.current_token.type == "ENUM":
                enum_node = self._parse_enum_definition()
                if enum_node:
                    if getattr(self, "_pending_export", False):
                        setattr(enum_node, "is_exported", True)
                        self._pending_export = False
                    enum_node.parent = self.ast
                    self.ast.children.append(enum_node)
                continue
            # Constraint declaration
            if self.current_token.type == "CONSTRAINT":
                if getattr(self, "_pending_export", False):
                    self.invalid_expression_error("Constraint exports are not supported yet", self.current_token)
                    self._pending_export = False
                self._parse_constraint_declaration()
                # Optional semicolon
                if self.current_token and self.current_token.type == "SEMICOLON":
                    self.consume("SEMICOLON")
                continue
            # Decorators: '@' name(...) immediately preceding a function
            # definition, or (for compiler-internal stdlib use only --
            # @owns_elements) a class definition.
            decorators = None
            if self.current_token.type == "AT":
                decorators = self._parse_decorator_list()
                if decorators is None:
                    continue
                # A trailing comment (e.g. a //~ diagnostic annotation) right
                # after the decorator's ')' must not mask the following
                # 'fn'/'class' -- skip it before checking, same as the
                # top-level loop does before dispatching on token type.
                while self.current_token and self.current_token.type in (
                    "SINGLE_LINE_COMMENT",
                    "MULTI_LINE_COMMENT_START",
                ):
                    self._skip_comment()
                if not (
                    self.current_token
                    and self.current_token.type in ("FN", "CLASS", "COPYABLE")
                ):
                    self.invalid_expression_error(
                        "Decorators may only precede a function or class definition", self.current_token
                    )
                    continue
            # Function definition: 'fn' name(...) -> ReturnType { ... }
            stmt = None
            if self.current_token.type == "FN":
                stmt = self._parse_function_definition()
                if stmt is not None and decorators:
                    setattr(stmt, "decorators", decorators)
                    self._validate_builtin_method_decorators(stmt, decorators)
            elif decorators and self.current_token.type in ("CLASS", "COPYABLE"):
                stmt = self._parse_class_definition()
                if stmt is not None:
                    setattr(stmt, "decorators", decorators)
                    self._validate_owns_elements_decorator(stmt, decorators)
                    if getattr(self, "_pending_export", False):
                        setattr(stmt, "is_exported", True)
                        self._pending_export = False
                    stmt.parent = self.ast
                    self.ast.children.append(stmt)
                continue
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

            if isinstance(stmt, ASTNode):
                if getattr(self, "_pending_export", False):
                    if stmt.node_type in (NodeTypes.FUNCTION_DEFINITION, NodeTypes.GENERATOR_DEFINITION, NodeTypes.VARIABLE_DECLARATION):
                        setattr(stmt, "is_exported", True)
                    else:
                        self.invalid_expression_error("export can only be applied to top-level declarations", stmt.token)
                    self._pending_export = False
                stmt.parent = self.ast
                self.ast.children.append(stmt)

            # Consume semicolon after simple statements (not blocks, loops, or function defs)
            if isinstance(stmt, ASTNode):
                if not (
                    stmt.node_type
                    in (
                        NodeTypes.IF_STATEMENT,
                        NodeTypes.WHILE_STATEMENT,
                        NodeTypes.FOR_STATEMENT,
                        NodeTypes.FOR_IN_STATEMENT,
                        NodeTypes.SCOPE,
                        NodeTypes.FUNCTION_DEFINITION,
                        NodeTypes.GENERATOR_DEFINITION,
                        NodeTypes.MATCH_EXPRESSION,
                    )
                ):
                    if self.current_token and self.current_token.type == "SEMICOLON":
                        self.consume("SEMICOLON")
                    else:
                        self.expected_token_error("semicolon after statement",
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

    def _parse_optional_alias(self) -> Optional[str]:
        """Parse an optional 'as <identifier>' alias clause.

        Returns the alias string if present, None if no 'as' keyword follows.
        Logs an error and returns None if 'as' is found but no identifier follows.
        """
        if not (self.current_token and self.current_token.type == "AS"):
            return None
        self.advance()  # consume 'as'
        al = self.consume("IDENTIFIER")
        if al is None:
            self.expected_token_error("alias name after 'as'", self.current_token)
            return None
        return al.value

    def _parse_import_symbol_group(self, symbols: list) -> bool:
        """Parse a '{sym [as x], sym2 [as y]}' import symbol group.

        Assumes current_token is '{' on entry. Appends parsed entries to symbols.
        Returns True on success, False if a parse error was encountered.
        """
        self.advance()  # consume '{'
        while self.current_token and self.current_token.type != "CLOSE_BRACE":
            if not (self.current_token and self.current_token.type == "IDENTIFIER"):
                self.expected_token_error("identifier in import symbol list", self.current_token)
                return False
            sname_tok = self.consume("IDENTIFIER")
            if sname_tok is None:
                self.expected_token_error("identifier in import symbol list", self.current_token)
                return False
            salias = self._parse_optional_alias()
            symbols.append({"name": sname_tok.value, "alias": salias})
            if self.current_token and self.current_token.type == "COMMA":
                self.advance()
                continue
            break
        if not self.consume("CLOSE_BRACE"):
            self.expected_token_error("'}' to close import symbol list", self.current_token)
            return False
        return True

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
                self.expected_token_error("package name after '@'", self.current_token or at_tok)
                return None
            idtok = self.consume("IDENTIFIER")
            if idtok is None:
                self.expected_token_error("identifier after '@'", self.current_token or at_tok)
                return None
            segs.append(idtok.value)
            # Accept sequence of '/' IDENTIFIER (slash tokenized as DIVIDE)
            while self.current_token and self.current_token.type == "DIVIDE":
                self.advance()
                if not (self.current_token and self.current_token.type == "IDENTIFIER"):
                    self.expected_token_error("identifier after '/' in external package name", self.current_token)
                    break
                nxtok = self.consume("IDENTIFIER")
                if nxtok is None:
                    self.expected_token_error("identifier after '/' in external package name", self.current_token)
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
                        self.invalid_expression_error(f"Too many iterations parsing dotted path. Current token: {self.current_token}, module_segs: {module_segs}", self.current_token)
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
                        # Only continue adding to module path if another DOT follows
                        # (same logic as regular imports: last segment before non-DOT is the symbol)
                        if nxt2 and nxt2.type == "DOT":
                            self.advance()  # consume '.'
                            id_tok = self.current_token
                            self.advance()  # consume identifier
                            module_segs.append(id_tok.value)
                            # Continue to check if there's more path
                        else:
                            # No DOT after next identifier, so it is a symbol — stop here
                            break
                    else:
                        # Unknown token after DOT, stop
                        break
                
                module_path = ".".join(module_segs)
                kind = None  # Will be determined later (module, symbols, wildcard)
                
                # Now parse any symbol syntax: .{symbols}, .*, or .symbol
                if self.current_token and self.current_token.type == "DOT":
                    self.advance()
                    if self.current_token and self.current_token.type == "OPEN_BRACE":
                        if not self._parse_import_symbol_group(symbols):
                            return None
                        kind = "symbols"
                    elif self.current_token and self.current_token.type == "MULTIPLY":
                        # Wildcard import
                        self.advance()
                        kind = "wildcard"
                    elif self.current_token and self.current_token.type == "IDENTIFIER":
                        sname_tok = self.consume("IDENTIFIER")
                        if sname_tok is None:
                            self.expected_token_error("symbol name after '.' in import", self.current_token)
                            return None
                        symbols.append({"name": sname_tok.value, "alias": self._parse_optional_alias(), "index": sname_tok.index})
                        kind = "symbols"
                    else:
                        self.expected_token_error("symbol name, '*', or '{' after '.' in import", self.current_token)
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
                self.expected_token_error("module name after 'import'", self.current_token or start_tok)
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
                    if not self._parse_import_symbol_group(symbols):
                        return None
                    kind = "symbols"
                elif self.current_token and self.current_token.type == "MULTIPLY":
                    # Wildcard import
                    self.advance()
                    kind = "wildcard"
                elif self.current_token and self.current_token.type == "IDENTIFIER":
                    sname_tok = self.consume("IDENTIFIER")
                    if sname_tok is None:
                        self.expected_token_error("symbol name after '.' in import", self.current_token)
                        return None
                    symbols.append({"name": sname_tok.value, "alias": self._parse_optional_alias(), "index": sname_tok.index})
                    kind = "symbols"
                else:
                    self.expected_token_error("symbol name, '*', or '{' after '.' in import", self.current_token)
                    return None
            else:
                # Module import with optional alias: import module.path [as Alias]
                alias = self._parse_optional_alias()
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
            self.invalid_expression_error("External packages are not supported", start_tok)

        return node

    def _parse_constraint_declaration(self):
        """Parse a constraint declaration: constraint Name = type1 | type2 | ...; """
        constraint_tok = self.consume("CONSTRAINT")
        if constraint_tok is None:
            return None
        
        name_tok = self.consume("IDENTIFIER")
        if name_tok is None:
            self.expected_token_error("constraint name after 'constraint'", self.current_token)
            return None
        
        if not self.consume("ASSIGN"):
            self.expected_token_error("'=' after constraint name", self.current_token)
            return None
        
        # Parse the type union: type1 | type2 | type3 | ...
        type_parts = []
        while True:
            # Accept IDENTIFIER (for interface names or aliases) or type tokens (int32, float64, etc.)
            if not (self.current_token and (self.current_token.type == "IDENTIFIER" or self._is_type_token(self.current_token))):
                self.expected_token_error("type name in constraint definition", self.current_token)
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
        """Parse a class definition: [copyable] class Name[<T, U>] [from Base] { <type> <field>; ... }"""
        # Check for optional 'copyable' annotation
        is_copyable = False
        if self.current_token and self.current_token.type == "COPYABLE":
            is_copyable = True
            self.advance()
        
        class_tok = self.consume("CLASS")
        if class_tok is None:
            return None
        name_tok = self.consume("IDENTIFIER")
        if name_tok is None:
            self.expected_token_error("class name after 'class'", self.current_token)
            return None

        # Make the class's own name resolvable as a type immediately, so
        # self-referential uses inside the body (e.g. a static factory method
        # returning the enclosing class) parse correctly before the class is
        # fully registered at the end of this method.
        self.user_types.add(name_tok.value)

        # Parse optional generic type parameters: <T, U, ...>
        class_type_params: list[str] = []
        prev_class_type_params = self._current_type_params
        prev_generic_class_name = self._current_generic_class_name
        if self.current_token and self.current_token.type == "LESS_THAN":
            self.advance()  # consume <
            while True:
                if not (self.current_token and self.current_token.type == "IDENTIFIER"):
                    self.expected_token_error("type parameter name", self.current_token)
                    return None
                tparam_tok = self.consume("IDENTIFIER")
                if tparam_tok is None:
                    return None
                # Skip optional 'nullable' constraint annotation on type parameters: T?
                if self.current_token and self.current_token.type == "QUESTION":
                    self.advance()
                class_type_params.append(tparam_tok.value)
                if self.current_token and self.current_token.type == "COMMA":
                    self.advance()
                    continue
                break
            if not (self.current_token and self.current_token.type == "GREATER_THAN"):
                self.expected_token_error("'>' to close generic type parameters", self.current_token)
                return None
            self.advance()  # consume >
            # Make type params visible while parsing the class body
            self._current_type_params = class_type_params.copy()
            self._current_generic_class_name = name_tok.value

        base_class: Optional[str] = None
        if self.current_token and self.current_token.type == "FROM":
            self.advance()  # consume 'from'
            base_tok = self.consume("IDENTIFIER")
            if base_tok is None:
                self.expected_token_error("base class name after 'from'", self.current_token)
                return None
            base_class = base_tok.value
            if base_class == name_tok.value:
                self.invalid_expression_error("A class cannot inherit from itself", base_tok)

        if not self.consume("OPEN_BRACE"):
            self.expected_token_error("'{' to start class body", self.current_token)
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
            local_is_static = False
            if self.current_token and self.current_token.type == "STATIC":
                local_is_static = True
                self.advance()

            # Method or constructor: 'fn' name(...) ['->' TypeExpr] { ... }
            if self.current_token and self.current_token.type == "FN":
                self.advance()  # consume 'fn'
                method_name_tok = self.consume("IDENTIFIER")
                if method_name_tok is None:
                    self.expected_token_error("method name after 'fn'", self.current_token)
                    while self.current_token and self.current_token.type not in ("SEMICOLON", "CLOSE_BRACE"):
                        self.advance()
                    if self.current_token and self.current_token.type == "SEMICOLON":
                        self.advance()
                    continue

                is_constructor = method_name_tok.value == name_tok.value
                if is_constructor and local_is_static:
                    self.invalid_expression_error("Constructors cannot be declared static", method_name_tok)

                if not self.consume("OPEN_PAREN"):
                    self.expected_token_error("'(' after method name", self.current_token)
                    return None

                params = self._parse_param_list(
                    allow_receiver=True,
                    allow_owned_receiver=is_constructor,
                    receiver_class_name=self._normalize_type_name(name_tok),
                    allow_array=False,
                    local_is_static=local_is_static,
                )
                if params is None:
                    return None

                if not self.consume("CLOSE_PAREN"):
                    self.expected_token_error("')' after method parameters", self.current_token)
                    return None

                return_type_value: Optional[str] = name_tok.value if is_constructor else None
                if self.current_token and self.current_token.type == "ARROW":
                    arrow_tok = self.current_token
                    self.advance()
                    ret_parsed = self._parse_type_expression()
                    if ret_parsed is None:
                        return None
                    if is_constructor:
                        self.invalid_expression_error("Constructors cannot declare a return type", arrow_tok)
                    elif self._validate_return_type(ret_parsed):
                        return None
                    else:
                        return_type_value = ret_parsed.base + ("[]" if ret_parsed.is_array else "")
                        if ret_parsed.is_nullable and not ret_parsed.is_array:
                            return_type_value += "?"
                elif not is_constructor:
                    self.expected_token_error("'->' return type after ')'", self.current_token)
                    return None

                if not (self.current_token and self.current_token.type == "OPEN_BRACE"):
                    self.expected_token_error("'{' to start method body", self.current_token)
                    return None

                self._class_context_stack.append((name_tok.value, bool(is_constructor), base_class))
                try:
                    body_node = self.parse_scope()
                finally:
                    self._class_context_stack.pop()
                if body_node is None:
                    return None

                param_nodes = params
                if not is_constructor and not local_is_static and not (params and params[0].name == "this"):
                    # Inject synthetic receiver named 'this' if not explicitly provided
                    self_param = ASTNode(
                        NodeTypes.PARAMETER,
                        method_name_tok,
                        "this",
                        [],
                        method_name_tok.index,
                        self._normalize_type_name(name_tok),
                        False,
                        False,
                        None,
                        False,
                        False,
                    )
                    setattr(self_param, "is_receiver", True)
                    # Default an omitted receiver on an Owned class to
                    # borrowed (read-only), matching every explicit-receiver
                    # form except plain `owned this` -- without this,
                    # downstream ownership/drop logic saw an unmarked
                    # (implicitly owned) parameter and auto-dropped it at the
                    # end of the method body, silently destroying the
                    # receiver on every call to any method that omits
                    # `&this`/`&mut this` on a class whose destructor does
                    # real work (e.g. Option<T>.isSome(), Vec<T>.length()).
                    # Copyable classes are exempted: they're stack values
                    # with no destructor to worry about (dropping one is
                    # already a no-op, see flir/lowering.py::lower_drop's
                    # is_copyable_class_str early return), and marking them
                    # borrowed would wrongly trip `_validate_borrow`'s
                    # "borrowing is only allowed for Owned types" check.
                    if not is_copyable:
                        setattr(self_param, "is_borrowed", True)
                    param_nodes = [self_param, *params]

                method_node = ASTNode(
                    NodeTypes.CLASS_METHOD_DEFINITION,
                    method_name_tok,
                    method_name_tok.value,
                    [*param_nodes, body_node],
                    method_name_tok.index,
                    None,
                    False,
                    False,
                    return_type_value,
                    False,
                    False,
                )
                setattr(method_node, "class_name", name_tok.value)
                setattr(method_node, "is_constructor", is_constructor)
                setattr(method_node, "is_static", local_is_static)
                methods.append(method_node)
                continue

            if local_is_static:
                # 'static' was consumed but nothing that can follow it (only 'fn') was found.
                self.expected_token_error("'fn' after 'static'", self.current_token)
                while self.current_token and self.current_token.type not in ("SEMICOLON", "CLOSE_BRACE"):
                    self.advance()
                if self.current_token and self.current_token.type == "SEMICOLON":
                    self.advance()
                continue

            # Field declaration: name ':' TypeExpr ';'
            field_name_tok = self.consume_name()
            if field_name_tok is None:
                self.expected_token_error("field name or 'fn' in class body", self.current_token)
                while self.current_token and self.current_token.type not in ("SEMICOLON", "CLOSE_BRACE"):
                    self.advance()
                if self.current_token and self.current_token.type == "SEMICOLON":
                    self.advance()
                continue
            if not self.consume("COLON"):
                self.expected_token_error("':' after field name", self.current_token)
                while self.current_token and self.current_token.type not in ("SEMICOLON", "CLOSE_BRACE"):
                    self.advance()
                if self.current_token and self.current_token.type == "SEMICOLON":
                    self.advance()
                continue
            field_parsed = self._parse_type_expression()
            if field_parsed is None:
                while self.current_token and self.current_token.type not in ("SEMICOLON", "CLOSE_BRACE"):
                    self.advance()
                if self.current_token and self.current_token.type == "SEMICOLON":
                    self.advance()
                continue
            if field_parsed.is_array and field_parsed.array_size is not None:
                self.invalid_expression_error("Fixed-size array fields are not supported for classes", field_parsed.token)
                while self.current_token and self.current_token.type not in ("SEMICOLON", "CLOSE_BRACE"):
                    self.advance()
                if self.current_token and self.current_token.type == "SEMICOLON":
                    self.advance()
                continue
            if not self.consume("SEMICOLON"):
                self.expected_token_error("';' after field declaration", self.current_token)
                while self.current_token and self.current_token.type not in ("SEMICOLON", "CLOSE_BRACE"):
                    self.advance()
                if self.current_token and self.current_token.type == "SEMICOLON":
                    self.advance()
            field_node = ASTNode(
                NodeTypes.CLASS_FIELD, field_name_tok, field_name_tok.value, [], field_name_tok.index,
                var_type=field_parsed.base, is_nullable=field_parsed.is_nullable,
                is_array=field_parsed.is_array, array_size=field_parsed.array_size,
            )
            fields.append(field_node)
            field_types[field_name_tok.value] = field_parsed.base + ("[]" if field_parsed.is_array else "")
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
                        self.invalid_expression_error(
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
            self.user_methods[name_tok.value][m.name] = {
                "return": m.return_type,
                "params": params_types,
                "is_static": bool(getattr(m, "is_static", False)),
            }

        cls_node = ASTNode(NodeTypes.CLASS_DEFINITION, name_tok, name_tok.value, [*all_fields, *all_methods], name_tok.index)
        setattr(cls_node, "base_class", base_class)
        setattr(cls_node, "is_copyable", is_copyable)
        setattr(cls_node, "type_params", class_type_params)

        # Restore previous type parameter context
        self._current_type_params = prev_class_type_params
        self._current_generic_class_name = prev_generic_class_name

        if class_type_params:
            # Generic class: store as a template, do NOT register as a concrete type yet.
            # Concrete monomorphized instances will be registered on-demand when the type is
            # first used (e.g. in a variable declaration or constructor call).
            self.generic_class_templates[name_tok.value] = cls_node
            self.generic_class_params[name_tok.value] = class_type_params
            # Remove any spurious registration that may have happened inside the body parse above
            self.user_types.discard(name_tok.value)
            self.user_classes.pop(name_tok.value, None)
            self.user_class_bases.pop(name_tok.value, None)
            self.user_methods.pop(name_tok.value, None)
            # The template's own Owned/Copyable category is fixed at
            # declaration (independent of the eventual type arguments), and
            # is needed immediately for borrow validation on `&this`/`&mut
            # this` receivers inside the class's own body -- those are typed
            # with the bare template name, not a concrete "Name<T>" instance
            # (which only gets registered on demand at first external use,
            # via _register_generic_class_instance in base.py). Does not
            # reintroduce the bare name as a usable standalone *type*
            # (user_types/user_classes above stay cleared); this only feeds
            # is_owned()/is_copyable() in utils/type_utils.py.
            from utils.type_utils import register_class
            register_class(name_tok.value, is_copyable)
        else:
            # Regular (non-generic) class
            # Register class with type_utils
            from utils.type_utils import register_class
            register_class(name_tok.value, is_copyable)

        return cls_node

    def _parse_enum_definition(self):
        """Parse an enum definition: enum Name { Variant1, Variant2(name: Type, ...), ... }

        Variant payload fields are named (`name: Type`, same declaration order
        as class fields / function parameters) so match patterns can bind by
        field name. Construction (`EnumName.Variant(args...)`) remains
        positional, in declaration order.
        """
        enum_tok = self.consume("ENUM")
        if enum_tok is None:
            return None
        name_tok = self.consume("IDENTIFIER")
        if name_tok is None:
            self.expected_token_error("enum name after 'enum'", self.current_token)
            return None

        if self.current_token and self.current_token.type == "LESS_THAN":
            self.invalid_expression_error("Generic enums are not yet supported", self.current_token)
            # Recover by skipping ahead to the enum body.
            while self.current_token and self.current_token.type != "OPEN_BRACE":
                self.advance()

        if not self.consume("OPEN_BRACE"):
            self.expected_token_error("'{' to start enum body", self.current_token)
            return None

        variants: list[ASTNode] = []
        variant_payloads: dict[str, list[tuple[str, str]]] = {}
        while self.current_token and self.current_token.type != "CLOSE_BRACE":
            if self.current_token.type in (
                "SINGLE_LINE_COMMENT",
                "MULTI_LINE_COMMENT_START",
            ):
                self._skip_comment()
                continue
            if self.current_token.type == "COMMA":
                self.advance()
                continue
            variant_tok = self.consume("IDENTIFIER")
            if variant_tok is None:
                self.expected_token_error("variant name in enum body", self.current_token)
                while self.current_token and self.current_token.type not in ("COMMA", "CLOSE_BRACE"):
                    self.advance()
                continue
            if variant_tok.value in variant_payloads:
                self.invalid_expression_error(
                    f"Duplicate variant '{variant_tok.value}' in enum '{name_tok.value}'", variant_tok
                )

            payload_fields: list[tuple[str, str]] = []
            if self.current_token and self.current_token.type == "OPEN_PAREN":
                self.advance()  # consume '('
                if self.current_token and self.current_token.type != "CLOSE_PAREN":
                    while True:
                        field_tok = self.consume("IDENTIFIER")
                        if field_tok is None:
                            self.expected_token_error("payload field name in enum variant", self.current_token)
                            break
                        if not self.consume("COLON"):
                            self.expected_token_error("':' after payload field name", self.current_token)
                            break
                        field_parsed = self._parse_type_expression()
                        if field_parsed is None:
                            break
                        if field_parsed.is_array:
                            self.invalid_expression_error("Array payload fields are not supported for enum variants", field_parsed.token)
                            break
                        field_type = field_parsed.base
                        if any(fname == field_tok.value for fname, _ in payload_fields):
                            self.invalid_expression_error(
                                f"Duplicate payload field '{field_tok.value}' in variant "
                                f"'{name_tok.value}.{variant_tok.value}'",
                                field_tok,
                            )
                        payload_fields.append((field_tok.value, field_type))
                        if self.current_token and self.current_token.type == "COMMA":
                            self.advance()
                            continue
                        break
                if not self.consume("CLOSE_PAREN"):
                    self.expected_token_error("')' to close enum variant payload", self.current_token)

            variant_node = ASTNode(NodeTypes.ENUM_VARIANT, variant_tok, variant_tok.value, [], variant_tok.index)
            setattr(variant_node, "payload_fields", payload_fields)
            variants.append(variant_node)
            variant_payloads[variant_tok.value] = payload_fields

            if self.current_token and self.current_token.type == "COMMA":
                self.advance()
            elif self.current_token and self.current_token.type != "CLOSE_BRACE":
                self.expected_token_error("',' or '}' after enum variant", self.current_token)

        if not self.consume("CLOSE_BRACE"):
            self.expected_token_error("'}' to close enum body", self.current_token)
            return None

        if not variant_payloads:
            self.invalid_expression_error(f"Enum '{name_tok.value}' must declare at least one variant", name_tok)

        self.user_types.add(name_tok.value)
        self.user_enums[name_tok.value] = variant_payloads
        # Enums are always heap-allocated tagged unions (see
        # ast_to_fir.py's _convert_enum, category="owned" unconditionally
        # -- there is no "copyable enum" variant) and so always need the
        # same automatic drop-insertion tracking classes get; without
        # this, preprocessor.py's is_owned() never recognized any enum
        # type, silently skipping every enum-typed local/param for
        # automatic dropping (FIRV-O3).
        from utils.type_utils import register_class

        register_class(name_tok.value, is_copyable=False)

        enum_node = ASTNode(NodeTypes.ENUM_DEFINITION, name_tok, name_tok.value, variants, name_tok.index)
        return enum_node
