# FIR Overview and Architecture [IMPLEMENTED]

The compiler pipeline is AST → FIR → FLIR → x86-64 assembly. This page summarizes why the
two-level IR exists and how the stages fit together; see [fir_spec.md](fir_spec.md) and
[flir_spec.md](flir_spec.md) for the per-IR details.

## Pipeline

```
Source Text
    ↓
Lexer + Parser → AST
    ↓
Import Resolution → Merged AST
    ↓
Preprocessing → Annotated AST
    ↓
Semantic Analysis → Type-checked, ownership-validated AST
    ↓
AST → FIR Converter (firescript/ast_to_fir.py) → FIR
    ↓
FIR → FLIR Lowering (firescript/flir/lowering.py) → FLIR
    ↓
FLIR → x86-64 assembly (firescript/codegen/x86_64/flir_to_asm.py)
    ↓
Self-hosted assembler + PE writer (firescript/backend/) → native .exe
```

Optimization passes over FIR (constant folding, DCE, CSE) are not implemented; FIR is lowered
to FLIR as-is.

## Stages

- **AST stage**: parser output plus import and preprocessing passes, with source structure
  still intact.
- **Semantic stage**: validates types, ownership, borrows, and drops while the tree is still
  high-level.
- **FIR stage**: preserves classes, generics, and ownership so later passes can still use
  language semantics.
- **FLIR stage**: erases high-level constructs into structs, pointers, primitive operations,
  and ABI-aware layouts (ready for a backend to consume directly).
- **Backend stage**: `flir_to_asm.py` emits x86-64 GAS-syntax text; `backend/x86_64/assembler.py`
  and `backend/windows/pe.py` turn that into a freestanding PE32+ executable importing only
  `kernel32.dll`.

## Type System Summary

- Copyable types: numeric, float, bool, char, user-defined `copyable class`
- Owned types: strings, arrays, user-defined classes (default), generics, generators

## Ownership Tracking

The semantic analyzer tracks binding scope, ownership states (`VALID`/`MOVED`/`MAYBE_MOVED`/
`BORROWED`), borrow validation, and drop points. This information is carried into FIR via
`fir.ownership.OwnershipMap` so it survives past semantic analysis instead of being discarded
before codegen.

Use `--emit-fir` and `--emit-flir` on `main.py` to dump either IR for a given source file.
