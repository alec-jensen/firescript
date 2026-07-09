"""FIR/FLIR snapshot test runner.

Converts a representative subset of test sources via --emit-fir and
--emit-flir, compares the dumps against goldens in tests/expected_fir/
and tests/expected_flir/, and verifies determinism (each case is
converted twice; the dumps must be identical).

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
EXPECTED_FLIR_DIR = os.path.join(REPO_ROOT, "tests", "expected_flir")
BUILD_DIR = os.path.join(REPO_ROOT, "build")

# Representative subset spanning the implemented feature surface.
SNAPSHOT_CASES = [
    "performance/fibonacci.fire",                  # recursion, int64
    "functions/functions_calling_functions.fire",  # params, returns, function-calling-function
    "control_flow/control_flow_while.fire",        # while loops, break/continue, nesting
    "expressions/operator_precedence.fire",        # expression structure
    "operators/operators_logical.fire",            # &&, ||, !
    "types/types_int64.fire",                      # numeric type literals and arithmetic
    "strings/strings_concatenation.fire",          # strings, concat, casts
    "arrays/arrays_iteration_for_in.fire",         # arrays, index, for-in
    "arrays/array_negative_indexing.fire",         # negative indices
    "conversions/numeric_casts.fire",              # as-casts incl. float128 alias
    "classes/classes_methods.fire",                # classes, constructors, methods
    "classes/classes_static_methods.fire",         # static methods
    "classes/inheritance.fire",                    # base classes, super()
    "memory/receiver_mut.fire",                    # &this / &mut this receivers
    "generics/generics_basic.fire",                # generic functions
    "generics/generics_class_basic.fire",          # generic classes
    "generators/generators_basic.fire",            # generators, yield, ranges
    "memory/memory_class_owned_fields.fire",       # destructors / owned fields
    "memory/move_semantics_test.fire",             # moves
    "memory/borrow_test.fire",                     # borrows
    "nullable/nullable_advanced.fire",             # nullable types
    "imports/imports_multi.fire",                  # module merging
    "std/types/std_types_test.fire",               # std.types Tuple/Option
    "std/cli/std_cli_args_basic.fire",             # process args intrinsics
    "std/syscalls/syscall_basic.fire",              # syscall intrinsics
]


def convert(source_path: str) -> tuple[str, str]:
    """Run --emit-fir --emit-flir for source_path; return both dump texts."""
    result = subprocess.run(
        [
            sys.executable,
            os.path.join(REPO_ROOT, "firescript", "main.py"),
            source_path,
            "--emit-fir",
            "--emit-flir",
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"--emit-fir/--emit-flir failed for {source_path}:\n{result.stdout}\n{result.stderr}"
        )
    base_name = os.path.splitext(os.path.basename(source_path))[0]
    with open(os.path.join(BUILD_DIR, f"{base_name}.fir"), "r", encoding="utf-8") as f:
        fir_text = f.read()
    with open(os.path.join(BUILD_DIR, f"{base_name}.flir"), "r", encoding="utf-8") as f:
        flir_text = f.read()
    return fir_text, flir_text


def main() -> int:
    parser = argparse.ArgumentParser(description="FIR snapshot test runner")
    parser.add_argument("--update", action="store_true", help="Regenerate golden files")
    parser.add_argument("--cases", nargs="*", help="Specific source files to run")
    args = parser.parse_args()

    if args.cases:
        cases = []
        for c in args.cases:
            abs_c = os.path.abspath(c)
            if abs_c.startswith(SOURCES_DIR + os.sep):
                cases.append(os.path.relpath(abs_c, SOURCES_DIR).replace(os.sep, "/"))
            else:
                cases.append(c)
    else:
        cases = SNAPSHOT_CASES

    os.makedirs(EXPECTED_DIR, exist_ok=True)
    os.makedirs(EXPECTED_FLIR_DIR, exist_ok=True)

    passed = 0
    failed = 0
    for case in cases:
        source_path = os.path.join(SOURCES_DIR, *case.split("/"))
        print(f"[CASE  ] {case}")
        try:
            first = convert(source_path)
            second = convert(source_path)
        except RuntimeError as e:
            print(f"[FAIL  ] {case}: {e}")
            failed += 1
            continue

        if first != second:
            print(f"[FAIL  ] {case}: IR dumps are not deterministic")
            failed += 1
            continue

        # expected_fir/expected_flir are a small, curated set of internal
        # compiler fixtures kept flat (basename-keyed), independent of the
        # source tree's category subdirectories.
        case_base = os.path.basename(case)
        case_ok = True
        checks = [
            (os.path.join(EXPECTED_DIR, case_base.replace(".fire", ".fir")), first[0], "FIR"),
            (os.path.join(EXPECTED_FLIR_DIR, case_base.replace(".fire", ".flir")), first[1], "FLIR"),
        ]
        for expected_path, actual, label in checks:
            if args.update:
                with open(expected_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(actual)
                print(f"[UPDATE] {expected_path}")
                continue
            if not os.path.exists(expected_path):
                print(f"[FAIL  ] {case}: missing {label} golden {expected_path} (run with --update)")
                case_ok = False
                continue
            with open(expected_path, "r", encoding="utf-8") as f:
                expected = f.read()
            if actual != expected:
                import difflib

                diff = "\n".join(
                    difflib.unified_diff(
                        expected.splitlines(), actual.splitlines(), "expected", "actual", lineterm=""
                    )
                )
                print(f"[FAIL  ] {case} ({label})\n{diff}")
                case_ok = False

        if case_ok:
            if not args.update:
                print(f"[PASS  ] {case}")
            passed += 1
        else:
            failed += 1

    print(f"\nSummary: {passed}/{len(cases)} passed, {failed}/{len(cases)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
