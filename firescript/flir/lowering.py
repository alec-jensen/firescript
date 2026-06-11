"""FIR -> FLIR lowering.

Responsibilities:
- monomorphize generic functions and classes (deterministic name mangling)
- lower classes to struct layouts (declaration order, natural alignment,
  padding to max field alignment; inherited fields first)
- lower ownership ops to explicit allocation / free / destructor calls
- lower generators to state-machine frame structs with init/next functions
- lower strings to ptr<i8> (NUL-terminated, heap) with fs_rt_* runtime calls
- lower arrays to ptr + statically tracked lengths (array params get an
  implicit trailing `<name>_len: i32` parameter, matching the legacy ABI)

Runtime ABI: all runtime entry points use the fs_rt_* namespace; the
backend maps them onto the runtime implementation.
"""

from __future__ import annotations

import logging
from typing import Optional

from fir.ir_module import FIRFunction, FIRModule, TypeDef
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
    DeclareLocalInst,
    DropInst,
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
    ParamValue,
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
from fir.ir_types import (
    ArrayType,
    FIRType,
    FunctionType,
    GeneratorType,
    GenericInstanceType,
    SimpleType,
)

from flir.ir import (
    BOOL,
    BinOp,
    Br,
    Call,
    GlobalLoad,
    ConstBool,
    ConstFloat,
    ConstInt,
    ConstNull,
    ConstStr,
    Cvt,
    F32,
    F64,
    FInst,
    FLIRBlock,
    FLIRFunction,
    FLIRModule,
    FLIRStruct,
    FLIRType,
    FValue,
    GlobalStore,
    I8,
    I16,
    I32,
    I64,
    Jmp,
    Load,
    Neg,
    Not,
    PtrAdd,
    PTR,
    Ret,
    SlotAddr,
    SlotDecl,
    SlotLoad,
    SlotStore,
    Store,
    U8,
    U16,
    U32,
    U64,
    Unreachable,
    VOID,
    ptr_to,
    struct_type,
)

_SCALARS: dict[str, FLIRType] = {
    "int8": I8,
    "int16": I16,
    "int32": I32,
    "int64": I64,
    "uint8": U8,
    "uint16": U16,
    "uint32": U32,
    "uint64": U64,
    "float32": F32,
    "float64": F64,
    "float128": F64,  # alias of float64
    "bool": BOOL,
    "char": I8,
    "void": VOID,
}

_CHAR_ESCAPES = {
    "\\n": 10,
    "\\t": 9,
    "\\r": 13,
    "\\0": 0,
    "\\\\": 92,
    "\\'": 39,
    '\\"': 34,
}

_CMP_OPS = {"==": "eq", "!=": "ne", "<": "lt", "<=": "le", ">": "gt", ">=": "ge"}
_ARITH_OPS = {"+": "add", "-": "sub", "*": "mul", "/": "div", "%": "mod"}


def sanitize(name: str) -> str:
    return (
        name.replace(".", "__")
        .replace("<", "_")
        .replace(">", "")
        .replace(",", "_")
        .replace(" ", "")
        .replace("[]", "_arr")
    )


def mangle_mono(base: str, type_args: list[str]) -> str:
    if not type_args:
        return sanitize(base)
    return sanitize(base) + "__" + "_".join(sanitize(t) for t in type_args)


class LoweringError(Exception):
    pass


class _FuncCtx:
    """Per-function lowering state."""

    def __init__(self, flir_func: FLIRFunction, type_map: Optional[dict[str, str]] = None):
        self.func = flir_func
        self.type_map = type_map or {}
        self.block: Optional[FLIRBlock] = None
        self.block_map: dict[str, FLIRBlock] = {}
        self.values: dict[int, FValue] = {}  # id(fir Instruction) -> FValue
        self.slot_types: dict[str, FLIRType] = {}
        # slot -> ("const", n) | ("slot", len_slot_name) for arrays
        self.array_lens: dict[str, tuple] = {}
        # slot -> element FIR type string, for arrays
        self.array_elems: dict[str, str] = {}
        # slot -> generator fir name, for generator frames
        self.gen_slots: dict[str, str] = {}
        # generator-next lowering: vars live in the frame
        self.frame_struct: Optional[FLIRStruct] = None
        self.frame_param: Optional[str] = None
        self.out_param: Optional[str] = None
        self.yield_counter = 0
        self.resume_blocks: list[FLIRBlock] = []
        self.temp_counter = 0

    def temp(self, prefix: str) -> str:
        self.temp_counter += 1
        return f"__{prefix}{self.temp_counter}"

    def emit(self, inst: FInst) -> Optional[FValue]:
        return self.block.add(inst)


class FIRToFLIRLowering:
    def __init__(self, fir_module: FIRModule, runtime_module: Optional[FIRModule] = None):
        self.fir = fir_module
        self.flir = FLIRModule(fir_module.name)

        self.typedefs: dict[str, TypeDef] = {t.name: t for t in fir_module.types}
        self.global_consts: dict[str, str] = {
            c.name: sanitize(c.name) for c in fir_module.constants
        }
        self.fir_funcs: dict[str, FIRFunction] = {f.name: f for f in fir_module.functions}
        if runtime_module is not None:
            # The firescript-implemented runtime: functions become callable
            # targets for fs_rt_* routing but stay out of the user's FIR dump.
            for func in runtime_module.functions:
                self.fir_funcs.setdefault(func.name, func)
            for type_def in runtime_module.types:
                self.typedefs.setdefault(type_def.name, type_def)
        # (fir name, tuple(type_args)) -> lowered name; also marks enqueued work
        self.lowered_names: dict[tuple[str, tuple], str] = {}
        self.worklist: list[tuple[FIRFunction, dict[str, str], str]] = []
        self.destructors: dict[str, str] = {}  # concrete class key -> destroy fn name
        self.generators_lowered: set[str] = set()
        # concrete struct name -> (TypeDef, type_map) for destructor generation
        self.struct_sources: dict[str, tuple[TypeDef, dict[str, str]]] = {}

    # ------------------------------------------------------------------
    # Types
    # ------------------------------------------------------------------

    def subst(self, type_str: str, type_map: dict[str, str]) -> str:
        if type_str in type_map:
            return type_map[type_str]
        return type_str

    def lower_type(self, t: FIRType, type_map: dict[str, str]) -> FLIRType:
        if isinstance(t, SimpleType):
            name = self.subst(t.name, type_map)
            if name.endswith("[]"):
                return PTR
            if name in _SCALARS:
                return _SCALARS[name]
            if name == "string":
                return ptr_to("i8")
            if name == "null":
                return PTR
            if name in self.typedefs:
                td = self.typedefs[name]
                args = [self.subst(p, type_map) for p in td.generic_params]
                struct_name = self.ensure_struct(name, args)
                if td.category == "copyable":
                    return struct_type(struct_name)
                return ptr_to(struct_name)
            if name == "SyscallResult":
                return struct_type(self.ensure_struct(name, []))
            # Unsubstituted generic parameter or unknown named type: treat
            # as pointer-sized owned value.
            return PTR
        if isinstance(t, ArrayType):
            return PTR
        if isinstance(t, GeneratorType):
            return PTR  # only meaningful through gen slots
        if isinstance(t, GenericInstanceType):
            args = [self.render_concrete(a, type_map) for a in t.type_args]
            struct_name = self.ensure_struct(t.base_name, args)
            if t.base_name in self.typedefs and self.typedefs[t.base_name].category == "copyable":
                return struct_type(struct_name)
            return ptr_to(struct_name)
        if isinstance(t, FunctionType):
            return PTR
        raise LoweringError(f"cannot lower FIR type {t.render()}")

    def render_concrete(self, t: FIRType, type_map: dict[str, str]) -> str:
        """Render a FIR type to a concrete firescript type string."""
        if isinstance(t, SimpleType):
            return self.subst(t.name, type_map)
        if isinstance(t, ArrayType):
            return self.render_concrete(t.element_type, type_map) + "[]"
        if isinstance(t, GeneratorType):
            return f"generator<{self.render_concrete(t.element_type, type_map)}>"
        if isinstance(t, GenericInstanceType):
            args = ", ".join(self.render_concrete(a, type_map) for a in t.type_args)
            return f"{t.base_name}<{args}>"
        return t.render()

    def lower_type_str(self, type_str: str, type_map: dict[str, str]) -> FLIRType:
        type_str = self.subst(type_str, type_map)
        if type_str.endswith("[]"):
            return PTR
        if type_str in _SCALARS:
            return _SCALARS[type_str]
        if type_str == "string":
            return ptr_to("i8")
        if type_str.startswith("generator<"):
            return PTR
        if "<" in type_str and type_str.endswith(">"):
            base, args_text = type_str.split("<", 1)
            args = [a.strip() for a in args_text[:-1].split(",")]
            struct_name = self.ensure_struct(base, args)
            if base in self.typedefs and self.typedefs[base].category == "copyable":
                return struct_type(struct_name)
            return ptr_to(struct_name)
        if type_str in self.typedefs:
            td = self.typedefs[type_str]
            args = [self.subst(p, type_map) for p in td.generic_params]
            struct_name = self.ensure_struct(type_str, args)
            if td.category == "copyable":
                return struct_type(struct_name)
            return ptr_to(struct_name)
        if type_str == "SyscallResult":
            return struct_type(self.ensure_struct(type_str, []))
        return PTR

    def class_fields_full(self, type_def: TypeDef) -> list[tuple[str, FIRType]]:
        """Fields including base-chain fields (base first), deduplicated."""
        chain: list[TypeDef] = []
        seen: set[str] = set()
        current: Optional[TypeDef] = type_def
        while current is not None and current.name not in seen:
            seen.add(current.name)
            chain.append(current)
            current = self.typedefs.get(current.base) if current.base else None
        fields: list[tuple[str, FIRType]] = []
        names: set[str] = set()
        for td in reversed(chain):
            for fname, ftype in td.fields:
                if fname not in names:
                    fields.append((fname, ftype))
                    names.add(fname)
        return fields

    def ensure_struct(self, class_name: str, type_args: list[str]) -> str:
        """Lower a (possibly generic) class to a struct; returns struct name."""
        if class_name == "SyscallResult" and class_name not in self.typedefs:
            # Compiler-internal copyable struct backing the syscall_* intrinsics.
            if not self.flir.has_struct("SyscallResult"):
                struct = FLIRStruct("SyscallResult", kind="builtin")
                self.flir.add_struct(struct)
                struct.add_field("status", I32, self.flir)
                struct.add_field("data", ptr_to("i8"), self.flir)
                struct.finalize()
            return "SyscallResult"
        type_def = self.typedefs.get(class_name)
        if type_def is None:
            raise LoweringError(f"unknown class {class_name}")
        struct_name = mangle_mono(class_name, type_args)
        if self.flir.has_struct(struct_name):
            return struct_name

        type_map = dict(zip(type_def.generic_params, type_args))
        struct = FLIRStruct(struct_name, kind="class")
        self.flir.add_struct(struct)  # add before fields to allow self-reference via ptr
        for fname, ftype in self.class_fields_full(type_def):
            struct.add_field(fname, self.lower_type(ftype, type_map), self.flir)
        struct.finalize()
        self.struct_sources[struct_name] = (type_def, type_map)
        return struct_name

    def is_copyable_class_str(self, type_str: str) -> bool:
        base = type_str.split("<")[0]
        if base == "SyscallResult" and base not in self.typedefs:
            return True
        td = self.typedefs.get(base)
        return td is not None and td.category == "copyable"

    def struct_for_class_str(self, type_str: str, type_map: Optional[dict[str, str]] = None) -> str:
        type_map = type_map or {}
        if "<" in type_str and type_str.endswith(">"):
            base, args_text = type_str.split("<", 1)
            args = [self.subst(a.strip(), type_map) for a in args_text[:-1].split(",")]
            return self.ensure_struct(base, args)
        td = self.typedefs.get(type_str)
        if td is not None and td.generic_params:
            # Bare generic class name inside its own methods: fill the type
            # args from the active monomorphization map.
            args = [self.subst(p, type_map) for p in td.generic_params]
            return self.ensure_struct(type_str, args)
        return self.ensure_struct(type_str, [])

    # ------------------------------------------------------------------
    # Driver
    # ------------------------------------------------------------------

    def lower(self) -> FLIRModule:
        # Builtin runtime struct: SyscallResult comes from std as a class.
        for constant in self.fir.constants:
            const_type = self.lower_type(constant.const_type, {})
            self.flir.globals.append((sanitize(constant.name), const_type, constant.literal_text))

        # Roots: every non-generic function (generators lower on demand).
        for func in self.fir.functions:
            if func.generic_params:
                continue
            if func.is_generator:
                continue
            if func.name.startswith("fs_rt_"):
                # Runtime implementations lower on demand via rt_call so
                # they get the impl_ prefix and dead ones are skipped.
                continue
            method_class = func.metadata.get("class_name")
            if method_class and self.typedefs.get(method_class) and self.typedefs[method_class].generic_params:
                continue  # methods of generic classes lower per instantiation
            lowered = "fs_main" if func.name == "main" else sanitize(func.name)
            self.lowered_names[(func.name, ())] = lowered
            self.worklist.append((func, {}, lowered))

        self.flir.entry_function = "fs_main" if ("main", ()) in self.lowered_names else None

        while self.worklist:
            fir_func, type_map, lowered_name = self.worklist.pop(0)
            self.lower_function(fir_func, type_map, lowered_name)

        self.flir.validate()
        return self.flir

    def request_function(self, fir_name: str, type_args: list[str]) -> str:
        """Get (or enqueue) the lowered name for a function instantiation."""
        key = (fir_name, tuple(type_args))
        if key in self.lowered_names:
            return self.lowered_names[key]
        func = self.fir_funcs.get(fir_name)
        if func is None:
            raise LoweringError(f"call to unknown function {fir_name}")
        lowered = mangle_mono("fs_main" if fir_name == "main" else fir_name, type_args)
        if fir_name.startswith("fs_rt_"):
            # firescript-implemented runtime entry point: keep it distinct
            # from the backend-provided fs_rt_* shim namespace.
            lowered = "impl_" + lowered
        self.lowered_names[key] = lowered
        type_map = dict(zip(func.generic_params, type_args))
        if func.is_generator:
            # Generators lower as frame struct + init + next.
            self.lower_generator(func, type_map, lowered)
        else:
            self.worklist.append((func, type_map, lowered))
        return lowered

    # ------------------------------------------------------------------
    # Function lowering
    # ------------------------------------------------------------------

    def _lowered_params(
        self, fir_func: FIRFunction, type_map: dict[str, str], ctx: _FuncCtx
    ) -> list[tuple[str, FLIRType]]:
        params: list[tuple[str, FLIRType]] = []
        for (pname, ptype), _mode in zip(fir_func.params, fir_func.param_modes):
            lowered_type = self.lower_type(ptype, type_map)
            params.append((pname, lowered_type))
            ctx.slot_types[pname] = lowered_type
            if isinstance(ptype, ArrayType):
                concrete = self.render_concrete(ptype.element_type, type_map)
                ctx.array_elems[pname] = concrete
                if type_map and False:
                    pass
                # Non-generic array params get an implicit length parameter
                # (legacy ABI). Generic instantiations do not (legacy parity).
                len_name = f"{pname}_len"
                params.append((len_name, I32))
                ctx.slot_types[len_name] = I32
                ctx.array_lens[pname] = ("slot", len_name)
        return params

    def lower_function(self, fir_func: FIRFunction, type_map: dict[str, str], lowered_name: str) -> None:
        ctx = _FuncCtx(None, type_map)
        params = self._lowered_params(fir_func, type_map, ctx)
        return_type = (
            self.lower_type(fir_func.return_type, type_map) if fir_func.return_type else VOID
        )
        flir_func = FLIRFunction(lowered_name, params, return_type)
        ctx.func = flir_func
        self.flir.add_function(flir_func)

        # Pre-create blocks
        for fir_block in fir_func.blocks:
            block = flir_func.new_block()
            ctx.block_map[fir_block.id] = block

        for fir_block in fir_func.blocks:
            ctx.block = ctx.block_map[fir_block.id]
            for inst in fir_block.instructions:
                self.lower_inst(inst, ctx)
            if fir_block.terminator is not None:
                self.lower_terminator(fir_block.terminator, ctx)

    # ------------------------------------------------------------------
    # Value helpers
    # ------------------------------------------------------------------

    def val(self, v: Value, ctx: _FuncCtx) -> FValue:
        if isinstance(v, ParamValue):
            return self.var_load(v.name, ctx.slot_types.get(v.name, PTR), ctx)
        if isinstance(v, FIRValue):
            fv = ctx.values.get(id(v.instruction))
            if fv is None:
                raise LoweringError(f"FIR value {v.instruction.opcode} has no lowered value")
            return fv
        raise LoweringError(f"unsupported FIR operand {type(v).__name__}")

    def set_val(self, inst: Instruction, fv: FValue, ctx: _FuncCtx) -> None:
        ctx.values[id(inst)] = fv

    def fir_type_str_of(self, v: Value, ctx: _FuncCtx) -> str:
        t = v.result_type
        if t is None:
            return "void"
        return self.render_concrete(t, ctx.type_map)

    # -- variable access (slots or generator frame fields) ---------------

    def var_load(self, name: str, value_type: FLIRType, ctx: _FuncCtx) -> FValue:
        if ctx.frame_struct is not None and self._frame_has(ctx, name):
            fname, ftype, offset = ctx.frame_struct.field(name)
            frame = ctx.emit(SlotLoad(ctx.frame_param, PTR))
            return ctx.emit(Load(ftype, frame, offset))
        return ctx.emit(SlotLoad(name, value_type))

    def var_store(self, name: str, value: FValue, ctx: _FuncCtx) -> None:
        if ctx.frame_struct is not None and self._frame_has(ctx, name):
            fname, ftype, offset = ctx.frame_struct.field(name)
            frame = ctx.emit(SlotLoad(ctx.frame_param, PTR))
            ctx.emit(Store(ftype, frame, offset, value))
            return
        ctx.emit(SlotStore(name, value))

    @staticmethod
    def _frame_has(ctx: _FuncCtx, name: str) -> bool:
        return any(f[0] == name for f in ctx.frame_struct.fields)

    def ensure_slot(self, name: str, slot_type: FLIRType, ctx: _FuncCtx) -> None:
        if name in ctx.slot_types:
            return
        ctx.slot_types[name] = slot_type
        ctx.emit(SlotDecl(name, slot_type))

    # ------------------------------------------------------------------
    # Instruction lowering
    # ------------------------------------------------------------------

    def lower_inst(self, inst: Instruction, ctx: _FuncCtx) -> None:
        if isinstance(inst, IntLiteralInst):
            self.set_val(inst, ctx.emit(ConstInt(inst.text, self.lower_type(inst.result_type, ctx.type_map))), ctx)
            return
        if isinstance(inst, FloatLiteralInst):
            self.set_val(inst, ctx.emit(ConstFloat(inst.text, self.lower_type(inst.result_type, ctx.type_map))), ctx)
            return
        if isinstance(inst, BoolLiteralInst):
            self.set_val(inst, ctx.emit(ConstBool(inst.value)), ctx)
            return
        if isinstance(inst, StringLiteralInst):
            self.set_val(inst, ctx.emit(ConstStr(inst.text)), ctx)
            return
        if isinstance(inst, CharLiteralInst):
            self.set_val(inst, ctx.emit(ConstInt(str(self._char_code(inst.text)), I8)), ctx)
            return
        if isinstance(inst, NullLiteralInst):
            self.set_val(inst, ctx.emit(ConstNull()), ctx)
            return
        if isinstance(inst, ArrayLiteralInst):
            self.lower_array_literal(inst, ctx)
            return
        if isinstance(inst, BinaryOpInst):
            self.lower_binary(inst, ctx)
            return
        if isinstance(inst, UnaryOpInst):
            self.lower_unary(inst, ctx)
            return
        if isinstance(inst, CastInst):
            self.lower_cast(inst, ctx)
            return
        if isinstance(inst, AllocateInst):
            self.lower_allocate(inst, ctx)
            return
        if isinstance(inst, LoadFieldInst):
            self.lower_load_field(inst, ctx)
            return
        if isinstance(inst, StoreFieldInst):
            self.lower_store_field(inst, ctx)
            return
        if isinstance(inst, IndexArrayInst):
            self.lower_index_array(inst, ctx)
            return
        if isinstance(inst, StoreArrayInst):
            self.lower_store_array(inst, ctx)
            return
        if isinstance(inst, DeclareLocalInst):
            self.lower_declare_local(inst, ctx)
            return
        if isinstance(inst, LoadVarInst):
            self.lower_load_var(inst, ctx)
            return
        if isinstance(inst, StoreVarInst):
            value = self.val(inst.operands[0], ctx)
            value = self._dup_if_literal_string(inst.operands[0], value, ctx)
            self.var_store(inst.name, value, ctx)
            return
        if isinstance(inst, (MoveInst, BorrowInst, CloneInst)):
            self.set_val(inst, self.val(inst.operands[0], ctx), ctx)
            return
        if isinstance(inst, DropInst):
            self.lower_drop(inst, ctx)
            return
        if isinstance(inst, CallInst):
            self.lower_call(inst, ctx)
            return
        if isinstance(inst, MethodCallInst):
            self.lower_method_call(inst, ctx)
            return
        if isinstance(inst, GenNewInst):
            # Deferred: the following DeclareLocal materializes the frame
            # slot and the init call (lower_gen_new_local).
            return
        if isinstance(inst, GenNextInst):
            self.lower_gen_next(inst, ctx)
            return
        if isinstance(inst, GenValueInst):
            self.lower_gen_value(inst, ctx)
            return
        if isinstance(inst, YieldInst):
            self.lower_yield(inst, ctx)
            return
        raise LoweringError(f"cannot lower FIR instruction {inst.opcode}")

    def lower_terminator(self, term: Instruction, ctx: _FuncCtx) -> None:
        if isinstance(term, ReturnInst):
            if ctx.frame_struct is not None:
                # return inside a generator body = exhaustion
                self._gen_exhaust(ctx)
                return
            if term.operands and ctx.func.return_type.kind == "void":
                # Top-level `return 0;` in script-style programs: the value
                # was already evaluated; the wrapper main supplies exit 0.
                ctx.emit(Ret())
            elif term.operands:
                ctx.emit(Ret(self.val(term.operands[0], ctx)))
            elif ctx.func.return_type.kind != "void":
                # Control may fall off the end of a non-void function in
                # source; return a zero value (legacy C fell off, which is
                # UB -- this is strictly better and output-compatible).
                zero = self._zero_value(ctx.func.return_type, ctx)
                ctx.emit(Ret(zero))
            else:
                ctx.emit(Ret())
            return
        if isinstance(term, BranchInst):
            cond = self.val(term.operands[0], ctx)
            ctx.emit(Br(cond, ctx.block_map[term.true_block].id, ctx.block_map[term.false_block].id))
            return
        if isinstance(term, JumpInst):
            ctx.emit(Jmp(ctx.block_map[term.target_block].id))
            return
        if isinstance(term, UnreachableInst):
            ctx.emit(Unreachable())
            return
        raise LoweringError(f"cannot lower terminator {term.opcode}")

    # -- literals / arrays ----------------------------------------------

    @staticmethod
    def _char_code(text: str) -> int:
        if text in _CHAR_ESCAPES:
            return _CHAR_ESCAPES[text]
        if len(text) == 1:
            return ord(text)
        # Fallback: first character of a longer/unknown escape
        return ord(text[-1])

    def lower_array_literal(self, inst: ArrayLiteralInst, ctx: _FuncCtx) -> None:
        array_type = inst.result_type
        assert isinstance(array_type, ArrayType)
        elem_str = self.render_concrete(array_type.element_type, ctx.type_map)
        elem_type = self.lower_type_str(elem_str, ctx.type_map)
        elem_size = elem_type.size(self.flir)
        count = array_type.size if array_type.size is not None else len(inst.operands)

        total = ctx.emit(ConstInt(str(max(count, 1) * elem_size), I64))
        ptr = self.rt_call("fs_rt_alloc_zeroed", [total], PTR, ctx)
        for i, operand in enumerate(inst.operands):
            value = self.val(operand, ctx)
            ctx.emit(Store(elem_type, ptr, i * elem_size, value))
        self.set_val(inst, ptr, ctx)

    # -- arithmetic -------------------------------------------------------

    def lower_binary(self, inst: BinaryOpInst, ctx: _FuncCtx) -> None:
        op = inst.op
        lhs_fir, rhs_fir = inst.operands
        operand_type_str = self.subst(inst.metadata.get("operand_type", ""), ctx.type_map)
        lhs_type_str = self.subst(self.fir_type_str_of(lhs_fir, ctx), ctx.type_map)
        rhs_type_str = self.subst(self.fir_type_str_of(rhs_fir, ctx), ctx.type_map)

        lhs = self.val(lhs_fir, ctx)
        rhs = self.val(rhs_fir, ctx)

        is_null_cmp = isinstance(lhs_fir, FIRValue) and isinstance(lhs_fir.instruction, NullLiteralInst)
        is_null_cmp = is_null_cmp or (
            isinstance(rhs_fir, FIRValue) and isinstance(rhs_fir.instruction, NullLiteralInst)
        )

        string_operands = (lhs_type_str == "string" or rhs_type_str == "string") and not is_null_cmp

        if string_operands:
            if op == "+":
                self.set_val(inst, self.rt_call("fs_rt_str_concat", [lhs, rhs], ptr_to("i8"), ctx), ctx)
                return
            if op == "==":
                self.set_val(inst, self.rt_call("fs_rt_str_eq", [lhs, rhs], BOOL, ctx), ctx)
                return
            if op == "!=":
                eq = self.rt_call("fs_rt_str_eq", [lhs, rhs], BOOL, ctx)
                self.set_val(inst, ctx.emit(Not(eq)), ctx)
                return
            raise LoweringError(f"unsupported string operator {op}")

        operand_type = self.lower_type_str(
            operand_type_str or lhs_type_str or rhs_type_str or "int32", ctx.type_map
        )
        if operand_type.kind == "ptr":
            operand_type = PTR  # pointer compares (null checks)

        if op in _CMP_OPS:
            self.set_val(inst, ctx.emit(BinOp(_CMP_OPS[op], operand_type, lhs, rhs, BOOL)), ctx)
            return

        result_type = self.lower_type(inst.result_type, ctx.type_map)
        if op == "**":
            int_kinds = ("i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64")
            if operand_type.kind in int_kinds and self.lower_type_str(rhs_type_str, ctx.type_map).kind in int_kinds:
                lhs64 = self._cvt_to(lhs, operand_type, I64, ctx)
                rhs64 = self._cvt_to(rhs, self.lower_type_str(rhs_type_str, ctx.type_map), I64, ctx)
                powed = self.rt_call("fs_rt_pow_i64", [lhs64, rhs64], I64, ctx)
                self.set_val(inst, self._cvt_to(powed, I64, result_type, ctx), ctx)
            else:
                lhs64 = self._cvt_to(lhs, operand_type, F64, ctx)
                rhs64 = self._cvt_to(rhs, self.lower_type_str(rhs_type_str, ctx.type_map), F64, ctx)
                powed = self.rt_call("fs_rt_pow_f64", [lhs64, rhs64], F64, ctx)
                self.set_val(inst, self._cvt_to(powed, F64, result_type, ctx), ctx)
            return

        if op in _ARITH_OPS:
            self.set_val(inst, ctx.emit(BinOp(_ARITH_OPS[op], result_type, lhs, rhs, result_type)), ctx)
            return
        if op in ("&&", "||"):
            # Should have been lowered to control flow in FIR; keep a
            # non-short-circuit fallback for hand-built FIR.
            flir_op = "and" if op == "&&" else "or"
            self.set_val(inst, ctx.emit(BinOp(flir_op, BOOL, lhs, rhs, BOOL)), ctx)
            return
        raise LoweringError(f"unsupported binary operator {op}")

    def _cvt_to(self, value: FValue, from_type: FLIRType, to_type: FLIRType, ctx: _FuncCtx) -> FValue:
        if from_type == to_type:
            return value
        return ctx.emit(Cvt(value, from_type, to_type))

    def lower_unary(self, inst: UnaryOpInst, ctx: _FuncCtx) -> None:
        operand = self.val(inst.operands[0], ctx)
        if inst.op == "!":
            self.set_val(inst, ctx.emit(Not(operand)), ctx)
            return
        if inst.op == "-":
            result_type = self.lower_type(inst.result_type, ctx.type_map)
            self.set_val(inst, ctx.emit(Neg(operand, result_type)), ctx)
            return
        if inst.op == "+":
            self.set_val(inst, operand, ctx)
            return
        raise LoweringError(f"unsupported unary operator {inst.op}")

    # -- casts -------------------------------------------------------------

    def lower_cast(self, inst: CastInst, ctx: _FuncCtx) -> None:
        source_str = self.subst(inst.metadata.get("source_type", "int32"), ctx.type_map)
        target_str = self.subst(self.render_concrete(inst.result_type, ctx.type_map), ctx.type_map)
        value = self.val(inst.operands[0], ctx)

        if target_str == "string":
            self.set_val(inst, self._to_string(value, source_str, inst.operands[0], ctx), ctx)
            return

        int_targets = {"int8", "int16", "int32", "int64", "uint8", "uint16", "uint32", "uint64"}
        float_targets = {"float32", "float64", "float128"}
        target_type = self.lower_type_str(target_str, ctx.type_map)

        if source_str == "string":
            if target_str in ("int64", "uint64"):
                parsed = self.rt_call("fs_rt_str_to_i64", [value], I64, ctx)
                self.set_val(inst, self._cvt_to(parsed, I64, target_type, ctx), ctx)
                return
            if target_str in int_targets:
                parsed = self.rt_call("fs_rt_str_to_i32", [value], I32, ctx)
                self.set_val(inst, self._cvt_to(parsed, I32, target_type, ctx), ctx)
                return
            if target_str in float_targets:
                parsed = self.rt_call("fs_rt_str_to_f64", [value], F64, ctx)
                self.set_val(inst, self._cvt_to(parsed, F64, target_type, ctx), ctx)
                return
            if target_str == "bool":
                self.set_val(inst, self.rt_call("fs_rt_str_to_bool", [value], BOOL, ctx), ctx)
                return
            if target_str == "char":
                code = self.rt_call("fs_rt_str_char_code", [value], I8, ctx)
                self.set_val(inst, code, ctx)
                return

        source_type = self.lower_type_str(source_str, ctx.type_map)
        self.set_val(inst, self._cvt_to(value, source_type, target_type, ctx), ctx)

    def _to_string(self, value: FValue, source_str: str, source_fir: Value, ctx: _FuncCtx) -> FValue:
        if source_str.endswith("[]"):
            return self._array_to_string(value, source_str[:-2], source_fir, ctx)
        match source_str:
            case "string":
                return self.rt_call("fs_rt_str_dup", [value], ptr_to("i8"), ctx)
            case "bool":
                return self.rt_call("fs_rt_bool_to_str", [value], ptr_to("i8"), ctx)
            case "char":
                return self.rt_call("fs_rt_char_to_str", [value], ptr_to("i8"), ctx)
            case "int8" | "int16" | "int32":
                v32 = self._cvt_to(value, self.lower_type_str(source_str, ctx.type_map), I32, ctx)
                return self.rt_call("fs_rt_i32_to_str", [v32], ptr_to("i8"), ctx)
            case "int64":
                return self.rt_call("fs_rt_i64_to_str", [value], ptr_to("i8"), ctx)
            case "uint8" | "uint16" | "uint32":
                v32 = self._cvt_to(value, self.lower_type_str(source_str, ctx.type_map), U32, ctx)
                return self.rt_call("fs_rt_u32_to_str", [v32], ptr_to("i8"), ctx)
            case "uint64":
                return self.rt_call("fs_rt_u64_to_str", [value], ptr_to("i8"), ctx)
            case "float32":
                return self.rt_call("fs_rt_f32_to_str", [value], ptr_to("i8"), ctx)
            case "float64" | "float128":
                return self.rt_call("fs_rt_f64_to_str", [value], ptr_to("i8"), ctx)
        raise LoweringError(f"cannot convert {source_str} to string")

    def _array_to_string(self, array: FValue, elem_str: str, source_fir: Value, ctx: _FuncCtx) -> FValue:
        """Build "[a, b, c]" text for an array, matching the legacy format."""
        length = self._array_length_value(source_fir, ctx)
        if length is None:
            return ctx.emit(Call("fs_rt_str_dup", [ctx.emit(ConstStr("[..."  "]"))], ptr_to("i8")))

        elem_type = self.lower_type_str(elem_str, ctx.type_map)
        elem_size = elem_type.size(self.flir)
        result_slot = ctx.temp("arrstr")
        idx_slot = ctx.temp("arridx")
        self.ensure_slot(result_slot, ptr_to("i8"), ctx)
        self.ensure_slot(idx_slot, I32, ctx)
        opener = self.rt_call("fs_rt_str_dup", [ctx.emit(ConstStr("["))], ptr_to("i8"), ctx)
        ctx.emit(SlotStore(result_slot, opener))
        ctx.emit(SlotStore(idx_slot, ctx.emit(ConstInt("0", I32))))

        header = ctx.func.new_block()
        body = ctx.func.new_block()
        sep_block = ctx.func.new_block()
        append_block = ctx.func.new_block()
        done = ctx.func.new_block()

        ctx.emit(Jmp(header.id))

        ctx.block = header
        idx = ctx.emit(SlotLoad(idx_slot, I32))
        cond = ctx.emit(BinOp("lt", I32, idx, length, BOOL))
        ctx.emit(Br(cond, body.id, done.id))

        ctx.block = body
        idx_b = ctx.emit(SlotLoad(idx_slot, I32))
        zero = ctx.emit(ConstInt("0", I32))
        first = ctx.emit(BinOp("gt", I32, idx_b, zero, BOOL))
        ctx.emit(Br(first, sep_block.id, append_block.id))

        ctx.block = sep_block
        cur = ctx.emit(SlotLoad(result_slot, ptr_to("i8")))
        sep = ctx.emit(ConstStr(", "))
        joined = self.rt_call("fs_rt_str_concat", [cur, sep], ptr_to("i8"), ctx)
        ctx.emit(SlotStore(result_slot, joined))
        ctx.emit(Jmp(append_block.id))

        ctx.block = append_block
        idx_a = ctx.emit(SlotLoad(idx_slot, I32))
        addr = ctx.emit(PtrAdd(array, idx_a, elem_size))
        elem = ctx.emit(Load(elem_type, addr, 0))
        elem_text = self._to_string(elem, elem_str, None, ctx) if elem_str != "string" else elem
        cur2 = ctx.emit(SlotLoad(result_slot, ptr_to("i8")))
        joined2 = self.rt_call("fs_rt_str_concat", [cur2, elem_text], ptr_to("i8"), ctx)
        ctx.emit(SlotStore(result_slot, joined2))
        one = ctx.emit(ConstInt("1", I32))
        nxt = ctx.emit(BinOp("add", I32, idx_a, one, I32))
        ctx.emit(SlotStore(idx_slot, nxt))
        ctx.emit(Jmp(header.id))

        ctx.block = done
        cur3 = ctx.emit(SlotLoad(result_slot, ptr_to("i8")))
        closer = ctx.emit(ConstStr("]"))
        return self.rt_call("fs_rt_str_concat", [cur3, closer], ptr_to("i8"), ctx)

    # -- objects -----------------------------------------------------------

    def lower_allocate(self, inst: AllocateInst, ctx: _FuncCtx) -> None:
        class_str = self.render_concrete(inst.result_type, ctx.type_map)
        struct_name = self.struct_for_class_str(class_str, ctx.type_map)
        struct = self.flir.struct(struct_name)
        is_copyable = self.is_copyable_class_str(class_str)

        args = [self.val(op, ctx) for op in inst.operands]

        if is_copyable:
            slot = ctx.temp("agg")
            self.ensure_slot(slot, struct_type(struct_name), ctx)
            base = ctx.emit(SlotAddr(slot, struct_name))
            zero_total = ctx.emit(ConstInt(str(struct.size), I64))
            self.rt_call("fs_rt_zero_memory", [base, zero_total], VOID, ctx)
            for (fname, ftype, offset), value in zip(struct.fields, args):
                ctx.emit(Store(ftype, base, offset, value))
            self.set_val(inst, ctx.emit(SlotLoad(slot, struct_type(struct_name))), ctx)
            return

        size = ctx.emit(ConstInt(str(struct.size), I64))
        ptr = self.rt_call("fs_rt_alloc_zeroed", [size], ptr_to(struct_name), ctx)
        for (fname, ftype, offset), value in zip(struct.fields, args):
            ctx.emit(Store(ftype, ptr, offset, value))
        self.set_val(inst, ptr, ctx)

    def _object_base(self, obj_fir: Value, obj_value: FValue, ctx: _FuncCtx) -> tuple[FValue, str]:
        """Pointer base + struct name for a field access."""
        type_str = self.subst(self.fir_type_str_of(obj_fir, ctx), ctx.type_map)
        struct_name = self.struct_for_class_str(type_str, ctx.type_map)
        if self.is_copyable_class_str(type_str):
            # By-value struct: take the address of its slot when possible,
            # otherwise spill to a temp slot.
            inst = obj_fir.instruction if isinstance(obj_fir, FIRValue) else None
            lowered = obj_value.instruction
            if isinstance(lowered, SlotLoad):
                return ctx.emit(SlotAddr(lowered.name, struct_name)), struct_name
            slot = ctx.temp("spill")
            self.ensure_slot(slot, struct_type(struct_name), ctx)
            ctx.emit(SlotStore(slot, obj_value))
            return ctx.emit(SlotAddr(slot, struct_name)), struct_name
        return obj_value, struct_name

    def lower_load_field(self, inst: LoadFieldInst, ctx: _FuncCtx) -> None:
        obj_value = self.val(inst.operands[0], ctx)
        base, struct_name = self._object_base(inst.operands[0], obj_value, ctx)
        _, ftype, offset = self.flir.struct(struct_name).field(inst.field)
        self.set_val(inst, ctx.emit(Load(ftype, base, offset)), ctx)

    def lower_store_field(self, inst: StoreFieldInst, ctx: _FuncCtx) -> None:
        obj_value = self.val(inst.operands[0], ctx)
        value = self.val(inst.operands[1], ctx)
        base, struct_name = self._object_base(inst.operands[0], obj_value, ctx)
        _, ftype, offset = self.flir.struct(struct_name).field(inst.field)
        ctx.emit(Store(ftype, base, offset, value))

    # -- arrays --------------------------------------------------------------

    def _array_info(self, array_fir: Value, ctx: _FuncCtx) -> tuple[Optional[str], Optional[int]]:
        """(slot name, static size) for an array operand when known."""
        if isinstance(array_fir, FIRValue):
            inst = array_fir.instruction
            if isinstance(inst, LoadVarInst):
                slot = inst.name
                meta = ctx.array_lens.get(slot)
                if meta and meta[0] == "const":
                    return slot, meta[1]
                return slot, None
            t = array_fir.result_type
            if isinstance(t, ArrayType) and t.size is not None:
                return None, t.size
        if isinstance(array_fir, ParamValue):
            return array_fir.name, None
        return None, None

    def _array_length_value(self, array_fir: Value, ctx: _FuncCtx) -> Optional[FValue]:
        slot, size = self._array_info(array_fir, ctx)
        if size is not None:
            return ctx.emit(ConstInt(str(size), I32))
        if slot is not None:
            meta = ctx.array_lens.get(slot)
            if meta:
                if meta[0] == "const":
                    return ctx.emit(ConstInt(str(meta[1]), I32))
                return self.var_load(meta[1], I32, ctx)
        return None

    def _elem_type_of_array(self, array_fir: Value, ctx: _FuncCtx) -> str:
        t = array_fir.result_type
        if isinstance(t, ArrayType):
            return self.render_concrete(t.element_type, ctx.type_map)
        if isinstance(array_fir, FIRValue) and isinstance(array_fir.instruction, LoadVarInst):
            slot = array_fir.instruction.name
            if slot in ctx.array_elems:
                return ctx.array_elems[slot]
        return "int32"

    def lower_index_array(self, inst: IndexArrayInst, ctx: _FuncCtx) -> None:
        array = self.val(inst.operands[0], ctx)
        index = self.val(inst.operands[1], ctx)
        elem_str = self.render_concrete(inst.result_type, ctx.type_map)
        elem_type = self.lower_type_str(elem_str, ctx.type_map)
        elem_size = elem_type.size(self.flir)
        index = self._normalize_index(inst.operands[0], index, ctx)
        addr = ctx.emit(PtrAdd(array, index, elem_size))
        self.set_val(inst, ctx.emit(Load(elem_type, addr, 0)), ctx)

    def lower_store_array(self, inst: StoreArrayInst, ctx: _FuncCtx) -> None:
        array = self.val(inst.operands[0], ctx)
        index = self.val(inst.operands[1], ctx)
        value = self.val(inst.operands[2], ctx)
        elem_str = self.fir_type_str_of(inst.operands[2], ctx)
        elem_type = self.lower_type_str(elem_str, ctx.type_map)
        elem_size = elem_type.size(self.flir)
        index = self._normalize_index(inst.operands[0], index, ctx)
        addr = ctx.emit(PtrAdd(array, index, elem_size))
        ctx.emit(Store(elem_type, addr, 0, value))

    def _normalize_index(self, array_fir: Value, index: FValue, ctx: _FuncCtx) -> FValue:
        """Negative-index normalization when the array size is known:
        idx + size * (idx < 0), computed branchlessly."""
        _, size = self._array_info(array_fir, ctx)
        if size is None:
            slot, _ = self._array_info(array_fir, ctx)
            meta = ctx.array_lens.get(slot) if slot else None
            if not meta:
                return index
            length = self._array_length_value(array_fir, ctx)
            zero = ctx.emit(ConstInt("0", I32))
            is_neg = ctx.emit(BinOp("lt", I32, index, zero, BOOL))
            neg32 = ctx.emit(Cvt(is_neg, BOOL, I32))
            adj = ctx.emit(BinOp("mul", I32, neg32, length, I32))
            return ctx.emit(BinOp("add", I32, index, adj, I32))
        length = ctx.emit(ConstInt(str(size), I32))
        zero = ctx.emit(ConstInt("0", I32))
        is_neg = ctx.emit(BinOp("lt", I32, index, zero, BOOL))
        neg32 = ctx.emit(Cvt(is_neg, BOOL, I32))
        adj = ctx.emit(BinOp("mul", I32, neg32, length, I32))
        return ctx.emit(BinOp("add", I32, index, adj, I32))

    # -- locals ----------------------------------------------------------------

    def lower_declare_local(self, inst: DeclareLocalInst, ctx: _FuncCtx) -> None:
        # Generator frame slot?
        if inst.operands and isinstance(inst.operands[0], FIRValue) and isinstance(
            inst.operands[0].instruction, GenNewInst
        ):
            self.lower_gen_new_local(inst, inst.operands[0].instruction, ctx)
            return

        var_type = inst.var_type
        lowered_type = self.lower_type(var_type, ctx.type_map)
        if ctx.frame_struct is None:
            self.ensure_slot(inst.name, lowered_type, ctx)
        if isinstance(var_type, ArrayType):
            ctx.array_elems[inst.name] = self.render_concrete(var_type.element_type, ctx.type_map)
            if var_type.size is not None:
                ctx.array_lens[inst.name] = ("const", var_type.size)
            elif inst.operands:
                # Propagate length from the initializer when it is another array.
                init = inst.operands[0]
                slot, size = self._array_info(init, ctx)
                if size is not None:
                    ctx.array_lens[inst.name] = ("const", size)
                elif slot and slot in ctx.array_lens:
                    ctx.array_lens[inst.name] = ctx.array_lens[slot]

        if inst.operands:
            value = self.val(inst.operands[0], ctx)
            value = self._dup_if_literal_string(inst.operands[0], value, ctx)
            self.var_store(inst.name, value, ctx)
        else:
            zero = self._zero_value(lowered_type, ctx)
            if zero is not None:
                self.var_store(inst.name, zero, ctx)

    def _dup_if_literal_string(self, fir_value: Value, value: FValue, ctx: _FuncCtx) -> FValue:
        if (
            isinstance(fir_value, FIRValue)
            and isinstance(fir_value.instruction, StringLiteralInst)
        ):
            return self.rt_call("fs_rt_str_dup", [value], ptr_to("i8"), ctx)
        return value

    def _zero_value(self, lowered_type: FLIRType, ctx: _FuncCtx) -> Optional[FValue]:
        if lowered_type.kind == "ptr":
            return ctx.emit(ConstNull())
        if lowered_type.kind == "bool":
            return ctx.emit(ConstBool(False))
        if lowered_type.is_float():
            return ctx.emit(ConstFloat("0", lowered_type))
        if lowered_type.kind == "struct":
            return None  # left unset; Allocate handles zeroing
        if lowered_type.kind == "void":
            return None
        return ctx.emit(ConstInt("0", lowered_type))

    def lower_load_var(self, inst: LoadVarInst, ctx: _FuncCtx) -> None:
        # Generator frames are accessed by address.
        if inst.name in ctx.gen_slots:
            self.set_val(inst, ctx.emit(SlotAddr(inst.name)), ctx)
            return
        result_type = self.lower_type(inst.result_type, ctx.type_map)
        if ctx.frame_struct is None and inst.name not in ctx.slot_types:
            if inst.name in self.global_consts:
                self.set_val(
                    inst, ctx.emit(GlobalLoad(self.global_consts[inst.name], result_type)), ctx
                )
                return
            # Reading an undeclared slot can only be a forward reference bug.
            raise LoweringError(f"load of undeclared local '{inst.name}' in {ctx.func.name}")
        self.set_val(inst, self.var_load(inst.name, result_type, ctx), ctx)

    # -- ownership ----------------------------------------------------------

    def class_needs_destructor(self, struct_name: str) -> bool:
        source = self.struct_sources.get(struct_name)
        if source is None:
            return False
        type_def, type_map = source
        for fname, ftype in self.class_fields_full(type_def):
            concrete = self.subst(self.render_concrete(ftype, type_map), type_map)
            if self._type_str_is_owned(concrete):
                return True
        return False

    def _type_str_is_owned(self, type_str: str) -> bool:
        if type_str.endswith("[]") or type_str == "string" or type_str.startswith("generator<"):
            return True
        base = type_str.split("<")[0]
        td = self.typedefs.get(base)
        return td is not None and td.category == "owned"

    def ensure_destructor(self, struct_name: str) -> str:
        """Generate (once) and return the destructor for a concrete class."""
        if struct_name in self.destructors:
            return self.destructors[struct_name]
        destroy_name = f"{struct_name}__destroy"
        self.destructors[struct_name] = destroy_name

        type_def, type_map = self.struct_sources[struct_name]
        struct = self.flir.struct(struct_name)
        func = FLIRFunction(destroy_name, [("self", ptr_to(struct_name))], VOID)
        self.flir.add_function(func)
        block = func.new_block()
        ctx = _FuncCtx(func, type_map)
        ctx.block = block
        ctx.slot_types["self"] = ptr_to(struct_name)

        for (fname, ftype) in self.class_fields_full(type_def):
            concrete = self.subst(self.render_concrete(ftype, type_map), type_map)
            if not self._type_str_is_owned(concrete):
                continue
            _, lowered_ftype, offset = struct.field(fname)
            self_val = ctx.emit(SlotLoad("self", ptr_to(struct_name)))
            field_val = ctx.emit(Load(lowered_ftype, self_val, offset))
            null = ctx.emit(ConstNull())
            non_null = ctx.emit(BinOp("ne", PTR, field_val, null, BOOL))
            free_block = func.new_block()
            next_block = func.new_block()
            ctx.emit(Br(non_null, free_block.id, next_block.id))

            ctx.block = free_block
            base = concrete.split("<")[0]
            td = self.typedefs.get(base)
            if td is not None and td.category == "owned":
                inner_struct = self.struct_for_class_str(concrete)
                if self.class_needs_destructor(inner_struct):
                    inner_destroy = self.ensure_destructor(inner_struct)
                    ctx.emit(Call(inner_destroy, [field_val], VOID))
                else:
                    self.rt_call("fs_rt_free", [field_val], VOID, ctx)
            else:
                self.rt_call("fs_rt_free", [field_val], VOID, ctx)
            ctx.emit(Jmp(next_block.id))
            ctx.block = next_block

        self_final = ctx.emit(SlotLoad("self", ptr_to(struct_name)))
        self.rt_call("fs_rt_free", [self_final], VOID, ctx)
        ctx.emit(Ret())
        return destroy_name

    def lower_drop(self, inst: DropInst, ctx: _FuncCtx) -> None:
        operand = inst.operands[0]
        type_str = self.subst(self.fir_type_str_of(operand, ctx), ctx.type_map)
        if type_str.startswith("generator<"):
            return  # generator frames live in stack slots
        if self.is_copyable_class_str(type_str):
            return  # copyable classes are stack values; nothing to free
        value = self.val(operand, ctx)
        base = type_str.split("<")[0]
        td = self.typedefs.get(base)
        if td is not None and td.category == "owned":
            struct_name = self.struct_for_class_str(type_str, ctx.type_map)
            if self.class_needs_destructor(struct_name):
                ctx.emit(Call(self.ensure_destructor(struct_name), [value], VOID))
                return
        self.rt_call("fs_rt_free", [value], VOID, ctx)

    # -- calls ----------------------------------------------------------------

    _INTRINSIC_MAP = {
        "stdout": ("fs_rt_stdout", VOID),
        "process_argc": ("fs_rt_argc", I32),
        "process_argv_at": ("fs_rt_argv_at", None),
        "str_length": ("fs_rt_str_length", I32),
        "str_char_at": ("fs_rt_str_char_at", None),
        "str_char_code_at": ("fs_rt_str_char_code_at", I8),
        "str_index_of": ("fs_rt_str_index_of", I32),
        "str_slice": ("fs_rt_str_slice", None),
        "free_shallow": ("fs_rt_free", VOID),
        "syscall_open": ("fs_rt_syscall_open", "SyscallResult"),
        "syscall_read": ("fs_rt_syscall_read", "SyscallResult"),
        "syscall_write": ("fs_rt_syscall_write", "SyscallResult"),
        "syscall_close": ("fs_rt_syscall_close", "SyscallResult"),
        "syscall_remove": ("fs_rt_syscall_remove", "SyscallResult"),
        "syscall_rename": ("fs_rt_syscall_rename", "SyscallResult"),
        "syscall_move": ("fs_rt_syscall_move", "SyscallResult"),
    }

    # Win32 externs: fir intrinsic -> (symbol, dll, return type, param types)
    _WIN_EXTERNS = {
        "win_get_process_heap": ("GetProcessHeap", U64, []),
        "win_heap_alloc": ("HeapAlloc", U64, [U64, U32, U64]),
        "win_heap_free": ("HeapFree", U32, [U64, U32, U64]),
        "win_get_std_handle": ("GetStdHandle", U64, [I32]),
        "win_write_file": ("WriteFile", I32, [U64, U64, U32, U64, U64]),
        "win_read_file": ("ReadFile", I32, [U64, U64, U32, U64, U64]),
        "win_create_file_a": ("CreateFileA", U64, [U64, U32, U32, U64, U32, U32, U64]),
        "win_close_handle": ("CloseHandle", I32, [U64]),
        "win_delete_file_a": ("DeleteFileA", I32, [U64]),
        "win_move_file_ex_a": ("MoveFileExA", I32, [U64, U64, U32]),
        "win_copy_file_a": ("CopyFileA", I32, [U64, U64, I32]),
        "win_get_last_error": ("GetLastError", U32, []),
        "win_get_command_line_a": ("GetCommandLineA", U64, []),
        "win_get_file_size": ("GetFileSize", U32, [U64, U64]),
        "win_exit_process": ("ExitProcess", VOID, [U32]),
    }

    _MEM_OPS = {
        "mem_load_u8": (U8, "load"),
        "mem_store_u8": (U8, "store"),
        "mem_load_u64": (U64, "load"),
        "mem_store_u64": (U64, "store"),
    }

    def _lower_lowlevel_intrinsic(self, inst: CallInst, name: str, args: list[FValue], ctx: _FuncCtx) -> bool:
        """Lower mem_*/win_*/state primitives. Returns True when handled."""
        if name in self._MEM_OPS:
            value_type, kind = self._MEM_OPS[name]
            addr = ctx.emit(Cvt(args[0], U64, PTR))
            if kind == "load":
                self.set_val(inst, ctx.emit(Load(value_type, addr, 0)), ctx)
            else:
                ctx.emit(Store(value_type, addr, 0, args[1]))
            return True
        if name == "mem_copy":
            dst = ctx.emit(Cvt(args[0], U64, PTR))
            src = ctx.emit(Cvt(args[1], U64, PTR))
            ctx.emit(Call("fs_rt_mem_copy", [dst, src, args[2]], VOID))
            return True
        if name == "str_to_addr":
            self.set_val(inst, ctx.emit(Cvt(args[0], ptr_to("i8"), U64)), ctx)
            return True
        if name == "addr_to_str":
            self.set_val(inst, ctx.emit(Cvt(args[0], U64, ptr_to("i8"))), ctx)
            return True
        if name == "runtime_state_get":
            self._ensure_state_cell()
            self.set_val(inst, ctx.emit(GlobalLoad("__fs_runtime_state", U64)), ctx)
            return True
        if name == "runtime_state_set":
            self._ensure_state_cell()
            ctx.emit(GlobalStore("__fs_runtime_state", args[0]))
            return True
        if name in self._WIN_EXTERNS:
            symbol, ret_type, param_types = self._WIN_EXTERNS[name]
            self.flir.externs.setdefault(symbol, ("kernel32.dll", ret_type, param_types))
            converted = []
            for arg, ptype in zip(args, param_types):
                from_type = arg.value_type if arg.value_type is not None else ptype
                converted.append(self._cvt_to(arg, from_type, ptype, ctx))
            result = ctx.emit(Call(symbol, converted, ret_type))
            if result is not None:
                self.set_val(inst, result, ctx)
            return True
        return False

    def _ensure_state_cell(self) -> None:
        if not any(n == "__fs_runtime_state" for n, _ in self.flir.mutable_globals):
            self.flir.mutable_globals.append(("__fs_runtime_state", U64))

    def rt_call(self, name: str, args: list[FValue], ret_type: FLIRType, ctx: _FuncCtx) -> Optional[FValue]:
        """Call a runtime entry point, preferring the firescript-implemented
        version (std/internal/runtime.fire) when present in the module."""
        if name in self.fir_funcs:
            lowered = self.request_function(name, [])
            return ctx.emit(Call(lowered, args, ret_type))
        return ctx.emit(Call(name, args, ret_type))

    def lower_call(self, inst: CallInst, ctx: _FuncCtx) -> None:
        name = inst.function_ref
        args = [self.val(op, ctx) for op in inst.operands]

        if self._lower_lowlevel_intrinsic(inst, name, args, ctx):
            return

        if name in self._INTRINSIC_MAP:
            rt_name, ret = self._INTRINSIC_MAP[name]
            if ret is None:
                ret_type = ptr_to("i8")
            elif ret == "SyscallResult":
                struct_name = self.ensure_struct("SyscallResult", [])
                ret_type = struct_type(struct_name)
            else:
                ret_type = ret
            result = self.rt_call(rt_name, args, ret_type, ctx)
            if result is not None:
                self.set_val(inst, result, ctx)
            return

        if name in ("toInt", "int", "toFloat", "toDouble", "toString", "toChar", "toBool"):
            self.lower_conversion_call(inst, name, args, ctx)
            return

        if name in ("i32_to_f64", "i32_to_f32", "f64_to_i32", "f32_to_i32"):
            mapping = {
                "i32_to_f64": (I32, F64),
                "i32_to_f32": (I32, F32),
                "f64_to_i32": (F64, I32),
                "f32_to_i32": (F32, I32),
            }
            from_t, to_t = mapping[name]
            self.set_val(inst, self._cvt_to(args[0], from_t, to_t, ctx), ctx)
            return

        if name in ("i32_to_str", "i64_to_str", "f32_to_str", "f64_to_str"):
            rt = {
                "i32_to_str": "fs_rt_i32_to_str",
                "i64_to_str": "fs_rt_i64_to_str",
                "f32_to_str": "fs_rt_f32_to_repr",
                "f64_to_str": "fs_rt_f64_to_repr",
            }[name]
            self.set_val(inst, ctx.emit(Call(rt, args, ptr_to("i8"))), ctx)
            return

        if name == "array_length":
            length = self._array_length_value(inst.operands[0], ctx)
            if length is None:
                raise LoweringError("array_length on array of unknown size")
            self.set_val(inst, length, ctx)
            return

        if name in ("array_index", "array_count"):
            self.lower_array_search(inst, name, args, ctx)
            return

        # User function (possibly generic).
        type_args = [self.subst(t, ctx.type_map) for t in inst.metadata.get("type_args", [])]
        lowered_name = self.request_function(name, type_args)
        callee = self.fir_funcs[name]
        final_args = self._call_args_with_lengths(callee, inst, args, bool(type_args), ctx)
        ret_type = VOID
        if inst.result_type is not None:
            ret_map = dict(zip(callee.generic_params, type_args))
            ret_type = self.lower_type(callee.return_type, ret_map) if callee.return_type else VOID
        result = ctx.emit(Call(lowered_name, final_args, ret_type))
        if result is not None:
            self.set_val(inst, result, ctx)

    def _call_args_with_lengths(
        self,
        callee: FIRFunction,
        inst: Instruction,
        args: list[FValue],
        is_generic_call: bool,
        ctx: _FuncCtx,
    ) -> list[FValue]:
        """Insert implicit array-length arguments (legacy ABI). Generic
        instantiations do not take length params (legacy parity)."""
        if is_generic_call or callee.is_generator:
            return args
        final: list[FValue] = []
        for (pname, ptype), arg_fir, arg in zip(callee.params, inst.operands, args):
            final.append(arg)
            if isinstance(ptype, ArrayType):
                length = self._array_length_value(arg_fir, ctx)
                if length is None:
                    length = ctx.emit(ConstInt("0", I32))
                final.append(length)
        # Trailing args beyond declared params (shouldn't happen) pass through.
        if len(args) > len(callee.params):
            final.extend(args[len(callee.params):])
        return final

    def lower_conversion_call(self, inst: CallInst, name: str, args: list[FValue], ctx: _FuncCtx) -> None:
        source_str = self.subst(self.fir_type_str_of(inst.operands[0], ctx), ctx.type_map)
        value = args[0]
        if name == "toString":
            self.set_val(inst, self._to_string(value, source_str, inst.operands[0], ctx), ctx)
            return
        source_type = self.lower_type_str(source_str, ctx.type_map)
        if name in ("toInt", "int"):
            if source_str == "string":
                self.set_val(inst, self.rt_call("fs_rt_str_to_i32", [value], I32, ctx), ctx)
            else:
                self.set_val(inst, self._cvt_to(value, source_type, I32, ctx), ctx)
            return
        if name == "toFloat":
            if source_str == "string":
                parsed = self.rt_call("fs_rt_str_to_f64", [value], F64, ctx)
                self.set_val(inst, self._cvt_to(parsed, F64, F32, ctx), ctx)
            else:
                self.set_val(inst, self._cvt_to(value, source_type, F32, ctx), ctx)
            return
        if name == "toDouble":
            if source_str == "string":
                self.set_val(inst, self.rt_call("fs_rt_str_to_f64", [value], F64, ctx), ctx)
            else:
                self.set_val(inst, self._cvt_to(value, source_type, F64, ctx), ctx)
            return
        if name == "toBool":
            if source_str == "string":
                self.set_val(inst, self.rt_call("fs_rt_str_to_bool", [value], BOOL, ctx), ctx)
            else:
                zero = self._zero_value(source_type, ctx)
                self.set_val(inst, ctx.emit(BinOp("ne", source_type, value, zero, BOOL)), ctx)
            return
        if name == "toChar":
            if source_str == "string":
                self.set_val(inst, self.rt_call("fs_rt_str_char_code", [value], I8, ctx), ctx)
            else:
                self.set_val(inst, self._cvt_to(value, source_type, I8, ctx), ctx)
            return
        raise LoweringError(f"unsupported conversion {name}")

    def lower_array_search(self, inst: CallInst, name: str, args: list[FValue], ctx: _FuncCtx) -> None:
        """Inline loops for array.index(v) / array.count(v)."""
        array_fir = inst.operands[0]
        array = args[0]
        needle = args[1]
        elem_str = inst.metadata.get("element_type", self._elem_type_of_array(array_fir, ctx))
        elem_str = self.subst(elem_str, ctx.type_map)
        elem_type = self.lower_type_str(elem_str, ctx.type_map)
        elem_size = elem_type.size(self.flir)
        length = self._array_length_value(array_fir, ctx)
        if length is None:
            raise LoweringError(f"{name} on array of unknown size")

        result_slot = ctx.temp("srch")
        idx_slot = ctx.temp("srchi")
        self.ensure_slot(result_slot, I32, ctx)
        self.ensure_slot(idx_slot, I32, ctx)
        init = "-1" if name == "array_index" else "0"
        ctx.emit(SlotStore(result_slot, ctx.emit(ConstInt(init, I32))))
        ctx.emit(SlotStore(idx_slot, ctx.emit(ConstInt("0", I32))))

        header = ctx.func.new_block()
        body = ctx.func.new_block()
        hit = ctx.func.new_block()
        cont = ctx.func.new_block()
        done = ctx.func.new_block()

        ctx.emit(Jmp(header.id))

        ctx.block = header
        idx = ctx.emit(SlotLoad(idx_slot, I32))
        cond = ctx.emit(BinOp("lt", I32, idx, length, BOOL))
        ctx.emit(Br(cond, body.id, done.id))

        ctx.block = body
        idx_b = ctx.emit(SlotLoad(idx_slot, I32))
        addr = ctx.emit(PtrAdd(array, idx_b, elem_size))
        elem = ctx.emit(Load(elem_type, addr, 0))
        if elem_str == "string":
            matches = self.rt_call("fs_rt_str_eq", [elem, needle], BOOL, ctx)
        else:
            matches = ctx.emit(BinOp("eq", elem_type, elem, needle, BOOL))
        ctx.emit(Br(matches, hit.id, cont.id))

        ctx.block = hit
        if name == "array_index":
            idx_h = ctx.emit(SlotLoad(idx_slot, I32))
            ctx.emit(SlotStore(result_slot, idx_h))
            ctx.emit(Jmp(done.id))
        else:
            cur = ctx.emit(SlotLoad(result_slot, I32))
            one = ctx.emit(ConstInt("1", I32))
            ctx.emit(SlotStore(result_slot, ctx.emit(BinOp("add", I32, cur, one, I32))))
            ctx.emit(Jmp(cont.id))

        ctx.block = cont
        idx_c = ctx.emit(SlotLoad(idx_slot, I32))
        one_c = ctx.emit(ConstInt("1", I32))
        ctx.emit(SlotStore(idx_slot, ctx.emit(BinOp("add", I32, idx_c, one_c, I32))))
        ctx.emit(Jmp(header.id))

        ctx.block = done
        self.set_val(inst, ctx.emit(SlotLoad(result_slot, I32)), ctx)

    def lower_method_call(self, inst: MethodCallInst, ctx: _FuncCtx) -> None:
        receiver_fir = inst.operands[0]
        receiver_type = self.subst(self.fir_type_str_of(receiver_fir, ctx), ctx.type_map)
        base = receiver_type.split("<")[0]
        type_args: list[str] = []
        if "<" in receiver_type and receiver_type.endswith(">"):
            type_args = [a.strip() for a in receiver_type.split("<", 1)[1][:-1].split(",")]

        fir_name = f"{base}.{inst.method}"
        if fir_name not in self.fir_funcs:
            raise LoweringError(f"unknown method {fir_name}")
        lowered_name = self.request_function(fir_name, type_args)

        callee = self.fir_funcs[fir_name]
        args = [self.val(op, ctx) for op in inst.operands]
        ret_type = VOID
        if inst.result_type is not None:
            ret_map = dict(zip(callee.generic_params, type_args))
            ret_type = self.lower_type(callee.return_type, ret_map) if callee.return_type else VOID
        result = ctx.emit(Call(lowered_name, args, ret_type))
        if result is not None:
            self.set_val(inst, result, ctx)

    # ------------------------------------------------------------------
    # Generators
    # ------------------------------------------------------------------

    def gen_frame_name(self, lowered_name: str) -> str:
        return f"__gen_{lowered_name}"

    def lower_generator(self, fir_func: FIRFunction, type_map: dict[str, str], lowered_name: str) -> None:
        """Build the frame struct, init function, and next function."""
        if lowered_name in self.generators_lowered:
            return
        self.generators_lowered.add(lowered_name)

        frame_name = self.gen_frame_name(lowered_name)
        frame = FLIRStruct(frame_name, kind="generator_frame")
        self.flir.add_struct(frame)
        frame.add_field("_state", I32, self.flir)
        param_types: list[tuple[str, FLIRType]] = []
        for pname, ptype in fir_func.params:
            lowered = self.lower_type(ptype, type_map)
            frame.add_field(pname, lowered, self.flir)
            param_types.append((pname, lowered))
        # Collect locals from DeclareLocal instructions.
        local_decls: list[tuple[str, FLIRType]] = []
        for block in fir_func.blocks:
            for inst in block.instructions:
                if isinstance(inst, DeclareLocalInst):
                    lowered = self.lower_type(inst.var_type, type_map)
                    frame.add_field(inst.name, lowered, self.flir)
                    local_decls.append((inst.name, lowered))
        frame.finalize()

        yield_type = fir_func.metadata.get("yield_type", "int32")
        out_type = self.lower_type_str(self.subst(yield_type, type_map), type_map)

        # -- init function: fills the frame ------------------------------
        init = FLIRFunction(
            f"{lowered_name}__init",
            [("frame", ptr_to(frame_name))] + param_types,
            VOID,
        )
        self.flir.add_function(init)
        ictx = _FuncCtx(init, type_map)
        ictx.block = init.new_block()
        ictx.slot_types["frame"] = ptr_to(frame_name)
        for pname, ptype in param_types:
            ictx.slot_types[pname] = ptype
        frame_ptr = ictx.emit(SlotLoad("frame", ptr_to(frame_name)))
        _, _, state_off = frame.field("_state")
        ictx.emit(Store(I32, frame_ptr, state_off, ictx.emit(ConstInt("0", I32))))
        for pname, ptype in param_types:
            _, ftype, offset = frame.field(pname)
            value = ictx.emit(SlotLoad(pname, ptype))
            fp = ictx.emit(SlotLoad("frame", ptr_to(frame_name)))
            ictx.emit(Store(ftype, fp, offset, value))
        for lname, ltype in local_decls:
            zero = self._zero_value(ltype, ictx)
            if zero is not None:
                _, ftype, offset = frame.field(lname)
                fp = ictx.emit(SlotLoad("frame", ptr_to(frame_name)))
                ictx.emit(Store(ftype, fp, offset, zero))
        ictx.emit(Ret())

        # -- next function: the state machine ------------------------------
        next_fn = FLIRFunction(
            f"{lowered_name}__next",
            [("frame", ptr_to(frame_name)), ("out", PTR)],
            BOOL,
        )
        self.flir.add_function(next_fn)
        nctx = _FuncCtx(next_fn, type_map)
        nctx.frame_struct = frame
        nctx.frame_param = "frame"
        nctx.out_param = "out"
        nctx.slot_types["frame"] = ptr_to(frame_name)
        nctx.slot_types["out"] = PTR
        nctx.func.metadata["out_type"] = out_type

        dispatch = next_fn.new_block()
        # Pre-create body blocks.
        for fir_block in fir_func.blocks:
            block = next_fn.new_block()
            nctx.block_map[fir_block.id] = block

        # Lower the body; yields create resume blocks recorded in nctx.
        for fir_block in fir_func.blocks:
            nctx.block = nctx.block_map[fir_block.id]
            for inst in fir_block.instructions:
                self.lower_inst(inst, nctx)
            if fir_block.terminator is not None:
                self.lower_terminator(fir_block.terminator, nctx)

        # Dispatch block: state == -1 -> false; state == k -> resume_k; else body.
        nctx.block = dispatch
        frame_ptr = nctx.emit(SlotLoad("frame", ptr_to(frame_name)))
        _, _, state_off = frame.field("_state")
        state = nctx.emit(Load(I32, frame_ptr, state_off))
        done_block = next_fn.new_block()

        current = dispatch
        nctx.block = current
        minus_one = nctx.emit(ConstInt("-1", I32))
        is_done = nctx.emit(BinOp("eq", I32, state, minus_one, BOOL))
        first_body = nctx.block_map[fir_func.blocks[0].id]
        if nctx.resume_blocks:
            chain_block = next_fn.new_block()
            nctx.emit(Br(is_done, done_block.id, chain_block.id))
            nctx.block = chain_block
            for state_id, resume in enumerate(nctx.resume_blocks, start=1):
                frame_ptr2 = nctx.emit(SlotLoad("frame", ptr_to(frame_name)))
                state2 = nctx.emit(Load(I32, frame_ptr2, state_off))
                k = nctx.emit(ConstInt(str(state_id), I32))
                is_k = nctx.emit(BinOp("eq", I32, state2, k, BOOL))
                if state_id < len(nctx.resume_blocks):
                    next_chain = next_fn.new_block()
                    nctx.emit(Br(is_k, resume.id, next_chain.id))
                    nctx.block = next_chain
                else:
                    nctx.emit(Br(is_k, resume.id, first_body.id))
        else:
            nctx.emit(Br(is_done, done_block.id, first_body.id))

        nctx.block = done_block
        nctx.emit(Ret(nctx.emit(ConstBool(False))))

        # The dispatch block must be first; FLIRFunction blocks are in creation
        # order with dispatch created first, so this holds.

    def lower_gen_new_local(self, decl: DeclareLocalInst, gen_new: GenNewInst, ctx: _FuncCtx) -> None:
        fir_name = gen_new.generator_ref
        gen_func = self.fir_funcs[fir_name]
        type_args: list[str] = []  # generators are concrete today
        lowered_name = self.request_function(fir_name, type_args)
        frame_name = self.gen_frame_name(lowered_name)

        slot = decl.name
        ctx.slot_types[slot] = struct_type(frame_name)
        ctx.emit(SlotDecl(slot, struct_type(frame_name)))
        ctx.gen_slots[slot] = lowered_name

        out_slot = f"{slot}__out"
        yield_type = gen_func.metadata.get("yield_type", "int32")
        out_type = self.lower_type_str(self.subst(yield_type, ctx.type_map), ctx.type_map)
        ctx.slot_types[out_slot] = out_type
        ctx.emit(SlotDecl(out_slot, out_type))

        args = [self.val(op, ctx) for op in gen_new.operands]
        frame_addr = ctx.emit(SlotAddr(slot, frame_name))
        ctx.emit(Call(f"{lowered_name}__init", [frame_addr] + args, VOID))
        self.set_val(gen_new, frame_addr, ctx)

    def _gen_slot_of(self, value: Value, ctx: _FuncCtx) -> str:
        if isinstance(value, FIRValue):
            inst = value.instruction
            if isinstance(inst, LoadVarInst) and inst.name in ctx.gen_slots:
                return inst.name
            if isinstance(inst, GenNewInst):
                # find the slot that maps to this generator
                for slot in ctx.gen_slots:
                    return slot
        raise LoweringError("generator operand is not a generator local")

    def lower_gen_next(self, inst: GenNextInst, ctx: _FuncCtx) -> None:
        slot = self._gen_slot_of(inst.operands[0], ctx)
        lowered_name = ctx.gen_slots[slot]
        frame_name = self.gen_frame_name(lowered_name)
        frame_addr = ctx.emit(SlotAddr(slot, frame_name))
        out_addr = ctx.emit(SlotAddr(f"{slot}__out"))
        self.set_val(inst, ctx.emit(Call(f"{lowered_name}__next", [frame_addr, out_addr], BOOL)), ctx)

    def lower_gen_value(self, inst: GenValueInst, ctx: _FuncCtx) -> None:
        slot = self._gen_slot_of(inst.operands[0], ctx)
        out_slot = f"{slot}__out"
        out_type = ctx.slot_types[out_slot]
        self.set_val(inst, ctx.emit(SlotLoad(out_slot, out_type)), ctx)

    def lower_yield(self, inst: YieldInst, ctx: _FuncCtx) -> None:
        if ctx.frame_struct is None:
            raise LoweringError("yield outside generator")
        value = self.val(inst.operands[0], ctx)
        out_type = ctx.func.metadata["out_type"]
        out_ptr = ctx.emit(SlotLoad("out", PTR))
        ctx.emit(Store(out_type, out_ptr, 0, value))
        ctx.yield_counter += 1
        frame_ptr = ctx.emit(SlotLoad("frame", PTR))
        _, _, state_off = ctx.frame_struct.field("_state")
        ctx.emit(Store(I32, frame_ptr, state_off, ctx.emit(ConstInt(str(ctx.yield_counter), I32))))
        ctx.emit(Ret(ctx.emit(ConstBool(True))))
        resume = ctx.func.new_block()
        ctx.resume_blocks.append(resume)
        ctx.block = resume

    def _gen_exhaust(self, ctx: _FuncCtx) -> None:
        frame_ptr = ctx.emit(SlotLoad("frame", PTR))
        _, _, state_off = ctx.frame_struct.field("_state")
        ctx.emit(Store(I32, frame_ptr, state_off, ctx.emit(ConstInt("-1", I32))))
        ctx.emit(Ret(ctx.emit(ConstBool(False))))
