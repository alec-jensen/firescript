"""Unit tests for fir.ownership.OwnershipMap."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from fir.ownership import OwnershipMap, OwnershipState  # noqa: E402


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

