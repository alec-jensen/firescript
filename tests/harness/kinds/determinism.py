"""`determinism` kind: byte-match recompiles of `run`-kind sources
(spec sec.7.5, phase 3)."""
from __future__ import annotations

import filecmp
import os
import subprocess
import sys
import time

from harness import seeds
from harness.config import REPO_ROOT
from harness.directives import DirectiveError, parse_fire_directives
from harness.kinds.base import ExecContext, Kind
from harness.kinds.run import RunKind
from harness.model import Status, TestCase, TestId, TestResult


class _TransientCompileError(Exception):
    """Infra-level compile flake (no diagnostic output) -- worth retrying."""


class DeterminismKind(Kind):
    name = "determinism"

    def discover(self, config) -> list[TestCase]:
        run_cases = [
            c for c in RunKind().discover(config)
            if "discovery_error" not in c.payload
        ]
        eligible = []
        for c in run_cases:
            directives = c.directives
            if directives is not None and directives.has("no-determinism"):
                continue
            eligible.append(c)

        mode = config.determinism
        if mode == "off" or not eligible:
            return []
        master = config.seed or seeds.new_master_seed()
        if mode == "all":
            chosen = eligible
        else:  # "sample"
            k = max(3, round(len(eligible) * 0.05))
            chosen = seeds.pick(master, "determinism", eligible, min(k, len(eligible)))

        cases = []
        for c in chosen:
            cases.append(
                TestCase(
                    id=TestId(kind="determinism", path=c.id.path, name=c.id.name),
                    directives=c.directives,
                    payload={"source": c.payload["source"]},
                )
            )
        return cases

    def _compile_once(self, src: str, work_dir: str, timeout: float) -> str:
        # Retried on transient infra failures only (see below) -- a real
        # compiler bug reproduces identically every attempt, so retrying
        # cannot mask genuine non-determinism, only absorb OS-level noise
        # from running many concurrent subprocess compiles (e.g. Windows AV
        # scan-on-close briefly hiding a just-closed file, or the OS killing
        # a process under heavy parallel load with no diagnostic output).
        attempts = 5
        last_exc: Exception | None = None
        for attempt in range(attempts):
            if attempt:
                time.sleep(0.3 * attempt)
            try:
                return self._compile_once_attempt(src, work_dir, timeout)
            except _TransientCompileError as e:
                last_exc = e
                continue
        raise RuntimeError(f"{last_exc} (persisted after {attempts} attempts)")

    def _compile_once_attempt(self, src: str, work_dir: str, timeout: float) -> str:
        os.makedirs(work_dir, exist_ok=True)
        binary = os.path.join(work_dir, os.path.splitext(os.path.basename(src))[0] + ".exe")
        cmd = [sys.executable, os.path.join(REPO_ROOT, "firescript", "main.py"), src, "-o", binary]
        proc = subprocess.run(
            cmd, cwd=work_dir, text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
        )
        if proc.returncode != 0:
            output = f"{proc.stdout}{proc.stderr}"
            # Two kinds of "transient, worth retrying" failure show up under
            # heavy parallel subprocess load on Windows:
            #  1. no diagnostic output at all (process killed/crashed by
            #     external contention before it could log anything);
            #  2. a WinError 3/5 (path-not-found / access-denied) raised from
            #     os.makedirs of a *relative* path (e.g. "build/temp") inside
            #     the compiler -- this means the subprocess's own cwd briefly
            #     stopped resolving (AV scan-on-create, FS churn), not a
            #     compiler bug. A genuine compiler bug never manifests as a
            #     raw FileNotFoundError out of os.makedirs.
            has_diagnostic = "ERROR" in output or "Error" in output or "Traceback" in output
            is_transient_os_error = "WinError 3" in output or "WinError 5" in output
            if not has_diagnostic or is_transient_os_error:
                raise _TransientCompileError(f"transient compile failure: {output!r}")
            raise RuntimeError(f"compile failed: {output}")
        # The compiler writes exactly to `binary` (-o always ends in ".exe"
        # already, so main.py never appends a second one). Under heavy
        # parallel I/O load, Windows can report a just-closed file as briefly
        # missing (antivirus scan-on-close, etc.); poll a bit before giving
        # up instead of guessing at a different filename.
        deadline = time.monotonic() + 2.0
        while not os.path.exists(binary) and time.monotonic() < deadline:
            time.sleep(0.05)
        if not os.path.exists(binary):
            raise _TransientCompileError(
                f"compiler reported success but '{binary}' was never created "
                f"(stdout={proc.stdout!r}, stderr={proc.stderr!r})"
            )
        return binary

    def execute(self, case: TestCase, ctx: ExecContext) -> TestResult:
        src = case.payload["source"]
        try:
            bin_a = self._compile_once(src, os.path.join(ctx.work_dir, "a"), ctx.config.compile_timeout)
            bin_b = self._compile_once(src, os.path.join(ctx.work_dir, "b"), ctx.config.compile_timeout)
        except RuntimeError as e:
            return TestResult(case.id, Status.ERROR, message=str(e))

        if filecmp.cmp(bin_a, bin_b, shallow=False):
            return TestResult(case.id, Status.PASS)

        with open(bin_a, "rb") as f:
            data_a = f.read()
        with open(bin_b, "rb") as f:
            data_b = f.read()
        offset = next((i for i, (x, y) in enumerate(zip(data_a, data_b)) if x != y), min(len(data_a), len(data_b)))
        import hashlib
        return TestResult(
            case.id, Status.FAIL,
            message=f"recompiled binaries differ at byte offset {offset}",
            details=(
                f"a: {len(data_a)} bytes, sha256={hashlib.sha256(data_a).hexdigest()}\n"
                f"b: {len(data_b)} bytes, sha256={hashlib.sha256(data_b).hexdigest()}\n\n"
                f"{_hex_diff(data_a, data_b, offset)}"
            ),
            artifacts=[bin_a, bin_b],
        )


def _hex_diff(data_a: bytes, data_b: bytes, offset: int, context: int = 32) -> str:
    """Render a side-by-side hex dump of the bytes around the first
    divergence, with differing bytes marked, so a FAIL is actionable without
    having to pull the binaries out of `artifacts` and diff them by hand."""
    start = max(0, (offset - context) & ~0xF)
    end = min(max(len(data_a), len(data_b)), offset + context)
    lines = [f"hex diff around offset 0x{offset:x} (rows of 16 bytes, '*' marks a differing byte):"]
    for row in range(start, end, 16):
        a_row = data_a[row:row + 16]
        b_row = data_b[row:row + 16]

        def fmt(row_bytes: bytes, other: bytes) -> str:
            cells = []
            for i, byte in enumerate(row_bytes):
                marker = "*" if i >= len(other) or byte != other[i] else " "
                cells.append(f"{byte:02x}{marker}")
            return " ".join(cells).ljust(16 * 3)

        lines.append(f"  {row:08x}  a: {fmt(a_row, b_row)}")
        lines.append(f"            b: {fmt(b_row, a_row)}")
    return "\n".join(lines)
