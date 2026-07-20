"""Regression tests for a generic class referencing itself (Name<Args>)
inside its own body -- e.g. a static factory returning the enclosing
class, or an instance method calling another method on `this` -- in a
file with *no* import statements at all.

self.generic_class_templates/self.user_methods aren't populated for the
enclosing class until its whole body finishes parsing (declarations.py's
_parse_class_definition registers it only at the end), so these
self-referential uses can't resolve through the normal "already known"
path. A pre-existing deferred-import fallback (self.defer_undefined_
identifiers) happens to paper over this whenever the file has at least
one import statement (defer_undefined_identifiers is derived from the
file's own token stream, per frontend_pipeline.py's has_import_tokens) --
every firescript/std/types/init.fire-style all-.fire test in the golden
suite has an unrelated `import @firescript/std.io.println;` for output,
which accidentally exercises that path instead of this one. This module
tests the sharper case directly: zero imports, so none of that fallback
is available, and the fix (a dedicated self._current_generic_class_name,
tracked separately across both the parse-time and type-check-time class
traversals) has to carry the whole thing on its own -- this is the shape
of firescript/std/types/init.fire itself (no imports at all), which is
where this bug was originally found.
"""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from compiler_pipeline import CompilerPipeline  # noqa: E402


def _parses_clean(source: str) -> CompilerPipeline:
    pipeline = CompilerPipeline(source, "test.fire", "test.fire")
    pipeline.parse()
    t.require(pipeline.parser_errors == [], pipeline.parser_errors)
    return pipeline


def test_static_factory_returning_enclosing_generic_class_no_imports():
    _parses_clean(
        "class Box<T?> {\n"
        "    value: T?;\n"
        "\n"
        "    fn Box(value: T?) {\n"
        "        this.value = value;\n"
        "    }\n"
        "\n"
        "    static fn wrap(v: T) -> Box<T> {\n"
        "        return Box<T>(v);\n"
        "    }\n"
        "}\n"
    )


def test_self_call_inside_generic_class_no_imports():
    _parses_clean(
        "class Box<T?> {\n"
        "    value: T?;\n"
        "\n"
        "    fn Box(value: T?) {\n"
        "        this.value = value;\n"
        "    }\n"
        "\n"
        "    fn isEmpty() -> bool {\n"
        "        return this.value == null;\n"
        "    }\n"
        "\n"
        "    fn describe() -> bool {\n"
        "        return this.isEmpty();\n"
        "    }\n"
        "}\n"
    )


def test_explicit_type_arg_static_call_on_enclosing_class_no_imports():
    # The Box<int32>.wrap(...) explicit-type-argument spelling, not just
    # the bare Box.wrap(...) inferred one -- called from top-level code
    # right after the class, same as the bare form's test above but for
    # the explicit-args parsing/lookahead path specifically.
    _parses_clean(
        "class Box<T?> {\n"
        "    value: T?;\n"
        "\n"
        "    fn Box(value: T?) {\n"
        "        this.value = value;\n"
        "    }\n"
        "\n"
        "    static fn wrap(v: T) -> Box<T> {\n"
        "        return Box<T>(v);\n"
        "    }\n"
        "}\n"
        "\n"
        "b: Box<int32> = Box<int32>.wrap(5);\n"
    )
