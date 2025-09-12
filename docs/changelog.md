# Changelog

firescript follows [Semantic Versioning](https://semver.org/). This makes it easier to understand the impact of changes in each release.

## 0.3.0 (Sep 12 2025)

### Breaking Changes

- **`int` type is a native int again.**
    * The `int` type is now a native `int64_t` type in the generated C code.
    * This change improves performance and reduces complexity in the generated code.
    * Arbitrary precision integer / decimal support has been removed from the core. Future optional library packages may re‑introduce them without impacting the core compiler.

### New Features

- **Function Definitions and Calls:**
    * Added support for defining functions.
    * Functions can be called by their name followed by parentheses.
    * Functions can accept parameters and return values.
    * Example:

    ```firescript
    int add(int a, int b) {
        return a + b;
    }```

### Changes

- **Improved Variable Declaration Parsing:**
    * Enhanced the parser to better handle nullable and const variable declarations.
- **Improved Error Handling:**
    * Enhanced error messages for syntax and type errors.
    * More context provided in error messages to help identify issues.
- **Refactored if-else parsing:**
    * Improved the parsing logic for `if`, `else if`, and `else` statements.
    * Better support for nested conditional statements.
- **Enhanced print function:**
    * The `print` function correctly prints all primitive types.

## 0.2.0 (May 8 2025)

### New Features

- **Improved Syntax Handling and Error Reporting:**
    * Refactored the lexer and parser for enhanced syntax handling
    * The lexer now correctly handles greater than (`>`) and less than (`<`) operators
    * The parser includes stricter checks for Abstract Syntax Tree (AST) node children to prevent unexpected errors from `None` values
    * Introduced new logic for parsing `if` and `while` statements to properly support nested structures
    * Improved error messages with more context for syntax errors

- **Enhanced Memory Management:**
    * Added a new reference counter for automated memory management
    * Currently runs in the runtime, with plans to move to the compiler in future versions
    * Helps prevent memory leaks and dangling pointers in the generated code
    * Improved garbage collection for dynamic arrays

- **Arbitrary Precision Integers:**
    * The `int` type is now represented using `mpz_t` in the generated code
    * Enables arbitrary precision integers for handling large numbers
    * Provides improved accuracy and reliability for complex calculations
    * No practical limit to integer size (constrained only by available memory)

- **Organized Build Outputs:**
    * Build outputs and temporary files are now stored in a dedicated `build` directory
    * Temporary files are specifically located under `build/temp`
    * Cleaner project structure with separate directories for source, documentation, and build artifacts

- **Expanded Array Operations:**
    * Added new array methods: `clear()` and improved `pop()` functionality
    * Enhanced array bounds checking for safer indexing operations
    * Optimized memory allocation for arrays to improve performance

- **More Operators:**
    * Added support for compound assignment operators: `+=`, `-=`, `*=`, `/=`, and `%=`
    * Added support for increment (`++`) and decrement (`--`) operators

### Bug Fixes

- Fixed parser issue causing incorrect handling of complex nested expressions
- Addressed memory leak in string operations when concatenating multiple strings
- Corrected type checking for nullable values in conditional statements
- Fixed compilation errors in C code generation for complex boolean expressions
- Resolved issue with array element access in while loop conditions

### Code Quality Improvements

- Comprehensive refactoring of the C code generator for improved maintainability
- Added more detailed debug logging throughout the compilation process
- Improved documentation with examples for all supported language features
- Enhanced test coverage with new test cases for core functionality

## 0.1.1 (January 2025)

*There is not a version 0.1.0 because of a versioning mishap during initial release.*

### New Features

- **Enhanced Variable Scoping:**
    * Strict enforcement of variable scoping rules
    * Prevention of variable shadowing to avoid common programming errors
    * Clear error messages for scope-related issues

- **Improved Type System:**
    * Comprehensive type checking for variable assignments
    * Type compatibility verification for expressions
    * Function and method call parameter validation
    * Support for nullable types with explicit declaration

- **Control Flow Structures:**
    * Basic implementation of `if`, `else if`, and `else` statements
    * Support for `while` loops with condition checking
    * `break` and `continue` statements in loops

- **Basic Standard Library:**
    * Implementation of essential built-in functions:
      * `print()` for output
      * `input()` for user input
      * Type conversion functions (`toInt()`, `toFloat()`, `toString()`, etc.)
      * `typeof()` function for runtime type introspection

### Bug Fixes

- Resolved parsing issues for nested expressions
- Fixed incorrect operator precedence in complex expressions
- Addressed memory management issues in the runtime library

## 0.0.1 (November 2024)

### Initial Release

- **First Public Alpha:**
  * Basic language structure and syntax
  * Simple variable declarations with primitive types
  * Arithmetic and logical operations
  * First iteration of the compilation pipeline

- **Array Support:**
  * Initial implementation of arrays with literal initialization
  * Basic array operations: indexing, assignment
  * Simple array methods: `append()` and `insert()`

- **Compiler Infrastructure:**
  * Lexer for tokenizing source code
  * Parser for building the abstract syntax tree
  * Simple C code generator for compilation
  * Runtime library with basic functions

## Roadmap for Future Releases

### Planned for Version 0.3.0

- Implementation of user-defined functions
- Enhanced array operations including slicing and negative indices
- For loop implementations (C-style, for-in, range loops)
- Better error recovery during compilation
- Performance optimizations for generated code

### Planned for Version 0.4.0

- Basic class system with instance fields and methods
- Improved standard library with more built-in functions
- Support for importing code from other files
- Optional and named function parameters

### Long-term Goals

- Full object-oriented programming support with inheritance
- Module system for code organization
- Tuple types and operations
- Generic type parameters
- First-class functions and closures
- Additional language tooling (formatter, linter, debugger)