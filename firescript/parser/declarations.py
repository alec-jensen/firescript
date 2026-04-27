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
            self.expected_token_error("return type at function definition", self.current_token)
            return None
        ret_type_token = self.current_token
        self.advance()

        # Optional array suffix for return type
        ret_is_array = False
        if self.current_token and self.current_token.type == "OPEN_BRACKET":
            self.advance()
            if not self.consume("CLOSE_BRACKET"):
                self.expected_token_error(
                    "']' after '[' in array return type", self.current_token
                )
                return None
            ret_is_array = True

        name_token = self.consume("IDENTIFIER")
        if name_token is None:
            self.expected_token_error("function name after return type", self.current_token)
            return None
        
        # Parse optional generic type parameters: <T, U, ...>
        type_params: list[str] = []
        type_constraints: dict[str, str] = {}
        
        if self.current_token and self.current_token.type == "LESS_THAN":
            self.advance()  # consume <
            # Parse type parameters
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
                        # Type names come as TYPE tokens, interface names as IDENTIFIER tokens
                        if not (self.current_token and (self._is_type_token(self.current_token) or self.current_token.type == "IDENTIFIER")):
                            self.expected_token_error("constraint type or interface", self.current_token)
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
                self.expected_token_error("'>' to close type parameters", self.current_token)
                return None
            self.advance()  # consume >
        
        # Validate return type if it was an IDENTIFIER (type parameter or user-defined class)
        if ret_type_token and ret_type_token.type == "IDENTIFIER" and ret_type_token.value not in self.TYPE_TOKEN_NAMES:
            # It could be: 1) a type parameter, 2) a user-defined class, or 3) an error
            is_type_param = ret_type_token.value in type_params
            is_user_class = ret_type_token.value in self.user_types
            if not is_type_param and not is_user_class:
                self.invalid_expression_error(f"Return type '{ret_type_token.value}' is not a declared type parameter", ret_type_token)
                return None
        
        if not self.consume("OPEN_PAREN"):
            self.expected_token_error("'(' after function name", self.current_token)
            return None

        # Set current type parameters for parsing function body
        prev_type_params = self._current_type_params
        self._current_type_params = type_params.copy()

        params: list[ASTNode] = []
        if self.current_token and self.current_token.type != "CLOSE_PAREN":
            while True:
                # Check for 'owned' keyword
                p_is_owned = False
                if self.current_token and self.current_token.type == "OWNED":
                    p_is_owned = True
                    self.advance()
                
                # Check for '&' borrow marker
                p_is_borrowed = False
                if self.current_token and self.current_token.type == "AMPERSAND":
                    p_is_borrowed = True
                    self.advance()
                
                # Allow both built-in types and user-defined class types
                if not (self.current_token and (self._is_type_token(self.current_token) or (
                    self.current_token.type == "IDENTIFIER" and self.current_token.value in self.user_types
                ))):
                    self.expected_token_error("parameter type", self.current_token)
                    return None
                ptype_tok = self.current_token
                self.advance()
                # Optional array suffix for parameter type: [] or [N]
                p_is_array = False
                p_array_size = None
                if self.current_token and self.current_token.type == "OPEN_BRACKET":
                    self.advance()
                    if self.current_token and self.current_token.type == "INTEGER_LITERAL":
                        try:
                            p_array_size = int(self.current_token.value)
                        except ValueError:
                            self.expected_token_error("integer size in array parameter type", self.current_token)
                            return None
                        self.advance()
                    if not self.consume("CLOSE_BRACKET"):
                        self.expected_token_error(
                            "']' after '[' in array parameter type",
                            self.current_token,
                        )
                        return None
                    p_is_array = True
                pname_tok = self.consume("IDENTIFIER")
                if pname_tok is None:
                    self.expected_token_error("parameter name", self.current_token)
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
                    array_size=p_array_size,
                )
                # Mark parameter as borrowed
                setattr(param_node, "is_borrowed", p_is_borrowed)
                params.append(param_node)
                if self.current_token and self.current_token.type == "COMMA":
                    self.advance()
                    continue
                break
        if not self.consume("CLOSE_PAREN"):
            self.expected_token_error("')' after parameters", self.current_token)
            return None
        if not (self.current_token and self.current_token.type == "OPEN_BRACE"):
            self.expected_token_error("'{' to start function body", self.current_token)
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
                idx_cur = self._current_token_index()
                if idx_cur + 2 < len(self.tokens):
                    next1 = self.tokens[idx_cur + 1]
                    next2 = self.tokens[idx_cur + 2]
                    if next1.type == "IDENTIFIER" and next2.type == "LESS_THAN":
                        can_be_func = True  # Likely a generic function
            
            if can_be_func:
                idx_cur = self._current_token_index()
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

            if isinstance(stmt, ASTNode):
                if getattr(self, "_pending_export", False):
                    if stmt.node_type in (NodeTypes.FUNCTION_DEFINITION, NodeTypes.VARIABLE_DECLARATION):
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
        if not (self.current_token and (
            self.current_token.type == "AS"
            or (self.current_token.type == "IDENTIFIER" and self.current_token.value == "as")
        )):
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

        # Parse optional generic type parameters: <T, U, ...>
        class_type_params: list[str] = []
        prev_class_type_params = self._current_type_params
        if self.current_token and self.current_token.type == "LESS_THAN":
            self.advance()  # consume <
            while True:
                # Skip optional 'nullable' constraint annotation on type parameters
                if self.current_token and self.current_token.type == "NULLABLE":
                    self.advance()
                if not (self.current_token and self.current_token.type == "IDENTIFIER"):
                    self.expected_token_error("type parameter name", self.current_token)
                    return None
                tparam_tok = self.consume("IDENTIFIER")
                if tparam_tok is None:
                    return None
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
            # Accept optional nullable modifier on field type or method return type
            local_is_nullable = False
            if self.current_token and self.current_token.type == "NULLABLE":
                local_is_nullable = True
                self.advance()
            # Accept types that are either known types or the current class name (for methods/fields/constructors)
            if not (self._is_type_token(self.current_token) or (
                self.current_token.type == "IDENTIFIER" and self.current_token.value == name_tok.value
            )):
                self.expected_token_error("field or method return type in class body", self.current_token)
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
                if local_is_static:
                    self.invalid_expression_error("Constructors cannot be declared static", ftype_tok)
                # Treat ftype_tok as the method name (constructor) and set return type to class name
                method_name_tok = ftype_tok
                # Parse parameters
                self.consume("OPEN_PAREN")
                params: list[ASTNode] = []
                seen_receiver = False
                if self.current_token and self.current_token.type != "CLOSE_PAREN":
                    while True:
                        # Borrowed receiver syntax: &this (read-only) or &mut this (mutable)
                        if (not seen_receiver) and self.current_token and self.current_token.type == "AMPERSAND":
                            amp_tok = self.current_token
                            self.advance()
                            is_mutable_borrow = False
                            if self.current_token and self.current_token.type == "MUT":
                                is_mutable_borrow = True
                                self.advance()
                            th_tok = self.consume("IDENTIFIER")
                            if th_tok is None or th_tok.value != "this":
                                self.expected_token_error("'this' after '&' (or '&mut') for receiver", th_tok or amp_tok)
                                return None
                            if local_is_static:
                                self.invalid_expression_error("Static methods cannot declare receiver parameter 'this'", th_tok)
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
                            setattr(recv, "is_mutable_borrow", is_mutable_borrow)
                            setattr(recv, "is_receiver", True)
                            params.append(recv)
                            seen_receiver = True
                        # Check for 'owned this' consuming receiver
                        elif (not seen_receiver) and self.current_token and self.current_token.type == "OWNED":
                            owned_tok = self.current_token
                            self.advance()
                            th_tok = self.consume("IDENTIFIER")
                            if th_tok is None or th_tok.value != "this":
                                self.expected_token_error("'this' after 'owned' for receiver", th_tok or owned_tok)
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
                            setattr(recv, "is_owned", True)
                            setattr(recv, "is_receiver", True)
                            params.append(recv)
                            seen_receiver = True
                        else:
                            # Check for 'owned' keyword
                            p_is_owned = False
                            if self.current_token and self.current_token.type == "OWNED":
                                p_is_owned = True
                                self.advance()
                            
                            # Check for '&' borrow marker
                            p_is_borrowed = False
                            if self.current_token and self.current_token.type == "AMPERSAND":
                                p_is_borrowed = True
                                self.advance()
                            
                            # Check for nullable modifier on parameter type
                            p_is_nullable = False
                            if self.current_token and self.current_token.type == "NULLABLE":
                                p_is_nullable = True
                                self.advance()
                            
                            # Parameter type: allow known types or current class name
                            if not (self.current_token and (self._is_type_token(self.current_token) or (
                                self.current_token.type == "IDENTIFIER" and self.current_token.value == name_tok.value
                            ))):
                                self.expected_token_error("parameter type in method", self.current_token)
                                return None
                            ptype_tok = self.current_token
                            self.advance()
                            p_is_array = False
                            if self.current_token and self.current_token.type == "OPEN_BRACKET":
                                self.invalid_expression_error("Array parameters are not supported for methods", self.current_token)
                                # try to recover
                                while self.current_token and self.current_token.type != "CLOSE_PAREN":
                                    self.advance()
                                break
                            pname_tok = self.consume("IDENTIFIER")
                            if pname_tok is None:
                                self.expected_token_error("parameter name in method", self.current_token)
                                return None
                            param_node = ASTNode(
                                NodeTypes.PARAMETER,
                                pname_tok,
                                pname_tok.value,
                                [],
                                pname_tok.index,
                                self._normalize_type_name(ptype_tok),
                                p_is_nullable,
                                False,
                                None,
                                p_is_array,
                                p_is_array,
                            )
                            if p_is_borrowed:
                                setattr(param_node, "is_borrowed", True)
                            if p_is_owned:
                                setattr(param_node, "is_owned", True)
                            params.append(param_node)
                        if self.current_token and self.current_token.type == "COMMA":
                            self.advance()
                            continue
                        break
                if not self.consume("CLOSE_PAREN"):
                    self.expected_token_error("')' after method parameters", self.current_token)
                    return None
                if not (self.current_token and self.current_token.type == "OPEN_BRACE"):
                    self.expected_token_error("'{' to start method body", self.current_token)
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
                setattr(method_node, "is_static", False)
                methods.append(method_node)
                continue
            # Look ahead: IDENTIFIER then '(' => method; IDENTIFIER then ';' => field
            name_tok2 = self.consume("IDENTIFIER")
            if name_tok2 is None:
                self.expected_token_error("identifier after type in class body", self.current_token)
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
                        # Borrowed receiver syntax: &this (read-only) or &mut this (mutable)
                        if (not seen_receiver) and self.current_token and self.current_token.type == "AMPERSAND":
                            amp_tok = self.current_token
                            self.advance()
                            is_mutable_borrow = False
                            if self.current_token and self.current_token.type == "MUT":
                                is_mutable_borrow = True
                                self.advance()
                            th_tok = self.consume("IDENTIFIER")
                            if th_tok is None or th_tok.value != "this":
                                self.expected_token_error("'this' after '&' (or '&mut') for receiver", th_tok or amp_tok)
                                return None
                            if local_is_static:
                                self.invalid_expression_error("Static methods cannot declare receiver parameter 'this'", th_tok)
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
                            setattr(recv, "is_mutable_borrow", is_mutable_borrow)
                            setattr(recv, "is_receiver", True)
                            params.append(recv)
                            seen_receiver = True
                        else:
                            # Check for nullable modifier on parameter type
                            p_is_nullable = False
                            if self.current_token and self.current_token.type == "NULLABLE":
                                p_is_nullable = True
                                self.advance()
                            # Parameter type: allow known types or current class name
                            if not (self.current_token and (self._is_type_token(self.current_token) or (
                                self.current_token.type == "IDENTIFIER" and self.current_token.value == name_tok.value
                            ))):
                                self.expected_token_error("parameter type in method", self.current_token)
                                return None
                            ptype_tok = self.current_token
                            self.advance()
                            p_is_array = False
                            if self.current_token and self.current_token.type == "OPEN_BRACKET":
                                self.invalid_expression_error("Array parameters are not supported for methods", self.current_token)
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
                                self.expected_token_error("parameter name in method", self.current_token)
                                return None
                            param_node = ASTNode(
                                NodeTypes.PARAMETER,
                                pname_tok,
                                pname_tok.value,
                                [],
                                pname_tok.index,
                                self._normalize_type_name(ptype_tok),
                                p_is_nullable,
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
                    self.expected_token_error("')' after method parameters", self.current_token)
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
                setattr(method_node, "is_static", local_is_static)
                methods.append(method_node)
            else:
                # Field declaration path
                if not self.consume("SEMICOLON"):
                    self.expected_token_error("';' after field declaration", self.current_token)
                    while self.current_token and self.current_token.type not in ("SEMICOLON", "CLOSE_BRACE"):
                        self.advance()
                    if self.current_token and self.current_token.type == "SEMICOLON":
                        self.advance()
                field_type = self._normalize_type_name(ftype_tok)
                field_node = ASTNode(NodeTypes.CLASS_FIELD, name_tok2, name_tok2.value, [], name_tok2.index, var_type=field_type, is_nullable=local_is_nullable)
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
        else:
            # Regular (non-generic) class
            # Register class with type_utils
            from utils.type_utils import register_class
            register_class(name_tok.value, is_copyable)

        return cls_node
