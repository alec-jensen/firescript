# Language Reference Overview

This section provides a comprehensive reference for the firescript programming language. firescript is a statically and strongly typed language that prioritizes readability, explicitness, and predictable behavior.

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
| Primitive Types | ✅ Complete | `int`, `float`, `double`, `bool`, `string`, `char` |
| Arrays | ⚠️ Partial | Basic operations work; slicing not implemented |
| Control Flow | ⚠️ Partial | `if/else` and `while` loops work; `for` loops planned |
| Functions | ⚠️ Partial | Built-in functions work; user-defined functions planned |
| Classes | ❌ Planned | Object-oriented features planned for future versions |
| Modules | ❌ Planned | Code organization across files planned for future versions |

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
- [Classes & Inheritance](classes.md) - Object-oriented programming (future)

## Example Code

```firescript
// Calculate fibonacci numbers
int i = 0;
int j = 1;
int count = 10;

print("Fibonacci Sequence:");
print(i);
print(j);

while (count > 0) {
    int next = i + j;
    print(next);
    i = j;
    j = next;
    count = count - 1;
}
```

For the complete language specification, see the [Language Specification](../language_specification.md) document.