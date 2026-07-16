"""Unit tests for firescript/frontend_pipeline.py: import merging and
deferred-identifier resolution, exercised both via real small on-disk
import graphs (compiled in-process through CompilerPipeline, not a
subprocess -- subprocess-based compiles in tests/python/cli/test_imports.py
don't register against this process's coverage measurement) and, for a
branch that's only reachable via an internal resolver-key mismatch that
can't be provoked without editing firescript/std/ itself, a direct call
with a hand-built resolver return value.
"""
from __future__ import annotations

import os
import sys
import types
from unittest import mock

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

import frontend_pipeline as fp  # noqa: E402
from compiler_pipeline import CompilerPipeline  # noqa: E402
from enums import NodeTypes  # noqa: E402
from imports import ImportSpec, Module, ModuleResolver  # noqa: E402
from parser.ast_node import ASTNode  # noqa: E402


def test_resolve_imports_returns_ast_unchanged_when_no_imports():
    ast = ASTNode(NodeTypes.ROOT, None, "root", [], 0)
    parser_stub = types.SimpleNamespace(deferred_undefined_identifiers=[], report_error=lambda *a, **k: None)
    result = fp.resolve_imports_and_deferred_identifiers(ast, parser_stub, "unused.fire")
    t.require(result is ast, "an import-free AST should be returned as-is")


def test_hydrate_parser_symbols_skips_class_definition_without_a_name():
    nameless_class = ASTNode(NodeTypes.CLASS_DEFINITION, None, "", [], 0)
    setattr(nameless_class, "name", None)  # no name at all
    merged_ast = ASTNode(NodeTypes.ROOT, None, "root", [nameless_class], 0)

    parser_stub = types.SimpleNamespace(
        user_types=set(),
        user_class_bases={},
        user_methods={},
        user_classes={},
        user_functions={},
        user_enums={},
    )
    fp._hydrate_parser_symbols_from_merged_ast(parser_stub, merged_ast)
    # The nameless class must not have been registered anywhere.
    t.require(parser_stub.user_types == set(), parser_stub.user_types)
    t.require(parser_stub.user_classes == {}, parser_stub.user_classes)


def test_deferred_identifier_resolved_against_merged_class_definition():
    # A real, small two-file import graph: main.fire imports Helper from
    # helper.fire and references Helper by name (a static method call) --
    # the parser defers resolving the bare "Helper" identifier until after
    # import merge (since imports are present), and it should resolve
    # cleanly against the merged-in CLASS_DEFINITION with no reported
    # error (frontend_pipeline.py's deferred-identifiers loop matching a
    # class name, not a plain merged symbol).
    with t.tmpdir() as tmp:
        helper_path = os.path.join(tmp, "helper.fire")
        with open(helper_path, "w", encoding="utf-8") as f:
            f.write(
                "export class Helper {\n"
                "    static fn make() -> int32 {\n"
                "        return 5i32;\n"
                "    }\n"
                "}\n"
            )
        main_path = os.path.join(tmp, "main.fire")
        with open(main_path, "w", encoding="utf-8") as f:
            f.write(
                "import helper.Helper;\n\n"
                "x: int32 = Helper.make();\n"
            )

        src = open(main_path, encoding="utf-8").read()
        pipeline = CompilerPipeline(src, "main.fire", main_path)
        pipeline.parse()
        t.require(
            any(name == "Helper" for name, _tok in pipeline.parser_instance.deferred_undefined_identifiers),
            pipeline.parser_instance.deferred_undefined_identifiers,
        )
        pipeline.resolve_imports()
        t.require(pipeline.parser_errors == [], pipeline.parser_errors)


def test_resolve_imports_skips_symbols_import_with_unresolvable_module_path():
    # Simulates the one scenario frontend_pipeline.py's symbols-import
    # validation loop defends against: a topo module whose own "symbols"
    # import's module_path was never registered as a key in
    # resolver.modules (as can happen for a stdlib file's short relative
    # sibling import, resolved to a different, fully-dotted key during
    # loading -- see CLAUDE.md's note on short relative sibling imports).
    # That exact case only arises inside firescript/std/ itself, which
    # this test suite must not modify, so it's reproduced directly here by
    # mocking ModuleResolver.resolve_for_entry's return value.
    ext_import = ASTNode(NodeTypes.IMPORT_STATEMENT, None, "import", [], 0)
    setattr(ext_import, "module_path", "@somepkg")
    setattr(ext_import, "kind", "external")  # skips the real _load_module call
    setattr(ext_import, "alias", None)
    setattr(ext_import, "symbols", [])
    setattr(ext_import, "span", (0, 0))
    entry_ast = ASTNode(NodeTypes.ROOT, None, "root", [ext_import], 0)

    entry_path = os.path.join(REPO_ROOT, "fake_entry.fire")
    entry_mod = Module(dotted="fake_entry", path=entry_path, ast=entry_ast)

    dep_ast = ASTNode(NodeTypes.ROOT, None, "root", [], 0)
    dep_mod = Module(dotted="dep_mod", path="dep_mod.fire", ast=dep_ast)
    dep_mod.imports = [
        ImportSpec(module_path="ghost_module", kind="symbols", symbols=[{"name": "Thing", "alias": None, "index": 0}], alias=None, span=(0, 0))
    ]

    reports: list = []
    parser_stub = types.SimpleNamespace(
        deferred_undefined_identifiers=[],
        report_error=lambda *a, **k: reports.append((a, k)),
    )

    with mock.patch.object(ModuleResolver, "resolve_for_entry", return_value=(entry_mod, [entry_mod, dep_mod])):
        merged = fp.resolve_imports_and_deferred_identifiers(entry_ast, parser_stub, entry_path)

    t.require(merged.node_type == NodeTypes.ROOT, merged.node_type)
    # "ghost_module" is absent from resolver.modules, so the symbols check
    # for dep_mod's import is skipped entirely -- no UndefinedIdentifierError
    # is (incorrectly) raised for a module path lookup that never resolved.
    t.require(reports == [], reports)
