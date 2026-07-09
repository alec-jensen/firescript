#!/usr/bin/env python3
"""
CLI behavior test runner for firescript.

Exercises firescript/main.py command-line flags that the golden/error/FIR
snapshot runners never touch: --check, --emit ast, --emit-deps, --dir
(batch directory compilation), -v/--version, and -o output renaming.

These are invocation-level tests (exit code / files produced / stdout
content), not language-feature golden tests, so they live in their own
runner rather than tests/sources + tests/expected.

Usage:
  python tests/cli_runner.py
  python tests/cli_runner.py --verbose
"""
from __future__ import annotations
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Callable, List, Optional

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(REPO_ROOT, os.pardir))
MAIN_PY = os.path.join(REPO_ROOT, "firescript", "main.py")
SOURCES_DIR = os.path.join(REPO_ROOT, "tests", "sources")
BUILD_DIR = os.path.join(REPO_ROOT, "build")

TAG_WIDTH = 6


def _tag(label: str) -> str:
    return f"[{label:<{TAG_WIDTH}}]"


def _log(label: str, message: str) -> None:
    print(f"{_tag(label)} {message}")


def run_cli(args: List[str], cwd: Optional[str] = None, timeout: float = 60.0) -> subprocess.CompletedProcess:
    cmd = [sys.executable, MAIN_PY] + args
    return subprocess.run(
        cmd,
        cwd=cwd or REPO_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


@dataclass
class Case:
    name: str
    fn: Callable[[], None]


class CaseFailure(AssertionError):
    pass


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise CaseFailure(msg)


def case_version() -> None:
    proc = run_cli(["-v"])
    _require(proc.returncode == 0, f"expected exit 0, got {proc.returncode}")
    _require("firescript" in proc.stdout.lower(), f"expected version banner in stdout, got: {proc.stdout!r}")


def case_no_input() -> None:
    proc = run_cli([])
    _require(proc.returncode == 1, f"expected exit 1 with no file/dir, got {proc.returncode}")


def case_check_valid() -> None:
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    base = os.path.splitext(os.path.basename(src))[0]
    exe = os.path.join(BUILD_DIR, base + ".exe")
    if os.path.exists(exe):
        os.remove(exe)
    proc = run_cli(["--check", src])
    _require(proc.returncode == 0, f"--check on valid file should exit 0, got {proc.returncode}: {proc.stderr}")
    _require(not os.path.exists(exe), "--check must not produce a binary")


def case_check_invalid() -> None:
    src = os.path.join(SOURCES_DIR, "invalid", "types", "type_mismatches.fire")
    proc = run_cli(["--check", src])
    _require(proc.returncode == 1, f"--check on invalid file should exit 1, got {proc.returncode}")


def case_emit_ast() -> None:
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    ast_out = os.path.join(BUILD_DIR, "functions.ast")
    if os.path.exists(ast_out):
        os.remove(ast_out)
    proc = run_cli(["--emit", "ast", src])
    _require(proc.returncode == 0, f"--emit ast should exit 0, got {proc.returncode}: {proc.stderr}")
    _require(os.path.exists(ast_out), f"expected AST file at {ast_out}")
    _require(os.path.getsize(ast_out) > 0, "AST output file is empty")


def case_emit_deps() -> None:
    src = os.path.join(SOURCES_DIR, "imports", "imports_multi.fire")
    deps_out = os.path.join(BUILD_DIR, "imports_multi.d")
    if os.path.exists(deps_out):
        os.remove(deps_out)
    proc = run_cli(["--emit-deps", "--check", src])
    _require(proc.returncode == 0, f"--emit-deps compile should exit 0, got {proc.returncode}: {proc.stderr}")
    _require(os.path.exists(deps_out), f"expected deps file at {deps_out}")
    content = open(deps_out, encoding="utf-8").read()
    _require("imports_multi.o:" in content, f"deps file missing target rule: {content!r}")
    _require("math_utils.fire" in content and "string_utils.fire" in content,
             f"deps file missing imported module paths: {content!r}")


def case_output_rename() -> None:
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "custom_name.exe")
        proc = run_cli(["-o", out_path, src])
        _require(proc.returncode == 0, f"-o compile should exit 0, got {proc.returncode}: {proc.stderr}")
        _require(os.path.exists(out_path), f"expected renamed binary at {out_path}")


def case_dir_batch() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(os.path.join(SOURCES_DIR, "functions", "functions.fire"), os.path.join(tmp, "a.fire"))
        shutil.copy(os.path.join(SOURCES_DIR, "operators", "unary_test.fire"), os.path.join(tmp, "b.fire"))
        build_dir = os.path.join(tmp, "build")
        proc = run_cli(["--dir", tmp], cwd=tmp)
        _require(proc.returncode == 0, f"--dir batch compile should exit 0, got {proc.returncode}: {proc.stderr}")
        _require(os.path.exists(os.path.join(build_dir, "a.exe")), "expected build/a.exe from --dir compile")
        _require(os.path.exists(os.path.join(build_dir, "b.exe")), "expected build/b.exe from --dir compile")


def case_dir_and_output_conflict() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(os.path.join(SOURCES_DIR, "functions", "functions.fire"), os.path.join(tmp, "a.fire"))
        proc = run_cli(["--dir", tmp, "-o", os.path.join(tmp, "out.exe")], cwd=tmp)
        _require(proc.returncode == 1, f"--dir with -o should exit 1 (conflicting args), got {proc.returncode}")


def case_dir_not_found() -> None:
    missing = os.path.join(REPO_ROOT, "tests", "__no_such_dir__")
    proc = run_cli(["--dir", missing])
    _require(proc.returncode == 1, f"--dir on missing directory should exit 1, got {proc.returncode}")


def case_dir_partial_failure() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(os.path.join(SOURCES_DIR, "functions", "functions.fire"), os.path.join(tmp, "good.fire"))
        with open(os.path.join(tmp, "bad.fire"), "w", encoding="utf-8") as f:
            f.write("int32 x = ;\n")
        proc = run_cli(["--dir", tmp], cwd=tmp)
        _require(proc.returncode == 0, f"--dir should exit 0 even with one bad file, got {proc.returncode}")
        combined = proc.stdout + proc.stderr
        _require("1 successful, 1 failed" in combined,
                 f"expected partial-failure summary in output, got: {combined!r}")


def case_file_not_found() -> None:
    proc = run_cli(["--check", os.path.join(REPO_ROOT, "tests", "__no_such_file__.fire")])
    _require(proc.returncode == 1, f"missing source file should exit 1, got {proc.returncode}")


def case_unsupported_target() -> None:
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    proc = run_cli(["--target", "web", src])
    _require(proc.returncode == 1, f"unsupported --target should exit 1, got {proc.returncode}")


def case_emit_asm() -> None:
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    asm_out = os.path.join(BUILD_DIR, "temp", "functions.s")
    if os.path.exists(asm_out):
        os.remove(asm_out)
    proc = run_cli(["--emit", "asm", src])
    _require(proc.returncode == 0, f"--emit asm should exit 0, got {proc.returncode}: {proc.stderr}")
    _require(os.path.exists(asm_out), f"expected assembly file at {asm_out}")


def case_emit_fir_only() -> None:
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    fir_out = os.path.join(BUILD_DIR, "functions.fir")
    if os.path.exists(fir_out):
        os.remove(fir_out)
    proc = run_cli(["--emit-fir", src])
    _require(proc.returncode == 0, f"--emit-fir should exit 0, got {proc.returncode}: {proc.stderr}")
    _require(os.path.exists(fir_out), f"expected FIR file at {fir_out}")


def case_no_link_rejected() -> None:
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    proc = run_cli(["--no-link", src])
    _require(proc.returncode == 1, f"--no-link should exit 1 (unsupported), got {proc.returncode}")


def case_message_format_json() -> None:
    src = os.path.join(SOURCES_DIR, "invalid", "types", "type_mismatches.fire")
    proc = run_cli(["--message-format", "json", "--check", src])
    _require(proc.returncode == 1, f"--check on invalid file should exit 1, got {proc.returncode}")
    combined = proc.stdout + proc.stderr
    _require('"type": "diagnostic"' in combined,
             f"expected JSON diagnostic events in output, got: {combined!r}")
    _require('"type": "log"' in combined,
             f"expected JSON log events in output, got: {combined!r}")


def case_debug_mode() -> None:
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    proc = run_cli(["-d", "--check", src])
    _require(proc.returncode == 0, f"-d --check on valid file should exit 0, got {proc.returncode}: {proc.stderr}")
    combined = proc.stdout + proc.stderr
    _require("DEBUG" in combined, f"expected DEBUG log lines with -d, got: {combined!r}")


def case_file_and_dir_together() -> None:
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(os.path.join(SOURCES_DIR, "operators", "unary_test.fire"), os.path.join(tmp, "b.fire"))
        proc = run_cli(["--check", "--dir", tmp, src], cwd=tmp)
        _require(proc.returncode == 0, f"file + --dir should compile both and exit 0, got {proc.returncode}: {proc.stderr}")
        combined = proc.stdout + proc.stderr
        _require("Both file and directory specified" in combined,
                 f"expected both-specified warning in output, got: {combined!r}")


def case_emit_asm_output_path() -> None:
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "custom.s")
        proc = run_cli(["--emit", "asm", "-o", out_path, src])
        _require(proc.returncode == 0, f"--emit asm -o should exit 0, got {proc.returncode}: {proc.stderr}")
        _require(os.path.exists(out_path), f"expected assembly file at {out_path}")


def case_emit_ast_output_rename() -> None:
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "renamed.ast")
        proc = run_cli(["--emit", "ast", "-o", out_path, src])
        _require(proc.returncode == 0, f"--emit ast -o should exit 0, got {proc.returncode}: {proc.stderr}")
        _require(os.path.exists(out_path), f"expected AST file moved to {out_path}")


def case_input_is_directory() -> None:
    proc = run_cli(["--check", SOURCES_DIR])
    _require(proc.returncode == 1, f"passing a directory as the input file should exit 1, got {proc.returncode}")


def case_output_rename_no_ext() -> None:
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "custom_name")
        proc = run_cli(["-o", out_path, src])
        _require(proc.returncode == 0, f"-o without .exe should exit 0, got {proc.returncode}: {proc.stderr}")
        # The compiler appends .exe when writing, then the -o handling moves
        # the result to the exact requested output path.
        _require(os.path.exists(out_path), f"expected binary at {out_path}")


def case_import_not_found_compile() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "missing_import.fire")
        with open(src, "w", encoding="utf-8") as f:
            f.write("import definitely_missing_module.helper;\nint32 x = helper(1);\n")
        proc = run_cli([src])
        _require(proc.returncode == 1, f"unresolvable import should exit 1, got {proc.returncode}")
        combined = proc.stdout + proc.stderr
        _require("Import resolution failed" in combined,
                 f"expected import resolution failure in output, got: {combined!r}")


def case_import_with_syntax_error() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "bad_after_merge.fire")
        with open(src, "w", encoding="utf-8") as f:
            f.write("import @firescript/std.io.println;\nint32 x = ;\nprintln(x);\n")
        proc = run_cli([src])
        _require(proc.returncode == 1, f"syntax error alongside imports should exit 1, got {proc.returncode}")


def case_emit_deps_no_imports() -> None:
    src = os.path.join(SOURCES_DIR, "classes", "classes_smoke.fire")
    deps_out = os.path.join(BUILD_DIR, "classes_smoke.d")
    if os.path.exists(deps_out):
        os.remove(deps_out)
    proc = run_cli(["--emit-deps", "--check", src])
    _require(proc.returncode == 0, f"--emit-deps on import-free file should exit 0, got {proc.returncode}: {proc.stderr}")
    _require(not os.path.exists(deps_out), "no deps file expected for an import-free source")


CASES: List[Case] = [
    Case("version", case_version),
    Case("no_input_specified", case_no_input),
    Case("check_valid_file", case_check_valid),
    Case("check_invalid_file", case_check_invalid),
    Case("emit_ast", case_emit_ast),
    Case("emit_deps", case_emit_deps),
    Case("output_rename", case_output_rename),
    Case("dir_batch_compile", case_dir_batch),
    Case("dir_and_output_conflict", case_dir_and_output_conflict),
    Case("dir_not_found", case_dir_not_found),
    Case("dir_partial_failure", case_dir_partial_failure),
    Case("file_not_found", case_file_not_found),
    Case("unsupported_target", case_unsupported_target),
    Case("emit_asm", case_emit_asm),
    Case("emit_fir_only", case_emit_fir_only),
    Case("no_link_rejected", case_no_link_rejected),
    Case("message_format_json", case_message_format_json),
    Case("debug_mode", case_debug_mode),
    Case("file_and_dir_together", case_file_and_dir_together),
    Case("emit_asm_output_path", case_emit_asm_output_path),
    Case("emit_ast_output_rename", case_emit_ast_output_rename),
    Case("input_is_directory", case_input_is_directory),
    Case("emit_deps_no_imports", case_emit_deps_no_imports),
    Case("output_rename_no_ext", case_output_rename_no_ext),
    Case("import_not_found_compile", case_import_not_found_compile),
    Case("import_with_syntax_error", case_import_with_syntax_error),
]


@dataclass
class SuiteStats:
    total: int
    passed: int
    failed: int


def run_cli_cases(
    cases: List[Case],
    fail_fast: bool = False,
    return_stats: bool = False,
) -> int | tuple[int, SuiteStats]:
    os.makedirs(BUILD_DIR, exist_ok=True)

    passed = 0
    failed = 0
    for case in cases:
        _log("CASE", case.name)
        try:
            case.fn()
        except CaseFailure as e:
            _log("FAIL", f"{case.name}: {e}")
            failed += 1
            if fail_fast:
                break
            continue
        except Exception as e:  # noqa: BLE001
            _log("ERROR", f"{case.name}: {e}")
            failed += 1
            if fail_fast:
                break
            continue
        _log("PASS", case.name)
        passed += 1

    total = passed + failed
    print(f"\nSummary: {passed}/{total} passed, {failed}/{total} failed")
    rc = 0 if failed == 0 else 1
    stats = SuiteStats(total=total, passed=passed, failed=failed)
    if return_stats:
        return rc, stats
    return rc


def main() -> None:
    ap = argparse.ArgumentParser(description="firescript CLI behavior test runner")
    ap.add_argument("--cases", nargs="*", help="Specific case names to run")
    ap.add_argument("--fail-fast", action="store_true", help="Stop on first failure")
    ap.add_argument("--verbose", action="store_true", help="Verbose output")
    args = ap.parse_args()

    cases = CASES
    if args.cases:
        wanted = set(args.cases)
        cases = [c for c in CASES if c.name in wanted]

    rc = run_cli_cases(cases, fail_fast=args.fail_fast)
    sys.exit(rc)


if __name__ == "__main__":
    main()
