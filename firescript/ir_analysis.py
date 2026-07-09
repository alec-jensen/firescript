"""Shared CFG/dataflow machinery for the FIR and FLIR verifiers.

Parameterized over "block id" (str) so both IR levels can reuse the same
reverse-postorder, dominance, and forward-dataflow-fixpoint code. Callers
supply the block order and a successor lookup; nothing here knows about
FIR or FLIR instruction shapes.

Determinism: block order is always the caller-supplied function-declaration
order, edges are visited in that order, and dataflow worklists are seeded
and drained in reverse-postorder with fixed tie-breaking -- never a Python
set/dict whose iteration order isn't insertion-stable in the way we need.
See CLAUDE.md's determinism rule and ir_verifier_spec.md section 3.4.
"""

from __future__ import annotations

from typing import Callable, Generic, Optional, TypeVar

State = TypeVar("State")


class CFG:
    """A control-flow graph over block ids, built from caller-declared order."""

    def __init__(self, block_ids: list[str], entry: str, successors: dict[str, list[str]]):
        self.block_ids = list(block_ids)
        self.entry = entry
        self.successors = successors
        preds: dict[str, list[str]] = {b: [] for b in block_ids}
        for b in block_ids:
            for s in successors.get(b, []):
                if s in preds:
                    preds[s].append(b)
        self.predecessors = preds
        reachable_order, visited = _reverse_postorder(entry, successors, block_ids)
        self.reachable = visited
        self.rpo = reachable_order + [b for b in block_ids if b not in visited]


def build_cfg(block_ids: list[str], entry: str, successors_of: Callable[[str], list[str]]) -> CFG:
    successors = {b: list(successors_of(b)) for b in block_ids}
    return CFG(block_ids, entry, successors)


def _reverse_postorder(
    entry: str, successors: dict[str, list[str]], all_ids: list[str]
) -> tuple[list[str], set[str]]:
    """Iterative DFS-based reverse postorder from `entry`.

    Deterministic: successors are visited in the order given by
    `successors[block]` (declaration order). Returns (order, visited) --
    `order` lists only blocks reachable from `entry`; `visited` is the
    same set of ids, for O(1) reachability checks.
    """
    all_id_set = set(all_ids)
    visited: set[str] = set()
    postorder: list[str] = []

    if entry in all_id_set:
        # (node, next-child-index-to-visit) explicit stack -- avoids Python
        # recursion-depth limits on large generated functions.
        stack: list[tuple[str, int]] = [(entry, 0)]
        visited.add(entry)
        while stack:
            node, idx = stack[-1]
            succs = successors.get(node, [])
            if idx < len(succs):
                stack[-1] = (node, idx + 1)
                nxt = succs[idx]
                if nxt not in visited:
                    visited.add(nxt)
                    stack.append((nxt, 0))
            else:
                postorder.append(node)
                stack.pop()

    postorder.reverse()
    return postorder, visited


def _intersect(b1: str, b2: str, idom: dict[str, str], order_index: dict[str, int]) -> str:
    while b1 != b2:
        while order_index[b1] > order_index[b2]:
            b1 = idom[b1]
        while order_index[b2] > order_index[b1]:
            b2 = idom[b2]
    return b1


def compute_dominators(cfg: CFG) -> dict[str, str]:
    """Cooper/Harvey/Kennedy iterative dominators.

    Returns `idom`: block id -> immediate dominator id (idom[entry] ==
    entry). Only covers blocks reachable from cfg.entry; unreachable
    blocks are absent from the result.
    """
    # cfg.rpo lists reachable blocks first, in RPO order, followed by
    # unreachable ones appended in declaration order; take the prefix.
    reachable_rpo = [b for b in cfg.rpo if b in cfg.reachable]
    order_index = {b: i for i, b in enumerate(reachable_rpo)}
    idom: dict[str, str] = {cfg.entry: cfg.entry}
    changed = True
    while changed:
        changed = False
        for b in reachable_rpo:
            if b == cfg.entry:
                continue
            preds = cfg.predecessors.get(b, [])
            processed_preds = [p for p in preds if p in idom]
            if not processed_preds:
                continue
            new_idom = processed_preds[0]
            for p in processed_preds[1:]:
                new_idom = _intersect(new_idom, p, idom, order_index)
            if idom.get(b) != new_idom:
                idom[b] = new_idom
                changed = True
    return idom


def dominates(idom: dict[str, str], a: str, b: str) -> bool:
    """Does block `a` dominate block `b`? (a == b counts as dominating.)"""
    if a == b:
        return True
    if b not in idom or a not in idom:
        return False
    node = b
    seen: set[str] = set()
    while node != idom[node]:
        node = idom[node]
        if node == a:
            return True
        if node in seen:
            break
        seen.add(node)
    return False


def instruction_dominates(
    idom: dict[str, str],
    def_block: str,
    def_index: int,
    use_block: str,
    use_index: int,
) -> bool:
    """Does the instruction at (def_block, def_index) dominate the use at
    (use_block, use_index)? Indices are positions within a block's
    instruction stream (terminator, if any, conventionally comes last).
    """
    if def_block == use_block:
        return def_index < use_index
    return dominates(idom, def_block, use_block)


def forward_dataflow(
    cfg: CFG,
    transfer: Callable[[str, State], State],
    meet: Callable[[list[State]], State],
    entry_state: State,
    bottom: State,
) -> tuple[dict[str, State], dict[str, State]]:
    """Iterative forward dataflow fixpoint, RPO-seeded worklist, deterministic.

    `transfer(block_id, in_state) -> out_state` and `meet(pred_out_states)
    -> in_state` must be pure functions of their inputs. Returns
    (in_states, out_states) keyed by block id, only for blocks reachable
    from cfg.entry. States must support `==` for fixpoint detection.
    """
    out_states: dict[str, State] = {b: bottom for b in cfg.reachable}
    in_states: dict[str, State] = {}

    worklist: list[str] = [b for b in cfg.rpo if b in cfg.reachable]
    in_worklist: set[str] = set(worklist)
    while worklist:
        b = worklist.pop(0)
        in_worklist.discard(b)
        if b == cfg.entry:
            in_state = entry_state
        else:
            preds = [p for p in cfg.predecessors.get(b, []) if p in cfg.reachable]
            pred_outs = [out_states[p] for p in preds]
            in_state = meet(pred_outs) if pred_outs else bottom
        in_states[b] = in_state
        new_out = transfer(b, in_state)
        if new_out != out_states[b]:
            out_states[b] = new_out
            for succ in cfg.successors.get(b, []):
                if succ in cfg.reachable and succ not in in_worklist:
                    worklist.append(succ)
                    in_worklist.add(succ)
    return in_states, out_states


class Violation:
    """One verifier rule violation, in the reporting shape spec section 3.3
    describes: rule id, IR level, function/block/instruction location, the
    instruction's own deterministic dump text, and a one-line explanation.
    """

    __slots__ = ("rule_id", "ir_level", "function_name", "block_id", "instruction_index", "instruction_text", "message")

    def __init__(
        self,
        rule_id: str,
        ir_level: str,
        function_name: str,
        message: str,
        block_id: Optional[str] = None,
        instruction_index: Optional[int] = None,
        instruction_text: str = "",
    ):
        self.rule_id = rule_id
        self.ir_level = ir_level
        self.function_name = function_name
        self.block_id = block_id
        self.instruction_index = instruction_index
        self.instruction_text = instruction_text
        self.message = message

    def location(self) -> str:
        loc = self.function_name
        if self.block_id is not None:
            loc += f"/{self.block_id}"
            if self.instruction_index is not None:
                loc += f"[{self.instruction_index}]"
        return loc

    def format(self) -> str:
        text = f"{self.rule_id} in {self.location()}: {self.message}"
        if self.instruction_text:
            text += f"\n    {self.instruction_text}"
        return text
