"""Unit tests for firescript/flir/lowering.py's decimal-to-binary128
converter (`_decimal_to_f128_bits`) and its round-half-even helper
(`_round_half_even`).

float128 literals are lowered to IEEE binary128 bit patterns entirely with
exact big-integer arithmetic (fractions.Fraction) -- no third-party
mpmath/decimal128 dependency. This directly drives that pure function with
edge-case decimal strings (signs, suffixes, special values, subnormals,
overflow, and rounding-carry-into-exponent, including carry that itself
overflows to infinity) rather than compiling float128 .fire sources for
each case, since exercising every IEEE corner this way from source would
require impractically extreme literal values."""
from __future__ import annotations

import os
import sys
from fractions import Fraction

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from flir.lowering import _decimal_to_f128_bits, _round_half_even  # noqa: E402

SIGN_BIT = 1 << 63


def _is_negative(hi: int) -> bool:
    return bool(hi & SIGN_BIT)


def test_positive_zero():
    lo, hi = _decimal_to_f128_bits("0")
    t.require((lo, hi) == (0, 0), f"got ({lo}, {hi})")


def test_negative_zero():
    lo, hi = _decimal_to_f128_bits("-0")
    t.require(lo == 0 and _is_negative(hi), f"got ({lo}, {hi})")


def test_explicit_plus_sign():
    pos_lo, pos_hi = _decimal_to_f128_bits("1.5")
    plus_lo, plus_hi = _decimal_to_f128_bits("+1.5")
    t.require((pos_lo, pos_hi) == (plus_lo, plus_hi), "leading '+' should match unsigned")


def test_suffix_stripped_f128():
    a = _decimal_to_f128_bits("1.5")
    b = _decimal_to_f128_bits("1.5f128")
    t.require(a == b, f"{a} != {b}")


def test_suffix_stripped_other_float_suffixes():
    a = _decimal_to_f128_bits("2.25")
    for suf in ("f64", "f32", "f16"):
        b = _decimal_to_f128_bits(f"2.25{suf}")
        t.require(a == b, f"suffix {suf}: {a} != {b}")


def test_nan():
    lo, hi = _decimal_to_f128_bits("nan")
    t.require(lo == 0, f"NaN lo should be 0, got {lo}")
    t.require((hi >> 48) & 0x7FFF == 0x7FFF, "NaN must have all-ones exponent")
    t.require(hi & ((1 << 48) - 1) != 0, "NaN significand must be nonzero")
    t.require(not _is_negative(hi), "plain 'nan' should not be negative")


def test_negative_nan():
    lo, hi = _decimal_to_f128_bits("-nan")
    t.require(_is_negative(hi), "-nan should carry the sign bit")


def test_infinity_forms():
    a = _decimal_to_f128_bits("inf")
    b = _decimal_to_f128_bits("infinity")
    t.require(a == b, "'inf' and 'infinity' should be identical")
    lo, hi = a
    t.require(lo == 0 and (hi >> 48) & 0x7FFF == 0x7FFF and hi & ((1 << 48) - 1) == 0,
              f"expected +inf bit pattern, got ({lo}, {hi})")


def test_negative_infinity():
    lo, hi = _decimal_to_f128_bits("-inf")
    t.require(_is_negative(hi), "-inf should carry the sign bit")


def test_scientific_notation():
    a = _decimal_to_f128_bits("1.5e2")
    b = _decimal_to_f128_bits("150")
    t.require(a == b, f"1.5e2 should equal 150: {a} != {b}")


def test_negative_scientific_notation():
    lo, hi = _decimal_to_f128_bits("-1.25e-1")
    t.require(_is_negative(hi), "expected sign bit set")


def test_malformed_text_falls_back_to_zero():
    lo, hi = _decimal_to_f128_bits("not_a_number")
    t.require((lo, hi) == (0, 0), f"malformed input should fall back to 0, got ({lo}, {hi})")


def test_overflow_to_infinity():
    lo, hi = _decimal_to_f128_bits("1e5000")
    t.require(lo == 0 and (hi >> 48) & 0x7FFF == 0x7FFF and hi & ((1 << 48) - 1) == 0,
              f"expected overflow to +inf, got ({lo}, {hi})")


def test_negative_overflow_to_infinity():
    lo, hi = _decimal_to_f128_bits("-1e5000")
    t.require(_is_negative(hi), "expected sign bit set on overflowed negative value")


def test_underflow_to_zero():
    lo, hi = _decimal_to_f128_bits("1e-5000")
    t.require((lo, hi) == (0, 0), f"expected underflow to 0, got ({lo}, {hi})")


def test_negative_underflow_to_zero():
    lo, hi = _decimal_to_f128_bits("-1e-5000")
    t.require(lo == 0 and _is_negative(hi), f"expected -0, got ({lo}, {hi})")


def test_subnormal_nonzero():
    # Near the underflow boundary but still representable as a nonzero
    # subnormal (biased_exp == 0, no implicit leading bit).
    lo, hi = _decimal_to_f128_bits("1e-4935")
    t.require((lo, hi) != (0, 0), "expected a nonzero subnormal result")
    t.require((hi >> 48) & 0x7FFF == 0, f"expected biased exponent 0 (subnormal), got hi={hi:#x}")


def test_rounding_carry_into_exponent_without_overflow():
    # 1.999...9 (well within binary128 precision) rounds up to exactly 2.0,
    # carrying the significand overflow into the exponent field without
    # exceeding the maximum exponent.
    lo, hi = _decimal_to_f128_bits("1." + "9" * 40)
    t.require(lo == 0, f"expected exact 2.0 (lo=0), got lo={lo}")
    biased_exp = (hi >> 48) & 0x7FFF
    t.require(biased_exp == 16384, f"expected biased exponent 16384 (2.0), got {biased_exp}")


def test_rounding_carry_overflows_to_infinity():
    # A value exactly half an ULP above the largest finite binary128 value
    # (an odd significand, so round-half-even rounds up) must round-carry
    # past the maximum exponent into +infinity -- this is the "overflow
    # after rounding" branch, distinct from the pre-rounding overflow
    # check (a value already >= 2^(e+1) before rounding).
    text = (
        "1.1897314953572317650857593266280070734799568698691021415011868527227124689678980396"
        "147313041605370567205087355247942180593264664074412459444736117251434132484671667965455"
        "130801840045255124679702103170E+4932"
    )
    lo, hi = _decimal_to_f128_bits(text)
    t.require(lo == 0 and (hi >> 48) & 0x7FFF == 0x7FFF and hi & ((1 << 48) - 1) == 0,
              f"expected rounding-carry overflow to +inf, got ({lo}, {hi})")


def test_round_half_even_rounds_up():
    t.require(_round_half_even(Fraction(5, 2)) == 2, "2.5 should round to even (2)")


def test_round_half_even_rounds_down_to_even():
    t.require(_round_half_even(Fraction(7, 2)) == 4, "3.5 should round to even (4)")


def test_round_half_even_below_half():
    t.require(_round_half_even(Fraction(1, 3)) == 0, "1/3 should round down")


def test_round_half_even_above_half():
    t.require(_round_half_even(Fraction(2, 3)) == 1, "2/3 should round up")
