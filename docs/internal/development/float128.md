# float128 — self-hosted IEEE 754 binary128

Status: **[IMPLEMENTED]**

`float128` is a true 16-byte IEEE 754 binary128 (quad-precision) type. All
arithmetic is performed by a soft-float runtime written in firescript itself
(`firescript/std/internal/float128.fire`), using only `+`, `-`, `*`, `/`, and
`%` on `uint64` — firescript has no bitwise or shift operators, so every shift
and mask is expressed as multiplication/division/modulo by a power of two.

## Representation

A `float128` is a by-value 16-byte struct (`__f128`, 16-byte aligned) holding
two `uint64` halves, matching the little-endian IEEE bit layout:

| half | bits | contents |
|------|------|----------|
| `lo` | `[63:0]`   | trailing significand bits `[63:0]` |
| `hi` | `[127:64]` | `sign<<63 \| exp<<48 \| significand[111:64]` |

- exponent: 15-bit biased, bias **16383**
- `exp == 0`: zero (`sig == 0`) or subnormal; effective exponent 1, no implicit 1
- `exp == 0x7FFF` (32767): infinity (`sig == 0`) or NaN (`sig != 0`)
- normal value = `(-1)^s · 2^(exp-16383) · (1 + sig/2^112)`
- canonical quiet NaN: `hi = 9223231299366420480`, `lo = 0`

The FLIR type and literal parsing live in `firescript/flir/ir.py`
(`ensure_f128_struct`, `ConstF128`) and `firescript/flir/lowering.py`
(`_decimal_to_f128_bits`, correctly-rounded RNE literal parsing). The three
low-level intrinsics `f128_from_halves(lo, hi)`, `f128_lo(x)`, `f128_hi(x)`
move between a `float128` and its raw halves; they require
`directive enable_lowlevel_runtime;` and exist for the runtime and tests only.

## Runtime entry points

The lowering routes `float128` operators and casts to these runtime functions:

| operation | function |
|-----------|----------|
| `+` `-` `*` `/` | `fs_rt_f128_add` / `_sub` / `_mul` / `_div` |
| unary `-` | `fs_rt_f128_neg` (sign-bit flip) |
| `== != < <= > >=` | `fs_rt_f128_eq` / `_ne` / `_lt` / `_le` / `_gt` / `_ge` |
| `as string` | `fs_rt_f128_to_str` (printf `%f`, 6 fraction digits) |
| `as float64` / `float64 as float128` | `fs_rt_f128_to_f64` / `fs_rt_f64_to_f128` |
| `as int64`/`uint64` and back | `fs_rt_f128_to_i64` / `_to_u64` / `fs_rt_i64_to_f128` / `fs_rt_u64_to_f128` |
| `string as float128` | `fs_rt_str_to_f128` (decimal parse) |

All operations are correctly rounded to nearest, ties to even, and handle
subnormals, signed zero, infinity, and NaN per IEEE 754.

### Key algorithms
- **add/sub**: align significands by the exponent difference into a 128-bit
  pair plus a guard/round/sticky accumulator, add or subtract, renormalize,
  round.
- **mul**: build 113-bit significands, form the full 128×128→256-bit product
  via 32-bit-decomposed partial products (`f128_mul64hi`), locate the leading
  bit, shift to the result position accumulating sticky, round, pack.
- **div**: bit-by-bit restoring long division of the dividend significand
  (shifted left 115) by the divisor significand, with the final remainder
  feeding the sticky bit; shared normalize/round/pack tail with `mul`.

## Validation

The ground-truth reference is `tests/support/float128_oracle.py`, a pure-stdlib
correctly-rounded binary128 implementation built on `fractions.Fraction`. The
runtime was validated bit-exactly against the oracle across the oracle's
hand-checked vectors plus large random and targeted fuzz (subnormal boundaries,
ties, near-overflow, dual-subnormal operands), and against f64↔f128 round trips.
The committed regression test is `tests/sources/special_types/float128_ops.fire`.
