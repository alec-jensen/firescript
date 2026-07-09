# Error Handling

firescript is designed in a way that minimizes runtime errors through static type checking and compile-time validation. However, some errors can still occur during execution, such as division by zero or out-of-bounds array access.

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

### Runtime Traps

Runtime errors terminate the program with an error. For example, arithmetic on fixed-size integers that exceeds the representable range traps at runtime rather than silently wrapping:

```firescript
int8 max = 127i8;
int8 overflow = max + 1i8;  // Runtime error: integer overflow
```

Overflows that can be detected at compile time (constant expressions) are reported as compile-time errors instead.

### Result Types in the Standard Library

For recoverable errors — currently file-system operations — the standard library uses result values instead of exceptions. Operations return a result object whose status you check explicitly:

```firescript
import @firescript/std.fs.File;
import @firescript/std.io.println;

File f = File("data.txt");
FileResult r = f.read();
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
    int8 result = 10 / 0;
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
