"""Direct unit tests for firescript/flir/lowering.py's
_decimal_to_f128_bits(): a pure decimal-string -> IEEE binary128 (lo, hi)
converter used when lowering a float128 literal to its rodata bit pattern.
Covers the sign-prefix, inf/nan, scientific-notation, and malformed-input
fallback branches that a normal .fire program (which only ever produces
plain decimal float128 literals) doesn't exercise."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from flir.lowering import _decimal_to_f128_bits  # noqa: E402
from support import float128_oracle as oracle  # noqa: E402
from fractions import Fraction  # noqa: E402


def test_positive_sign_prefix():
    lo_plain, hi_plain = _decimal_to_f128_bits("1.5")
    lo_signed, hi_signed = _decimal_to_f128_bits("+1.5")
    t.require_eq((lo_plain, hi_plain), (lo_signed, hi_signed))


def test_negative_sign_prefix_sets_sign_bit():
    lo_pos, hi_pos = _decimal_to_f128_bits("1.5")
    lo_neg, hi_neg = _decimal_to_f128_bits("-1.5")
    t.require_eq(lo_pos, lo_neg)
    t.require_eq(hi_neg, hi_pos | (1 << 63))


def test_infinity_positive():
    lo, hi = _decimal_to_f128_bits("inf")
    t.require_eq(lo, 0)
    t.require_eq(hi, 0x7FFF << 48)


def test_infinity_named_infinity():
    lo, hi = _decimal_to_f128_bits("infinity")
    t.require_eq(lo, 0)
    t.require_eq(hi, 0x7FFF << 48)


def test_infinity_negative():
    lo, hi = _decimal_to_f128_bits("-inf")
    t.require_eq(lo, 0)
    t.require_eq(hi, (1 << 63) | (0x7FFF << 48))


def test_nan():
    lo, hi = _decimal_to_f128_bits("nan")
    t.require_eq(lo, 0)
    t.require_eq(hi, (0x7FFF << 48) | (1 << 47))


def test_scientific_notation():
    lo, hi = _decimal_to_f128_bits("1.5e2")
    lo_expanded, hi_expanded = _decimal_to_f128_bits("150")
    t.require_eq((lo, hi), (lo_expanded, hi_expanded))


def test_scientific_notation_negative_exponent():
    lo, hi = _decimal_to_f128_bits("15e-1")
    lo_expanded, hi_expanded = _decimal_to_f128_bits("1.5")
    t.require_eq((lo, hi), (lo_expanded, hi_expanded))


def test_malformed_text_falls_back_to_zero():
    t.require_eq(_decimal_to_f128_bits("not-a-number"), (0, 0))


def test_zero_division_falls_back_to_zero():
    t.require_eq(_decimal_to_f128_bits("1/0"), (0, 0))


def test_f128_suffix_is_stripped():
    lo, hi = _decimal_to_f128_bits("2.0f128")
    lo_plain, hi_plain = _decimal_to_f128_bits("2.0")
    t.require_eq((lo, hi), (lo_plain, hi_plain))


def _oracle_halves(text: str) -> tuple:
    bits = oracle.from_fraction(Fraction(text))
    return oracle.to_halves(bits)


def test_overflow_to_infinity_matches_oracle():
    text = "1e5000"  # far beyond binary128's max finite exponent
    t.require_eq(_decimal_to_f128_bits(text), _oracle_halves(text))


def test_subnormal_matches_oracle():
    # ~2^-16400, deep in subnormal range (min normal exponent is -16382).
    text = "1e-4940"
    t.require_eq(_decimal_to_f128_bits(text), _oracle_halves(text))


def test_underflow_to_zero_matches_oracle():
    text = "1e-6000"  # smaller than the minimum subnormal
    t.require_eq(_decimal_to_f128_bits(text), _oracle_halves(text))


def test_rounding_carry_into_exponent_matches_oracle():
    # 2 - 2^-113: significand rounds up to exactly 2^112, carrying into the
    # exponent field (sig resets to 0, biased_exp += 1).
    text = str(Fraction(2) - Fraction(1, 2**113))
    t.require_eq(_decimal_to_f128_bits(text), _oracle_halves(text))


def test_round_half_even_ties_to_even_both_directions():
    # A value exactly halfway between two representable significands, once
    # with an even truncated significand (stays put) and once with an odd
    # one (rounds up) -- exercises both branches of _round_half_even's tie
    # case at once via oracle cross-checks on either side of the tie.
    base = Fraction(1) + Fraction(1, 2**113)  # tie between sig=0 and sig=1
    t.require_eq(_decimal_to_f128_bits(str(base)), _oracle_halves(str(base)))
    base2 = Fraction(1) + Fraction(3, 2**113)  # tie between sig=1 and sig=2
    t.require_eq(_decimal_to_f128_bits(str(base2)), _oracle_halves(str(base2)))
