# FIR Development Quick Reference [IMPLEMENTED]

Practical guidance for working with the FIR/FLIR code, complementing the specs in
[fir_spec.md](fir_spec.md) and [flir_spec.md](flir_spec.md).

## Directory Layout

```
firescript/
├── fir/
│   ├── ir_types.py      # FIRType, SimpleType, ArrayType, GenericInstanceType,
│   │                    #   GeneratorType, FunctionType
│   ├── ir_node.py       # Value, ParamValue, FIRValue, Instruction, Terminator, BasicBlock
│   ├── ir_module.py     # FIRModule, FIRFunction, TypeDef, GlobalConstant
│   ├── ownership.py     # OwnershipState, OwnershipMap
│   ├── ir_builder.py    # FIRBuilder — helper for constructing FIR
│   └── textual.py       # dump_module() — deterministic textual FIR dumps
│
├── ast_to_fir.py         # AST → FIR converter
│
├── flir/
│   ├── ir.py             # FLIR types/nodes (structs, pointers, primitive ops)
│   ├── lowering.py        # FIR → FLIR lowering (monomorphization, class/ownership lowering)
│   └── textual.py         # Deterministic textual FLIR dumps
│
├── codegen/
│   └── flir_to_asm.py    # FLIR → x86-64 GAS-syntax assembly (the only backend)
│
└── backend/
    ├── assembler.py       # x86-64 assembler: GAS text → object image
    └── pe.py              # PE32+ writer: object image → freestanding .exe
```

## Key Classes

### FIR types (`fir/ir_types.py`)

`FIRType` is the base class; every subtype carries a `category` of `"owned"` or `"copyable"`.
`SimpleType` covers scalars and named classes, `ArrayType` fixed-size arrays,
`GenericInstanceType` a generic class applied to type arguments (e.g. `Box<int32>`),
`GeneratorType` `generator<T>`, and `FunctionType` a signature (not a value). `make_simple()`
builds a `SimpleType`, inferring `copyable` for the built-in numeric/bool/char types and
`owned` otherwise.

### Instructions and values (`fir/ir_node.py`)

`Value` is the base operand type: either a `ParamValue` (a function parameter, rendered by
name) or a `FIRValue` (the result of an `Instruction`, rendered as `%N`). Every `Instruction`
formats itself deterministically via `format(resolve)`, where `resolve` maps a `Value` to its
dump name — this is what makes FIR/FLIR dumps stable and diffable.

### Ownership tracking (`fir/ownership.py`)

`OwnershipMap` tracks each binding's `OwnershipState` (`VALID`, `MOVED`, `MAYBE_MOVED`,
`BORROWED`) as FIR is built, carrying forward the ownership analysis already computed during
semantic analysis instead of discarding it before codegen.

### Building FIR (`fir/ir_builder.py`)

`FIRBuilder` wraps a `BasicBlock` and exposes one method per instruction kind (`int_literal`,
`binary_op`, `move`, `borrow`, `call`, `drop`, `ret`, `branch`, ...). `ast_to_fir.py` uses it to
turn each AST node into FIR instructions without touching `BasicBlock` internals directly.

## Debugging

```
python firescript/main.py example.fire --emit-fir    # dump FIR
python firescript/main.py example.fire --emit-flir   # dump FLIR
python firescript/main.py example.fire --emit asm     # dump the generated x86-64 assembly
```

Dumps are deterministic (value numbers follow block order, then instruction order), so they
diff cleanly across compiler changes.
