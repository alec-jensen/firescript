# FLIR Specification (Lowered IR) [IMPLEMENTED]

FLIR (firescript Lowered IR) is the machine-like IR produced by lowering FIR. It is defined in `firescript/flir/` (`ir.py`, `lowering.py`, `textual.py`) and consumed by `firescript/codegen/x86_64/flir_to_asm.py`, the only backend. Dump it for a given source file with `--emit-flir`.

Every FLIR module is validated on every compilation before codegen; see [ir_verifier_spec.md](ir_verifier_spec.md) for the full rule catalog (`firescript/flir/verifier.py`, `firescript/flir/heap_verifier.py`).

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

## Implemented Representation Decisions

These are the concrete layouts the implemented lowering uses:

- **Strings**: `ptr<i8>` to a NUL-terminated, heap-allocated byte buffer.
  Literals live in read-only data (`strconst`); binding a literal to a local
  duplicates it (`fs_rt_str_dup`). Concatenation/equality go through
  `fs_rt_str_concat` / `fs_rt_str_eq`. No refcount header (matches the
  legacy backend's plain `char*` representation).
- **Arrays**: `ptr` to a heap buffer of elements; no length header. Lengths
  are tracked statically per binding; array-typed function parameters get an
  implicit trailing `<name>_len: i32` parameter (legacy ABI). Generic
  instantiations do not take length parameters (legacy parity).
- **Classes**: fields in declaration order, inherited (base-chain) fields
  first; natural alignment with padding; struct size padded to max field
  alignment. Owned classes are heap pointers (`ptr<Struct>`), copyable
  classes are by-value structs. Classes with owned fields get a generated
  `<Struct>__destroy` function (null-checks each owned field, recursing into
  owned class fields, then frees self).
- **Monomorphization**: deterministic name mangling `base__arg1_arg2` (e.g.
  `Pair__int32_string`, `println__int32`); methods are `Class__T__method`.
  Reachability-driven from non-generic roots via a FIFO worklist.
- **Generators**: a frame struct `__gen_<name>` (`_state: i32`, params,
  locals) plus `<name>__init(frame, args)` and
  `<name>__next(frame, out) -> bool`. `_state` is 0 initially, k after the
  k-th yield (the dispatch chain jumps to the matching resume block), and -1
  when exhausted. Frames live in caller stack slots; `for-in` drives
  GenNew/GenNext/GenValue.
- **SyscallResult**: compiler-internal copyable struct
  `{ status: i32 @ 0, data: ptr<i8> @ 8 }`, returned by value from the
  `fs_rt_syscall_*` runtime calls.
- **Runtime ABI**: all runtime entry points are `fs_rt_*` (alloc/free,
  string ops, numeric<->string conversions, pow, stdout, process args,
  syscalls). Backends bind these names to the runtime implementation.
- **Entry**: the user/synthetic `main` lowers to `fs_main`; backends emit a
  host entry that sets process args, calls `fs_main`, and exits 0.

## ABI & Backend Notes

FLIR carries the stable ABI data (field offsets, sizes, alignments, calling conventions) that `flir_to_asm.py` needs to emit correct code without re-evaluating high-level semantics.
