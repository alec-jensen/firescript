"""FLIR types, instructions, blocks, functions, and modules.

Design rules:
- Every value is a scalar (fixed-width int/float/bool), a pointer, or a
  by-value struct (copyable classes, SyscallResult, generator frames).
- Locals are named slots; instruction results are numbered at dump time.
- All sizes, alignments, and field offsets are explicit so backends can
  emit code without consulting high-level semantics.
- Calls into the firescript runtime use the fs_rt_* namespace; backends
  resolve those names against the runtime implementation.
"""

from __future__ import annotations

from typing import Callable, Optional

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

_SCALAR_SIZES = {
    "i8": 1,
    "i16": 2,
    "i32": 4,
    "i64": 8,
    "u8": 1,
    "u16": 2,
    "u32": 4,
    "u64": 8,
    "f32": 4,
    "f64": 8,
    "bool": 1,
    "ptr": 8,
    "void": 0,
}

# Name of the builtin 16-byte struct that represents a float128 value.
F128_STRUCT_NAME = "__f128"


class FLIRType:
    """A FLIR value type: scalar, pointer, or by-value struct."""

    def __init__(self, kind: str, struct_name: Optional[str] = None, pointee: Optional[str] = None):
        self.kind = kind  # one of _SCALAR_SIZES keys, or "struct"
        self.struct_name = struct_name  # for kind == "struct"
        self.pointee = pointee  # for kind == "ptr": struct name or scalar kind, informational

    def size(self, module: Optional["FLIRModule"] = None) -> int:
        if self.kind == "struct":
            if module is None:
                raise ValueError(f"struct {self.struct_name} size requires module context")
            return module.struct(self.struct_name).size
        return _SCALAR_SIZES[self.kind]

    def align(self, module: Optional["FLIRModule"] = None) -> int:
        if self.kind == "struct":
            if module is None:
                raise ValueError(f"struct {self.struct_name} align requires module context")
            return module.struct(self.struct_name).align
        return max(1, _SCALAR_SIZES[self.kind])

    def is_float(self) -> bool:
        return self.kind in ("f32", "f64")

    def is_signed_int(self) -> bool:
        return self.kind in ("i8", "i16", "i32", "i64")

    def is_unsigned_int(self) -> bool:
        return self.kind in ("u8", "u16", "u32", "u64")

    def render(self) -> str:
        if self.kind == "struct":
            return f"%{self.struct_name}"
        if self.kind == "ptr" and self.pointee:
            return f"ptr<{self.pointee}>"
        return self.kind

    def __eq__(self, other: object) -> bool:
        return isinstance(other, FLIRType) and self.render() == other.render()

    def __hash__(self) -> int:
        return hash(self.render())

    def __repr__(self) -> str:
        return f"<FLIRType {self.render()}>"


I8 = FLIRType("i8")
I16 = FLIRType("i16")
I32 = FLIRType("i32")
I64 = FLIRType("i64")
U8 = FLIRType("u8")
U16 = FLIRType("u16")
U32 = FLIRType("u32")
U64 = FLIRType("u64")
F32 = FLIRType("f32")
F64 = FLIRType("f64")
BOOL = FLIRType("bool")
PTR = FLIRType("ptr")
VOID = FLIRType("void")
# float128 lives as a 16-byte by-value struct in FLIR.
F128 = FLIRType("struct", struct_name=F128_STRUCT_NAME)


def ptr_to(pointee: str) -> FLIRType:
    return FLIRType("ptr", pointee=pointee)


def struct_type(name: str) -> FLIRType:
    return FLIRType("struct", struct_name=name)


def ensure_f128_struct(module: "FLIRModule") -> None:
    """Ensure the __f128 struct (16-byte, align 16) exists in the module."""
    if module.has_struct(F128_STRUCT_NAME):
        return
    s = FLIRStruct(F128_STRUCT_NAME, kind="builtin")
    module.add_struct(s)
    # Two uint64 fields: lo (bytes 0..7) and hi (bytes 8..15).
    s.fields = [("lo", U64, 0), ("hi", U64, 8)]
    s.size = 16
    s.align = 16


def align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


class FLIRStruct:
    """A struct layout with explicit field offsets, size, and alignment."""

    def __init__(self, name: str, kind: str = "class"):
        self.name = name
        self.kind = kind  # "class" | "enum" | "generator_frame" | "builtin"
        self.fields: list[tuple[str, FLIRType, int]] = []  # (name, type, offset)
        self.size = 0
        self.align = 1
        # For kind == "enum" only: variant name -> its payload fields, laid
        # out independently starting at the shared payload region offset
        # (different variants' fields may share the same byte offsets, like
        # a C union of structs).
        self.variant_layouts: dict[str, list[tuple[str, FLIRType, int]]] = {}

    def add_field(self, name: str, field_type: FLIRType, module: "FLIRModule") -> int:
        field_align = field_type.align(module)
        field_size = field_type.size(module)
        offset = align_up(self.size, field_align)
        self.fields.append((name, field_type, offset))
        self.size = offset + field_size
        self.align = max(self.align, field_align)
        return offset

    def finalize(self) -> None:
        if self.size == 0:
            # C requires structs to have nonzero size.
            self.size = 1
        self.size = align_up(self.size, self.align)

    def field(self, name: str) -> tuple[str, FLIRType, int]:
        for entry in self.fields:
            if entry[0] == name:
                return entry
        raise KeyError(f"struct {self.name} has no field {name}")


# ---------------------------------------------------------------------------
# Values and instructions
# ---------------------------------------------------------------------------

class FValue:
    """A value produced by an instruction."""

    def __init__(self, instruction: "FInst"):
        self.instruction = instruction

    @property
    def value_type(self) -> FLIRType:
        return self.instruction.result_type


Resolver = Callable[["FValue"], str]


class FInst:
    """Base FLIR instruction."""

    opcode = "inst"

    def __init__(self, operands: Optional[list[FValue]] = None, result_type: Optional[FLIRType] = None):
        self.operands: list[FValue] = operands or []
        self.result_type = result_type
        self._result: Optional[FValue] = None

    def has_result(self) -> bool:
        return self.result_type is not None and self.result_type.kind != "void"

    def result(self) -> FValue:
        if self._result is None:
            self._result = FValue(self)
        return self._result

    def format(self, resolve: Resolver) -> str:
        args = ", ".join(resolve(op) for op in self.operands)
        return f"{self.opcode} {args}".rstrip()


class ConstInt(FInst):
    opcode = "const"

    def __init__(self, text: str, result_type: FLIRType):
        super().__init__(result_type=result_type)
        self.text = text

    def format(self, resolve: Resolver) -> str:
        return f"const.{self.result_type.kind} {self.text}"


class ConstFloat(FInst):
    opcode = "fconst"

    def __init__(self, text: str, result_type: FLIRType):
        super().__init__(result_type=result_type)
        self.text = text

    def format(self, resolve: Resolver) -> str:
        return f"fconst.{self.result_type.kind} {self.text}"


class ConstF128(FInst):
    """A float128 literal: stores the 16 raw bytes (lo_bits: int, hi_bits: int)
    where lo_bits = LO qword (bytes 0..7) and hi_bits = HI qword (bytes 8..15),
    both as unsigned 64-bit integers matching the IEEE binary128 representation."""

    opcode = "f128const"

    def __init__(self, lo_bits: int, hi_bits: int, struct_type_val: "FLIRType"):
        super().__init__(result_type=struct_type_val)
        self.lo_bits = lo_bits  # unsigned 64-bit LO qword
        self.hi_bits = hi_bits  # unsigned 64-bit HI qword

    def format(self, resolve: Resolver) -> str:
        return f"f128const 0x{self.lo_bits:016x}:{self.hi_bits:016x}"


class ConstBool(FInst):
    opcode = "bconst"

    def __init__(self, value: bool):
        super().__init__(result_type=BOOL)
        self.value = value

    def format(self, resolve: Resolver) -> str:
        return f"bconst {'true' if self.value else 'false'}"


class ConstStr(FInst):
    """Pointer to a NUL-terminated string literal in read-only data."""

    opcode = "strconst"

    def __init__(self, text: str):
        super().__init__(result_type=ptr_to("i8"))
        self.text = text  # escaped source text (no surrounding quotes)

    def format(self, resolve: Resolver) -> str:
        return f'strconst "{self.text}"'


class ConstNull(FInst):
    opcode = "nullconst"

    def __init__(self):
        super().__init__(result_type=PTR)

    def format(self, resolve: Resolver) -> str:
        return "nullconst"


class BinOp(FInst):
    """Typed binary op. op in {add,sub,mul,div,mod,pow} or comparison
    {eq,ne,lt,le,gt,ge} (comparisons produce bool)."""

    opcode = "binop"

    def __init__(self, op: str, operand_type: FLIRType, lhs: FValue, rhs: FValue, result_type: FLIRType):
        super().__init__(operands=[lhs, rhs], result_type=result_type)
        self.op = op
        self.operand_type = operand_type

    def format(self, resolve: Resolver) -> str:
        return (
            f"{self.op}.{self.operand_type.kind} "
            f"{resolve(self.operands[0])}, {resolve(self.operands[1])}"
        )


class Not(FInst):
    opcode = "not"

    def __init__(self, value: FValue):
        super().__init__(operands=[value], result_type=BOOL)

    def format(self, resolve: Resolver) -> str:
        return f"not {resolve(self.operands[0])}"


class Neg(FInst):
    opcode = "neg"

    def __init__(self, value: FValue, result_type: FLIRType):
        super().__init__(operands=[value], result_type=result_type)

    def format(self, resolve: Resolver) -> str:
        return f"neg.{self.result_type.kind} {resolve(self.operands[0])}"


class Cvt(FInst):
    """Numeric conversion between scalar types (C cast semantics)."""

    opcode = "cvt"

    def __init__(self, value: FValue, from_type: FLIRType, to_type: FLIRType):
        super().__init__(operands=[value], result_type=to_type)
        self.from_type = from_type

    def format(self, resolve: Resolver) -> str:
        return f"cvt.{self.from_type.kind}_to_{self.result_type.kind} {resolve(self.operands[0])}"


class Load(FInst):
    """Load a value of a given type from base pointer + byte offset."""

    opcode = "load"

    def __init__(self, value_type: FLIRType, base: FValue, offset: int):
        super().__init__(operands=[base], result_type=value_type)
        self.offset = offset

    def format(self, resolve: Resolver) -> str:
        return f"load.{self.result_type.render()} {resolve(self.operands[0])}, {self.offset}"


class Store(FInst):
    """Store a value at base pointer + byte offset."""

    opcode = "store"

    def __init__(self, value_type: FLIRType, base: FValue, offset: int, value: FValue):
        super().__init__(operands=[base, value])
        self.value_type = value_type
        self.offset = offset

    def format(self, resolve: Resolver) -> str:
        return (
            f"store.{self.value_type.render()} {resolve(self.operands[0])}, "
            f"{self.offset}, {resolve(self.operands[1])}"
        )


class PtrAdd(FInst):
    """Pointer arithmetic: base + index * scale (byte scale)."""

    opcode = "ptradd"

    def __init__(self, base: FValue, index: FValue, scale: int):
        super().__init__(operands=[base, index], result_type=PTR)
        self.scale = scale

    def format(self, resolve: Resolver) -> str:
        return f"ptradd {resolve(self.operands[0])}, {resolve(self.operands[1])}, {self.scale}"


class SlotDecl(FInst):
    """Declare a named local slot of a given type."""

    opcode = "slot"

    def __init__(self, name: str, slot_type: FLIRType):
        super().__init__()
        self.name = name
        self.slot_type = slot_type

    def format(self, resolve: Resolver) -> str:
        return f"slot {self.name}: {self.slot_type.render()}"


class SlotLoad(FInst):
    opcode = "slotload"

    def __init__(self, name: str, value_type: FLIRType):
        super().__init__(result_type=value_type)
        self.name = name

    def format(self, resolve: Resolver) -> str:
        return f"slotload.{self.result_type.render()} {self.name}"


class SlotStore(FInst):
    opcode = "slotstore"

    def __init__(self, name: str, value: FValue):
        super().__init__(operands=[value])
        self.name = name

    def format(self, resolve: Resolver) -> str:
        return f"slotstore {self.name}, {resolve(self.operands[0])}"


class SlotAddr(FInst):
    """Address of a named local slot."""

    opcode = "slotaddr"

    def __init__(self, name: str, pointee: Optional[str] = None):
        super().__init__(result_type=FLIRType("ptr", pointee=pointee))
        self.name = name

    def format(self, resolve: Resolver) -> str:
        return f"slotaddr {self.name}"


class GlobalLoad(FInst):
    """Read a module-level constant or mutable global cell."""

    opcode = "gload"

    def __init__(self, name: str, value_type: FLIRType):
        super().__init__(result_type=value_type)
        self.name = name

    def format(self, resolve: Resolver) -> str:
        return f"gload.{self.result_type.render()} @{self.name}"


class GlobalStore(FInst):
    """Write a mutable module-level global cell."""

    opcode = "gstore"

    def __init__(self, name: str, value: FValue):
        super().__init__(operands=[value])
        self.name = name

    def format(self, resolve: Resolver) -> str:
        return f"gstore @{self.name}, {resolve(self.operands[0])}"


class Call(FInst):
    opcode = "call"

    def __init__(self, callee: str, args: list[FValue], result_type: FLIRType = VOID):
        super().__init__(operands=list(args), result_type=result_type)
        self.callee = callee

    def format(self, resolve: Resolver) -> str:
        args = ", ".join(resolve(op) for op in self.operands)
        return f"call.{self.result_type.render()} @{self.callee}({args})"


class Ret(FInst):
    opcode = "ret"

    def __init__(self, value: Optional[FValue] = None):
        super().__init__(operands=[value] if value is not None else [])

    def format(self, resolve: Resolver) -> str:
        if self.operands:
            return f"ret {resolve(self.operands[0])}"
        return "ret"


class Br(FInst):
    opcode = "br"

    def __init__(self, cond: FValue, true_block: str, false_block: str):
        super().__init__(operands=[cond])
        self.true_block = true_block
        self.false_block = false_block

    def format(self, resolve: Resolver) -> str:
        return f"br {resolve(self.operands[0])}, {self.true_block}, {self.false_block}"


class Jmp(FInst):
    opcode = "jmp"

    def __init__(self, target: str):
        super().__init__()
        self.target = target

    def format(self, resolve: Resolver) -> str:
        return f"jmp {self.target}"


class Unreachable(FInst):
    opcode = "unreachable"

    def format(self, resolve: Resolver) -> str:
        return "unreachable"


TERMINATOR_OPS = ("ret", "br", "jmp", "unreachable")


# ---------------------------------------------------------------------------
# Blocks, functions, modules
# ---------------------------------------------------------------------------

class FLIRBlock:
    def __init__(self, block_id: str):
        self.id = block_id
        self.instructions: list[FInst] = []

    def add(self, inst: FInst) -> Optional[FValue]:
        if self.is_terminated():
            raise ValueError(f"FLIR block {self.id} already terminated")
        self.instructions.append(inst)
        return inst.result() if inst.has_result() else None

    def is_terminated(self) -> bool:
        return bool(self.instructions) and self.instructions[-1].opcode in TERMINATOR_OPS


class FLIRFunction:
    def __init__(
        self,
        name: str,
        params: Optional[list[tuple[str, FLIRType]]] = None,
        return_type: FLIRType = VOID,
    ):
        self.name = name
        self.params = params or []
        self.return_type = return_type
        self.blocks: list[FLIRBlock] = []
        self.metadata: dict = {}
        self._block_counter = 0

    def new_block(self) -> FLIRBlock:
        block = FLIRBlock(f"L{self._block_counter}")
        self._block_counter += 1
        self.blocks.append(block)
        return block

    def validate(self) -> None:
        ids = set()
        for block in self.blocks:
            if block.id in ids:
                raise ValueError(f"duplicate FLIR block id {block.id} in {self.name}")
            ids.add(block.id)
            if not block.is_terminated():
                raise ValueError(f"FLIR block {block.id} in {self.name} has no terminator")
        for block in self.blocks:
            last = block.instructions[-1]
            targets = []
            if isinstance(last, Br):
                targets = [last.true_block, last.false_block]
            elif isinstance(last, Jmp):
                targets = [last.target]
            for target in targets:
                if target not in ids:
                    raise ValueError(
                        f"FLIR block {block.id} in {self.name} targets unknown block {target}"
                    )


class FLIRModule:
    def __init__(self, name: str = "firescript"):
        self.name = name
        self.structs: list[FLIRStruct] = []
        self.functions: list[FLIRFunction] = []
        self.globals: list[tuple[str, FLIRType, str]] = []  # (name, type, literal text)
        # Mutable global cells: (name, type, zero-initialized)
        self.mutable_globals: list[tuple[str, FLIRType]] = []
        # External imports: symbol -> (dll, return type, param types)
        self.externs: dict[str, tuple[str, FLIRType, list[FLIRType]]] = {}
        self.entry_function: Optional[str] = None
        self._struct_index: dict[str, FLIRStruct] = {}

    def add_struct(self, s: FLIRStruct) -> FLIRStruct:
        self.structs.append(s)
        self._struct_index[s.name] = s
        return s

    def struct(self, name: str) -> FLIRStruct:
        return self._struct_index[name]

    def has_struct(self, name: str) -> bool:
        return name in self._struct_index

    def add_function(self, f: FLIRFunction) -> FLIRFunction:
        self.functions.append(f)
        return f

    def validate(self) -> None:
        for f in self.functions:
            f.validate()
