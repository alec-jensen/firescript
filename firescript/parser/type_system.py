import logging
import re
from typing import Optional

from utils.type_utils import is_owned, is_copyable
from utils.literal_utils import (
    unsuffixed_literal_of, literal_range_error, coerce_literal, int_literal_value, INT_RANGES,
)
from enums import NodeTypes
from .ast_node import ASTNode
from .statements import StatementsMixin


class TypeSystemMixin(StatementsMixin):
    def _annotate_value_category(self, node: ASTNode, var_type: Optional[str], is_array: bool):
        """Annotate node.value_category based on ownership/copyability of var_type."""
        try:
            node.value_category = (
                "Owned" if is_owned(var_type, is_array) else (
                    "Copyable" if is_copyable(var_type, is_array) else None
                )
            )
        except Exception:
            pass

    def resolve_variable_types(self, node: ASTNode, current_scope=None):
        """
        Recursively traverse the AST to annotate Identifier nodes with the variable type,
        enforce no shadowing and undefined variable usage.
        """
        if current_scope is None:
            current_scope = {}
            # Top-level pass: remember which top-level variables this file
            # declares, so a use that precedes its declaration is reported
            # even when imports defer ordinary undefined-name checks.
            self._scope_counter = 0
            self._resolve_scope_id = 0
            self._toplevel_var_names = {
                c.name for c in node.children if c.node_type == NodeTypes.VARIABLE_DECLARATION
            }

        # New scope node: copy parent scope. Each scope entry is
        # (type, is_array, is_nullable, scope_id); scope_id tells a
        # same-scope redeclaration apart from shadowing an outer name.
        if node.node_type == NodeTypes.SCOPE:
            new_scope = current_scope.copy()
            prev_scope_id = self._resolve_scope_id
            self._scope_counter += 1
            self._resolve_scope_id = self._scope_counter
            for child in node.children:
                self.resolve_variable_types(child, new_scope)
            self._resolve_scope_id = prev_scope_id
            return

        # For loops: create new scope for init variables
        if node.node_type in (NodeTypes.FOR_STATEMENT, NodeTypes.FOR_IN_STATEMENT):
            new_scope = current_scope.copy()
            prev_scope_id = self._resolve_scope_id
            self._scope_counter += 1
            self._resolve_scope_id = self._scope_counter
            # Process all children (init, condition, increment, body) in the new scope
            for child in node.children:
                self.resolve_variable_types(child, new_scope)
            self._resolve_scope_id = prev_scope_id
            return

        # Function/generator definition: parameters introduce a new scope level
        if node.node_type in (NodeTypes.FUNCTION_DEFINITION, NodeTypes.GENERATOR_DEFINITION):
            # Children layout: [params..., body_scope]
            new_scope = current_scope.copy()
            prev_scope_id = self._resolve_scope_id
            self._scope_counter += 1
            self._resolve_scope_id = self._scope_counter
            # Register parameters (prevent shadowing outer vars)
            for child in node.children[
                :-1
            ]:  # all except last which should be body scope
                if child.node_type == NodeTypes.PARAMETER:
                    self._register_parameter_in_scope(child, new_scope)
            # Traverse body with parameter scope
            body = node.children[-1] if node.children else None
            if body:
                self.resolve_variable_types(body, new_scope)
            self._resolve_scope_id = prev_scope_id
            return

        # Class method definition: similar to function but includes receiver parameter
        if node.node_type == NodeTypes.CLASS_METHOD_DEFINITION:
            new_scope = current_scope.copy()
            prev_scope_id = self._resolve_scope_id
            self._scope_counter += 1
            self._resolve_scope_id = self._scope_counter
            for child in node.children[:-1]:  # params (including receiver)
                if child.node_type == NodeTypes.PARAMETER:
                    self._register_parameter_in_scope(child, new_scope)
            # Inject implicit alias 'this' to the class type for method/constructor bodies,
            # so 'this.x' resolves even if receiver param was named differently or synthetic.
            cls_name = getattr(node, "class_name", None)
            if cls_name and "this" not in new_scope and not bool(getattr(node, "is_static", False)):
                new_scope["this"] = (cls_name, False, False, self._resolve_scope_id)
            body = node.children[-1] if node.children else None
            if body:
                self.resolve_variable_types(body, new_scope)
            self._resolve_scope_id = prev_scope_id
            return

        # Variable declaration: enforce no shadowing
        if node.node_type == NodeTypes.VARIABLE_DECLARATION:
            if node.name in current_scope:
                if current_scope[node.name][3] == self._resolve_scope_id:
                    self.invalid_type_error(
                        f"Variable '{node.name}' is already declared in this scope",
                        node.token,
                    )
                else:
                    self.invalid_type_error(
                        f"Variable '{node.name}' already declared in an outer scope; shadowing not allowed",
                        node.token,
                    )
            elif node.name in self.user_types:
                self.invalid_type_error(
                    f"Variable '{node.name}' conflicts with the type '{node.name}'; "
                    f"a variable cannot reuse a class or enum name",
                    node.token,
                )
            current_scope[node.name] = (
                node.var_type, node.is_array, bool(node.is_nullable), self._resolve_scope_id
            )
            self._annotate_value_category(node, node.var_type, node.is_array)
            # Resolve initializer expression
            for child in node.children:
                self.resolve_variable_types(child, current_scope)
            return

        # Variable assignment: the target must already be declared (via a
        # `name: Type = ...` declaration) in an enclosing scope. Bare
        # assignment to an undeclared name is not a declaration.
        if node.node_type == NodeTypes.VARIABLE_ASSIGNMENT:
            # Resolve RHS first to allow identifiers inside it to be typed
            for child in node.children:
                self.resolve_variable_types(child, current_scope)
            if node.name not in current_scope:
                if self.defer_undefined_identifiers and node.name not in self._toplevel_var_names:
                    self.deferred_undefined_identifiers.append((node.name, node.token))
                else:
                    self.undefined_identifier_error(node.name, node.token)
            return

        # Match expression: scrutinee resolves in the outer scope; each arm
        # gets its own scope with pattern bindings registered.
        if node.node_type == NodeTypes.MATCH_EXPRESSION:
            if node.children:
                self.resolve_variable_types(node.children[0], current_scope)
                for arm in node.children[1:]:
                    self.resolve_variable_types(arm, current_scope)
            return

        if node.node_type == NodeTypes.MATCH_ARM:
            new_scope = current_scope.copy()
            enum_name = getattr(node, "enum_name", None)
            bindings = getattr(node, "bindings", []) or []
            if bindings:
                payload_fields = dict(
                    self.user_enums.get(enum_name or "", {}).get(
                        getattr(node, "variant_name", None) or "", []
                    )
                )
                for field_name, local_name in bindings:
                    bind_type = payload_fields.get(field_name)
                    new_scope[local_name] = (bind_type, False, False, self._resolve_scope_id)
            body = node.children[0] if node.children else None
            if body:
                self.resolve_variable_types(body, new_scope)
            return

        # Identifier usage: ensure variable defined
        if node.node_type == NodeTypes.IDENTIFIER:
            if node.name not in current_scope:
                if self.defer_undefined_identifiers and node.name not in self._toplevel_var_names:
                    self.deferred_undefined_identifiers.append((node.name, node.token))
                else:
                    # Not yet declared. With imports pending, a name this
                    # very file declares at top level *later* is a
                    # use-before-declaration, not a possible imported name.
                    self.undefined_identifier_error(node.name, node.token)
            else:
                node.var_type, node.is_array, node.declared_nullable = current_scope[node.name][:3]
                self._annotate_value_category(node, node.var_type, node.is_array)
            return

        # Recurse into children for all other nodes
        for child in node.children:
            self.resolve_variable_types(child, current_scope)

    def _register_parameter_in_scope(self, child: ASTNode, scope: dict) -> None:
        """Register a PARAMETER node in `scope`, diagnosing a duplicate
        parameter name or a name that shadows an outer variable."""
        param_name = child.name
        if param_name in scope:
            if scope[param_name][3] == self._resolve_scope_id:
                self.invalid_type_error(
                    f"Parameter '{param_name}' is declared more than once",
                    child.token,
                )
            else:
                self.invalid_type_error(
                    f"Parameter '{param_name}' already declared in an outer scope; shadowing not allowed",
                    child.token,
                )
        scope[param_name] = (child.var_type, child.is_array, bool(child.is_nullable), self._resolve_scope_id)
        self._annotate_value_category(child, child.var_type, child.is_array)

    # Class-level defaults so type checking also works when driven without
    # type_check() (type_check() re-initializes them per file).
    _current_callable: Optional[ASTNode] = None
    _duplicate_class_nodes: frozenset = frozenset()

    def type_check(self):
        """Initiates the type checking process on the AST."""
        logging.debug("Starting type checking...")
        symbol_table = (
            {}
        )  # Build initial symbol table if needed, or rely on resolved types
        # Unsuffixed integer literals are typed int32 by default but may take
        # the type of the declaration/parameter/return they initialize (see
        # _coerce_literal). Those still uncoerced after the whole walk are
        # range-checked as int32.
        self._pending_int_literals: list[ASTNode] = []
        self._current_callable: Optional[ASTNode] = None
        self._local_functions: dict[str, ASTNode] = {
            c.name: c
            for c in self.ast.children
            if c.node_type in (NodeTypes.FUNCTION_DEFINITION, NodeTypes.GENERATOR_DEFINITION)
        }
        self._check_class_declarations()
        self._type_check_node(self.ast, symbol_table)
        for lit in self._pending_int_literals:
            if not getattr(lit, "_literal_coerced", False) and not getattr(lit, "_range_checked", False):
                lit._range_checked = True
                err = self._literal_range_error(lit, "int32")
                if err:
                    self.invalid_type_error(err, lit.token)
        logging.debug("Type checking finished.")

    def _check_class_declarations(self) -> None:
        """Declaration-level class checks over this file's own classes:
        duplicate class names, duplicate fields, unknown base classes and
        cyclic inheritance. (With imports pending, a base class that is not
        declared here may come from an imported module; that case is
        checked after the merge by the semantic analyzer.)"""
        seen_functions: set[str] = set()
        for fn in self.ast.children:
            if fn.node_type not in (NodeTypes.FUNCTION_DEFINITION, NodeTypes.GENERATOR_DEFINITION):
                continue
            if fn.name in seen_functions:
                self.invalid_type_error(f"Function '{fn.name}' is already defined", fn.token)
            seen_functions.add(fn.name)
        classes = [c for c in self.ast.children if c.node_type == NodeTypes.CLASS_DEFINITION]
        by_name: dict[str, ASTNode] = {}
        self._duplicate_class_nodes: set[int] = set()
        for cls in classes:
            if cls.name in by_name:
                self.invalid_type_error(f"Class '{cls.name}' is already defined", cls.token)
                self._duplicate_class_nodes.add(id(cls))
                self._duplicate_class_nodes.add(id(by_name[cls.name]))
                continue
            by_name[cls.name] = cls
        for cls in classes:
            seen_fields: set[str] = set()
            for member in cls.children:
                if member.node_type != NodeTypes.CLASS_FIELD:
                    continue
                if member.name in seen_fields:
                    self.invalid_type_error(
                        f"Field '{member.name}' is already declared in class '{cls.name}'", member.token
                    )
                seen_fields.add(member.name)
        for cls in classes:
            base = getattr(cls, "base_class", None)
            if not base or base == cls.name:
                continue
            if base not in by_name and base not in self.user_types and base not in self.generic_class_templates:
                if not self.defer_undefined_identifiers:
                    self.invalid_type_error(
                        f"Unknown base class '{base}' for class '{cls.name}'", cls.token
                    )
                continue
            # Walk the (single-inheritance) chain; reaching `cls` again is a cycle.
            cur = base
            visited = {cls.name}
            while cur:
                if cur in visited:
                    if cur == cls.name:
                        self.invalid_type_error(
                            f"Cyclic inheritance: class '{cls.name}' (indirectly) inherits from itself",
                            cls.token,
                        )
                    break
                visited.add(cur)
                nxt = by_name.get(cur)
                cur = getattr(nxt, "base_class", None) if nxt is not None else None

    # -- literal typing (see utils/literal_utils.py) --------------------------

    def _unsuffixed_literal_of(self, node: ASTNode) -> Optional[tuple[ASTNode, bool]]:
        return unsuffixed_literal_of(node)

    def _literal_range_error(self, lit: ASTNode, type_name: str) -> Optional[str]:
        return literal_range_error(lit, type_name)

    def _coerce_literal(self, node: ASTNode, expected: Optional[str]) -> tuple[bool, Optional[str]]:
        """Type an unsuffixed numeric literal from the type it initializes
        (docs/reference/type_system.md, "Type Inference for Literals")."""
        return coerce_literal(node, expected)

    # -- compile-time constant integer expressions ----------------------------

    def _const_int(self, node: Optional[ASTNode]) -> Optional[int]:
        """The exact value of an all-literal integer expression, or None."""
        if node is None:
            return None
        cached = getattr(node, "_const_value", None)
        if cached is not None:
            return cached
        if (
            node.node_type == NodeTypes.LITERAL
            and node.token is not None
            and node.token.type == "INTEGER_LITERAL"
        ):
            return int_literal_value(node)
        return None

    def _fold_binary_constant(self, node: ASTNode, left: ASTNode, right: ASTNode, op: str, type_str: str) -> None:
        """Evaluate `left op right` when both are constant integers of
        `type_str`; report an overflow, or a division by a constant zero."""
        if type_str not in INT_RANGES:
            return
        rv = self._const_int(right)
        if op in ("/", "%") and rv == 0:
            self.constant_division_by_zero_error(
                f"Division by zero: the right operand of '{op}' is the constant 0", node.token
            )
            return
        lv = self._const_int(left)
        if lv is None or rv is None:
            return
        if op == "+":
            result = lv + rv
        elif op == "-":
            result = lv - rv
        elif op == "*":
            result = lv * rv
        elif op == "/":
            result = abs(lv) // abs(rv) * (1 if (lv < 0) == (rv < 0) else -1)
        elif op == "%":
            result = abs(lv) % abs(rv) * (1 if lv >= 0 else -1)
        elif op == "**":
            if rv < 0:
                return
            if rv > 128 and abs(lv) > 1:
                result = INT_RANGES[type_str][1] + 1  # certainly out of range
            else:
                result = lv ** rv
        else:
            return
        self._check_constant_range(node, result, type_str)

    def _check_constant_range(self, node: ASTNode, result: int, type_str: str) -> None:
        lo, hi = INT_RANGES[type_str]
        if lo <= result <= hi:
            node._const_value = result
            return
        shown = str(result) if abs(result) < 10 ** 30 else "a value too large to display"
        self.constant_overflow_error(
            f"Constant expression overflows type {type_str}: the result {shown} is outside {lo} to {hi}",
            node.token,
        )

    def _check_constant_index(self, node: ASTNode, symbol_table: dict) -> None:
        """A constant index into an array with a declared size must be in
        range (negative indices count from the end: -len..-1)."""
        arr, idx = node.children[0], node.children[1]
        if arr.node_type != NodeTypes.IDENTIFIER:
            return
        info = symbol_table.get(arr.name)
        size = info[3] if info is not None and len(info) > 3 else None
        value = self._const_int(idx)
        if size is None or value is None:
            return
        if value >= size or value < -size:
            self.constant_index_error(
                f"Array index {value} is out of range for '{arr.name}' of size {size} "
                f"(valid indices are {-size} to {size - 1})",
                idx.token or node.token,
            )

    def _is_subclass_of(self, actual: str, expected: str) -> bool:
        cur = self.user_class_bases.get(actual)
        seen = set()
        while cur and cur not in seen:
            if cur == expected:
                return True
            seen.add(cur)
            cur = self.user_class_bases.get(cur)
        return False

    def _assignability(
        self,
        expected: Optional[str],
        expected_nullable: bool,
        expr: ASTNode,
        actual: Optional[str],
        allow_subclass: bool = True,
    ) -> tuple[str, str]:
        """Check that `expr` (of type `actual`) may initialize/assign/pass
        as `expected`. Returns ("ok"|"null"|"range"|"mismatch", detail).
        Unknown types on either side are accepted: only a definite
        disagreement is reported."""
        if expected is None or actual is None:
            return "ok", ""
        if actual == "null":
            return ("ok", "") if expected_nullable else ("null", "")
        applied, err = self._coerce_literal(expr, expected)
        if applied:
            return ("range", err) if err else ("ok", "")
        actual_base = actual[:-1] if actual.endswith("?") else actual
        expected_base = expected[:-1] if expected.endswith("?") else expected
        if actual_base == expected_base:
            return "ok", ""
        if allow_subclass and self._is_subclass_of(actual_base, expected_base):
            return "ok", ""
        return "mismatch", ""

    @staticmethod
    def _param_type_str(param: ASTNode, subst: Optional[dict] = None) -> str:
        base = param.var_type or ""
        if subst and base in subst:
            base = subst[base]
        return f"{base}[]" if param.is_array else base

    def _enclosing_callable(self, node: ASTNode) -> Optional[ASTNode]:
        return self._current_callable

    def _check_match_value_arms(
        self, match_node: ASTNode, expected: Optional[str], expected_nullable: bool
    ) -> None:
        """A `match` used as a value (initializer / assigned value): every
        expression arm must produce the context's type."""
        for arm in match_node.children[1:]:
            if arm.node_type != NodeTypes.MATCH_ARM or not arm.children:
                continue
            body = arm.children[0]
            if body.node_type == NodeTypes.SCOPE:
                continue
            arm_t = getattr(arm, "_value_type", None)
            kind, detail = self._assignability(
                expected, expected_nullable, body, arm_t, allow_subclass=False
            )
            tok = body.token or arm.token
            if kind == "mismatch":
                self.invalid_type_error(
                    f"Match arm produces {arm_t}, but the match is used as {expected}", tok
                )
            elif kind == "null":
                self.invalid_type_error(
                    f"Match arm produces null, but the match is used as non-nullable {expected}", tok
                )
            elif kind == "range":
                self.invalid_type_error(detail, tok)

    def _type_param_is_float_only(self, type_param: str) -> bool:
        """True if the enclosing generic function constrains `type_param` to
        floating-point types only (e.g. `T: Float` or `T: float32 | float64`),
        for which `%` (integer-only) is not defined."""
        fn = self._current_callable
        constraint = (getattr(fn, "type_constraints", None) or {}).get(type_param)
        if not constraint or "&" in constraint:
            return False
        alternatives = [alt.strip() for alt in constraint.split("|")]
        return all(alt in ("Float", "float32", "float64", "float128") for alt in alternatives)

    @staticmethod
    def _is_compiler_intrinsic(name: str) -> bool:
        """True for a callee the FIR converter resolves itself (directive-gated
        runtime primitives, conversion intrinsics), which has no firescript
        definition to look up."""
        from ast_to_fir import INTRINSIC_RETURN_TYPES

        return name in INTRINSIC_RETURN_TYPES

    def _check_returned_value(
        self, fn: ASTNode, declared: str, expr: ASTNode, actual: Optional[str], node: ASTNode
    ) -> None:
        """Check `return <expr>` against the enclosing function's declared
        return type."""
        if actual is None:
            return
        # Types that mention a generic type parameter are only resolved at
        # monomorphization; leave those to the later (post-substitution) checks.
        params = set(self._current_type_params)
        if params and params & set(re.findall(r"\w+", f"{declared} {actual}")):
            return
        nullable = declared.endswith("?")
        declared_base = declared[:-1] if nullable else declared
        kind, detail = self._assignability(declared_base, nullable, expr, actual)
        if kind == "mismatch":
            self.invalid_type_error(
                f"Cannot return {actual} from '{fn.name}', which returns {declared}", node.token
            )
        elif kind == "null":
            self.invalid_type_error(
                f"Cannot return null from '{fn.name}': return type {declared} is not nullable",
                node.token,
            )
        elif kind == "range":
            self.invalid_type_error(detail, expr.token or node.token)

    def _check_local_function_call(self, node: ASTNode, child_types: list) -> None:
        """Argument count/type checking for a call to a free function
        defined in this file (see _check_call_args; calls to functions that
        only exist after import merging are checked by the semantic
        analyzer)."""
        fn = self._local_functions[node.name]
        params = [c for c in fn.children if c.node_type == NodeTypes.PARAMETER]
        node._signature_checked = True
        if len(node.children) != len(params):
            self.invalid_type_error(
                f"Function '{node.name}' expected {len(params)} argument(s), got {len(node.children)}",
                node.token,
            )
            return
        subst: dict[str, str] = {}
        if fn.type_params:
            if not node.type_args or len(node.type_args) != len(fn.type_params):
                return  # inference already failed (and was reported)
            subst = dict(zip(fn.type_params, node.type_args))
        for i, (param, arg, arg_t) in enumerate(zip(params, node.children, child_types)):
            expected = self._param_type_str(param, subst)
            kind, detail = self._assignability(expected, bool(param.is_nullable), arg, arg_t)
            self._report_arg_problem(
                kind, detail, f"function '{node.name}'", i, expected, arg_t, arg, node
            )

    def _report_arg_problem(
        self, kind: str, detail: str, what: str, index: int, expected: str,
        actual: Optional[str], arg: ASTNode, call: ASTNode,
    ) -> None:
        tok = arg.token if arg.token is not None else call.token
        if kind == "mismatch":
            self.invalid_type_error(
                f"Argument {index + 1} for {what} expected type {expected}, got {actual}", tok
            )
        elif kind == "null":
            self.invalid_type_error(
                f"Argument {index + 1} for {what} cannot be null: parameter type {expected} is not nullable",
                tok,
            )
        elif kind == "range":
            self.invalid_type_error(detail, tok)

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
                # self.invalid_type_error("Cannot determine type of empty array literal", node.token)
                return None  # Or a special "empty_array" type?
            # Check the type of the first element to infer array type
            first_elem_type_node = node.children[0]
            # Ensure the first element node itself has a token before checking type
            if first_elem_type_node:
                first_elem_type = self._checked_type(
                    first_elem_type_node, symbol_table
                )
                if first_elem_type is None:
                    return None  # Error in element
                if first_elem_type.endswith("[]"):
                    self.invalid_type_error(
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
                array_type = self._checked_type(array_expr_node, symbol_table)
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
        
        # Extract parameter types from function definition (paired with
        # is_array, since a `&arr: T[]` parameter's own var_type is just
        # "T" -- array-ness is tracked separately).
        param_types = []
        for child in func_def.children:
            if child.node_type == NodeTypes.PARAMETER:
                param_types.append((child.var_type or "", bool(getattr(child, "is_array", False))))

        # Build a mapping from type parameters to inferred concrete types
        type_map: dict[str, str] = {}

        for (param_type, param_is_array), arg_type in zip(param_types, arg_types):
            if param_type in type_params:
                # A `T[]` parameter binds T to the argument's element type,
                # not the whole array type -- an `int32[]` argument must
                # infer T=int32, not T="int32[]".
                if param_is_array and arg_type.endswith("[]"):
                    arg_type = arg_type[:-2]
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

    def _generic_template_method_sig(self, class_name: str, method_name: str) -> Optional[dict]:
        """Look up a method's signature directly on a generic class
        template's own AST node (self.generic_class_templates), computing
        the same {"return", "params", "is_static"} shape declarations.py
        registers into self.user_methods for a concrete (non-generic)
        class -- generic templates deliberately have no user_methods entry
        (see declarations.py's generic-class-registration comment), so
        NodeTypes.TYPE_METHOD_CALL validation needs this fallback for a
        static method called on the bare template name (e.g. `Box.make(5)`
        for `class Box<T>`)."""
        template = self.generic_class_templates.get(class_name)
        if template is None:
            return None
        for member in template.children or []:
            if member.node_type != NodeTypes.CLASS_METHOD_DEFINITION or member.name != method_name:
                continue
            param_nodes = [p for p in member.children[:-1] if p.node_type == NodeTypes.PARAMETER]
            effective_params = (
                param_nodes[1:] if (param_nodes and param_nodes[0].name == "this") else param_nodes
            )
            return {
                "return": member.return_type,
                "params": [p.var_type for p in effective_params],
                "is_static": bool(getattr(member, "is_static", False)),
            }
        return None

    def _dispatch_builtin_method(
        self,
        node: ASTNode,
        family: str,
        elem_type: Optional[str],
        object_type: str,
        method_name: str,
        arg_types: list,
    ) -> None:
        """Type-check a dot-method call on a primitive receiver (string/array)
        against the @builtin_method registry (firescript/builtin_methods.py),
        the single source of truth for these methods' signatures -- populated
        by scanning std/internal/*.fire, rather than a hand-written table
        per receiver type. `elem_type` is the array's element type (None for
        string receivers); it's substituted for any type-parameterized
        argument/return type in the registered signature.
        """
        from builtin_methods import get_builtin_method_registry

        spec = get_builtin_method_registry().lookup(family, method_name)
        if spec is None:
            self.invalid_type_error(f"Unknown method '{method_name}' for type '{object_type}'", node.token)
            return

        if len(arg_types) != len(spec.public_param_types):
            self.invalid_type_error(
                f"Method '{method_name}' expected {len(spec.public_param_types)} argument(s), got {len(arg_types)}",
                node.token,
            )
            return

        for i, (arg_t, expected) in enumerate(zip(arg_types, spec.public_param_types)):
            concrete_expected = expected if elem_type is None or expected not in spec.type_params else elem_type
            if arg_t != concrete_expected:
                self.invalid_type_error(
                    f"Method '{method_name}' for {object_type} argument {i + 1} expected type "
                    f"{concrete_expected}, got {arg_t}",
                    node.children[i + 1].token,
                )
                return

        ret = spec.return_type
        node.return_type = ret if elem_type is None or ret not in spec.type_params else elem_type

    def _type_check_node(self, node: ASTNode, symbol_table: dict) -> Optional[str]:
        """Recursively checks types in the AST node and returns the node's expression type."""
        # Track the enclosing function/method so `return`/`yield` can be
        # checked against its signature (function bodies are not linked to
        # their definition node by `.parent`).
        if node.node_type in (
            NodeTypes.FUNCTION_DEFINITION,
            NodeTypes.GENERATOR_DEFINITION,
            NodeTypes.CLASS_METHOD_DEFINITION,
        ):
            prev_callable = self._current_callable
            self._current_callable = node
            try:
                result = self._type_check_node_impl(node, symbol_table)
            finally:
                self._current_callable = prev_callable
        else:
            result = self._type_check_node_impl(node, symbol_table)
        node._tc_result = result
        return result

    def _checked_type(self, node: ASTNode, symbol_table: dict) -> Optional[str]:
        """The type of `node`, reusing the result of an earlier check so a
        node's diagnostics are not reported again when a parent re-asks."""
        if hasattr(node, "_tc_result"):
            return node._tc_result
        return self._type_check_node(node, symbol_table)

    def _type_check_node_impl(self, node: ASTNode, symbol_table: dict) -> Optional[str]:
        node_type_str = None  # The type of the expression this node represents

        # A class defined twice has an ambiguous field/method registry, so
        # its bodies would only produce misleading cascade errors (the
        # duplicate itself is reported by _check_class_declarations).
        if node.node_type == NodeTypes.CLASS_DEFINITION and id(node) in self._duplicate_class_nodes:
            return None

        # A literal under a unary minus is range-checked as a negative value
        # (so `-128i8` is valid); make sure it can see that parent.
        if (
            node.node_type == NodeTypes.UNARY_EXPRESSION
            and len(node.children) == 1
            and node.children[0].node_type == NodeTypes.LITERAL
        ):
            node.children[0].parent = node

        # Special handling for generic function definitions: set type parameter context
        if node.node_type == NodeTypes.FUNCTION_DEFINITION and hasattr(node, 'type_params') and node.type_params:
            prev_type_params = self._current_type_params
            self._current_type_params = node.type_params.copy()
            child_types = [
                self._type_check_node(child, symbol_table) for child in node.children
            ]
            self._current_type_params = prev_type_params
        elif node.node_type == NodeTypes.CLASS_DEFINITION and hasattr(node, 'type_params') and node.type_params:
            # A generic class's own type parameters (e.g. ArrayList<T>'s `T`,
            # HashMap<K,V>'s `K`/`V`) must stay visible while type-checking
            # every method body in the class, not just the class's own
            # field/method *signatures* -- this recursive walk runs once,
            # fully separately from (and after) the live parse-time
            # _current_type_params tracking in declarations.py's
            # _parse_class_definition (which correctly scopes the class's
            # type params during parsing but resets them once the whole
            # class is done being parsed). Without this, an expression like
            # `this.val == x` inside a non-generic method of a generic class
            # -- both operands typed as the bare class type parameter --
            # failed with "Cannot compare types T and T with '=='" because
            # `T` wasn't recognized as a type parameter here, only as parsed.
            prev_type_params = self._current_type_params
            prev_generic_class_name = self._current_generic_class_name
            self._current_type_params = node.type_params.copy()
            self._current_generic_class_name = node.name
            child_types = [
                self._type_check_node(child, symbol_table) for child in node.children
            ]
            self._current_type_params = prev_type_params
            self._current_generic_class_name = prev_generic_class_name
        else:
            # First, recursively check children to determine their types
            child_types = [
                self._type_check_node(child, symbol_table) for child in node.children
            ]

        # --- Type Checking Logic based on Node Type ---
        if node.node_type == NodeTypes.ROOT or node.node_type == NodeTypes.SCOPE:
            # Scopes don't have a type themselves, just check children
            pass  # Children already checked

        elif node.node_type == NodeTypes.LITERAL:
            if node.token is not None and node.token.type == "INTEGER_LITERAL":
                if self._unsuffixed_literal_of(node) is not None:
                    # Typed int32 unless a parent coerces it; range-checked
                    # at the end of the walk (see type_check).
                    self._pending_int_literals.append(node)
                elif not getattr(node, "_range_checked", False):
                    node._range_checked = True
                    err = self._literal_range_error(node, node.return_type or "")
                    if err:
                        self.invalid_type_error(err, node.token)

        elif node.node_type == NodeTypes.VARIABLE_DECLARATION:
            declared_type = f"{node.var_type}[]" if node.is_array else node.var_type
            initializer_type = child_types[0] if child_types else None
            init_node = node.children[0] if node.children else None

            if init_node is not None and node.is_array:
                if init_node.node_type == NodeTypes.ARRAY_LITERAL:
                    # docs/reference/arrays.md: the declared size must match the
                    # initializer's element count, and the elements take the
                    # declared element type (unsuffixed literals).
                    if (
                        node.array_size is not None
                        and init_node.children
                        and len(init_node.children) != node.array_size
                    ):
                        self.invalid_type_error(
                            f"Array '{node.name}' is declared with size {node.array_size} but its "
                            f"initializer has {len(init_node.children)} element(s)",
                            init_node.token or node.token,
                        )
                    coerced = []
                    for el in init_node.children:
                        applied, lit_err = self._coerce_literal(el, node.var_type)
                        if applied and lit_err:
                            self.invalid_type_error(lit_err, el.token or node.token)
                        coerced.append(applied)
                    if init_node.children and all(coerced):
                        initializer_type = declared_type
                elif init_node.node_type == NodeTypes.IDENTIFIER:
                    src = symbol_table.get(init_node.name)
                    if (
                        src is not None and len(src) > 3 and src[3] is not None
                        and node.array_size is not None and src[3] != node.array_size
                    ):
                        self.type_error(
                            f"Type mismatch for variable '{node.name}'. Expected {node.var_type}[{node.array_size}], "
                            f"got {src[0]}[{src[3]}]",
                            node.token,
                        )

            if init_node is not None and init_node.node_type == NodeTypes.MATCH_EXPRESSION:
                self._check_match_value_arms(init_node, declared_type, bool(node.is_nullable))

            if initializer_type:
                # Special case: initializing with null
                if initializer_type == "null":
                    if not node.is_nullable:
                        self.invalid_type_error(
                            f"Cannot initialize non-nullable variable '{node.name}' with null",
                            node.token,
                        )
                else:
                    # `declared_type` never carries a "?" (this check
                    # predates nullable-scalar support and compares the
                    # bare base type either way); strip a nullable
                    # initializer's own "?" before comparing so a
                    # nullable-scalar-returning call (e.g. `x: int32? =
                    # tryDivide(a, b);`) is accepted the same as a bare
                    # value would be -- see ast_to_fir.py's "Nullable
                    # scalars" section for how the "?" is actually used
                    # downstream.
                    init_base = (
                        initializer_type[:-1] if initializer_type.endswith("?") else initializer_type
                    )
                    # An unsuffixed literal takes the declared type
                    # (docs/reference/type_system.md, "Type Inference for
                    # Literals"); anything else must match exactly.
                    applied, lit_err = self._coerce_literal(node.children[0], declared_type)
                    if applied:
                        if lit_err:
                            self.invalid_type_error(lit_err, node.children[0].token or node.token)
                    elif declared_type != init_base:
                        # Strict: no implicit coercions between numeric families
                        self.type_error(
                            f"Type mismatch for variable '{node.name}'. Expected {declared_type}, got {initializer_type}",
                            node.token,
                        )
            # Add variable to symbol table for current scope (if not already done by resolve)
            symbol_table[node.name] = (node.var_type, node.is_array, node.is_nullable, node.array_size)

        elif node.node_type == NodeTypes.VARIABLE_ASSIGNMENT:
            var_info = symbol_table.get(node.name)
            assigned_type = child_types[0] if child_types else None
            if not var_info:
                # Already reported by resolve_variable_types; don't duplicate.
                return None
            else:
                var_type, is_array = var_info[0], var_info[1]
                is_nullable = var_info[2] if len(var_info) > 2 else False
                expected_type = f"{var_type}[]" if is_array else var_type
                if node.children and node.children[0].node_type == NodeTypes.MATCH_EXPRESSION:
                    self._check_match_value_arms(node.children[0], expected_type, is_nullable)
                if (
                    is_array and node.children and node.children[0].node_type == NodeTypes.IDENTIFIER
                    and len(var_info) > 3 and var_info[3] is not None
                ):
                    src = symbol_table.get(node.children[0].name)
                    if src is not None and len(src) > 3 and src[3] is not None and src[3] != var_info[3]:
                        self.type_error(
                            f"Type mismatch assigning to variable '{node.name}'. Expected "
                            f"{var_type}[{var_info[3]}], got {src[0]}[{src[3]}]",
                            node.token,
                        )
                if assigned_type:
                    if assigned_type == "null":
                        if not is_nullable:
                            self.invalid_type_error(
                                f"Cannot assign null to non-nullable variable '{node.name}'",
                                node.token,
                            )
                    else:
                        applied, lit_err = self._coerce_literal(node.children[0], expected_type)
                        if applied:
                            if lit_err:
                                self.invalid_type_error(lit_err, node.children[0].token or node.token)
                        elif expected_type != assigned_type:
                            # TODO: Implement type coercion rules
                            self.type_error(
                                f"Type mismatch assigning to variable '{node.name}'. Expected {expected_type}, got {assigned_type}",
                                node.token,
                            )

        elif node.node_type == NodeTypes.ARRAY_LITERAL:
            # All elements must share one type (docs/reference/arrays.md); a
            # later unsuffixed literal may take the first element's type.
            if len(node.children) > 1 and child_types[0] is not None:
                first_t = child_types[0]
                for el, el_t in zip(node.children[1:], child_types[1:]):
                    if el_t is None or el_t == first_t:
                        continue
                    applied, lit_err = self._coerce_literal(el, first_t)
                    if applied:
                        if lit_err:
                            self.invalid_type_error(lit_err, el.token or node.token)
                        continue
                    self.invalid_type_error(
                        f"Array literal elements must all have the same type: expected {first_t}, got {el_t}",
                        el.token or node.token,
                    )

        elif node.node_type == NodeTypes.MATCH_ARM:
            # A value-producing arm (an expression, not a block) carries the
            # type of its body; `_check_match_value_arms` compares it against
            # the context the whole match is used in.
            if node.children and node.children[0].node_type != NodeTypes.SCOPE:
                node._value_type = child_types[0]

        elif node.node_type == NodeTypes.ASSIGNMENT:
            # `lhs = rhs` where lhs is a field access or array element (a
            # plain `name = rhs` is a VARIABLE_ASSIGNMENT above).
            if len(node.children) == 2:
                lhs, rhs = node.children
                lhs_type, rhs_type = child_types[0], child_types[1]
                if lhs.node_type not in (
                    NodeTypes.FIELD_ACCESS, NodeTypes.ARRAY_ACCESS, NodeTypes.IDENTIFIER
                ):
                    self.invalid_expression_error(
                        "Invalid assignment target: the left side of '=' must be a variable, "
                        "a field, or an array element",
                        node.token,
                    )
                else:
                    lhs_nullable = True  # unknown nullability: do not reject null
                    if lhs.node_type == NodeTypes.FIELD_ACCESS and lhs.children:
                        owner_t = lhs.children[0].return_type or getattr(lhs.children[0], "var_type", None)
                        field_nodes = self._class_field_nodes.get(owner_t or "")
                        if field_nodes is not None:
                            for fnode in field_nodes:
                                if fnode.name == lhs.name:
                                    lhs_nullable = bool(fnode.is_nullable)
                                    break
                    kind, detail = self._assignability(
                        lhs_type, lhs_nullable, rhs, rhs_type, allow_subclass=False
                    )
                    if kind == "mismatch":
                        self.type_error(
                            f"Type mismatch in assignment. Expected {lhs_type}, got {rhs_type}",
                            node.token,
                        )
                    elif kind == "null":
                        self.invalid_type_error(
                            f"Cannot assign null to non-nullable {lhs.node_type.name.lower().replace('_', ' ')} of type {lhs_type}",
                            node.token,
                        )
                    elif kind == "range":
                        self.invalid_type_error(detail, rhs.token or node.token)

        elif node.node_type == NodeTypes.RETURN_STATEMENT:
            fn = self._enclosing_callable(node)
            if fn is not None and not getattr(fn, "is_constructor", False):
                declared = fn.return_type
                expr = node.children[0] if node.children else None
                if fn.node_type == NodeTypes.GENERATOR_DEFINITION:
                    pass  # generator `return` carries no value; yields are checked separately
                elif declared in (None, "void"):
                    if expr is not None:
                        self.invalid_type_error(
                            f"Cannot return a value from '{fn.name}': it is declared '-> void'",
                            node.token,
                        )
                elif expr is None:
                    if declared:
                        self.invalid_type_error(
                            f"'return' without a value in '{fn.name}', which returns {declared}",
                            node.token,
                        )
                else:
                    self._check_returned_value(fn, declared, expr, child_types[0], node)

        elif node.node_type == NodeTypes.YIELD_STATEMENT:
            fn = self._enclosing_callable(node)
            if fn is not None and fn.node_type != NodeTypes.GENERATOR_DEFINITION:
                self.invalid_type_error(
                    "'yield' can only be used inside a generator function (declared '-> generator<T>')",
                    node.token,
                )
            elif fn is not None and node.children:
                yield_t = getattr(fn, "yield_type", None)
                kind, detail = self._assignability(
                    yield_t, False, node.children[0], child_types[0]
                )
                if kind == "mismatch":
                    self.invalid_type_error(
                        f"Cannot yield {child_types[0]} from generator '{fn.name}' of generator<{yield_t}>",
                        node.token,
                    )
                elif kind == "null":
                    self.invalid_type_error(
                        f"Cannot yield null from generator '{fn.name}' of generator<{yield_t}>",
                        node.token,
                    )
                elif kind == "range":
                    self.invalid_type_error(detail, node.children[0].token or node.token)

        elif node.node_type == NodeTypes.FOR_IN_STATEMENT:
            if len(node.children) >= 2:
                coll = node.children[1]
                coll_t = child_types[1]
                if coll_t is not None and not (
                    coll_t.endswith("[]") or coll_t == "string" or coll_t.startswith("generator<")
                ):
                    self.invalid_type_error(
                        f"Cannot iterate over a value of type {coll_t}: 'for ... in' requires an "
                        f"array, a string, or a generator",
                        coll.token or node.token,
                    )

        elif node.node_type == NodeTypes.COMPOUND_ASSIGNMENT:
            # `x OP= expr` is `x = x OP expr`: the target must exist, and the
            # operator must be valid for (type of x, type of expr) exactly as
            # the equivalent binary expression would be. Without this check a
            # mismatch only surfaced later as an internal FIR verifier error.
            var_info = symbol_table.get(node.name)
            if not var_info:
                self.undefined_identifier_error(node.name, node.token)
                return None
            right_type = child_types[0] if child_types else None
            if right_type is None:
                return None
            left_type = f"{var_info[0]}[]" if var_info[1] else var_info[0]
            op_symbol = {
                "ADD_ASSIGN": "+",
                "SUBTRACT_ASSIGN": "-",
                "MULTIPLY_ASSIGN": "*",
                "DIVIDE_ASSIGN": "/",
                "MODULO_ASSIGN": "%",
                "POWER_ASSIGN": "**",
            }.get(getattr(node.token, "type", ""), "+")
            same = left_type == right_type
            is_param = left_type in self._current_type_params
            if op_symbol == "+" and same and left_type == "string":
                ok = True
            elif op_symbol == "%":
                ok = same and (
                    left_type in self.INTEGER_TYPES
                    or (is_param and not self._type_param_is_float_only(left_type))
                )
            else:
                float_types = {"float", "double", "float32", "float64", "float128"}
                ok = same and (
                    left_type in self.INTEGER_TYPES or left_type in float_types or is_param
                )
            if not ok:
                self.invalid_type_error(
                    f"Operator '{op_symbol}=' not supported between types {left_type} and {right_type}",
                    node.token,
                )
            elif op_symbol in ("/", "%") and left_type in INT_RANGES and self._const_int(node.children[0]) == 0:
                self.constant_division_by_zero_error(
                    f"Division by zero: the right operand of '{op_symbol}=' is the constant 0", node.token
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

            # String concatenation: both operands must be string; use 'as string' for explicit conversion
            if op == "+":
                if left_type == "string" and right_type == "string":
                    node_type_str = "string"
                elif left_type == "string" or right_type == "string":
                    non_str = right_type if left_type == "string" else left_type
                    self.invalid_type_error(
                        f"Cannot implicitly convert '{non_str}' to 'string'; "
                        f"use '(value as string)' for explicit conversion",
                        node.token,
                    )
                elif left_type == right_type and left_type in integer_types:
                    node_type_str = left_type
                elif left_type == right_type and left_type in float_types:
                    node_type_str = left_type
                # Allow if both are the same type parameter (assumed to be numeric via constraints)
                elif left_type == right_type and is_left_type_param:
                    node_type_str = left_type
                else:
                    self.invalid_type_error(
                        f"Operator '{op}' not supported between types {left_type} and {right_type}",
                        node.token,
                    )
            elif op in ("-", "*", "/", "**"):
                if left_type == right_type and left_type in integer_types:
                    node_type_str = left_type
                elif left_type == right_type and left_type in float_types:
                    node_type_str = left_type
                # Allow if both are the same type parameter (assumed to be numeric via constraints)
                elif left_type == right_type and is_left_type_param:
                    node_type_str = left_type
                else:
                    self.invalid_type_error(
                        f"Operator '{op}' not supported between types {left_type} and {right_type}",
                        node.token,
                    )
            elif op in ("&&", "||"):
                if left_type == "bool" and right_type == "bool":
                    node_type_str = "bool"
                else:
                    self.invalid_type_error(
                        f"Operator '{op}' requires bool operands, got {left_type} and {right_type}",
                        node.token,
                    )
            elif op == "%":
                if left_type == right_type and left_type in integer_types:
                    node_type_str = left_type
                # Allow if both are the same type parameter (assumed to be numeric via constraints),
                # unless its constraint admits only floating-point types.
                elif (
                    left_type == right_type
                    and is_left_type_param
                    and not self._type_param_is_float_only(left_type)
                ):
                    node_type_str = left_type
                else:
                    self.invalid_type_error(
                        f"Operator '{op}' requires integer operands of the same type, got {left_type} and {right_type}",
                        node.token,
                    )
            else:
                self.invalid_type_error(f"Unsupported binary operator '{op}'", node.token)

            node.return_type = node_type_str
            if node_type_str is not None and len(node.children) == 2:
                self._fold_binary_constant(node, node.children[0], node.children[1], op, node_type_str)

        elif node.node_type == NodeTypes.UNARY_EXPRESSION:
            op = node.name
            
            # Increment/decrement operators (++/--) have no children - they operate on the identifier stored in node.token
            if op in ("++", "--"):
                # The variable being incremented/decremented is in node.token
                var_name = node.token.value if node.token and hasattr(node.token, 'value') else None
                if var_name:
                    var_info = symbol_table.get(var_name)
                    if var_info:
                        var_type, is_array = var_info[0], var_info[1]
                        # Increment/decrement only work on integer types
                        if var_type in self.INTEGER_TYPES:
                            node_type_str = var_type
                        else:
                            self.type_error(f"Operator '{op}' requires an integer variable, got {var_type}", node.token)
                    else:
                        self.undefined_identifier_error(var_name, node.token)
                return node_type_str
            
            # Unary +/- operators have a child operand
            if not child_types:
                self.invalid_type_error(f"Unary operator '{op}' missing operand", node.token)
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
                    self.invalid_type_error(
                        f"Unary operator '{op}' requires numeric operand, got {operand_type}",
                        node.token,
                    )
                    node_type_str = None
            elif op == "!":
                if operand_type == "bool":
                    node_type_str = "bool"
                else:
                    self.invalid_type_error(
                        f"Unary operator '{op}' requires bool operand, got {operand_type}",
                        node.token,
                    )
                    node_type_str = None
            else:
                self.invalid_type_error(f"Unsupported unary operator '{op}'", node.token)
                node_type_str = None

            node.return_type = node_type_str
            if op in ("+", "-") and node_type_str in INT_RANGES and len(node.children) == 1:
                cv = self._const_int(node.children[0])
                if cv is not None:
                    self._check_constant_range(node, -cv if op == "-" else cv, node_type_str)

        elif node.node_type == NodeTypes.EQUALITY_EXPRESSION:  # ==, !=
            left_type = child_types[0]
            right_type = child_types[1]
            op = node.name

            if left_type is None or right_type is None:
                return None

            # Allow comparison between same-type numerics, string==string, bool==bool,
            # with null, or between two values of the same type parameter (assumed
            # comparable via constraints; deferred to monomorphization, same as the
            # BINARY_EXPRESSION/RELATIONAL_EXPRESSION type-parameter allowances above).
            integer_types = self.INTEGER_TYPES
            float_types = {"float32", "float64", "float128"}
            is_type_param = left_type in self._current_type_params
            if (
                (left_type == right_type and (left_type in integer_types or left_type in float_types))
                or (left_type == right_type and left_type in {"string", "bool"})
                or (left_type == "null" or right_type == "null")
                or (left_type == right_type and is_type_param)
            ):
                node_type_str = "bool"
            else:
                self.invalid_type_error(
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
                self.invalid_type_error(
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
                    self.invalid_type_error(
                        f"Cannot cast array type {expr_type} to {target_type}",
                        node.token,
                    )
                    return None
            elif isinstance(target_type, str) and target_type.endswith("[]"):
                self.invalid_type_error(
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
                self.invalid_type_error(
                    f"Cannot cast to unknown or non-numeric type {target_type}",
                    node.token,
                )
                return None
            elif expr_type not in integer_types and expr_type not in float_types and expr_type != "bool" and expr_type != "string":
                self.invalid_type_error(
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
                        self.invalid_type_error(
                            f"Generic function '{func_name}' expects {len(type_params)} type arguments, got {len(node.type_args)}",
                            node.token,
                        )
                else:
                    # Infer type arguments from call arguments
                    inferred = self._infer_generic_type_args(func_name, [t for t in child_types if t is not None])
                    if inferred is None:
                        self.invalid_type_error(
                            f"Could not infer type arguments for generic function '{func_name}'",
                            node.token,
                        )
                        node.type_args = []
                        # The call has no usable type: leave it untyped so the
                        # enclosing declaration/argument doesn't report a
                        # second, derived mismatch for the same call.
                        node.return_type = None
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
                                self.invalid_type_error(
                                    f"Type '{concrete_type}' does not satisfy constraint '{constraint}' for type parameter '{tp}'",
                                    node.token,
                                )
                    
                    # Set return type by substituting type parameters
                    generic_return_type = self.user_functions.get(func_name)
                    if generic_return_type:
                        # Create type substitution map
                        type_subst = dict(zip(type_params, node.type_args))
                        # Substitute return type if it's a type parameter,
                        # including a bare type parameter used as an array
                        # element type (e.g. "T[]", for generic intrinsics
                        # like fs_rt_array_new<T> that return T[]).
                        if generic_return_type in type_subst:
                            node.return_type = type_subst[generic_return_type]
                            node_type_str = node.return_type
                        elif generic_return_type.endswith("[]") and generic_return_type[:-2] in type_subst:
                            node.return_type = type_subst[generic_return_type[:-2]] + "[]"
                            node_type_str = node.return_type
                        else:
                            node.return_type = generic_return_type
                            node_type_str = generic_return_type
            
            if func_name in self._local_functions and func_name not in self.user_types:
                self._check_local_function_call(node, child_types)
            elif (
                not self.defer_undefined_identifiers
                and "<" not in func_name
                and func_name not in self.builtin_functions
                and not self._is_compiler_intrinsic(func_name)
                and func_name not in self.user_functions
                and func_name not in self.generic_functions
                and func_name not in self.user_types
                and func_name not in self.generic_class_templates
                and func_name != self._current_generic_class_name
            ):
                # Never defined in this file (and no imports could supply
                # it). The statement form is reported by the parser; this
                # covers a call inside an expression.
                if func_name in symbol_table:
                    self.invalid_type_error(
                        f"'{func_name}' is a variable, not a function; it cannot be called",
                        node.token,
                    )
                else:
                    self.invalid_expression_error(
                        f"Function '{func_name}' is not defined", node.token
                    )

            expected_arg_count = -1  # Use -1 for variable args like print
            expected_arg_types = []  # Define expected types for builtins

            if func_name == "print":
                expected_arg_count = 1  # Simplified: assumes 1 arg for now
                # Allow printing any basic type
            elif func_name in ("toInt", "toBool", "toString", "toChar"):
                expected_arg_count = 1
                # Allow conversion from reasonable types (simplified check)

            if expected_arg_count != -1 and len(child_types) != expected_arg_count:
                self.invalid_type_error(
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
                        self.invalid_type_error(
                            f"Argument {i+1} for function '{func_name}' expected type {expected_arg_types[i]}, got {arg_type}",
                            node.children[i].token,
                        )

            # Return type is already set in the node for builtins during parsing
            # Constructors: calling a class name acts as a constructor call.
            if func_name in self.user_types:
                # A bare `ClassName(args)` call must resolve against the
                # class's real declared constructor (self.user_methods),
                # same as `new ClassName(args)` (NodeTypes.CONSTRUCTOR_CALL,
                # below) already does -- not against field order. Every
                # class in current firescript has an explicit constructor
                # (see docs/reference/classes.md); the field-order fallback
                # below is only reachable for a class with no constructor
                # at all, which "new" reports as "No constructor defined".
                ctor_sig = self.user_methods.get(func_name, {}).get(func_name)
                if ctor_sig is not None:
                    expected_params = ctor_sig.get("params", [])
                    if len(child_types) != len(expected_params):
                        self.invalid_type_error(
                            f"Constructor '{func_name}' expected {len(expected_params)} args, got {len(child_types)}",
                            node.token,
                        )
                    else:
                        for i, (arg_t, exp_t) in enumerate(zip(child_types, expected_params)):
                            # See the matching comment on the field-order
                            # fallback below: `null` isn't tracked in
                            # expected_params' type strings.
                            if arg_t != "null" and arg_t != exp_t:
                                self.invalid_type_error(
                                    f"Constructor '{func_name}' arg {i+1} expected {exp_t}, got {arg_t}",
                                    node.children[i].token if i < len(node.children) else node.token,
                                )
                else:
                    # Validate against class fields order
                    fields_map = self.user_classes.get(func_name, {})
                    field_order = list(fields_map.items())  # [(name, type), ...] insertion order preserved
                    if len(child_types) != len(field_order):
                        self.invalid_type_error(
                            f"Constructor '{func_name}' expected {len(field_order)} args, got {len(child_types)}",
                            node.token,
                        )
                    else:
                        for i, (arg_t, (_, exp_t)) in enumerate(zip(child_types, field_order)):
                            # `null` is not tracked in field_order's type
                            # strings (they never carry a nullable "?" -- see
                            # ast_to_fir.py's "Nullable scalars" section for
                            # where that's actually enforced), so it can't be
                            # strictly compared here; trust the later FIR-level
                            # check instead of rejecting a legitimately
                            # nullable field's null argument.
                            if arg_t != "null" and arg_t != exp_t:
                                self.invalid_type_error(
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
                if method_name in ("append", "insert", "pop", "clear"):
                    self.invalid_type_error(
                        f"Arrays are fixed-size; method '{method_name}' is not supported",
                        node.token,
                    )
                else:
                    self._dispatch_builtin_method(node, "array", elem_type, object_type, method_name, arg_types)
            elif object_type == "string":
                self._dispatch_builtin_method(node, "string", None, object_type, method_name, arg_types)
            else:
                # Class instance methods
                if object_type in self.user_methods and method_name in self.user_methods[object_type]:
                    sig = self.user_methods[object_type][method_name]
                    node._signature_checked = True
                    if bool(sig.get("is_static", False)):
                        self.invalid_type_error(
                            f"Static method '{method_name}' must be called on type '{object_type}', not an instance",
                            node.token,
                        )
                        return None
                    expected_params = sig.get("params", [])
                    if len(arg_types) != len(expected_params):
                        self.invalid_type_error(
                            f"Method '{method_name}' for '{object_type}' expected {len(expected_params)} args, got {len(arg_types)}",
                            node.token,
                        )
                    else:
                        for i, (arg_t, exp_t) in enumerate(zip(arg_types, expected_params)):
                            # See the matching comment on the constructor
                            # positional-args check above: `null` isn't
                            # tracked in expected_params' type strings.
                            if arg_t != "null" and arg_t != exp_t:
                                self.invalid_type_error(
                                    f"Argument {i+1} for method '{method_name}' expected type {exp_t}, got {arg_t}",
                                    node.children[i+1].token if len(node.children) > i+1 else node.token,
                                )
                    node.return_type = sig.get("return")
                else:
                    # When imports are pending, defer method lookup for unresolved
                    # imported types (including composite generic types like
                    # Option<string>) until after import resolution/merge.
                    # Also defer a self-referential call inside the generic
                    # class's own body (e.g. `this.isSome()` inside one of
                    # Option<T?>'s own methods) -- self.user_methods isn't
                    # populated for the enclosing class until its whole body
                    # finishes parsing, independent of defer_undefined_
                    # identifiers (which is about *other*, not-yet-merged
                    # modules, not this same-file timing gap).
                    if (
                        self.defer_undefined_identifiers
                        and object_type
                        and (
                            "<" in object_type
                            or object_type not in self.user_methods
                        )
                    ) or object_type == self._current_generic_class_name:
                        pass  # Will be resolved after import merge / class body completes
                    else:
                        self.invalid_type_error(
                            f"Methods not supported for type {object_type}",
                            node.children[0].token,
                        )

        elif node.node_type == NodeTypes.SUPER_CALL:
            enclosing_class = getattr(node, "enclosing_class", None)
            super_class = getattr(node, "super_class", None)
            in_ctor = bool(getattr(node, "in_constructor", False))

            if not enclosing_class:
                self.invalid_type_error("'super' can only be used inside a class method", node.token)
                return None
            if not super_class:
                self.invalid_type_error(f"Class '{enclosing_class}' has no base class; cannot use 'super'", node.token)
                return None

            if not in_ctor:
                self.invalid_type_error("'this.super(...)' is only valid inside a constructor", node.token)
                return None

            # Validate constructor exists on base
            if super_class not in self.user_methods or super_class not in self.user_methods[super_class]:
                self.invalid_type_error(f"No constructor defined for base type '{super_class}'", node.token)
                return None
            sig = self.user_methods[super_class][super_class]
            expected_params = sig.get("params", [])
            if len(child_types) != len(expected_params):
                self.invalid_type_error(
                    f"Super constructor '{super_class}' expected {len(expected_params)} args, got {len(child_types)}",
                    node.token,
                )
            else:
                for i, (arg_t, exp_t) in enumerate(zip(child_types, expected_params)):
                    # See the matching comment on the constructor
                    # positional-args check above.
                    if arg_t != "null" and arg_t != exp_t:
                        self.invalid_type_error(
                            f"Super constructor '{super_class}' arg {i+1} expected {exp_t}, got {arg_t}",
                            node.children[i].token if i < len(node.children) else node.token,
                        )

            node.return_type = "void"
            node_type_str = "void"
        elif node.node_type == NodeTypes.TYPE_METHOD_CALL:
            class_name = getattr(node, "class_name", None)
            method_name = node.name
            # class_name is either a plain class ("Widget"), a generic
            # template's bare name ("Box", from the no-type-args call form
            # Box.make(5)), or an explicit composite instantiation
            # ("Box<int32>", from Box<int32>.make(5) -- base_class_name
            # strips it to "Box" for the template/method lookup, same as
            # ast_to_fir.py's _find_method_def already does for receivers).
            base_class_name = class_name.split("<", 1)[0] if class_name and "<" in class_name else class_name
            explicit_type_args = list(getattr(node, "type_args", []) or [])
            sig = None
            if base_class_name and base_class_name in self.user_methods:
                sig = self.user_methods[base_class_name].get(method_name)
            is_generic_template = False
            if sig is None and base_class_name and base_class_name in self.generic_class_templates:
                # A generic class's bare template name is deliberately
                # absent from self.user_methods (declarations.py registers
                # it under generic_class_templates instead, popping any
                # user_methods entry) -- look the method up directly on the
                # template's own AST node, computing the same signature
                # shape declarations.py would have registered.
                sig = self._generic_template_method_sig(base_class_name, method_name)
                is_generic_template = sig is not None
            if sig is None:
                # Deferred-import mode: base_class_name may be a generic
                # class imported from another, not-yet-merged module (e.g.
                # `Option<int32>.None()`, where "Option" isn't in
                # user_methods/generic_class_templates until after merge) --
                # same reasoning as the FIELD_ACCESS deferral above. Leave
                # node.return_type unset (VARIABLE_DECLARATION's type-match
                # check is a no-op when initializer_type is falsy) rather
                # than rejecting a call that will resolve correctly once
                # imports are merged; the real check happens then.
                class_name_known = bool(
                    base_class_name
                    and (
                        base_class_name in self.user_types
                        or base_class_name in self.user_methods
                        or base_class_name in self.generic_class_templates
                    )
                )
                if self.defer_undefined_identifiers and base_class_name and not class_name_known:
                    return None
                self.invalid_type_error(f"Unknown constructor or static method '{method_name}' for type '{class_name}'", node.token)
                return None
            is_static = bool(sig.get("is_static", False))
            is_constructor = sig.get("return") == base_class_name
            if not is_static and not is_constructor:
                self.invalid_type_error(f"'{method_name}' is neither a static method nor a constructor for type '{class_name}'", node.token)
                return None
            # Validate args. For a generic template, a param/return type may
            # itself be a bare type parameter (e.g. "T") -- type inference
            # and substitution happen later, in ast_to_fir.py (mirroring how
            # a generic class's constructor is already handled), so skip
            # the exact-type-match check here rather than rejecting a
            # legitimately-substitutable argument.
            expected_params = sig.get("params", [])
            if len(child_types) != len(expected_params):
                self.invalid_type_error(
                    f"Call '{class_name}.{method_name}' expected {len(expected_params)} args, got {len(child_types)}",
                    node.token,
                )
            elif not is_generic_template:
                for i, (arg_t, exp_t) in enumerate(zip(child_types, expected_params)):
                    # See the matching comment on the constructor
                    # positional-args check above.
                    if arg_t != "null" and arg_t != exp_t:
                        self.invalid_type_error(
                            f"Call '{class_name}.{method_name}' arg {i+1} expected {exp_t}, got {arg_t}",
                            node.children[i].token if i < len(node.children) else node.token,
                        )
            if is_static:
                ret = sig.get("return")
                if is_generic_template and ret:
                    # Substitute the class's type arguments into the
                    # declared (unsubstituted) return type, e.g.
                    # "Box<T>" -> "Box<int32>". Prefer the explicit
                    # arguments from Box<int32>.make(5) when present;
                    # otherwise infer them from this call's argument types
                    # (there's no receiver instance to read concrete type
                    # arguments from, unlike an ordinary instance method
                    # call -- mirrors _infer_generic_type_args' matching
                    # for a generic *function* call). ast_to_fir.py's FIR
                    # conversion performs the equivalent substitution
                    # again (it can't see this parser-level result), plus
                    # the monomorphization dispatch this can't do.
                    type_params = self.generic_class_params.get(base_class_name, [])
                    if explicit_type_args:
                        type_map = dict(zip(type_params, explicit_type_args))
                    else:
                        type_map = {}
                        for param_t, arg_t in zip(expected_params, child_types):
                            if param_t in type_params and arg_t and arg_t != "null":
                                type_map.setdefault(param_t, arg_t)
                    if ret in type_map:
                        ret = type_map[ret]
                    elif "<" in ret and ret.endswith(">"):
                        base, args_text = ret.split("<", 1)
                        inner = [type_map.get(a.strip(), a.strip()) for a in args_text[:-1].split(",")]
                        ret = f"{base}<{', '.join(inner)}>"
                node.return_type = ret
                node_type_str = ret
            else:
                node.return_type = base_class_name
                node_type_str = base_class_name

            node_type_str = node.return_type
        elif node.node_type == NodeTypes.CONSTRUCTOR_CALL:
            class_name = node.name
            # Look up a constructor method whose name equals the class name
            # (for a generic instantiation such as `Box<int32>` the
            # constructor is declared under the bare template name `Box`).
            base_ctor_name = class_name.split("<", 1)[0]
            class_methods = self.user_methods.get(class_name, {})
            sig = class_methods.get(class_name) or class_methods.get(base_ctor_name)
            if sig is None:
                self.invalid_type_error(f"No constructor defined for type '{class_name}'", node.token)
                return None
            expected_params = sig.get("params", [])
            if len(child_types) != len(expected_params):
                self.invalid_type_error(
                    f"Constructor '{class_name}' expected {len(expected_params)} args, got {len(child_types)}",
                    node.token,
                )
            else:
                for i, (arg_t, exp_t) in enumerate(zip(child_types, expected_params)):
                    # See the matching comment on the positional-field-
                    # construction check above: `null` isn't tracked in
                    # expected_params' type strings.
                    if arg_t != "null" and arg_t != exp_t:
                        self.invalid_type_error(
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
                    self.invalid_type_error(f"Type '{obj_type}' has no field '{field_name}'", node.token)
                    node_type_str = None
            elif obj_type in self.generic_class_templates:
                # Inside a generic class template body: look up field from template nodes
                template_fields: dict[str, str] = {}
                for ch in (self._class_field_nodes.get(obj_type) or []):
                    if ch.node_type == NodeTypes.CLASS_FIELD:
                        template_fields[ch.name] = (ch.var_type or "int32") + ("[]" if ch.is_array else "")
                if field_name in template_fields:
                    node.return_type = template_fields[field_name]
                    node_type_str = template_fields[field_name]
                else:
                    self.invalid_type_error(f"Type '{obj_type}' has no field '{field_name}'", node.token)
                    node_type_str = None
            else:
                # In deferred-import mode a class type -- composite generic
                # ("Pair<int32, string>") or a plain class imported from
                # another module ("Widget") -- may not be registered until
                # imports are fully merged. Suppress the error so parsing
                # can complete; FIR conversion resolves the real field type
                # afterward from the fully-merged class definitions,
                # independent of this parser-level check. Only a genuine
                # primitive type (never a valid class-field-access target)
                # is still reported immediately.
                primitive_types = self.INTEGER_TYPES | {"float32", "float64", "float128", "bool", "char", "string", "void"}
                if self.defer_undefined_identifiers and obj_type and obj_type not in primitive_types:
                    node_type_str = None
                else:
                    self.invalid_type_error(f"Field access on non-class type '{obj_type}'", node.token)
                    node_type_str = None

        elif node.node_type == NodeTypes.ARRAY_ACCESS:
            array_type = child_types[0]
            index_type = child_types[1]

            if array_type is None or index_type is None:
                return None

            if not array_type.endswith("[]"):
                self.invalid_type_error(
                    f"Cannot apply index operator [] to non-array type {array_type}",
                    node.children[0].token,
                )
            elif index_type not in self.INTEGER_TYPES:
                self.invalid_type_error(
                    f"Array index must be an integer type, got {index_type}",
                    node.children[1].token,
                )
            else:
                node_type_str = array_type[:-2]  # The element type
                self._check_constant_index(node, symbol_table)

            node.return_type = node_type_str

        elif (
            node.node_type == NodeTypes.IF_STATEMENT
            or node.node_type == NodeTypes.WHILE_STATEMENT
        ):
            condition_type = child_types[0]
            if condition_type is None:
                return None
            if condition_type != "bool":
                self.invalid_type_error(
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
                if cur.node_type == NodeTypes.WHILE_STATEMENT or cur.node_type == NodeTypes.FOR_STATEMENT or cur.node_type == NodeTypes.FOR_IN_STATEMENT:
                    in_loop = True
                    break
                cur = cur.parent
            if not in_loop:
                self.invalid_type_error(f"'{node.name}' statement not within a loop", node.token)

        # --- Determine node's type string based on checks ---
        # If node_type_str wasn't set explicitly, try getting it generally
        if node_type_str is None:
            node_type_str = self._get_node_type(node, symbol_table)

        return node_type_str
