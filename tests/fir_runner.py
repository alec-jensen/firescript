#!/usr/bin/env python3
"""Differential test harness for the FIR pipeline.

Runs the full golden suite through `--backend c-fir` (AST -> FIR -> FLIR
-> C). The goldens are the same as the legacy pipeline's, so a green run
means output parity. This harness is migration scaffolding and is removed
once the FIR pipeline becomes the default.

Usage:
    python tests/fir_runner.py [golden_runner args...]
"""

import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    cmd = [
        sys.executable,
        os.path.join(REPO_ROOT, "tests", "golden_runner.py"),
        "--backend",
        "c-fir",
    ] + sys.argv[1:]
    sys.exit(subprocess.run(cmd, cwd=REPO_ROOT).returncode)
