"""`compile-fail` kind: subprocess `--check --message-format json`, compare
diagnostics against //~ annotations (spec sec.4.2)."""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys

from harness.compilecmd import build_compile_cmd
from harness.config import REPO_ROOT, SOURCES_DIR
from harness.directives import DirectiveError, parse_fire_directives
from harness.expectations import (
    ActualDiagnostic,
    match_diagnostics,
    parse_diagnostic_annotations,
    update_diagnostic_annotations,
)
from harness.kinds.base import ExecContext, Kind
from harness.model import Status, TestCase, TestId, TestResult

INVALID_DIR = os.path.join(SOURCES_DIR, "invalid")


def _repo_relative(path: str) -> str:
    return os.path.relpath(path, REPO_ROOT).replace(os.sep, "/")


class CompileFailKind(Kind):
    name = "compile-fail"

    def discover(self, config) -> list[TestCase]:
        cases: list[TestCase] = []
        pattern = os.path.join(INVALID_DIR, "**", "*.fire")
        for src in sorted(glob.glob(pattern, recursive=True)):
            rel = _repo_relative(src)
            stem = os.path.splitext(os.path.basename(rel))[0]
            with open(src, "r", encoding="utf-8") as f:
                text = f.read()
            try:
                directives = parse_fire_directives(text)
            except DirectiveError as e:
                cases.append(
                    TestCase(
                        id=TestId(kind="compile-fail", path=rel, name=stem),
                        payload={"discovery_error": str(e)},
                    )
                )
                continue
            if directives.has("helper"):
                continue
            mode = directives.value("mode")
            if mode == "run":
                cases.append(
                    TestCase(
                        id=TestId(kind="compile-fail", path=rel, name=stem),
                        payload={
                            "discovery_error": (
                                "//@ mode: run conflicts with location: file is under "
                                "tests/sources/invalid/"
                            )
                        },
                    )
                )
                continue
            if directives.value("skip"):
                cases.append(
                    TestCase(
                        id=TestId(kind="compile-fail", path=rel, name=stem),
                        directives=directives,
                        payload={"source": src, "text": text},
                    )
                )
                continue
            try:
                annotations = parse_diagnostic_annotations(text)
            except DirectiveError as e:
                cases.append(
                    TestCase(
                        id=TestId(kind="compile-fail", path=rel, name=stem),
                        payload={"discovery_error": str(e)},
                    )
                )
                continue
            if not annotations and not config.update:
                cases.append(
                    TestCase(
                        id=TestId(kind="compile-fail", path=rel, name=stem),
                        payload={
                            "discovery_error": (
                                "compile-fail file has zero //~ annotations "
                                "(run with --update to insert them)"
                            )
                        },
                    )
                )
                continue
            cases.append(
                TestCase(
                    id=TestId(kind="compile-fail", path=rel, name=stem),
                    directives=directives,
                    payload={"source": src, "text": text},
                )
            )
        return cases

    def _collect_actuals(self, src: str, ctx: ExecContext) -> tuple[list[ActualDiagnostic], str]:
        cmd = build_compile_cmd(src, check=True, message_format="json")
        proc = subprocess.run(
            cmd, cwd=REPO_ROOT, text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=ctx.config.compile_timeout,
        )
        combined = (proc.stdout or "") + (proc.stderr or "")
        actuals: list[ActualDiagnostic] = []
        for line in combined.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "diagnostic":
                continue
            actuals.append(
                ActualDiagnostic(
                    severity=event.get("level", "error").upper(),
                    code=event.get("code", "FS-COMP-0000"),
                    line=event.get("line", 0),
                    column=event.get("column", 0),
                    message=event.get("message", ""),
                )
            )
        return actuals, combined

    def execute(self, case: TestCase, ctx: ExecContext) -> TestResult:
        src = case.payload["source"]
        actuals, combined = self._collect_actuals(src, ctx)
        if not actuals:
            return TestResult(
                case.id, Status.FAIL,
                message="expected compilation to fail but it succeeded",
                details=combined,
            )
        annotations = parse_diagnostic_annotations(case.payload["text"])
        missing, extra = match_diagnostics(annotations, actuals)
        if not missing and not extra:
            return TestResult(case.id, Status.PASS)
        lines = []
        for m in missing:
            lines.append(f"  missing: {m.severity} {m.code} @ line {m.target_line}"
                         + (f" col {m.column}" if m.column is not None else ""))
        for e in extra:
            lines.append(f"  extra:   {e.severity} {e.code} @ line {e.line} col {e.column}: {e.message}")
        return TestResult(case.id, Status.FAIL, message="diagnostic mismatch", details="\n".join(lines))

    def update(self, case: TestCase, ctx: ExecContext) -> TestResult:
        src = case.payload["source"]
        actuals, combined = self._collect_actuals(src, ctx)
        if not actuals:
            return TestResult(
                case.id, Status.FAIL,
                message="expected compilation to fail but it succeeded (cannot --update)",
                details=combined,
            )
        new_text = update_diagnostic_annotations(case.payload["text"], actuals)
        if new_text != case.payload["text"]:
            with open(src, "w", encoding="utf-8", newline="\n") as f:
                f.write(new_text)
            return TestResult(case.id, Status.UPDATED, message="//~ annotations updated")
        return TestResult(case.id, Status.PASS)
