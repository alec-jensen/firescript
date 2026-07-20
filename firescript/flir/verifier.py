"""Tier-1 (structural/type/memory) verifier for FLIR modules.

Implements FLIRV-S, FLIRV-T, FLIRV-M1-M3 from
docs/internal/development/ir_verifier_spec.md section 5. Tier-2 rules
(heap-token allocation lifecycle FLIRV-A1-A5, null discipline FLIRV-M4-M5)
land in a later phase.

Verifier failures are internal-compiler-error diagnostics
(errors.IRVerificationError): valid FIR must never lower to FLIR that
fails this verifier. Rules are normative; when the verifier fires on IR
the current pipeline emits, the fix belongs in flir/lowering.py, not here.
"""

from __future__ import annotations

from typing import Optional

from errors import IRVerificationError
from flir.ir import (
    BOOL,
    BinOp,
    Br,
    Call,
    Cvt,
    FLIRBlock,
    FLIRFunction,
    FLIRModule,
    FLIRStruct,
    FLIRType,
    FValue,
    FInst,
    GlobalLoad,
    GlobalStore,
    Jmp,
    Load,
    Neg,
    Not,
    PTR,
    PtrAdd,
    Ret,
    SlotAddr,
    SlotDecl,
    SlotLoad,
    SlotStore,
    Store,
    TERMINATOR_OPS,
    Unreachable,
    VOID,
)
from flir.runtime_abi import runtime_signature
from ir_analysis import CFG, Violation, build_cfg, compute_dominators, instruction_dominates

_ARITH_OPS = frozenset({"add", "sub", "mul", "div", "mod", "pow"})
_CMP_OPS = frozenset({"eq", "ne", "lt", "le", "gt", "ge"})


def verify_flir_module(module: FLIRModule) -> None:
    """Verify a FLIR module against the Tier-1 rule catalog.

    Raises IRVerificationError, with every violation in the module
    (structure order, deterministic), if any rule is broken.
    """
    violations: list[Violation] = []

    func_index: dict[str, FLIRFunction] = {}
    for function in module.functions:
        if function.name in func_index:
            violations.append(Violation("FLIRV-S2", "FLIR", function.name, f"duplicate function name '{function.name}'"))
        else:
            func_index[function.name] = function

    struct_index: dict[str, FLIRStruct] = {}
    for struct in module.structs:
        if struct.name in struct_index:
            violations.append(Violation("FLIRV-S2", "FLIR", struct.name, f"duplicate struct name '{struct.name}'"))
        else:
            struct_index[struct.name] = struct

    if module.entry_function is not None and module.entry_function not in func_index:
        violations.append(Violation("FLIRV-S2", "FLIR", module.name, f"entry_function '{module.entry_function}' is not a defined function"))

    global_names: set[str] = set()
    global_types: dict[str, FLIRType] = {}
    for name, gtype, _text in module.globals:
        if name in global_names:
            violations.append(Violation("FLIRV-S2", "FLIR", module.name, f"duplicate global name '{name}'"))
        global_names.add(name)
        global_types[name] = gtype
    mutable_names: set[str] = set()
    for name, gtype in module.mutable_globals:
        if name in mutable_names or name in global_names:
            violations.append(Violation("FLIRV-S2", "FLIR", module.name, f"global name '{name}' is not unique across globals/mutable_globals"))
        mutable_names.add(name)
        global_types[name] = gtype

    _verify_structs(module, struct_index, violations)

    for function in module.functions:
        before = len(violations)
        fv = _FunctionVerifier(module, function, func_index, struct_index, global_names, mutable_names, global_types, violations)
        fv.run()
        # Tier 2 (heap-token allocation lifecycle, FLIRV-A/M4-M5) assumes a
        # well-formed CFG with valid dominance, which Tier 1 guarantees;
        # skip it for a function Tier 1 already flagged rather than
        # cascading false positives off broken structure.
        if len(violations) == before and function.blocks:
            from flir.heap_verifier import verify_heap_lifecycle

            verify_heap_lifecycle(module, function, func_index, struct_index, fv.cfg, fv.def_positions, violations)

    if violations:
        dump = _format_first_offender(module, func_index, violations)
        raise IRVerificationError("FLIR", violations, dump)


def _format_first_offender(module: FLIRModule, func_index: dict[str, FLIRFunction], violations: list[Violation]) -> str:
    from flir.textual import dump_flir_module

    first_func = func_index.get(violations[0].function_name)
    if first_func is None:
        return ""
    try:
        sub = FLIRModule(module.name)
        sub.structs = module.structs
        sub.functions = [first_func]
        return dump_flir_module(sub)
    except Exception:
        return ""


def _resolve_struct_type(fir_type: Optional[FLIRType]) -> Optional[str]:
    if fir_type is None:
        return None
    if fir_type.kind == "ptr":
        return fir_type.pointee
    return None


def _verify_structs(module: FLIRModule, struct_index: dict[str, FLIRStruct], violations: list[Violation]) -> None:
    for struct in module.structs:
        if struct.size % max(struct.align, 1) != 0:
            violations.append(Violation("FLIRV-S3", "FLIR", struct.name, f"struct size {struct.size} is not a multiple of its align {struct.align}"))
        # Non-enum fields must not overlap; sort by offset and walk.
        ordered = sorted(struct.fields, key=lambda f: f[2])
        for fname, ftype, offset in struct.fields:
            if ftype.kind == "struct" and ftype.struct_name not in struct_index and ftype.struct_name != struct.name:
                violations.append(Violation("FLIRV-S2", "FLIR", struct.name, f"field '{fname}' references unresolved struct '{ftype.struct_name}'"))
                continue
            falign = ftype.align(module)
            fsize = ftype.size(module)
            if falign and offset % falign != 0:
                violations.append(Violation("FLIRV-S3", "FLIR", struct.name, f"field '{fname}' at offset {offset} is misaligned for align {falign}"))
            if offset + fsize > struct.size:
                violations.append(Violation("FLIRV-S3", "FLIR", struct.name, f"field '{fname}' [{offset}, {offset + fsize}) exceeds struct size {struct.size}"))
        if struct.kind != "enum":
            for i in range(1, len(ordered)):
                pname, ptype, poffset = ordered[i - 1]
                pend = poffset + ptype.size(module)
                cname, ctype, coffset = ordered[i]
                if coffset < pend:
                    violations.append(Violation("FLIRV-S3", "FLIR", struct.name, f"fields '{pname}' and '{cname}' overlap"))
        else:
            tag_entry = next((f for f in struct.fields if f[0] == "tag"), None)
            if tag_entry is not None:
                _, tag_type, tag_offset = tag_entry
                tag_end = tag_offset + tag_type.size(module)
                for variant_name, layout in struct.variant_layouts.items():
                    for fname, ftype, offset in layout:
                        if offset < tag_end:
                            violations.append(Violation("FLIRV-S3", "FLIR", struct.name, f"variant '{variant_name}' field '{fname}' overlaps the tag"))
            for variant_name, layout in struct.variant_layouts.items():
                ordered_variant = sorted(layout, key=lambda f: f[2])
                for i in range(1, len(ordered_variant)):
                    pname, ptype, poffset = ordered_variant[i - 1]
                    pend = poffset + ptype.size(module)
                    cname, ctype, coffset = ordered_variant[i]
                    if coffset < pend:
                        violations.append(Violation("FLIRV-S3", "FLIR", struct.name, f"variant '{variant_name}' fields '{pname}' and '{cname}' overlap"))


class _FunctionVerifier:
    def __init__(
        self,
        module: FLIRModule,
        function: FLIRFunction,
        func_index: dict[str, FLIRFunction],
        struct_index: dict[str, FLIRStruct],
        global_names: set[str],
        mutable_names: set[str],
        global_types: dict[str, FLIRType],
        violations: list[Violation],
    ):
        self.module = module
        self.function = function
        self.func_index = func_index
        self.struct_index = struct_index
        self.global_names = global_names
        self.mutable_names = mutable_names
        self.global_types = global_types
        self.violations = violations
        self.param_types: dict[str, FLIRType] = dict(function.params)
        self.def_positions: dict[int, tuple[str, int]] = {}
        self.slot_decls: dict[str, list[tuple[str, int]]] = {}
        self.slot_types: dict[str, FLIRType] = {}
        self.block_ids: list[str] = []
        self.cfg: Optional[CFG] = None
        self.idom: dict[str, str] = {}

    def emit(self, rule_id: str, message: str, block: Optional[FLIRBlock] = None, index: Optional[int] = None, inst: Optional[FInst] = None) -> None:
        text = inst.format(self._safe_resolve) if inst is not None else ""
        self.violations.append(Violation(rule_id, "FLIR", self.function.name, message, block.id if block else None, index, text))

    def _safe_resolve(self, value: FValue) -> str:
        pos = self.def_positions.get(id(value.instruction))
        if pos is None:
            return f"<{value.instruction.opcode}?>"
        return f"%{pos[0]}[{pos[1]}]"

    def run(self) -> None:
        function = self.function
        if not function.blocks:
            self.emit("FLIRV-S1", f"function '{function.name}' has no blocks")
            return

        seen_ids: set[str] = set()
        for block in function.blocks:
            if block.id in seen_ids:
                self.emit("FLIRV-S1", f"duplicate block id '{block.id}'", block)
            seen_ids.add(block.id)
            if not block.instructions:
                self.emit("FLIRV-S1", f"block '{block.id}' is empty (no terminator)", block)
                continue
            for idx, inst in enumerate(block.instructions[:-1]):
                if inst.opcode in TERMINATOR_OPS:
                    self.emit("FLIRV-S1", f"terminator opcode '{inst.opcode}' found mid-block", block, idx, inst)
            last = block.instructions[-1]
            if last.opcode not in TERMINATOR_OPS:
                self.emit("FLIRV-S1", f"block '{block.id}' does not end with a terminator", block, len(block.instructions) - 1, last)

        ordered_ids: list[str] = []
        seen_order: set[str] = set()
        for block in function.blocks:
            if block.id not in seen_order:
                ordered_ids.append(block.id)
                seen_order.add(block.id)
        self.block_ids = ordered_ids

        for block in function.blocks:
            if not block.instructions:
                continue
            for target in self._targets_of(block.instructions[-1]):
                if target not in seen_order:
                    self.emit("FLIRV-S1", f"branch target '{target}' does not exist", block, len(block.instructions) - 1, block.instructions[-1])

        for block in function.blocks:
            for idx, inst in enumerate(block.instructions):
                self.def_positions[id(inst)] = (block.id, idx)

        entry = function.blocks[0].id
        self.cfg = build_cfg(ordered_ids, entry, self._successors_of_id)

        for block in function.blocks:
            if block.id not in self.cfg.reachable:
                self.emit("FLIRV-S1", f"block '{block.id}' is unreachable from entry")

        self.idom = compute_dominators(self.cfg)

        for block in function.blocks:
            for idx, inst in enumerate(block.instructions):
                if isinstance(inst, SlotDecl):
                    self.slot_decls.setdefault(inst.name, []).append((block.id, idx))
                    self.slot_types[inst.name] = inst.slot_type

        for name, positions in self.slot_decls.items():
            if len(positions) > 1:
                b, i = positions[1]
                self.emit("FLIRV-T5", f"slot '{name}' is declared more than once", next(bl for bl in function.blocks if bl.id == b), i)

        for block in function.blocks:
            for idx, inst in enumerate(block.instructions):
                self._check_instruction(block, idx, inst)

    def _successors_of_id(self, block_id: str) -> list[str]:
        block = next((b for b in self.function.blocks if b.id == block_id), None)
        if block is None or not block.instructions:
            return []
        return [t for t in self._targets_of(block.instructions[-1]) if t in self.block_ids]

    @staticmethod
    def _targets_of(inst: FInst) -> list[str]:
        if isinstance(inst, Br):
            return [inst.true_block, inst.false_block]
        if isinstance(inst, Jmp):
            return [inst.target]
        return []

    # -- operand resolution (FLIRV-T1) -----------------------------------

    def _use_operand(self, value: FValue, block: FLIRBlock, index: int, inst: FInst) -> Optional[FLIRType]:
        def_pos = self.def_positions.get(id(value.instruction))
        if def_pos is None:
            self.emit("FLIRV-T1", f"operand produced by '{value.instruction.opcode}' does not belong to function '{self.function.name}'", block, index, inst)
            return None
        def_block, def_index = def_pos
        if def_block not in self.cfg.reachable:
            self.emit("FLIRV-T1", f"operand produced by unreachable instruction in block '{def_block}'", block, index, inst)
            return value.instruction.result_type
        if not instruction_dominates(self.idom, def_block, def_index, block.id, index):
            self.emit("FLIRV-T1", f"definition in block '{def_block}' does not dominate this use", block, index, inst)
        rtype = value.instruction.result_type
        if rtype is None or rtype.kind == "void":
            self.emit("FLIRV-T1", f"operand '{value.instruction.opcode}' does not produce a value", block, index, inst)
            return None
        return rtype

    # -- per-instruction dispatch -----------------------------------------

    def _check_instruction(self, block: FLIRBlock, index: int, inst: FInst) -> None:
        operand_types: list[Optional[FLIRType]] = [self._use_operand(op, block, index, inst) for op in inst.operands]

        if isinstance(inst, BinOp):
            self._check_binop(inst, operand_types, block, index)
        elif isinstance(inst, Not):
            self._check_not(inst, operand_types, block, index)
        elif isinstance(inst, Neg):
            self._check_neg(inst, operand_types, block, index)
        elif isinstance(inst, Cvt):
            self._check_cvt(inst, operand_types, block, index)
        elif isinstance(inst, Br):
            cond_t = operand_types[0] if operand_types else None
            if cond_t is not None and cond_t != BOOL:
                self.emit("FLIRV-T3", f"br condition has type '{cond_t.render()}', expected bool", block, index, inst)
        elif isinstance(inst, Ret):
            self._check_ret(inst, operand_types, block, index)
        elif isinstance(inst, Call):
            self._check_call(inst, operand_types, block, index)
        elif isinstance(inst, SlotLoad):
            self._check_slot_load(inst, block, index)
        elif isinstance(inst, SlotStore):
            self._check_slot_store(inst, operand_types, block, index)
        elif isinstance(inst, SlotAddr):
            self._check_slot_addr(inst, block, index)
        elif isinstance(inst, GlobalLoad):
            self._check_global_load(inst, block, index)
        elif isinstance(inst, GlobalStore):
            self._check_global_store(inst, operand_types, block, index)
        elif isinstance(inst, Load):
            self._check_load(inst, operand_types, block, index)
        elif isinstance(inst, Store):
            self._check_store(inst, operand_types, block, index)
        elif isinstance(inst, PtrAdd):
            self._check_ptradd(inst, operand_types, block, index)

    def _check_binop(self, inst, operand_types, block, index) -> None:
        lhs_t, rhs_t = operand_types
        # eq/ne against a nullable value (e.g. `T? == null` where T is a
        # value type like int32) compares the boxed-pointer representation
        # of the nullable, not `operand_type` (which reflects T itself) --
        # a bare `ptr` actual operand is always acceptable for equality
        # comparisons, matching this null-check pattern (see
        # std/types/option.fire's `this.value == null` and its FIRV-T2
        # narrowing rationale in ir_verifier_spec.md section 8).
        is_null_check = inst.op in ("eq", "ne") and (
            (lhs_t is not None and lhs_t.kind == "ptr") or (rhs_t is not None and rhs_t.kind == "ptr")
        )
        if is_null_check:
            return
        if lhs_t is not None and not _binop_operand_ok(lhs_t, inst.operand_type):
            self.emit("FLIRV-T2", f"binop '{inst.op}' lhs type '{lhs_t.render()}' does not match operand_type '{inst.operand_type.render()}'", block, index, inst)
        if rhs_t is not None and not _binop_operand_ok(rhs_t, inst.operand_type):
            self.emit("FLIRV-T2", f"binop '{inst.op}' rhs type '{rhs_t.render()}' does not match operand_type '{inst.operand_type.render()}'", block, index, inst)
        if inst.op in _ARITH_OPS or inst.op in ("and", "or"):
            if inst.result_type != inst.operand_type:
                self.emit("FLIRV-T2", f"binop '{inst.op}' result type '{inst.result_type.render()}' does not match operand_type '{inst.operand_type.render()}'", block, index, inst)
        elif inst.op in _CMP_OPS:
            if inst.result_type != BOOL:
                self.emit("FLIRV-T2", f"comparison '{inst.op}' must produce bool", block, index, inst)
        else:
            self.emit("FLIRV-T2", f"unknown binop '{inst.op}'", block, index, inst)

    def _check_not(self, inst, operand_types, block, index) -> None:
        (t,) = operand_types
        if t is not None and t != BOOL:
            self.emit("FLIRV-T2", f"'not' requires bool, got '{t.render()}'", block, index, inst)

    def _check_neg(self, inst, operand_types, block, index) -> None:
        (t,) = operand_types
        if t is not None and t != inst.result_type:
            self.emit("FLIRV-T2", f"'neg' operand type '{t.render()}' does not match result type '{inst.result_type.render()}'", block, index, inst)

    def _check_cvt(self, inst, operand_types, block, index) -> None:
        (t,) = operand_types
        if t is not None and t != inst.from_type:
            self.emit("FLIRV-T2", f"cvt from_type '{inst.from_type.render()}' does not match operand's actual type '{t.render()}'", block, index, inst)
        # "ptr" is included: lowering uses Cvt for u64<->ptr reinterpretation
        # (e.g. mem_* intrinsics, str_to_addr/addr_to_str) even though the
        # class's own docstring says "scalar types".
        scalar_kinds = {"i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64", "f32", "f64", "bool", "ptr"}
        if inst.from_type.kind not in scalar_kinds:
            self.emit("FLIRV-T2", f"cvt from_type '{inst.from_type.render()}' is not scalar", block, index, inst)
        if inst.result_type.kind not in scalar_kinds:
            self.emit("FLIRV-T2", f"cvt to_type '{inst.result_type.render()}' is not scalar", block, index, inst)

    def _check_ret(self, inst, operand_types, block, index) -> None:
        func = self.function
        if not inst.operands:
            if func.return_type.kind != "void":
                self.emit("FLIRV-T3", f"bare ret in non-void function (declared '{func.return_type.render()}')", block, index, inst)
            return
        value_t = operand_types[0]
        if value_t is None:
            return
        if func.return_type.kind == "void":
            self.emit("FLIRV-T3", "ret carries a value in a void function", block, index, inst)
        elif not _ptr_lenient_eq(value_t, func.return_type):
            self.emit("FLIRV-T3", f"ret value type '{value_t.render()}' does not match declared return type '{func.return_type.render()}'", block, index, inst)

    def _check_call(self, inst, operand_types, block, index) -> None:
        callee = self.func_index.get(inst.callee)
        if callee is not None:
            self._check_call_against(inst, operand_types, block, index, [t for _, t in callee.params], callee.return_type, "function")
            return
        extern = self.module.externs.get(inst.callee)
        if extern is not None:
            _dll, ret_type, param_types = extern
            self._check_call_against(inst, operand_types, block, index, param_types, ret_type, "extern")
            return
        sig = runtime_signature(inst.callee)
        if sig is not None:
            self._check_call_against(inst, operand_types, block, index, list(sig.params), sig.ret, "runtime ABI entry")
            return
        self.emit("FLIRV-T4", f"call to unresolved callee '{inst.callee}' (not a module function, extern, or runtime ABI entry)", block, index, inst)

    def _check_call_against(self, inst, operand_types, block, index, param_types, ret_type, kind) -> None:
        if len(inst.operands) != len(param_types):
            self.emit("FLIRV-T4", f"call to {kind} '{inst.callee}' passes {len(inst.operands)} argument(s), expected {len(param_types)}", block, index, inst)
        else:
            for i, (ptype, arg_t) in enumerate(zip(param_types, operand_types)):
                if arg_t is not None and not _ptr_lenient_eq(arg_t, ptype):
                    self.emit("FLIRV-T4", f"call to {kind} '{inst.callee}' argument {i} has type '{arg_t.render()}', expected '{ptype.render()}'", block, index, inst)
        if not _ptr_lenient_eq(inst.result_type, ret_type):
            self.emit("FLIRV-T4", f"call to {kind} '{inst.callee}' result type '{inst.result_type.render()}' does not match its return type '{ret_type.render()}'", block, index, inst)

    def _check_slot_load(self, inst, block, index) -> None:
        self._check_slot_name(inst.name, block, index, inst, "FLIRV-T5", "slotload")
        declared = self._slot_or_param_type(inst.name)
        if declared is not None and not _ptr_lenient_eq(inst.result_type, declared):
            self.emit("FLIRV-T5", f"slotload('{inst.name}') result type '{inst.result_type.render()}' does not match declared type '{declared.render()}'", block, index, inst)

    def _check_slot_store(self, inst, operand_types, block, index) -> None:
        self._check_slot_name(inst.name, block, index, inst, "FLIRV-T5", "slotstore")
        declared = self._slot_or_param_type(inst.name)
        value_t = operand_types[0]
        if declared is not None and value_t is not None and not _ptr_lenient_eq(value_t, declared):
            self.emit("FLIRV-T5", f"slotstore('{inst.name}') value type '{value_t.render()}' does not match declared type '{declared.render()}'", block, index, inst)

    def _check_slot_addr(self, inst, block, index) -> None:
        self._check_slot_name(inst.name, block, index, inst, "FLIRV-T5", "slotaddr")

    def _check_slot_name(self, name, block, index, inst, rule_id, opname) -> None:
        if name in self.param_types:
            return
        decls = self.slot_decls.get(name, [])
        dominating = [
            (b, i) for (b, i) in decls
            if b in self.cfg.reachable and instruction_dominates(self.idom, b, i, block.id, index)
        ]
        if not dominating:
            self.emit(rule_id, f"{opname}('{name}') has no dominating parameter or slot declaration", block, index, inst)

    def _slot_or_param_type(self, name: str) -> Optional[FLIRType]:
        if name in self.param_types:
            return self.param_types[name]
        return self.slot_types.get(name)

    def _check_global_load(self, inst, block, index) -> None:
        if inst.name not in self.global_names and inst.name not in self.mutable_names:
            self.emit("FLIRV-T6", f"gload references undeclared global '@{inst.name}'", block, index, inst)
            return
        declared = self.global_types.get(inst.name)
        if declared is not None and inst.result_type != declared:
            self.emit("FLIRV-T6", f"gload('@{inst.name}') result type '{inst.result_type.render()}' does not match declared type '{declared.render()}'", block, index, inst)

    def _check_global_store(self, inst, operand_types, block, index) -> None:
        if inst.name not in self.mutable_names:
            if inst.name in self.global_names:
                self.emit("FLIRV-T6", f"gstore targets read-only global '@{inst.name}' (not in mutable_globals)", block, index, inst)
            else:
                self.emit("FLIRV-T6", f"gstore references undeclared global '@{inst.name}'", block, index, inst)
            return
        declared = self.global_types.get(inst.name)
        value_t = operand_types[0]
        if declared is not None and value_t is not None and value_t != declared:
            self.emit("FLIRV-T6", f"gstore('@{inst.name}') value type '{value_t.render()}' does not match declared type '{declared.render()}'", block, index, inst)

    def _check_load(self, inst, operand_types, block, index) -> None:
        (base_t,) = operand_types
        if base_t is None:
            return
        if base_t.kind != "ptr":
            self.emit("FLIRV-M1", f"load base has non-pointer type '{base_t.render()}'", block, index, inst)
            return
        self._check_typed_access(base_t, inst.offset, inst.result_type, block, index, inst, "load")

    def _check_store(self, inst, operand_types, block, index) -> None:
        base_t, value_t = operand_types
        if base_t is None:
            return
        if base_t.kind != "ptr":
            self.emit("FLIRV-M1", f"store base has non-pointer type '{base_t.render()}'", block, index, inst)
            return
        self._check_typed_access(base_t, inst.offset, inst.value_type, block, index, inst, "store")
        if value_t is not None and not _ptr_lenient_eq(value_t, inst.value_type):
            self.emit("FLIRV-T1", f"store value type '{value_t.render()}' does not match declared value_type '{inst.value_type.render()}'", block, index, inst)

    def _check_typed_access(self, base_t: FLIRType, offset: int, access_type: FLIRType, block, index, inst, opname) -> None:
        struct_name = base_t.pointee
        struct = self.struct_index.get(struct_name) if struct_name else None
        if struct is None:
            return  # unknown/raw pointee: M1's "known struct" scope doesn't apply.
        align = access_type.align(self.module)
        if align and offset % align != 0:
            self.emit("FLIRV-M2", f"{opname} offset {offset} is misaligned for type '{access_type.render()}' (align {align})", block, index, inst)
        candidates = list(struct.fields)
        if struct.kind == "enum":
            for layout in struct.variant_layouts.values():
                candidates.extend(layout)
        matches = [f for f in candidates if f[2] == offset]
        if not matches:
            self.emit("FLIRV-M1", f"{opname} at offset {offset} into '%{struct_name}' does not land on a declared field", block, index, inst)
            return
        if not any(f[1] == access_type for f in matches):
            found_types = ", ".join(sorted({f[1].render() for f in matches}))
            self.emit("FLIRV-M1", f"{opname} type '{access_type.render()}' at offset {offset} into '%{struct_name}' does not match field type(s) {found_types}", block, index, inst)

    def _check_ptradd(self, inst, operand_types, block, index) -> None:
        base_t = operand_types[0] if operand_types else None
        if base_t is not None and base_t.kind != "ptr":
            self.emit("FLIRV-M3", f"ptradd base has non-pointer type '{base_t.render()}'", block, index, inst)
        if inst.scale <= 0:
            self.emit("FLIRV-M3", f"ptradd scale {inst.scale} is not positive", block, index, inst)


_INT_KIND_SIZE = {"i8": 1, "i16": 2, "i32": 4, "i64": 8, "u8": 1, "u16": 2, "u32": 4, "u64": 8}


def _binop_operand_ok(actual: FLIRType, declared: FLIRType) -> bool:
    """FLIRV-T2, narrowed (see ir_verifier_spec.md section 8): an integer
    operand narrower than the binop's declared `operand_type` may feed it
    directly, with no explicit Cvt in between, regardless of relative
    signedness (u8 -> i32 is lossless and common, matching C's usual
    arithmetic conversions). Sub-i32 arithmetic promotes implicitly --
    existing, tested lowering behavior (int8/int16 loop counters, byte
    arithmetic, array element comparisons) -- not something to paper over
    by inserting new Cvt instructions at every narrow-int binop site."""
    if _ptr_lenient_eq(actual, declared):
        return True
    a_size = _INT_KIND_SIZE.get(actual.kind)
    d_size = _INT_KIND_SIZE.get(declared.kind)
    if a_size is not None and d_size is not None:
        return a_size <= d_size
    return False


def _ptr_lenient_eq(a: Optional[FLIRType], b: Optional[FLIRType]) -> bool:
    """Pointer pointee is informational, not a machine-level distinction:
    any two pointer-kind types are considered equal for signature/return
    matching purposes (extern/runtime-ABI calls, generic allocators, raw
    pointer plumbing all rely on this). Non-pointer types still compare
    exactly."""
    if a is None or b is None:
        return True
    if a.kind == "ptr" and b.kind == "ptr":
        return True
    return a == b
