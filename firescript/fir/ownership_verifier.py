"""Tier-2 ownership-linearity verifier for FIR functions.

Implements FIRV-O1-O7, FIRV-L3, FIRV-G4, FIRV-E1 from
docs/internal/development/ir_verifier_spec.md sections 4.4-4.7. FIRV-O8
(cross-checking the recorded OwnershipMap) is staged separately (spec
section 8.5) and not implemented here.

This module recomputes ownership facts by forward dataflow; it never
reads fir.ownership.OwnershipMap (spec section 1, principle 3). It only
runs against a function that already passed Tier-1 checks (S/D/T/L1-L2/
G1-G3) -- Tier-2 dataflow assumes a well-formed CFG with valid dominance,
which Tier-1 guarantees.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Union

from fir.ir_module import FIRFunction, FIRModule
from fir.ir_node import (
    AllocateInst,
    BasicBlock,
    CallInst,
    CloneInst,
    ConstructVariantInst,
    DeclareLocalInst,
    DropInst,
    ExtractPayloadFieldInst,
    ExtractTagInst,
    FIRValue,
    GenNextInst,
    GenValueInst,
    IndexArrayInst,
    Instruction,
    IntLiteralInst,
    LoadFieldInst,
    LoadVarInst,
    MethodCallInst,
    MoveInst,
    ParamValue,
    ReturnInst,
    StoreArrayInst,
    StoreFieldInst,
    StoreVarInst,
    Value,
)
from ir_analysis import CFG, Violation, compute_dominators, dominates, forward_dataflow

Identifier = Union[str, tuple]  # binding name, or ("temp", id(instruction))


class OwnState(Enum):
    OWNED = "owned"
    MOVED = "moved"
    MAYBE_MOVED = "maybe_moved"


def _meet_one(a: OwnState, b: OwnState) -> OwnState:
    if a == b:
        return a
    return OwnState.MAYBE_MOVED


def _meet_states(states: list[dict[Identifier, OwnState]]) -> dict[Identifier, OwnState]:
    if not states:
        return {}
    result: dict[Identifier, OwnState] = dict(states[0])
    for other in states[1:]:
        for key, value in other.items():
            if key in result:
                result[key] = _meet_one(result[key], value)
            else:
                result[key] = value
        # Keys present only in `result` but not `other` are left as-is:
        # dominance (L1) guarantees a binding used later is declared on
        # every path that reaches that use, so a key missing from one
        # predecessor here is one that isn't live past this join anyway.
    return result


class _StateDict(dict):
    """A dict usable as a dataflow State: hashable-by-value via frozenset
    for equality/fixpoint comparison, immutable from the driver's point of
    view (transfer always returns a fresh copy)."""

    def __eq__(self, other):
        return isinstance(other, dict) and dict.__eq__(self, other)

    def __hash__(self):  # pragma: no cover - not actually hashed
        return hash(frozenset(self.items()))


class _OwnershipChecker:
    def __init__(self, module: FIRModule, function: FIRFunction, cfg: CFG, idom: dict[str, str], violations: list[Violation]):
        self.module = module
        self.function = function
        self.cfg = cfg
        self.idom = idom
        self.violations = violations
        # Gates emit(): see run()'s comment -- False while the dataflow
        # fixpoint is still converging (transfer() runs speculatively,
        # possibly several times per block, on intermediate states), True
        # for the single, final reporting pass over converged states.
        self._reporting = False

        # FIR keeps generics unspecialized (only FLIR monomorphizes), so a
        # binding whose declared type is a bare, unresolved generic type
        # parameter (e.g. 'T' in `function add<T>` or `class Pair<T, U>`)
        # can't be known to be owned or copyable here -- matches the same
        # exemption Tier 1 applies (fir/verifier.py::_is_generic_param).
        self.generic_names: set[str] = set(function.generic_params)

        self.own_params: set[str] = set()
        self.borrow_params: set[str] = set()
        for (pname, ptype), mode in zip(function.params, function.param_modes):
            if self._is_generic(ptype):
                continue
            if mode == "own" and ptype.is_owned():
                self.own_params.add(pname)
            elif mode in ("borrow", "borrow_mut"):
                self.borrow_params.add(pname)

        self.owned_local_names: set[str] = set()
        for block in function.blocks:
            for inst in block.instructions:
                if (
                    isinstance(inst, DeclareLocalInst)
                    and inst.var_type.is_owned()
                    and not self._is_generic(inst.var_type)
                    and not self._is_aliased_read(inst.operands[0] if inst.operands else None)
                ):
                    self.owned_local_names.add(inst.name)

        self.def_positions: dict[int, tuple[str, int]] = {}
        for block in function.blocks:
            for idx, inst in enumerate(block.instructions):
                self.def_positions[id(inst)] = (block.id, idx)
            if block.terminator is not None:
                self.def_positions[id(block.terminator)] = (block.id, len(block.instructions))

    def _is_generic(self, fir_type) -> bool:
        from fir.ir_types import SimpleType

        return isinstance(fir_type, SimpleType) and fir_type.name in self.generic_names

    def _is_aliased_read(self, value: Optional["Value"]) -> bool:
        """True if `value` is a LoadField/IndexArray/ExtractPayloadField
        result -- an in-place read of a slot the containing object/array/
        enum still owns (see _identifier_of's matching comment), not a
        fresh allocation. A `T x = <that>;` binding is therefore still an
        alias, not a new independently-ownable value: tracking it as one
        would demand a Drop that double-frees once the container is later
        dropped.
        """
        return isinstance(value, FIRValue) and isinstance(
            value.instruction, (LoadFieldInst, IndexArrayInst, ExtractPayloadFieldInst)
        )

    def emit(self, rule_id: str, message: str, block: Optional[BasicBlock] = None, index: Optional[int] = None, inst: Optional[Instruction] = None) -> None:
        if not self._reporting:
            return
        text = inst.format(lambda v: self._safe_resolve(v)) if inst is not None else ""
        self.violations.append(Violation(rule_id, "FIR", self.function.name, message, block.id if block else None, index, text))

    def _safe_resolve(self, value: Value) -> str:
        if isinstance(value, ParamValue):
            return value.name
        if isinstance(value, FIRValue):
            pos = self.def_positions.get(id(value.instruction))
            return f"%{pos[0]}[{pos[1]}]" if pos else f"<{value.instruction.opcode}?>"
        return "<?>"

    # -- identifier resolution -------------------------------------------

    def _identifier_of(self, value: Value) -> Optional[Identifier]:
        if isinstance(value, ParamValue):
            if value.name in self.own_params or value.name in self.borrow_params:
                return value.name
            return None
        if isinstance(value, FIRValue):
            inst = value.instruction
            if isinstance(inst, LoadVarInst):
                if inst.name in self.owned_local_names or inst.name in self.own_params or inst.name in self.borrow_params:
                    return inst.name
                return None
            if isinstance(inst, (LoadFieldInst, IndexArrayInst, ExtractPayloadFieldInst)):
                # These read an existing slot (struct field, array
                # element, enum payload field) in place -- no fresh
                # allocation happens at the FLIR level (lower_field/
                # lower_index_array/lower_extract_payload_field all just
                # `load` an existing pointer). The result aliases memory
                # the containing object/array/enum still owns; it is not
                # a new "must be independently consumed" value, unlike a
                # genuine allocation (Allocate, Call returning fresh
                # owned data, Move). Treating it as one would demand a
                # Drop that -- since the field/element/payload slot isn't
                # cleared -- would double free once the container itself
                # is later dropped.
                return None
            # Anonymous instruction-result temporaries (an owned Call/Cast/
            # BinaryOp result used directly as a sub-expression, never
            # bound to a name) are deliberately NOT tracked here -- see
            # ir_verifier_spec.md section 8's note on FIRV-O1-O3 scope.
            # ast_to_fir.py has no expression-temporary lifetime tracking
            # at all today (nothing in the pipeline ever drops such a
            # value), so treating every one as a trackable, must-be-
            # consumed identifier surfaces a real, but enormous and
            # untargeted, pre-existing leak class across nearly every
            # string-producing sub-expression in the test corpus --
            # `println(x)`'s own `value as string` cast being typical.
            # Fixing it needs dedicated expression-temporary lifetime
            # infrastructure, not a narrow emitter patch; tracked as a
            # known, scoped-out gap rather than half-fixed here.
            return None
        return None

    def run(self) -> None:
        entry = self.function.blocks[0].id
        entry_state: dict[Identifier, OwnState] = {name: OwnState.OWNED for name in self.own_params | self.borrow_params}
        bottom: dict[Identifier, OwnState] = {}

        block_by_id = {b.id: b for b in self.function.blocks}

        def transfer(block_id: str, in_state: dict[Identifier, OwnState]) -> dict[Identifier, OwnState]:
            block = block_by_id[block_id]
            state = dict(in_state)
            for idx, inst in enumerate(block.instructions):
                self._process_instruction(block, idx, inst, state)
            if block.terminator is not None:
                self._process_instruction(block, len(block.instructions), block.terminator, state)
            return state

        def meet(pred_states: list[dict[Identifier, OwnState]]) -> dict[Identifier, OwnState]:
            return _meet_states(pred_states)

        # The worklist driver calls `transfer` repeatedly (once per block
        # per fixpoint round) with intermediate, not-yet-converged
        # in-states; running the emit-as-a-side-effect instruction
        # processing during that phase would report the same violation
        # multiple times, or report spurious ones off a state that isn't
        # final yet. So: converge silently first...
        self._reporting = False
        in_states, _out_states = forward_dataflow(self.cfg, transfer, meet, entry_state, bottom)
        # ...then do exactly one more pass per block, in deterministic
        # block-declaration order, using each block's final converged
        # in-state, with reporting turned on.
        self._reporting = True
        for block in self.function.blocks:
            if block.id not in self.cfg.reachable:
                continue
            transfer(block.id, in_states[block.id])

        self._check_borrow_params_never_consumed()

    # -- per-instruction processing ---------------------------------------

    def _use(self, value: Value, state: dict[Identifier, OwnState], block: BasicBlock, index: int, inst: Instruction, consuming_rule: Optional[str] = None) -> None:
        """Record a use of `value`. If the identifier is currently MOVED or
        MAYBE_MOVED, flag O1 (or O2 if this specific use is itself a
        consume, per spec's 'subsumes double-drop and drop-after-move')."""
        ident = self._identifier_of(value)
        if ident is None:
            return
        cur = state.get(ident, OwnState.OWNED)
        if cur in (OwnState.MOVED, OwnState.MAYBE_MOVED):
            rule = consuming_rule or "FIRV-O1"
            what = "moved" if cur == OwnState.MOVED else "possibly moved (on some paths)"
            self.emit(rule, f"use of '{_ident_text(ident)}', which is {what}", block, index, inst)

    def _consume(self, value: Value, state: dict[Identifier, OwnState], block: BasicBlock, index: int, inst: Instruction, drop_or_move: bool = False) -> None:
        ident = self._identifier_of(value)
        if ident is None:
            return
        self._use(value, state, block, index, inst, consuming_rule="FIRV-O2" if drop_or_move else None)
        state[ident] = OwnState.MOVED

    def _process_instruction(self, block: BasicBlock, index: int, inst: Instruction, state: dict[Identifier, OwnState]) -> None:
        if isinstance(inst, DeclareLocalInst):
            if inst.operands:
                self._consume(inst.operands[0], state, block, index, inst)
            if (
                inst.var_type.is_owned()
                and not self._is_generic(inst.var_type)
                and not self._is_aliased_read(inst.operands[0] if inst.operands else None)
            ):
                state[inst.name] = OwnState.OWNED
            return

        if isinstance(inst, StoreVarInst):
            self._consume(inst.operands[0], state, block, index, inst)
            if inst.name in self.owned_local_names:
                state[inst.name] = OwnState.OWNED
            return

        if isinstance(inst, DropInst):
            operand = inst.operands[0]
            if operand.result_type is not None and not operand.result_type.is_owned():
                self.emit("FIRV-O5", f"Drop operand has non-owned type '{operand.result_type.render()}'", block, index, inst)
            self._consume(operand, state, block, index, inst, drop_or_move=True)
            return

        if isinstance(inst, MoveInst):
            operand = inst.operands[0]
            if operand.result_type is not None and not operand.result_type.is_owned():
                self.emit("FIRV-O6", f"Move operand has non-owned type '{operand.result_type.render()}'", block, index, inst)
            self._consume(operand, state, block, index, inst, drop_or_move=True)
            return

        if isinstance(inst, CloneInst):
            operand = inst.operands[0]
            if operand.result_type is not None and not operand.result_type.is_owned():
                self.emit("FIRV-O6", f"Clone operand has non-owned type '{operand.result_type.render()}'", block, index, inst)
            self._use(operand, state, block, index, inst)
            return

        if isinstance(inst, ReturnInst):
            for operand in inst.operands:
                self._consume(operand, state, block, index, inst)
            self._check_leaks_at_return(block, index, inst, state)
            return

        if isinstance(inst, StoreFieldInst):
            self._use(inst.operands[0], state, block, index, inst)
            self._consume(inst.operands[1], state, block, index, inst)
            return

        if isinstance(inst, StoreArrayInst):
            self._use(inst.operands[0], state, block, index, inst)
            self._use(inst.operands[1], state, block, index, inst)
            self._consume(inst.operands[2], state, block, index, inst)
            return

        if isinstance(inst, (CallInst, MethodCallInst)):
            self._process_call(inst, state, block, index)
            return

        if isinstance(inst, (AllocateInst, ConstructVariantInst)):
            for operand in inst.operands:
                self._consume(operand, state, block, index, inst)
            return

        if isinstance(inst, (GenNextInst, GenValueInst, ExtractTagInst, ExtractPayloadFieldInst)):
            self._use(inst.operands[0], state, block, index, inst)
            return

        # Default: every other instruction's operands are non-consuming
        # uses (BinaryOp, UnaryOp, Cast, LoadField, IndexArray, Branch
        # condition, LoadVar, Yield's value counts as a borrow-out since
        # the generator retains no ownership record here, ArrayLiteral
        # elements, ...). Still subject to O1 (use-after-move).
        for operand in inst.operands:
            self._use(operand, state, block, index, inst)

    def _process_call(self, inst: Instruction, state: dict[Identifier, OwnState], block: BasicBlock, index: int) -> None:
        is_method = isinstance(inst, MethodCallInst)
        arg_operands = inst.operands[1:] if is_method else inst.operands
        if is_method:
            self._use(inst.operands[0], state, block, index, inst)
        modes = inst.arg_modes
        if len(modes) != len(arg_operands):
            return  # already flagged by Tier 1 (FIRV-T5/T6); don't cascade here.

        seen_modes: dict[Identifier, list[str]] = {}
        for operand, mode in zip(arg_operands, modes):
            ident = self._identifier_of(operand)
            if ident is not None:
                seen_modes.setdefault(ident, []).append(mode)
            if mode == "own":
                self._consume(operand, state, block, index, inst)
            else:
                self._use(operand, state, block, index, inst)

        for ident, mode_list in seen_modes.items():
            if "own" in mode_list and len(mode_list) > 1:
                self.emit("FIRV-O4", f"'{_ident_text(ident)}' is passed both as 'own' and as a borrow in the same call", block, index, inst)
            elif mode_list.count("borrow_mut") > 1:
                self.emit("FIRV-O4", f"'{_ident_text(ident)}' is passed as 'borrow_mut' more than once in the same call", block, index, inst)

    def _check_leaks_at_return(self, block: BasicBlock, index: int, inst: Instruction, state: dict[Identifier, OwnState]) -> None:
        for ident, own_state in state.items():
            if own_state in (OwnState.OWNED, OwnState.MAYBE_MOVED):
                if isinstance(ident, str) and ident in self.borrow_params:
                    continue  # borrow params are never owned by the callee; nothing to leak.
                label = "on some paths" if own_state == OwnState.MAYBE_MOVED else "not consumed"
                self.emit("FIRV-O3", f"'{_ident_text(ident)}' is not consumed on every path to this Return ({label})", block, index, inst)

    def _check_borrow_params_never_consumed(self) -> None:
        """FIRV-O7 (borrow half): a borrow/borrow_mut parameter must never
        be consumed. Checked structurally (independent of dataflow state)
        since it must hold unconditionally, not just 'on some path'."""
        for block in self.function.blocks:
            for idx, inst in enumerate(block.instructions):
                self._check_no_borrow_consume(inst, block, idx)
            if block.terminator is not None:
                self._check_no_borrow_consume(block.terminator, block, len(block.instructions))

    def _check_no_borrow_consume(self, inst: Instruction, block: BasicBlock, index: int) -> None:
        consuming_operands: list[Value] = []
        if isinstance(inst, (DropInst, MoveInst)):
            consuming_operands.append(inst.operands[0])
        elif isinstance(inst, ReturnInst):
            consuming_operands.extend(inst.operands)
        elif isinstance(inst, StoreFieldInst):
            consuming_operands.append(inst.operands[1])
        elif isinstance(inst, StoreArrayInst):
            consuming_operands.append(inst.operands[2])
        elif isinstance(inst, StoreVarInst):
            consuming_operands.append(inst.operands[0])
        elif isinstance(inst, DeclareLocalInst) and inst.operands:
            consuming_operands.append(inst.operands[0])
        elif isinstance(inst, (AllocateInst, ConstructVariantInst)):
            consuming_operands.extend(inst.operands)
        elif isinstance(inst, (CallInst, MethodCallInst)):
            arg_operands = inst.operands[1:] if isinstance(inst, MethodCallInst) else inst.operands
            for operand, mode in zip(arg_operands, inst.arg_modes):
                if mode == "own":
                    consuming_operands.append(operand)

        for operand in consuming_operands:
            if isinstance(operand, ParamValue) and operand.name in self.borrow_params:
                self.emit("FIRV-O7", f"borrow parameter '{operand.name}' is consumed (must never be moved out, dropped, or passed as 'own')", block, index, inst)
            elif isinstance(operand, FIRValue) and isinstance(operand.instruction, LoadVarInst) and operand.instruction.name in self.borrow_params:
                self.emit("FIRV-O7", f"borrow parameter '{operand.instruction.name}' is consumed (must never be moved out, dropped, or passed as 'own')", block, index, inst)


def _ident_text(ident: Identifier) -> str:
    if isinstance(ident, tuple):
        pos = ident[1]
        if isinstance(pos, tuple):
            return f"<temp {pos[0]}[{pos[1]}]>"
        return f"<temp %{pos}>"
    return ident


def verify_ownership(module: FIRModule, function: FIRFunction, cfg: CFG, idom: dict[str, str], violations: list[Violation]) -> None:
    _OwnershipChecker(module, function, cfg, idom, violations).run()


# ---------------------------------------------------------------------------
# FIRV-L3: no DeclareLocal dominated by another DeclareLocal of the same
# name; no local shadows a parameter name.
# ---------------------------------------------------------------------------

def verify_no_shadowing(function: FIRFunction, idom: dict[str, str], cfg: CFG, violations: list[Violation]) -> None:
    param_names = {name for name, _ in function.params}
    decls_by_name: dict[str, list[tuple[str, int, Instruction]]] = {}
    for block in function.blocks:
        for idx, inst in enumerate(block.instructions):
            if isinstance(inst, DeclareLocalInst):
                if inst.name in param_names:
                    violations.append(
                        Violation("FIRV-L3", "FIR", function.name, f"local '{inst.name}' shadows a parameter of the same name", block.id, idx, inst.format(lambda v: "?"))
                    )
                decls_by_name.setdefault(inst.name, []).append((block.id, idx, inst))

    for name, decls in decls_by_name.items():
        if len(decls) < 2:
            continue
        for i, (b1, idx1, inst1) in enumerate(decls):
            for b2, idx2, inst2 in decls[i + 1:]:
                if b1 not in cfg.reachable or b2 not in cfg.reachable:
                    continue
                if dominates(idom, b1, b2) and (b1, idx1) != (b2, idx2):
                    violations.append(
                        Violation("FIRV-L3", "FIR", function.name, f"DeclareLocal('{name}') is dominated by another DeclareLocal of the same name", b2, idx2, inst2.format(lambda v: "?"))
                    )
                elif dominates(idom, b2, b1):
                    violations.append(
                        Violation("FIRV-L3", "FIR", function.name, f"DeclareLocal('{name}') is dominated by another DeclareLocal of the same name", b1, idx1, inst1.format(lambda v: "?"))
                    )


# ---------------------------------------------------------------------------
# FIRV-G4: every GenValue is dominated by a GenNext on the same generator
# value.
# ---------------------------------------------------------------------------

def _generator_identity(value: Value) -> Optional[Identifier]:
    if isinstance(value, ParamValue):
        return ("param", value.name)
    if isinstance(value, FIRValue):
        inst = value.instruction
        if isinstance(inst, LoadVarInst):
            return ("var", inst.name)
        return ("val", id(inst))
    return None


def verify_generator_dominance(function: FIRFunction, idom: dict[str, str], cfg: CFG, def_positions: dict[int, tuple[str, int]], violations: list[Violation]) -> None:
    gen_nexts: list[tuple[Identifier, str, int]] = []
    for block in function.blocks:
        for idx, inst in enumerate(block.instructions):
            if isinstance(inst, GenNextInst):
                ident = _generator_identity(inst.operands[0])
                if ident is not None:
                    gen_nexts.append((ident, block.id, idx))

    for block in function.blocks:
        for idx, inst in enumerate(block.instructions):
            if not isinstance(inst, GenValueInst):
                continue
            ident = _generator_identity(inst.operands[0])
            if ident is None:
                continue
            dominated = any(
                gid == ident and gblock in cfg.reachable and block.id in cfg.reachable
                and _instruction_dominates(idom, gblock, gidx, block.id, idx)
                for gid, gblock, gidx in gen_nexts
            )
            if not dominated:
                violations.append(
                    Violation("FIRV-G4", "FIR", function.name, "GenValue is not dominated by a GenNext on the same generator value", block.id, idx, inst.format(lambda v: "?"))
                )


def _instruction_dominates(idom: dict[str, str], def_block: str, def_index: int, use_block: str, use_index: int) -> bool:
    from ir_analysis import instruction_dominates

    return instruction_dominates(idom, def_block, def_index, use_block, use_index)


# ---------------------------------------------------------------------------
# FIRV-E1: every ExtractPayloadField(v, variant, i) is tag-guarded by the
# true edge of a Branch(ExtractTag(v) == IntLiteral(tag_index(variant))).
# ---------------------------------------------------------------------------

def verify_enum_payload_guards(
    module: FIRModule, function: FIRFunction, idom: dict[str, str], cfg: CFG, violations: list[Violation]
) -> None:
    from fir.ir_node import BinaryOpInst, BranchInst

    variant_tag_index: dict[str, dict[str, int]] = {}
    for type_def in module.types:
        if type_def.kind == "enum":
            variant_tag_index[type_def.name] = {v.name: i for i, v in enumerate(type_def.variants)}

    # Collect guard branches: Branch(BinaryOp("==", ExtractTag(v), IntLiteral(k)), true_block, _)
    guards: list[tuple[Identifier, int, str]] = []  # (enum identity, tag index, true_block id)
    for block in function.blocks:
        term = block.terminator
        if not isinstance(term, BranchInst):
            continue
        cond = term.operands[0]
        if not isinstance(cond, FIRValue) or not isinstance(cond.instruction, BinaryOpInst):
            continue
        cmp = cond.instruction
        if cmp.op != "==":
            continue
        lhs, rhs = cmp.operands
        tag_operand, lit_operand = None, None
        if isinstance(lhs, FIRValue) and isinstance(lhs.instruction, ExtractTagInst):
            tag_operand, lit_operand = lhs, rhs
        elif isinstance(rhs, FIRValue) and isinstance(rhs.instruction, ExtractTagInst):
            tag_operand, lit_operand = rhs, lhs
        if tag_operand is None:
            continue
        if not (isinstance(lit_operand, FIRValue) and isinstance(lit_operand.instruction, IntLiteralInst)):
            continue
        try:
            tag_value = int(lit_operand.instruction.text)
        except ValueError:
            continue
        enum_ident = _generator_identity(tag_operand.instruction.operands[0])
        if enum_ident is None:
            continue
        guards.append((enum_ident, tag_value, term.true_block))

    for block in function.blocks:
        for idx, inst in enumerate(block.instructions):
            if not isinstance(inst, ExtractPayloadFieldInst):
                continue
            enum_ident = _generator_identity(inst.operands[0])
            variant_indices = variant_tag_index.get(_enum_type_name(inst.operands[0]), {})
            expected_tag = variant_indices.get(inst.variant_name)
            guarded = False
            if enum_ident is not None and expected_tag is not None:
                for gident, gtag, gtrue_block in guards:
                    if gident == enum_ident and gtag == expected_tag and gtrue_block in cfg.reachable:
                        if dominates(idom, gtrue_block, block.id):
                            guarded = True
                            break
            if not guarded:
                violations.append(
                    Violation("FIRV-E1", "FIR", function.name, f"ExtractPayloadField('{inst.variant_name}') is not dominated by a matching tag-guard branch", block.id, idx, inst.format(lambda v: "?"))
                )


def _enum_type_name(value: Value) -> Optional[str]:
    rtype = value.result_type
    if rtype is None:
        return None
    return getattr(rtype, "name", None)
