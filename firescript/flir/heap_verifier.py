"""Tier-2 heap-token allocation-lifecycle verifier for FLIR functions.

Implements FLIRV-A1-A5 and FLIRV-M4 from
docs/internal/development/ir_verifier_spec.md sections 5.3-5.4. FLIRV-M5
(null discipline) is not implemented here -- see that spec's section 8.2.
Only runs against a function that already passed Tier-1 checks
(FLIRV-S/T/M1-M3), which guarantee a well-formed CFG with valid dominance.

An intraprocedural forward dataflow tracks the state of *heap tokens*:
values produced by a call that returns a fresh heap allocation (per
flir/runtime_abi.py's RETURNS_FRESH effect, or a call to a
non-runtime FLIRFunction returning a `ptr<...>` -- lowering has no other
source of a fresh pointer). Token identity is tracked through slot
stores/loads (the pattern every normal local variable lowers to --
SlotStore/SlotLoad -- see flir/lowering.py's var_store/var_load): a
`slotstore` of a tracked token's value makes subsequent `slotload`s of
that slot resolve to the same token. Aliasing through struct fields,
arrays, or generator frames is not tracked (a value re-derived via
`load`/`ptradd` is treated as opaque) -- this is a deliberate,
conservative narrowing: under-detecting a leak/misuse of an untracked
alias is preferred over false positives on the many struct/array/frame
access patterns lowering already generates correctly. See
ir_verifier_spec.md section 8 for the same policy applied at the FIR
ownership-verifier layer.

States: LIVE (allocated, not yet freed or transferred away), FREED. A
token that "escapes" -- stored as a struct/array field value, passed as
an argument to a call other than a freeing call or a recognized
borrow-only runtime call, or returned -- is dropped from tracking
entirely: this function is no longer responsible for it (matches the FIR
ownership verifier's stance that a transferred value's downstream fate
isn't this function's concern), so it is not reported as a leak
(FLIRV-A4), nor are further references to it checked.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Union

from flir.ir import (
    BinOp,
    Br,
    Call,
    ConstStr,
    FLIRBlock,
    FLIRFunction,
    FLIRModule,
    FLIRStruct,
    FLIRType,
    FInst,
    FValue,
    GlobalLoad,
    Load,
    PtrAdd,
    Ret,
    SlotAddr,
    SlotLoad,
    SlotStore,
    Store,
)
from flir.runtime_abi import MemoryEffect, runtime_signature
from ir_analysis import CFG, Violation, forward_dataflow

# A token identity is either a "temp" (the (block_id, index) position of the
# defining Call instruction) -- position-keyed, not id()-keyed, for
# determinism across runs -- or a "slot" (a named local the token was
# stored into via SlotStore, tracked so later SlotLoads of that name
# resolve to the same token).
Identifier = tuple[str, object]


class HeapState(Enum):
    LIVE = "live"
    FREED = "freed"
    MAYBE_FREED = "maybe_freed"


def _meet_one(a: HeapState, b: HeapState) -> HeapState:
    if a == b:
        return a
    return HeapState.MAYBE_FREED


class _State:
    """Dataflow state: token states plus the current slot->token aliasing.

    Immutable by convention (transfer() always builds a fresh copy);
    equality/copy support the forward_dataflow fixpoint driver.
    """

    __slots__ = ("tokens", "slot_alias")

    def __init__(self, tokens: Optional[dict[Identifier, HeapState]] = None, slot_alias: Optional[dict[str, Identifier]] = None):
        self.tokens: dict[Identifier, HeapState] = dict(tokens) if tokens else {}
        self.slot_alias: dict[str, Identifier] = dict(slot_alias) if slot_alias else {}

    def copy(self) -> "_State":
        return _State(self.tokens, self.slot_alias)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _State) and self.tokens == other.tokens and self.slot_alias == other.slot_alias


def _meet_states(states: list[_State]) -> _State:
    if not states:
        return _State()
    tokens: dict[Identifier, HeapState] = dict(states[0].tokens)
    slot_alias: dict[str, Identifier] = dict(states[0].slot_alias)
    for other in states[1:]:
        # A token id is position-keyed to the one instruction that created
        # it (see _process's fresh-token handling), which does not
        # dominate every predecessor of a join the way a named FIR binding
        # does (L1's dominance guarantee doesn't apply here) -- e.g. a
        # branch that skips the block defining the token entirely. A key
        # missing from one predecessor's tokens/slot_alias is therefore
        # one that predecessor never reached, not one that "isn't live
        # past this join anyway": intersect instead of union, dropping
        # anything not present (and, for tokens, meet-combined) on every
        # incoming path.
        for key in list(tokens.keys()):
            if key not in other.tokens:
                del tokens[key]
            else:
                tokens[key] = _meet_one(tokens[key], other.tokens[key])
        for name in list(slot_alias.keys()):
            if slot_alias.get(name) != other.slot_alias.get(name):
                del slot_alias[name]
    return _State(tokens, slot_alias)


_FREEING_SUFFIX = "__destroy"


def _runtime_name(callee: str) -> str:
    """Strip the "impl_" prefix flir/lowering.py's rt_call() adds when a
    fs_rt_* entry point has a firescript-implemented body (the common
    case -- see request_function()): the call's actual FLIR callee is
    "impl_fs_rt_free", not "fs_rt_free". RUNTIME_ABI is keyed by the
    unprefixed name, so lookups against it must undo this first."""
    return callee[len("impl_"):] if callee.startswith("impl_") else callee


def _is_freeing_call(callee: str) -> bool:
    name = _runtime_name(callee)
    return name == "fs_rt_free" or callee.endswith(_FREEING_SUFFIX)


class _HeapChecker:
    def __init__(
        self,
        module: FLIRModule,
        function: FLIRFunction,
        func_index: dict[str, FLIRFunction],
        struct_index: dict[str, FLIRStruct],
        cfg: CFG,
        def_positions: dict[int, tuple[str, int]],
        violations: list[Violation],
    ):
        self.module = module
        self.function = function
        self.func_index = func_index
        self.struct_index = struct_index
        self.cfg = cfg
        self.def_positions = def_positions
        self.violations = violations
        # See ownership_verifier.py's identical two-phase gate: the
        # worklist driver calls transfer() speculatively, possibly several
        # times per block, on intermediate not-yet-converged states.
        # Reporting during that phase would duplicate or fabricate
        # violations off a state that isn't final yet.
        self._reporting = False

        # Which (block_id, index) positions are themselves the origin of a
        # fresh heap token, and which struct each token points to (for A5).
        self.token_origin_pointee: dict[tuple[str, int], Optional[str]] = {}
        for block in function.blocks:
            for idx, inst in enumerate(block.instructions):
                pointee = self._fresh_token_pointee(inst)
                if pointee is not None or self._is_fresh_token(inst):
                    self.token_origin_pointee[(block.id, idx)] = pointee

    # -- token provenance --------------------------------------------------

    def _is_fresh_token(self, inst: FInst) -> bool:
        if not isinstance(inst, Call):
            return False
        if inst.result_type is None or inst.result_type.kind != "ptr":
            return False
        sig = runtime_signature(_runtime_name(inst.callee))
        if sig is not None:
            return sig.effect == MemoryEffect.RETURNS_FRESH
        # A call to a non-runtime (user, monomorphized) function returning
        # a pointer: lowering has no other way to produce a pointer value
        # than an allocation inside that callee, so treat it the same as a
        # RETURNS_FRESH runtime call -- ownership of the result transfers
        # to this function, exactly like FIR-level own-mode returns.
        return inst.callee in self.func_index

    def _fresh_token_pointee(self, inst: FInst) -> Optional[str]:
        if self._is_fresh_token(inst) and inst.result_type is not None:
            return inst.result_type.pointee
        return None

    def _is_borrow_only_call(self, callee: str) -> bool:
        sig = runtime_signature(_runtime_name(callee))
        if sig is not None:
            return sig.effect in (MemoryEffect.BORROWS, MemoryEffect.RETURNS_FRESH)
        return False

    # -- identifier resolution ----------------------------------------------

    def _identifier_of(self, value: FValue, state: _State) -> Optional[Identifier]:
        pos = self.def_positions.get(id(value.instruction))
        inst = value.instruction
        if isinstance(inst, SlotLoad):
            return state.slot_alias.get(inst.name)
        if pos is not None and pos in self.token_origin_pointee:
            return ("temp", pos)
        return None

    def emit(self, rule_id: str, message: str, block: FLIRBlock, index: int, inst: FInst) -> None:
        if not self._reporting:
            return
        text = inst.format(self._safe_resolve)
        self.violations.append(Violation(rule_id, "FLIR", self.function.name, message, block.id, index, text))

    def _safe_resolve(self, value: FValue) -> str:
        pos = self.def_positions.get(id(value.instruction))
        return f"%{pos[0]}[{pos[1]}]" if pos else f"<{value.instruction.opcode}?>"

    def _ident_text(self, ident: Identifier) -> str:
        kind, payload = ident
        if kind == "slot":
            return f"slot '{payload}'"
        block_id, idx = payload
        return f"<token %{block_id}[{idx}]>"

    # -- structural provenance (A3, M4) --------------------------------------

    def _resolved_origin(self, value: FValue, state: _State) -> FInst:
        """Follow one hop of must-alias slot resolution, then return the
        (possibly still slot-load) originating instruction for a
        structural provenance check (A3/M4)."""
        inst = value.instruction
        if isinstance(inst, SlotLoad):
            ident = state.slot_alias.get(inst.name)
            if ident is not None and ident[0] == "temp":
                block_id, idx = ident[1]
                block = next((b for b in self.function.blocks if b.id == block_id), None)
                if block is not None and idx < len(block.instructions):
                    return block.instructions[idx]
        return inst

    def _check_free_provenance(self, value: FValue, state: _State, block: FLIRBlock, index: int, inst: FInst) -> None:
        origin = self._resolved_origin(value, state)
        if isinstance(origin, (ConstStr, SlotAddr, GlobalLoad, PtrAdd)):
            self.emit("FLIRV-A3", f"free/destroy argument is not a heap-allocation base pointer ({origin.opcode})", block, index, inst)

    def _check_readonly_store_base(self, base: FValue, state: _State, block: FLIRBlock, index: int, inst: FInst) -> None:
        origin = self._resolved_origin(base, state)
        if isinstance(origin, ConstStr):
            self.emit("FLIRV-M4", "store base is read-only data (strconst)", block, index, inst)

    # -- destructor totality (A5) --------------------------------------------

    def _struct_needs_destructor(self, struct_name: Optional[str]) -> bool:
        if struct_name is None or struct_name not in self.struct_index:
            return False
        struct = self.struct_index[struct_name]
        for _fname, ftype, _offset in struct.fields:
            if ftype.kind == "ptr":
                return True
        for layout in struct.variant_layouts.values():
            for _fname, ftype, _offset in layout:
                if ftype.kind == "ptr":
                    return True
        return False

    # -- per-instruction processing ------------------------------------------

    def _use(self, value: FValue, state: _State, block: FLIRBlock, index: int, inst: FInst) -> None:
        ident = self._identifier_of(value, state)
        if ident is None:
            return
        cur = state.tokens.get(ident)
        if cur in (HeapState.FREED, HeapState.MAYBE_FREED):
            what = "freed" if cur == HeapState.FREED else "possibly freed (on some paths)"
            self.emit("FLIRV-A2", f"use of {self._ident_text(ident)}, which is {what}", block, index, inst)

    def _escape(self, value: FValue, state: _State) -> None:
        ident = self._identifier_of(value, state)
        if ident is not None:
            state.tokens.pop(ident, None)

    def _process(self, block: FLIRBlock, index: int, inst: FInst, state: _State) -> None:
        pos = (block.id, index)

        if isinstance(inst, SlotStore):
            value = inst.operands[0]
            self._use(value, state, block, index, inst)
            ident = self._identifier_of(value, state)
            if ident is not None:
                state.slot_alias[inst.name] = ident
            else:
                state.slot_alias.pop(inst.name, None)
            return

        if isinstance(inst, Load):
            self._use(inst.operands[0], state, block, index, inst)
            return

        if isinstance(inst, Store):
            base, value = inst.operands[0], inst.operands[1]
            self._use(base, state, block, index, inst)
            self._check_readonly_store_base(base, state, block, index, inst)
            self._escape(value, state)
            return

        if isinstance(inst, Call):
            if _is_freeing_call(inst.callee):
                target = inst.operands[0]
                self._check_free_provenance(target, state, block, index, inst)
                # A5 is structural (the argument's *static* pointee type),
                # not gated on dataflow-token tracking: the dominant
                # fs_rt_free-on-a-struct-field pattern (every generated
                # destructor's recursive field free) frees a `load` result,
                # an alias this analysis doesn't track as a token (see the
                # module docstring) -- but the rule still applies to it.
                if _runtime_name(inst.callee) == "fs_rt_free":
                    pointee = target.value_type.pointee if target.value_type is not None else None
                    # A struct's own generated `<S>__destroy` legitimately
                    # frees S's own backing allocation directly as its
                    # final step, after already recursively
                    # freeing/destroying each owned field individually
                    # earlier in the same function (see
                    # flir/lowering.py's ensure_destructor/
                    # ensure_enum_destructor) -- that terminal self-free is
                    # not the "should have called the destructor instead"
                    # mistake this rule targets.
                    is_own_destructor_self_free = pointee is not None and self.function.name == f"{pointee}__destroy"
                    # ast_to_fir.py's _convert_super_call splices a
                    # temporary base-class object's fields onto `this`
                    # then releases the shell without running its
                    # destructor (the fields already transferred) --
                    # tagged by lowering.py's lower_call, see there.
                    is_shallow_free = bool(inst.metadata.get("shallow_free"))
                    if self._struct_needs_destructor(pointee) and not is_own_destructor_self_free and not is_shallow_free:
                        self.emit("FLIRV-A5", f"fs_rt_free called directly on '{pointee}', which has owned fields -- call its destructor instead", block, index, inst)
                ident = self._identifier_of(target, state)
                if ident is not None:
                    cur = state.tokens.get(ident)
                    if cur in (HeapState.FREED, HeapState.MAYBE_FREED):
                        what = "freed" if cur == HeapState.FREED else "possibly freed (on some paths)"
                        self.emit("FLIRV-A1", f"{self._ident_text(ident)} is {what} again", block, index, inst)
                    state.tokens[ident] = HeapState.FREED
            else:
                borrow_only = self._is_borrow_only_call(inst.callee)
                for arg in inst.operands:
                    self._use(arg, state, block, index, inst)
                    if not borrow_only:
                        self._escape(arg, state)
            if self._is_fresh_token(inst):
                state.tokens[("temp", pos)] = HeapState.LIVE
            return

        if isinstance(inst, Ret):
            for value in inst.operands:
                self._use(value, state, block, index, inst)
                self._escape(value, state)
            return

        if isinstance(inst, Br):
            self._use(inst.operands[0], state, block, index, inst)
            return

        for operand in inst.operands:
            self._use(operand, state, block, index, inst)

    def _check_leaks_at_ret(self, block: FLIRBlock, index: int, inst: FInst, state: _State) -> None:
        # A4 is narrowed to tokens currently referenced by a named slot --
        # see the module docstring's "named vs. anonymous" note. A token
        # that is live but was never stored into any slot is a pure
        # expression-temporary (e.g. an intermediate concatenation result
        # never bound to a local); the FIR ownership verifier does not
        # track those at all (ir_verifier_spec.md section 8), for the same
        # reason: ast_to_fir.py has no expression-temporary lifetime
        # tracking anywhere in the pipeline, so treating every one as a
        # must-be-freed value surfaces a real, but enormous and
        # untargeted, pre-existing leak class -- string concatenation
        # chains are typical -- rather than a specific lowering bug.
        named = set(state.slot_alias.values())
        for ident, st in state.tokens.items():
            if st == HeapState.LIVE and ident in named:
                self.emit("FLIRV-A4", f"{self._ident_text(ident)} is still live at this Return (leaked)", block, index, inst)

    def run(self) -> None:
        if not self.function.blocks:
            return
        entry = self.function.blocks[0].id
        entry_state = _State()
        bottom = _State()
        block_by_id = {b.id: b for b in self.function.blocks}

        def transfer(block_id: str, in_state: _State) -> _State:
            block = block_by_id[block_id]
            state = in_state.copy()
            for idx, inst in enumerate(block.instructions):
                self._process(block, idx, inst, state)
                if self._reporting and isinstance(inst, Ret):
                    self._check_leaks_at_ret(block, idx, inst, state)
            return state

        def meet(pred_states: list[_State]) -> _State:
            return _meet_states(pred_states)

        self._reporting = False
        in_states, _out_states = forward_dataflow(self.cfg, transfer, meet, entry_state, bottom)
        self._reporting = True
        for block in self.function.blocks:
            if block.id not in self.cfg.reachable:
                continue
            transfer(block.id, in_states[block.id])


def verify_heap_lifecycle(
    module: FLIRModule,
    function: FLIRFunction,
    func_index: dict[str, FLIRFunction],
    struct_index: dict[str, FLIRStruct],
    cfg: CFG,
    def_positions: dict[int, tuple[str, int]],
    violations: list[Violation],
) -> None:
    _HeapChecker(module, function, func_index, struct_index, cfg, def_positions, violations).run()
