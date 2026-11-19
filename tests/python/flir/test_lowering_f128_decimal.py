"""Direct unit tests for firescript.flir.lowering._decimal_to_f128_bits.

This helper converts a decimal float literal's source text into an IEEE
binary128 (lo, hi) qword pair. It is only reachable from real firescript
source through a `float128`-typed FloatLiteralInst, and many of its edge
cases (subnormals, rounding ties, overflow-after-carry, malformed text)
are impractical or impossible to trigger through the compiler's lexer/
parser pipeline. Per the "drive the pass directly" pattern used elsewhere
in this suite (e.g. tests/python/flir/test_verifier_types.py), we call the
function directly with hand-crafted decimal strings.

Test values for the deep-subnormal / rounding-carry cases were derived
with fractions.Fraction arithmetic offline (see comments) to land exactly
on round-half-even tie points and clamp/overflow boundaries; they are
hardcoded here as plain strings so the test itself has no dependency on
that derivation machinery.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "firescript"))

from flir.lowering import _decimal_to_f128_bits, _round_half_even  # noqa: E402
from fractions import Fraction  # noqa: E402


def test_nan_text():
    lo, hi = _decimal_to_f128_bits("nan")
    assert lo == 0
    assert hi == (0x7FFF << 48) | (1 << 47)


def test_negative_nan_sets_sign_bit():
    lo, hi = _decimal_to_f128_bits("-nan")
    assert lo == 0
    assert hi == (1 << 63) | (0x7FFF << 48) | (1 << 47)


def test_inf_text():
    lo, hi = _decimal_to_f128_bits("inf")
    assert (lo, hi) == (0, 0x7FFF << 48)


def test_infinity_alias_text():
    lo, hi = _decimal_to_f128_bits("infinity")
    assert (lo, hi) == (0, 0x7FFF << 48)


def test_negative_infinity():
    lo, hi = _decimal_to_f128_bits("-infinity")
    assert (lo, hi) == (0, (1 << 63) | (0x7FFF << 48))


def test_leading_plus_sign():
    # Sign handling for '+' must not set the sign bit, unlike '-'.
    _, hi_pos = _decimal_to_f128_bits("+1.5")
    _, hi_neg = _decimal_to_f128_bits("-1.5")
    assert hi_pos >> 63 == 0
    assert hi_neg >> 63 == 1


def test_f128_suffix_is_stripped():
    a = _decimal_to_f128_bits("-1.5f128")
    b = _decimal_to_f128_bits("-1.5")
    assert a == b


def test_malformed_text_falls_back_to_zero():
    # Fraction(...) raises ValueError for text it can't parse.
    assert _decimal_to_f128_bits("garbage!!!") == (0, 0)


def test_positive_zero():
    assert _decimal_to_f128_bits("0.0") == (0, 0)


def test_negative_zero_sets_sign_bit_only():
    lo, hi = _decimal_to_f128_bits("-0.0")
    assert (lo, hi) == (0, 1 << 63)


def test_overflow_to_infinity_before_rounding():
    # Absurdly large magnitude: biased exponent exceeds EXP_MAX outright.
    lo, hi = _decimal_to_f128_bits("1e5000")
    assert (lo, hi) == (0, 0x7FFF << 48)


def test_underflow_to_zero():
    # Absurdly small magnitude: even the smallest subnormal rounds to 0.
    assert _decimal_to_f128_bits("1e-5000") == (0, 0)


def test_subnormal_rounds_to_nonzero_value():
    lo, hi = _decimal_to_f128_bits("1e-4950")
    assert (lo, hi) != (0, 0)
    # Must stay in the subnormal range: biased exponent field is 0.
    assert (hi >> 48) & 0x7FFF == 0


def test_subnormal_rounding_carries_into_smallest_normal():
    # Derived so that frac*2**shift == 2**112 - 0.4, which round-half-even
    # rounds *up* to exactly 2**112 -- one past the largest representable
    # subnormal significand. The carry must land on the smallest normal
    # number (biased exponent 1, zero significand), not clamp (regression B12).
    text = "3.36210314311209350626267781732175234359107456732546680313127e-4932"
    lo, hi = _decimal_to_f128_bits(text)
    assert lo == 0
    assert hi == 1 << 48
    # Same value with a minus sign keeps the sign bit.
    lo_n, hi_n = _decimal_to_f128_bits("-" + text)
    assert lo_n == 0
    assert hi_n == (1 << 63) | (1 << 48)


def test_subnormal_rounding_just_below_carry_stays_subnormal():
    # 2**112 - 0.6 rounds down to the largest subnormal significand.
    from fractions import Fraction
    frac = (Fraction(2) ** 112 - Fraction(6, 10)) / Fraction(2) ** 16494
    digits = 80
    from decimal import Decimal, getcontext
    getcontext().prec = digits
    text = format(Decimal(frac.numerator) / Decimal(frac.denominator), ".70e")
    lo, hi = _decimal_to_f128_bits(text)
    sig = (hi & 0xFFFFFFFFFFFF) << 64 | lo
    assert sig == (1 << 112) - 1
    assert (hi >> 48) & 0x7FFF == 0


def test_round_half_even_ties_to_even_significand():
    # Two decimal strings constructed (via Fraction arithmetic offline) so
    # that the rounded significand fraction sits exactly halfway between
    # two integers -- one where the lower candidate is odd (rounds up)
    # and one where it is even (stays put). Both must land on the same
    # (even) final significand of 4.
    odd_floor_tie = (
        "1.00000000000000000000000000000000067407548053553254856959227"
        "990472456148833557687538586833397857844829559326171875"
    )
    even_floor_tie = (
        "1.00000000000000000000000000000000086666847497425613387519007"
        "416321729334214574169692468785797245800495147705078125"
    )
    lo_odd, hi_odd = _decimal_to_f128_bits(odd_floor_tie)
    lo_even, hi_even = _decimal_to_f128_bits(even_floor_tie)
    assert lo_odd == 4
    assert lo_even == 4


def test_rounding_carry_bumps_exponent_without_overflow():
    # frac is just below 2.0 with a mantissa that rounds all the way up to
    # exactly 2.0, carrying into the exponent field (sig resets to 0).
    text = "1.99999999999999999999999999999999992296280222451056587776088"
    lo, hi = _decimal_to_f128_bits(text)
    assert lo == 0
    biased_exp = (hi >> 48) & 0x7FFF
    assert biased_exp == 16383 + 1  # value is exactly 2.0


def test_rounding_carry_overflows_to_infinity():
    # frac sits just ABOVE the largest finite binary128 value (by more than
    # half an ulp), so it rounds up past it, carrying the exponent beyond
    # EXP_MAX and producing infinity.
    text = "1.18973149535723176508575932662800708493665443331458376069548e4932"
    lo, hi = _decimal_to_f128_bits(text)
    assert (lo, hi) == (0, 0x7FFF << 48)


def test_round_half_even_helper_directly():
    assert _round_half_even(Fraction(5, 2)) == 2  # ties to even (2)
    assert _round_half_even(Fraction(7, 2)) == 4  # ties to even (4)
    assert _round_half_even(Fraction(5, 4)) == 1  # rounds down
    assert _round_half_even(Fraction(7, 4)) == 2  # rounds up


def test_suffix_stripped_other_float_suffixes():
    a = _decimal_to_f128_bits("2.25")
    for suf in ("f64", "f32", "f16"):
        b = _decimal_to_f128_bits(f"2.25{suf}")
        assert a == b, f"suffix {suf}: {a} != {b}"


def test_negative_overflow_to_infinity():
    # Overflow keeps the sign: -infinity, not +infinity.
    lo, hi = _decimal_to_f128_bits("-1e5000")
    assert (lo, hi) == (0, (1 << 63) | (0x7FFF << 48))


def test_negative_underflow_to_zero():
    # Underflow keeps the sign: -0, not +0.
    assert _decimal_to_f128_bits("-1e-5000") == (0, 1 << 63)


def test_round_half_even_below_half():
    assert _round_half_even(Fraction(1, 3)) == 0, "1/3 should round down"


def test_round_half_even_above_half():
    assert _round_half_even(Fraction(2, 3)) == 1, "2/3 should round up"
