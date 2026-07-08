# FIR Specification (High-Level IR) [IMPLEMENTED]

This document describes the Firescript IR (FIR): a compact, typed high-level IR used for analysis and optimization before lowering to FLIR. It is defined in `firescript/fir/` (`ir_types.py`, `ir_node.py`, `ir_module.py`, `ownership.py`, `ir_builder.py`, `textual.py`) and produced from the semantic-analyzed AST by `firescript/ast_to_fir.py`. Dump it for a given source file with `--emit-fir`.

## Design Principles

- Preserve all type information (classes, generics, ownership)
- Keep structure simple (no SSA, no φ-functions)
- Provide human-readable textual dumps for debugging
- Support ownership ops explicitly (Move/Borrow/Drop)

## Core Concepts

- Instructions: `op(args) → result_type`
- Value categories: `copyable` | `owned`
- Basic blocks: sequences of instructions + terminator (no block parameters)
- OwnershipMap: binding → VALID/MOVED/MAYBE_MOVED/BORROWED

## Data Structures

```
FIRModule
  ├─ TypeDefinitions (classes with fields)
  ├─ FunctionDefinitions
  │   ├─ Signature (params, return type, generic params if any)
  │   ├─ BasicBlocks
  │   │   ├─ Instructions (simple sequence)
  │   │   │   └─ op, args, result_type
  │   │   └─ Terminator (Branch, Jump, Return)
  │   └─ OwnershipMap (variable → OwnershipState)
  └─ GlobalConstants
```

## Instruction Set (summary)

- Literals: `IntLiteral`, `FloatLiteral`, `StringLiteral`, `CharLiteral`, `BoolLiteral`, `NullLiteral`, `ArrayLiteral`
- Arithmetic: `BinaryOp`, `UnaryOp`, `Cast`
- Memory: `Allocate`, `LoadField`, `StoreField`, `IndexArray`, `StoreArray`
- Locals: `DeclareLocal`, `LoadVar`, `StoreVar` (FIR is not SSA; mutable locals are explicit named slots instead of block parameters)
- Ownership: `Move`, `Borrow`, `Clone`, `Drop`
- Calls: `Call`, `MethodCall`
- Generators: `Yield`, `GenNew(name, [args]) -> generator<T>`, `GenNext(gen) -> bool`, `GenValue(gen) -> T` (generator functions render with the `generator` keyword instead of `function`; `for-in` over a generator converts to a GenNew/GenNext/GenValue loop)
- Control: `Branch`, `Jump`, `Return`, `Unreachable`

### Dump format rules

- Value numbers `%N` are assigned in (block order, instruction order) within each function; dumps are deterministic.
- Instructions that produce no value (`StoreField`, `StoreArray`, `StoreVar`, `DeclareLocal`, `Drop`, `Yield`, void `Call`s) are not numbered.
- Function parameters are referenced by name in operand position.
- Parameter passing modes render as `name: T` (owned), `name: &T` (borrow), `name: &mut T` (mutable borrow).
- `Call`/`MethodCall` render their argument modes and, when non-void, a trailing `-> type`.

## Textual Representation

FIR is designed to be directly dumpable for debugging. Example:

```
module firescript

type Point copyable {
  x: int32
  y: int32
}

function main() -> void {
  block_0:
    %0 = IntLiteral(10, int32)
    %1 = IntLiteral(20, int32)
    %2 = Allocate(Point, [%0, %1])
    %3 = LoadField(%2, "x")
    %4 = Call(distance, [%3, %3]) -> int32
    %5 = Call(println, [%4]) -> void
    Drop(%2)
    Return()
}
```

### Larger FIR Example: Ownership, Branching, and a Method Call

This example keeps classes, ownership, and control flow visible in FIR:

```
module firescript

type Counter owned {
  value: int32
}

function bump_or_reset(counter: Counter, should_reset: bool) -> int32 {
  block_0:
    %0 = LoadField(counter, "value")
    Branch(should_reset, block_1, block_2)

  block_1:
    %1 = IntLiteral(0, int32)
    StoreField(counter, "value", %1)
    Drop(counter)
    Return(%1)

  block_2:
    %2 = IntLiteral(1, int32)
    %3 = BinaryOp("+", %0, %2)
    StoreField(counter, "value", %3)
    Call(println, [%3], ["borrow"])
    Return(%3)
}
```

### Larger FIR Example: Generic Function Before Monomorphization

FIR keeps the generic type parameter intact so optimization can still see the original shape of the program:

```
type Box<T> owned {
  value: T
}

function<T> unwrap_or_default(box: Box<T>, fallback: T) -> T {
  block_0:
    %0 = LoadField(box, "value")
    %1 = Call(is_default, [%0]) -> bool
    Branch(%1, block_1, block_2)

  block_1:
    Return(fallback)

  block_2:
    Return(%0)
}
```

In FIR, the type parameter `T` is still present. That means passes can still reason about ownership, field access, and control flow before lowering specializes the function.

## Ownership & Optimization Notes

FIR preserves ownership information coming from the semantic analyzer. No FIR-level optimization passes (dead code elimination, constant folding, CSE) are implemented yet; FIR is lowered to FLIR as-is.

For details on lowering and FLIR, see `flir_spec.md`.
