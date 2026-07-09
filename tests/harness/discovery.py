"""Discovery driver: walks kinds, expands the matrix, applies selectors
(spec sec.3.4 steps 3-4, sec.6.2)."""
from __future__ import annotations

import fnmatch
import os

from harness import kinds as kinds_pkg
from harness.config import PYTHON_TESTS_DIR, REPO_ROOT, SOURCES_DIR
from harness.matrix import select_cells
from harness.model import TestCase, TestId

# Kinds whose cases are expanded across matrix cells (spec sec.7.1).
MATRIX_KINDS = {"run", "compile-fail", "snapshot"}


def _normalize_selector_path(sel: str) -> str:
    p = sel.replace("\\", "/")
    if os.path.isabs(sel):
        p = os.path.relpath(sel, REPO_ROOT).replace(os.sep, "/")
    return p


def discover_cases(config, kind_names: list[str] | None = None) -> list[TestCase]:
    """Discover all cases for the given kinds (default: all registered),
    then expand run/compile-fail/snapshot cases across the selected matrix
    cells. Discovery-error cases (payload has 'discovery_error') are never
    matrix-expanded."""
    all_kinds = kinds_pkg.all_kinds()
    names = kind_names if kind_names is not None else list(all_kinds.keys())

    cases: list[TestCase] = []
    for name in names:
        kind_cls = all_kinds[name]
        kind = kind_cls()
        discovered = kind.discover(config)
        for case in discovered:
            if "discovery_error" in case.payload:
                cases.append(case)
                continue
            if name in MATRIX_KINDS and not config.update:
                test_key = f"{name}:{case.id.path}"
                master = config.seed or "0" * 16
                cells = select_cells(config.matrix, master, test_key)
                for cell in cells:
                    cases.append(
                        TestCase(
                            id=TestId(kind=case.id.kind, path=case.id.path, name=case.id.name, cell=cell.id),
                            directives=case.directives,
                            payload=dict(case.payload, cell_flags=cell.flags),
                        )
                    )
            else:
                cases.append(case)
    return cases


def _selector_matches(sel: str, case: TestCase) -> bool:
    tid = case.id

    if sel.startswith("kind:"):
        return tid.kind == sel[len("kind:"):]

    if sel.startswith("name:"):
        pattern = sel[len("name:"):]
        return fnmatch.fnmatch(tid.name, pattern)

    if "::" in sel:
        file_part, func_part = sel.split("::", 1)
        file_norm = _normalize_selector_path(file_part)
        return tid.path == file_norm and (tid.name == func_part or tid.name.startswith(func_part + "["))

    norm = _normalize_selector_path(sel)

    # Exact file match.
    if tid.path == norm:
        return True

    # Directory / category shorthand: match by prefix, trying the selector
    # as-is and rooted under tests/sources/ or tests/python/.
    candidates = [norm.rstrip("/") + "/"]
    if not norm.startswith("tests/"):
        candidates.append(f"tests/sources/{norm.rstrip('/')}/")
        candidates.append(f"tests/python/{norm.rstrip('/')}/")
    return any(tid.path.startswith(c) for c in candidates)


def apply_selectors(cases: list[TestCase], selectors: list[str]) -> list[TestCase]:
    if not selectors:
        return cases
    return [c for c in cases if any(_selector_matches(sel, c) for sel in selectors)]
