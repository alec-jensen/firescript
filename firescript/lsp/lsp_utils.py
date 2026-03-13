"""Shared utility helpers for the firescript language server."""

import logging
import os
import pathlib
import urllib.request
from typing import Optional
from urllib.parse import unquote, urlparse

from lsprotocol.types import Position

from lexer import Lexer
from parser import ASTNode, Parser


def try_parse(text: str, file_path: str) -> Optional[ASTNode]:
    """Lex and parse text, returning a best-effort AST or None."""
    root_logger = logging.getLogger()
    prev_level = root_logger.level
    root_logger.setLevel(logging.CRITICAL + 1)
    try:
        lexer = Lexer(text)
        tokens = lexer.tokenize()
        if not tokens:
            return None
        parser_instance = Parser(tokens, text, file_path)
        try:
            return parser_instance.parse()
        except Exception:
            return parser_instance.ast
    except Exception:
        return None
    finally:
        root_logger.setLevel(prev_level)


def find_block_end(source: str, from_pos: int) -> int:
    """Return the index of the closing brace for the first block at or after from_pos."""
    i = source.find("{", from_pos)
    if i == -1:
        return len(source)
    i += 1
    depth = 1
    while i < len(source) and depth > 0:
        c = source[i]
        if c == '"':
            i += 1
            while i < len(source) and source[i] != '"':
                if source[i] == '\\':
                    i += 1
                i += 1
        elif c == '/' and i + 1 < len(source) and source[i + 1] == '/':
            while i < len(source) and source[i] != '\n':
                i += 1
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return len(source)


def cursor_offset(source: str, line: int, character: int) -> int:
    """Convert a 0-based LSP position to a source offset."""
    lines = source.split("\n")
    return sum(len(lines[i]) + 1 for i in range(min(line, len(lines)))) + character


def uri_to_path(uri: str) -> str:
    """Convert a file:// URI to an OS-native absolute path."""
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        return urllib.request.url2pathname(unquote(parsed.path))
    return uri


def path_to_uri(path: str) -> str:
    """Convert an OS-native absolute path to a file:// URI."""
    return pathlib.Path(os.path.abspath(path)).as_uri()


def offset_to_position(source: str, offset: int) -> Position:
    """Convert a character offset to a 0-based LSP Position."""
    text_before = source[:max(0, offset)]
    lines = text_before.split("\n")
    return Position(line=len(lines) - 1, character=len(lines[-1]))


def word_at_offset(source: str, offset: int) -> str:
    """Return the identifier word that contains or is immediately before offset."""
    offset = min(offset, len(source))
    start = offset
    while start > 0 and (source[start - 1].isalnum() or source[start - 1] == "_"):
        start -= 1
    end = offset
    while end < len(source) and (source[end].isalnum() or source[end] == "_"):
        end += 1
    return source[start:end]


def word_start_offset(source: str, offset: int) -> int:
    """Return the start offset of the identifier at offset."""
    offset = min(offset, len(source))
    while offset > 0 and (source[offset - 1].isalnum() or source[offset - 1] == "_"):
        offset -= 1
    return offset