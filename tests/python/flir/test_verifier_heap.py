"""Unit tests for the FLIR Tier-2 heap rules that test_heap_verifier_checks.py
does not cover: A3 (free of a string literal), A5 (free of a struct with
owned fields, and the destructor's own-allocation exemption) and M4 (store
into read-only data). The A1/A2/A4 lifecycle rules live in
test_heap_verifier_checks.py."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from errors import IRVerificationError  # noqa: E402
from flir.ir import (  # noqa: E402
    Call,
    ConstInt,
    ConstStr,
    FLIRFunction,
    FLIRModule,
    FLIRStruct,
    I32,
    Load,
    Ret,
    SlotLoad,
    Store,
    VOID,
    ptr_to,
)


def _expect_rule(module: FLIRModule, rule_id: str) -> None:
    try:
        module.validate()
        t.require(False, f"no error raised (expected {rule_id})")
    except IRVerificationError as e:
        t.require(any(v.rule_id == rule_id for v in e.violations), f"{rule_id} not in: {e}")


def test_a3_free_invalid_provenance():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    lit = entry.add(ConstStr("literal"))
    entry.add(Call("fs_rt_free", [lit], VOID))  # freeing read-only data
    entry.instructions.append(Ret())
    _expect_rule(module, "FLIRV-A3")


def test_a5_free_on_struct_with_owned_fields():
    module = FLIRModule("firescript")
    struct = FLIRStruct("Box", kind="class")
    struct.fields = [("label", ptr_to("i8"), 0)]
    struct.size = 8
    struct.align = 8
    module.add_struct(struct)

    func = FLIRFunction("f", params=[("b", ptr_to("Box"))], return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    b = entry.add(SlotLoad("b", ptr_to("Box")))
    entry.add(Call("fs_rt_free", [b], VOID))  # should call Box__destroy instead
    entry.instructions.append(Ret())
    _expect_rule(module, "FLIRV-A5")


def test_a5_allows_destructor_freeing_its_own_struct():
    """<S>__destroy legitimately fs_rt_free's its own backing allocation as
    its terminal step, after recursively freeing owned fields earlier."""
    module = FLIRModule("firescript")
    struct = FLIRStruct("Box", kind="class")
    struct.fields = [("label", ptr_to("i8"), 0)]
    struct.size = 8
    struct.align = 8
    module.add_struct(struct)

    destroy = FLIRFunction("Box__destroy", params=[("self", ptr_to("Box"))], return_type=VOID)
    module.add_function(destroy)
    entry = destroy.new_block()
    self_val = entry.add(SlotLoad("self", ptr_to("Box")))
    label_val = entry.add(Load(ptr_to("i8"), self_val, 0))
    entry.add(Call("fs_rt_free", [label_val], VOID))
    self_val2 = entry.add(SlotLoad("self", ptr_to("Box")))
    entry.add(Call("fs_rt_free", [self_val2], VOID))
    entry.instructions.append(Ret())
    module.validate()  # must not raise


def test_m4_store_to_readonly_data():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    lit = entry.add(ConstStr("literal"))
    value = entry.add(ConstInt("1", I32))
    entry.add(Store(I32, lit, 0, value))  # storing into read-only data
    entry.instructions.append(Ret())
    _expect_rule(module, "FLIRV-M4")
