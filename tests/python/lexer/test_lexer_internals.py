"""Direct unit test for firescript/lexer.py's Lexer.tokenize() defensive
`token_type is None` fallback (a successful regex match whose .lastgroup is
None). Every alternative in the master token regex is a named group
requiring at least one character, so a real successful match always has a
lastgroup -- this branch looks structurally unreachable through any real
input (confirmed by probing: no single character or empty string produces
a match with lastgroup=None; unmatched characters instead produce no match
at all, which is the *other*, already-covered UNKNOWN-token fallback a few
lines below). It is exercised here only by monkeypatching the compiled
regex's .match to return a fake match object, purely to cover the branch's
own formatting logic (token_type = "UNKNOWN", token_value = current char)."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from lexer import Lexer  # noqa: E402


class _FakeMatchNoGroup:
    """A match object that succeeded but whose winning alternative has no
    named group -- lastgroup is None, same shape re.Match would have in
    that (otherwise unreachable) situation."""

    def __init__(self, matched_text: str):
        self._text = matched_text
        self.lastgroup = None

    def group(self, name):
        return self._text


class _FakeRegex:
    """Stands in for the compiled master regex object itself (re.Pattern
    objects are read-only, so their .match attribute can't be monkeypatched
    directly -- the whole object must be swapped out)."""

    def match(self, text, pos):
        return _FakeMatchNoGroup(text[pos])


def test_tokenize_handles_successful_match_with_no_named_group():
    lx = Lexer("x")
    orig_regex = lx._master_token_regex
    lx._master_token_regex = _FakeRegex()
    try:
        tokens = lx.tokenize()
    finally:
        lx._master_token_regex = orig_regex

    t.require_eq(len(tokens), 1)
    t.require_eq(tokens[0].type, "UNKNOWN")
    t.require_eq(tokens[0].value, "x")
