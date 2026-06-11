"""FLIR (firescript lowered IR) infrastructure.

FLIR is the machine-like IR produced by lowering FIR: classes become
struct layouts with explicit offsets, generics are monomorphized,
ownership ops become explicit allocation/free/runtime calls, and
generators become state-machine structs with resume functions.

See docs/internal/development/FIR_flir_spec.md for the specification.
"""

from flir.ir import (
    FLIRType,
    FLIRStruct,
    FLIRFunction,
    FLIRModule,
    FLIRBlock,
    I8,
    I16,
    I32,
    I64,
    U8,
    U16,
    U32,
    U64,
    F32,
    F64,
    BOOL,
    PTR,
    VOID,
    ptr_to,
    struct_type,
)
from flir.textual import dump_flir_module
from flir.lowering import FIRToFLIRLowering
