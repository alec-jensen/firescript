"""
float128_oracle.py — IEEE 754 binary128 (quad-precision) correctness oracle.

Pure Python standard library only: fractions, decimal, struct, math (integer ops).
No Python float (binary64) is used as an intermediate for any precision-sensitive
computation.  All arithmetic is exact rational (fractions.Fraction) → rounded to
binary128 with round-to-nearest-even.

REPRESENTATION CONTRACT
=======================
A binary128 value is represented throughout as a 128-bit unsigned integer (the
raw IEEE bit pattern).

Layout:
  bit 127     : sign  (s)
  bits 126-112: biased exponent (e), 15 bits, bias = 16383
  bits 111-0  : trailing significand (t), 112 bits

  • Normal   (1 ≤ e ≤ 0x7FFE): value = (-1)^s · 2^(e-16383) · (1 + t/2^112)
  • Subnormal (e == 0, t != 0): value = (-1)^s · 2^(1-16383) · (t/2^112)
  • Zero      (e == 0, t == 0): ±0
  • Infinity  (e == 0x7FFF, t == 0): ±∞
  • NaN       (e == 0x7FFF, t != 0): NaN  (quiet NaN: bit 111 set)

128-bit pattern ↔ two uint64 halves (little-endian):
  LO = bits[63:0]
  HI = bits[127:64]  ← sign|exp|significand[111:64]

Public API
==========
  pack(sign, exp, sig) -> int128
  unpack(bits128) -> (sign, exp, sig)
  to_halves(bits128) -> (lo, hi)
  from_halves(lo, hi) -> int128
  to_fraction(bits128) -> fractions.Fraction | str   ('nan', '+inf', '-inf')
  from_fraction(frac, sign_of_zero=0) -> int128

  add(a, b) -> int128
  sub(a, b) -> int128
  mul(a, b) -> int128
  div(a, b) -> int128

  eq(a, b) -> bool
  ne(a, b) -> bool
  lt(a, b) -> bool
  le(a, b) -> bool
  gt(a, b) -> bool
  ge(a, b) -> bool

  from_int(n) -> int128          (any Python int, correctly rounded)
  to_int(a) -> int               (truncate toward zero; inf/nan → 0)
  from_f64(bits64) -> int128     (exact: binary64 ⊆ binary128)
  to_f64(a) -> int               (correctly rounded binary64 bit pattern)
  parse(s) -> int128             (decimal string, correctly rounded)
  format_f(a) -> str             (printf %f: fixed, 6 frac digits)
  format_g(a) -> str             (printf %g: 6 sig digits, sci/fixed)

  vectors() -> list              (comprehensive test-vector list)

Edge-case decisions
===================
• NaN propagation: if either operand is NaN, return a canonical quiet NaN
  (sign=0, exp=0x7FFF, sig=2^111, i.e. only the quiet bit set).
• to_int(inf / nan) → 0  (documented).
• Signed zero: 0+0=+0, (-0)+(-0)=-0, (+0)+(-0)=+0,
  (+0)-0=+0, (-0)-(-0)=+0 (IEEE subtractive cancel).
• div(±0, ±0) → NaN (IEEE).
• div(finite, ±0) → ±inf (IEEE, sign = XOR of operand signs).
• Overflow → ±inf.
• Underflow to subnormal is handled; underflow below smallest subnormal → ±0.
"""

from fractions import Fraction
import struct
import math

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SIGN_SHIFT = 127
_EXP_SHIFT  = 112
_EXP_MASK   = 0x7FFF          # 15 bits
_SIG_MASK   = (1 << 112) - 1  # 112 bits (trailing significand)
_BIAS       = 16383
_QNAN_BITS  = (0x7FFF << 112) | (1 << 111)   # canonical quiet NaN

_POS_INF = 0x7FFF << 112
_NEG_INF = (1 << 127) | (0x7FFF << 112)
_POS_ZERO = 0
_NEG_ZERO = 1 << 127

# Smallest positive subnormal: e=0, t=1
_MIN_SUBNORMAL = 1
# Largest finite: e=0x7FFE, t=all-ones
_MAX_FINITE_SIG = _SIG_MASK
_MAX_FINITE = (0x7FFE << 112) | _SIG_MASK

_F128_MAX_EXP = 0x7FFE  # largest finite biased exponent

# ---------------------------------------------------------------------------
# Packing / unpacking
# ---------------------------------------------------------------------------

def pack(sign: int, exp: int, sig: int) -> int:
    """Pack (sign, biased_exp, trailing_sig) into a 128-bit raw pattern."""
    return ((sign & 1) << 127) | ((exp & 0x7FFF) << 112) | (sig & _SIG_MASK)


def unpack(bits128: int) -> tuple:
    """Return (sign, biased_exp, trailing_sig) from a 128-bit raw pattern."""
    sign = (bits128 >> 127) & 1
    exp  = (bits128 >> 112) & 0x7FFF
    sig  = bits128 & _SIG_MASK
    return sign, exp, sig


def to_halves(bits128: int) -> tuple:
    """Return (lo, hi) where lo = bits[63:0], hi = bits[127:64]."""
    lo = bits128 & ((1 << 64) - 1)
    hi = (bits128 >> 64) & ((1 << 64) - 1)
    return lo, hi


def from_halves(lo: int, hi: int) -> int:
    """Reconstruct 128-bit pattern from (lo, hi) halves."""
    return ((hi & ((1 << 64) - 1)) << 64) | (lo & ((1 << 64) - 1))


# ---------------------------------------------------------------------------
# Conversion: raw pattern ↔ exact Fraction
# ---------------------------------------------------------------------------

def to_fraction(bits128: int):
    """
    Convert a 128-bit pattern to an exact Fraction (or 'nan'/'+inf'/'-inf').
    Returns a Fraction for finite values (including ±0).
    """
    sign, exp, sig = unpack(bits128)
    if exp == 0x7FFF:
        if sig != 0:
            return 'nan'
        return '-inf' if sign else '+inf'
    if exp == 0:
        # subnormal / zero: value = (-1)^s * 2^(1-16383) * sig / 2^112
        val = Fraction(sig, 1 << 112) * Fraction(1, 1 << (_BIAS - 1))
    else:
        # normal: value = (-1)^s * 2^(exp-bias) * (1 + sig/2^112)
        mant = Fraction((1 << 112) + sig, 1 << 112)
        e = exp - _BIAS
        if e >= 0:
            val = mant * (1 << e)
        else:
            val = mant * Fraction(1, 1 << (-e))
    return -val if sign else val


def _round_to_f128(frac: Fraction, sign_of_zero: int = 0) -> int:
    """
    Round an exact Fraction to the nearest binary128 value
    (round-to-nearest-even).  Returns the 128-bit raw pattern.

    sign_of_zero: used only when frac == 0 to choose ±0.
    """
    if frac == 0:
        return _NEG_ZERO if sign_of_zero else _POS_ZERO

    negative = frac < 0
    sign = 1 if negative else 0
    abs_val = -frac if negative else frac

    # Find the biased binary exponent of the result.
    # abs_val = m * 2^e where 1 <= m < 2  (normal) or smaller (subnormal).
    # We need integer floor(log2(abs_val)).
    # Use integer arithmetic: find e such that 2^e <= abs_val < 2^(e+1).
    n = abs_val.numerator
    d = abs_val.denominator
    # bit_length of n and d gives us log2 approximation.
    # e = floor(log2(n/d)) = bit_length(n) - bit_length(d) + adjustment
    e = n.bit_length() - d.bit_length()
    # Refine: check if 2^e <= abs_val
    if Fraction(1 << e if e >= 0 else 1, 1 if e >= 0 else (1 << -e)) > abs_val:
        e -= 1

    # Subnormal threshold: e < 1 - bias = 1 - 16383 = -16382
    EMIN = 1 - _BIAS  # = -16382, smallest normal binary exponent

    if e < EMIN - 112:
        # Below the smallest subnormal; round toward zero (underflow to zero).
        # The two candidate values are 0 (sig=0, even) and min_subnormal (sig=1, odd).
        # Exact midpoint = 2^(-16495) = half_min_sub.
        half_min_sub = Fraction(1, 1 << (_BIAS - 1 + 112 + 1))  # 2^(-16495)
        if abs_val > half_min_sub:
            # Above midpoint → round up to min subnormal.
            return pack(sign, 0, 1)
        # At or below midpoint → round to zero.
        # Tie (abs_val == half_min_sub): ties-to-even → 0 (sig=0 is even).
        return _NEG_ZERO if sign else _POS_ZERO

    biased_e = e + _BIAS  # biased exponent for a normal

    if biased_e <= 0:
        # Subnormal result.
        # Subnormal value = sig/2^112 * 2^(1-bias)
        # sig = round(abs_val / 2^(1-bias-112)) = round(abs_val * 2^(bias-1+112))
        shift = _BIAS - 1 + 112  # = 16382 + 112 = 16494
        # Represent abs_val * 2^shift as integer with remainder for rounding.
        scaled = abs_val * (1 << shift)
        sig_int = int(scaled)  # floor
        rem = scaled - sig_int
        sig_int, carry = _rne(sig_int, rem, sig_int & 1)
        if sig_int >= (1 << 112):
            # Carried into normal range.
            return pack(sign, 1, 0)
        return pack(sign, 0, sig_int)
    else:
        # Normal result.
        # Mantissa = abs_val / 2^e, in [1, 2).
        # sig (integer) = (mantissa - 1) * 2^112, rounded to nearest even.
        if e >= 0:
            mantissa = Fraction(abs_val, 1 << e)
        else:
            mantissa = abs_val * (1 << (-e))
        # t_exact = (mantissa - 1) * 2^112
        t_frac = (mantissa - 1) * (1 << 112)
        t_int = int(t_frac)  # floor
        rem = t_frac - t_int
        t_int, carry = _rne(t_int, rem, t_int & 1)
        if t_int >= (1 << 112):
            # Carry into next biased exponent.
            t_int = 0
            biased_e += 1
        if biased_e > _F128_MAX_EXP:
            # Overflow → infinity.
            return _NEG_INF if sign else _POS_INF
        return pack(sign, biased_e, t_int)


def _rne(floor_val: int, rem: Fraction, lsb: int) -> tuple:
    """
    Apply round-to-nearest-even given:
      floor_val : integer floor of the exact value
      rem       : fractional part (a Fraction in [0,1))
      lsb       : the least-significant bit of floor_val (for tie-breaking)

    Returns (rounded_int, carry_occurred).
    """
    if rem > Fraction(1, 2):
        return floor_val + 1, False
    elif rem == Fraction(1, 2):
        # Tie: round to even (round up if lsb is 1, i.e. floor_val is odd).
        if lsb:
            return floor_val + 1, False
        return floor_val, False
    else:
        return floor_val, False


def from_fraction(frac, sign_of_zero: int = 0) -> int:
    """Round a Fraction (or special string) to a binary128 pattern."""
    if frac == 'nan':
        return _QNAN_BITS
    if frac == '+inf':
        return _POS_INF
    if frac == '-inf':
        return _NEG_INF
    return _round_to_f128(frac, sign_of_zero)


# ---------------------------------------------------------------------------
# Special-case helpers
# ---------------------------------------------------------------------------

def _is_nan(bits128: int) -> bool:
    _, exp, sig = unpack(bits128)
    return exp == 0x7FFF and sig != 0


def _is_inf(bits128: int) -> bool:
    _, exp, sig = unpack(bits128)
    return exp == 0x7FFF and sig == 0


def _is_zero(bits128: int) -> bool:
    _, exp, sig = unpack(bits128)
    return exp == 0 and sig == 0


def _sign(bits128: int) -> int:
    return (bits128 >> 127) & 1


def _propagate_nan(a: int, b: int) -> int:
    """Return canonical quiet NaN for NaN propagation."""
    return _QNAN_BITS


# ---------------------------------------------------------------------------
# Arithmetic operations
# ---------------------------------------------------------------------------

def _arith(a: int, b: int, op):
    """
    Perform a binary arithmetic operation using exact Fraction arithmetic,
    then round to binary128.  op(fa, fb) → Fraction or special string.
    """
    if _is_nan(a) or _is_nan(b):
        return _QNAN_BITS
    fa = to_fraction(a)
    fb = to_fraction(b)
    result = op(fa, fb)
    if result == 'nan':
        return _QNAN_BITS
    if result == '+inf':
        return _POS_INF
    if result == '-inf':
        return _NEG_INF
    return from_fraction(result)


def add(a: int, b: int) -> int:
    """Return correctly-rounded binary128 sum a + b."""
    if _is_nan(a) or _is_nan(b):
        return _QNAN_BITS
    fa = to_fraction(a)
    fb = to_fraction(b)
    # Special infinity cases.
    if isinstance(fa, str) or isinstance(fb, str):
        if fa == 'nan' or fb == 'nan':
            return _QNAN_BITS
        if fa == '+inf' and fb == '-inf':
            return _QNAN_BITS
        if fa == '-inf' and fb == '+inf':
            return _QNAN_BITS
        if fa == '+inf' or fb == '+inf':
            return _POS_INF
        if fa == '-inf' or fb == '-inf':
            return _NEG_INF
    exact = fa + fb
    # Determine sign of zero for (+0)+(-0)=+0 etc.
    if exact == 0:
        sa = _sign(a)
        sb = _sign(b)
        # IEEE: sum of two zeros with same sign → that sign; different → +0
        sz = sa if sa == sb else 0
        return _NEG_ZERO if sz else _POS_ZERO
    return _round_to_f128(exact)


def sub(a: int, b: int) -> int:
    """Return correctly-rounded binary128 difference a - b."""
    # Subtraction is addition with negated b sign.
    if _is_nan(a) or _is_nan(b):
        return _QNAN_BITS
    b_neg = b ^ (1 << 127)  # flip sign bit of b
    return add(a, b_neg)


def mul(a: int, b: int) -> int:
    """Return correctly-rounded binary128 product a * b."""
    if _is_nan(a) or _is_nan(b):
        return _QNAN_BITS
    fa = to_fraction(a)
    fb = to_fraction(b)
    sa = _sign(a)
    sb = _sign(b)
    result_sign = sa ^ sb
    # inf * 0 = NaN
    if (isinstance(fa, str) and _is_zero(b)) or (isinstance(fb, str) and _is_zero(a)):
        # But only if the non-zero is inf.
        fa_inf = fa in ('+inf', '-inf')
        fb_inf = fb in ('+inf', '-inf')
        if (fa_inf and _is_zero(b)) or (fb_inf and _is_zero(a)):
            return _QNAN_BITS
    if isinstance(fa, str) or isinstance(fb, str):
        if fa == 'nan' or fb == 'nan':
            return _QNAN_BITS
        # inf * finite-nonzero or inf * inf
        return _NEG_INF if result_sign else _POS_INF
    exact = fa * fb
    if exact == 0:
        return _NEG_ZERO if result_sign else _POS_ZERO
    return _round_to_f128(exact)


def div(a: int, b: int) -> int:
    """Return correctly-rounded binary128 quotient a / b."""
    if _is_nan(a) or _is_nan(b):
        return _QNAN_BITS
    fa = to_fraction(a)
    fb = to_fraction(b)
    sa = _sign(a)
    sb = _sign(b)
    result_sign = sa ^ sb
    fa_inf = fa in ('+inf', '-inf')
    fb_inf = fb in ('+inf', '-inf')
    fa_zero = (not isinstance(fa, str)) and fa == 0
    fb_zero = (not isinstance(fb, str)) and fb == 0
    # inf / inf = NaN
    if fa_inf and fb_inf:
        return _QNAN_BITS
    # 0 / 0 = NaN
    if fa_zero and fb_zero:
        return _QNAN_BITS
    # finite / inf = ±0
    if fb_inf:
        return _NEG_ZERO if result_sign else _POS_ZERO
    # inf / finite = ±inf
    if fa_inf:
        return _NEG_INF if result_sign else _POS_INF
    # finite / 0 = ±inf
    if fb_zero:
        return _NEG_INF if result_sign else _POS_INF
    exact = fa / fb
    if exact == 0:
        return _NEG_ZERO if result_sign else _POS_ZERO
    return _round_to_f128(exact)


# ---------------------------------------------------------------------------
# Comparisons  (NaN is unordered)
# ---------------------------------------------------------------------------

def _cmp_val(bits128: int):
    """Return a Fraction for finite values, or None for NaN, for comparisons."""
    if _is_nan(bits128):
        return None
    f = to_fraction(bits128)
    if isinstance(f, str):
        # ±inf: return a sentinel that compares correctly
        # Use very large Fractions so ordering works.
        return None if 'nan' in f else f
    return f


def _ordered_lt(a: int, b: int):
    """Return (fa, fb, ordered) where ordered=False if either is NaN."""
    if _is_nan(a) or _is_nan(b):
        return None, None, False
    fa = to_fraction(a)
    fb = to_fraction(b)
    # Convert inf strings to sentinel fractions for ordering.
    FA = _frac_or_inf(fa)
    FB = _frac_or_inf(fb)
    return FA, FB, True


_INF_SENTINEL = Fraction(10 ** 10000)
_NEG_INF_SENTINEL = Fraction(-10 ** 10000)


def _frac_or_inf(f):
    if f == '+inf':
        return _INF_SENTINEL
    if f == '-inf':
        return _NEG_INF_SENTINEL
    return f


def eq(a: int, b: int) -> bool:
    """IEEE equality: NaN operand → False; +0 == -0."""
    if _is_nan(a) or _is_nan(b):
        return False
    fa = to_fraction(a)
    fb = to_fraction(b)
    return _frac_or_inf(fa) == _frac_or_inf(fb)


def ne(a: int, b: int) -> bool:
    """IEEE not-equal: NaN operand → True."""
    if _is_nan(a) or _is_nan(b):
        return True
    return not eq(a, b)


def lt(a: int, b: int) -> bool:
    FA, FB, ok = _ordered_lt(a, b)
    return ok and FA < FB


def le(a: int, b: int) -> bool:
    FA, FB, ok = _ordered_lt(a, b)
    return ok and FA <= FB


def gt(a: int, b: int) -> bool:
    FA, FB, ok = _ordered_lt(a, b)
    return ok and FA > FB


def ge(a: int, b: int) -> bool:
    FA, FB, ok = _ordered_lt(a, b)
    return ok and FA >= FB


# ---------------------------------------------------------------------------
# Conversions: int ↔ binary128
# ---------------------------------------------------------------------------

def from_int(n: int) -> int:
    """Convert any Python integer to the correctly-rounded binary128 pattern."""
    return _round_to_f128(Fraction(n))


def to_int(a: int) -> int:
    """
    Convert binary128 to Python int, truncating toward zero
    (C (int64_t) cast semantics for finite in-range values).
    inf/nan → 0  (documented behavior).
    For finite values, simply truncates toward zero regardless of magnitude.
    """
    if _is_nan(a) or _is_inf(a):
        return 0
    f = to_fraction(a)
    # Fraction supports truncation toward zero via int() for positive values;
    # for negative, int() already truncates toward zero in Python.
    return int(f)  # Python int() truncates toward zero


# ---------------------------------------------------------------------------
# Conversions: binary64 ↔ binary128
# ---------------------------------------------------------------------------

def from_f64(bits64: int) -> int:
    """
    Convert a binary64 bit pattern (uint64) to an exact binary128 pattern.
    binary64 → binary128 is always exact (no rounding needed).
    """
    bits64 = bits64 & ((1 << 64) - 1)
    sign64  = (bits64 >> 63) & 1
    exp64   = (bits64 >> 52) & 0x7FF
    sig64   = bits64 & ((1 << 52) - 1)

    if exp64 == 0x7FF:
        # NaN or inf.
        if sig64 != 0:
            # NaN: quiet bit is bit 51 in f64; map to bit 111 in f128.
            # Preserve payload in low bits.
            new_sig = (1 << 111) | (sig64 << (111 - 51))
            return pack(sign64, 0x7FFF, new_sig)
        # Infinity.
        return _NEG_INF if sign64 else _POS_INF

    if exp64 == 0:
        # Subnormal or zero.
        if sig64 == 0:
            return _NEG_ZERO if sign64 else _POS_ZERO
        # Subnormal f64: value = sig64 * 2^(-1074)
        # In f128 this is a normal number.
        # value = sig64 * 2^(-1074)
        # Find the highest set bit in sig64 to normalize.
        lead = sig64.bit_length() - 1  # position of leading 1
        # value = sig64 * 2^(-1074) = (sig64 / 2^lead) * 2^(lead - 1074)
        #       = (1 + (sig64 - 2^lead) / 2^lead) * 2^(lead-1074)
        new_exp = (lead - 1074) + _BIAS  # biased
        new_sig = (sig64 - (1 << lead)) << (112 - lead)
        return pack(sign64, new_exp, new_sig)
    else:
        # Normal f64: value = (1 + sig64/2^52) * 2^(exp64 - 1023)
        # In f128: exp128 = (exp64 - 1023) + 16383
        new_exp = (exp64 - 1023) + _BIAS
        # sig128 is sig64 left-shifted to fill 112 bits.
        new_sig = sig64 << (112 - 52)  # = sig64 << 60
        return pack(sign64, new_exp, new_sig)


def to_f64(a: int) -> int:
    """
    Convert binary128 to the correctly-rounded binary64 bit pattern.
    Returns a uint64 (as a Python int).
    """
    if _is_nan(a):
        # Return canonical quiet NaN for f64.
        return 0x7FF8000000000000
    sign, exp128, sig128 = unpack(a)
    if exp128 == 0x7FFF:
        # Infinity.
        return (sign << 63) | (0x7FF << 52)

    f = to_fraction(a)
    if f == 0:
        return (sign << 63)

    # Round the Fraction to binary64 using the same _round_to_f128 logic
    # but targeting 52 trailing significand bits and bias 1023.
    abs_val = -f if f < 0 else f
    # Find binary exponent.
    n = abs_val.numerator
    d = abs_val.denominator
    e = n.bit_length() - d.bit_length()
    if Fraction(1 << e if e >= 0 else 1, 1 if e >= 0 else (1 << (-e))) > abs_val:
        e -= 1

    F64_BIAS = 1023
    F64_SIG_BITS = 52
    EMIN_F64 = 1 - F64_BIAS  # = -1022

    biased_e64 = e + F64_BIAS

    if biased_e64 <= 0:
        # Subnormal or underflow.
        if e < EMIN_F64 - F64_SIG_BITS - 1:
            # Too small, round to zero or min subnormal.
            half_min = Fraction(1, 1 << (F64_BIAS - 1 + F64_SIG_BITS + 1))
            if abs_val >= half_min:
                return (sign << 63) | 1
            return sign << 63
        # Subnormal f64.
        shift64 = F64_BIAS - 1 + F64_SIG_BITS  # = 1074
        scaled = abs_val * (1 << shift64)
        t_int = int(scaled)
        rem = scaled - t_int
        t_int, _ = _rne(t_int, rem, t_int & 1)
        if t_int >= (1 << F64_SIG_BITS):
            # Carried to normal.
            return (sign << 63) | (1 << F64_SIG_BITS)
        return (sign << 63) | t_int
    else:
        # Normal.
        if e >= 0:
            mantissa = Fraction(abs_val, 1 << e)
        else:
            mantissa = abs_val * (1 << (-e))
        t_frac = (mantissa - 1) * (1 << F64_SIG_BITS)
        t_int = int(t_frac)
        rem = t_frac - t_int
        t_int, _ = _rne(t_int, rem, t_int & 1)
        if t_int >= (1 << F64_SIG_BITS):
            t_int = 0
            biased_e64 += 1
        if biased_e64 > 0x7FE:
            # Overflow to infinity.
            return (sign << 63) | (0x7FF << 52)
        return (sign << 63) | (biased_e64 << F64_SIG_BITS) | t_int


# ---------------------------------------------------------------------------
# Decimal string parsing
# ---------------------------------------------------------------------------

def parse(s: str) -> int:
    """
    Parse a decimal string to a correctly-rounded binary128 pattern.
    Supports: optional sign, integer, fraction, 'e'/'E' exponent.
    Examples: "1.25", "-3.14159e10", "inf", "-inf", "nan", "0.0001".
    """
    s = s.strip()
    sl = s.lower()
    if sl in ('nan', '+nan', '-nan'):
        return _QNAN_BITS
    if sl in ('inf', '+inf', 'infinity', '+infinity'):
        return _POS_INF
    if sl in ('-inf', '-infinity'):
        return _NEG_INF

    negative = False
    if s.startswith('-'):
        negative = True
        s = s[1:]
    elif s.startswith('+'):
        s = s[1:]

    # Split at 'e'/'E'.
    e_idx = -1
    for i, c in enumerate(s):
        if c in ('e', 'E'):
            e_idx = i
            break

    if e_idx >= 0:
        mantissa_str = s[:e_idx]
        exp_str = s[e_idx+1:]
        exp10 = int(exp_str)
    else:
        mantissa_str = s
        exp10 = 0

    # Parse mantissa as exact rational.
    if '.' in mantissa_str:
        dot = mantissa_str.index('.')
        int_part = mantissa_str[:dot] or '0'
        frac_part = mantissa_str[dot+1:] or '0'
        numer = int(int_part) * (10 ** len(frac_part)) + int(frac_part)
        denom = 10 ** len(frac_part)
        exact = Fraction(numer, denom)
    else:
        exact = Fraction(int(mantissa_str or '0'))

    # Apply exponent.
    if exp10 >= 0:
        exact = exact * (10 ** exp10)
    else:
        exact = Fraction(exact, 10 ** (-exp10))

    if negative:
        exact = -exact

    if exact == 0:
        return _NEG_ZERO if negative else _POS_ZERO
    return _round_to_f128(exact)


# ---------------------------------------------------------------------------
# Decimal formatting  (matching firescript runtime conventions exactly)
# ---------------------------------------------------------------------------

def _f128_to_decimal_digits(bits128: int) -> tuple:
    """
    Convert a finite, nonzero binary128 value to its exact decimal expansion.
    Returns (negative, int_digits, frac_digits) where each is a list of
    integer digits (0-9), int_digits being the integer part and frac_digits
    being the fractional part.  All exact (no rounding here).
    """
    sign, exp, sig = unpack(bits128)
    negative = bool(sign)
    if exp == 0:
        # Subnormal: value = sig * 2^(1 - bias - 112) = sig * 2^(-16494)
        mant_int = sig
        bexp = 1 - _BIAS - 112  # binary exponent of mant_int (i.e. value = mant_int * 2^bexp)
    else:
        # Normal: value = (2^112 + sig) * 2^(exp - bias - 112)
        mant_int = (1 << 112) | sig
        bexp = exp - _BIAS - 112

    # Convert mant_int * 2^bexp to decimal digit arrays.
    if bexp >= 0:
        int_val = mant_int << bexp
        int_digits = list(map(int, str(int_val))) if int_val else []
        frac_digits = []
    else:
        # We need to compute mant_int / 2^(-bexp) = integer + fraction parts.
        denom = 1 << (-bexp)
        int_val = mant_int // denom
        rem = mant_int % denom
        int_digits = list(map(int, str(int_val))) if int_val else []
        # Compute fractional digits until remainder is zero.
        frac_digits = []
        while rem:
            rem *= 10
            frac_digits.append(rem // denom)
            rem = rem % denom

    return negative, int_digits, frac_digits


def _round_digits(int_digits: list, frac_digits: list, keep_frac: int) -> tuple:
    """
    Round the exact decimal digit arrays to `keep_frac` fractional digits
    using round-half-to-even.  Returns (new_int_digits, new_frac_digits).
    """
    frac = list(frac_digits)
    # Pad frac with zeros if shorter than keep_frac.
    while len(frac) < keep_frac:
        frac.append(0)
    if len(frac) <= keep_frac:
        return list(int_digits), frac[:keep_frac]

    # Check the digit at position keep_frac (0-indexed).
    next_d = frac[keep_frac]
    rest_nonzero = any(d != 0 for d in frac[keep_frac+1:])

    round_up = False
    if next_d > 5:
        round_up = True
    elif next_d == 5:
        if rest_nonzero:
            round_up = True
        else:
            # Tie: round to even — look at digit at position keep_frac - 1.
            if keep_frac > 0:
                prev = frac[keep_frac - 1]
            elif int_digits:
                prev = int_digits[-1]
            else:
                prev = 0
            if prev % 2 == 1:
                round_up = True

    frac = frac[:keep_frac]
    ints = list(int_digits)

    if round_up:
        # Propagate carry through frac then int.
        carry = 1
        for i in range(len(frac) - 1, -1, -1):
            v = frac[i] + carry
            frac[i] = v % 10
            carry = v // 10
            if carry == 0:
                break
        if carry:
            for i in range(len(ints) - 1, -1, -1):
                v = ints[i] + carry
                ints[i] = v % 10
                carry = v // 10
                if carry == 0:
                    break
            if carry:
                ints.insert(0, carry)

    return ints, frac


def format_f(a: int) -> str:
    """
    Format binary128 in printf '%f' style:
    fixed notation, 6 fractional digits, round-half-to-even.
    Specials: 'nan', '-inf', 'inf'.
    """
    sign, exp, sig = unpack(a)
    if exp == 0x7FFF:
        if sig != 0:
            return 'nan'
        return '-inf' if sign else 'inf'

    negative, int_digits, frac_digits = _f128_to_decimal_digits(a)
    int_d, frac_d = _round_digits(int_digits, frac_digits, 6)

    prefix = '-' if negative else ''
    int_str = ''.join(map(str, int_d)) if int_d else '0'
    frac_str = ''.join(map(str, frac_d))
    # Pad frac to exactly 6 digits.
    frac_str = frac_str.ljust(6, '0')[:6]
    return f"{prefix}{int_str}.{frac_str}"


def _collect_sig_digits(int_digits: list, frac_digits: list) -> tuple:
    """
    Collect significant digits and the decimal exponent of the leading digit.
    Returns (all_digits_list, exp10, leading_frac_zeros).

    all_digits_list: flat list of all significant digits (including leading zeros
    in the fraction skipped — those are accounted for in exp10).
    exp10: decimal exponent of the first significant digit.
    """
    if int_digits:
        exp10 = len(int_digits) - 1
        all_sig = int_digits + list(frac_digits)
        return all_sig, exp10
    else:
        # Find first nonzero in frac.
        leading_zeros = 0
        for d in frac_digits:
            if d != 0:
                break
            leading_zeros += 1
        else:
            # All zeros (shouldn't happen for nonzero value).
            return [0], 0
        exp10 = -(leading_zeros + 1)
        all_sig = list(frac_digits[leading_zeros:])
        return all_sig, exp10


def _round_sig_digits(all_sig: list, exp10: int, keep: int) -> tuple:
    """
    Round all_sig to `keep` significant digits using round-half-to-even.
    Returns (rounded_digits, new_exp10).
    """
    digits = list(all_sig)
    # Pad to at least keep+1 for lookahead.
    while len(digits) <= keep:
        digits.append(0)

    next_d = digits[keep]
    rest_nonzero = any(d != 0 for d in digits[keep+1:])

    round_up = False
    if next_d > 5:
        round_up = True
    elif next_d == 5:
        if rest_nonzero:
            round_up = True
        else:
            prev = digits[keep - 1] if keep > 0 else 0
            if prev % 2 == 1:
                round_up = True

    out = digits[:keep]
    if round_up:
        carry = 1
        for i in range(len(out) - 1, -1, -1):
            v = out[i] + carry
            out[i] = v % 10
            carry = v // 10
            if carry == 0:
                break
        if carry:
            out.insert(0, carry)
            # Length increased by 1: the leading digit is 1 and exp10 grows by 1.
            exp10 += 1
            out = out[:keep]  # drop last digit (it's 0 due to carry)

    # Strip to exactly `keep` digits (pad with zeros if needed).
    while len(out) < keep:
        out.append(0)

    return out, exp10


def format_g(a: int) -> str:
    """
    Format binary128 in printf '%g' style:
    6 significant digits, fixed or scientific notation.
    Scientific when exp10 < -4 or exp10 >= 6.
    Trailing zeros stripped.
    Specials: 'nan', '-inf', 'inf'.
    Zero → '0' or '-0'.
    Exponent format: e+NN or e-NN (always at least 2 digits).
    """
    sign, exp_field, sig = unpack(a)
    if exp_field == 0x7FFF:
        if sig != 0:
            return 'nan'
        return '-inf' if sign else 'inf'

    if exp_field == 0 and sig == 0:
        return '-0' if sign else '0'

    negative, int_digits, frac_digits = _f128_to_decimal_digits(a)
    all_sig, exp10 = _collect_sig_digits(int_digits, frac_digits)
    digits, exp10 = _round_sig_digits(all_sig, exp10, 6)

    # Strip trailing zeros.
    sig_count = len(digits)
    while sig_count > 1 and digits[sig_count - 1] == 0:
        sig_count -= 1
    digits = digits[:sig_count]

    prefix = '-' if negative else ''

    if exp10 < -4 or exp10 >= 6:
        # Scientific notation: d[.ddd]e[+-]NN
        lead = str(digits[0])
        if len(digits) > 1:
            rest = ''.join(map(str, digits[1:]))
            mantissa_str = f"{lead}.{rest}"
        else:
            mantissa_str = lead
        # Exponent: always sign + at least 2 digits.
        if exp10 < 0:
            exp_str = f"e-{abs(exp10):02d}"
        else:
            exp_str = f"e+{exp10:02d}"
        return f"{prefix}{mantissa_str}{exp_str}"
    elif exp10 >= 0:
        # Fixed: some integer digits, possibly fraction.
        int_count = exp10 + 1  # number of integer digits
        int_part = digits[:int_count]
        frac_part = digits[int_count:]
        # Pad int_part with zeros if digits ran out.
        while len(int_part) < int_count:
            int_part.append(0)
        int_str = ''.join(map(str, int_part))
        if frac_part:
            frac_str = ''.join(map(str, frac_part))
            return f"{prefix}{int_str}.{frac_str}"
        return f"{prefix}{int_str}"
    else:
        # Fixed: 0.000...ddd
        leading_zeros = -exp10 - 1
        frac_str = '0' * leading_zeros + ''.join(map(str, digits))
        return f"{prefix}0.{frac_str}"


# ---------------------------------------------------------------------------
# Test vector generation
# ---------------------------------------------------------------------------

def vectors() -> list:
    """
    Generate a comprehensive list of test vectors.
    Each entry is a dict with keys: 'op', 'inputs', 'expected', 'note'.
    'inputs' and 'expected' are 128-bit integer patterns (or strings for
    format_f/format_g outputs, or ints for to_int/to_f64 outputs).
    """
    vecs = []

    def v(op, inputs, expected, note=''):
        vecs.append({'op': op, 'inputs': inputs, 'expected': expected, 'note': note})

    # --- Bit-pattern constants (hand-computed) ---
    ONE    = pack(0, _BIAS, 0)               # 1.0
    NEG_ONE = pack(1, _BIAS, 0)              # -1.0
    TWO    = pack(0, _BIAS + 1, 0)           # 2.0
    HALF   = pack(0, _BIAS - 1, 0)           # 0.5
    ONE25  = pack(0, _BIAS, 1 << 110)        # 1.25  (sig=0.25*2^112=2^110)
    THREE  = add(TWO, ONE)                   # 3.0
    FOUR   = pack(0, _BIAS + 2, 0)           # 4.0
    ZERO   = _POS_ZERO
    NZERO  = _NEG_ZERO
    INF_P  = _POS_INF
    INF_N  = _NEG_INF
    NAN_C  = _QNAN_BITS
    MIN_SUB = _MIN_SUBNORMAL               # smallest positive subnormal

    # --- Unpack self-checks (verified constants) ---
    v('unpack', [ONE],    (0, _BIAS, 0),   '1.0 unpack')
    v('unpack', [TWO],    (0, _BIAS+1, 0), '2.0 unpack')
    v('unpack', [HALF],   (0, _BIAS-1, 0), '0.5 unpack')
    v('unpack', [ONE25],  (0, _BIAS, 1 << 110), '1.25 unpack')
    v('unpack', [INF_P],  (0, 0x7FFF, 0),  '+inf unpack')
    v('unpack', [INF_N],  (1, 0x7FFF, 0),  '-inf unpack')
    v('unpack', [MIN_SUB],(0, 0, 1),       'min_subnormal unpack')

    # --- to_halves / from_halves round-trips ---
    for x, note in [(ONE, '1.0'), (INF_P, '+inf'), (NAN_C, 'nan'), (MIN_SUB, 'min_sub')]:
        lo, hi = to_halves(x)
        v('from_halves', [(lo, hi)], x, f'halves round-trip {note}')

    # --- ADD ---
    v('add', [ONE, ONE],   TWO,   '1+1=2')
    v('add', [ONE, HALF],  pack(0, _BIAS, 1<<111), '1+0.5=1.5')
    v('add', [INF_P, ONE], INF_P, 'inf+1=inf')
    v('add', [INF_P, INF_N], NAN_C, 'inf+(-inf)=nan')
    v('add', [NAN_C, ONE], NAN_C, 'nan+1=nan')
    v('add', [ZERO, NZERO], ZERO, '+0+(-0)=+0')
    v('add', [NZERO, NZERO], NZERO, '-0+(-0)=-0')
    v('add', [NEG_ONE, ONE], ZERO, '-1+1=+0')
    v('add', [ONE, NEG_ONE], ZERO, '1+(-1)=+0')
    v('add', [_MAX_FINITE, _MAX_FINITE], INF_P, 'overflow to +inf')
    v('add', [MIN_SUB, MIN_SUB], pack(0, 0, 2), 'min_sub+min_sub')

    # --- SUB ---
    v('sub', [TWO, ONE],   ONE,    '2-1=1')
    v('sub', [ONE, TWO],   NEG_ONE,'1-2=-1')
    v('sub', [ONE, ONE],   ZERO,   '1-1=+0')
    v('sub', [INF_P, INF_P], NAN_C,'inf-inf=nan')
    v('sub', [NAN_C, ONE], NAN_C,  'nan-1=nan')
    v('sub', [NZERO, ZERO], NZERO, '-0-0=-0')

    # --- MUL ---
    v('mul', [TWO, THREE],  add(add(TWO, TWO), TWO), '2*3=6')
    v('mul', [NEG_ONE, NEG_ONE], ONE, '(-1)*(-1)=1')
    v('mul', [INF_P, ZERO],  NAN_C,  'inf*0=nan')
    v('mul', [INF_P, NEG_ONE], INF_N, 'inf*(-1)=-inf')
    v('mul', [NAN_C, TWO], NAN_C,   'nan*2=nan')
    v('mul', [HALF, HALF], pack(0, _BIAS-2, 0), '0.5*0.5=0.25')
    # Overflow: max_finite * 2 = inf
    v('mul', [_MAX_FINITE, TWO], INF_P, 'max_finite*2=inf')
    # Tiny * tiny → subnormal
    v('mul', [MIN_SUB, ONE], MIN_SUB, 'min_sub*1=min_sub')

    # --- DIV ---
    v('div', [ONE, TWO],    HALF,   '1/2=0.5')
    v('div', [TWO, ONE],    TWO,    '2/1=2')
    v('div', [ZERO, ONE],   ZERO,   '0/1=+0')
    v('div', [ZERO, ZERO],  NAN_C,  '0/0=nan')
    v('div', [ONE, ZERO],   INF_P,  '1/0=+inf')
    v('div', [NEG_ONE, ZERO], INF_N,'-1/0=-inf')
    v('div', [INF_P, INF_P], NAN_C, 'inf/inf=nan')
    v('div', [INF_P, TWO],  INF_P,  'inf/2=inf')
    v('div', [ONE, INF_P],  ZERO,   '1/inf=+0')
    v('div', [NAN_C, ONE],  NAN_C,  'nan/1=nan')
    # 1/3 — must be correctly rounded binary128
    ONE_THIRD = div(ONE, THREE)
    v('div', [ONE, THREE], ONE_THIRD, '1/3 correctly rounded')

    # --- Comparisons ---
    v('eq',  [ONE, ONE],    True,  '1==1')
    v('eq',  [ONE, TWO],    False, '1==2 false')
    v('eq',  [ZERO, NZERO], True,  '+0==-0 true')
    v('eq',  [NAN_C, NAN_C], False,'nan==nan false')
    v('ne',  [NAN_C, ONE],  True,  'nan!=1 true')
    v('ne',  [ONE, ONE],    False, '1!=1 false')
    v('lt',  [ONE, TWO],    True,  '1<2')
    v('lt',  [TWO, ONE],    False, '2<1 false')
    v('lt',  [NAN_C, ONE],  False, 'nan<1 false')
    v('le',  [ONE, ONE],    True,  '1<=1')
    v('le',  [TWO, ONE],    False, '2<=1 false')
    v('gt',  [TWO, ONE],    True,  '2>1')
    v('gt',  [NAN_C, ONE],  False, 'nan>1 false')
    v('ge',  [ONE, ONE],    True,  '1>=1')
    v('ge',  [ONE, TWO],    False, '1>=2 false')
    v('lt',  [INF_N, INF_P], True, '-inf<+inf')
    v('gt',  [INF_P, _MAX_FINITE], True, '+inf>max_finite')

    # --- from_int ---
    v('from_int', [0],    ZERO,    'from_int(0)')
    v('from_int', [1],    ONE,     'from_int(1)')
    v('from_int', [2],    TWO,     'from_int(2)')
    v('from_int', [-1],   NEG_ONE, 'from_int(-1)')
    v('from_int', [2**113], from_int(2**113), 'from_int(2^113)')
    # Large odd integer that requires rounding
    big_odd = (2**113) + 1
    v('from_int', [big_odd], from_int(big_odd), 'from_int(2^113+1) rounds to even')
    v('from_int', [10**40],  from_int(10**40),  'from_int(10^40)')
    v('from_int', [-10**40], from_int(-10**40), 'from_int(-10^40)')

    # --- to_int ---
    v('to_int', [ONE],    1,   'to_int(1.0)=1')
    v('to_int', [NEG_ONE], -1, 'to_int(-1.0)=-1')
    v('to_int', [ZERO],   0,   'to_int(0)=0')
    v('to_int', [INF_P],  0,   'to_int(+inf)=0')
    v('to_int', [NAN_C],  0,   'to_int(nan)=0')
    # 1.75 truncates to 1
    ONE75 = add(ONE, add(HALF, pack(0, _BIAS-2, 0)))
    v('to_int', [ONE75],  1,   'to_int(1.75)=1')
    NEG175 = pack(1, _BIAS, 3 << 110)  # -1.75
    v('to_int', [NEG175], -1,  'to_int(-1.75)=-1')

    # --- from_f64 ---
    # 1.0 in f64: exp=1023, sig=0 → bits = 0x3FF0000000000000
    F64_ONE = 0x3FF0000000000000
    F64_TWO = 0x4000000000000000
    F64_HALF = 0x3FE0000000000000
    F64_NAN  = 0x7FF8000000000000
    F64_INF  = 0x7FF0000000000000
    F64_NINF = 0xFFF0000000000000
    F64_MIN_SUB = 0x0000000000000001  # smallest f64 subnormal

    v('from_f64', [F64_ONE],  ONE,    'from_f64(1.0)')
    v('from_f64', [F64_TWO],  TWO,    'from_f64(2.0)')
    v('from_f64', [F64_HALF], HALF,   'from_f64(0.5)')
    v('from_f64', [F64_INF],  INF_P,  'from_f64(+inf)')
    v('from_f64', [F64_NINF], INF_N,  'from_f64(-inf)')
    v('from_f64', [0],        ZERO,   'from_f64(+0)')
    v('from_f64', [F64_MIN_SUB], from_f64(F64_MIN_SUB), 'from_f64(min_f64_sub)')

    # --- to_f64 ---
    v('to_f64', [ONE],    F64_ONE,  'to_f64(1.0)')
    v('to_f64', [TWO],    F64_TWO,  'to_f64(2.0)')
    v('to_f64', [HALF],   F64_HALF, 'to_f64(0.5)')
    v('to_f64', [INF_P],  F64_INF,  'to_f64(+inf)')
    v('to_f64', [INF_N],  F64_NINF, 'to_f64(-inf)')
    v('to_f64', [NAN_C],  F64_NAN,  'to_f64(nan)')
    v('to_f64', [ZERO],   0,        'to_f64(+0)')

    # --- parse ---
    v('parse', ['1.0'],   ONE,    "parse('1.0')")
    v('parse', ['2.0'],   TWO,    "parse('2.0')")
    v('parse', ['0.5'],   HALF,   "parse('0.5')")
    v('parse', ['1.25'],  ONE25,  "parse('1.25')")
    v('parse', ['-1.0'],  NEG_ONE,"parse('-1.0')")
    v('parse', ['0.0'],   ZERO,   "parse('0.0')")
    v('parse', ['inf'],   INF_P,  "parse('inf')")
    v('parse', ['-inf'],  INF_N,  "parse('-inf')")
    v('parse', ['nan'],   NAN_C,  "parse('nan')")
    v('parse', ['1e10'],  from_int(10**10),  "parse('1e10')")
    v('parse', ['1.5e-1'], parse('1.5e-1'),  "parse('1.5e-1')")
    v('parse', ['3.14159265358979323846264338327950288'],
               parse('3.14159265358979323846264338327950288'), 'parse(pi 34 digits)')
    # Exact decimal tie to even
    # 1.5 rounds to even (sig=0.5 → bit 111): already exact
    v('parse', ['1.5'],   pack(0, _BIAS, 1<<111), "parse('1.5')")

    # --- format_f ---
    v('format_f', [ONE],    '1.000000',   'format_f(1.0)')
    v('format_f', [TWO],    '2.000000',   'format_f(2.0)')
    v('format_f', [HALF],   '0.500000',   'format_f(0.5)')
    v('format_f', [ONE25],  '1.250000',   'format_f(1.25)')
    v('format_f', [NEG_ONE],'-1.000000',  'format_f(-1.0)')
    v('format_f', [ZERO],   '0.000000',   'format_f(0)')
    v('format_f', [NZERO],  '-0.000000',  'format_f(-0)')
    v('format_f', [INF_P],  'inf',        'format_f(+inf)')
    v('format_f', [INF_N],  '-inf',       'format_f(-inf)')
    v('format_f', [NAN_C],  'nan',        'format_f(nan)')
    v('format_f', [parse('123456.789')], format_f(parse('123456.789')),
      'format_f(123456.789)')
    v('format_f', [parse('0.0000001')], '0.000000', 'format_f(1e-7) rounds to 0.000000')
    v('format_f', [parse('1.9999995')], format_f(parse('1.9999995')),
      'format_f(1.9999995) tie-to-even')

    # --- format_g ---
    v('format_g', [ONE],    '1',      'format_g(1.0)')
    v('format_g', [TWO],    '2',      'format_g(2.0)')
    v('format_g', [HALF],   '0.5',    'format_g(0.5)')
    v('format_g', [ONE25],  '1.25',   'format_g(1.25)')
    v('format_g', [NEG_ONE],'-1',     'format_g(-1.0)')
    v('format_g', [ZERO],   '0',      'format_g(0)')
    v('format_g', [NZERO],  '-0',     'format_g(-0)')
    v('format_g', [INF_P],  'inf',    'format_g(+inf)')
    v('format_g', [INF_N],  '-inf',   'format_g(-inf)')
    v('format_g', [NAN_C],  'nan',    'format_g(nan)')
    v('format_g', [parse('123456.0')], '123456', 'format_g(123456)')
    v('format_g', [parse('1234567.0')], '1.23457e+06', 'format_g(1234567) scientific')
    v('format_g', [parse('0.0001')], '0.0001', 'format_g(0.0001) fixed boundary')
    v('format_g', [parse('0.00001')], '1e-05', 'format_g(1e-5) scientific')
    v('format_g', [parse('3.14159265')], '3.14159', 'format_g(pi 6 sig)')
    v('format_g', [parse('100000.0')], '100000', 'format_g(1e5) fixed')
    v('format_g', [parse('1000000.0')], '1e+06', 'format_g(1e6) scientific')
    v('format_g', [parse('-0.00314159')], '-0.00314159', 'format_g(-3.14159e-3)')
    v('format_g', [MIN_SUB], format_g(MIN_SUB), 'format_g(min_subnormal)')

    # --- Subnormal arithmetic ---
    half_sub = pack(0, 0, 1 << 111)  # largest subnormal / something
    v('add', [MIN_SUB, ZERO], MIN_SUB, 'min_sub + 0 = min_sub')
    v('mul', [MIN_SUB, TWO],  pack(0, 0, 2), 'min_sub * 2')
    v('div', [pack(0, 0, 2), TWO], MIN_SUB, 'subnormal/2 = min_sub')

    # --- Mixed-sign large/small ---
    BIG   = from_int(10**100)
    SMALL = div(ONE, from_int(10**100))
    v('add', [BIG, SMALL], BIG, 'big + tiny = big (tiny lost)')
    v('mul', [BIG, SMALL], mul(BIG, SMALL), 'big * tiny = ~1')

    # --- Rounding ties-to-even ---
    # 1.5 → rounded to 2 (even) when rounding to integer-ish precision via add
    # Exact tie case: value midway between two f128 values
    # e.g. parse a decimal that is exactly half-way between adjacent f128 vals
    v('parse', ['0.1'], parse('0.1'), 'parse(0.1) correctly rounded')
    v('parse', ['0.2'], parse('0.2'), 'parse(0.2)')
    v('parse', ['0.3'], parse('0.3'), 'parse(0.3)')
    # sum of 0.1+0.2 should equal parse('0.3') only approximately in f128;
    # they won't be bitwise equal in general (just like in any binary float).

    # --- Round-trip: parse → format_f ---
    for s in ['1.000000', '0.500000', '1.250000', '-1.000000', '0.000000']:
        p = parse(s)
        ff = format_f(p)
        v('parse_format_f', [s], ff, f'round-trip {s}')

    # --- from_f64 / to_f64 round-trips for representable values ---
    for bits64, name in [
        (F64_ONE, '1.0'), (F64_TWO, '2.0'), (F64_HALF, '0.5'),
        (0x4008000000000000, '3.0'),   # 3.0 in f64
        (0xC008000000000000, '-3.0'),  # -3.0 in f64
    ]:
        f128 = from_f64(bits64)
        rt = to_f64(f128)
        v('from_f64_to_f64', [(bits64,)], bits64, f'round-trip f64 {name}')

    return vecs

