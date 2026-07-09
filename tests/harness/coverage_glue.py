"""Coverage integration, ported from run_tests.py (spec sec.9). Optional
dependency; absent -> note printed, everything else still works."""
from __future__ import annotations

import glob
import os

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


def finish(cov, uncovered_only: bool, fail_under: float | None = None) -> float | None:
    if cov is None:
        print("\n(coverage not available -- install 'coverage' for coverage reporting)")
        return None
    cov.stop()
    cov.save()
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
