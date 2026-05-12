# FIR Implementation Plan

This is the short index for the FIR + FLIR design docs. The full details are split into smaller files so each page stays manageable.

Internal pages:

- [Overview and architecture](FIR_overview.md)
- [FIR specification](FIR_fir_spec.md)
- [FLIR specification](FIR_flir_spec.md)
- [Roadmap, migration, and testing](FIR_roadmap_and_migration.md)

Warning: internal docs for compiler and language developers only.

Use `--emit-fir` and `--emit-flir` when debugging the pipeline.

TODO: should FIR+FLIR be held off until the compiler is bootstrapped, since the bootstrapping process will already necessitate a compiler rewrite? Or is it better to implement FIR+FLIR early so the bootstrapping process can be done in terms of FIR+FLIR from the start?