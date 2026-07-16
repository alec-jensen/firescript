"""One-off migration tool: rewrites firescript source from prefix type
declarations to postfix type declarations.

    int32 a = 5;                          -> a: int32 = 5;
    int32 add(int32 a, int32 b) { ... }   -> fn add(a: int32, b: int32) -> int32 { ... }
    generator<int32> gen(int32 n) { ... } -> fn gen(n: int32) -> generator<int32> { ... }
    class Foo { int32 x; Foo(int32 x) {} } -> class Foo { x: int32; fn Foo(x: int32) {} }
    Circle(float64 radius)                -> Circle(radius: float64)
    for (int32 i = 0; ...)                -> for (i: int32 = 0; ...)
    for (int32 x in xs)                   -> for (x: int32 in xs)

This is a text-preserving TOKEN-STREAM rewriter, not an AST round-trip: it
walks the original token stream and, for everything it doesn't specifically
recognize as a prefix-typed declaration, copies the original source text
verbatim (comments, whitespace, formatting included). It is deliberately
conservative -- when a construct doesn't match an expected shape, it leaves
that region untouched and prints a warning, so a human can fix it by hand
rather than risk silently mangling the file.

Not part of the shipped compiler; delete after the migration is complete.

Usage:
    python tools/migrate_postfix.py <file_or_dir> [<file_or_dir> ...] [--write] [--diff]

Without --write, prints a unified diff per file and does not modify anything.
"""
from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "firescript"))

from lexer import Lexer, Token  # noqa: E402

TYPE_TOKEN_NAMES = {
    "INT8", "INT16", "INT32", "INT64",
    "UINT8", "UINT16", "UINT32", "UINT64",
    "FLOAT32", "FLOAT64", "FLOAT128",
    "BOOL", "STRING", "VOID",
}

class ConversionAbort(Exception):
    """Raised internally when a recognized-looking construct doesn't match the
    expected shape closely enough to convert safely; caller falls back to
    verbatim copy for that region."""


class Ctx:
    def __init__(self, source: str, filename: str):
        self.source = source
        self.filename = filename
        self.tokens: list[Token] = Lexer(source).tokenize()
        self.pos = 0
        self.out: list[str] = []
        self.emitted_upto = 0
        self.warnings: list[str] = []
        # Best-effort registry of names known to be types (classes/enums), so
        # bare "Identifier Identifier" declarations of user types are recognized.
        self.known_types: set[str] = set()
        # Mirrors ParserBase.defer_undefined_identifiers: when a file has any
        # import, the real parser accepts ANY bare identifier as a type name
        # (deferred validation) -- this is how e.g. 'char' (never a lexer
        # keyword nor pre-registered) is accepted as a type at all.
        self.defer_undefined_identifiers = any(t.type == "IMPORT" for t in self.tokens)
        # Mirrors _parse_directive's special-case registration: `directive
        # enable_syscalls;` implicitly declares the built-in 'SyscallResult'
        # type, the only directive with this side effect.
        for idx, t in enumerate(self.tokens):
            if t.type == "DIRECTIVE" and idx + 1 < len(self.tokens) and self.tokens[idx + 1].value == "enable_syscalls":
                self.known_types.add("SyscallResult")
                break

    # -- token access -------------------------------------------------------
    def tok(self, offset: int = 0) -> Token | None:
        i = self.pos + offset
        return self.tokens[i] if 0 <= i < len(self.tokens) else None

    def at_end(self) -> bool:
        return self.pos >= len(self.tokens)

    def tok_offset(self, token_index: int) -> int:
        return self.tokens[token_index].index if token_index < len(self.tokens) else len(self.source)

    # -- text emission --------------------------------------------------------
    def flush_verbatim_to_tok(self, token_index: int) -> None:
        """Emit original source text from emitted_upto up to (not including) tokens[token_index]."""
        offset = self.tok_offset(token_index)
        if offset > self.emitted_upto:
            self.out.append(self.source[self.emitted_upto:offset])
            self.emitted_upto = offset

    def consume_silently_to_tok(self, token_index: int) -> None:
        """Mark original source up to tokens[token_index] as consumed WITHOUT
        emitting it (used right after appending replacement text for that span)."""
        self.emitted_upto = self.tok_offset(token_index)

    def replace_span(self, start_idx: int, end_idx: int, replacement: str) -> None:
        """Flush verbatim up to start_idx, emit `replacement` in place of the
        original tokens[start_idx:end_idx), and advance pos to end_idx.

        Only swallows source text through the END of the last actually-replaced
        token (end_idx - 1); any original whitespace/comments between that token
        and tokens[end_idx] are left for the next flush to pick up naturally, so
        e.g. the space before '=' or '{' in the source isn't silently dropped.
        """
        self.flush_verbatim_to_tok(start_idx)
        self.out.append(replacement)
        last_idx = end_idx - 1
        if start_idx <= last_idx < len(self.tokens):
            t = self.tokens[last_idx]
            self.emitted_upto = t.index + len(t.value)
        else:
            self.emitted_upto = self.tok_offset(end_idx)
        self.pos = end_idx

    def skip_token_verbatim(self) -> None:
        """Flush up to and including the current token's original text, advance pos."""
        t = self.tok()
        assert t is not None
        end = t.index + len(t.value)
        self.flush_verbatim_to_tok(self.pos)
        self.out.append(self.source[self.emitted_upto:end])
        self.emitted_upto = end
        self.pos += 1

    def result(self) -> str:
        self.flush_verbatim_to_tok(len(self.tokens))
        return "".join(self.out)

    def warn(self, msg: str) -> None:
        at = self.tok().index if self.tok() else len(self.source)
        line = self.source.count("\n", 0, at) + 1
        self.warnings.append(f"{self.filename}:{line}: {msg}")


def is_type_tok(ctx: Ctx, tok: Token | None) -> bool:
    if tok is None:
        return False
    if tok.type in TYPE_TOKEN_NAMES:
        return True
    if tok.type == "IDENTIFIER":
        if tok.value in ctx.known_types:
            return True
        if ctx.defer_undefined_identifiers and bool(tok.value.strip()):
            return True
    return False


def slice_between(ctx: Ctx, start_tok_idx: int, end_tok_idx: int) -> str:
    """Verbatim original text spanning tokens[start_tok_idx:end_tok_idx] (end exclusive)."""
    start = ctx.tokens[start_tok_idx].index
    end = ctx.tok_offset(end_tok_idx)
    return ctx.source[start:end].rstrip()


def find_matching(ctx: Ctx, open_idx: int, open_type: str, close_type: str) -> int:
    """Return the index of the token matching tokens[open_idx] (which must be open_type)."""
    depth = 0
    i = open_idx
    n = len(ctx.tokens)
    while i < n:
        tt = ctx.tokens[i].type
        if tt == open_type:
            depth += 1
        elif tt == close_type:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ConversionAbort(f"no matching {close_type} for {open_type} at token {open_idx}")


def find_matching_generic_gt(ctx: Ctx, lt_idx: int) -> int | None:
    """Like find_matching for '<'/'>', but -- since bare '<' is also the
    less-than operator -- bails out (returns None, meaning "not real generic
    brackets") if a statement boundary is crossed before a balanced '>' is
    found. Mirrors ParserBase._scan_matching_gt in the real parser, which
    exists for exactly this reason."""
    depth = 0
    i = lt_idx
    n = len(ctx.tokens)
    while i < n:
        tt = ctx.tokens[i].type
        if tt == "LESS_THAN":
            depth += 1
        elif tt == "GREATER_THAN":
            depth -= 1
            if depth == 0:
                return i
        elif tt in ("SEMICOLON", "OPEN_BRACE", "CLOSE_BRACE"):
            return None
        i += 1
    return None


# ---------------------------------------------------------------------------
# Type expression parsing (over the OLD prefix grammar): consumes a leading
# type (with optional generic args) starting at a given token index.
# ---------------------------------------------------------------------------

def parse_prefix_type(ctx: Ctx, pos: int) -> tuple[str, int]:
    """Parse `TYPE` or `Name<T1, T2>` (possibly nested) starting at token pos.
    Returns (verbatim_type_text, index_after_type)."""
    tok = ctx.tokens[pos]
    if not is_type_tok(ctx, tok):
        raise ConversionAbort(f"expected type at token {pos} ({tok.type} {tok.value!r})")
    i = pos + 1
    if tok.type == "IDENTIFIER" and i < len(ctx.tokens) and ctx.tokens[i].type == "LESS_THAN":
        close = find_matching_generic_gt(ctx, i)
        if close is not None:
            i = close + 1
        # else: '<' wasn't balanced generic brackets (e.g. a '<' comparison
        # operator) -- treat this as a bare type name, don't consume it.
    text = slice_between(ctx, pos, i)
    return text, i


def parse_array_suffix(ctx: Ctx, pos: int) -> tuple[str, int]:
    """Optional `[]` or `[N]` immediately at token pos. Returns (verbatim_text, next_index)."""
    if pos < len(ctx.tokens) and ctx.tokens[pos].type == "OPEN_BRACKET":
        close = pos + 1
        while close < len(ctx.tokens) and ctx.tokens[close].type != "CLOSE_BRACKET":
            close += 1
        if close >= len(ctx.tokens):
            raise ConversionAbort("unterminated array suffix")
        text = slice_between(ctx, pos, close + 1)
        return text, close + 1
    return "", pos


def extract_type_param_names(ctx: Ctx, open_idx: int, close_idx: int) -> list[str]:
    """Names bound by a '<...>' type-parameter list (open_idx/close_idx are the
    '<'/'>' token indices): an IDENTIFIER at the start of the list or right
    after a top-level comma, before any ':' constraint."""
    names: list[str] = []
    i = open_idx + 1
    expect_name = True
    depth = 0
    while i < close_idx:
        t = ctx.tokens[i]
        if t.type == "LESS_THAN":
            depth += 1
        elif t.type == "GREATER_THAN":
            depth -= 1
        elif depth == 0:
            if expect_name and t.type == "IDENTIFIER":
                names.append(t.value)
                expect_name = False
            elif t.type == "COMMA":
                expect_name = True
            elif t.type == "COLON":
                expect_name = False
        i += 1
    return names


# ---------------------------------------------------------------------------
# Variable declaration:  [const] TYPE [ARRAY] NAME [?] (= expr)? ;
# ---------------------------------------------------------------------------

def try_variable_declaration(ctx: Ctx) -> bool:
    start = ctx.pos
    p = start
    is_const = False
    if ctx.tokens[p].type == "CONST":
        is_const = True
        p += 1
    if p >= len(ctx.tokens) or not is_type_tok(ctx, ctx.tokens[p]):
        return False
    try:
        type_text, p = parse_prefix_type(ctx, p)
        arr_text, p = parse_array_suffix(ctx, p)
        # Variable names accept IDENTIFIER or a keyword-usable-as-name (AS, OWNED),
        # matching the real parser's consume_name().
        if p >= len(ctx.tokens) or ctx.tokens[p].type not in ("IDENTIFIER", "AS", "OWNED"):
            return False
        name_tok = ctx.tokens[p]
        p += 1
        nullable = ""
        if p < len(ctx.tokens) and ctx.tokens[p].type == "QUESTION":
            nullable = "?"
            p += 1
        # Must be followed by '=' or ';' (matches parse_variable_declaration)
        if p >= len(ctx.tokens) or ctx.tokens[p].type not in ("ASSIGN", "SEMICOLON"):
            return False
    except ConversionAbort:
        return False

    const_kw = "const " if is_const else ""
    # Nullable '?' moves to the type in postfix form: `a: int32?`, not `a?: int32`.
    new_header = f"{const_kw}{name_tok.value}: {type_text}{arr_text}{nullable}"
    ctx.replace_span(start, p, new_header)
    return True


# ---------------------------------------------------------------------------
# Parameter list: (TYPE|owned TYPE|&TYPE|&mut TYPE) [ARRAY] NAME [?] (',' ...)*
# receivers &this / &mut this / owned this pass through unchanged.
# ---------------------------------------------------------------------------

def convert_param_list(ctx: Ctx, open_idx: int, close_idx: int) -> str:
    """Convert the parameter list tokens[open_idx+1 : close_idx] (open/close are
    the '(' / ')' token indices) to postfix form. Returns the new '(' ... ')' text."""
    parts: list[str] = []
    i = open_idx + 1
    while i < close_idx:
        tok = ctx.tokens[i]
        if tok.type == "AMPERSAND":
            j = i + 1
            mut = ""
            if j < close_idx and ctx.tokens[j].type == "MUT":
                mut = "mut "
                j += 1
            if j < close_idx and ctx.tokens[j].type == "IDENTIFIER" and ctx.tokens[j].value == "this":
                parts.append(f"&{mut}this")
                i = j + 1
                if i < close_idx and ctx.tokens[i].type == "COMMA":
                    i += 1
                continue
            # Not a receiver -- an ordinary borrowed parameter '&Type name' /
            # '&mut Type name'; fall through to the generic modifier-parsing path below.
        if tok.type == "OWNED" and i + 1 < close_idx and ctx.tokens[i + 1].type == "IDENTIFIER" and ctx.tokens[i + 1].value == "this":
            parts.append("owned this")
            i += 2
            if i < close_idx and ctx.tokens[i].type == "COMMA":
                i += 1
            continue

        modifier = ""
        j = i
        if ctx.tokens[j].type == "OWNED":
            modifier = "owned "
            j += 1
        elif ctx.tokens[j].type == "AMPERSAND":
            j += 1
            if j < close_idx and ctx.tokens[j].type == "MUT":
                modifier = "&mut "
                j += 1
            else:
                modifier = "&"
        if j >= close_idx or not is_type_tok(ctx, ctx.tokens[j]):
            raise ConversionAbort(f"expected parameter type at token {j}")
        type_text, j = parse_prefix_type(ctx, j)
        arr_text, j = parse_array_suffix(ctx, j)
        # Class methods (unlike functions/constructors/generators) historically wrote
        # the borrow marker *after* the type, before the name: `Type &name`. Accept
        # that ordering too when no modifier was found before the type.
        if not modifier and j < close_idx and ctx.tokens[j].type == "AMPERSAND":
            j += 1
            if j < close_idx and ctx.tokens[j].type == "MUT":
                modifier = "&mut "
                j += 1
            else:
                modifier = "&"
        if j >= close_idx or ctx.tokens[j].type not in ("IDENTIFIER", "AS", "OWNED"):
            raise ConversionAbort(f"expected parameter name at token {j}")
        pname = ctx.tokens[j].value
        j += 1
        nullable = ""
        if j < close_idx and ctx.tokens[j].type == "QUESTION":
            nullable = "?"
            j += 1
        # Nullable '?' moves to the type in postfix form: `p: int32?`, not `p?: int32`.
        parts.append(f"{pname}: {modifier}{type_text}{arr_text}{nullable}")
        i = j
        if i < close_idx and ctx.tokens[i].type == "COMMA":
            i += 1
        elif i < close_idx:
            raise ConversionAbort(f"expected ',' or ')' in parameter list at token {i}")
    return "(" + ", ".join(parts) + ")"


def emit_signature_and_recurse_body(ctx: Ctx, start: int, header: str, body_open: int) -> None:
    """Replace tokens[start:body_open] (the whole prefix-style signature) with
    `header`, then emit the original '{' verbatim and recursively convert the
    body, leaving ctx.pos right after the matching '}'."""
    ctx.replace_span(start, body_open, header)
    ctx.skip_token_verbatim()  # emits '{' verbatim, advances past it
    convert_scope(ctx)


# ---------------------------------------------------------------------------
# Top-level / free function definition:
#   TYPE [ARRAY] NAME [<TYPE_PARAMS>] ( PARAMS ) { BODY }
# ---------------------------------------------------------------------------

def try_function_definition(ctx: Ctx) -> bool:
    start = ctx.pos
    first = ctx.tokens[start]
    # A bare, not-yet-known IDENTIFIER is still accepted as a return type when it
    # looks like `IDENT IDENT <` -- a generic function whose return type is its
    # own type parameter, e.g. `T max<T: int32 | float64>(T a, T b) { ... }`.
    looks_like_generic_return = (
        first.type == "IDENTIFIER"
        and start + 2 < len(ctx.tokens)
        and ctx.tokens[start + 1].type == "IDENTIFIER"
        and ctx.tokens[start + 2].type == "LESS_THAN"
    )
    if not is_type_tok(ctx, first) and not looks_like_generic_return:
        return False
    try:
        if is_type_tok(ctx, first):
            ret_type_text, p = parse_prefix_type(ctx, start)
        else:
            ret_type_text, p = first.value, start + 1
        ret_arr_text, p = parse_array_suffix(ctx, p)
        if p >= len(ctx.tokens) or ctx.tokens[p].type != "IDENTIFIER":
            return False
        name_tok = ctx.tokens[p]
        p += 1
        type_params_text = ""
        if p < len(ctx.tokens) and ctx.tokens[p].type == "LESS_THAN":
            tp_open = p
            tp_close = find_matching(ctx, tp_open, "LESS_THAN", "GREATER_THAN")
            ctx.known_types.update(extract_type_param_names(ctx, tp_open, tp_close))
            type_params_text = slice_between(ctx, tp_open, tp_close + 1)
            p = tp_close + 1
        if p >= len(ctx.tokens) or ctx.tokens[p].type != "OPEN_PAREN":
            return False
        open_idx = p
        close_idx = find_matching(ctx, open_idx, "OPEN_PAREN", "CLOSE_PAREN")
        p = close_idx + 1
        if p >= len(ctx.tokens) or ctx.tokens[p].type != "OPEN_BRACE":
            return False
        new_params = convert_param_list(ctx, open_idx, close_idx)
        body_open = p
    except ConversionAbort as e:
        ctx.warn(f"function definition looked malformed, left unconverted: {e}")
        return False

    header = f"fn {name_tok.value}{type_params_text}{new_params} -> {ret_type_text}{ret_arr_text}"
    emit_signature_and_recurse_body(ctx, start, header, body_open)
    return True


# ---------------------------------------------------------------------------
# Generator definition: generator < TYPE > NAME ( PARAMS ) { BODY }
# ---------------------------------------------------------------------------

def try_generator_definition(ctx: Ctx) -> bool:
    start = ctx.pos
    if ctx.tokens[start].type != "GENERATOR":
        return False
    try:
        p = start + 1
        if p >= len(ctx.tokens) or ctx.tokens[p].type != "LESS_THAN":
            raise ConversionAbort("expected '<' after 'generator'")
        yield_type_text, p = parse_prefix_type(ctx, p + 1)
        if p >= len(ctx.tokens) or ctx.tokens[p].type != "GREATER_THAN":
            raise ConversionAbort("expected '>' after generator yield type")
        p += 1
        if p >= len(ctx.tokens) or ctx.tokens[p].type != "IDENTIFIER":
            raise ConversionAbort("expected generator name")
        name_tok = ctx.tokens[p]
        p += 1
        if p >= len(ctx.tokens) or ctx.tokens[p].type != "OPEN_PAREN":
            raise ConversionAbort("expected '(' after generator name")
        open_idx = p
        close_idx = find_matching(ctx, open_idx, "OPEN_PAREN", "CLOSE_PAREN")
        p = close_idx + 1
        if p >= len(ctx.tokens) or ctx.tokens[p].type != "OPEN_BRACE":
            raise ConversionAbort("expected '{' to start generator body")
        new_params = convert_param_list(ctx, open_idx, close_idx)
        body_open = p
    except ConversionAbort as e:
        ctx.warn(f"generator definition looked malformed, left unconverted: {e}")
        return False

    header = f"fn {name_tok.value}{new_params} -> generator<{yield_type_text}>"
    emit_signature_and_recurse_body(ctx, start, header, body_open)
    return True


# ---------------------------------------------------------------------------
# for (...) headers
# ---------------------------------------------------------------------------

def try_for_header(ctx: Ctx) -> bool:
    if ctx.tokens[ctx.pos].type != "FOR":
        return False
    p = ctx.pos + 1
    if p >= len(ctx.tokens) or ctx.tokens[p].type != "OPEN_PAREN":
        return False
    p += 1
    if p >= len(ctx.tokens) or not is_type_tok(ctx, ctx.tokens[p]):
        return False  # not a typed-decl for-header; leave 'for (' to verbatim path
    try:
        type_start = p
        type_text, q = parse_prefix_type(ctx, p)
        if q >= len(ctx.tokens) or ctx.tokens[q].type != "IDENTIFIER":
            return False
        name_tok = ctx.tokens[q]
        q += 1
        if q < len(ctx.tokens) and ctx.tokens[q].type in ("IN", "ASSIGN"):
            # for-in `TYPE NAME in` -> `NAME: TYPE in`, or C-style init
            # `TYPE NAME =` -> `NAME: TYPE =`
            ctx.replace_span(type_start, q, f"{name_tok.value}: {type_text}")
            return True
        return False
    except ConversionAbort:
        return False


# ---------------------------------------------------------------------------
# class body: fields `TYPE NAME [?];`, constructors `ClassName(PARAMS) { }`,
# methods `[static] TYPE NAME(PARAMS) { }`.
# ---------------------------------------------------------------------------

def convert_class_body(ctx: Ctx, class_name: str) -> None:
    """Assumes ctx.pos is right after the class body's OPEN_BRACE (already flushed
    and emitted by the caller). Consumes through (and emits) the matching CLOSE_BRACE."""
    while True:
        if ctx.at_end():
            raise ConversionAbort("unexpected EOF in class body")
        if skip_comment_if_present(ctx):
            continue
        tok = ctx.tok()
        if tok.type == "CLOSE_BRACE":
            ctx.skip_token_verbatim()
            return
        if tok.type == "SEMICOLON":
            ctx.pos += 1
            continue

        start = ctx.pos
        p = start
        is_static = False
        if ctx.tokens[p].type == "STATIC":
            is_static = True
            p += 1

        if p >= len(ctx.tokens) or not (
            is_type_tok(ctx, ctx.tokens[p])
            or (ctx.tokens[p].type == "IDENTIFIER" and ctx.tokens[p].value == class_name)
        ):
            raise ConversionAbort(f"unrecognized class-body member at token {p}")

        ftype_tok = ctx.tokens[p]
        is_ctor = ftype_tok.type == "IDENTIFIER" and ftype_tok.value == class_name
        q = p + 1

        if is_ctor and q < len(ctx.tokens) and ctx.tokens[q].type == "OPEN_PAREN":
            # constructor: ClassName(PARAMS) { BODY }
            open_idx = q
            close_idx = find_matching(ctx, open_idx, "OPEN_PAREN", "CLOSE_PAREN")
            r = close_idx + 1
            if r >= len(ctx.tokens) or ctx.tokens[r].type != "OPEN_BRACE":
                raise ConversionAbort("expected '{' to start constructor body")
            new_params = convert_param_list(ctx, open_idx, close_idx)
            header = f"fn {class_name}{new_params}"
            emit_signature_and_recurse_body(ctx, start, header, r)
            continue

        # method or field: TYPE NAME ...
        type_text, r = parse_prefix_type(ctx, p)
        if r >= len(ctx.tokens) or ctx.tokens[r].type != "IDENTIFIER":
            raise ConversionAbort(f"expected member name at token {r}")
        name_tok = ctx.tokens[r]
        r += 1
        nullable = ""
        if r < len(ctx.tokens) and ctx.tokens[r].type == "QUESTION":
            nullable = "?"
            r += 1

        if r < len(ctx.tokens) and ctx.tokens[r].type == "OPEN_PAREN":
            # method definition
            open_idx = r
            close_idx = find_matching(ctx, open_idx, "OPEN_PAREN", "CLOSE_PAREN")
            s = close_idx + 1
            if s >= len(ctx.tokens) or ctx.tokens[s].type != "OPEN_BRACE":
                raise ConversionAbort("expected '{' to start method body")
            new_params = convert_param_list(ctx, open_idx, close_idx)
            static_kw = "static " if is_static else ""
            # Note: a '?' here (nullable marker on a method's own name) was already a
            # no-op in the old grammar (parsed but never stored/used for methods) --
            # dropped rather than carried forward, since there's no postfix position
            # for it (nullable return types aren't supported).
            header = f"{static_kw}fn {name_tok.value}{new_params} -> {type_text}"
            emit_signature_and_recurse_body(ctx, start, header, s)
            continue

        # field declaration: TYPE NAME [?] ;
        if r >= len(ctx.tokens) or ctx.tokens[r].type != "SEMICOLON":
            raise ConversionAbort(f"expected ';' after field declaration at token {r}")
        # Nullable '?' moves to the type in postfix form: `x: int32?;`, not `x?: int32;`.
        ctx.replace_span(start, r, f"{name_tok.value}: {type_text}{nullable}")


def try_class_definition(ctx: Ctx) -> bool:
    start = ctx.pos
    p = start
    if ctx.tokens[p].type == "COPYABLE":
        p += 1
    if p >= len(ctx.tokens) or ctx.tokens[p].type != "CLASS":
        return False
    p += 1
    if p >= len(ctx.tokens) or ctx.tokens[p].type != "IDENTIFIER":
        raise ConversionAbort("expected class name after 'class'")
    class_name = ctx.tokens[p].value
    ctx.known_types.add(class_name)
    p += 1
    if p < len(ctx.tokens) and ctx.tokens[p].type == "LESS_THAN":
        close = find_matching(ctx, p, "LESS_THAN", "GREATER_THAN")
        ctx.known_types.update(extract_type_param_names(ctx, p, close))
        p = close + 1
    if p < len(ctx.tokens) and ctx.tokens[p].type == "FROM":
        p += 2  # 'from' BaseName
    if p >= len(ctx.tokens) or ctx.tokens[p].type != "OPEN_BRACE":
        raise ConversionAbort("expected '{' to start class body")

    ctx.flush_verbatim_to_tok(p)
    ctx.pos = p
    ctx.skip_token_verbatim()  # emit '{' verbatim
    convert_class_body(ctx, class_name)
    return True


# ---------------------------------------------------------------------------
# enum body: `Variant(TYPE name, ...)` -> `Variant(name: TYPE, ...)`
# ---------------------------------------------------------------------------

def try_enum_definition(ctx: Ctx) -> bool:
    start = ctx.pos
    if ctx.tokens[start].type != "ENUM":
        return False
    p = start + 1
    if p >= len(ctx.tokens) or ctx.tokens[p].type != "IDENTIFIER":
        raise ConversionAbort("expected enum name after 'enum'")
    enum_name = ctx.tokens[p].value
    ctx.known_types.add(enum_name)
    p += 1
    if p >= len(ctx.tokens) or ctx.tokens[p].type != "OPEN_BRACE":
        raise ConversionAbort("expected '{' to start enum body")
    open_idx = p
    close_idx = find_matching(ctx, open_idx, "OPEN_BRACE", "CLOSE_BRACE")

    # Convert each variant's payload list in place.
    ctx.flush_verbatim_to_tok(open_idx)
    ctx.pos = open_idx
    i = open_idx + 1
    while i < close_idx:
        new_i = skip_comment_span_idx(ctx, i)
        if new_i != i:
            i = new_i
            continue
        tok = ctx.tokens[i]
        if tok.type == "COMMA":
            i += 1
            continue
        if tok.type != "IDENTIFIER":
            raise ConversionAbort(f"unexpected token in enum body at {i}")
        i += 1
        if i < close_idx and ctx.tokens[i].type == "OPEN_PAREN":
            popen = i
            pclose = find_matching(ctx, popen, "OPEN_PAREN", "CLOSE_PAREN")
            new_payload_parts: list[str] = []
            j = popen + 1
            while j < pclose:
                if not is_type_tok(ctx, ctx.tokens[j]):
                    raise ConversionAbort(f"expected payload field type at token {j}")
                ftype_text, j = parse_prefix_type(ctx, j)
                if j >= pclose or ctx.tokens[j].type != "IDENTIFIER":
                    raise ConversionAbort(f"expected payload field name at token {j}")
                fname = ctx.tokens[j].value
                j += 1
                new_payload_parts.append(f"{fname}: {ftype_text}")
                if j < pclose and ctx.tokens[j].type == "COMMA":
                    j += 1
            ctx.replace_span(popen, pclose + 1, "(" + ", ".join(new_payload_parts) + ")")
            i = pclose + 1
        else:
            i += 1

    ctx.flush_verbatim_to_tok(close_idx + 1)
    ctx.pos = close_idx + 1
    return True


# ---------------------------------------------------------------------------
# Generic scope / top-level walker
# ---------------------------------------------------------------------------

def skip_comment_span_idx(ctx: Ctx, i: int) -> int:
    """Index-based counterpart to skip_comment_if_present, for callers that
    scan with a raw token index rather than ctx.pos. Returns i unchanged if
    tokens[i] isn't a comment start."""
    if i >= len(ctx.tokens):
        return i
    t = ctx.tokens[i]
    if t.type == "SINGLE_LINE_COMMENT":
        return i + 1
    if t.type == "MULTI_LINE_COMMENT_START":
        j = i + 1
        while j < len(ctx.tokens) and ctx.tokens[j].type != "MULTI_LINE_COMMENT_END":
            j += 1
        return j + 1 if j < len(ctx.tokens) else j
    return i


def skip_comment_if_present(ctx: Ctx) -> bool:
    """A MULTI_LINE_COMMENT_START/END pair only marks the delimiters -- the
    lexer tokenizes everything BETWEEN them as ordinary code-shaped tokens
    (identifiers, '=', numbers, ...), which can accidentally look like a
    declaration to the recognizers below (e.g. text inside a `/* EXPECT ... */`
    block). Skip a comment's entire span atomically so its interior tokens are
    never offered to a recognizer. Returns True if a comment was skipped."""
    tok = ctx.tok()
    if tok is None:
        return False
    if tok.type == "SINGLE_LINE_COMMENT":
        ctx.pos += 1
        return True
    if tok.type == "MULTI_LINE_COMMENT_START":
        ctx.pos += 1
        while not ctx.at_end() and ctx.tok().type != "MULTI_LINE_COMMENT_END":
            ctx.pos += 1
        if not ctx.at_end():
            ctx.pos += 1  # consume MULTI_LINE_COMMENT_END itself
        return True
    return False


def convert_scope(ctx: Ctx) -> None:
    """Assumes ctx.pos is right after an already-flushed-and-emitted OPEN_BRACE.
    Consumes (and emits) through the matching CLOSE_BRACE."""
    while True:
        if ctx.at_end():
            raise ConversionAbort("unexpected EOF inside scope")
        if skip_comment_if_present(ctx):
            continue
        tok = ctx.tok()
        if tok.type == "CLOSE_BRACE":
            ctx.skip_token_verbatim()
            return
        if tok.type == "OPEN_BRACE":
            ctx.skip_token_verbatim()
            convert_scope(ctx)
            continue
        if try_variable_declaration(ctx):
            continue
        if try_for_header(ctx):
            continue
        # Nothing recognized: advance one token (its text is flushed lazily later).
        ctx.pos += 1


def convert_top_level(ctx: Ctx) -> None:
    while not ctx.at_end():
        if skip_comment_if_present(ctx):
            continue
        tok = ctx.tok()
        if tok.type == "OPEN_BRACE":
            ctx.skip_token_verbatim()
            convert_scope(ctx)
            continue
        try:
            if try_class_definition(ctx):
                continue
            if try_enum_definition(ctx):
                continue
            if try_generator_definition(ctx):
                continue
            if try_function_definition(ctx):
                continue
        except ConversionAbort as e:
            ctx.warn(f"top-level construct looked malformed, left unconverted: {e}")
            ctx.pos += 1
            continue
        if try_variable_declaration(ctx):
            continue
        if try_for_header(ctx):
            continue
        ctx.pos += 1


def convert_source(source: str, filename: str) -> tuple[str, list[str]]:
    ctx = Ctx(source, filename)
    convert_top_level(ctx)
    return ctx.result(), ctx.warnings


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--write", action="store_true", help="write changes in place")
    ap.add_argument("--diff", action="store_true", help="print unified diffs")
    args = ap.parse_args()

    files: list[Path] = []
    for p in args.paths:
        path = Path(p)
        if path.is_dir():
            files.extend(sorted(path.rglob("*.fire")))
        else:
            files.append(path)

    total_warnings = 0
    failed = 0
    for f in files:
        source = f.read_text(encoding="utf-8")
        try:
            new_source, warnings = convert_source(source, str(f))
        except Exception as e:  # noqa: BLE001
            print(f"FAILED: {f}: {e}")
            failed += 1
            continue
        for w in warnings:
            print(f"WARN {w}")
        total_warnings += len(warnings)
        if new_source == source:
            continue
        if args.diff:
            diff = difflib.unified_diff(
                source.splitlines(keepends=True),
                new_source.splitlines(keepends=True),
                fromfile=str(f), tofile=str(f) + " (converted)",
            )
            sys.stdout.writelines(diff)
        if args.write:
            f.write_text(new_source, encoding="utf-8")
            print(f"wrote {f}")
    print(f"\n{len(files)} files scanned, {total_warnings} warnings, {failed} failed")


if __name__ == "__main__":
    main()
