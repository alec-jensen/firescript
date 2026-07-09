"""-o output-path renaming behavior."""
from __future__ import annotations

import os

from harness import pyunit as t

SOURCES_DIR = t.sources_dir


def test_output_rename():
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    with t.tmpdir() as tmp:
        out_path = os.path.join(tmp, "custom_name.exe")
        proc = t.run_compiler(["-o", out_path, src])
        t.require_eq(proc.returncode, 0, proc.stderr)
        t.require(os.path.exists(out_path))


def test_output_rename_no_ext():
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    with t.tmpdir() as tmp:
        out_path = os.path.join(tmp, "custom_name")
        proc = t.run_compiler(["-o", out_path, src])
        t.require_eq(proc.returncode, 0, proc.stderr)
        # The compiler appends .exe when writing, then the -o handling moves
        # the result to the exact requested output path.
        t.require(os.path.exists(out_path))
