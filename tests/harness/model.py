"""Core data model shared by every kind (spec sec.3.2)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass(frozen=True)
class TestId:
    kind: str  # "run", "compile-fail", "snapshot", "python", ...
    path: str  # repo-relative posix path of the test file
    name: str  # for python tests: "test_emit_ast"; else file stem
    cell: str = "default"  # matrix cell id, "default" outside matrix runs

    def __str__(self) -> str:
        if self.kind == "python":
            return f"python:{self.path}::{self.name}"
        return f"{self.kind}:{self.path}[{self.cell}]"


class Status(str, Enum):
    """No SKIP value on purpose: this harness never skips a discovered test.
    A test either passes, fails, errors, or (in --update mode) gets its
    in-file expectations rewritten -- see CLAUDE.md's "never skip tests"
    rule. A kind that can't run a case yet (e.g. an unimplemented feature)
    should discover zero cases for it, not report a fake skipped one."""

    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    UPDATED = "UPDATED"
    NEW = "NEW"


@dataclass
class TestCase:
    id: TestId
    directives: object = None  # harness.directives.Directives, kind-specific
    payload: dict = field(default_factory=dict)  # kind-specific extra data


@dataclass
class TestResult:
    id: TestId
    status: Status
    duration_s: float = 0.0
    message: str = ""
    details: str = ""
    artifacts: list = field(default_factory=list)
    seed: str | None = None
