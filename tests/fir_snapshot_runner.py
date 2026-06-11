"""FIR snapshot test runner.

Converts a representative subset of test sources to FIR via --emit-fir,
compares the dumps against goldens in tests/expected_fir/, and verifies
determinism (each case is converted twice; the dumps must be identical).

Usage:
    python tests/fir_snapshot_runner.py            # run all snapshot cases
    python tests/fir_snapshot_runner.py --update   # regenerate goldens
    python tests/fir_snapshot_runner.py --cases tests/sources/fibonacci.fire
"""

import argparse
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES_DIR = os.path.join(REPO_ROOT, "tests", "sources")
EXPECTED_DIR = os.path.join(REPO_ROOT, "tests", "expected_fir")
BUILD_DIR = os.path.join(REPO_ROOT, "build")

# Representative subset spanning the implemented feature surface.
SNAPSHOT_CASES = [
    "fibonacci.fire",                       # recursion, int64
    "functions_comprehensive.fire",         # params, returns, nesting
    "control_flow_comprehensive.fire",      # if/elif/else, loops, break/continue
    "operator_precedence.fire",             # expression structure
    "operators_logical.fire",               # &&, ||, !
    "types_numeric_comprehensive.fire",     # all numeric types and literals
    "string_operations_comprehensive.fire", # strings, concat, length, iteration
    "array_operations_comprehensive.fire",  # arrays, index/count, for-in
    "array_negative_indexing.fire",         # negative indices
    "numeric_casts.fire",                   # as-casts incl. float128 alias
    "classes_methods.fire",                 # classes, constructors, methods
    "classes_static_methods.fire",          # static methods
    "inheritance.fire",                     # base classes, super()
    "receiver_mut.fire",                    # &this / &mut this receivers
    "generics_basic.fire",                  # generic functions
    "generics_class_basic.fire",            # generic classes
    "generators_basic.fire",                # generators, yield, ranges
    "memory_class_owned_fields.fire",       # destructors / owned fields
    "move_semantics_test.fire",             # moves
    "borrow_test.fire",                     # borrows
    "nullable_advanced.fire",               # nullable types
    "imports_multi.fire",                   # module merging
    "std_types_test.fire",                  # std.types Tuple/Option
    "std_cli_args_basic.fire",              # process args intrinsics
    "syscall_basic.fire",                   # syscall intrinsics
]


def convert(source_path: str) -> str:
    """Run --emit-fir for source_path and return the dump text."""
    result = subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "firescript", "main.py"), source_path, "--emit-fir"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"--emit-fir failed for {source_path}:\n{result.stdout}\n{result.stderr}"
        )
    base_name = os.path.splitext(os.path.basename(source_path))[0]
    fir_path = os.path.join(BUILD_DIR, f"{base_name}.fir")
    with open(fir_path, "r", encoding="utf-8") as f:
        return f.read()


def main() -> int:
    parser = argparse.ArgumentParser(description="FIR snapshot test runner")
    parser.add_argument("--update", action="store_true", help="Regenerate golden files")
    parser.add_argument("--cases", nargs="*", help="Specific source files to run")
    args = parser.parse_args()

    if args.cases:
        cases = [os.path.basename(c) for c in args.cases]
    else:
        cases = SNAPSHOT_CASES

    os.makedirs(EXPECTED_DIR, exist_ok=True)

    passed = 0
    failed = 0
    for case in cases:
        source_path = os.path.join(SOURCES_DIR, case)
        expected_path = os.path.join(EXPECTED_DIR, case.replace(".fire", ".fir"))
        print(f"[CASE  ] {case}")
        try:
            first = convert(source_path)
            second = convert(source_path)
        except RuntimeError as e:
            print(f"[FAIL  ] {case}: {e}")
            failed += 1
            continue

        if first != second:
            print(f"[FAIL  ] {case}: FIR dump is not deterministic")
            failed += 1
            continue

        if args.update:
            with open(expected_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(first)
            print(f"[UPDATE] {expected_path}")
            passed += 1
            continue

        if not os.path.exists(expected_path):
            print(f"[FAIL  ] {case}: missing golden {expected_path} (run with --update)")
            failed += 1
            continue

        with open(expected_path, "r", encoding="utf-8") as f:
            expected = f.read()
        if first == expected:
            print(f"[PASS  ] {case}")
            passed += 1
        else:
            import difflib

            diff = "\n".join(
                difflib.unified_diff(
                    expected.splitlines(), first.splitlines(), "expected", "actual", lineterm=""
                )
            )
            print(f"[FAIL  ] {case}\n{diff}")
            failed += 1

    print(f"\nSummary: {passed}/{len(cases)} passed, {failed}/{len(cases)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
