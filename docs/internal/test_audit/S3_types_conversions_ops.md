<!-- Audit shard report, 2026-11-18. Raw audit output; see README.md for the consolidated plan. Verdicts are recommendations, not applied changes. -->
# S3 audit: types / conversions / operators / edge_cases / identifiers / io  (53 files)

Method: every file compiled + run in a private temp dir (wine) with my own runner; all 53 outputs MATCH their EXPECT
blocks, so no test is stale. Numerics re-derived with a Python oracle (two's-complement wrap, struct float32 rounding,
printf %f for float64). All EXPECT *values* are arithmetically right under the compiler's actual semantics; the
INCORRECT verdicts below are about pinning behavior that contradicts the docs or is undefined/undocumented.
Docs facts used: type_system.md L141-153 and error_handling.md L31-38 say fixed-width int overflow TRAPS at runtime
(compile error if constant-detectable). Float printing is printf "%f" (6 digits; stated in special_types/float128_ops.fire).
Harness normalisation (tests/harness/expectations.py:20) rstrips every line and strips trailing blank lines.

## DELETE-candidate
types/types_bool.fire | REDUNDANT, TRIVIAL | prints two bool literals; types_deep.fire (bool section), operators_boolean.fire, io_test.fire all do more
types/types_tests.fire | REDUNDANT | every section (int ops, float32/64 add, bool, compare, string concat, int/string arrays) repeated in types_deep.fire + operators_arithmetic.fire + operators_comparison.fire
operators/unary_test.fire | REDUNDANT | expressions/expressions_unary_and_incdec.fire covers -x, -(-x), +x; only extra is `y: int32 = -x` into a var and top-level `return 0;`
conversions/conversions_to_string.fire | REDUNDANT | subset of conversions_to_string_all_types.fire (int32, float32, bool) with weaker values
conversions/conversions_int_narrowing.fire | REDUNDANT | conversions_integer_wraparound.fire (70000 as int16/int8, uint64/int64 narrowing) covers it with more discriminating values
conversions/conversions_int_widening.fire | REDUNDANT, WEAK | positive 42/100 cannot detect zero- vs sign-extension; wraparound test covers n8 as int64/uint32, u8 as int32/int64. Only the 3-deep cast chain is unique
conversions/conversions_signed_unsigned.fire | REDUNDANT | u8->int8, u32->int32, neg->uint32 are all in conversions_integer_wraparound.fire
edge_cases/edge_cases_comparisons.fire | REDUNDANT, TRIVIAL | literal 0/1 comparisons; operators_comparison.fire + operators_boolean.fire cover all of it
edge_cases/edge_cases_arithmetic.fire | REDUNDANT, TRIVIAL | 1/1, 1.0f/2.0f, 0%5, 5%5, 1%5; operators_arithmetic.fire covers / and %
edge_cases/edge_cases_strings.fire | TRIVIAL | length of "a" and "   "; strings/ tests cover length. (Missing the one real edge: "".length())
edge_cases/edge_cases_overflow_underflow.fire | INCORRECT, REDUNDANT | see detail #1; its 6 lines are fully subsumed by types_int8 + types_uint8 (also INCORRECT)
edge_cases/edge_cases.fire | REDUNDANT, WEAK | grab-bag: nested scopes (scoping/scoping_block_nesting.fire), compound assign (operators_arithmetic.fire), inc/dec (expressions_unary_and_incdec.fire), while-zero (edge_cases_loops), fn call, array index. Compound-assign chain ends at 0 so most mutations pass; labels are stale ("avoid empty array literals" while empty arrays are used elsewhere)
edge_cases/edge_cases_nesting_and_functions.fire | REDUNDANT | 5-deep blocks -> scoping/scoping_block_nesting.fire; if/else-if returns -> functions/ + control_flow_if.fire
edge_cases/edge_cases_arrays.fire | REDUNDANT | empty array length -> arrays/arrays_basics.fire L10; single element / for-in covered in arrays/ and control_flow/for_in.fire

## MERGE-candidate
types/types_int8.fire + types_uint8.fire | INCORRECT (overflow lines) | after dropping the wrap lines, merge bounds into one "integer bounds" file (see #1)
types/types_int16.fire, types_int32.fire, types_int64.fire, types_uint16.fire, types_uint32.fire, types_uint64.fire | KEEP-ish, MERGE | each prints min/max + one op; fine individually but one file ("integer bounds") would do. int64 keeps its snapshot directive. int16/uint16/uint32 min/max not covered elsewhere so keep content
edge_cases/edge_cases_numeric_bounds.fire | REDUNDANT, TRIVIAL(floats) | i8/i32/u8/i64/u64 bounds duplicate types_int8/int32/int64/uint8/uint64; "small" floats 0.0001f/0.0000001 are printed with %f (0.000100 / 0.000000): the float64 case prints 0.000000 so it cannot distinguish 1e-7 from 0
conversions/string_to_numeric_casts.fire | KEEP/MERGE | covers int64, uint64 max, float32 which conversions_string_to_numeric_all_types lacks; merge the three lines there
conversions/conversions_int_float.fire | MERGE | int->float32/64, float32->int (42.75), float64->int64; partially in int_float_cast_matrix + wraparound; fold in
conversions/conversions_in_expressions.fire | REDUNDANT-ish | expressions/expressions_casts.fire does (int as float32)/float32; int8+int16 widening sum is the only extra
conversions/string_cast_test.fire | REDUNDANT, directive misuse | uses `directive enable_lowlevel_stdout` + stdout() (CLAUDE.md: no directives in tests unless testing the directive); covers all types as conversions_to_string_all_types does. Unique: signed max values, string->string identity, 0. Move those lines into all_types and drop this

## FIX-EXPECTATION / FIX-TEST
types/types_int8.fire | INCORRECT | `i8_max + 1i8` expects -128, `i8_min - 1i8` expects 127; docs say runtime trap/compile error (detail #1)
types/types_uint8.fire | INCORRECT | `u8_max + 1u8` expects 0; same contradiction
edge_cases/edge_cases_overflow_underflow.fire | INCORRECT | same; header even says "behavior may vary"
conversions/builtin_conversions.fire | INCORRECT/WEAK | toInt/toFloat/toDouble/toBool/toChar/toString are NOT in docs/reference (only a v0.x changelog mention); pins toChar("65") -> '6' (first char) while toChar(66) -> 'B' (code point): inconsistent, undocumented (detail #2)
conversions/builtin_conversions_numeric_source.fire | WEAK | same undocumented builtins; toBool(5)=true, toInt(9.75)=9 are plausible but unspecified. Ask owner whether these builtins are supported/deprecated
conversions/int_float_cast_matrix.fire | INCORRECT (partly), WEAK | `200.9 as int8` -> -56 pins out-of-range float->int result (undefined in C; docs only say "may truncate"). Probe shows the impl goes float->int64->truncate (1e10 as int32 = 1410065408, inf as int32 = 0) (detail #3)
conversions/conversions_regression_uint64_to_float.fire | WEAK | claims to test the sticky bit but cannot (detail #4); real bug found
conversions/conversions_float_precision.fire | WEAK | detail #5
types/const_declarations_wide_types.fire | REDUNDANT, WEAK | PI32 float32 const duplicates const_declarations.fire SCALE; `it\'s here` duplicates strings/string_escape_edge_cases.fire; float128 const is declared-but-never-read so asserts only "compiles" (the underlying backend bug is described in its own header: that belongs in a known_issues test, not a silent drop)
edge_cases/edge_cases_zero_values.fire | WEAK | `println("")` expectation is invisible: normaliser strips trailing blank lines, so a missing empty line would still pass. Put another println after it
operators/operators_arithmetic.fire | WEAK (float pow) | `fbase ** fexp` only uses integer exponents (2.0**3.0); real compiler bug hidden (detail #6)
operators/operators_regression_power_assign.fire | KEEP, WEAK(float) | regression for **=; only integer-valued exponents (1.5 **= 2.0)

## KEEP
types/char_type.fire | KEEP | char literals + escapes; note `'\d'`->'d' pins an undocumented fallback (commented); \r \0 \' \" not exercised though listed in header
types/const_declarations.fire | KEEP | module-level consts incl. float32 global path
types/literal_bases_and_separators.fire | KEEP | hex/bin/oct/`_`; values verified (0xDEAD_BEEF=3735928559, 0o755=493). Gap: no negative/uppercase-prefix/invalid-digit cases (check invalid/literals)
types/types_deep.fire | KEEP (partially redundant) | only test doing add/sub across all int widths + float32/64/128 +,-,*,/. Bool/string/array/compare sections are redundant. All values verified (f128 1.5679.. etc). Prints at %f so float32-vs-64 differences are invisible
types/types_float32.fire | KEEP, WEAK | %f hides single precision; values correct (3.14159f*2 = 6.283180) but a double-precision implementation gives identical output. Add e.g. 16777216.0f + 1.0f == 16777216.0f (I verified compiler does round in float32)
types/types_float64.fire | KEEP, WEAK | 1e100 prints exact 101-digit expansion (== python '%f'%1e100, verified): good formatter check, but 1e-100 -> 0.000000 is trivial
conversions/conversions_integer_wraparound.fire | KEEP | strongest conversion test; all 24 outputs verified with oracle
conversions/conversions_string_to_numeric_all_types.fire | KEEP | boundaries + "+7" + "1e3" (parse leniency undocumented). Gap: no invalid string ("abc", "300" as int8)
conversions/conversions_to_string_all_types.fire | KEEP | all types at extremes
conversions/numeric_casts.fire | KEEP (snapshot) | exists for fir/flir snapshots; casts are in-range so no truncation is checked
operators/operators_boolean.fire | KEEP | truth tables; all 24 lines verified by hand
operators/operators_comparison.fire | KEEP, WEAK | only small positive values: no negative/signed-vs-unsigned, high-bit uint32/uint64, NaN cases. (I probed unsigned/signed high-bit comparisons: all correct today, but nothing guards them)
operators/operators_logical.fire | KEEP (snapshot) | mostly overlaps operators_boolean but carries fir/flir snapshots
operators/operators_logical_short_circuit.fire | KEEP | good: observable side effects
identifiers/identifiers_keyword_prefix.fire | KEEP | regression; add a `void`-prefixed identifier (lexer fix also covered VOID_LITERAL)
io/io_test.fire | KEEP | only per-type print/println-without-newline test; float128/uint64 included
edge_cases/edge_cases_loops.fire | KEEP (low value) | zero/one-iteration while/C-for/for-in-empty; control_flow/ has no zero-iteration cases, so keep

## Counts (53 files; a file can carry several)
KEEP-ish 22 | REDUNDANT 17 | TRIVIAL 4 | WEAK 14 | INCORRECT 5 (types_int8, types_uint8, edge_cases_overflow_underflow, builtin_conversions (pins inconsistent undocumented behavior), int_float_cast_matrix (partial))

# Detailed evidence

## #1 INCORRECT: wraparound pinned where docs mandate a trap
types_int8.fire, types_uint8.fire, edge_cases_overflow_underflow.fire expect `127i8 + 1i8 = -128`, `-128i8 - 1i8 = 127`,
`255u8 + 1u8 = 0`. docs/reference/type_system.md L141-153 and error_handling.md L31-38: "arithmetic ... that exceeds the
representable range will throw an error at runtime ... constant expressions are compile-time errors". The compiler wraps
silently (also int32: `2147483647 + 1` -> -2147483648, `2 ** 31` -> -2147483648, uint8 0-1 -> 255; verified by probe).
Either the compiler is wrong (and these must move to tests/sources/known_issues/ or become an expected-trap test), or the
docs are stale; in both cases blessing wrap silently is wrong. Owner decision needed; stress_integer_overflow.fire
(performance/, out of my slice) pins the same wrap. Suggested: delete the overflow lines from the three files; add one
test that states the decided semantics (trap test, or `//` note + wrap test if docs get changed).

## #2 builtin_conversions.fire
toChar("65") expects `6`; toChar(66) (other file) expects `B`. TEST_MANIFEST documents "toChar on a string takes its first
character's code point". No reference doc defines these builtins; parser/type_system.py L873 still special-cases them.
Not wrong per se but unspecified and self-inconsistent; recommend confirming the builtins are supported, otherwise
mark known-legacy. If kept, drop the toChar("65") line.

## #3 int_float_cast_matrix.fire
`f1 as int8` (200.9) -> -56, `as int16` -> 200: out-of-range float->narrow-int is UB in C, docs only say "may lose
precision or truncate". Probe results (all pinned nowhere): NaN as int32 = 0, inf as int32 = 0, inf as int64 =
-9223372036854775808, 300.5 as uint8 = 44, -1.5 as uint8 = 255, -1.0 as uint64 = 18446744073709551615,
2147483648.0 as int32 = -2147483648, 1e10 as int32 = 1410065408. Keep only in-range cases (the uint64 >2^63 lines are
good and verified: float32(1.8e19) = 18000000404716257280 exact), or document the semantics first.

## #4 conversions_regression_uint64_to_float.fire (WEAK + real bug)
Header says the `odd` value (2^63+1) checks "the halving step must keep the sticky bit". 2^63+1 rounds to 2^63 with or
without a sticky bit, so the case cannot fail. A value that does need it: 9223372036854776833u64 (= 2^63+1025).
Correct float64: 9223372036854777856.000000 (python float(2**63+1025)). Compiler prints 9223372036854775808.000000: WRONG
(see bugs). Replacement lines:  `println(9223372036854776833u64 as float64);` expect 9223372036854777856.000000 (will fail
until fixed => known_issues convention or fix compiler first).

## #5 conversions_float_precision.fire
Header: "Float64 to float32 (precision loss)". Output shows no loss: 3.141593 / 3.141593 (6-digit %f). Test cannot detect a
no-op cast. Replacement: `println((precise as float32) as float64 == precise)` expect false; `println((0.1f as float64) == 0.1)` expect false
(I verified the latter is false today), `println((16777217.0 as float32) as float64)` expect 16777216.000000.

## #6 float ** fractional exponent (see bugs); operators_arithmetic.fire should add `println(2.0 ** 0.5)` -> 1.414214, `9.0 ** 0.5` -> 3.000000.

## WEAK summary of printing
Every float assertion goes through %f (6 decimals) so float32 vs float64 storage, subnormals, rounding mode and NaN/inf
formatting (inf/-inf/nan do print as `inf`, `-inf`, `nan`; -0.0 prints `-0.000000`) are essentially untested in this slice;
no test in the slice covers NaN, inf, float overflow (3.4e38f32*10 -> inf works), or the documented `type_system.md`
NaN/Infinity examples.

# Compiler bugs discovered (all reproduced in private dir)

1. NaN comparisons are wrong (IEEE says all false except !=):
   z: float64 = 0.0; n: float64 = z / z;
   println(n == n)  -> true   (expected false)
   println(n == 1.0) -> true   (false);  n < 1.0 -> true (false);  n <= 1.0 -> true (false); n > 1.0, n >= 1.0 false (ok)
   same for float32. Docs: "Floating point operations follow IEEE 754 semantics". Looks like ucomisd with unordered (ZF=PF=CF=1) not checked for PF.
2. Float `**` ignores fractional exponent: `println(2.0 ** 0.5)` -> 1.000000 (1.414214); `9.0 ** 0.5` -> 1.000000 (3);
   `2.0 ** 1.5` -> 2.000000 (2.828427); `10.0 ** 2.5` -> 100.000000 (316.227766). Integer exponents are fine. Exponent is truncated.
3. uint64 -> float64 loses the sticky bit: `println(9223372036854776833u64 as float64)` -> 9223372036854775808.000000,
   correct 9223372036854777856.000000. (2^63+1025; not rounded up; values < 2^63 and exact halves are fine.)
4. Integer overflow wraps instead of trapping (docs contradiction, see #1).
5. `2 ** -1` (int) prints 1 (undocumented; should likely be error or 0); int `5 / z` with z == 0 raises a raw hardware
   divide-by-zero (wine: "Unhandled division by zero"), not the documented firescript runtime error. Not covered by any test in my slice.
6. Float->int casts of out-of-range/NaN/inf values are silent and inconsistent between widths (see #3 list) - spec gap more than bug.

Could not verify: native Windows behavior (only wine); the harness's own run of these tests (not run per instructions;
my private runner reproduced all 53 EXPECT blocks); the redundancy claims for edge_cases_* vs scoping/functions/arrays tests
rest on grep + reading, not on mutation testing.
