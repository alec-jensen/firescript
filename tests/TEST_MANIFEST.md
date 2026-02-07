# firescript Test Suite

This document provides an overview of the test suite for the firescript compiler.

## Test Organization

All test source files are located in `tests/sources/`. Golden output files are in `tests/expected/`. The test runner (`tests/golden_runner.py`) compiles each test file, runs it, and compares output against golden files.

## Running Tests

### Valid Code Tests (Golden Tests)

```bash
# Run all tests
python tests/golden_runner.py

# Run specific test(s)
python tests/golden_runner.py --cases tests/sources/operators_arithmetic.fire

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
python tests/error_runner.py --cases tests/sources/invalid/syntax_errors.fire

# Update expected error files (review diffs carefully!)
python tests/error_runner.py --update

# Verbose output
python tests/error_runner.py --verbose

# Stop on first failure
python tests/error_runner.py --fail-fast
```

The error test runner verifies that:
- Invalid code fails compilation (returns non-zero exit code)
- Error messages match expected output exactly
- Error line numbers are correct
- No unexpected errors or warnings appear

Expected error files are stored in `tests/expected_errors/` with `.err` extension.

## Test Categories

### Core Language Features

#### Operators
- **operators_arithmetic.fire** - All arithmetic operators (+, -, *, /, %, **), compound assignment (+=, -=, etc.), increment/decrement
- **operators_comparison.fire** - Equality (==, !=), relational (<, >, <=, >=) for all numeric types and strings
- **operators_logical.fire** - Logical AND (&&), OR (||), NOT (!), short-circuit evaluation, complex boolean expressions
- **unary_test.fire** - Unary operators (-, +, !)

#### Control Flow
- **control_flow_comprehensive.fire** - if/else/else-if chains, while loops, C-style for loops, for-in loops, break/continue, nested control structures
- **for_c_style.fire** - C-style for loop variations
- **for_in.fire** - For-in loop over arrays

#### Types and Variables
- **types_numeric_comprehensive.fire** - All numeric types (int8/16/32/64, uint8/16/32/64, float32/64/128), min/max values, overflow behavior
- **types_tests.fire** - Basic type operations and comparisons
- **types_deep.fire** - Deep type testing

#### Type Conversions
- **conversions_comprehensive.fire** - Explicit casting with 'as' keyword, int-to-int, int-to-float, float-to-int, signed/unsigned conversions
- **numeric_casts.fire** - Numeric type casting
- **simple_cast_test.fire** - Simple casting examples
- **string_cast_test.fire** - String casting operations

#### Strings
- **string_operations_comprehensive.fire** - String declaration, concatenation, comparison, length, special characters, unicode
- **test_string_heap.fire** - String heap allocation testing

#### Arrays
- **array_operations_comprehensive.fire** - Array declaration, indexing, length, iteration, multi-dimensional arrays, array functions
- **array_tests.fire** - Basic array operations
- **test_array_string.fire** - Array of strings

#### Functions
- **functions_comprehensive.fire** - Function declaration, parameters, return values, recursion, array parameters/returns, void functions, early returns
- **functions.fire** - Basic function examples

#### Scoping
- **scoping_comprehensive.fire** - Block scope, nested scopes, variable shadowing, function scope, loop scope
- **scope_tests.fire** - Basic scoping tests

#### Expressions
- **expressions_comprehensive.fire** - Operator precedence, parenthesized expressions, complex nested expressions, function calls in expressions

#### Edge Cases
- **edge_cases_comprehensive.fire** - Zero values, min/max values, empty arrays, single-element arrays, empty strings, overflow/underflow, empty loops
- **edge_cases.fire** - Various edge case scenarios

### Advanced Features

#### Memory Management
- **memory_branching.fire** - Memory behavior with branching
- **memory_early_return.fire** - Memory with early returns
- **memory_reassign.fire** - Memory during reassignment
- **memory_scopes.fire** - Memory in different scopes
- **ownership_demo.fire** - Ownership model demonstration
- **ownership_test.fire** - Ownership testing
- **ownership_simple.fire** - Simple ownership examples
- **move_semantics_test.fire** - Move semantics
- **borrow_test.fire** - Borrowing tests
- **test_borrow_to_owned.fire** - Borrow to owned conversions
- **copyable_test.fire** - Copyable type testing
- **use_after_move_test.fire** - Use after move error testing

#### Heap Management
- **test_heap_comprehensive.fire** - Comprehensive heap testing
- **test_heap_verify.fire** - Heap verification

#### Classes and OOP
- **classes_smoke.fire** - Basic class smoke tests
- **classes_field_access.fire** - Class field access
- **classes_methods.fire** - Class methods
- **classes_nested.fire** - Nested classes
- **classes_deep.fire** - Deep class testing
- **inheritance.fire** - Class inheritance
- **return_class_test.fire** - Returning class instances

#### Generics
- **generics_basic.fire** - Basic generic functions
- **generics_simple.fire** - Simple generic examples
- **generics_clamp.fire** - Generic clamp function
- **generics_constraint.fire** - Type constraints on generics
- **generics_swap.fire** - Generic swap function
- **generics_no_comments.fire** - Generics without comments
- **constraint_alias_test.fire** - Constraint aliases
- **nested_constraint_test.fire** - Nested constraints
- **math_with_constraints.fire** - Math operations with constraints

#### Imports/Modules
- **imports_single.fire** - Single symbol import
- **imports_multi.fire** - Multiple symbol imports
- **imports_symbols.fire** - Specific symbol imports
- **imports_wildcard.fire** - Wildcard imports

#### Built-in Functions
- **io_test.fire** - Input/output functions

#### Compiler Features
- **directive_enabled_test.fire** - Compiler directives when enabled
- **directive_isolation_test.fire** - Directive isolation

#### Performance Tests
- **fibonacci.fire** - Recursive fibonacci (also used for benchmarking)

#### Special Types
- **float128_test.fire** - 128-bit float testing

#### Utility Modules (not standalone tests)
- **utils.fire** - Utility functions for other tests
- **math_utils.fire** - Math utility functions
- **string_utils.fire** - String utility functions

### Invalid Tests
Tests in `tests/sources/invalid/` are expected to fail compilation and test error handling.

#### Error Test Categories

**Syntax Errors**
- **syntax_errors.fire** - Original syntax error tests
- **syntax_comprehensive.fire** - Missing semicolons, unclosed parens/braces, invalid tokens, malformed control flow

**Type Errors**
- **type_mismatches.fire** - Original type mismatch tests
- **type_errors_comprehensive.fire** - Type mismatches in assignments, function calls, operators, conditions, indexing

**Scope Errors**
- **scope_errors.fire** - Variable shadowing (not allowed), use before declaration, out-of-scope access

**Memory/Ownership Errors**
- **memory_errors.fire** - Use-after-move, invalid borrows, out-of-bounds access

**Control Flow Errors**
- **control_flow_invalid.fire** - Invalid control flow constructs

**AError Testing

The firescript test suite includes comprehensive error testing to ensure the compiler produces correct error messages for invalid code.

### Error Test System

- **Location**: `tests/sources/invalid/*.fire`
- **Expected Errors**: `tests/expected_errors/*.err`
- **Runner**: `tests/error_runner.py`

### How It Works

1. Invalid source files are compiled (expected to fail)
2. Compiler error output (stderr) is captured
3. Output is normalized (timestamps removed, whitespace normalized)
4. Compared against golden error files
5. Test passes if error output matches exactly

### Benefits

- **Regression Prevention**: Changes to error messages are detected
- **Error Quality**: Ensures error messages are helpful and accurate
- **Line Number Accuracy**: Verifies errors point to the right location
- **No False Positives**: Catches unexpected errors or warnings
### Adding Valid Code Tests

1. Create a new `.fire` source file in `tests/sources/`
2. Add comprehensive test cases with expected output via `println()`
3. Run `python tests/golden_runner.py --update` to generate the golden file
4. Review the generated `tests/expected/<testname>.out` file
5. Commit both the source and golden files
6. Update this manifest

### Adding Error Tests

1. Create a new `.fire` source file in `tests/sources/invalid/`
2. Add code that should produce compilation errors
3. Run `python tests/error_runner.py --update` to generate the expected error file
4. Review the generated `tests/expected_errors/<testname>.err` file
5. Verify the errors are correct, at the right line numbers, and have clear messages
6. Commit both the source and expected error files
7   ERROR] --- Type mismatch for variable 'num'. Expected int32, got string
> int32 num = "string value";
        ^
(tests\sources\invalid\type_errors_comprehensive.fire:7:7)
```

## rray Errors**
- **array_edge_invalid.fire** - Invalid array operations

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

1. Create a new `.fire` source file in `tests/sources/`
2. Add comprehensive test cases with expected output via `println()`
3. Run `python tests/golden_runner.py --update` to generate the golden file
4. Review the generated `tests/expected/<testname>.out` file
5. Commit both the source and golden files
6. Update this manifest

## Golden File Format

Golden files contain the expected stdout output from running the compiled test binary. They use Unix-style line endings (\n) and have trailing newlines stripped per line.

## Test Naming Conventions

- `<feature>_comprehensive.fire` - Comprehensive test coverage for a feature
- `<feature>_test.fire` - Specific feature test
- `<feature>_<variant>.fire` - Specific variant of a feature (e.g., for_c_style, for_in)
- `test_<feature>.fire` - Alternative test naming for specific features

## Continuous Integration

Tests run automatically on GitHub Actions for:
- Push to main branch
- Pull requests to main
- Changes to workflow, compiler, or tests

See `.github/workflows/test.yml` for CI configuration.
