# firescript Test Suite

This document provides an overview of the test suite for the firescript compiler.

## Test Organization

Test source files live under `tests/sources/<category>/`, grouped by feature area (e.g. `tests/sources/arrays/`, `tests/sources/classes/`). Invalid/error-triggering sources live under the mirrored `tests/sources/invalid/<category>/`. Golden output files mirror the same category structure: `tests/expected/<category>/<name>.out` for valid tests, `tests/expected_errors/<category>/<name>.err` for error tests. The test runner (`tests/golden_runner.py`) compiles each test file, runs it, and compares output against golden files.

Helper/provider modules that are imported by other tests but never compiled standalone (e.g. `utils.fire`, `math_utils.fire`, files ending in `_provider.fire`) live alongside the tests that import them, since imports resolve relative to the importing file's own directory.

## Running Tests

### Valid Code Tests (Golden Tests)

```bash
# Run all tests
python tests/golden_runner.py

# Run specific test(s)
python tests/golden_runner.py --cases tests/sources/operators/operators_arithmetic.fire

# Update golden files (review diffs carefully!)
python tests/golden_runner.py --update

# Verbose output
python tests/golden_runner.py --verbose

# Stop on first failure
python tests/golden_runner.py --fail-fast
```

### Invalid Code Tests (Error Tests)

```bash
# Run all error tests
python tests/error_runner.py

# Run specific error test(s)
python tests/error_runner.py --cases tests/sources/invalid/syntax/syntax_errors.fire

# Update expected error files (review diffs carefully!)
python tests/error_runner.py --update

# Verbose output
python tests/error_runner.py --verbose

# Stop on first failure
python tests/error_runner.py --fail-fast
```

The error test runner verifies that:
- Invalid code produces structured diagnostics
- Diagnostic error codes match expected values
- Diagnostic locations (line/column) match expected values
- Message wording can change without breaking tests

Expected error files are stored in `tests/expected_errors/<category>/` with `.err` extension, mirroring `tests/sources/invalid/<category>/`.

### Compiler Infrastructure Tests

```bash
# FIR (firescript intermediate representation) infrastructure unit tests
python tests/fir_unit_tests.py
```

- **fir_unit_tests.py** - Unit tests for `firescript/fir/`: FIRBuilder construction, textual dump format (verified against the spec example in `docs/internal/development/fir_spec.md`), dump determinism, structural validation (terminators, branch targets, cross-function value use)

```bash
# FIR snapshot tests (AST->FIR conversion goldens)
python tests/fir_snapshot_runner.py

# Regenerate FIR goldens (review diffs carefully!)
python tests/fir_snapshot_runner.py --update
```

- **fir_snapshot_runner.py** - Converts a representative subset of test sources (25 cases spanning the implemented feature surface, referenced by their category-relative path e.g. `arrays/arrays_iteration_for_in.fire`) to FIR and FLIR via `--emit-fir`/`--emit-flir`, compares the dumps against goldens in `tests/expected_fir/` and `tests/expected_flir/`, and verifies determinism by converting each case twice. These goldens are internal compiler fixtures, kept flat and basename-keyed (independent of the source tree's category subdirectories) since it's a small curated set, not user-facing behavior.

The golden runner also verifies every compiled binary imports only `kernel32.dll` (via the pure-Python PE inspector); firescript binaries are freestanding.

```bash
# CLI invocation behavior tests (firescript/main.py flags)
python tests/cli_runner.py
```

- **cli_runner.py** - Exercises `firescript/main.py` command-line behavior that the golden/error/FIR-snapshot runners never touch, since those only ever invoke the default single-file `--emit bin` path: `-v/--version`, no-input-specified error, `--check` (valid and invalid input), `--emit ast`, `--emit-deps`, `--emit asm`, `--emit-fir` without `--emit-flir`, `-o` output renaming, `--dir` batch directory compilation (including partial-failure counting and the `--dir`+`-o` conflict error), missing-file and missing-directory errors, unsupported `--target`, and the unsupported `--no-link` path. These are invocation-level (exit code / files produced / log output) checks, not language-feature goldens, so they don't use the `tests/sources` + `tests/expected` convention.

## Test Categories

Each heading below is a directory under `tests/sources/`.

### `operators/`
- **operators_arithmetic.fire** - All arithmetic operators (+, -, *, /, %, **), compound assignment (+=, -=, etc.), increment/decrement
- **operators_boolean.fire** - Boolean operator behavior
- **operators_comparison.fire** - Equality (==, !=), relational (<, >, <=, >=) for all numeric types and strings
- **operators_logical.fire** - Logical operators (`&&`, `||`, `!`) including nested and combined conditions
- **unary_test.fire** - Unary numeric operators (-, +)

### `control_flow/`
- **control_flow_if.fire** - if/else/else-if chains, nested if
- **control_flow_while.fire** - while loops, break, continue, nested while
- **control_flow_mixed_nesting.fire** - Interaction between for/if/while nested together
- **for_c_style.fire** - C-style for loop variations (including break/continue, nesting)
- **for_in.fire** - For-in loop over arrays (including break/continue)

### `generators/`
- **generators_basic.fire** - Generator functions with `generator<T>` syntax, `yield`, stdlib `range`/`rangeFrom`/`rangeStep`, user-defined generators, for-in over generators
- **generators_break_continue.fire** - `break`/`continue` inside a for-in loop over a generator, and nested for-in-over-generator loops

### `enums/`
- **enum_tag_only.fire** - Tag-only (no data payload) enum declarations, variant construction (`EnumName.Variant`), and reassignment (verifies the previously-held owned enum value is dropped without corrupting later allocations).
- **enum_payload_construct.fire** - Enum variants with named data payloads (e.g. `Circle(float64 radius)`), positional construction with arguments, and reassignment across variants with different payload shapes sharing the same tagged-union storage.
- **enum_owned_payload_drop.fire** - Owned payload data (a `string` field, and a class field elsewhere) is dropped correctly when the active variant goes out of scope; the destructor is tag-dispatched so only the active variant's owned fields are ever freed (never a different variant's, since payload storage is shared/overlapping). Also covers a class with an owned-enum-typed field, and 5000 construct/match/drop cycles as a leak/double-free sanity check.

### `match/`
- **match_statement_basic.fire** - Statement-form `match` over a tag-only enum with per-arm print side effects
- **match_payload_destructure.fire** - Payload variants destructured by declared field name, including renaming a field to a different local (`field: local`) and omitting fields a given arm doesn't need
- **match_expression_value.fire** - `match` used as a value-producing expression: as a function's `return` expression and as a variable declaration's initializer
- **match_wildcard.fire** - A `_` wildcard arm covering multiple variants not listed explicitly

### `types/`
Per-type min/max value and overflow/underflow behavior, split by numeric type:
- **types_int8.fire** / **types_int16.fire** / **types_int32.fire** / **types_int64.fire**
- **types_uint8.fire** / **types_uint16.fire** / **types_uint32.fire** / **types_uint64.fire**
- **types_float32.fire** / **types_float64.fire**
- **types_bool.fire**
- **types_tests.fire** - Basic type operations and comparisons
- **types_deep.fire** - Deep type testing (arithmetic across all widths with arbitrary values, distinct focus from the `types_<type>.fire` min/max-boundary files above)
- **char_type.fire** - `char` type: literals (`'A'`, escape chars `'\t'` `'\n'` `'\\'`), copyability, cast to string

### `conversions/`
Split by conversion category:
- **conversions_int_widening.fire** - int8->int16->int32->int64 upcasting, chained conversions
- **conversions_int_narrowing.fire** - int64->int32->int16->int8 downcasting (potential data loss)
- **conversions_signed_unsigned.fire** - Signed<->unsigned reinterpretation
- **conversions_int_float.fire** - int<->float, float-to-int truncation
- **conversions_float_precision.fire** - float32<->float64
- **conversions_in_expressions.fire** - Casts combined with arithmetic operations
- **conversions_to_string.fire** - Numeric/bool `as string`
- **numeric_casts.fire** - Numeric type casting (downcast-focused, distinct scenarios from the `conversions_*` files above)
- **string_cast_test.fire** - String casting operations
- **builtin_conversions.fire** - Free-function conversion builtins (`toInt`, `toFloat`, `toDouble`, `toBool`, `toChar`, `toString`) called directly rather than via `as` casting. Note: `toChar` on a string takes its first character's code point, it does not parse the string as a numeric char code.

### `strings/`
Split from a single `string_operations_comprehensive.fire` into per-behavior files (see "Splitting large test files" below):
- **strings_basics.fire** - Declaration, empty string, long strings
- **strings_concatenation.fire** - Concatenation (literal, repeated, with a cast expression, via variables)
- **strings_escapes.fire** - Escape sequences (`\n`, `\t`, `\"`, `\\`)
- **strings_comparison.fire** - `==` / `!=`
- **strings_unicode.fire** - Emoji and accented characters

### `arrays/`
Split from a single `array_operations_comprehensive.fire` into per-behavior files, plus pre-existing focused tests:
- **arrays_basics.fire** - Declaration, indexing, `.length()`, empty array, large array, bounds access
- **arrays_typed.fire** - int8/int64/float32/float64/string/bool element arrays
- **arrays_mutation.fire** - Element reassignment
- **arrays_iteration_for_in.fire** - for-in iteration
- **arrays_iteration_c_style.fire** - C-style for iteration
- **arrays_iteration_while.fire** - while-loop iteration
- **arrays_function_param.fire** - Array passed to a function and summed
- **array_tests.fire** - Basic array operations
- **array_to_string.fire** - `array as string` conversion for int32, float64, string, and empty arrays (`[a, b, c]` formatting)
- **array_index_count.fire** - `.index()` / `.count()` array methods
- **array_negative_indexing.fire** - Negative index access

### `functions/`
- **functions_basic_params.fire** - No/single/multiple parameters, return values
- **functions_calling_functions.fire** - One function calling another, multi-step internal logic
- **functions_recursion.fire** - Recursive functions (factorial)
- **functions_return_types.fire** - float/bool/string return types
- **functions_array_params.fire** - Array parameters
- **functions_early_and_multiple_returns.fire** - Early return, multiple return paths
- **functions_void.fire** - Void functions with side effects
- **functions.fire** - Basic function examples (multi-return-type, array param, string concat, void with multiple args — a different set of scenarios from the `functions_*` files above)

### `scoping/`
- **scoping_block_nesting.fire** - Global/block scope, deeply nested blocks, complex nesting across block/if/while
- **scoping_control_flow.fire** - if/else, while, for, for-in loop scope
- **scoping_function.fire** - Function scope (parameters and locals not visible outside)
- **scoping_variable_declaration_order.fire** - Declared-before-use, same names in separate sibling scopes
- **scope_tests.fire** - Basic scoping tests

### `expressions/`
- **expressions_function_calls.fire** - Function call expressions, nested function calls
- **expressions_array_and_string.fire** - Array indexing arithmetic, string concatenation expressions
- **expressions_casts.fire** - Casts within expressions, mixed-type expressions
- **expressions_unary_and_incdec.fire** - Unary +/-, increment/decrement
- **expressions_nested_and_conditional.fire** - Complex nested parenthesized expressions, conditional value via if/else
- **operator_precedence.fire** - Operator precedence (each expression commented with the expected value, so a wrong precedence produces an obviously-wrong number)

### `edge_cases/`
- **edge_cases_zero_values.fire** - Zero/empty values across types
- **edge_cases_numeric_bounds.fire** - Min/max values, very large/small numbers
- **edge_cases_arithmetic.fire** - Division and modulo edge cases
- **edge_cases_overflow_underflow.fire** - int8/uint8 overflow, int8 underflow
- **edge_cases_arrays.fire** - Empty array, single-element array, identical elements
- **edge_cases_strings.fire** - Single-char and whitespace-only strings
- **edge_cases_comparisons.fire** - Equality/relational edge cases
- **edge_cases_loops.fire** - Zero-iteration and single-iteration loops
- **edge_cases_nesting_and_functions.fire** - Deeply nested blocks, minimal function, all-paths return function
- **edge_cases.fire** - Various edge case scenarios

### `memory/`
- **memory_branching.fire** - Memory behavior with branching
- **memory_break_continue_owned.fire** - Owned vars correctly dropped on break/continue
- **memory_class_owned_fields.fire** - Classes with owned fields (string) use generated destructors
- **memory_constructor_move.fire** - Owned objects moved into a constructor not double-freed
- **memory_early_exit_precision.fire** - Precise drop insertion around early exits (only variables actually in scope at the exit point are dropped)
- **memory_early_return.fire** - Memory with early returns
- **memory_move_no_use_after_free.fire** - Moving an owned value via declaration/assignment does not drop the moved-from variable (no use-after-free / double-drop)
- **memory_reassign.fire** - Memory during reassignment (int and string)
- **memory_scopes.fire** - Memory in different scopes
- **ownership_demo.fire** - Ownership model demonstration
- **ownership_test.fire** - Ownership testing
- **move_semantics_test.fire** - Move semantics
- **borrow_test.fire** - Borrowing tests
- **copyable_test.fire** - Copyable type testing
- **receiver_mut.fire** - `&this` / `&mut this` borrow receivers on class methods

### `classes/`
- **classes_smoke.fire** - Basic class smoke tests
- **classes_field_access.fire** - Class field access
- **classes_methods.fire** - Class methods
- **classes_nested.fire** - Nested classes
- **classes_deep.fire** - Deep class testing
- **classes_static_methods.fire** - Static methods
- **inheritance.fire** - Class inheritance, `super()`, multi-level (double/triple/quad) inheritance chains
- **return_class_test.fire** - Returning a class instance from a function

### `generics/`
- **generics_basic.fire** - Basic generic functions
- **generics_simple.fire** - Simple generic examples
- **generics_clamp.fire** - Generic clamp function
- **generics_constraint.fire** - Type constraints on generics
- **generics_swap.fire** - Generic swap function
- **constraint_alias_test.fire** - Constraint aliases
- **nested_constraint_test.fire** - Nested constraints
- **math_with_constraints.fire** - Math operations with constraints
- **generics_class_basic.fire** - Generic classes (`class Pair<T, U>`) with explicit type arguments at both declaration and construction sites
- **generics_class_inferred_construct.fire** - Generic class construction with type arguments omitted at the call site (`Pair<int32, string> p = Pair(1, "x");`), inferred from the declared variable type

### `imports/`
- **imports_single.fire** - Single symbol import
- **imports_multi.fire** - Multiple symbol imports (merges `math_utils` and `string_utils`)
- **imports_symbols.fire** - Specific symbol imports (`utils`)
- **imports_wildcard.fire** - Wildcard imports (`utils.*`)
- **export_visibility.fire** - Importing an explicitly exported symbol (`visibility_provider.addOne`)
- **utils.fire**, **math_utils.fire**, **string_utils.fire**, **visibility_provider.fire** - Helper modules, not standalone tests

### `io/`
- **io_test.fire** - Input/output functions

### `performance/`
- **fibonacci.fire** - Recursive fibonacci (also used for benchmarking)
- **stress_array_bounds.fire** - Array boundary access stress test (off-by-one, index validation)
- **stress_deep_recursion.fire** - Deep recursion stress test
- **stress_integer_overflow.fire** - Integer overflow behavior under repeated operations
- **stress_string_operations.fire** - Heavy string concatenation/manipulation
- **stress_type_conversions.fire** - Repeated type conversion stress test

### `special_types/`
- **float128_test.fire** - 128-bit float testing
- **float128_ops.fire** - binary128 soft-float: arithmetic (`+ - * /`, unary `-`), comparisons, and conversions (int, float64, string parse)

### `std/regex/`
- **std_regex_basic.fire** - `is_match` over literals, `.`, alternation, quantifiers (`* + ?`), groups, character classes (including ranges and negation), and `last_error` for invalid patterns
- **std_regex_anchor_simple.fire** / **std_regex_anchors.fire** - Anchor handling (`^`, `$`) in `is_match`
- **std_regex_find_at.fire** / **std_regex_find_at_anchors.fire** - Position-aware matching via `find_at`, with and without anchors
- **std_regex_validate_anchors.fire** / **std_regex_validate_anchors2.fire** - Pattern validation with anchors
- **std_regex_regression_generic_matcher.fire** - Regression: quantifier/group/class patterns (`xy?z`, `(cd)+e`, `[b-d]+`, `x*z`) must go through the generic matcher; guards against reintroducing per-pattern hard-coded results in `is_match`

### `std/fs/`
- **std_fs_basic.fire** - Basic `File`/`FileResult` usage
- **std_fs_helpers.fire** - Filesystem helper functions
- **std_fs_path_ops.fire** - Path manipulation operations

### `std/cli/`
- **std_cli_args_basic.fire** - Basic `std.cli.args` usage
- **std_cli_args_parser.fire** - Argument parser behavior
- **std_cli_args_with_argv.fire** / **std_cli_args_edge_with_argv.fire** - Argument handling with real argv input (`.args` sidecar supplies the process's own command-line tokens)

### `std/fcl/`
- **std_fcl_lexer.fire** - FCL (firescript config language) lexer: tokens, kinds, lexemes, positions

### `std/types/`
- **std_types_test.fire** - `std.types` `Tuple`/`Option` basic usage

### `std/syscalls/`
- **syscall_basic.fire** - Low-level syscall intrinsics (open/read/write/close/etc.)

### `nullable/`
- **nullable_basic.fire** - Nullable variables, `== null` / `!= null` checks
- **nullable_advanced.fire** - Nullable class fields

### `integration/`
Larger multi-feature programs (coding-challenge solutions used as integration-style tests, not focused unit tests):
- **hackathon8_mission1.fire** / **hackathon8_mission2.fire** - `std.io` + `std.fs` combined usage

### `known_issues/`
See "Known-Failing Regression Tests" below.

## Splitting large test files

Prefer many small, single-behavior `.fire` files over one large multi-assertion file — a failure in a 10-line file tells you exactly what broke; a failure in a 150-line file with a dozen unrelated assertions does not. When a category needs more than one file, name them `<category>_<specific_behavior>.fire` (e.g. `arrays_iteration_for_in.fire`, `strings_escapes.fire`). This is the standard convention going forward; all of the original `*_comprehensive.fire` files have been split (see `arrays/`, `strings/`, `control_flow/`, `conversions/`, `edge_cases/`, `expressions/`, `functions/`, `scoping/`, `types/` above). When splitting, drop redundant content already covered by a sibling file in the same category (noted inline above where it applies) and drop commented-out "not yet implemented" placeholder assertions rather than preserving them.

## Known-Failing Regression Tests

These `tests/sources/known_issues/*.fire` cases are **expected to fail** under `golden_runner.py` right now — they were added to lock in known compiler bugs before a fix lands, per CLAUDE.md's "always add a test that would have failed before the fix" rule, applied here in advance of the fix rather than alongside it. Do not "fix" them by editing the golden or deleting the case; they should start passing once the underlying bug referenced in each file's header comment is fixed, at which point re-run with `--update`, review the diff, and move the file into its normal feature category (e.g. an `Option` fix moves `option_issome_isnone_regression.fire` into `std/types/`).

- **option_issome_isnone_regression.fire** - `Option`/`CopyableOption` `isSome()`/`isNone()` return `false` for both calls regardless of whether the option actually holds a value (confirmed: a populated `Option<int32>(42)` and `CopyableOption<int32>(7)` both report `isSome()==false, isNone()==false`). Golden encodes the *correct* expected values (`true, false, true, false`), so the test fails until the bug is fixed. See CLAUDE.md's feature table note and `docs/reference/std/types.md`.
- **generic_nested_call_crash_regression.fire** - `println(max(3, 7))` (passing a generic function call directly as another call's argument) crashes FIR->FLIR lowering with `LoweringError: cannot convert T to string` — the generic type parameter `T` isn't substituted with the concrete instantiated type before the implicit string cast. No golden file (compilation itself fails); the runner reports this as `ERROR` with the full traceback until fixed.
- **generic_method_if_condition_crash_regression.fire** - `if (some_opt.isSome())` (calling a generic class's method inline as a branch condition, or as any inline expression not first assigned to a variable) crashes FIR->FLIR lowering with `LoweringError: unsupported FIR operand NoneType`. No golden file; reports as `ERROR` until fixed.

This category is specifically for currently-known, not-yet-fixed bugs (expected to fail). Normal regression tests added alongside a fix (per CLAUDE.md's standard "Bug Fix Tests" workflow — a test that would have failed before the fix and passes after) go in their feature's regular category directory, not here.

## Invalid Tests

Tests in `tests/sources/invalid/<category>/` are expected to fail compilation and test error handling. Categories:

- **arrays/** - `array_edge_invalid.fire`, `array_errors.fire`, `array_index_count_errors.fire`, `array_slice_errors.fire`
- **borrow/** - `borrow_alias_escape_errors.fire`, `borrow_escape_projection_errors.fire`, `borrow_move_errors.fire`, `branch_move_errors.fire`, `constructor_borrow_move_errors.fire`, `constructor_move_errors.fire`, `for_in_move_errors.fire`, `loop_move_errors.fire`, `method_move_errors.fire`, `memory_errors.fire` (use-after-move, invalid borrows, out-of-bounds access)
- **classes/** - `class_errors.fire`, `class_static_method_errors.fire`, `receiver_readonly_mutation_errors.fire`
- **control_flow/** - `control_flow_invalid.fire`
- **enums/** - `enum_generic_unsupported.fire` (generic enums `enum Foo<T>` are rejected with a clear, intentional "not yet supported" error rather than a confusing parse failure), `enum_variant_arity_mismatch.fire` (constructing a payload variant with too many/too few arguments is rejected with a clear arity-mismatch error)
- **functions/** - `function_errors.fire`
- **generics/** - `generics_errors.fire`
- **imports/** - `import_errors.fire`, `export_visibility_private.fire` (importing a non-exported symbol), `visibility_provider.fire` (helper, not a standalone test)
- **literals/** - `literal_errors.fire`
- **match/** - `match_non_exhaustive.fire` (missing variant arms and no `_` wildcard), `match_duplicate_variant.fire` (same variant matched twice), `match_wildcard_not_last.fire` (arms after a wildcard `_` are unreachable), `match_unknown_variant.fire` (pattern references a variant that doesn't exist on the enum), `match_unknown_payload_field.fire` (pattern binds a field name the variant doesn't declare), `match_duplicate_field_binding.fire` (the same payload field is bound twice in one pattern)
- **nullable/** - `nullable_errors.fire`
- **operators/** - `operator_errors.fire`
- **scoping/** - `scope_errors.fire` (variable shadowing not allowed, use before declaration, out-of-scope access)
- **strings/** - `string_implicit_conv_error.fire`
- **syntax/** - `syntax_errors.fire`, `syntax_comprehensive.fire` (missing semicolons, unclosed parens/braces, invalid tokens, malformed control flow)
- **types/** - `type_mismatches.fire`, `type_errors_comprehensive.fire` (type mismatches in assignments, function calls, operators, conditions, indexing)

### Error Test System

- **Location**: `tests/sources/invalid/<category>/*.fire`
- **Expected Errors**: `tests/expected_errors/<category>/*.err`
- **Runner**: `tests/error_runner.py`

### How It Works

1. Invalid source files are linted through the compiler front-end.
2. Structured diagnostics are collected as error objects.
3. Diagnostics are compared to golden signatures in this format: `<ERROR_CODE>@<line>:<column>`.
4. Test passes when all expected signatures match.

### Benefits

- **Message-Independent**: Error message text can evolve without brittle test churn.
- **Regression Prevention**: Error code and location regressions are caught immediately.
- **Location Accuracy**: Ensures diagnostics point to the right source coordinates.

## Test Coverage Summary

| Feature Category | Coverage |
|-----------------|----------|
| Operators | ✅ Comprehensive |
| Control Flow | ✅ Comprehensive |
| Types | ✅ Comprehensive |
| Type Conversions | ✅ Comprehensive |
| Strings | ✅ Comprehensive |
| Arrays | ✅ Comprehensive |
| Functions | ✅ Comprehensive |
| Scoping | ✅ Comprehensive |
| Expressions | ✅ Comprehensive |
| Memory Management | ✅ Good |
| Classes/OOP | ⚠️ Partial (feature in development) |
| Generics | ✅ Good |
| Imports | ✅ Good |
| Edge Cases | ✅ Comprehensive |

## Adding New Tests

1. Pick (or create) the matching category subdirectory under `tests/sources/`, e.g. `tests/sources/arrays/`. Prefer one focused behavior per file over adding more assertions to an existing file — see "Splitting large test files" above.
2. Add test cases with expected output via `println()`.
3. Run `python tests/golden_runner.py --cases tests/sources/<category>/<name>.fire --update` to generate the golden file — it's written to the mirrored `tests/expected/<category>/<name>.out`.
4. Review the generated golden file.
5. Commit both the source and golden files.
6. Update this manifest.

## Golden File Format

Golden files contain the expected stdout output from running the compiled test binary. They use Unix-style line endings (\n) and have trailing newlines stripped per line.

## Test Naming Conventions

- `<category>_<specific_behavior>.fire` - One focused behavior per file, in the `<category>/` directory (the standard convention — see "Splitting large test files"). Do not introduce new `*_comprehensive.fire` multi-assertion files.
- `<feature>_test.fire` - Specific feature test
- `<feature>_<variant>.fire` - Specific variant of a feature (e.g., for_c_style, for_in)

## Continuous Integration

Tests run automatically on GitHub Actions for:
- Push to main branch
- Pull requests to main
- Changes to workflow, compiler, or tests

See `.github/workflows/windows_x86_64_test.yml` for CI configuration.
