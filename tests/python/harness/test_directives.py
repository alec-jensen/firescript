"""Self-tests for harness.directives (spec sec.11 phase 1)."""
from __future__ import annotations

from harness import pyunit as t
from harness.directives import (
    DirectiveError,
    build_argv,
    parse_fire_directives,
    parse_python_directives,
)


def test_header_directive_parses_key_value():
    text = "//@ exit-code: 2\nint32 x = 1;\n"
    d = parse_fire_directives(text)
    t.require_eq(d.value("exit-code"), "2")


def test_bare_directive_has_no_value():
    text = "//@ helper\nfunction f() {}\n"
    d = parse_fire_directives(text)
    t.require(d.has("helper"))
    t.require_eq(d.value("helper"), None)


def test_unknown_key_is_error():
    text = "//@ bogus: 1\nint32 x = 1;\n"
    try:
        parse_fire_directives(text)
        t.require(False, "expected DirectiveError")
    except DirectiveError:
        pass


def test_directive_after_code_is_error():
    text = "int32 x = 1;\n//@ exit-code: 2\n"
    try:
        parse_fire_directives(text)
        t.require(False, "expected DirectiveError for misplaced //@")
    except DirectiveError:
        pass


def test_repeating_non_repeatable_key_is_error():
    text = "//@ exit-code: 1\n//@ exit-code: 2\nint32 x = 1;\n"
    try:
        parse_fire_directives(text)
        t.require(False, "expected DirectiveError for repeated key")
    except DirectiveError:
        pass


def test_repeatable_keys_accumulate_in_order():
    text = "//@ arg: a\n//@ args: b c\n//@ arg: d\nprintln(1);\n"
    d = parse_fire_directives(text)
    t.require_eq(build_argv(d), ["a", "b", "c", "d"])


def test_python_directives_use_hash_at():
    text = "#@ timeout: 5\nimport os\n"
    d = parse_python_directives(text)
    t.require_eq(d.value("timeout"), "5")


def test_two_spaces_after_marker_is_error():
    text = "//@  exit-code: 1\nint32 x = 1;\n"
    try:
        parse_fire_directives(text)
        t.require(False, "expected DirectiveError for double space")
    except DirectiveError:
        pass
