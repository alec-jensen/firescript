"""Kind ABC (spec sec.3.3)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from harness.config import RunConfig
from harness.model import TestCase, TestResult


@dataclass
class ExecContext:
    work_dir: str
    results_dir: str
    seed: str  # per-test derived seed, hex
    master_seed: str
    cell_flags: list
    config: RunConfig
    verbose: bool = False

    def log(self, message: str) -> None:
        if self.verbose:
            print(f"[LOG   ] {message}")


class Kind(ABC):
    name: str

    @abstractmethod
    def discover(self, config: RunConfig) -> list[TestCase]:
        ...

    @abstractmethod
    def execute(self, case: TestCase, ctx: ExecContext) -> TestResult:
        ...

    def update(self, case: TestCase, ctx: ExecContext) -> TestResult:
        """Default: kinds without a bless mode just execute normally."""
        return self.execute(case, ctx)
