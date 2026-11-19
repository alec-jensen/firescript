from __future__ import annotations
from typing import Optional

# Compile-time handling of numeric literals shared by the parser's type
# checker and the semantic analyzer: range checks for fixed-width integer
# literals, and typing an unsuffixed literal from the type it initializes
# (docs/reference/type_system.md, "Type Inference for Literals").

INT_RANGES = {
    "int8": (-(2 ** 7), 2 ** 7 - 1),
    "int16": (-(2 ** 15), 2 ** 15 - 1),
    "int32": (-(2 ** 31), 2 ** 31 - 1),
    "int64": (-(2 ** 63), 2 ** 63 - 1),
    "uint8": (0, 2 ** 8 - 1),
    "uint16": (0, 2 ** 16 - 1),
    "uint32": (0, 2 ** 32 - 1),
    "uint64": (0, 2 ** 64 - 1),
}

INT_LITERAL_SUFFIXES = ("i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64")


def unsuffixed_literal_of(node) -> Optional[tuple]:
    """If `node` is an unsuffixed numeric literal (optionally under a unary
    +/-), return (literal_node, is_negated); else None."""
    negated = False
    lit = node
    if (
        node.node_type.name == "UNARY_EXPRESSION"
        and node.name in ("+", "-")
        and len(node.children) == 1
    ):
        negated = node.name == "-"
        lit = node.children[0]
    if lit.node_type.name != "LITERAL" or lit.token is None:
        return None
    if lit.token.type == "DOUBLE_LITERAL":
        return lit, negated
    if lit.token.type == "INTEGER_LITERAL":
        text = str(lit.token.value).replace("_", "").lower()
        if any(text.endswith(sfx) for sfx in INT_LITERAL_SUFFIXES):
            return None
        return lit, negated
    return None


def int_literal_value(lit) -> Optional[int]:
    text = str(lit.token.value).replace("_", "").lower()
    for sfx in INT_LITERAL_SUFFIXES:
        if text.endswith(sfx):
            text = text[: -len(sfx)]
            break
    try:
        return int(text, 0) if text[:2] in ("0x", "0b", "0o") else int(text, 10)
    except ValueError:
        return None


def literal_range_error(lit, type_name: str) -> Optional[str]:
    """Return an error message if integer literal `lit` does not fit in
    `type_name`, taking a unary minus parent into account."""
    rng = INT_RANGES.get(type_name)
    if rng is None or lit.token is None or lit.token.type != "INTEGER_LITERAL":
        return None
    value = int_literal_value(lit)
    if value is None:
        return None
    parent = lit.parent
    if (
        parent is not None
        and parent.node_type.name == "UNARY_EXPRESSION"
        and parent.name == "-"
        and len(parent.children) == 1
    ):
        value = -value
    lo, hi = rng
    if value < lo or value > hi:
        if lo == 0 and value < 0:
            return f"Negative literal {value} is invalid for unsigned type {type_name}"
        return f"Integer literal {value} is out of range for type {type_name} ({lo} to {hi})"
    return None


def coerce_literal(node, expected: Optional[str]) -> tuple:
    """Type an unsuffixed numeric literal from the type it initializes.

    Returns (applied, error): `applied` is False when `node` is not an
    unsuffixed literal or `expected` is not a numeric type of the literal's
    family (the caller then falls back to the ordinary type comparison). On
    success the literal's (and any enclosing unary's) return_type becomes
    `expected`, so FIR conversion emits it with that type."""
    if not expected:
        return False, None
    found = unsuffixed_literal_of(node)
    if found is None:
        return False, None
    lit, _negated = found
    if lit.token.type == "INTEGER_LITERAL":
        if expected not in INT_RANGES:
            return False, None
        lit._literal_coerced = True
        err = literal_range_error(lit, expected)
        if err:
            return True, err
    else:  # DOUBLE_LITERAL
        if expected not in ("float32", "float64"):
            return False, None
        lit._literal_coerced = True
    lit.return_type = expected
    if node is not lit:
        node.return_type = expected
    return True, None
