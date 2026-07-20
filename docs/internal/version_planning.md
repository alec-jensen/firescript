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
- **firescript runtime** — `std/internal/*.fire` implements strings, arrays, numeric
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
| Extended string methods: `split`, `substring`, `indexOf`, `startsWith`, `endsWith`, `trim`, `lower`, `upper`, `replace` | Lexing and string processing require these — cannot write a parser without substring search and splitting. |
| `Result<T,E>` proper error type | Compiler phases propagate errors; a well-typed Result is essential for ergonomic error handling in firescript code. |

### Standard library

- New module `@firescript/std.collections` — `Vec<T>`, `HashMap<K,V>` (and later `Stack<T>`,
  `Queue<T>`, `Deque<T>`)
  - `Vec<T>` — **done**: `push`/`pop`/`get`/`set`/`length`/`size`, capacity-doubling growth,
    correct for both Copyable and Owned element types (owned elements are dropped by the
    generated destructor before the backing buffer is freed — see the new `@owns_elements`
    class decorator in `flir/lowering.py`). Built on two new compiler intrinsics private to
    `std/collections/`, `fs_rt_array_new<T>`/`fs_rt_array_copy<T>`, which allocate/copy a
    `T[]` buffer of a runtime-determined element count (the "Dynamic arrays (stdlib)"
    `CLAUDE.md` feature-table entry, now flipped to `[IMPLEMENTED]`).
  - `enumerate` generator for iterating over `Vec<T>` with index/value pairs `Tuple<int32,T>`
    — **done**. Surfaced (and fixed) a compiler bug where a generic-class-shaped type
    string with an unresolved nested type argument (e.g. `Tuple<int32, T>`) substituted the
    outer type but never the type parameters inside it, and a second bug where generic
    generator functions had no type-argument inference/monomorphization at all.
  - `HashMap<K,V>` — **done**: `set`/`get`/`has`/`remove`/`length`/`size`, open addressing
    with tombstones, capacity-doubling growth at a 70% load factor. `K` restricted to a
    fixed hashable set (integer types, `bool`, `char`, `string`) via a new `fs_rt_hash<K>`
    compiler intrinsic (dispatched by concrete `K` at FLIR-lowering time, same pattern as
    `fs_rt_array_new<T>`) — no `Hashable` trait to dispatch through generically until 0.7.0.
    `get`/`remove` return `V` directly rather than `Option<V>` — not because of a compiler
    gap any more (see below), just to keep this milestone's changes scoped; switching to
    `Option<V>` is a viable, purely additive follow-up. Surfaced (and
    fixed) three more previously-unexercised generic-class bugs: a later type-checking pass
    only pushed a *method's own* (empty) type parameters into scope, clobbering the
    *enclosing class's* type parameters for the whole method body, so comparing two values
    of the class's own type parameter with `==` failed; a generic class method calling
    *another method on the same instance* didn't monomorphize the callee correctly (method
    receivers are always typed by bare class name, never `ClassName<Args>`, and lowering
    assumed otherwise); and `drop()` on a bare generic-type-parameter value that turns out
    concretely Copyable/primitive tried to heap-free its raw bit pattern instead of no-op'ing
    (needed for `HashMap<K,V>.set()`'s conditional `drop(key)` on overwrite). Also led directly
    into full nullable-*scalar* support (locals, class fields, function/method/constructor
    parameters, and plain-function return types all now carry a real "has a value" tag, not
    just a zero-lowered `null`) — see the changelog and `Option<T>`/`CopyableOption<T>` note
    below.
  - Nullable-*scalar* types (`int32?`, `bool?`, `char?`, and the other fixed-width numeric
    types) — **done**: a real, separate "has a value" tag alongside the value itself (a
    companion `bool` binding/field/parameter, added transparently by the compiler), so `null`
    and a legitimate stored `0`/`false` are always distinguishable. Covers local variables,
    class fields, function/method/constructor parameters, and (for plain functions) return
    types (`fn foo() -> int32?`, previously a hard parse error — lifted this milestone). A
    nullable-scalar return is compiled to an internal `__NullableReturn<T>` struct return,
    unwrapped transparently at the call site (evaluating the callee at most once, even when
    both its value and has-value flag are needed). `Option<T>`/`CopyableOption<T>` needed zero
    source changes to become correct for a primitive `T` — `Option<int32>(0).isSome()` now
    correctly returns `true`. String/class/array nullables were already unambiguous via the
    pointer value `0` and are untouched by this.
- New module `@firescript/std.text` — `StringBuilder` — **done**: backed by a `Vec<string>`
  of fragments rather than a raw growable byte buffer (`std/internal/strings.fire` can't
  construct a `Vec<T>` itself — internal runtime files carry no import statements), with
  `append`/`length`/`build`. `build()` drains fragments with `Vec<T>.pop()`, not
  `get()`/`enumerate()` (unsafe for the Owned `string` element type — see
  `docs/reference/std/collections.md`). No zero-arg constructor (`StringBuilder("")` starts
  empty instead) — see the compiler-improvements note below.
- Extended string methods — **done**: `.indexOf()`, `.substring()`, `.startsWith()`,
  `.endsWith()`, `.trim()`, `.replace()`, alongside the existing `.length()`/`.upper()`/
  `.lower()`, all via `@builtin_method` in `std/internal/strings.fire` (`.indexOf()`/
  `.substring()` decorate the pre-existing `fs_rt_str_index_of`/`fs_rt_str_slice`
  primitives directly). `split` is the one method from this list that's a plain function
  (`split(s, delim)`), not a `.split()` dot-method — it needs to return `Vec<string>`, and
  `@builtin_method` backing functions live in `std/internal/`, which (as above) can't
  reference `Vec<T>`. Lives in `@firescript/std.text` alongside `StringBuilder`.
- Enhanced `@firescript/std.types` — `Result<T,E>`/`CopyableResult<T,E>` — **done**: `value: T?`/`error: E?`
  fields (mirrors `Option<T>`'s pattern exactly, including automatic nullable-scalar correctness for a
  primitive `T`/`E`), `isOk()`/`isErr()`. No `Ok`/`Err` static factory constructors and no combinators
  (`map`, `unwrapOr`, etc.) — while probing the natural `Result.Ok(value)`/`Result.Err(error)` design,
  discovered static methods on generic classes didn't work in any form at the time (explicit type
  arguments, `Box<int32>.make(5)`, were a parser error; inferred type arguments, `Box.make(5)`, crashed
  AST->FIR conversion). `Result`/`CopyableResult` are constructed directly instead (`Result<T,E>(value,
  error)`, `null` on the unused side); the underlying compiler gap is now fixed (see
  `generics/generic_class_static_method_inferred.fire` and `generic_class_static_method_explicit.fire`
  under Compiler improvements below) but `Result` was kept as direct construction rather than revisited,
  as adding `Ok`/`Err` factories now would be a purely additive follow-up with no functional need.
- **`@firescript/std.regex`** — full regex matching engine (lexer, parser, NFA/DFA
  compilation, matching over strings). Required by FCL and by compiler string-processing
  needs. (Existing stub needs real implementation.)

### Compiler improvements

- Support `enum` and `match` in the front-end pipeline (lexer, parser, semantic analysis,
  FIR lowering) — **done**: `enum` declarations (tag-only and named data-payload variants,
  positional construction) and `match` expressions (name-based payload binding with
  optional rename, exhaustiveness/duplicate/wildcard-order checks, statement and
  value-producing forms, tag-dispatched destructors for owned payload data) work across the
  full pipeline. Generic enums (`enum Option<T>`) remain a follow-up.
- Support `Vec<T>`, `HashMap<K,V>`, `StringBuilder`, and `Result<T,E>` as stdlib modules
  with appropriate compiler intrinsics where needed — `Vec<T>` (including `enumerate`),
  `HashMap<K,V>`, and `Result<T,E>`/`CopyableResult<T,E>` **done**; also unblocked unsized
  array class fields (previously rejected entirely), added a `fs_rt_hash<K>` intrinsic and
  multi-field `@owns_elements` support, and fixed a series of narrow, previously-unexercised
  generic-class/generator bugs both surfaced (method-call return-type substitution for a bare
  type-parameter return, missing receiver on a method with no explicit `&this`/`this`
  destroying the object on every call, a generic class's own bare-name Owned/Copyable
  registration, a generator-loop-variable drop gap for Owned yield types, nested-type-argument
  substitution inside a compound generic type string, generic generator functions having no
  type-argument inference/monomorphization at all, class-body type-parameter scoping in the
  standalone type-checking pass, a generic method calling another method on the same instance,
  `drop()` on a primitive corrupting the heap, and `null` for a nullable scalar type) — see
  `docs/changelog.md`'s 0.6.0 Bug Fixes. Another one surfaced while designing `Result<T,E>`
  and later fixed: static methods on generic classes didn't work in any call form. The
  parser's `Type.method(...)` special case (and its `Identifier<TypeArgs>.method(...)`
  counterpart) only ever recognized a *concrete* class name, since a generic class's bare
  template name is deliberately absent from `self.user_types`/`self.user_methods`
  (registered as a `generic_class_templates` entry instead); `type_system.py`'s
  `TYPE_METHOD_CALL` validation and `ast_to_fir.py`'s monomorphization needed the
  equivalent generic-template fallback a constructor call already had, plus type-argument
  inference from the call's own arguments (there's no receiver instance to read concrete
  type arguments from) for the no-explicit-type-args form — see
  `generics/generic_class_static_method_inferred.fire` and
  `generic_class_static_method_explicit.fire`. Separately, fixed an unrelated lexer bug hit
  while writing `Result<T,E>`'s regression tests: identifiers with `true`/`false`/`null` as
  a literal prefix (e.g. `false_ok`) failed to parse, since those three literal token
  patterns (unlike every keyword) had no trailing word-boundary — see `docs/changelog.md`'s
  0.6.0 Bug Fixes and `tests/sources/identifiers/`.
- Extended string methods and `StringBuilder`/`split` **done** — see the Standard library
  section above. Fixed another real bug hit while building `StringBuilder`: an owned
  value moved via a method call through a *field-access* receiver (`this.parts.push(s)`)
  was never recognized as moved, so it was also auto-dropped at scope exit (FIRV-O2) —
  `semantic_analyzer.py` and `preprocessor.py` each only resolved a receiver's type for a
  bare-identifier receiver, and the generic-field case additionally needed the "strip
  generic type arguments" normalization `ast_to_fir.py` already had — see
  `docs/changelog.md`'s 0.6.0 Bug Fixes and
  `tests/sources/memory/memory_field_receiver_method_move.fire`. Two more surfaced in the
  same investigation, and were also fixed (all `tests/sources/known_issues/` entries from
  this release are now resolved, with regression tests moved to their normal categories):
  a same-file class's bare `Foo(args)` constructor call resolved against field order
  instead of the real declared constructor whenever they diverged (`func_name in
  self.user_types` in `parser/type_system.py` now checks `self.user_methods` for a real
  constructor first — see `classes/classes_zero_arg_constructor_bare_call.fire`), and a
  class imported from another module lost its type for raw field access (not method calls)
  after a bare-call construction (the deferred-import suppression in `FIELD_ACCESS`
  handling widened from composite-generic-only to any not-yet-resolved non-primitive type
  — see `classes/classes_cross_module_bare_construct_field_access.fire`).
- Implement `@firescript/std.regex` with necessary runtime support
- Regenerate and freeze goldens for all new features

### Test coverage

- Comprehensive golden tests for enums and match — **done**: `tests/sources/enums/`,
  `tests/sources/match/`, plus error tests in `tests/sources/invalid/enums/` and
  `tests/sources/invalid/match/`
- Comprehensive golden tests for Vec, HashMap, StringBuilder operations — Vec and HashMap
  **done**: `tests/sources/std/collections/` (push/pop, growth, get/set, an Owned element
  type; integer keys, string keys, growth/rehashing, an Owned value type with a
  leak/double-free stress cycle). StringBuilder **done**:
  `tests/sources/std/text/stringbuilder_basic.fire`
- Golden tests for Result/CopyableResult — **done**: `tests/sources/std/types/`
  (`result_isok_iserr.fire`, `result_null_vs_zero.fire`, `result_copyable.fire`)
- Golden tests for new string methods — **done**: `tests/sources/strings/`
  (`strings_index_of_substring.fire`, `strings_starts_ends_with.fire`, `strings_trim.fire`,
  `strings_replace.fire`) and `tests/sources/std/text/split_basic.fire`
- Comprehensive golden tests for regex (matching, capture groups, anchors, character
  classes, alternation, quantifiers)
- Error tests for invalid enum/match usage — **done**
- Error tests for invalid regex patterns
- Improve overall test coverage

### Gate

All stdlib modules are usable from firescript code. Vec, HashMap, string methods, and regex
are thoroughly tested. Enum and match work across the full pipeline (no FIR/FLIR gaps) —
**done**.

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
- firescript front-end modules live under `firescript/std/compiler/` so they are
  importable like standard library modules

### Compiler improvements (Python side)

- Expose whatever compiler intrinsics or ABI hooks the firescript front-end needs
  (e.g., internal type representations, memory allocation patterns)
- Add `--frontend {python,firescript}` flag to `main.py`

### Test coverage

- firescript lexer produces identical token streams to Python lexer across all test files
- firescript parser produces identical ASTs across all test files
- firescript semantic analysis passes all golden and error tests (output-identical)
- firescript FIR builder produces FIR dumps matching Python FIR dumps (deterministic)

### Gate

firescript front-end passes 100% of the existing test suite with output-identical results
when run via `--frontend firescript`. The Python front-end is still the default, but the
firescript front-end is feature-complete.

---

## 0.9.0 — Behemoth

**Theme: Self-hosted backend and bootstrap (Windows).**

Write the code generator (FLIR lowering, assembly emission) and the self-hosted toolchain
(assembler, PE writer) in firescript. The firescript compiler compiles itself end-to-end
on Windows x86_64.

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

### Gate

`python firescript/main.py --compiler firescript <file>.fire` produces a working binary
for any test source (Windows x86_64). The firescript compiler can compile itself end-to-end.
The resulting binary, when run on the firescript compiler sources, produces a byte-identical
(or semantically equivalent) copy of itself.

---

## 0.10.0 — Chimera

**Theme: Linux x86_64 target + kiln foundations.**

Two parallel tracks: (A) port the compiler to Linux x86_64 with ELF output, and (B) build
kiln basics on top of FCL. Chimera is the hybrid beast — fitting for a hybrid-platform,
hybrid-tool release.

### Track A: Linux x86_64 target

#### firescript/std/compiler/elf_writer.fire
- Pure-firescript ELF64 writer for Linux x86_64
- ELF header, program headers, section headers, symbol table, relocation handling
- Linux x86-64 syscall ABI (instead of kernel32.dll imports)
- System V AMD64 calling convention differences from Win64

#### Python backend support
- Add an ELF64 writer under `backend/linux/elf.py` (mirrors `backend/windows/pe.py`)
- Add a Linux runtime-extern table under `firescript/platforms/linux.py` (mirrors
  `firescript/platforms/windows.py`), wired into `flir/lowering.py` for the Linux target
- Add a System V AMD64 calling convention to `codegen/x86_64/flir_to_asm.py` alongside
  the existing `Win64Convention`, selected per-target
- Runtime: Linux syscall wrappers for heap (brk/mmap), I/O (read/write), process exit
- Add `Target(Platform.LINUX, Arch.X86_64)` to `SUPPORTED_TARGETS` in `firescript/targets.py`
  (already selectable on the CLI via `--platform linux --arch x86_64`, since the choices
  mirror the full README support matrix — this just wires up the backend)
- firescript-on-Linux CI (GitHub Actions) runs the golden suite under native Linux build
- Update `tests/run.py`'s `run` kind / matrix engine to support cross-target testing

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

`--platform linux --arch x86_64` produces a working native ELF binary for all test sources.
Kiln can `init`, `build`, and `run` a simple project with local-only dependencies. Both
targets pass their golden suites on CI.

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
