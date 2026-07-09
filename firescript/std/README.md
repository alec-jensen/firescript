# firescript standard library

This directory contains the standard library for firescript, providing essential modules and utilities for firescript programs.

## standard library modules
- `std.io`: Output utilities (`print`, `println`).
- `std.math`: Mathematical utilities (`abs`, `min`, `max`, `clamp` exported; more in development).
- `std.fs`: File I/O utilities backed by syscall wrappers, centered on `File` object methods (`read`, `readBytes`, `writeAll`, `appendAll`, `exists`, `remove`, `renameTo`, `moveTo`) with `FileResult` helper accessors.
- `std.regex`: Regular-expression matching helpers (`is_match`, `match`, `find_at`, `last_error`) plus the `RegexPattern` class, with anchor (`^`/`$`) support.
- `std.types`: Generic container types (`Tuple`, `CopyableTuple`, `Option`, `CopyableOption`).
- `std.ranges`: `range`, `rangeFrom`, and `rangeStep` generators for counting loops.
- `std.cli.args`: Command-line argument parsing (`argc`, `argv_at`, flags, options, positionals).
- `std.fcl`: Lexer for firescript config language (FCL) data.
- `std.constraints`: Common generic constraint aliases (in development; not yet exported).
- `std.internal`: The firescript-implemented language runtime (`runtime.fire`, `float128.fire`). Not for user code.
