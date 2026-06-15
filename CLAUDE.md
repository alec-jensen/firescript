# firescript — CLAUDE.md

## Project Identity

The project name is **firescript**, all lowercase. Do not capitalize it.

## Running the Compiler

```bash
# Compile a firescript source file
python firescript/main.py <source-file>

# Compile with debug output
python firescript/main.py <source-file> -d
```

## Code Style

- Keep a consistent style with existing code.
- Do not add new features or change functionality unless explicitly instructed.
- If something is unclear, ask for clarification. Things exist the way they do for a reason.
- Do not remove code unless you are certain it is dead and unused.

## Documentation Accuracy

The docs in `/docs` describe both **implemented** and **planned** language features. When reading or writing docs, treat status markers as ground truth:

- `[IMPLEMENTED]` — feature is complete and working in the current compiler.
- `[IN DEVELOPMENT]` — feature is partially implemented; behavior may be incomplete or unstable.
- `[PLANNED]` — feature is designed but not yet implemented; it will not compile or run correctly.

When adding or modifying documentation:
- Every documented feature must carry one of these markers.
- Do not describe a planned feature as if it works.
- Do not remove or contradict a marker without verifying the actual implementation.

## Changelog

The changelog lives at `docs/changelog.md`. Changelog rules:

- **Only user-facing changes** belong in the changelog: new syntax, changed behavior, new standard library APIs, breaking changes.
- Internal refactors, performance improvements, and tooling changes that don't affect how a user writes or runs firescript code do **not** need entries.
- Any change to how an end-user interacts with firescript — new keyword, removed built-in, new flag, changed error message format, new or removed stdlib function — **must** be documented under `## Currently in Development` before it is merged.
- Do not move items from `## Currently in Development` into a versioned section; that is done at release time by the project maintainer.

## Tests

### Philosophy

The goal is **100% test coverage** of all implemented language features. Every implemented feature must have at least one test. Every bug fix must be accompanied by a regression test that would have caught the bug.

### Running Tests

```bash
# Valid-code golden tests
python tests/golden_runner.py

# Run a specific test
python tests/golden_runner.py --cases tests/sources/<name>.fire

# Regenerate golden files (review diffs carefully)
python tests/golden_runner.py --update

# Invalid-code / error tests
python tests/error_runner.py
```

### Adding Tests

1. Create a `.fire` source file in `tests/sources/` (or `tests/sources/invalid/` for error tests).
2. For valid tests: add `println()` calls to produce expected output, then run `--update` to generate the golden file. Review the output before committing.
3. For error tests: add the file to `tests/sources/invalid/`. Run `python tests/error_runner.py --update` to capture expected diagnostics in `tests/expected_errors/`.
4. Commit both the source and golden/error files.
5. Update `tests/TEST_MANIFEST.md` to document the new test.

### Golden Files

- Located in `tests/expected/` with a `.out` extension, matching the source filename.
- Per-test command-line argument sidecars can be placed next to the source as `tests/sources/<name>.args`.
- Use Unix line endings; trailing newlines per line are stripped.

### Bug Fix Tests

When fixing a bug, **always add a test** that would have failed before the fix and passes after. Name it `<feature>_regression_<short_description>.fire` or add a case to an existing comprehensive test if the feature already has one.

### Do Not Edit Tests to Force Passing

If a test fails, investigate and fix the underlying compiler or stdlib issue. Only modify a test if there is an intentional, documented behavior change (and update the changelog accordingly).

## Compiler Directives

- Directives are for internal use by the compiler and standard library only.
- Do not add directives to user source files or tests unless testing specific directive behavior.

## Examples and Test Files

Whenever you add a file to `examples/` or `tests/sources/`, create a corresponding golden file in `tests/expected/` with the same name and a `.out` extension containing the expected output.

## Standard Library

Standard library modules live under `firescript/std/`. Sibling modules can be imported with short relative paths (e.g., `import tuple.Tuple;`).

## Feature Status Reference

The table below reflects the **current implementation status** of major language features. Keep this up to date when features are added, completed, or removed.

| Feature | Status |
|---|---|
| Static and strong typing | [IMPLEMENTED] |
| Fixed-width numeric types (`int8`…`uint64`, `float32`, `float64`) | [IMPLEMENTED] |
| `float128` (true 16-byte IEEE binary128; self-hosted soft-float) | [IMPLEMENTED] |
| Literal suffixes (`i8`, `u32`, `f64`, etc.) | [IMPLEMENTED] |
| `char` type | [IMPLEMENTED] |
| Character literals (`'A'`, `'\n'`) | [IMPLEMENTED] |
| String concatenation (explicit, `string + string`) | [IMPLEMENTED] |
| `string.length()` | [IMPLEMENTED] |
| String-to-numeric casting (`"42" as int32`) | [IMPLEMENTED] |
| String iteration in `for-in` | [IMPLEMENTED] |
| Explicit `as` casting (numeric ↔ numeric, built-ins → string) | [IMPLEMENTED] |
| `if` / `else if` / `else` | [IMPLEMENTED] |
| `while` loops | [IMPLEMENTED] |
| C-style `for` loops | [IMPLEMENTED] |
| `for-in` loops (arrays and strings) | [IMPLEMENTED] |
| `break` / `continue` | [IMPLEMENTED] |
| Functions (params, return values, recursion) | [IMPLEMENTED] |
| Generic functions | [IMPLEMENTED] |
| Fixed-size arrays | [IMPLEMENTED] |
| Negative array indexing | [IMPLEMENTED] |
| Array utility methods (`index`, `count`) | [IMPLEMENTED] |
| Classes (fields, methods, constructors, inheritance) | [IMPLEMENTED] |
| Generic classes (`class Pair<T, U>`) | [IMPLEMENTED] |
| Class static methods | [IMPLEMENTED] |
| `&this` / `&mut this` borrow receivers | [IMPLEMENTED] |
| Logical operators (`&&`, `||`, `!`) | [IMPLEMENTED] |
| Exponentiation (`**`) | [IMPLEMENTED] |
| Compound assignment (`+=`, `-=`, `*=`, `/=`, `%=`) | [IMPLEMENTED] |
| Increment / decrement (`++`, `--`) | [IMPLEMENTED] |
| Imports and modules | [IMPLEMENTED] |
| Explicit module exports (private by default) | [IMPLEMENTED] |
| Ownership model (moves, borrows, copyable types) | [IMPLEMENTED] |
| Deterministic drop / destructor insertion | [IMPLEMENTED] |
| `@firescript/std.io` (`print`, `println`) | [IMPLEMENTED] |
| `@firescript/std.math` | [IMPLEMENTED] |
| `@firescript/std.types` (`Tuple`, `Option`, etc.) | [IMPLEMENTED] |
| `@firescript/std.fs` (`File`, `FileResult`) | [IMPLEMENTED] |
| `@firescript/std.regex` | [IMPLEMENTED] |
| `@firescript/std.cli.args` | [IMPLEMENTED] |
| `@firescript/std.fcl` (FCL lexer) | [IMPLEMENTED] |
| LSP server (`firescript/lsp_server.py`) | [IMPLEMENTED] |
| VS Code extension (syntax highlighting, LSP diagnostics) | [IMPLEMENTED] |
| Generator functions (`generator<T>`, `yield`) | [IMPLEMENTED] |
| `for-in` over generators | [IMPLEMENTED] |
| `@firescript/std.ranges` (`range`, `rangeFrom`, `rangeStep`) | [IMPLEMENTED] |
| FIR + FLIR pipeline (AST → FIR → FLIR → native code) | [IMPLEMENTED] |
| Native x86-64 backend (Windows x64; freestanding, kernel32-only) | [IMPLEMENTED] |
| Self-hosted toolchain (Python x86-64 assembler + PE writer; no external tools) | [IMPLEMENTED] |
| firescript-implemented runtime (`std/internal/runtime.fire`) | [IMPLEMENTED] |
| Linux / macOS native targets | [PLANNED] |
| JavaScript + Wasm compilation target | [PLANNED] |
| Dynamic arrays (stdlib) | [PLANNED] |
| Built-in `input()` function | Removed in current dev cycle |
