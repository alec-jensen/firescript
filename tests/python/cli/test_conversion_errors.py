"""Conversion-stage (AST->FIR) failures print a coded diagnostic, never a raw
Python traceback. These constructs pass --check (the front end accepts them)
so they can only be exercised through a full compile."""
from __future__ import annotations

import json
import os

from harness import pyunit as t

_MOVE_GLOBAL = (
    "import @firescript/std.io.println;\n"
    "s: string = \"x\";\n"
    "fn f() -> void {\n"
    "    t: string = s;\n"
    "    println(t);\n"
    "}\n"
    "f();\n"
)

_DIRECTIVE_IN_FN = (
    "fn f() -> void {\n"
    "    directive enable_lowlevel_runtime;\n"
    "}\n"
    "f();\n"
)


def _compile(source: str):
    with t.tmpdir() as tmp:
        path = os.path.join(tmp, "a.fire")
        with open(path, "w", encoding="utf-8") as f:
            f.write(source)
        return t.run_compiler(["--message-format", "json", path, "-o", os.path.join(tmp, "a.out")], cwd=tmp)


def _diagnostics(proc):
    events = [json.loads(line) for line in proc.stdout.splitlines() + proc.stderr.splitlines() if line.startswith("{")]
    return [e for e in events if e.get("type") == "diagnostic"]


_CASES = {
    "move_owned_global": (_MOVE_GLOBAL, 4),
    "directive_in_function": (_DIRECTIVE_IN_FN, 2),
}


@t.params(sorted(_CASES))
def test_conversion_error_is_coded_diagnostic(name):
    source, line = _CASES[name]
    proc = _compile(source)
    t.require(proc.returncode != 0, "compilation should fail")
    t.require("Traceback" not in proc.stdout + proc.stderr, proc.stderr)
    diags = _diagnostics(proc)
    t.require_eq(len(diags), 1)
    t.require_eq(diags[0]["code"], "FS-CGEN-0002")
    t.require_eq(diags[0]["line"], line)
