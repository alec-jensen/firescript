# FLIR Specification (Lowered IR)

FLIR (Firescript Lowered IR) is the machine-like IR produced by lowering FIR. It is intended to be backend-ready and minimal.

## Purpose

- Lower classes to struct layouts and pointers
- Monomorphize generics
- Convert ownership ops into explicit memory operations (`allocate`, `free`, loads/stores)
- Provide ABI metadata (size, alignment, calling conventions) for backend codegen

## FLIR Type Model

```python
FLIRType:
  kind: "int32" | "pointer" | "i64" | "f64" | "bool"
  size: int                # size in bytes (ABI information)
  align: int               # alignment in bytes (ABI information)
  abi_info: dict           # optional ABI metadata (calling convention, register constraints)
```

## Instructions & Functions

FLIR instructions are low-level and primitive-focused: `add_i32`, `load`, `store`, `allocate`, `free`, `call`, `branch`, `jump`, `return`.

Functions have primitive or pointer parameters only and are monomorphized.

## Lowering Examples

See the main plan for FIR→FLIR lowering examples. In short:
- `LoadField(obj, "x")` → `load(obj, offset)`
- `Allocate(Point, ...)` → `allocate(sizeof(Point))` + field stores
- `Drop(x)` → `free(x)`

## ABI & Backend Notes

FLIR must include stable ABI data (field offsets, sizes, alignments, calling conventions) so that backends can emit correct code without re-evaluating high-level semantics.

## Optional Advanced Path

If a native backend needs advanced register allocation or SSA-based optimizations, implement an optional `flir_to_ssa(flir_module)` or a translator from FLIR to Cranelift/LLVM IR. This is opt-in; default FLIR remains simple.
