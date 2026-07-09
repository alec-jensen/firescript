# firescript Test Suite

This document provides an overview of the test suite for the firescript compiler.

## Test Organization

Test source files live under `tests/sources/<category>/`, grouped by feature area (e.g. `tests/sources/arrays/`, `tests/sources/classes/`). Invalid/error-triggering sources live under the mirrored `tests/sources/invalid/<category>/`. All expectations for a `.fire` test live **inside the test file itself** as magic-comment directives and a trailing output block — there are no sidecar golden files (the one exception is FIR/FLIR IR snapshots; see "Snapshot Tests" below). Python-based tests (compiler-infrastructure unit tests, CLI invocation tests) live under `tests/python/<category>/test_*.py` and always run alongside the `.fire` suite.

The single entry point for every kind of test is `tests/run.py` (`python tests/run.py`). It replaces the previous eight separate runners (`golden_runner.py`, `error_runner.py`, `cli_runner.py`, `asm_encoding_tests.py`, `fir_unit_tests.py`, `fir_snapshot_runner.py`, `run_tests.py`, `float128_oracle.py`'s self-tests). See `docs/internal/development/test_harness_v2.md` for the full harness architecture spec.

Helper/provider modules that are imported by other tests but never compiled standalone (e.g. `utils.fire`, `math_utils.fire`, files ending in `_provider.fire`) live alongside the tests that import them, since imports resolve relative to the importing file's own directory, and carry a `//@ helper` directive so the harness never treats them as a standalone test case.

## Running Tests

```bash
# Run everything (all kinds: run, compile-fail, snapshot, python)
python tests/run.py

# Run a specific test file (works for .fire and .py)
python tests/run.py tests/sources/operators/operators_arithmetic.fire

# Run everything under a category (checks both sources/<cat> and python/<cat>)
python tests/run.py arrays

# Run only one kind
python tests/run.py kind:run
python tests/run.py kind:compile-fail
python tests/run.py kind:snapshot
python tests/run.py kind:python

# Run one Python test function
python tests/run.py tests/python/cli/test_emit.py::test_emit_ast

# Glob test ids by name
python tests/run.py name:generics_*

# Bless mode: rewrite in-file EXPECT blocks / //~ annotations / snapshots to
# match current output (review the diff before committing!)
python tests/run.py --update

# List matching test ids without running them (also the discovery debugging tool)
python tests/run.py --list

# Verbose per-case output, stop after first failure, parallelism, fixed seed
python tests/run.py --verbose
python tests/run.py --fail-fast
python tests/run.py --jobs 4
python tests/run.py --seed 0x1c9e4d2ab0f37e51

# Coverage report (on by default for unfiltered runs when `coverage` is installed)
python tests/run.py --coverage
python tests/run.py --uncovered   # show only uncovered lines

# CI profile (quick matrix, full determinism sampling)
python tests/run.py --profile ci
```

The master seed for the run is always printed as the first and last line of
output (`Seed: 0x...`) so any run -- including anything that used sampling
(matrix cells, determinism sampling) -- is exactly reproducible with `--seed`.

### `run` kind (golden tests)

Discovers every `tests/sources/**/*.fire` not under `invalid/` and not marked
`//@ helper`. Compiles the file, runs the binary (verifying it imports only
`kernel32.dll` via the pure-Python PE inspector -- firescript binaries are
freestanding), and compares normalized stdout against the trailing `/* EXPECT
... */` block in the source file (see "EXPECT Block Format" below).

### `compile-fail` kind (error tests)

Discovers every `tests/sources/invalid/**/*.fire` not marked `//@ helper`.
Invokes `firescript/main.py --check --message-format json` in a subprocess
and compares the JSON diagnostic events against the file's `//~ ERROR`
line-anchored annotations (see "Invalid Tests" below). Message wording can
change freely without breaking tests; only the diagnostic code, line, and
(optionally) column are checked.

### `snapshot` kind (FIR/FLIR IR dumps)

Discovers every `.fire` file carrying `//@ snapshot: fir` and/or `//@
snapshot: flir` (a small, curated subset of the feature surface -- 25 cases
today). Compiles each case twice via `--emit-fir`/`--emit-flir` (the two
dumps must be byte-identical -- an IR-dump determinism check) and compares
against the golden file at `tests/snapshots/<category>/<name>.fir` /
`.flir`. This is the **one deliberate sidecar exception**: IR dumps are
large, machine-generated, and would harm readability if inlined into the
test source.

### `python` kind (compiler-infrastructure and CLI tests)

Discovers every `tests/python/**/test_*.py`; every top-level `test_*`
callable is one test case, run in a worker process using the `pyunit`
micro-framework (`from harness import pyunit as t`; see
`tests/harness/pyunit.py` for the full API: `t.require`, `t.require_eq`,
`t.tmpdir()`, `t.run_compiler()`, `t.subtest()`, `t.params()`; there is no
`t.skip()` -- this harness has no skip capability, see CLAUDE.md).
Plain `assert` also works. Covers:

- `tests/python/cli/` -- `firescript/main.py` invocation behavior never
  exercised by the golden/error/snapshot kinds (`-v`, `--check`, `--emit
  ast`/`asm`/`--emit-fir`, `--emit-deps`, `-o` renaming, `--dir` batch
  compilation, `--message-format json`, `-d` debug mode, import-resolution
  errors), split by area: `test_check.py`, `test_emit.py`,
  `test_dir_batch.py`, `test_output.py`, `test_diagnostics.py`,
  `test_imports.py`.
- `tests/python/backend/test_asm_encoding.py` -- differential + unit tests
  for the pure-Python x86-64 assembler; unit assertions always run,
  differential comparison against MinGW `as` only when `as` is on `PATH`.
- `tests/python/fir/` -- unit tests for `firescript/fir/`: builder
  construction (`test_builder.py`), textual dump format verified against
  the spec example in `docs/internal/development/fir_spec.md`
  (`test_dump.py`), structural validation of terminators/branch
  targets/cross-function value use (`test_validation.py`).
- `tests/python/float128/` -- self-tests for the binary128 correctness
  oracle (`tests/support/float128_oracle.py`): hand-verified constants and
  arithmetic/comparison/parse/format checks (`test_oracle_units.py`), plus
  self-consistency of every generated test vector (`test_oracle_vectors.py`).
- `tests/python/harness/` -- the harness's own tests (directive parser,
  EXPECT/`//~` parsing and rewriting, seed derivation, matrix engine,
  selector matching). The harness ships with its own test coverage since it
  is the arbiter of every other test.

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
- **enum_field_in_class_drop.fire** - Regression: an owned identifier (a class instance) passed as an enum variant's payload argument (`Slot.Holds(b)`) must be moved into the payload, not also auto-dropped at its own scope exit. Covers both a plain owned field (`Holder.note: Note`) and a nested owned-class-inside-enum-inside-class field (`Shelf.slot: Slot` where `Slot.Holds` carries a `Box`), verifying the payload's data survives to the point it's read via `match`.

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

## Splitting large test files

Prefer many small, single-behavior `.fire` files over one large multi-assertion file — a failure in a 10-line file tells you exactly what broke; a failure in a 150-line file with a dozen unrelated assertions does not. When a category needs more than one file, name them `<category>_<specific_behavior>.fire` (e.g. `arrays_iteration_for_in.fire`, `strings_escapes.fire`). This is the standard convention going forward; all of the original `*_comprehensive.fire` files have been split (see `arrays/`, `strings/`, `control_flow/`, `conversions/`, `edge_cases/`, `expressions/`, `functions/`, `scoping/`, `types/` above). When splitting, drop redundant content already covered by a sibling file in the same category (noted inline above where it applies) and drop commented-out "not yet implemented" placeholder assertions rather than preserving them.

## Known-Failing Regression Tests

`tests/sources/known_issues/*.fire` cases are **expected to fail** under the `run` kind right now — they were added to lock in known compiler bugs before a fix lands, per CLAUDE.md's "always add a test that would have failed before the fix" rule, applied here in advance of the fix rather than alongside it. Do not "fix" them by editing the EXPECT block or deleting the case; they should start passing once the underlying bug referenced in each file's header comment is fixed, at which point re-run with `--update`, review the diff, and move the file into its normal feature category. As of this writing the category is empty -- the three prior entries (`Option`/`CopyableOption` `isSome()`/`isNone()` wrong values, and two generic-call FIR->FLIR lowering crashes) were all traced to one root cause in `ast_to_fir.py`'s `_find_method_def()`/`_expr_type()` (methods/calls on a class or function imported from another module could resolve against a stale or unsubstituted generic type instead of the concrete instantiation) and fixed; the regression tests now live at `std/types/option_issome_isnone.fire`, `generics/generic_nested_call.fire`, and `generics/generic_method_if_condition.fire`.

This category is specifically for currently-known, not-yet-fixed bugs (expected to fail). Normal regression tests added alongside a fix (per CLAUDE.md's standard "Bug Fix Tests" workflow — a test that would have failed before the fix and passes after) go in their feature's regular category directory, not here.

## Invalid Tests

Tests in `tests/sources/invalid/<category>/` are expected to fail compilation and test error handling. Categories:

- **arrays/** - `array_edge_invalid.fire`, `array_errors.fire`, `array_index_count_errors.fire`, `array_slice_errors.fire`
- **borrow/** - `borrow_alias_escape_errors.fire`, `borrow_escape_projection_errors.fire`, `borrow_move_errors.fire`, `branch_move_errors.fire`, `constructor_borrow_move_errors.fire`, `constructor_move_errors.fire`, `for_in_move_errors.fire`, `loop_move_errors.fire`, `method_move_errors.fire`, `memory_errors.fire` (use-after-move, invalid borrows, out-of-bounds access)
- **classes/** - `class_errors.fire`, `class_static_method_errors.fire`, `receiver_readonly_mutation_errors.fire`
- **control_flow/** - `control_flow_invalid.fire`
- **enums/** - `enum_generic_unsupported.fire` (generic enums `enum Foo<T>` are rejected with a clear, intentional "not yet supported" error rather than a confusing parse failure), `enum_variant_arity_mismatch.fire` (constructing a payload variant with too many/too few arguments is rejected with a clear arity-mismatch error), `enum_construct_move_errors.fire` (regression: passing an owned identifier as an enum variant's payload argument moves it, so using that identifier afterward is a use-after-move error, same as passing it to a function/constructor/method call)
- **functions/** - `function_errors.fire`
- **generics/** - `generics_errors.fire`
- **imports/** - `import_errors.fire`, `export_visibility_private.fire` (importing a non-exported symbol), `visibility_provider.fire` (helper, not a standalone test)
- **literals/** - `literal_errors.fire`
- **match/** - `match_non_exhaustive.fire` (missing variant arms and no `_` wildcard), `match_duplicate_variant.fire` (same variant matched twice), `match_wildcard_not_last.fire` (arms after a wildcard `_` are unreachable), `match_unknown_variant.fire` (pattern references a variant that doesn't exist on the enum), `match_unknown_payload_field.fire` (pattern binds a field name the variant doesn't declare), `match_duplicate_field_binding.fire` (the same payload field is bound twice in one pattern), `match_syntax_errors.fire` (malformed match expression syntax)
- **nullable/** - `nullable_errors.fire`
- **operators/** - `operator_errors.fire`
- **scoping/** - `scope_errors.fire` (variable shadowing not allowed, use before declaration, out-of-scope access)
- **strings/** - `string_implicit_conv_error.fire`
- **syntax/** - `syntax_errors.fire`, `syntax_comprehensive.fire` (missing semicolons, unclosed parens/braces, invalid tokens, malformed control flow), `export_errors.fire` (invalid uses of `export`), `expression_operand_errors.fire` (missing right-hand operands and malformed primary expressions)
- **types/** - `type_mismatches.fire`, `type_errors_comprehensive.fire` (type mismatches in assignments, function calls, operators, conditions, indexing)

### Error Test System

- **Location**: `tests/sources/invalid/<category>/*.fire`
- **Expected diagnostics**: in-file `//~ ERROR <CODE> [@<column>]` annotations, anchored to the offending source line (see "Directive Reference" below) -- no sidecar files.
- **Kind**: `compile-fail` (`python tests/run.py kind:compile-fail`)

### How It Works

1. `firescript/main.py --check --message-format json` is invoked in a subprocess against the invalid source.
2. Structured JSON diagnostic events are parsed from its output.
3. Diagnostics are compared against the file's `//~ ERROR` annotations: the multiset of `(code, line, column?)` must match exactly (column is only checked when the annotation specifies one).
4. Test passes when all annotations match with no missing or extra diagnostics.

### Benefits

- **Message-Independent**: Error message text can evolve without brittle test churn (an optional quoted substring can still assert on wording when useful).
- **Regression Prevention**: Error code and location regressions are caught immediately.
- **Location Accuracy**: Ensures diagnostics point to the right source coordinates.
- **Self-Maintaining Line Numbers**: `//~^` caret-stacking anchors an annotation to a line *relative to itself*, so annotations don't silently go stale when lines are inserted/removed elsewhere in the file (the classic problem with absolute-line-number sidecar files).

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

### A golden (`run` kind) test

1. Pick (or create) the matching category subdirectory under `tests/sources/`, e.g. `tests/sources/arrays/`. Prefer one focused behavior per file over adding more assertions to an existing file — see "Splitting large test files" above.
2. Write the `.fire` file with test cases producing expected output via `println()`. Add any `//@` header directives it needs (`//@ args:`, `//@ exit-code:`, etc. -- see "Directive Reference" below).
3. Run `python tests/run.py tests/sources/<category>/<name>.fire --update` to write the trailing `/* EXPECT ... */` block *into the file itself*.
4. Review the EXPECT block the update wrote (it's part of the diff now, not a separate golden file).
5. Commit the source file.
6. Update this manifest.

### An error (`compile-fail` kind) test

1. Add the file to `tests/sources/invalid/<category>/`.
2. Either hand-write `//~ ERROR <CODE> [@<column>]` annotations on the offending lines, or run `python tests/run.py tests/sources/invalid/<category>/<name>.fire --update` to have the harness insert them from the compiler's actual diagnostics.
3. Review the inserted annotations.
4. Commit the source file.

### A Python test

Add a `test_*` function to an existing (or new) `tests/python/<category>/test_*.py` module; it always runs, no registration needed. Use `from harness import pyunit as t` for assertions/helpers.

## EXPECT Block Format

The trailing `/* EXPECT ... */` block (or its `// EXPECT: <line>` fallback form, used only when the expected output itself contains a `*/`) holds the expected stdout from running the compiled test binary, normalized the same way the actual output is: Unix-style line endings (`\n`), trailing whitespace stripped per line. It must be the last non-blank content in the file. `--update` rewrites it in place.

## Directive Reference

Header directives (`//@ key: value` in `.fire` files, `#@ key: value` in `.py` files) must appear in the leading comment block at the top of the file -- one found after the first code token is a discovery-time error, never a silent skip. `//~` diagnostic annotations are the opposite: only valid *after* code starts, anchored to source lines.

**There is no skip directive and no skip capability anywhere in this harness, on purpose** -- see CLAUDE.md's "never skip tests" rule. A test that can't currently pass must fail or error loudly (optionally moved into a `known_issues/` directory with a header comment explaining why, per the conventions above), never silently disappear from the results.

| Directive | Applies to | Meaning |
|---|---|---|
| `//@ mode: run \| compile-fail` | `.fire` | Explicit kind override; normally inferred from location (`invalid/` -> compile-fail). Conflicting with location is a discovery error. |
| `//@ helper` | `.fire` | File is imported by other tests; never a standalone test case. |
| `//@ args: <tokens>` | `.fire` | argv for the compiled binary, shlex-split (repeatable, concatenates with `arg:` in file order). |
| `//@ arg: <verbatim>` | `.fire` | One argv token, verbatim to end of line (repeatable). |
| `//@ stdin: <text>` | `.fire` | One line of stdin (repeatable, joined with `\n`). Mutually exclusive with `stdin-file:`. |
| `//@ stdin-file: <path>` | `.fire` | stdin from a file, path relative to the test file. |
| `//@ exit-code: <int>` | `.fire` | Expected binary exit code (default 0). |
| `//@ timeout: <seconds>` | `.fire` | Binary run timeout (default: harness config). |
| `//@ compile-timeout: <seconds>` | `.fire` | Compile timeout (default: harness config). |
| `//@ compile-flags: <flags>` | `.fire` | Extra flags appended to the compiler invocation. |
| `//@ snapshot: fir[, flir]` | `.fire` | Opt into the `snapshot` kind in addition to `run`. |
| `//@ no-matrix` | `.fire` | Run only in the default matrix cell. |
| `//@ no-determinism: <reason>` | `.fire` | Exclude from determinism-kind sampling; reason required. |
| `//~ [^*] ERROR <CODE> [@<col>] ["substr"]` | `.fire` (`invalid/`) | Expected diagnostic, anchored to its own line minus one per leading `^`. |

Unknown directive keys, and directives outside the rules above (misplaced `//@`, a `compile-fail` file with zero `//~` annotations, a duplicate EXPECT block), are always loud discovery errors -- never silently skipped.

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
