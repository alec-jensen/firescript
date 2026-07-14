"""Direct unit tests for defensive/"impossible" guard branches in
firescript/parser/statements.py that cannot be reached from any real .fire
source, because the sole caller of each function already validated the
exact condition being re-checked inside it.

See tests/python/parser/_helpers.py for the shared parser-construction
helpers. Reachable behavior is covered by .fire sources under tests/sources/**
instead (see e.g. tests/sources/invalid/declarations/const_missing_type.fire,
tests/sources/invalid/generics/generic_class_*_errors.fire,
tests/sources/invalid/control_flow/*.fire) -- this module only fills in the
small number of leftover guards that no real source can reach.
"""
from __future__ import annotations

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from harness import pyunit as t
from parser.statements import StatementsMixin

from _helpers import make_parser, blank_token


def test_parse_if_statement_returns_none_when_not_at_if_token():
    # parse_if_statement() is only ever called from _parse_statement() after
    # confirming current_token.type == "IF"; calling it directly with the
    # cursor elsewhere exercises the defensive `if not if_token: return None`
    # guard at statements.py:29.
    p = make_parser("42;")
    result = p.parse_if_statement()
    t.require(result is None)


def test_parse_while_statement_returns_none_when_not_at_while_token():
    # Same defensive pattern as parse_if_statement, for the WHILE keyword
    # guard at statements.py:327.
    p = make_parser("42;")
    result = p.parse_while_statement()
    t.require(result is None)


def test_parse_for_statement_returns_none_when_not_at_for_token():
    # Same defensive pattern, for the FOR keyword guard at statements.py:367.
    p = make_parser("42;")
    result = p.parse_for_statement()
    t.require(result is None)


def test_if_statement_condition_none_with_close_paren_still_present():
    # In real source, whenever parse_expression() fails to produce a
    # condition, the low-level primary parser has already consumed the
    # offending token as part of its own error recovery (see
    # expressions.py's "Unexpected token" path), so by the time
    # parse_if_statement() checks `self.current_token.type == "CLOSE_PAREN"`
    # after a None condition, the ')' has always already been consumed too.
    # That specific consume-branch (statements.py:38-39) is therefore only
    # reachable by forcing parse_expression() to fail while leaving the
    # cursor sitting exactly on the CLOSE_PAREN token.
    p = make_parser("if () {}")
    p.parse_expression = lambda: None  # type: ignore[method-assign]
    result = p.parse_if_statement()
    t.require(result is None)
    # The forced-None condition path must still consume the ')' token.
    t.require(p.current_token is not None and p.current_token.type == "OPEN_BRACE")


def test_while_statement_condition_none_with_close_paren_still_present():
    # Mirror of the IF case above, for statements.py:333-334.
    p = make_parser("while () {}")
    p.parse_expression = lambda: None  # type: ignore[method-assign]
    result = p.parse_while_statement()
    t.require(result is None)
    t.require(p.current_token is not None and p.current_token.type == "OPEN_BRACE")


def test_if_statement_then_branch_none_is_defensive():
    # parse_scope() always returns a real SCOPE node once an OPEN_BRACE has
    # been confirmed present (the only way it returns None is failing to
    # consume the '{', which can't happen here since the caller already
    # checked current_token.type == "OPEN_BRACE"). Monkeypatch parse_scope
    # to force the "then_branch_node is None" guard at statements.py:53-55.
    p = make_parser("if (true) {}")
    p.parse_scope = lambda: None  # type: ignore[method-assign]
    result = p.parse_if_statement()
    t.require(result is None)
    t.require(len(p.errors) >= 1)


def test_while_statement_body_none_is_defensive():
    # Same reasoning as above, for the while-body guard at statements.py:346.
    p = make_parser("while (true) {}")
    p.parse_scope = lambda: None  # type: ignore[method-assign]
    result = p.parse_while_statement()
    t.require(result is None)


def test_for_in_statement_body_none_is_defensive():
    # Same reasoning, for statements.py:419-421 (for-in body).
    p = make_parser("for (int32 i in arr) {}")
    p.parse_scope = lambda: None  # type: ignore[method-assign]
    result = p.parse_for_statement()
    t.require(result is None)


def test_for_c_style_statement_body_none_is_defensive():
    # Same reasoning, for statements.py:500 (C-style for body).
    p = make_parser("for (int32 i = 0; i < 10; i++) {}")
    p.parse_scope = lambda: None  # type: ignore[method-assign]
    result = p.parse_for_statement()
    t.require(result is None)


class _ToggleContainer:
    """A `TYPE_TOKEN_NAMES`-like container whose membership test is True on
    the first call and False afterwards, used to force the guaranteed-true
    recheck at statements.py:388 to observe a (real-code-impossible) False
    on its second read of the same, unmoved current_token."""

    def __init__(self, real):
        self._real = real
        self._n = 0

    def __contains__(self, item):
        self._n += 1
        if self._n == 1:
            return item in self._real
        return False


def test_for_in_type_recheck_is_defensive():
    # The `is_for_in` lookahead at statements.py:377-383 already confirms
    # current_token.type is in TYPE_TOKEN_NAMES before is_for_in is set
    # True, and nothing advances the cursor before the recheck at
    # statements.py:388-390, so that recheck can never actually fail in real
    # source. Toggle TYPE_TOKEN_NAMES's membership test to observe False on
    # its second (redundant) read.
    p = make_parser("for (int32 i in arr) {}")
    p.TYPE_TOKEN_NAMES = _ToggleContainer(type(p).TYPE_TOKEN_NAMES)  # type: ignore[attr-defined]
    result = p.parse_for_statement()
    t.require(result is None)


def test_for_in_loop_var_name_recheck_is_defensive():
    # statements.py:395-397: after the type-token check passes, the parser
    # advances past it; the loop-var-name recheck can only fail if the real
    # next token isn't actually an IDENTIFIER, which the `is_for_in`
    # lookahead already ruled out via peek(1). Lie about peek(1)/peek(2) to
    # get is_for_in set True despite the real second token not being an
    # identifier, so the post-advance recheck sees the real (non-identifier)
    # token and fails.
    p = make_parser("for (int32 + in arr) {}")
    real_peek = p.peek

    def fake_peek(offset: int = 1):
        if offset == 1:
            return blank_token("IDENTIFIER", "fake")
        if offset == 2:
            return blank_token("IN", "in")
        return real_peek(offset)

    p.peek = fake_peek  # type: ignore[method-assign]
    result = p.parse_for_statement()
    t.require(result is None)


def test_for_in_missing_in_keyword_recheck_is_defensive():
    # statements.py:402-404: mirror of the above, but for the 'in' keyword
    # recheck -- lie only about peek(2) so is_for_in is set True even though
    # the real third token isn't IN.
    p = make_parser("for (int32 arr2 + collection) {}")
    real_peek = p.peek

    def fake_peek(offset: int = 1):
        if offset == 2:
            return blank_token("IN", "in")
        return real_peek(offset)

    p.peek = fake_peek  # type: ignore[method-assign]
    result = p.parse_for_statement()
    t.require(result is None)


def test_parse_variable_assignment_identifier_none_is_defensive():
    # parse_variable_assignment() is only called from _parse_statement()
    # after confirming token_type == "IDENTIFIER" and next token is ASSIGN,
    # so consume_name() inside it always succeeds in real flow
    # (statements.py:250-253).
    p = make_parser("= 5;")
    result = p.parse_variable_assignment()
    t.require(result is None)


def test_parse_variable_assignment_missing_assign_is_defensive():
    # statements.py:256-259: reachable only if an identifier is not
    # followed by '=', which the sole caller already guarantees.
    p = make_parser("x 5;")
    result = p.parse_variable_assignment()
    t.require(result is None)


def test_parse_function_call_missing_name_is_defensive():
    # parse_function_call() is only called after confirming current token is
    # an IDENTIFIER followed by '(' (statements.py:282-285).
    p = make_parser("(1, 2);")
    result = p.parse_function_call()
    t.require(result is None)


def test_parse_function_call_missing_open_paren_is_defensive():
    # statements.py:288-291.
    p = make_parser("foo 1;")
    result = p.parse_function_call()
    t.require(result is None)


def test_parse_statement_dot_lhs_none_is_defensive():
    # statements.py:704-706: the DOT-continuation branch of _parse_statement
    # is only reached for an IDENTIFIER that _is_type_token() and
    # self.user_types/self.user_enums did NOT already intercept (those are
    # handled earlier in dispatch / inside parse_primary's own type-level
    # branches). For any such plain identifier, parse_primary always
    # manages to build at least an IDENTIFIER node before running out of
    # postfix continuations, so lhs is never actually None here. Force it by
    # monkeypatching parse_primary.
    p = make_parser("foo.bar;")
    p.parse_primary = lambda: None  # type: ignore[method-assign]
    result = p._parse_statement()
    t.require(result is None)


def test_parse_scope_missing_open_brace_is_defensive():
    # statements.py:761-763: every real call site of parse_scope() (in
    # statements.py's if/while/for handlers, and in declarations.py's
    # function/method/generator body parsing) checks
    # `current_token.type == "OPEN_BRACE"` before calling parse_scope(), so
    # the "'{' to start scope" error inside parse_scope() itself can never
    # fire from real source.
    p = make_parser("42;")
    result = p.parse_scope()
    t.require(result is None)
    t.require(len(p.errors) == 1)


def test_parse_statement_directive_without_declarations_mixin():
    # DIRECTIVE handling in _parse_statement() (statements.py:539-545) looks
    # up `_parse_directive` via getattr because StatementsMixin does not
    # itself implement directive parsing -- only DeclarationsMixin (further
    # down the real Parser's MRO) does. A bare StatementsMixin-only parser
    # (as could exist in a minimal embedding of this mixin) takes the "not
    # available" branch.
    class MiniParser(StatementsMixin):
        pass

    src = "directive enable_drops;"
    ref = make_parser(src)
    p = MiniParser(ref.tokens, src, "<test>")
    result = p._parse_statement()
    t.require(result is None)
    t.require(len(p.errors) == 1)


def test_parse_statement_generator_without_declarations_mixin():
    # Mirror of the above for GENERATOR handling (statements.py:553-557).
    class MiniParser(StatementsMixin):
        pass

    src = "generator<int32> gen() { yield 1; }"
    ref = make_parser(src)
    p = MiniParser(ref.tokens, src, "<test>")
    result = p._parse_statement()
    t.require(result is None)
