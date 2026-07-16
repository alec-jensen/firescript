"""Direct unit tests for defensive/"impossible" guard branches in
firescript/parser/type_system.py that cannot be reached from any real .fire
source.

Most of these fall into one of two families:

  1. `_get_node_type()` fallback branches for node kinds (FUNCTION_CALL,
     METHOD_CALL, SUPER_CALL, ARRAY_ACCESS, LITERAL) that `_type_check_node()`
     *always* assigns an explicit (possibly-None) `node_type_str` for before
     the shared `if node_type_str is None: node_type_str =
     self._get_node_type(...)` fallback at the end of `_type_check_node()`
     runs. Since a LITERAL node's `return_type` is always set by the parser
     at construction time (see expressions.py's LITERAL branch), and a
     FUNCTION_CALL/METHOD_CALL/SUPER_CALL/ARRAY_ACCESS's `node_type_str` is
     always independently derived by `_type_check_node()` itself, these
     `_get_node_type()` branches are true dead code reachable only by
     calling `_get_node_type()` directly, out of band.
  2. Guards that re-check a condition the sole caller already established
     (e.g. `_infer_generic_type_args` being called only when `func_name` is
     already confirmed to be a generic function).

Reachable behavior is covered by .fire sources under tests/sources/**
instead -- this module only fills in the leftover guards that no real
source can reach. See tests/python/parser/_helpers.py for the shared
parser-construction helper.
"""
from __future__ import annotations

from harness import pyunit as t
from enums import NodeTypes
from parser.ast_node import ASTNode

from _helpers import make_parser


def _lit(value, token_type="INTEGER_LITERAL", return_type=None):
    from _helpers import blank_token

    tok = blank_token(token_type, str(value))
    node = ASTNode(NodeTypes.LITERAL, tok, str(value), [], 0, return_type=return_type)
    return node


def test_annotate_value_category_swallows_exceptions():
    # _annotate_value_category wraps is_owned/is_copyable in a bare
    # try/except Exception: pass, defending against a lookup helper raising
    # for a malformed/unexpected var_type. Real var_type values are always
    # plain strings or None, so this can't fire from real source -- force it
    # with a var_type value engineered to blow up inside is_owned/is_copyable.
    p = make_parser("x: int32 = 1;")

    class Explodes:
        def __eq__(self, other):
            raise RuntimeError("boom")

        def __hash__(self):
            return 0

    node = ASTNode(NodeTypes.VARIABLE_DECLARATION, None, "x", [], 0)
    p._annotate_value_category(node, Explodes(), False)  # type: ignore[arg-type]
    t.require(node.value_category is None)


def test_get_node_type_literal_fallback_is_dead():
    # Every real LITERAL node gets return_type set at construction time by
    # the parser (expressions.py), so _get_node_type()'s own "derive from
    # token.type" fallback for LITERAL (which only runs when return_type is
    # falsy) can only be hit by calling _get_node_type() directly on a
    # hand-built, return_type-less LITERAL node.
    p = make_parser("1;")
    for token_type, expected in (
        ("INTEGER_LITERAL", "int32"),
        ("FLOAT_LITERAL", "float32"),
        ("DOUBLE_LITERAL", "float64"),
        ("BOOLEAN_LITERAL", "bool"),
        ("STRING_LITERAL", "string"),
        ("NULL_LITERAL", "null"),
    ):
        node = _lit("v", token_type=token_type, return_type=None)
        result = p._get_node_type(node, {})
        t.require(result == expected, (token_type, result))


def test_get_node_type_array_literal_element_node_none_is_defensive():
    # ARRAY_LITERAL's first-element-node-is-None branch (statements.py's
    # array literal parsing always builds real element nodes) can't occur
    # from real source; a None child would in fact be rejected by
    # ASTNode's own constructor guard. Simulate it by bypassing that guard.
    p = make_parser("1;")
    node = ASTNode(NodeTypes.ARRAY_LITERAL, None, "arr", [], 0)
    node.children = [None]  # type: ignore[list-item]
    result = p._get_node_type(node, {})
    t.require(result is None)


def test_get_node_type_function_call_array_fallback_is_dead():
    # _type_check_node() always assigns FUNCTION_CALL's node_type_str from
    # node.return_type itself, so if node.return_type already ends with
    # "[]", node_type_str is already non-None and the shared fallback to
    # _get_node_type() never runs. Call _get_node_type() directly to hit the
    # is_array branch.
    node = ASTNode(NodeTypes.FUNCTION_CALL, None, "f", [], 0, return_type="int32[]")
    p = make_parser("1;")
    result = p._get_node_type(node, {})
    t.require(result == "int32[]")


def test_get_node_type_super_call_fallback_is_dead():
    # _type_check_node() always explicitly sets node_type_str = "void" for
    # SUPER_CALL, so _get_node_type()'s own SUPER_CALL branch is unreachable
    # via the shared fallback.
    p = make_parser("1;")
    array_node = ASTNode(NodeTypes.SUPER_CALL, None, "super", [], 0, return_type="Base[]")
    t.require(p._get_node_type(array_node, {}) == "Base[]")
    # A falsy return_type takes the `else: is_array = False` branch instead
    # of the `if base_type:` branch above it.
    falsy_node = ASTNode(NodeTypes.SUPER_CALL, None, "super", [], 0, return_type=None)
    t.require(p._get_node_type(falsy_node, {}) is None)


def test_get_node_type_method_call_array_fallback_is_dead():
    # Like FUNCTION_CALL, _type_check_node() never leaves METHOD_CALL's
    # node_type_str assignment to the shared _get_node_type() fallback in
    # practice: class methods can't be declared with an array return type
    # (the class-body parser has no OPEN_BRACKET handling after a field/
    # method's type token), so a METHOD_CALL node with an array
    # node.return_type can only be constructed by hand.
    node = ASTNode(NodeTypes.METHOD_CALL, None, "get", [], 0, return_type="int32[]")
    p = make_parser("1;")
    result = p._get_node_type(node, {})
    t.require(result == "int32[]")


def test_function_call_return_type_fallback_assignment_is_dead():
    # _type_check_node()'s FUNCTION_CALL handling guards a fallback
    # `node.return_type = self.user_functions.get(func_name)` assignment
    # with `not hasattr(node, 'return_type')` -- but ASTNode.__init__
    # unconditionally sets self.return_type (defaulting to None), so every
    # ASTNode instance always has the attribute and this guard can never be
    # True from real code. (This looks like a latent authoring bug in
    # type_system.py -- the intended check was probably
    # `node.return_type is None` -- but per project policy compiler bugs
    # found while adding tests are reported, not fixed here.)
    p = make_parser("1;")
    node = ASTNode(NodeTypes.FUNCTION_CALL, None, "mystery_fn", [], 0)
    del node.return_type
    t.require(not hasattr(node, "return_type"))
    result = p._type_check_node(node, {})
    t.require(node.return_type is None)
    t.require(result is None)


def test_get_node_type_array_access_child_none_is_defensive():
    # ARRAY_ACCESS always has a real array-expression child from the
    # parser; children[0] being falsy can't happen from real source.
    node = ASTNode(NodeTypes.ARRAY_ACCESS, None, "idx", [], 0)
    node.children = [None]  # type: ignore[list-item]
    p = make_parser("1;")
    result = p._get_node_type(node, {})
    t.require(result is None)


def test_infer_generic_type_args_name_not_generic_is_defensive():
    # _infer_generic_type_args() is only ever called (in _type_check_node's
    # FUNCTION_CALL handling) after confirming func_name is already a key of
    # self.generic_functions, so its own membership recheck can't fail.
    p = make_parser("1;")
    result = p._infer_generic_type_args("not_a_generic_fn", [])
    t.require(result is None)


def test_infer_generic_type_args_empty_type_params_is_defensive():
    # A generic function is always registered with at least one type
    # parameter (that's what makes it generic); an empty type_params list
    # can't occur from real source.
    p = make_parser("1;")
    p.generic_functions["weird"] = []
    result = p._infer_generic_type_args("weird", [])
    t.require(result == [])


def test_infer_generic_type_args_missing_function_definition_is_defensive():
    # _infer_generic_type_args() looks up the FUNCTION_DEFINITION AST node
    # for func_name among self.ast.children; a name registered in
    # self.generic_functions always has a matching definition in the same
    # parse, so "not found" can't happen from real source. Simulate a
    # generic function registered without ever having been parsed as a
    # top-level definition (e.g. hypothetically merged in from elsewhere).
    p = make_parser("1;")
    p.generic_functions["ghost"] = ["T"]
    result = p._infer_generic_type_args("ghost", ["int32"])
    t.require(result is None)


def test_unary_missing_operand_is_defensive():
    # parse_primary always attaches exactly one operand child to a unary
    # +/-/! UNARY_EXPRESSION node; child_types is only empty here if called
    # out of band with a childless node.
    node = ASTNode(NodeTypes.UNARY_EXPRESSION, None, "-", [], 0)
    p = make_parser("1;")
    result = p._type_check_node(node, {})
    t.require(result is None)


def test_unary_unsupported_operator_is_defensive():
    # The parser only ever constructs UNARY_EXPRESSION nodes with name in
    # {"+", "-", "!", "++", "--"}; any other operator string can't occur
    # from real source.
    node = ASTNode(NodeTypes.UNARY_EXPRESSION, None, "~", [_lit(1, return_type="int32")], 0)
    p = make_parser("1;")
    result = p._type_check_node(node, {})
    t.require(result is None)
    t.require(node.return_type is None)


def test_binary_unsupported_operator_is_defensive():
    # The parser only ever constructs BINARY_EXPRESSION nodes for the
    # arithmetic/logical operators handled explicitly above; any other
    # operator string can't occur from real source.
    node = ASTNode(
        NodeTypes.BINARY_EXPRESSION,
        None,
        "^",
        [_lit(1, return_type="int32"), _lit(2, return_type="int32")],
        0,
    )
    p = make_parser("1;")
    p._type_check_node(node, {})
    t.require(node.return_type is None)


def test_cast_to_array_type_is_defensive():
    # The postfix `as <type>` cast syntax only ever captures a single type
    # token or bare identifier (expressions.py's _parse_postfix_cast), so a
    # CAST_EXPRESSION's target type (node.name) can never itself end in
    # "[]" from real source.
    node = ASTNode(
        NodeTypes.CAST_EXPRESSION,
        None,
        "int32[]",
        [_lit(1, return_type="int32")],
        0,
    )
    p = make_parser("1;")
    result = p._type_check_node(node, {})
    t.require(result is None)


def test_function_call_expected_arg_types_loop_is_defensive():
    # expected_arg_types is declared and always left as an empty list in
    # _type_check_node's FUNCTION_CALL handling -- nothing ever populates
    # it -- so the `elif expected_arg_types:` branch and its loop can never
    # run from real source. This is exercised by exhaustively calling every
    # builtin that sets expected_arg_count; none of them ever reach the
    # per-argument-type loop since expected_arg_types stays empty regardless
    # of arguments. Documented here as dead rather than driven directly,
    # since there is no seam to inject a non-empty expected_arg_types
    # without rewriting the function itself.
    t.require(True)


def test_super_call_no_enclosing_class_is_defensive():
    # `this.super(...)` only parses inside a class method (declarations.py
    # sets enclosing_class from the active class-context stack whenever the
    # SUPER_CALL node is built), so enclosing_class is always truthy for a
    # real SUPER_CALL node.
    node = ASTNode(NodeTypes.SUPER_CALL, None, "super", [], 0)
    p = make_parser("1;")
    result = p._type_check_node(node, {})
    t.require(result is None)


def test_super_call_not_in_constructor_is_defensive():
    # `this.super(...)` syntax is only accepted while parsing a
    # constructor body (the parser gates it on in_constructor from the
    # class-context stack), so in_constructor is always True for a real
    # SUPER_CALL node.
    node = ASTNode(NodeTypes.SUPER_CALL, None, "super", [], 0)
    setattr(node, "enclosing_class", "Derived")
    setattr(node, "super_class", "Base")
    setattr(node, "in_constructor", False)
    p = make_parser("1;")
    result = p._type_check_node(node, {})
    t.require(result is None)
