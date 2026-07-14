"""Shared helpers for direct (in-process) parser unit tests.

Most parser behavior is exercised end-to-end through .fire test sources
(see tests/sources/** and tests/sources/invalid/**) run via the CLI, which
is preferred whenever a real source snippet can reach the code path. This
module exists for the residual cases that can't be reached that way: pure
defensive "impossible" guards deep in helper methods where the only way to
land on the branch is to build parser state directly (see
test_declarations_dead_guards.py for examples of that pattern).
"""
from __future__ import annotations

import os
import sys

from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from lexer import Lexer, Token  # noqa: E402
from parser import Parser, ASTNode  # noqa: E402


def make_parser(source: str, filename: str = "<test>", defer_undefined_identifiers=None) -> Parser:
    """Tokenize `source` and construct a Parser positioned at the first token."""
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    return Parser(tokens, source, filename, defer_undefined_identifiers=defer_undefined_identifiers)


def parse_source(source: str, filename: str = "<test>", defer_undefined_identifiers=None):
    """Tokenize + fully parse `source`. Returns (parser, ast)."""
    parser_instance = make_parser(source, filename, defer_undefined_identifiers)
    ast = parser_instance.parse()
    return parser_instance, ast


def error_codes(parser_instance: Parser) -> list[str]:
    return [e.code for e in parser_instance.errors]


def _force_next_consume_none(parser_instance: Parser) -> None:
    """Force the next call to `parser_instance.consume(...)` to fail (return None)
    regardless of the current token, by pointing current_token at an
    exhausted/blank position. Used to reach defensive "consume() must
    succeed because we just checked the type" guards that can't be hit
    through any real token stream.
    """
    parser_instance.current_token = None


def blank_token(token_type: str = "IDENTIFIER", value: str = "") -> Token:
    """A synthetic token with blank/whitespace value, mimicking the lexer's
    internal whitespace-placeholder IDENTIFIER tokens (see ParserBase.advance,
    which treats blank-value IDENTIFIER tokens as skippable whitespace)."""
    return Token(token_type, value, 0)
