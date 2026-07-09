"""float128_oracle.vectors() self-consistency check: every generated vector
must reproduce its own expected value when replayed through the oracle
functions (migrated from tests/float128_oracle.py's __main__ self-tests)."""
from __future__ import annotations

from harness import pyunit as t
from support import float128_oracle as o

_OPS = {
    "add": o.add, "sub": o.sub, "mul": o.mul, "div": o.div,
    "eq": o.eq, "ne": o.ne, "lt": o.lt, "le": o.le, "gt": o.gt, "ge": o.ge,
    "from_int": o.from_int, "to_int": o.to_int,
    "from_f64": o.from_f64, "to_f64": o.to_f64,
    "parse": o.parse, "format_f": o.format_f, "format_g": o.format_g,
    "unpack": o.unpack,
}

_UNARY_OPS = {"format_f", "format_g", "from_int", "to_int", "from_f64", "to_f64", "parse", "unpack"}
_BINARY_OPS = {"eq", "ne", "lt", "le", "gt", "ge", "add", "sub", "mul", "div"}


def _replay(vec: dict):
    op = vec["op"]
    inp = vec["inputs"]
    if op == "from_halves":
        lo, hi = inp[0]
        return o.from_halves(lo, hi)
    if op == "parse_format_f":
        return o.format_f(o.parse(inp[0]))
    if op == "from_f64_to_f64":
        bits64 = inp[0][0]
        return o.to_f64(o.from_f64(bits64))
    fn = _OPS[op]
    if op in _UNARY_OPS:
        return fn(inp[0])
    if op in _BINARY_OPS:
        return fn(inp[0], inp[1])
    return fn(*inp)


def test_all_generated_vectors_are_self_consistent():
    vecs = o.vectors()
    t.require(len(vecs) > 0, "vectors() produced no test cases")
    for i, vec in enumerate(vecs):
        op = vec["op"]
        if op not in _OPS and op not in ("from_halves", "parse_format_f", "from_f64_to_f64"):
            continue
        with t.subtest(f"{op}[{i}] {vec['note']}"):
            got = _replay(vec)
            exp = vec["expected"]
            if isinstance(exp, int) and isinstance(got, int) and o._is_nan(exp) and o._is_nan(got):
                continue
            t.require_eq(got, exp)
