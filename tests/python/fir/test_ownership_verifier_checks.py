"""Gap-filling unit tests for firescript/fir/ownership_verifier.py (Tier 2):
the dataflow meet of binding sets that differ between predecessors,
StoreArray consumption and its borrow-parameter check (FIRV-O7),
generator identity through LoadVar (FIRV-G4), and enum-guard collection
skipping `==` branches that do not compare an ExtractTag. Built by hand with
FIRBuilder and corrupted in exactly one place."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from errors import IRVerificationError  # noqa: E402
from fir import ArrayType, FIRBuilder, FIRFunction, FIRModule, TypeDef, make_simple  # noqa: E402
from fir.ir_types import GeneratorType  # noqa: E402
from fir.ownership_verifier import OwnState, _meet_states  # noqa: E402

INT32 = make_simple("int32")
BOOL = make_simple("bool")


def _rules(module: FIRModule) -> list[str]:
    try:
        module.validate()
    except IRVerificationError as e:
        return [v.rule_id for v in e.violations]
    return []


def _point_module():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Point", "owned", fields=[("x", INT32)]))
    return module, make_simple("Point")


# -- _meet_states -----------------------------------------------------------

def test_meet_states_keeps_binding_present_in_only_a_later_state():
    merged = _meet_states([{"a": OwnState.OWNED}, {"a": OwnState.OWNED, "b": OwnState.MOVED}])
    t.require_eq(merged["a"], OwnState.OWNED)
    t.require_eq(merged["b"], OwnState.MOVED)


def test_meet_states_disagreeing_owned_and_moved_becomes_maybe_moved():
    merged = _meet_states([{"a": OwnState.OWNED}, {"a": OwnState.MOVED}])
    t.require_eq(merged["a"], OwnState.MAYBE_MOVED)


# -- StoreArray: consumes the stored value; O7 on a borrow parameter --------

def test_o7_borrow_param_stored_into_array_is_flagged():
    module, point_t = _point_module()
    arr_t = ArrayType(point_t)
    func = FIRFunction("f", params=[("p", point_t), ("a", arr_t)],
                       param_modes=["borrow", "borrow_mut"], return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    b.store_array(func.param_value("a"), b.int_literal("0", INT32), func.param_value("p"))
    b.ret()
    t.require("FIRV-O7" in _rules(module), "storing a borrow param into an array consumes it")


def test_store_array_of_owned_param_into_array_consumes_it_once():
    module, point_t = _point_module()
    arr_t = ArrayType(point_t)
    func = FIRFunction("f", params=[("p", point_t), ("a", arr_t)],
                       param_modes=["own", "borrow_mut"], return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    b.store_array(func.param_value("a"), b.int_literal("0", INT32), func.param_value("p"))
    b.ret()
    rules = _rules(module)
    t.require("FIRV-O7" not in rules and "FIRV-O3" not in rules, rules)


def test_store_array_twice_with_same_owned_value_is_use_after_move():
    module, point_t = _point_module()
    arr_t = ArrayType(point_t)
    func = FIRFunction("f", params=[("p", point_t), ("a", arr_t)],
                       param_modes=["own", "borrow_mut"], return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    p, a = func.param_value("p"), func.param_value("a")
    b.store_array(a, b.int_literal("0", INT32), p)
    b.store_array(a, b.int_literal("1", INT32), p)
    b.ret()
    t.require("FIRV-O1" in _rules(module), "second store of a moved value must be O1")


# -- FIRV-G4 with the generator held in a local -----------------------------

def _gen_local_module(with_next: bool):
    module = FIRModule("firescript")
    gen_t = GeneratorType(INT32)
    gen = FIRFunction("g", return_type=gen_t, is_generator=True)
    module.add_function(gen)
    gb = FIRBuilder(gen)
    gb.yield_value(gb.int_literal("1", INT32))
    gb.ret()

    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    b.declare_local("it", gen_t, b.gen_new("g", [], gen_t))
    if with_next:
        b.gen_next(b.load_var("it", gen_t), BOOL)
    value = b.gen_value(b.load_var("it", gen_t), INT32)
    b.ret(value)
    return module


def test_g4_gen_value_dominated_by_gen_next_on_same_local():
    t.require("FIRV-G4" not in _rules(_gen_local_module(True)), "same local generator: dominated")


def test_g4_gen_value_on_local_without_gen_next():
    t.require("FIRV-G4" in _rules(_gen_local_module(False)), "no GenNext on the local generator")


# -- enum guard collection ignores non-tag equality branches ----------------

def test_e1_equality_branch_without_extract_tag_is_not_a_guard():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    cond = b.binary_op("==", b.int_literal("1", INT32), b.int_literal("2", INT32), BOOL)
    then_b, else_b = b.new_block(), b.new_block()
    b.branch(cond, then_b.id, else_b.id)
    b.position_at(then_b)
    b.ret()
    b.position_at(else_b)
    b.ret()
    t.require_eq(_rules(module), [])
