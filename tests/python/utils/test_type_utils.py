"""Direct unit tests for firescript/utils/type_utils.py's ownership-category
registries (copyable vs owned classification used by semantic analysis and
codegen)."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

import utils.type_utils as tu  # noqa: E402


def test_is_copyable_none_base_type_is_false():
    tu.reset_registries()
    t.require(not tu.is_copyable(None, False))


def test_is_copyable_array_is_always_false():
    tu.reset_registries()
    t.require(not tu.is_copyable("int32", True))


def test_is_owned_none_base_type_is_false():
    tu.reset_registries()
    t.require(not tu.is_owned(None, False))


def test_is_user_class_none_base_type_is_false():
    tu.reset_registries()
    t.require(not tu.is_user_class(None))


def test_register_class_then_unregister_copyable_flag():
    tu.reset_registries()
    tu.register_class("Point", is_copyable=True)
    t.require(tu.is_copyable("Point", False))
    t.require(not tu.is_owned("Point", False))

    # Re-registering the same class as non-copyable must demote it out of
    # the copyable-classes set (not just fail to add it).
    tu.register_class("Point", is_copyable=False)
    t.require(not tu.is_copyable("Point", False))
    t.require(tu.is_owned("Point", False))
    tu.reset_registries()


def test_reset_registries_clears_state():
    tu.register_class("Temp", is_copyable=True)
    t.require(tu.is_user_class("Temp"))
    tu.reset_registries()
    t.require(not tu.is_user_class("Temp"))
    t.require(not tu.is_copyable("Temp", False))
