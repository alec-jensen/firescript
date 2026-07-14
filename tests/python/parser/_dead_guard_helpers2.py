"""Shared helpers for hand-built parser-state coverage tests (not a test module itself).

Some branches in firescript/parser/{declarations,type_system,statements}.py are
defensive guards that can only be exercised by constructing parser state
directly (bypassing the normal lex -> top-level-dispatch path), because the
top-level dispatch heuristics in `parse()` already validate the conditions
these guards check before ever calling into the deeper parsing routines. See
CLAUDE.md's testing philosophy: such genuinely-unreachable-from-real-source
branches are covered here via direct method calls / monkeypatching rather than
left silently uncovered.

Import from this module in test files; do not redefine these helpers. Since
this directory is not a Python package on sys.path by default, each test
file must add its own directory to sys.path before importing, e.g.::

    import os, sys
    sys.path.insert(0, os.path.dirname(__file__))
    from _dead_guard_helpers import make_parser, error_codes
"""
from __future__ import annotations

import os
import sys
from typing import Optional

from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from lexer import Lexer, Token  # noqa: E402
from parser import Parser, ASTNode  # noqa: E402


def blank_token(token_type: str, value: str = "", index: int = 0) -> Token:
    """Construct a bare Token for hand-built parser states."""
    return Token(token_type, value, index)


def make_parser(source_text: str, defer_undefined_identifiers: Optional[bool] = None) -> Parser:
    """Lex `source_text` and return a fresh (not-yet-parsed) Parser positioned
    at the first token. Callers typically then invoke a private parsing
    method directly (e.g. ``parser._parse_function_definition()``)."""
    tokens = Lexer(source_text).tokenize()
    return Parser(tokens, source_text, "<test>", defer_undefined_identifiers=defer_undefined_identifiers)


def make_parser_from_tokens(tokens: list[Token], defer_undefined_identifiers: Optional[bool] = None) -> Parser:
    """Build a Parser directly from a hand-built token list."""
    src = " ".join(t.value for t in tokens)
    return Parser(tokens, src, "<test>", defer_undefined_identifiers=defer_undefined_identifiers)


def parse_source(source_text: str, defer_undefined_identifiers: Optional[bool] = None) -> tuple[Parser, ASTNode]:
    """Run the full parser pipeline (lex + parse()) and return (parser, ast)."""
    parser = make_parser(source_text, defer_undefined_identifiers=defer_undefined_identifiers)
    ast = parser.parse()
    return parser, ast


def error_codes(parser: Parser) -> list[str]:
    """Return the list of error codes recorded on `parser.errors`, in order."""
    return [e.code for e in parser.errors]


def _force_next_consume_none(parser: Parser, token_type: str) -> None:
    """Monkeypatch `parser.consume` so the next call with `token_type` returns
    None (simulating a consume failure) without altering `current_token`,
    then restores normal behavior for subsequent calls."""
    original_consume = parser.consume
    state = {"done": False}

    def patched(tt: str):
        if not state["done"] and tt == token_type:
            state["done"] = True
            return None
        return original_consume(tt)

    parser.consume = patched  # type: ignore[method-assign]
