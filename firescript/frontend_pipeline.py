"""Shared frontend pipeline helpers for parse/import resolution.

This module centralizes lex/parse/import-merge logic so compile and lint paths
stay in sync.
"""

import os
from typing import Tuple

from lexer import Lexer, Token
from parser import Parser, ASTNode
from enums import NodeTypes
from errors import (
    UndefinedIdentifierError,
    ImportSymbolNotFoundError,
    ImportSymbolNotExportedError,
    ImportSymbolConflictError,
)
from imports import (
    ModuleResolver,
    Module,
    build_merged_ast,
    apply_symbol_aliases,
    CyclicImportException,
    ImportNotFoundException,
)

_DEFINITION_TYPES = (
    NodeTypes.FUNCTION_DEFINITION,
    NodeTypes.GENERATOR_DEFINITION,
    NodeTypes.CLASS_DEFINITION,
    NodeTypes.VARIABLE_DECLARATION,
)


def _hydrate_parser_symbols_from_merged_ast(parser_instance: Parser, merged_ast: ASTNode) -> None:
    """Populate parser symbol registries from merged AST after import resolution.

    This ensures imported classes/methods/functions are visible to subsequent
    type resolution and method-call validation.
    """
    for node in merged_ast.children or []:
        if node.node_type == NodeTypes.FUNCTION_DEFINITION:
            if getattr(node, "name", None):
                parser_instance.user_functions[node.name] = node.return_type
            continue

        if node.node_type == NodeTypes.ENUM_DEFINITION:
            enum_name = getattr(node, "name", None)
            if enum_name:
                parser_instance.user_types.add(enum_name)
                parser_instance.user_enums[enum_name] = {
                    child.name: list(getattr(child, "payload_types", []) or [])
                    for child in (node.children or [])
                    if child.node_type == NodeTypes.ENUM_VARIANT
                }
            continue

        if node.node_type != NodeTypes.CLASS_DEFINITION:
            continue

        class_name = getattr(node, "name", None)
        if not class_name:
            continue

        parser_instance.user_types.add(class_name)
        parser_instance.user_class_bases[class_name] = getattr(node, "base_class", None)

        fields: dict[str, str] = {}
        methods_sig: dict[str, dict[str, object]] = parser_instance.user_methods.get(class_name, {})

        for child in node.children or []:
            if child.node_type == NodeTypes.CLASS_FIELD:
                field_name = getattr(child, "name", None)
                if field_name:
                    fields[field_name] = getattr(child, "var_type", None)
                continue

            if child.node_type == NodeTypes.CLASS_METHOD_DEFINITION:
                param_nodes = [p for p in (child.children[:-1] if child.children else []) if p.node_type == NodeTypes.PARAMETER]
                effective_params = param_nodes[1:] if (param_nodes and getattr(param_nodes[0], "name", None) == "this") else param_nodes
                params_types = [getattr(p, "var_type", None) for p in effective_params]
                methods_sig[child.name] = {
                    "return": getattr(child, "return_type", None),
                    "params": params_types,
                    "is_static": bool(getattr(child, "is_static", False)),
                }

        parser_instance.user_classes[class_name] = fields
        parser_instance.user_methods[class_name] = methods_sig


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
    entry_mod_obj = Module(dotted=dotted, path=entry_abs, ast=ast)
    apply_symbol_aliases(entry_mod_obj)
    resolver.modules[dotted] = entry_mod_obj

    # Cycles and missing modules are reported as coded diagnostics anchored
    # at the entry file's import statement that led to them.
    # When the entry file already has syntax errors, an unresolvable import is
    # likely fallout from a malformed import statement, so it is not reported
    # separately (the merge is still skipped).
    had_parse_errors = bool(parser_instance.errors)
    load_failed = False
    for imp in entry_mod_obj.imports:
        if imp.kind == "external":
            continue
        try:
            resolver._load_module(imp.module_path, [dotted])
        except (CyclicImportException, ImportNotFoundException) as e:
            if not had_parse_errors:
                parser_instance.report_error(
                    e.error, token=Token("IMPORT", "import", imp.span[0])
                )
            load_failed = True
    if load_failed:
        return ast

    entry_mod, topo = resolver.resolve_for_entry(file_path)

    failed_import_names: set[str] = set()
    for mod in topo:
        for imp in getattr(mod, "imports", []) or []:
            if imp.kind != "symbols":
                continue
            source_mod = resolver.modules.get(imp.module_path)
            if source_mod is None:
                continue
            source_exports = source_mod.exports or {}
            defined_names = {
                getattr(c, "name", None)
                for c in source_mod.ast.children
                if c.node_type in _DEFINITION_TYPES
            }
            for symbol in imp.symbols:
                symbol_name = symbol.get("name")
                if symbol_name and symbol_name not in source_exports:
                    err_cls = (
                        ImportSymbolNotExportedError
                        if symbol_name in defined_names
                        else ImportSymbolNotFoundError
                    )
                    if mod is entry_mod:
                        failed_import_names.add(symbol_name)
                    parser_instance.report_error(
                        err_cls(
                            symbol=symbol_name,
                            module=imp.module_path,
                            source_file=mod.path,
                        ),
                        token=Token("IDENTIFIER", symbol_name, int(symbol.get("index", 0))),
                    )

    merged_ast = build_merged_ast(entry_mod, topo)

    for conflict in getattr(merged_ast, "_import_conflicts", []) or []:
        name = conflict["symbol"]
        if conflict["entry"]:
            # An entry definition silently replaces a transitively imported
            # symbol; it is only a conflict when the entry explicitly
            # imports that name.
            anchor = next(
                (
                    imp for imp in entry_mod.imports
                    if (imp.kind == "symbols" and any(s.get("name") == name for s in imp.symbols))
                    or (imp.kind == "wildcard" and imp.module_path == conflict["first"])
                ),
                None,
            )
        else:
            anchor = next(
                (imp for imp in entry_mod.imports if imp.module_path == conflict["second"]),
                entry_mod.imports[0] if entry_mod.imports else None,
            )
        if anchor is None:
            continue
        parser_instance.report_error(
            ImportSymbolConflictError(
                symbol=name,
                first=conflict["first"],
                second=conflict["second"],
                source_file=entry_mod.path,
            ),
            token=Token("IMPORT", "import", anchor.span[0]),
        )
    setattr(merged_ast, "_resolver", resolver)
    _hydrate_parser_symbols_from_merged_ast(parser_instance, merged_ast)

    deferred = getattr(parser_instance, "deferred_undefined_identifiers", [])
    if deferred:
        merged_symbols = getattr(merged_ast, "_merged_symbols", {}) or {}
        for name, tok in deferred:
            if name in merged_symbols or name in failed_import_names:
                continue
            if any(
                c.node_type == NodeTypes.CLASS_DEFINITION and getattr(c, "name", None) == name
                for c in (merged_ast.children or [])
            ):
                continue
            parser_instance.report_error(
                UndefinedIdentifierError(identifier=name, source_file=file_path),
                token=tok,
            )

    return merged_ast
