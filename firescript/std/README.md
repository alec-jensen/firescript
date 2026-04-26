# firescript standard library

This directory contains the standard library for FireScript, providing essential modules and utilities for FireScript programs.

## standard library modules
- `std.math`: Mathematical functions and constants.
- `std.io`: Input and output utilities.
- `std.fs`: File I/O utilities backed by syscall wrappers, centered on `File` object methods (`read`, `readBytes`, `writeAll`, `appendAll`, `exists`, `remove`, `renameTo`, `moveTo`) with `FileResult` helper accessors.
- `std.regex`: Regular-expression matching helpers (`is_match`, `match`, `last_error`) for full-string pattern matching.