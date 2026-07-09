"""--dir batch directory compilation behavior."""
from __future__ import annotations

import os
import shutil

from harness import pyunit as t

SOURCES_DIR = t.sources_dir


def test_dir_batch_compile():
    with t.tmpdir() as tmp:
        shutil.copy(os.path.join(SOURCES_DIR, "functions", "functions.fire"), os.path.join(tmp, "a.fire"))
        shutil.copy(os.path.join(SOURCES_DIR, "operators", "unary_test.fire"), os.path.join(tmp, "b.fire"))
        build_dir = os.path.join(tmp, "build")
        proc = t.run_compiler(["--dir", tmp], cwd=tmp)
        t.require_eq(proc.returncode, 0, proc.stderr)
        t.require(os.path.exists(os.path.join(build_dir, "a.exe")))
        t.require(os.path.exists(os.path.join(build_dir, "b.exe")))


def test_dir_and_output_conflict():
    with t.tmpdir() as tmp:
        shutil.copy(os.path.join(SOURCES_DIR, "functions", "functions.fire"), os.path.join(tmp, "a.fire"))
        proc = t.run_compiler(["--dir", tmp, "-o", os.path.join(tmp, "out.exe")], cwd=tmp)
        t.require_eq(proc.returncode, 1)


def test_dir_not_found():
    missing = os.path.join(t.repo_root, "tests", "__no_such_dir__")
    proc = t.run_compiler(["--dir", missing])
    t.require_eq(proc.returncode, 1)


def test_dir_partial_failure():
    with t.tmpdir() as tmp:
        shutil.copy(os.path.join(SOURCES_DIR, "functions", "functions.fire"), os.path.join(tmp, "good.fire"))
        with open(os.path.join(tmp, "bad.fire"), "w", encoding="utf-8") as f:
            f.write("int32 x = ;\n")
        proc = t.run_compiler(["--dir", tmp], cwd=tmp)
        t.require_eq(proc.returncode, 0, proc.stderr)
        combined = proc.stdout + proc.stderr
        t.require("1 successful, 1 failed" in combined, combined)


def test_file_and_dir_together():
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    with t.tmpdir() as tmp:
        shutil.copy(os.path.join(SOURCES_DIR, "operators", "unary_test.fire"), os.path.join(tmp, "b.fire"))
        proc = t.run_compiler(["--check", "--dir", tmp, src], cwd=tmp)
        t.require_eq(proc.returncode, 0, proc.stderr)
        combined = proc.stdout + proc.stderr
        t.require("Both file and directory specified" in combined, combined)
