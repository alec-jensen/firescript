#!/usr/bin/env python3
"""
Unified test runner for firescript.

Runs golden tests and error tests from a single entrypoint.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import List


REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(REPO_ROOT, os.pardir))

TESTS_DIR = os.path.join(REPO_ROOT, "tests")
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

from golden_runner import DEFAULT_SEARCH, discover_cases, run_golden  # noqa: E402
from error_runner import discover_error_tests, run_error_tests  # noqa: E402


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


def _suite_label(name: str) -> str:
    return "Golden tests" if name == "golden" else "Error tests"


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

    should_run_golden = not args.error_only
    should_run_error = not args.golden_only

    overall_failures = 0
    suite_results: List[tuple[str, bool, int, int]] = []
    stopped_early = False

    if should_run_golden:
        print(_colorize("\n== Running golden tests ==", "36"))
        golden_cases = discover_cases(DEFAULT_SEARCH)
        golden_result = run_golden(
            golden_cases,
            update=args.update,
            verbose=args.verbose,
            fail_fast=args.fail_fast,
            timeout=args.timeout,
            compile_timeout=args.compile_timeout,
            jobs=args.jobs,
            return_stats=True,
        )
        if not isinstance(golden_result, tuple):
            raise RuntimeError("run_golden(return_stats=True) did not return stats")
        rc, stats = golden_result
        passed = rc == 0
        suite_results.append(("golden", passed, stats.passed, stats.total))
        if not passed:
            overall_failures += 1
            if args.fail_fast:
                stopped_early = True

    if should_run_error and not stopped_early:
        print(_colorize("\n== Running error tests ==", "36"))
        error_cases = discover_error_tests()
        error_result = run_error_tests(
            error_cases,
            update=args.update,
            verbose=args.verbose,
            fail_fast=args.fail_fast,
            return_stats=True,
        )
        if not isinstance(error_result, tuple):
            raise RuntimeError("run_error_tests(return_stats=True) did not return stats")
        rc, stats = error_result
        passed = rc == 0
        suite_results.append(("error", passed, stats.passed, stats.total))
        if not passed:
            overall_failures += 1

    print(_colorize("\n== Unified Results ==", "36"))
    for suite_name, _, passed_tests, total_tests in suite_results:
        failed_tests = total_tests - passed_tests
        line = f"{_suite_label(suite_name)}: {passed_tests}/{total_tests} passed, {failed_tests}/{total_tests} failed"
        color = "32" if failed_tests == 0 else "31"
        print(_colorize(line, color))

    suites_total = len(suite_results)
    suites_passed = sum(1 for _, passed, _, _ in suite_results if passed)
    suites_failed = suites_total - suites_passed
    tests_total = sum(total_tests for _, _, _, total_tests in suite_results)
    tests_passed = sum(passed_tests for _, _, passed_tests, _ in suite_results)
    tests_failed = tests_total - tests_passed

    if stopped_early:
        print(_colorize("Fail-fast enabled: stopped after first suite failure.", "33"))

    print(_colorize("\nTotal:", "36"))
    tests_line = f"Tests: {tests_passed}/{tests_total} passed, {tests_failed}/{tests_total} failed"
    suites_line = f"Suites: {suites_passed}/{suites_total} passed, {suites_failed}/{suites_total} failed"
    print(_colorize(tests_line, "32" if tests_failed == 0 else "31"))
    print(_colorize(suites_line, "32" if suites_failed == 0 else "31"))

    if overall_failures == 0:
        print(_colorize("\nUnified summary: all selected suites passed.", "32"))
        return 0

    print(_colorize("\nUnified summary: one or more suites failed.", "31"))
    return 1


if __name__ == "__main__":
    sys.exit(main())