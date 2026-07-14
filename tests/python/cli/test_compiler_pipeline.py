"""Unit tests for firescript/compiler_pipeline.py's CompilerPipeline: the
parse()-must-precede-later-stages guard clauses on resolve_imports(),
preprocess(), and analyze_semantics(), plus a full happy-path run."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from compiler_pipeline import CompilerPipeline  # noqa: E402


def _fresh_pipeline() -> CompilerPipeline:
    return CompilerPipeline(source_text="int32 x = 1;", source_name="t.fire", source_path="t.fire")


def test_resolve_imports_before_parse_raises():
    pipeline = _fresh_pipeline()
    try:
        pipeline.resolve_imports()
        t.require(False, "no error raised")
    except RuntimeError as e:
        t.require("parse() must be called" in str(e), str(e))


def test_preprocess_before_parse_raises():
    pipeline = _fresh_pipeline()
    try:
        pipeline.preprocess()
        t.require(False, "no error raised")
    except RuntimeError as e:
        t.require("parse() must be called" in str(e), str(e))


def test_analyze_semantics_before_parse_raises():
    pipeline = _fresh_pipeline()
    try:
        pipeline.analyze_semantics()
        t.require(False, "no error raised")
    except RuntimeError as e:
        t.require("parse() must be called" in str(e), str(e))


def test_full_pipeline_happy_path():
    pipeline = _fresh_pipeline()
    pipeline.parse()
    t.require(not pipeline.has_imports())
    pipeline.resolve_imports()
    pipeline.preprocess()
    analyzer = pipeline.analyze_semantics()
    t.require(analyzer is not None)
