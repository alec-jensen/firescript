"""Self-tests for harness.expectations (spec sec.11 phase 1)."""
from __future__ import annotations

from harness import pyunit as t
from harness.directives import DirectiveError
from harness.expectations import (
    ActualDiagnostic,
    match_diagnostics,
    normalize_output,
    parse_diagnostic_annotations,
    parse_expect,
    update_diagnostic_annotations,
    update_expect,
)


def test_normalize_strips_trailing_ws_and_crlf():
    t.require_eq(normalize_output("a \r\nb\r\n"), "a\nb\n")


def test_parse_block_form_expect():
    text = "println(1);\n\n/* EXPECT\n42\ndone\n*/\n"
    block = parse_expect(text)
    t.require_eq(block.content_norm, "42\ndone\n")
    t.require_eq(block.form, "block")


def test_parse_line_form_expect():
    text = "println(1);\n\n// EXPECT: 42\n// EXPECT: done\n"
    block = parse_expect(text)
    t.require_eq(block.content_norm, "42\ndone\n")
    t.require_eq(block.form, "line")


def test_no_expect_block_returns_none():
    t.require(parse_expect("println(1);\n") is None)


def test_duplicate_block_is_error():
    text = "/* EXPECT\na\n*/\n\n/* EXPECT\nb\n*/\n"
    try:
        parse_expect(text)
        t.require(False, "expected DirectiveError for duplicate block")
    except DirectiveError:
        pass


def test_update_appends_block_when_missing():
    new_text = update_expect("println(1);\n", "42\n")
    block = parse_expect(new_text)
    t.require_eq(block.content_norm, "42\n")


def test_update_replaces_existing_block_in_place():
    text = "code();\n\n/* EXPECT\nold\n*/\n"
    new_text = update_expect(text, "new\n")
    block = parse_expect(new_text)
    t.require_eq(block.content_norm, "new\n")
    t.require(new_text.startswith("code();\n"))


def test_update_uses_line_form_when_content_has_close_marker():
    new_text = update_expect("println(1);\n", "*/\nok\n")
    block = parse_expect(new_text)
    t.require_eq(block.form, "line")
    t.require_eq(block.content_norm, "*/\nok\n")


def test_diagnostic_annotation_caret_anchoring():
    src = (
        'x: int32 = "hello";        //~ ERROR FS-TYPE-0001\n'
        's: string = y;             //~ ERROR FS-NAME-0002 @7\n'
        '                          //~^ ERROR FS-TYPE-0004\n'
    )
    annos = parse_diagnostic_annotations(src)
    t.require_eq(len(annos), 3)
    t.require_eq(annos[2].target_line, 2)
    t.require_eq(annos[1].column, 7)


def test_match_diagnostics_exact():
    annos = parse_diagnostic_annotations('x;  //~ ERROR FS-TYPE-0001 @3\n')
    actuals = [ActualDiagnostic("ERROR", "FS-TYPE-0001", 1, 3)]
    missing, extra = match_diagnostics(annos, actuals)
    t.require_eq(missing, [])
    t.require_eq(extra, [])


def test_match_diagnostics_reports_missing_and_extra():
    annos = parse_diagnostic_annotations('x;  //~ ERROR FS-TYPE-0001 @3\n')
    actuals = [ActualDiagnostic("ERROR", "FS-TYPE-9999", 1, 3)]
    missing, extra = match_diagnostics(annos, actuals)
    t.require_eq(len(missing), 1)
    t.require_eq(len(extra), 1)


def test_update_diagnostic_annotations_round_trips():
    src = 'x: int32 = "hello";\ns: string = y;\n'
    actuals = [
        ActualDiagnostic("ERROR", "FS-TYPE-0001", 1, 11),
        ActualDiagnostic("ERROR", "FS-NAME-0002", 2, 12),
        ActualDiagnostic("ERROR", "FS-TYPE-0004", 2, 5),
    ]
    new_text = update_diagnostic_annotations(src, actuals)
    annos = parse_diagnostic_annotations(new_text)
    missing, extra = match_diagnostics(annos, actuals)
    t.require_eq(missing, [])
    t.require_eq(extra, [])


def test_update_diagnostic_annotations_drops_stale():
    src = 'x;  //~ ERROR FS-TYPE-0001 @3\n'
    new_text = update_diagnostic_annotations(src, [])
    t.require("//~" not in new_text)
