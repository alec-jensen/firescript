#!/usr/bin/env python3
"""
Error test runner for firescript.

Tests that invalid code produces the expected compilation errors.
Uses golden error signatures to verify error codes at specific source locations.

Usage:
  python tests/error_runner.py                    # Run all error tests
  python tests/error_runner.py --update           # Update golden error files
  python tests/error_runner.py --cases file.fire  # Test specific file
"""
import argparse
import sys
import os
import glob
import threading
from typing import List, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(REPO_ROOT, os.pardir))
INVALID_DIR = os.path.join(REPO_ROOT, "tests", "sources", "invalid")
EXPECTED_ERRORS_DIR = os.path.join(REPO_ROOT, "tests", "expected_errors")

FIRESCRIPT_DIR = os.path.join(REPO_ROOT, "firescript")
if FIRESCRIPT_DIR not in sys.path:
    sys.path.insert(0, FIRESCRIPT_DIR)

from main import lint_text  # noqa: E402  # type: ignore[import-not-found]
from errors import CompileTimeError  # noqa: E402  # type: ignore[import-not-found]

_LINT_LOCK = threading.Lock()


@dataclass
class ErrorTestCase:
    source: str
    expected_errors: str


@dataclass(frozen=True)
class ErrorSignature:
    code: str
    line: int
    column: int


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


def _tag(label: str, color_code: str | None = None) -> str:
    padded = f"[{label:<6}]"
    return _colorize(padded, color_code) if color_code else padded


def _log(label: str, message: str, color_code: str | None = None) -> None:
    print(f"{_tag(label, color_code)} {message}")


def _normalize_user_path(path_value: str) -> str:
    """Normalize a user-provided path used by local test harness operations."""
    if not isinstance(path_value, str) or not path_value:
        raise ValueError("Path must be a non-empty string")
    if "\x00" in path_value:
        raise ValueError("Path contains invalid NUL byte")
    return os.path.abspath(os.path.expanduser(path_value))


def discover_error_tests() -> List[ErrorTestCase]:
    """Find all .fire files in tests/sources/invalid/"""
    pattern = os.path.join(INVALID_DIR, "*.fire")
    sources = glob.glob(pattern)
    
    cases = []
    for src in sorted(sources):
        base = os.path.splitext(os.path.basename(src))[0]
        # Helper provider modules are imported by other invalid tests and are not
        # intended to be compiled as standalone failing cases.
        if base.endswith("_provider"):
            continue
        expected = os.path.join(EXPECTED_ERRORS_DIR, f"{base}.err")
        cases.append(ErrorTestCase(source=src, expected_errors=expected))
    
    return cases


def collect_errors(source: str) -> List[CompileTimeError]:
    """Run front-end linting and return structured compile-time diagnostics."""
    source_path = _normalize_user_path(source)
    with open(source_path, "r", encoding="utf-8") as f:
        source_text = f.read()

    display_path = os.path.relpath(source_path, REPO_ROOT)
    # lint_text temporarily mutates global logging level; serialize calls so
    # parallel test execution does not leak diagnostics to stderr.
    with _LINT_LOCK:
        return lint_text(source_text, display_path)


def _parse_expected_signatures(content: str) -> List[ErrorSignature]:
    signatures: List[ErrorSignature] = []
    for raw in content.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "@" not in line or ":" not in line:
            continue
        code, location = line.split("@", 1)
        line_num, col_num = location.split(":", 1)
        signatures.append(ErrorSignature(code=code, line=int(line_num), column=int(col_num)))
    return signatures


def _serialize_expected_signatures(signatures: List[ErrorSignature]) -> str:
    lines = ["# firescript expected diagnostics v2", "# format: <ERROR_CODE>@<line>:<column>"]
    for sig in signatures:
        lines.append(f"{sig.code}@{sig.line}:{sig.column}")
    return "\n".join(lines) + "\n"


def _extract_signatures(errors: List[CompileTimeError]) -> List[ErrorSignature]:
    signatures: List[ErrorSignature] = []
    for err in errors:
        signatures.append(
            ErrorSignature(
                code=getattr(err, "code", "FS-COMP-0000"),
                line=getattr(err, "line", 0),
                column=getattr(err, "column", 0),
            )
        )
    return sorted(signatures, key=lambda s: (s.line, s.column, s.code))


def read_file(path: str) -> str:
    """Read file contents."""
    file_path = _normalize_user_path(path)
    if not os.path.exists(file_path):
        return ""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def write_file(path: str, content: str) -> None:
    """Write file contents."""
    file_path = _normalize_user_path(path)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def run_one_error_test(tc: ErrorTestCase, update: bool, verbose: bool) -> Tuple[bool, str, str, str]:
    """
    Run a single error test case.
    Returns: (success, source, expected_errors, actual_errors)
    """
    if verbose:
        _log("COMPILE", tc.source, "90")  # dim
    
    errors = collect_errors(tc.source)

    # Invalid tests must produce at least one diagnostic
    if not errors:
        return (False, tc.source, "UNEXPECTED SUCCESS", "")

    actual_signatures = _extract_signatures(errors)
    actual_errors = _serialize_expected_signatures(actual_signatures)
    
    if os.path.exists(tc.expected_errors):
        expected_errors = read_file(tc.expected_errors)
        expected_signatures = sorted(
            _parse_expected_signatures(expected_errors),
            key=lambda s: (s.line, s.column, s.code),
        )

        if expected_signatures == actual_signatures:
            return (True, tc.source, "", "")
        else:
            if update:
                write_file(tc.expected_errors, actual_errors)
                return (True, tc.source, "", "")
            else:
                return (
                    False,
                    tc.source,
                    _serialize_expected_signatures(expected_signatures),
                    actual_errors,
                )
    else:
        # No golden file exists
        if update:
            write_file(tc.expected_errors, actual_errors)
            return (True, tc.source, "", "")
        else:
            return (False, tc.source, "<missing golden>", actual_errors)


def run_error_tests(cases: List[ErrorTestCase], update: bool, verbose: bool, fail_fast: bool) -> int:
    """
    Run error tests in parallel and return exit code.
    """
    total = len(cases)
    passed = 0
    failed = []

    if fail_fast:
        # Sequential execution for fail-fast
        for tc in cases:
            _log("CASE", tc.source, "36")  # cyan
            success, source, expected, actual = run_one_error_test(tc, update, verbose)
            
            if success:
                passed += 1
                _log("PASS", source, "32")  # green
            else:
                failed.append((tc, expected, actual))
                if expected == "UNEXPECTED SUCCESS":
                    _log("FAIL", f"{source} - Expected compilation to fail but it succeeded!", "31")
                elif expected == "<missing golden>":
                    _log("FAIL", f"{source} - No golden error file", "31")
                else:
                    _log("FAIL", f"{source} - Error signature mismatch", "31")  # red
                break
    else:
        # Parallel execution
        with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
            futures = {executor.submit(run_one_error_test, tc, update, verbose): tc for tc in cases}
            
            for future in futures:
                tc = futures[future]
                _log("CASE", tc.source, "36")  # cyan
                
                success, source, expected, actual = future.result()
                
                if success:
                    passed += 1
                    if update and expected == "":
                        _log("UPDATE", tc.expected_errors, "33")  # yellow
                    else:
                        _log("PASS", source, "32")  # green
                else:
                    failed.append((tc, expected, actual))
                    if expected == "UNEXPECTED SUCCESS":
                        _log("FAIL", f"{source} - Expected compilation to fail but it succeeded!", "31")
                    elif expected == "<missing golden>":
                        _log("FAIL", f"{source} - No golden error file", "31")
                    else:
                        _log("FAIL", f"{source} - Error signature mismatch", "31")  # red

    # Summary
    summary = f"Summary: {passed}/{total} passed, {len(failed)}/{total} failed"
    if failed:
        print(_colorize(f"\n{summary}", "31"))
        if verbose:
            for tc, expected, actual in failed:
                print(f"\n{_colorize('FAILED:', '31')} {tc.source}")
                if expected != "UNEXPECTED SUCCESS":
                    print(f"\nExpected errors:\n{expected}")
                    print(f"\nActual errors:\n{actual}")
    else:
        print(_colorize(f"\n{summary}", "32"))
    
    return 0 if not failed else 1


def main():
    parser = argparse.ArgumentParser(description="firescript error test runner")
    parser.add_argument("--cases", nargs="*", help="Specific invalid .fire files to test")
    parser.add_argument("--update", action="store_true", help="Update or create golden error files")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failure")
    args = parser.parse_args()

    if args.cases:
        # Test specific files
        cases = []
        for src in args.cases:
            src = _normalize_user_path(src)
            base = os.path.splitext(os.path.basename(src))[0]
            expected = os.path.join(EXPECTED_ERRORS_DIR, f"{base}.err")
            cases.append(ErrorTestCase(source=src, expected_errors=expected))
    else:
        # Discover all error tests
        cases = discover_error_tests()
    
    if not cases:
        print("No error test cases found.")
        return 0

    rc = run_error_tests(cases, update=args.update, verbose=args.verbose, fail_fast=args.fail_fast)
    sys.exit(rc)


if __name__ == "__main__":
    main()
