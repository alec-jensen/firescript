"""Direct unit tests for firescript/semantic_analyzer.py's less-common
branches: BorrowInfo construction, report_error()'s node=None and
index-out-of-range except branches, error()'s convenience wrapper,
_is_direct_borrow_view / _expr_is_owned_value fallbacks, _merge_state_pair's
BORROWED/VALID/both-moved branches, _definitely_terminates' default-False
fallback, _validate_match_arms' empty-arms and enum-mismatch/unknown-enum
branches, _validate_borrow's error-reporting branch, and several
"no children -> return early" guards across _analyze_node's dispatch."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from enums import NodeTypes  # noqa: E402
from parser.ast_node import ASTNode  # noqa: E402
from errors import SemanticError  # noqa: E402
from semantic_analyzer import SemanticAnalyzer, BorrowInfo, BindingInfo, OwnershipState  # noqa: E402


def _root(children=None) -> ASTNode:
    return ASTNode(NodeTypes.ROOT, None, "root", children or [], 0)


def _analyzer(source_code=None, source_file="test.fire") -> SemanticAnalyzer:
    return SemanticAnalyzer(_root(), source_file=source_file, source_code=source_code)


# --- BorrowInfo ----------------------------------------------------------------

def test_borrow_info_stores_fields():
    node = ASTNode(NodeTypes.IDENTIFIER, None, "s", [], 0)
    info = BorrowInfo("s", node, 2)
    t.require_eq(info.borrowed_name, "s")
    t.require(info.borrow_node is node)
    t.require_eq(info.scope_depth, 2)


# --- report_error --------------------------------------------------------------

def test_report_error_without_node_appends_directly():
    analyzer = _analyzer(source_code=None)
    err = SemanticError(message="boom")
    analyzer.report_error(err)
    t.require_eq(len(analyzer.errors), 1)
    t.require_eq(analyzer.errors[0].source_file, "test.fire")


def test_report_error_with_out_of_range_node_falls_back():
    """get_line_and_coumn_from_index never raises (it just walks off the
    end of the string), but get_line(file, line) does an IndexError-prone
    `file.splitlines()[line - 1]` -- reachable when source_code is empty,
    since splitlines() then returns [] for any line number. This exercises
    report_error's except (IndexError, ValueError) fallback branch."""
    analyzer = _analyzer(source_code="")
    node = ASTNode(NodeTypes.IDENTIFIER, None, "x", [], 0)
    err = SemanticError(message="boom")
    analyzer.report_error(err, node)
    t.require_eq(len(analyzer.errors), 1)
    t.require_eq(analyzer.errors[0].source_file, "test.fire")


def test_error_convenience_method():
    analyzer = _analyzer(source_code=None)
    analyzer.error("something went wrong")
    t.require_eq(len(analyzer.errors), 1)
    t.require("something went wrong" in analyzer.errors[0].message)


# --- _is_direct_borrow_view fallback --------------------------------------------

def test_is_direct_borrow_view_false_for_unrelated_node_type():
    analyzer = _analyzer()
    literal = ASTNode(NodeTypes.LITERAL, None, "1", [], 0, var_type="int32")
    t.require(analyzer._is_direct_borrow_view(literal, {"s"}) is False)


# --- _expr_is_owned_value fallbacks ----------------------------------------------

def test_expr_is_owned_value_false_for_no_binding_no_return_type():
    analyzer = _analyzer()
    node = ASTNode(NodeTypes.IDENTIFIER, None, "unbound", [], 0)
    t.require(analyzer._expr_is_owned_value(node) is False)


def test_expr_is_owned_value_array_return_type():
    analyzer = _analyzer()
    node = ASTNode(NodeTypes.FUNCTION_CALL, None, "make_boxes", [], 0, return_type="Box[]")
    # Box is not a registered class here, so is_owned(...) resolves via the
    # default (unregistered types are treated as Owned) -- either way this
    # exercises the array-return-type branch without raising.
    analyzer._expr_is_owned_value(node)


def test_expr_is_owned_value_false_for_non_identifier_no_return_type():
    analyzer = _analyzer()
    node = ASTNode(NodeTypes.LITERAL, None, "1", [], 0, var_type="int32")
    t.require(analyzer._expr_is_owned_value(node) is False)


# --- _merge_state_pair -----------------------------------------------------------

def test_merge_state_pair_both_movedish_yields_moved():
    analyzer = _analyzer()
    result = analyzer._merge_state_pair(OwnershipState.MOVED, OwnershipState.MAYBE_MOVED)
    t.require_eq(result, OwnershipState.MOVED)


def test_merge_state_pair_borrowed_wins():
    analyzer = _analyzer()
    result = analyzer._merge_state_pair(OwnershipState.BORROWED, OwnershipState.VALID)
    t.require_eq(result, OwnershipState.BORROWED)


def test_merge_state_pair_default_valid():
    analyzer = _analyzer()
    result = analyzer._merge_state_pair(OwnershipState.VALID, OwnershipState.VALID)
    t.require_eq(result, OwnershipState.VALID)


# --- _definitely_terminates default False ----------------------------------------

def test_definitely_terminates_false_for_unrelated_node():
    analyzer = _analyzer()
    node = ASTNode(NodeTypes.VARIABLE_DECLARATION, None, "x", [], 0, var_type="int32")
    t.require(analyzer._definitely_terminates(node) is False)


# --- _validate_match_arms ----------------------------------------------------------

def test_validate_match_arms_empty_arms_reports_error():
    analyzer = _analyzer()
    match_node = ASTNode(NodeTypes.MATCH_EXPRESSION, None, "match", [], 0)
    analyzer._validate_match_arms(match_node, [])
    t.require(len(analyzer.errors) == 1)
    t.require("at least one arm" in analyzer.errors[0].message)


def test_validate_match_arms_enum_mismatch_and_unknown_enum():
    analyzer = _analyzer()
    analyzer.enum_variants = {"Color": {"Red": []}}
    match_node = ASTNode(NodeTypes.MATCH_EXPRESSION, None, "match", [], 0)

    arm1 = ASTNode(NodeTypes.MATCH_ARM, None, "arm1", [], 0)
    arm1.is_wildcard = False
    arm1.enum_name = "Color"
    arm1.variant_name = "Red"
    arm1.bindings = []

    arm2 = ASTNode(NodeTypes.MATCH_ARM, None, "arm2", [], 0)
    arm2.is_wildcard = False
    arm2.enum_name = "Shape"  # mismatched enum type vs arm1 -> line 445 branch
    arm2.variant_name = "Circle"
    arm2.bindings = []

    arm3 = ASTNode(NodeTypes.MATCH_ARM, None, "arm3", [], 0)
    arm3.is_wildcard = False
    arm3.enum_name = "TotallyUnknownEnum"  # -> unknown enum type branch (456-460)
    arm3.variant_name = "X"
    arm3.bindings = []

    analyzer._validate_match_arms(match_node, [arm1, arm2, arm3])
    messages = [e.message for e in analyzer.errors]
    t.require(any("does not match" in m for m in messages), messages)
    t.require(any("Unknown enum type" in m for m in messages), messages)


# --- _validate_borrow error branch --------------------------------------------------

def test_validate_borrow_reports_error_for_copyable_type():
    analyzer = _analyzer()
    node = ASTNode(NodeTypes.PARAMETER, None, "n", [], 0, var_type="int32")
    analyzer._validate_borrow("int32", False, node)
    t.require_eq(len(analyzer.errors), 1)
    t.require("Cannot borrow Copyable type" in analyzer.errors[0].message)


# --- _analyze_node: None input and "no children -> return" guards -------------------

def test_analyze_node_none_is_noop():
    analyzer = _analyzer()
    analyzer._analyze_node(None)  # must not raise
    t.require_eq(len(analyzer.errors), 0)


def test_analyze_node_method_call_no_children_returns_early():
    analyzer = _analyzer()
    node = ASTNode(NodeTypes.METHOD_CALL, None, "m", [], 0)
    analyzer._analyze_node(node)  # must not raise (early return)


def test_analyze_node_if_statement_no_children_returns_early():
    analyzer = _analyzer()
    node = ASTNode(NodeTypes.IF_STATEMENT, None, "if", [], 0)
    analyzer._analyze_node(node)


def test_analyze_node_match_expression_no_children_returns_early():
    analyzer = _analyzer()
    node = ASTNode(NodeTypes.MATCH_EXPRESSION, None, "match", [], 0)
    analyzer._analyze_node(node)


def test_analyze_node_while_statement_no_children_returns_early():
    analyzer = _analyzer()
    node = ASTNode(NodeTypes.WHILE_STATEMENT, None, "while", [], 0)
    analyzer._analyze_node(node)


def test_analyze_node_elif_else_recurse_into_children():
    analyzer = _analyzer()
    inner = ASTNode(NodeTypes.IDENTIFIER, None, "z", [], 0)
    elif_node = ASTNode(NodeTypes.ELIF_STATEMENT, None, "elif", [inner], 0)
    analyzer._analyze_node(elif_node)  # must not raise; recurses into `inner`

    else_node = ASTNode(NodeTypes.ELSE_STATEMENT, None, "else", [inner], 0)
    analyzer._analyze_node(else_node)


# --- _collect_function_signatures(None) is a no-op ----------------------------------

def test_collect_function_signatures_none_is_noop():
    analyzer = _analyzer()
    analyzer._collect_function_signatures(None)  # must not raise
    t.require_eq(analyzer.function_signatures, {})
