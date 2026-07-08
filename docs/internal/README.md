# Internal Documentation

This is documentation for internal language features intended for use in the compiler and standard library. These are not intended for use in user code, as these features require careful handling to be used safely and correctly.

## Compiler internals

[FIR + FLIR Pipeline](development/fir_flir_pipeline.md) - Index for the FIR (Firescript Intermediate Representation) and FLIR (Firescript Lowered Intermediate Representation) design docs: architecture overview, per-IR specs, and a developer quick reference. **[IMPLEMENTED]**

[Native Toolchain](development/native_toolchain.md) - How the self-hosted x86-64 assembler and PE32+ writer work. **[IMPLEMENTED]**

[float128](development/float128.md) - The self-hosted IEEE 754 binary128 `float128` type and its soft-float runtime. **[IMPLEMENTED]**

## Directives

[Directives](directives.md) - Internal directives for controlling compiler behavior, used in the standard library and for testing. Not intended for user code.

[Syscall Directive](syscalls.md) - Internal directive for defining syscalls, used in the standard library to define OS-level syscalls. Not intended for user code.