#!/usr/bin/env python3
"""
Error test runner for firescript.

Tests that invalid code produces the expected compilation errors.
Uses golden error files to verify error messages, line numbers, and error types.

Usage:
  python tests/error_runner.py                    # Run all error tests
  python tests/error_runner.py --update           # Update golden error files
  python tests/error_runner.py --cases file.fire  # Test specific file
"""
import argparse
import subprocess
import sys
import os
import glob
from typing import List, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(REPO_ROOT, os.pardir))
INVALID_DIR = os.path.join(REPO_ROOT, "tests", "sources", "invalid")
EXPECTED_ERRORS_DIR = os.path.join(REPO_ROOT, "tests", "expected_errors")


@dataclass
class ErrorTestCase:
    source: str
    expected_errors: str


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


def discover_error_tests() -> List[ErrorTestCase]:
    """Find all .fire files in tests/sources/invalid/"""
    pattern = os.path.join(INVALID_DIR, "*.fire")
    sources = glob.glob(pattern)
    
    cases = []
    for src in sorted(sources):
        base = os.path.splitext(os.path.basename(src))[0]
        expected = os.path.join(EXPECTED_ERRORS_DIR, f"{base}.err")
        cases.append(ErrorTestCase(source=src, expected_errors=expected))
    
    return cases


def compile_and_capture_errors(source: str) -> Tuple[int, str]:
    """
    Attempt to compile a firescript source file and capture stderr.
    Returns (exit_code, stderr_output)
    """
    cmd = [sys.executable, os.path.join(REPO_ROOT, "firescript", "main.py"), source]
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30.0,
    )
    return proc.returncode, proc.stderr


def normalize_errors(error_output: str) -> str:
    """
    Normalize error output for comparison.
    - Strips timestamps like [14:50:18]
    - Normalizes line endings
    - Strips trailing whitespace
    """
    import re
    
    lines = error_output.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    normalized_lines = []
    
    for line in lines:
        # Remove timestamps at the start of lines (e.g., [14:50:18])
        line = re.sub(r'^\[\d{2}:\d{2}:\d{2}\]\s*', '', line)
        normalized_lines.append(line.rstrip())
    
    normalized = "\n".join(normalized_lines).strip()
    return normalized + "\n" if normalized else ""


def read_file(path: str) -> str:
    """Read file contents."""
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_file(path: str, content: str) -> None:
    """Write file contents."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def run_one_error_test(tc: ErrorTestCase, update: bool, verbose: bool) -> Tuple[bool, str, str, str]:
    """
    Run a single error test case.
    Returns: (success, source, expected_errors, actual_errors)
    """
    if verbose:
        _log("COMPILE", tc.source, "90")  # dim
    
    exit_code, stderr = compile_and_capture_errors(tc.source)
    
    # Compilation should FAIL for error tests
    if exit_code == 0:
        return (False, tc.source, "UNEXPECTED SUCCESS", "")
    
    actual_errors = normalize_errors(stderr)
    
    if os.path.exists(tc.expected_errors):
        expected_errors = normalize_errors(read_file(tc.expected_errors))
        
        if actual_errors == expected_errors:
            return (True, tc.source, "", "")
        else:
            if update:
                write_file(tc.expected_errors, actual_errors)
                return (True, tc.source, "", "")
            else:
                return (False, tc.source, expected_errors, actual_errors)
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
                    _log("FAIL", f"{source} - Error output mismatch", "31")  # red
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
                        _log("FAIL", f"{source} - Error output mismatch", "31")  # red

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
