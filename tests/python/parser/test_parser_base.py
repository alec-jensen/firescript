"""Direct unit tests for firescript/parser/base.py helpers: comment-anchored
diagnostic positions, literal-suffix inference, and token-stream lookahead
helpers. These are exercised through crafted invalid .fire programs
elsewhere, but several branches (comment-boundary scanning at EOF, literal
suffix edge cases) are far easier and more precise to hit by constructing a
Parser directly."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from lexer import Lexer, Token  # noqa: E402
from parser import Parser  # noqa: E402
from enums import NodeTypes  # noqa: E402
from errors import CompileTimeError, ParserError  # noqa: E402


def _parser_for(src: str) -> Parser:
    tokens = Lexer(src).tokenize()
    return Parser(tokens, src, "test.fire")


def test_report_error_with_no_token_anchors_after_last_real_token():
    # No `token` kwarg -> report_error falls back to the last non-comment
    # token in the stream via _last_non_comment_token(None): the position
    # just past the trailing ';', not the trailing comment and not the start
    # of the file.
    p = _parser_for("x: int32 = 1; // trailing comment\n")
    p.report_error(ParserError(message="synthetic", source_file="test.fire"))
    t.require_eq(len(p.errors), 1)
    t.require_eq((p.errors[0].line, p.errors[0].column), (1, 14))


def test_report_error_skips_trailing_multiline_comment_block():
    src = "x: int32 = 1;\n/* trailing\nblock\ncomment */"
    p = _parser_for(src)
    p.report_error(ParserError(message="synthetic", source_file="test.fire"))
    # The anchored line must be the statement's line, not inside the comment block.
    t.require_eq(len(p.errors), 1)
    t.require_eq((p.errors[0].line, p.errors[0].column), (1, 14))


def test_consume_name_accepts_as_and_owned_keywords():
    p = _parser_for("as owned regular_ident")
    tok1 = p.consume_name()
    t.require(tok1 is not None and tok1.type == "AS")
    tok2 = p.consume_name()
    t.require(tok2 is not None and tok2.type == "OWNED")
    tok3 = p.consume_name()
    t.require(tok3 is not None and tok3.type == "IDENTIFIER")


def test_infer_literal_type_integer_suffixes():
    p = _parser_for("x: int32 = 1;")
    for suf, expected in (
        ("i8", "int8"), ("i16", "int16"), ("i32", "int32"), ("i64", "int64"),
        ("u8", "uint8"), ("u16", "uint16"), ("u32", "uint32"), ("u64", "uint64"),
    ):
        tok = Token("INTEGER_LITERAL", f"1{suf}", 0)
        t.require_eq(p._infer_literal_type(tok), expected, suf)


@t.params([
    ("INTEGER_LITERAL", "42", "int32"),
    ("FLOAT_LITERAL", "1.0", "float32"),
    ("FLOAT_LITERAL", "1.0f", "float32"),
    ("FLOAT_LITERAL", "1.0f32", "float32"),
    ("FLOAT_LITERAL", "1.0f64", "float64"),
    ("FLOAT_LITERAL", "1.0f128", "float128"),
    ("DOUBLE_LITERAL", "1.0", "float64"),
    ("STRING_LITERAL", "hi", ""),
])
def test_infer_literal_type_defaults_and_float_suffixes(case):
    token_type, text, expected = case
    p = _parser_for("x: int32 = 1;")
    t.require_eq(p._infer_literal_type(Token(token_type, text, 0)), expected, text)


def test_is_type_token_recognizes_registered_user_type():
    p = _parser_for("x: Foo = y;")
    p.user_types.add("Foo")
    foo_tok = next(tok for tok in p.tokens if tok.value == "Foo")
    t.require(p._is_type_token(foo_tok))
    t.require(not p._is_type_token(None))


def test_token_helpers_are_safe_at_eof():
    p = _parser_for("int32")
    p.advance()  # consumes "int32", current_token becomes None
    t.require(p.current_token is None)
    p.advance()  # must not raise when already at EOF
    t.require(p.current_token is None)
    t.require(p.peek() is None)
    t.require_eq(p._current_token_index(), -1)
    t.require(p.consume_name() is None)


def test_scan_matching_gt_returns_minus_one_at_eof_without_boundary():
    # No ';'/'{'/'}' anywhere, and '<' is never closed: _scan_matching_gt
    # must fall through its while loop to the final `return -1` rather than
    # hitting the statement-boundary early-return.
    p = _parser_for("Foo<int32")
    lt_idx = next(i for i, tok in enumerate(p.tokens) if tok.type == "LESS_THAN")
    t.require_eq(p._scan_matching_gt(lt_idx), -1)


@t.params([
    ("(x)", False),            # current token is not '<'
    ("<int32> x", False),      # closed '<...>' but no '(' after it
    ("", False),               # EOF
    ("<int32>(x)", True),      # '< TYPE_ARGS > (' is a generic constructor call
])
def test_looks_like_generic_constructor_call(case):
    src, expected = case
    p = _parser_for(src)
    t.require_eq(p._looks_like_generic_constructor_call(), expected, src)


def test_constructor_with_borrowed_and_owned_regular_params_parses():
    # Regular (non-receiver) constructor params can carry a leading '&'/'owned'
    # marker; the parse must succeed and produce all 3 parameters. (The
    # end-to-end behaviour is covered by
    # tests/sources/classes/classes_regression_ctor_borrowed_and_owned_param.)
    src = (
        "class Outer {\n"
        "    total: int32;\n"
        "    fn Outer(&this, &a: Inner, owned b: Inner) {\n"
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


# --- report_error edge cases -------------------------------------------------

def test_last_non_comment_token_returns_none_when_all_comments():
    p = _parser_for("// only a comment\n")
    t.require(p._last_non_comment_token() is None)


def test_report_error_comment_token_at_eof_falls_back_to_last_token_index():
    p = _parser_for("x: int32 = 1; // trailing\n")
    while p.current_token is not None:
        p.advance()
    comment_tok = next(tok for tok in p.tokens if tok.type == "SINGLE_LINE_COMMENT")
    p.report_error(ParserError(message="synthetic", source_file="test.fire"), token=comment_tok)
    t.require_eq(len(p.errors), 1)
    # Anchored just past the last real token (';'), not at the comment.
    t.require_eq((p.errors[0].line, p.errors[0].column), (1, 14))


def test_report_error_sets_source_file_when_missing():
    p = _parser_for("x: int32 = 1;")
    err = CompileTimeError(source_file=None)
    p.report_error(err, token=p.tokens[0])
    t.require_eq(err.source_file, p.filename)


def test_report_error_swallows_position_lookup_exception():
    p = _parser_for("x: int32 = 1;")
    p.file = ""  # get_line("", 1) raises IndexError inside report_error's try
    err = ParserError(message="synthetic", source_file="test.fire")
    p.report_error(err, token=p.tokens[0])
    t.require_eq(len(p.errors), 1)
    t.require_eq(err.line, 0)  # position lookup failed; default untouched
