from __future__ import annotations

# Utility helpers for value category queries used by semantic analysis and codegen.
# Copyable vs Owned is a language-level concept described in docs/reference/memory_management.md.
# Current MVP assumptions:
# - Copyable: bool, char, string, all fixed-width ints (int8/16/32/64, uint8/16/32/64), floats (float32/64/128), arrays (T[])
# - Owned: none (for now)
# Future Owned types: user-defined objects, closures, etc.

_NUMERIC_INTS = {
    "int8", "int16", "int32", "int64",
    "uint8", "uint16", "uint32", "uint64",
}

_NUMERIC_FLOATS = {"float32", "float64", "float128"}

_COPYABLE_BASE = _NUMERIC_INTS | _NUMERIC_FLOATS | {"bool", "char", "string"}


def is_copyable(base_type: str | None, is_array: bool) -> bool:
    """Return True if a value with the given base type and array flag is Copyable.

    Arrays are Owned by definition in the MVP. Scalars in _COPYABLE_BASE are Copyable.
    """
    if base_type is None:
        return False
    if is_array:
        return True
    return base_type in _COPYABLE_BASE


def is_owned(base_type: str | None, is_array: bool) -> bool:
    """Return True if this value is considered Owned in the MVP.

    MVP rule: no types are Owned yet.
    """
    return False
