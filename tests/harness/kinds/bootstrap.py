"""`bootstrap` kind stub (spec sec.10.4) [FUTURE].

Contract once the self-hosted compiler exists: stage1 (current Python
compiler) builds the firescript-implemented compiler -> stage2 binary;
stage2 builds the same source -> stage3 binary; stage2 and stage3 must be
byte-identical. `--profile full` and release CI only.

This stub proves the kind-plugin seam (one module, no core edits) without
implementing the real contract, per spec sec.11 phase 3. There is no
capability to skip a test in this harness (tests must fail loudly, never be
silently skipped -- see CLAUDE.md), so until the self-hosted toolchain
actually exists to byte-compare, this kind discovers zero cases rather than
producing a fake one that reports as skipped.
"""
from __future__ import annotations

from harness.kinds.base import ExecContext, Kind
from harness.model import TestCase, TestResult


class BootstrapKind(Kind):
    name = "bootstrap"

    def discover(self, config) -> list[TestCase]:
        return []

    def execute(self, case: TestCase, ctx: ExecContext) -> TestResult:
        raise NotImplementedError("bootstrap kind has no runnable cases yet")
