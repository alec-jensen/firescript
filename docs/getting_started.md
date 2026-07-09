# Getting Started

## Prerequisites

- Python 3.13+ (firescript generally targets the latest version of Python)

No C compiler, assembler, or linker is required — the firescript compiler assembles x86-64 machine code and writes the executable itself using only the Python standard library.

**Supported Platforms:**
- Windows (x86_64)

**Note: The compiler is developed on Windows. As it is currently under active development, there may be platform-specific issues. If you encounter any problems on your platform, please report them in the issue tracker. Contributions to improve cross-platform compatibility are also welcome.**

## Installation

### Windows

Clone the repository

```bash
git clone https://github.com/alec-jensen/firescript.git
cd firescript
```

## Compiling and Running a Program

```bash
# Compile a firescript program (output goes to build\program.exe)
python firescript/main.py program.fire

# Execute the compiled program
.\build\program.exe
```

Useful flags:

- `-o <path>` — choose the output file
- `-d` — debug output
- `--check` — run checks only, without generating code
- `--emit {ast,asm,obj,bin}` — choose the kind of output to generate
