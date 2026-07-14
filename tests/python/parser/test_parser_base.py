"""Direct unit tests for firescript/parser/base.py helpers: error-reporting
wrappers, comment-anchored diagnostic positions, and literal-suffix
inference. These are exercised through crafted invalid .fire programs
elsewhere, but several branches (comment-boundary scanning at EOF,
rarely-triggered error helper wrappers, literal suffix edge cases) are far
easier and more precise to hit by constructing a Parser directly."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from lexer import Lexer, Token  # noqa: E402
from parser import Parser  # noqa: E402
from parser.base import ParserBase  # noqa: E402
from enums import NodeTypes  # noqa: E402
from errors import CompileTimeError, ParserError  # noqa: E402


def _parser_for(src: str) -> Parser:
    tokens = Lexer(src).tokenize()
    return Parser(tokens, src, "test.fire")


def test_field_not_found_error_records_error():
    p = _parser_for("int32 x = 1;")
    p.field_not_found_error("Point", "z", p.tokens[0])
    t.require_eq(len(p.errors), 1)
    t.require("z" in str(p.errors[0]) or "Point" in str(p.errors[0]))


def test_method_not_found_error_records_error():
    p = _parser_for("int32 x = 1;")
    p.method_not_found_error("Point", "distanceTo", p.tokens[0])
    t.require_eq(len(p.errors), 1)


def test_constructor_not_found_error_records_error():
    p = _parser_for("int32 x = 1;")
    p.constructor_not_found_error("Point", p.tokens[0])
    t.require_eq(len(p.errors), 1)


def test_invalid_operator_error_records_error():
    p = _parser_for("int32 x = 1;")
    p.invalid_operator_error("+", "Point", p.tokens[0])
    t.require_eq(len(p.errors), 1)


def test_control_flow_error_records_error():
    p = _parser_for("int32 x = 1;")
    p.control_flow_error("break", p.tokens[0])
    t.require_eq(len(p.errors), 1)


def test_invalid_super_error_records_error():
    p = _parser_for("int32 x = 1;")
    p.invalid_super_error("super used outside a subclass", p.tokens[0])
    t.require_eq(len(p.errors), 1)


def test_undefined_identifier_error_records_error():
    p = _parser_for("int32 x = 1;")
    p.undefined_identifier_error("y", p.tokens[0])
    t.require_eq(len(p.errors), 1)


def test_missing_identifier_error_records_error():
    p = _parser_for("int32 x = 1;")
    p.missing_identifier_error(p.tokens[0])
    t.require_eq(len(p.errors), 1)


def test_invalid_array_access_error_records_error():
    p = _parser_for("int32 x = 1;")
    p.invalid_array_access_error("index must be an integer", p.tokens[0])
    t.require_eq(len(p.errors), 1)


def test_report_error_with_no_token_anchors_after_last_real_token():
    # No `token` kwarg -> report_error falls back to the last non-comment
    # token in the stream via _last_non_comment_token(None).
    p = _parser_for("int32 x = 1; // trailing comment\n")
    p.report_error(__import__("errors").ParserError(message="synthetic", source_file="test.fire"))
    t.require_eq(len(p.errors), 1)
    t.require(p.errors[0].line > 0)


def test_report_error_skips_trailing_multiline_comment_block():
    src = "int32 x = 1;\n/* trailing\nblock\ncomment */"
    p = _parser_for(src)
    p.report_error(__import__("errors").ParserError(message="synthetic", source_file="test.fire"))
    # The anchored line must be the statement's line, not inside the comment block.
    t.require_eq(len(p.errors), 1)
    t.require(p.errors[0].line == 1, f"expected line 1, got {p.errors[0].line}")


def test_consume_name_accepts_as_and_owned_keywords():
    p = _parser_for("as owned regular_ident")
    tok1 = p.consume_name()
    t.require(tok1 is not None and tok1.type == "AS")
    tok2 = p.consume_name()
    t.require(tok2 is not None and tok2.type == "OWNED")
    tok3 = p.consume_name()
    t.require(tok3 is not None and tok3.type == "IDENTIFIER")


def test_infer_literal_type_integer_suffixes():
    p = _parser_for("int32 x = 1;")
    for suf, expected in (
        ("i8", "int8"), ("i16", "int16"), ("i32", "int32"), ("i64", "int64"),
        ("u8", "uint8"), ("u16", "uint16"), ("u32", "uint32"), ("u64", "uint64"),
    ):
        tok = Token("INTEGER_LITERAL", f"1{suf}", 0)
        t.require_eq(p._infer_literal_type(tok), expected, suf)


def test_infer_literal_type_integer_no_suffix_defaults_int32():
    p = _parser_for("int32 x = 1;")
    tok = Token("INTEGER_LITERAL", "42", 0)
    t.require_eq(p._infer_literal_type(tok), "int32")


def test_infer_literal_type_float_suffixes():
    p = _parser_for("int32 x = 1;")
    t.require_eq(p._infer_literal_type(Token("FLOAT_LITERAL", "1.0f128", 0)), "float128")
    t.require_eq(p._infer_literal_type(Token("FLOAT_LITERAL", "1.0f64", 0)), "float64")
    t.require_eq(p._infer_literal_type(Token("FLOAT_LITERAL", "1.0f32", 0)), "float32")
    t.require_eq(p._infer_literal_type(Token("FLOAT_LITERAL", "1.0f", 0)), "float32")


def test_infer_literal_type_float_no_suffix_defaults_float32():
    p = _parser_for("int32 x = 1;")
    tok = Token("FLOAT_LITERAL", "1.0", 0)
    t.require_eq(p._infer_literal_type(tok), "float32")


def test_infer_literal_type_double_literal_is_float64():
    p = _parser_for("int32 x = 1;")
    tok = Token("DOUBLE_LITERAL", "1.0", 0)
    t.require_eq(p._infer_literal_type(tok), "float64")


def test_infer_literal_type_unknown_token_type_returns_empty():
    p = _parser_for("int32 x = 1;")
    tok = Token("STRING_LITERAL", "hi", 0)
    t.require_eq(p._infer_literal_type(tok), "")


def test_is_type_token_recognizes_registered_user_type():
    p = _parser_for("Foo x = y;")
    p.user_types.add("Foo")
    t.require(p._is_type_token(p.tokens[0]))


def test_is_type_token_none_returns_false():
    p = _parser_for("int32 x = 1;")
    t.require(not p._is_type_token(None))


def test_advance_at_eof_is_noop():
    p = _parser_for("int32")
    p.advance()  # consumes "int32", current_token becomes None
    t.require(p.current_token is None)
    p.advance()  # must not raise when already at EOF
    t.require(p.current_token is None)


def test_peek_returns_none_at_eof():
    p = _parser_for("int32")
    p.advance()
    t.require(p.peek() is None)


def test_current_token_index_is_minus_one_at_eof():
    p = _parser_for("int32")
    p.advance()
    t.require_eq(p._current_token_index(), -1)


def test_consume_name_returns_none_at_eof():
    p = _parser_for("int32")
    p.advance()
    t.require(p.consume_name() is None)


def test_expect_records_unexpected_token_error():
    p = _parser_for("int32 x = 1;")
    result = p.expect("SEMICOLON")  # current token is INT32, not SEMICOLON
    t.require(result is None)
    t.require_eq(len(p.errors), 1)


def test_expect_succeeds_and_advances():
    p = _parser_for("int32 x = 1;")
    result = p.expect("INT32")
    t.require(result is not None and result.type == "INT32")
    t.require_eq(len(p.errors), 0)
    t.require_eq(p.current_token.type, "IDENTIFIER")


def test_expect_returns_none_at_eof():
    p = _parser_for("")
    t.require(p.expect("SEMICOLON") is None)
    t.require_eq(len(p.errors), 0)


def test_looks_like_generic_var_decl_false_when_no_less_than():
    p = _parser_for("int32 x = 1;")
    t.require(not p._looks_like_generic_var_decl())


def test_looks_like_generic_var_decl_false_when_angle_brackets_unmatched():
    p = _parser_for("Foo<int32 x = 1;")
    t.require(not p._looks_like_generic_var_decl())


def test_scan_matching_gt_returns_minus_one_at_eof_without_boundary():
    # No ';'/'{'/'}' anywhere, and '<' is never closed: _scan_matching_gt
    # must fall through its while loop to the final `return -1` rather than
    # hitting the statement-boundary early-return.
    p = _parser_for("Foo<int32")
    lt_idx = next(i for i, tok in enumerate(p.tokens) if tok.type == "LESS_THAN")
    t.require_eq(p._scan_matching_gt(lt_idx), -1)


def test_skip_comment_at_eof_is_noop():
    p = _parser_for("")
    p._skip_comment()  # must not raise
    t.require(p.current_token is None)


def test_looks_like_generic_var_decl_false_when_no_assign_after_name():
    p = _parser_for("Foo<int32> x;")
    t.require(not p._looks_like_generic_var_decl())


def test_looks_like_generic_constructor_call_false_when_not_less_than():
    p = _parser_for("(x)")
    t.require(not p._looks_like_generic_constructor_call())


def test_looks_like_generic_constructor_call_false_when_no_open_paren():
    p = _parser_for("<int32> x")
    t.require(not p._looks_like_generic_constructor_call())


def test_looks_like_generic_var_decl_false_at_eof():
    p = _parser_for("")
    t.require(not p._looks_like_generic_var_decl())


def test_looks_like_generic_constructor_call_false_at_eof():
    p = _parser_for("")
    t.require(not p._looks_like_generic_constructor_call())


def test_looks_like_generic_var_decl_false_when_var_name_is_blank_placeholder():
    p = _parser_for("Foo<int32> = 1;")
    real_tokens = list(p.tokens)
    # Splice a blank-value IDENTIFIER placeholder in for the variable name
    # (the lexer never emits one; see the whitespace-placeholder tests
    # above for why this is only reachable via direct construction).
    gt_pos = next(i for i, tok in enumerate(real_tokens) if tok.type == "GREATER_THAN")
    p.tokens = [*real_tokens[:gt_pos + 1], _blank_token(99), *real_tokens[gt_pos + 1:]]
    t.require(not p._looks_like_generic_var_decl())


def test_parser_base_parse_expression_is_not_implemented():
    # Parser itself mixes in ExpressionsMixin, which overrides
    # parse_expression -- but the abstract declaration lives on ParserBase
    # for the mixins' static typing, and its body is a real
    # NotImplementedError guard for any future direct subclass that skips
    # ExpressionsMixin.
    base = ParserBase([], "", "test.fire")
    try:
        base.parse_expression()
        t.require(False, "expected NotImplementedError")
    except NotImplementedError:
        pass


def test_invalid_field_access_error_records_error():
    p = _parser_for("int32 x = 1;")
    p.invalid_field_access_error("field access on non-class type", p.tokens[0])
    t.require_eq(len(p.errors), 1)


def test_bare_error_method_records_error():
    p = _parser_for("int32 x = 1;")
    p.error("a generic parser error", p.tokens[0])
    t.require_eq(len(p.errors), 1)


def test_type_error_and_invalid_type_error_record_errors():
    p = _parser_for("int32 x = 1;")
    p.type_error("bad type", p.tokens[0])
    p.invalid_type_error("invalid type usage", p.tokens[0])
    t.require_eq(len(p.errors), 2)


def test_constructor_with_borrowed_and_owned_regular_params_parses():
    # Regular (non-receiver) constructor params can carry explicit '&'/'owned'
    # markers, but only once an explicit receiver has already been consumed
    # (a bare '&'/'owned' as the very first param is always parsed as a
    # receiver marker expecting 'this' next) -- this combination isn't
    # exercised by any full-program test since the semantic analyzer's
    # constructor-arity bookkeeping doesn't yet handle it end-to-end (see
    # spawned follow-up task), so it's checked here at the parser-output
    # level only: the parse must succeed and produce all 3 parameters.
    src = (
        "class Outer {\n"
        "    int32 total;\n"
        "    Outer(&this, &Inner a, owned Inner b) {\n"
        "        this.total = 0;\n"
        "    }\n"
        "}\n"
    )
    p = _parser_for(src)
    p.user_types.add("Inner")
    ast = p.parse()
    t.require_eq(p.errors, [])
    class_node = next(c for c in ast.children if c.node_type == NodeTypes.CLASS_DEFINITION)
    ctor = next(m for m in class_node.children if getattr(m, "is_constructor", False))
    param_names = [c.name for c in ctor.children if c.node_type == NodeTypes.PARAMETER]
    t.require_eq(param_names, ["this", "a", "b"])


# --- whitespace-placeholder-token skipping ----------------------------------
# The lexer's IDENTIFIER regex requires at least one character, so it never
# actually emits an empty-value IDENTIFIER token; advance()/peek()/
# _skip_ws_from()'s "skip whitespace placeholder tokens" branches are
# defensive scaffolding for a token stream shape the real lexer doesn't
# produce. Exercised here by splicing a synthetic empty-value IDENTIFIER
# token into the stream directly.

def _blank_token(index: int) -> Token:
    return Token("IDENTIFIER", "", index)


def test_advance_skips_whitespace_placeholder_tokens():
    p = _parser_for("int32 x = 1;")
    real_tokens = list(p.tokens)
    p.tokens = [real_tokens[0], _blank_token(5), real_tokens[1], *real_tokens[2:]]
    p._token_idx = 0
    p.current_token = p.tokens[0]
    p.advance()
    t.require_eq(p.current_token.type, "IDENTIFIER")
    t.require_eq(p.current_token.value, "x")


def test_peek_skips_whitespace_placeholder_tokens():
    p = _parser_for("int32 x = 1;")
    real_tokens = list(p.tokens)
    p.tokens = [real_tokens[0], _blank_token(5), *real_tokens[1:]]
    p._token_idx = 0
    p.current_token = p.tokens[0]
    t.require_eq(p.peek(1).value, "x")


def test_skip_ws_from_skips_placeholder_tokens():
    p = _parser_for("int32 x = 1;")
    real_tokens = list(p.tokens)
    p.tokens = [real_tokens[0], _blank_token(5), _blank_token(6), *real_tokens[1:]]
    t.require_eq(p._skip_ws_from(1), 3)


# --- _recover_to_statement_boundary ------------------------------------------
# Not called anywhere in the current parser (grep confirms no callers) -- a
# panic-mode recovery helper kept for future use. Exercised directly here so
# it doesn't silently rot; its own final "if _token_idx == start_idx" guard
# (base.py line ~520) is unreachable by construction (advance() always moves
# _token_idx forward whenever current_token was non-None on entry, and the
# guard requires current_token to be non-None too), so that one line is left
# uncovered as genuinely dead code, not chased further here.

def test_parse_statement_dot_dispatch_handles_none_from_parse_primary():
    # _parse_statement's IDENTIFIER-then-DOT branch calls parse_primary()
    # and checks for None, but parse_primary() always builds at least a
    # bare IDENTIFIER node for an IDENTIFIER token, so this guard is
    # unreachable via real input -- covered directly by monkeypatching
    # parse_primary for the duration of one call.
    p = _parser_for("a.b();")
    original = type(p).parse_primary
    type(p).parse_primary = lambda self: None
    try:
        result = p._parse_statement()
        t.require(result is None)
    finally:
        type(p).parse_primary = original


def test_parse_statement_directive_without_declarations_mixin_errors():
    # _parse_statement's DIRECTIVE branch does a getattr(self,
    # "_parse_directive", None) fallback for a parser built from
    # StatementsMixin without DeclarationsMixin (which is where
    # _parse_directive actually lives) -- the real `Parser` class always
    # has both mixed in, so this only matters for a stripped-down parser.
    from parser.statements import StatementsMixin

    class _BareStatementsParser(StatementsMixin):
        pass

    tokens = Lexer("directive enable_drops;").tokenize()
    p = _BareStatementsParser(tokens, "directive enable_drops;", "test.fire")
    result = p._parse_statement()
    t.require(result is None)
    t.require_eq(len(p.errors), 1)
    t.require("not available" in str(p.errors[0]))


def test_parse_statement_generator_without_declarations_mixin_returns_none():
    from parser.statements import StatementsMixin

    class _BareStatementsParser(StatementsMixin):
        pass

    tokens = Lexer("generator<int32> g() { }").tokenize()
    p = _BareStatementsParser(tokens, "generator<int32> g() { }", "test.fire")
    result = p._parse_statement()
    t.require(result is None)


def test_parse_scope_without_open_brace_records_error():
    # Every one of parse_scope()'s ~12 call sites across declarations.py /
    # statements.py / expressions.py already checks `current_token.type ==
    # "OPEN_BRACE"` before calling it, so this defensive branch is
    # unreachable through real parsing -- covered directly instead.
    p = _parser_for("int32 x = 1;")
    result = p.parse_scope()
    t.require(result is None)
    t.require_eq(len(p.errors), 1)


def test_recover_to_statement_boundary_stops_at_semicolon():
    p = _parser_for("1 2 3 ; 4")
    p._recover_to_statement_boundary()
    t.require_eq(p.current_token.value, "4")


def test_recover_to_statement_boundary_stops_at_close_brace():
    p = _parser_for("1 2 } 3")
    p._recover_to_statement_boundary()
    t.require_eq(p.current_token.type, "CLOSE_BRACE")


def test_recover_to_statement_boundary_stops_at_strong_starter():
    p = _parser_for("1 2 return 3;")
    p._recover_to_statement_boundary()
    t.require_eq(p.current_token.type, "RETURN")


def test_recover_to_statement_boundary_runs_to_eof():
    p = _parser_for("1 2 3")
    p._recover_to_statement_boundary()
    t.require(p.current_token is None)


# --- report_error edge cases -------------------------------------------------

def test_last_non_comment_token_returns_none_when_all_comments():
    p = _parser_for("// only a comment\n")
    t.require(p._last_non_comment_token() is None)


def test_report_error_comment_token_at_eof_falls_back_to_last_token_index():
    p = _parser_for("int32 x = 1; // trailing\n")
    while p.current_token is not None:
        p.advance()
    comment_tok = next(tok for tok in p.tokens if tok.type == "SINGLE_LINE_COMMENT")
    p.report_error(ParserError(message="synthetic", source_file="test.fire"), token=comment_tok)
    t.require_eq(len(p.errors), 1)
    t.require(p.errors[0].line > 0)


def test_report_error_sets_source_file_when_missing():
    p = _parser_for("int32 x = 1;")
    err = CompileTimeError(source_file=None)
    p.report_error(err, token=p.tokens[0])
    t.require_eq(err.source_file, p.filename)


def test_report_error_swallows_position_lookup_exception():
    p = _parser_for("int32 x = 1;")
    p.file = ""  # get_line("", 1) raises IndexError inside report_error's try
    err = ParserError(message="synthetic", source_file="test.fire")
    p.report_error(err, token=p.tokens[0])
    t.require_eq(len(p.errors), 1)
    t.require_eq(err.line, 0)  # position lookup failed; default untouched
