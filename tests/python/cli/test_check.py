"""Basic CLI invocation / --check behavior (spec sec.4.4 migration table)."""
from __future__ import annotations

import os

from harness import pyunit as t

SOURCES_DIR = t.sources_dir
BUILD_DIR = os.path.join(t.repo_root, "build")


def test_version():
    proc = t.run_compiler(["-v"])
    t.require_eq(proc.returncode, 0)
    t.require("firescript" in proc.stdout.lower())


def test_no_input_specified():
    proc = t.run_compiler([])
    t.require_eq(proc.returncode, 1)


def test_check_valid_file():
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    exe = os.path.join(BUILD_DIR, "functions.exe")
    if os.path.exists(exe):
        os.remove(exe)
    proc = t.run_compiler(["--check", src])
    t.require_eq(proc.returncode, 0, proc.stderr)
    t.require(not os.path.exists(exe), "--check must not produce a binary")


def test_check_invalid_file():
    src = os.path.join(SOURCES_DIR, "invalid", "types", "type_mismatches.fire")
    proc = t.run_compiler(["--check", src])
    t.require_eq(proc.returncode, 1)


def test_file_not_found():
    proc = t.run_compiler(["--check", os.path.join(t.repo_root, "tests", "__no_such_file__.fire")])
    t.require_eq(proc.returncode, 1)


def test_unsupported_target():
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    proc = t.run_compiler(["--target", "web", src])
    t.require_eq(proc.returncode, 1)


def test_no_link_rejected():
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    proc = t.run_compiler(["--no-link", src])
    t.require_eq(proc.returncode, 1)


def test_input_is_directory():
    proc = t.run_compiler(["--check", SOURCES_DIR])
    t.require_eq(proc.returncode, 1)
