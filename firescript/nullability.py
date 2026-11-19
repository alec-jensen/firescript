"""Nullable-to-non-nullable conversion check (FS-SEM-0018).

A value of type `T?` may not be assigned, passed, returned or used to
initialize a position that requires `T`, unless the compiler can prove it is
not null at that point. The proof is a small flow-sensitive narrowing rule
(see docs/reference/type_system.md, "Narrowing"):

* inside the true branch of `if (x != null)` (and the right operand of
  `x != null && ...`, and the body of `while (x != null)`), `x` is non-null;
* inside the false branch of `if (x == null)` (and the right operand of
  `x == null || ...`), `x` is non-null;
* after `if (x == null) { return ...; }` (the then-branch always leaves the
  enclosing flow: return / break / continue), `x` is non-null for the rest of
  the enclosing block, and symmetrically for `if (x != null) {...} else {
  return; }`.

`x` may be a local, a parameter, a global, or a field path such as
`this.value` / `obj.f`. Narrowing of a path ends at the first write to it
(or to a prefix of it), at a redeclaration of its root, and -- for field
paths -- at any call that receives the owning object (a method call on it,
or passing it as an argument), since the callee may reassign the field.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from enums import NodeTypes
from errors import NullableConversionError
from parser.ast_node import ASTNode

# (path, include_self): kill `path` itself (when include_self) and every
# narrowed path below it ("path.field...").
_Kill = Tuple[str, bool]

_FUNCTION_NODES = (
    NodeTypes.FUNCTION_DEFINITION,
    NodeTypes.GENERATOR_DEFINITION,
    NodeTypes.CLASS_METHOD_DEFINITION,
)


def _is_null_literal(node: Optional[ASTNode]) -> bool:
    return (
        node is not None
        and node.node_type == NodeTypes.LITERAL
        and (getattr(node, "return_type", None) == "null" or node.name == "null")
    )


def _path_of(node: Optional[ASTNode]) -> Optional[str]:
    if node is None:
        return None
    if node.node_type == NodeTypes.IDENTIFIER:
        return node.name
    if node.node_type == NodeTypes.FIELD_ACCESS and node.children:
        owner = _path_of(node.children[0])
        return f"{owner}.{node.name}" if owner is not None else None
    return None


def _base_type(t: Optional[str]) -> Optional[str]:
    """'Box<int32>?' -> 'Box'; None for arrays and unknown types."""
    if not t:
        return None
    if t.endswith("?"):
        t = t[:-1]
    if t.endswith("[]"):
        return None
    if "<" in t:
        t = t[: t.index("<")]
    return t


class NullabilityChecker:
    def __init__(self, analyzer) -> None:
        self.a = analyzer
        # name -> (type, is_array, nullable)
        self.scopes: List[Dict[str, Tuple[Optional[str], bool, bool]]] = [{}]
        self.narrowed: Set[str] = set()
        self.class_name: Optional[str] = None
        self.fn: Optional[ASTNode] = None

    # -- entry ------------------------------------------------------------

    def run(self, root: ASTNode) -> None:
        for child in root.children:
            if child.node_type == NodeTypes.VARIABLE_DECLARATION:
                self._declare(child)
        for child in root.children:
            self._walk(child)

    # -- scopes / bindings ------------------------------------------------

    def _declare(self, decl: ASTNode) -> None:
        self.scopes[-1][decl.name] = (decl.var_type, bool(decl.is_array), bool(decl.is_nullable))

    def _lookup(self, name: str) -> Optional[Tuple[Optional[str], bool, bool]]:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    # -- narrowing helpers --------------------------------------------------

    def _kill(self, kills: Set[_Kill]) -> None:
        for path, include_self in kills:
            prefix = path + "."
            self.narrowed = {
                n for n in self.narrowed
                if not ((include_self and n == path) or n.startswith(prefix))
            }

    def _writes(self, node: Optional[ASTNode]) -> Set[_Kill]:
        out: Set[_Kill] = set()
        if node is None:
            return out
        nt = node.node_type
        if nt in (NodeTypes.VARIABLE_ASSIGNMENT, NodeTypes.COMPOUND_ASSIGNMENT, NodeTypes.VARIABLE_DECLARATION):
            out.add((node.name, True))
        elif nt == NodeTypes.ASSIGNMENT and node.children:
            p = _path_of(node.children[0])
            if p is not None:
                out.add((p, True))
        elif nt == NodeTypes.METHOD_CALL and node.children:
            p = _path_of(node.children[0])
            if p is not None:
                out.add((p, False))
        if nt in (NodeTypes.FUNCTION_CALL, NodeTypes.METHOD_CALL, NodeTypes.CONSTRUCTOR_CALL, NodeTypes.TYPE_METHOD_CALL):
            args = node.children[1:] if nt == NodeTypes.METHOD_CALL else node.children
            for arg in args:
                p = _path_of(arg)
                if p is not None:
                    out.add((p, False))
        for child in node.children:
            out |= self._writes(child)
        return out

    def _true_set(self, c: Optional[ASTNode]) -> Set[str]:
        """Paths known non-null when `c` evaluates to true."""
        if c is None:
            return set()
        if c.node_type == NodeTypes.EQUALITY_EXPRESSION and c.name == "!=" and len(c.children) == 2:
            return self._null_compared_path(c)
        if c.node_type == NodeTypes.BINARY_EXPRESSION and len(c.children) == 2:
            if c.name == "&&":
                return self._true_set(c.children[0]) | self._true_set(c.children[1])
            if c.name == "||":
                return self._true_set(c.children[0]) & self._true_set(c.children[1])
        if c.node_type == NodeTypes.UNARY_EXPRESSION and c.name == "!" and c.children:
            return self._false_set(c.children[0])
        return set()

    def _false_set(self, c: Optional[ASTNode]) -> Set[str]:
        """Paths known non-null when `c` evaluates to false."""
        if c is None:
            return set()
        if c.node_type == NodeTypes.EQUALITY_EXPRESSION and c.name == "==" and len(c.children) == 2:
            return self._null_compared_path(c)
        if c.node_type == NodeTypes.BINARY_EXPRESSION and len(c.children) == 2:
            if c.name == "||":
                return self._false_set(c.children[0]) | self._false_set(c.children[1])
            if c.name == "&&":
                return self._false_set(c.children[0]) & self._false_set(c.children[1])
        if c.node_type == NodeTypes.UNARY_EXPRESSION and c.name == "!" and c.children:
            return self._true_set(c.children[0])
        return set()

    @staticmethod
    def _null_compared_path(c: ASTNode) -> Set[str]:
        left, right = c.children
        if _is_null_literal(right):
            p = _path_of(left)
        elif _is_null_literal(left):
            p = _path_of(right)
        else:
            p = None
        return {p} if p is not None else set()

    # -- type / nullability of expressions ---------------------------------

    def _class_of(self, node: Optional[ASTNode]) -> Optional[str]:
        """Class name of the value `node` evaluates to (None if unknown)."""
        if node is None:
            return None
        nt = node.node_type
        if nt == NodeTypes.IDENTIFIER:
            if node.name == "this":
                return self.class_name
            info = self._lookup(node.name)
            if info is not None:
                t, is_array, _ = info
                return None if is_array else _base_type(t)
            return None
        if nt == NodeTypes.FIELD_ACCESS and node.children:
            field = self._find_field(self._class_of(node.children[0]), node.name)
            if field is not None and not field.is_array:
                return _base_type(field.var_type)
            return None
        if nt == NodeTypes.CONSTRUCTOR_CALL:
            return _base_type(node.name)
        if nt == NodeTypes.FUNCTION_CALL and node.name in self.a.class_defs:
            return _base_type(node.name)
        rt = getattr(node, "return_type", None)
        return _base_type(rt) if isinstance(rt, str) else None

    def _find_field(self, class_name: Optional[str], field: str) -> Optional[ASTNode]:
        seen: Set[str] = set()
        cur = class_name
        while cur and cur not in seen:
            seen.add(cur)
            cdef = self.a.class_defs.get(cur)
            if cdef is None:
                return None
            for child in cdef.children:
                if child.node_type == NodeTypes.CLASS_FIELD and child.name == field:
                    return child
            cur = getattr(cdef, "base_class", None)
        return None

    def _find_method(self, class_name: Optional[str], method: str) -> Optional[ASTNode]:
        seen: Set[str] = set()
        cur = class_name
        while cur and cur not in seen:
            seen.add(cur)
            m = self.a.method_defs.get((cur, method))
            if m is not None:
                return m
            cdef = self.a.class_defs.get(cur)
            cur = getattr(cdef, "base_class", None) if cdef is not None else None
        return None

    def _callee_def(self, node: ASTNode) -> Optional[ASTNode]:
        nt = node.node_type
        if nt == NodeTypes.FUNCTION_CALL:
            base = _base_type(node.name) or node.name
            fdef = self.a.function_defs.get(node.name) or self.a.function_defs.get(base)
            if fdef is not None:
                return fdef
            if base in self.a.class_defs:
                return self._find_method(base, base)
            return None
        if nt == NodeTypes.CONSTRUCTOR_CALL:
            return self.a.method_defs.get((_base_type(node.name), _base_type(node.name)))
        if nt == NodeTypes.METHOD_CALL and node.children:
            return self._find_method(self._class_of(node.children[0]), node.name)
        if nt == NodeTypes.TYPE_METHOD_CALL:
            cname = _base_type(getattr(node, "class_name", None))
            return self._find_method(cname, node.name) if cname else None
        return None

    def _is_nullable_expr(self, node: Optional[ASTNode]) -> Optional[str]:
        """A description of `node` if it is a possibly-null `T?` value that is
        not proven non-null here, else None."""
        if node is None:
            return None
        nt = node.node_type
        if nt == NodeTypes.IDENTIFIER:
            if node.name == "this":
                return None
            info = self._lookup(node.name)
            if info is not None and info[2] and node.name not in self.narrowed:
                return f"'{node.name}'"
            return None
        if nt == NodeTypes.FIELD_ACCESS and node.children:
            field = self._find_field(self._class_of(node.children[0]), node.name)
            if field is not None and field.is_nullable:
                path = _path_of(node)
                if path is None or path not in self.narrowed:
                    return f"'{path or node.name}'"
            return None
        if nt in (NodeTypes.FUNCTION_CALL, NodeTypes.METHOD_CALL, NodeTypes.TYPE_METHOD_CALL, NodeTypes.CONSTRUCTOR_CALL):
            if nt == NodeTypes.CONSTRUCTOR_CALL:
                return None
            d = self._callee_def(node)
            rt = getattr(d, "return_type", None) if d is not None else getattr(node, "return_type", None)
            if isinstance(rt, str) and rt.endswith("?") and not rt.endswith("[]?"):
                return f"the result of '{node.name}(...)'"
        return None

    # -- reporting ----------------------------------------------------------

    def _report(self, expr: ASTNode, desc: str, what: str) -> None:
        self.a.report_error(
            NullableConversionError(
                detail=(
                    f"Cannot {what}: {desc} may be null (a nullable value cannot be used where a "
                    f"non-nullable value is required); check it first, e.g. 'if (x != null) {{ ... }}'"
                ),
                source_file=self.a.source_file,
            ),
            expr,
        )

    _SCALARS = frozenset({
        "int8", "int16", "int32", "int64", "uint8", "uint16", "uint32", "uint64",
        "float32", "float64", "float128", "bool", "char",
    })

    def _declared_nullable_scalar(self, expr: ASTNode) -> Optional[str]:
        """The scalar type name if `expr` is declared `T?` for a scalar T."""
        if expr.node_type == NodeTypes.IDENTIFIER:
            info = self._lookup(expr.name)
            if info is not None and info[2] and not info[1] and info[0] in self._SCALARS:
                return info[0]
        elif expr.node_type == NodeTypes.FIELD_ACCESS and expr.children:
            field = self._find_field(self._class_of(expr.children[0]), expr.name)
            if field is not None and field.is_nullable and not field.is_array and field.var_type in self._SCALARS:
                return field.var_type
        return None

    def _check_flow_into(
        self, parent: ASTNode, idx: int, target_nullable: bool, what: str, rewrite: bool = True,
    ) -> None:
        expr = parent.children[idx] if idx < len(parent.children) else None
        if target_nullable or expr is None:
            return
        desc = self._is_nullable_expr(expr)
        if desc is not None:
            self._report(expr, desc, what)
            return
        if rewrite:
            # Proven non-null (narrowed): a nullable *scalar* is lowered as a
            # value plus a has-value flag, so make the unwrap explicit by
            # wrapping it in a same-type cast, which the FIR converter lowers
            # to the plain value.
            scalar = self._declared_nullable_scalar(expr)
            if scalar is not None:
                cast = ASTNode(NodeTypes.CAST_EXPRESSION, expr.token, scalar, [expr], expr.index)
                cast.return_type = scalar
                cast.parent = parent
                expr.parent = cast
                parent.children[idx] = cast

    # -- traversal ------------------------------------------------------------

    def _walk_all(self, nodes) -> None:
        for n in nodes:
            self._walk(n)

    def _walk(self, node: Optional[ASTNode]) -> None:
        if node is None:
            return
        nt = node.node_type
        handler = getattr(self, f"_w_{nt.name.lower()}", None)
        if handler is not None:
            handler(node)
        else:
            self._walk_all(node.children)

    def _w_class_definition(self, node: ASTNode) -> None:
        prev = self.class_name
        self.class_name = node.name
        try:
            for child in node.children:
                if child.node_type == NodeTypes.CLASS_METHOD_DEFINITION:
                    self._walk(child)
        finally:
            self.class_name = prev

    def _w_function_definition(self, node: ASTNode) -> None:
        saved_narrowed, saved_fn, saved_scopes = self.narrowed, self.fn, self.scopes
        self.narrowed = set()
        self.fn = node
        # Only the module-level scope is visible inside a function.
        self.scopes = [saved_scopes[0], {}]
        try:
            for child in node.children:
                if child.node_type == NodeTypes.PARAMETER:
                    self.scopes[-1][child.name] = (child.var_type, bool(child.is_array), bool(child.is_nullable))
            for child in node.children:
                if child.node_type == NodeTypes.SCOPE:
                    self._walk(child)
        finally:
            self.narrowed, self.fn, self.scopes = saved_narrowed, saved_fn, saved_scopes

    _w_generator_definition = _w_function_definition
    _w_class_method_definition = _w_function_definition

    def _w_scope(self, node: ASTNode) -> None:
        entry = set(self.narrowed)
        self.scopes.append({})
        try:
            self._walk_all(node.children)
        finally:
            self.scopes.pop()
        self.narrowed = entry
        self._kill(self._writes(node))

    def _w_variable_declaration(self, node: ASTNode) -> None:
        self._walk_all(node.children)
        if node.children and node.parent is not None and node.parent.node_type == NodeTypes.FOR_IN_STATEMENT:
            pass  # loop variable: its "initializer" child is just the name
        elif node.children:
            self._check_flow_into(
                node, 0, bool(node.is_nullable),
                f"initialize non-nullable variable '{node.name}'", rewrite=False,
            )
        self._declare(node)
        self._kill({(node.name, True)})

    def _w_variable_assignment(self, node: ASTNode) -> None:
        self._walk_all(node.children)
        info = self._lookup(node.name)
        if info is not None and node.children:
            self._check_flow_into(node, 0, info[2], f"assign to non-nullable variable '{node.name}'")
        self._kill({(node.name, True)})

    def _w_compound_assignment(self, node: ASTNode) -> None:
        self._walk_all(node.children)
        self._kill({(node.name, True)})

    def _w_assignment(self, node: ASTNode) -> None:
        self._walk_all(node.children)
        if len(node.children) == 2:
            lhs, rhs = node.children
            if lhs.node_type == NodeTypes.FIELD_ACCESS and lhs.children:
                field = self._find_field(self._class_of(lhs.children[0]), lhs.name)
                if field is not None:
                    self._check_flow_into(node, 1, bool(field.is_nullable), f"assign to non-nullable field '{lhs.name}'")
            elif lhs.node_type == NodeTypes.IDENTIFIER:
                info = self._lookup(lhs.name)
                if info is not None:
                    self._check_flow_into(node, 1, info[2], f"assign to non-nullable variable '{lhs.name}'")
            p = _path_of(lhs)
            if p is not None:
                self._kill({(p, True)})

    def _w_return_statement(self, node: ASTNode) -> None:
        self._walk_all(node.children)
        fn = self.fn
        if fn is None or not node.children or getattr(fn, "is_constructor", False):
            return
        if fn.node_type == NodeTypes.GENERATOR_DEFINITION:
            return
        declared = getattr(fn, "return_type", None)
        if not declared or declared == "void":
            return
        self._check_flow_into(
            node, 0, declared.endswith("?"), f"return it from '{fn.name}', which returns {declared}"
        )

    def _w_binary_expression(self, node: ASTNode) -> None:
        if node.name in ("&&", "||") and len(node.children) == 2:
            left, right = node.children
            self._walk(left)
            saved = set(self.narrowed)
            self.narrowed |= self._true_set(left) if node.name == "&&" else self._false_set(left)
            self._walk(right)
            self.narrowed = saved
            return
        self._walk_all(node.children)

    def _check_args(self, node: ASTNode, args: List[ASTNode], offset: int = 0) -> None:
        d = self._callee_def(node)
        if d is None:
            return
        params = [
            c for c in d.children
            if c.node_type == NodeTypes.PARAMETER
            and not (bool(getattr(c, "is_receiver", False)) or c.name == "this")
        ]
        if len(params) != len(args):
            return
        # A parameter typed by a type parameter (`T`) is instantiated with the
        # argument's own type, nullable or not; nothing to convert.
        type_params = set(getattr(d, "type_params", None) or [])
        owners = {_base_type(getattr(node, "class_name", None)), _base_type(node.name)}
        if node.node_type == NodeTypes.METHOD_CALL and node.children:
            owners.add(self._class_of(node.children[0]))
        for cname in owners:
            cdef = self.a.class_defs.get(cname) if cname else None
            if cdef is not None:
                type_params |= set(getattr(cdef, "type_params", None) or [])
        label = {
            NodeTypes.METHOD_CALL: "method",
            NodeTypes.TYPE_METHOD_CALL: "method",
        }.get(node.node_type, "function")
        for i, (param, arg) in enumerate(zip(params, args)):
            if param.var_type in type_params:
                continue
            self._check_flow_into(
                node, offset + i, bool(param.is_nullable),
                f"pass it as argument {i + 1} of {label} '{node.name}'",
            )

    def _after_call(self, node: ASTNode, args: List[ASTNode]) -> None:
        """A callee that receives an object may reassign its fields."""
        kills: Set[_Kill] = set()
        if node.node_type == NodeTypes.METHOD_CALL and node.children:
            p = _path_of(node.children[0])
            if p is not None:
                kills.add((p, False))
        for arg in args:
            p = _path_of(arg)
            if p is not None:
                kills.add((p, False))
        if kills:
            self._kill(kills)

    def _w_function_call(self, node: ASTNode) -> None:
        self._walk_all(node.children)
        self._check_args(node, node.children)
        self._after_call(node, node.children)

    _w_constructor_call = _w_function_call
    _w_type_method_call = _w_function_call

    def _w_method_call(self, node: ASTNode) -> None:
        self._walk_all(node.children)
        self._check_args(node, node.children[1:], 1)
        self._after_call(node, node.children[1:])

    def _w_if_statement(self, node: ASTNode) -> None:
        if not node.children:
            return
        cond = node.children[0]
        then_b = node.children[1] if len(node.children) > 1 else None
        else_b = node.children[2] if len(node.children) > 2 else None
        self._walk(cond)
        t, f = self._true_set(cond), self._false_set(cond)
        entry = set(self.narrowed)

        self.narrowed = entry | t
        self._walk(then_b)
        then_end = self.narrowed
        then_term = self.a._definitely_terminates(then_b)

        self.narrowed = entry | f
        if else_b is not None:
            self._walk(else_b)
        else_end = self.narrowed
        else_term = else_b is not None and self.a._definitely_terminates(else_b)

        if then_term and else_term:
            self.narrowed = entry
        elif then_term:
            self.narrowed = else_end
        elif else_term:
            self.narrowed = then_end
        else:
            self.narrowed = entry
            self._kill(self._writes(node))

    def _enter_loop(self, node: ASTNode) -> Set[str]:
        """Drop narrowing invalidated anywhere in the loop (back edge);
        returns the loop-entry state minus those kills."""
        self._kill(self._writes(node))
        return set(self.narrowed)

    def _w_while_statement(self, node: ASTNode) -> None:
        if len(node.children) < 2:
            self._walk_all(node.children)
            return
        cond, body = node.children[0], node.children[1]
        entry = self._enter_loop(node)
        self._walk(cond)
        self.narrowed = entry | self._true_set(cond)
        self._walk(body)
        self.narrowed = entry
        self._kill(self._writes(node))

    def _w_for_statement(self, node: ASTNode) -> None:
        self.scopes.append({})
        try:
            if len(node.children) >= 4:
                init, cond, inc, body = node.children[:4]
                self._walk(init)
                entry = self._enter_loop(node)
                self._walk(cond)
                self.narrowed = entry | self._true_set(cond)
                self._walk(body)
                self._walk(inc)
                self.narrowed = entry
            else:
                self._walk_all(node.children)
        finally:
            self.scopes.pop()
        self._kill(self._writes(node))

    def _w_for_in_statement(self, node: ASTNode) -> None:
        if len(node.children) < 3:
            self._walk_all(node.children)
            return
        var_decl, coll, body = node.children[:3]
        self._walk(coll)
        self.scopes.append({})
        try:
            self._declare(var_decl)
            entry = self._enter_loop(node)
            self._walk(body)
            self.narrowed = entry
        finally:
            self.scopes.pop()
        self._kill(self._writes(node))

    def _w_match_expression(self, node: ASTNode) -> None:
        if not node.children:
            return
        self._walk(node.children[0])
        for arm in node.children[1:]:
            saved = set(self.narrowed)
            self.scopes.append({})
            try:
                for _field, local in getattr(arm, "bindings", []) or []:
                    self.scopes[-1][local] = (None, False, False)
                self._walk_all(arm.children)
            finally:
                self.scopes.pop()
            self.narrowed = saved
        self._kill(self._writes(node))
