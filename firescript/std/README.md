# firescript standard library

This directory contains the standard library for firescript, providing essential modules and utilities for firescript programs.

## standard library modules
- `std.io`: Output utilities (`print`, `println`).
- `std.math`: Mathematical utilities (`abs`, `min`, `max`, `clamp` exported; more in development).
- `std.fs`: File I/O utilities backed by syscall wrappers, centered on `File` object methods (`read`, `readBytes`, `writeAll`, `appendAll`, `exists`, `remove`, `renameTo`, `moveTo`) with `FileResult` helper accessors.
- `std.regex`: Regular-expression matching helpers (`is_match`, `match`, `find_at`, `last_error`) plus the `RegexPattern` class, with anchor (`^`/`$`) support.
- `std.types`: Generic container types (`Tuple`, `CopyableTuple`, `Option`, `CopyableOption`).
- `std.collections`: `Vec<T>`, a dynamically-growable array (`push`, `pop`, `get`, `set`, `length`/`size`, `enumerate<T>`), and `HashMap<K,V>`, an open-addressing hash table (`set`, `get`, `has`, `remove`, `length`/`size`; keys restricted to integer types, `bool`, `char`, `string`).
- `std.ranges`: `range`, `rangeFrom`, and `rangeStep` generators for counting loops.
- `std.cli.args`: Command-line argument parsing (`argc`, `argv_at`, flags, options, positionals).
- `std.fcl`: Lexer for firescript config language (FCL) data.
- `std.constraints`: Common generic constraint aliases (in development; not yet exported).
- `std.internal`: The firescript-implemented language runtime. Not for user code. Split by concern rather than one file: `alloc.fire` (heap/allocation registry), `arithmetic.fire` (`**` operator support), `strings.fire` (string primitives), `number_conversions.fire` (int/bool/char <-> string), `float_conversions.fire` (float <-> string, exact decimal), `io.fire` (stdout, process args), `syscalls.fire` (file-descriptor syscalls, `SyscallResult`), `builtin_arrays.fire` (array dot-methods), `float128.fire` (binary128 soft-float). Every std/internal/*.fire file is merged into every program with no user import, and any file may call any other's functions with no import between them either (see `firescript/main.py`'s `_collect_internal_signatures`/`_runtime_fir_module`). Functions here tagged `@builtin_method("family", "name")` (gated by `directive enable_builtin_methods;`) become dot-methods on that primitive family (`string`, `array`) for every program -- see `firescript/builtin_methods.py`.
