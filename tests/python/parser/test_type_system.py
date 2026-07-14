"""Direct unit tests for firescript/parser/type_system.py's defensive
branches that are hard to trigger through a real .fire program."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from lexer import Lexer  # noqa: E402
from parser import Parser  # noqa: E402
from parser.ast_node import ASTNode  # noqa: E402
from enums import NodeTypes  # noqa: E402
import parser.type_system as type_system_mod  # noqa: E402


def _parser_for(src: str) -> Parser:
    tokens = Lexer(src).tokenize()
    return Parser(tokens, src, "test.fire")


def test_annotate_value_category_swallows_exception():
    p = _parser_for("int32 x = 1;")
    node = ASTNode(NodeTypes.IDENTIFIER, None, "x", [], 0)

    original = type_system_mod.is_owned

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated is_owned failure")

    type_system_mod.is_owned = _raise
    try:
        # Must not raise; value_category is simply left unset.
        p._annotate_value_category(node, "int32", False)
        t.require(not hasattr(node, "value_category") or node.value_category is None)
    finally:
        type_system_mod.is_owned = original


def test_annotate_value_category_owned():
    p = _parser_for("int32 x = 1;")
    node = ASTNode(NodeTypes.IDENTIFIER, None, "arr", [], 0)
    p._annotate_value_category(node, "int32", True)  # arrays are Owned
    t.require_eq(node.value_category, "Owned")


def test_annotate_value_category_copyable():
    p = _parser_for("int32 x = 1;")
    node = ASTNode(NodeTypes.IDENTIFIER, None, "x", [], 0)
    p._annotate_value_category(node, "int32", False)
    t.require_eq(node.value_category, "Copyable")
