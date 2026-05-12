# FIR Roadmap, Migration & Testing

This document contains the implementation roadmap, migration strategy, language recommendations, and testing/validation guidance for the FIR+FLIR work.

## Pipeline & Module Organization

```
Source Code
    ↓
[Lexer + Parser] → AST
    ↓
[Semantic Analysis] → AST (with type/ownership info)
    ↓
[AST → FIR Converter] → FIR (high-level, generic, classes intact)
    ↓
[Optimization Passes] → FIR (optimized)
    ↓
[FIR → FLIR Lowering] → FLIR (machine-like, monomorphized)
    ↓
[Backends: FLIR → C/ASM/WASM/...]
```

Suggested module layout (under `firescript/`):

- `fir/` — FIR infra: `ir_types.py`, `ir_node.py`, `ir_module.py`, `ownership.py`, `textual.py`, `builder.py`
- `flir/` — FLIR infra: `ir_types.py`, `ir_node.py`, `lowering.py`
- `ast_to_fir.py` — AST → FIR converter
- `optimizations/` — FIR optimization passes
- `codegen/` — FLIR → C backend + other backends

## 4-Week Implementation Roadmap

Week 1 — FIR infrastructure
- Implement core FIR types, builder, textual emitters
- Add `--emit-fir` and `--emit-flir` flags
- Add deterministic lowering tests and golden outputs

Week 2 — AST → FIR conversion
- Implement `ASTToFIRConverter` and basic coverage tests

Week 3 — FIR → FLIR lowering + basic optimizations
- Implement lowering, monomorphization, class lowering
- Implement dead code elimination and constant folding

Week 4 — FLIR → C backend + integration
- Implement `FLIRToCBackend`, integrate into pipeline, run full test suite

## Migration Strategy

- Implement `--use-fir` toggle to preserve existing pipeline during development
- Run both old and new paths in CI and compare outputs and behaviors
- Keep old codegen as a reference until parity is achieved

## Testing & Validation

- Add `--emit-fir` and `--emit-flir` to dump IR
- Add `fir_runner.py` to run tests via AST→FIR→FLIR→C path
- Create golden output fixtures in `tests/expected/` for FIR and FLIR dumps
- Deterministic lowering is required so diffs are meaningful

## Language Recommendations (summary)

- Consider making value category explicit in AST (`owned` / `copyable`)
- Consider explicit `move()` / `borrow()` call-site syntax
- Ownership-aware generics and optional lifetimes (phase 2)
- Add standard library dynamic collections rather than core language arrays

## Expected Outcomes & Metrics

- Faster addition of new backends (reuse FLIR)
- Small compile-time overhead for IR conversion
- Measurable code-quality improvements from IR-level optimizations

---

For detailed FIR and FLIR specifications, see `FIR_fir_spec.md` and `FIR_flir_spec.md`.
