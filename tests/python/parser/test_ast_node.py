"""Direct unit tests for firescript/parser/ast_node.py's ASTNode: the
None-children guard and __repr__."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from parser.ast_node import ASTNode  # noqa: E402
from enums import NodeTypes  # noqa: E402


def test_constructor_rejects_none_in_children():
    try:
        ASTNode(NodeTypes.SCOPE, None, "scope", [None], 0)
        t.require(False, "expected ValueError")
    except ValueError as e:
        t.require("None" in str(e), str(e))


def test_repr_matches_str():
    node = ASTNode(NodeTypes.IDENTIFIER, None, "x", [], 0)
    t.require_eq(repr(node), str(node))
