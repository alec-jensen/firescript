"""Shared helpers for direct parser unit tests (tests/python/parser/**).

Real, reachable behavior should be tested via .fire sources under
tests/sources/** instead; these helpers are only for the narrow cases that
need a Parser constructed or driven directly.
"""
from __future__ import annotations

import os
import sys

from harness.config import REPO_ROOT

_FIRESCRIPT_DIR = os.path.join(REPO_ROOT, "firescript")
if _FIRESCRIPT_DIR not in sys.path:
    sys.path.insert(0, _FIRESCRIPT_DIR)

from lexer import Lexer  # noqa: E402
from parser import Parser  # noqa: E402


def make_parser(source_text: str, filename: str = "<test>", defer_undefined_identifiers=None) -> Parser:
    tokens = Lexer(source_text).tokenize()
    return Parser(tokens, source_text, filename, defer_undefined_identifiers)


def error_codes(parser: Parser) -> list[str]:
    return [getattr(e, "code", None) for e in parser.errors]
