"""FIR (firescript intermediate representation) infrastructure.

FIR is the high-level, typed IR produced from the semantic-analyzed AST.
It preserves classes, generics, and ownership so optimization passes can
reason about language semantics before lowering to FLIR.

See docs/internal/development/FIR_fir_spec.md for the specification.
"""

from fir.ir_types import (
    FIRType,
    SimpleType,
    ArrayType,
    GenericInstanceType,
    GeneratorType,
    FunctionType,
    make_simple,
    VOID,
)
from fir.ir_node import (
    Value,
    ParamValue,
    FIRValue,
    Instruction,
    Terminator,
    BasicBlock,
)
from fir.ir_module import FIRModule, FIRFunction, TypeDef, GlobalConstant
from fir.ownership import OwnershipState, OwnershipMap
from fir.ir_builder import FIRBuilder
from fir.textual import dump_module
