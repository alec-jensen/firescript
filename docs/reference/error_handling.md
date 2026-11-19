# Error Handling

firescript is designed in a way that minimizes runtime errors through static type checking and compile-time validation. However, some errors can still occur during execution, such as integer overflow, division by zero or out-of-bounds array access; these trap (see below).

## Error Types

1. **Syntax Errors**: Caught at compile-time, these errors occur when the code is not well-formed.
2. **Type Errors**: Also caught at compile-time, these occur when operations are applied to incompatible types.
3. **Ownership Errors**: Caught at compile-time — use-after-move, illegal borrows, and borrow escapes are rejected by the compiler (see [Memory Management](memory_management.md)).
4. **Runtime Errors**: These occur during execution and can include:
   - Integer overflow and underflow
   - Division by zero
   - Null reference access
   - Array index out of bounds

## Current Behavior [IMPLEMENTED]

### Compile-Time Diagnostics

Most errors are caught before the program ever runs. The compiler reports structured diagnostics with exact source locations:

```text
[ERROR] --- Cannot assign string to variable of type int8
> int8 age = "thirty";
             ^
(main.fire:3:12)
```

### Runtime Traps [IMPLEMENTED]

firescript's model is safety: operations that would silently produce a wrong value instead **trap**. A trap writes one line to standard error and terminates the program with exit status **101**. No destructors run and nothing is unwound.

```text
firescript runtime error: <Kind>: <detail>
```

Every trap, whatever its cause, goes through a single runtime entry point (`fs_rt_trap` in `std/internal/trap.fire`); the compiler emits each check as a branch to a cold block that calls it. The trap kinds are:

| Kind | Raised by | Detail |
|---|---|---|
| `IntegerOverflow` | `+`, `-`, `*`, unary `-`, `++`, `--`, compound assignment, and `**` whose exact result does not fit the integer type; signed `MIN / -1` and `MIN % -1` | operation and type, e.g. `addition on int8` |
| `DivisionByZero` | integer `/` or `%` with a zero divisor | operation and type, e.g. `division on int32` |
| `InvalidArgument` | a negative exponent in integer `**` | e.g. `negative exponent in integer exponentiation` |

```firescript
max: int8 = 127i8;
overflow: int8 = max + 1i8;  // firescript runtime error: IntegerOverflow: addition on int8  (exit status 101)
```

The checks apply to every integer width (`int8`..`int64`, `uint8`..`uint64`). Floating-point arithmetic is not trapped: it follows IEEE 754 (`Infinity`, `NaN`). Narrowing `as` casts **between integer types** (e.g. `300 as int8`) are explicit truncation and do not trap (see [Type System](type_system.md)).

Overflows that can be detected at compile time (constant expressions) are reported as compile-time errors instead.

#### Explicit wrapping operations [IMPLEMENTED]

Code that really wants modular arithmetic uses `wrapping_add`, `wrapping_sub`, `wrapping_mul` and `wrapping_neg` from `@firescript/std.math.wrapping` (see [Math](std/math.md)). Saturating and checked (`Option<T>`-returning) variants are [PLANNED].

#### Catchable exceptions [PLANNED]

In a later release (0.9.0) these traps become catchable exceptions (for example `ArithmeticException` and `IndexOutOfBoundsException`, subclasses of a language-level `Exception`), and debug builds will print stack traces. Because every trap already goes through one entry point and each check is a branch to a cold block, that change replaces only the body of the entry point. Until then, traps always terminate the program as described above.

### Result Types in the Standard Library

For recoverable errors — currently file-system operations — the standard library uses result values instead of exceptions. Operations return a result object whose status you check explicitly:

```firescript
import @firescript/std.fs.File;
import @firescript/std.io.println;

f: File = File("data.txt");
r: FileResult = f.read();
if (r.ok()) {
    println(r.result_data());
} else {
    println("read failed with error code " + (r.err_code() as string));
}
```

See [File System (`std.fs`)](std/fs.md) for details. A general-purpose `Result<T, E>` type for the standard library is planned.

## Planned Error Handling Features [PLANNED]

The following mechanisms are designed but **not yet implemented** — this code will not compile today:

- **Try/Catch Blocks**:

```firescript
// Future syntax
try {
    result: int8 = 10 / 0;
} catch (DivisionByZeroError e) {
    print("Error: " + e.message);
}
```

- **Assertions**:

```firescript
// Future syntax
assert(x > 0, "x must be positive");
```

## Best Practices

- Always validate user input to prevent errors.
- Check result statuses (e.g., `FileResult.ok()`) after fallible operations.
- Write tests to catch errors early in the development process.
