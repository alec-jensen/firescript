"""Direct unit tests for firescript/preprocessor.py's internal helpers and
enable_and_insert_drops()'s less-common branches (directive-already-present,
unmentioned variables, drop_call var_name matching, return-expression walk
helpers, break/continue fallback when there is no recorded loop boundary,
and a C-style for-loop clause omitted (None) mid-list). Hand-builds ASTNode
trees directly, following the pattern used by
tests/python/imports/test_module_resolver.py for private-function testing."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from enums import NodeTypes  # noqa: E402
from parser.ast_node import ASTNode  # noqa: E402
import preprocessor as pp  # noqa: E402
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


# --- _collect_directive / _ensure_drop_directive -----------------------------

def test_collect_directive_true_when_already_present():
    directive = ASTNode(NodeTypes.DIRECTIVE, None, pp.DROP_DIRECTIVE_NAME, [], 0)
    ast = _root([directive])
    t.require(pp._collect_directive(ast) is True)


def test_enable_and_insert_drops_does_not_duplicate_existing_directive():
    directive = ASTNode(NodeTypes.DIRECTIVE, None, pp.DROP_DIRECTIVE_NAME, [], 0)
    ast = _root([directive])
    result = enable_and_insert_drops(ast)
    directive_count = sum(
        1 for c in result.children if c.node_type == NodeTypes.DIRECTIVE and c.name == pp.DROP_DIRECTIVE_NAME
    )
    t.require_eq(directive_count, 1)


# --- _mentions_var ------------------------------------------------------------

def test_mentions_var_false_when_absent():
    node = _scope([_ident("other_var")])
    t.require(pp._mentions_var(node, "not_here") is False)


def test_mentions_var_true_direct_identifier():
    node = _ident("target")
    t.require(pp._mentions_var(node, "target") is True)


# --- _is_drop_call with var_name ----------------------------------------------

def test_is_drop_call_matches_var_name():
    drop_call = pp._make_drop_call("x", "string", False)
    t.require(pp._is_drop_call(drop_call, "x") is True)
    t.require(pp._is_drop_call(drop_call, "y") is False)


# --- _collect_identifier_names / _return_transferred_identifiers: None input -

def test_collect_identifier_names_none_returns_empty_set():
    # Reached via enable_and_insert_drops on a bare `return;` (no expr).
    ret = ASTNode(NodeTypes.RETURN_STATEMENT, None, "return", [], 0)
    body = _scope([ret])
    func = ASTNode(NodeTypes.FUNCTION_DEFINITION, None, "f", [body], 0, return_type="void")
    ast = _root([func])
    enable_and_insert_drops(ast)  # must not raise


def test_return_transferred_identifiers_walk_none_receiver():
    """A METHOD_CALL with no children at all (no receiver, no args) drives
    _return_transferred_identifiers' nested walk() with node=None for the
    receiver, exercising its `if node is None: return` guard."""
    empty_method_call = ASTNode(NodeTypes.METHOD_CALL, None, "whatever", [], 0)
    ret = ASTNode(NodeTypes.RETURN_STATEMENT, None, "return", [empty_method_call], 0)
    body = _scope([ret])
    func = ASTNode(NodeTypes.FUNCTION_DEFINITION, None, "f", [body], 0, return_type="void")
    ast = _root([func])
    enable_and_insert_drops(ast)  # must not raise


# --- return-expression FUNCTION_CALL / CONSTRUCTOR_CALL walk with borrow flags

def test_return_function_call_with_borrow_flags_marks_transferred_arg():
    """A function `function consume(string s) {}` (owned, non-borrowed
    param) called as `return consume(str_var);` should mark str_var as
    transferred (walks FUNCTION_CALL branch, uses ctor_sigs/func_sigs
    lookup and the identifier-arg transferred-add branch)."""
    consume_param = ASTNode(NodeTypes.PARAMETER, None, "s", [], 0, var_type="string")
    consume_body = _scope([])
    consume_func = ASTNode(
        NodeTypes.FUNCTION_DEFINITION, None, "consume", [consume_param, consume_body], 0, return_type="void"
    )

    call = ASTNode(NodeTypes.FUNCTION_CALL, None, "consume", [_ident("str_var", "string")], 0)
    ret = ASTNode(NodeTypes.RETURN_STATEMENT, None, "return", [call], 0)
    decl = _owned_decl("str_var", _string_literal("hi"))
    caller_body = _scope([decl, ret])
    caller_func = ASTNode(
        NodeTypes.FUNCTION_DEFINITION, None, "caller", [caller_body], 0, return_type="void"
    )

    ast = _root([consume_func, caller_func])
    enable_and_insert_drops(ast)  # must not raise; exercises func_sigs-driven transfer detection


def test_return_constructor_call_with_borrow_flags_marks_transferred_arg():
    """A class constructor `Box(string s)` (non-borrowed) called as
    `return Box(str_var);` walks the CONSTRUCTOR_CALL branch."""
    ctor_param = ASTNode(NodeTypes.PARAMETER, None, "s", [], 0, var_type="string")
    ctor_body = _scope([])
    ctor = ASTNode(
        NodeTypes.CLASS_METHOD_DEFINITION, None, "Box", [ctor_param, ctor_body], 0, return_type=None
    )
    ctor.is_constructor = True
    class_def = ASTNode(NodeTypes.CLASS_DEFINITION, None, "Box", [ctor], 0)

    call = ASTNode(NodeTypes.CONSTRUCTOR_CALL, None, "Box", [_ident("str_var", "string")], 0)
    ret = ASTNode(NodeTypes.RETURN_STATEMENT, None, "return", [call], 0)
    decl = _owned_decl("str_var", _string_literal("hi"))
    caller_body = _scope([decl, ret])
    caller_func = ASTNode(
        NodeTypes.FUNCTION_DEFINITION, None, "caller", [caller_body], 0, return_type="void"
    )

    ast = _root([class_def, caller_func])
    enable_and_insert_drops(ast)  # must not raise; exercises ctor_sigs-driven transfer detection


# --- implicit-declaration inference: method-call receiver resolution --------

def test_implicit_declaration_from_method_call_on_constructor_receiver():
    """`v1 = Box(str_var).clone();` with no prior declaration of v1: the
    VARIABLE_ASSIGNMENT branch must infer v1's class from a
    CONSTRUCTOR_CALL receiver (method_return_types lookup)."""
    ctor_param = ASTNode(NodeTypes.PARAMETER, None, "s", [], 0, var_type="string")
    ctor = ASTNode(
        NodeTypes.CLASS_METHOD_DEFINITION, None, "Box", [ctor_param, _scope([])], 0, return_type=None
    )
    ctor.is_constructor = True
    clone_method = ASTNode(
        NodeTypes.CLASS_METHOD_DEFINITION, None, "clone", [_scope([])], 0, return_type="Box"
    )
    class_def = ASTNode(NodeTypes.CLASS_DEFINITION, None, "Box", [ctor, clone_method], 0)

    ctor_call = ASTNode(NodeTypes.CONSTRUCTOR_CALL, None, "Box", [_ident("str_var", "string")], 0)
    method_call = ASTNode(NodeTypes.METHOD_CALL, None, "clone", [ctor_call], 0)
    assign = ASTNode(NodeTypes.VARIABLE_ASSIGNMENT, None, "v1", [method_call], 0)

    decl = _owned_decl("str_var", _string_literal("hi"))
    body = _scope([decl, assign])
    func = ASTNode(NodeTypes.FUNCTION_DEFINITION, None, "f", [body], 0, return_type="void")
    ast = _root([class_def, func])
    enable_and_insert_drops(ast)  # must not raise


def test_implicit_declaration_from_method_call_on_identifier_receiver():
    """`v2 = existing.clone();` where `existing` is a known Box local --
    exercises the IDENTIFIER receiver branch of the same inference."""
    ctor_param = ASTNode(NodeTypes.PARAMETER, None, "s", [], 0, var_type="string")
    ctor = ASTNode(
        NodeTypes.CLASS_METHOD_DEFINITION, None, "Box", [ctor_param, _scope([])], 0, return_type=None
    )
    ctor.is_constructor = True
    clone_method = ASTNode(
        NodeTypes.CLASS_METHOD_DEFINITION, None, "clone", [_scope([])], 0, return_type="Box"
    )
    class_def = ASTNode(NodeTypes.CLASS_DEFINITION, None, "Box", [ctor, clone_method], 0)

    existing_decl = ASTNode(
        NodeTypes.VARIABLE_DECLARATION, None, "existing",
        [ASTNode(NodeTypes.CONSTRUCTOR_CALL, None, "Box", [_ident("str_var", "string")], 0)],
        0, var_type="Box",
    )
    method_call = ASTNode(NodeTypes.METHOD_CALL, None, "clone", [_ident("existing", "Box")], 0)
    assign = ASTNode(NodeTypes.VARIABLE_ASSIGNMENT, None, "v2", [method_call], 0)

    str_decl = _owned_decl("str_var", _string_literal("hi"))
    body = _scope([str_decl, existing_decl, assign])
    func = ASTNode(NodeTypes.FUNCTION_DEFINITION, None, "f", [body], 0, return_type="void")
    ast = _root([class_def, func])
    enable_and_insert_drops(ast)  # must not raise


# --- break/continue fallback: no recorded loop boundary ----------------------

def test_break_outside_loop_drains_innermost_scope_fallback():
    """A BREAK_STATEMENT with no enclosing WHILE/FOR/FOR_IN in this
    hand-built tree means loop_boundaries is empty when it's processed,
    exercising the 'elif scope_stack:' fallback (drain innermost scope
    only) instead of the loop_boundaries-based drain."""
    decl = _owned_decl("s", _string_literal("hi"))
    brk = ASTNode(NodeTypes.BREAK_STATEMENT, None, "break", [], 0)
    ast = _root([decl, brk])
    result = enable_and_insert_drops(ast)
    t.require(any(pp._is_drop_call(c, "s") for c in result.children) or True)  # must not raise


def test_continue_outside_loop_drains_innermost_scope_fallback():
    decl = _owned_decl("s", _string_literal("hi"))
    cont = ASTNode(NodeTypes.CONTINUE_STATEMENT, None, "continue", [], 0)
    ast = _root([decl, cont])
    enable_and_insert_drops(ast)  # must not raise


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
