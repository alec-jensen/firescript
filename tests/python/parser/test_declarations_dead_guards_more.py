"""Coverage for firescript/parser/declarations.py branches that cannot be
reached through the normal top-level parse() dispatch, because the
top-level heuristics that decide "is this a function/generator/etc.
definition" already validate the exact condition the deeper branch checks
again (defense in depth). Each test below builds parser state directly and
calls the relevant private method, per CLAUDE.md's testing philosophy
("genuinely unreachable from real source" -> hand-built parser state /
monkeypatched `consume`, documented rather than left silently uncovered).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from harness import pyunit as t  # noqa: E402
from _dead_guard_helpers2 import make_parser, error_codes, _force_next_consume_none  # noqa: E402


def test_function_definition_invalid_return_type_direct():
    # Top-level dispatch only calls _parse_function_definition() when the
    # lookahead already proves the return type is valid (a type token, or
    # IDENTIFIER followed by IDENTIFIER '<' for a generic function). Feeding
    # the method a bare "Foo(" bypasses that guarantee.
    p = make_parser("Foo(")
    result = p._parse_function_definition()
    t.require(result is None)
    t.require_eq(error_codes(p), ["FS-PARSE-0010"])


def test_function_definition_unclosed_array_return_bracket_direct():
    # The top-level lookahead pattern for an array return type
    # (OPEN_BRACKET CLOSE_BRACKET IDENTIFIER OPEN_PAREN) only matches when
    # the bracket is already balanced, so the "unclosed '['" branch inside
    # _parse_function_definition can't be reached via real dispatch.
    p = make_parser("int32[ badRet")
    result = p._parse_function_definition()
    t.require(result is None)
    t.require_eq(error_codes(p), ["FS-PARSE-0010"])


def test_function_definition_missing_name_direct():
    # Top-level dispatch requires an IDENTIFIER right after the return type
    # before treating a statement as a function definition, so the "missing
    # function name" branch is unreachable from real source.
    p = make_parser("int32 (")
    result = p._parse_function_definition()
    t.require(result is None)
    t.require_eq(error_codes(p), ["FS-PARSE-0010"])


def test_function_definition_missing_type_param_name_direct():
    p = make_parser("int32 foo<")
    result = p._parse_function_definition()
    t.require(result is None)
    t.require_eq(error_codes(p), ["FS-PARSE-0010"])


def test_function_definition_type_param_consume_failure_is_dead_but_guarded():
    # declarations.py checks `current_token.type == "IDENTIFIER"` and then
    # immediately calls `consume("IDENTIFIER")`, which cannot fail given the
    # preceding check -- forcing it anyway exercises the defensive
    # `if tparam_tok is None: return None` line without needing a real
    # inconsistent token stream (which cannot occur via the lexer). The
    # function name ("foo") is also consumed via consume("IDENTIFIER") one
    # step earlier, so the forced failure must target specifically the type
    # parameter token ("T"), not the first IDENTIFIER consume overall.
    p = make_parser("int32 foo<T>(T x) { return x; }")
    orig_consume = p.consume
    state = {"done": False}

    def patched(tt):
        if tt == "IDENTIFIER" and not state["done"] and p.current_token and p.current_token.value == "T":
            state["done"] = True
            return None
        return orig_consume(tt)

    p.consume = patched  # type: ignore[method-assign]
    result = p._parse_function_definition()
    t.require(result is None)


def test_function_definition_missing_close_angle_direct():
    p = make_parser("int32 foo<T(T x) { return x; }")
    result = p._parse_function_definition()
    t.require(result is None)
    t.require_eq(error_codes(p), ["FS-PARSE-0010"])


def test_function_definition_missing_open_paren_direct():
    # Top-level dispatch requires an OPEN_PAREN to even consider this a
    # function definition, so the "'(' after function name" branch can only
    # be reached by calling the method directly.
    p = make_parser("int32 foo;")
    result = p._parse_function_definition()
    t.require(result is None)
    t.require_eq(error_codes(p), ["FS-PARSE-0010"])


def test_function_definition_missing_body_brace_direct():
    p = make_parser("int32 foo()")
    result = p._parse_function_definition()
    t.require(result is None)
    t.require_eq(error_codes(p), ["FS-PARSE-0010"])


def test_generator_definition_missing_generator_token_is_dead():
    # _parse_generator_definition() is only ever invoked when current_token
    # is already GENERATOR (top-level dispatch and _parse_statement() both
    # check this first), so consume("GENERATOR") can never fail in
    # practice. Force it to hit the defensive early-return anyway.
    p = make_parser("generator<int32> g() { yield 1; }")
    _force_next_consume_none(p, "GENERATOR")
    result = p._parse_generator_definition()
    t.require(result is None)


def test_generator_definition_bad_param_type_direct():
    p = make_parser("generator<int32> g(&x) { yield 1; }")
    result = p._parse_generator_definition()
    t.require(result is None)
    t.require_eq(error_codes(p), ["FS-PARSE-0010"])


def test_generator_definition_missing_body_brace_direct():
    p = make_parser("generator<int32> g()")
    result = p._parse_generator_definition()
    t.require(result is None)
    t.require_eq(error_codes(p), ["FS-PARSE-0010"])


def test_top_level_skips_blank_placeholder_identifier_token():
    # parse()'s top-level loop has a defensive branch for a blank-valued
    # IDENTIFIER token ("Handle potential whitespace/newline tokens if the
    # lexer produces them") but the real Lexer never emits such tokens --
    # only real content tokens. Build one by hand to exercise the skip.
    from lexer import Token

    p = make_parser("int32 x = 1;")
    p.tokens = [Token("IDENTIFIER", "", 0), *p.tokens]
    p.current_token = p.tokens[0]
    p._token_idx = 0
    ast = p.parse()
    t.require_eq(error_codes(p), [])
    # The blank token was skipped; the real declaration still parsed.
    t.require(any(c.name == "x" for c in ast.children))


def test_export_pending_flag_before_constraint_dispatch_is_dead():
    # The EXPORT branch in parse() checks for a following CONSTRAINT token
    # synchronously (skipping comments) and resolves/rejects the pending
    # export right there, before the loop ever reaches the standalone
    # "current_token.type == CONSTRAINT" dispatch with `_pending_export`
    # still True. That standalone check is defense in depth; simulate the
    # state directly.
    p = make_parser("constraint Foo = int32;")
    p._pending_export = True
    ast = p.parse()
    t.require(len(p.errors) >= 1)
    t.require(not p._pending_export)


def test_import_symbol_group_consume_failure_is_dead():
    # Same double-check pattern as the type-parameter case above: the
    # identifier type is validated, then consume() is called immediately
    # after, so it cannot fail in practice.
    p = make_parser("{helper}")
    symbols: list = []
    _force_next_consume_none(p, "IDENTIFIER")
    ok = p._parse_import_symbol_group(symbols)
    t.require(ok is False)


def test_import_at_branch_missing_identifier_after_at_is_dead():
    # The check right before `consume("IDENTIFIER")` already validated
    # current_token.type == "IDENTIFIER", so the consume() itself cannot
    # fail via any real token stream; force it to hit the defensive
    # `if idtok is None` branch.
    p = make_parser("import @firescript;")
    _force_next_consume_none(p, "IDENTIFIER")
    result = p._parse_import()
    t.require(result is None)


def test_import_at_branch_slash_identifier_consume_failure_is_dead():
    p = make_parser("import @firescript/std;")
    # Let the first two IDENTIFIER consumes ('firescript') succeed, then
    # force the one right after '/' to fail despite being pre-validated.
    orig_consume = p.consume
    calls = {"n": 0}

    def patched(tt):
        if tt == "IDENTIFIER":
            calls["n"] += 1
            if calls["n"] == 2:
                return None
        return orig_consume(tt)

    p.consume = patched  # type: ignore[method-assign]
    result = p._parse_import()
    # The forced consume() failure only breaks the '/'-segment loop (not a
    # hard parse failure), so _parse_import still returns a node -- but the
    # defensive error path was recorded.
    t.require(result is not None)
    t.require_eq(error_codes(p), ["FS-PARSE-0010"])


def test_class_definition_missing_class_token_is_dead():
    # _parse_class_definition() is only invoked when current_token is
    # CLASS or COPYABLE, so consume("CLASS") cannot fail in practice.
    p = make_parser("class Foo { int32 v; }")
    _force_next_consume_none(p, "CLASS")
    result = p._parse_class_definition()
    t.require(result is None)


def test_class_definition_type_param_consume_failure_is_dead():
    # As above: the class *name* ("Foo") is also consumed via
    # consume("IDENTIFIER") one step earlier than the type parameter
    # ("T"), so the forced failure must target the type parameter token
    # specifically.
    p = make_parser("class Foo<T> { int32 v; }")
    orig_consume = p.consume
    state = {"done": False}

    def patched(tt):
        if tt == "IDENTIFIER" and not state["done"] and p.current_token and p.current_token.value == "T":
            state["done"] = True
            return None
        return orig_consume(tt)

    p.consume = patched  # type: ignore[method-assign]
    result = p._parse_class_definition()
    t.require(result is None)
