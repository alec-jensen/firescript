"""Direct unit tests for firescript/targets.py's host detection fallbacks:
host_platform()/host_arch() raise UnknownHostError for an unrecognized
platform.system()/platform.machine() value, which never happens on the
Windows/AMD64 CI host so must be exercised via monkeypatching."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

import targets  # noqa: E402


def test_host_platform_unknown_raises():
    original = targets._host_platform_module.system
    targets._host_platform_module.system = lambda: "PlanFromOuterSpace"
    try:
        try:
            targets.host_platform()
            t.require(False, "expected UnknownHostError")
        except targets.UnknownHostError:
            pass
    finally:
        targets._host_platform_module.system = original


def test_host_arch_unknown_raises():
    original = targets._host_platform_module.machine
    targets._host_platform_module.machine = lambda: "quantum-computer"
    try:
        try:
            targets.host_arch()
            t.require(False, "expected UnknownHostError")
        except targets.UnknownHostError:
            pass
    finally:
        targets._host_platform_module.machine = original
