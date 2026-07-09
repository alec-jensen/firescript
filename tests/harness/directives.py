"""Magic-comment header directive parser, shared by .fire (//@) and .py (#@)
files (spec sec.5).

Header directives must appear in the leading comment block: the contiguous
run of comment/blank lines at the very top of the file. A directive found
after the first code token is a discovery error.
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field


class DirectiveError(Exception):
    """A malformed or misplaced directive. Always a discovery-time error,
    never a silent skip (spec sec.5.6)."""

    def __init__(self, message: str, line: int | None = None):
        self.message = message
        self.line = line
        loc = f" (line {line})" if line else ""
        super().__init__(f"{message}{loc}")


# key -> (repeatable, takes_value)
FIRE_KEYS = {
    "mode": (False, True),
    "helper": (False, False),
    "args": (True, True),
    "arg": (True, True),
    "stdin": (True, True),
    "stdin-file": (False, True),
    "exit-code": (False, True),
    "timeout": (False, True),
    "compile-timeout": (False, True),
    "compile-flags": (False, True),
    "snapshot": (False, True),
    "no-matrix": (False, False),
    "no-determinism": (False, True),
}

PYTHON_KEYS = {
    "timeout": (False, True),
    "no-matrix": (False, False),
}

_KEY_RE = re.compile(r"^[a-z-]+")


@dataclass
class Directives:
    """Parsed header directives for one test file.

    `entries[key]` is a list of (value, line_no) pairs in file order,
    covering repeatable and non-repeatable keys alike (non-repeatable keys
    have at most one entry, enforced at parse time).
    """

    entries: dict = field(default_factory=dict)

    def has(self, key: str) -> bool:
        return key in self.entries

    def value(self, key: str, default=None):
        vals = self.entries.get(key)
        if not vals:
            return default
        return vals[0][0]

    def values(self, key: str) -> list[str]:
        return [v for v, _ in self.entries.get(key, [])]

    def ordered(self, *keys: str) -> list[tuple[str, str, int]]:
        """All entries for the given keys, in file order, as (key, value, line)."""
        items = []
        for key in keys:
            for value, line in self.entries.get(key, []):
                items.append((key, value, line))
        items.sort(key=lambda t: t[2])
        return items


def _parse_directive_line(prefix: str, keys: dict, raw: str, line_no: int) -> tuple[str, str | None]:
    rest = raw[len(prefix):]
    if not rest.startswith(" "):
        raise DirectiveError(f"{prefix} must be followed by exactly one space", line_no)
    rest = rest[1:]
    if rest.startswith(" "):
        raise DirectiveError(f"{prefix} must be followed by exactly one space", line_no)
    m = _KEY_RE.match(rest)
    if not m:
        raise DirectiveError(f"malformed directive key in {raw!r}", line_no)
    key = m.group(0)
    remainder = rest[len(key):]
    if key not in keys:
        raise DirectiveError(f"unknown directive key '{key}'", line_no)
    repeatable, takes_value = keys[key]
    if takes_value:
        if not remainder.startswith(":"):
            raise DirectiveError(f"directive '{key}' requires a ': value'", line_no)
        value = remainder[1:].strip()
        if not value:
            raise DirectiveError(f"directive '{key}' requires a non-empty value", line_no)
    else:
        if remainder.strip():
            raise DirectiveError(f"directive '{key}' takes no value", line_no)
        value = None
    return key, value


def _is_comment_or_blank(line: str, comment_prefix: str) -> bool:
    s = line.strip()
    return s == "" or s.startswith(comment_prefix)


def _header_region_end(lines: list[str], comment_prefix: str) -> int:
    """Index (exclusive) of the header region: contiguous comment/blank lines
    from the top of the file."""
    i = 0
    while i < len(lines) and _is_comment_or_blank(lines[i], comment_prefix):
        i += 1
    return i


def parse_fire_directives(text: str) -> Directives:
    lines = text.splitlines()
    header_end = _header_region_end(lines, "//")
    directives = Directives()
    for idx, raw in enumerate(lines):
        line_no = idx + 1
        stripped = raw.strip()
        if not stripped.startswith("//@"):
            continue
        if idx >= header_end:
            raise DirectiveError(
                "//@ directive found outside the leading header comment block", line_no
            )
        key, value = _parse_directive_line("//@", FIRE_KEYS, stripped, line_no)
        repeatable, _ = FIRE_KEYS[key]
        if key in directives.entries and not repeatable:
            raise DirectiveError(f"directive '{key}' repeated (not repeatable)", line_no)
        directives.entries.setdefault(key, []).append((value, line_no))
    return directives


def parse_python_directives(text: str) -> Directives:
    lines = text.splitlines()
    header_end = _header_region_end(lines, "#")
    directives = Directives()
    for idx, raw in enumerate(lines):
        line_no = idx + 1
        stripped = raw.strip()
        if not stripped.startswith("#@"):
            continue
        if idx >= header_end:
            raise DirectiveError(
                "#@ directive found outside the leading header comment block", line_no
            )
        key, value = _parse_directive_line("#@", PYTHON_KEYS, stripped, line_no)
        repeatable, _ = PYTHON_KEYS[key]
        if key in directives.entries and not repeatable:
            raise DirectiveError(f"directive '{key}' repeated (not repeatable)", line_no)
        directives.entries.setdefault(key, []).append((value, line_no))
    return directives


def build_argv(directives: Directives) -> list[str]:
    """Combine //@ args: (shlex-split) and //@ arg: (verbatim) in file order."""
    argv: list[str] = []
    for key, value, _line in directives.ordered("args", "arg"):
        if key == "args":
            argv.extend(shlex.split(value))
        else:
            argv.append(value)
    return argv


def build_stdin(directives: Directives, test_dir: str) -> str | None:
    import os

    stdin_file = directives.value("stdin-file")
    stdin_lines = directives.values("stdin")
    if stdin_file and stdin_lines:
        raise DirectiveError("'stdin:' and 'stdin-file:' are mutually exclusive")
    if stdin_file:
        path = os.path.join(test_dir, stdin_file)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    if stdin_lines:
        return "\n".join(stdin_lines) + "\n"
    return None
