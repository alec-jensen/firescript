# firescript v0.3.0 Documentation

> This documentation is being used for the most part as a reference for planning the direction of the firescript language and its features. The compiler is still in early development, so many features are not yet implemented, or are implemented differently than described here. Nothing here should be considered final until the language reaches a stable 1.0.0 release.

This documentation is organized to help both newcomers and experienced developers understand and use the firescript language effectively.

## 1. Language Reference Manual

* [Type System](reference/type_system.md) - Formal definition of types, nullability, arrays
* [Scoping Rules](reference/scoping.md) - Variable visibility, lifetime, and scope creation
* [Control Flow](reference/control_flow.md) - Conditional statements and loops

## 2. Getting Started & Tutorials

* [Types & Variables](reference/variables.md) - Basic variable declarations and types
* [Arrays](reference/arrays.md) - Working with array data structures
* [Functions & Methods](reference/functions.md) - Built-in functions and user-defined functions

## 3. Language Features

* [Classes & Inheritance](reference/classes.md) - Object-oriented programming fundamentals

## 4. Standard Library Reference

Standard library does not yet exist.

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

* ❌ Some types are supported: Copyable types (`bool`, `char`), Owned types (`string`, arrays), and numeric types (`intN`, `floatN`) are planned.
* ✅ Static type checking for expressions and assignments.
* ✅ Built-in functions: `print`, `input`, and type conversions.
* ❌ User-defined functions are not yet implemented.
* ❌ Classes and inheritance are planned but not implemented.
* ❌ Advanced array features like slicing and negative indices are not supported.
* ❌ Control flow is limited to `if`/`else` and `while` loops; `for` loops and `switch` statements are not implemented.
