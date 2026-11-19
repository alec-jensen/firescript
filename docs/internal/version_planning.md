# firescript version planning

Planning for future versions toward **1.0.0 — Titan**, the self-hosted release.

> **Terminology.** The language is defined by the firescript Language Specification (fls); the
> compiler is the firescript Compiler (fsc). They are versioned independently — see
> [spec_and_versioning.md](spec_and_versioning.md). During 0.N the roadmap below builds toward a
> preliminary fls 1.0.0; fsc 0.N tracks that draft without being a full implementation. fls 1.0.0
> and fsc 1.0.0 are released together when the compiler implements the whole specification.

## Guiding Vision

The goal of firescript 1.0 is a **self-hosted compiler**: a firescript compiler written in
firescript that can compile itself. Every version from 0.6.0 onward builds explicitly toward
this end state.

The bootstrap path has three phases:
1. **Stdlib foundation** — give firescript the data structures and string utilities a compiler
   needs (ArrayList, HashMap, StringBuilder, enums, pattern matching)
2. **Language maturity** — a value-semantics memory model, const and visibility, an interface-
   based object model, diagnostics infrastructure — so the firescript compiler code is clean and
   idiomatic. This precedes self-hosting so the compiler is not written twice. Linux support
   (Python backend) is pulled forward ahead of it.
3. **Self-hosted implementation** — write the compiler front-end, then the backend, in
   firescript, culminating in a full bootstrap

## Working in tasks

Work is done as **small, self-contained tasks**, one per session. A task block (below, under each
release) carries everything a fresh session needs, so nothing depends on chat history. A session
reads `CLAUDE.md`, this section, its one task block, and the docs the block links to, and does
nothing else.

### Session protocol

1. **Pick one task** whose dependencies are done (the owner usually names it). Set its status to
   `in-progress` with the branch name.
2. **Work in the main checkout on a branch** `task/T-xxx-nn` (or continue the named WIP branch).
   No subagent fan-out and no parallel agents: one task, one session, one line of work.
3. **Keep runs small.** Use targeted tests (`python tests/run.py <path> --no-coverage`) while
   working. Run the full CI profile only once, at the end: `python tests/run.py --profile ci`
   (about 10 minutes; it also checks determinism on every run test).
4. **Linux needs the wine environment** (the native backend targets Windows only):
   `export FIRESCRIPT_TEST_TARGET=windows/x86_64 FIRESCRIPT_TEST_RUN_PREFIX=wine WINEDEBUG=-all`
   (see "Running on Linux" in `tests/TEST_MANIFEST.md`).
5. **Follow `CLAUDE.md`**: regression test with every bug fix, changelog entry with every
   user-facing change, manifest and status-marker updates in the same commit, one logical change
   per commit, determinism, never skip a test, never change an expectation just to pass.
6. **Tests must be portable to Windows**: no assertions on OS-specific error wording, no
   characters invalid in Windows file names (`<>:"\|?*`) in test ids or paths, never rely on the
   platform default text encoding (always pass `encoding="utf-8"`). Windows CI is the real check.
7. **If a task grows, stop and split it.** Add the new smaller tasks to this file, finish only the
   first, and say so. A task that needs more than one session was defined too big.
8. **Finish**: merge to `main`, set the status to `done` with the commit, and note anything the
   next task needs. Push only when the owner says so (the project settings allow
   `git push origin main`).
9. **Record decisions here, not in chat.** An owner decision goes into the task block or the
   relevant design doc in the same commit.

Status values: `todo`, `in-progress (branch)`, `done (commit)`, `blocked (reason)`.
Sizes: **S** is a short session, **M** is one full session. There is no **L**: split it.

### Decisions that apply to every task

Confirmed by the owner. Design detail is in
[language_model_redesign.md](language_model_redesign.md); the audit evidence is in
[test_audit/README.md](test_audit/README.md).

- **Safety is the model.** Integer overflow, division by zero, `MIN / -1`, out-of-range array
  indexing, and float-to-int casts of NaN/infinity/out-of-range values **trap** (a runtime error;
  catchable exceptions come in 0.9.0). Narrowing `as` casts between integer widths stay explicit
  truncation. Explicit `wrapping`/`saturating`/`checked` operations exist for control.
- **Braces are required** on `if`, `else`, `while`, `for`. Missing `return` on a path in a non-void
  function is an error. Unknown string/char escapes are errors. A nullable value may not flow into
  a non-nullable position (the minimal null-check narrowing rule is a judgment call to review).
- **Explicit receivers are required.** Instance methods declare `&this` or `&mut this`;
  constructors declare `&mut this`; consuming receivers on ordinary methods are not supported yet.
  `this` (the binding) can never be assigned; the receiver governs mutation of the object.
- **`const` cannot be reassigned.** `const` class fields are `[PLANNED]`.
- **Constraint unions are written `Union<A, B>`** (replacing `A | B`); `Intersection<A, B>` is
  `[PLANNED]`; `&` is a syntax error; unknown constraint names are errors.
- **The legacy conversion builtins are removed** (`toInt`, `toFloat`, `toDouble`, `toBool`,
  `toChar`, `toString`, `int`, `i32_to_f64`, `i32_to_f32`, `f64_to_i32`, `f32_to_i32`, `i32_to_str`,
  `i64_to_str`, `f64_to_str`, `f32_to_str`). `as` casts stay until the 0.9.0 bindings.
- **Absence is `Option<T>`; `null` and `T?` go away (decided 2026-11-19).** One mechanism, not two.
  `Option<T>` stays explicit: no implicit wrapping of a value or `null` into an `Option` on
  return or assignment. `Some(5)` / `None()` infer their type arguments from the expected type
  (a declared return type, a typed variable, a parameter), so `Option<int32>.None()` need not be
  spelled out there. `T?`, the `null` literal and the null-flow rule are removed once generic
  enums and `match` exist (0.9.0); until then they stay as shipped in 0.6.0, and the narrowing rule
  shipped in 0.6.0 is interim. Design: [language_model_redesign.md](language_model_redesign.md) §12.
- **Errors (0.9.0):** operations throw catchable exceptions (`Exception extends Object`);
  fallible function calls return `Result`. Until then traps print a message and exit through one
  runtime entry point.
- **No real users yet**: breaking changes need only a changelog Breaking Changes entry.
- **Deferred past 0.6.0**: borrow-checker holes and diagnostic-cascade cleanup (0.8.0 memory
  rework), the fls/fsc terminology work, the formal specification, fuzzing.
- **Open owner decisions** (do not decide in a task): a `?`-style propagation operator;
  `Result.unwrap()` throwing; an `Indexable` interface for `list[i]`; naming of the explicit
  arithmetic functions (camelCase vs snake_case); whether `catch` can rethrow; the `std.fs` split
  between `Result` and exceptions.

## 0.7.0 — Chimera

**Carried over from 0.6.0** (found during the 0.6.0 close-out, not yet scheduled as tasks):
- A method call on a literal (`"abc".length()`) fails to parse: the literal branch of
  `parse_primary` has no postfix member-access loop. This is a feature, not a bug fix.
- On "Unexpected token" the parser should also consume the `;`; doing so moves the reported
  column in about ten compile-fail tests, so it needs re-blessed expectations.
- A class used in a constraint before its declaration may report "unknown constraint" (user types
  register in declaration order).
- Generic enums (`enum Option<T>`) remain a follow-up.

**Theme: Linux x86_64 target (Python backend).**

Linux support moves up the timeline. It is independent of the language-model work below, it
gives the project native Linux CI early, and the audit found the target-independent portion of
the compiler is large (lexer, parser, semantic analysis, FIR/FLIR, the assembler core, most of
`flir_to_asm`). Only the self-hosted tooling (`elf_writer.fire`) stays later, in 0.12.0.

### Python backend support

- Add an ELF64 writer under `backend/linux/elf.py` (mirrors `backend/windows/pe.py`): a static
  executable with no imports and a `_start` entry point
- Add a Linux runtime-extern table under `firescript/platforms/linux.py` (mirrors
  `firescript/platforms/windows.py`), wired into `flir/lowering.py` for the Linux target
- Add a System V AMD64 calling convention to `codegen/x86_64/flir_to_asm.py` alongside the
  existing `Win64Convention`, selected per-target (rdi/rsi/rdx/rcx/r8/r9, no shadow space,
  16-byte stack alignment); update the register assumptions in the `fs_rt_mem_copy` thunk and
  the stack-argument offsets
- Replace the Windows entry sequence with a `_start` that reads argc/argv from the stack, calls
  the entry function, and exits via `exit_group`
- Add a `syscall` instruction to the assembler and an FLIR intrinsic that lowers to
  `mov rax, n; syscall`
- Runtime: a Linux layer under `std/internal` — heap via `mmap`/`brk`, I/O and file operations
  via raw syscalls (read, write, open, close, unlink, rename, lseek/fstat, exit_group), and
  process arguments from the initial stack. `main.py` currently compiles every
  `std/internal/*.fire` file into every program, with the `win_*` externs inside them, so the
  runtime sources must become per-target
- `main.py` selects the writer and output suffix per target (no `.exe` on Linux)
- Add `Target(Platform.LINUX, Arch.X86_64)` to `SUPPORTED_TARGETS` in `firescript/targets.py`
  (already selectable on the CLI via `--platform linux --arch x86_64`, since the choices mirror
  the full README support matrix — this just wires up the backend)
- firescript-on-Linux CI (GitHub Actions) runs the golden suite under a native Linux build
- Update `tests/run.py`'s `run` kind / matrix engine to support cross-target testing

### Test coverage

- ELF validity checks (readelf or a pure-Python ELF inspector) on Linux target builds
- Linux target golden suite runs on CI (native Linux)
- Cross-target tests: the same source produces equivalent output on both targets
- Fuzzing and edge-case infrastructure, phase 1 (see [testing_plan.md](testing_plan.md)): the
  `fuzz` test kind with minimization, the error-code coverage check, `PYTHONHASHSEED`
  determinism variation, numeric-boundary matrices, and the regex / collection oracles

### Gate

`--platform linux --arch x86_64` produces a working native ELF binary for all test sources, and
both targets pass their golden suites on CI.

---

## 0.8.0 — Basilisk

**Theme: Memory and safety model.**

Replaces the Owned/Copyable model with value semantics: every type is a value, copying is the
default, moving and borrowing are explicit. Also delivers const enforcement and member
visibility. Full design: [language_model_redesign.md](language_model_redesign.md) §1–§4.

This release deliberately precedes self-hosting. The Python compiler is the only implementation
right now; reworking the model before the self-hosted front-end and backend are written avoids
writing them twice.

### Language features

| Feature | Rationale |
|---|---|
| Memberwise copy by default; explicit move; first-party deep-copy hook | Predictable value semantics like C++; the Owned/Copyable categories disappear from user code. |
| Inline class layout (classes are values, not implicit heap pointers) | Required by value semantics and by the performance goal. |
| `&T` / `&mut T` as real reference types with exclusive `&mut` | Memory safety without runtime checks. Elided-lifetime returns allowed; no reference fields yet. |
| `const` enforcement: binding const, transitive const through `&T`, const fields | `const` is currently parsed but not enforced. |
| `private` / `protected` / `public` on class members | Encapsulation; no member visibility exists today. |
| Removal of `copyable class`, `CopyableOption`/`CopyableResult`/`CopyablePair`, and the planned `Owned`/`Copyable` generic constraints | One kind of value; no duplicated stdlib types. |

### Compiler improvements

- Consolidate move/drop logic (currently duplicated in `semantic_analyzer.py`, `preprocessor.py`
  and the FIR ownership verifier) into one source of truth before changing the rules
- Change class lowering from heap-pointer to inline layout in FIR/FLIR
- Derive *trivially copyable* / *needs destructor* / *copyable* internally; derive the
  destructor for `ArrayList`-style types from field types instead of `@owns_elements`
- Implement `&T` as a type, exclusivity checking over lexical scope, and the elided-return rules
- Enforce const and read-only access through `&T`
- Enforce that compiler directives are usable only from the standard library
- Rewrite `docs/reference/memory_management.md`, `docs/glossary.md` and the other docs that use
  the Owned/Copyable terms (see the migration notes in the design document); resolve the
  doc/implementation drift listed there

### Test coverage

- Intentional, documented update of the memory tests that encode the old model
- Golden and error tests for copy, move, use-after-move, move-only types, `&`/`&mut` exclusivity,
  reference-return rules, const, and visibility
- Regression tests for the unified `Option` / `Result` / `Pair`
- Ownership and borrowing fuzzer plus the runtime allocation counter (see
  [testing_plan.md](testing_plan.md))

### Gate

No `Owned`/`Copyable` terminology remains in the language or docs. Copy, move, borrow, const
and visibility rules are enforced by the compiler and covered by tests. All existing programs
that are still valid under the new model pass; any change to a test's expectations is
documented in the changelog.

---

## 0.9.0 — Manticore

**Theme: Object model and standard library architecture.**

Java-style OOP that compiles to flat, statically dispatched code, and a standard library built
on it. Full design: [language_model_redesign.md](language_model_redesign.md) §5–§9.

### Language features

| Feature | Rationale |
|---|---|
| Interfaces, with static dispatch by default and `&Interface` for dynamic dispatch | Abstraction over AST node types, type representations and backends; `Comparable`, `Iterable`, `Hashable`. |
| Abstract classes | Java-style class hierarchies. |
| `Object` root class, with vtable pointers only where dynamic dispatch needs them and whole-program devirtualization | A single related hierarchy without a universal per-object cost. |
| Primitive bindings (`@bind`, std-only), with implicit import, and `Integer` as an interface for generic `<T: Integer>` | `a.abs()` on an `int32`; accept any precision with type safety. |
| Function interfaces (`interface fn`) and non-capturing lambdas | Contracts on callable parameters. |
| Conversion methods on bindings replace the `as` keyword; `contains` replaces `in`-membership; `isInstance<T>()` / `isExactly<T>()` / `downcast<T>()` on `Object` | Fewer keywords, explicit conversion semantics, fallible parsing via `Result`. See design doc §8. |
| `Box<T>` and `Shared<T>` | Recursive types, owned polymorphism and dynamic lifetime. Lowest priority in this release; may slip. |
| Capturing and escaping closures | Depend on exclusivity and `Box`. Lowest priority; may slip. |
| Exceptions raised by language operations (overflow, division by zero, bounds, invalid casts) as catchable `Exception extends Object` subclasses with `try` / `catch` / `finally`; fallible function calls return `Result`; debug-build stack traces | Python-style error handling consistent with the safety model. See design doc §9. |
| Generic enums and `Option<T>` as `enum { Some(T), None }`, matched with `match`; `Some`/`None` infer type arguments from the expected type; `null` and `T?` removed | One way to express absence, explicit and composable (nests, usable as a generic argument). Needs inline storage or a compact representation for small enums so `Option<int32>` does not allocate. See design doc §12. |
| Improved error messages / diagnostic infrastructure | The firescript compiler should produce rich, helpful diagnostics; implementing this in firescript requires the same. |

### Compiler improvements

- Interface and abstract-class parsing, semantic checking, and FIR/FLIR lowering (monomorphized
  static dispatch, vtables only where needed, devirtualization of non-overridden methods)
- Replace the parse-time copy-down inheritance with real subtyping
- Binding table (type to class) with deterministic implicit module loading; generalize
  `@builtin_method` beyond the string and array families
- Function-type syntax, signature matching, and lambda lowering (non-capturing first)
- Initial standard library abstractions modeled on Java: `Object`, `Comparable<T>`,
  `Iterable<T>`, `Hashable`, `Equatable`, `Printable`; migrate `HashMap<K,V>` off its fixed
  hashable-type set onto `Hashable`

### Test coverage

- Golden tests for interfaces, abstract classes, `Object`, bounds on generic functions, and
  dispatch (static and dynamic)
- Tests that unoverridden methods are devirtualized and that vtables are emitted only where
  needed
- Binding tests (implicit import, every integer width, generic `Integer` bound)
- Function-interface and lambda golden and error tests
- Generated tests for dispatch, interface bounds, and bindings (see
  [testing_plan.md](testing_plan.md))

### Gate

Interfaces, abstract classes, `Object`, primitive bindings, and function interfaces work across
the full pipeline, and the standard library collections use the new abstractions. The language
is mature enough to begin writing a compiler front-end.

---

## 0.10.0 — Wyvern

**Theme: FCL configuration system.**

With collections, regex and the object model in place, this release delivers FCL — the config
language that kiln will use for package manifests.

### FCL

FCL (firescript config language) is a typed configuration DSL that kiln will use for
package manifests and project configuration. It is a mini-compiler: lexer, parser,
typechecker, and (eventually) interpreter. Implementing FCL in firescript serves as
a crucible for the self-hosting work in 0.11.0 — the same patterns (enums for tokens/AST,
recursive-descent parsing, interface-based visitors) are exercised here at smaller scale
before tackling the full firescript compiler.

- Lexer (tokenizer) — builds on the existing `std/fcl/lexer.fire` stub
- Parser — recursive-descent over FCL syntax, producing typed AST (enum-based)
- Typechecker — validates structure against expected types
- Runtime interpreter — evaluates FCL expressions and produces config values
- Compile-time import support for `.fcl` files in firescript source
- Document `.fcl` format and FCL import mechanism

### Compiler improvements

- Implement FCL pipeline in the firescript compiler (recognize `.fcl` imports, invoke
  FCL interpreter, merge results into the FIR module)

### Test coverage

- Comprehensive FCL golden tests (valid config files produce expected output)
- FCL error tests (invalid config syntax, type mismatches, missing values)
- End-to-end tests for `.fcl` imports in firescript source

### Gate

FCL is usable: valid `.fcl` files produce correct config values; invalid ones report clear
diagnostics. The compiler can import and consume FCL configuration.

---

## 0.11.0 — Dragon

**Theme: Self-hosted compiler front-end.**

Write the firescript compiler's front-end (lexer, parser, semantic analysis, FIR
construction) in firescript. The Python compiler remains the bootstrap compiler; the
firescript front-end is developed alongside it and tested against the same test suite.

### firescript/std/compiler/lexer.fire
- Token type definitions (enum-based)
- Source text → token stream conversion
- Character classification, string/number literal lexing, keyword recognition
- Error reporting with source locations

### firescript/std/compiler/parser.fire
- Recursive-descent parser producing AST nodes (enum-based)
- Expression, statement, type, and declaration parsing
- Operator precedence handling
- Error recovery / syntax error reporting

### firescript/std/compiler/semantic.fire
- Scope and binding analysis
- Type checking and type inference
- Ownership tracking (VALID/MOVED/MAYBE_MOVED/BORROWED/DROPPED)
- Generic monomorphization resolution
- Drop point / destructor insertion

### firescript/std/compiler/fir_builder.fire
- FIR type definitions
- AST → FIR lowering
- FIR textual dump (for round-trip testing against Python FIR dumps)

### Integration
- `python firescript/main.py --frontend firescript` toggle to use the firescript
  front-end instead of the Python front-end
- Run full test suite through firescript front-end, compare FIR snapshots
- Incremental rollout: lexer first, then parser, then semantic analysis, then FIR
- firescript front-end modules live under `firescript/std/compiler/` so they are
  importable like standard library modules

### Compiler improvements (Python side)

- Expose whatever compiler intrinsics or ABI hooks the firescript front-end needs
  (e.g., internal type representations, memory allocation patterns)
- Add `--frontend {python,firescript}` flag to `main.py`

### Test coverage

- firescript lexer produces identical token streams to Python lexer across all test files
- Fuzz both front-ends with the same inputs and require identical diagnostics (see
  [testing_plan.md](testing_plan.md))
- firescript parser produces identical ASTs across all test files
- firescript semantic analysis passes all golden and error tests (output-identical)
- firescript FIR builder produces FIR dumps matching Python FIR dumps (deterministic)

### Gate

firescript front-end passes 100% of the existing test suite with output-identical results
when run via `--frontend firescript`. The Python front-end is still the default, but the
firescript front-end is feature-complete.

---

## 0.12.0 — Behemoth

**Theme: Self-hosted backend and bootstrap (Windows and Linux).**

Write the code generator (FLIR lowering, assembly emission) and the self-hosted toolchain
(assembler, PE writer, ELF writer) in firescript. The firescript compiler compiles itself
end-to-end on Windows x86_64 and Linux x86_64 (the Linux target exists in the Python backend
since 0.7.0).

### firescript/std/compiler/codegen.fire
- FIR → FLIR lowering (monomorphization, class lowering, generator lowering)
- FLIR → x86-64 assembly text emission
- Support for all FLIR ops the Python backend emits (must achieve byte-identical assembly)

### firescript/std/compiler/assembler.fire
- Pure-firescript x86-64 assembler consuming the same GAS Intel text format
- Object image production (sections, symbols, relocations)
- Must produce byte-identical output to Python `backend/x86_64/assembler.py`

### firescript/std/compiler/pe_writer.fire
- Pure-firescript PE32+ writer
- DOS header, COFF header, optional header, section layout, import directory, IAT
- Must produce byte-identical output to Python `backend/windows/pe.py`

### firescript/std/compiler/elf_writer.fire
- Pure-firescript ELF64 writer for Linux x86_64
- ELF header, program headers, section headers, symbol table, relocation handling
- Must produce byte-identical output to Python `backend/linux/elf.py`
- Linux x86-64 syscall ABI and System V AMD64 calling convention in the firescript codegen

### Bootstrap
- `python firescript/main.py --compiler firescript` toggle uses the firescript
  compiler (front-end + backend) end-to-end
- The firescript compiler compiles itself: `python firescript/main.py --compiler firescript
  firescript/std/compiler/...` produces a working firescript compiler binary
- **First-stage bootstrap**: use the resulting binary to compile itself again:
  `./build/compiler.exe firescript/std/compiler/...` produces a byte-identical binary
  (or semantically equivalent)
- Document the bootstrap procedure in `docs/internal/development/bootstrap.md`

### Compiler improvements (Python side)

- Add `--compiler {python,firescript}` flag to `main.py`
- Expose any remaining intrinsics or runtime hooks the firescript backend needs
- Remove `--frontend` flag (superseded by `--compiler`)

### Test coverage

- firescript codegen passes all golden tests (output-identical)
- firescript assembler + PE writer pass `tests/python/backend/test_asm_encoding.py`
- Bootstrap binary passes full test suite on its own
- Determinism test: bootstrap binary is byte-identical on repeated compilations
- Fuzz the Python and firescript backends against each other: identical FIR, assembly, and bytes
  (see [testing_plan.md](testing_plan.md))

### Gate

`python firescript/main.py --compiler firescript <file>.fire` produces a working binary
for any test source (Windows x86_64 and Linux x86_64). The firescript compiler can compile itself end-to-end.
The resulting binary, when run on the firescript compiler sources, produces a byte-identical
(or semantically equivalent) copy of itself.

---

## 0.13.0 — Hydra

**Theme: kiln foundations.**

Build kiln basics on top of FCL.

### Package manifest format
- Define FCL-based package manifest format (`firescript.toml` or equivalent `.fcl` schema)
- Define lockfile format for deterministic dependency resolution

### Commands
- `kiln init` — scaffold a new project with a valid manifest
- `kiln build` — invoke the compiler on a project
- `kiln run` — build and execute a project
- Local-only dependency resolution (path/workspace deps; no network yet)

### Integration
- kiln is implemented in firescript (uses `std.cli.args`, `std.fs`, FCL)
- Python driver initially shells out to the firescript binary, later self-hosted
- kiln source lives at `firescript/tools/kiln/`

### Compiler improvements (Python side)

- Add any compiler API hooks needed by `kiln build` (compile a project given a root
  module, collect diagnostics, output binary to a specified path)

### Test coverage

- Kiln end-to-end CLI tests for `init`, `build`, `run` on a smoke project
- Kiln negative tests: invalid manifest, missing source, build failures
- Lockfile determinism tests

### Gate

Kiln can `init`, `build`, and `run` a simple project with local-only dependencies on both
targets.

---

## 0.14.0 — Leviathan

**Theme: std.net + kiln networking.**

Leviathan is the primordial sea beast — the vast network ocean. This release delivers
networking primitives and connects kiln to the world with registry support.

### @firescript/std.net

- TCP socket primitives (connect, listen, accept, send, receive, close)
- UDP socket primitives (sendto, recvfrom)
- Address and endpoint abstractions for IPv4/IPv6
- Non-blocking I/O and timeout semantics
- Consistent error model with clear diagnostics
- Backed by kernel32 sockets (Winsock) on Windows, POSIX sockets on Linux

### kiln networking

- Registry protocol definition (HTTP-based)
- `kiln publish` — package a project to a registry
- `kiln add` — add a dependency from a registry
- `kiln update` / `kiln sync` — resolve and lock dependencies from registries
- Install/cache layout for reproducible restores

### Compiler improvements

- Add `--platform`/`--arch` flags to the firescript backend (mirrors the Python flags)
- Ensure std.net compiles and runs on both targets

### Test coverage

- Loopback TCP client/server golden tests
- UDP send/receive tests
- Connection error, timeout, and invalid endpoint tests
- Kiln end-to-end tests for `publish`, `add`, `sync`, `update`
- Kiln lockfile determinism tests with registry fixtures
- Cross-target networking tests where applicable

### Gate

`std.net` provides working TCP/UDP on both Windows and Linux. Kiln supports the full
development lifecycle: init, build, run, test, publish, add, sync, update.

---

## 1.0.0 — Titan

**Theme: Stabilization, polish, and release.**

With the compiler self-hosted, running on both Windows and Linux, the full kiln toolchain
available, and the standard library covering networking, the 1.0.0 release focuses on
making firescript production-ready and retiring the Python compiler.

### Language and stdlib stabilization

- Finalize all language features for 1.0 (no breaking changes after this); this assumes the
  memory model (0.8.0) and object model (0.9.0) have shipped — see
  [language_model_redesign.md](language_model_redesign.md)
- Complete standard library documentation across all modules
- Performance profiling and optimization of the self-hosted compiler
- `@firescript/std.cli.args` final API surface

### Tooling

- kiln documentation: manifest format, command reference, tutorial
- LSP and VS Code extension polished and tested with the self-hosted compiler

### Compiler retirement

- Remove `--compiler python` flag; the firescript compiler is the only compiler
- Remove `--frontend` flag (long superseded)
- Remove Python test-runner dependency: test runners rewritten in firescript or
  kept as lightweight Python wrappers with no compiler logic
- firescript compiler source becomes the canonical implementation

### Release criteria

1. firescript compiler is fully self-hosted — compiles itself end-to-end with no Python
   compiler code invoked in the compile path
2. 100% test suite passes on the self-hosted compiler across both target platforms
3. Compiler runs on **Windows x86_64** (Tier 1) and **Linux x86_64** (Tier 1, CI-tested every
   commit)
4. kiln provides `init`, `build`, `run`, `test`, `publish`, `add`, `sync`, `update`
5. Standard library is documented, stable, and tested (`std.collections`, `std.text`,
   `std.types`, `std.io`, `std.math`, `std.fs`, `std.regex`, `std.fcl`, `std.ranges`,
   `std.cli.args`, `std.net`)
6. Changelog is complete; migration guide documents any breaking changes from 0.x
7. No feature in `docs/` carries `[IN DEVELOPMENT]`; `[PLANNED]` items are explicitly
   marked for post-1.0
8. The Python compiler is removed; `python firescript/main.py` is a thin shim or gone
9. A nightly fuzz run (see [testing_plan.md](testing_plan.md)) completes with no open crashers

## Post-1.0

Features deferred beyond 1.0, prioritized for subsequent releases:

### High priority
- **`@firescript/std.math.linalg`** — vectors, matrices, core linear algebra
- **macOS x86_64** Mach-O target

### Medium priority
- **`@firescript/std.io.input`** — keyboard/mouse/gamepad input APIs
- **Performance optimization** — codegen optimizations (constant folding, DCE, CSE)

### Lower priority / stretch
- JavaScript + Wasm compilation target
- Async/await
- Advanced generic features (higher-kinded types, GATs)
- Macro system
- `@firescript/window` and `@firescript/graphics` packages
