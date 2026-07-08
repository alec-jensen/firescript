# firescript version planning

Planning for future versions toward **1.0.0 — Titan**, the self-hosted release.

## Guiding Vision

The goal of firescript 1.0 is a **self-hosted compiler**: a firescript compiler written in
firescript that can compile itself. Every version from 0.6.0 onward builds explicitly toward
this end state.

The bootstrap path has three phases:
1. **Stdlib foundation** — give firescript the data structures and string utilities a compiler
   needs (Vec, HashMap, StringBuilder, enums, pattern matching)
2. **Language maturity** — traits, ownership ergonomics, diagnostics infrastructure — so the
   firescript compiler code is clean and idiomatic
3. **Self-hosted implementation** — write the compiler front-end, then the backend, in
   firescript, culminating in a full bootstrap

---

## 0.5.0 — Kirin

*FIR + FLIR pipeline, self-hosted native toolchain, runtime in firescript, generators, char,
`&mut this`, module exports, generic classes, stdlib expansion, true float128.*

### Already complete

- **FIR + FLIR pipeline** — AST → FIR → FLIR → x86-64 assembly is the only pipeline
- **Self-hosted native toolchain** — pure-Python x86-64 assembler and PE32+ writer;
  no external tools, no MinGW binutils, zero subprocess calls
- **firescript runtime** — `std/internal/runtime.fire` implements strings, arrays, numeric
  formatting and parsing, process arguments, file syscalls in firescript
- Generators (`generator<T>`, `yield`), `for-in` over generators, `std.ranges`
- `char` type and character literal syntax (`'A'`, `'\n'`)
- `&mut this` receiver syntax
- Module exports (private by default)
- Generic classes (`class Pair<T, U>`)
- String methods (`length`, string iteration)
- String-to-numeric casting
- `std.types` (`Tuple`, `Option`, `CopyableTuple`, `CopyableOption`)
- `std.fs` (file I/O), `std.regex`, `std.cli.args` (expanded), `std.fcl`
- Logical operators (`&&`, `||`, `!`), exponentiation (`**`), compound assignment,
  increment/decrement
- Sized array declarations with optional initializers, negative indexing, utility methods
- LSP server, VS Code extension
- Unified structured diagnostics
- **True `float128` (IEEE binary128)** — 16-byte soft-float over `uint64` pairs;
  correctly-rounded literal parsing, full arithmetic/comparison/conversion set

### Remaining for Kirin

Nothing — all planned Kirin items are complete.

---

## 0.6.0 — Griffin (Current)

**Theme: Standard library foundations for compiler writing.**

The firescript compiler needs rich collections and string utilities that are simply not
expressible with fixed-size arrays alone. This release fills those gaps so the subsequent
self-hosting work is not blocked by missing data structures.

### Language features

| Feature | Rationale |
|---|---|
| `enum` / sum types with data payloads | AST node types, tokens, and type variants map naturally to enums. Without them the compiler code is class hierarchies and manual dispatch. |
| `match` expressions | Ergonomic destructuring of enums. Without match, working with enums is verbose if-else chains. |
| `Vec<T>` in `@firescript/std.collections` | Dynamic arrays are the single most critical missing collection — needed for token lists, AST child lists, symbol tables, etc. |
| `HashMap<K,V>` in `@firescript/std.collections` | Symbol tables, type environments, and identifier lookups require associative maps. |
| `StringBuilder` in `@firescript/std.text` | Code generation and error message formatting need efficient string accumulation. |
| Extended string methods: `split`, `substring`, `indexOf`, `startsWith`, `endsWith`, `trim`, `toLower`, `toUpper`, `replace` | Lexing and string processing require these — cannot write a parser without substring search and splitting. |
| `Result<T,E>` proper error type | Compiler phases propagate errors; a well-typed Result is essential for ergonomic error handling in firescript code. |

### Standard library

- New module `@firescript/std.collections` — `Vec<T>`, `HashMap<K,V>` (and later `Stack<T>`,
  `Queue<T>`, `Deque<T>`)
- New module `@firescript/std.text` — `StringBuilder`
- Enhanced `@firescript/std.types` — `Result<T,E>` with `Ok`, `Err` variants and combinators
- **`@firescript/std.regex`** — full regex matching engine (lexer, parser, NFA/DFA
  compilation, matching over strings). Required by FCL and by compiler string-processing
  needs. (Existing stub needs real implementation.)

### Compiler improvements

- Support `enum` and `match` in the front-end pipeline (lexer, parser, semantic analysis,
  FIR lowering)
- Support `Vec<T>`, `HashMap<K,V>`, `StringBuilder`, and `Result<T,E>` as stdlib modules
  with appropriate compiler intrinsics where needed
- Implement `@firescript/std.regex` with necessary runtime support
- Regenerate and freeze goldens for all new features

### Test coverage

- Comprehensive golden tests for enums and match
- Comprehensive golden tests for Vec, HashMap, StringBuilder operations
- Golden tests for new string methods
- Comprehensive golden tests for regex (matching, capture groups, anchors, character
  classes, alternation, quantifiers)
- Error tests for invalid enum/match usage
- Error tests for invalid regex patterns

### Gate

All stdlib modules are usable from firescript code. Vec, HashMap, string methods, and regex
are thoroughly tested. Enum and match work across the full pipeline (no FIR/FLIR gaps).

---

## 0.7.0 — Wyvern

**Theme: Language maturity + FCL configuration system.**

With basic collections and regex in place, this release adds the abstraction features that
make a firescript compiler readable and maintainable, and delivers FCL — the config language
that kiln will use for package manifests.

### Language features

| Feature | Rationale |
|---|---|
| Trait / interface system | Abstraction over AST node types, type representations, and backends. Essential for a modular compiler architecture. |
| Ownership-aware generic constraints (`Owned`, `Copyable`) | Generic compiler code (e.g., a `Vec<T>` used with both owned and copyable types) needs constraint clarity. |
| `move()` and `borrow()` call-site syntax | Explicit ownership operations make compiler code self-documenting and catch ownership bugs at compile time. |
| Improved error messages / diagnostic infrastructure | The firescript compiler should produce rich, helpful diagnostics. Implementing this in firescript requires the same. |

### FCL

FCL (firescript config language) is a typed configuration DSL that kiln will use for
package manifests and project configuration. It is a mini-compiler: lexer, parser,
typechecker, and (eventually) interpreter. Implementing FCL in firescript serves as
a crucible for the self-hosting work in 0.8.0 — the same patterns (enums for tokens/AST,
recursive-descent parsing, trait-based visitors) are exercised here at smaller scale
before tackling the full firescript compiler.

- Lexer (tokenizer) — builds on the existing `std/fcl/lexer.fire` stub
- Parser — recursive-descent over FCL syntax, producing typed AST (enum-based)
- Typechecker — validates structure against expected types
- Runtime interpreter — evaluates FCL expressions and produces config values
- Compile-time import support for `.fcl` files in firescript source
- Document `.fcl` format and FCL import mechanism

### Compiler improvements

- Add trait parsing, semantic checking, and FIR/FLIR lowering (monomorphization-based;
  no vtables unless needed)
- Add `move(expr)` / `borrow(expr)` as expression forms with semantic enforcement
- Generalize generic constraint system to accept `Owned` and `Copyable` as built-in
  constraint kinds
- Deprecation warning path for implicit moves (prepare for future mandatory explicit
  move/borrow)
- Implement FCL pipeline in the firescript compiler (recognize `.fcl` imports, invoke
  FCL interpreter, merge results into the FIR module)
- Optional: initial trait-based standard library abstractions (`Iterable<T>`, `Cloneable`)

### Test coverage

- Comprehensive golden tests for traits (impl, bounds, generic functions with trait bounds)
- Tests for `move()` / `borrow()` at call sites
- Ownership-aware generic constraint tests
- Comprehensive FCL golden tests (valid config files produce expected output)
- FCL error tests (invalid config syntax, type mismatches, missing values)
- End-to-end tests for `.fcl` imports in firescript source

### Gate

Traits, ownership-aware generics, and explicit move/borrow all work across the pipeline.
FCL is usable: valid `.fcl` files produce correct config values; invalid ones report clear
diagnostics. The compiler can import and consume FCL configuration. The language is mature
enough to begin writing a compiler front-end.

---

## 0.8.0 — Dragon

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
- Firescript front-end modules live under `firescript/std/compiler/` so they are
  importable like standard library modules

### Compiler improvements (Python side)

- Expose whatever compiler intrinsics or ABI hooks the firescript front-end needs
  (e.g., internal type representations, memory allocation patterns)
- Add `--frontend {python,firescript}` flag to `main.py`

### Test coverage

- Firescript lexer produces identical token streams to Python lexer across all test files
- Firescript parser produces identical ASTs across all test files
- Firescript semantic analysis passes all golden and error tests (output-identical)
- Firescript FIR builder produces FIR dumps matching Python FIR dumps (deterministic)

### Gate

Firescript front-end passes 100% of the existing test suite with output-identical results
when run via `--frontend firescript`. The Python front-end is still the default, but the
firescript front-end is feature-complete.

---

## 0.9.0 — Behemoth

**Theme: Self-hosted backend and bootstrap (Windows).**

Write the code generator (FLIR lowering, assembly emission) and the self-hosted toolchain
(assembler, PE writer) in firescript. The firescript compiler compiles itself end-to-end
on Windows x64.

### firescript/std/compiler/codegen.fire
- FIR → FLIR lowering (monomorphization, class lowering, generator lowering)
- FLIR → x86-64 assembly text emission
- Support for all FLIR ops the Python backend emits (must achieve byte-identical assembly)

### firescript/std/compiler/assembler.fire
- Pure-firescript x86-64 assembler consuming the same GAS Intel text format
- Object image production (sections, symbols, relocations)
- Must produce byte-identical output to Python `backend/assembler.py`

### firescript/std/compiler/pe_writer.fire
- Pure-firescript PE32+ writer
- DOS header, COFF header, optional header, section layout, import directory, IAT
- Must produce byte-identical output to Python `backend/pe.py`

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

- Firescript codegen passes all golden tests (output-identical)
- Firescript assembler + PE writer pass `tests/asm_encoding_tests.py`
- Bootstrap binary passes full test suite on its own
- Determinism test: bootstrap binary is byte-identical on repeated compilations

### Gate

`python firescript/main.py --compiler firescript <file>.fire` produces a working binary
for any test source (Windows x64). The firescript compiler can compile itself end-to-end.
The resulting binary, when run on the firescript compiler sources, produces a byte-identical
(or semantically equivalent) copy of itself.

---

## 0.10.0 — Chimera

**Theme: Linux x64 target + kiln foundations.**

Two parallel tracks: (A) port the compiler to Linux x64 with ELF output, and (B) build
kiln basics on top of FCL. Chimera is the hybrid beast — fitting for a hybrid-platform,
hybrid-tool release.

### Track A: Linux x64 target

#### firescript/std/compiler/elf_writer.fire
- Pure-firescript ELF64 writer for Linux x64
- ELF header, program headers, section headers, symbol table, relocation handling
- Linux x86-64 syscall ABI (instead of kernel32.dll imports)
- System V AMD64 calling convention differences from Win64

#### Python backend support
- Add ELF64 writer to the Python backend (`backend/elf.py`)
- Add Linux x86-64 syscall ABI to the codegen (`codegen/flir_to_asm.py` already emits
  target-neutral assembly; add `--target` flag to select Win64 vs System V ABI)
- Runtime: Linux syscall wrappers for heap (brk/mmap), I/O (read/write), process exit
- `--target {windows-x64,linux-x64}` flag in `main.py`
- Firescript-on-Linux CI (GitHub Actions) runs the golden suite under native Linux build
- Update `tests/golden_runner.py` to support cross-target testing

### Track B: kiln foundations

#### Package manifest format
- Define FCL-based package manifest format (`firescript.toml` or equivalent `.fcl` schema)
- Define lockfile format for deterministic dependency resolution

#### Commands
- `kiln init` — scaffold a new project with a valid manifest
- `kiln build` — invoke the compiler on a project
- `kiln run` — build and execute a project
- Local-only dependency resolution (path/workspace deps; no network yet)

#### Integration
- kiln is implemented in firescript (uses `std.cli.args`, `std.fs`, FCL)
- Python driver initially shells out to the firescript binary, later self-hosted
- kiln source lives at `firescript/tools/kiln/`

### Compiler improvements (Python side)

- Add any compiler API hooks needed by `kiln build` (compile a project given a root
  module, collect diagnostics, output binary to a specified path)

### Test coverage

- ELF validity checks (readelf or pure-Python ELF inspector) on Linux target builds
- Linux target golden suite runs on CI (native Linux)
- Cross-target tests: same source produces equivalent output on both targets
- Kiln end-to-end CLI tests for `init`, `build`, `run` on a smoke project
- Kiln negative tests: invalid manifest, missing source, build failures
- Lockfile determinism tests

### Gate

`--target linux-x64` produces a working native ELF binary for all test sources. Kiln can
`init`, `build`, and `run` a simple project with local-only dependencies. Both targets
pass their golden suites on CI.

---

## 0.11.0 — Leviathan

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

- Add `--target {windows-x64,linux-x64}` to the firescript backend (mirrors Python flag)
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

- Finalize all language features for 1.0 (no breaking changes after this)
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
- Firescript compiler source becomes the canonical implementation

### Release criteria

1. Firescript compiler is fully self-hosted — compiles itself end-to-end with no Python
   compiler code invoked in the compile path
2. 100% test suite passes on the self-hosted compiler across both target platforms
3. Compiler runs on **Windows x64** (Tier 1) and **Linux x64** (Tier 1, CI-tested every
   commit)
4. kiln provides `init`, `build`, `run`, `test`, `publish`, `add`, `sync`, `update`
5. Standard library is documented, stable, and tested (`std.collections`, `std.text`,
   `std.types`, `std.io`, `std.math`, `std.fs`, `std.regex`, `std.fcl`, `std.ranges`,
   `std.cli.args`, `std.net`)
6. Changelog is complete; migration guide documents any breaking changes from 0.x
7. No feature in `docs/` carries `[IN DEVELOPMENT]`; `[PLANNED]` items are explicitly
   marked for post-1.0
8. The Python compiler is removed; `python firescript/main.py` is a thin shim or gone

## Post-1.0

Features deferred beyond 1.0, prioritized for subsequent releases:

### High priority
- **`@firescript/std.math.linalg`** — vectors, matrices, core linear algebra
- **macOS x64** Mach-O target

### Medium priority
- **`@firescript/std.io.input`** — keyboard/mouse/gamepad input APIs
- **Performance optimization** — codegen optimizations (constant folding, DCE, CSE)

### Lower priority / stretch
- JavaScript + Wasm compilation target
- Async/await
- Advanced generic features (higher-kinded types, GATs)
- Macro system
- `@firescript/window` and `@firescript/graphics` packages
