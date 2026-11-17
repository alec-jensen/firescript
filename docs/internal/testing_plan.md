# fuzzing and advanced edge-case testing plan

> Status: **[PLANNED]** — nothing here exists yet unless it says so. The release roadmap that
> schedules this work is [version_planning.md](version_planning.md). The existing test harness is
> described in `tests/TEST_MANIFEST.md`.

## Goals

- A compiler that **never crashes with a Python traceback**: every input produces either a binary
  or a diagnostic.
- Find bugs that hand-written tests miss, using **oracles** (a trusted second opinion) instead of
  hand-written expected output wherever one exists.
- Keep every found bug permanent: each one becomes a regression test per `CLAUDE.md`.
- Stay deterministic: every fuzz run is reproducible from a printed seed (the harness already
  prints and accepts `--seed`).

Line coverage is a diagnostic here, not a goal; see the test philosophy in `CLAUDE.md`.

## 1. Fuzzing

### 1.1 Harness integration

- A new `fuzz` test kind in `tests/harness/kinds/`, **excluded from the default profile** so
  `python tests/run.py` stays fast; included under `--profile full` and a scheduled (nightly) CI
  job. A short fixed-seed smoke run is allowed in the default CI profile.
- Every failure prints its seed and writes the failing input plus a **minimized** copy
  (delta-debugging over tokens/lines) to the work directory.
- A found bug is fixed, and its minimized repro is added as an ordinary regression test in the
  feature's category directory. Fuzz targets never get a skip mechanism.
- Standard library only for generators and mutators (no new dependency) unless a tool is clearly
  worth it; `hypothesis` is the one candidate and would be a dev-only dependency.

### 1.2 Targets

| Target | Input | Invariant (oracle) |
|---|---|---|
| Lexer / parser | Mutated corpus of `tests/sources/**/*.fire` (character, token, and splice mutations) plus grammar-generated programs | Never an uncaught Python exception; either diagnostics or success |
| Whole front-end (`--check`) | Same | Never crashes; diagnostics have valid locations; same input gives identical diagnostics twice |
| Backend arithmetic | Generated well-typed expression programs over every integer/float width | Compiled-and-run output equals a Python reference evaluator that implements firescript's wraparound, cast, and shift rules |
| Regex | Random patterns and texts within the supported syntax | `is_match`, `find_first`, `find_all`, `replace` agree with Python's `re` (`fullmatch` for `is_match`) on the supported subset; unsupported syntax yields `last_error`, never a crash |
| `ArrayList`, `HashMap`, `StringBuilder`, `split`, string methods | Random operation sequences | Model-based: results equal a Python `list` / `dict` / `str` run through the same operations; no leak or crash |
| Assembler encoder | Random instruction/operand combinations | Bytes equal GNU `as` (extends `test_asm_encoding.py`; see 3.5) |
| FIR / FLIR verifiers | Valid FIR/FLIR with one random corruption applied | The verifier rejects it with a diagnostic; valid IR from real programs is always accepted |
| Ownership and borrowing (after 0.8.0) | Random programs of moves, copies, borrows, scopes, early exits | The compiler either rejects with an ownership diagnostic, or the program runs with no use-after-move, leak, or double free |

### 1.3 Prerequisites

- A runtime **allocation counter** (debug-only, behind a directive) so leaks and double frees are
  detectable at run time and not only by the static heap verifier.
- A small generator library under `tests/support/` (typed expression generator, program
  generator, pattern generator) shared by the fuzz targets.
- Ownership fuzzing waits for the 0.8.0 memory model, since the rules change; the other targets
  can start now.

## 2. Advanced edge-case testing

Systematic matrices for places where bugs hide, written as ordinary run tests (or generated into
them):

- **Numeric boundaries.** For every integer width: min, max, ±1, overflow wraparound for `+ - *`,
  `MIN / -1`, division and modulo by zero behavior, shifts by amounts at and beyond the width,
  every cast pair. Floats: NaN, ±infinity, -0.0, denormals, float-to-int out of range, parsing and
  printing round trips. `float128` against published IEEE binary128 test vectors.
- **Strings and arrays.** Empty, very long, embedded escapes, non-ASCII bytes; boundary indices
  for `substring`, `indexOf`, negative array indexing, zero-length arrays, out-of-range access
  (define and test the behavior).
- **Compiler robustness.** Deeply nested expressions and blocks (the parser is recursive; a deep
  nest must give a diagnostic, not a Python `RecursionError`), very long identifiers and
  literals, many functions, very large files.
- **Stack and heap stress.** Deep recursion limits, allocate/free churn over many iterations with
  owned elements (`ArrayList`, `HashMap`, strings, classes), large arrays.
- **Feature interaction matrix.** Pairwise combinations of generics, ownership, nullable types,
  classes, generators, enums/match, and imports (generated, so the matrix stays maintainable).
- **Error-code coverage.** Every diagnostic code the compiler can emit, and every verifier check,
  has at least one test that triggers it. Checkable mechanically by listing the codes in
  `firescript/errors.py` and the verifiers against the test annotations.
- **Metamorphic tests.** Semantics-preserving rewrites must not change output: rename
  identifiers, reorder independent top-level definitions, add redundant parentheses or blocks,
  insert dead code, split expressions into temporaries.
- **Determinism variations.** Extend the existing compile-twice check to vary
  `PYTHONHASHSEED`, the working directory, and path spelling, since the compiler must never depend
  on hash order.
- **Cross-target** (after Linux support): the same source produces the same output on both
  targets.

## 3. Implementation notes

1. Start with what needs no new infrastructure: error-code coverage check, `PYTHONHASHSEED`
   determinism variation, numeric-boundary matrices, and the regex and collection oracles.
2. Then the `fuzz` kind and the corpus-mutation parser fuzzer, with minimization.
3. Then the generated-program backend differential (arithmetic and casts).
4. Then the allocation counter, which unlocks leak detection for the stdlib model tests and later
   the ownership fuzzer.
5. `tests/python/backend/test_asm_encoding.py` currently compares against a MinGW `as` that
   produces COFF; on Linux `as` produces ELF, so its cases fail locally. Reading `.text` from ELF
   as well as COFF would make that test usable on both and is a good first step for the encoder
   fuzzer.
6. When the self-hosted front-end and backend exist (0.11.0 and 0.12.0), the Python and
   firescript compilers become oracles for each other: fuzz both with the same inputs and require
   identical diagnostics, FIR, and bytes.

## 4. Release hooks

Scheduling is in [version_planning.md](version_planning.md): infrastructure and the
no-dependency items alongside cross-target testing in 0.7.0, the ownership fuzzer in 0.8.0,
dispatch/interface/binding generation in 0.9.0, the two-compiler differential in 0.11.0 and
0.12.0, and "no open crashers from a nightly fuzz run" as a 1.0.0 release criterion.
