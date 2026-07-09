"""`run` kind: compile + execute + compare golden stdout (spec sec.4.1)."""
from __future__ import annotations

import difflib
import glob
import os
import subprocess
import sys

from harness.compilecmd import build_compile_cmd
from harness.config import REPO_ROOT, SOURCES_DIR
from harness.directives import DirectiveError, build_argv, build_stdin, parse_fire_directives
from harness.expectations import normalize_output, parse_expect, update_expect
from harness.kinds.base import ExecContext, Kind
from harness.model import Status, TestCase, TestId, TestResult

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))


def _repo_relative(path: str) -> str:
    return os.path.relpath(path, REPO_ROOT).replace(os.sep, "/")


def _discover_sources() -> list[str]:
    pattern = os.path.join(SOURCES_DIR, "**", "*.fire")
    return sorted(glob.glob(pattern, recursive=True))


class RunKind(Kind):
    name = "run"

    def discover(self, config) -> list[TestCase]:
        cases: list[TestCase] = []
        for src in _discover_sources():
            rel = _repo_relative(src)
            if "/invalid/" in "/" + rel:
                continue
            with open(src, "r", encoding="utf-8") as f:
                text = f.read()
            try:
                directives = parse_fire_directives(text)
            except DirectiveError as e:
                cases.append(
                    TestCase(
                        id=TestId(kind="run", path=rel, name=os.path.splitext(os.path.basename(rel))[0]),
                        payload={"discovery_error": str(e)},
                    )
                )
                continue
            if directives.has("helper"):
                continue
            mode = directives.value("mode")
            if mode == "compile-fail":
                cases.append(
                    TestCase(
                        id=TestId(kind="run", path=rel, name=os.path.splitext(os.path.basename(rel))[0]),
                        payload={
                            "discovery_error": (
                                "//@ mode: compile-fail conflicts with location: file is not under "
                                "tests/sources/invalid/"
                            )
                        },
                    )
                )
                continue
            stem = os.path.splitext(os.path.basename(rel))[0]
            cases.append(
                TestCase(
                    id=TestId(kind="run", path=rel, name=stem),
                    directives=directives,
                    payload={"source": src, "text": text},
                )
            )
        return cases

    def execute(self, case: TestCase, ctx: ExecContext) -> TestResult:
        return self._run(case, ctx, update=False)

    def update(self, case: TestCase, ctx: ExecContext) -> TestResult:
        return self._run(case, ctx, update=True)

    def _run(self, case: TestCase, ctx: ExecContext, update: bool) -> TestResult:
        from backend import pe_inspect

        src = case.payload["source"]
        directives = case.directives
        stem = case.id.name
        os.makedirs(ctx.work_dir, exist_ok=True)
        binary = os.path.join(ctx.work_dir, stem + ".exe")

        compile_flags = list(ctx.cell_flags)
        extra = directives.value("compile-flags")
        if extra:
            import shlex

            compile_flags += shlex.split(extra)

        compile_timeout = float(directives.value("compile-timeout", ctx.config.compile_timeout))
        cmd = build_compile_cmd(src, out=binary, extra_flags=compile_flags)
        try:
            # cwd=work_dir: main.py writes intermediate output (build/temp/*.s
            # etc.) relative to cwd, so this is what gives each (test, cell)
            # its own isolated compile scratch space (spec sec.3.5 / known
            # problem #1) without any compiler changes.
            proc = subprocess.run(
                cmd, cwd=ctx.work_dir, text=True, encoding="utf-8", errors="replace",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=compile_timeout,
            )
        except subprocess.TimeoutExpired:
            return TestResult(case.id, Status.ERROR, message=f"compile timeout after {compile_timeout:g}s")
        if proc.returncode != 0:
            return TestResult(
                case.id, Status.ERROR,
                message=f"compile failed (exit {proc.returncode})",
                details=(proc.stdout or "") + (proc.stderr or ""),
            )

        resolved_binary = binary if os.path.exists(binary) else binary + ".exe"
        try:
            dlls = pe_inspect.imported_dlls(resolved_binary)
        except Exception as e:  # noqa: BLE001
            return TestResult(case.id, Status.ERROR, message=f"PE inspection failed: {e}")
        bad = [d for d in dlls if d.upper() != "KERNEL32.DLL"]
        if bad:
            return TestResult(case.id, Status.FAIL, message=f"binary imports more than kernel32: {', '.join(dlls)}")

        argv = build_argv(directives)
        stdin_text = build_stdin(directives, os.path.dirname(src))
        run_timeout = float(directives.value("timeout", ctx.config.timeout))
        expected_exit = int(directives.value("exit-code", "0"))

        run_cmd = [resolved_binary] + argv
        try:
            proc = subprocess.run(
                run_cmd, cwd=REPO_ROOT, text=True, encoding="utf-8", errors="replace",
                input=stdin_text, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=run_timeout,
            )
        except subprocess.TimeoutExpired:
            return TestResult(case.id, Status.ERROR, message=f"runtime timeout after {run_timeout:g}s")

        if proc.returncode != expected_exit:
            return TestResult(
                case.id, Status.ERROR,
                message=f"exit code {proc.returncode}, expected {expected_exit}",
                details=(proc.stdout or "") + (proc.stderr or ""),
            )

        actual_norm = normalize_output(proc.stdout)

        if update:
            new_text = update_expect(case.payload["text"], actual_norm)
            if new_text != case.payload["text"]:
                with open(src, "w", encoding="utf-8", newline="\n") as f:
                    f.write(new_text)
                return TestResult(case.id, Status.UPDATED, message="EXPECT block updated")
            return TestResult(case.id, Status.PASS)

        try:
            block = parse_expect(case.payload["text"])
        except DirectiveError as e:
            return TestResult(case.id, Status.ERROR, message=str(e))

        if block is None:
            return TestResult(
                case.id, Status.FAIL,
                message="missing expectation; run with --update",
                details=actual_norm,
            )

        if actual_norm == block.content_norm:
            return TestResult(case.id, Status.PASS)

        diff = "".join(difflib.unified_diff(
            block.content_norm.splitlines(keepends=True),
            actual_norm.splitlines(keepends=True),
            fromfile="expected", tofile="actual",
        ))
        return TestResult(case.id, Status.FAIL, message="output mismatch", details=diff)
