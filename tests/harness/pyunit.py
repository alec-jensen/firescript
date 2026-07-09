"""Micro test framework imported by tests/python/** (spec sec.4.4).

This is deliberately the whole API surface -- keep it small. The API is
pytest-shaped (plain test_* functions, assert-based) on purpose, so a future
migration to pytest would be mechanical, even though this project doesn't
use pytest (stdlib only; see spec sec.14 decisions log).
"""
from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import tempfile

from harness.config import REPO_ROOT, SOURCES_DIR

repo_root = REPO_ROOT
sources_dir = SOURCES_DIR

MAIN_PY = os.path.join(REPO_ROOT, "firescript", "main.py")


class TestFailure(AssertionError):
    pass


class SkipTest(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class SubtestFailure(AssertionError):
    def __init__(self, label: str, inner: BaseException):
        self.label = label
        self.inner = inner
        super().__init__(f"[{label}] {inner}")


def require(cond: bool, msg: str = "") -> None:
    if not cond:
        raise TestFailure(msg or "requirement failed")


def require_eq(a, b, msg: str = "") -> None:
    if a != b:
        detail = f"{msg}: " if msg else ""
        raise TestFailure(f"{detail}{a!r} != {b!r}")


def skip(reason: str) -> None:
    raise SkipTest(reason)


@contextlib.contextmanager
def tmpdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@contextlib.contextmanager
def subtest(label: str):
    try:
        yield
    except SkipTest:
        raise
    except Exception as e:  # noqa: BLE001
        raise SubtestFailure(label, e) from e


def run_compiler(args: list[str], cwd: str | None = None, timeout: float = 60.0) -> subprocess.CompletedProcess:
    cmd = [sys.executable, MAIN_PY] + list(args)
    return subprocess.run(
        cmd, cwd=cwd or REPO_ROOT, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
    )


def params(iterable):
    """Decorator: expands one test_ fn into N cases.

    @t.params(["a", "b"])
    def test_x(value): ...
    -> test_x[a], test_x[b]
    """
    values = list(iterable)

    def decorator(fn):
        fn._pyunit_params = values
        return fn

    return decorator
