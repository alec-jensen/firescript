"""FIR instructions, values, and basic blocks.

Structure is intentionally simple: no SSA, no phi nodes. Mutable locals
are modeled with DeclareLocal/LoadVar/StoreVar instead of block
parameters, which keeps the AST->FIR conversion direct and the dumps
readable.

Every instruction knows how to format itself deterministically via
`format(resolve)`, where `resolve` maps a Value to its dump name
("%0", "%1", or a parameter name). The textual grammar mirrors FLIR's
(`opcode.type operands`, `@`-prefixed symbols, `L<n>` blocks) so the two
IRs read as one family at different abstraction levels: FIR keeps
firescript-level types (int64, string, generic T, nullable ?) and
still-unresolved ops (a generic BinaryOp "+" rather than FLIR's add.i64),
while FLIR's mnemonics are already monomorphic and machine-typed.
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

    opcode: str = "inst"

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
        return f"{self.opcode} {args}".rstrip()


def _fmt_args(values: list[Value], resolve: Resolver) -> str:
    """Comma-joined operand list, used inside parens: op.type(a, b)."""
    return ", ".join(resolve(v) for v in values)


def _fmt_array_elems(values: list[Value], resolve: Resolver) -> str:
    """Bracketed element list for array literal values: [a, b]."""
    return "[" + ", ".join(resolve(v) for v in values) + "]"


def _fmt_args_with_modes(values: list[Value], modes: list[str], resolve: Resolver) -> str:
    return ", ".join(f"{resolve(v)} {m}" for v, m in zip(values, modes))


# ---------------------------------------------------------------------------
# Literals
# ---------------------------------------------------------------------------

class IntLiteralInst(Instruction):
    opcode = "const"

    def __init__(self, text: str, result_type: FIRType):
        super().__init__(result_type=result_type)
        self.text = text  # source text, normalized (suffix/underscores removed)

    def format(self, resolve: Resolver) -> str:
        return f"const.{self.result_type.render()} {self.text}"


class FloatLiteralInst(Instruction):
    opcode = "fconst"

    def __init__(self, text: str, result_type: FIRType):
        super().__init__(result_type=result_type)
        self.text = text

    def format(self, resolve: Resolver) -> str:
        return f"fconst.{self.result_type.render()} {self.text}"


class BoolLiteralInst(Instruction):
    opcode = "bconst"

    def __init__(self, value: bool, result_type: FIRType):
        super().__init__(result_type=result_type)
        self.value = value

    def format(self, resolve: Resolver) -> str:
        return f"bconst {'true' if self.value else 'false'}"


class StringLiteralInst(Instruction):
    opcode = "strconst"

    def __init__(self, text: str, result_type: FIRType):
        super().__init__(result_type=result_type)
        self.text = text  # raw contents without surrounding quotes

    def format(self, resolve: Resolver) -> str:
        return f'strconst "{self.text}"'


class CharLiteralInst(Instruction):
    opcode = "cconst"

    def __init__(self, text: str, result_type: FIRType):
        super().__init__(result_type=result_type)
        self.text = text  # raw contents without surrounding quotes

    def format(self, resolve: Resolver) -> str:
        return f"cconst '{self.text}'"


class NullLiteralInst(Instruction):
    opcode = "nullconst"

    def __init__(self, result_type: FIRType):
        super().__init__(result_type=result_type)

    def format(self, resolve: Resolver) -> str:
        return f"nullconst {self.result_type.render()}"


class ArrayLiteralInst(Instruction):
    opcode = "arrayconst"

    def __init__(self, elements: list[Value], result_type: FIRType):
        super().__init__(operands=list(elements), result_type=result_type)

    def format(self, resolve: Resolver) -> str:
        return f"arrayconst.{self.result_type.render()} {_fmt_array_elems(self.operands, resolve)}"


# ---------------------------------------------------------------------------
# Arithmetic / logic
# ---------------------------------------------------------------------------

class BinaryOpInst(Instruction):
    opcode = "binop"

    def __init__(self, op: str, lhs: Value, rhs: Value, result_type: FIRType):
        super().__init__(operands=[lhs, rhs], result_type=result_type)
        self.op = op

    def format(self, resolve: Resolver) -> str:
        return f'binop "{self.op}", {resolve(self.operands[0])}, {resolve(self.operands[1])}'


class UnaryOpInst(Instruction):
    opcode = "unop"

    def __init__(self, op: str, operand: Value, result_type: FIRType):
        super().__init__(operands=[operand], result_type=result_type)
        self.op = op

    def format(self, resolve: Resolver) -> str:
        return f'unop "{self.op}", {resolve(self.operands[0])}'


class CastInst(Instruction):
    opcode = "cast"

    def __init__(self, value: Value, target_type: FIRType):
        super().__init__(operands=[value], result_type=target_type)

    def format(self, resolve: Resolver) -> str:
        return f"cast.{self.result_type.render()} {resolve(self.operands[0])}"


# ---------------------------------------------------------------------------
# Memory: objects, fields, arrays
# ---------------------------------------------------------------------------

class AllocateInst(Instruction):
    """Construct a class instance; args are constructor arguments."""

    opcode = "alloc"

    def __init__(self, class_type: FIRType, args: list[Value]):
        super().__init__(operands=list(args), result_type=class_type)

    def format(self, resolve: Resolver) -> str:
        return f"alloc.{self.result_type.render()}({_fmt_args(self.operands, resolve)})"


class LoadFieldInst(Instruction):
    opcode = "loadfield"

    def __init__(self, obj: Value, field: str, result_type: FIRType):
        super().__init__(operands=[obj], result_type=result_type)
        self.field = field

    def format(self, resolve: Resolver) -> str:
        return f'loadfield.{self.result_type.render()} {resolve(self.operands[0])}, "{self.field}"'


class StoreFieldInst(Instruction):
    opcode = "storefield"

    def __init__(self, obj: Value, field: str, value: Value):
        super().__init__(operands=[obj, value])
        self.field = field

    def format(self, resolve: Resolver) -> str:
        return (
            f'storefield {resolve(self.operands[0])}, "{self.field}", '
            f"{resolve(self.operands[1])}"
        )


class ConstructVariantInst(Instruction):
    """Construct an enum value with a given active variant and payload."""

    opcode = "ctorvariant"

    def __init__(self, enum_type: FIRType, variant_name: str, payload: list[Value]):
        super().__init__(operands=list(payload), result_type=enum_type)
        self.variant_name = variant_name

    def format(self, resolve: Resolver) -> str:
        return (
            f'ctorvariant.{self.result_type.render()} "{self.variant_name}"'
            f"({_fmt_args(self.operands, resolve)})"
        )


class ExtractTagInst(Instruction):
    """Read the active-variant tag (discriminant) from an enum value."""

    opcode = "extracttag"

    def __init__(self, enum_value: Value, result_type: FIRType):
        super().__init__(operands=[enum_value], result_type=result_type)

    def format(self, resolve: Resolver) -> str:
        return f"extracttag.{self.result_type.render()} {resolve(self.operands[0])}"


class ExtractPayloadFieldInst(Instruction):
    """Read one payload field of a given variant from an enum value.

    Only valid when the enum's active tag matches `variant_name` at
    runtime; the compiler only emits this inside the corresponding match
    arm block.
    """

    opcode = "extractfield"

    def __init__(self, enum_value: Value, variant_name: str, field_index: int, result_type: FIRType):
        super().__init__(operands=[enum_value], result_type=result_type)
        self.variant_name = variant_name
        self.field_index = field_index

    def format(self, resolve: Resolver) -> str:
        return (
            f'extractfield.{self.result_type.render()} {resolve(self.operands[0])}, '
            f'"{self.variant_name}", {self.field_index}'
        )


class IndexArrayInst(Instruction):
    opcode = "indexarray"

    def __init__(self, array: Value, index: Value, result_type: FIRType):
        super().__init__(operands=[array, index], result_type=result_type)

    def format(self, resolve: Resolver) -> str:
        return f"indexarray.{self.result_type.render()} {resolve(self.operands[0])}, {resolve(self.operands[1])}"


class StoreArrayInst(Instruction):
    opcode = "storearray"

    def __init__(self, array: Value, index: Value, value: Value):
        super().__init__(operands=[array, index, value])

    def format(self, resolve: Resolver) -> str:
        ops = ", ".join(resolve(op) for op in self.operands)
        return f"storearray {ops}"


# ---------------------------------------------------------------------------
# Mutable locals (FIR is not SSA; locals are explicit named slots)
# ---------------------------------------------------------------------------

class DeclareLocalInst(Instruction):
    """Introduce a named local binding, optionally with an initial value."""

    opcode = "local"

    def __init__(self, name: str, var_type: FIRType, init: Optional[Value] = None):
        super().__init__(operands=[init] if init is not None else [])
        self.name = name
        self.var_type = var_type

    def format(self, resolve: Resolver) -> str:
        if self.operands:
            return f"local {self.name}: {self.var_type.render()} = {resolve(self.operands[0])}"
        return f"local {self.name}: {self.var_type.render()}"


class LoadVarInst(Instruction):
    opcode = "loadvar"

    def __init__(self, name: str, result_type: FIRType):
        super().__init__(result_type=result_type)
        self.name = name

    def format(self, resolve: Resolver) -> str:
        return f"loadvar.{self.result_type.render()} {self.name}"


class StoreVarInst(Instruction):
    opcode = "storevar"

    def __init__(self, name: str, value: Value):
        super().__init__(operands=[value])
        self.name = name

    def format(self, resolve: Resolver) -> str:
        return f"storevar {self.name}, {resolve(self.operands[0])}"


# ---------------------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------------------

class MoveInst(Instruction):
    opcode = "move"

    def __init__(self, value: Value):
        super().__init__(operands=[value], result_type=value.result_type)


class BorrowInst(Instruction):
    opcode = "borrow"

    def __init__(self, value: Value, mutable: bool = False):
        super().__init__(operands=[value], result_type=value.result_type)
        self.mutable = mutable

    def format(self, resolve: Resolver) -> str:
        if self.mutable:
            return f"borrow {resolve(self.operands[0])}, mut"
        return f"borrow {resolve(self.operands[0])}"


class CloneInst(Instruction):
    opcode = "clone"

    def __init__(self, value: Value):
        super().__init__(operands=[value], result_type=value.result_type)


class DropInst(Instruction):
    opcode = "drop"

    def __init__(self, value: Value):
        super().__init__(operands=[value])


# ---------------------------------------------------------------------------
# Calls
# ---------------------------------------------------------------------------

class CallInst(Instruction):
    opcode = "call"

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
        args = _fmt_args_with_modes(self.operands, self.arg_modes, resolve)
        opcode = f"call.{self.result_type.render()}" if self.result_type is not None else "call"
        return f"{opcode} @{self.function_ref}({args})"


class MethodCallInst(Instruction):
    opcode = "mcall"

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
        args = _fmt_args_with_modes(self.operands[1:], self.arg_modes, resolve)
        opcode = f"mcall.{self.result_type.render()}" if self.result_type is not None else "mcall"
        return f'{opcode} {receiver}, "{self.method}"({args})'


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

class YieldInst(Instruction):
    """Yield a value from a generator function body."""

    opcode = "yield"

    def __init__(self, value: Value):
        super().__init__(operands=[value])


class GenNewInst(Instruction):
    """Instantiate a generator: gennew.generator<T> @name(args)."""

    opcode = "gennew"

    def __init__(self, generator_ref: str, args: list[Value], result_type: FIRType):
        super().__init__(operands=list(args), result_type=result_type)
        self.generator_ref = generator_ref

    def format(self, resolve: Resolver) -> str:
        return f"gennew.{self.result_type.render()} @{self.generator_ref}({_fmt_args(self.operands, resolve)})"


class GenNextInst(Instruction):
    """Advance a generator; result is true while a value was produced."""

    opcode = "gennext"

    def __init__(self, generator: Value, result_type: FIRType):
        super().__init__(operands=[generator], result_type=result_type)

    def format(self, resolve: Resolver) -> str:
        return f"gennext.{self.result_type.render()} {resolve(self.operands[0])}"


class GenValueInst(Instruction):
    """Read the current value of a generator after a successful GenNext."""

    opcode = "genvalue"

    def __init__(self, generator: Value, result_type: FIRType):
        super().__init__(operands=[generator], result_type=result_type)

    def format(self, resolve: Resolver) -> str:
        return f"genvalue.{self.result_type.render()} {resolve(self.operands[0])}"


# ---------------------------------------------------------------------------
# Terminators
# ---------------------------------------------------------------------------

class Terminator(Instruction):
    """Base class for block-terminating instructions."""


class ReturnInst(Terminator):
    opcode = "ret"

    def __init__(self, value: Optional[Value] = None):
        super().__init__(operands=[value] if value is not None else [])

    def format(self, resolve: Resolver) -> str:
        if self.operands:
            return f"ret {resolve(self.operands[0])}"
        return "ret"


class BranchInst(Terminator):
    opcode = "br"

    def __init__(self, cond: Value, true_block: str, false_block: str):
        super().__init__(operands=[cond])
        self.true_block = true_block
        self.false_block = false_block

    def format(self, resolve: Resolver) -> str:
        return f"br {resolve(self.operands[0])}, {self.true_block}, {self.false_block}"


class JumpInst(Terminator):
    opcode = "jmp"

    def __init__(self, target_block: str):
        super().__init__()
        self.target_block = target_block

    def format(self, resolve: Resolver) -> str:
        return f"jmp {self.target_block}"


class UnreachableInst(Terminator):
    opcode = "unreachable"

    def format(self, resolve: Resolver) -> str:
        return "unreachable"


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
