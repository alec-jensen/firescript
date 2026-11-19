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
  under T-060-04 is interim. Design: [language_model_redesign.md](language_model_redesign.md) §12.
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
- **0.6.0 is done when** every task below is `done`, the full CI profile passes locally, the
  Windows CI run is green, and the owner has cut the release (moving changelog entries into the
  versioned section is the owner's job).

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
| `ArrayList<T>` in `@firescript/std.collections` | Dynamic arrays are the single most critical missing collection — needed for token lists, AST child lists, symbol tables, etc. |
| `HashMap<K,V>` in `@firescript/std.collections` | Symbol tables, type environments, and identifier lookups require associative maps. |
| `StringBuilder` in `@firescript/std.text` | Code generation and error message formatting need efficient string accumulation. |
| Extended string methods: `split`, `substring`, `indexOf`, `startsWith`, `endsWith`, `trim`, `lower`, `upper`, `replace` | Lexing and string processing require these — cannot write a parser without substring search and splitting. |
| `Result<T,E>` proper error type | Compiler phases propagate errors; a well-typed Result is essential for ergonomic error handling in firescript code. |

### Standard library

- New module `@firescript/std.collections` — `ArrayList<T>`, `HashMap<K,V>` (and later `Stack<T>`,
  `Queue<T>`, `Deque<T>`)
  - `ArrayList<T>` — **done**: `add`/`removeLast`/`get`/`set`/`size`, capacity-doubling growth,
    correct for both Copyable and Owned element types (owned elements are dropped by the
    generated destructor before the backing buffer is freed — see the new `@owns_elements`
    class decorator in `flir/lowering.py`). Built on two new compiler intrinsics private to
    `std/collections/`, `fs_rt_array_new<T>`/`fs_rt_array_copy<T>`, which allocate/copy a
    `T[]` buffer of a runtime-determined element count (the "Dynamic arrays (stdlib)"
    `CLAUDE.md` feature-table entry, now flipped to `[IMPLEMENTED]`).
  - `enumerate` generator for iterating over `ArrayList<T>` with index/value pairs `Pair<int32,T>`
    — **done**. Surfaced (and fixed) a compiler bug where a generic-class-shaped type
    string with an unresolved nested type argument (e.g. `Pair<int32, T>`) substituted the
    outer type but never the type parameters inside it, and a second bug where generic
    generator functions had no type-argument inference/monomorphization at all.
  - `HashMap<K,V>` — **done**: `set`/`get`/`has`/`remove`/`length`/`size`, open addressing
    with tombstones, capacity-doubling growth at a 70% load factor. `K` restricted to a
    fixed hashable set (integer types, `bool`, `char`, `string`) via a new `fs_rt_hash<K>`
    compiler intrinsic (dispatched by concrete `K` at FLIR-lowering time, same pattern as
    `fs_rt_array_new<T>`) — no `Hashable` trait to dispatch through generically until the interfaces release (0.9.0).
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
- New module `@firescript/std.text` — `StringBuilder` — **done**: backed by an `ArrayList<string>`
  of fragments rather than a raw growable byte buffer (`std/internal/strings.fire` can't
  construct an `ArrayList<T>` itself — internal runtime files carry no import statements), with
  `append`/`length`/`build`. `build()` drains fragments with `ArrayList<T>.removeLast()`, not
  `get()`/`enumerate()` (unsafe for the Owned `string` element type — see
  `docs/reference/std/collections.md`). No zero-arg constructor (`StringBuilder("")` starts
  empty instead) — see the compiler-improvements note below.
- Extended string methods — **done**: `.indexOf()`, `.substring()`, `.startsWith()`,
  `.endsWith()`, `.trim()`, `.replace()`, alongside the existing `.length()`/`.upper()`/
  `.lower()`, all via `@builtin_method` in `std/internal/strings.fire` (`.indexOf()`/
  `.substring()` decorate the pre-existing `fs_rt_str_index_of`/`fs_rt_str_slice`
  primitives directly). `split` is the one method from this list that's a plain function
  (`split(s, delim)`), not a `.split()` dot-method — it needs to return `ArrayList<string>`, and
  `@builtin_method` backing functions live in `std/internal/`, which (as above) can't
  reference `ArrayList<T>`. Lives in `@firescript/std.text` alongside `StringBuilder`.
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
  - Parser + backtracking matcher over a compiled program (literals, escapes, `.`, anchors,
    groups, alternation, `* + ?`, classes) — **done**
  - Shorthand classes `\d \D \w \W \s \S`, counted quantifiers `{n}`/`{n,}`/`{n,m}`,
    non-capturing groups — **done**
  - Capture groups with submatch extraction (`Match`, `find_first`, `find_all`, `replace`
    with `$0`..`$9`) — **done**
  - NFA/DFA compilation (linear-time matching), lookarounds, non-greedy quantifiers,
    backreferences, named groups, `\b` — not done

### Compiler improvements

- Support `enum` and `match` in the front-end pipeline (lexer, parser, semantic analysis,
  FIR lowering) — **done**: `enum` declarations (tag-only and named data-payload variants,
  positional construction) and `match` expressions (name-based payload binding with
  optional rename, exhaustiveness/duplicate/wildcard-order checks, statement and
  value-producing forms, tag-dispatched destructors for owned payload data) work across the
  full pipeline. Generic enums (`enum Option<T>`) remain a follow-up.
- Support `ArrayList<T>`, `HashMap<K,V>`, `StringBuilder`, and `Result<T,E>` as stdlib modules
  with appropriate compiler intrinsics where needed — `ArrayList<T>` (including `enumerate`),
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
  value moved via a method call through a *field-access* receiver (`this.parts.add(s)`)
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
- Added `Some`/`None`/`Ok`/`Err` static factories and `unwrapOr()` to
  `Option`/`CopyableOption`/`Result`/`CopyableResult` **done** — see
  `docs/reference/std/types.md`. Building these surfaced four more previously-unexercised
  compiler bugs, all fixed (see `docs/changelog.md`'s 0.6.0 Bug Fixes): the FLIR verifier's
  store check was the one place not using the codebase's established pointer-leniency
  comparison, breaking `this.value = null;` for a pointer-shaped generic field; the same
  assignment for a *scalar*-shaped generic field lowered `null` to a bare pointer instead of
  the scalar's zero value, since the assignment-conversion paths never propagated the
  target's expected type before converting a `null` RHS; a generic class referencing itself
  inside its own body (a static factory returning `Box<T>`, or a self-call like
  `this.isSome()` from another of its own methods) failed to parse/type-check in a file with
  no imports at all — exactly `std/types/init.fire`'s own shape — because the enclosing
  class isn't registered in the parser's normal registries until its whole body finishes
  parsing, and a pre-existing fallback for this only ever activated in files that happened
  to have an unrelated import; fixed with a dedicated `_current_generic_class_name` tracked
  independently across the parser's parse-time and separate type-check-time traversals. And
  a *general*, non-generic-specific gap: a bare (no explicit type arguments) type-qualified
  static call on a class imported from another module (`Counter.fromDouble(5)`) had no
  deferred-import parsing fallback at all — only the `<TypeArgs>` form did — so it silently
  fell through to being parsed as an ordinary instance method call and crashed AST->FIR
  conversion.
- Implement `@firescript/std.regex` with necessary runtime support
- Regenerate and freeze goldens for all new features

### Test coverage

- Comprehensive golden tests for enums and match — **done**: `tests/sources/enums/`,
  `tests/sources/match/`, plus error tests in `tests/sources/invalid/enums/` and
  `tests/sources/invalid/match/`
- Comprehensive golden tests for ArrayList, HashMap, StringBuilder operations — ArrayList and HashMap
  **done**: `tests/sources/std/collections/` (push/pop, growth, get/set, an Owned element
  type; integer keys, string keys, growth/rehashing, an Owned value type with a
  leak/double-free stress cycle). StringBuilder **done**:
  `tests/sources/std/text/stringbuilder_basic.fire`
- Golden tests for Result/CopyableResult — **done**: `tests/sources/std/types/`
  (`result_isok_iserr.fire`, `result_null_vs_zero.fire`, `result_copyable.fire`)
- Golden tests for the `Some`/`None`/`Ok`/`Err`/`unwrapOr` static factories/combinator —
  **done**: `tests/sources/std/types/` (`option_unwrap_or.fire`, `result_unwrap_or.fire`;
  the former `option_static_factories.fire` / `result_static_factories.fire` were merged into them), plus
  regression coverage for the compiler bugs found along the way:
  `tests/sources/generics/generic_self_referential_static_factory.fire`,
  `tests/python/parser/test_generic_self_reference.py` (the no-imports edge specifically),
  and `tests/sources/classes/classes_cross_module_bare_static_method.fire`
- Golden tests for new string methods — **done**: `tests/sources/strings/`
  (`strings_index_of_substring.fire`, `strings_starts_ends_with.fire`, `strings_trim.fire`,
  `strings_replace.fire`) and `tests/sources/std/text/split_basic.fire`
- Comprehensive golden tests for regex (matching, capture groups, anchors, character
  classes, alternation, quantifiers) — **done**: `tests/sources/std/regex/`
- Error tests for invalid enum/match usage — **done**
- Error tests for invalid regex patterns — **done**: `tests/sources/std/regex/std_regex_error_*.fire`
- Improve overall test coverage

### Gate

All stdlib modules are usable from firescript code. ArrayList, HashMap, string methods, and regex
are thoroughly tested. Enum and match work across the full pipeline (no FIR/FLIR gaps) —
**done**.

### Close-out tasks

Order matters only where `Depends on` says so. WIP means unfinished, untested work saved as a
labeled commit on a branch; a session may build on it or discard it.

#### T-060-01 · Fix the Windows CI `strings_unicode` failure · S · `done (80f121c)`
- **Goal:** Windows CI is fully green.
- **Evidence:** CI run 44572498054 (commit `6c0bb25`) has exactly one failure,
  `run:tests/sources/strings/strings_unicode.fire`, an output mismatch. After the compiler started
  reading source as UTF-8 (`6c0bb25`), the likely cause is the test harness reading each test file
  (the `/* EXPECT */` block, directives) with the platform default encoding (cp1252 on Windows).
- **Steps:** find every `open(` without `encoding=` in `tests/harness/` (expectations, discovery,
  directives, workdir) and read as UTF-8; add a Python test that forces a non-UTF-8 default
  (`LC_ALL=C PYTHONUTF8=0 PYTHONCOERCECLOCALE=0`, as in
  `tests/python/cli/test_main_arg_errors.py`) and parses a non-ASCII EXPECT block; push and check
  the Windows run.
- **Actual cause (found):** not the harness (it already reads UTF-8). The x86-64 assembler's
  `_decode_gas_string` encoded string-literal characters with the locale codec (cp1252 on
  Windows), so `é` became `0xE9`; it now always encodes UTF-8.
- **Done when:** the Windows run on the pushed commit is green.

#### T-060-02 · Housekeeping: remove merged agent worktrees and branches · S · `done`
- **Goal:** a clean repository to work in.
- **Steps:** every branch below is already merged into `main`; remove its worktree and branch:
  `cleanup-compile-fail`, `cleanup-run-tests`, `cleanup-run-followup`, `cleanup-python-front`,
  `cleanup-python-back`, `fix-numerics`, `fix-parser-imports-cli`, `fix-frontend-checks`,
  `fix-fir-crashes`, plus the leftover `worktree-agent-*` branches and the superseded
  `wip/coverage-worker-flush`. **Keep** `safety-runtime-traps`, `safety-frontend`,
  `docs-and-cleanup-060`, `explicit-receivers` (open work). Use `git worktree remove` then
  `git branch -d` (a refusal means it is not merged: investigate, do not force).
- **Done when:** `git worktree list` shows only `main` and the four kept branches.

#### T-060-03 · Review and merge `safety-runtime-traps` · M · `done (210c692)`
- **Goal:** runtime safety traps on `main`.
- **Start from:** branch `safety-runtime-traps` (5 commits, not merged): `stderr-contains` test
  directive; checked integer arithmetic, division by zero and `MIN / -1` through one runtime trap
  entry point, plus `std.math.wrapping` and an `enable_wrapping_arithmetic` std-only directive;
  float-to-int cast traps; array bounds checks; ArrayList bounds docs. It regenerated many FLIR
  snapshots.
- **Steps:** `git switch -c task/T-060-03 safety-runtime-traps`, merge `main`; run the full CI
  profile and fix fallout. **Verify** (not assumed): the stdlib no longer depends on wraparound
  anywhere (hashing, float128 soft-float, collections, regex, text: grep unsigned arithmetic in
  `firescript/std`); trap kinds go through a single entry point and the message format is
  `firescript runtime error: <Kind>: <detail>` with one documented nonzero exit code; snapshot
  diffs are only the added trap function; tests that pinned wraparound (`types_int8`,
  `types_uint8`, `edge_cases_overflow_underflow`, `stress_integer_overflow`, out-of-range cast cases
  in `int_float_cast_matrix`) now assert the trap or use `std.math.wrapping`; measure the
  overhead on `tests/sources/performance/*` and record it in the commit message.
- **Docs:** `docs/reference/error_handling.md`, `type_system.md` (overflow, casts), `arrays.md`
  (bounds); mark catchable exceptions `[PLANNED]`; changelog Breaking Changes.
- **Done when:** merged, CI profile green. If the verify list shows large gaps, split into new
  tasks (e.g. "migrate stdlib to wrapping ops") instead of growing this one.

#### T-060-04 · Review and merge `safety-frontend` · M · `done (085ebe8)`
- **Goal:** front-end safety rules on `main`.
- **Start from:** branch `safety-frontend` (5 commits, not merged): required braces; missing
  `return` on a path is an error; unknown escapes are errors; nullable-to-non-nullable rejected
  with a null-check narrowing rule; constant integer overflow, constant out-of-range index and
  constant division by zero are errors. The 6th commit (`fd0a877`) is unrelated WIP for T-060-05
  and may be left out of this merge.
- **Steps:** branch from it, merge `main`; run the CI profile; fix fallout. Confirm firescript/std,
  `examples/` and every test were migrated for the new rules; review the nullable narrowing design
  with the owner (it is a judgment call: report exactly what it accepts; the whole nullable
  feature is interim, see "Absence is `Option<T>`" above); docs
  (`control_flow.md`, `functions.md`, `type_system.md`, the nullable docs); changelog Breaking
  Changes.
- **Done when:** merged, CI profile green.

#### T-060-05 · Leftover parser bugs · M · `done (7c59c23)` · Depends on T-060-04
- **Start from:** WIP commit `fd0a877` on `safety-frontend` (parser base/expressions/statements).
- **Fix, each with a regression test:** statements that start with a non-identifier token are
  silently dropped or get a misleading "Invalid assignment target" (`arr[0] = ;`); a nested explicit
  generic constructor `Pair<Pair<int32,int32>,int32>(Pair<int32,int32>(1,2), 3)` does not parse;
  `TITLE.length()` on an uppercase `const` string is parsed as a type method call;
  `"é".length()` on a non-ASCII string literal is a parse error (verify first).
- **Outcome:** fixed statement-start tokens (reported, not dropped), nested explicit generic
  constructor (`_parse_type_arg_list` accepts nested generics) and the uppercase `const` string
  method call. Not fixed, verified: `"é".length()` is not a non-ASCII problem; a method call on
  *any* literal (`"abc".length()`) does not parse, because the literal branch of `parse_primary`
  has no postfix member-access loop. That is a feature, not a bug fix; left for a separate task.
  The WIP change that stopped `parse_primary` from consuming a `;` on "Unexpected token" was
  dropped: it moves the reported column in about ten existing compile-fail tests (`arr[0] = ;`
  is still reported at the next statement), so it needs its own task with re-blessed expectations.
- **Done when:** merged, CI profile green.

#### T-060-06 · Remove the legacy conversion builtins · S · `done (task/T-060-06 7858298)`
- **Goal:** the names listed under "Decisions" are gone.
- **Start from:** WIP commit `1683fac` on `docs-and-cleanup-060` (12 files; likely this task plus
  `const`/constraint work; read the diff first, take only what belongs to this task).
- **Where:** `firescript/ast_to_fir.py` (intrinsic tables and return types),
  `firescript/flir/lowering.py`, `firescript/parser/type_system.py` (arity check), `parser/base.py`.
- **Steps:** a call afterwards gives the normal "Function 'X' is not defined" error; nothing in
  `firescript/std` or `examples/` uses them (migrate to `as`); delete the tests that only exercised
  them (`conversions/builtin_conversions*`, `performance/stress_type_conversions`) and rewrite
  incidental uses to `as`; one compile-fail test; changelog Breaking Changes.

#### T-060-07 · `const` reassignment is an error · S · `done (task/T-060-07)`
- **Goal:** `PI = 3.2;` is a compile error (today it compiles); `PI += 1`, `PI++` too, for module
  level and local consts. Mark `const` class fields `[PLANNED]` in `docs/reference/classes.md`
  (they do not parse today). Compile-fail tests, a valid-twin run test, changelog.

#### T-060-08 · Constraint syntax: `Union<A, B>` · M · `done (479ed1d)`
- **Goal:** `Union<A, B, ...>` replaces `A | B` in constraints; `Intersection<A, B>` gives a clear
  "not supported yet" diagnostic; `&` is a syntax error pointing at it; unknown constraint names
  are errors. Keep `|` working everywhere else it exists.
- **Update:** `firescript/std/constraints.fire`, every std/test/example/doc using `|` in a
  constraint (grep `constraint ` and `<T: `), `docs/reference/type_system.md` (mark the unmarked
  examples around the constraint-alias section), tests (valid twin bounded by `Union<int32,
  float64>`; compile-fail for `|`, `Intersection<...>`, `&`, an unknown name), changelog Breaking.
- **Start from:** parts may exist in WIP `1683fac` (`docs-and-cleanup-060`).

#### T-060-09 · Explicit receivers: the compiler rule · M · `done (5b79cb5)`
- **Goal:** the rule in "Decisions" is enforced with coded diagnostics: receiver-less instance
  method; receiver-less constructor; `owned this` in an ordinary method (today the misleading
  "Constructor 'A' expected 0 args"); plain `this` receiver (today "Expected ':' after parameter
  name"); assignment to `this`; mutation through `&this` (already an error; keep).
- **Start from:** WIP commit `f5e6bac` on `explicit-receivers` (parser/declarations,
  type_system, semantic_analyzer). Keep parser edits confined to receiver parsing.
- **Done when:** compile-fail tests exist for each diagnostic; the migration tasks below make the
  suite green again. **Merge this and T-060-10..12 together** (the suite is red between them),
  working on one branch `task/explicit-receivers`.

#### T-060-10 · Explicit receivers: migrate the standard library · M · `done (ee9d542)` · Depends on T-060-09
- Every class in `firescript/std/**` (Pair/CopyablePair, Option/CopyableOption, Result/
  CopyableResult, ArrayList, HashMap, StringBuilder, fs, regex, fcl, ...): add `&this` to read-only
  methods and `&mut this` to mutating methods and constructors, deciding each by reading the body.
- **Note:** most std methods already had receivers; the rest (constructors, `isSome`/`isNone`/`isOk`/`isErr`/`unwrapOr` on Option/Result, Pair, FileResult, StringBuilder, fcl results) were migrated. Copyable-class methods needed a small compiler fix (receiver exempt from the Owned-only borrow check). `std_types_test` FIR snapshot regenerated (receiver-only diffs).

#### T-060-11 · Explicit receivers: migrate tests and examples · M · `done (b9bdf5a)` · Depends on T-060-10
- `examples/` and the `.fire` sources under `tests/sources/` (run and invalid) and any
  `tests/python/**` that embeds receiver-less source or asserts the old behavior. Regenerate
  FIR/FLIR snapshots only after confirming the only diffs are receiver-related. If it does not fit
  one session, split by directory (classes, generics, memory, invalid, python).

#### T-060-12 · Explicit receivers: docs and changelog · S · `done (4f3c327)` · Depends on T-060-09
- `docs/reference/classes.md` (receiver convention), `memory_management.md` receiver wording,
  `functions.md`, std doc samples; changelog Breaking Changes. Consuming receivers stay
  `[PLANNED]`. Add the compile-fail test list for T-060-09 to the manifest.

#### T-060-13 · Array returned from a call has no tracked length · M · `done (cb77718)`
- `fn mk() -> int32[] { return [1,2,3]; } x: int32[] = mk();` now compiles, but `.length()`,
  negative indexing and `for-in` over `x` fail in lowering ("array_length on array of unknown
  size"). Track or carry the length (hidden length value like array parameters have). Regression
  tests for each use.

#### T-060-14 · `while (true) { consume(x); break; }` internal error · S · `done (e2daf78)`
- An internal ownership-verifier error (FIRV-O3) on an owned value moved in a loop that always
  exits via `break`. Reproduce, find the drop-insertion/move-state cause, fix, regression test.

#### T-060-15 · Scope leak: a variable name clashes across functions · M · `done (aa2ffc5)`
- Declaring `bexp` in `firescript/std/internal/float128.fire` produced "Expected uint64, got int64",
  apparently from an `int64 bexp` parameter in another runtime function. Reproduce with two
  functions that use the same name with different types, find where scope/type tables leak, fix,
  regression test.

#### T-060-16 · Internal conversion errors print raw Python tracebacks · M · `done (4b99981)`
- AST-to-FIR and FIR-to-FLIR failures surface as a traceback with no error code: moving an owned
  module-level variable, `directive x;` inside a function, `u: string? = "a"; u.length()`. Make
  each a coded diagnostic (or fix the underlying bug), and make `main.py` print any remaining
  conversion error as a normal diagnostic without a traceback. Tests for each.

#### T-060-17 · Docs: `enums.md` and `match.md` reference pages · M · `done`
- There are no reference pages for enums and `match`, only changelog entries. Write
  `docs/reference/enums.md` and `match.md` from `tests/sources/enums`, `tests/sources/match` and
  the changelog, **running every code sample** and fixing the text where the compiler differs; mark
  features `[IMPLEMENTED]`, generic enums `[PLANNED]`; link from the docs index.

#### T-060-18 · Docs: string methods, `fn main`, implicit constructors, `%`, array methods · M · `done (2dc1c1a)`
- Document `indexOf`, `substring` (clamps out-of-range), `startsWith`, `endsWith`, `trim`,
  `replace`, `upper`, `lower`, `length`, and array `.size()` (same as `.length()`); the behavior of
  `fn main` (top-level statements are ignored with a warning when `main` exists, while module-level
  variable initializers still run); implicit constructors (`class Pt { x: int32; y: int32; }` gives
  `Pt(1, 2)`, `new Pt(...)` needs a declared constructor); `%` is integer-only. Verify each by
  running it.

#### T-060-19 · Docs: stale and false statements · S · `done (e55a20a)`
- `docs/reference/std/math.md` says nested generic calls fail (they work); `std/*.md` and
  `type_system.md` still mention `push`/`pop`/`length()` on collections, `Tuple`, a `list<T>`
  section for ArrayList, `char = "A"`, prefix-style signatures in `io.md`, and floats printed as
  `3.14` (they print `3.140000`); `classes.md` shows a call-site `&` (a parse error) and a
  `copyable class` that violates its own all-fields-Copyable rule (weaken that rule's text to
  "intended, not yet enforced"); `memory_management.md:216` call-site `&`; `error_handling.md` says
  `Result` is planned (it exists). Fix wording and markers only.

#### T-060-20 · Changelog corrections · S · `done`
- Add the missing Breaking Changes entry for `Tuple`/`CopyableTuple` → `Pair`/`CopyablePair`
  (`Tuple` shipped in 0.5.0); fix three stale entries (the never-shipped `int a?` form, the enum
  entry's prefix payload syntax, the match entry saying statement arms must be braces when
  expression arms work); then compare `git log 77a09c4..HEAD` against `docs/changelog.md` for any
  other user-facing change with no entry.

#### T-060-21 · `CLAUDE.md` feature table and notes · S · `done` · Depends on the language tasks above
- Fix the stale `Built-in input()` row (removed in 0.5.0); update rows made inaccurate by the
  tasks above (traps, braces, receivers, constraints, globals are already listed). Add the
  fls/fsc terminology only when the owner starts that work.

#### T-060-22 · 0.6.0 release check · S · `todo` · Depends on everything above
- `python tests/run.py --profile ci` passes locally; the Windows CI run is green; the roadmap's
  0.6.0 section statuses are final; the owner moves `## Currently in Development` into a versioned
  section (the owner's job, not an agent's).

---

## 0.7.0 — Chimera

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
