#!/usr/bin/env python3
"""
End-to-end test for imports: builds a tiny temp project with two modules, compiles entry with
--enable-imports and a custom --import-root, and verifies the output.

Run with:
  python3 tests/imports_e2e_test.py
"""
from __future__ import annotations
import os
import sys
import tempfile
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
MAIN = REPO_ROOT / "firescript" / "main.py"

SIMPLE_A = """
// module a: exports a function and a const
int32 add(int32 x, int32 y) {
    return x + y;
}

string greet() {
    return "hello";
}

int32 TEN = 10;
"""

SIMPLE_B = """
// entry: import module and use its symbols
import a.*

print(add(2, TEN));
print(greet());
"""

def run_cmd(cmd: list[str], cwd: Path | None = None, input_text: str | None = None, timeout: float | None = 10.0):
    p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, input=input_text, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        tdir = Path(tmpdir)
        # Write modules
        (tdir / "a.fire").write_text(SIMPLE_A, encoding="utf-8")
        (tdir / "b.fire").write_text(SIMPLE_B, encoding="utf-8")

        # Compile entry b.fire (imports are now enabled by default)
        cmd = [PY, str(MAIN), str(tdir / "b.fire")]
        code, out, err = run_cmd(cmd, cwd=REPO_ROOT)
        if code != 0:
            print("[FAIL] compile\n", out, err)
            sys.exit(1)

        # Binary lives in build/b
        bin_path = REPO_ROOT / "build" / "b"
        if not bin_path.exists():
            print("[FAIL] binary missing:", bin_path)
            sys.exit(1)

        code, out, err = run_cmd([str(bin_path)], cwd=REPO_ROOT)
        if code != 0:
            print("[FAIL] run\n", out, err)
            sys.exit(1)

        norm = "\n".join(line.rstrip() for line in out.replace("\r\n", "\n").split("\n")).strip() + "\n"
        expected = "12\nhello\n"
        if norm != expected:
            print("[FAIL] unexpected output\nActual:\n", norm, "Expected:\n", expected)
            sys.exit(1)

        print("OK: imports e2e passed")


if __name__ == "__main__":
    main()
