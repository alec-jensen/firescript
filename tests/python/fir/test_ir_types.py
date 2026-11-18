"""Direct unit tests for fir.ir_types: SimpleType ownership classification."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from fir.ir_types import make_simple  # noqa: E402


def test_is_copyable_true_for_copyable_category():
    t.require(make_simple("int32").is_copyable())
    t.require(not make_simple("int32").is_owned())

