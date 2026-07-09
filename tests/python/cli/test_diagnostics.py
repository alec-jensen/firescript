"""--message-format json and -d debug logging behavior."""
from __future__ import annotations

import os

from harness import pyunit as t

SOURCES_DIR = t.sources_dir


def test_message_format_json():
    src = os.path.join(SOURCES_DIR, "invalid", "types", "type_mismatches.fire")
    proc = t.run_compiler(["--message-format", "json", "--check", src])
    t.require_eq(proc.returncode, 1)
    combined = proc.stdout + proc.stderr
    t.require('"type": "diagnostic"' in combined, combined)
    t.require('"type": "log"' in combined, combined)


def test_debug_mode():
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    proc = t.run_compiler(["-d", "--check", src])
    t.require_eq(proc.returncode, 0, proc.stderr)
    combined = proc.stdout + proc.stderr
    t.require("DEBUG" in combined, combined)
