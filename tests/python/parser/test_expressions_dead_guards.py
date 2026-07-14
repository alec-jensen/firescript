"""Direct unit tests for defensive "impossible" guards in
firescript/parser/expressions.py.

Each of these methods is only ever invoked by callers (parse_primary's
dispatch, _parse_statement's dispatch) after already checking that the
current token matches the method's expected entry token. That means the
"couldn't consume the expected entry token" branches inside these methods
can never be reached by parsing any real source text -- the only way to
observe them is to call the method directly with the parser positioned on
the wrong token, which is what these tests do.
"""
from __future__ import annotations

import os
import sys

from harness import pyunit as t

sys.path.insert(0, os.path.dirname(__file__))
from _dead_guard_helpers import make_parser  # noqa: E402


def test_parse_array_literal_without_open_bracket_is_defensive_none():
    p = make_parser("1, 2, 3]")
    result = p.parse_array_literal()
    t.require(result is None)
    t.require(any(e.code == "FS-PARSE-0010" for e in p.errors))


def test_parse_array_access_without_open_bracket_is_defensive_none():
    p = make_parser("0]")
    array_node = p.parse_primary()  # not used as an array; just a placeholder node
    result = p.parse_array_access(array_node)
    t.require(result is None)
    t.require(any(e.code == "FS-PARSE-0010" for e in p.errors))


def test_parse_match_expression_without_match_token_is_defensive_none():
    p = make_parser("1 + 1")
    result = p._parse_match_expression()
    t.require(result is None)


def test_parse_compound_assignment_without_identifier_is_defensive_none():
    p = make_parser("+= 1")
    result = p.parse_compound_assignment()
    t.require(result is None)
    t.require(any(e.code == "FS-PARSE-0010" for e in p.errors))


def test_parse_compound_assignment_wrong_operator_reports_error():
    """Reached by calling parse_compound_assignment() directly on
    `x = 1` (no compound-assign operator after the identifier) -- the
    statement dispatcher in statements.py would never route here for this
    token stream (it only calls this method when the next token is one of
    the five compound-assign operators), so this branch is unreachable
    through _parse_statement()."""
    p = make_parser("x = 1")
    result = p.parse_compound_assignment()
    t.require(result is None)
    t.require(any(e.code == "FS-PARSE-0012" for e in p.errors))


def test_parse_increment_or_decrement_without_identifier_is_defensive_none():
    p = make_parser("++ x")
    result = p.parse_increment_or_decrement()
    t.require(result is None)
    t.require(any(e.code == "FS-PARSE-0010" for e in p.errors))


def test_parse_increment_or_decrement_wrong_operator_reports_error():
    """Same shape as test_parse_compound_assignment_wrong_operator_reports_error:
    _parse_statement() only calls parse_increment_or_decrement() when the next
    token is INCREMENT/DECREMENT, so this else-branch is otherwise dead."""
    p = make_parser("x = 1")
    result = p.parse_increment_or_decrement()
    t.require(result is None)
    t.require(any(e.code == "FS-PARSE-0012" for e in p.errors))
