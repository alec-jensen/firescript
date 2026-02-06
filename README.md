<img src="assets/firescript-logo.svg" alt="firescript logo" width="200"/>

[![Tests](https://github.com/alec-jensen/firescript/actions/workflows/test.yml/badge.svg)](https://github.com/alec-jensen/firescript/actions/workflows/test.yml)

# firescript

firescript is a statically and strongly typed programming language that compiles natively or to JavaScript + Wasm. It is designed to be simple, powerful, and easy to learn while remaining expressive for advanced applications.

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
import @firescript/std.io.{println};

// Define a function that returns the nth Fibonacci number
int8 fibonacci(int8 n) {
    if n <= 1 {
        return n
    }
    return fibonacci(n - 1) + fibonacci(n - 2)
}

// Print the first 10 Fibonacci numbers
for (int8 i : range(9)) {
    println(fibonacci(i))
}
```

## Getting Started

See the [Getting Started Guide](https://firescript.alecj.com/getting_started/) for installation and usage instructions.

## Documentation

Full documentation is available at: [https://alec-jensen.github.io/firescript/](https://firescript.alecj.com/)

## Contributing

Contributions are welcome! Please open an issue or submit a pull request on [GitHub](https://github.com/alec-jensen/firescript).

## License

firescript is released under the MIT License. See [LICENSE](LICENSE) for details.
