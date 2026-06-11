# Build Prompt: Migrate firescript to the FIR Pipeline (No C Backend)

> This is a self-contained build prompt. Hand it to a developer or coding agent starting cold.
> It encodes all decisions already made; do not re-litigate them. Read the referenced design
> docs before writing code.

---

## Mission

Replace firescript's current AST → C codegen with the FIR + FLIR pipeline described in
`docs/internal/development/FIR_impl_plan.md` (and its linked pages: `FIR_overview.md`,
`FIR_fir_spec.md`, `FIR_flir_spec.md`, `FIR_roadmap_and_migration.md`,
`fir_developer_reference.md`), ending in a compiler that emits **native Windows x64
executables with no C anywhere**: no generated C source, no C compiler, no C runtime,
no libc/ucrt linkage.

End-state pipeline:

```
Source → Lexer/Parser → Import Resolution → Preprocessing → Semantic Analysis
       → AST→FIR → (optimization passes: later, out of scope)
       → FIR→FLIR (monomorphize, lower classes/ownership/generators)
       → FLIR→x86-64 assembly (GAS syntax)
       → MinGW `as` + `ld` → freestanding PE .exe importing only kernel32.dll
```

The compiler itself remains written in Python (`firescript/`). Bootstrapping/self-hosting is
explicitly **out of scope** — this resolves the TODO in `FIR_impl_plan.md`: FIR lands first,
so any future bootstrap is written against FIR/FLIR.

## Locked Decisions

These were decided by the project owner; treat them as requirements:

1. **Final backend = direct x86-64 assembly** (GAS syntax), assembled and linked with MinGW
   binutils (`as`, `ld`). No C compiler is invoked at any point in the final pipeline.
2. **An interim FLIR→C backend IS allowed during migration** for differential testing, and
   **must be deleted** at the end along with the old AST→C codegen.
3. **Platform scope: Windows x64 only** for completion. Structure the FLIR→asm backend so a
   Linux x64 target can be added later (isolate calling convention, OS interface, and object
   emission behind clear seams), but do not implement it now.
4. **Binaries are freestanding**: import only `kernel32.dll`. No ucrtbase/msvcrt. Heap via
   `HeapAlloc`/`GetProcessHeap`, I/O via `ReadFile`/`WriteFile`/`CreateFileA`, exit via
   `ExitProcess`.
5. **Runtime is rewritten in firescript** (`firescript/std/` + internal runtime modules),
   bottoming out in compiler intrinsics that lower to FLIR ops / kernel32 extern calls. The
   C files `firescript/runtime/runtime.c`, `runtime.h`, `conversions.h` are deleted at the end.
6. **Relaxed goldens for float formatting**: float-to-string no longer goes through `printf`
   `%g`/`%f`, so golden files in `tests/expected/` MAY be regenerated where (and only where)
   float text formatting differs. Each such regeneration must be reviewed and the behavior
   change documented in `docs/changelog.md` under `## Currently in Development`.
7. **float128 becomes an alias of float64** for now (the current implementation is MinGW
   80-bit `long double` anyway). Document as an `[IN DEVELOPMENT]` limitation + changelog
   entry. True binary128 softfloat is a future project.
8. **Optimization passes (constant folding, DCE, CSE) are follow-up work**, not part of this
   migration. Completion = correctness parity. The resulting binaries being slower than the
   old `gcc -O3` output is accepted.
9. **Front-end (lexer, parser, imports, preprocessor, semantic analyzer, LSP) is untouched**
   except where AST→FIR needs extra annotations preserved. All diagnostics and
   `tests/error_runner.py` expectations must remain byte-identical.

## Ground Rules (from CLAUDE.md — apply throughout)

- Project name is **firescript**, lowercase.
- Never edit a test to force it to pass; fix the compiler. Golden regeneration is allowed
  only under decision 6 (float formatting) and must be reviewed diff-by-diff.
- Every bug fix gets a regression test. Every phase that adds user-visible behavior updates
  `docs/changelog.md` (`## Currently in Development`) and doc status markers.
- New directives/intrinsics are internal-only: document them in `docs/internal/directives.md`,
  never use them in user-facing examples.
- Keep `CLAUDE.md`'s feature status table accurate as features move.
- Commit at each phase gate at minimum; keep the main branch green (old pipeline remains the
  default until Phase 7 cutover).

## Current State Inventory (verify before starting)

- Old codegen: `firescript/codegen/` (`generator.py`, `statements.py`, `classes.py`,
  `generics.py`, `declarations.py`, `base.py`) — AST → C strings.
- C runtime: `firescript/runtime/runtime.c|.h`, `conversions.h`. Note: the GMP/MPFR bigint &
  decimal functions in `runtime.c` are **dead** — nothing in `codegen/` references them
  (verified by grep). `firescript_print_long_double`/`firescript_format_long_double` use MPFR
  and are live only for float128 printing.
- Driver: `firescript/main.py` — detects gcc/clang via `detect_c_compiler()` / `--cc`, invokes
  it with `-O3`, links `runtime.c`.
- Intrinsic surface the runtime rewrite must preserve (see `runtime.h` and
  `docs/internal/directives.md` / `docs/internal/syscalls.md`): refcounted strings, string
  helpers (`str_length`, `str_char_at`, `str_index_of`, `str_slice`), numeric→string
  conversions, `print`/`println` paths, process args (`process_argc`, `process_argv_at`),
  `syscall_open/read/write/close/remove/rename/move` returning `SyscallResult`.
- Tests: `tests/golden_runner.py` (valid programs vs `tests/expected/*.out`),
  `tests/error_runner.py` (diagnostics), `tests/TEST_MANIFEST.md`.
- Feature surface that FIR must cover = every `[IMPLEMENTED]` row in `CLAUDE.md`'s table,
  including generics (functions and classes), inheritance, borrow receivers, ownership
  moves/drops/destructors, generators + `yield` + `for-in` over generators, modules/imports,
  and the std modules (io, math, types, fs, regex, cli.args, fcl, ranges).

---

## Migration Phases

Each phase has an exit gate. Do not start the next phase until the gate passes.

### Phase 0 — Baseline & decks-clearing

1. Run `python tests/golden_runner.py` and `python tests/error_runner.py`; record the full
   pass list as the parity baseline.
2. Implement the float128→float64 aliasing in the **current** pipeline (so old and new
   pipelines agree from day one). Update affected tests/goldens, docs, changelog.
3. Delete the dead GMP/MPFR code from `runtime.c`/`runtime.h` (everything `mpz_*`/`mpfr_*`
   except what float128 printing needed — which step 2 just made unnecessary). Remove the
   `-lgmp -lmpfr` link flags from `main.py` if present.
4. Add `--emit-fir`, `--emit-flir`, and `--backend {c-legacy,c-fir,asm}` CLI plumbing
   (initially only `c-legacy` works; default stays `c-legacy` until Phase 7).

**Gate 0**: full suite green on the current pipeline with float128 aliased and GMP/MPFR gone;
binaries no longer link GMP/MPFR.

### Phase 1 — FIR infrastructure

Build `firescript/fir/` exactly per `fir_developer_reference.md` Part 1–2 and
`FIR_fir_spec.md`: `ir_types.py`, `ir_node.py`, `ir_module.py`, `ownership.py`,
`ir_builder.py`, `textual.py`. Requirements:

- Instruction set per spec: literals, `BinaryOp`/`UnaryOp`, `Allocate`/`LoadField`/
  `StoreField`/`IndexArray`/`StoreArray`, `Move`/`Borrow`/`Clone`/`Drop`,
  `Call`/`MethodCall`, `Branch`/`Jump`/`Return`/`Unreachable`. Extend as needed for
  generators (e.g. `Yield`, generator state ops) — document any spec additions back into
  `FIR_fir_spec.md`.
- Textual dumps must be **deterministic** (stable value numbering, stable block naming,
  stable type ordering) — dumping the same module twice yields identical text.
- Unit tests for builder + textual round-trip determinism.

**Gate 1**: FIR unit tests pass; hand-built sample modules dump to the documented textual
format deterministically.

### Phase 2 — AST → FIR converter

Implement `firescript/ast_to_fir.py` (`ASTToFIRConverter`) covering **every implemented
language feature**. Consume the semantic analyzer's type/ownership/drop results — do not
re-infer them. Key risk areas:

- Generic functions/classes stay generic in FIR (monomorphization happens in lowering).
- Ownership: every move/borrow/drop the preprocessor/semantic analyzer decided must appear
  as explicit FIR `Move`/`Borrow`/`Drop` instructions; destructor insertion for owned class
  fields must survive the translation.
- Generators: represent `generator<T>` functions and `yield` in FIR explicitly.
- Strings/arrays: keep as high-level typed values (lowering decides representation).
- Directive-gated intrinsics (`syscall_*`, `str_*`, `process_arg*`, lowlevel stdout/stdin)
  become FIR `Call`s to well-known intrinsic names.

Validation: add `--emit-fir` golden snapshots under `tests/expected_fir/` for a
representative subset (~15–25 sources spanning the feature table) and a `fir_snapshot`
test mode. These FIR goldens are internal test fixtures, not user-facing behavior.

**Gate 2**: converter handles every `.fire` file in `tests/sources/`, `examples/`, and
`firescript/std/` without raising; FIR snapshots are deterministic and reviewed.

### Phase 3 — FLIR infrastructure + FIR→FLIR lowering

Build `firescript/flir/` per `FIR_flir_spec.md`: typed low-level IR with explicit sizes,
alignments, field offsets, and ABI metadata. Lowering must implement:

- **Monomorphization** of generic functions/classes into concrete FLIR functions/structs
  (deterministic name mangling, e.g. `unwrap_or_default_Box_i32`).
- **Class lowering** to struct layouts (document the layout algorithm: field order, padding,
  alignment) + method calls to plain calls with explicit receiver pointer; inheritance via
  embedded base struct; static methods to plain functions.
- **Ownership lowering**: `Allocate`→heap alloc + stores, `Drop`→destructor call + free,
  `Clone` for copyable aggregates, moves become plain pointer copies (validity already
  proven by semantic analysis).
- **Generator lowering** to a state-machine struct + resume function (heap-allocated frame,
  state field, `for-in` drives resume until done).
- **String/array representation**: define the concrete layouts (length-prefixed or
  struct-based; refcount field if keeping refcounted strings) — write this decision into
  `FIR_flir_spec.md`.
- `--emit-flir` deterministic dumps + FLIR snapshot goldens for the same subset as Phase 2.

**Gate 3**: lowering succeeds for the entire test corpus + std; FLIR snapshots deterministic.

### Phase 4 — Interim FLIR→C backend (differential harness)

Implement a deliberately thin `firescript/codegen/flir_to_c.py` (FLIR is already explicit, so
this is mostly 1:1 printing) reachable via `--backend c-fir`. Add `tests/fir_runner.py` that
runs the **entire** golden + error suites through `--backend c-fir` and diffs program output
against the Phase 0 baseline.

This backend is scaffolding: it exists to prove FIR/FLIR semantics are right before any
assembly is written, so miscompiles in Phase 6 can only be backend bugs. Do not polish it.

**Gate 4 (parity gate)**: 100% of baseline-passing golden tests produce identical output via
`--backend c-fir`; error suite unchanged. CI (or a documented script) runs both pipelines.

### Phase 5 — Runtime rewrite in firescript (freestanding-ready)

Replace the C runtime with firescript code + a small set of new internal intrinsics. Do this
**while still on the `c-fir` backend** so every piece is differentially testable before
assembly exists (C can call kernel32 too).

1. **New internal intrinsics/directives** (document in `docs/internal/directives.md`):
   raw memory (`mem_alloc`, `mem_free`, `mem_copy`, `mem_load8/16/32/64`, `mem_store...`),
   pointer-sized integers, and `extern_import("kernel32.dll", "WriteFile", ...)`-style
   foreign call declarations that lower to FLIR extern calls. Gate them behind a directive
   (`enable_lowlevel_memory` or similar) — internal use only.
2. **Port `runtime.c` to firescript modules** (suggested: `firescript/std/internal/` or
   `firescript/runtime_fs/`): string type + concat/compare/slice/index, numeric→string
   conversions including a float dtoa (shortest-roundtrip not required; pick a simple,
   well-tested algorithm — golden diffs from old `%g` output are allowed per decision 6),
   string→numeric parsing (`as int32` casts), print/println over a buffered stdout writer,
   process args via `GetCommandLineA` + Windows arg-parsing rules, `syscall_*` over
   kernel32 (`CreateFileA`/`ReadFile`/`WriteFile`/`CloseHandle`/`DeleteFileA`/`MoveFileExA`),
   fd table mapping small ints → HANDLEs with 0/1/2 = std handles, `GetLastError` → negated
   errno-style codes preserving documented `SyscallResult` semantics.
3. Heap: `HeapAlloc(GetProcessHeap(), ...)`; keep or simplify the double-free guard registry
   semantics of `firescript_malloc`/`firescript_free` (decide and document).
4. Switch the `c-fir` backend to emit calls to the firescript runtime instead of `runtime.c`
   (the interim C build may temporarily link kernel32 directly; that's fine — it's scaffolding).
5. Regenerate float-formatting goldens here (once), with changelog entry.

**Gate 5**: full suite green on `--backend c-fir` with **zero references to `runtime.c`** —
the C compiler compiles only generated code; the only remaining C is the interim backend's
output itself.

### Phase 6 — FLIR → x86-64 assembly backend

Implement `firescript/codegen/flir_to_asm/` targeting Windows x64, GAS syntax, reachable via
`--backend asm`:

- **ABI**: Win64 calling convention (RCX/RDX/R8/R9 + XMM0–3, 32-byte shadow space, 16-byte
  stack alignment at calls, callee-saved RBX/RBP/RSI/RDI/R12–R15/XMM6–15). Isolate this in a
  `CallingConvention` module for future Linux SysV support.
- **Codegen strategy**: simplest correct approach first — every FLIR value gets a stack slot,
  naive per-instruction load/op/store. No register allocator required for completion.
- **Floats**: SSE2 scalar only. No x87.
- **Stack probing**: no CRT means no `__chkstk` — emit explicit page-touching probes for
  frames ≥ 4KB.
- **Entry point**: emit a `_start`-style entry (`-e firescript_entry`) that fetches args,
  calls user `main`, then `ExitProcess(0)`.
- **Assemble & link**: invoke MinGW `as` then `ld` with `-lkernel32` (libkernel32.a import
  lib), no CRT objects, subsystem console. Update `main.py` to drive this; keep `--emit-asm`
  (or reuse `-d` debug artifacts) to retain the `.s` file.
- **Extern calls**: FLIR extern imports become PE imports through the kernel32 import lib.

Validation: run the full suite via `--backend asm` and diff against `--backend c-fir` output
(which already matches baseline). Verify with `objdump -p` that test binaries import only
`KERNEL32.dll`.

**Gate 6 (parity gate)**: 100% of golden tests pass via `--backend asm` with output identical
to `c-fir`; error suite unchanged; binaries import only kernel32.dll; `examples/` all build
and run correctly.

### Phase 7 — Cutover and deletion

1. Make `asm` the default backend. Remove `--cc`, `detect_c_compiler`, and all C-compiler
   invocation from `main.py`.
2. Delete: old AST→C codegen (`generator.py`, `statements.py`, `classes.py`, `generics.py`,
   `declarations.py`, `base.py` — everything not used by the asm backend), the interim
   `flir_to_c.py`, `firescript/runtime/runtime.c|.h`, `conversions.h`, `tests/fir_runner.py`
   (fold into the normal runners), and the `c-legacy`/`c-fir` backend choices.
3. Docs sweep: update `CLAUDE.md` feature table; mark FIR/FLIR docs as implemented reality
   (not plan); resolve the bootstrapping TODO in `FIR_impl_plan.md`; changelog entries for
   every user-visible change (removed `--cc`, MinGW binutils now required instead of
   gcc/clang, float formatting change, float128 alias, any flag additions); update
   `tests/TEST_MANIFEST.md`.
4. Final full-suite run + manual smoke of `examples/`.

**Gate 7**: see Completion Criteria below — all must hold on a clean checkout.

---

## Completion Criteria

The migration is **done** when ALL of the following are true on a clean clone with only
Python + MinGW binutils installed (no gcc, no clang, no MSVC):

1. `python firescript/main.py <file>.fire` produces a runnable Windows x64 `.exe`, invoking
   only `as` and `ld` as external tools. Setting `CC` in the environment has no effect;
   `--cc` no longer exists.
2. Compiled binaries import **only `kernel32.dll`** (verified via `objdump -p` on at least
   the binaries for `tests/sources/` — automate this check in the test runner).
3. `python tests/golden_runner.py` passes 100% (every test that passed at the Phase 0
   baseline, plus any added during migration). Golden diffs versus baseline exist only for
   float text formatting and are changelog-documented.
4. `python tests/error_runner.py` passes 100% with **byte-identical** diagnostics to the
   Phase 0 baseline.
5. Every `[IMPLEMENTED]` feature in `CLAUDE.md`'s table has at least one passing test through
   the new pipeline — explicitly including: generic functions AND generic classes,
   inheritance, `&this`/`&mut this`, destructors/deterministic drops, generators +
   `for-in` over generators, ranges, negative indexing, string iteration, all std modules
   (io, math, types, fs, regex, cli.args, fcl), modules/exports, and `process_argc`/argv
   handling with `.args` sidecar tests.
6. Every file in `examples/` compiles and matches its `tests/expected/*.out` golden.
7. `--emit-fir` and `--emit-flir` work and are deterministic (two consecutive compiles of the
   same source produce identical dumps; automated test exists). FIR/FLIR snapshot goldens
   pass.
8. The repository contains **no C source or headers used by the compiler pipeline**
   (`Grep` for `#include`, `runtime.c`, `gcc`, `clang`, `detect_c_compiler` in `firescript/`
   returns nothing relevant), and no generated `.c` files are produced at any stage.
9. The runtime is firescript code compiled through the same pipeline as user code; new
   low-level directives are documented in `docs/internal/directives.md` and rejected in user
   code without the directive.
10. `docs/changelog.md` `## Currently in Development` documents every user-facing change;
    `CLAUDE.md` and the FIR internal docs reflect the implemented reality; the float128
    alias is documented `[IN DEVELOPMENT]`.
11. LSP server and VS Code extension behavior is unchanged (front-end untouched).
12. CI / documented test commands no longer reference the old pipeline; a fresh-machine
    build-and-test procedure (Python + MinGW binutils only) is documented in the README or
    docs.

## Known Risks / Watch Items

- **dtoa**: float→string in pure firescript is the trickiest runtime piece. Budget real time;
  fuzz against Python's `repr`/`%g` for sanity even though exact match isn't required.
- **Generators** are the newest language feature and have no FIR design yet — expect spec
  work in Phases 2–3, and write the design back into the spec docs.
- **Stack probes** (`__chkstk` replacement) and **Win64 unwind/alignment** bugs crash
  intermittently, not deterministically — add stress tests with deep recursion and large
  locals.
- **Windows arg parsing** (`GetCommandLineA` → argv) has cursed quoting rules; match the
  behavior the current tests rely on (`.args` sidecars are the contract).
- **fd semantics**: tests may depend on POSIX-ish fd behavior; the HANDLE-table shim must
  preserve `SyscallResult` documented semantics exactly.
- Keep the old pipeline runnable until Gate 6 passes — never strand `main` without a working
  default backend.
