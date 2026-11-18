<!-- Audit shard report, 2026-11-18. Raw audit output; see README.md for the consolidated plan. Verdicts are recommendations, not applied changes. -->
# S2 audit: generics, functions, generators, scoping, expressions (60 files)

Method: every file was compiled+run in a private temp dir (wine) and diffed against its EXPECT block: all 60 match
(function_main_ignores_top_level only "differs" because I merged the compiler's WARNING line into stdout; real output matches).
Expected values were also recomputed by hand (arithmetic, loop trip counts, float formatting). No EXPECT block is numerically wrong;
the problems are (a) tests that pin unspecified/buggy/PLANNED behavior, (b) redundancy, (c) weak/stale headers.

Scratch repros live in .../scratchpad/audit/s2work/t/*.fire (a,b,c,d,g1,g2,g3,h,h1,h2,p,q,m).

## DELETE-candidates (REDUNDANT)
generics/math_with_constraints.fire | REDUNDANT | every call (max/min int32, max float64, abs int64, clamp int32) is also in tests/sources/std/math/math_abs_min_max_clamp.fire (superset: ties, u8, i8, bounds); cross-module generic call also covered by generics/generic_nested_call.fire
generics/generics_constraint.fire | REDUNDANT | `max<T: int32|int64>` with int32 args is a strict subset of generics/generics_basic.fire (max/min/abs over 4-type unions, int32/int64/float32, explicit + inferred)
functions/functions_explicit_owned_param.fire | REDUNDANT | byte-for-byte the same Box/consume(owned b) program as memory/memory_owned_function_param.fire (that one just wraps it in main). Also WEAK (see below)
functions/functions_stray_semicolon.fire | REDUNDANT | control_flow/empty_statements.fire already has `;` as first/middle/last statement in an identical fn body, same output
functions/functions_array_params.fire | REDUNDANT | arraySum half is identical to arrays/arrays_function_param.fire (sum 1..5=15); getFirst (index into param) is covered by functions.fire sumFirstTwo, functions_array_return.fire, functions_sized_array_param.fire
expressions/expressions_unary_and_incdec.fire | REDUNDANT | -x, -(-x) in operators/operators_arithmetic.fire + operators/unary_test.fire (also `+5`); ++/-- in operators_arithmetic.fire (and ~10 loop tests). Only unique bit: unary + on a variable (`+pos`)
expressions/expressions_casts.fire | REDUNDANT | conversions/conversions_in_expressions.fire (`(x as float32) / y` = 2.5) and conversions/conversions_int_float.fire; plus the int_float_cast_matrix test
expressions/expressions_array_and_string.fire | REDUNDANT | arrays/arrays_basics.fire (index/length()-1), strings/strings_concatenation.fire (`"Count: " + (n as string)`, `a + " " + b`)
expressions/expressions_nested_and_conditional.fire | REDUNDANT/TRIVIAL | nesting ((10+5)*2-6)/3 is covered by operator_precedence.fire parens cases; the "conditional" half is `if (10 > 5)` on a constant + if/else assign = control_flow/control_flow_if.fire
scoping/scope_tests.fire | REDUNDANT | mirror of the docs example; bare-block / nested-if / outer-read cases are all in scoping_block_nesting.fire + scoping_control_flow.fire
scoping/scoping_function.fire | REDUNDANT + WEAK | param+local in a function is exercised by every functions_* test; header comment ("functions can't access outer scope variables") is not tested and contradicts docs (see compiler bug 3)
functions/functions.fire | REDUNDANT | kitchen-sink; add int32 -> functions_basic_params, float32 -> functions_return_types, float64 mul -> functions_many_params, array param -> arrays_function_param, string return -> functions_return_types, void -> functions_void. Header/comments stale ("char type not yet in types", "no substring support yet", "&& not implemented yet"). Only mildly unique: bool *parameters* (bothTrue)
generics/generics_modulo_type_param.fire | REDUNDANT | both it and generic_function_same_type_param_modulo.fire reach the same branch (type_system.py:625 `left_type == right_type and is_left_type_param`) and print 1; the latter additionally has FIR/FLIR snapshots

## MERGE-candidates
generators/generators_multi_yield_sites.fire | REDUNDANT(low) | generators_advanced.fire `multiYield()` already has 3 yield sites (same multi-way resume dispatch) and its `earlyStop(limit)` shows params persisting across resumes. Fold `yield a+b` (param reuse) into advanced if wanted
functions/functions_missing_return_fallthrough.fire, functions/functions_fallthrough_return.fire, functions/functions_return_types.fire (fallthrough half) | REDUNDANT + INCORRECT | three files assert the same "implicit zero on fall-off" behavior (bool appears in all three; int32, float64, float128 once each). See INCORRECT section. If kept at all, one file.
generics/constraint_intersection.fire + generics/generic_intersection_constraint.fire | REDUNDANT | identical program (identity<T: int32 & Comparable>(7/5i32)); alias form vs inline form. Both INCORRECT (below)

## FIX-EXPECTATION / FIX-TEST (INCORRECT or stale)
generics/constraint_intersection.fire | INCORRECT | pins `&` constraint semantics that are [PLANNED] and actually implemented as a *union containing a literal "&"* (see evidence 1)
generics/generic_intersection_constraint.fire | INCORRECT | same
generics/generics_constraint_intersection.fire | INCORRECT | `constraint Combo = int32 & float64` is an empty intersection; test instantiates it with int32 and expects success
scoping/scope_stray_token_recovery.fire | INCORRECT | asserts a program containing a lone `]` compiles and runs with no diagnostic (evidence 2)
functions/functions_missing_return_fallthrough.fire | INCORRECT(soft) | pins unspecified implicit-zero return; header also contains a stale/odd bug narrative
functions/functions_fallthrough_return.fire | INCORRECT(soft) | same
functions/functions_return_types.fire | INCORRECT(soft)+stale | fallthrough part pins unspecified behavior; header claims `char` cannot be a return type -- false now (char return compiles and runs)
generics/generics_class_basic.fire, generics/generics_class_inferred_construct.fire | INCORRECT(soft) | `copyable class Pair<T,U>` instantiated with `string` (an Owned type); docs/reference/classes.md requires all fields of a copyable class be Copyable (evidence 3)
generators/generators_frame_zero_init_types.fire | WEAK + stale | evidence 4
scoping/scoping_variable_declaration_order.fire | WEAK/INCORRECT header | evidence 5
generics/generics_swap.fire | WEAK | header says "multiple type parameters" (only one, T); swap works on copies and never checks caller values are unchanged
functions/functions_many_params.fire | WEAK | evidence 6
generators/generators_borrow_param.fire | WEAK | does not check the borrowed box is still usable/not dropped after the loop
functions/functions_explicit_owned_param.fire | WEAK | only checks `owned` parses; nothing checks the move (no use-after-move rejection, no drop/leak assertion)
expressions/operator_precedence.fire | WEAK (minor) | evidence 7

## KEEP
generics/constraint_alias_test.fire | KEEP | unique: `constraint X = a|b|..` alias used as bound; ints+floats (abs half overlaps generics_basic, harmless). Comments say 4.0 while EXPECT is 4.000000 (cosmetic)
generics/nested_constraint_test.fire | KEEP | alias-of-aliases (AllInt = SmallInt | MediumInt) over int8..int64; values verified (30/300/3000/30000)
generics/generic_class_static_method_explicit.fire | KEEP | narrow parser regression (`Box<int32>.make(5)`)
generics/generic_class_static_method_inferred.fire | KEEP | narrow regression (`Box.make(5)` inferred)
generics/generic_function_same_type_param_modulo.fire | KEEP | snapshot test of `%` on type param (keeps; subsumes generics_modulo_type_param)
generics/generic_method_if_condition.fire | KEEP | regression, cross-module generic method as inline condition
generics/generic_nested_call.fire | KEEP | regression, nested cross-module generic call
generics/generic_self_referential_static_factory.fire | KEEP | static factory + this.method() on `Box<T?>`; overlaps the two static-method regressions but adds self-reference/nullable T
generics/generics_array_param_inference.fire | KEEP | regression, T[] inference + hidden length ABI; outputs verified
generics/generics_basic.fire | KEEP | main generic-function test w/ snapshots
generics/generics_clamp.fire | KEEP(low)/MERGE | 3-param generic w/ two early returns; mostly covered by generics_basic + std math clamp test; values verified (10,15,20,1.0,3.0,5.0)
generics/generics_compound_assignment.fire | KEEP | unique: += *= -= /= on type-param local; verified 2 / 3.25 / 10 by hand (int division 8/3=2)
generics/generics_regression_imported_class_type_arg.fire | KEEP | regression (imported class as type arg)
generics/generics_simple.fire | KEEP | only test of an *unconstrained* `T` with `>` (docs show that form)
generics/generics_swap.fire | KEEP(weak) | see above
functions/function_main_ignores_top_level.fire | KEEP | only test of "top-level ignored when main exists"; NOTE this behavior is documented nowhere in docs/reference (only compiler WARNING) -- design decision worth confirming
functions/function_user_main.fire | KEEP | dedicated entry-point test (main is also used incidentally elsewhere)
functions/functions_array_return.fire | KEEP | array return value used in expressions; header mentions "array methods" but none are called (cosmetic)
functions/functions_basic_params.fire | KEEP | all values verified
functions/functions_calling_functions.fire | KEEP | snapshot; 75/20/10 verified
functions/functions_early_and_multiple_returns.fire | KEEP | else-if chain returns
functions/functions_nullable_scalar_param.fire | KEEP | unique (has-value companion param); zero vs null distinguished
functions/functions_rare_constructs.fire | KEEP | snapshot; sized-array for-in identifier branch is not hit by arrays_iteration_for_in (unsized). First half overlaps arrays_length_param
functions/functions_recursion.fire | KEEP | factorial
functions/functions_sized_array_param.fire | KEEP | only `int32[N]` param test
functions/functions_void.fire | KEEP (small) | void fn, trivial but dedicated
generators/generators_advanced.fire | KEEP | early `return;` in generator + 2nd call site + multi-yield. Header documents an unfixed ICE (compiler bug 1) that has no known_issues test
generators/generators_basic.fire | KEEP | the ONLY positive test of std.ranges range/rangeFrom/rangeStep (tests/sources/std/ranges has only an empty/negative test) plus user generator; snapshots
generators/generators_break_continue.fire | KEEP | break/continue/nested generator loops; verified 0,1,2 / 1,3,5 / 0,1,10,11
scoping/scoping_block_nesting.fire | KEEP | verified 12-line nested output by hand
scoping/scoping_control_flow.fire | KEEP | if/else/while/for/for-in scope bodies, values verified
scoping/scoping_variable_declaration_order.fire | KEEP(weak) | see evidence 5
expressions/expressions_function_calls.fire | KEEP | only test of calls as arguments of non-generic calls (add(mul(..),..)); values verified

## Detailed evidence

### 1. `&` "intersection" constraints (INCORRECT x3)
- docs/reference/type_system.md: interface constraints and "Multiple Constraints" (`Comparable & (int32|float64)`) are marked [PLANNED]; `Comparable` is not defined anywhere (grep: only mentioned in docs and as a hard-coded allow-list string in firescript/parser/type_system.py:842).
- firescript/parser/declarations.py:82-86 handles AMPERSAND by appending a literal "&" part and joining with " | ". Probe (s2work/t/b.fire): `fn identity<T: int32 & Nonexistent>` rejects float64 with message "does not satisfy constraint 'int32 | & | Nonexistent'" -- i.e. the constraint is a union of {int32, "&", Nonexistent}. Probe c.fire: `constraint Combo = int32 & float64; identity(5.5f64)` is accepted for float64 as well as int32 -- so `&` currently behaves as union, not intersection.
- Correct behavior under real intersection semantics: `int32 & float64` admits no type (identity(5i32) should be an error); `int32 & Comparable` with undefined Comparable should be an unknown-type error until interfaces exist. The tests therefore pin an accidental parse artifact of a PLANNED feature, with no [PLANNED] note.
- Suggested replacement: delete all three; if intersection syntax should be tracked, add a tests/sources/invalid/known_issues/ file expecting an error for `T: int32 & float64`/unknown interface. Also manifest line 634 should be dropped.

### 2. scope_stray_token_recovery.fire (INCORRECT)
- Source has a lone `]` inside a function body. It compiles with exit 0, no warning, and prints 5. Probe a.fire: a stray `)` in a fn body and a stray `]` at top level are also silently skipped. In contrast tests/sources/invalid/syntax/syntax_errors.fire expects FS-PARSE-0010/0012 for stray `@ # $`. The `]` is dropped in parse_scope's "no progress -> force advance" guard (firescript/parser/statements.py:664-668), because _parse_statement returns None without reporting an error.
- Correct behavior: a syntax error (FS-PARSE-*). The test validates "recovery" by asserting the invalid program is valid. Replace with a tests/sources/invalid/syntax test (or known_issues/ version) `//~ ERROR FS-PARSE-xxxx` on the `]`. Unlike control_flow/empty_statements.fire (legit `;`), this is not valid input.

### 3. copyable generic class with a string (soft INCORRECT)
- docs/reference/classes.md "Copyable Classes": all fields must be Copyable. generics_class_basic.fire p2 (`Pair<int32,string>`) and generics_class_inferred_construct.fire (`Pair<int32,string>`) violate it. The compiler does not enforce the rule at all (probe q.fire: non-generic `copyable class S { name: string }` also compiles silently), and p.fire shows a bit-copy `p3 = p2` of such a value compiles and runs (potential double-free of the string, not observed here).
- The docs' own example uses the same `copyable class Pair<T,U>`, so this is partly a docs/compiler gap; but tests should not rely on it. Suggested: use `class Pair<T,U>` (owned) for the string instantiations, keep copyable for int/int; add an invalid test for copyable-with-owned-field.

### 4. generators_frame_zero_init_types.fire (WEAK + stale)
- Header says the test checks locals are zero-initialised in `__init` independent of their source initialiser, but every local (flag, big, v, i) has an explicit initialiser and is read only after assignment, so the zero-init is unobservable: the test would pass if _zero_value returned garbage. It only proves bool/float128/copyable-struct locals survive across yields.
- Header also says pointer-kind generator locals (string/array/class) crash with FLIRV-T1. That is no longer true: probe g2/g3.fire (string, int32[2], class locals in a generator) compile and print correctly. So the "intentionally avoids" rationale is stale and the test now omits the most valuable cases. Suggested: add string/array/class locals (g3.fire passes), and to observe zero-init, yield before a local's first assignment ... or just retitle as "mixed-type generator locals". Also update the stale header.

### 5. scoping_variable_declaration_order.fire (header/claim mismatch)
- Comment (and TEST_MANIFEST line 555) says "same variable name across different sibling scopes are separate variables", but the names are value2, value3, value4 -- all distinct, nothing is reused. docs/reference/scoping.md section 5 says reusing a name across sibling scopes is OK. Probe e.fire (`v` declared in a bare block, an if body and a for body) works and prints 1,2,3. Replace the distinct names with `v` so the test checks what it claims (also `before`/`after = before+1` half is trivial).

### 6. functions_many_params.fire (WEAK)
- All checks are commutative sums (a+b+c+d+e; p.x+p.y), so a swapped/misplaced stack argument (the exact class of bug a >4-arg ABI test must catch) still gives 15 / 17.5 / 40. Also only 5 params; no interleaved int/float mix (Win64 shares slots) and no 2nd struct. Probe m.fire with positional weights (a+10b+100c+...) over 7 int params, 7 mixed int/float32-64 params, and 2 struct params passes (7654321 each), so the stronger test is safe to adopt.

### 7. operator_precedence.fire (minor WEAK, comment errors)
- `10 % 3 + 1`: comment says wrong precedence would give 1; it gives 10%(3+1)=2, the same as correct (2): does not discriminate. `r7 = false && false || false` is false under any grouping: non-discriminating. The comment on `4 / 2 ** 2` ("not 1 (same here...)") is wrong: correct is 1, wrong grouping (4/2)**2 = 4, so it does discriminate. All other lines verified discriminating and EXPECT correct (14,4,8,2,18,1,2,3,9,tftt..: true,false,true,true,true,true,false,false,false,20,14,64). No unary-vs-`**` (`-2 ** 2`), `!` or `as` precedence cases; `**` associativity lives in operators_regression_power_assign.fire.

### 8. fall-off-the-end returns (soft INCORRECT)
- No doc specifies it (grep docs/reference: none). The three tests assert implicit zero for bool/int32/float64/float128. Probe h2.fire: the same shape with a `string` return ICEs (FIRV-T4), so behavior is inconsistent by type -- this is an accident of ast_to_fir._synthesize_zero, not a design. The header of functions_missing_return_fallthrough.fire itself says "no missing return diagnostic exists" and the repo has just added known_issues for other missing diagnostics. Correct long-term behavior is a missing-return diagnostic; these tests will then break. Consolidate into one explicitly-labelled "current behavior" test or move to known_issues with the expected diagnostic.
- Also stale: functions_return_types.fire says `char` cannot be a return type and is untestable. Probe h1.fire: `fn f(n) -> char { if (n>1) { return 'a'; } }` compiles; f(2)='a', f(0) prints a NUL char.

### 9. functions_explicit_owned_param.fire (WEAK)
- Duplicate of memory/memory_owned_function_param.fire; additionally asserts nothing about ownership (no use-after-move diagnostic, no drop observation). The doc rule ("owned params move into the function; argument invalid after the call") is what should be tested, in invalid/borrow.

## Compiler bugs discovered
1. Nested generator ICE (header of generators_advanced.fire; no known_issues test exists):
   ```
   fn inner() -> generator<int32> { yield 1; yield 2; }
   fn outer() -> generator<int32> { for (x: int32 in inner()) { yield x * 10; } }
   for (v: int32 in outer()) { println(v); }
   ```
   -> "FLIR verification failed (FLIRV-T5)" internal compiler error (reproduced, g1.fire). Should get a known_issues test.
2. Non-scalar fall-off-the-end return ICE: `fn s(n: int32) -> string { if (n > 1) { return "x"; } }` -> FIRV-T4 internal compiler error (h2.fire). Should be a clean missing-return diagnostic (no such known_issues file exists; return_missing_value.fire covers only bare `return;`).
3. Function reading a global is an ICE although docs say it works: docs/reference/scoping.md ("User-defined functions also have access to global variables", section 6 example) is marked [IMPLEMENTED], but
   ```
   g: int32 = 10;
   fn f() -> int32 { return g + 1; }
   println(f());
   ```
   -> "FIR verification failed (FIRV-L1)" internal error (d.fire). The scoping_function.fire header ("can't access outer scope variables in the current implementation") knows about the limitation but nothing tracks it; docs and compiler disagree and should not both stand. Needs either a clean diagnostic or implementation, plus a known_issues test.
4. Stray `]` / `)` tokens inside a scope are silently dropped with exit 0 (parser/statements.py:664-668; probes a.fire). Missing syntax diagnostic.
5. `&` in generic constraints is parsed into a "|"-joined list containing "&" (declarations.py:82-86), so it silently means union; and the constraint-check at type_system.py:842 exempts any constraint string equal to Numeric/Comparable/... from checking.
6. Copyable-class field rule (all fields Copyable) is not enforced (q.fire).
7. `%` is accepted on any same-type type parameter (type_system.py:625) even when the constraint allows floats (generic_function_same_type_param_modulo.fire's `Numeric = int32 | float32`), whereas the concrete-type path requires integers (docs: integer operands). Not exercised by a test; noted only.
8. (not a bug) docs/reference has no description of `fn main()` entry-point semantics or the "top-level ignored" warning that function_main_ignores_top_level.fire pins.

## Could not verify
- Snapshot (.fir/.flir) content correctness was not reviewed in depth (only existence and that FIR is not constant-folded for operator_precedence).
- float128 `as string` formatting ("0.000000"/"2.500000") assumed consistent with special_types tests (not independently derived).
- Whether any python test under tests/python independently covers the nested-generator or `&` constraint cases (grep for "generator"/"intersection" found only parser dead-guard tests, none asserting those behaviors).
