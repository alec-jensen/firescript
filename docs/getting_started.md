# Getting Started

## Prerequisites

- GCC (other compilers may work, but GCC is recommended)
- Python 3

**Supported Platforms:**
- Linux (development is primarily done on Fedora Linux)
- Windows (via MSYS2, WSL is not officially supported but may work)

## Installation

### Linux

```bash
# Debian/Ubuntu
sudo apt-get install gcc python3 libgmp-dev libmpfr-dev

# Fedora/RHEL/CentOS
sudo dnf install gcc python3 gmp-devel mpfr-devel

# Arch/Manjaro
sudo pacman -S gcc python3 gmp mpfr

# Clone the repository
git clone https://github.com/alec-jensen/firescript.git
cd firescript
```

### Windows

Install python

Install [GCC via MSYS2](https://www.msys2.org/):

Open the MSYS2 UCRT64 terminal and run:

```bash
pacman -Syu
pacman -S --needed base-devel mingw-w64-ucrt-x86_64-toolchain
```

Add `C:\msys64\ucrt64\bin` to your system PATH.

Clone the repository

```bash
git clone https://github.com/alec-jensen/firescript.git
cd firescript
```

## Compiling and Running a Program

```bash
# Compile a firescript program
python3 firescript/firescript.py program.fire

# Execute the compiled program
./output/program
```
