"""Unit tests for fir.ownership.OwnershipMap."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from fir.ownership import OwnershipMap, OwnershipState  # noqa: E402


def test_declare_sets_valid():
    m = OwnershipMap()
    m.declare("x")
    t.require_eq(m.state_of("x"), OwnershipState.VALID)
    t.require(m.is_valid("x"))


def test_state_of_unknown_binding_is_none():
    m = OwnershipMap()
    t.require(m.state_of("nope") is None)
    t.require(not m.is_valid("nope"))


def test_record_move_without_value():
    m = OwnershipMap()
    m.declare("x")
    m.record_move("x")
    t.require_eq(m.state_of("x"), OwnershipState.MOVED)
    t.require(not m.is_valid("x"))
    t.require_eq(len(m.move_invalidations), 0)


def test_record_move_with_value_tracks_invalidation():
    m = OwnershipMap()
    m.declare("x")
    move_value = object()
    m.record_move("x", move_value)
    t.require_eq(m.state_of("x"), OwnershipState.MOVED)
    t.require_eq(m.move_invalidations[move_value], "x")


def test_record_maybe_move():
    m = OwnershipMap()
    m.declare("x")
    m.record_maybe_move("x")
    t.require_eq(m.state_of("x"), OwnershipState.MAYBE_MOVED)


def test_record_and_release_borrow():
    m = OwnershipMap()
    m.declare("x")
    m.record_borrow("x", "bb0", "bb1")
    t.require_eq(m.state_of("x"), OwnershipState.BORROWED)
    t.require_eq(m.borrow_lifetimes["x"], ("bb0", "bb1"))

    m.release_borrow("x")
    t.require_eq(m.state_of("x"), OwnershipState.VALID)
    t.require("x" not in m.borrow_lifetimes)


def test_release_borrow_on_non_borrowed_binding_is_noop_for_state():
    m = OwnershipMap()
    m.declare("x")
    m.record_move("x")
    m.release_borrow("x")
    # release_borrow only resets state to VALID when currently BORROWED
    t.require_eq(m.state_of("x"), OwnershipState.MOVED)


def test_release_borrow_clears_stale_lifetime_entry():
    m = OwnershipMap()
    m.declare("x")
    m.record_borrow("x", "bb0", "bb1")
    m.binding_states["x"] = OwnershipState.MOVED
    m.release_borrow("x")
    t.require("x" not in m.borrow_lifetimes)
