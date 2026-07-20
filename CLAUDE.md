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

## Determinism

The compiler must be fully deterministic: compiling the same source twice on the same machine must produce byte-identical output. Never introduce reliance on hash-randomized iteration order (e.g. iterating a `dict`/`set` keyed by object identity or `hash()` where insertion order isn't guaranteed stable across runs), uninitialized memory, wall-clock time, or thread/process scheduling order anywhere in the compiler pipeline. The `determinism` test kind (`tests/run.py`, see [test_harness_v2.md](docs/internal/development/test_harness_v2.md)) enforces this by compiling sources twice and byte-comparing the binaries — treat any failure there as a real compiler bug, not a harness flake, unless proven otherwise.

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

## Commits and Pushes

- **Changelog**: any commit with a user-facing change updates `docs/changelog.md` in the same commit (see Changelog rules above) — not a follow-up commit.
- **Regression tests**: any commit that fixes a bug includes its regression test in the same commit (see Bug Fix Tests below) — not a follow-up commit.
- **Feature Status Reference**: any commit that adds, completes, or removes a language feature updates the table below in the same commit.
- **Docs status markers**: any commit that changes a feature's implementation status updates that feature's `[IMPLEMENTED]` / `[IN DEVELOPMENT]` / `[PLANNED]` marker under `/docs` in the same commit (see Documentation Accuracy above).
- **Test manifest**: any commit that adds a new test category or file updates `tests/TEST_MANIFEST.md` in the same commit.
- **One logical change per commit**: don't bundle an unrelated fix or cleanup into a feature/bugfix commit.
- **No stray build artifacts**: check `git status` before staging — `.gitignore` covers known cases (`build/`, `*.pyc`, `hello.fire`, `kiln.exe`) but is hand-maintained, so watch for one-off compiled binaries or scratch `.fire` files it doesn't yet know about.
- **Commit messages**: short imperative summary line, matching the style already in `git log`; a body only when the *why* isn't obvious from the diff. No co-authored-by trailer.
- Never commit with `--no-verify`; never amend a commit that's already been pushed.
- Never push without asking first — every time, even within the same session; a prior approval doesn't carry forward.

## Tests

### Philosophy

The goal is **100% test coverage** of all implemented language features. Every implemented feature must have at least one test. Every bug fix must be accompanied by a regression test that would have caught the bug.

### Never Skip Tests

There is no skip capability anywhere in the test harness, and none should ever be added. If a test can't currently pass — a compiler bug, a harness limitation, environmental flakiness — it must fail or error loudly, not be silently skipped or hidden. Do not add a `//@ skip:`-style directive, a `pyunit` skip helper, a `Status.SKIP`-equivalent result, or any other mechanism that makes a discovered test disappear from the pass/fail count. If a case is a known, not-yet-fixed bug, document it with a header comment explaining the bug and let it fail/error (see `tests/sources/known_issues/` and `tests/sources/invalid/known_issues/` for the convention — move the file there, don't remove it from the run). Never edit a test's expectations just to make a known-broken case stop showing up as a failure.

### Running Tests

```bash
# Run everything: run + compile-fail + snapshot + python kinds
python tests/run.py

# Run a specific test (works for .fire and .py)
python tests/run.py tests/sources/<category>/<name>.fire
python tests/run.py tests/python/<category>/test_foo.py::test_bar

# Run only one kind, or everything under a category
python tests/run.py kind:run
python tests/run.py kind:compile-fail
python tests/run.py <category>

# Bless mode: rewrite in-file EXPECT blocks / //~ annotations / snapshots to
# match current output (review the diff before committing!)
python tests/run.py --update

# List matching test ids without running them
python tests/run.py --list
```

Test sources are grouped into category subdirectories (`tests/sources/<category>/`, e.g. `arrays/`, `classes/`, `std/regex/`). Error tests follow the same pattern under `tests/sources/invalid/<category>/`. All expectations for a `.fire` test live **inside the file itself** as magic-comment directives (`//@ key: value`), diagnostic annotations (`//~ ERROR <CODE>`), and a trailing `/* EXPECT ... */` output block — there are no sidecar golden files, with the sole exception of FIR/FLIR IR snapshots under `tests/snapshots/<category>/`. Python-based tests live under `tests/python/<category>/test_*.py` and always run. See `tests/TEST_MANIFEST.md` for the full category list, directive reference, and harness architecture pointer (`docs/internal/development/test_harness_v2.md`).

### Adding Tests

1. Pick (or create) the matching category subdirectory, e.g. `tests/sources/arrays/` (or `tests/sources/invalid/<category>/` for error tests). Prefer one focused behavior per file — see "Splitting large test files" in `tests/TEST_MANIFEST.md` — over adding more assertions to an existing file.
2. For valid tests: write the `.fire` file with `println()` calls, then run `python tests/run.py <path> --update` to write the `/* EXPECT ... */` block *into the file*. Review it before committing.
3. For error tests: add the file to `tests/sources/invalid/<category>/` with `//~ ERROR <CODE> [@<col>]` annotations (hand-written, or generated with `python tests/run.py <path> --update`).
4. For Python tests: add a `test_*` function to a `tests/python/<category>/test_*.py` module (new or existing); it runs automatically, no registration needed.
5. Commit the source file(s).
6. Update `tests/TEST_MANIFEST.md` to document the new test.

### Bug Fix Tests

When fixing a bug, **always add a test** that would have failed before the fix and passes after, in the feature's normal category directory. Name it `<feature>_regression_<short_description>.fire` or add a case to an existing comprehensive test if the feature already has one. (`tests/sources/known_issues/` is a separate, narrower convention for bugs found but not yet fixed — see `tests/TEST_MANIFEST.md`.)

### Do Not Edit Tests to Force Passing

If a test fails, investigate and fix the underlying compiler or stdlib issue. Only modify a test if there is an intentional, documented behavior change (and update the changelog accordingly).

## Compiler Directives

- Directives are for internal use by the compiler and standard library only.
- Do not add directives to user source files or tests unless testing specific directive behavior.

## Examples and Test Files

Whenever you add a file to `examples/` or `tests/sources/<category>/`, give it a trailing `/* EXPECT ... */` block with the expected output (run `python tests/run.py <path> --update` to generate it) — see "Adding Tests" above.

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
| `string.upper()` / `string.lower()` | [IMPLEMENTED] |
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
| `@firescript/std.types` — `Tuple`, `CopyableTuple` | [IMPLEMENTED] |
| `@firescript/std.types` — `Option`, `CopyableOption` | [IMPLEMENTED] |
| `@firescript/std.types` — `Result`, `CopyableResult` | [IMPLEMENTED] |
| `@firescript/std.fs` (`File`, `FileResult`) | [IMPLEMENTED] |
| `@firescript/std.regex` | [IMPLEMENTED] |
| `@firescript/std.cli.args` | [IMPLEMENTED] |
| `@firescript/std.fcl` (FCL lexer) | [IMPLEMENTED] |
| LSP server (`firescript/lsp_server.py`) | [IMPLEMENTED] |
| VS Code extension (syntax highlighting, LSP diagnostics) | [IMPLEMENTED] |
| Generator functions (`fn` returning `generator<T>`, `yield`) | [IMPLEMENTED] |
| `for-in` over generators | [IMPLEMENTED] |
| `@firescript/std.ranges` (`range`, `rangeFrom`, `rangeStep`) | [IMPLEMENTED] |
| FIR + FLIR pipeline (AST → FIR → FLIR → native code) | [IMPLEMENTED] |
| Native x86-64 backend (Windows x86_64; freestanding, kernel32-only) | [IMPLEMENTED] |
| Self-hosted toolchain (Python x86-64 assembler + PE writer; no external tools) | [IMPLEMENTED] |
| firescript-implemented runtime (`std/internal/*.fire`) | [IMPLEMENTED] |
| Linux / macOS native targets | [PLANNED] |
| Dynamic arrays (stdlib, `std.collections.Vec<T>`) | [IMPLEMENTED] |
| Built-in `input()` function | Removed in current dev cycle |
| `enum` declarations, tag-only and named-data-payload variants (`Circle(float64 radius)`) | [IMPLEMENTED] |
| Generic enums (`enum Option<T>`) | [PLANNED] |
| `match` expressions, statement and value-producing forms | [IMPLEMENTED] |
