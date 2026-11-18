"""Direct unit tests for firescript/log_formatter.py's LogFormatter (per-level
format selection) and JsonFormatter (structured diagnostic vs plain log
events)."""
from __future__ import annotations

import json
import logging
import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

import log_formatter  # noqa: E402
from errors import ParserError  # noqa: E402


def _record(level: int, msg, *args) -> logging.LogRecord:
    return logging.LogRecord("fs", level, "file.py", 7, msg, args, None)


@t.params([logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL])
def test_log_formatter_formats_each_level(level):
    out = log_formatter.LogFormatter().format(_record(level, "hello %s", "world"))
    t.require("hello world" in out, out)
    t.require(logging.getLevelName(level) in out, out)


def test_log_formatter_debug_includes_source_location():
    dbg = log_formatter.LogFormatter().format(_record(logging.DEBUG, "m"))
    info = log_formatter.LogFormatter().format(_record(logging.INFO, "m"))
    t.require("(fs - file.py:7)" in dbg, dbg)
    t.require("file.py" not in info, info)


def test_log_formatter_unknown_level_falls_back_to_bare_message():
    # FORMATS only has the five standard levels; a custom level number has
    # no entry, so logging.Formatter(None, ...) falls back to the bare message.
    out = log_formatter.LogFormatter().format(_record(25, "custom"))
    t.require_eq(out, "custom")


def test_json_formatter_plain_log_event():
    out = log_formatter.JsonFormatter().format(_record(logging.WARNING, "n=%d", 3))
    t.require_eq(json.loads(out), {"type": "log", "level": "warning", "message": "n=3"})


def test_json_formatter_compile_error_event():
    err = ParserError(source_file="a.fire", line=2, column=5, snippet="x = ;", message="oops")
    out = log_formatter.JsonFormatter().format(_record(logging.ERROR, err))
    t.require_eq(json.loads(out), {
        "type": "diagnostic", "level": "error", "code": "FS-PARSE-0001",
        "category": "parser", "message": "oops", "file": "a.fire",
        "line": 2, "column": 5, "snippet": "x = ;",
    })
