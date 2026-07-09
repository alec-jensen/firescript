#!/usr/bin/env python3
"""firescript unified test runner.

    python tests/run.py [SELECTOR ...] [options]

See docs/internal/development/test_harness_v2.md for the full spec and
tests/TEST_MANIFEST.md for the directive reference and test inventory.
"""
from __future__ import annotations

import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(TESTS_DIR, os.pardir))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if os.path.join(REPO_ROOT, "firescript") not in sys.path:
    sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from harness.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
