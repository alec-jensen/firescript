# Internal Documentation

This is documentation for internal language features intended for use in the compiler and standard library. These are not intended for use in user code, as these features require careful handling to be used safely and correctly.

## The future of firescript

The following are documents for planning the future of firescript.

[Ecosystem Roadmap](ecosystem_roadmap.md) - Overview of planned ecosystem features, including language features, standard library additions, tooling, and ecosystem growth initiatives.

[FIR Implementation Plan](development/FIR_impl_plan.md) - Details a plan to replace the current AST-based codegen with a new FIR (Firescript Intermediate Representation) and FLIR (Firescript Lowered Intermediate Representation) pipeline. This includes design notes, implementation plans, and testing strategies. **[IMPLEMENTED]**

[Self-Hosted Toolchain + binary128 Build Prompt](development/selfhost_toolchain_and_float128_build_prompt.md) - Spec for removing the last external dependencies (the MinGW `as`/`ld` assembler and linker) by writing a pure-Python x86-64 assembler and PE32+ writer, and for implementing true IEEE binary128 `float128`. Includes phased gates and completion criteria. Track A (self-hosted toolchain) and Track B (binary128) are both **[IMPLEMENTED]**.

[Native Toolchain](development/native_toolchain.md) - How the self-hosted x86-64 assembler and PE32+ writer work (the implemented Track A). **[IMPLEMENTED]**

## Directives

[Directives](directives.md) - Internal directives for controlling compiler behavior, used in the standard library and for testing. Not intended for user code.

[Syscall Directive](syscalls.md) - Internal directive for defining syscalls, used in the standard library to define OS-level syscalls. Not intended for user code.