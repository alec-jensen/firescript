import logging
from typing import Optional

from lexer import Token
from utils.file_utils import get_line_and_coumn_from_index, get_line
from enums import NodeTypes, CompilerDirective
from errors import (
    CompileTimeError,
    ParserError,
    UnexpectedTokenError,
    TypeError,
    UndefinedIdentifierError,
    ExpectedTokenError,
    MissingIdentifierError,
    InvalidExpressionError,
    InvalidArrayAccessError,
    InvalidFieldAccessError,
    InvalidTypeError,
    FieldNotFoundError,
    MethodNotFoundError,
    ConstructorNotFoundError,
    InvalidOperatorError,
    ControlFlowError,
    InvalidSuperError,
)
from .ast_node import ASTNode


class ParserBase:
    # Recognized type token names emitted by the lexer
    TYPE_TOKEN_NAMES = {
        "INT8", "INT16", "INT32", "INT64",
        "UINT8", "UINT16", "UINT32", "UINT64",
        "FLOAT32", "FLOAT64", "FLOAT128",
        "BOOL", "STRING", "VOID",
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

    # Directive-gated intrinsics: available only when the corresponding directive is active.
    # The parser accepts calls to these names without erroring; the code generator enforces
    # the directive requirement at emit time.
    builtin_functions: dict[str, str] = {
        "stdout": "void",          # requires directive enable_lowlevel_stdout
        "drop": "void",            # requires directive enable_drops
        "process_argc": "int32",   # requires directive enable_process_args
        "process_argv_at": "string",  # requires directive enable_process_args
        "str_length": "int32",     # requires directive enable_process_args
        "str_char_at": "string",   # requires directive enable_process_args
        "str_index_of": "int32",   # requires directive enable_process_args
        "str_slice": "string",     # requires directive enable_process_args
        "syscall_open": "SyscallResult",   # requires directive enable_syscalls
        "syscall_read": "SyscallResult",   # requires directive enable_syscalls
        "syscall_write": "SyscallResult",  # requires directive enable_syscalls
        "syscall_close": "SyscallResult",  # requires directive enable_syscalls
        "syscall_remove": "SyscallResult",  # requires directive enable_syscalls
        "syscall_rename": "SyscallResult",  # requires directive enable_syscalls
        "syscall_move": "SyscallResult",    # requires directive enable_syscalls
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
        self._token_idx: int = 0
        self.current_token: Optional[Token] = self.tokens[0] if tokens else None
        self.ast = ASTNode(NodeTypes.ROOT, None, "program", [], 0)
        self.file = file
        self.filename = filename
        self.errors: list[CompileTimeError] = []
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
        # Track type parameters in current scope (for parsing inside generic functions/classes)
        self._current_type_params: list[str] = []
        # Generic class tracking: template name -> AST node / type param list
        self.generic_class_templates: dict[str, ASTNode] = {}
        self.generic_class_params: dict[str, list[str]] = {}
        
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
        if tok.type == "IDENTIFIER":
            return (
                tok.value in self.user_types
                or tok.value in self._current_type_params
                or tok.value in self.generic_class_templates
            )
        return False

    def _normalize_type_name(self, tok: Token) -> str:
        """Normalize token.value to canonical firescript type name (handles legacy aliases)."""
        val = tok.value
        return self.LEGACY_TYPE_ALIASES.get(val, val)

    def advance(self):
        """Advance the current token to the next non-whitespace token."""
        if self.current_token is None:
            return

        new_index = self._token_idx + 1
        while (
            new_index < len(self.tokens)
            and self.tokens[new_index].type == "IDENTIFIER"
            and self.tokens[new_index].value.strip() == ""
        ):
            new_index += 1
        self._token_idx = new_index
        self.current_token = (
            self.tokens[new_index] if new_index < len(self.tokens) else None
        )

    def peek(self, offset: int = 1) -> Optional[Token]:
        """Peek at the non-whitespace token at the given offset."""
        if self.current_token is None:
            return None

        count = 0
        for token in self.tokens[self._token_idx + 1:]:
            if token.type == "IDENTIFIER" and token.value.strip() == "":
                continue
            count += 1
            if count == offset:
                return token
        return None

    def _current_token_index(self) -> int:
        """Return the index of current_token in self.tokens, or -1 if not present."""
        if self.current_token is None:
            return -1
        return self._token_idx

    def _skip_ws_from(self, i: int) -> int:
        """Skip whitespace-placeholder IDENTIFIER tokens starting at index i."""
        n = len(self.tokens)
        while i < n and self.tokens[i].type == "IDENTIFIER" and not self.tokens[i].value.strip():
            i += 1
        return i

    def _scan_matching_gt(self, lt_index: int) -> int:
        """From index lt_index (a LESS_THAN token), find the matching GREATER_THAN.

        Returns the index of the matching GREATER_THAN, or -1 if not found before a
        statement boundary (;, {, }).
        """
        depth = 0
        n = len(self.tokens)
        i = lt_index
        while i < n:
            tt = self.tokens[i].type
            if tt == "LESS_THAN":
                depth += 1
            elif tt == "GREATER_THAN":
                depth -= 1
                if depth == 0:
                    return i
            elif tt in ("SEMICOLON", "OPEN_BRACE", "CLOSE_BRACE"):
                return -1  # hit a statement boundary — can't be a type param list
            i += 1
        return -1

    def _looks_like_generic_var_decl(self) -> bool:
        """Lookahead: current token is IDENTIFIER, next should be '<'.

        Returns True when the token stream from the current position matches
        the pattern ``IDENT < TYPE_ARGS > IDENT =`` (a generic variable
        declaration), False otherwise.  Used in deferred-import mode to route
        ``TypeName<T1, T2> varName = ...`` to ``parse_variable_declaration``
        even when TypeName is not yet registered as a generic class template.
        """
        idx = self._current_token_index()
        if idx < 0:
            return False
        n = len(self.tokens)
        i = self._skip_ws_from(idx + 1)
        if i >= n or self.tokens[i].type != "LESS_THAN":
            return False
        gt_idx = self._scan_matching_gt(i)
        if gt_idx < 0:
            return False
        i = self._skip_ws_from(gt_idx + 1)
        # Expect an IDENTIFIER (the variable name)
        if i >= n or self.tokens[i].type != "IDENTIFIER" or not self.tokens[i].value.strip():
            return False
        i = self._skip_ws_from(i + 1)
        return i < n and self.tokens[i].type == "ASSIGN"

    def _looks_like_generic_constructor_call(self) -> bool:
        """Lookahead: current token is '<'.

        Returns True when the token stream from the current position matches
        ``< TYPE_ARGS > (`` (a generic class constructor argument list), as
        opposed to a plain less-than comparison.  Used in deferred-import mode.
        """
        idx = self._current_token_index()
        if idx < 0 or self.tokens[idx].type != "LESS_THAN":
            return False
        gt_idx = self._scan_matching_gt(idx)
        if gt_idx < 0:
            return False
        i = self._skip_ws_from(gt_idx + 1)
        n = len(self.tokens)
        return i < n and self.tokens[i].type == "OPEN_PAREN"

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
        self.report_error(
            UnexpectedTokenError(
                expected=token_type,
                actual=self.current_token.type,
                source_file=self.filename,
                line=0,
                column=0,
            ),
            token=self.current_token,
        )
        return None

    def report_error(self, err: CompileTimeError, token: Optional[Token] = None) -> None:
        if token is not None and self.file is not None:
            try:
                line_num, column_num = get_line_and_coumn_from_index(self.file, token.index)
                line_text = get_line(self.file, line_num)
                err.line = line_num
                err.column = column_num
                err.snippet = line_text
            except Exception:
                pass
        if not err.source_file:
            err.source_file = self.filename
        logging.error(err)
        self.errors.append(err)

    def error(self, text: str, token: Optional[Token] = None):
        self.report_error(ParserError(message=text, source_file=self.filename), token=token)

    def expected_token_error(self, expected: str, token: Optional[Token] = None) -> None:
        self.report_error(ExpectedTokenError(expected=expected, source_file=self.filename), token=token)

    def missing_identifier_error(self, token: Optional[Token] = None) -> None:
        self.report_error(MissingIdentifierError(source_file=self.filename), token=token)

    def invalid_expression_error(self, detail: str, token: Optional[Token] = None) -> None:
        self.report_error(InvalidExpressionError(detail=detail, source_file=self.filename), token=token)

    def invalid_array_access_error(self, detail: str, token: Optional[Token] = None) -> None:
        self.report_error(InvalidArrayAccessError(detail=detail, source_file=self.filename), token=token)

    def invalid_field_access_error(self, detail: str, token: Optional[Token] = None) -> None:
        self.report_error(InvalidFieldAccessError(detail=detail, source_file=self.filename), token=token)

    def type_error(self, detail: str, token: Optional[Token] = None) -> None:
        self.report_error(TypeError(detail=detail, source_file=self.filename), token=token)

    def invalid_type_error(self, detail: str, token: Optional[Token] = None) -> None:
        self.report_error(InvalidTypeError(detail=detail, source_file=self.filename), token=token)

    def field_not_found_error(self, type_name: str, field_name: str, token: Optional[Token] = None) -> None:
        self.report_error(FieldNotFoundError(type_name=type_name, field_name=field_name, source_file=self.filename), token=token)

    def method_not_found_error(self, type_name: str, method_name: str, token: Optional[Token] = None) -> None:
        self.report_error(MethodNotFoundError(type_name=type_name, method_name=method_name, source_file=self.filename), token=token)

    def constructor_not_found_error(self, type_name: str, token: Optional[Token] = None) -> None:
        self.report_error(ConstructorNotFoundError(type_name=type_name,source_file=self.filename), token=token)

    def invalid_operator_error(self, operator: str, type_name: str, token: Optional[Token] = None) -> None:
        self.report_error(InvalidOperatorError(operator=operator, type_name=type_name, source_file=self.filename), token=token)

    def control_flow_error(self, statement: str, token: Optional[Token] = None) -> None:
        self.report_error(ControlFlowError(statement=statement, source_file=self.filename), token=token)

    def invalid_super_error(self, detail: str, token: Optional[Token] = None) -> None:
        self.report_error(InvalidSuperError(detail=detail, source_file=self.filename), token=token)

    def undefined_identifier_error(self, identifier: str, token: Optional[Token] = None) -> None:
        self.report_error(
            UndefinedIdentifierError(identifier=identifier, source_file=self.filename),
            token=token,
        )

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

    def _sync_to_semicolon(self):
        """Advance tokens until we reach a semicolon or run out of tokens."""
        while self.current_token and self.current_token.type != "SEMICOLON":
            self.advance()
        self.consume("SEMICOLON")

    def _recover_to_statement_boundary(self):
        """Panic-mode recovery to the next likely statement boundary.

        Always advances at least one token, then skips until a semicolon,
        closing brace, or a strong statement starter token is found.
        """
        strong_starters = {
            "IF",
            "ELSE",
            "WHILE",
            "FOR",
            "RETURN",
            "BREAK",
            "CONTINUE",
            "IMPORT",
            "EXPORT",
            "DIRECTIVE",
            "CLASS",
            "COPYABLE",
            "CONSTRAINT",
        }

        start_idx = self._token_idx
        if self.current_token is not None:
            self.advance()

        while self.current_token is not None:
            t = self.current_token.type
            if t == "SEMICOLON":
                self.advance()
                break
            if t == "CLOSE_BRACE":
                break
            if t in strong_starters:
                break
            self.advance()

        if self._token_idx == start_idx and self.current_token is not None:
            self.advance()

    def _parse_argument_list(self) -> list:
        """Parse a comma-separated list of expressions inside already-consumed '('.

        Consumes tokens up to and including ')'. Returns the list of argument nodes.
        Any argument that parses to None is skipped silently (error already logged).
        """
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
                self.expected_token_error("')' after argument list", self.current_token)
        return args

    def parse_expression(self) -> Optional[ASTNode]:
        """Implemented by expression mixins; declared here for static type checking."""
        raise NotImplementedError("parse_expression must be implemented by parser mixins")

    def _parse_type_arg_list(self) -> Optional[list[str]]:
        """Parse a comma-separated list of type arguments inside '<' ... '>'.

        Assumes current_token is '<' on entry. Consumes '<', the type arguments,
        and '>'. Returns the list of canonical type-name strings, or None on error.
        """
        self.advance()  # consume '<'
        type_args: list[str] = []
        while True:
            if not (self.current_token and self._is_type_token(self.current_token)):
                self.expected_token_error("type argument", self.current_token)
                return None
            targ_tok = self.current_token
            self.advance()
            type_args.append(self._normalize_type_name(targ_tok))
            if self.current_token and self.current_token.type == "COMMA":
                self.advance()
                continue
            break
        if not (self.current_token and self.current_token.type == "GREATER_THAN"):
            self.expected_token_error("'>' after type arguments", self.current_token)
            return None
        self.advance()  # consume '>'
        return type_args

    def _register_generic_class_instance(self, class_name: str, type_args: list[str]) -> str:
        """Register a monomorphized generic class instance for type checking.

        Substitutes the template's type parameters with the concrete type arguments
        and registers the result in user_types, user_classes, and user_methods so that
        the type-checker and downstream codegen can treat it like a normal class.

        Returns the composite type name, e.g. ``'Pair<int32, string>'``.
        """
        composite = f"{class_name}<{', '.join(type_args)}>"
        if composite in self.user_types:
            return composite  # Already registered

        template = self.generic_class_templates.get(class_name)
        if template is None:
            return composite

        type_params = getattr(template, "type_params", [])
        type_map = dict(zip(type_params, type_args))
        is_copyable_class = getattr(template, "is_copyable", False)

        def substitute(t: str) -> str:
            return type_map.get(t, t) if t else t

        # Build concrete field types from stored template field nodes
        field_types: dict[str, str] = {}
        for child in self._class_field_nodes.get(class_name, []):
            if child.node_type == NodeTypes.CLASS_FIELD:
                field_types[child.name] = substitute(child.var_type or "int32")

        # Register composite type for type-checking
        self.user_types.add(composite)
        self.user_classes[composite] = field_types
        self.user_class_bases[composite] = None

        # Build concrete method signatures
        self.user_methods[composite] = {}
        for m in self._class_method_nodes.get(class_name, []):
            param_nodes = [p for p in m.children[:-1] if p.node_type == NodeTypes.PARAMETER]
            # Exclude receiver 'this' from the external parameter list
            effective_params = (
                param_nodes[1:] if (param_nodes and param_nodes[0].name == "this") else param_nodes
            )
            params_types = [substitute(p.var_type or "int32") for p in effective_params]
            ret_type = substitute(m.return_type or "void")
            self.user_methods[composite][m.name] = {"return": ret_type, "params": params_types}

        # Register ownership category in type_utils
        from utils.type_utils import register_class
        register_class(composite, is_copyable_class)

        return composite

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
