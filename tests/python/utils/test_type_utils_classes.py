"""Direct unit tests for firescript/utils/type_utils.py: primitive and
user-class ownership classification (is_copyable / is_owned / is_user_class)."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

import utils.type_utils as tu  # noqa: E402

_PRIMITIVES = [
    "int8", "int16", "int32", "int64", "uint8", "uint16", "uint32", "uint64",
    "float32", "float64", "float128", "bool", "char",
]


@t.params(_PRIMITIVES)
def test_primitives_are_copyable_and_not_owned(name):
    tu.reset_registries()
    t.require(tu.is_copyable(name, False))
    t.require(not tu.is_owned(name, False))
    t.require(not tu.is_user_class(name))


@t.params(_PRIMITIVES + ["string", "Foo"])
def test_arrays_are_owned_not_copyable(name):
    tu.reset_registries()
    t.require(tu.is_owned(name, True))
    t.require(not tu.is_copyable(name, True))


def test_string_is_owned_not_copyable():
    tu.reset_registries()
    t.require(tu.is_owned("string", False))
    t.require(not tu.is_copyable("string", False))


def test_unregistered_name_is_neither_copyable_nor_owned():
    tu.reset_registries()
    t.require(not tu.is_copyable("Mystery", False))
    t.require(not tu.is_owned("Mystery", False))


def test_plain_user_class_is_owned():
    tu.reset_registries()
    tu.register_class("Foo")
    t.require(tu.is_user_class("Foo"))
    t.require(tu.is_owned("Foo", False))
    t.require(not tu.is_copyable("Foo", False))
    tu.reset_registries()


def test_copyable_user_class_is_copyable_not_owned():
    tu.reset_registries()
    tu.register_class("Pt", is_copyable=True)
    t.require(tu.is_user_class("Pt"))
    t.require(tu.is_copyable("Pt", False))
    t.require(not tu.is_owned("Pt", False))
    tu.reset_registries()


def test_is_user_class_empty_string_is_false():
    tu.reset_registries()
    t.require(not tu.is_user_class(""))
