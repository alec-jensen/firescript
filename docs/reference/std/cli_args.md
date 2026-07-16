# Command-Line Arguments (`std.cli.args`)

The `std.cli.args` module provides utilities for parsing and accessing command-line arguments in a robust, convention-friendly way.

## Core Functions

### `argc()`

```firescript
fn argc() -> int32
```

Return the count of command-line arguments (including the program name).

### `argv_at(index: int32)`

```firescript
fn argv_at(index: int32) -> string
```

Get the argument at the specified index. Index 0 is the program name.

## Flag and Option Parsing

### `has_flag(name: string)`

```firescript
fn has_flag(name: string) -> bool
```

Check if a boolean flag was provided. Supports short form (`-x`) and long form (`--flag`), as well as grouped short flags (`-abc`).

**Parameters:**
- `name`: Flag name (without the dash prefix)

**Example:**

```firescript
import @firescript/std.cli.args.has_flag;

if (has_flag("verbose")) {
    println("Verbose mode enabled");
}

// Recognizes: -v, --verbose, or -xvyz (grouped flags)
```

### `has_flag_alias(long_name: string, short_name: string)`

```firescript
fn has_flag_alias(long_name: string, short_name: string) -> bool
```

Check if a flag was provided using a long or short alias.

**Example:**

```firescript
if (has_flag_alias("output", "o")) {
    println("Output flag recognized");
}

// Recognizes: -o, --output, or grouped forms
```

### `option_value(name: string, fallback: string)`

```firescript
fn option_value(name: string, fallback: string) -> string
```

Get the value for an option. Supports multiple syntaxes:
- `-n value`
- `--name value`
- `-n=value`
- `--name=value`

**Parameters:**
- `name`: Option name (without dashes)
- `fallback`: Value to return if option not provided

**Example:**

```firescript
import @firescript/std.cli.args.option_value;

output: string = option_value("output", "stdout");

// Recognizes:
//   -o file.txt
//   --output file.txt
//   -o=file.txt
//   --output=file.txt
```

### `option_value_alias(long_name: string, short_name: string, fallback: string)`

```firescript
fn option_value_alias(long_name: string, short_name: string, fallback: string) -> string
```

Get the value for an option providing long and short name aliases.

**Example:**

```firescript
port: string = option_value_alias("port", "p", "8080");
```

## Positional Arguments

### `positional(index: int32, fallback: string)`

```firescript
fn positional(index: int32, fallback: string) -> string
```

Get a positional argument by index (0-based, after the program name).

**Example:**

```firescript
import @firescript/std.cli.args.positional;

cmd: string = positional(0, "help");  // First positional arg
```

### `positional_value(index: int32, fallback: string)`

```firescript
fn positional_value(index: int32, fallback: string) -> string
```

Get the nth positional value, skipping options and flags. Respects `--` as the end of options.

**Example:**

```firescript
// For: prog --verbose file1 file2
// positional_value(0, ...) returns "file1"
// positional_value(1, ...) returns "file2"
```

## Syntax Support

The module recognizes standard CLI conventions:

- **Long flags:** `--verbose`, `--flag`
- **Short flags:** `-v`, `-f`
- **Grouped short flags:** `-abc` (equivalent to `-a -b -c`)
- **Options with values:**
  - `-n value`
  - `--name value`
  - `-n=value`
  - `--name=value`
  - Grouped short with value: `-abc` (where `b` takes a value in certain contexts)
- **End of options:** `--` stops processing flags; all following arguments are positional

## Example

```firescript
import @firescript/std.cli.args.argc;
import @firescript/std.cli.args.argv_at;
import @firescript/std.cli.args.has_flag;
import @firescript/std.cli.args.option_value;
import @firescript/std.cli.args.positional_value;
import @firescript/std.io.println;

// Program: myapp -v --output result.txt file.txt

if (has_flag("verbose") || has_flag("v")) {
    println("Verbose mode");
}

output: string = option_value("output", "a.out");
println("Output: " + output);

input: string = positional_value(0, "stdin");
println("Input: " + input);
```
