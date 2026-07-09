"""`bootstrap` kind stub (spec sec.10.4) [FUTURE].

Contract once the self-hosted compiler exists: stage1 (current Python
compiler) builds the firescript-implemented compiler -> stage2 binary;
stage2 builds the same source -> stage3 binary; stage2 and stage3 must be
byte-identical. `--profile full` and release CI only.

This stub proves the kind-plugin seam (one module, no core edits) without
implementing the real contract, per spec sec.11 phase 3.
"""
from __future__ import annotations

from harness.kinds.base import ExecContext, Kind
from harness.model import Status, TestCase, TestId, TestResult


class BootstrapKind(Kind):
    name = "bootstrap"

    def discover(self, config) -> list[TestCase]:
        if config.profile != "full":
            return []
        return [TestCase(id=TestId(kind="bootstrap", path="tests/bootstrap", name="stage2_stage3_byte_match"))]

    def execute(self, case: TestCase, ctx: ExecContext) -> TestResult:
        return TestResult(case.id, Status.SKIP, message="self-hosted compiler not yet buildable")
