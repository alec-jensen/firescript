"""Self-tests for harness.discovery selector matching (spec sec.6.2,
sec.11 phase 1)."""
from __future__ import annotations

from harness import pyunit as t
from harness.discovery import apply_selectors
from harness.model import TestCase, TestId


def _case(kind, path, name, cell="default"):
    return TestCase(id=TestId(kind=kind, path=path, name=name, cell=cell))


def test_exact_path_selector():
    cases = [
        _case("run", "tests/sources/arrays/foo.fire", "foo"),
        _case("run", "tests/sources/arrays/bar.fire", "bar"),
    ]
    result = apply_selectors(cases, ["tests/sources/arrays/foo.fire"])
    t.require_eq([c.id.name for c in result], ["foo"])


def test_kind_selector():
    cases = [
        _case("run", "tests/sources/arrays/foo.fire", "foo"),
        _case("compile-fail", "tests/sources/invalid/arrays/bad.fire", "bad"),
    ]
    result = apply_selectors(cases, ["kind:compile-fail"])
    t.require_eq([c.id.name for c in result], ["bad"])


def test_name_glob_selector():
    cases = [
        _case("run", "tests/sources/generics/generics_basic.fire", "generics_basic"),
        _case("run", "tests/sources/arrays/arrays_basics.fire", "arrays_basics"),
    ]
    result = apply_selectors(cases, ["name:generics_*"])
    t.require_eq([c.id.name for c in result], ["generics_basic"])


def test_category_shorthand_selector():
    cases = [
        _case("run", "tests/sources/arrays/foo.fire", "foo"),
        _case("run", "tests/sources/classes/bar.fire", "bar"),
    ]
    result = apply_selectors(cases, ["arrays"])
    t.require_eq([c.id.name for c in result], ["foo"])


def test_python_func_selector():
    cases = [
        _case("python", "tests/python/cli/test_emit.py", "test_emit_ast"),
        _case("python", "tests/python/cli/test_emit.py", "test_emit_asm"),
    ]
    result = apply_selectors(cases, ["tests/python/cli/test_emit.py::test_emit_ast"])
    t.require_eq([c.id.name for c in result], ["test_emit_ast"])


def test_no_selectors_returns_all():
    cases = [_case("run", "tests/sources/arrays/foo.fire", "foo")]
    t.require_eq(apply_selectors(cases, []), cases)


def test_or_combined_selectors():
    cases = [
        _case("run", "tests/sources/arrays/foo.fire", "foo"),
        _case("run", "tests/sources/classes/bar.fire", "bar"),
        _case("run", "tests/sources/enums/baz.fire", "baz"),
    ]
    result = apply_selectors(cases, ["arrays", "classes"])
    t.require_eq(sorted(c.id.name for c in result), ["bar", "foo"])
