"""Direct unit tests for firescript/semantic_analyzer.py's less-common
branches: report_error()'s node-less, no-source-code and out-of-range
fallbacks, _expr_is_owned_value fallbacks, _merge_state_pair's full truth
table, _definitely_terminates' default-False fallback, _validate_match_arms'
empty-arms and enum-mismatch/unknown-enum branches, _validate_borrow's
error-reporting branch, and the "no children -> return early" guards and
ELIF/ELSE recursion in _analyze_node's dispatch."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from enums import NodeTypes  # noqa: E402
from parser.ast_node import ASTNode  # noqa: E402
from errors import SemanticError  # noqa: E402
from semantic_analyzer import SemanticAnalyzer, OwnershipState  # noqa: E402


def _root(children=None) -> ASTNode:
    return ASTNode(NodeTypes.ROOT, None, "root", children or [], 0)


def _analyzer(source_code=None, source_file="test.fire") -> SemanticAnalyzer:
    return SemanticAnalyzer(_root(), source_file=source_file, source_code=source_code)


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


def test_report_error_without_source_code_uses_no_line_info():
    analyzer = _analyzer(source_code=None)
    analyzer.error("synthetic error", ASTNode(NodeTypes.IDENTIFIER, None, "x", [], 0))
    t.require_eq(len(analyzer.errors), 1)
    t.require_eq(analyzer.errors[0].line, 0)


# --- _expr_is_owned_value ---------------------------------------------------------

def test_expr_is_owned_value_false_without_binding_or_return_type():
    analyzer = _analyzer()
    unbound = ASTNode(NodeTypes.IDENTIFIER, None, "unbound", [], 0)
    t.require(analyzer._expr_is_owned_value(unbound) is False)
    literal = ASTNode(NodeTypes.LITERAL, None, "1", [], 0, var_type="int32")
    t.require(analyzer._expr_is_owned_value(literal) is False)


def test_expr_is_owned_value_array_return_type_is_owned():
    analyzer = _analyzer()
    node = ASTNode(NodeTypes.FUNCTION_CALL, None, "make_boxes", [], 0, return_type="Box[]")
    t.require(analyzer._expr_is_owned_value(node) is True)


# --- _merge_state_pair -----------------------------------------------------------

_S = OwnershipState


@t.params([
    (_S.VALID, _S.VALID, _S.VALID),
    (_S.MOVED, _S.MOVED, _S.MOVED),
    (_S.MOVED, _S.MAYBE_MOVED, _S.MOVED),
    (_S.MAYBE_MOVED, _S.MOVED, _S.MOVED),
    (_S.MOVED, _S.VALID, _S.MAYBE_MOVED),
    (_S.VALID, _S.MOVED, _S.MAYBE_MOVED),
    (_S.MAYBE_MOVED, _S.VALID, _S.MAYBE_MOVED),
    (_S.MOVED, _S.BORROWED, _S.MAYBE_MOVED),
    (_S.BORROWED, _S.VALID, _S.BORROWED),
    (_S.VALID, _S.BORROWED, _S.BORROWED),
])
def test_merge_state_pair_truth_table(case):
    a, b, expected = case
    t.require_eq(_analyzer()._merge_state_pair(a, b), expected, f"{a} + {b}")


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


# --- _analyze_node: "no children -> return" guards and ELIF/ELSE recursion ----------

@t.params([
    NodeTypes.METHOD_CALL,
    NodeTypes.IF_STATEMENT,
    NodeTypes.MATCH_EXPRESSION,
    NodeTypes.WHILE_STATEMENT,
])
def test_analyze_node_childless_control_nodes_return_early(node_type):
    analyzer = _analyzer()
    analyzer._analyze_node(ASTNode(node_type, None, "n", [], 0))  # must not raise
    t.require_eq(analyzer.errors, [])


@t.params([NodeTypes.ELIF_STATEMENT, NodeTypes.ELSE_STATEMENT])
def test_analyze_node_elif_else_recurse_into_children(node_type):
    analyzer = _analyzer()
    inner = ASTNode(NodeTypes.IDENTIFIER, None, "z", [], 0)
    visited = []
    original = analyzer._analyze_node

    def _spy(node, *args, **kwargs):
        visited.append(node)
        return original(node, *args, **kwargs)

    analyzer._analyze_node = _spy
    original(ASTNode(node_type, None, "branch", [inner], 0))
    t.require(any(v is inner for v in visited), "child of ELIF/ELSE was not analyzed")
