"""Compatibility wrapper for the firescript language server entrypoint."""

import os
import sys

_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from firescript.lsp.lsp_server import server


if __name__ == "__main__":
    server.start_io()
