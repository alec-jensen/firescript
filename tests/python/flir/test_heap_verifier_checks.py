"""Focused unit tests for the FLIR Tier-2 heap-token verifier
(firescript/flir/heap_verifier.py): one allocation lifecycle per test,
each asserting a specific FLIRV-A1..A5 / M4 diagnostic (leak, double free,
use after free, free of a non-heap pointer, free of a struct that needs its
destructor), with matching valid cases at the boundaries: control-flow
joins (freed on every path vs. some paths vs. none), loops, ownership
escapes (store into a field, call argument, return), slot re-binding,
user-function-returned allocations, and `__destroy`-style frees."""
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
    ConstInt,
    ConstNull,
    ConstStr,
    FLIRFunction,
    FLIRModule,
    FLIRStruct,
    GlobalLoad,
    I32,
    I64,
    Jmp,
    PtrAdd,
    Ret,
    SlotAddr,
    SlotDecl,
    SlotLoad,
    SlotStore,
    Store,
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


def _rules(module: FLIRModule) -> list[str]:
    return [v.rule_id for v in _violations(module)]


def _expect(module: FLIRModule, rule_id: str, fragment: str = "") -> None:
    found = _violations(module)
    t.require(
        any(v.rule_id == rule_id and fragment in v.message for v in found),
        f"{rule_id} / {fragment!r} not in: {[(v.rule_id, v.message) for v in found]}",
    )


def _expect_clean(module: FLIRModule) -> None:
    found = _violations(module)
    t.require(not found, f"unexpected violations: {[(v.rule_id, v.message) for v in found]}")


def _func(params=None, return_type=VOID):
    module = FLIRModule("firescript")
    func = FLIRFunction("f", params=params, return_type=return_type)
    module.add_function(func)
    return module, func


def _alloc(block, slot: str = "s"):
    """Fresh token (fs_rt_str_dup is RETURNS_FRESH) bound to a declared slot."""
    block.add(SlotDecl(slot, STR))
    src = block.add(ConstStr("x"))
    token = block.add(Call("fs_rt_str_dup", [src], STR))
    block.add(SlotStore(slot, token))
    return token


def _free(block, slot: str = "s"):
    block.add(Call("fs_rt_free", [block.add(SlotLoad(slot, STR))], VOID))


def _use(block, slot: str = "s"):
    block.add(Call("fs_rt_str_length", [block.add(SlotLoad(slot, STR))], I32))



# -- straight-line lifecycles -----------------------------------------------------

def test_valid_alloc_use_free_is_clean():
    module, func = _func()
    b = func.new_block()
    _alloc(b)
    _use(b)
    _free(b)
    b.add(Ret())
    _expect_clean(module)


def test_a4_leak_reports_the_allocating_position():
    module, func = _func()
    b = func.new_block()
    _alloc(b)
    b.add(Ret())
    found = [v for v in _violations(module) if v.rule_id == "FLIRV-A4"]
    t.require(len(found) == 1, str(found))
    t.require("<token %L0[" in found[0].message and "leaked" in found[0].message, found[0].message)


def test_a4_anonymous_temporary_never_bound_to_a_slot_is_not_a_leak():
    module, func = _func()
    b = func.new_block()
    b.add(Call("fs_rt_str_dup", [b.add(ConstStr("x"))], STR))
    b.add(Ret())
    _expect_clean(module)


def test_a1_double_free_message_says_freed_again():
    module, func = _func()
    b = func.new_block()
    _alloc(b)
    _free(b)
    _free(b)
    b.add(Ret())
    _expect(module, "FLIRV-A1", "is freed again")
    t.require("FLIRV-A4" not in _rules(module))


def test_a2_use_after_free_via_borrowing_runtime_call():
    module, func = _func()
    b = func.new_block()
    _alloc(b)
    _free(b)
    b.add(Call("fs_rt_str_length", [b.add(SlotLoad("s", STR))], I32))
    b.add(Ret())
    _expect(module, "FLIRV-A2", "which is freed")


def test_a2_storing_a_freed_token_into_another_slot_is_a_use():
    module, func = _func()
    b = func.new_block()
    _alloc(b)
    b.add(SlotDecl("t", STR))
    _free(b)
    b.add(SlotStore("t", b.add(SlotLoad("s", STR))))
    b.add(Ret())
    _expect(module, "FLIRV-A2", "which is freed")


def test_a2_use_after_free_as_store_base():
    module, func = _func()
    b = func.new_block()
    _alloc(b)
    _free(b)
    base = b.add(SlotLoad("s", STR))
    b.add(Store(I32, base, 0, b.add(ConstInt("1", I32))))
    b.add(Ret())
    _expect(module, "FLIRV-A2", "which is freed")


def test_double_free_through_aliasing_slot_is_detected():
    module, func = _func()
    b = func.new_block()
    _alloc(b)
    b.add(SlotDecl("alias", STR))
    b.add(SlotStore("alias", b.add(SlotLoad("s", STR))))
    _free(b, "s")
    _free(b, "alias")
    b.add(Ret())
    _expect(module, "FLIRV-A1", "is freed again")


# -- control-flow joins --------------------------------------------------------------

def _diamond(module_func_pair):
    module, func = module_func_pair
    entry = func.new_block()
    then_b, else_b, join = func.new_block(), func.new_block(), func.new_block()
    return module, func, entry, then_b, else_b, join


def _wire_diamond(entry, then_b, else_b, join):
    entry.add(Br(entry.add(ConstBool(True)), then_b.id, else_b.id))
    then_b.add(Jmp(join.id))
    else_b.add(Jmp(join.id))


def test_free_on_both_branches_then_free_at_join_is_a1_freed_again():
    module, func, entry, then_b, else_b, join = _diamond(_func())
    _alloc(entry)
    _free(then_b)
    _free(else_b)
    _wire_diamond(entry, then_b, else_b, join)
    _free(join)
    join.add(Ret())
    _expect(module, "FLIRV-A1", "is freed again")


def test_free_on_one_branch_then_free_at_join_is_a1_possibly_freed():
    module, func, entry, then_b, else_b, join = _diamond(_func())
    _alloc(entry)
    _free(then_b)
    _wire_diamond(entry, then_b, else_b, join)
    _free(join)
    join.add(Ret())
    _expect(module, "FLIRV-A1", "possibly freed (on some paths) again")


def test_free_on_one_branch_then_use_at_join_is_a2_possibly_freed():
    module, func, entry, then_b, else_b, join = _diamond(_func())
    _alloc(entry)
    _free(then_b)
    _wire_diamond(entry, then_b, else_b, join)
    _use(join)
    join.add(Ret())
    _expect(module, "FLIRV-A2", "possibly freed (on some paths)")


def test_free_on_neither_branch_leaks_at_join():
    module, func, entry, then_b, else_b, join = _diamond(_func())
    _alloc(entry)
    _wire_diamond(entry, then_b, else_b, join)
    join.add(Ret())
    _expect(module, "FLIRV-A4", "is still live at this Return (leaked)")


def test_free_on_both_branches_is_clean():
    module, func, entry, then_b, else_b, join = _diamond(_func())
    _alloc(entry)
    _free(then_b)
    _free(else_b)
    _wire_diamond(entry, then_b, else_b, join)
    join.add(Ret())
    _expect_clean(module)


def test_free_on_one_branch_only_is_not_reported_as_leak_conservative_meet():
    """After a join where the token is freed on only some paths its state is
    MAYBE_FREED, and FLIRV-A4 reports only definitely-LIVE tokens: the
    verifier under-reports rather than guessing (documented narrowing)."""
    module, func, entry, then_b, else_b, join = _diamond(_func())
    _alloc(entry)
    _free(then_b)
    _wire_diamond(entry, then_b, else_b, join)
    join.add(Ret())
    _expect_clean(module)


def test_token_escaped_on_only_one_branch_is_dropped_at_join():
    """Meet intersects the token sets: a token that escaped on one incoming
    path (so is no longer tracked there) is not tracked past the join, even
    though the other path still holds it LIVE and the slot alias survives.
    Keeping it (a union meet) would report a leak at the Return."""
    module, func, entry, then_b, else_b, join = _diamond(_func(params=[("holder", ptr_to("Holder"))]))
    _alloc(entry)
    _wire_diamond(entry, then_b, else_b, join)
    # The escaping branch is the second predecessor of the join, so the
    # meet has to drop a token that its first predecessor still holds.
    jmp = else_b.instructions.pop()
    holder = else_b.add(SlotLoad("holder", ptr_to("Holder")))
    else_b.add(Store(STR, holder, 0, else_b.add(SlotLoad("s", STR))))  # escape
    else_b.instructions.append(jmp)
    join.add(Ret())
    _expect_clean(module)


def test_slot_bound_to_different_tokens_on_each_branch_loses_alias_at_join():
    module, func, entry, then_b, else_b, join = _diamond(_func())
    entry.add(SlotDecl("s", STR))
    _wire_diamond(entry, then_b, else_b, join)
    for blk in (then_b, else_b):
        jmp = blk.instructions.pop()
        src = blk.add(ConstStr("x"))
        blk.add(SlotStore("s", blk.add(Call("fs_rt_str_dup", [src], STR))))
        blk.instructions.append(jmp)
    _free(join)  # which token? unknown after the join: no A-rule can fire
    join.add(Ret())
    _expect_clean(module)


# -- loops -----------------------------------------------------------------------------

def test_a1_double_free_within_a_loop_body_is_reported():
    module, func = _func()
    entry = func.new_block()
    header, body, exit_b = func.new_block(), func.new_block(), func.new_block()
    entry.add(Jmp(header.id))
    header.add(Br(header.add(ConstBool(True)), body.id, exit_b.id))
    _alloc(body)
    _free(body)
    _free(body)
    body.add(Jmp(header.id))
    exit_b.add(Ret())
    _expect(module, "FLIRV-A1", "is freed again")


def test_alloc_and_free_within_each_loop_iteration_is_clean():
    module, func = _func()
    entry = func.new_block()
    header, body, exit_b = func.new_block(), func.new_block(), func.new_block()
    entry.add(Jmp(header.id))
    header.add(Br(header.add(ConstBool(True)), body.id, exit_b.id))
    _alloc(body)
    _use(body)
    _free(body)
    body.add(Jmp(header.id))
    exit_b.add(Ret())
    _expect_clean(module)


def test_free_after_loop_that_only_uses_token_is_clean():
    module, func = _func()
    entry = func.new_block()
    header, body, exit_b = func.new_block(), func.new_block(), func.new_block()
    _alloc(entry)
    entry.add(Jmp(header.id))
    header.add(Br(header.add(ConstBool(True)), body.id, exit_b.id))
    _use(body)
    body.add(Jmp(header.id))
    _free(exit_b)
    exit_b.add(Ret())
    _expect_clean(module)


# -- ownership escapes and slot re-binding ------------------------------------------------

def test_escape_by_returning_the_token_is_not_a_leak():
    module, func = _func(return_type=STR)
    b = func.new_block()
    _alloc(b)
    b.add(Ret(b.add(SlotLoad("s", STR))))
    _expect_clean(module)


def test_escape_by_storing_into_a_field_is_not_a_leak():
    module, func = _func(params=[("holder", ptr_to("Holder"))])
    b = func.new_block()
    _alloc(b)
    b.add(Store(STR, b.add(SlotLoad("holder", ptr_to("Holder"))), 0, b.add(SlotLoad("s", STR))))
    b.add(Ret())
    # no struct Holder in the module: the store is an unchecked raw access.
    _expect_clean(module)


def test_escape_by_passing_to_non_runtime_function_is_not_a_leak():
    module, func = _func()
    sink = FLIRFunction("sink", params=[("p", STR)], return_type=VOID)
    module.add_function(sink)
    sink.new_block().add(Ret())
    b = func.new_block()
    _alloc(b)
    b.add(Call("sink", [b.add(SlotLoad("s", STR))], VOID))
    b.add(Ret())
    _expect_clean(module)


def test_escaped_token_freed_afterwards_is_not_a_double_free():
    """Once escaped, the token is no longer this function's responsibility,
    so the verifier stops tracking it (no A1 for the later free)."""
    module, func = _func()
    sink = FLIRFunction("sink", params=[("p", STR)], return_type=VOID)
    module.add_function(sink)
    sink.new_block().add(Ret())
    b = func.new_block()
    _alloc(b)
    b.add(Call("sink", [b.add(SlotLoad("s", STR))], VOID))
    _free(b)
    b.add(Ret())
    _expect_clean(module)


def test_borrow_only_runtime_call_does_not_escape_the_token():
    module, func = _func()
    b = func.new_block()
    _alloc(b)
    _use(b)  # fs_rt_str_length borrows
    b.add(Ret())
    _expect(module, "FLIRV-A4", "leaked")


def test_rebinding_slot_to_non_token_drops_alias_so_free_is_untracked():
    module, func = _func()
    b = func.new_block()
    _alloc(b)
    _free(b)
    b.add(SlotStore("s", b.add(ConstNull())))
    _free(b)  # frees whatever s now holds: not a tracked token
    b.add(Ret())
    _expect_clean(module)


def test_rebinding_slot_to_fresh_token_after_free_is_clean():
    module, func = _func()
    b = func.new_block()
    _alloc(b)
    _free(b)
    src = b.add(ConstStr("y"))
    b.add(SlotStore("s", b.add(Call("fs_rt_str_dup", [src], STR))))
    _free(b)
    b.add(Ret())
    _expect_clean(module)


# -- user-function allocations and __destroy frees ------------------------------------------

def _make_ptr_returner(module: FLIRModule, name: str = "make"):
    make = FLIRFunction(name, return_type=STR)
    module.add_function(make)
    mb = make.new_block()
    mb.add(Ret(mb.add(Call("fs_rt_alloc_zeroed", [mb.add(ConstInt("8", I64))], STR))))
    return make


def test_a4_pointer_returned_by_user_function_is_a_fresh_token_and_can_leak():
    module, func = _func()
    _make_ptr_returner(module)
    b = func.new_block()
    b.add(SlotDecl("s", STR))
    b.add(SlotStore("s", b.add(Call("make", [], STR))))
    b.add(Ret())
    _expect(module, "FLIRV-A4", "leaked")


def test_user_function_returned_pointer_freed_once_is_clean():
    module, func = _func()
    _make_ptr_returner(module)
    b = func.new_block()
    b.add(SlotDecl("s", STR))
    b.add(SlotStore("s", b.add(Call("make", [], STR))))
    _free(b)
    b.add(Ret())
    _expect_clean(module)


def test_user_function_returned_pointer_freed_twice_is_a1():
    module, func = _func()
    _make_ptr_returner(module)
    b = func.new_block()
    b.add(SlotDecl("s", STR))
    b.add(SlotStore("s", b.add(Call("make", [], STR))))
    _free(b)
    _free(b)
    b.add(Ret())
    _expect(module, "FLIRV-A1", "is freed again")


def test_user_function_returning_scalar_is_not_a_token():
    module, func = _func()
    scalar = FLIRFunction("scalar", return_type=I32)
    module.add_function(scalar)
    sb = scalar.new_block()
    sb.add(Ret(sb.add(ConstInt("1", I32))))
    b = func.new_block()
    # Bound to a named slot and never freed: if a scalar result were treated
    # as a fresh token this would be reported as a leak (FLIRV-A4).
    b.add(SlotDecl("n", I32))
    b.add(SlotStore("n", b.add(Call("scalar", [], I32))))
    b.add(Ret())
    _expect_clean(module)


def test_destroy_call_frees_token():
    module, func = _func()
    destroy = FLIRFunction("Thing__destroy", params=[("p", STR)], return_type=VOID)
    module.add_function(destroy)
    destroy.new_block().add(Ret())
    b = func.new_block()
    _alloc(b)
    b.add(Call("Thing__destroy", [b.add(SlotLoad("s", STR))], VOID))
    b.add(Ret())
    _expect_clean(module)


def test_double_destroy_call_is_a1():
    module, func = _func()
    destroy = FLIRFunction("Thing__destroy", params=[("p", STR)], return_type=VOID)
    module.add_function(destroy)
    destroy.new_block().add(Ret())
    b = func.new_block()
    _alloc(b)
    for _ in range(2):
        b.add(Call("Thing__destroy", [b.add(SlotLoad("s", STR))], VOID))
    b.add(Ret())
    _expect(module, "FLIRV-A1", "is freed again")


def test_impl_prefixed_free_is_recognized_as_freeing_call():
    module, func = _func()
    impl_free = FLIRFunction("impl_fs_rt_free", params=[("p", STR)], return_type=VOID)
    module.add_function(impl_free)
    impl_free.new_block().add(Ret())
    b = func.new_block()
    _alloc(b)
    for _ in range(2):
        b.add(Call("impl_fs_rt_free", [b.add(SlotLoad("s", STR))], VOID))
    b.add(Ret())
    _expect(module, "FLIRV-A1", "is freed again")


# -- A3: freeing something that is not a heap allocation base --------------------------------

def test_a3_free_of_stack_slot_address():
    module, func = _func()
    b = func.new_block()
    b.add(SlotDecl("local", I32))
    b.add(Call("fs_rt_free", [b.add(SlotAddr("local"))], VOID))
    b.add(Ret())
    _expect(module, "FLIRV-A3", "(slotaddr)")


def test_a3_free_of_read_only_global_value():
    module, func = _func()
    module.globals.append(("cell", STR, "0"))
    b = func.new_block()
    b.add(Call("fs_rt_free", [b.add(GlobalLoad("cell", STR))], VOID))
    b.add(Ret())
    _expect(module, "FLIRV-A3", "(gload)")


def test_a3_free_of_mutable_global_value_is_allowed():
    # A module-level variable holds a real heap pointer (an owned string
    # global being reassigned frees its old value), unlike a read-only
    # global constant.
    module, func = _func()
    module.mutable_globals.append(("cell", STR))
    b = func.new_block()
    b.add(Call("fs_rt_free", [b.add(GlobalLoad("cell", STR))], VOID))
    b.add(Ret())
    _expect_clean(module)


def test_a3_free_of_interior_pointer_from_ptradd():
    module, func = _func(params=[("p", STR)])
    b = func.new_block()
    interior = b.add(PtrAdd(b.add(SlotLoad("p", STR)), b.add(ConstInt("4", I64)), 1))
    b.add(Call("fs_rt_free", [interior], VOID))
    b.add(Ret())
    _expect(module, "FLIRV-A3", "(ptradd)")


def test_a3_destroy_of_string_literal_is_also_checked():
    module, func = _func()
    destroy = FLIRFunction("Thing__destroy", params=[("p", STR)], return_type=VOID)
    module.add_function(destroy)
    destroy.new_block().add(Ret())
    b = func.new_block()
    b.add(Call("Thing__destroy", [b.add(ConstStr("lit"))], VOID))
    b.add(Ret())
    _expect(module, "FLIRV-A3", "(strconst)")


def test_a3_free_of_a_parameter_pointer_is_not_flagged():
    """A pointer parameter is an opaque value of unknown provenance, not a
    provably non-heap one: the structural check accepts it."""
    module, func = _func(params=[("p", STR)])
    b = func.new_block()
    b.add(Call("fs_rt_free", [b.add(SlotLoad("p", STR))], VOID))
    b.add(Ret())
    _expect_clean(module)


def test_m4_store_through_slot_loaded_string_literal_alias_is_not_resolved():
    """Only the direct strconst operand (or a one-hop token alias) is
    resolved; a store into a literal-derived pointer stored to a slot via a
    non-token value is outside the M4 narrowing."""
    module, func = _func()
    b = func.new_block()
    b.add(SlotDecl("s", STR))
    b.add(SlotStore("s", b.add(ConstStr("lit"))))
    b.add(Store(I32, b.add(SlotLoad("s", STR)), 0, b.add(ConstInt("1", I32))))
    b.add(Ret())
    _expect_clean(module)


# -- A5: destructor totality -----------------------------------------------------------------

def _struct(module, name, fields, kind="class", variants=None):
    s = FLIRStruct(name, kind=kind)
    s.fields = fields
    s.size = 16
    s.align = 8
    if variants:
        s.variant_layouts = variants
    module.add_struct(s)
    return s


def _free_param(module, func, struct_name, shallow=False):
    b = func.new_block()
    call = Call("fs_rt_free", [b.add(SlotLoad("p", ptr_to(struct_name)))], VOID)
    if shallow:
        call.metadata["shallow_free"] = True
    b.add(call)
    b.add(Ret())


def test_a5_enum_with_pointer_payload_variant_requires_destructor():
    module, func = _func(params=[("p", ptr_to("Msg"))])
    _struct(module, "Msg", [("tag", I32, 0)], kind="enum", variants={"Text": [("text", STR, 8)]})
    _free_param(module, func, "Msg")
    _expect(module, "FLIRV-A5", "fs_rt_free called directly on 'Msg'")


def test_a5_enum_with_only_scalar_payloads_may_be_freed_directly():
    module, func = _func(params=[("p", ptr_to("Num"))])
    _struct(module, "Num", [("tag", I32, 0)], kind="enum", variants={"Int": [("n", I64, 8)]})
    _free_param(module, func, "Num")
    _expect_clean(module)


def test_a5_struct_without_pointer_fields_may_be_freed_directly():
    module, func = _func(params=[("p", ptr_to("Plain"))])
    _struct(module, "Plain", [("a", I32, 0), ("b", I64, 8)])
    _free_param(module, func, "Plain")
    _expect_clean(module)


def test_a5_shallow_free_metadata_exempts_struct_with_owned_fields():
    module, func = _func(params=[("p", ptr_to("Owner"))])
    _struct(module, "Owner", [("name", STR, 0)])
    _free_param(module, func, "Owner", shallow=True)
    _expect_clean(module)


def test_a5_pointee_not_a_known_struct_is_not_checked():
    module, func = _func(params=[("p", ptr_to("Unknown"))])
    _free_param(module, func, "Unknown")
    _expect_clean(module)


def test_a5_free_of_untyped_pointer_is_not_checked():
    from flir.ir import PTR

    module, func = _func(params=[("p", PTR)])
    b = func.new_block()
    b.add(Call("fs_rt_free", [b.add(SlotLoad("p", PTR))], VOID))
    b.add(Ret())
    _expect_clean(module)


def test_a5_destroy_call_is_not_subject_to_direct_free_rule():
    module, func = _func(params=[("p", ptr_to("Owner"))])
    _struct(module, "Owner", [("name", STR, 0)])
    d = FLIRFunction("Owner__destroy", params=[("p", ptr_to("Owner"))], return_type=VOID)
    module.add_function(d)
    d.new_block().add(Ret())
    b = func.new_block()
    b.add(Call("Owner__destroy", [b.add(SlotLoad("p", ptr_to("Owner")))], VOID))
    b.add(Ret())
    _expect_clean(module)
