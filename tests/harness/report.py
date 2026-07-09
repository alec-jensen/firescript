"""Console + JSON reporting (spec sec.6.4, sec.6.5). Preserves the existing
visual language: [CASE ] cyan, [PASS ] green, [FAIL ]/[ERROR ] red,
[UPDATE]/[NEW ] yellow; per-kind summary lines, totals, then coverage, then
the seed as the final line. There is no SKIP status -- see model.py."""
from __future__ import annotations

import json
import os
import sys
import time

from harness.model import Status, TestResult

TAG_WIDTH = 6


def supports_color() -> bool:
    if os.environ.get("NO_COLOR") is not None:
        return False
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def colorize(text: str, code: str) -> str:
    if not supports_color():
        return text
    return f"\x1b[{code}m{text}\x1b[0m"


def tag(label: str, color_code: str | None = None) -> str:
    padded = f"[{label:<{TAG_WIDTH}}]"
    return colorize(padded, color_code) if color_code else padded


_STATUS_COLOR = {
    Status.PASS: "32",
    Status.FAIL: "31",
    Status.ERROR: "31",
    Status.UPDATED: "33",
    Status.NEW: "33",
}


class ConsoleReporter:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.start_time = time.time()

    def on_case_start(self, case) -> None:
        print(f"{tag('CASE', '36')} {case.id}")

    def on_case_done(self, result: TestResult) -> None:
        color = _STATUS_COLOR.get(result.status, None)
        label = result.status.value
        line = f"{tag(label, color)} {result.id}"
        if result.message:
            line += f" - {result.message}"
        print(line)
        if result.status in (Status.FAIL, Status.ERROR) and result.details:
            print(colorize(result.details, "33" if result.status == Status.FAIL else "31"))

    def summarize(self, results: list[TestResult], seed_line: str, coverage_report_fn=None) -> None:
        by_kind: dict[str, list[TestResult]] = {}
        for r in results:
            by_kind.setdefault(r.id.kind, []).append(r)

        print()
        for kind_name, kind_results in sorted(by_kind.items()):
            total = len(kind_results)
            passed = sum(1 for r in kind_results if r.status in (Status.PASS, Status.UPDATED, Status.NEW))
            failed = sum(1 for r in kind_results if r.status in (Status.FAIL, Status.ERROR))
            color = "32" if failed == 0 else "31"
            print(colorize(f"{kind_name}: {passed}/{total} passed, {failed}/{total} failed", color))

        total = len(results)
        failed_total = sum(1 for r in results if r.status in (Status.FAIL, Status.ERROR))
        passed_total = total - failed_total
        summary_color = "32" if failed_total == 0 else "31"
        print(colorize(f"\nSummary: {passed_total}/{total} passed, {failed_total}/{total} failed", summary_color))

        if coverage_report_fn is not None:
            print(colorize("\n== Coverage ==", "36"))
            coverage_report_fn()

        print(f"\n{seed_line}")


class JsonReporter:
    def __init__(self):
        self.results: list[TestResult] = []

    def on_case_start(self, case) -> None:
        pass

    def on_case_done(self, result: TestResult) -> None:
        self.results.append(result)

    def write(self, path: str, *, seed: str, profile: str, matrix: str, started: float, coverage_pct=None) -> None:
        counts = {"pass": 0, "fail": 0, "error": 0, "updated": 0, "new": 0}
        for r in self.results:
            counts[r.status.value.lower()] += 1
        payload = {
            "schema": 1,
            "seed": seed,
            "profile": profile,
            "matrix": matrix,
            "started": started,
            "duration_s": time.time() - started,
            "counts": counts,
            "coverage_pct": coverage_pct,
            "results": [
                {
                    "id": str(r.id),
                    "kind": r.id.kind,
                    "path": r.id.path,
                    "name": r.id.name,
                    "cell": r.id.cell,
                    "status": r.status.value,
                    "duration_s": r.duration_s,
                    "message": r.message,
                    "details": r.details,
                    "artifacts": r.artifacts,
                    "seed": r.seed,
                }
                for r in self.results
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)


class TeeReporter:
    """Fans out to multiple reporters (console + JSON)."""

    def __init__(self, *reporters):
        self.reporters = reporters

    def on_case_start(self, case) -> None:
        for r in self.reporters:
            r.on_case_start(case)

    def on_case_done(self, result: TestResult) -> None:
        for r in self.reporters:
            r.on_case_done(result)
