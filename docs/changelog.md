# Changelog

firescript follows [Semantic Versioning](https://semver.org/). This makes it easier to understand the impact of changes in each release.

## 0.6.0 - Griffin (Currently in Development)

### New Language Features
- Added `enum` declarations, e.g. `enum Shape { Circle(float64 radius), Rectangle(float64 width, float64 height), Point }`. Enums are owned types (heap-allocated, like classes without an explicit `copyable` annotation), lowered to a tagged-union layout where variants share the same payload storage. Variants are constructed with `EnumName.Variant` / `EnumName.Variant(args...)` syntax (e.g. `Color.Red`, `Shape.Circle(3.0)`); construction is positional, in declaration order. Payload fields may be any type, including owned types (`string`, classes, other enums) — owned payload data is correctly dropped when the active variant goes out of scope, and only the active variant's fields are ever freed. Generic enums (`enum Foo<T>`) are not yet supported and produce a clear compile error rather than miscompiling.
- Added `match` as a reserved keyword and `match <expr> { <pattern> -> <body>, ... }` expressions, for destructuring `enum` values. Patterns match a bare `EnumName.Variant`, a payload-carrying `EnumName.Variant(bindings...)`, or a wildcard `_`. Payload bindings resolve by the variant's declared field name (`Circle(radius) -> ...`), not position, and can be renamed with `field: local` (`Circle(radius: r) -> ...`); a field can be left out of the pattern entirely if the arm doesn't need it. Match is exhaustiveness-checked at compile time: every variant must be covered by an arm, or a trailing `_` wildcard arm must be present; duplicate arms for the same variant, a wildcard arm followed by more arms, and patterns naming a field the variant doesn't declare (or binding the same field twice) are all compile errors. Payload bindings are read-only borrows scoped to their arm. `match` works both as a statement (arm bodies are `{ }` blocks) and, when every arm body is a plain expression, as a value-producing expression usable in a `return` or a variable initializer.

### Breaking Changes
- firescript now uses **postfix type declarations** everywhere, Rust/TypeScript-style, instead of the previous C-style prefix syntax. This is a whole-language syntax change:
  - Variables and constants: `int32 a = 5;` → `a: int32 = 5;`; `const float64 PI = 3.14;` → `const PI: float64 = 3.14;`.
  - Nullable markers move to the type: `int32 a? = null;` → `a: int32? = null;`.
  - Ownership/borrow modifiers move to the type, right after the colon: `owned Type name` → `name: owned Type`; `&Type name` → `name: &Type`; `&mut Type name` → `name: &mut Type`.
  - Arrays stay attached to the type as a unit: `int32[N] name;` → `name: int32[N];`.
  - Class fields: `int32 age;` → `age: int32;`. Enum variant payloads: `Circle(float64 radius)` → `Circle(radius: float64)`.
  - `for`-loops: `for (int32 i = 0; ...)` → `for (i: int32 = 0; ...)`; `for (int32 x in xs)` → `for (x: int32 in xs)`.
  - A new `fn` keyword now introduces every callable — top-level functions, instance methods, static methods, and constructors — with a Rust-style `-> ReturnType` arrow: `int32 add(int32 a, int32 b) { }` → `fn add(a: int32, b: int32) -> int32 { }`. Constructors take `fn` too but never a return type: `ClassName(int32 x) { }` → `fn ClassName(x: int32) { }`.
  - Generators are no longer a distinct declaration form — `generator<int32> countdown(int32 n) { }` is now an ordinary function whose return type happens to be `generator<T>`: `fn countdown(n: int32) -> generator<int32> { }`.
  - Casts (`expr as Type`), match-arm bindings (`field: local`), and generic constraints (`T: int32 | float64`) were already postfix and are unchanged.
- `match` is now a reserved keyword. `@firescript/std.regex`'s `match(pattern, text)` function (added in 0.5.0) has been renamed to `find_match(pattern, text)` to avoid the collision; `is_match` is unaffected.
- The `-t`/`--target` flag (`native`/`web`) has been removed. It is replaced by two separate flags, `--platform` (`windows`, `linux`, `macos`, `bare-metal`) and `--arch` (`x86_64`, `i686`, `aarch64`, `armv7`, `riscv64`, `riscv32`), which can be combined for cross-compilation; either or both may be omitted to default to the host platform/architecture. Only `--platform windows --arch x86_64` is currently implemented — any other combination fails with a clear "unsupported target" error rather than compiling.

### Bug Fixes
- Parser diagnostics that occur at end-of-file (no current token to anchor to, e.g. an incomplete trailing declaration) now report a real line/column — the last real token's position — instead of always reporting line 0, column 0. This anchor position is now also stable regardless of trailing comments in the source, and no longer depends on a stray comment token the parser hadn't yet skipped.
- Nullable variables, fields, and parameters are now declared with a trailing `?` after the name instead of a leading `nullable` keyword: `int a? = null;` instead of `nullable int a = null;`. The `nullable` keyword has been removed. This also applies to the generic-parameter constraint form (`class Option<T?>` instead of `class Option<nullable T>`).
- `export` followed only by a trailing comment (nothing else before end-of-file) no longer silently drops the "expected declaration after 'export'" diagnostic.
- `Option<T>`/`CopyableOption<T>` (and any other generic class imported from a different module) now correctly resolve method calls against the concrete instantiated type: `isSome()`/`isNone()` returned wrong results, and calling a generic class's method inline (e.g. as an `if` condition or directly as another call's argument) crashed the compiler. Both were the same root cause — method calls on an imported generic class resolved against the bare class name instead of its instantiation.
- Passing a generic function call directly as another call's argument (e.g. `println(max(3, 7))`, where `max<T>` is generic) no longer crashes with `LoweringError: cannot convert T to string` — the inner call's return type is now resolved to its concrete substituted type instead of the raw unsubstituted type parameter.
- On Windows, compiling or importing a file whose path is on a different drive letter than the current working directory (e.g. source under `C:\...\Temp\...` while running from a `D:\` checkout) no longer crashes with `ValueError: path is on mount 'X', start on mount 'Y'`. The relative path shown in diagnostics now falls back to the absolute path when a true relative path can't be computed.
- Passing an owned identifier as an enum variant's payload argument (e.g. `Slot.Holds(b)`) now correctly moves it, matching function/constructor/method calls. Previously the identifier was left live, so it was both dropped at its own scope exit *and* still reachable through the enum payload — a double-free/use-after-free that could silently read freed memory (observed as the payload's data going missing) depending on heap allocator behavior. Reusing the identifier after such a move is now also caught at compile time as a use-after-move error.

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