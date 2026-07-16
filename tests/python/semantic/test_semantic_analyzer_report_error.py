"""Direct unit tests for SemanticAnalyzer.report_error()/error() edge cases
that are hard to reach through a full compile: no source_code available
(e.g. embedded/tooling use), and a node whose .index falls outside the
source text (defensive IndexError/ValueError fallback)."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from parser import ASTNode  # noqa: E402
from enums import NodeTypes  # noqa: E402
from semantic_analyzer import SemanticAnalyzer  # noqa: E402


def _bare_node(index: int) -> ASTNode:
    return ASTNode(NodeTypes.IDENTIFIER, None, "x", [], index)


def test_report_error_without_source_code_uses_no_line_info():
    analyzer = SemanticAnalyzer(ASTNode(NodeTypes.ROOT, None, "program", [], 0), source_file="x.fire", source_code=None)
    node = _bare_node(0)
    analyzer.error("synthetic error", node)
    t.require_eq(len(analyzer.errors), 1)
    t.require_eq(analyzer.errors[0].line, 0)


def test_report_error_without_node_uses_no_line_info():
    analyzer = SemanticAnalyzer(ASTNode(NodeTypes.ROOT, None, "program", [], 0), source_file="x.fire", source_code="x: int32 = 1;\n")
    analyzer.error("synthetic error")
    t.require_eq(len(analyzer.errors), 1)
    t.require_eq(analyzer.errors[0].line, 0)


def test_report_error_index_out_of_range_falls_back_gracefully():
    analyzer = SemanticAnalyzer(ASTNode(NodeTypes.ROOT, None, "program", [], 0), source_file="x.fire", source_code="x: int32 = 1;\n")
    # Index far past the end of the 14-char source string.
    node = _bare_node(10_000)
    analyzer.error("synthetic out-of-range error", node)
    t.require_eq(len(analyzer.errors), 1)
    t.require_eq(analyzer.errors[0].source_file, "x.fire")


def test_report_error_negative_index_falls_back_gracefully():
    analyzer = SemanticAnalyzer(ASTNode(NodeTypes.ROOT, None, "program", [], 0), source_file="x.fire", source_code="x: int32 = 1;\n")
    node = _bare_node(-5)
    analyzer.error("synthetic negative-index error", node)
    t.require_eq(len(analyzer.errors), 1)
