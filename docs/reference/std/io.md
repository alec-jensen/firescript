# Standard I/O (`std.io`)

The `std.io` module provides basic output utilities for printing values to standard output.

## Functions

### `print`

```firescript
fn print<T>(&value: T) -> void
```

Print a value to standard output without a trailing newline. The value is implicitly converted to a string.

**Parameters:**
- `value`: Any type (will be converted to string for output)

**Example:**

```firescript
import @firescript/std.io.print;

print("Hello");
print(42);
print(3.14);   // prints 3.140000
```

### `println`

```firescript
fn println<T>(&value: T) -> void
```

Print a value to standard output followed by a newline.

**Parameters:**
- `value`: Any type (will be converted to string for output)

**Example:**

```firescript
import @firescript/std.io.println;

println("Hello, World!");
println(100);
```

## Supported Types

Both `print` and `println` are generic and support all built-in types that can be converted to strings:

- Numeric types (`intN`, `uintN`, `floatN`)
- `bool`
- `char`
- `string`

## Notes

- Floating-point values print with six digits after the decimal point (`3.14` prints as `3.140000`).
- Both functions are generic and polymorphic; they infer the type from the argument.
- Output goes directly to standard output (stdout).
