"""Platform-specific native backend: Windows PE32+ executables.

Turns an arch backend's `ObjectImage` into a runnable Windows executable,
building the import table by hand. No external tools.
"""
