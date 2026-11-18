<!-- Audit shard report, 2026-11-18. Raw audit output; see README.md for the consolidated plan. Verdicts are recommendations, not applied changes. -->
# S4 audit: tests/sources/{strings,arrays,control_flow,performance}  (51 files)

Method: every file compiled+run under wine in private temp dirs; all 51 outputs match their EXPECT blocks
(so no "stale" EXPECTs). Correctness was judged against language semantics/docs, plus extra probes
(see "compiler bugs"). Harness note: tests/harness/expectations.py normalize_output() strips TRAILING blank
lines, so an expected-empty output at the very end of a test is never asserted.

## DELETE-candidate
tests/sources/arrays/arrays_function_param.fire | REDUNDANT | exact duplicate of the `arraySum` case in functions/functions_array_params.fire (same for-in sum over [1..5] = 15); also array_length_propagation.sumOf
tests/sources/arrays/arrays_basics.fire | REDUNDANT, WEAK | empty array => edge_cases/edge_cases_arrays.fire; index/len => array_tests, arrays_typed, array_negative_indexing, array_length_propagation; "large array (20 elems)" and "bounds access" add nothing
tests/sources/arrays/array_tests.fire | REDUNDANT, INCORRECT | legacy multi-feature suite; every case covered elsewhere (indexing: arrays_typed; length: array_length_propagation; while iteration: arrays_iteration_while; string array: arrays_typed); pins the "[...]" placeholder from println(array) (see evidence)
tests/sources/performance/stress_array_bounds.fire | REDUNDANT, WEAK | not a stress/bounds test: only valid indices 0..9; subsumed by arrays_iteration_while/arrays_basics/array_negative_indexing; never touches an out-of-range index
tests/sources/performance/stress_deep_recursion.fire | REDUNDANT, WEAK | max depth 10; factorial(5) == functions/functions_recursion.fire; sum_to_n(10)/is_even(7) trivial depth. Not "deep"
tests/sources/performance/stress_string_operations.fire | REDUNDANT, WEAK | empty/concat/long string/string array all covered by strings_basics, strings_concatenation, arrays_typed; 3-iteration loop; stale unused s1/s2 + "equality might not be supported" comment (it is, strings_comparison). Only unique bits: raw newline/tab inside a literal, and i32_to_str (undocumented builtin)
tests/sources/arrays/arrays_iteration_c_style.fire | REDUNDANT | c-style array iteration covered by array_length_propagation.sumOf and arrays_basics-style loops; merge arrays_iteration_* into one file
tests/sources/arrays/arrays_iteration_while.fire | REDUNDANT | array_tests Test 4 / stress_array_bounds loop / control_flow_while
tests/sources/arrays/arrays_iteration_for_in.fire | REDUNDANT (except its fir/flir snapshot) | control_flow/for_in.fire "For-in with array variable" and arrays_function_param; keep only if the snapshot is wanted -> move `//@ snapshot: fir, flir` onto for_in.fire
tests/sources/arrays/array_dynamic_alloc.fire | REDUNDANT (moderate) | header rationale ("exercised standalone before any ArrayList code exists") is stale: std/collections arraylist_growth / arraylist_of_strings / hashmap_growth exercise fs_rt_array_new/copy<T> incl. string elems far more thoroughly. Keep only as a unit test of the intrinsic
tests/sources/strings/strings_basics.fire | TRIVIAL | println of string literals/empty/long literal is exercised by every test in the suite

## MERGE-candidate
tests/sources/arrays/arrays_mutation.fire | REDUNDANT-ish | positive-index store is the same path as array_negative_indexing (nums[-1]=99), arrays_of_class_instances (boxes[0]=...), array_dynamic_alloc; fold into one arrays test
tests/sources/arrays/arrays_move_assign_from_var.fire | KEEP-borderline | adjacent to array_length_propagation (`copy: int32[] = fixed;`, `mirror = values`) and for_in_and_match_temporaries (`fromExpr: int32[3] = src`); differs only in source being an unsized literal local. Merge into array_length_propagation
tests/sources/control_flow/for_c_style.fire | KEEP (one case redundant) | "empty init" case duplicates for_header_variants.fire "No init clause"; comment "variable declaration before loop" is inaccurate (the for declares i in its header)
tests/sources/performance/stress_integer_overflow.fire | WEAK, misnamed | contains NO overflow (10000*10000=1e8, 2147483640+5, -2147483640-5 all fit). Unique value = negative integer division/modulo semantics (-100/3=-33, -100/-3=33, 100/-3=-33, -10%3=-1, 10%-3=1, -10%-3=-1: all correct, match docs/reference/operators.md "truncates toward zero; sign of dividend") which no other test covers -> move to operators/ as operators_division_modulo_negative; drop the rest (val/2.. powers of two, zero arithmetic: trivial)
tests/sources/performance/stress_type_conversions.fire | REDUNDANT, WEAK | float->int truncation / int<->float covered by conversions/conversions_int_float, conversions_integer_wraparound (fneg=-3.99), int_float_cast_matrix; the ONLY coverage of legacy builtins i32_to_f64/f64_to_i32/i32_to_str (undocumented, listed in ast_to_fir.py) -> if those builtins are supported keep a tiny test in conversions/; else delete. Large run time (1.8 s) comes from nothing special
tests/sources/performance/fibonacci.fire | KEEP (relocate) | not a perf test (fib(20) ~22k calls, instant). Unique value vs functions_recursion: tree recursion + int64 + fir/flir snapshot. Move to functions/

## FIX-EXPECTATION / FIX-TEST
tests/sources/arrays/array_tests.fire | INCORRECT | see evidence E1 (also delete candidate)
tests/sources/control_flow/control_flow_braceless_if_at_eof.fire | INCORRECT (pins likely-bug) | see E2
tests/sources/strings/strings_index_of_substring.fire | WEAK | last case `s.substring(10, 2)` yields "" which is a trailing blank line => stripped, never asserted (see E3). Clamping semantics (negative start->0, end>len->len, start>end->"") pinned with no docs/header note
tests/sources/strings/strings_upper_lower.fire | WEAK | `empty.upper()` / `empty.lower()` are the last two printlns -> blank trailing lines stripped, effectively unasserted (E3)
tests/sources/strings/strings_comparison.fire | WEAK | see E4
tests/sources/strings/strings_unicode.fire | WEAK | see E5
tests/sources/arrays/arrays_typed.fire | WEAK | see E6
tests/sources/control_flow/for_in_and_match_temporaries.fire | WEAK (+ misfiled) | see E7

## KEEP
tests/sources/strings/string_escape_edge_cases.fire | KEEP | snapshot; pins impl-specific `\q` keeping the backslash, but header documents it as intentional; header also mentions `\0` which isn't exercised
tests/sources/strings/strings_concatenation.fire | KEEP | snapshot; all outputs verified
tests/sources/strings/strings_escapes.fire | KEEP | \n \t \" \\ ; (\r untested here, only via strings_trim)
tests/sources/strings/strings_for_in.fire | KEEP | ident / fresh-expr collection, break/continue; correct (a b c w x z l)
tests/sources/strings/strings_for_in_regression_conditional_move.fire | KEEP | narrow regression, FIRV-O2 tail case
tests/sources/strings/strings_for_in_regression_conditional_move_mid_body.fire | KEEP (low-confidence overlap) | harder variant would likely also catch the simple tail-position bug, but cheap and different fix path; note `first = first;` is a pointless filler statement
tests/sources/strings/strings_for_in_regression_conditional_move_break.fire | KEEP | distinct _drop_loop_cleanup path (FIRV-O2/O3)
tests/sources/strings/strings_regression_builtin_method_on_imported_call_result.fire | KEEP | regression, correct
tests/sources/strings/strings_replace.fire | KEEP | all outputs verified incl. empty-old no-op (documented in changelog)
tests/sources/strings/strings_starts_ends_with.fire | KEEP | verified
tests/sources/strings/strings_trim.fire | KEEP | verified; blank lines are mid-output so they ARE asserted
tests/sources/arrays/array_index_count.fire | KEEP | verified (index first-occurrence, -1, count)
tests/sources/arrays/array_length_propagation.fire | KEEP | lowering regression coverage; verified (3,1,3,50)
tests/sources/arrays/array_negative_indexing.fire | KEEP | snapshot; read/store/variable/param negative idx; verified
tests/sources/arrays/arrays_length_param.fire | KEEP | only test of `.size()` (note: `.size()` is not in docs/reference/arrays.md)
tests/sources/arrays/arrays_of_class_instances.fire | KEEP | owned + copyable class element paths; verified
tests/sources/arrays/array_to_string.fire | KEEP | `as string` on arrays ("[1, 2, 3]", float "[1.500000, 2.500000]", "[]"); feature undocumented in docs/reference/arrays.md (pins format w/o spec)
tests/sources/control_flow/control_flow_braceless.fire | KEEP | if/else/while/for braceless; verified
tests/sources/control_flow/control_flow_if.fire | KEEP | verified (B, Can drive)
tests/sources/control_flow/control_flow_mixed_nesting.fire | KEEP | 0,100,101,200 verified
tests/sources/control_flow/control_flow_nested_break_continue.fire | KEEP | strong; independently traced: output exactly matches (innermost-loop semantics; m ends at 5)
tests/sources/control_flow/control_flow_regression_conditional_move.fire | KEEP | preprocessor IF-move regression
tests/sources/control_flow/control_flow_while.fire | KEEP | snapshot; verified
tests/sources/control_flow/empty_statements.fire | KEEP | parser branch coverage; correct
tests/sources/control_flow/for_header_variants.fire | KEEP | traced: 0 1 2 | i++ => 4 | 4 5 | k=2 | m=0 m=1 : correct
tests/sources/control_flow/for_in_braceless_body.fire | KEEP | braceless for-in
tests/sources/control_flow/for_in.fire | KEEP | verified
(performance/fibonacci.fire listed above as KEEP-relocate)

## Evidence for INCORRECT / WEAK findings

E1 arrays/array_tests.fire INCORRECT. `println(numbers)` (numbers: int32[] = [10,20,30,40,50]) and `println(names)` are
expected to print `[...]`. That literal comes from flir/lowering.py::_array_to_string fallback
`ConstStr("[...]")` used when the array length is unknown. Probe: `a: int32[]=[10,20,30]; println(a)` -> `[...]`;
`b: int32[3]=[1,2,3]; println(b)` -> `[...]` (even statically sized!), but `println(b as string)` -> `[1, 2, 3]` and
array_to_string.fire expects `[1, 2, 3]` for the same data. So println(array) silently degrades to a placeholder
while `as string` works: the EXPECT block blessed a compiler inconsistency/placeholder. Suggest: fix compiler or
delete the println(array) lines; this test is the only place `[...]` appears in tests/. The rest of the file is redundant.

E2 control_flow_braceless_if_at_eof.fire INCORRECT (pins likely-bug). The source ends with `if (b)` and no body and
compiles successfully (probe: exit 0) and runs. A dangling `if` with no statement is malformed; the test was written
to cover a parser fallback branch (`_parse_braceless_body` returning None at EOF) and blesses it as
valid. Suggest: make the parser emit a diagnostic and move this to tests/sources/invalid/ (compile-fail with
//~ ERROR), or at minimum state in the header that it is a pinned leniency. Mark with owner decision.

E3 Trailing-blank-line blindness. strings_index_of_substring: println(s.substring(10,2)) prints "" as the final line;
strings_upper_lower: last two printlns print "" . normalize_output() strips them so e.g. a regression that printed
"x" is caught but one that printed "   " or nothing is not, and an off-by-one that returns the empty string vs
nothing cannot be distinguished. Fix: wrap in markers (`println("[" + s.substring(10,2) + "]")` -> `[]`) or
reorder so the empty case is not last. Also add a one-line header note that substring clamps out-of-range bounds
(negative start -> 0, end>len -> len, start>end -> "") since this is pinned but undocumented (only the changelog
mentions the methods).

E4 strings_comparison WEAK. Only literal-vs-literal equal ("apple"=="apple", which may be interned/pointer-equal),
and one unequal same-length-class case. Missing: different lengths with common prefix ("app" vs "apple"),
equal-length-different-content ("abc" vs "abd"), empty string, and equal strings built at runtime
("ap"+"ple" vs "apple") which would catch a pointer-compare regression. I probed all of these: they currently
work (false,true,false,true,true,true,false), so the replacement is just those lines.

E5 strings_unicode WEAK. Only round-trips bytes through println. Probe: "café".length() == 5 (byte count, not 4
chars), so length/indexOf/for-in semantics on non-ASCII are byte-based and undocumented; test pins none of it
(good: not wrongly pinned, but also would not catch a regression in length/slicing on multibyte input). Suggest
adding `.length()` expectation only once the owner decides the intended semantics.

E6 arrays_typed WEAK. int8 array reads only [0] and length; int64 reads only [1]; f64 only [1]; bool [0],[1].
A wrong element stride for int8/int16/uint8 (1-byte elements) would be invisible at index 0. Read the last
element of each typed array (and at least 3 elements of the int8 one); other widths (uint8/16/32/64, int16, char) absent.

E7 for_in_and_match_temporaries WEAK/misfiled. Bundles match-on-call-result and sized-array-declaration paths
(not control flow). `uninitialized: int32[4]` reads only [0]: zero-initialization of a sized array is
only asserted for one element of one array in the whole suite (array_to_string's int32[0] has no elements);
a fresh stack frame may already be zero there. Suggest reading all 4 elements, and after dirtying the stack
with a prior function call. Also relocate the match/array-decl parts to match/ and arrays/.

stress_*: manifest (tests/TEST_MANIFEST.md lines 659-665) describes these as "stress", "heavy", "repeated"
tests; none loops more than 10 times or allocates more than a few objects. There is NO real performance/stress
test in the directory. Runtimes are all <2 s including wine start-up, so nothing is slow; nothing stresses either.
Suggested real stress tests: recursion depth ~1e5 (stack limit behavior), a 1e6-iteration loop with string
concatenation/drop (leak/allocator), a large (e.g. 1e5-element) array fill/sum.

## Compiler bugs / doc mismatches discovered (minimal repros; all verified by me under wine)

B1 println(array) prints "[...]" (see E1):
   a: int32[3] = [1,2,3]; println(a);   // prints [...]   ; println(a as string) prints [1, 2, 3]

B2 Out-of-range array index is unchecked, reads garbage; docs/reference/arrays.md says it "will cause a runtime error":
   a: int32[] = [1,2,3]; i: int32 = 5; println(a[i]); println("after");   // prints 6029362 then "after", exit 0
   No test anywhere pins OOB behavior; stress_array_bounds does not either.

B3 Signed integer overflow wraps silently; docs/reference/error_handling.md says it "traps at runtime rather than silently wrapping":
   a: int32 = 2147483647; b: int32 = a + 1; println(b);   // prints -2147483648, exit 0
   (stress_integer_overflow never overflows, so the doc/impl mismatch is not caught. edge_cases/edge_cases_overflow_underflow.fire
   is labelled "behavior may vary"; outside my slice.)

B4 ICE returning an array literal from an `int32[]` function (also noted in for_in_and_match_temporaries header, but
   NOT captured by any known-issue test; note tests/sources/known_issues/ does not exist, only invalid/known_issues/):
   fn mk() -> int32[] { return [1,2,3]; }  x: int32[] = mk(); println(x.length());
   -> FIR verifier dump (FIRV-T4 'int32[3]' vs declared 'int32[]'), no binary. (functions_array_return.fire only returns a param.)

B5 `if (b)` with no body at EOF compiles (see E2).

B6 String literal with embedded NUL truncates: r: string = "a\rb\0c"; println(r.length()); -> 3 (expected 5): strings are
   NUL-terminated C-style; string_escape_edge_cases.fire header claims `\0` is handled but no test exercises it. Likely a
   known limitation; worth a documented note or a test.

## Could not verify
- Whether `.size()` on arrays, `as string` on arrays and substring clamping are intended/specified (no docs found).
- Whether snapshot files (tests/snapshots/*) are current: I did not run the harness (forbidden); only checked the run output.
- Determinism / compile-fail kinds were not run.
