"""RunConfig: all harness knobs, fully typed (spec sec.3.1, sec.6.3)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
TESTS_DIR = os.path.join(REPO_ROOT, "tests")
SOURCES_DIR = os.path.join(TESTS_DIR, "sources")
PYTHON_TESTS_DIR = os.path.join(TESTS_DIR, "python")
SNAPSHOTS_DIR = os.path.join(TESTS_DIR, "snapshots")
BUILD_DIR = os.path.join(REPO_ROOT, "build")
WORK_DIR = os.path.join(BUILD_DIR, "test-work")
RESULTS_DIR = os.path.join(BUILD_DIR, "test-results")

PROFILES = {
    "local": dict(matrix="quick", determinism="sample", coverage=None),
    "ci": dict(matrix="quick", determinism="all", coverage=None),
    "full": dict(matrix="full", determinism="all", coverage=None),
}


@dataclass
class RunConfig:
    selectors: list[str] = field(default_factory=list)
    update: bool = False
    jobs: int = field(default_factory=lambda: max(1, os.cpu_count() or 1))
    fail_fast: bool = False
    verbose: bool = False
    timeout: float = 20.0
    compile_timeout: float = 120.0
    matrix: str = "quick"  # quick | full | sample=K
    determinism: str = "sample"  # off | sample | all
    seed: str | None = None
    coverage: bool | None = None  # None = auto
    coverage_fail_under: float | None = None
    uncovered: bool = False
    json_path: str | None = None
    keep_artifacts: bool = False
    list_only: bool = False
    profile: str = "local"
    verify_ir: bool = False  # TODO seam (spec sec.10.1); not yet a real compiler flag

    def apply_profile(self) -> None:
        if self.profile not in PROFILES:
            raise ValueError(f"unknown profile '{self.profile}'")
        defaults = PROFILES[self.profile]
        # Profile sets defaults; explicit CLI flags (handled in cli.py) override.
        if self._matrix_is_default:
            self.matrix = defaults["matrix"]
        if self._determinism_is_default:
            self.determinism = defaults["determinism"]

    _matrix_is_default: bool = True
    _determinism_is_default: bool = True
