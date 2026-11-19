"""CLI argument-error exits and rarely-used flag combinations of
firescript/main.py, black-box via subprocess on tiny temp sources
(complements test_check.py / test_emit.py / test_dir_batch.py)."""
from __future__ import annotations

import os
import subprocess
import sys

from harness import pyunit as t

_GOOD_SRC = "x: int32 = 1;\n"


def _write(tmp: str, name: str, text: str = _GOOD_SRC) -> str:
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


@t.params([
    ["--platform", "not-a-real-platform"],
    ["--arch", "not-a-real-arch"],
    ["--emit", "bogus"],
    ["--message-format", "xml"],
])
def test_invalid_choice_rejected(flag_and_value):
    with t.tmpdir() as tmp:
        proc = t.run_compiler(flag_and_value + [_write(tmp, "a.fire")], cwd=tmp)
        t.require_eq(proc.returncode, 2)
        t.require("invalid choice" in proc.stderr, proc.stderr)
        t.require(flag_and_value[1] in proc.stderr, proc.stderr)


def test_two_positional_files_rejected():
    with t.tmpdir() as tmp:
        proc = t.run_compiler(["--check", _write(tmp, "a.fire"), _write(tmp, "b.fire")], cwd=tmp)
        t.require_eq(proc.returncode, 2)
        t.require("unrecognized arguments" in proc.stderr, proc.stderr)


def test_no_input_error_message():
    proc = t.run_compiler([])
    t.require_eq(proc.returncode, 1)
    t.require("No input file or directory specified" in proc.stdout + proc.stderr)


def test_emit_obj_unsupported():
    with t.tmpdir() as tmp:
        proc = t.run_compiler(["--emit", "obj", _write(tmp, "a.fire")], cwd=tmp)
        t.require_eq(proc.returncode, 1)
        t.require("--emit obj / --no-link is not supported" in proc.stdout + proc.stderr,
                  proc.stdout + proc.stderr)


def test_unsupported_target_error_text_names_supported_targets():
    with t.tmpdir() as tmp:
        proc = t.run_compiler(
            ["--platform", "linux", "--arch", "x86_64", _write(tmp, "a.fire")], cwd=tmp)
        t.require_eq(proc.returncode, 1)
        combined = proc.stdout + proc.stderr
        t.require("Unsupported target: linux/x86_64" in combined, combined)
        t.require("Currently supported: windows/x86_64" in combined, combined)


def test_check_skips_target_support_check():
    # --check returns before the unsupported-target test, so it succeeds
    # even for a target the backend cannot build.
    with t.tmpdir() as tmp:
        proc = t.run_compiler(
            ["--check", "--platform", "linux", "--arch", "x86_64", _write(tmp, "a.fire")], cwd=tmp)
        t.require_eq(proc.returncode, 0, proc.stdout + proc.stderr)


def test_emit_flir_writes_flir_file():
    with t.tmpdir() as tmp:
        proc = t.run_compiler(["--emit-flir", _write(tmp, "a.fire")], cwd=tmp)
        t.require_eq(proc.returncode, 0, proc.stdout + proc.stderr)
        out = os.path.join(tmp, "build", "a.flir")
        t.require(os.path.exists(out) and os.path.getsize(out) > 0)
        t.require(not os.path.exists(os.path.join(tmp, "build", "a.fir")),
                  "--emit-flir alone must not write FIR")


def test_emit_fir_and_flir_write_both():
    with t.tmpdir() as tmp:
        proc = t.run_compiler(["--emit-fir", "--emit-flir", _write(tmp, "a.fire")], cwd=tmp)
        t.require_eq(proc.returncode, 0, proc.stdout + proc.stderr)
        for ext in ("fir", "flir"):
            t.require(os.path.exists(os.path.join(tmp, "build", f"a.{ext}")), ext)


def test_unreadable_source_reports_read_error():
    # Invalid UTF-8 makes open().read() raise UnicodeDecodeError, which is
    # reported via the generic "Error reading file" path.
    with t.tmpdir() as tmp:
        path = os.path.join(tmp, "bad.fire")
        with open(path, "wb") as f:
            f.write(b"x: int32 = \xff\xfe;\n")
        proc = t.run_compiler(["--check", path], cwd=tmp)
        t.require_eq(proc.returncode, 1)
        t.require("Error reading file" in proc.stdout + proc.stderr, proc.stdout + proc.stderr)


def test_source_is_read_as_utf8_regardless_of_the_platform_default_encoding():
    # open() without an encoding uses the platform default (cp1252 on Windows,
    # UTF-8 on Linux), so the same source decoded differently per platform.
    # Force a non-UTF-8 default here and require non-ASCII source to still
    # compile: a regression would fail on Linux too.
    env = dict(os.environ, LC_ALL="C", PYTHONUTF8="0", PYTHONCOERCECLOCALE="0")
    with t.tmpdir() as tmp:
        path = os.path.join(tmp, "uni.fire")
        with open(path, "wb") as f:
            f.write('s: string = "caf\u00e9";\n'.encode("utf-8"))
        proc = subprocess.run(
            [sys.executable, t.MAIN_PY, "--check", path], cwd=tmp, env=env,
            text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
        )
        t.require_eq(proc.returncode, 0, proc.stdout + proc.stderr)


def test_file_not_found_error_text():
    with t.tmpdir() as tmp:
        proc = t.run_compiler(["--check", os.path.join(tmp, "missing.fire")], cwd=tmp)
        t.require_eq(proc.returncode, 1)
        t.require("File not found" in proc.stdout + proc.stderr)


def test_message_format_json_read_error_is_log_event():
    with t.tmpdir() as tmp:
        proc = t.run_compiler(
            ["--message-format", "json", "--check", os.path.join(tmp, "missing.fire")], cwd=tmp)
        t.require_eq(proc.returncode, 1)
        combined = proc.stdout + proc.stderr
        t.require('"type": "log"' in combined and '"level": "error"' in combined, combined)
        t.require('"type": "diagnostic"' not in combined, combined)


def test_debug_flag_logs_parsed_args():
    with t.tmpdir() as tmp:
        proc = t.run_compiler(["-d", "--check", _write(tmp, "a.fire")], cwd=tmp)
        t.require_eq(proc.returncode, 0, proc.stdout + proc.stderr)
        t.require("Namespace(" in proc.stdout + proc.stderr, proc.stdout + proc.stderr)


def test_dir_with_unsupported_target_counts_failures():
    with t.tmpdir() as tmp:
        _write(tmp, "a.fire")
        proc = t.run_compiler(
            ["--dir", tmp, "--platform", "linux", "--arch", "x86_64"], cwd=tmp)
        t.require_eq(proc.returncode, 1, proc.stdout + proc.stderr)
        t.require("0 successful, 1 failed" in proc.stdout + proc.stderr, proc.stdout + proc.stderr)
