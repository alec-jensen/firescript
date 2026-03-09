"""
firescript Language Server

Implements the Language Server Protocol using pygls.

Provides:
  - Diagnostics (error squiggles) on open / change / save
  - Completion items for variables, functions, classes, keywords, and built-ins

Launch via stdio (used by the VS Code extension):
  uv run python firescript/lsp_server.py --stdio
"""

import logging
import os
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
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_DID_SAVE,
    CompletionItem,
    CompletionItemKind,
    CompletionList,
    CompletionOptions,
    CompletionParams,
    Diagnostic,
    DiagnosticSeverity,
    DidChangeTextDocumentParams,
    DidOpenTextDocumentParams,
    DidSaveTextDocumentParams,
    Position,
    PublishDiagnosticsParams,
    Range,
)

from enums import NodeTypes
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


def _walk_ast(node: ASTNode, out: list[tuple[str, CompletionItemKind, str]]) -> None:
    """Recursively collect (name, kind, detail) from all binding nodes in *node*."""
    for child in (node.children or []):
        if child is None:
            continue
        if child.node_type == NodeTypes.VARIABLE_DECLARATION and child.name:
            out.append((child.name, CompletionItemKind.Variable, child.var_type or ""))
        elif child.node_type == NodeTypes.FUNCTION_DEFINITION and child.name:
            out.append((child.name, CompletionItemKind.Function, child.var_type or ""))
        elif child.node_type == NodeTypes.CLASS_DEFINITION and child.name:
            out.append((child.name, CompletionItemKind.Class, ""))
        elif child.node_type == NodeTypes.PARAMETER and child.name:
            out.append((child.name, CompletionItemKind.Variable, child.var_type or ""))
        _walk_ast(child, out)


def _uri_to_path(uri: str) -> str:
    """Convert a file:// URI to an OS-native absolute path."""
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        return urllib.request.url2pathname(unquote(parsed.path))
    return uri


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


@server.feature(TEXT_DOCUMENT_COMPLETION, CompletionOptions())
def completion(ls: LanguageServer, params: CompletionParams) -> CompletionList:
    """Return completion items for variables, functions, classes, and keywords."""
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
        symbol_entries: list[tuple[str, CompletionItemKind, str]] = []
        _walk_ast(ast, symbol_entries)
        for name, kind, detail in symbol_entries:
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
