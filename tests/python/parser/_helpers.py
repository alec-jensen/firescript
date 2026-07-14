"""Shared helpers for direct parser unit tests (tests/python/parser/**).

These tests exercise defensive/"impossible" guard branches in
firescript/parser/statements.py and firescript/parser/type_system.py that
cannot be reached through any real .fire source -- the calling code already
validated the exact condition being re-checked. Real, reachable behavior
should be tested via .fire sources under tests/sources/** instead; this
module is only for the narrow leftover dead-guard cases.
"""
from __future__ import annotations

import os
import sys

from harness.config import REPO_ROOT

_FIRESCRIPT_DIR = os.path.join(REPO_ROOT, "firescript")
if _FIRESCRIPT_DIR not in sys.path:
    sys.path.insert(0, _FIRESCRIPT_DIR)

from lexer import Lexer, Token  # noqa: E402
from parser import Parser  # noqa: E402


def tokenize(source_text: str):
    return Lexer(source_text).tokenize()


def make_parser(source_text: str, filename: str = "<test>", defer_undefined_identifiers=None) -> Parser:
    tokens = tokenize(source_text)
    return Parser(tokens, source_text, filename, defer_undefined_identifiers)


def blank_token(token_type: str = "IDENTIFIER", value: str = "", index: int = 0) -> Token:
    return Token(token_type, value, index)


def error_codes(parser: Parser) -> list[str]:
    return [getattr(e, "code", None) for e in parser.errors]


def force_current_token_none(parser: Parser) -> None:
    """Force parser.current_token to None without changing token index bookkeeping.

    Used to drive an already-past-the-end parser state into a code path that
    only triggers when current_token is None.
    """
    parser.current_token = None
