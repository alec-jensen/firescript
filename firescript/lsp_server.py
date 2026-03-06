"""
firescript Language Server

Implements the Language Server Protocol using pygls.

Provides:
  - Diagnostics (error squiggles) on open / change / save

Launch via stdio (used by the VS Code extension):
  uv run python firescript/lsp_server.py --stdio
"""

import logging
import os
import re
import sys
import urllib.request
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
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_DID_SAVE,
    Diagnostic,
    DiagnosticSeverity,
    DidChangeTextDocumentParams,
    DidOpenTextDocumentParams,
    DidSaveTextDocumentParams,
    Position,
    PublishDiagnosticsParams,
    Range,
)

from main import FIRESCRIPT_VERSION, lint_text

server = LanguageServer(
    name="firescript-language-server",
    version=FIRESCRIPT_VERSION,
)


def _uri_to_path(uri: str) -> str:
    """Convert a file:// URI to an OS-native absolute path."""
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        return urllib.request.url2pathname(unquote(parsed.path))
    return uri


def _publish_diagnostics(ls: LanguageServer, uri: str, text: str) -> None:
    """Run the firescript front-end on *text* and push diagnostics to the client."""
    file_path = _uri_to_path(uri)

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


if __name__ == "__main__":
    logging.info("firescript language server starting (stdio transport)")
    server.start_io()
