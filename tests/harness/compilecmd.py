"""Single place that constructs `firescript/main.py` invocations (spec sec.3.1).
Every kind that needs to invoke the compiler goes through here so that
cross-cutting concerns (matrix flags, --verify-ir, coverage subprocess env)
stay in one spot."""
from __future__ import annotations

import os
import sys

from harness.config import REPO_ROOT

MAIN_PY = os.path.join(REPO_ROOT, "firescript", "main.py")

# TODO(spec sec.10.1, sec.12.2): once `--verify-ir` exists on main.py, pass it
# on every compile here so every golden/compile-fail test becomes an
# IR-invariant test for free. A verifier failure must be surfaced as ERROR
# (compiler bug), never a test FAIL.
VERIFY_IR_FLAG: list[str] = []


def build_compile_cmd(
    src: str,
    *,
    out: str | None = None,
    emit: str | None = None,
    check: bool = False,
    message_format: str | None = None,
    emit_fir: bool = False,
    emit_flir: bool = False,
    debug: bool = False,
    extra_flags: list[str] | None = None,
) -> list[str]:
    cmd = [sys.executable, MAIN_PY]
    if debug:
        cmd.append("-d")
    if out:
        cmd += ["-o", out]
    if emit:
        cmd += ["--emit", emit]
    if check:
        cmd.append("--check")
    if message_format:
        cmd += ["--message-format", message_format]
    if emit_fir:
        cmd.append("--emit-fir")
    if emit_flir:
        cmd.append("--emit-flir")
    cmd += VERIFY_IR_FLAG
    if extra_flags:
        cmd += extra_flags
    cmd.append(src)
    return cmd


def coverage_env(base_env: dict | None = None) -> dict:
    """Env additions so a compiler subprocess reports into the shared
    coverage data file (spec sec.9)."""
    env = dict(base_env if base_env is not None else os.environ)
    if "COVERAGE_PROCESS_START" in os.environ:
        env["COVERAGE_PROCESS_START"] = os.environ["COVERAGE_PROCESS_START"]
        env["COVERAGE_FILE"] = os.environ.get("COVERAGE_FILE", os.path.join(REPO_ROOT, ".coverage"))
    return env
