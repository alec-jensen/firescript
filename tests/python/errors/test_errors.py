"""Direct unit tests for firescript/errors.py's CompileTimeError base class,
in particular the message-template rendering fallback."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from errors import CompileTimeError  # noqa: E402


class _BadTemplateError(CompileTimeError):
    code = "FS-TEST-0000"
    # References a context key that callers never supply, so .format(**context)
    # raises KeyError and _render() must fall back to the raw template.
    message_template = "missing key: {not_supplied}"


def test_render_falls_back_to_raw_template_on_format_error():
    err = _BadTemplateError(source_file="x.fire")
    t.require_eq(err.message, "missing key: {not_supplied}")


def test_to_log_string_without_snippet_omits_caret_line():
    err = CompileTimeError(source_file="x.fire", line=0, column=0, snippet=None)
    log = err.to_log_string()
    t.require("^" not in log)
