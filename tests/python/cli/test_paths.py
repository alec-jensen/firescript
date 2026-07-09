"""Regression tests for firescript/utils/file_utils.py::safe_relpath.

Guards against a Windows crash where compiling or importing a file whose
path is on a different drive letter than the cwd raised an unhandled
ValueError from os.path.relpath (see docs/changelog.md 0.6.0 bug fixes)."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from utils.file_utils import safe_relpath  # noqa: E402


def test_safe_relpath_matches_relpath_when_it_succeeds():
    path = os.path.join(REPO_ROOT, "firescript", "main.py")
    t.require_eq(safe_relpath(path), os.path.relpath(path))


def test_safe_relpath_falls_back_to_input_on_value_error():
    def _raise(*args, **kwargs):
        raise ValueError("path is on mount 'D:', start on mount 'C:'")

    original = os.path.relpath
    os.path.relpath = _raise
    try:
        t.require_eq(safe_relpath("C:\\some\\path.fire"), "C:\\some\\path.fire")
    finally:
        os.path.relpath = original
