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
    t.require("Parsing failed" in proc.stdout + proc.stderr, proc.stdout + proc.stderr)


def test_compile_with_configured_target_produces_binary():
    # t.run_compiler() adds --platform/--arch from FIRESCRIPT_TEST_TARGET when
    # it is set (and otherwise leaves the compiler's host default), so this
    # tests "whatever target this test run is configured for", not the host
    # default specifically; host-default resolution is covered by
    # test_targets_resolution.py.
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    exe = os.path.join(BUILD_DIR, "functions.exe")
    if os.path.exists(exe):
        os.remove(exe)
    proc = t.run_compiler([src])
    t.require_eq(proc.returncode, 0, proc.stderr)
    t.require(os.path.exists(exe), "the configured target must produce build/functions.exe")


def test_no_link_rejected():
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    proc = t.run_compiler(["--no-link", src])
    t.require_eq(proc.returncode, 1)
    t.require("--emit obj / --no-link is not supported" in proc.stdout + proc.stderr,
              proc.stdout + proc.stderr)


def test_input_is_directory():
    proc = t.run_compiler(["--check", SOURCES_DIR])
    t.require_eq(proc.returncode, 1)
    # The OS wording differs ("Is a directory" on POSIX, "Permission denied" on
    # Windows), so assert on the compiler's own message.
    t.require("Error reading file" in proc.stdout + proc.stderr, proc.stdout + proc.stderr)
