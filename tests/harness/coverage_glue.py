"""Coverage integration, ported from run_tests.py (spec sec.9). Optional
dependency; absent -> note printed, everything else still works."""
from __future__ import annotations

import glob
import os
import re

from harness.config import BUILD_DIR, REPO_ROOT

COVERAGERC = os.path.join(REPO_ROOT, ".coveragerc")
COVERAGE_DIR = os.path.join(BUILD_DIR, "coverage")
COVERAGE_FILE = os.path.join(COVERAGE_DIR, ".coverage")


def available() -> bool:
    try:
        import coverage  # noqa: F401
        return True
    except ImportError:
        return False


def start():
    if not available():
        return None
    import coverage as coverage_mod

    os.makedirs(COVERAGE_DIR, exist_ok=True)
    stale = glob.glob(os.path.join(COVERAGE_DIR, ".coverage*"))
    for f in stale:
        try:
            os.remove(f)
        except OSError:
            pass
    os.environ["COVERAGE_PROCESS_START"] = COVERAGERC
    os.environ["FIRESCRIPT_COV_ROOT"] = REPO_ROOT
    os.environ["COVERAGE_FILE"] = COVERAGE_FILE
    cov = coverage_mod.Coverage(config_file=COVERAGERC)
    cov.start()
    return cov


def _strip_data_hash_suffixes() -> None:
    """Make combine() dedupe worker data files by content, not by name.

    Pool workers are killed with os._exit() (skipping coverage's atexit save),
    so scheduler._flush_worker_coverage() saves their in-process coverage after
    every case. coverage tags a data file with a ".H<hash>h" name suffix at its
    first write and never updates it, so several workers whose first save was
    identical share the suffix, and combine() skips all but one of them as
    "duplicates", losing real data. Without the suffix combine falls back to
    hashing the file contents, which is a correct duplicate check."""
    for f in glob.glob(os.path.join(COVERAGE_DIR, ".coverage.*")):
        stripped = re.sub(r"\.H[A-Za-z0-9]{10}h$", "", f)
        if stripped != f:
            os.replace(f, stripped)


def finish(cov, uncovered_only: bool, fail_under: float | None = None) -> float | None:
    if cov is None:
        print("\n(coverage not available -- install 'coverage' for coverage reporting)")
        return None
    cov.stop()
    _strip_data_hash_suffixes()
    cov.combine(keep=False)
    print()
    percent = cov.report(
        include=["firescript/*"],
        omit=["firescript/lsp_server.py", "firescript/lsp/*"],
        show_missing=uncovered_only,
        skip_covered=uncovered_only,
    )
    if fail_under is not None and percent < fail_under:
        print(f"\nCoverage {percent:.2f}% is below --coverage-fail-under {fail_under:.2f}%")
    return percent
