# FIR Specification (High-Level IR) [IMPLEMENTED]

This document describes the firescript IR (FIR): a compact, typed high-level IR used for analysis and optimization before lowering to FLIR. It is defined in `firescript/fir/` (`ir_types.py`, `ir_node.py`, `ir_module.py`, `ownership.py`, `ir_builder.py`, `textual.py`) and produced from the semantic-analyzed AST by `firescript/ast_to_fir.py`. Dump it for a given source file with `--emit-fir`.

Every FIR module is validated on every compilation before lowering; see [ir_verifier_spec.md](ir_verifier_spec.md) for the full rule catalog (`firescript/fir/verifier.py`, `firescript/fir/ownership_verifier.py`).

## Design Principles

- Preserve all type information (classes, generics, ownership)
- Keep structure simple (no SSA, no φ-functions)
- Provide human-readable textual dumps for debugging
- Support ownership ops explicitly (Move/Borrow/Drop)

## Core Concepts

- Instructions: `%n = opcode.type operands` (or `opcode operands` when the instruction produces no value)
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

- Literals: `const` (int), `fconst` (float), `strconst`, `cconst` (char), `bconst`, `nullconst`, `arrayconst`
- Arithmetic: `binop`, `unop`, `cast`
- Memory: `alloc`, `loadfield`, `storefield`, `indexarray`, `storearray`
- Locals: `local`, `loadvar`, `storevar` (FIR is not SSA; mutable locals are explicit named bindings instead of block parameters)
- Ownership: `move`, `borrow`, `clone`, `drop`
- Calls: `call`, `mcall`
- Generators: `yield`, `gennew.generator<T> @name(args)`, `gennext.bool gen`, `genvalue.T gen` (generator functions render with the `generator` keyword instead of `function`; `for-in` over a generator converts to a gennew/gennext/genvalue loop)
- Control: `br`, `jmp`, `ret`, `unreachable`

The textual grammar deliberately mirrors [flir_spec.md](flir_spec.md)'s (`opcode.type operands`, `@`-prefixed symbols, `L<n>` blocks) so FIR and FLIR dumps read as one family at two abstraction levels, rather than as two unrelated notations. What still differs, on purpose, is the *level*: FIR types stay firescript-level (`int64`, `string`, a still-unresolved generic `T`, `int32?`) and some ops stay polymorphic/unresolved (a generic `binop "+"` that could be integer addition or string concatenation, still-intact class/generic identity) where FLIR's mnemonics are already monomorphic and machine-typed (`add.i64`, `ptr<i8>`, a concrete runtime call for that same `+`).

### Dump format rules

- Value numbers `%N` are assigned in (block order, instruction order) within each function; dumps are deterministic.
- Basic blocks are labeled `L0`, `L1`, ... in creation order (matches FLIR).
- Function names and call/method-call/gennew targets are `@`-prefixed symbols (matches FLIR).
- Instructions that produce no value (`storefield`, `storearray`, `storevar`, `local`, `drop`, `yield`, void `call`s) are not numbered.
- Function parameters are referenced by name in operand position.
- Parameter passing modes render as `name: T` (owned), `name: &T` (borrow), `name: &mut T` (mutable borrow).
- `call`/`mcall` render each argument's ownership mode inline after the value (`%v own`, `%v borrow`) and, when the callee returns a value, a `.type` suffix on the opcode itself (`call.int32 @f(...)`) rather than a trailing `-> type`.

## Textual Representation

FIR is designed to be directly dumpable for debugging. Example:

```
fir module firescript

type Point copyable {
  x: int32
  y: int32
}

function @main() -> void {
  L0:
    %0 = const.int32 10
    %1 = const.int32 20
    %2 = alloc.Point(%0, %1)
    %3 = loadfield.int32 %2, "x"
    %4 = call.int32 @distance(%3 own, %3 own)
    call @println(%4 own)
    drop %2
    ret
}
```

### Larger FIR Example: Ownership, Branching, and a Method Call

This example keeps classes, ownership, and control flow visible in FIR:

```
fir module firescript

type Counter owned {
  value: int32
}

function @bump_or_reset(counter: Counter, should_reset: bool) -> int32 {
  L0:
    %0 = loadfield.int32 counter, "value"
    br should_reset, L1, L2

  L1:
    %1 = const.int32 0
    storefield counter, "value", %1
    drop counter
    ret %1

  L2:
    %2 = const.int32 1
    %3 = binop "+", %0, %2
    storefield counter, "value", %3
    call @println(%3 borrow)
    drop counter
    ret %3
}
```

### Larger FIR Example: Generic Function Before Monomorphization

FIR keeps the generic type parameter intact so optimization can still see the original shape of the program:

```
type Box<T> owned {
  value: T
}

function<T> @unwrap_or_default(box: Box<T>, fallback: T) -> T {
  L0:
    %0 = loadfield.T box, "value"
    %1 = call.bool @is_default(%0 borrow)
    br %1, L1, L2

  L1:
    ret fallback

  L2:
    ret %0
}
```

In FIR, the type parameter `T` is still present. That means passes can still reason about ownership, field access, and control flow before lowering specializes the function.

## Ownership & Optimization Notes

FIR preserves ownership information coming from the semantic analyzer. No FIR-level optimization passes (dead code elimination, constant folding, CSE) are implemented yet; FIR is lowered to FLIR as-is.

For details on lowering and FLIR, see `flir_spec.md`.
