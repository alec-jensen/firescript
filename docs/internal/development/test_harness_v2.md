# firescript Test Harness v2 — Specification

Status: **APPROVED FOR IMPLEMENTATION** (phases 1–3 now; phases 4+ are designed here but implemented later).

This document specifies a complete redesign of the firescript test infrastructure. It replaces
eight independent entry points with one unified runner, replaces sidecar expectation files with
in-file "magic comment" directives (GCC/DejaGnu-style), reorganizes Python-based tests into the
same category layout as firescript tests, and lays the architectural groundwork for the full
future test strategy: 100% coverage gating, differential testing, fuzzing, A/B optimization
testing, bootstrap byte-match, determinism testing, FIR/FLIR verification, and full
compiler-flag-matrix runs.

The implementer should treat this spec as authoritative. Where a decision was debatable, the
chosen option and its rationale are stated. Sections marked **[FUTURE]** must be *designed for*
now (interfaces, directory slots, seed plumbing, CLI reservations) but not implemented until
their phase.

---

## 1. Current state (what is being replaced)

| Entry point | What it does | Fate |
|---|---|---|
| `tests/run_tests.py` | Orchestrates golden + error + CLI suites, coverage | Replaced by `tests/run.py` |
| `tests/golden_runner.py` | Compile + run `.fire`, compare stdout vs `tests/expected/**/*.out` | Becomes the `run` kind; expectations move in-file |
| `tests/error_runner.py` | Lint invalid `.fire`, compare diagnostics vs `tests/expected_errors/**/*.err` | Becomes the `compile-fail` kind; expectations move in-file |
| `tests/cli_runner.py` | 26 hardcoded Python functions testing `main.py` flags | Migrates to `tests/python/cli/` |
| `tests/asm_encoding_tests.py` | Assembler differential tests vs MinGW `as` + unit cases | Migrates to `tests/python/backend/` |
| `tests/fir_unit_tests.py` | FIR builder/dump/validation unit tests | Migrates to `tests/python/fir/` |
| `tests/fir_snapshot_runner.py` | Hardcoded list of 25 sources → FIR/FLIR dump goldens + determinism | Becomes the `snapshot` kind, opt-in via directive |
| `tests/float128_oracle.py` | binary128 oracle library + `__main__` self-tests | Library moves to `tests/support/`; self-tests migrate to `tests/python/float128/` |

Sidecar/expectation files being **eliminated**:

- `tests/expected/<category>/<name>.out` — golden stdout → in-file `EXPECT` block.
- `tests/expected_errors/<category>/<name>.err` — error signatures → in-file `//~ ERROR` annotations.
- `tests/sources/**/*.args` — argv sidecars (2 exist today) → `//@ args:` directive.
- `tests/diffs/` — failure diffs move under `build/test-results/`.

**One deliberate exception** (see §6.3): FIR/FLIR snapshot goldens stay as external files.
They are large machine-generated IR dumps, not human-authored expectations; inlining hundreds of
lines of IR into a `.fire` test would destroy readability. They move to `tests/snapshots/`.

Known problems the redesign must fix (not just carry over):

1. **Build-path collisions**: today every compile writes `build/<basename>`, so two tests with
   the same basename in different categories, or the same test in two matrix cells, would
   clobber each other. v2 gives every (test, matrix-cell) pair an isolated work directory.
2. **Helper-module detection by filename** (`utils`, `math_utils`, `_provider` suffix) is a
   hidden hardcoded list in `golden_runner.py`. v2 replaces it with an explicit `//@ helper`
   directive.
3. **Python suites not run by default**: `asm_encoding_tests.py`, `fir_unit_tests.py`,
   `fir_snapshot_runner.py`, and the float128 self-tests are not invoked by `run_tests.py` (CI
   runs `run_tests.py` only, so they are effectively untested in CI). In v2, *everything* runs
   under the unified runner by default.
4. **Snapshot case list is hardcoded** in the runner instead of declared by the tests.

---

## 2. Goals and non-goals

Goals:

- **G1** One runner, one command: `python tests/run.py` runs *every* test in the repository.
- **G2** All expectations live inside the test file (magic comments), except IR snapshots.
- **G3** Python tests are first-class, categorized like firescript tests, always run.
- **G4** Deterministic, reproducible randomness: every randomized decision derives from one
  master seed that is always printed and can be passed back with `--seed`.
- **G5** Extensible "test kind" plugin architecture so future kinds (fuzz, differential,
  bootstrap) slot in without touching the core.
- **G6** A matrix engine that can run every test under every combination of compiler flags,
  with quick/full/sampled modes.
- **G7** Zero new *required* dependencies. Python stdlib only, matching the project's
  self-hosted-toolchain ethos. (`coverage` remains an optional extra, as today.)

Non-goals:

- No pytest/unittest adoption. Rationale: the project deliberately has zero external tooling
  (own assembler, own PE writer); a stdlib micro-framework of ~100 lines covers everything the
  current suites need, and the harness needs full control of scheduling, seeding, and
  reporting anyway. The Python-test API is deliberately pytest-*shaped* (plain `test_*`
  functions, assert-based) so a future migration would be mechanical.
- No change to compiler diagnostics format, except the additions listed in §12 (compiler work
  items) which are prerequisites for specific future kinds.
- Windows x86-64 remains the only execution target; the harness must not assume it (skip
  directives exist), but no cross-platform work is in scope.

---

## 3. Architecture overview

### 3.1 Directory layout (target state)

```
tests/
  run.py                      # thin entrypoint: parses argv, calls harness.cli.main()
  harness/                    # the framework (a package; no test content)
    __init__.py
    cli.py                    # argument parsing, profiles, top-level orchestration
    config.py                 # RunConfig dataclass (all knobs, fully typed)
    discovery.py              # walks tests/, produces TestCase objects
    directives.py             # magic-comment parser (shared by .fire and .py)
    expectations.py           # EXPECT block + //~ ERROR parsing, matching, rewriting
    matrix.py                 # flag-matrix axes, cell expansion, sampling
    scheduler.py              # parallel execution (process pool), fail-fast, interrupt
    seeds.py                  # master seed, per-test seed derivation
    workdir.py                # isolated build dirs, artifact retention
    report.py                 # console reporter, JSON reporter, summary, diffs
    coverage_glue.py          # in-process + subprocess coverage (port of run_tests.py logic)
    compilecmd.py             # single place that constructs `main.py` invocations
    pyunit.py                 # micro-framework API imported by tests/python/**
    kinds/
      __init__.py             # kind registry
      base.py                 # Kind ABC: discover(), plan(), execute(), update()
      run.py                  # golden compile+execute tests
      compile_fail.py         # diagnostic-expectation tests
      snapshot.py             # FIR/FLIR snapshot tests
      python_unit.py          # tests/python/** executor
      determinism.py          # [FUTURE, phase 3] byte-match recompiles
      fuzz.py                 # [FUTURE] crash-oracle fuzzing
      differential.py         # [FUTURE] generated-program differential tests
      bootstrap.py            # [FUTURE] stage2/stage3 byte-match
    tools/
      convert_legacy.py       # one-shot migration script (§11); delete after migration
  support/                    # libraries used BY tests (not tests themselves)
    __init__.py
    float128_oracle.py        # moved from tests/float128_oracle.py, unchanged API
  sources/                    # firescript test sources — layout unchanged
    <category>/*.fire
    invalid/<category>/*.fire
  python/                     # Python tests, mirrored category layout
    cli/test_*.py
    backend/test_*.py
    fir/test_*.py
    float128/test_*.py
  snapshots/                  # curated IR goldens (the one sidecar exception)
    <category>/<name>.fir
    <category>/<name>.flir
  TEST_MANIFEST.md
```

Deleted at the end of migration: `golden_runner.py`, `error_runner.py`, `cli_runner.py`,
`asm_encoding_tests.py`, `fir_unit_tests.py`, `fir_snapshot_runner.py`, `run_tests.py`,
`tests/expected/`, `tests/expected_errors/`, `tests/expected_fir/`, `tests/expected_flir/`,
`tests/diffs/`, all `*.args` files, and `tests/float128_oracle.py` (moved).

### 3.2 Core data model

```python
@dataclass(frozen=True)
class TestId:
    kind: str          # "run", "compile-fail", "snapshot", "python", ...
    path: str          # repo-relative posix path of the test file
    name: str          # for python tests: "test_emit_ast"; else file stem
    cell: str          # matrix cell id, "default" outside matrix runs
    # str(TestId) -> "run:tests/sources/arrays/arrays_iteration.fire[default]"
    #                "python:tests/python/cli/test_emit.py::test_emit_ast"

@dataclass
class TestCase:
    id: TestId
    directives: Directives      # parsed magic comments (§5)
    # kind-specific payload attached by the Kind during discovery

@dataclass
class TestResult:
    id: TestId
    status: Status              # PASS | FAIL | ERROR | SKIP | UPDATED | NEW
    duration_s: float
    message: str = ""           # one-line failure summary
    details: str = ""           # diff / traceback / captured output
    artifacts: list[str] = ...  # paths under build/test-results/ (diffs, dumps)
    seed: str | None = None     # per-test seed if any randomness was used
```

`Status` semantics match today's runners: `ERROR` = infrastructure/timeout/crash,
`FAIL` = expectation mismatch, `SKIP` = directive- or requirement-driven skip (reported,
never silently dropped), `UPDATED`/`NEW` only in `--update` mode.

### 3.3 Kind plugin contract

Each kind is a module in `harness/kinds/` registering itself in the kind registry:

```python
class Kind(ABC):
    name: str
    def discover(self, config: RunConfig) -> list[TestCase]: ...
    def execute(self, case: TestCase, ctx: ExecContext) -> TestResult: ...
    def update(self, case: TestCase, ctx: ExecContext) -> TestResult: ...
    # update() = "bless" mode: rewrite in-file expectations / snapshot files.
```

`ExecContext` provides: the isolated work dir, the per-test seed, the matrix cell's compiler
flags, `compilecmd` helpers, timeouts, and a `log()` for verbose mode. Kinds must never write
outside their work dir (except `update()` rewriting the test's own file / snapshot golden).

Adding a future kind = adding one module + registering it. The core (discovery driver,
scheduler, reporter, CLI) must not need edits. **This is the load-bearing design property —
review any implementation PR against it.**

### 3.4 Execution pipeline

1. **CLI** parses args into `RunConfig` (profile defaults → explicit flags override).
2. **Seed manager** fixes the master seed and prints it (always, first line of output;
   see §8).
3. **Discovery**: each selected kind discovers its cases; selectors (§9.2) filter them.
4. **Matrix expansion**: each case expands into one `TestCase` per selected matrix cell (§7).
5. **Scheduler** runs cases on a process pool (`--jobs`, default = CPU count).
   - Compile+execute kinds are subprocess-heavy → processes avoid today's GIL/threading
     hazards (`error_runner` currently needs a lint lock; `python_unit` executes in worker
     processes so no lock is needed).
   - `--fail-fast` cancels pending work after the first FAIL/ERROR.
   - KeyboardInterrupt → cancel, exit 130 (preserve today's behavior).
6. **Reporter** streams per-case lines (same `[CASE  ]`/`[PASS  ]` tag style and colors as
   today, `NO_COLOR`/non-tty aware), then prints the unified summary table per kind and in
   total, then coverage (§10), then the seed again (last line, so it's visible after long
   output).
7. Exit code: 0 iff no FAIL/ERROR (SKIP does not fail; UPDATED/NEW do not fail).

### 3.5 Work directories and artifacts

Every (case, cell) gets `build/test-work/<kind>/<cell>/<category>/<stem>/` as its compile
output dir (passed to the compiler via `-o`; the compiler already supports explicit output
paths). Failure artifacts (diffs, actual-output dumps, IR dumps, fuzz reproducers) are written
to `build/test-results/<same-subpath>/`. Both trees are wiped at the start of a run unless
`--keep-artifacts`. Nothing is ever written into `tests/` at run time except by `--update`.

---

## 4. Test kinds (phase 1–2 scope)

### 4.1 `run` (golden) — replaces golden_runner

Discovery: every `tests/sources/**/*.fire` **not** under `sources/invalid/` and not marked
`//@ helper` and not `//@ mode: compile-fail` (a valid-tree file may opt into compile-fail? —
no: mode conflicts with location are a discovery **error**, see §5.6).

Execution per case:

1. Compile with `python firescript/main.py <src> -o <workdir>/<stem>.exe` plus the matrix
   cell's flags plus `//@ compile-flags:` extras. Timeout: `//@ compile-timeout:` or config
   default (120 s). Nonzero exit / timeout → ERROR with captured compiler output.
2. PE import check: binary must import only `KERNEL32.dll` (keep `pe_inspect` check verbatim).
3. Run the binary with `//@ args:` argv and `//@ stdin:`/`//@ stdin-file:` input, timeout
   `//@ timeout:` or default (20 s). Exit code must equal `//@ exit-code:` (default 0).
4. Normalize stdout exactly as today (CRLF→LF, strip trailing whitespace per line, single
   trailing newline) and compare against the in-file `EXPECT` block (§5.3).
5. Mismatch → FAIL with unified diff inline (as today) + diff artifact. Missing EXPECT block →
   FAIL ("missing expectation; run with --update").

`update()`: rewrite (or append) the EXPECT block in the source file with actual output.
A file whose output differs across matrix cells fails in full-matrix mode by design — that is
the A/B optimization guarantee (§7.4). `--update` only ever runs in the default cell.

### 4.2 `compile-fail` — replaces error_runner

Discovery: every `tests/sources/invalid/**/*.fire` not marked `//@ helper`.

Execution: run the front-end **in-process is forbidden** — v2 invokes
`main.py --check --message-format json <src>` in a subprocess and parses the JSON diagnostic
events. Rationale: (a) removes the `lint_text` global-logging lock hack, (b) exercises the
real CLI path users hit, (c) processes parallelize cleanly, (d) coverage still works via
`COVERAGE_PROCESS_START` (§10).

Expected diagnostics come from `//~` annotations (§5.4). Matching rule (unchanged semantics
from today): the multiset of `(code, line, column?)` signatures must exactly equal the actual
diagnostics; column is checked only when the annotation specifies one. Zero diagnostics →
FAIL "expected compilation to fail but it succeeded". Extra or missing diagnostics → FAIL
listing both sides.

`update()`: rewrite the file's `//~` annotations to match actual diagnostics: keep annotations
that still match, drop stale ones, and insert new ones at the end of the offending source line.
The updater must preserve the file byte-for-byte outside the annotations it touches. (This is
the trickiest updater; implement it with line-based edits, and its own Python tests in
`tests/python/harness/`.)

### 4.3 `snapshot` — replaces fir_snapshot_runner

Discovery: every `tests/sources/**/*.fire` carrying `//@ snapshot: fir` and/or
`//@ snapshot: flir` (comma list allowed: `//@ snapshot: fir, flir`). The 25 files in the
current hardcoded `SNAPSHOT_CASES` list get this directive during migration; the hardcoded
list dies.

Execution: compile with `--emit-fir`/`--emit-flir` into the work dir, **twice**; the two dumps
must be byte-identical (IR-dump determinism, preserved from today); then compare against
`tests/snapshots/<category>/<stem>.fir` / `.flir`. Note the golden tree is category-mirrored
(the current flat basename-keyed `expected_fir/` layout is replaced).

`update()` regenerates the snapshot files.

### 4.4 `python` — replaces cli_runner, asm_encoding_tests, fir_unit_tests, float128 self-tests

Discovery: every `tests/python/**/test_*.py`. Each module is imported in a worker process;
every top-level callable named `test_*` is one test case (id
`python:tests/python/cli/test_emit.py::test_emit_ast`).

The micro-framework (`harness/pyunit.py`) provides — and this is the *whole* API surface,
keep it small:

```python
from tests.harness import pyunit as t

t.require(cond, msg)                 # rich assert (today's _require)
t.require_eq(a, b, msg="")           # prints both values on failure
t.tmpdir()                           # context manager, auto-cleaned temp dir
t.run_compiler(args, cwd=None, timeout=60)  # runs main.py, returns CompletedProcess
t.repo_root, t.sources_dir           # canonical paths
t.subtest(label)                     # context manager; failures report "test_x[label]"
t.skip(reason)                       # raises SkipTest
t.params(iterable)                   # decorator: expands one test_ fn into N cases
                                     #   @t.params(["a", "b"]) → test_x[a], test_x[b]
```

Plain `assert` also works (AssertionError → FAIL with traceback). Module-level directives use
`#@` comments (§5.5) — e.g. `tests/python/backend/test_asm_encoding.py` carries
`#@ requires: mingw-as` on the differential half (function-level `t.skip()` when `as` is
missing is also fine and is what the migration should use, matching current behavior: unit
cases always run, differential cases skip without `as`).

Migration mapping:

| Old | New |
|---|---|
| `cli_runner.py` 26 cases | `tests/python/cli/test_check.py`, `test_emit.py`, `test_dir_batch.py`, `test_output.py`, `test_diagnostics.py`, `test_imports.py` (split by area; one behavior per function, as with `.fire` tests) |
| `asm_encoding_tests.py` | `tests/python/backend/test_asm_encoding.py` (unit cases + `as`-differential cases) |
| `fir_unit_tests.py` | `tests/python/fir/test_builder.py`, `test_dump.py`, `test_validation.py` |
| `float128_oracle.py __main__` | `tests/python/float128/test_oracle_units.py`, `test_oracle_vectors.py`; oracle imports from `tests.support.float128_oracle` |
| (new) | `tests/python/harness/test_directives.py`, `test_expectations.py`, `test_matrix.py`, `test_seeds.py` — **the harness tests itself**; required in phase 1 |

---

## 5. The directive language ("magic comments")

### 5.1 Design rules

- Directive prefix in `.fire` files: `//@` (header directives) and `//~` (diagnostic
  expectations). In `.py` files: `#@`. Chosen over GCC's `{ dg-... }` for greppability and
  because Rust's `//@`/`//~` split (header config vs. line-anchored expectations) is the
  cleanest existing design in this space.
- Header directives must appear in the **leading comment block**: the contiguous run of
  comments/blank lines at the very top of the file. A `//@` found after the first code token
  is a **discovery error** (fail loudly; silent misplacement is how directives rot). `//~` is
  the opposite: only valid *after* code starts, anchored to source lines.
- Unknown directive keys are discovery errors, not warnings.
- Syntax: `//@ key: value` — key is `[a-z-]+`, exactly one space after `//@`, value runs to
  end of line, trimmed. Repeatable keys are explicitly marked below; repeating a
  non-repeatable key is an error.

### 5.2 Header directives (`.fire`)

| Directive | Meaning | Default |
|---|---|---|
| `//@ mode: run \| compile-fail` | Explicit kind override. Rarely needed: location decides (valid tree → run, `invalid/` → compile-fail). | inferred |
| `//@ helper` | File is imported by other tests; never a standalone test case. Replaces the `utils`/`_provider` filename hacks (during migration, add this to every current helper and delete the hardcoded lists). | — |
| `//@ args: <tokens>` | argv for the compiled binary; POSIX-`shlex`-split, so quoting gives args with spaces. Repeatable; lines concatenate in order. | none |
| `//@ arg: <verbatim>` | One argv token, taken verbatim to end of line (for args where quoting is awkward). Repeatable; interleaves with `args:` in file order. | none |
| `//@ stdin: <text>` | One line of stdin. Repeatable; lines join with `\n`, trailing newline appended. | none |
| `//@ stdin-file: <path>` | stdin from a file, path relative to the test file. (Not a sidecar *expectation* — it's test *input* data, e.g. `hackathon8_input.txt`; allowed.) Mutually exclusive with `stdin:`. | none |
| `//@ exit-code: <int>` | Expected binary exit code. | 0 |
| `//@ timeout: <seconds>` | Binary run timeout (float). | config (20) |
| `//@ compile-timeout: <seconds>` | Compile timeout. | config (120) |
| `//@ compile-flags: <flags>` | Extra flags appended to the compiler invocation (shlex-split). | none |
| `//@ snapshot: fir[, flir]` | Opt into the snapshot kind (in addition to run kind). | off |
| `//@ no-matrix` | Run only in the default matrix cell (§7.3). | matrix on |
| `//@ no-determinism` | Exclude from determinism sampling (§7.5 / determinism kind). Requires a reason: `//@ no-determinism: <why>`. | included |
| `//@ requires: <feature>` | Skip unless the named capability is available. Initial registry: `mingw-as`. Repeatable. | — |
| `//@ skip: <reason>` | Unconditional skip with mandatory reason (for temporarily disabled tests; shows as SKIP, greppable). | — |

### 5.3 Expected output — the `EXPECT` block (`run` kind)

Canonical form, **must be the last non-blank content of the file**:

```fire
import @firescript/std.io.println;

int32 x = 41 + 1;
println(x as string);
println("done");

/* EXPECT
42
done
*/
```

Rules:

- Opening line: exactly `/* EXPECT` (nothing after on the line). Closing: a line that is
  exactly `*/`. Everything between, verbatim, is the expectation; comparison applies the same
  normalization as the runner applies to actual output (§4.1 step 4). An empty block means
  "expect no output".
- Exactly one EXPECT block per file; two is a discovery error; zero is a FAIL at run time
  (with a hint to use `--update`).
- **Escape hatch** — if any expected line is `*/` or starts with `*/` (would terminate the
  block), the line-comment form is used instead, for the *whole* expectation:

  ```fire
  // EXPECT: line one
  // EXPECT: line two
  ```

  Same placement rule (trailing contiguous block at end of file). A file must use one form,
  never both. `--update` emits the block form unless the content forces line form.
- The updater replaces the existing block in place (or appends one) and touches nothing else
  in the file.

### 5.4 Diagnostic expectations — `//~` (`compile-fail` kind)

Anchored to source lines, Rust-UI style:

```fire
int32 x = "hello";        //~ ERROR FS-TYPE-0001
string s = y;             //~ ERROR FS-NAME-0002 @7
                          //~^ ERROR FS-TYPE-0004
```

Grammar: `//~ ('^'*) SEVERITY CODE ('@' column)? ('"' message-substring '"')?`

- Line anchor: the annotation's own line, minus one per `^` (so `//~^` = previous line;
  `//~^^` = two up). This lets multiple expectations stack under one offending line, and —
  the key win over `.err` sidecars — **line numbers self-maintain when the file is edited**.
- `SEVERITY`: `ERROR` now; reserve `WARNING` for when the compiler grows warnings.
- `CODE`: the structured code (`FS-TYPE-0001`). Required (today's signatures are code-based).
- `@<col>`: optional column assertion (today's `.err` files assert columns; the migration
  converter carries columns over, but hand-written new tests may omit them).
- Optional quoted substring: must appear in the diagnostic message. Optional and
  order-independent — signature matching (multiset over code/line/col) stays the primary
  contract so message wording can change freely, exactly as today.
- A compile-fail file with zero `//~` annotations is a discovery error (except in `--update`,
  which inserts them).

### 5.5 Python directives (`#@`)

Same header-block placement rule, keys limited to: `#@ requires:`, `#@ skip:`,
`#@ timeout:` (per-function default for the module), `#@ no-matrix` (reserved — python tests
are matrix-exempt by default; see §7.3). Everything else (params, subtests, skips) is done in
code via `pyunit`, where Python is more expressive than comments.

### 5.6 Validation

`discovery.py` + `directives.py` enforce every "is an error" above at discovery time, before
anything runs, and report them as ERROR results tied to the file. A malformed test must never
be silently skipped — that is how coverage quietly rots.

---

## 6. Selection, CLI, and output

### 6.1 Command

```
python tests/run.py [SELECTOR ...] [options]
```

No selectors → run everything (all kinds, default matrix cell, determinism sampling per
profile). CI (`windows_x86_64_test.yml`) switches to exactly `python tests/run.py --profile ci`.

### 6.2 Selectors

Positional selectors, OR-combined; each may be:

- a path: `tests/sources/arrays/arrays_iteration_for_in.fire` (works for `.fire` and `.py`)
- a directory / category: `tests/sources/arrays/`, `arrays/` (category shorthand searches
  both `sources/<cat>` and `python/<cat>`)
- a kind filter: `kind:python`, `kind:run`, `kind:compile-fail`, `kind:snapshot`
- a glob on test ids: `name:generics_*`, `tests/python/cli/test_emit.py::test_emit_ast`

`--list` prints matching test ids without running (implementers: this is also the debugging
tool for discovery).

### 6.3 Options

```
--update                 bless mode: rewrite in-file expectations / snapshots (never runs
                         matrix cells other than default; incompatible with --seed-dependent
                         kinds)
--jobs N                 parallelism (default: cpu count)
--fail-fast              stop scheduling after first FAIL/ERROR
--verbose                per-case detail (BUILD/RUN lines, failure detail inline)
--timeout S / --compile-timeout S      global defaults (per-test directives win)
--matrix quick|full|sample=K           see §7.3         [default: quick]
--determinism off|sample|all           see §7.5         [default: sample]
--seed HEX               fix the master seed (default: random, always printed)
--coverage / --no-coverage             see §10
--coverage-fail-under PCT              gate: nonzero exit if total coverage below PCT
--uncovered              coverage report shows only uncovered lines (as today)
--json PATH              write machine-readable results (schema in §6.4)
--keep-artifacts         don't wipe build/test-work + build/test-results first
--profile local|ci|full  bundles: local = quick matrix, sample determinism, coverage if
                         installed; ci = quick matrix, ALL determinism, coverage gate ready;
                         full = full matrix, all determinism (the slow pre-release run)
--list                   print selected test ids and exit
```

### 6.4 JSON results (`--json`)

One object: `{schema: 1, seed, profile, matrix, started, duration_s, counts: {pass, fail,
error, skip, updated, new}, coverage_pct?, results: [TestResult...]}` with TestResult fields
from §3.2. CI consumes this later; keep the schema versioned.

### 6.5 Console output

Preserve the existing visual language (it's good): `[CASE  ]` cyan, `[PASS  ]` green,
`[FAIL  ]` red, `[SKIP  ]` yellow with reason, `[UPDATE]`/`[NEW   ]` yellow; per-kind summary
lines, then the totals block, then coverage, then `Seed: 0x…` as the final line. Inline
unified diffs on golden failures, expected/actual signature lists on compile-fail failures.

---

## 7. The matrix engine

### 7.1 Concept

A **matrix axis** is a named set of compiler flag variants. A **cell** is one selection from
every axis; the cell id is the joined variant names (`default`, or e.g. `O2+debug`). Every
`run`/`compile-fail`/`snapshot` case is expanded per selected cell; expectations are **cell
invariant** — the same EXPECT block / `//~` set / snapshot must hold in every cell. There are
deliberately no per-cell expectations: if optimization changes observable behavior, that is a
compiler bug and the test should fail.

### 7.2 Axis registry

Axes are declared in `matrix.py`:

```python
AXES = [
    Axis("opt", variants={"O0": [], ...}),      # populated when -O lands; today: single variant
]
```

Today the compiler has no optimization levels, so the initial registry has exactly one cell
(`default`) and the engine is trivially exercised. The registry is the *only* place to touch
when `-O1`/`-O2` land — this spec requires the engine, expansion, cell-suffixed test ids,
per-cell work dirs, and reporting to be fully implemented and tested (via a fake axis in the
harness's own Python tests) in phase 2, so that adding real axes later is a one-line change.
Debug logging (`-d`) is *not* an axis: it changes logging, not codegen, and would pollute
matrix time; it gets one dedicated python CLI test instead (already exists as
`case_debug_mode`).

### 7.3 Modes

- `quick` (default, local): default cell only.
- `full`: full cartesian product. The A/B and pre-release mode.
- `sample=K`: default cell always, plus K additional cells chosen per-test with the test's
  derived seed (so the sampled subset differs per test but is reproducible from the master
  seed). Middle ground for CI once the product gets large.

Python tests are matrix-exempt (they construct their own compiler invocations). `//@ no-matrix`
exempts a `.fire` test (e.g., one asserting debug-only output), always with the default cell.

### 7.4 A/B optimization testing **[FUTURE, lands with the first real axis]**

Falls out of the above for free: `--matrix full` runs every golden test at every optimization
level and demands identical output. Additionally, the determinism kind (§7.5) at `all` +
`full` matrix asserts per-cell binary stability. No separate kind is needed; document this in
TEST_MANIFEST when the opt axis lands.

### 7.5 Determinism testing (phase 3)

Implemented in `kinds/determinism.py`, but driven from the `run` kind's results to avoid
recompiling from scratch unnecessarily:

- Mode `sample` (local default): select 5% of the run-kind cases (minimum 3), chosen with the
  master seed (`seeds.pick(master, "determinism", population)`); recompile each selected case
  in a *fresh* work dir and byte-compare the two binaries (`.exe` files, whole-file
  comparison).
- Mode `all` (CI default): every run-kind case.
- Mismatch → FAIL with the first differing offset and both file hashes; artifacts: both
  binaries retained under `build/test-results/`.
- The console line for the kind header prints the sample: e.g.
  `[DETERM] sampling 12/236 cases (seed 0x9f3a…)` — the seed makes the sample reproducible.
- Prerequisite verified: the PE writer already zeroes `TimeDateStamp` (COFF header packs 0),
  so binaries are timestamp-free today. If a future compiler change introduces any
  nondeterminism (hash-ordered dicts in codegen, absolute paths embedded in binaries), this
  kind is the tripwire. `//@ no-determinism: <reason>` is the escape hatch, intended to be
  empty in a healthy tree.

---

## 8. Seeds and reproducibility

`seeds.py` is the single source of randomness for the whole harness:

- Master seed: `--seed` value, else `secrets.token_hex(8)`. Printed as the **first** and
  **last** line of every run: `Seed: 0x1c9e4d2ab0f37e51` (last line so it survives scrollback
  after a huge log — the user requirement "output seed in console" applies to *every*
  randomized subsystem and is satisfied centrally here).
- Per-purpose derivation: `derive(master, *labels) -> int` =
  `sha256(master ‖ "\0".join(labels))` truncated to 64 bits. Labels are stable strings, e.g.
  `derive(master, "determinism", "sample")`, `derive(master, "fuzz", test_path, str(i))`.
- Every `TestResult` for a case that consumed randomness records its derived seed, and every
  future kind (fuzz, differential) must print a per-case reproduction command on failure:
  `Reproduce: python tests/run.py kind:fuzz --seed 0x… name:<case>`.
- **Rule for implementers**: no `random.random()` / `random.seed()` global state anywhere in
  the harness; always `random.Random(derive(...))` instances.

---

## 9. Coverage (goal: 100%)

Port `run_tests.py`'s coverage integration into `coverage_glue.py` unchanged in approach:

- Optional dependency; absent → note printed, everything else works.
- Subprocess coverage via `COVERAGE_PROCESS_START` + pinned `COVERAGE_FILE` at repo root,
  combine at end (this already handles the compiler-subprocess model; compile-fail moving to
  subprocesses in v2 *increases* measured fidelity vs. today's in-process lint).
- Report includes `firescript/*`, omits `firescript/lsp/*` as today.
- Default: on for unfiltered runs when installed; off automatically when selectors are given
  (a filtered run's coverage number is noise); `--coverage`/`--no-coverage` override.
- `--coverage-fail-under 100` is how CI eventually enforces the 100% goal — wire the flag now,
  turn it on in CI when the number is real. The **feature-coverage** half of the 100% goal
  (every language feature has a test) remains a TEST_MANIFEST/process concern, not a harness
  concern.

---

## 10. Future kinds **[FUTURE — design contracts only; do not implement in phases 1–3]**

These sections exist so phase-1 architecture leaves the right seams. Each future kind must be
implementable as *one new module* in `harness/kinds/` plus, where noted, a compiler work item.

### 10.1 FIR/FLIR verification (compiler work item + one harness line)

A structural verifier inside the compiler (`firescript/fir/verify.py`, `flir` equivalent):
after FIR construction and after each lowering pass, verify strict invariants (every value
defined before use, blocks end in exactly one terminator, types on both sides of stores agree,
drop/move rules, etc. — the rule list belongs in `fir_spec.md`/`flir_spec.md`, not here).
Exposed as `--verify-ir` on `main.py`; **the harness passes `--verify-ir` on every test
compile once the flag exists** (one line in `compilecmd.py`, reserved now with a TODO). A
verifier failure is an ERROR (compiler bug), never a test FAIL. This turns every existing
golden test into an IR-invariant test for free.

### 10.2 Fuzzing (`kinds/fuzz.py`)

- Oracle: the compiler, on arbitrary input, must terminate within timeout and either succeed
  or emit structured diagnostics with exit 1. Any traceback, nonzero-but-undiagnosed exit,
  hang, or assembler/PE-writer crash on accepted input = FAIL.
- Three generators, selected by weight, all seeded per-case (§8): byte-level mutation of
  existing test sources; token-level mutation (splice/duplicate/delete lexed tokens — reuses
  `firescript/lexer.py`); grammar-based generation (shared with §10.3's generator).
- Invocation: `python tests/run.py kind:fuzz --fuzz-count 500 [--seed …]`; not part of the
  default run or CI profile (a small smoke count may be added to `--profile full` later).
- On failure: reproducer source saved to `build/test-results/fuzz/…`, reproduction command
  printed (§8). Triaged crashers get *manually* minimized and committed as normal
  compile-fail or known-issue tests — the corpus is not auto-committed.

### 10.3 Differential testing (`kinds/differential.py` + `tests/harness/generators/`)

- A seeded generator produces random programs in a **defined firescript subset** (integers,
  strings, arrays, control flow, functions — the subset grows over time and is versioned in
  the generator), sized by `--diff-size`, count by `--diff-count`. "Very large" programs are
  a size preset, not a different mode.
- For each program the generator *simultaneously* emits a semantically identical Python
  program (twin emission from one internal program AST — do **not** write a
  firescript-to-Python transpiler that parses firescript; the generator owns one IR and two
  printers, which sidesteps trusting the system under test). Both are run; stdout must match
  after golden normalization. Integer overflow/wrapping semantics must be modeled explicitly
  in the Python twin (masking to the firescript type's width) — this is the main correctness
  trap; the generator's twin-emitter needs its own python-kind unit tests.
- Failures persist both programs + both outputs as artifacts and print the reproduction
  command with seed.

### 10.4 Bootstrap byte-match (`kinds/bootstrap.py`)

Gated on the self-hosted compiler existing. Contract: stage1 = current (Python) compiler
builds the firescript-implemented compiler → stage2 binary; stage2 builds the same source →
stage3 binary; stage2 and stage3 must be byte-identical. One test case, `--profile full` and
release CI only. The kind module is a stub raising SKIP("self-hosted compiler not yet
buildable") until then — write the stub in phase 3 so the seam is proven.

---

## 11. Migration plan

Phase boundaries are hard: each phase ends with `python tests/run.py` green and CI green.

**Phase 1 — harness core + directive tests replace golden/error runners.**
1. Build `harness/` core: config, discovery, directives, expectations, seeds, workdir,
   scheduler, report, compilecmd, kinds `run` + `compile-fail` + `python`, `pyunit`.
2. Write the harness's own tests under `tests/python/harness/` (directive parser, EXPECT
   parser/updater, `//~` parser/updater, seed derivation, selector matching). The harness
   must not ship untested — it is about to become the arbiter of every other test.
3. Write and run `harness/tools/convert_legacy.py`:
   - For each `tests/expected/<cat>/<name>.out` → append EXPECT block to the paired source;
     delete the `.out`.
   - For each `.args` → insert `//@ arg:` lines; delete the sidecar.
   - For each `tests/expected_errors/<cat>/<name>.err` → parse signatures, insert
     `//~ ERROR CODE @col` at the recorded lines (using `//~^`-stacking when a line already
     has a trailing comment); delete the `.err`.
   - Add `//@ helper` to `utils.fire`, `math_utils.fire`, `string_utils.fire`, and every
     `*_provider.fire`; delete the hardcoded basename lists.
   - The converter must verify: full run before == full run after (same pass/fail per test).
4. Migrate `cli_runner.py` → `tests/python/cli/` per the §4.4 table.
5. Point CI at `python tests/run.py --profile ci`. Delete `golden_runner.py`,
   `error_runner.py`, `cli_runner.py`, `run_tests.py`, `tests/expected/`,
   `tests/expected_errors/`, `tests/diffs/`, the `.args` files.
6. Update docs (§13).

**Phase 2 — remaining suites + snapshot kind + matrix engine.**
1. Migrate `asm_encoding_tests.py`, `fir_unit_tests.py`, float128 self-tests per §4.4; move
   `float128_oracle.py` → `tests/support/`; fix the path reference in
   `docs/internal/development/float128.md`.
2. Implement `snapshot` kind; add `//@ snapshot:` directives to the 25 current cases; move
   goldens `expected_fir/`+`expected_flir/` → `tests/snapshots/<category>/` (now
   category-mirrored); delete `fir_snapshot_runner.py`.
3. Implement the matrix engine end-to-end with a fake axis exercised only by harness tests
   (§7.2), plus `--matrix` CLI.

**Phase 3 — determinism kind + future seams.**
1. Implement `kinds/determinism.py` per §7.5 (sample default locally, `all` in the CI
   profile).
2. Add the `--verify-ir` pass-through TODO in `compilecmd.py`, the `bootstrap` stub kind, and
   `--json` output if not already done.

**Phase 4+ [FUTURE]** — fuzz kind, differential kind + generator, FIR/FLIR verifier (compiler
side), real matrix axes when `-O` lands, coverage gate flip to `--coverage-fail-under=100`.

Nothing in phases 1–3 changes user-facing compiler behavior → **no changelog entries** per
project changelog rules. (If the `compile-fail` migration to `--message-format json` exposes
missing JSON diagnostics for any error path, fixing the compiler's JSON output *is*
user-facing and needs a changelog entry.)

---

## 12. Compiler work items implied by this spec

Tracked separately from the harness; the harness must not block on them beyond what's noted:

1. **None for phase 1** — `--check`, `--message-format json`, `-o`, `--emit-fir/flir` all
   exist and suffice. Verify during phase 1 that JSON diagnostics carry `code`, `line`,
   `column` for every diagnostic the error tests exercise; fix gaps (changelog-worthy).
2. `--verify-ir` flag + FIR/FLIR structural verifiers (**[FUTURE]**, enables §10.1).
3. Optimization flags (`-O…`) whenever the optimizer lands → register the matrix axis (§7.2).
4. Guard against nondeterminism regressions (the determinism kind is the tripwire; PE
   timestamp already zeroed).

---

## 13. Documentation updates required

- **`CLAUDE.md`**: replace the *Running Tests* and *Adding Tests* sections — commands become
  `python tests/run.py [selector]`, `--update`; adding a golden test = write the `.fire` file,
  run `--update`, review the EXPECT block it wrote *in the file*; adding an error test =
  write `//~ ERROR` annotations (or `--update`); Python tests go in `tests/python/<category>/
  test_*.py` and always run. Remove all references to `golden_runner.py`/`error_runner.py`
  and golden/sidecar file paths.
- **`tests/TEST_MANIFEST.md`**: rewrite the mechanics sections (organization, running,
  adding, directive reference — §5 condensed); keep the per-category test inventory.
- **`docs/internal/development/float128.md`**: oracle path change.
- This spec stays as the architecture reference; keep it in sync as phases land.

---

## 14. Decisions log (chosen vs. rejected)

| Decision | Chosen | Rejected & why |
|---|---|---|
| Test framework for python tests | stdlib micro-framework (`pyunit`) | pytest: external dep against project ethos; unittest: verbose, poor parametrization; both cede scheduling/seeding/reporting control the unified harness needs |
| Expectation placement | in-file EXPECT block + `//~` annotations | sidecars: user requirement to eliminate; separate `.expected` section files: still sidecars |
| EXPECT syntax | `/* EXPECT … */` block, `// EXPECT:` line-form fallback | FileCheck `CHECK:` patterns: substring/regex matching is weaker than exact-output golden semantics we already rely on |
| Error annotation syntax | Rust-style `//~ ERROR CODE [@col]` line-anchored | GCC `{ dg-error }`: brace syntax collides visually with firescript blocks; absolute line/col files: don't self-maintain under edits |
| compile-fail execution | subprocess `--check --message-format json` | in-process `lint_text`: needs a global lock, hides CLI bugs, single-process coverage only |
| Parallelism | process pool | thread pool (today): GIL contention, needs lint lock, shared-cwd hazards |
| IR snapshot goldens | external files in `tests/snapshots/` (sole exception) | inline: hundreds of lines of machine-generated IR inside test sources harms readability and churn |
| Matrix expectations | cell-invariant (one EXPECT for all cells) | per-cell goldens: legitimizes behavior differences across opt levels, which are compiler bugs |
| Helper detection | `//@ helper` directive | filename conventions: hidden, hardcoded, already caused special-case code |
