# Standard Library Overview

firescript includes a standard library under the `@firescript/std` namespace, providing utilities for common programming tasks.

## Guide to Modules

- [I/O](io.md): Formatted output with `print` and `println`
- [File System](fs.md): File operations via the `File` class and `FileResult` helpers
- [Math](math.md): Mathematical constants and functions
- [Regex](regex.md): Full-string regular-expression matching and pattern validation
- [Command-Line Arguments](cli_args.md): Argument parsing for CLI programs
- [Types](types.md): Generic container types (`Tuple`, `Option`)
- FCL Lexer: Lexer for parsing FireScript Configuration Language (FCL) data

## Importing

Standard library modules are imported using `@firescript/std` namespace syntax:

```firescript
import @firescript/std.io.println;
import @firescript/std.fs.File;
import @firescript/std.math.PI64;
import @firescript/std.fcl.next_token;  // FCL lexer
```

You can also import at the module level:

```firescript
import @firescript/std.io;  // imports all I/O exports
import @firescript/std.fcl;  // imports all FCL lexer functions
```

Or use wildcard imports:

```firescript
import @firescript/std.types.*;  // imports Tuple, Option, etc.
```

## Error Handling

Most file-system operations return result types (e.g., `FileResult`) that encode success/failure in a `status` field. Check the [File System](fs.md) module for details on error semantics and `FileResult` methods like `ok()`.

## Best Practices

- **Prefer stdlib over syscalls**: User code should use standard library modules, not low-level syscalls (which require `directive enable_syscalls`).
- **Explicit imports**: Import specific symbols to avoid namespace pollution and make dependencies clear.
- **Check result status**: Always inspect result types after file operations to handle errors robustly.
