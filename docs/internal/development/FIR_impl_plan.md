# FIR Implementation Plan [IMPLEMENTED]

**Status: the FIR + FLIR pipeline is implemented and is the compiler's only pipeline.** The legacy AST → C backend, the C runtime, and the interim FLIR → C differential backend have been removed. The compiler lowers AST → FIR → FLIR → x86-64 assembly (Windows x64, MinGW binutils, freestanding binaries importing only kernel32.dll), and the language runtime is implemented in firescript (`std/internal/runtime.fire`).

This is the short index for the FIR + FLIR design docs. The full details are split into smaller files so each page stays manageable.

Internal pages:

- [Overview and architecture](FIR_overview.md)
- [FIR specification](FIR_fir_spec.md)
- [FLIR specification](FIR_flir_spec.md)
- [Roadmap, migration, and testing](FIR_roadmap_and_migration.md)
- [Migration build prompt (no C backend)](FIR_migration_build_prompt.md) — the executed migration plan, kept for reference

Warning: internal docs for compiler and language developers only.

Use `--emit-fir` and `--emit-flir` when debugging the pipeline.

Resolved: FIR+FLIR landed before bootstrapping. Any future self-hosting work is written against FIR/FLIR (the bootstrap compiler can target FLIR directly).