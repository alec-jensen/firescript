#!/usr/bin/env python3
"""Codebase analytics for firescript.

Walks the whole repository and reports as many statistics as it
reasonably can: lines of code per language (with a blank/comment/code
split for Python and firescript), test-suite counts, symbol counts
(functions/classes/enums/directives), TODO markers, largest files,
per-directory breakdowns, and git history stats.

Usage:
    python scripts/analyze_codebase.py
    python scripts/analyze_codebase.py --json report.json
    python scripts/analyze_codebase.py --top 20

Stdlib only, no external dependencies. The blank/comment/code split is a
simple line-prefix heuristic (not a real tokenizer) -- treat it as
approximate, not authoritative.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent

# Directories we never want to walk into (build artifacts / dependency
# trees / caches, not hand-written source).
EXCLUDE_DIR_NAMES = {
    "__pycache__", "build", "node_modules", "dist", "egg-info", "out",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
}

LANGUAGE_NAMES = {
    ".py": "Python",
    ".fire": "firescript",
    ".md": "Markdown",
    ".fir": "FIR (IR snapshot)",
    ".flir": "FLIR (IR snapshot)",
}

# Highlighted first in the per-language table, in this order; everything
# else found in the repo is appended after, sorted by line count.
HIGHLIGHTED_EXTENSIONS = [".py", ".fire", ".md", ".fir", ".flir"]

LINE_COMMENT_PREFIXES = {".py": "#", ".fire": "//"}
BLOCK_COMMENT_DELIMS = {".fire": ("/*", "*/")}

TODO_RE = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")
FIRE_FN_RE = re.compile(r"^\s*fn\s+\w+", re.MULTILINE)
FIRE_CLASS_RE = re.compile(r"^\s*(copyable\s+)?class\s+\w+", re.MULTILINE)
FIRE_ENUM_RE = re.compile(r"^\s*enum\s+\w+", re.MULTILINE)
FIRE_DIRECTIVE_RE = re.compile(r"^\s*directive\s+\w+", re.MULTILINE)
FIRE_IMPORT_RE = re.compile(r"^\s*import\s+", re.MULTILINE)
FIRE_BUILTIN_METHOD_RE = re.compile(r"@builtin_method\(")
PY_TEST_FN_RE = re.compile(r"^def (test_\w+)", re.MULTILINE)


@dataclass
class FileStats:
    path: Path
    ext: str
    size_bytes: int = 0
    total_lines: int = 0
    blank_lines: int = 0
    comment_lines: int = 0
    code_lines: int = 0


def should_skip_dir(name: str) -> bool:
    return name.startswith(".") or name in EXCLUDE_DIR_NAMES


def iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]
        for fname in filenames:
            yield Path(dirpath) / fname


def analyze_lines(lines: list[str], ext: str) -> tuple[int, int, int]:
    """Return (blank, comment, code) line counts. Heuristic, not a real parser."""
    blank = comment = code = 0
    line_prefix = LINE_COMMENT_PREFIXES.get(ext)
    block = BLOCK_COMMENT_DELIMS.get(ext)
    in_block = False
    for raw in lines:
        s = raw.strip()
        if not s:
            blank += 1
            continue
        if in_block:
            comment += 1
            if block[1] in s:
                in_block = False
            continue
        if block and s.startswith(block[0]):
            comment += 1
            if block[1] not in s[len(block[0]):]:
                in_block = True
            continue
        if line_prefix and s.startswith(line_prefix):
            comment += 1
            continue
        code += 1
    return blank, comment, code


def analyze_file(path: Path) -> Optional[FileStats]:
    ext = path.suffix.lower()
    try:
        size = path.stat().st_size
    except OSError:
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        # Binary or unreadable: still counted in file/size totals, not in
        # line-based stats.
        return FileStats(path=path, ext=ext, size_bytes=size)
    lines = text.splitlines()
    blank, comment, code = analyze_lines(lines, ext)
    return FileStats(
        path=path, ext=ext, size_bytes=size,
        total_lines=len(lines), blank_lines=blank,
        comment_lines=comment, code_lines=code,
    )


# --------------------------------------------------------------------------
# Section analyzers
# --------------------------------------------------------------------------

def python_symbol_counts(paths: list[Path]) -> dict:
    functions = classes = async_functions = 0
    import_lines = 0
    for p in paths:
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                async_functions += 1
            elif isinstance(node, ast.FunctionDef):
                functions += 1
            elif isinstance(node, ast.ClassDef):
                classes += 1
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                import_lines += 1
    return {
        "functions": functions,
        "async_functions": async_functions,
        "classes": classes,
        "import_statements": import_lines,
    }


def fire_symbol_counts(paths: list[Path]) -> dict:
    counts = Counter()
    for p in paths:
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        counts["functions"] += len(FIRE_FN_RE.findall(text))
        counts["classes"] += len(FIRE_CLASS_RE.findall(text))
        counts["enums"] += len(FIRE_ENUM_RE.findall(text))
        counts["directives"] += len(FIRE_DIRECTIVE_RE.findall(text))
        counts["import_statements"] += len(FIRE_IMPORT_RE.findall(text))
        counts["builtin_method_decorators"] += len(FIRE_BUILTIN_METHOD_RE.findall(text))
    return dict(counts)


def todo_scan(all_stats: list[FileStats]) -> tuple[int, list[tuple[str, int]]]:
    per_file = []
    total = 0
    this_script = Path(__file__).resolve()
    for fs in all_stats:
        if fs.ext not in (".py", ".fire", ".md"):
            continue
        if fs.path.resolve() == this_script:
            # This script's own source literally contains the marker
            # words (in TODO_RE's pattern and this comment) -- exclude it
            # from its own scan so the report reflects the rest of the
            # codebase, not itself.
            continue
        try:
            text = fs.path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        n = len(TODO_RE.findall(text))
        if n:
            per_file.append((str(fs.path.relative_to(REPO_ROOT)), n))
            total += n
    per_file.sort(key=lambda t: t[1], reverse=True)
    return total, per_file


def test_suite_analytics(root: Path) -> dict:
    tests_dir = root / "tests"
    result: dict = {}

    py_test_files = sorted((tests_dir / "python").rglob("test_*.py")) if (tests_dir / "python").exists() else []
    test_fn_count = 0
    for p in py_test_files:
        try:
            test_fn_count += len(PY_TEST_FN_RE.findall(p.read_text(encoding="utf-8")))
        except (UnicodeDecodeError, OSError):
            pass
    result["python_test_files"] = len(py_test_files)
    result["python_test_functions"] = test_fn_count

    sources_dir = tests_dir / "sources"
    invalid_dir = sources_dir / "invalid"

    def category_counts(base: Path, skip: Optional[Path] = None) -> Counter:
        c: Counter = Counter()
        if not base.exists():
            return c
        for p in base.rglob("*.fire"):
            if skip is not None and skip in p.parents:
                continue
            rel = p.relative_to(base)
            category = rel.parts[0] if len(rel.parts) > 1 else "(root)"
            c[category] += 1
        return c

    valid_categories = category_counts(sources_dir, skip=invalid_dir)
    invalid_categories = category_counts(invalid_dir) if invalid_dir.exists() else Counter()

    result["fire_run_snapshot_sources"] = sum(valid_categories.values())
    result["fire_compile_fail_sources"] = sum(invalid_categories.values())
    result["fire_source_categories"] = valid_categories.most_common()
    result["fire_invalid_categories"] = invalid_categories.most_common()

    snapshots_dir = tests_dir / "snapshots"
    if snapshots_dir.exists():
        fir_files = list(snapshots_dir.rglob("*.fir"))
        flir_files = list(snapshots_dir.rglob("*.flir"))
    else:
        fir_files, flir_files = [], []
    result["snapshot_fir_files"] = len(fir_files)
    result["snapshot_flir_files"] = len(flir_files)

    result["total_fire_test_sources"] = result["fire_run_snapshot_sources"] + result["fire_compile_fail_sources"]
    return result


def git_stats(root: Path) -> Optional[dict]:
    def run(args: list[str]) -> Optional[str]:
        try:
            proc = subprocess.run(
                ["git", *args], cwd=root, capture_output=True, text=True, timeout=15,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if proc.returncode != 0:
            return None
        return proc.stdout.strip()

    if run(["rev-parse", "--is-inside-work-tree"]) != "true":
        return None

    stats: dict = {}
    stats["branch"] = run(["rev-parse", "--abbrev-ref", "HEAD"])
    commit_count = run(["rev-list", "--count", "HEAD"])
    stats["commit_count"] = int(commit_count) if commit_count and commit_count.isdigit() else None

    # NOTE: `git log --reverse -1` does NOT give the oldest commit -- `-1`
    # limits the walk to the newest commit *before* --reverse reorders it,
    # so it silently returns the same commit as plain `-1` would. Fetch
    # the full reversed history and take the first line instead.
    reversed_log = run(["log", "--reverse", "--format=%ad", "--date=short"])
    first_log = reversed_log.splitlines()[0] if reversed_log else None
    last_log = run(["log", "-1", "--format=%ad", "--date=short"])
    stats["first_commit_date"] = first_log
    stats["last_commit_date"] = last_log

    # Deliberately HEAD-only (not --all): this repo accumulates many
    # throwaway `worktree-agent-*`/dependabot branches that aren't part of
    # the project's real history, and --all pulled them in, over-counting
    # commits and even producing a blank-author entry from them. Keeping
    # every git query scoped to HEAD keeps the numbers mutually consistent.
    shortlog = run(["shortlog", "-sn", "HEAD"])
    contributors = []
    if shortlog:
        for line in shortlog.splitlines():
            parts = line.strip().split("\t", 1)
            if len(parts) == 2 and parts[1].strip():
                contributors.append((parts[1].strip(), int(parts[0])))
    stats["contributors"] = contributors

    uncommitted = run(["status", "--porcelain"])
    stats["uncommitted_changes"] = len(uncommitted.splitlines()) if uncommitted else 0
    return stats


# --------------------------------------------------------------------------
# Report rendering
# --------------------------------------------------------------------------

def print_header(title: str) -> None:
    print()
    print(title)
    print("=" * len(title))


def print_table(headers: list[str], rows: list[list], align_right: Optional[set] = None) -> None:
    align_right = align_right or set()
    str_rows = [[str(c) for c in row] for row in rows]
    widths = [len(h) for h in headers]
    for row in str_rows:
        for i, c in enumerate(row):
            widths[i] = max(widths[i], len(c))

    def fmt_row(row):
        cells = []
        for i, c in enumerate(row):
            cells.append(c.rjust(widths[i]) if i in align_right else c.ljust(widths[i]))
        return "  ".join(cells).rstrip()

    print(fmt_row(headers))
    print(fmt_row(["-" * w for w in widths]))
    for row in str_rows:
        print(fmt_row(row))


def human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", metavar="PATH", help="also write the full report as JSON to this path")
    parser.add_argument("--top", type=int, default=15, help="row count for 'top N' tables (default: 15)")
    args = parser.parse_args()

    print(f"Analyzing {REPO_ROOT} ...")
    all_paths = list(iter_files(REPO_ROOT))
    all_stats = [s for s in (analyze_file(p) for p in all_paths) if s is not None]

    by_ext: dict[str, list[FileStats]] = defaultdict(list)
    for fs in all_stats:
        by_ext[fs.ext].append(fs)

    total_files = len(all_stats)
    total_lines = sum(fs.total_lines for fs in all_stats)
    total_size = sum(fs.size_bytes for fs in all_stats)
    total_dirs = 0
    for dirpath, dirnames, _ in os.walk(REPO_ROOT):
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]
        total_dirs += len(dirnames)

    # ---- Repository overview -------------------------------------------
    print_header("Repository Overview")
    print(f"Root:              {REPO_ROOT}")
    print(f"Total files:       {total_files:,}")
    print(f"Total directories: {total_dirs:,}")
    print(f"Total lines:       {total_lines:,}")
    print(f"Total size:        {human_size(total_size)}")
    print(f"Distinct file exts:{len(by_ext):>5}")

    git = git_stats(REPO_ROOT)
    if git:
        print(f"Git branch:        {git['branch']}")
        print(f"Git commits:       {git['commit_count']:,}" if git["commit_count"] else "Git commits:       n/a")
        print(f"First commit:      {git['first_commit_date']}")
        print(f"Last commit:       {git['last_commit_date']}")
        print(f"Uncommitted files: {git['uncommitted_changes']}")
        if git["contributors"]:
            top_contrib = ", ".join(f"{name} ({n})" for name, n in git["contributors"][:5])
            print(f"Top contributors:  {top_contrib}")

    # ---- Lines of code by language --------------------------------------
    print_header("Lines of Code by Language")
    rows = []
    seen = set()
    ext_order = HIGHLIGHTED_EXTENSIONS + sorted(
        (e for e in by_ext if e not in HIGHLIGHTED_EXTENSIONS),
        key=lambda e: sum(fs.total_lines for fs in by_ext[e]),
        reverse=True,
    )
    for ext in ext_order:
        if ext in seen or ext not in by_ext:
            continue
        seen.add(ext)
        files = by_ext[ext]
        name = LANGUAGE_NAMES.get(ext, ext or "(no ext)")
        code = sum(f.code_lines for f in files)
        comment = sum(f.comment_lines for f in files)
        blank = sum(f.blank_lines for f in files)
        total = sum(f.total_lines for f in files)
        rows.append([name, len(files), code, comment, blank, total])
    print_table(
        ["Language", "Files", "Code", "Comment", "Blank", "Total"],
        rows,
        align_right={1, 2, 3, 4, 5},
    )

    grand_code = sum(fs.code_lines for fs in all_stats)
    grand_comment = sum(fs.comment_lines for fs in all_stats)
    grand_blank = sum(fs.blank_lines for fs in all_stats)
    if total_lines:
        print(
            f"\nOverall density: {grand_code / total_lines:.0%} code, "
            f"{grand_comment / total_lines:.0%} comment, {grand_blank / total_lines:.0%} blank"
        )

    # ---- Python details ---------------------------------------------------
    py_files = [fs.path for fs in by_ext.get(".py", [])]
    if py_files:
        print_header("Python Code Details")
        py_syms = python_symbol_counts(py_files)
        py_code = sum(fs.code_lines for fs in by_ext[".py"])
        print(f"Functions:          {py_syms['functions']:,} ({py_syms['async_functions']} async)")
        print(f"Classes:            {py_syms['classes']:,}")
        print(f"Import statements:  {py_syms['import_statements']:,}")
        if py_syms["functions"]:
            print(f"Avg code lines/fn:  {py_code / py_syms['functions']:.1f}")
        print(f"\nTop {args.top} largest Python files:")
        largest = sorted(by_ext[".py"], key=lambda f: f.total_lines, reverse=True)[: args.top]
        print_table(
            ["File", "Lines", "Code"],
            [[str(f.path.relative_to(REPO_ROOT)), f.total_lines, f.code_lines] for f in largest],
            align_right={1, 2},
        )

    # ---- firescript details -------------------------------------------
    fire_files = [fs.path for fs in by_ext.get(".fire", [])]
    if fire_files:
        print_header("firescript Code Details")
        fire_syms = fire_symbol_counts(fire_files)
        fire_code = sum(fs.code_lines for fs in by_ext[".fire"])
        print(f"Functions (fn):             {fire_syms.get('functions', 0):,}")
        print(f"Classes:                    {fire_syms.get('classes', 0):,}")
        print(f"Enums:                      {fire_syms.get('enums', 0):,}")
        print(f"Directives:                 {fire_syms.get('directives', 0):,}")
        print(f"Import statements:          {fire_syms.get('import_statements', 0):,}")
        print(f"@builtin_method decorators: {fire_syms.get('builtin_method_decorators', 0):,}")
        if fire_syms.get("functions"):
            print(f"Avg code lines/fn:          {fire_code / fire_syms['functions']:.1f}")

        std_dir = REPO_ROOT / "firescript" / "std"
        if std_dir.exists():
            modules = sorted(p.name for p in std_dir.iterdir() if p.is_dir() or p.suffix == ".fire")
            print(f"\nstd/ entries ({len(modules)}): {', '.join(modules)}")

        print(f"\nTop {args.top} largest firescript files:")
        largest = sorted(by_ext[".fire"], key=lambda f: f.total_lines, reverse=True)[: args.top]
        print_table(
            ["File", "Lines", "Code"],
            [[str(f.path.relative_to(REPO_ROOT)), f.total_lines, f.code_lines] for f in largest],
            align_right={1, 2},
        )

    # ---- Test suite analytics ------------------------------------------
    print_header("Test Suite Analytics")
    tstats = test_suite_analytics(REPO_ROOT)
    print(f"Python test files:              {tstats['python_test_files']:,}")
    print(f"Python test functions (def test_*): {tstats['python_test_functions']:,}")
    print(f".fire run/snapshot source tests: {tstats['fire_run_snapshot_sources']:,}")
    print(f".fire compile-fail source tests: {tstats['fire_compile_fail_sources']:,}")
    print(f"Total .fire source tests:        {tstats['total_fire_test_sources']:,}")
    print(f"FIR snapshot files:              {tstats['snapshot_fir_files']:,}")
    print(f"FLIR snapshot files:             {tstats['snapshot_flir_files']:,}")

    if tstats["fire_source_categories"]:
        print(f"\nTop categories under tests/sources/ (valid):")
        print_table(
            ["Category", "Files"],
            [[cat, n] for cat, n in tstats["fire_source_categories"][: args.top]],
            align_right={1},
        )
    if tstats["fire_invalid_categories"]:
        print(f"\nTop categories under tests/sources/invalid/ (compile-fail):")
        print_table(
            ["Category", "Files"],
            [[cat, n] for cat, n in tstats["fire_invalid_categories"][: args.top]],
            align_right={1},
        )

    # ---- TODO / FIXME markers -------------------------------------------
    todo_total, todo_files = todo_scan(all_stats)
    print_header("TODO / FIXME / XXX / HACK Markers")
    print(f"Total markers: {todo_total:,} across {len(todo_files):,} file(s)")
    if todo_files:
        print(f"\nTop {args.top} files by marker count:")
        print_table(["File", "Markers"], todo_files[: args.top], align_right={1})

    # ---- Largest files overall ------------------------------------------
    print_header(f"Top {args.top} Largest Files (by line count)")
    largest_overall = sorted(all_stats, key=lambda f: f.total_lines, reverse=True)[: args.top]
    print_table(
        ["File", "Lines", "Size"],
        [[str(f.path.relative_to(REPO_ROOT)), f.total_lines, human_size(f.size_bytes)] for f in largest_overall],
        align_right={1},
    )

    # ---- Top-level directory breakdown ----------------------------------
    print_header("Top-Level Directory Breakdown")
    dir_stats: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # [files, lines]
    for fs in all_stats:
        rel = fs.path.relative_to(REPO_ROOT)
        top = rel.parts[0] if len(rel.parts) > 1 else "(root)"
        dir_stats[top][0] += 1
        dir_stats[top][1] += fs.total_lines
    rows = sorted(
        ([d, v[0], v[1]] for d, v in dir_stats.items()),
        key=lambda r: r[2], reverse=True,
    )
    print_table(["Directory", "Files", "Lines"], rows, align_right={1, 2})

    # ---- Optional JSON dump ----------------------------------------------
    if args.json:
        report = {
            "root": str(REPO_ROOT),
            "total_files": total_files,
            "total_lines": total_lines,
            "total_size_bytes": total_size,
            "by_language": {
                LANGUAGE_NAMES.get(ext, ext): {
                    "files": len(files),
                    "code_lines": sum(f.code_lines for f in files),
                    "comment_lines": sum(f.comment_lines for f in files),
                    "blank_lines": sum(f.blank_lines for f in files),
                    "total_lines": sum(f.total_lines for f in files),
                }
                for ext, files in by_ext.items()
            },
            "python_symbols": python_symbol_counts(py_files) if py_files else {},
            "fire_symbols": fire_symbol_counts(fire_files) if fire_files else {},
            "tests": tstats,
            "todo_markers": {"total": todo_total, "by_file": dict(todo_files)},
            "git": git,
            "directory_breakdown": {d: {"files": v[0], "lines": v[1]} for d, v in dir_stats.items()},
        }
        out_path = Path(args.json)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nJSON report written to {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
