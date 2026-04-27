<img src="assets/firescript-logo.svg" alt="firescript logo" width="200"/>

[![Tests](https://github.com/alec-jensen/firescript/actions/workflows/test.yml/badge.svg)](https://github.com/alec-jensen/firescript/actions/workflows/test.yml)

# firescript

firescript is a statically and strongly typed programming language that compiles natively or to JavaScript + Wasm (planned, not yet implemented). It is designed to be simple, powerful, and easy to learn while remaining expressive for advanced applications.

*Disclaimer: firescript is currently in development and is not yet feature-complete. The language and compiler are subject to change. Not everything described in this document is implemented or working. Current builds may leak resources; the design goal is deterministic destruction via an ownership model.*

## Features

- **Static & Strong Typing:** Enhances code readability and reliability.
- **Simple Syntax:** Combines the best of C, Java, JavaScript, and Python.
- **Everything is Explicit:** No implicit conversions or hidden behavior.
- **Versatile Compilation:** Supports native binaries and JavaScript output.
- **Cohesive Design:** All parts of the language work seamlessly together.
- **Deterministic Ownership Model (planned):** Ownership, moves, borrows, and explicit cloning instead of a tracing garbage collector. See the [Memory Management Model](docs/reference/memory_management.md).

## Example

```firescript
import @firescript/std.io.println;

// Define a function that returns the nth Fibonacci number
int8 fibonacci(int8 n) {
    if n <= 1 {
        return n
    }
    return fibonacci(n - 1i8) + fibonacci(n - 2i8)
}

// Print the first 10 Fibonacci numbers
for (int8 i=0i8; i < 10i8; i++) {
    println(fibonacci(i))
}
```

## Platforms

firescript is cross-platform. Native compilation currently targets Windows, Linux, and macOS. A future JavaScript + Wasm target is planned for browser and Node.js environments.

Development happens primarily on Windows and Linux, and CI test coverage runs on Windows, Linux, and macOS.

## Build and Test Requirements

firescript compiles source code to C and then builds native binaries. Because of this, a C compiler is required for local builds and test runs:

- **Required:** GCC or Clang available on your `PATH`
- **Used by:** compiler output builds and `tests/run_tests.py`

On Linux/macOS, install GCC or Clang with your system package manager. On Windows, use MSYS2 (or another environment that provides GCC/Clang and related toolchain binaries on `PATH`).

## Getting Started

See the [Getting Started Guide](https://firescript.alecj.com/getting_started/) for installation and usage instructions.

## Documentation

Full documentation is available at: [https://alec-jensen.github.io/firescript/](https://firescript.alecj.com/)

## Contributing

Contributions are welcome! Please open an issue or submit a pull request on [GitHub](https://github.com/alec-jensen/firescript).

## License

firescript is released under the MIT License. See [LICENSE](LICENSE) for details.
