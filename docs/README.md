# firescript v0.2.0 Documentation

**Note:** The current compiler does not support all language features. Unsupported features are explicitly marked in each guide with **Not yet implemented** or **Note**.

This documentation is organized to help both newcomers and experienced developers understand and use the firescript language effectively.

## 1. Language Reference Manual

* [Type System](type_system.md) - Formal definition of types, nullability, arrays
* [Scoping Rules](scoping.md) - Variable visibility, lifetime, and scope creation
* [Control Flow](control_flow.md) - Conditional statements and loops

## 2. Getting Started & Tutorials

* [Types & Variables](variables.md) - Basic variable declarations and types
* [Arrays](arrays.md) - Working with array data structures
* [Functions & Methods](functions.md) - Built-in functions and user-defined functions

## 3. Language Features

* [Classes & Inheritance](classes.md) - Object-oriented programming fundamentals

## 4. Standard Library Reference

* Built-in functions: `print`, `input`, `toInt`, `toFloat`, etc.
* Array operations: `append`, `insert`, `pop`, `clear`, `length`

## 5. Examples

Check the `/examples` directory for complete code samples:

* Basic usage of built-in functions
* Fibonacci sequence implementation
* Array manipulation
* Scope and variable visibility demonstrations

## 6. Changelog

For the latest updates and changes to the firescript language, see the [changelog](changelog.md).

---

### Implementation Status

firescript is under active development. Key limitations in the current compiler version:

* ✅ Primitive types (`int`, `float`, `double`, `bool`, `string`, `char`) are fully supported.
* ✅ Arrays support basic operations: `append`, `insert`, `pop`, `clear`, and `length`.
* ✅ Static type checking for expressions and assignments.
* ✅ Built-in functions: `print`, `input`, type conversions, and `typeof`.
* ❌ User-defined functions are not yet implemented.
* ❌ Classes and inheritance are planned but not implemented.
* ❌ Advanced array features like slicing and negative indices are not supported.
* ❌ Control flow is limited to `if`/`else` and `while` loops; `for` loops and `switch` statements are not implemented.
