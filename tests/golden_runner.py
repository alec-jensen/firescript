#!/usr/bin/env python3
"""
Golden test runner for firescript.

Discovers .fire source files, compiles them with the firescript compiler, runs the produced binaries,
captures stdout, and compares it against expected golden files.

Golden files live under tests/expected/<basename>.out by default.

Usage examples:
  - Run all tests under examples/tests (excluding invalid):
      python3 tests/golden_runner.py

  - Run a specific file:
      python3 tests/golden_runner.py --cases examples/tests/functions.fire

  - Update goldens to match current output (review diffs in Git):
      python3 tests/golden_runner.py --update

Notes:
  - Requires a C compiler (gcc/clang) available, as the firescript compiler targets native by default.
  - Uses build/<basename> as the binary path, consistent with firescript/main.py behavior.
"""
from __future__ import annotations
import argparse
import subprocess
import sys
import os
import glob
from dataclasses import dataclass
from typing import List, Tuple, Optional

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(REPO_ROOT, os.pardir))
DEFAULT_SEARCH = [
    os.path.join(REPO_ROOT, "examples", "tests", "*.fire"),
]
EXPECTED_DIR = os.path.join(REPO_ROOT, "tests", "expected")
INPUTS_DIR = os.path.join(REPO_ROOT, "tests", "inputs")

@dataclass
class TestCase:
    source: str
    binary: str
    expected_path: str
    input_path: Optional[str]


def discover_cases(patterns: List[str]) -> List[TestCase]:
    sources: List[str] = []
    for pat in patterns:
        sources.extend(glob.glob(pat))
    # Exclude invalid tests and helper modules (utils.fire, math_utils.fire, string_utils.fire) by simple path check
    sources = [s for s in sources if os.sep + "invalid" + os.sep not in s]
    helper_modules = {"utils.fire", "math_utils.fire", "string_utils.fire"}
    sources = [s for s in sources if os.path.basename(s) not in helper_modules]
    cases: List[TestCase] = []
    for src in sorted(set(sources)):
        base = os.path.splitext(os.path.basename(src))[0]
        binary = os.path.join(REPO_ROOT, "build", base)
        expected = os.path.join(EXPECTED_DIR, f"{base}.out")
        input_path = os.path.join(INPUTS_DIR, f"{base}.in")
        if not os.path.exists(input_path):
            input_path = None
        cases.append(TestCase(source=src, binary=binary, expected_path=expected, input_path=input_path))
    return cases


def run_cmd(cmd: List[str], cwd: str | None = None, check: bool = True, input_text: Optional[str] = None, timeout: Optional[float] = None) -> Tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd, output=proc.stdout, stderr=proc.stderr)
    return proc.returncode, proc.stdout, proc.stderr


def compile_fire(src: str) -> None:
    # Invoke the firescript compiler to build the native binary into build/<basename>
    cmd = [sys.executable, os.path.join(REPO_ROOT, "firescript", "main.py"), src]
    code, out, err = run_cmd(cmd, cwd=REPO_ROOT, check=False)
    if code != 0:
        print(f"[FAIL] compile {src}\nstdout:\n{out}\nstderr:\n{err}")
        raise SystemExit(1)


def run_binary(path: str, input_text: Optional[str], timeout: Optional[float]) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Binary not found: {path}")
    cmd = [path]
    code, out, err = run_cmd(cmd, cwd=REPO_ROOT, check=False, input_text=input_text, timeout=timeout)
    if code != 0:
        print(f"[FAIL] run {path}\nstdout:\n{out}\nstderr:\n{err}")
        raise SystemExit(1)
    return out


def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_file(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def normalize(s: str) -> str:
    # Normalize newlines and strip trailing whitespace per line
    return "\n".join(line.rstrip() for line in s.replace("\r\n", "\n").replace("\r", "\n").split("\n")).strip() + "\n"


def run_golden(cases: List[TestCase], update: bool, verbose: bool, fail_fast: bool, timeout: Optional[float]) -> int:
    total = 0
    passed = 0
    failed: List[Tuple[TestCase, str, str]] = []

    for tc in cases:
        total += 1
        try:
            if verbose:
                print(f"[BUILD] {tc.source}")
            compile_fire(tc.source)
            if verbose:
                print(f"[RUN  ] {tc.binary}")
            input_text = read_file(tc.input_path) if tc.input_path else None
            actual = run_binary(tc.binary, input_text=input_text, timeout=timeout)
            actual_norm = normalize(actual)

            if os.path.exists(tc.expected_path):
                expected_norm = normalize(read_file(tc.expected_path))
                if actual_norm == expected_norm:
                    passed += 1
                    if verbose:
                        print(f"[PASS] {tc.source}")
                else:
                    if update:
                        write_file(tc.expected_path, actual_norm)
                        passed += 1
                        print(f"[UPDATE] {tc.expected_path}")
                    else:
                        failed.append((tc, expected_norm, actual_norm))
                        print(f"[FAIL] {tc.source} -> see diff")
                        if fail_fast:
                            break
            else:
                if update:
                    write_file(tc.expected_path, actual_norm)
                    passed += 1
                    print(f"[NEW] wrote golden {tc.expected_path}")
                else:
                    failed.append((tc, "<missing>", actual_norm))
                    print(f"[FAIL] missing golden for {tc.source}: {tc.expected_path}")
                    if fail_fast:
                        break
        except Exception as e:
            failed.append((tc, "<exception>", str(e)))
            print(f"[ERROR] {tc.source}: {e}")
            if fail_fast:
                break

    print(f"\nSummary: {passed}/{total} passed, {len(failed)} failed")
    if failed and verbose:
        for tc, exp, act in failed:
            print("\nCase:", tc.source)
            print("Expected (normalized):\n", exp)
            print("Actual (normalized):\n", act)
    return 0 if not failed else 1


def main():
    ap = argparse.ArgumentParser(description="firescript golden test runner")
    ap.add_argument("--cases", nargs="*", help="Specific .fire sources to test")
    ap.add_argument("--glob", action="append", help="Glob(s) to discover sources; defaults to examples/tests/*.fire")
    ap.add_argument("--update", action="store_true", help="Update or create golden files to match current output")
    ap.add_argument("--fail-fast", action="store_true", help="Stop on first failure")
    ap.add_argument("--verbose", action="store_true", help="Verbose output")
    ap.add_argument("--timeout", type=float, default=5.0, help="Per-test timeout in seconds (default: 5.0)")
    args = ap.parse_args()

    patterns = args.glob if args.glob else DEFAULT_SEARCH
    if args.cases:
        cases = []
        for src in args.cases:
            base = os.path.splitext(os.path.basename(src))[0]
            binary = os.path.join(REPO_ROOT, "build", base)
            expected = os.path.join(EXPECTED_DIR, f"{base}.out")
            input_path = os.path.join(INPUTS_DIR, f"{base}.in")
            if not os.path.exists(input_path):
                input_path = None
            cases.append(TestCase(src, binary, expected, input_path))
    else:
        cases = discover_cases(patterns)

    rc = run_golden(cases, update=args.update, verbose=args.verbose, fail_fast=args.fail_fast, timeout=args.timeout)
    sys.exit(rc)


if __name__ == "__main__":
    main()
