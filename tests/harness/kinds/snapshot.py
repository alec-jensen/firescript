"""`snapshot` kind: FIR/FLIR IR dump goldens, the one sidecar exception
(spec sec.4.3, sec.6.3 decisions log)."""
from __future__ import annotations

import glob
import os
import subprocess
import sys

from harness.config import REPO_ROOT, SNAPSHOTS_DIR, SOURCES_DIR
from harness.directives import DirectiveError, parse_fire_directives
from harness.kinds.base import ExecContext, Kind
from harness.model import Status, TestCase, TestId, TestResult
from harness.workdir import _category_stem


def _repo_relative(path: str) -> str:
    return os.path.relpath(path, REPO_ROOT).replace(os.sep, "/")


class SnapshotKind(Kind):
    name = "snapshot"

    def discover(self, config) -> list[TestCase]:
        cases: list[TestCase] = []
        pattern = os.path.join(SOURCES_DIR, "**", "*.fire")
        for src in sorted(glob.glob(pattern, recursive=True)):
            rel = _repo_relative(src)
            if "/invalid/" in "/" + rel:
                continue
            with open(src, "r", encoding="utf-8") as f:
                text = f.read()
            try:
                directives = parse_fire_directives(text)
            except DirectiveError:
                continue  # already reported as a discovery error by the run kind
            if directives.has("helper"):
                continue
            snap = directives.value("snapshot")
            if not snap:
                continue
            formats = [s.strip() for s in snap.split(",")]
            stem = os.path.splitext(os.path.basename(rel))[0]
            cases.append(
                TestCase(
                    id=TestId(kind="snapshot", path=rel, name=stem),
                    directives=directives,
                    payload={"source": src, "formats": formats},
                )
            )
        return cases

    def _emit(self, src: str, work_dir: str, formats: list[str], timeout: float) -> dict:
        os.makedirs(work_dir, exist_ok=True)
        cmd = [sys.executable, os.path.join(REPO_ROOT, "firescript", "main.py"), src]
        if "fir" in formats:
            cmd.append("--emit-fir")
        if "flir" in formats:
            cmd.append("--emit-flir")
        proc = subprocess.run(
            cmd, cwd=work_dir, text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"--emit-fir/--emit-flir failed: {proc.stdout}{proc.stderr}")
        base = os.path.splitext(os.path.basename(src))[0]
        dumps = {}
        if "fir" in formats:
            with open(os.path.join(work_dir, "build", f"{base}.fir"), "r", encoding="utf-8") as f:
                dumps["fir"] = f.read()
        if "flir" in formats:
            with open(os.path.join(work_dir, "build", f"{base}.flir"), "r", encoding="utf-8") as f:
                dumps["flir"] = f.read()
        return dumps

    def _golden_path(self, rel_path: str, fmt: str) -> str:
        category, stem = _category_stem(rel_path)
        return os.path.join(SNAPSHOTS_DIR, category, f"{stem}.{fmt}")

    def execute(self, case: TestCase, ctx: ExecContext) -> TestResult:
        src = case.payload["source"]
        formats = case.payload["formats"]
        try:
            first = self._emit(src, os.path.join(ctx.work_dir, "run1"), formats, ctx.config.compile_timeout)
            second = self._emit(src, os.path.join(ctx.work_dir, "run2"), formats, ctx.config.compile_timeout)
        except RuntimeError as e:
            return TestResult(case.id, Status.ERROR, message=str(e))

        if first != second:
            return TestResult(case.id, Status.FAIL, message="IR dumps are not deterministic")

        mismatches = []
        for fmt in formats:
            golden_path = self._golden_path(case.id.path, fmt)
            if not os.path.exists(golden_path):
                mismatches.append(f"missing {fmt} golden {golden_path} (run with --update)")
                continue
            with open(golden_path, "r", encoding="utf-8") as f:
                expected = f.read()
            if expected != first[fmt]:
                import difflib
                diff = "\n".join(difflib.unified_diff(
                    expected.splitlines(), first[fmt].splitlines(), "expected", "actual", lineterm="",
                ))
                mismatches.append(f"{fmt} mismatch:\n{diff}")

        if mismatches:
            return TestResult(case.id, Status.FAIL, message="; ".join(m.splitlines()[0] for m in mismatches),
                               details="\n\n".join(mismatches))
        return TestResult(case.id, Status.PASS)

    def update(self, case: TestCase, ctx: ExecContext) -> TestResult:
        src = case.payload["source"]
        formats = case.payload["formats"]
        try:
            dumps = self._emit(src, os.path.join(ctx.work_dir, "update"), formats, ctx.config.compile_timeout)
        except RuntimeError as e:
            return TestResult(case.id, Status.ERROR, message=str(e))
        for fmt in formats:
            golden_path = self._golden_path(case.id.path, fmt)
            os.makedirs(os.path.dirname(golden_path), exist_ok=True)
            with open(golden_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(dumps[fmt])
        return TestResult(case.id, Status.UPDATED, message="snapshot(s) regenerated")
