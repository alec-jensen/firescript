"""Tier-2 heap-token verifier (firescript/flir/heap_verifier.py) across loop
back-edges: tokens allocated before a loop must stay tracked through the
loop header, so leaks, frees inside the body, and use-after-free across the
back-edge are all reported, while valid loop shapes stay clean."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from errors import IRVerificationError  # noqa: E402
from flir.ir import (  # noqa: E402
    Br,
    Call,
    ConstBool,
    ConstStr,
    FLIRFunction,
    FLIRModule,
    I32,
    Jmp,
    Ret,
    SlotDecl,
    SlotLoad,
    SlotStore,
    VOID,
    ptr_to,
)

STR = ptr_to("i8")


def _violations(module: FLIRModule) -> list:
    try:
        module.validate()
    except IRVerificationError as e:
        return e.violations
    return []


def _expect(module: FLIRModule, rule_id: str, fragment: str = "") -> None:
    found = _violations(module)
    t.require(
        any(v.rule_id == rule_id and fragment in v.message for v in found),
        f"{rule_id} / {fragment!r} not in: {[(v.rule_id, v.message) for v in found]}",
    )


def _expect_clean(module: FLIRModule) -> None:
    found = _violations(module)
    t.require(not found, f"unexpected violations: {[(v.rule_id, v.message) for v in found]}")


def _func():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", params=None, return_type=VOID)
    module.add_function(func)
    return module, func


def _alloc(block, slot: str = "s"):
    block.add(SlotDecl(slot, STR))
    src = block.add(ConstStr("x"))
    token = block.add(Call("fs_rt_str_dup", [src], STR))
    block.add(SlotStore(slot, token))
    return token


def _free(block, slot: str = "s"):
    block.add(Call("fs_rt_free", [block.add(SlotLoad(slot, STR))], VOID))


def _use(block, slot: str = "s"):
    block.add(Call("fs_rt_str_length", [block.add(SlotLoad(slot, STR))], I32))


def _cond(block):
    return block.add(ConstBool(True))


def _close(body, header):
    body.add(Jmp(header.id))


def _simple_loop():
    """entry -> header -> (body -> header | exit); the caller fills body, then calls _close(body, header)."""
    module, func = _func()
    entry = func.new_block()
    header, body, exit_b = func.new_block(), func.new_block(), func.new_block()
    header.add(Br(_cond(header), body.id, exit_b.id))
    return module, entry, header, body, exit_b


def test_a4_pre_loop_allocation_never_freed_is_reported():
    module, entry, header, body, exit_b = _simple_loop()
    _alloc(entry)
    entry.add(Jmp(header.id))
    _close(body, header)
    exit_b.add(Ret())
    _expect(module, "FLIRV-A4", "leaked")


def test_a1_pre_loop_allocation_freed_in_body_is_possibly_freed_on_next_iteration():
    module, entry, header, body, exit_b = _simple_loop()
    _alloc(entry)
    _free(body)
    entry.add(Jmp(header.id))
    _close(body, header)
    exit_b.add(Ret())
    _expect(module, "FLIRV-A1")


def test_a2_use_after_free_across_back_edge_is_reported():
    module, func = _func()
    entry = func.new_block()
    header, body, exit_b = func.new_block(), func.new_block(), func.new_block()
    _alloc(entry)
    entry.add(Jmp(header.id))
    header.add(Br(_cond(header), body.id, exit_b.id))
    _use(body)
    _free(body)
    body.add(Jmp(header.id))
    exit_b.add(Ret())
    found = _violations(module)
    t.require(any(v.rule_id in ("FLIRV-A1", "FLIRV-A2") for v in found), str([(v.rule_id, v.message) for v in found]))


def test_valid_alloc_and_free_inside_loop_body_is_clean():
    module, entry, header, body, exit_b = _simple_loop()
    _alloc(body)
    _use(body)
    _free(body)
    entry.add(Jmp(header.id))
    _close(body, header)
    exit_b.add(Ret())
    _expect_clean(module)


def test_valid_pre_loop_allocation_freed_after_loop_exit_is_clean():
    module, entry, header, body, exit_b = _simple_loop()
    _alloc(entry)
    _use(body)
    entry.add(Jmp(header.id))
    _close(body, header)
    _free(exit_b)
    exit_b.add(Ret())
    _expect_clean(module)


def _nested_loops():
    module, func = _func()
    entry = func.new_block()
    outer_h, inner_h, inner_b, outer_latch, exit_b = (func.new_block() for _ in range(5))
    outer_h.add(Br(_cond(outer_h), inner_h.id, exit_b.id))
    inner_h.add(Br(_cond(inner_h), inner_b.id, outer_latch.id))
    outer_latch.add(Jmp(outer_h.id))
    return module, entry, outer_h, inner_b, inner_h, outer_latch, exit_b


def test_nested_loops_pre_loop_allocation_leak_is_reported():
    module, entry, outer_h, inner_b, inner_h, outer_latch, exit_b = _nested_loops()
    _alloc(entry)
    _use(inner_b)
    entry.add(Jmp(outer_h.id))
    inner_b.add(Jmp(inner_h.id))
    exit_b.add(Ret())
    _expect(module, "FLIRV-A4", "leaked")


def test_nested_loops_free_in_inner_body_is_reported():
    module, entry, outer_h, inner_b, inner_h, outer_latch, exit_b = _nested_loops()
    _alloc(entry)
    _free(inner_b)
    entry.add(Jmp(outer_h.id))
    inner_b.add(Jmp(inner_h.id))
    exit_b.add(Ret())
    _expect(module, "FLIRV-A1")


def test_nested_loops_use_in_inner_free_after_exit_is_clean():
    module, entry, outer_h, inner_b, inner_h, outer_latch, exit_b = _nested_loops()
    _alloc(entry)
    _use(inner_b)
    entry.add(Jmp(outer_h.id))
    inner_b.add(Jmp(inner_h.id))
    _free(exit_b)
    exit_b.add(Ret())
    _expect_clean(module)


def test_while_loop_conditional_free_inside_body_is_reported():
    module, func = _func()
    entry = func.new_block()
    header, body, then_b, latch, exit_b = (func.new_block() for _ in range(5))
    _alloc(entry)
    entry.add(Jmp(header.id))
    header.add(Br(_cond(header), body.id, exit_b.id))
    body.add(Br(_cond(body), then_b.id, latch.id))
    _free(then_b)
    then_b.add(Jmp(latch.id))
    latch.add(Jmp(header.id))
    exit_b.add(Ret())
    _expect(module, "FLIRV-A1")


def test_while_loop_conditional_use_then_free_after_exit_is_clean():
    module, func = _func()
    entry = func.new_block()
    header, body, then_b, latch, exit_b = (func.new_block() for _ in range(5))
    _alloc(entry)
    entry.add(Jmp(header.id))
    header.add(Br(_cond(header), body.id, exit_b.id))
    body.add(Br(_cond(body), then_b.id, latch.id))
    _use(then_b)
    then_b.add(Jmp(latch.id))
    latch.add(Jmp(header.id))
    _free(exit_b)
    exit_b.add(Ret())
    _expect_clean(module)
