"""--emit ast/asm/fir and -o output-path behavior."""
from __future__ import annotations

import os

from harness import pyunit as t

SOURCES_DIR = t.sources_dir


def test_emit_ast():
    # cwd=tmp: --emit ast writes relative to cwd with no -o override for
    # this case, and running in an isolated tmpdir avoids racing other
    # parallel tests that also compile functions.fire into the shared
    # build/ directory.
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    with t.tmpdir() as tmp:
        ast_out = os.path.join(tmp, "build", "functions.ast")
        proc = t.run_compiler(["--emit", "ast", src], cwd=tmp)
        t.require_eq(proc.returncode, 0, proc.stderr)
        t.require(os.path.exists(ast_out))
        t.require(os.path.getsize(ast_out) > 0)


def test_emit_asm():
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    with t.tmpdir() as tmp:
        asm_out = os.path.join(tmp, "build", "temp", "functions.s")
        proc = t.run_compiler(["--emit", "asm", src], cwd=tmp)
        t.require_eq(proc.returncode, 0, proc.stderr)
        t.require(os.path.exists(asm_out))


def test_emit_fir_only():
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    with t.tmpdir() as tmp:
        fir_out = os.path.join(tmp, "build", "functions.fir")
        proc = t.run_compiler(["--emit-fir", src], cwd=tmp)
        t.require_eq(proc.returncode, 0, proc.stderr)
        t.require(os.path.exists(fir_out))


def test_emit_asm_output_path():
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    with t.tmpdir() as tmp:
        out_path = os.path.join(tmp, "custom.s")
        proc = t.run_compiler(["--emit", "asm", "-o", out_path, src])
        t.require_eq(proc.returncode, 0, proc.stderr)
        t.require(os.path.exists(out_path))


def test_emit_ast_output_rename():
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    with t.tmpdir() as tmp:
        out_path = os.path.join(tmp, "renamed.ast")
        proc = t.run_compiler(["--emit", "ast", "-o", out_path, src])
        t.require_eq(proc.returncode, 0, proc.stderr)
        t.require(os.path.exists(out_path))


def test_emit_ast_output_rename_failure_exits_nonzero():
    # -o points inside a directory that doesn't exist, so compile_file's
    # internal write to build/<name>.ast succeeds but the final
    # shutil.move(...) to the requested -o path raises.
    src = os.path.join(SOURCES_DIR, "functions", "functions.fire")
    with t.tmpdir() as tmp:
        out_path = os.path.join(tmp, "no_such_subdir", "renamed.ast")
        proc = t.run_compiler(["--emit", "ast", "-o", out_path, src])
        t.require_eq(proc.returncode, 1)
        t.require("Failed to move output" in (proc.stdout + proc.stderr))
