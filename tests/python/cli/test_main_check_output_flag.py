"""Regression: `--check -o <file>` must exit 0 and write nothing.

compile_file() returns True (not a path) after a successful --check, and
main() used to treat the truthy `output_path != args.output` as a file to
shutil.move(), failing with "rename: src should be string, bytes or
os.PathLike, not bool".
"""
from __future__ import annotations

import os

from harness import pyunit as t

def _write(tmp: str, name: str) -> str:
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("x: int32 = 1;\n")
    return path


def test_check_with_output_flag_writes_nothing():
    with t.tmpdir() as tmp:
        out = os.path.join(tmp, "out.exe")
        proc = t.run_compiler(["--check", "-o", out, _write(tmp, "a.fire")], cwd=tmp)
        t.require_eq(proc.returncode, 0, proc.stdout + proc.stderr)
        t.require(not os.path.exists(out))
