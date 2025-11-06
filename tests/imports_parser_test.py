#!/usr/bin/env python3
"""
Quick parser tests for import parsing (not a full test harness).

Run with:
  python3 tests/imports_parser_test.py

Exits 0 on success, non-zero on failure.
"""
from __future__ import annotations
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from firescript.lexer import Lexer
from firescript.parser import Parser
from firescript.enums import NodeTypes


def run_valid_import_parsing():
    src = """
import util.math as m
import foo.bar.{a as b, c}
import baz.qux.*
"""
    lexer = Lexer(src)
    tokens = lexer.tokenize()
    p = Parser(tokens, src, "<test-valid>")
    ast = p.parse()
    if p.errors:
        print("Parser reported errors for valid import sample:")
        for e in p.errors:
            print(e)
        return False

    # Compare by enum value string to avoid mismatched enum objects when tests run
    imports = [c for c in (ast.children or []) if getattr(c.node_type, 'value', str(c.node_type)) == NodeTypes.IMPORT_STATEMENT.value]
    if not imports:
        print("No import nodes found in AST for valid sample")
        return False

    # Basic attribute checks
    # import util.math as m -> imports symbol 'math' from module 'util' with alias 'm'
    mp = getattr(imports[0], "module_path", None)
    if mp != "util":
        print("Expected first import module_path 'util', got:", mp)
        return False

    # second import has explicit symbol list
    second = imports[1]
    if getattr(second, "kind", None) != "symbols":
        print("Expected second import kind 'symbols', got:", getattr(second, 'kind', None))
        return False

    return True


def run_invalid_import_in_scope():
    src = """
fn main() {
    import something
}
"""
    lexer = Lexer(src)
    tokens = lexer.tokenize()
    p = Parser(tokens, src, "<test-invalid>")
    _ = p.parse()
    # Parser should record an error for import inside a scope
    if not p.errors:
        print("Expected parser errors for import inside scope, but none were reported")
        return False
    return True


def main():
    ok1 = run_valid_import_parsing()
    ok2 = run_invalid_import_in_scope()
    if ok1 and ok2:
        print("OK: import parser tests passed")
        sys.exit(0)
    else:
        print("FAIL: one or more parser tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
