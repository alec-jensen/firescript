"""Additional unit tests for firescript/flir/verifier.py filling gaps left by
test_verifier_structure.py / test_verifier_types.py / test_verifier_checks.py:
S1 cases (a function with no blocks, an empty block), S2 duplicate mutable
globals and struct fields naming an unresolved struct, T1 operand provenance
(foreign / non-dominating), SlotAddr acceptance, and the M1 base/value
checks (non-pointer bases, unresolved base types)."""
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
    FLIRFunction,
    FLIRModule,
    FLIRStruct,
    I32,
    Jmp,
    Load,
    Ret,
    SlotAddr,
    SlotDecl,
    SlotLoad,
    Store,
    VOID,
    ptr_to,
    struct_type,
)


def _expect_rule(module: FLIRModule, rule_id: str) -> None:
    try:
        module.validate()
        t.require(False, f"no error raised (expected {rule_id})")
    except IRVerificationError as e:
        t.require(any(v.rule_id == rule_id for v in e.violations), f"{rule_id} not in: {e}")


def _simple_module() -> tuple[FLIRModule, FLIRFunction]:
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=I32)
    module.add_function(func)
    return module, func


# ---------------------------------------------------------------------------
# S1: function with no blocks at all; a block with no instructions.
# ---------------------------------------------------------------------------

def test_s1_function_with_no_blocks():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=VOID)  # never call new_block()
    module.add_function(func)
    _expect_rule(module, "FLIRV-S1")


def test_s1_empty_block_is_the_only_violation():
    # The empty block is reachable (a jmp target), so the only thing wrong
    # with the function is that the block has no terminator.
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    empty = func.new_block()
    entry.instructions.append(Jmp(empty.id))
    try:
        module.validate()
        t.require(False, "no error raised")
    except IRVerificationError as e:
        found = [(v.rule_id, v.message) for v in e.violations]
        t.require(
            found == [("FLIRV-S1", f"block '{empty.id}' is empty (no terminator)")],
            str(found),
        )


# ---------------------------------------------------------------------------
# S2: duplicate mutable global, field referencing an unresolved struct.
# ---------------------------------------------------------------------------


def test_s2_duplicate_mutable_global_name():
    module = FLIRModule("firescript")
    module.mutable_globals.append(("g", I32))
    module.mutable_globals.append(("g", I32))
    func = FLIRFunction("f", return_type=VOID)
    func.new_block().instructions.append(Ret())
    module.add_function(func)
    _expect_rule(module, "FLIRV-S2")


def test_s2_field_references_unresolved_struct():
    module = FLIRModule("firescript")
    struct = FLIRStruct("Bad", kind="class")
    struct.fields = [("f", struct_type("DoesNotExist"), 0)]
    struct.size = 8
    struct.align = 8
    module.add_struct(struct)
    func = FLIRFunction("f", return_type=VOID)
    func.new_block().instructions.append(Ret())
    module.add_function(func)
    _expect_rule(module, "FLIRV-S2")


# ---------------------------------------------------------------------------
# T1: operand from a foreign function; operand that doesn't dominate its use.
# ---------------------------------------------------------------------------

def test_t1_operand_foreign_to_function_and_dump_fallback():
    module = FLIRModule("firescript")
    func_a = FLIRFunction("a", return_type=I32)
    module.add_function(func_a)
    block_a = func_a.new_block()
    foreign = block_a.add(ConstInt("1", I32))
    block_a.instructions.append(Ret(foreign))

    func_b = FLIRFunction("b", return_type=I32)
    module.add_function(func_b)
    block_b = func_b.new_block()
    block_b.instructions.append(Ret(foreign))  # value produced in func_a

    # This also exercises _format_first_offender's except-branch: dumping
    # func_b for the error report fails (dump_flir_module itself raises,
    # since `foreign` doesn't belong to func_b either), which must be
    # caught rather than propagate out of verify_flir_module.
    try:
        module.validate()
        t.require(False, "no error raised")
    except IRVerificationError as e:
        t.require(any(v.rule_id == "FLIRV-T1" for v in e.violations), e.violations)


def test_t1_operand_does_not_dominate_use():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=I32)
    module.add_function(func)
    entry = func.new_block()
    then_block = func.new_block()
    else_block = func.new_block()
    cond = entry.add(ConstBool(True))
    entry.instructions.append(Br(cond, then_block.id, else_block.id))
    # Defined only in then_block, used in else_block -- else_block isn't
    # dominated by then_block's definition.
    one = then_block.add(ConstInt("1", I32))
    then_block.instructions.append(Ret(one))
    else_block.instructions.append(Ret(one))
    _expect_rule(module, "FLIRV-T1")


# ---------------------------------------------------------------------------
# T5: slotaddr of a declared slot is accepted.
# ---------------------------------------------------------------------------


def test_slotaddr_accepts_declared_slot():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=I32)
    module.add_function(func)
    entry = func.new_block()
    entry.add(SlotDecl("x", I32))
    addr = entry.add(SlotAddr("x"))
    loaded = entry.add(Load(I32, addr, 0))
    entry.instructions.append(Ret(loaded))
    module.validate()  # must not raise


# ---------------------------------------------------------------------------
# M1: load/store base is not a pointer; value-type and unresolved-base cases.
# ---------------------------------------------------------------------------

def test_m1_load_base_non_pointer():
    module, func = _simple_module()
    entry = func.new_block()
    a = entry.add(ConstInt("1", I32))
    bad = entry.add(Load(I32, a, 0))  # base is i32, not a pointer
    entry.instructions.append(Ret(bad))
    _expect_rule(module, "FLIRV-M1")


def test_m1_store_base_non_pointer():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    a = entry.add(ConstInt("1", I32))
    v = entry.add(ConstInt("2", I32))
    entry.add(Store(I32, a, 0, v))  # base is i32, not a pointer
    entry.instructions.append(Ret())
    _expect_rule(module, "FLIRV-M1")


def test_store_value_type_mismatch():
    module = FLIRModule("firescript")
    struct = FLIRStruct("Point", kind="class")
    struct.fields = [("x", I32, 0)]
    struct.size = 4
    struct.align = 4
    module.add_struct(struct)
    func = FLIRFunction("f", params=[("p", ptr_to("Point"))], return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    p = entry.add(SlotLoad("p", ptr_to("Point")))
    b = entry.add(ConstBool(True))
    entry.add(Store(I32, p, 0, b))  # declared value_type i32, actual operand is bool
    entry.instructions.append(Ret())
    _expect_rule(module, "FLIRV-T1")


def test_load_skips_further_checks_when_base_type_unresolved():
    module = FLIRModule("firescript")
    callee = FLIRFunction("callee", return_type=VOID)
    callee.new_block().instructions.append(Ret())
    module.add_function(callee)
    func = FLIRFunction("f", return_type=I32)
    module.add_function(func)
    entry = func.new_block()
    call_inst = Call("callee", [], VOID)  # already flags its own FLIRV-T1
    entry.instructions.append(call_inst)
    void_val = call_inst.result()
    bad = entry.add(Load(I32, void_val, 0))  # base type unresolved: must not crash further
    entry.instructions.append(Ret(bad))
    try:
        module.validate()
        t.require(False, "no error raised")
    except IRVerificationError as e:
        # Just the void-operand FLIRV-T1 (twice: once for Load's own use of
        # void_val, once for Ret's use of Load's result) -- no FLIRV-M1
        # about a non-pointer base, since _check_load bails out early.
        t.require(any(v.rule_id == "FLIRV-T1" for v in e.violations), e.violations)
        t.require(not any(v.rule_id == "FLIRV-M1" for v in e.violations), e.violations)


def test_store_skips_further_checks_when_base_type_unresolved():
    module = FLIRModule("firescript")
    callee = FLIRFunction("callee", return_type=VOID)
    callee.new_block().instructions.append(Ret())
    module.add_function(callee)
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    call_inst = Call("callee", [], VOID)
    entry.instructions.append(call_inst)
    void_val = call_inst.result()
    v = entry.add(ConstInt("1", I32))
    entry.add(Store(I32, void_val, 0, v))  # base type unresolved: must not crash further
    entry.instructions.append(Ret())
    try:
        module.validate()
        t.require(False, "no error raised")
    except IRVerificationError as e:
        t.require(any(v.rule_id == "FLIRV-T1" for v in e.violations), e.violations)
        t.require(not any(v.rule_id == "FLIRV-M1" for v in e.violations), e.violations)


