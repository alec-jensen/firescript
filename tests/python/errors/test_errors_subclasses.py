"""Direct unit tests for firescript/errors.py: caret/location rendering in
CompileTimeError.to_log_string, concrete subclass metadata, and
IRVerificationError message assembly."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

import errors  # noqa: E402


class _Violation:
    def __init__(self, rule_id: str, text: str):
        self.rule_id = rule_id
        self._text = text

    def format(self) -> str:
        return self._text


def test_to_log_string_with_location_renders_caret_and_position():
    err = errors.UnexpectedTokenError(
        source_file="a.fire", line=3, column=4, snippet="let x = ;   \n",
        expected="expression", actual="';'")
    t.require_eq(
        err.to_log_string(),
        "Expected expression but got ';'\n> let x = ;\n     ^\n(a.fire:3:4)",
    )
    t.require_eq(str(err), err.to_log_string())


def test_to_log_string_omits_location_when_line_is_zero():
    err = errors.ParserError(source_file="a.fire", line=0, column=1, snippet="x", message="boom")
    t.require_eq(err.to_log_string(), "boom")


def test_to_log_string_omits_location_without_source_file():
    err = errors.ParserError(line=2, column=1, snippet="x", message="boom")
    t.require_eq(err.to_log_string(), "boom")


def test_to_log_string_empty_snippet_still_renders_location():
    err = errors.ParserError(source_file="a.fire", line=1, column=0, snippet="", message="boom")
    t.require_eq(err.to_log_string(), "boom\n> \n ^\n(a.fire:1:0)")


@t.params([
    (errors.ParserError, "FS-PARSE-0001", errors.ErrorCategory.PARSER),
    (errors.SemanticError, "FS-SEM-0001", errors.ErrorCategory.SEMANTIC),
    (errors.TypeError, "FS-SEM-0002", errors.ErrorCategory.SEMANTIC),
    (errors.CodegenError, "FS-CGEN-0001", errors.ErrorCategory.CODEGEN),
    (errors.ImportNotFoundError, "FS-IMP-0001", errors.ErrorCategory.IMPORT),
    (errors.CyclicImportError, "FS-IMP-0002", errors.ErrorCategory.IMPORT),
])
def test_subclass_code_and_category(case):
    cls, code, category = case
    t.require_eq(cls.code, code)
    t.require_eq(cls.category, category)


def test_subclass_message_templates_render_context():
    t.require_eq(errors.UndefinedIdentifierError(identifier="q").message, "Variable 'q' not defined")
    t.require_eq(errors.ImportNotFoundError(module="m.x").message, "Module not found: m.x")
    t.require_eq(errors.CyclicImportError(cycle="a -> b -> a").message,
                 "Cyclic import detected: a -> b -> a")
    t.require_eq(errors.TypeError(detail="bad types").message, "bad types")


def test_error_codes_are_unique():
    seen: dict[str, str] = {}
    for name in dir(errors):
        obj = getattr(errors, name)
        if isinstance(obj, type) and issubclass(obj, errors.CompileTimeError) \
                and obj is not errors.CompileTimeError:
            t.require(obj.code not in seen, f"{obj.code} used by {seen.get(obj.code)} and {name}")
            seen[obj.code] = name


def test_ir_verification_error_message_with_violations_and_dump():
    vs = [_Violation("FIR-001", "violation one"), _Violation("FIR-002", "violation two")]
    err = errors.IRVerificationError("FIR", vs, function_dump="fn main() {}")
    t.require_eq(err.ir_level, "FIR")
    t.require_eq(err.violations, vs)
    t.require_eq(err.function_dump, "fn main() {}")
    msg = str(err)
    t.require(msg.startswith("internal compiler error: FIR verification failed (FIR-001): 2 violation(s)"), msg)
    t.require("violation one\nviolation two" in msg, msg)
    t.require(msg.endswith("-- first offending function --\nfn main() {}"), msg)
    t.require(not isinstance(err, errors.CompileTimeError))


def test_ir_verification_error_without_violations_or_dump():
    err = errors.IRVerificationError("FLIR", [])
    msg = str(err)
    t.require("(?): 0 violation(s)" in msg, msg)
    t.require("first offending function" not in msg, msg)
