<!-- Audit shard report, 2026-11-18. Raw audit output; see README.md for the consolidated plan. Verdicts are recommendations, not applied changes. -->
# S7 audit: tests/sources/invalid/{classes,borrow,generics}  (72 files, no helpers)

Method: read every file; ran the real compiler (--check --message-format json) on each; wrote /scratchpad/audit/cmp.py to confirm
annotations == actual diagnostics (all 72 currently pass, so no stale columns); wrote ~30 scratch programs in
/tmp/.../scratchpad/audit/t/ (a1..f4) to separate primary errors from cascades and probe for missed diagnostics.
Parser facts used as redundancy evidence: firescript/parser/declarations.py lines 140/188/194 (receiver/param parsing shared by methods AND
constructors), 1069 (static ctor), 1086 (')' after params), 1109 ('{' body); expressions.py:247 (single site for "'(' after constructor type").

IMPORTANT STRUCTURAL FACTS
* Any parse error stops the pipeline before semantic analysis. So every file that mixes a parse error with semantic mistakes silently
  hides the semantic ones (see class_errors, generics_errors).
* Many tests annotate CASCADE diagnostics (e.g. "Variable 'this' not defined", "Function 'Pair' is not defined", "Variable 'identity' not
  defined" where the name IS defined). These lock incidental error-recovery behaviour into the test; any parser-recovery improvement breaks them.

====================================================================================================
## DELETE-candidate (REDUNDANT / INCORRECT-and-redundant)
classes/constructor_amp_not_this.fire | REDUNDANT | same as class_constructor_syntax_errors CR1 (l.14) and constructor_param_syntax_errors R1 (l.12); one shared parser branch (declarations.py:188)
classes/constructor_param_array_unsupported.fire | REDUNDANT | same as constructor_param_syntax_errors P2 (l.51), class_constructor_syntax_errors CP2, class_def_syntax_errors P2; one branch (declarations.py:194)
classes/constructor_param_bad_type.fire | REDUNDANT | same "Expected type" as constructor_param_syntax_errors P1 (l.42), class_constructor_syntax_errors CP1, class_def_syntax_errors P1
classes/class_constructor_syntax_errors.fire | REDUNDANT | every case (R1,R2,bad type,array,missing name,missing ')',missing '{') is repeated in constructor_param_syntax_errors (same lines 188/194/1086/1109) and class_def_syntax_errors; 13 annotations, 6 are cascade "this not defined"
classes/constructor_static_with_receiver.fire | INCORRECT + REDUNDANT | header/name say "static constructor with &this -> two parse errors" but file has NON-static `fn Foo(&this)` and expects FS-SEM-0001 read-only-receiver mutation; that rule is already tested by receiver_readonly_mutation_errors; the real double error is constructor_param_syntax_errors R3 (l.32)
classes/super_call_no_base.fire | REDUNDANT | super_call_errors.fire l.16
classes/super_call_base_no_ctor.fire | REDUNDANT | super_call_errors.fire l.30
classes/super_call_arg_count.fire | REDUNDANT | super_call_errors.fire l.47
classes/super_call_arg_type.fire | REDUNDANT | super_call_errors.fire l.56
classes/static_and_type_method_errors.fire | REDUNDANT | all 4 cases covered: static-on-instance=class_static_method_errors l.16; unknown Type.m=constructor_and_type_method_call_errors l.35; static count/type = class_static_method_errors l.20/23 and constructor_and_type_method_call_errors l.41/44
classes/type_method_call_arg_count.fire | REDUNDANT | class_static_method_errors l.20, constructor_and_type_method_call_errors l.41
classes/type_method_call_arg_type.fire | REDUNDANT | class_static_method_errors l.23, constructor_and_type_method_call_errors l.44
classes/type_method_call_unknown.fire | REDUNDANT | constructor_and_type_method_call_errors l.35
classes/constructor_call_arg_count.fire | REDUNDANT | `new` count: constructor_call_arg_errors l.27, class_new_constructor_errors l.13, constructor_and_type_method_call_errors l.29
classes/constructor_call_arg_type.fire | REDUNDANT | `new` type: constructor_call_arg_errors l.28, class_new_constructor_errors l.16, constructor_and_type_method_call_errors l.32
classes/constructor_arg_type_mismatch_errors.fire | REDUNDANT | bare-call arg type: constructor_call_arg_errors l.22 (only difference is arg position 2 vs 1)
classes/constructor_call_no_ctor.fire | REDUNDANT | constructor_call_arg_errors l.29, constructor_and_type_method_call_errors l.26
classes/field_access_type_errors.fire | REDUNDANT | identical two cases (unknown field, field on int32) as field_access_errors l.12/15
classes/field_access_unknown_field.fire | REDUNDANT | field_access_errors l.12
classes/method_duplicate_param_shadow.fire | REDUNDANT | class_method_duplicate_param.fire (same rule, same construct); function form is scoping/scope_errors.fire l.29
classes/instance_method_arg_count.fire | REDUNDANT | instance_method_arg_errors l.16 (only diff: statement vs initializer context; no separate parser path for that in a semantic error)
classes/instance_method_arg_type.fire | REDUNDANT | instance_method_arg_errors l.22
classes/instance_method_unknown.fire | REDUNDANT | unknown_instance_method.fire (same diagnostic "Methods not supported for type X")
classes/implicit_var_method_call_on_untyped.fire | REDUNDANT + WEAK | all 3 diagnostics are bare-assignment-to-undeclared-name + its cascade; identical to scoping/bare_assignment_without_declaration_errors.fire l.23-25 (`n = w.getV();`)
classes/new_unknown_type.fire | REDUNDANT | `new Unknown(..)` (PARSE-0012 + SEM-0010 same col) = class_new_constructor_errors l.19-20 = new_constructor_syntax_errors l.14-15; extra PARSE-0003 is the bare-assignment cascade
classes/new_missing_paren.fire | REDUNDANT | same parser site (expressions.py:247) as new_constructor_syntax_errors l.18
generics/generic_class_field_access_unknown.fire | INCORRECT + REDUNDANT | l.18 `new Box<int32>(5)` annotated "No constructor defined" but Box DOES define one: this locks in a compiler bug (scratch a2/b2/b3: valid program rejected; `Box<int32>(5)` form passes, b1). Rule on l.13 is duplicated by generic_class_template_field_errors l.15 and generic_class_unknown_field l.11
generics/generic_class_unknown_field.fire | REDUNDANT | generic_class_template_field_errors.fire (same rule; that file uses a proper `&this` receiver, this one has `fn bad()` with no receiver)
generics/generic_constraint_violation_errors.fire | REDUNDANT | same rule/same message as generic_call_constraint_violation l.9 (one of the two; the latter adds a cascade, the former is cleaner -> keep this one, drop the other or drop its cascade)
borrow/memory_errors.fire | REDUNDANT + TRIVIAL | case 1 (use after move l.9) = constructor_move_errors/method_move_errors; case 2 (return borrowed string l.12) is unique only in using a plain string (borrow_escape_projection uses field/array) -> move into borrow_escape_projection_errors; rest of file is 20 lines of commented-out TODO prose and an unannotated `small[10]` that the comment itself says is not an error

## MERGE-candidate
classes/class_def_syntax_errors.fire | WEAK/MERGE | keep header cases (class name, G1<>, G2<T, from-missing, self-inherit, missing '{', bad member, static ctor); cases R1,R2,P1,P2,P3 are duplicates of constructor_param_syntax_errors (shared param parser); 8 of 18 annotations are cascade "Expected '=' in variable declaration" on the field line after a failed class header
classes/constructor_param_syntax_errors.fire | KEEP (canonical) | the single file that should hold the shared param/ctor-syntax cases; 7 of 16 annotations are cascade "this not defined" -> consider dropping the `this.v = 1;` bodies or accepting the cascade
classes/class_static_method_errors.fire | KEEP (canonical) | static/instance call-form errors; only file demanding "static method called on instance" besides the redundant one above
classes/constructor_and_type_method_call_errors.fire | KEEP (canonical) | superset of ctor/type-call cases
classes/constructor_call_arg_errors.fire | KEEP (canonical) | only file covering BARE `Foo(1,2)` count/type, plus `new`
classes/super_call_errors.fire | KEEP (canonical)
classes/field_access_errors.fire | KEEP (canonical)
generics/generic_class_type_arg_errors.fire, generic_class_nested_type_arg_errors.fire, generic_class_unclosed_type_args.fire | WEAK + MERGE | each is one "Expected type argument"/"Expected '>'" parse error + a misleading cascade PARSE-0012 "Function 'Pair' is not defined" (Pair(1,2) is valid: a5). Same message as generic_declaration_errors l.16/20 (type-arg list in declaration). Merge into one file; drop the cascade annotations if harness allows
generics/generic_func_empty_type_args.fire + generics/new_constructor_empty_type_args.fire | KEEP-both-ish/MERGE | distinct parse paths (call vs `new`), but the first demands cascade PARSE-0003 "identity not defined" (identity IS defined) and the second demands a cascade "Expected initializer expression"
generics/generic_call_errors.fire | WEAK | 4 cases; 4 of 10 annotations are the misleading cascade "Variable 'Box'/'identity' not defined"

## FIX-EXPECTATION (INCORRECT / WEAK)
classes/class_errors.fire | INCORRECT | see detail D1; only 10 annotations, nearly all cascades; never tests the stated rules
generics/generics_errors.fire | INCORRECT + WEAK | see detail D2
generics/generic_class_nested_unclosed_type_args.fire | INCORRECT | see D3
generics/nested_generic_missing_close_errors.fire | INCORRECT | see D3
generics/generic_declaration_errors.fire | INCORRECT (l.24,28) | see D3 (l.16,20 are fine)
classes/constructor_static_with_receiver.fire | INCORRECT | see above
generics/generic_class_field_access_unknown.fire | INCORRECT | l.18 locks a compiler bug (D4)
generics/generic_call_constraint_violation.fire | WEAK | l.9 second annotation FS-SEM-0002 @5 is only the downstream consequence (declared int32 vs result string); first error is the real one; also `identity<string>(5)` argument mismatch is NOT reported (compiler bug B3)
generics/generic_function_inference_errors.fire | WEAK | l.16 SEM-0002 "Expected int32, got T" is a cascade of the inference failure; also function body `return x` (int32) in `make<T>() -> T` is a type error that is not reported (return-type check missing, cf. known_issues/return_type_mismatch)
generics/generic_def_syntax_errors.fire | WEAK | 15 annotations = 4 cases x (1 primary + 2 recovery cascades) + 4x `return x` "x not defined" cascades; only 4 real rules; case 4 (`-> Q`, undefined return type) is labelled "not a declared type parameter" but the compiler reports parse errors "Expected type" and cascades, i.e. no semantic undefined-type diagnostic
classes/type_member_access_errors.fire | WEAK | l.24-25: `c: int32 = f.;` -> second error SEM-0002 "Expected int32, got Foo" is a pure cascade (f. parsed as f); l.15/19 pair each annotate a cascade "Expected initializer expression"
classes/type_method_call_constructor_form.fire | WEAK/TRIVIAL | relies on undocumented `Widget.Widget(5)` call form (docs only show `new W(..)` and `W(..)`); asserted error is a plain declared-type mismatch (SEM-0002), not a class rule
borrow/loop_move_errors.fire, borrow/for_in_move_errors.fire | WEAK | see D5: only the post-loop use is demanded; the actual per-iteration use-after-move (consume(a) inside the body) is not diagnosed and not demanded
borrow/branch_move_errors.fire | KEEP (message "may have been moved on another control-flow path" is right for if-without-else)

## KEEP
borrow/borrow_alias_escape_errors.fire | KEEP | moving a borrowed field projection into owned local / owned param (memory_management.md "borrow cannot be retained"); distinct from borrow_move_errors (plain param)
borrow/borrow_escape_projection_errors.fire | KEEP | returning b.name / borrowed array; correct SEM-0001 and columns
borrow/borrow_move_errors.fire | KEEP | borrowed string -> owned binding / owned param
borrow/constructor_borrow_move_errors.fire | KEEP | borrowed value into ctor param, bare and `new` forms
borrow/constructor_move_errors.fire | KEEP | owned moved into ctor (bare and `new`), later use
borrow/method_move_errors.fire | KEEP | owned moved into method param (the &-param negative control on l.24-25 is a good valid-side check)
classes/receiver_readonly_mutation_errors.fire | KEEP | &this mutation; correct. Missing: calling a &mut method via &this (see missing coverage)
classes/class_method_duplicate_param.fire | KEEP | canonical method duplicate-param
classes/class_method_syntax_errors.fire | KEEP | field missing type; `static fn get(&this)` (only static-METHOD receiver test)
classes/class_new_constructor_errors.fire | KEEP | new: count/type/unknown type
classes/field_access_missing_identifier.fire | KEEP | `h.;` (two annotations on same col are two real separate diagnostics from different layers; mild cascade)
classes/new_constructor_syntax_errors.fire | KEEP (WEAK) | l.14 case duplicates unknown-type tests; l.18 generic missing '(' and l.22 `new Pair<5,int32>` are the useful ones; each has a duplicated "Expected initializer expression" cascade
classes/unknown_instance_method.fire | KEEP | canonical unknown method
classes/instance_method_arg_errors.fire | KEEP | canonical instance-method count/type
generics/constraint_decl_errors.fire | KEEP | 4 distinct constraint-declaration parse errors, no cascades, columns right
generics/generic_class_template_field_errors.fire | KEEP | canonical unknown field in generic template (uses &this); l.19 valid instantiation is a good negative control
generics/generic_call_constraint_violation.fire or generic_constraint_violation_errors.fire | KEEP ONE | see above
generics/generic_function_inference_errors.fire | KEEP (WEAK) | cannot-infer + inferred-type-violates-constraint (l.22) are unique

====================================================================================================
## DETAILED EVIDENCE (INCORRECT / WEAK)

D1  classes/class_errors.fire  (INCORRECT)
 Intended: undefined class, unknown field, field type mismatch, unknown method, duplicate class, duplicate field, class name used as variable,
 uninitialized instance. Actual annotated diagnostics (10):
 - l.5 `UndefinedClass obj;` : old C-style declaration syntax; the two PARSE-0010 "Expected assignment, function call..." are not an undefined-class error.
 - l.16/22/28/63 `p: Point;` : declaration without initializer -> PARSE-0010 "Expected '=' in variable declaration" (variables.md: declarations without initializer unsupported). The intended field/method errors are never reached.
 - l.17/23/29 PARSE-0003 "Variable 'p' not defined": pure cascade of the failed declaration.
 - l.64 PARSE-0012 "Function 'println' is not defined": println is not imported (incidental), not the intended `obj.required` problem.
 - l.38-44 duplicate class, l.47-50 duplicate field, l.54 `Point: int32 = 5` : NO diagnostic, because parse errors suppress semantic analysis. In isolation (scratch a4) the compiler ALSO reports nothing for them (compiler bug B1).
 Fix: delete the file (every legitimate rule is covered elsewhere: unknown field = field_access_errors, unknown method = unknown_instance_method) and add real tests for duplicate class/field once B1 is fixed (known_issues).

D2  generics/generics_errors.fire  (INCORRECT + WEAK; 6 annotations)
 - l.5 `T x;`: old syntax; PARSE-0010 x2 are not "undefined type parameter".
 - l.15 `x: int32 = identity<string>(42)`: comment says "expects string but got int" (argument mismatch). The compiler does NOT check the argument (scratch c4/c8: `identity<string>(42)` and `identity<int32>("s")` compile clean). The annotated SEM-0002 comes only from declared-type int32 vs result string. Test passes for the wrong reason and would keep passing if the arg check were never written.
 - l.19-24 `add<T: Numeric>` with undefined constraint `Numeric`, then `add<string>(..)`: unannotated, NO diagnostic even in isolation (c5): undefined constraint and violating call both silently accepted (compiler bug B4).
 - l.29 `identity(5);` valid program, comment "May require explicit type parameter" is wrong.
 - l.34 `identity<int32,string>(5)` SEM-0010 type-arg count: the only correct, unique case (no other file tests generic function type-arg count). Move it to its own file.
 - l.43-44 `box: Box<int32>;` no initializer -> PARSE-0010; l.44 PARSE-0003 "box not defined" is a cascade; intended "generic class field type mismatch" untested (and `b.value = "s"` is undetected anyway, B2).

D3  Malformed nested/unclosed type-argument tests using obsolete name-first syntax (INCORRECT)
 generic_class_nested_unclosed_type_args.l.14 `Pair<p: Pair<int32,int32 int32> = Pair(...)`, nested_generic_missing_close_errors.l.14 `Pair<Pair<int32, int32, p: string;`, generic_declaration_errors.l.24/28 `Pair<c: Pair<...> = good;`
 These are leftovers from an older `Pair<..> name` declaration order. Under current `name: Type` syntax the line is parsed as an expression statement starting with `Pair <`, so the first annotation is PARSE-0010 "Expected assignment, function call, or method call" @col 1/5 (statement dispatch), not "missing '>'". generic_declaration_errors l.24/28 additionally yield FS-SEM-0002 "Expected Pair<int32,int32,int32>, got Pair<int32,int32>" / "Expected int32, got Pair<int32,int32>" which are nonsense type-mismatch cascades.
 The properly-formed variants work and give a sane primary error (scratch c1: `p: Pair<Pair<int32,int32, int32> = Pair(Pair(1,2),3);` -> PARSE-0010 "Expected '>' to close generic type arguments" @35 + cascade PARSE-0012; c2 likewise). Rewrite these three files with the current syntax (and then they collapse into generic_class_unclosed_type_args).

D4  generics/generic_class_field_access_unknown.fire l.18  (INCORRECT: locks compiler bug)
 `b: Box<int32> = new Box<int32>(5);` with `fn Box(value: T)` defined is rejected: "No constructor defined for type 'Box<int32>'" (also for `copyable class`, and with `&mut this`: b2,b3). Same program with `Box<int32>(5)` compiles (b1). `new Generic<T>(...)` is undocumented/untested anywhere valid (grep docs/examples/tests: no hit), so the rejection is a bug or an unimplemented form, not an intentional rule. The test demands it.

D5  borrow/loop_move_errors.fire, for_in_move_errors.fire  (WEAK)
 `while(..){ consume(a); }` with a declared outside the loop: the second iteration uses the moved value, yet the compiler reports nothing at the call site (scratch a1: while loop, no later use -> zero diagnostics). The tests only demand the use AFTER the loop ("may have been moved on another control-flow path"). Either (a) the in-loop move should be an error and the tests are missing it, or (b) it is intentionally allowed; docs/reference/memory_management.md l.136 only says "Values used across iterations drop after loop", so the intent is unspecified. At minimum a spec decision + test is needed. Same for for-in (for_in_move_errors l.13).

D6  Cascade-locked annotations (WEAK, systemic)
 FS-PARSE-0003 "Variable 'this' not defined" after a failed method/ctor parameter list: class_constructor_syntax_errors (6), constructor_param_syntax_errors (7), class_def_syntax_errors (1), constructor_amp_not_this, constructor_param_array_unsupported (2), constructor_param_bad_type (2).
 FS-PARSE-0012 "Function 'Pair' is not defined" etc. after a failed generic declaration: generic_class_type_arg_errors, generic_class_nested_type_arg_errors, generic_class_unclosed_type_args, generic_class_nested_unclosed_type_args.
 FS-PARSE-0003 "Variable 'identity'/'Box' not defined" where the name IS defined: generic_call_errors (4), generic_func_empty_type_args (1).
 FS-PARSE-0003 "Variable 'x' not defined" for params after a failed fn header: generic_def_syntax_errors (4).
 FS-PARSE-0010 "Expected initializer expression" duplicates: new_missing_paren, new_constructor_syntax_errors, new_constructor_empty_type_args, type_member_access_errors.
 Duplicate diagnostics for one fault: unknown `new` type reports PARSE-0012 AND SEM-0010 at the same column (class_new_constructor_errors l.19-20, new_constructor_syntax_errors l.14-15, new_unknown_type l.5-7).

====================================================================================================
## MISSING COVERAGE (no test in slice; most would currently fail because of the bugs below)
Classes: duplicate class definition; duplicate field; class name reused as variable; unknown base class (`class C from Missing`); cyclic inheritance (A from B, B from A; only self-inheritance is tested); constructor of derived class not calling this.super when base needs args; `this.super(...)` outside a constructor (comment in super_call_errors says it yields "Methods not supported", untested); unknown field via `this.` in a NON-generic class; field assignment type mismatch (`p.x = "s"`, `this.x = "s"`); returning a field of the wrong type; unknown declared type `x: Nope = ...` produces misleading "Expected type"+"Variable 'Nope' not defined" (untested); calling a `&mut this` method through a `&this` receiver; unknown static/field access on a type (`Foo.field`); instantiating abstract/private? (n/a).
Borrow/ownership: assigning to / mutating through a borrowed `&param` (`s = "x"`, `w.text = "z"`, `c.inc()` where inc is &mut this); storing a borrowed param into a field (`this.text = text` with `&text`); borrowing a Copyable (`fn f(&x: int32)` -> SEM-0001 "Cannot borrow Copyable"; only covered by tests/python/semantic/test_semantic_analyzer_internals.py:179, no .fire test); passing a Copyable where &T required; use-after-move inside the same loop iteration chain (D5); move in one branch of if/else then use in other branch (valid) and join; moving a class field out of a borrowed/owned object (partial move); use-after-move via method call receiver; double move `consume(a); consume(a);` straight-line (only appears incidentally in d5 scratch: works, not tested in this dir -- check tests/sources/invalid elsewhere); re-initialisation after move (`x = "again"` after move currently errors, spec silent).
Generics: wrong number of type args on a generic CLASS (`Box<int32,int32>` -> no error, B5); wrong argument type for explicit/inferred generic call (B3); conflicting inference (`same(1,"a")` reports odd "Could not infer" + SEM-0002 "got T"); undefined constraint name (B4); constraint violation on a generic CLASS type arg; unknown generic class/type name in type-arg list; type-param shadowing / duplicate type param names (`fn f<T,T>`).

====================================================================================================
## COMPILER BUGS / ODDITIES DISCOVERED (minimal repros; scratch files in .../scratchpad/audit/t/)
B1  Duplicate class / duplicate field / class name shadowed by variable produce no diagnostic (a4):
      class A { x: int32; }  class A { y: int32; }   class B { x: int32; x: int32; }   fn f()->void{ A: int32 = 5; }
    (the second A silently wins: `A()` later reports "expected 1 args, got 0" referencing the wrong class)
B2  Field assignment/return type mismatch not detected (d1/d2):
      p: Point = Point(1,2); p.x = "string";   // no error     fn get(&this)->string{ return this.x; } // x:int32, no error
B3  Explicit/inferred generic call argument type not checked (c4, c8):
      fn identity<T>(v:T)->T{return v;}  x: string = identity<string>(42);  a: int32 = identity<int32>("s");   // no error
B4  Undefined constraint name accepted; violation not reported (c5): fn add<T: Numeric>(a:T,b:T)->T{return a+b;}  add<string>("a","b");
B5  Wrong number of type args on generic class accepted (f3): a: Box<int32,int32> = Box<int32,int32>(1);   // no error
B6  `new GenericClass<int32>(5)` rejected with "No constructor defined for type 'Box<int32>'" although constructor exists; `Box<int32>(5)` accepted (b1/b2/b3). Valid program rejected or undocumented form (see D4).
B7  Borrow checker holes (e1,e4,f1,d4): storing `&text` param into `this.text`; assigning/mutating through `&w` param (`w.text = "z"`); calling `&mut this` method (`c.inc()`) on a `&c` param; `s = "x"` on `&s: string` -- all accepted although memory_management.md l.59/78 say borrows are read-only and non-retainable.
B8  Move inside loop body not diagnosed (a1/D5).
B9  Unknown base class `class C from Missing` and cyclic inheritance accepted (e6).
B10 Misleading cascade diagnostics: after a failed generic call/decl the compiler says "Variable 'identity'/'Box'/'Pair' not defined" or "Function 'Pair' is not defined" for names that ARE defined; after failed params `this` "not defined".
B11 `class NoCtor{x:int32;}`: `NoCtor()` is accepted (implicit field constructor, "expected 1 args") but `new NoCtor(5)` -> "No constructor defined" (a6; class_static_method_errors.l.15 relies on `Tool()` with no ctor being legal). classes.md documents neither implicit constructors nor this asymmetry.
B12 Methods without a receiver (`fn add(a:int32)` using `this.value`) and receiver-less constructors compile and are treated as instance methods; classes.md says receivers are required and static needs `static fn`. A large part of the slice (instance_method_*, super_call_*, constructor_call_*, field_access_*) is written in this receiver-less style, i.e. relies on undocumented behaviour. (`static fn` + `this` does error: b6.)
B13 Re-assigning a moved owned variable (`x = "again"` after `consume(x)`) is reported as use-after-move at the assignment (f4); spec silent.
B14 Unknown declared type reports PARSE-0010 "Expected type" + PARSE-0003 "Variable 'Undefined' not defined" (c7) rather than an undefined-type diagnostic.

NOT VERIFIED: whether B7/B8/B13 are intentional design (docs are ambiguous; memory_management.md marks borrow rules IMPLEMENTED); whether instance-method statement vs initializer contexts take different semantic paths (instance_method_arg_count/type/unknown marked redundant on message equality only); error CODE choice (PARSE-0012 for "Array parameters not supported", SEM-0010 for nearly everything) was not judged against a spec because errors.py has no per-code docs.
