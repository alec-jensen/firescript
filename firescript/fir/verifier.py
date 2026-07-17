"""Tier-1 (structural/type) verifier for FIR modules.

Implements FIRV-S, FIRV-D, FIRV-T, FIRV-L1-L2, FIRV-G1-G3 from
docs/internal/development/ir_verifier_spec.md section 4. Tier-2 rules
(ownership dataflow FIRV-O*, local-shadow FIRV-L3, generator dominance
FIRV-G4, enum-payload guard FIRV-E1) land in a later phase.

Verifier failures are internal-compiler-error diagnostics
(errors.IRVerificationError), not user-facing source diagnostics: valid
firescript source must never produce IR that fails this verifier (spec
section 1). Rules are normative; when the verifier fires on IR the
current pipeline emits, the fix belongs in ast_to_fir.py, not here.
"""

from __future__ import annotations

from typing import Optional

from errors import IRVerificationError
from fir.ir_module import FIRFunction, FIRModule, TypeDef
from fir.ir_node import (
    AllocateInst,
    ArrayLiteralInst,
    BasicBlock,
    BinaryOpInst,
    BorrowInst,
    BranchInst,
    CallInst,
    CastInst,
    CloneInst,
    ConstructVariantInst,
    DeclareLocalInst,
    DropInst,
    ExtractPayloadFieldInst,
    ExtractTagInst,
    FIRValue,
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
    Terminator,
    UnaryOpInst,
    Value,
    YieldInst,
)
from fir.ir_types import ArrayType, FIRType, FunctionType, GeneratorType, GenericInstanceType, SimpleType
from fir.textual import dump_module
from ir_analysis import CFG, Violation, build_cfg, compute_dominators, instruction_dominates

_NUMERIC_TYPES = frozenset(
    {
        "int8", "int16", "int32", "int64",
        "uint8", "uint16", "uint32", "uint64",
        "float32", "float64", "float128",
    }
)
_ARITH_OPS = frozenset({"+", "-", "*", "/", "%", "**"})
_COMPARISON_OPS = frozenset({"==", "!=", "<", "<=", ">", ">="})
_LOGICAL_OPS = frozenset({"&&", "||"})
_VALID_MODES = frozenset({"own", "borrow", "borrow_mut"})


def verify_fir_module(module: FIRModule) -> None:
    """Verify a FIR module against the Tier-1 rule catalog.

    Raises IRVerificationError, with every violation in the module
    (structure order, deterministic), if any rule is broken.
    """
    violations: list[Violation] = []
    type_index: dict[str, TypeDef] = {}
    for type_def in module.types:
        if type_def.name in type_index:
            violations.append(
                Violation("FIRV-S6", "FIR", type_def.name, f"duplicate type name '{type_def.name}'")
            )
        else:
            type_index[type_def.name] = type_def

    func_index: dict[str, FIRFunction] = {}
    for function in module.functions:
        if function.name in func_index:
            violations.append(
                Violation("FIRV-S6", "FIR", function.name, f"duplicate function name '{function.name}'")
            )
        else:
            func_index[function.name] = function

    const_names: set[str] = set()
    for constant in module.constants:
        if constant.name in const_names:
            violations.append(
                Violation("FIRV-S6", "FIR", constant.name, f"duplicate global constant name '{constant.name}'")
            )
        const_names.add(constant.name)

    _verify_type_defs(module, type_index, violations)

    const_types: dict[str, FIRType] = {c.name: c.const_type for c in module.constants}
    for function in module.functions:
        before = len(violations)
        fv = _FunctionVerifier(module, function, type_index, func_index, const_types, violations)
        fv.run()
        # Tier 2 (ownership dataflow, FIRV-L3/G4/E1) assumes a well-formed
        # CFG with valid dominance, which Tier 1 guarantees; skip it for a
        # function Tier 1 already flagged rather than cascading false
        # positives off broken structure.
        if len(violations) == before and function.blocks:
            from fir.ownership_verifier import (
                verify_enum_payload_guards,
                verify_generator_dominance,
                verify_no_shadowing,
                verify_ownership,
            )

            verify_no_shadowing(function, fv.idom, fv.cfg, violations)
            verify_ownership(module, function, fv.cfg, fv.idom, violations)
            verify_generator_dominance(function, fv.idom, fv.cfg, fv.def_positions, violations)
            verify_enum_payload_guards(module, function, fv.idom, fv.cfg, violations)

    if violations:
        dump = ""
        first_func_name = violations[0].function_name
        first_func = func_index.get(first_func_name)
        if first_func is not None:
            try:
                dump = "\n".join(_format_function_only(module, first_func))
            except Exception:
                dump = ""
        raise IRVerificationError("FIR", violations, dump)


def _format_function_only(module: FIRModule, function: FIRFunction) -> list[str]:
    # Reuse the textual dumper but isolate just the offending function.
    sub = FIRModule(module.name)
    sub.types = module.types
    sub.functions = [function]
    text = dump_module(sub)
    return text.splitlines()


def _verify_type_defs(module: FIRModule, type_index: dict[str, TypeDef], violations: list[Violation]) -> None:
    for type_def in module.types:
        if type_def.kind == "enum":
            if not type_def.variants:
                violations.append(
                    Violation("FIRV-S6", "FIR", type_def.name, f"enum '{type_def.name}' has no variants")
                )
            if type_def.base is not None:
                violations.append(
                    Violation("FIRV-S6", "FIR", type_def.name, f"enum '{type_def.name}' must not have a base")
                )
        # base chain resolves and is acyclic
        seen: set[str] = {type_def.name}
        current = type_def.base
        while current is not None:
            if current not in type_index:
                violations.append(
                    Violation(
                        "FIRV-S6", "FIR", type_def.name,
                        f"type '{type_def.name}' has unresolved base '{current}'",
                    )
                )
                break
            if current in seen:
                violations.append(
                    Violation(
                        "FIRV-S6", "FIR", type_def.name,
                        f"base chain of type '{type_def.name}' is cyclic at '{current}'",
                    )
                )
                break
            seen.add(current)
            current = type_index[current].base
        for _, field_type in type_def.fields:
            _check_type_reference(field_type, type_index, type_def.name, violations)
        for variant in type_def.variants:
            for _, field_type in variant.payload:
                _check_type_reference(field_type, type_index, type_def.name, violations)


def _check_type_reference(
    fir_type: FIRType, type_index: dict[str, TypeDef], owner: str, violations: list[Violation]
) -> None:
    if isinstance(fir_type, SimpleType):
        name = fir_type.name
        if name in _NUMERIC_TYPES or name in ("bool", "char", "string", "void", "null"):
            return
        if name not in type_index:
            # Unresolved bare names are either generic type parameters
            # (legitimately unresolved at this level) or a genuine error;
            # the converter does not currently mark which, so this is
            # deliberately lenient pending a generic-parameter carve-out.
            return
        type_def = type_index[name]
        if len(type_def.generic_params) != 0:
            violations.append(
                Violation(
                    "FIRV-S6", "FIR", owner,
                    f"type reference '{name}' omits its {len(type_def.generic_params)} type argument(s)",
                )
            )
    elif isinstance(fir_type, ArrayType):
        _check_type_reference(fir_type.element_type, type_index, owner, violations)
    elif isinstance(fir_type, GenericInstanceType):
        if fir_type.base_name in type_index:
            type_def = type_index[fir_type.base_name]
            if len(type_def.generic_params) != len(fir_type.type_args):
                violations.append(
                    Violation(
                        "FIRV-S6", "FIR", owner,
                        f"'{fir_type.base_name}' expects {len(type_def.generic_params)} type argument(s), "
                        f"got {len(fir_type.type_args)}",
                    )
                )
        for arg in fir_type.type_args:
            _check_type_reference(arg, type_index, owner, violations)
    elif isinstance(fir_type, GeneratorType):
        _check_type_reference(fir_type.element_type, type_index, owner, violations)


def _is_void(fir_type: Optional[FIRType]) -> bool:
    return fir_type is None or (isinstance(fir_type, SimpleType) and fir_type.name == "void")


def _type_assignable(actual: Optional[FIRType], expected: Optional[FIRType]) -> bool:
    """Looser-than-equality compatibility used for argument passing: a
    fixed-size array (`T[4]`) is assignable to an unsized array parameter
    (`T[]`), matching the language's array-parameter covariance. Field/
    local declarations still use strict equality (`==`); this is only for
    call/construct argument checks (FIRV-T5/T6/T9/T10)."""
    if actual is None or expected is None:
        return True
    if isinstance(actual, ArrayType) and isinstance(expected, ArrayType):
        if expected.size is not None and actual.size != expected.size:
            return False
        return _type_assignable(actual.element_type, expected.element_type)
    return actual == expected


class _FunctionVerifier:
    def __init__(
        self,
        module: FIRModule,
        function: FIRFunction,
        type_index: dict[str, TypeDef],
        func_index: dict[str, FIRFunction],
        const_types: dict[str, FIRType],
        violations: list[Violation],
    ):
        self.module = module
        self.function = function
        self.type_index = type_index
        self.func_index = func_index
        self.const_types = const_types
        self.violations = violations
        self.generic_names: set[str] = set(function.generic_params)
        self.param_types: dict[str, FIRType] = dict(function.params)
        self.param_modes: dict[str, str] = dict(zip((p[0] for p in function.params), function.param_modes))
        # id(instruction) -> (block_id, index-within-block; terminator gets
        # index == len(block.instructions))
        self.def_positions: dict[int, tuple[str, int]] = {}
        # local name -> [(block_id, index), ...] of its DeclareLocal(s)
        self.local_decls: dict[str, list[tuple[str, int]]] = {}
        self.local_types: dict[str, FIRType] = {}
        self.block_ids: set[str] = set()
        self.cfg: Optional[CFG] = None
        self.idom: dict[str, str] = {}

    def emit(self, rule_id: str, message: str, block: Optional[BasicBlock] = None, index: Optional[int] = None, inst: Optional[Instruction] = None) -> None:
        text = inst.format(self._safe_resolve) if inst is not None else ""
        self.violations.append(
            Violation(rule_id, "FIR", self.function.name, message, block.id if block else None, index, text)
        )

    def _safe_resolve(self, value: Value) -> str:
        if isinstance(value, ParamValue):
            return value.name
        if isinstance(value, FIRValue):
            pos = self.def_positions.get(id(value.instruction))
            if pos is None:
                return f"<{value.instruction.opcode}?>"
            return f"%{pos[0]}[{pos[1]}]"
        return "<?>"

    def run(self) -> None:
        function = self.function

        # -- S1: at least one block ------------------------------------
        if not function.blocks:
            self.emit("FIRV-S1", f"function '{function.name}' has no blocks")
            return

        # -- S2: unique block ids ---------------------------------------
        seen_ids: set[str] = set()
        for block in function.blocks:
            if block.id in seen_ids:
                self.emit("FIRV-S2", f"duplicate block id '{block.id}'", block)
            seen_ids.add(block.id)
        self.block_ids = seen_ids

        # -- S3: exactly one terminator, held separately -----------------
        for block in function.blocks:
            for idx, inst in enumerate(block.instructions):
                if isinstance(inst, Terminator):
                    self.emit("FIRV-S3", f"terminator instruction '{inst.opcode}' found in instruction stream", block, idx, inst)
            if block.terminator is None:
                self.emit("FIRV-S3", f"block '{block.id}' has no terminator", block, len(block.instructions))

        # -- S4: branch/jump targets resolve -----------------------------
        for block in function.blocks:
            term = block.terminator
            if term is None:
                continue
            for target in self._targets_of(term):
                if target not in self.block_ids:
                    self.emit("FIRV-S4", f"branch target '{target}' does not exist", block, len(block.instructions), term)

        # def positions (needed even if CFG/dominance can't be trusted yet)
        for block in function.blocks:
            for idx, inst in enumerate(block.instructions):
                self.def_positions[id(inst)] = (block.id, idx)
            if block.terminator is not None:
                self.def_positions[id(block.terminator)] = (block.id, len(block.instructions))

        entry = function.blocks[0].id
        # Deterministic order (declaration order), not self.block_ids
        # (a set -- hash-order iteration is not permitted; see CLAUDE.md's
        # determinism rule and ir_verifier_spec.md section 3.4). Duplicate
        # ids (flagged above as FIRV-S2) are deduplicated in file order.
        ordered_ids: list[str] = []
        seen_order: set[str] = set()
        for block in function.blocks:
            if block.id not in seen_order:
                ordered_ids.append(block.id)
                seen_order.add(block.id)
        self.cfg = build_cfg(ordered_ids, entry, self._successors_of_id)

        # -- S5: every block reachable from entry -------------------------
        for block in function.blocks:
            if block.id not in self.cfg.reachable:
                self.emit("FIRV-S5", f"block '{block.id}' is unreachable from entry")

        self.idom = compute_dominators(self.cfg)

        # local declarations (name -> positions), only for reachable code;
        # unreachable DeclareLocals still get indexed so D1 dominance
        # checks against them fail closed rather than crashing.
        for block in function.blocks:
            for idx, inst in enumerate(block.instructions):
                if isinstance(inst, DeclareLocalInst):
                    self.local_decls.setdefault(inst.name, []).append((block.id, idx))
                    self.local_types[inst.name] = inst.var_type

        # -- per-instruction checks ---------------------------------------
        for block in function.blocks:
            for idx, inst in enumerate(block.instructions):
                self._check_instruction(block, idx, inst)
            if block.terminator is not None:
                self._check_instruction(block, len(block.instructions), block.terminator)

    def _successors_of_id(self, block_id: str) -> list[str]:
        block = next((b for b in self.function.blocks if b.id == block_id), None)
        if block is None or block.terminator is None:
            return []
        return [t for t in self._targets_of(block.terminator) if t in self.block_ids]

    @staticmethod
    def _targets_of(term: Instruction) -> list[str]:
        if isinstance(term, BranchInst):
            return [term.true_block, term.false_block]
        if isinstance(term, JumpInst):
            return [term.target_block]
        return []

    # -- operand resolution (D1-D3) ------------------------------------

    def _use_operand(self, value: Value, block: BasicBlock, index: int, inst: Instruction) -> Optional[FIRType]:
        """Check D1-D3 for one operand use; returns its type, or None if
        the operand itself is invalid (callers should skip further
        type-checking against a None result)."""
        if isinstance(value, ParamValue):
            if value.name not in self.param_types:
                self.emit("FIRV-D2", f"ParamValue '{value.name}' does not name a parameter of '{self.function.name}'", block, index, inst)
                return None
            return self.param_types[value.name]
        if isinstance(value, FIRValue):
            def_pos = self.def_positions.get(id(value.instruction))
            if def_pos is None:
                self.emit("FIRV-D1", f"operand produced by '{value.instruction.opcode}' does not belong to function '{self.function.name}'", block, index, inst)
                return None
            def_block, def_index = def_pos
            if def_block not in self.cfg.reachable:
                self.emit("FIRV-D1", f"operand produced by unreachable instruction in block '{def_block}'", block, index, inst)
                return value.instruction.result_type
            if not instruction_dominates(self.idom, def_block, def_index, block.id, index):
                self.emit("FIRV-D1", f"definition in block '{def_block}' does not dominate this use", block, index, inst)
            if _is_void(value.instruction.result_type):
                self.emit("FIRV-D3", f"operand '{value.instruction.opcode}' does not produce a value", block, index, inst)
                return None
            return value.instruction.result_type
        self.emit("FIRV-D1", f"unsupported operand kind '{type(value).__name__}'", block, index, inst)
        return None

    # -- per-instruction dispatch ---------------------------------------

    def _check_instruction(self, block: BasicBlock, index: int, inst: Instruction) -> None:
        operand_types: list[Optional[FIRType]] = [self._use_operand(op, block, index, inst) for op in inst.operands]

        if isinstance(inst, BinaryOpInst):
            self._check_binary_op(inst, operand_types, block, index)
        elif isinstance(inst, UnaryOpInst):
            self._check_unary_op(inst, operand_types, block, index)
        elif isinstance(inst, CastInst):
            pass  # T3: cast legality is enforced by semantic analysis; FIR trusts it.
        elif isinstance(inst, BranchInst):
            cond_t = operand_types[0] if operand_types else None
            if cond_t is not None and not _is_bool(cond_t):
                self.emit("FIRV-T4", f"Branch condition has type '{cond_t.render()}', expected bool", block, index, inst)
        elif isinstance(inst, ReturnInst):
            self._check_return(inst, operand_types, block, index)
        elif isinstance(inst, CallInst):
            self._check_call(inst, operand_types, block, index)
        elif isinstance(inst, MethodCallInst):
            self._check_method_call(inst, operand_types, block, index)
        elif isinstance(inst, LoadFieldInst):
            self._check_load_field(inst, operand_types, block, index)
        elif isinstance(inst, StoreFieldInst):
            self._check_store_field(inst, operand_types, block, index)
        elif isinstance(inst, IndexArrayInst):
            self._check_index_array(inst, operand_types, block, index)
        elif isinstance(inst, StoreArrayInst):
            self._check_store_array(inst, operand_types, block, index)
        elif isinstance(inst, AllocateInst):
            self._check_allocate(inst, operand_types, block, index)
        elif isinstance(inst, ConstructVariantInst):
            self._check_construct_variant(inst, operand_types, block, index)
        elif isinstance(inst, ExtractTagInst):
            self._check_extract_tag(inst, operand_types, block, index)
        elif isinstance(inst, ExtractPayloadFieldInst):
            self._check_extract_payload_field(inst, operand_types, block, index)
        elif isinstance(inst, (LoadVarInst, StoreVarInst)):
            self._check_var_access(inst, operand_types, block, index)
        elif isinstance(inst, IntLiteralInst):
            self._check_int_literal(inst, block, index)
        elif isinstance(inst, NullLiteralInst):
            if not _is_nullable(inst.result_type):
                self.emit("FIRV-T12", f"NullLiteral has non-nullable type '{inst.result_type.render()}'", block, index, inst)
        elif isinstance(inst, YieldInst):
            self._check_yield(inst, operand_types, block, index)
        elif isinstance(inst, (GenNewInst, GenNextInst, GenValueInst)):
            self._check_generator_inst(inst, operand_types, block, index)
        elif isinstance(inst, (MoveInst, CloneInst, BorrowInst)):
            pass  # ownership legality is a Tier-2 (FIRV-O) concern.
        elif isinstance(inst, DropInst):
            pass  # FIRV-O5 is Tier-2.

    def _check_binary_op(self, inst: BinaryOpInst, operand_types, block, index) -> None:
        lhs_t, rhs_t = operand_types
        if lhs_t is None or rhs_t is None:
            return
        if _is_generic_param(lhs_t, self.generic_names) or _is_generic_param(rhs_t, self.generic_names):
            return
        op = inst.op
        if op in _LOGICAL_OPS:
            if not (_is_bool(lhs_t) and _is_bool(rhs_t)):
                self.emit("FIRV-T1", f"logical operator '{op}' requires bool operands, got '{lhs_t.render()}' and '{rhs_t.render()}'", block, index, inst)
            elif not _is_bool(inst.result_type):
                self.emit("FIRV-T1", f"logical operator '{op}' must produce bool", block, index, inst)
            return
        if op in _COMPARISON_OPS:
            # nullable vs non-nullable of the same base type is allowed
            # (e.g. comparing a `string` against a `string?`, or a null
            # literal); only the base type must agree.
            if _strip_nullable(lhs_t) != _strip_nullable(rhs_t):
                self.emit("FIRV-T1", f"comparison '{op}' operands have differing types '{lhs_t.render()}' vs '{rhs_t.render()}'", block, index, inst)
            if not _is_bool(inst.result_type):
                self.emit("FIRV-T1", f"comparison '{op}' must produce bool", block, index, inst)
            return
        if op in _ARITH_OPS:
            is_string_concat = op == "+" and _is_string(lhs_t) and _is_string(rhs_t)
            if is_string_concat:
                if not _is_string(inst.result_type):
                    self.emit("FIRV-T1", f"string '+' must produce string", block, index, inst)
                return
            if lhs_t != rhs_t:
                self.emit("FIRV-T1", f"arithmetic '{op}' operands have differing types '{lhs_t.render()}' vs '{rhs_t.render()}'", block, index, inst)
                return
            if not _is_numeric(lhs_t):
                self.emit("FIRV-T1", f"arithmetic '{op}' requires numeric operands, got '{lhs_t.render()}'", block, index, inst)
                return
            if inst.result_type != lhs_t:
                self.emit("FIRV-T1", f"arithmetic '{op}' result type '{inst.result_type.render()}' does not match operand type '{lhs_t.render()}'", block, index, inst)
            return

    def _check_unary_op(self, inst: UnaryOpInst, operand_types, block, index) -> None:
        (operand_t,) = operand_types
        if operand_t is None:
            return
        if _is_generic_param(operand_t, self.generic_names):
            return
        if inst.op == "!":
            if not _is_bool(operand_t):
                self.emit("FIRV-T2", f"unary '!' requires bool, got '{operand_t.render()}'", block, index, inst)
            elif not _is_bool(inst.result_type):
                self.emit("FIRV-T2", "unary '!' must produce bool", block, index, inst)
        elif inst.op in ("-", "+"):
            if not _is_numeric(operand_t):
                self.emit("FIRV-T2", f"unary '{inst.op}' requires a numeric operand, got '{operand_t.render()}'", block, index, inst)
            elif inst.result_type != operand_t:
                self.emit("FIRV-T2", f"unary '{inst.op}' result type does not match operand type", block, index, inst)

    def _check_return(self, inst: ReturnInst, operand_types, block, index) -> None:
        func = self.function
        if func.is_generator:
            if inst.operands:
                self.emit("FIRV-G2", "generator function's Return must carry no value (return means exhaustion)", block, index, inst)
            return
        if not inst.operands:
            if not _is_void(func.return_type):
                self.emit("FIRV-T4", f"value-less Return in non-void function (declared '{func.return_type.render()}')", block, index, inst)
            return
        value_t = operand_types[0]
        if value_t is None:
            return
        if _is_void(func.return_type):
            self.emit("FIRV-T4", "Return carries a value in a void function", block, index, inst)
        elif value_t != func.return_type:
            self.emit("FIRV-T4", f"Return value type '{value_t.render()}' does not match declared return type '{func.return_type.render()}'", block, index, inst)

    def _check_call(self, inst: CallInst, operand_types, block, index) -> None:
        if len(inst.arg_modes) != len(inst.operands):
            self.emit("FIRV-T5", f"Call has {len(inst.operands)} argument(s) but {len(inst.arg_modes)} arg_mode(s)", block, index, inst)
        for mode in inst.arg_modes:
            if mode not in _VALID_MODES:
                self.emit("FIRV-T5", f"Call arg_mode '{mode}' is not one of {sorted(_VALID_MODES)}", block, index, inst)
        callee = self.func_index.get(inst.function_ref)
        if callee is None:
            return  # intrinsic or otherwise-resolved call; not checked further at Tier 1.
        if callee.generic_params:
            return  # generic callee: argument types depend on inference not modeled here yet.
        if len(inst.operands) != len(callee.params):
            self.emit("FIRV-T5", f"Call to '{inst.function_ref}' passes {len(inst.operands)} argument(s), expected {len(callee.params)}", block, index, inst)
            return
        for i, ((pname, ptype), arg_t) in enumerate(zip(callee.params, operand_types)):
            if not _type_assignable(arg_t, ptype):
                self.emit("FIRV-T5", f"Call argument {i} ('{pname}') has type '{arg_t.render()}', expected '{ptype.render()}'", block, index, inst)
        callee_ret = callee.return_type
        if _is_void(callee_ret) != _is_void(inst.result_type):
            self.emit("FIRV-T5", f"Call result shape does not match callee '{inst.function_ref}' return type", block, index, inst)
        elif not _is_void(callee_ret) and inst.result_type != callee_ret:
            self.emit("FIRV-T5", f"Call result type '{inst.result_type.render()}' does not match callee return type '{callee_ret.render()}'", block, index, inst)

    def _check_method_call(self, inst: MethodCallInst, operand_types, block, index) -> None:
        n_args = len(inst.operands) - 1
        if len(inst.arg_modes) != n_args:
            self.emit("FIRV-T6", f"MethodCall has {n_args} argument(s) but {len(inst.arg_modes)} arg_mode(s)", block, index, inst)
        for mode in inst.arg_modes:
            if mode not in _VALID_MODES:
                self.emit("FIRV-T6", f"MethodCall arg_mode '{mode}' is not one of {sorted(_VALID_MODES)}", block, index, inst)
        receiver_t = operand_types[0] if operand_types else None
        if receiver_t is None:
            return
        class_name = _class_name_of(receiver_t)
        if class_name is None or class_name not in self.type_index:
            return  # unresolved / builtin receiver type; not checked further at Tier 1.
        callee = self._resolve_method(class_name, inst.method)
        if callee is None:
            return  # intrinsic method (e.g. array.index/count) or otherwise-resolved; not checked further.
        if callee.generic_params or self.type_index[class_name].generic_params:
            return  # generic receiver/method: argument types depend on inference not modeled here yet.
        # Instance methods keep an explicit leading `this` parameter (only
        # constructors strip it -- see ast_to_fir.py::_convert_method); the
        # receiver is passed separately as inst.operands[0], not counted
        # among `args`, so skip it on the callee side too.
        callee_params = callee.params[1:] if callee.params and callee.params[0][0] == "this" else callee.params
        args = operand_types[1:]
        if len(args) != len(callee_params):
            self.emit("FIRV-T6", f"MethodCall to '{class_name}.{inst.method}' passes {len(args)} argument(s), expected {len(callee_params)}", block, index, inst)
            return
        for i, ((pname, ptype), arg_t) in enumerate(zip(callee_params, args)):
            if not _type_assignable(arg_t, ptype):
                self.emit("FIRV-T6", f"MethodCall argument {i} ('{pname}') has type '{arg_t.render()}', expected '{ptype.render()}'", block, index, inst)
        callee_ret = callee.return_type
        if _is_void(callee_ret) != _is_void(inst.result_type):
            self.emit("FIRV-T6", f"MethodCall result shape does not match callee '{class_name}.{inst.method}' return type", block, index, inst)
        elif not _is_void(callee_ret) and inst.result_type != callee_ret:
            self.emit("FIRV-T6", f"MethodCall result type '{inst.result_type.render()}' does not match callee return type '{callee_ret.render()}'", block, index, inst)

    def _resolve_method(self, class_name: str, method: str) -> Optional[FIRFunction]:
        current = self.type_index.get(class_name)
        while current is not None:
            candidate = self.func_index.get(f"{current.name}.{method}")
            if candidate is not None:
                return candidate
            current = self.type_index.get(current.base) if current.base else None
        return None

    def _check_load_field(self, inst: LoadFieldInst, operand_types, block, index) -> None:
        (obj_t,) = operand_types
        if obj_t is None:
            return
        class_name = _class_name_of(obj_t)
        if class_name is None:
            self.emit("FIRV-T7", f"LoadField object operand has non-class type '{obj_t.render()}'", block, index, inst)
            return
        type_def = self.type_index.get(class_name)
        if type_def is None:
            return
        if type_def.kind == "enum":
            self.emit("FIRV-T7", f"LoadField on enum type '{class_name}' is invalid", block, index, inst)
            return
        field_type = self._resolve_field_type(type_def, inst.field)
        if field_type is None:
            self.emit("FIRV-T7", f"class '{class_name}' has no field '{inst.field}'", block, index, inst)
        elif _is_generic_param(field_type, set(type_def.generic_params)):
            pass  # field's declared type is the class's own unresolved generic parameter
        elif inst.result_type != field_type:
            self.emit("FIRV-T7", f"LoadField result type '{inst.result_type.render()}' does not match field type '{field_type.render()}'", block, index, inst)

    def _check_store_field(self, inst: StoreFieldInst, operand_types, block, index) -> None:
        obj_t, value_t = operand_types
        if obj_t is None:
            return
        class_name = _class_name_of(obj_t)
        if class_name is None:
            self.emit("FIRV-T7", f"StoreField object operand has non-class type '{obj_t.render()}'", block, index, inst)
            return
        type_def = self.type_index.get(class_name)
        if type_def is None:
            return
        if type_def.kind == "enum":
            self.emit("FIRV-T7", f"StoreField on enum type '{class_name}' is invalid", block, index, inst)
            return
        field_type = self._resolve_field_type(type_def, inst.field)
        if field_type is None:
            self.emit("FIRV-T7", f"class '{class_name}' has no field '{inst.field}'", block, index, inst)
        elif _is_generic_param(field_type, set(type_def.generic_params)):
            pass  # field's declared type is the class's own unresolved generic parameter
        elif value_t is not None and value_t != field_type:
            self.emit("FIRV-T7", f"StoreField value type '{value_t.render()}' does not match field type '{field_type.render()}'", block, index, inst)

    def _resolve_field_type(self, type_def: TypeDef, field: str) -> Optional[FIRType]:
        current: Optional[TypeDef] = type_def
        seen: set[str] = set()
        while current is not None and current.name not in seen:
            seen.add(current.name)
            for fname, ftype in current.fields:
                if fname == field:
                    return ftype
            current = self.type_index.get(current.base) if current.base else None
        return None

    def _check_index_array(self, inst: IndexArrayInst, operand_types, block, index) -> None:
        array_t, index_t = operand_types
        if array_t is not None:
            if not isinstance(array_t, ArrayType):
                self.emit("FIRV-T8", f"IndexArray operand has non-array type '{array_t.render()}'", block, index, inst)
            elif inst.result_type != array_t.element_type:
                self.emit("FIRV-T8", f"IndexArray result type '{inst.result_type.render()}' does not match element type '{array_t.element_type.render()}'", block, index, inst)
        if index_t is not None and not _is_integer(index_t):
            self.emit("FIRV-T8", f"IndexArray index has non-integer type '{index_t.render()}'", block, index, inst)

    def _check_store_array(self, inst: StoreArrayInst, operand_types, block, index) -> None:
        array_t, index_t, value_t = operand_types
        if array_t is not None:
            if not isinstance(array_t, ArrayType):
                self.emit("FIRV-T8", f"StoreArray operand has non-array type '{array_t.render()}'", block, index, inst)
            elif value_t is not None and value_t != array_t.element_type:
                self.emit("FIRV-T8", f"StoreArray value type '{value_t.render()}' does not match element type '{array_t.element_type.render()}'", block, index, inst)
        if index_t is not None and not _is_integer(index_t):
            self.emit("FIRV-T8", f"StoreArray index has non-integer type '{index_t.render()}'", block, index, inst)

    def _check_allocate(self, inst: AllocateInst, operand_types, block, index) -> None:
        class_name = _class_name_of(inst.result_type)
        if class_name is None or class_name not in self.type_index:
            return
        type_def = self.type_index[class_name]
        ctor = self.func_index.get(f"{class_name}.{class_name}")
        if ctor is not None:
            # A class with an explicit constructor is constructed via a
            # Call to Class.Class (see ast_to_fir.py::_convert_construction);
            # Allocate only appears bare, as the constructor's own `this =
            # Allocate(Class, [])` bootstrap, with fields set afterward via
            # StoreField.
            if inst.operands:
                self.emit("FIRV-T9", f"Allocate passes {len(inst.operands)} argument(s) to '{class_name}', which has an explicit constructor (expected the bare bootstrap allocation)", block, index, inst)
            return
        # No explicit constructor: the language allows default,
        # positional-field construction (e.g. `SyscallResult(-22, "")`
        # for `copyable class SyscallResult { int32 status; string
        # data; }` in std/internal/syscalls.fire).
        params = self._all_fields(type_def)
        if len(inst.operands) != len(params):
            self.emit("FIRV-T9", f"Allocate passes {len(inst.operands)} argument(s) to '{class_name}', expected {len(params)}", block, index, inst)
            return
        for i, ((pname, ptype), arg_t) in enumerate(zip(params, operand_types)):
            if not _type_assignable(arg_t, ptype):
                self.emit("FIRV-T9", f"Allocate argument {i} ('{pname}') has type '{arg_t.render()}', expected '{ptype.render()}'", block, index, inst)

    def _all_fields(self, type_def: TypeDef) -> list[tuple[str, FIRType]]:
        """Fields including base-chain fields (base first), deduplicated --
        mirrors flir/lowering.py's class_fields_full."""
        chain: list[TypeDef] = []
        seen: set[str] = set()
        current: Optional[TypeDef] = type_def
        while current is not None and current.name not in seen:
            seen.add(current.name)
            chain.append(current)
            current = self.type_index.get(current.base) if current.base else None
        fields: list[tuple[str, FIRType]] = []
        names: set[str] = set()
        for td in reversed(chain):
            for fname, ftype in td.fields:
                if fname not in names:
                    fields.append((fname, ftype))
                    names.add(fname)
        return fields

    def _check_construct_variant(self, inst: ConstructVariantInst, operand_types, block, index) -> None:
        class_name = _class_name_of(inst.result_type)
        if class_name is None or class_name not in self.type_index:
            return
        type_def = self.type_index[class_name]
        variant = next((v for v in type_def.variants if v.name == inst.variant_name), None)
        if variant is None:
            self.emit("FIRV-T10", f"enum '{class_name}' has no variant '{inst.variant_name}'", block, index, inst)
            return
        if len(inst.operands) != len(variant.payload):
            self.emit("FIRV-T10", f"variant '{inst.variant_name}' expects {len(variant.payload)} payload field(s), got {len(inst.operands)}", block, index, inst)
            return
        for i, ((fname, ftype), arg_t) in enumerate(zip(variant.payload, operand_types)):
            if not _type_assignable(arg_t, ftype):
                self.emit("FIRV-T10", f"variant '{inst.variant_name}' payload field {i} ('{fname}') has type '{arg_t.render()}', expected '{ftype.render()}'", block, index, inst)

    def _check_extract_tag(self, inst: ExtractTagInst, operand_types, block, index) -> None:
        (enum_t,) = operand_types
        if enum_t is None:
            return
        class_name = _class_name_of(enum_t)
        type_def = self.type_index.get(class_name) if class_name else None
        if type_def is None or type_def.kind != "enum":
            self.emit("FIRV-T11", f"ExtractTag operand has non-enum type '{enum_t.render()}'", block, index, inst)

    def _check_extract_payload_field(self, inst: ExtractPayloadFieldInst, operand_types, block, index) -> None:
        (enum_t,) = operand_types
        if enum_t is None:
            return
        class_name = _class_name_of(enum_t)
        type_def = self.type_index.get(class_name) if class_name else None
        if type_def is None or type_def.kind != "enum":
            self.emit("FIRV-T11", f"ExtractPayloadField operand has non-enum type '{enum_t.render()}'", block, index, inst)
            return
        variant = next((v for v in type_def.variants if v.name == inst.variant_name), None)
        if variant is None:
            self.emit("FIRV-T11", f"enum '{class_name}' has no variant '{inst.variant_name}'", block, index, inst)
            return
        if not (0 <= inst.field_index < len(variant.payload)):
            self.emit("FIRV-T11", f"field_index {inst.field_index} out of range for variant '{inst.variant_name}' ({len(variant.payload)} field(s))", block, index, inst)
            return
        field_type = variant.payload[inst.field_index][1]
        if inst.result_type != field_type:
            self.emit("FIRV-T11", f"ExtractPayloadField result type '{inst.result_type.render()}' does not match payload field type '{field_type.render()}'", block, index, inst)

    def _check_var_access(self, inst: Instruction, operand_types, block, index) -> None:
        name = inst.name
        declared_type: Optional[FIRType] = None
        if name in self.param_types:
            declared_type = self.param_types[name]
        elif name in self.const_types:
            # Global constant: referenced via a bare LoadVar with its own
            # name (see ast_to_fir.py::_convert_const / the IDENTIFIER
            # fallback when _lookup finds no local scope entry); lowering
            # redirects these to a FLIR global load rather than a slot.
            declared_type = self.const_types[name]
        else:
            decls = self.local_decls.get(name, [])
            dominating = [
                (b, i) for (b, i) in decls
                if b in self.cfg.reachable and instruction_dominates(self.idom, b, i, block.id, index)
            ]
            if not dominating:
                self.emit("FIRV-L1", f"'{name}' has no dominating parameter, DeclareLocal, or global constant", block, index, inst)
                return
            declared_type = self.local_types.get(name)
        if declared_type is None:
            return
        if isinstance(inst, LoadVarInst):
            if inst.result_type != declared_type:
                self.emit("FIRV-L2", f"LoadVar('{name}') result type '{inst.result_type.render()}' does not match declared type '{declared_type.render()}'", block, index, inst)
        elif isinstance(inst, StoreVarInst):
            value_t = operand_types[0]
            if value_t is not None and not _nullable_assignable(value_t, declared_type):
                self.emit("FIRV-L2", f"StoreVar('{name}') value type '{value_t.render()}' does not match declared type '{declared_type.render()}'", block, index, inst)

    def _check_int_literal(self, inst: IntLiteralInst, block, index) -> None:
        text = inst.text
        try:
            value = int(text, 0) if text.lower().startswith(("0x", "0o", "0b")) else int(text)
        except ValueError:
            self.emit("FIRV-T12", f"IntLiteral text '{text}' does not parse as an integer", block, index, inst)
            return
        bounds = _INT_BOUNDS.get(_type_name(inst.result_type))
        if bounds is not None:
            lo, hi = bounds
            # A signed type's most-negative literal (e.g. `-128i8`) parses
            # as a UnaryOp("-", IntLiteral("128", int8)) -- the literal
            # itself carries the positive magnitude, one past `hi`, and is
            # only in range once negated by its (separate) enclosing
            # UnaryOp. FIR has no operator-aware literal, so this is the
            # one deliberate, narrow allowance here.
            if not (lo <= value <= hi) and not (lo < 0 and value == hi + 1):
                self.emit("FIRV-T12", f"IntLiteral value {value} does not fit in '{inst.result_type.render()}'", block, index, inst)
        elif _type_name(inst.result_type) not in _NUMERIC_TYPES:
            self.emit("FIRV-T12", f"IntLiteral has non-numeric type '{inst.result_type.render()}'", block, index, inst)

    def _check_yield(self, inst: YieldInst, operand_types, block, index) -> None:
        if not self.function.is_generator:
            self.emit("FIRV-G1", "Yield used outside a generator function", block, index, inst)
            return
        value_t = operand_types[0]
        if value_t is None:
            return
        elem_type = self.function.return_type
        if isinstance(elem_type, GeneratorType):
            elem_type = elem_type.element_type
        if elem_type is not None and value_t != elem_type:
            self.emit("FIRV-G1", f"Yield value type '{value_t.render()}' does not match generator element type '{elem_type.render()}'", block, index, inst)

    def _check_generator_inst(self, inst: Instruction, operand_types, block, index) -> None:
        if isinstance(inst, GenNewInst):
            callee = self.func_index.get(inst.generator_ref)
            if callee is None:
                return
            if not callee.is_generator:
                self.emit("FIRV-G3", f"GenNew references non-generator function '{inst.generator_ref}'", block, index, inst)
                return
            if not callee.generic_params and len(inst.operands) != len(callee.params):
                self.emit("FIRV-G3", f"GenNew passes {len(inst.operands)} argument(s), expected {len(callee.params)}", block, index, inst)
            if not isinstance(inst.result_type, GeneratorType):
                self.emit("FIRV-G3", f"GenNew result type '{inst.result_type.render()}' is not a generator type", block, index, inst)
                return
            callee_elem = callee.return_type.element_type if isinstance(callee.return_type, GeneratorType) else None
            if callee_elem is not None and inst.result_type.element_type != callee_elem:
                self.emit("FIRV-G3", f"GenNew result element type '{inst.result_type.element_type.render()}' does not match generator element type '{callee_elem.render()}'", block, index, inst)
        elif isinstance(inst, GenNextInst):
            (gen_t,) = operand_types
            if gen_t is not None and not isinstance(gen_t, GeneratorType):
                self.emit("FIRV-G3", f"GenNext operand has non-generator type '{gen_t.render()}'", block, index, inst)
            if not _is_bool(inst.result_type):
                self.emit("FIRV-G3", "GenNext must produce bool", block, index, inst)
        elif isinstance(inst, GenValueInst):
            (gen_t,) = operand_types
            if gen_t is None:
                return
            if not isinstance(gen_t, GeneratorType):
                self.emit("FIRV-G3", f"GenValue operand has non-generator type '{gen_t.render()}'", block, index, inst)
                return
            if inst.result_type != gen_t.element_type:
                self.emit("FIRV-G3", f"GenValue result type '{inst.result_type.render()}' does not match generator element type '{gen_t.element_type.render()}'", block, index, inst)


_INT_BOUNDS = {
    "int8": (-128, 127),
    "int16": (-32768, 32767),
    "int32": (-2147483648, 2147483647),
    "int64": (-9223372036854775808, 9223372036854775807),
    "uint8": (0, 255),
    "uint16": (0, 65535),
    "uint32": (0, 4294967295),
    "uint64": (0, 18446744073709551615),
}


def _type_name(fir_type: Optional[FIRType]) -> Optional[str]:
    return fir_type.name if isinstance(fir_type, SimpleType) else None


def _is_numeric(fir_type: Optional[FIRType]) -> bool:
    return _type_name(fir_type) in _NUMERIC_TYPES


def _is_integer(fir_type: Optional[FIRType]) -> bool:
    name = _type_name(fir_type)
    return name is not None and name in _NUMERIC_TYPES and name not in ("float32", "float64", "float128")


def _is_bool(fir_type: Optional[FIRType]) -> bool:
    return _type_name(fir_type) == "bool"


def _is_string(fir_type: Optional[FIRType]) -> bool:
    return _type_name(fir_type) == "string"


def _is_nullable(fir_type: Optional[FIRType]) -> bool:
    return isinstance(fir_type, SimpleType) and fir_type.nullable


def _strip_nullable(fir_type: Optional[FIRType]) -> Optional[FIRType]:
    if isinstance(fir_type, SimpleType) and fir_type.nullable:
        return SimpleType(fir_type.name, category=fir_type.category, nullable=False, metadata=fir_type.metadata)
    return fir_type


def _nullable_assignable(value_t: Optional[FIRType], declared_t: Optional[FIRType]) -> bool:
    """A non-nullable value may be stored into a nullable-typed slot of
    the same base type (e.g. `string? c; c = "world";`); the reverse
    (storing a possibly-null value into a non-nullable slot) is not
    allowed."""
    if value_t == declared_t:
        return True
    if not (isinstance(declared_t, SimpleType) and declared_t.nullable):
        return False
    return _strip_nullable(value_t) == _strip_nullable(declared_t)


def _is_generic_param(fir_type: Optional[FIRType], names: set[str]) -> bool:
    """True if `fir_type` is a bare, unresolved generic type parameter
    name (e.g. 'T' in `class Pair<T, U>` or `function add<T>`). FIR keeps
    generics unspecialized -- only FLIR monomorphizes -- so Tier-1 cannot
    check operations against a parameter's eventual concrete type; the
    verifier treats these as unknown rather than false-flagging every
    generic function/class body."""
    return isinstance(fir_type, SimpleType) and fir_type.name in names


def _class_name_of(fir_type: Optional[FIRType]) -> Optional[str]:
    if isinstance(fir_type, SimpleType):
        return fir_type.name
    if isinstance(fir_type, GenericInstanceType):
        return fir_type.base_name
    return None
