"""Shared frontend pipeline helpers for parse/import resolution.

This module centralizes lex/parse/import-merge logic so compile and lint paths
stay in sync.
"""

import os
from typing import Tuple

from lexer import Lexer
from parser import Parser, ASTNode
from enums import NodeTypes
from imports import ModuleResolver, Module, build_merged_ast


def tokenize_and_parse(source_text: str, file_path: str) -> Tuple[Parser, ASTNode, bool]:
    """Run lexer + parser and return (parser, ast, has_import_tokens)."""
    lexer = Lexer(source_text)
    tokens = lexer.tokenize()

    has_import_tokens = any(getattr(t, "type", None) == "IMPORT" for t in tokens)
    parser_instance = Parser(
        tokens,
        source_text,
        file_path,
        defer_undefined_identifiers=has_import_tokens,
    )
    ast = parser_instance.parse()
    return parser_instance, ast, has_import_tokens


def resolve_imports_and_deferred_identifiers(
    ast: ASTNode,
    parser_instance: Parser,
    file_path: str,
) -> ASTNode:
    """Resolve imports into a merged AST and validate deferred identifiers.

    Raises RuntimeError when import resolution fails.
    """
    has_imports = any(c.node_type == NodeTypes.IMPORT_STATEMENT for c in ast.children)
    if not has_imports:
        return ast

    import_root = os.path.dirname(os.path.abspath(file_path))
    resolver = ModuleResolver(import_root)

    # Reuse already-parsed entry AST to avoid reparsing entry failures.
    entry_abs = os.path.abspath(file_path)
    dotted = resolver.path_to_dotted(entry_abs)
    entry_mod_obj = Module(dotted, entry_abs, ast)
    resolver.modules[dotted] = entry_mod_obj

    for imp in entry_mod_obj.imports:
        if imp.kind != "external":
            resolver._load_module(imp.module_path, [dotted])

    entry_mod, topo = resolver.resolve_for_entry(file_path)
    merged_ast = build_merged_ast(entry_mod, topo)

    deferred = getattr(parser_instance, "deferred_undefined_identifiers", [])
    if deferred:
        merged_symbols = getattr(merged_ast, "_merged_symbols", {}) or {}
        for name, tok in deferred:
            if name in merged_symbols:
                continue
            if any(
                c.node_type == NodeTypes.CLASS_DEFINITION and getattr(c, "name", None) == name
                for c in (merged_ast.children or [])
            ):
                continue
            parser_instance.error(f"Variable '{name}' not defined", tok)

    return merged_ast
