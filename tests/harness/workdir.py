"""Isolated per-(test, matrix-cell) work directories and failure artifacts
(spec sec.3.5). Nothing is ever written into tests/ at run time except by
--update."""
from __future__ import annotations

import os
import shutil

from harness.config import RESULTS_DIR, WORK_DIR


def _category_stem(repo_relative_path: str) -> tuple[str, str]:
    """Split 'tests/sources/arrays/foo.fire' -> ('arrays', 'foo')."""
    parts = repo_relative_path.replace("\\", "/").split("/")
    stem = os.path.splitext(parts[-1])[0]
    # category = the directory name(s) between the sources/python root and the file
    if "sources" in parts:
        idx = parts.index("sources")
    elif "python" in parts:
        idx = parts.index("python")
    else:
        idx = 0
    category_parts = parts[idx + 1:-1]
    category = "/".join(category_parts) if category_parts else "_root"
    return category, stem


def _safe_name_segment(name: str) -> str:
    return name.replace("/", "_").replace("[", "(").replace("]", ")")


def work_dir_for(kind: str, cell: str, repo_relative_path: str, name: str | None = None) -> str:
    category, stem = _category_stem(repo_relative_path)
    if name and name != stem:
        stem = f"{stem}__{_safe_name_segment(name)}"
    path = os.path.join(WORK_DIR, kind, cell, category, stem)
    return path


def results_dir_for(kind: str, cell: str, repo_relative_path: str, name: str | None = None) -> str:
    category, stem = _category_stem(repo_relative_path)
    if name and name != stem:
        stem = f"{stem}__{_safe_name_segment(name)}"
    path = os.path.join(RESULTS_DIR, kind, cell, category, stem)
    return path


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def wipe_trees(keep_artifacts: bool) -> None:
    if keep_artifacts:
        return
    for d in (WORK_DIR, RESULTS_DIR):
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
