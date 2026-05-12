# FIR Specification (High-Level IR)

This document describes the Firescript IR (FIR): a compact, typed high-level IR used for analysis and optimization before lowering to FLIR.

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

- Literals: `IntLiteral`, `FloatLiteral`, `StringLiteral`, `BoolLiteral`, `ArrayLiteral`
- Arithmetic: `BinaryOp`, `UnaryOp`
- Memory: `Allocate`, `LoadField`, `StoreField`, `IndexArray`, `StoreArray`
- Ownership: `Move`, `Borrow`, `Clone`, `Drop`
- Calls: `Call`, `MethodCall`
- Control: `Branch`, `Jump`, `Return`, `Unreachable`

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

## Ownership & Optimization Notes

FIR preserves ownership information coming from the semantic analyzer. Optimization passes (dead code elimination, constant folding, CSE) operate on FIR while type/ownership info is still available.

For details on lowering and FLIR, see `FIR_flir_spec.md`.
