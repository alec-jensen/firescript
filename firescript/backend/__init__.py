"""firescript native backend: self-hosted assembler and executable writer.

The compiler emits no C and shells out to no external tools. This package
is split by concern: `backend.<arch>` turns assembly text into machine
code (an `ObjectImage`), and `backend.<platform>` turns that image into a
runnable executable for a specific OS. See `firescript/targets.py` for
which (platform, arch) combinations are currently implemented.
"""
