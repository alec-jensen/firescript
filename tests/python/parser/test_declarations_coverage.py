"""Direct unit tests for firescript/parser/declarations.py's
`_parse_function_definition`, for the few parse paths that no compile-fail
or run .fire source reaches: a missing function name, a missing '(' after the
name, and an `owned` array parameter. Each test calls the method directly on
a Parser positioned at the `fn` token, bypassing parse()'s top-level
dispatch loop."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from enums import NodeTypes  # noqa: E402
from _helpers import make_parser, error_codes  # noqa: E402


def test_function_definition_rejects_missing_name():
    p = make_parser("fn + () -> int32 {}")
    result = p._parse_function_definition()
    t.require(result is None)
    t.require("FS-PARSE-0010" in error_codes(p))


def test_function_definition_missing_open_paren():
    p = make_parser("fn foo {}")
    result = p._parse_function_definition()
    t.require(result is None)
    t.require("FS-PARSE-0010" in error_codes(p))


def test_function_definition_owned_array_param():
    """'owned' combined with an array-typed parameter on a plain (free)
    function -- not exercised by any real .fire test, since free functions
    taking owned array params aren't otherwise needed by the test suite's
    example programs."""
    p = make_parser("fn foo(owned xs: int32[]) -> void {}")
    result = p._parse_function_definition()
    t.require(result is not None)
    param = result.children[0]
    t.require_eq(param.node_type, NodeTypes.PARAMETER)
    t.require(getattr(param, "is_owned", False))
    t.require(param.is_array)
