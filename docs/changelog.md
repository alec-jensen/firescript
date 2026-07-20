# Changelog

firescript follows [Semantic Versioning](https://semver.org/). This makes it easier to understand the impact of changes in each release.

## 0.6.0 - Griffin (Currently in Development)

### New Language Features
- Added `@firescript/std.collections` with `Vec<T>`, a dynamically-growable array (`push`, `pop`, `get`, `set`, `length`/`size`, `enumerate<T>`, capacity-doubling growth). `pop()`/`push()`/`set()` are safe for any element type, including Owned types (`string`, classes) — `Vec<T>`'s destructor drops each live element before freeing its own backing buffer. `get()` (and `enumerate<T>`, which calls it internally) reads an element out by value without shrinking the tracked length, which is only safe for Copyable-ish `T` (numeric types, `bool`, `char`) until `Owned`/`Copyable` generic constraints exist to enforce it — see `docs/reference/std/collections.md`.
- Added `HashMap<K,V>` to `@firescript/std.collections`: an open-addressing hash table (`set`, `get`, `has`, `remove`, `length`/`size`, capacity-doubling growth at a 70% load factor). `set()`/`has()`/`remove()` are safe for any `K`/`V`; `get()` has the same Copyable-`V` caveat as `Vec<T>.get()`, and `get()`/`remove()` are only well-defined after checking `has()` (no bounds/presence check, matching core array indexing). `K` is restricted to a fixed hashable set (integer types, `bool`, `char`, `string`) since firescript has no `Hashable` trait yet — see `docs/reference/std/collections.md`.
- Class fields may now be declared as an unsized array type (`data: int32[];`); fixed-size array fields (`data: int32[10];`) remain unsupported.
- Added `.upper()` and `.lower()` methods on `string`, alongside the existing `.length()` — ASCII case folding (`'a'..'z'` / `'A'..'Z'`); non-letter bytes pass through unchanged. No import needed.
- Added `enum` declarations, e.g. `enum Shape { Circle(float64 radius), Rectangle(float64 width, float64 height), Point }`. Enums are owned types (heap-allocated, like classes without an explicit `copyable` annotation), lowered to a tagged-union layout where variants share the same payload storage. Variants are constructed with `EnumName.Variant` / `EnumName.Variant(args...)` syntax (e.g. `Color.Red`, `Shape.Circle(3.0)`); construction is positional, in declaration order. Payload fields may be any type, including owned types (`string`, classes, other enums) — owned payload data is correctly dropped when the active variant goes out of scope, and only the active variant's fields are ever freed. Generic enums (`enum Foo<T>`) are not yet supported and produce a clear compile error rather than miscompiling.
- Added `match` as a reserved keyword and `match <expr> { <pattern> -> <body>, ... }` expressions, for destructuring `enum` values. Patterns match a bare `EnumName.Variant`, a payload-carrying `EnumName.Variant(bindings...)`, or a wildcard `_`. Payload bindings resolve by the variant's declared field name (`Circle(radius) -> ...`), not position, and can be renamed with `field: local` (`Circle(radius: r) -> ...`); a field can be left out of the pattern entirely if the arm doesn't need it. Match is exhaustiveness-checked at compile time: every variant must be covered by an arm, or a trailing `_` wildcard arm must be present; duplicate arms for the same variant, a wildcard arm followed by more arms, and patterns naming a field the variant doesn't declare (or binding the same field twice) are all compile errors. Payload bindings are read-only borrows scoped to their arm. `match` works both as a statement (arm bodies are `{ }` blocks) and, when every arm body is a plain expression, as a value-producing expression usable in a `return` or a variable initializer.
- Nullable *scalar* types (`int32?`, `bool?`, `char?`, `float64?`, etc. — any fixed-width numeric type, `bool`, or `char`) now carry a real, separate "has a value" tag, so `null` and a legitimate stored `0`/`false` are always correctly distinguishable. This covers local variables, class fields, function/method/constructor parameters, and (for plain functions) return types (`fn tryDivide(a: int32, b: int32) -> int32?`, previously a hard parse error). `Option<T>`/`CopyableOption<T>` benefit automatically for any scalar `T` — `Option<int32>(0).isSome()` now correctly returns `true` — with no changes to `Option`'s own source. String/class/array nullables are unaffected; they were already unambiguous via the pointer value `0`.

### Breaking Changes
- firescript now uses **postfix type declarations** everywhere, Rust/TypeScript-style, instead of the previous C-style prefix syntax. This is a whole-language syntax change:
  - Variables and constants: `int32 a = 5;` → `a: int32 = 5;`; `const float64 PI = 3.14;` → `const PI: float64 = 3.14;`.
  - Nullable markers move to the type: `int32 a? = null;` → `a: int32? = null;`.
  - Ownership/borrow modifiers move to the *name*, matching how method receivers already write `&this`/`&mut this`/`owned this`: `owned Type name` → `owned name: Type`; `&Type name` → `&name: Type`; `&mut Type name` → `&mut name: Type`. This only affects parameters — modifiers were never valid on variables, fields, or return types.
  - Arrays stay attached to the type as a unit: `int32[N] name;` → `name: int32[N];`.
  - Class fields: `int32 age;` → `age: int32;`. Enum variant payloads: `Circle(float64 radius)` → `Circle(radius: float64)`.
  - `for`-loops: `for (int32 i = 0; ...)` → `for (i: int32 = 0; ...)`; `for (int32 x in xs)` → `for (x: int32 in xs)`.
  - A new `fn` keyword now introduces every callable — top-level functions, instance methods, static methods, and constructors — with a Rust-style `-> ReturnType` arrow: `int32 add(int32 a, int32 b) { }` → `fn add(a: int32, b: int32) -> int32 { }`. Constructors take `fn` too but never a return type: `ClassName(int32 x) { }` → `fn ClassName(x: int32) { }`.
  - Generators are no longer a distinct declaration form — `generator<int32> countdown(int32 n) { }` is now an ordinary function whose return type happens to be `generator<T>`: `fn countdown(n: int32) -> generator<int32> { }`.
  - Casts (`expr as Type`), match-arm bindings (`field: local`), and generic constraints (`T: int32 | float64`) were already postfix and are unchanged.
- `match` is now a reserved keyword. `@firescript/std.regex`'s `match(pattern, text)` function (added in 0.5.0) has been renamed to `find_match(pattern, text)` to avoid the collision; `is_match` is unaffected.
- The `-t`/`--target` flag (`native`/`web`) has been removed. It is replaced by two separate flags, `--platform` (`windows`, `linux`, `macos`, `bare-metal`) and `--arch` (`x86_64`, `i686`, `aarch64`, `armv7`, `riscv64`, `riscv32`), which can be combined for cross-compilation; either or both may be omitted to default to the host platform/architecture. Only `--platform windows --arch x86_64` is currently implemented — any other combination fails with a clear "unsupported target" error rather than compiling.
- Bare assignment to a name that was never declared (e.g. `w = Widget(7);` with no preceding `w: Widget = ...`) is no longer accepted as an implicit declaration. Every variable must now be explicitly declared with `name: Type = ...` before its first assignment or use; assigning to an undeclared name is a compile error (`FS-PARSE-0003`, undefined identifier).

### Bug Fixes
- Parser diagnostics that occur at end-of-file (no current token to anchor to, e.g. an incomplete trailing declaration) now report a real line/column — the last real token's position — instead of always reporting line 0, column 0. This anchor position is now also stable regardless of trailing comments in the source, and no longer depends on a stray comment token the parser hadn't yet skipped.
- Nullable variables, fields, and parameters are now declared with a trailing `?` after the name instead of a leading `nullable` keyword: `int a? = null;` instead of `nullable int a = null;`. The `nullable` keyword has been removed. This also applies to the generic-parameter constraint form (`class Option<T?>` instead of `class Option<nullable T>`).
- `export` followed only by a trailing comment (nothing else before end-of-file) no longer silently drops the "expected declaration after 'export'" diagnostic.
- `Option<T>`/`CopyableOption<T>` (and any other generic class imported from a different module) now correctly resolve method calls against the concrete instantiated type: `isSome()`/`isNone()` returned wrong results, and calling a generic class's method inline (e.g. as an `if` condition or directly as another call's argument) crashed the compiler. Both were the same root cause — method calls on an imported generic class resolved against the bare class name instead of its instantiation.
- Passing a generic function call directly as another call's argument (e.g. `println(max(3, 7))`, where `max<T>` is generic) no longer crashes with `LoweringError: cannot convert T to string` — the inner call's return type is now resolved to its concrete substituted type instead of the raw unsubstituted type parameter.
- On Windows, compiling or importing a file whose path is on a different drive letter than the current working directory (e.g. source under `C:\...\Temp\...` while running from a `D:\` checkout) no longer crashes with `ValueError: path is on mount 'X', start on mount 'Y'`. The relative path shown in diagnostics now falls back to the absolute path when a true relative path can't be computed.
- Passing an owned identifier as an enum variant's payload argument (e.g. `Slot.Holds(b)`) now correctly moves it, matching function/constructor/method calls. Previously the identifier was left live, so it was both dropped at its own scope exit *and* still reachable through the enum payload — a double-free/use-after-free that could silently read freed memory (observed as the payload's data going missing) depending on heap allocator behavior. Reusing the identifier after such a move is now also caught at compile time as a use-after-move error.
- A constructor declared with an `owned this` receiver (e.g. `fn Box(owned this, v: int32) { ... }`) no longer crashes with an internal "FIR verification failed (FIRV-O1): use of 'this', which is moved" error. The receiver's `this` was being auto-dropped at the end of the constructor body like an ordinary owned parameter, but a constructor always implicitly returns its own freshly-allocated `this` — the drop ran before that read.
- Calling through an aliased symbol import (`import module.symbol as alias;` ... `alias(...)`) no longer fails to compile with `LoweringError: call to unknown function <alias>`. The alias is now resolved back to the imported symbol's real name in every importing module, including the entry file.
- An owned local moved into an outer variable on only one arm of an `if`/`else` (e.g. a run-length-encoding accumulator: `if (c == last) { count++; } else { last = c; }`) no longer crashes the compiler with an internal FIR verifier error (`FIRV-O2`, "possibly moved on some paths") or silently leaks the variable on the other arm. This affected both ordinary owned locals and a `for (x: string in s)` loop variable moved out of the loop body this way, including when the conditional move isn't the last statement in the loop body (more code follows it) or isn't the last statement of its own branch. A single drop inserted after the whole `if`/`else` can't be correct when only one branch consumes the variable; the compiler now tracks each arm's ownership state independently (duplicating whatever code follows a conditionally-moving `if` into each of its branches, for the `for`-in-`string` loop-variable case, since a runtime flag can't be checked by the compiler's static ownership verifier) and drops (or doesn't) accordingly.
- A method call on a monomorphized generic class instance imported from another module (e.g. `vec.get(i)` on an imported `Vec<int32>`), whose method's declared return type is itself a bare type parameter (e.g. `T`), no longer produces a wrongly-typed value (previously stayed the unsubstituted `T`, later crashing FLIR lowering with `cannot convert T to string` if the result was ever passed to something needing a concrete type). The return type is now substituted using the receiver's concrete type arguments, matching the substitution already done for generic *fields* and (separately) generic *function* calls.
- A class method declared with no receiver parameter at all (neither `&this`, `&mut this`, nor plain `this`) on a class whose destructor does real work (has an owned field, or one decorated `@owns_elements`) no longer destroys the receiver on every call — the implicit receiver was being treated as an ordinary owned parameter and auto-dropped at the end of the method body. An omitted receiver on an Owned class now defaults to borrowed (read-only), matching every explicit form except `owned this`; a method that mutates a field without declaring `&mut this` is now correctly rejected at compile time instead of silently destroying the object it just mutated. (Copyable-class receivers are unaffected — they have no destructor to worry about.) `Option<T>.isSome()`/`isNone()` and other stdlib accessor methods that relied on the implicit-receiver form were affected by this bug and are fixed by this change.
- A generic class's own explicit `&this`/`&mut this` receivers (inside its own method bodies) no longer fail with "Cannot borrow Copyable type" — the bare template name's Owned/Copyable category (fixed at declaration, independent of eventual type arguments) is now registered immediately rather than only its concrete instantiations.
- `for`-in over a generator whose yield type is Owned (e.g. a generator yielding `Tuple<int32, T>`) no longer crashes the compiler with an internal FIR verifier error (`FIRV-O3`, "not consumed on every path") on the loop's normal fallthrough path — the per-iteration loop variable is now dropped at the end of each iteration, matching how owned locals are already dropped elsewhere. (`break`/`continue` out of such a loop remains an unhandled case; no existing code exercises it.)
- A generic generator function whose yield type is (or contains) a bare type parameter (e.g. `enumerate<T>`'s `generator<Tuple<int32, T>>`) no longer silently yields wrong values — every generic-class-shaped type string with an unresolved nested type argument (e.g. `Tuple<int32, T>`) was resolving the *outer* type correctly but never substituting the type parameters *inside* it, so the yielded struct's field layout used the wrong (generic-parameter-sized) offsets and read back adjacent zeroed memory. Also fixed: calling (or `for`-in-iterating) a generic generator function now correctly infers and monomorphizes its type arguments from the call's arguments, including when the parameter type is itself a generic class (`&v: Vec<T>` unifying against a `Vec<int32>` argument) — generators previously had no type-argument inference at all ("generators are concrete today").
- Comparing two values of the same generic type parameter with `==`/`!=` inside a *class* method body (e.g. `this.val == x` where both are the class's own `T`) no longer fails with "Cannot compare types T and T with '=='". A separate, later type-checking pass tracks which names are currently in scope as type parameters, but only ever pushed a *function's* own type parameters (empty for an ordinary, non-generic method) onto that scope, clobbering the *enclosing class's* type parameters for the duration of every method body — previously invisible because no existing generic class ever compared two values of its own type parameter.
- A generic class method calling *another method on the same instance* (e.g. `this._probe(key)` from within `HashMap<K,V>.set()`) now correctly monomorphizes the callee for the current instantiation, instead of silently calling the generic template's unspecialized (and differently-typed) version. A receiver parameter's declared type is always just the bare class name (`Vec`, `HashMap`), never `ClassName<Args>` — method-call lowering assumed the opposite, deriving the callee's type arguments from the receiver's own static type string, which only happened to work when the receiver was a local variable declared with a fully-written-out type (`v: Vec<int32>`). No existing generic class previously called one of its own methods from another.
- `drop(x)` (and the ownership-analysis-inserted implicit drops it models) no longer corrupts the heap when `x`'s concrete type turns out to be a primitive scalar (`int32`, `bool`, ...) rather than an Owned type — it silently tried to `HeapFree()` the raw bit pattern of the value as if it were a pointer. This was only reachable from generic code that calls `drop()` on a bare generic-type-parameter value regardless of whether the concrete instantiation is Owned or Copyable (e.g. `HashMap<K,V>.set()`'s `drop(key)` on an overwrite, needed only when `K` is Owned) — no existing code did this before `HashMap<K,V>`. `drop()` on a primitive is now a correct no-op, same as it already was for a `copyable class`.
- A `null` literal typed as a nullable *scalar* (e.g. `int32?`, reachable via a generic `Option<T>`/`HashMap<K,V>` instantiated with a primitive type argument) no longer fails to compile with a pointer/integer type mismatch — it's now lowered to that scalar type's zero value. Every previous use of `null` only ever involved a pointer-shaped nullable type (`string?`, a class, an array), where `null` is unambiguously the pointer value zero. This was the first step toward full nullable-scalar support, completed above ("Nullable *scalar* types...").
- A `null` argument passed to a nullable-scalar constructor, method, or function parameter is no longer wrongly rejected by the type checker with a spurious "expected `int32`, got `null`"-shaped error — the parameter-signature type strings the checker compares against never carried a nullable `?` marker (a pre-existing, previously-unobserved gap, since nothing produced a nullable-scalar parameter with real semantics before this release).
- Passing a definitely-present scalar value (e.g. a literal) to a nullable-scalar parameter (e.g. `int32` to an `int32?` parameter) no longer fails FIR-level verification with a type-mismatch internal compiler error.
- A generic class with no explicit constructor being allocated with substituted (non-generic-placeholder) field values — the internal mechanism `Option<T>`'s and other nullable-scalar-returning functions' machinery relies on — is no longer incorrectly rejected by the FIR verifier; it now substitutes the class's own generic parameters the same way field load/store already did.
- An identifier starting with `true`, `false`, or `null` as a prefix (e.g. `false_flag`, `nullable_count`) no longer fails to parse. The lexer's `BOOLEAN_LITERAL`/`NULL_LITERAL`/`VOID_LITERAL` token patterns were missing the trailing word-boundary every other keyword pattern has, so the literal keyword matched greedily as a prefix of the identifier, leaving the remainder to tokenize separately and break the surrounding statement.

## 0.5.0 - Kirin
*July 2, 2026*

### New Language Features
- Added generator functions with `generator<T>` syntax: lazy iterables that produce values on demand via `yield`. Generators compile to state-machine structs with resumable next-functions. User-defined generators and `for-in` loops over generators are both supported.
- Added `@firescript/std.ranges` standard library module with `range(end)`, `rangeFrom(start, end)`, and `rangeStep(start, end, step)` generators, enabling `for (i: int32 in range(5))` style loops.
- Added `char` type — a copyable, stack-allocated scalar representing a single character. Initialized with single-character string literals (`c: char = "A"`).
- Added character literal syntax with single quotes (`'A'`, `'\n'`).
- Added `&mut this` receiver syntax for mutable borrowing in methods. Methods can now declare `&this` for read-only access or `&mut this` for mutable access, with compiler enforcement preventing field mutation through read-only receivers.
- Added `string.length()` method, returning an `int32` count of characters.
- String concatenation now requires both operands to be strings (`string + string`). Implicit type conversion is no longer allowed; use explicit `as` casting instead (e.g., `"value: " + (42 as string)`).
- Added explicit module exports with top-level `export` declarations. Module symbols are private by default and imports can only access exported symbols.
- Added generic classes with multiple type parameters (e.g., `class Pair<T, U> { ... }`). Monomorphization is performed automatically at each use site.
- `Tuple<T, U>`, `CopyableTuple<T, U>`, `Option<T>`, and `CopyableOption<T>` are now provided by the standard library (`@firescript/std.types`).
- Added `@firescript/std.fs` with class-based file I/O centered on `File` objects and `FileResult` values, including `File` methods (`read`, `readBytes`, `writeAll`, `appendAll`, `exists`, `remove`, `renameTo`, `moveTo`) and result helpers (`ok`, `err_code`, `result_status`, `result_data`).
- Added `@firescript/std.regex` for regular-expression matching with `is_match(pattern, text)`, `match(pattern, text)`, `find_at(pattern, text, start_pos)`, and `last_error(pattern)`. The module also exports the `RegexPattern` class for constructing a pattern once and matching it repeatedly. Current syntax supports literals, escapes, `.`, anchors (`^`, `$`), grouping `(...)`, alternation `|`, quantifiers `* + ?`, and character classes (`[...]`, `[^...]`, basic ranges like `[a-z]`). `find_at` performs position-aware matching, returning the length of the match starting at `start_pos`, or `-1` if there is no match.
- Added `syscall_*` intrinsics (`syscall_open`, `syscall_read`, `syscall_write`, `syscall_close`, `syscall_remove`, `syscall_rename`, `syscall_move`) behind `directive enable_syscalls`. For standard library use only.
- Expanded `@firescript/std.cli.args` parsing helpers to support grouped short flags (for example `-abc`), `--name=value` / `-n=value` option forms, `--` terminator handling, and parsed positional value lookup.
- Added support for logical operators `&&`, `||`, and unary `!` in expressions and conditions.
- Added support for exponentiation operator `**`.
- Added sized array declarations with optional initializers (e.g., `int32[10]` or `int32[10] = [1, 2, 3]`). Arrays without explicit initializers are zero-initialized.
- Added string iteration in `for-in` loops (e.g., `for (ch: string in "hello")`), iterating over individual characters.
- Added string-to-numeric type casting via `as` operator (e.g., `("42" as int32)`, `("3.14" as float64)`).
- Added `@firescript/std.fcl` standard library module with FCL (FireScript Configuration Language) lexer for parsing configuration data.

### Breaking Changes
- **firescript now compiles with zero external dependencies — Python only.** The compiler lowers source through its own intermediate representations (FIR and FLIR), then assembles x86-64 machine code and writes the PE32+ executable itself: no C compiler, no assembler, no linker, no external programs are invoked at any stage. GCC/Clang and MinGW binutils (`as`/`ld`) are no longer used or required; the `--cc` flag and the `CC` environment variable have been removed, and `--emit c` is replaced by `--emit asm`.
- Native compilation currently targets **Windows x86_64 only**. Compiled binaries are freestanding, position-independent, ASLR-compatible (DYNAMICBASE/NXCOMPAT) PE32+ executables that import only `kernel32.dll`. Linux and macOS native targets are planned for a future release.
- The language runtime (strings, arrays, numeric formatting and parsing, process arguments, file syscalls) is now implemented in firescript itself (`std/internal/runtime.fire`) and compiled into every program.
- `float128` is now a true 16-byte IEEE 754 binary128 (quad-precision) type, implemented as a self-hosted soft-float runtime over pairs of 64-bit integers (no external libraries). Arithmetic (`+`, `-`, `*`, `/`, unary `-`), comparisons, and conversions to/from `float64`, integers, and decimal strings are correctly rounded (round-to-nearest-even), with full support for subnormals, signed zero, infinity, and NaN. Converting a `float128` to a string uses printf `%f` formatting with 6 fraction digits (e.g. `4.000000`).
- Removed built-in `input()` function.
- Modules now need to explicitly export symbols to be imported by other modules. Top-level declarations are private by default.
- String concatenation no longer performs implicit type conversion. Both operands must be strings; use explicit `as` casting for non-string values.

### Compiler improvements
- Added `--emit-fir` and `--emit-flir` flags to dump the compiler's intermediate representations (FIR and FLIR) for debugging.
- firescript binaries no longer link against GMP and MPFR; the libraries are no longer build dependencies.
- Standard library modules can now import sibling modules using short relative paths (e.g., `import tuple.Tuple;`).
- Golden runner now supports per-test command-line argument sidecars placed next to each source file (`tests/sources/<name>.args`).
- Compiler diagnostics are now unified under structured compile-time error objects across parser, semantic analysis, code generation, and `lint_text(...)`; this improves consistency of reported locations and diagnostics integrations (for example LSP).
- Added negative array indexing support for fixed-size arrays (currently for array literals and explicit array parameters) so `arr[-1]` resolves to the last element.
- Added fixed-size array utility methods `index(value)` and `count(value)`.
- Added class static methods via `static` declarations and `Type.method(...)` calls.
- Added `lint_text(source_text, file_path)` API for in-memory diagnostics without code generation.
- Added LSP implementation (`firescript/lsp_server.py`) via `pygls`.
- Added VS Code extension with syntax highlighting, bracket matching, comment toggling, and LSP diagnostics.

### Bug Fixes
- Fixed float-to-string conversion silently truncating at 31 characters for large magnitudes (e.g. `1e100 as string` now produces the full fixed-notation digits instead of a truncated prefix).
- Fixed `for-in` loops and `length()` calls on array function parameters.
- Fixed error caret positions for indented code.
- Semantic analysis errors now report exact source location with a caret.
- Semantic analysis now enforces ownership moves when passing Owned identifiers to class method parameters that are not borrowed.
- Semantic analysis now reports post-branch uses of Owned values that may have moved on another control-flow path.
- Semantic analysis now reports post-loop uses of Owned values that may have moved in `while`/`for`/`for-in` loop bodies.
- Semantic flow analysis now treats definitely terminating branches (`return`, `break`, `continue`) as non-continuing paths to reduce false-positive move diagnostics after `if` statements.
- Semantic analysis now rejects attempts to move borrowed values into owned variables or owned parameters.
- Semantic analysis now rejects returning direct borrowed projections (for example borrowed identifiers, field projections, and array projections) when they would escape callable scope as Owned values.
- Semantic analysis now enforces ownership moves for class constructor arguments in both `Type(args)` and `new Type(args)` forms.

## 0.4.0 - Phoenix
*February 2, 2026*

Starting with 0.4.0, releases will now be named.

### Breaking Changes

- Removed legacy numeric aliases: `int`, `float`, and `double`.
    - Use explicit-width types instead: `int8|16|32|64`, `uint8|16|32|64`, and `float32|64|128`.
    - Integer literals default to `int32` when unsuffixed.
    - No implicit numeric promotions. Arithmetic and comparisons require operands of the exact same type.
    - Modulo (`%`) is defined only for integer types.
- Beginning memory management implementation
- Remove type conversion functions in favor of future Java-style casting.
- Removed built-in `print()` function in favor of `std.io.print()` and `std.io.println()`.
- Arrays are now fixed-size. Future dynamic arrays will be in the standard library.
- Beginning of memory management implementation. See [Memory Management](docs/memory_management.md) for details.

### New Language Features

- Fixed-width numeric types across the board:
    - Integers: `int8`, `int16`, `int32`, `int64`, `uint8`, `uint16`, `uint32`, `uint64`.
    - Floats: `float32`, `float64`, `float128`.
- Literal suffixes for precise typing:
    - Integers: `i8/i16/i32/i64` and `u8/u16/u32/u64` (e.g., `42i8`, `7u32`).
    - Floats: `f32`, `f64`, `f128` (e.g., `3.14f32`, `2.0f64`, `1.0f128`).
- String concatenation remains supported via `+` between two strings.
- Initial support for classes
    - Class definitions with fields, methods, and constructors.
    - Object instantiation using `new` keyword.
    - Method calls on class instances.
    - Inheritance
- Imports
- Casting (rust-like syntax `(87 as int8)`)
    - Currently only supported for numeric->numeric casts, and built-in types to string.
- Generic functions
- `std.math` library with basic math functions like `abs`, `min`, `max`, etc.
- `std.io` library with `print` and `println` functions.
- C-style for loops and for-in loops.
- Added `--version` flag to the compiler for displaying version information.

### Compiler/Backend Improvements

- Name mangling in generated C code to prevent name collisions between multiple source files and built-in C functions.

## 0.3.0
*September 12, 2025*

### Breaking Changes

- **`int` type is a native int again.**
    * The `int` type is now a native `int64_t` type in the generated C code.
    * This change improves performance and reduces complexity in the generated code.
    * Arbitrary precision integer / decimal support has been removed from the core. Future optional library packages may re‑introduce them without impacting the core compiler.

### New Features

- **Function Definitions and Calls:**
    * Added support for defining functions.
    * Functions can be called by their name followed by parentheses.
    * Functions can accept parameters and return values.
    * Example:

```firescript
int add(int a, int b) {
    return a + b;
}
```

### Changes

- **Improved Variable Declaration Parsing:**
    * Enhanced the parser to better handle nullable and const variable declarations.
- **Improved Error Handling:**
    * Enhanced error messages for syntax and type errors.
    * More context provided in error messages to help identify issues.
- **Refactored if-else parsing:**
    * Improved the parsing logic for `if`, `else if`, and `else` statements.
    * Better support for nested conditional statements.
- **Enhanced print function:**
    * The `print` function correctly prints all primitive types.

## 0.2.0
*May 8, 2025*

### New Features

- **Improved Syntax Handling and Error Reporting:**
    * Refactored the lexer and parser for enhanced syntax handling
    * The lexer now correctly handles greater than (`>`) and less than (`<`) operators
    * The parser includes stricter checks for Abstract Syntax Tree (AST) node children to prevent unexpected errors from `None` values
    * Introduced new logic for parsing `if` and `while` statements to properly support nested structures
    * Improved error messages with more context for syntax errors

- **Memory Model Progress:**
    * Introduced an interim reference-counting mechanism for certain heap values (e.g., strings, arrays)
    * This is a stepping stone toward the planned ownership + deterministic drop model (see Memory Management documentation)
    * Improves leak resilience while compiler-based last-use drop insertion is under development
    * Dynamic array resource reclamation aligned with deterministic drop goals

- **Arbitrary Precision Integers:**
    * The `int` type is now represented using `mpz_t` in the generated code
    * Enables arbitrary precision integers for handling large numbers
    * Provides improved accuracy and reliability for complex calculations
    * No practical limit to integer size (constrained only by available memory)

- **Organized Build Outputs:**
    * Build outputs and temporary files are now stored in a dedicated `build` directory
    * Temporary files are specifically located under `build/temp`
    * Cleaner project structure with separate directories for source, documentation, and build artifacts

- **Expanded Array Operations:**
    * Added new array methods: `clear()` and improved `pop()` functionality
    * Enhanced array bounds checking for safer indexing operations
    * Optimized memory allocation for arrays to improve performance

- **More Operators:**
    * Added support for compound assignment operators: `+=`, `-=`, `*=`, `/=`, and `%=`
    * Added support for increment (`++`) and decrement (`--`) operators

### Bug Fixes

- Fixed parser issue causing incorrect handling of complex nested expressions
- Addressed memory leak in string operations when concatenating multiple strings
- Corrected type checking for nullable values in conditional statements
- Fixed compilation errors in C code generation for complex boolean expressions
- Resolved issue with array element access in while loop conditions

### Code Quality Improvements

- Comprehensive refactoring of the C code generator for improved maintainability
- Added more detailed debug logging throughout the compilation process
- Improved documentation with examples for all supported language features
- Enhanced test coverage with new test cases for core functionality

## 0.1.1
*January 2025*

*There is not a version 0.1.0 because of a versioning mishap during initial release.*

### New Features

- **Enhanced Variable Scoping:**
    * Strict enforcement of variable scoping rules
    * Prevention of variable shadowing to avoid common programming errors
    * Clear error messages for scope-related issues

- **Improved Type System:**
    * Comprehensive type checking for variable assignments
    * Type compatibility verification for expressions
    * Function and method call parameter validation
    * Support for nullable types with explicit declaration

- **Control Flow Structures:**
    * Basic implementation of `if`, `else if`, and `else` statements
    * Support for `while` loops with condition checking
    * `break` and `continue` statements in loops

- **Basic Standard Library:**
    * Implementation of essential built-in functions:
      * `print()` for output (note: later moved to standard library)
      * Type conversion functions (`toInt()`, `toFloat()`, `toString()`, etc.)
      * `typeof()` function for runtime type introspection

### Bug Fixes

- Resolved parsing issues for nested expressions
- Fixed incorrect operator precedence in complex expressions
- Addressed memory management issues in the runtime library

## 0.0.1
*November 2024*

### Initial Release

- **First Public Alpha:**
  * Basic language structure and syntax
  * Simple variable declarations with primitive types
  * Arithmetic and logical operations
  * First iteration of the compilation pipeline

- **Array Support:**
  * Initial implementation of arrays with literal initialization
  * Basic array operations: indexing, assignment
  * Simple array methods: `append()` and `insert()`

- **Compiler Infrastructure:**
  * Lexer for tokenizing source code
  * Parser for building the abstract syntax tree
  * Simple C code generator for compilation
  * Runtime library with basic functions