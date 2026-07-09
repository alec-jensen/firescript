"""float128_oracle hand-verified constants and unit checks, migrated from
tests/float128_oracle.py's __main__ self-tests (spec sec.4.4 migration
table)."""
from __future__ import annotations

from fractions import Fraction

from harness import pyunit as t
from support import float128_oracle as o

ONE = o.pack(0, 16383, 0)
NEG_ONE = o.pack(1, 16383, 0)
TWO = o.pack(0, 16384, 0)
HALF = o.pack(0, 16382, 0)
ONE25 = o.pack(0, 16383, 1 << 110)
ZERO = 0
NZERO = 1 << 127
INF_P = 0x7FFF << 112
INF_N = (1 << 127) | (0x7FFF << 112)
NAN_C = (0x7FFF << 112) | (1 << 111)
MIN_SUB = 1

F64_ONE = 0x3FF0000000000000
F64_TWO = 0x4000000000000000
F64_HALF = 0x3FE0000000000000
F64_INF = 0x7FF0000000000000
F64_NINF = 0xFFF0000000000000
F64_NAN = 0x7FF8000000000000


def test_unpack_hand_verified_constants():
    for name, bits, s_exp, e_exp, t_exp in [
        ("1.0", ONE, 0, 16383, 0),
        ("2.0", TWO, 0, 16384, 0),
        ("0.5", HALF, 0, 16382, 0),
        ("1.25", ONE25, 0, 16383, 1 << 110),
        ("+inf", INF_P, 0, 0x7FFF, 0),
        ("-inf", INF_N, 1, 0x7FFF, 0),
        ("min_sub", MIN_SUB, 0, 0, 1),
        ("+0", ZERO, 0, 0, 0),
        ("-0", NZERO, 1, 0, 0),
        ("qnan", NAN_C, 0, 0x7FFF, 1 << 111),
    ]:
        with t.subtest(name):
            s, e, sig = o.unpack(bits)
            t.require_eq(s, s_exp, "sign")
            t.require_eq(e, e_exp, "exp")
            t.require_eq(sig, t_exp, "sig")


def test_min_subnormal_value():
    t.require_eq(o.to_fraction(MIN_SUB), Fraction(1, 1 << 16494))


def test_to_halves():
    lo, hi = o.to_halves(ONE)
    t.require_eq((lo, hi), (0, 0x3FFF000000000000))

    lo25, hi25 = o.to_halves(ONE25)
    t.require_eq((lo25, hi25), (0, 0x3FFF000000000000 | (1 << 46)))

    lo_inf, hi_inf = o.to_halves(INF_P)
    t.require_eq((lo_inf, hi_inf), (0, 0x7FFF000000000000))


def test_arithmetic_spot_checks():
    t.require_eq(o.add(ONE, ONE), TWO)
    t.require_eq(o.sub(TWO, ONE), ONE)
    t.require_eq(o.div(ONE, TWO), HALF)
    t.require_eq(o.mul(HALF, TWO), ONE)
    t.require(o._is_nan(o.add(INF_P, INF_N)))
    t.require_eq(o.div(ONE, ZERO), INF_P)
    t.require_eq(o.div(o.pack(1, 16383, 0), ZERO), INF_N)
    t.require(o._is_nan(o.div(ZERO, ZERO)))
    t.require(o._is_nan(o.mul(INF_P, ZERO)))
    t.require(o._is_nan(o.add(NAN_C, ONE)))

    two_thirds = o.div(TWO, o.add(ONE, TWO))
    one_third = o.div(ONE, o.add(ONE, TWO))
    frac_sum = o.to_fraction(o.add(one_third, two_thirds))
    t.require(abs(frac_sum - 1) <= Fraction(1, 1 << 112))

    t.require_eq(o.div(o._MAX_FINITE, HALF), INF_P)
    t.require_eq(o.mul(TWO, MIN_SUB), o.pack(0, 0, 2))
    t.require(o.mul(MIN_SUB, HALF) in (ZERO, o.pack(0, 0, 0)))


def test_comparisons():
    t.require(o.eq(ONE, ONE))
    t.require(o.eq(ZERO, NZERO))
    t.require(not o.eq(NAN_C, NAN_C))
    t.require(o.ne(NAN_C, ONE))
    t.require(o.lt(ONE, TWO))
    t.require(not o.lt(TWO, ONE))
    t.require(not o.lt(NAN_C, ONE))
    t.require(o.ge(ONE, ONE))
    t.require(o.gt(INF_P, o._MAX_FINITE))
    t.require(o.lt(INF_N, NEG_ONE))


def test_from_int_to_int():
    t.require_eq(o.from_int(0), ZERO)
    t.require_eq(o.from_int(1), ONE)
    t.require_eq(o.from_int(2), TWO)
    t.require_eq(o.from_int(-1), NEG_ONE)
    t.require_eq(o.to_int(ONE), 1)
    t.require_eq(o.to_int(NEG_ONE), -1)
    t.require_eq(o.to_int(INF_P), 0)
    t.require_eq(o.to_int(NAN_C), 0)
    t.require_eq(o.to_int(o.parse("1.75")), 1)
    t.require_eq(o.to_int(o.parse("-1.75")), -1)
    for n in [0, 1, -1, 2**52, 2**63, -(2**63), 10**30]:
        with t.subtest(f"round-trip {n}"):
            t.require_eq(o.to_int(o.from_int(n)), n)


def test_from_f64_to_f64():
    t.require_eq(o.from_f64(F64_ONE), ONE)
    t.require_eq(o.from_f64(F64_TWO), TWO)
    t.require_eq(o.from_f64(F64_HALF), HALF)
    t.require_eq(o.from_f64(F64_INF), INF_P)
    t.require_eq(o.from_f64(F64_NINF), INF_N)
    t.require_eq(o.to_f64(ONE), F64_ONE)
    t.require_eq(o.to_f64(TWO), F64_TWO)
    t.require_eq(o.to_f64(HALF), F64_HALF)
    t.require_eq(o.to_f64(INF_P), F64_INF)
    t.require_eq(o.to_f64(INF_N), F64_NINF)
    t.require_eq((o.to_f64(NAN_C) >> 52) & 0x7FF, 0x7FF)
    for bits64, name in [
        (F64_ONE, "1.0"), (F64_TWO, "2.0"), (F64_HALF, "0.5"),
        (0x4008000000000000, "3.0"), (0x400921FB54442D18, "pi_f64"),
    ]:
        with t.subtest(f"f64 round-trip {name}"):
            t.require_eq(o.to_f64(o.from_f64(bits64)), bits64)


def test_parse():
    t.require_eq(o.parse("1.0"), ONE)
    t.require_eq(o.parse("2.0"), TWO)
    t.require_eq(o.parse("0.5"), HALF)
    t.require_eq(o.parse("1.25"), ONE25)
    t.require_eq(o.parse("-1.0"), NEG_ONE)
    t.require_eq(o.parse("inf"), INF_P)
    t.require_eq(o.parse("-inf"), INF_N)
    t.require(o._is_nan(o.parse("nan")))
    t.require_eq(o.parse("0.0"), ZERO)
    t.require_eq(o.parse("1e0"), ONE)
    t.require_eq(o.parse("2e0"), TWO)
    t.require_eq(o.parse("1.5"), o.pack(0, 16383, 1 << 111))


def test_format_f():
    t.require_eq(o.format_f(ONE), "1.000000")
    t.require_eq(o.format_f(TWO), "2.000000")
    t.require_eq(o.format_f(HALF), "0.500000")
    t.require_eq(o.format_f(ONE25), "1.250000")
    t.require_eq(o.format_f(NEG_ONE), "-1.000000")
    t.require_eq(o.format_f(ZERO), "0.000000")
    t.require_eq(o.format_f(NZERO), "-0.000000")
    t.require_eq(o.format_f(INF_P), "inf")
    t.require_eq(o.format_f(INF_N), "-inf")
    t.require_eq(o.format_f(NAN_C), "nan")
    t.require_eq(o.format_f(o.div(ONE, o.add(ONE, TWO))), "0.333333")
    t.require_eq(o.format_f(o.div(TWO, o.add(ONE, TWO))), "0.666667")
    t.require_eq(o.format_f(o.from_int(100)), "100.000000")
    t.require_eq(o.format_f(o.parse("0.1")), "0.100000")
    t.require_eq(o.format_f(o.parse("0.0000001")), "0.000000")
    t.require_eq(o.format_f(o.parse("1000000.0")), "1000000.000000")


def test_format_g():
    t.require_eq(o.format_g(ONE), "1")
    t.require_eq(o.format_g(TWO), "2")
    t.require_eq(o.format_g(HALF), "0.5")
    t.require_eq(o.format_g(ONE25), "1.25")
    t.require_eq(o.format_g(NEG_ONE), "-1")
    t.require_eq(o.format_g(ZERO), "0")
    t.require_eq(o.format_g(NZERO), "-0")
    t.require_eq(o.format_g(INF_P), "inf")
    t.require_eq(o.format_g(INF_N), "-inf")
    t.require_eq(o.format_g(NAN_C), "nan")
    t.require_eq(o.format_g(o.parse("0.0001")), "0.0001")
    t.require_eq(o.format_g(o.parse("0.00001")), "1e-05")
    t.require_eq(o.format_g(o.from_int(100000)), "100000")
    t.require_eq(o.format_g(o.from_int(1000000)), "1e+06")
    t.require_eq(o.format_g(o.from_int(123456)), "123456")
    t.require_eq(o.format_g(o.from_int(1234567)), "1.23457e+06")
    t.require_eq(o.format_g(o.parse("3.14159")), "3.14159")
    t.require_eq(o.format_g(o.parse("3.141592653")), "3.14159")
    t.require_eq(o.format_g(o.parse("1e-5")), "1e-05")
    t.require_eq(o.format_g(o.parse("1.5e10")), "1.5e+10")
    t.require_eq(o.format_g(o.parse("0.1")), "0.1")
    t.require_eq(o.format_g(ZERO), "0")


def test_cross_checks_add_sub_round_trip():
    for a_str, b_str in [("1.0", "0.5"), ("3.14159", "2.71828"), ("100.0", "0.001")]:
        with t.subtest(f"({a_str}+{b_str})-{b_str}"):
            a = o.parse(a_str)
            b = o.parse(b_str)
            result = o.sub(o.add(a, b), b)
            fa = o.to_fraction(a)
            fr = o.to_fraction(result)
            t.require(abs(fr - fa) <= abs(fa) * Fraction(1, 1 << 112))


def test_cross_checks_parse_format_round_trip():
    for s in ["1.0", "0.5", "1.25", "100.0", "3.14159"]:
        with t.subtest(s):
            x = o.parse(s)
            x2 = o.parse(o.format_f(x))
            fx = o.to_fraction(x)
            fx2 = o.to_fraction(x2)
            if fx != 0:
                rel_err = abs(fx2 - fx) / abs(fx)
                t.require(rel_err < Fraction(1, 10**5))


def test_cross_checks_large_int_round_trip():
    for n in [0, 1, -1, 42, -100, 2**50, -(2**50), 2**113, -(2**113)]:
        with t.subtest(str(n)):
            t.require_eq(o.to_int(o.from_int(n)), n)
