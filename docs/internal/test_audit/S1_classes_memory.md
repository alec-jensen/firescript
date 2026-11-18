<!-- Audit shard report, 2026-11-18. Raw audit output; see README.md for the consolidated plan. Verdicts are recommendations, not applied changes. -->
# S1 audit: tests/sources/{classes,memory,nullable,special_types}

Scope: 49 standalone tests (+2 helpers: classes_cross_module_helper.fire, classes_widget_helper.fire; both fine, used by their tests).
Verification: every test was compiled and run privately (wine, windows/x86_64); ALL 49 outputs match their EXPECT blocks exactly. Expected values were also derived by hand
(float128 values, truncation, nullable logic, ownership semantics). No EXPECT block is wrong. The problems are weakness / redundancy / misleading headers, plus 2 real compiler bugs
found while probing (section at the end).

Key structural facts that drive many verdicts (verified):
 (a) Runtime free is registry-based (firescript/std/internal/alloc.fire fs_rt_free): double-free, and free of string literals, are SILENTLY IGNORED. So "no double free" /
     "no leak" claims in headers cannot be observed through program output. Only use-after-free via block reuse/corruption, or the FIR/FLIR snapshots, can detect drop bugs.
 (b) Fixed-size array `.length()` is constant-folded to a literal in FIR (checked with --emit-fir on memory_branching), so printing it observes nothing about runtime state.
 (c) `msg: string = "iter"` is a string literal => drop is a no-op at runtime.

## DELETE-candidate
classes/classes_smoke.fire | TRIVIAL, REDUNDANT | Field-only class with empty EXPECT; nothing can fail that return_class_test.fire / every other class test (class without ctor, `Point(x,y)` implicit ctor) does not already exercise.
classes/type_method_call_constructor_form.fire | REDUNDANT | Same feature (`Type.Type(args)` constructor via TYPE_METHOD_CALL) as classes/classes_explicit_constructor_call.fire, which has the identical shape plus 2 fields; invalid side covered by invalid/classes/constructor_and_type_method_call_errors.fire.
classes/classes_nested.fire | REDUNDANT, (stale comment) | Strict subset of memory/memory_constructor_move.fire (same Point/Rect/`new`/width(), that one also prints all 4 coords + height). Also carries a stale LSP TODO comment unrelated to the test.
classes/classes_new_constructor_syntax.fire | REDUNDANT (moderate) | `new Foo(args)` is used by classes_methods, classes_field_access, receiver_mut, inheritance, etc.; error side in invalid/classes/new_constructor_syntax_errors.fire. Only unique bits are the `5i32` suffix and wrapping in `fn main`. (If kept, nothing lost either way.)
memory/copyable_local_drop.fire | TRIVIAL, INCORRECT(header) | Prints 7; header claims "ownership lowering inserts a Drop" yet its own earlier sentence says no DropInst is emitted (I confirmed via --emit-fir: no drop). Cites a stale lowering.py line number. Tests only that a copyable local in a function compiles. See detail.
memory/ownership_test.fire | REDUNDANT, TRIVIAL | Class move then read = memory_move_no_use_after_free.fire (stronger) + move_semantics_test.fire; `b: int32 = a` copy is trivially guaranteed.
memory/ownership_demo.fire | REDUNDANT | Composite: copyable copy == copyable_test; move == move_semantics_test/memory_move_no_use_after_free; borrow + owned param == borrow_test. No unique assertion; violates one-behavior-per-file.
special_types/float128_narrow_conversions.fire | REDUNDANT | Every conversion (int8/16/32 -> f128, f128 -> int8/16/32, f128 <-> float32) is in float128_narrow_casts.fire with more discriminating values (41.9 truncation, negative -1234).
special_types/float128_test.fire | TRIVIAL, REDUNDANT | `1.25+2.75` printed; identical to first line of float128_ops.fire. Cannot fail unless ops.fire fails too.

## MERGE-candidate / WEAK (keep intent, fix)
memory/memory_branching.fire | WEAK | prints constant-folded array lengths; asserts nothing about drops on if/else exits. Add `//@ snapshot: fir` (drops are visible there) or use heap-class payloads.
memory/memory_scopes.fire | WEAK, near-REDUNDANT | same shape as memory_branching/early_return (fixed array local, println length, scope exit); differs only in exit path (block).
memory/memory_early_return.fire | WEAK | same; `return` exit path. (These 3 could be one snapshot-backed file; keep one-per-file only if each gets a snapshot.)
memory/memory_break_continue_owned.fire | WEAK | Claims drops on break/continue are correct, but `msg` is a string literal (untracked by the runtime registry), so a missing, extra or double drop is unobservable. FIR does contain `drop msg` on both paths, so a `//@ snapshot: fir` would pin it. Use a heap owned object.
memory/memory_reassign.fire | WEAK | Header "old owned value must be dropped before rebinding" is unobservable (literals, int32 half is copyable and trivial). FIR shows drop-before-store; add snapshot or use heap strings.
memory/memory_owned_function_param.fire | WEAK | Explicit `owned` is the default for non-borrow params, so output is identical if the keyword were ignored (parse-only check). Also partly overlaps classes/classes_constructor_owned_borrowed_param.fire (owned keyword accepted on a param).
classes/classes_constructor_owned_borrowed_param.fire | WEAK | No header; name promises owned+borrowed but only an `owned a: int32` (copyable!) param and `&this` receiver; prints 7 either way. Parse-acceptance only.
classes/classes_method_nullable_param.fire | WEAK | Named "nullable param" but only ever passes a non-null literal; null/string?-variable arguments are never exercised, and those ICE (compiler bug #1). Missing null path of the concat too.
nullable/nullable_advanced.fire | WEAK, partly REDUNDANT | Both Config objects get non-null ports so the `return this.host` (null) branch never runs. The a/b/c counting and `val` reassign blocks duplicate nullable_basic.fire (cases c and a/b). Fix: construct one Config with `p: string? = null` variable (note: literal `null` into string? ctor param ICEs today, bug #1) and drop duplicated blocks.
classes/classes_nested_copyable_field.fire | WEAK | `copied = l.midpointStart()` returns `start` = (0,0): all-zero is indistinguishable from a failed/zero-filled struct load (method name is also misleading, returns start not a midpoint). Use non-zero start, e.g. Point(1,2).
classes/classes_array_field.fire | KEEP-with-note | Header claims destructor frees buffer / no leak: unobservable from output; covered only by its snapshot (4 drop/destroy lines). Fine because of the snapshot.
special_types/float128_ops.fire | WEAK | Everything printed with %f (6 digits) and uses values exactly representable / identical in float64; 1/3 -> 0.333333 etc. cannot distinguish binary128 from binary64. tests/python/float128 only self-checks the oracle (test_oracle_vectors replays the oracle against itself; test_lowering_float128 is FLIR-level), so NO end-to-end test validates 113-bit precision, rounding, inf/NaN/subnormals (docs/reference/type_system.md claims all). See detail.

## KEEP (necessary and correct)
classes/classes_cross_module_bare_construct_field_access.fire | KEEP | Regression, narrow, needs helper; header accurate.
classes/classes_cross_module_bare_static_method.fire | KEEP | Regression; EXPECT 10 correct (5*2).
classes/classes_deep.fire | KEEP | Only test with a `&other` borrowed param on a method + method returning new object; 4,6,11 verified. Name "deep" misleading.
classes/classes_explicit_constructor_call.fire | KEEP | (keeper of the Type.Type pair)
classes/classes_field_access.fire | KEEP | Only test of external field *assignment* on a simple class (`p.x = 7`); minimal but fine.
classes/classes_methods.fire | KEEP | snapshot fir/flir; instance method with ctor.
classes/classes_nullable_scalar_field.fire | KEEP | Correct and discriminating (null vs stored 0 vs value).
classes/classes_owned_this_constructor.fire | KEEP | Regression. Note: docs/reference/memory_management.md says consuming `this` receivers are [PLANNED]/unsupported while this pins `owned this` on a ctor and classes_constructor_... says `&this` ctor; docs/behaviour mismatch for the owner to decide.
classes/classes_regression_method_call_chain.fire | KEEP | Parser regression; values bb / 3 correct (match [1,3)).
classes/classes_static_methods.fire | KEEP | snapshot; NOTE pins undocumented behaviour: receiver-less `fn twice(x)` called as `m.twice(6)` (docs say instance methods always take a receiver) and zero-field `Math()`.
classes/classes_stray_semicolon_in_body.fire | KEEP | Parser regression.
classes/classes_zero_arg_constructor_bare_call.fire | KEEP | Regression; header accurate.
classes/inheritance.fire | KEEP | snapshot; first half (Person/Student) is subsumed by the 4-level chain except the `toString(this.age)` and field-shadow-free override; fine.
classes/return_class_test.fire | KEEP | Returning a named local (move-out, must not be dropped). Stale "what happens here?" comment. Class with no ctor/implicit field ctor.
memory/borrow_test.fire | KEEP | snapshot pins drops/borrow; only test of borrowed vs owned on a class fn param.
memory/copyable_test.fire | KEEP | Only focused copyable-class copy test; would fail (use-after-move) if `copyable` were ignored. 1.000000 correct for float32.
memory/memory_class_owned_fields.fire | KEEP | Value is its snapshot (destructor of string fields); output alone is weak.
memory/memory_constructor_move.fire | KEEP | Regression; premature drop of p1/p2 would corrupt freed Point (heap header overwrite), so it is observable.
memory/memory_early_exit_precision.fire | KEEP | Good: move on one return path must not poison the other path.
memory/memory_field_receiver_method_move.fire | KEEP | Regression (two root causes), correct.
memory/memory_implicit_receiver_borrow.fire | KEEP | Regression; use-after-free of Box would corrupt `label` (first field), so observable. Pins receiver-less instance method using `this` (undocumented, as above).
memory/memory_move_no_use_after_free.fire | KEEP | Strongest memory test: reuse-of-freed-block observable (111/222, 333/555 correct).
memory/move_semantics_test.fire | KEEP | snapshot; string move/borrow.
memory/receiver_mut.fire | KEEP | snapshot; I additionally verified the swap (`tmp = this.first` out of &mut this) with heap strings + a filler allocation: no corruption.
nullable/nullable_basic.fire | KEEP | 4 transitions, all correct.
nullable/nullable_scalar_local.fire | KEEP | 0-vs-null discrimination, correct.
nullable/nullable_scalar_return.fire | KEEP | Includes single-evaluation check (loggedZero printed once); correct.
special_types/float128_narrow_casts.fire | KEEP | Good values (41.9->41, negative, widening); all hand-verified.
classes/classes_widget_helper.fire, classes/classes_cross_module_helper.fire | helper | fine.

## Detailed evidence: INCORRECT / WEAK

### memory/copyable_local_drop.fire (INCORRECT header, TRIVIAL)
Header: "`p` is never used again; ownership lowering inserts a Drop for it at the end of the function's scope" directly contradicts the first half of the same comment ("no DropInst is ever emitted for `p`"). `--emit-fir` of the function shows only alloc/local/loadfield/binop/ret, no drop. The test is titled "regression coverage ... going out of scope" but there is no scope-exit action to cover; the claimed dead-code observation about lowering.py ~1648 is also stale (the is_copyable_class_str uses are now at lines 578/1276/1335/1787). Replace with either deletion, or fix the header to say "copyable class local in a function: no drop emitted, value usable", and consider `//@ snapshot: fir` so the absence of a drop is actually asserted.

### memory_branching / memory_scopes / memory_early_return (WEAK)
`println(b.length())` on a fixed-size array literal is folded to `const.int32 1` in FIR (verified L2 of memory_branching.fir). Output is a constant independent of runtime heap state; the only things tested are "compiles" and "does not crash". Registry-based free ignores double free. Suggested replacement: one test with `//@ snapshot: fir` covering block exit, if/else exit and early return together (drops appear in the dump), or a class whose fields are read after unrelated allocation to expose premature free.

### memory_break_continue_owned (WEAK)
FIR has `drop %msg` before both `jmp L1` (continue) and the break exit, so drop insertion works, but msg is `strconst` -> fs_rt_free ignores untracked pointers. Replace `msg` with heap data (e.g. `"it" + toString(i)` or a class instance) and add `//@ snapshot: fir`.

### memory_reassign (WEAK)
FIR: `drop s; storevar s` is correct, but both literals are untracked, so output "hello/world" would be identical with no drop. Use concatenated strings and snapshot.

### nullable_advanced (WEAK)
c1 and c2 are both constructed with non-null ports; the `this.port != null` false branch (returns bare host) is never executed. Correct expectation for a null-port Config is `localhost`. I could not write the obvious fix as-is: `new Config("localhost", null)` and `new Config("localhost", p)` (p: string? = null) both fail with FIRV-T5 (bug #1), which is probably why the test only uses literals.

### classes_method_nullable_param (WEAK)
Passes "World" only. Missing: null argument (ICE, bug #1) and what `prefix + " " + name` does when name is null.

### classes_nested_copyable_field (WEAK)
Whole-struct load via method: result (0,0) equals zero-initialised memory; the later `l.start = l.end` (4,8) is discriminating but the method-return path is not. Use non-zero values for `a`.

### float128_ops (WEAK) with replacement
Every assertion uses 6-digit %f output and exactly representable operands. A float128 implemented as float64 would pass. Verified the runtime is actually correct for these discriminating probes (outputs in parentheses), so they can be added as comparisons (not printing):
  1.0f128 + 1.0e-30f128 > 1.0f128  (true;  float64 gives false)
  1.0f128 + 1.0e-33f128 > 1.0f128  (true)
  1.0f128 + 1.0e-35f128 > 1.0f128  (false: below half-ulp, round-to-nearest-even)
  (1.0f128 + 1.0e-34f128) - 1.0f128 == 0.0f128  (false: rounds up to 1+ulp)
  zero/zero: nan == nan false, nan != nan true; 1/0 > 1.0e4000f128 true; -zero == zero true
  7.5f128 as int64 = 7, -7.5f128 as int64 = -7 (truncation toward zero)
These are documented guarantees (type_system.md: correctly rounded, subnormals, signed zero, inf, NaN) with no end-to-end test.

## Compiler bugs discovered (verified with the current main)

Bug 1: `string?` parameters (plain functions and ctors/methods) reject `null` and any `string?`-typed value with an internal compiler error. Passing a non-null literal works (that is all the existing tests do). `int32?` parameters work fine (verified), so it is specific to pointer-shaped nullables; the parameter signature keeps `string` instead of `string?` at the FIR verifier.
  Repro A (minimal):
    import @firescript/std.io.println;
    fn f(s: string?) -> void { println("in f"); }
    f(null);
  -> "FIR verification failed (FIRV-T5): Call argument 0 ('s') has type 'string?', expected 'string'"
  Repro B: `x: string? = "b"; f(x);` -> same FIRV-T5.
  Repro C: `class Config{host:string; port:string?; fn Config(&mut this, host:string, port:string?){...}}  p: string? = null; new Config("h", p);` -> FIRV-T5 ('port'); and a method `greet(&this, name: string?)` called with null -> FIRV-T6.
  Docs changelog line 58-59 describe fixing this only for nullable *scalars*.

Bug 2: function declared `-> string?` that returns a string literal fails FIR verification.
  Repro:
    fn f(b: bool) -> string? { if (b) { return "yes"; } return null; }
    x: string? = f(true);
  -> "FIRV-T4 in f/...: Return value type 'string' does not match declared return type 'string?'"
  (class-typed nullable locals `q: P? = null; q = P(3);` work fine.)

Neither has a test in tests/sources (not under known_issues either); nullable/ has no string?/class? param or return coverage. Per CLAUDE.md these belong in tests/sources/known_issues/ with header comments.

Minor doc/behaviour mismatches pinned by tests (owner decision, not bugs per se): receiver-less instance methods using `this` (classes_static_methods `twice`, memory_implicit_receiver_borrow `describe`), `owned this` ctor receiver (classes_owned_this_constructor) vs memory_management.md saying consuming `this` is PLANNED, ctor with `&this` receiver (classes_constructor_owned_borrowed_param) vs docs saying ctors take `&mut this`.

Not verified: that memory_constructor_move / memory_implicit_receiver_borrow would fail on a revert of their fixes (relied on reasoning about Windows heap corruption of freed blocks rather than re-introducing the bugs; I may not modify the repo); the "no other test covers X" claims are based on grep of tests/sources and tests/python filenames/contents, not exhaustive semantic analysis.
