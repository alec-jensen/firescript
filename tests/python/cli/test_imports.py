"""--emit-deps and import-resolution CLI behavior."""
from __future__ import annotations

import os

from harness import pyunit as t

SOURCES_DIR = t.sources_dir


def test_emit_deps():
    # cwd=tmp: --emit-deps has no -o override, so an isolated cwd keeps this
    # from racing other parallel tests writing into the shared build/ dir.
    src = os.path.join(SOURCES_DIR, "imports", "imports_multi.fire")
    with t.tmpdir() as tmp:
        deps_out = os.path.join(tmp, "build", "imports_multi.d")
        proc = t.run_compiler(["--emit-deps", "--check", src], cwd=tmp)
        t.require_eq(proc.returncode, 0, proc.stderr)
        t.require(os.path.exists(deps_out))
        content = open(deps_out, encoding="utf-8").read()
        t.require("imports_multi.o:" in content, content)
        t.require("math_utils.fire" in content and "string_utils.fire" in content, content)


def test_emit_deps_no_imports():
    src = os.path.join(SOURCES_DIR, "classes", "classes_smoke.fire")
    with t.tmpdir() as tmp:
        deps_out = os.path.join(tmp, "build", "classes_smoke.d")
        proc = t.run_compiler(["--emit-deps", "--check", src], cwd=tmp)
        t.require_eq(proc.returncode, 0, proc.stderr)
        t.require(not os.path.exists(deps_out), "no deps file expected for an import-free source")


def test_import_not_found_compile():
    with t.tmpdir() as tmp:
        src = os.path.join(tmp, "missing_import.fire")
        with open(src, "w", encoding="utf-8") as f:
            f.write("import definitely_missing_module.helper;\nx: int32 = helper(1);\n")
        proc = t.run_compiler([src])
        t.require_eq(proc.returncode, 1)
        combined = proc.stdout + proc.stderr
        t.require("Import resolution failed" in combined, combined)


def test_import_with_syntax_error():
    with t.tmpdir() as tmp:
        src = os.path.join(tmp, "bad_after_merge.fire")
        with open(src, "w", encoding="utf-8") as f:
            f.write("import @firescript/std.io.println;\nx: int32 = ;\nprintln(x);\n")
        proc = t.run_compiler([src])
        t.require_eq(proc.returncode, 1)
