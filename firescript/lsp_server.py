"""
firescript Language Server

Implements the Language Server Protocol using pygls.

Provides:
  - Diagnostics (error squiggles) on open / change / save
  - Completion items for variables, functions, classes, keywords, and built-ins
  - Hover documentation for variables, functions, and classes
  - Go-to-definition (Ctrl+click) for local symbols and imported names

Launch via stdio (used by the VS Code extension):
  uv run python firescript/lsp_server.py --stdio
"""

import logging
import os
import pathlib
import re
import sys
import urllib.request
from typing import Optional
from urllib.parse import urlparse, unquote

# Keep sys.path correct when run directly (i.e. not as a module).
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

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

from enums import NodeTypes
from imports import ModuleResolver
from lexer import Lexer
from parser import ASTNode, Parser
from main import FIRESCRIPT_VERSION, lint_text

server = LanguageServer(
    name="firescript-language-server",
    version=FIRESCRIPT_VERSION,
)

# Per-document AST cache; updated whenever a document is opened or changed.
_ast_cache: dict[str, Optional[ASTNode]] = {}

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
    "bool", "string", "tuple", "void",
]


def _try_parse(text: str, file_path: str) -> Optional[ASTNode]:
    """Lex and parse *text*; return the AST root, or None on hard failure.

    Errors emitted by the parser are intentionally swallowed here — we only
    need a best-effort AST for completion purposes.  If the post-parse
    analysis steps (resolve_variable_types, type_check) throw, we still
    return the partial AST that was built so symbols are available.
    Returns None when the text is empty or produces no tokens.
    """
    root_logger = logging.getLogger()
    prev_level = root_logger.level
    root_logger.setLevel(logging.CRITICAL + 1)
    try:
        lexer = Lexer(text)
        tokens = lexer.tokenize()
        if not tokens:
            return None
        parser_instance = Parser(tokens, text, file_path)
        try:
            return parser_instance.parse()
        except Exception:
            # parse() may have thrown after building part of the AST (e.g.
            # during resolve_variable_types).  Return whatever was collected.
            return parser_instance.ast
    except Exception:
        return None
    finally:
        root_logger.setLevel(prev_level)


def _find_block_end(source: str, from_pos: int) -> int:
    """Return the index of the } that closes the first { at or after from_pos.

    Skips string literals and line comments to avoid false positives.
    Returns len(source) when no matching brace is found.
    """
    i = source.find("{", from_pos)
    if i == -1:
        return len(source)
    i += 1  # move past the opening brace
    depth = 1
    while i < len(source) and depth > 0:
        c = source[i]
        if c == '"':
            i += 1
            while i < len(source) and source[i] != '"':
                if source[i] == '\\':
                    i += 1
                i += 1
        elif c == '/' and i + 1 < len(source) and source[i + 1] == '/':
            while i < len(source) and source[i] != '\n':
                i += 1
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return len(source)


def _cursor_offset(source: str, line: int, character: int) -> int:
    """Convert a 0-based (line, character) LSP position to a source character offset."""
    lines = source.split("\n")
    return sum(len(lines[i]) + 1 for i in range(min(line, len(lines)))) + character


def _walk_scope(
    node: ASTNode,
    source: str,
    cursor_offset: int,
    out: list[tuple[str, CompletionItemKind, str]],
    in_scope: bool,
) -> None:
    """Recursively collect symbols visible at cursor_offset.

    in_scope — True when the cursor is inside this node's lexical scope.
    Symbols from sibling scopes that do not contain the cursor are excluded.
    """
    for child in (node.children or []):
        if child is None:
            continue

        if child.node_type == NodeTypes.VARIABLE_DECLARATION:
            if in_scope and child.name and child.index <= cursor_offset:
                out.append((child.name, CompletionItemKind.Variable, child.var_type or ""))

        elif child.node_type == NodeTypes.FUNCTION_DEFINITION:
            if in_scope and child.name:
                # Functions are hoisted — visible anywhere in the containing scope.
                out.append((child.name, CompletionItemKind.Function, child.return_type or child.var_type or ""))
            fn_end = _find_block_end(source, child.index)
            cursor_inside = child.index <= cursor_offset <= fn_end
            _walk_scope(child, source, cursor_offset, out, in_scope=cursor_inside)

        elif child.node_type == NodeTypes.CLASS_DEFINITION:
            if in_scope and child.name:
                out.append((child.name, CompletionItemKind.Class, ""))
            # Don't recurse into class bodies — fields/methods are not in scope outside them.

        elif child.node_type == NodeTypes.PARAMETER:
            if in_scope and child.name:
                out.append((child.name, CompletionItemKind.Variable, child.var_type or ""))

        elif child.node_type == NodeTypes.SCOPE:
            scope_end = _find_block_end(source, child.index)
            cursor_inside = child.index <= cursor_offset <= scope_end
            _walk_scope(child, source, cursor_offset, out, in_scope=cursor_inside)

        else:
            _walk_scope(child, source, cursor_offset, out, in_scope=in_scope)


def _collect_import_symbols(
    ast_root: ASTNode,
    file_path: str,
    out: list[tuple[str, CompletionItemKind, str]],
) -> None:
    """Collect completion items for names introduced by import statements."""
    import_root = os.path.dirname(os.path.abspath(file_path)) if file_path else None
    try:
        resolver = ModuleResolver(import_root)
    except Exception:
        return

    for child in (ast_root.children or []):
        if child is None or child.node_type != NodeTypes.IMPORT_STATEMENT:
            continue

        module_path: str = getattr(child, "module_path", "") or ""
        kind: str = getattr(child, "kind", "module") or "module"
        alias: Optional[str] = getattr(child, "alias", None)
        symbols: list[dict] = getattr(child, "symbols", []) or []

        if kind == "external" or not module_path:
            continue

        try:
            if kind == "module":
                name = alias or module_path.rsplit(".", 1)[-1]
                out.append((name, CompletionItemKind.Module, module_path))
                continue

            mod_file = resolver.dotted_to_path(module_path)
            if not os.path.isfile(mod_file):
                continue
            with open(mod_file, "r", encoding="utf-8") as f:
                mod_text = f.read()
            mod_ast = _try_parse(mod_text, mod_file)
            if mod_ast is None:
                continue

            exports: dict[str, tuple[CompletionItemKind, str]] = {}
            for node in (mod_ast.children or []):
                if node is None or not node.name:
                    continue
                if node.node_type == NodeTypes.FUNCTION_DEFINITION:
                    exports[node.name] = (CompletionItemKind.Function, node.return_type or node.var_type or "")
                elif node.node_type == NodeTypes.CLASS_DEFINITION:
                    exports[node.name] = (CompletionItemKind.Class, "")
                elif node.node_type == NodeTypes.VARIABLE_DECLARATION:
                    exports[node.name] = (CompletionItemKind.Variable, node.var_type or "")

            if kind == "wildcard":
                for name, (item_kind, detail) in exports.items():
                    out.append((name, item_kind, detail))
            elif kind == "symbols":
                for sym in symbols:
                    sym_name = sym.get("name", "")
                    sym_alias = sym.get("alias") or sym_name
                    if sym_name in exports:
                        item_kind, detail = exports[sym_name]
                        out.append((sym_alias, item_kind, detail))
                    elif sym_name:
                        out.append((sym_alias, CompletionItemKind.Function, ""))
        except Exception:
            pass


def _uri_to_path(uri: str) -> str:
    """Convert a file:// URI to an OS-native absolute path."""
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        return urllib.request.url2pathname(unquote(parsed.path))
    return uri


def _path_to_uri(path: str) -> str:
    """Convert an OS-native absolute path to a file:// URI."""
    return pathlib.Path(os.path.abspath(path)).as_uri()


def _offset_to_position(source: str, offset: int) -> Position:
    """Convert a character offset to a 0-based LSP Position."""
    text_before = source[:max(0, offset)]
    lines = text_before.split("\n")
    return Position(line=len(lines) - 1, character=len(lines[-1]))


def _word_at_offset(source: str, offset: int) -> str:
    """Return the identifier word that contains (or is immediately before) offset."""
    offset = min(offset, len(source))
    start = offset
    while start > 0 and (source[start - 1].isalnum() or source[start - 1] == "_"):
        start -= 1
    end = offset
    while end < len(source) and (source[end].isalnum() or source[end] == "_"):
        end += 1
    return source[start:end]


def _word_start_offset(source: str, offset: int) -> int:
    """Return the character offset of the beginning of the identifier at offset."""
    offset = min(offset, len(source))
    while offset > 0 and (source[offset - 1].isalnum() or source[offset - 1] == "_"):
        offset -= 1
    return offset


def _build_symbol_map(node: ASTNode, out: dict[str, ASTNode]) -> None:
    """Recursively populate out with name -> ASTNode for all binding nodes.

    First definition wins — inner scopes do not shadow outer ones in the map,
    since we only need to find *a* definition for hover/goto purposes.
    """
    for child in (node.children or []):
        if child is None:
            continue
        if child.node_type in (
            NodeTypes.VARIABLE_DECLARATION,
            NodeTypes.FUNCTION_DEFINITION,
            NodeTypes.CLASS_DEFINITION,
            NodeTypes.PARAMETER,
        ) and child.name:
            if child.name not in out:
                out[child.name] = child
        _build_symbol_map(child, out)


def _format_hover(node: ASTNode) -> str:
    """Return a Markdown code-fenced hover string for a symbol node."""
    if node.node_type == NodeTypes.FUNCTION_DEFINITION:
        params = [
            c for c in (node.children or [])
            if c is not None and c.node_type == NodeTypes.PARAMETER
        ]
        param_strs = []
        for p in params:
            t = p.var_type or "?"
            arr = "[]" if getattr(p, "is_array", False) else ""
            ref = "&" if getattr(p, "is_ref", False) else ""
            param_strs.append(f"{ref}{t}{arr} {p.name}")
        ret = node.var_type or node.return_type or "void"
        arr = "[]" if getattr(node, "is_array", False) else ""
        return f"```firescript\n{ret}{arr} {node.name}({', '.join(param_strs)})\n```"
    elif node.node_type == NodeTypes.CLASS_DEFINITION:
        return f"```firescript\nclass {node.name}\n```"
    elif node.node_type in (NodeTypes.VARIABLE_DECLARATION, NodeTypes.PARAMETER):
        mods = ""
        if getattr(node, "is_const", False):
            mods += "const "
        if getattr(node, "is_nullable", False):
            mods += "nullable "
        t = node.var_type or "?"
        arr = "[]" if getattr(node, "is_array", False) else ""
        decl = f"{mods}{t}{arr} {node.name}"
        if getattr(node, "is_const", False):
            value_node = next(
                (c for c in (node.children or [])
                 if c is not None and c.node_type not in (NodeTypes.PARAMETER,) and getattr(c, "token", None) is not None),
                None,
            )
            if value_node is not None:
                decl += f" = {value_node.token.value}"
        return f"```firescript\n{decl}\n```"
    return ""


def _resolve_imported_symbol(
    ast_root: ASTNode,
    word: str,
    file_path: str,
) -> Optional[tuple[str, str, ASTNode]]:
    """Resolve an imported name to its definition.

    Returns (mod_file_path, mod_text, ASTNode) for the definition of *word* in
    any imported module, or None if the name is not imported or can't be resolved.
    """
    import_root = os.path.dirname(os.path.abspath(file_path)) if file_path else None
    try:
        resolver = ModuleResolver(import_root)
    except Exception:
        return None

    for child in (ast_root.children or []):
        if child is None or child.node_type != NodeTypes.IMPORT_STATEMENT:
            continue

        module_path: str = getattr(child, "module_path", "") or ""
        kind: str = getattr(child, "kind", "module") or "module"
        symbols: list[dict] = getattr(child, "symbols", []) or []

        if kind == "external" or not module_path or kind == "module":
            continue

        target_name: Optional[str] = None
        if kind == "wildcard":
            target_name = word
        elif kind == "symbols":
            for sym in symbols:
                alias = sym.get("alias") or sym.get("name", "")
                if alias == word:
                    target_name = sym.get("name", "")
                    break

        if not target_name:
            continue

        try:
            mod_file = resolver.dotted_to_path(module_path)
            if not os.path.isfile(mod_file):
                continue
            with open(mod_file, "r", encoding="utf-8") as f:
                mod_text = f.read()
            mod_ast = _try_parse(mod_text, mod_file)
            if mod_ast is None:
                continue
            sym_map: dict[str, ASTNode] = {}
            _build_symbol_map(mod_ast, sym_map)
            def_node = sym_map.get(target_name)
            if def_node is None:
                continue
            return (mod_file, mod_text, def_node)
        except Exception:
            pass

    return None


def _find_import_definition(
    ast_root: ASTNode,
    word: str,
    file_path: str,
) -> Optional[tuple[str, Position]]:
    """Return (file_uri, Position) of the definition of word in an imported module."""
    result = _resolve_imported_symbol(ast_root, word, file_path)
    if result is None:
        return None
    mod_file, mod_text, def_node = result
    def_pos = _offset_to_position(mod_text, def_node.index)
    return (_path_to_uri(mod_file), def_pos)


def _publish_diagnostics(ls: LanguageServer, uri: str, text: str) -> None:
    """Run the firescript front-end on *text* and push diagnostics to the client."""
    file_path = _uri_to_path(uri)

    # Update the AST cache for completion use.
    # Only replace the cached AST when the parse succeeds so that the last
    # good result is preserved while the user is mid-edit.
    _parsed = _try_parse(text, file_path)
    if _parsed is not None:
        _ast_cache[uri] = _parsed

    try:
        raw_errors = lint_text(text, file_path)
    except Exception as exc:
        logging.exception("lint_text raised an unexpected exception: %s", exc)
        raw_errors = []

    source_lines = text.split("\n")
    diagnostics: list[Diagnostic] = []
    for message, line, col in raw_errors:
        # lint_text returns 1-based line/col; LSP is 0-based.
        # When position is unavailable both are 0 — keep them at 0:0.
        lsp_line = max(0, line - 1) if line > 0 else 0
        lsp_col = max(0, col) if line > 0 else 0
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


@server.feature(TEXT_DOCUMENT_DID_OPEN)
def did_open(ls: LanguageServer, params: DidOpenTextDocumentParams) -> None:
    _publish_diagnostics(ls, params.text_document.uri, params.text_document.text)


@server.feature(TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls: LanguageServer, params: DidChangeTextDocumentParams) -> None:
    # Full-document sync: the last entry is the complete current text.
    text = params.content_changes[-1].text
    _publish_diagnostics(ls, params.text_document.uri, text)


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
    except Exception:
        return None

    file_path = _uri_to_path(uri)
    ast = _try_parse(source, file_path)
    if ast is None:
        ast = _ast_cache.get(uri)
    if ast is None:
        return None

    cursor_off = _cursor_offset(source, pos.line, pos.character)
    word = _word_at_offset(source, cursor_off)
    if not word:
        return None

    sym_map: dict[str, ASTNode] = {}
    _build_symbol_map(ast, sym_map)
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
    except Exception:
        return None

    file_path = _uri_to_path(uri)
    ast = _try_parse(source, file_path)
    if ast is None:
        ast = _ast_cache.get(uri)
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
    except Exception:
        current_text = None

    file_path = _uri_to_path(uri)
    if current_text:
        ast = _try_parse(current_text, file_path)
        if ast is not None:
            _ast_cache[uri] = ast
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
