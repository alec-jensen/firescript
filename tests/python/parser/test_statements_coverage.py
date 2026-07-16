"""Direct-parser unit tests for real (reachable) statements.py branches that
cannot be exercised through a full `.fire` compile because a later pipeline
stage (AST->FIR lowering) doesn't yet support the resulting AST shape. These
are genuine parser behaviors -- not defensive/dead guards -- so they're
tested via the actual public Parser API (tokenize + parse), just without
going through the rest of the compiler.

Discovered gaps worth flagging (not fixed here, per project policy):
  - ast_to_fir.py's `_convert_statement` has no case for a bare
    NodeTypes.ARRAY_ACCESS statement (e.g. `arr[0];`), even though the
    parser accepts it as a valid statement.
  - ast_to_fir.py's `_convert_statement` has no case for NodeTypes.DIRECTIVE
    nested inside a function body, even though the parser accepts a
    directive declared inside a nested scope (not just at file top level).
"""
from __future__ import annotations

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from harness import pyunit as t
from enums import NodeTypes

from _helpers import make_parser


def test_array_access_as_bare_statement_parses():
    # `arr[0];` -- an array-access expression used as a statement with its
    # value discarded -- is accepted by _parse_statement()'s OPEN_BRACKET
    # lookahead branch when no '=' follows (statements.py: the bracket path
    # falls through to `return expr`). See module docstring: ast_to_fir
    # cannot yet lower this to FIR, so it's tested at the parser level.
    src = "arr: int32[] = [1, 2, 3]; arr[0];"
    p = make_parser(src)
    ast = p.parse()
    t.require(len(p.errors) == 0, [str(e) for e in p.errors])
    stmt_types = [c.node_type for c in ast.children]
    t.require(NodeTypes.ARRAY_ACCESS in stmt_types, stmt_types)


def test_nested_directive_inside_function_parses():
    # A `directive <name>;` statement inside a function body is accepted by
    # _parse_statement()'s DIRECTIVE branch (statements.py), which is only
    # reached for *nested* directives -- file top-level directives go
    # through declarations.py's own top-level loop instead.
    src = "fn main() -> int32 { directive enable_drops; return 0; }"
    p = make_parser(src)
    p.parse()
    t.require(len(p.errors) == 0, [str(e) for e in p.errors])
    func = next(c for c in p.ast.children if c.node_type == NodeTypes.FUNCTION_DEFINITION)
    body = func.children[-1]
    t.require(any(s.node_type == NodeTypes.DIRECTIVE for s in body.children))


def test_generic_class_nested_type_argument_parses():
    # `Pair<Pair<int32, int32>, int32>` -- a generic class instantiated with
    # another generic-class instance as one of its own type arguments --
    # exercises the successful nested-generic-type-argument path in
    # parse_variable_declaration() (statements.py). Not tested via a full
    # `.fire` run because using this as a real value currently trips an
    # unrelated FLIR-lowering bug (nested generic-class-typed fields lower
    # to a mismatched 'ptr' vs struct-value type, failing FLIRV-T4/T5
    # verification) -- a separate, pre-existing codegen issue.
    src = (
        "class Pair<T, U> { a: T; b: U; fn Pair(a: T, b: U) { this.a = a; this.b = b; } } "
        "nested: Pair<Pair<int32, int32>, int32> = Pair(Pair(1, 2), 3);"
    )
    p = make_parser(src)
    p.parse()
    t.require(len(p.errors) == 0, [str(e) for e in p.errors])
    decl = next(c for c in p.ast.children if c.node_type == NodeTypes.VARIABLE_DECLARATION)
    t.require("Pair" in decl.var_type, decl.var_type)
