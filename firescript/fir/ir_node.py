"""FIR instructions, values, and basic blocks.

Structure is intentionally simple: no SSA, no phi nodes. Mutable locals
are modeled with DeclareLocal/LoadVar/StoreVar instead of block
parameters, which keeps the AST->FIR conversion direct and the dumps
readable.

Every instruction knows how to format itself deterministically via
`format(resolve)`, where `resolve` maps a Value to its dump name
("%0", "%1", or a parameter name).
"""

from __future__ import annotations

from typing import Callable, Optional

from fir.ir_types import FIRType


class Value:
    """Base class for anything an instruction can consume as an operand."""

    result_type: Optional[FIRType] = None


class ParamValue(Value):
    """A reference to a function parameter; renders as the parameter name."""

    def __init__(self, name: str, param_type: FIRType):
        self.name = name
        self.result_type = param_type


class FIRValue(Value):
    """The value produced by an instruction."""

    def __init__(self, instruction: "Instruction"):
        self.instruction = instruction

    @property
    def result_type(self) -> Optional[FIRType]:  # type: ignore[override]
        return self.instruction.result_type


Resolver = Callable[[Value], str]


class Instruction:
    """Base class for all FIR instructions."""

    opcode: str = "Instruction"

    def __init__(self, operands: Optional[list[Value]] = None, result_type: Optional[FIRType] = None):
        self.operands: list[Value] = operands or []
        self.result_type = result_type
        # Source metadata: line, column, file (best effort, for diagnostics)
        self.metadata: dict = {}
        self._result: Optional[FIRValue] = None

    def has_result(self) -> bool:
        return self.result_type is not None

    def result(self) -> FIRValue:
        if self._result is None:
            self._result = FIRValue(self)
        return self._result

    def format(self, resolve: Resolver) -> str:
        args = ", ".join(resolve(op) for op in self.operands)
        return f"{self.opcode}({args})"


def _fmt_value_list(values: list[Value], resolve: Resolver) -> str:
    return "[" + ", ".join(resolve(v) for v in values) + "]"


def _fmt_mode_list(modes: list[str]) -> str:
    return "[" + ", ".join(f'"{m}"' for m in modes) + "]"


# ---------------------------------------------------------------------------
# Literals
# ---------------------------------------------------------------------------

class IntLiteralInst(Instruction):
    opcode = "IntLiteral"

    def __init__(self, text: str, result_type: FIRType):
        super().__init__(result_type=result_type)
        self.text = text  # source text, normalized (suffix/underscores removed)

    def format(self, resolve: Resolver) -> str:
        return f"IntLiteral({self.text}, {self.result_type.render()})"


class FloatLiteralInst(Instruction):
    opcode = "FloatLiteral"

    def __init__(self, text: str, result_type: FIRType):
        super().__init__(result_type=result_type)
        self.text = text

    def format(self, resolve: Resolver) -> str:
        return f"FloatLiteral({self.text}, {self.result_type.render()})"


class BoolLiteralInst(Instruction):
    opcode = "BoolLiteral"

    def __init__(self, value: bool, result_type: FIRType):
        super().__init__(result_type=result_type)
        self.value = value

    def format(self, resolve: Resolver) -> str:
        text = "true" if self.value else "false"
        return f"BoolLiteral({text}, {self.result_type.render()})"


class StringLiteralInst(Instruction):
    opcode = "StringLiteral"

    def __init__(self, text: str, result_type: FIRType):
        super().__init__(result_type=result_type)
        self.text = text  # raw contents without surrounding quotes

    def format(self, resolve: Resolver) -> str:
        return f'StringLiteral("{self.text}", {self.result_type.render()})'


class CharLiteralInst(Instruction):
    opcode = "CharLiteral"

    def __init__(self, text: str, result_type: FIRType):
        super().__init__(result_type=result_type)
        self.text = text  # raw contents without surrounding quotes

    def format(self, resolve: Resolver) -> str:
        return f"CharLiteral('{self.text}', {self.result_type.render()})"


class NullLiteralInst(Instruction):
    opcode = "NullLiteral"

    def __init__(self, result_type: FIRType):
        super().__init__(result_type=result_type)

    def format(self, resolve: Resolver) -> str:
        return f"NullLiteral({self.result_type.render()})"


class ArrayLiteralInst(Instruction):
    opcode = "ArrayLiteral"

    def __init__(self, elements: list[Value], result_type: FIRType):
        super().__init__(operands=list(elements), result_type=result_type)

    def format(self, resolve: Resolver) -> str:
        return f"ArrayLiteral({_fmt_value_list(self.operands, resolve)}, {self.result_type.render()})"


# ---------------------------------------------------------------------------
# Arithmetic / logic
# ---------------------------------------------------------------------------

class BinaryOpInst(Instruction):
    opcode = "BinaryOp"

    def __init__(self, op: str, lhs: Value, rhs: Value, result_type: FIRType):
        super().__init__(operands=[lhs, rhs], result_type=result_type)
        self.op = op

    def format(self, resolve: Resolver) -> str:
        return f'BinaryOp("{self.op}", {resolve(self.operands[0])}, {resolve(self.operands[1])})'


class UnaryOpInst(Instruction):
    opcode = "UnaryOp"

    def __init__(self, op: str, operand: Value, result_type: FIRType):
        super().__init__(operands=[operand], result_type=result_type)
        self.op = op

    def format(self, resolve: Resolver) -> str:
        return f'UnaryOp("{self.op}", {resolve(self.operands[0])})'


class CastInst(Instruction):
    opcode = "Cast"

    def __init__(self, value: Value, target_type: FIRType):
        super().__init__(operands=[value], result_type=target_type)

    def format(self, resolve: Resolver) -> str:
        return f"Cast({resolve(self.operands[0])}, {self.result_type.render()})"


# ---------------------------------------------------------------------------
# Memory: objects, fields, arrays
# ---------------------------------------------------------------------------

class AllocateInst(Instruction):
    """Construct a class instance; args are constructor arguments."""

    opcode = "Allocate"

    def __init__(self, class_type: FIRType, args: list[Value]):
        super().__init__(operands=list(args), result_type=class_type)

    def format(self, resolve: Resolver) -> str:
        return f"Allocate({self.result_type.render()}, {_fmt_value_list(self.operands, resolve)})"


class LoadFieldInst(Instruction):
    opcode = "LoadField"

    def __init__(self, obj: Value, field: str, result_type: FIRType):
        super().__init__(operands=[obj], result_type=result_type)
        self.field = field

    def format(self, resolve: Resolver) -> str:
        return f'LoadField({resolve(self.operands[0])}, "{self.field}")'


class StoreFieldInst(Instruction):
    opcode = "StoreField"

    def __init__(self, obj: Value, field: str, value: Value):
        super().__init__(operands=[obj, value])
        self.field = field

    def format(self, resolve: Resolver) -> str:
        return (
            f'StoreField({resolve(self.operands[0])}, "{self.field}", '
            f"{resolve(self.operands[1])})"
        )


class IndexArrayInst(Instruction):
    opcode = "IndexArray"

    def __init__(self, array: Value, index: Value, result_type: FIRType):
        super().__init__(operands=[array, index], result_type=result_type)

    def format(self, resolve: Resolver) -> str:
        return f"IndexArray({resolve(self.operands[0])}, {resolve(self.operands[1])})"


class StoreArrayInst(Instruction):
    opcode = "StoreArray"

    def __init__(self, array: Value, index: Value, value: Value):
        super().__init__(operands=[array, index, value])

    def format(self, resolve: Resolver) -> str:
        ops = ", ".join(resolve(op) for op in self.operands)
        return f"StoreArray({ops})"


# ---------------------------------------------------------------------------
# Mutable locals (FIR is not SSA; locals are explicit named slots)
# ---------------------------------------------------------------------------

class DeclareLocalInst(Instruction):
    """Introduce a named local binding, optionally with an initial value."""

    opcode = "DeclareLocal"

    def __init__(self, name: str, var_type: FIRType, init: Optional[Value] = None):
        super().__init__(operands=[init] if init is not None else [])
        self.name = name
        self.var_type = var_type

    def format(self, resolve: Resolver) -> str:
        if self.operands:
            return f'DeclareLocal("{self.name}", {self.var_type.render()}, {resolve(self.operands[0])})'
        return f'DeclareLocal("{self.name}", {self.var_type.render()})'


class LoadVarInst(Instruction):
    opcode = "LoadVar"

    def __init__(self, name: str, result_type: FIRType):
        super().__init__(result_type=result_type)
        self.name = name

    def format(self, resolve: Resolver) -> str:
        return f'LoadVar("{self.name}") -> {self.result_type.render()}'


class StoreVarInst(Instruction):
    opcode = "StoreVar"

    def __init__(self, name: str, value: Value):
        super().__init__(operands=[value])
        self.name = name

    def format(self, resolve: Resolver) -> str:
        return f'StoreVar("{self.name}", {resolve(self.operands[0])})'


# ---------------------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------------------

class MoveInst(Instruction):
    opcode = "Move"

    def __init__(self, value: Value):
        super().__init__(operands=[value], result_type=value.result_type)


class BorrowInst(Instruction):
    opcode = "Borrow"

    def __init__(self, value: Value, mutable: bool = False):
        super().__init__(operands=[value], result_type=value.result_type)
        self.mutable = mutable

    def format(self, resolve: Resolver) -> str:
        if self.mutable:
            return f"Borrow({resolve(self.operands[0])}, mut)"
        return f"Borrow({resolve(self.operands[0])})"


class CloneInst(Instruction):
    opcode = "Clone"

    def __init__(self, value: Value):
        super().__init__(operands=[value], result_type=value.result_type)


class DropInst(Instruction):
    opcode = "Drop"

    def __init__(self, value: Value):
        super().__init__(operands=[value])


# ---------------------------------------------------------------------------
# Calls
# ---------------------------------------------------------------------------

class CallInst(Instruction):
    opcode = "Call"

    def __init__(
        self,
        function_ref: str,
        args: list[Value],
        arg_modes: Optional[list[str]] = None,
        return_type: Optional[FIRType] = None,
    ):
        super().__init__(operands=list(args), result_type=return_type)
        self.function_ref = function_ref
        self.arg_modes = arg_modes or ["own"] * len(args)

    def format(self, resolve: Resolver) -> str:
        text = (
            f"Call({self.function_ref}, {_fmt_value_list(self.operands, resolve)}, "
            f"{_fmt_mode_list(self.arg_modes)})"
        )
        if self.result_type is not None:
            text += f" -> {self.result_type.render()}"
        return text


class MethodCallInst(Instruction):
    opcode = "MethodCall"

    def __init__(
        self,
        receiver: Value,
        method: str,
        args: list[Value],
        arg_modes: Optional[list[str]] = None,
        return_type: Optional[FIRType] = None,
    ):
        super().__init__(operands=[receiver] + list(args), result_type=return_type)
        self.method = method
        self.arg_modes = arg_modes or ["own"] * len(args)

    def format(self, resolve: Resolver) -> str:
        receiver = resolve(self.operands[0])
        args = _fmt_value_list(self.operands[1:], resolve)
        text = f'MethodCall({receiver}, "{self.method}", {args}, {_fmt_mode_list(self.arg_modes)})'
        if self.result_type is not None:
            text += f" -> {self.result_type.render()}"
        return text


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

class YieldInst(Instruction):
    """Yield a value from a generator function body."""

    opcode = "Yield"

    def __init__(self, value: Value):
        super().__init__(operands=[value])


class GenNewInst(Instruction):
    """Instantiate a generator: GenNew(name, [args]) -> generator<T>."""

    opcode = "GenNew"

    def __init__(self, generator_ref: str, args: list[Value], result_type: FIRType):
        super().__init__(operands=list(args), result_type=result_type)
        self.generator_ref = generator_ref

    def format(self, resolve: Resolver) -> str:
        return (
            f"GenNew({self.generator_ref}, {_fmt_value_list(self.operands, resolve)})"
            f" -> {self.result_type.render()}"
        )


class GenNextInst(Instruction):
    """Advance a generator; result is true while a value was produced."""

    opcode = "GenNext"

    def __init__(self, generator: Value, result_type: FIRType):
        super().__init__(operands=[generator], result_type=result_type)

    def format(self, resolve: Resolver) -> str:
        return f"GenNext({resolve(self.operands[0])}) -> {self.result_type.render()}"


class GenValueInst(Instruction):
    """Read the current value of a generator after a successful GenNext."""

    opcode = "GenValue"

    def __init__(self, generator: Value, result_type: FIRType):
        super().__init__(operands=[generator], result_type=result_type)

    def format(self, resolve: Resolver) -> str:
        return f"GenValue({resolve(self.operands[0])}) -> {self.result_type.render()}"


# ---------------------------------------------------------------------------
# Terminators
# ---------------------------------------------------------------------------

class Terminator(Instruction):
    """Base class for block-terminating instructions."""


class ReturnInst(Terminator):
    opcode = "Return"

    def __init__(self, value: Optional[Value] = None):
        super().__init__(operands=[value] if value is not None else [])

    def format(self, resolve: Resolver) -> str:
        if self.operands:
            return f"Return({resolve(self.operands[0])})"
        return "Return()"


class BranchInst(Terminator):
    opcode = "Branch"

    def __init__(self, cond: Value, true_block: str, false_block: str):
        super().__init__(operands=[cond])
        self.true_block = true_block
        self.false_block = false_block

    def format(self, resolve: Resolver) -> str:
        return f"Branch({resolve(self.operands[0])}, {self.true_block}, {self.false_block})"


class JumpInst(Terminator):
    opcode = "Jump"

    def __init__(self, target_block: str):
        super().__init__()
        self.target_block = target_block

    def format(self, resolve: Resolver) -> str:
        return f"Jump({self.target_block})"


class UnreachableInst(Terminator):
    opcode = "Unreachable"

    def format(self, resolve: Resolver) -> str:
        return "Unreachable()"


# ---------------------------------------------------------------------------
# Basic blocks
# ---------------------------------------------------------------------------

class BasicBlock:
    """A sequence of instructions ending in exactly one terminator."""

    def __init__(self, block_id: str):
        self.id = block_id
        self.instructions: list[Instruction] = []
        self.terminator: Optional[Terminator] = None

    def add_instruction(self, inst: Instruction) -> Optional[FIRValue]:
        if self.terminator is not None:
            raise ValueError(f"block {self.id} already has a terminator")
        self.instructions.append(inst)
        return inst.result() if inst.has_result() else None

    def set_terminator(self, term: Terminator) -> None:
        if self.terminator is not None:
            raise ValueError(f"block {self.id} already has a terminator")
        self.terminator = term

    def is_terminated(self) -> bool:
        return self.terminator is not None
