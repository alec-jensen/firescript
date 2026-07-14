"""Direct unit tests for internal type-checker helper methods in
firescript/parser/type_system.py whose defensive branches can't be reached
by compiling any real source.

`_get_node_type` is only reached (via the fallback at the end of
`_type_check_node`) for node types that `_type_check_node`'s own dispatch
does *not* already set an explicit return type for. Every node type that
_get_node_type itself special-cases (LITERAL, IDENTIFIER, ARRAY_LITERAL,
FUNCTION_CALL, METHOD_CALL, SUPER_CALL, ARRAY_ACCESS, BINARY/EQUALITY/
RELATIONAL_EXPRESSION) is *also* explicitly handled inside
`_type_check_node`, which always assigns `node_type_str` for those cases
before falling through -- except METHOD_CALL (which sets `node.return_type`
but never touches the local `node_type_str`) and ARRAY_LITERAL (not handled
by `_type_check_node` at all). So `_get_node_type`'s FUNCTION_CALL and
SUPER_CALL branches, and the array-suffix-trim on its LITERAL fallback
path, are unreachable through the public `_type_check_node` entry point and
are only exercised here via direct construction + a direct call.
"""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from enums import NodeTypes  # noqa: E402
from parser import ASTNode  # noqa: E402
from _dead_guard_helpers import make_parser  # noqa: E402


def test_get_node_type_literal_fallback_infers_from_token_type():
    for token_type, value, expected in (
        ("INTEGER_LITERAL", "5", "int32"),
        ("BOOLEAN_LITERAL", "true", "bool"),
        ("STRING_LITERAL", '"hi"', "string"),
        ("NULL_LITERAL", "null", "null"),
    ):
        p = make_parser(value)
        node = ASTNode(NodeTypes.LITERAL, p.current_token, value, [], 0)
        node.return_type = None  # bypass parse_primary's normal annotation
        node.token.type = token_type  # force the fallback's token.type dispatch
        result = p._get_node_type(node, {})
        t.require_eq(result, expected, f"{token_type} fallback")


def test_get_node_type_function_call_array_suffix_is_unreachable_via_type_check_node():
    """FUNCTION_CALL is explicitly handled by _type_check_node, which always
    assigns node_type_str, so _get_node_type's own FUNCTION_CALL branch
    (array-suffix trimming) is only reachable by calling _get_node_type
    directly."""
    p = make_parser("")
    node = ASTNode(NodeTypes.FUNCTION_CALL, None, "makeArr", [], 0)
    node.return_type = "int32[]"
    result = p._get_node_type(node, {})
    t.require_eq(result, "int32[]")


def test_get_node_type_method_call_array_suffix():
    """Class methods can't syntactically declare an array return type (no
    '[]' suffix parsing in _parse_class_definition), so a METHOD_CALL node
    with an array return type never occurs from real parsing; construct one
    directly to exercise the trim branch."""
    p = make_parser("")
    node = ASTNode(NodeTypes.METHOD_CALL, None, "getAll", [], 0)
    node.return_type = "string[]"
    result = p._get_node_type(node, {})
    t.require_eq(result, "string[]")


def test_get_node_type_super_call_is_unreachable_via_type_check_node():
    """SUPER_CALL is explicitly handled by _type_check_node (always setting
    node_type_str = 'void'), so _get_node_type's own SUPER_CALL branch is
    dead through the normal entry point."""
    p = make_parser("")
    node = ASTNode(NodeTypes.SUPER_CALL, None, "super", [], 0)
    node.return_type = "int32[]"
    result = p._get_node_type(node, {})
    t.require_eq(result, "int32[]")

    node2 = ASTNode(NodeTypes.SUPER_CALL, None, "super", [], 0)
    node2.return_type = None
    result2 = p._get_node_type(node2, {})
    t.require(result2 is None)


def test_annotate_value_category_swallows_exceptions():
    """_annotate_value_category wraps is_owned/is_copyable in a bare
    try/except; passing a var_type that isn't a valid string (e.g. an int)
    makes is_owned/is_copyable raise, which is otherwise never observed
    from real source (var_type is always a str or None there)."""
    p = make_parser("")
    node = ASTNode(NodeTypes.IDENTIFIER, None, "x", [], 0)
    # var_type is normally Optional[str]; pass an unhashable value (a list)
    # to force `base_type in _COPYABLE_BASE`/`_OWNED_BASE` to raise
    # TypeError deep inside is_owned/is_copyable.
    p._annotate_value_category(node, ["not", "a", "type", "name"], False)  # must not raise
    t.require(True)


def test_infer_generic_type_args_unknown_function_returns_none():
    """_infer_generic_type_args is only ever called (from the FUNCTION_CALL
    branch of _type_check_node) after already confirming func_name is in
    self.generic_functions, so the 'func_name not in generic_functions'
    guard at its top is otherwise unreachable."""
    p = make_parser("")
    result = p._infer_generic_type_args("not_a_generic_function", ["int32"])
    t.require(result is None)


def test_infer_generic_type_args_empty_type_params_returns_empty_list():
    """A function is only added to generic_functions when its parsed type
    params list is non-empty (declarations.py: `if type_params: ...`), so
    this guard against an empty type_params list is otherwise unreachable."""
    p = make_parser("")
    p.generic_functions["weird"] = []
    result = p._infer_generic_type_args("weird", [])
    t.require_eq(result, [])


def test_infer_generic_type_args_missing_function_def_returns_none():
    """Registering a name in generic_functions without a matching
    FUNCTION_DEFINITION child in self.ast (e.g. because it came from a
    different AST than the one being searched) can't happen through the
    normal parse() flow, since the same Parser instance appends the node it
    just parsed to self.ast.children right before/at registration."""
    p = make_parser("")
    p.generic_functions["ghost"] = ["T"]
    result = p._infer_generic_type_args("ghost", ["int32"])
    t.require(result is None)


def test_cast_to_array_type_is_rejected():
    """The postfix-cast grammar ('<expr> as <type>') only ever parses a
    single type token/identifier after 'as' -- there is no bracket parsing
    for an array suffix -- so a CAST_EXPRESSION node whose target name ends
    in '[]' can never come from real parsing; build one directly to
    exercise the type checker's defensive rejection of it."""
    p = make_parser("5")
    operand = p.parse_primary()
    cast_node = ASTNode(NodeTypes.CAST_EXPRESSION, operand.token, "int32[]", [operand], 0)
    result = p._type_check_node(cast_node, {})
    t.require(result is None)
    t.require(any(e.code == "FS-SEM-0010" for e in p.errors))


def test_function_call_return_type_already_always_set_by_parser():
    """FUNCTION_CALL nodes always have a `return_type` attribute (ASTNode's
    constructor sets it unconditionally, defaulting to None), so
    `not hasattr(node, 'return_type')` can never be True through
    _type_check_node's normal FUNCTION_CALL handling; this directly proves
    the invariant rather than exercising a reachable branch."""
    p = make_parser("")
    node = ASTNode(NodeTypes.FUNCTION_CALL, None, "someFunc", [], 0)
    t.require(hasattr(node, "return_type"))
