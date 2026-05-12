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

### Larger FLIR Example: Lowered Counter Update

The same `bump_or_reset` function from FIR becomes pointer arithmetic, explicit loads/stores, and concrete control flow in FLIR:

```text
type Counter {
  value: i32
  size: 4
  align: 4
  abi_info: { kind: "struct", pass_by: "pointer" }
}

function bump_or_reset(counter: *Counter, should_reset: bool) -> i32 {
  block_0:
    %0 = load_i32(counter, 0)
    branch should_reset, block_1, block_2

  block_1:
    %1 = const_i32(0)
    store_i32(counter, 0, %1)
    free(counter)
    return %1

  block_2:
    %2 = const_i32(1)
    %3 = add_i32(%0, %2)
    store_i32(counter, 0, %3)
    call void @println_i32(%3)
    return %3
}
```

### Larger FLIR Example: Monomorphized Generic

FIR generics disappear in FLIR. A single generic function may become multiple concrete functions:

```text
function unwrap_or_default_Box_i32(box: *Box_i32, fallback: i32) -> i32 {
  block_0:
    %0 = load_i32(box, 0)
    %1 = call bool @is_default_i32(%0)
    branch %1, block_1, block_2

  block_1:
    return fallback

  block_2:
    return %0
}

function unwrap_or_default_Box_String(box: *Box_String, fallback: *String) -> *String {
  block_0:
    %0 = load_ptr(box, 0)
    %1 = call bool @is_default_String(%0)
    branch %1, block_1, block_2

  block_1:
    return fallback

  block_2:
    return %0
}
```

These examples show the key FLIR rule: every high-level language feature that would complicate backend code is already resolved into concrete loads, stores, calls, and jumps.

## ABI & Backend Notes

FLIR must include stable ABI data (field offsets, sizes, alignments, calling conventions) so that backends can emit correct code without re-evaluating high-level semantics.

## Optional Advanced Path

If a native backend needs advanced register allocation or SSA-based optimizations, implement an optional `flir_to_ssa(flir_module)` or a translator from FLIR to Cranelift/LLVM IR. This is opt-in; default FLIR remains simple.
