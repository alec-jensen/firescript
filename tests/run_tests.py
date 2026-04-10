#!/usr/bin/env python3
"""
Unified test runner for firescript.

Runs golden tests and error tests from a single entrypoint.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import List


REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(REPO_ROOT, os.pardir))


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR") is not None:
        return False
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def _colorize(text: str, code: str) -> str:
    if not _supports_color():
        return text
    return f"\x1b[{code}m{text}\x1b[0m"


def _run(cmd: List[str]) -> int:
    proc = subprocess.run(cmd, cwd=REPO_ROOT)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="firescript unified test runner")
    parser.add_argument("--update", action="store_true", help="Update golden outputs for both suites")
    parser.add_argument("--verbose", action="store_true", help="Verbose output for both suites")
    parser.add_argument("--fail-fast", action="store_true", help="Stop after the first suite failure")
    parser.add_argument("--golden-only", action="store_true", help="Run only golden tests")
    parser.add_argument("--error-only", action="store_true", help="Run only error tests")
    parser.add_argument("--jobs", type=int, default=4, help="Golden runner parallel workers (default: 4)")
    parser.add_argument("--timeout", type=float, default=20.0, help="Golden runner per-test runtime timeout in seconds")
    parser.add_argument("--compile-timeout", type=float, default=120.0, help="Golden runner compile timeout in seconds")
    args = parser.parse_args()

    if args.golden_only and args.error_only:
        print("Cannot use --golden-only and --error-only together.")
        return 2

    run_golden = not args.error_only
    run_error = not args.golden_only

    overall_failures = 0

    if run_golden:
        print(_colorize("\n== Running golden tests ==", "36"))
        golden_cmd = [
            sys.executable,
            os.path.join("tests", "golden_runner.py"),
            "--jobs",
            str(args.jobs),
            "--timeout",
            str(args.timeout),
            "--compile-timeout",
            str(args.compile_timeout),
        ]
        if args.update:
            golden_cmd.append("--update")
        if args.verbose:
            golden_cmd.append("--verbose")
        if args.fail_fast:
            golden_cmd.append("--fail-fast")

        rc = _run(golden_cmd)
        if rc != 0:
            overall_failures += 1
            if args.fail_fast:
                return 1

    if run_error:
        print(_colorize("\n== Running error tests ==", "36"))
        error_cmd = [sys.executable, os.path.join("tests", "error_runner.py")]
        if args.update:
            error_cmd.append("--update")
        if args.verbose:
            error_cmd.append("--verbose")
        if args.fail_fast:
            error_cmd.append("--fail-fast")

        rc = _run(error_cmd)
        if rc != 0:
            overall_failures += 1

    if overall_failures == 0:
        print(_colorize("\nUnified summary: all selected suites passed.", "32"))
        return 0

    print(_colorize(f"\nUnified summary: {overall_failures} suite(s) failed.", "31"))
    return 1


if __name__ == "__main__":
    sys.exit(main())