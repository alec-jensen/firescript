# firescript

firescript is a statically and strongly typed programming language that compiles natively or to JavaScript. It is designed to be simple, powerful, and easy to learn while remaining expressive for advanced applications.

*Disclaimer: firescript is currently in development and is not yet feature-complete. The language and compiler are subject to change. Not everything described in this document is implemented or working.*

## Features

- **Static & Strong Typing:** Enhances code readability and reliability.
- **Simple Syntax:** Combines the best of C, Java, JavaScript, and Python.
- **Everything is Explicit:** No implicit conversions or hidden behavior.
- **Versatile Compilation:** Supports native binaries and JavaScript output.
- **Cohesive Design:** All parts of the language work seamlessly together.

## Example

```firescript
// Define a function that returns the nth Fibonacci number
int fibonacci(int n) {
    if n <= 1 {
        return n
    }
    return fibonacci(n - 1) + fibonacci(n - 2)
}

// Print the first 10 Fibonacci numbers
for (int i : range(9)) {
    print(fibonacci(i))
}
```

## Getting Started

### Prerequisites

- C Compiler (GCC recommended, but any C compiler should work as long as it's location is in the CC environment variable)
- Python 3

### Installation

```bash
# Debian/Ubuntu
sudo apt-get install gcc python3

# Fedora/RHEL/CentOS
sudo dnf install gcc python3

# Arch/Manjaro
sudo pacman -S gcc python3

# Clone the repository
git clone https://github.com/alec-jensen/firescript.git
cd firescript
```

### Compiling and Running a Program

```bash
# Compile a firescript program
python3 firescript/firescript.py program.fire

# Execute the compiled program
./output/program
```

## Documentation

For detailed language feature guides, see the [documentation index](docs/README.md).

## Contributing

Contributions are welcome! Please open an issue or submit a pull request on [GitHub](https://github.com/alec-jensen/firescript).

## License

firescript is released under the MIT License. See [LICENSE](LICENSE) for details.
