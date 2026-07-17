# FIR + FLIR Pipeline [IMPLEMENTED]

The FIR + FLIR pipeline is implemented and is the compiler's only pipeline. The legacy AST →
C backend, the C runtime, and the interim FLIR → C differential backend used during migration
have all been removed. The compiler lowers AST → FIR → FLIR → x86-64 assembly (Windows x86_64,
self-hosted assembler and PE writer, freestanding binaries importing only kernel32.dll), and
the language runtime is implemented in firescript (`std/internal/*.fire`).

This is the short index for the FIR + FLIR design docs. The full details are split into
smaller files so each page stays manageable.

Internal pages:

- [Overview and architecture](fir_flir_overview.md)
- [FIR specification](fir_spec.md)
- [FLIR specification](flir_spec.md)
- [Developer quick reference](fir_developer_reference.md)

Warning: internal docs for compiler and language developers only.

Use `--emit-fir` and `--emit-flir` when debugging the pipeline.
