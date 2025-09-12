# firescript tests

This directory contains sample programs for exercising the compiler/runtime.
They are **not** an automated harness yet, but can be used manually.

## Layout

- `functions.fire`, `types_tests.fire`, `array_tests.fire`, etc.: Existing functional tests (expected to compile and run).
- `edge_cases.fire`: Additional valid edge scenarios; should compile successfully.
- `invalid/`: Negative tests intentionally containing errors. The compiler **should** report at least one error for each file.

### Invalid Test Files

| File | Primary Error Themes |
|------|----------------------|
| `invalid/type_mismatches.fire` | Type mismatches, undefined function, wrong method argument types, shadowing, use-before-declare, nested arrays |
| `invalid/syntax_errors.fire` | Missing semicolons, unclosed delimiters, malformed control structures, stray tokens |
| `invalid/array_edge_invalid.fire` | Disallowed nested arrays, unknown methods, assigning array to scalar |
| `invalid/control_flow_invalid.fire` | break/continue outside loops, non-bool conditions |

## Suggested Manual Run Procedure

1. Run each valid file to ensure no errors are produced.
2. Run each invalid file; verify that at least one meaningful error appears. (Exact wording may evolve.)

Example (adjust CLI if different):

```
python -m firescript.main examples/tests/edge_cases.fire
python -m firescript.main examples/tests/invalid/type_mismatches.fire
```

## Future Enhancements

- Add an automated test runner script that batches all `.fire` files and asserts pass/fail groups.
- Integrate into CI once the compiler exposes non-zero exit codes on errors.

