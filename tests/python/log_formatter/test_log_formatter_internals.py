"""Direct unit tests for firescript/log_formatter.py's two hard-to-reach
branches:

1. Colors' Windows-console VT-mode setup (module-level class body code that
   only runs when sys.stdout.isatty() is True *and* platform.system() ==
   "Windows"). Under the test harness stdout is normally redirected/piped
   (not a real tty), so this branch never runs during a normal coverage
   pass. We are running on native Windows here (see CLAUDE.md env), so
   monkeypatching isatty() to True and reloading the module exercises the
   real (harmless, standard) kernel32.SetConsoleMode call.
2. JsonFormatter.format()'s `except ImportError` fallback when `from errors
   import CompileTimeError` fails -- forced via the standard
   sys.modules[name] = None trick, which makes any subsequent `import
   errors` (or `from errors import ...`) raise ImportError.
"""
from __future__ import annotations

import importlib
import logging
import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

import log_formatter  # noqa: E402


def test_colors_windows_vt_mode_setup_when_isatty_true():
    orig_isatty = sys.stdout.isatty
    sys.stdout.isatty = lambda: True
    try:
        reloaded = importlib.reload(log_formatter)
        # The module executed its Windows VT-mode branch without raising;
        # Colors' SGR codes remain real ANSI escapes in this branch (not
        # blanked out, unlike the non-tty branch).
        t.require(reloaded.Colors.BLUE.startswith("\033["), reloaded.Colors.BLUE)
    finally:
        sys.stdout.isatty = orig_isatty
        # Restore normal (non-tty) module state for any tests that run after.
        importlib.reload(log_formatter)


def test_json_formatter_handles_import_error_fallback():
    orig_errors_module = sys.modules.get("errors")
    sys.modules["errors"] = None  # forces ImportError on `from errors import ...`
    try:
        formatter = log_formatter.JsonFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname=__file__, lineno=1,
            msg="a plain log message", args=(), exc_info=None,
        )
        output = formatter.format(record)
    finally:
        if orig_errors_module is not None:
            sys.modules["errors"] = orig_errors_module
        else:
            sys.modules.pop("errors", None)

    import json
    event = json.loads(output)
    t.require_eq(event["type"], "log")
    t.require_eq(event["message"], "a plain log message")
