"""Direct unit tests for firescript/parser/declarations.py branches that are
awkward or impossible to reach by compiling a full real source file, either
because:

  * the branch is a defensive "impossible" guard that the top-level parse()
    dispatcher already rules out before calling the method (e.g.
    _parse_function_definition's own return-type/name re-validation, which
    duplicates checks parse() already performed in its lookahead before
    deciding to call it), or
  * exercising the branch through a full runnable program would also
    require satisfying unrelated semantic/ownership constraints that have
    nothing to do with the parser behavior actually under test.

Each test calls the relevant `_parse_*`/`parse_*` method directly on a
Parser positioned at the right starting token, bypassing parse()'s top-level
dispatch loop (see _dead_guard_helpers.make_parser).
"""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from enums import NodeTypes  # noqa: E402
from _dead_guard_helpers import make_parser, error_codes  # noqa: E402


# --- _parse_function_definition: guards parse()'s own lookahead already
# --- rules out in practice, only reachable by calling the method directly
# --- on a token stream that doesn't match that lookahead. ---

def test_function_definition_rejects_non_type_return():
    p = make_parser("fn foo() -> + {}")
    result = p._parse_function_definition()
    t.require(result is None)
    t.require("FS-PARSE-0010" in error_codes(p))


def test_function_definition_rejects_malformed_array_return_bracket():
    p = make_parser("fn foo() -> int32[5 {}")
    result = p._parse_function_definition()
    t.require(result is None)
    t.require("FS-PARSE-0010" in error_codes(p))


def test_function_definition_rejects_missing_name():
    p = make_parser("fn + () -> int32 {}")
    result = p._parse_function_definition()
    t.require(result is None)
    t.require("FS-PARSE-0010" in error_codes(p))


def test_function_definition_generic_type_param_missing_name():
    p = make_parser("fn foo<5>(x: T) -> T { return x; }")
    result = p._parse_function_definition()
    t.require(result is None)
    t.require("FS-PARSE-0010" in error_codes(p))


def test_function_definition_generic_constraint_missing_type():
    p = make_parser("fn foo<T: 5>(x: T) -> T { return x; }")
    result = p._parse_function_definition()
    t.require(result is None)
    t.require("FS-PARSE-0010" in error_codes(p))


def test_function_definition_generic_missing_close_angle():
    p = make_parser("fn foo<T (x: T) -> T { return x; }")
    result = p._parse_function_definition()
    t.require(result is None)


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
    p = make_parser("fn foo(xs: owned int32[]) -> void {}")
    result = p._parse_function_definition()
    t.require(result is not None)
    param = result.children[0]
    t.require_eq(param.node_type, NodeTypes.PARAMETER)
    t.require(getattr(param, "is_owned", False))
    t.require(param.is_array)


def test_function_definition_array_param_bad_size_token():
    p = make_parser("fn foo(xs: int32[3]) -> void {}")
    result = p._parse_function_definition()
    t.require(result is not None)
    param = result.children[0]
    t.require_eq(param.array_size, 3)


def test_function_definition_close_paren_missing():
    p = make_parser("fn foo(x: int32 {}")
    result = p._parse_function_definition()
    t.require(result is None)
    t.require("FS-PARSE-0010" in error_codes(p))


# --- _parse_function_definition with a generator<T> return type ------------
# Generators are no longer a distinct declaration form: `fn gen(...) ->
# generator<T> { ... }` goes through the exact same _parse_function_definition
# as any other function, so these guards -- previously exercised via the
# now-deleted _parse_generator_definition -- are checked here instead.

def test_generator_definition_borrowed_param():
    p = make_parser("fn gen(x: &int32) -> generator<int32> { yield x; }")
    result = p._parse_function_definition()
    t.require(result is not None)
    param = result.children[0]
    t.require(getattr(param, "is_borrowed", False))


def test_generator_definition_missing_close_paren():
    p = make_parser("fn gen(x: int32 { yield x; }")
    result = p._parse_function_definition()
    t.require(result is None)
    t.require("FS-PARSE-0010" in error_codes(p))


def test_generator_definition_missing_body_brace():
    p = make_parser("fn gen(x: int32) -> generator<int32> yield x;")
    result = p._parse_function_definition()
    t.require(result is None)
    t.require("FS-PARSE-0010" in error_codes(p))


# --- _parse_import ---

def test_import_symbol_group_bad_identifier():
    p = make_parser("import mod.{5, ok}")
    result = p._parse_import()
    t.require(result is None)
    t.require("FS-PARSE-0010" in error_codes(p))


def test_import_at_missing_identifier_after_at():
    p = make_parser("import @ 5")
    result = p._parse_import()
    t.require(result is None)
    t.require("FS-PARSE-0010" in error_codes(p))


def test_import_at_missing_identifier_after_slash():
    p = make_parser("import @pkg/")
    result = p._parse_import()
    t.require(result is not None)  # recovers, treated as external package
    t.require("FS-PARSE-0010" in error_codes(p))


def test_import_symbol_missing_after_dot():
    p = make_parser("import mod.")
    result = p._parse_import()
    t.require(result is None)
    t.require("FS-PARSE-0010" in error_codes(p))


def test_import_symbol_group_missing_close_brace():
    p = make_parser("import mod.{a, b")
    result = p._parse_import()
    t.require(result is None)
    t.require("FS-PARSE-0010" in error_codes(p))


def test_import_module_alias():
    p = make_parser("import mod as Alias")
    result = p._parse_import()
    t.require(result is not None)
    t.require_eq(getattr(result, "alias", None), "Alias")
    t.require_eq(getattr(result, "kind", None), "module")
