# Language Reference Overview

> This section provides a comprehensive reference for the firescript programming language. firescript is a statically and strongly typed language that prioritizes readability, explicitness, and predictable behavior.

## Core Design Principles

firescript's design follows several key principles:

- **Static & Strong Typing**: Every variable has a defined type that is checked at compile-time
- **Explicit Behavior**: No implicit type conversions or hidden behaviors
- **Simple Syntax**: Draws inspiration from C, Java, JavaScript, and Python
- **Consistent Rules**: Language constructs follow consistent patterns
- **Predictable Execution**: Code behaves as written, minimizing surprises

## Implementation Status

The firescript compiler is under active development. Current status:

| Feature | Status | Notes |
|---------|--------|-------|
| Copyable Types | [IMPLEMENTED] | `bool`, `char`, `intN`, `floatN` (stack-allocated scalars) |
| Owned Types | [IMPLEMENTED] | `string`, arrays, user-defined classes (heap-allocated with move semantics) |
| Memory Model | [IMPLEMENTED] | Ownership, moves, borrows, and deterministic drop insertion are enforced by the compiler. See [Memory Management](memory_management.md). |
| Control Flow | [IMPLEMENTED] | `if`/`else if`/`else`, `while`, C-style `for`, `for-in` (arrays, strings, generators), `break`/`continue`. Range loops via `@firescript/std.ranges`. |
| Functions | [IMPLEMENTED] | Parameters, return values, recursion, generic functions, generators |
| Classes | [IMPLEMENTED] | Fields, methods, constructors, inheritance, static methods, generic classes |
| Modules | [IMPLEMENTED] | Imports with explicit export visibility (private by default) |

## Getting Started

For those new to firescript, we recommend starting with the following guides:

1. [Types & Variables](variables.md) - Learn how to declare and use variables
2. [Arrays](arrays.md) - Working with collections of data
3. [Control Flow](control_flow.md) - Conditionals and loops
4. [Functions & Methods](functions.md) - Using built-in functions

## Detailed Reference

For more detailed information, each section of this reference covers specific aspects of the language:

- [Type System](type_system.md) - Comprehensive information about the firescript type system
- [Scoping Rules](scoping.md) - How variable scoping works
- [Classes & Inheritance](classes.md) - Object-oriented programming

## Example Code

```firescript
import @firescript/std.io.println;

// Calculate fibonacci numbers
int32 i = 0;
int32 j = 1;
int32 count = 10;

println("Fibonacci Sequence:");
println(i);
println(j);

while (count > 0) {
    int32 next = i + j;
    println(next);
    i = j;
    j = next;
    count = count - 1;
}
```