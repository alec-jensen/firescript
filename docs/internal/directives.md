# compiler directives

compiler directives are special instructions to the compiler that affect compilation behavior. They are not part of the runtime language and do not produce any code themselves.

Directives are not intended to be used in source files except in specific scenarios (e.g., enabling syscalls in the standard library). They are primarily for internal use by the compiler and standard library.

## Directive Syntax

```firescript
directive <name> [<arg1> [, <arg2> ...]];
```

- `directive` keyword starts the directive.
- `<name>` is the name of the directive (e.g., `enable_syscalls`).
- Optional arguments can be provided, separated by commas.

### Examples

- Enable syscalls in a file:

```firescript
directive enable_syscalls;
```

## Available Directives

- `enable_syscalls`: Allows the use of syscalls in the file. This is required for files in the standard library that need syscall access.