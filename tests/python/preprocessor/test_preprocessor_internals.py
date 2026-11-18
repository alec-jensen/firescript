"""Direct unit tests for firescript/preprocessor.py's internal helpers and
enable_and_insert_drops()'s less-common branches (directive-already-present,
`_mentions_var` recursion, drop_call var_name matching, return-expression
transfer detection through function/constructor borrow flags, implicit
declaration inference from a method call, and a C-style for-loop clause
omitted (None) mid-list). Hand-builds ASTNode trees directly, following the
pattern used by tests/python/imports/test_module_resolver.py for
private-function testing."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from enums import NodeTypes  # noqa: E402
from parser.ast_node import ASTNode  # noqa: E402
import preprocessor as pp  # noqa: E402
import utils.type_utils as tu  # noqa: E402
from preprocessor import enable_and_insert_drops  # noqa: E402


def _scope(children=None) -> ASTNode:
    return ASTNode(NodeTypes.SCOPE, None, "scope", children or [], 0)


def _root(children=None) -> ASTNode:
    return ASTNode(NodeTypes.ROOT, None, "root", children or [], 0)


def _ident(name: str, var_type=None, is_array=False) -> ASTNode:
    return ASTNode(NodeTypes.IDENTIFIER, None, name, [], 0, var_type, False, False, var_type, is_array, is_array)


def _string_literal(text: str) -> ASTNode:
    return ASTNode(NodeTypes.LITERAL, None, text, [], 0, var_type="string")


def _owned_decl(name: str, value: ASTNode, var_type: str = "string") -> ASTNode:
    return ASTNode(NodeTypes.VARIABLE_DECLARATION, None, name, [value], 0, var_type=var_type)


def _post_return_drop_names(root: ASTNode) -> list:
    """Names the preprocessor marked for a drop *after* the first return's
    value is built (identifiers read by the return expression but not
    transferred out of it)."""
    def find(node):
        if node.node_type == NodeTypes.RETURN_STATEMENT:
            return node
        for child in node.children:
            if child is not None:
                hit = find(child)
                if hit is not None:
                    return hit
        return None

    return list(getattr(find(root), "post_return_drop_names", []))


def _has_drop(node: ASTNode, var_name: str) -> bool:
    if pp._is_drop_call(node, var_name):
        return True
    return any(_has_drop(c, var_name) for c in node.children if c is not None)


# --- enable_and_insert_drops: directive handling --------------------------------

def test_enable_and_insert_drops_does_not_duplicate_existing_directive():
    directive = ASTNode(NodeTypes.DIRECTIVE, None, pp.DROP_DIRECTIVE_NAME, [], 0)
    ast = _root([directive])
    result = enable_and_insert_drops(ast)
    directive_count = sum(
        1 for c in result.children if c.node_type == NodeTypes.DIRECTIVE and c.name == pp.DROP_DIRECTIVE_NAME
    )
    t.require_eq(directive_count, 1)


# --- _mentions_var ------------------------------------------------------------

def test_mentions_var_direct_nested_and_absent():
    t.require(pp._mentions_var(_ident("target"), "target") is True)
    nested = _scope([_scope([_ident("target")])])
    t.require(pp._mentions_var(nested, "target") is True)
    t.require(pp._mentions_var(_scope([_ident("other_var")]), "not_here") is False)


# --- _is_drop_call with var_name ----------------------------------------------

def test_is_drop_call_matches_var_name():
    drop_call = pp._make_drop_call("x", "string", False)
    t.require(pp._is_drop_call(drop_call, "x") is True)
    t.require(pp._is_drop_call(drop_call, "y") is False)


# --- return-expression FUNCTION_CALL / CONSTRUCTOR_CALL walk with borrow flags

def _consume_caller(borrowed: bool):
    """`fn consume(s: string)` (or `&s` when borrowed) plus
    `fn caller() { str_var = "hi"; return consume(str_var); }`."""
    consume_param = ASTNode(NodeTypes.PARAMETER, None, "s", [], 0, var_type="string")
    consume_param.is_borrowed = borrowed
    consume_func = ASTNode(
        NodeTypes.FUNCTION_DEFINITION, None, "consume", [consume_param, _scope([])], 0, return_type="void"
    )
    call = ASTNode(NodeTypes.FUNCTION_CALL, None, "consume", [_ident("str_var", "string")], 0)
    ret = ASTNode(NodeTypes.RETURN_STATEMENT, None, "return", [call], 0)
    decl = _owned_decl("str_var", _string_literal("hi"))
    caller_func = ASTNode(
        NodeTypes.FUNCTION_DEFINITION, None, "caller", [_scope([decl, ret])], 0, return_type="void"
    )
    return _root([consume_func, caller_func]), caller_func


def test_return_function_call_with_owned_param_transfers_arg():
    """`return consume(str_var);` where `consume` takes its argument by
    ownership: str_var is transferred out through the call, so it is not
    marked for a post-return drop."""
    ast, caller = _consume_caller(borrowed=False)
    result = enable_and_insert_drops(ast)
    caller = next(c for c in result.children if c.name == "caller")
    t.require_eq(_post_return_drop_names(caller), [])


def test_return_function_call_with_borrowed_param_still_drops_arg():
    """Valid twin: a borrowed parameter does not transfer ownership, so
    str_var is still marked for a post-return drop."""
    ast, caller = _consume_caller(borrowed=True)
    result = enable_and_insert_drops(ast)
    caller = next(c for c in result.children if c.name == "caller")
    t.require_eq(_post_return_drop_names(caller), ["str_var"])


def _box_ctor_caller(borrowed: bool):
    """`class Box { fn Box(s: string) }` (or `&s`) plus
    `fn caller() { str_var = "hi"; return Box(str_var); }`."""
    ctor_param = ASTNode(NodeTypes.PARAMETER, None, "s", [], 0, var_type="string")
    ctor_param.is_borrowed = borrowed
    ctor = ASTNode(
        NodeTypes.CLASS_METHOD_DEFINITION, None, "Box", [ctor_param, _scope([])], 0, return_type=None
    )
    ctor.is_constructor = True
    class_def = ASTNode(NodeTypes.CLASS_DEFINITION, None, "Box", [ctor], 0)
    call = ASTNode(NodeTypes.CONSTRUCTOR_CALL, None, "Box", [_ident("str_var", "string")], 0)
    ret = ASTNode(NodeTypes.RETURN_STATEMENT, None, "return", [call], 0)
    decl = _owned_decl("str_var", _string_literal("hi"))
    caller_func = ASTNode(
        NodeTypes.FUNCTION_DEFINITION, None, "caller", [_scope([decl, ret])], 0, return_type="void"
    )
    return _root([class_def, caller_func])


def test_return_constructor_call_with_owned_param_transfers_arg():
    result = enable_and_insert_drops(_box_ctor_caller(borrowed=False))
    caller = next(c for c in result.children if c.name == "caller")
    t.require_eq(_post_return_drop_names(caller), [])


def test_return_constructor_call_with_borrowed_param_still_drops_arg():
    result = enable_and_insert_drops(_box_ctor_caller(borrowed=True))
    caller = next(c for c in result.children if c.name == "caller")
    t.require_eq(_post_return_drop_names(caller), ["str_var"])


# --- implicit-declaration inference: method-call receiver resolution --------

def _box_with_clone():
    ctor_param = ASTNode(NodeTypes.PARAMETER, None, "s", [], 0, var_type="string")
    ctor = ASTNode(
        NodeTypes.CLASS_METHOD_DEFINITION, None, "Box", [ctor_param, _scope([])], 0, return_type=None
    )
    ctor.is_constructor = True
    clone_method = ASTNode(
        NodeTypes.CLASS_METHOD_DEFINITION, None, "clone", [_scope([])], 0, return_type="Box"
    )
    return ASTNode(NodeTypes.CLASS_DEFINITION, None, "Box", [ctor, clone_method], 0)


def test_implicit_declaration_from_method_call_on_constructor_receiver():
    """`v1 = Box(str_var).clone();` with no prior declaration of v1: the
    VARIABLE_ASSIGNMENT branch infers v1's class (Box, via the CONSTRUCTOR_CALL
    receiver and Box.clone's return type) and registers it for auto-drop."""
    tu.reset_registries()
    tu.register_class("Box")
    try:
        ctor_call = ASTNode(NodeTypes.CONSTRUCTOR_CALL, None, "Box", [_ident("str_var", "string")], 0)
        method_call = ASTNode(NodeTypes.METHOD_CALL, None, "clone", [ctor_call], 0)
        assign = ASTNode(NodeTypes.VARIABLE_ASSIGNMENT, None, "v1", [method_call], 0)
        body = _scope([_owned_decl("str_var", _string_literal("hi")), assign])
        func = ASTNode(NodeTypes.FUNCTION_DEFINITION, None, "f", [body], 0, return_type="void")
        result = enable_and_insert_drops(_root([_box_with_clone(), func]))
    finally:
        tu.reset_registries()
    f = next(c for c in result.children if c.name == "f")
    t.require(_has_drop(f, "v1"), "implicitly declared v1 was not auto-dropped")


def test_implicit_declaration_from_method_call_on_identifier_receiver():
    """`v2 = existing.clone();` where `existing` is a known Box local --
    the IDENTIFIER receiver branch of the same inference."""
    tu.reset_registries()
    tu.register_class("Box")
    try:
        existing_decl = ASTNode(
            NodeTypes.VARIABLE_DECLARATION, None, "existing",
            [ASTNode(NodeTypes.CONSTRUCTOR_CALL, None, "Box", [_ident("str_var", "string")], 0)],
            0, var_type="Box",
        )
        method_call = ASTNode(NodeTypes.METHOD_CALL, None, "clone", [_ident("existing", "Box")], 0)
        assign = ASTNode(NodeTypes.VARIABLE_ASSIGNMENT, None, "v2", [method_call], 0)
        body = _scope([_owned_decl("str_var", _string_literal("hi")), existing_decl, assign])
        func = ASTNode(NodeTypes.FUNCTION_DEFINITION, None, "f", [body], 0, return_type="void")
        result = enable_and_insert_drops(_root([_box_with_clone(), func]))
    finally:
        tu.reset_registries()
    f = next(c for c in result.children if c.name == "f")
    t.require(_has_drop(f, "v2"), "implicitly declared v2 was not auto-dropped")


# --- C-style for-loop with an omitted (None) middle clause -------------------

def test_for_loop_with_none_clause_preserved():
    """A C-style `for (int32 i = 0; ; i = i + 1)` (condition omitted) is
    represented as a FOR_STATEMENT with children [init, None, incr, body].
    ASTNode's constructor rejects None children, so the parser (and this
    test) builds the node with an empty children list first, then assigns
    .children directly -- exercising the loop-clause None-preservation
    branch in enable_and_insert_drops's FOR_STATEMENT handling."""
    init = ASTNode(NodeTypes.VARIABLE_DECLARATION, None, "i", [ASTNode(NodeTypes.LITERAL, None, "0", [], 0, var_type="int32")], 0, var_type="int32")
    incr = ASTNode(NodeTypes.VARIABLE_ASSIGNMENT, None, "i", [_ident("i", "int32")], 0)
    body = _scope([])
    for_node = ASTNode(NodeTypes.FOR_STATEMENT, None, "for", [], 0)
    for_node.children = [init, None, incr, body]

    ast = _root([for_node])
    result = enable_and_insert_drops(ast)
    processed_for = next(c for c in result.children if c.node_type == NodeTypes.FOR_STATEMENT)
    t.require_eq(len(processed_for.children), 4)
    t.require_eq(processed_for.children[1], None)
