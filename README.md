<img src="assets/firescript-logo.svg" alt="firescript logo" width="200"/>

[![Tests](https://github.com/alec-jensen/firescript/actions/workflows/windows_x86_64_test.yml/badge.svg)](https://github.com/alec-jensen/firescript/actions/workflows/windows_x86_64_test.yml)

# firescript

firescript is a statically and strongly typed programming language designed to be simple, explicit, and prevent bugs at compile time. It prioritizes readability, predictable behavior, and safety through its type system and ownership model. As part of that vision, firescript is building toward an **entirely self-hosted toolchain** — the compiler front-end, codegen backend, x86-64 assembler, PE and ELF writers, FCL configuration language, kiln build system, and package registry are all implemented in firescript itself, depending on nothing but the OS kernel.

*Disclaimer: firescript is currently in development and is not yet feature-complete. The language and compiler are subject to change. Not everything described in this document is implemented or working. Current builds may leak resources; the design goal is deterministic destruction via an ownership model.*

## Features

- **Static & Strong Typing:** Enhances code readability and reliability.
- **Simple Syntax:** Combines the best of C, Java, JavaScript, and Python.
- **Everything is Explicit:** No implicit conversions or hidden behavior.
- **Self-Hosted Toolchain:** The x86-64 assembler, PE/ELF writers, FCL config language parser, and kiln build system are all implemented in firescript itself. The compiler compiles itself end-to-end with no Python invoked in the compile path.
- **Zero External Dependencies:** The compiler produces native executables using only the Python standard library — no C compiler, no assembler, no linker, no third-party packages. Compiled binaries are freestanding and import only `kernel32.dll` (Windows) or use raw syscalls (Linux).
- **Native Code Generation:** Compiles through its own intermediate representations (FIR → FLIR) directly to machine code.
- **Cohesive Design:** All parts of the language work seamlessly together.
- **Deterministic Ownership Model:** Ownership, moves, borrows, and explicit cloning instead of a tracing garbage collector. See the [Memory Management Model](docs/reference/memory_management.md).

## Example

```firescript
import @firescript/std.io.println;

// Define a function that returns the nth Fibonacci number
int8 fibonacci(int8 n) {
    if (n <= 1i8) {
        return n;
    }
    return fibonacci(n - 1i8) + fibonacci(n - 2i8);
}

// Print the first 10 Fibonacci numbers
for (int8 i = 0i8; i < 10i8; i++) {
    println(fibonacci(i));
}
```

## Self-Hosting Vision

firescript is built to compile itself. The entire toolchain is implemented in firescript code:

| Layer | Implementation | Status |
|---|---|---|
| Lexer, parser, semantic analysis | `firescript/std/compiler/*.fire` | [PLANNED] |
| FIR → FLIR lowering | `firescript/std/compiler/codegen.fire` | [PLANNED] |
| x86-64 assembler | `firescript/std/compiler/assembler.fire` | [PLANNED] |
| PE32+ writer (Windows) | `firescript/std/compiler/pe_writer.fire` | [PLANNED] |
| ELF64 writer (Linux) | `firescript/std/compiler/elf_writer.fire` | [PLANNED] |
| FCL config language | `firescript/std/fcl/` | [IN DEVELOPMENT] |
| kiln build system | `firescript/tools/kiln/` | [IN DEVELOPMENT] |
| Package registry | `firescript/tools/kiln/` | [PLANNED] |

The Python compiler is a bootstrap seed. At 1.0, it is retired and the firescript compiler is the only compiler.

## Platforms

| OS      | x86_64 | i686 | aarch64 | armv7 | riscv64 | riscv32 |
|---------|--------|------|---------|-------|---------|---------|
| Windows | ✅ current | ❌ | 🔜 planned | ❌ | ❌ | ❌ |
| Linux   | 🔜 planned | ❌ | 🔜 planned | ❌ | 🔜 planned | ❌ |
| macOS   | ❌ | ❌ | 🔜 planned | ❌ | ❌ | ❌ |
| none (bare-metal) | 🔜 planned | 🔜 planned | 🔜 planned | 🔜 planned | 🔜 planned | 🔜 planned |

## Build Requirements

- **Required:** Python 3.13+ (bootstrap only; removed at 1.0).

The compiler assembles machine code and writes the executable itself; it invokes no external programs. Compiled binaries are freestanding (Windows: `kernel32.dll` only; Linux: raw syscalls). The entire language runtime is written in firescript. No C compiler, no assembler, no linker, and no third-party Python packages are needed.

## Getting Started

See the [Getting Started Guide](https://firescript.alecj.com/getting_started/) for installation and usage instructions.

## Documentation

Full documentation is available at: [https://alec-jensen.github.io/firescript/](https://firescript.alecj.com/)

## Contributing

Contributions are welcome! Please open an issue or submit a pull request on [GitHub](https://github.com/alec-jensen/firescript).

## License

firescript is released under the MIT License. See [LICENSE](LICENSE) for details.
