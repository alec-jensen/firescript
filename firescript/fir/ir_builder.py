"""FIRBuilder: convenience API for constructing FIR instruction streams."""

from __future__ import annotations

from typing import Optional

from fir.ir_module import FIRFunction
from fir.ir_node import (
    AllocateInst,
    ArrayLiteralInst,
    BasicBlock,
    BinaryOpInst,
    BoolLiteralInst,
    BorrowInst,
    BranchInst,
    CallInst,
    CastInst,
    CharLiteralInst,
    CloneInst,
    ConstructVariantInst,
    DeclareLocalInst,
    DropInst,
    ExtractPayloadFieldInst,
    ExtractTagInst,
    FIRValue,
    FloatLiteralInst,
    GenNewInst,
    GenNextInst,
    GenValueInst,
    IndexArrayInst,
    Instruction,
    IntLiteralInst,
    JumpInst,
    LoadFieldInst,
    LoadVarInst,
    MethodCallInst,
    MoveInst,
    NullLiteralInst,
    ReturnInst,
    StoreArrayInst,
    StoreFieldInst,
    StoreVarInst,
    StringLiteralInst,
    UnaryOpInst,
    UnreachableInst,
    Value,
    YieldInst,
)
from fir.ir_types import FIRType


class FIRBuilder:
    """Builds instructions into the current block of a function."""

    def __init__(self, function: FIRFunction, block: Optional[BasicBlock] = None):
        self.function = function
        self.current_block = block if block is not None else function.new_block()

    def position_at(self, block: BasicBlock) -> None:
        self.current_block = block

    def new_block(self) -> BasicBlock:
        return self.function.new_block()

    def emit(self, inst: Instruction) -> Optional[FIRValue]:
        return self.current_block.add_instruction(inst)

    # -- literals ----------------------------------------------------------

    def int_literal(self, text: str, target_type: FIRType) -> FIRValue:
        return self.emit(IntLiteralInst(text, target_type))

    def float_literal(self, text: str, target_type: FIRType) -> FIRValue:
        return self.emit(FloatLiteralInst(text, target_type))

    def bool_literal(self, value: bool, target_type: FIRType) -> FIRValue:
        return self.emit(BoolLiteralInst(value, target_type))

    def string_literal(self, text: str, target_type: FIRType) -> FIRValue:
        return self.emit(StringLiteralInst(text, target_type))

    def char_literal(self, text: str, target_type: FIRType) -> FIRValue:
        return self.emit(CharLiteralInst(text, target_type))

    def null_literal(self, target_type: FIRType) -> FIRValue:
        return self.emit(NullLiteralInst(target_type))

    def array_literal(self, elements: list[Value], target_type: FIRType) -> FIRValue:
        return self.emit(ArrayLiteralInst(elements, target_type))

    # -- arithmetic / casts ------------------------------------------------

    def binary_op(self, op: str, lhs: Value, rhs: Value, result_type: Optional[FIRType] = None) -> FIRValue:
        if result_type is None:
            result_type = lhs.result_type
        return self.emit(BinaryOpInst(op, lhs, rhs, result_type))

    def unary_op(self, op: str, operand: Value, result_type: Optional[FIRType] = None) -> FIRValue:
        if result_type is None:
            result_type = operand.result_type
        return self.emit(UnaryOpInst(op, operand, result_type))

    def cast(self, value: Value, target_type: FIRType) -> FIRValue:
        return self.emit(CastInst(value, target_type))

    # -- memory ------------------------------------------------------------

    def allocate(self, class_type: FIRType, args: list[Value]) -> FIRValue:
        return self.emit(AllocateInst(class_type, args))

    def load_field(self, obj: Value, field: str, result_type: FIRType) -> FIRValue:
        return self.emit(LoadFieldInst(obj, field, result_type))

    def store_field(self, obj: Value, field: str, value: Value) -> None:
        self.emit(StoreFieldInst(obj, field, value))

    def construct_variant(self, enum_type: FIRType, variant_name: str, payload: list[Value]) -> FIRValue:
        return self.emit(ConstructVariantInst(enum_type, variant_name, payload))

    def extract_tag(self, enum_value: Value, result_type: FIRType) -> FIRValue:
        return self.emit(ExtractTagInst(enum_value, result_type))

    def extract_payload_field(
        self, enum_value: Value, variant_name: str, field_index: int, result_type: FIRType
    ) -> FIRValue:
        return self.emit(ExtractPayloadFieldInst(enum_value, variant_name, field_index, result_type))

    def index_array(self, array: Value, index: Value, result_type: FIRType) -> FIRValue:
        return self.emit(IndexArrayInst(array, index, result_type))

    def store_array(self, array: Value, index: Value, value: Value) -> None:
        self.emit(StoreArrayInst(array, index, value))

    # -- locals --------------------------------------------------------------

    def declare_local(self, name: str, var_type: FIRType, init: Optional[Value] = None) -> None:
        self.emit(DeclareLocalInst(name, var_type, init))
        self.function.ownership.declare(name)

    def load_var(self, name: str, result_type: FIRType) -> FIRValue:
        return self.emit(LoadVarInst(name, result_type))

    def store_var(self, name: str, value: Value) -> None:
        self.emit(StoreVarInst(name, value))

    # -- ownership -----------------------------------------------------------

    def move(self, value: Value) -> FIRValue:
        return self.emit(MoveInst(value))

    def borrow(self, value: Value, mutable: bool = False) -> FIRValue:
        return self.emit(BorrowInst(value, mutable))

    def clone(self, value: Value) -> FIRValue:
        return self.emit(CloneInst(value))

    def drop(self, value: Value) -> None:
        self.emit(DropInst(value))

    # -- calls ---------------------------------------------------------------

    def call(
        self,
        function_ref: str,
        args: list[Value],
        arg_modes: Optional[list[str]] = None,
        return_type: Optional[FIRType] = None,
    ) -> Optional[FIRValue]:
        return self.emit(CallInst(function_ref, args, arg_modes, return_type))

    def method_call(
        self,
        receiver: Value,
        method: str,
        args: list[Value],
        arg_modes: Optional[list[str]] = None,
        return_type: Optional[FIRType] = None,
    ) -> Optional[FIRValue]:
        return self.emit(MethodCallInst(receiver, method, args, arg_modes, return_type))

    # -- generators ------------------------------------------------------------

    def yield_value(self, value: Value) -> None:
        self.emit(YieldInst(value))

    def gen_new(self, generator_ref: str, args: list[Value], result_type: FIRType) -> FIRValue:
        return self.emit(GenNewInst(generator_ref, args, result_type))

    def gen_next(self, generator: Value, bool_type: FIRType) -> FIRValue:
        return self.emit(GenNextInst(generator, bool_type))

    def gen_value(self, generator: Value, element_type: FIRType) -> FIRValue:
        return self.emit(GenValueInst(generator, element_type))

    # -- terminators -------------------------------------------------------

    def ret(self, value: Optional[Value] = None) -> None:
        self.current_block.set_terminator(ReturnInst(value))

    def branch(self, cond: Value, true_block: str, false_block: str) -> None:
        self.current_block.set_terminator(BranchInst(cond, true_block, false_block))

    def jump(self, target_block: str) -> None:
        self.current_block.set_terminator(JumpInst(target_block))

    def unreachable(self) -> None:
        self.current_block.set_terminator(UnreachableInst())
