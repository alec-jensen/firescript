"""Per-platform runtime bindings.

Each module here defines how the firescript runtime's low-level
`win_*`-style intrinsics map onto a specific OS's actual syscall/library
ABI. `flir/lowering.py` currently wires directly to `platforms.windows`
since that's the only implemented target (see `firescript/targets.py`);
a future Linux/macOS/bare-metal target would add a sibling module here.
"""
