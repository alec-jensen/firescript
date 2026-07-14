"""Direct unit tests for defensive "impossible" guards in
firescript/parser/declarations.py: `consume(TOKEN_TYPE)` immediately after
an equivalent `current_token.type == TOKEN_TYPE` check can never actually
return None, but the guard exists anyway. Each test monkeypatches
`consume` for exactly one call to force the None branch, covering the
guard's own body without claiming these are reachable from real input."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from lexer import Lexer  # noqa: E402
from parser import Parser  # noqa: E402


def _parser_for(src: str) -> Parser:
    tokens = Lexer(src).tokenize()
    return Parser(tokens, src, "test.fire")


def _force_next_consume_none(p: Parser) -> None:
    """Make the *next* call to p.consume(...) return None regardless of
    the current token, then restore normal behavior for subsequent calls."""
    original = p.consume
    state = {"used": False}

    def _patched(token_type):
        if not state["used"]:
            state["used"] = True
            return None
        return original(token_type)

    p.consume = _patched


def test_parse_import_symbol_group_handles_none_from_consume():
    p = _parser_for("import utils.{a};")
    for _ in range(3):  # 'import' 'utils' '.' -> leaves current_token at '{'
        p.advance()
    # _parse_import_symbol_group's own advance() past '{' happens
    # internally; the identifier consume() right after that is what we
    # force to return None despite the type check just before it passing.
    _force_next_consume_none(p)
    result = p._parse_import_symbol_group([])
    t.require_eq(result, False)
    t.require_eq(len(p.errors), 1)


def test_parse_class_definition_handles_none_class_consume():
    p = _parser_for("class Foo { }")
    _force_next_consume_none(p)
    result = p._parse_class_definition()
    t.require(result is None)


def test_parse_class_definition_handles_none_type_param_consume():
    p = _parser_for("class Foo<T> { }")
    p.advance()  # 'class'
    p.advance()  # 'Foo'
    # current_token is now '<'; force the type-param IDENTIFIER consume()
    # to return None despite the type check passing.
    _force_next_consume_none(p)
    result = p._parse_class_definition()
    t.require(result is None)


def test_parse_constraint_declaration_handles_none_constraint_consume():
    p = _parser_for("constraint Foo = int32;")
    _force_next_consume_none(p)
    result = p._parse_constraint_declaration()
    t.require(result is None)


# Note: _parse_constraint_declaration's `type_tok is None` check (right
# after `type_tok = self.current_token; self.advance()`) is unreachable
# even via monkeypatching consume() -- type_tok is captured directly from
# current_token, not returned by a consume() call, so there's nothing to
# intercept. Left uncovered as genuinely dead code.
