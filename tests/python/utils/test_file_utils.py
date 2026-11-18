"""Direct unit tests for firescript/utils/file_utils.py: index-to-line/column
mapping and line lookup."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

import utils.file_utils as fu  # noqa: E402

_TEXT = "ab\ncde\n\nf"


@t.params([
    (0, (1, 1)),
    (1, (1, 2)),
    (2, (1, 3)),   # the newline itself is still on line 1
    (3, (2, 1)),
    (5, (2, 3)),
    (6, (2, 4)),
    (7, (3, 1)),   # empty line
    (8, (4, 1)),
])
def test_line_and_column_from_index(case):
    index, expected = case
    t.require_eq(fu.get_line_and_coumn_from_index(_TEXT, index), expected)


def test_line_and_column_index_past_end_returns_end_position():
    t.require_eq(fu.get_line_and_coumn_from_index("ab\nc", 99), (2, 2))


def test_line_and_column_empty_file():
    t.require_eq(fu.get_line_and_coumn_from_index("", 0), (1, 1))


def test_get_line_one_based():
    t.require_eq(fu.get_line(_TEXT, 1), "ab")
    t.require_eq(fu.get_line(_TEXT, 3), "")
    t.require_eq(fu.get_line(_TEXT, 4), "f")


def test_get_line_out_of_range_raises_index_error():
    try:
        fu.get_line(_TEXT, 5)
        t.require(False, "expected IndexError")
    except IndexError:
        pass
