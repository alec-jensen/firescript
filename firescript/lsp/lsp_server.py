"""
firescript Language Server

Implements the Language Server Protocol using pygls.

Provides:
    - Diagnostics (error squiggles) on open / change / save
    - Completion items for variables, functions, classes, keywords, and built-ins
    - Hover documentation for variables, functions, and classes
    - Go-to-definition (Ctrl+click) for local symbols and imported names

Launch via stdio (used by the VS Code extension):
    uv run python firescript/lsp/lsp_server.py --stdio
"""

import logging
import os
import re
import sys
from typing import Optional

# Keep sys.path correct when run directly (i.e. not as a module).
_package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_repo_root = os.path.dirname(_package_root)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _package_root not in sys.path:
    sys.path.insert(0, _package_root)

# Redirect all logging to a file so nothing bleeds onto stdio and corrupts the
# JSON-RPC transport.
_log_path = os.path.join(os.path.expanduser("~"), ".firescript-lsp.log")
logging.basicConfig(
    filename=_log_path,
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

from pygls.lsp.server import LanguageServer
from lsprotocol.types import (
    TEXT_DOCUMENT_COMPLETION,
    TEXT_DOCUMENT_DEFINITION,
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_DID_SAVE,
    TEXT_DOCUMENT_HOVER,
    CompletionItem,
    CompletionItemKind,
    CompletionList,
    CompletionOptions,
    CompletionParams,
    DefinitionParams,
    Diagnostic,
    DiagnosticSeverity,
    DidChangeTextDocumentParams,
    DidOpenTextDocumentParams,
    DidSaveTextDocumentParams,
    Hover,
    HoverParams,
    Location,
    MarkupContent,
    MarkupKind,
    Position,
    PublishDiagnosticsParams,
    Range,
)

from firescript.lsp.lsp_symbols import (
    build_symbol_map as _build_symbol_map,
    collect_import_symbols as _collect_import_symbols,
    find_field_access_at_offset as _find_field_access_at_offset,
    find_import_definition as _find_import_definition,
    find_method_call_at_offset as _find_method_call_at_offset,
    format_hover as _format_hover,
    hover_field_access as _hover_field_access,
    hover_method_call as _hover_method_call,
    resolve_imported_symbol as _resolve_imported_symbol,
    walk_scope as _walk_scope,
)
from firescript.lsp.lsp_utils import (
    cursor_offset as _cursor_offset,
    offset_to_position as _offset_to_position,
    try_parse as _try_parse,
    uri_to_path as _uri_to_path,
    word_at_offset as _word_at_offset,
    word_start_offset as _word_start_offset,
)
from firescript.main import FIRESCRIPT_VERSION, lint_text
from firescript.parser import ASTNode

server = LanguageServer(
    name="firescript-language-server",
    version=FIRESCRIPT_VERSION,
)

# Per-document AST cache; updated whenever a document is opened or changed.
_ast_cache: dict[str, Optional[ASTNode]] = {}
_ast_version_cache: dict[str, int] = {}

# Keywords and type keywords used for static completion items.
# Note: builtin functions (stdout, drop, etc.) are intentionally excluded —
# they are either directive-gated or stdlib-imported and will appear in the
# AST when actually available in the current file.
_KEYWORDS = [
    "if", "else", "elif", "while", "for", "in", "break", "continue", "return",
    "import", "from", "new", "class", "constraint", "nullable", "generator",
    "const", "ternary", "copyable",
]
_TYPE_KEYWORDS = [
    "int8", "int16", "int32", "int64",
    "uint8", "uint16", "uint32", "uint64",
    "float32", "float64", "float128",
    "bool", "string", "void",
]


def _publish_diagnostics(ls: LanguageServer, uri: str, text: str, version: Optional[int] = None) -> None:
    """Run the firescript front-end on *text* and push diagnostics to the client."""
    file_path = _uri_to_path(uri)

    # Update the AST cache for completion use.
    # Only replace the cached AST when the parse succeeds so that the last
    # good result is preserved while the user is mid-edit.
    _parsed = _try_parse(text, file_path)
    if _parsed is not None:
        _ast_cache[uri] = _parsed
        if version is not None:
            _ast_version_cache[uri] = version

    try:
        raw_errors = lint_text(text, file_path)
    except Exception as exc:
        logging.exception("lint_text raised an unexpected exception: %s", exc)
        raw_errors = []

    source_lines = text.split("\n")
    diagnostics: list[Diagnostic] = []
    for err in raw_errors:
        message = err.message
        line = err.line
        col = err.column
        # lint_text returns 1-based line/col; LSP is 0-based.
        # When position is unavailable both are 0 — keep them at 0:0.
        lsp_line = max(0, line - 1) if line > 0 else 0
        lsp_col = max(0, col - 1) if line > 0 else 0
        # Extend the range to cover the full word/token at the error position.
        end_col = lsp_col + 1
        if lsp_line < len(source_lines):
            tail = source_lines[lsp_line][lsp_col:]
            word_match = re.match(r"\w+", tail)
            if word_match:
                end_col = lsp_col + len(word_match.group())
        start = Position(line=lsp_line, character=lsp_col)
        end = Position(line=lsp_line, character=end_col)
        diagnostics.append(
            Diagnostic(
                range=Range(start=start, end=end),
                message=message,
                severity=DiagnosticSeverity.Error,
                source="firescript",
            )
        )

    ls.text_document_publish_diagnostics(PublishDiagnosticsParams(uri=uri, diagnostics=diagnostics))


def _get_ast_for_document(
    uri: str,
    source: str,
    file_path: str,
    version: Optional[int],
) -> Optional[ASTNode]:
    """Return a best-effort AST while avoiding reparsing unchanged document versions."""
    cached_ast = _ast_cache.get(uri)
    if version is not None and _ast_version_cache.get(uri) == version and cached_ast is not None:
        return cached_ast

    parsed = _try_parse(source, file_path)
    if parsed is not None:
        _ast_cache[uri] = parsed
        if version is not None:
            _ast_version_cache[uri] = version
        return parsed

    return cached_ast


@server.feature(TEXT_DOCUMENT_DID_OPEN)
def did_open(ls: LanguageServer, params: DidOpenTextDocumentParams) -> None:
    _publish_diagnostics(
        ls,
        params.text_document.uri,
        params.text_document.text,
        getattr(params.text_document, "version", None),
    )


@server.feature(TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls: LanguageServer, params: DidChangeTextDocumentParams) -> None:
    # Full-document sync: the last entry is the complete current text.
    text = params.content_changes[-1].text
    _publish_diagnostics(
        ls,
        params.text_document.uri,
        text,
        getattr(params.text_document, "version", None),
    )


@server.feature(TEXT_DOCUMENT_DID_SAVE)
def did_save(ls: LanguageServer, params: DidSaveTextDocumentParams) -> None:
    # Diagnostics were already published on the last didChange; nothing to do.
    pass


@server.feature(TEXT_DOCUMENT_HOVER)
def hover(ls: LanguageServer, params: HoverParams) -> Optional[Hover]:
    """Return type/signature documentation when the user hovers over a symbol."""
    uri = params.text_document.uri
    pos = params.position

    try:
        doc = ls.workspace.get_text_document(uri)
        source = doc.source
        doc_version: Optional[int] = getattr(doc, "version", None)
    except Exception:
        return None

    file_path = _uri_to_path(uri)
    ast = _get_ast_for_document(uri, source, file_path, doc_version)
    if ast is None:
        return None

    cursor_off = _cursor_offset(source, pos.line, pos.character)
    word = _word_at_offset(source, cursor_off)
    if not word:
        return None

    sym_map: dict[str, ASTNode] = {}
    _build_symbol_map(ast, sym_map)

    # Try field-access hover first: resolve concrete type for  t1.field
    fa_node = _find_field_access_at_offset(ast, cursor_off)
    if fa_node is not None:
        fa_content = _hover_field_access(fa_node, ast, sym_map, file_path)
        if fa_content:
            word_start = _word_start_offset(source, cursor_off)
            fa_range = Range(
                start=_offset_to_position(source, word_start),
                end=_offset_to_position(source, word_start + len(word)),
            )
            return Hover(
                contents=MarkupContent(kind=MarkupKind.Markdown, value=fa_content),
                range=fa_range,
            )

    # Try method-call hover: show concrete method signature for  obj.method()
    mc_node = _find_method_call_at_offset(ast, cursor_off)
    if mc_node is not None:
        mc_content = _hover_method_call(mc_node, ast, sym_map, file_path)
        if mc_content:
            word_start = _word_start_offset(source, cursor_off)
            mc_range = Range(
                start=_offset_to_position(source, word_start),
                end=_offset_to_position(source, word_start + len(word)),
            )
            return Hover(
                contents=MarkupContent(kind=MarkupKind.Markdown, value=mc_content),
                range=mc_range,
            )

    node = sym_map.get(word)

    # Fall back to imported modules if the symbol isn't defined locally.
    if node is None:
        result = _resolve_imported_symbol(ast, word, file_path)
        if result is not None:
            _mod_file, _mod_text, node = result

    if node is None:
        return None

    content = _format_hover(node)
    if not content:
        return None

    word_start = _word_start_offset(source, cursor_off)
    hover_range = Range(
        start=_offset_to_position(source, word_start),
        end=_offset_to_position(source, word_start + len(word)),
    )
    return Hover(
        contents=MarkupContent(kind=MarkupKind.Markdown, value=content),
        range=hover_range,
    )


@server.feature(TEXT_DOCUMENT_DEFINITION)
def goto_definition(ls: LanguageServer, params: DefinitionParams) -> Optional[Location]:
    """Jump to the definition of the symbol under the cursor (Ctrl+click)."""
    uri = params.text_document.uri
    pos = params.position

    try:
        doc = ls.workspace.get_text_document(uri)
        source = doc.source
        doc_version: Optional[int] = getattr(doc, "version", None)
    except Exception:
        return None

    file_path = _uri_to_path(uri)
    ast = _get_ast_for_document(uri, source, file_path, doc_version)
    if ast is None:
        return None

    cursor_off = _cursor_offset(source, pos.line, pos.character)
    word = _word_at_offset(source, cursor_off)
    if not word:
        return None

    # Check current file first.
    sym_map: dict[str, ASTNode] = {}
    _build_symbol_map(ast, sym_map)
    node = sym_map.get(word)
    if node is not None:
        def_pos = _offset_to_position(source, node.index)
        def_end = Position(line=def_pos.line, character=def_pos.character + len(word))
        return Location(uri=uri, range=Range(start=def_pos, end=def_end))

    # Fall back to imported modules.
    result = _find_import_definition(ast, word, file_path)
    if result is not None:
        mod_uri, def_pos = result
        def_end = Position(line=def_pos.line, character=def_pos.character + len(word))
        return Location(uri=mod_uri, range=Range(start=def_pos, end=def_end))

    return None


@server.feature(TEXT_DOCUMENT_COMPLETION, CompletionOptions())
def completion(ls: LanguageServer, params: CompletionParams) -> CompletionList:
    """Return completion items for variables, functions, classes, imports, and keywords.

    Only symbols that are in scope and declared before the cursor are included.
    Imported names are resolved from the referenced module files.
    """
    items: list[CompletionItem] = []
    seen: set[str] = set()

    def _add(name: str, kind: CompletionItemKind, detail: str = "") -> None:
        if name and name not in seen:
            seen.add(name)
            items.append(CompletionItem(label=name, kind=kind, detail=detail or None))

    uri = params.text_document.uri

    # Always parse the current workspace text so symbols are up-to-date.
    # Fall back to the cached AST only when the workspace document is unavailable.
    try:
        doc = ls.workspace.get_text_document(uri)
        current_text = doc.source
        doc_version: Optional[int] = getattr(doc, "version", None)
    except Exception:
        current_text = None
        doc_version = None

    file_path = _uri_to_path(uri)
    if current_text:
        ast = _get_ast_for_document(uri, current_text, file_path, doc_version)
    else:
        ast = _ast_cache.get(uri)

    if ast is not None:
        pos = params.position
        cursor_off = _cursor_offset(current_text or "", pos.line, pos.character)

        symbol_entries: list[tuple[str, CompletionItemKind, str]] = []
        _walk_scope(ast, current_text or "", cursor_off, symbol_entries, in_scope=True)
        for name, kind, detail in symbol_entries:
            _add(name, kind, detail)

        import_entries: list[tuple[str, CompletionItemKind, str]] = []
        _collect_import_symbols(ast, file_path, import_entries)
        for name, kind, detail in import_entries:
            _add(name, kind, detail)

    # Type keywords.
    for kw in _TYPE_KEYWORDS:
        _add(kw, CompletionItemKind.Keyword)

    # Control-flow and other keywords.
    for kw in _KEYWORDS:
        _add(kw, CompletionItemKind.Keyword)

    return CompletionList(is_incomplete=False, items=items)


if __name__ == "__main__":
    logging.info("firescript language server starting (stdio transport)")
    server.start_io()
