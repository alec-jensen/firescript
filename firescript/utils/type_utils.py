from __future__ import annotations
from typing import Optional

# Utility helpers for value category queries used by semantic analysis and codegen.
# Copyable vs Owned is a language-level concept described in docs/reference/memory_management.md.
# Current implementation:
# - Copyable: bool, char, string, all fixed-width ints (int8/16/32/64, uint8/16/32/64), floats (float32/64/128)
#            AND classes explicitly marked as 'copyable' (if they satisfy constraints)
# - Owned: arrays (T[]), user-defined classes (unless marked copyable), closures (future)

_NUMERIC_INTS = {
    "int8", "int16", "int32", "int64",
    "uint8", "uint16", "uint32", "uint64",
}

_NUMERIC_FLOATS = {"float32", "float64", "float128"}

_COPYABLE_BASE = _NUMERIC_INTS | _NUMERIC_FLOATS | {"bool", "char", "string"}

# Global registries (populated by parser and semantic analyzer)
# Set of class names that are explicitly marked as copyable
_COPYABLE_CLASSES: set[str] = set()
# Set of all user-defined class names (Owned unless in _COPYABLE_CLASSES)
_USER_CLASSES: set[str] = set()


def register_class(class_name: str, is_copyable: bool = False) -> None:
    """Register a user-defined class and its ownership category."""
    _USER_CLASSES.add(class_name)
    if is_copyable:
        _COPYABLE_CLASSES.add(class_name)
    elif class_name in _COPYABLE_CLASSES:
        _COPYABLE_CLASSES.remove(class_name)


def is_copyable(base_type: str | None, is_array: bool) -> bool:
    """Return True if a value with the given base type and array flag is Copyable.

    Per spec:
    - Arrays are Owned (not Copyable)
    - Primitive scalars in _COPYABLE_BASE are Copyable
    - User classes are Copyable only if explicitly marked 'copyable'
    """
    if base_type is None:
        return False
    if is_array:
        # Arrays are Owned per spec
        return False
    # Check primitive copyables
    if base_type in _COPYABLE_BASE:
        return True
    # Check copyable classes
    if base_type in _COPYABLE_CLASSES:
        return True
    return False


def is_owned(base_type: str | None, is_array: bool) -> bool:
    """Return True if this value is considered Owned.

    Per spec:
    - Arrays are always Owned
    - User-defined classes are Owned unless explicitly marked copyable
    - Closures will be Owned (future)
    - Primitive scalars are not Owned (they're Copyable)
    """
    if base_type is None:
        return False
    if is_array:
        # Arrays are always Owned
        return True
    # User-defined classes are Owned unless copyable
    if base_type in _USER_CLASSES:
        return base_type not in _COPYABLE_CLASSES
    # Everything else (primitives) is not Owned
    return False


def is_user_class(base_type: str | None) -> bool:
    """Return True if this is a user-defined class."""
    return base_type in _USER_CLASSES if base_type else False


def reset_registries() -> None:
    """Clear all type registries (used for testing)."""
    _COPYABLE_CLASSES.clear()
    _USER_CLASSES.clear()
