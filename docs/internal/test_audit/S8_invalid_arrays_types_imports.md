<!-- Audit shard report, 2026-11-18. Raw audit output; see README.md for the consolidated plan. Verdicts are recommendations, not applied changes. -->
# S8 audit: tests/sources/invalid/{arrays,types,imports,match,control_flow}

Method: every file read, compiled with `main.py --platform windows --arch x86_64 --check --message-format json`;
all 174 non-known_issues invalid tests were also compiled and their diagnostics grouped by (code, normalized message)
to find cross-file duplicates. Un-annotated lines were additionally probed in isolation (check mode AND a full compile
to a scratch dir) to see which "claimed" errors are really produced. Scratch repros live in
`/tmp/claude-1000/-home-alec-Programming-firescript/2f6fea08-4b29-4fbd-9b67-4bb973797cf6/scratchpad/audit/s8/`.
61 standalone tests + 2 helpers (imports/import_cycle_b_provider.fire, imports/visibility_provider.fire).

Legend: path | verdict(s) | reason.  "dup-of X" means X emits the same code+message for the same rule.

## DELETE-candidates (fully redundant, or pinning something wrong with no unique value)

arrays/array_access_and_method_errors.fire | REDUNDANT | all 3 cases dup: line5 (index non-array) = arrays/array_errors.fire:56, types/type_mismatches.fire:33, types/type_errors_comprehensive.fire:38; line11 (undefined index) = arrays/array_access_undefined_index_errors.fire:6; line17 (length(1)) = arrays/array_length_arg_count.fire:5, array_method_call_errors.fire:15
arrays/array_access_undefined_index.fire | REDUNDANT | identical case to array_access_undefined_index_errors.fire (undefined var as index, exactly one FS-PARSE-0003); only differs by being inside a fn
arrays/array_literal_undefined_element.fire | REDUNDANT | same as array_literal_undefined_element_errors.fire and array_literal_unresolvable_element.fire (undefined 1st element, exactly one FS-PARSE-0003). Three files, one behavior; keep one
arrays/array_literal_unresolvable_element.fire | REDUNDANT | see above
arrays/array_length_arg_count.fire | REDUNDANT | `arr.length(1)` is array_method_call_errors.fire:15 (also :27 for string)
control_flow/assignment_target_errors.fire | REDUNDANT | `x = ;` identical to statement_form_errors.fire:33 (same 2 diagnostics, same columns)
control_flow/assignment_undefined_chain.fire | REDUNDANT | `x = y;` with both undefined is the same as expressions/implicit_assign_undefined_rhs.fire (same two FS-PARSE-0003 @9,@5)
control_flow/for_c_style_missing_semicolon.fire | REDUNDANT + WEAK | "Expected ';' after for loop condition" also at syntax/statement_dispatch_errors.fire:26; second annotation (`Variable 'i' not defined` @31) is a cascade, see detail
imports/stdlib_import_path_errors.fire | REDUNDANT | line4 `import @firescript/std.` = imports/import_trailing_dot_eof.fire:8 (and its comment "very end of file" is false: more lines follow); line8 iteration-guard case = import_syntax_errors.fire:28
match/match_missing_scrutinee.fire | REDUNDANT | match_syntax_errors.fire:10 produces the same 3 diagnostics (+1 cascade)
match/match_pattern_bad_binding.fire | REDUNDANT | match_syntax_errors.fire:71 emits the identical 3 FS-PARSE-0010 @ the same token
match/match_pattern_missing_variant.fire | REDUNDANT | match_syntax_errors.fire:47 (`Shape. -> 1`)
   (the three match singles vs match_syntax_errors are mutual duplicates: delete either the 3 singles or those 3 cases from the big file; singles are the more robust side)
types/semantic_unary_not_non_bool.fire | REDUNDANT | exactly unary_operator_type_errors.fire:4 (also operators/logical_and_increment_errors.fire:5)
types/semantic_unary_minus_undefined.fire | REDUNDANT | = unary_operator_type_errors.fire:9
types/semantic_unary_incdec_undefined.fire | REDUNDANT | = unary_operator_type_errors.fire:14
types/semantic_equality_mismatch.fire | REDUNDANT | `int32 == string` = binary_operator_type_errors.fire:25 (same message)
types/semantic_logical_non_bool.fire | REDUNDANT | `&&` on non-bool = binary_operator_type_errors.fire:12 (same rule, same message shape)
types/cast_array_to_non_string.fire | REDUNDANT | `arr as int32` = cast_and_generic_type_errors.fire:16 (`arr as float64`), same message
types/field_access_on_primitive.fire | REDUNDANT | = classes/field_access_errors.fire:15, classes/field_access_type_errors.fire:19 (same message)
imports/import_cycle_a.fire (+ helper import_cycle_b_provider.fire) | INCORRECT | pins a wrong diagnostic; see detail (cycle detection is dead code; the test cannot be "fixed" by relabeling)

## FIX-EXPECTATION (INCORRECT / WEAK: keep the file but change it)

types/semantic_modulo_mismatch.fire | INCORRECT | line 5 `b: int64 = 6;` is VALID per docs/reference/type_system.md:102-111 yet is annotated as FS-SEM-0002; the intended error is only line 6. Use `6i64`. (Compiler bug, see below)
types/type_errors_comprehensive.fire | INCORRECT (header) + WEAK + REDUNDANT | header claims function-call, array-literal, array-element, return, call-arity errors; 9 of ~17 error lines are demanded, the rest silently unchecked; see detail
types/type_mismatches.fire | INCORRECT | 19 of 33 annotations are incidental `Function 'print' is not defined` (file never imports println); the "use before declaration" and array-method cases do not test what their labels say; see detail
types/cast_and_generic_type_errors.fire | INCORRECT (line 39) + WEAK (line 35) | `print(1, 2);` annotated as "Builtin arity error" but the diagnostic is `print` not defined; `pick(1,"two")` pins a cascade (`Expected int32, got T`)
arrays/array_edge_invalid.fire | INCORRECT | 5 of 9 annotations are `print` not defined (no import); its own comments ("EXPECT: errors about arrays", "remove not implemented") are stale; line 16 nested-array and line 8 are dups
arrays/array_errors.fire | INCORRECT (comments) + WEAK | only 6 of the ~12 commented error scenarios are demanded; the other 5 are silently accepted by --check; see detail
control_flow/control_flow_invalid.fire | INCORRECT | 5 of 11 annotations are `print` not defined; break/continue cases pin a bogus parse error (`Expected semicolon after statement` on `break;` at top level)
imports/import_errors.fire | INCORRECT | every case is a JS-style / quoted-string import that dies in the parser with "Expected module name"; none tests nonexistent module, nonexistent symbol, wildcard conflict, or import-after-code as its comments claim; lines 14/15 are the same case twice; see detail
arrays/array_slice_errors.fire | WEAK | lines 12-13 pin cascades (`badStart`/`badEnd` not defined because the failed declaration was dropped); both slice cases are the same single rule (FS-PARSE-0013), the comments ("start must be integer") describe checks that never run
arrays/array_access_syntax_errors.fire | WEAK | pins cascade diagnostics (`Expected initializer expression...`) in addition to the real one; two valid distinct cases
arrays/array_element_assignment_invalid_target.fire | WEAK | pins 3 cascading diagnostics for `arr[] = 5;`, covered in spirit by array_index_assignment_target_errors.fire (`arr[!]`); keep only one
imports/export_visibility_private.fire | WEAK | no "symbol not exported" diagnostic exists: the test pins `Variable 'hiddenValue' not defined` twice (import line + use). Right behavior (rejection), misleading code/message
control_flow/statement_form_errors.fire | WEAK | line 30 `arr[0] = ;` is a documented case with NO annotation (swallowed by error recovery of the previous statement); `x = ;` at :33 dup of assignment_target_errors
control_flow/for_in_extra_tokens.fire | WEAK | 2nd annotation (@27 `Expected assignment, function call, or method call`) is recovery noise; first message dup of loop_header_errors.fire:47
match/match_syntax_errors.fire | WEAK | 4 cascade annotations on lines 13, 17(2nd), 82-85 (`};` after missing arm body yields 4 diagnostics); cases 10/47/71 dup the single-case files
imports/deferred_generic_call_errors.fire | WEAK | 3 diagnostics all @10 for one malformed token (`Pair<5>(1,2)`), two are cascades of the first
imports/deferred_generic_call_empty_type_args.fire | WEAK | message is the generic "Expected assignment, function call, or method call", not about empty type args; fine as a regression pin but test intent is not verifiable from the code

## MERGE-candidates

arrays/array_index_count_errors.fire | REDUNDANT (partial) | index() / index("1") = array_method_call_errors.fire:18-19; only `count()` (0 args) and `count(true)` (wrong type) are unique; move those two lines into array_method_call_errors.fire then delete
types/semantic_operator_errors.fire | KEEP/MERGE | `int32 - float64` (mixed numeric) is not covered by binary_operator_type_errors (which has `+` bool); merge as one more function there
types/binary_operator_type_errors.fire | KEEP | the consolidated place for binary-op cases; absorbs the semantic_* single files
types/unary_operator_type_errors.fire | KEEP | consolidated unary file
arrays/array_method_call_errors.fire | KEEP | the main array-method file; its 2 string-method lines (:27,:28) are dup of strings/string_length_arg_count.fire and strings/string_unknown_method.fire (minor)
control_flow/dangling_else_errors.fire | REDUNDANT (low) | = syntax/syntax_errors.fire:28 (`Unexpected 'else' without matching 'if'`, same message)

## KEEP

arrays/array_access_undefined_index_errors.fire | KEEP | (the one to retain of the 4-way undefined-index/element family) verifies exactly one diagnostic
arrays/array_element_assignment_missing_expr.fire | KEEP | `arr[0] = ;` unique; this is the only place the case is actually demanded
arrays/array_index_assignment_target_errors.fire | KEEP | `arr[!] = 5` unique target-parse path
arrays/array_size_literal_suffix.fire | KEEP | `int32[5i8]` unique (FS-PARSE-0010)
control_flow/if_condition_syntax_errors.fire | KEEP | unique path (`if (,)`)
control_flow/loop_header_errors.fire | KEEP | 10 distinct header errors, each is a separate rule; all demanded; no cascades
control_flow/unterminated_if_body.fire | KEEP | unique EOF case
imports/import_inside_function.fire | KEEP | also syntax/statement_dispatch_errors.fire:11 emits it (dup of the same message) -> consider REDUNDANT; verified identical `Imports must appear at top level`
imports/import_syntax_errors.fire | KEEP (minor dups) | lines 19 and 22 dup syntax/declaration_dispatch_errors.fire:47,50; line 16 dup :50. Also relies on module `utils` not existing (module-not-found is a log, not a diagnostic, so nothing is pinned)
imports/import_trailing_dot_eof.fire | KEEP | the true EOF case
imports/deferred_generic_call_* | see WEAK above
match/match_duplicate_field_binding.fire | KEEP | unique semantic rule, correct
match/match_duplicate_variant.fire | KEEP | correct
match/match_non_exhaustive.fire | KEEP | correct (lists missing Point, Rectangle)
match/match_unknown_payload_field.fire | KEEP | correct
match/match_unknown_variant.fire | KEEP | correct: the 2nd annotation (non-exhaustive @10) is a real second error (Point is genuinely unmatched), not a cascade
match/match_wildcard_not_last.fire | KEEP | correct
types/cast_undefined_operand.fire | KEEP | unique operand-undefined cast path, one diagnostic
types/semantic_operator_errors.fire | see MERGE
types/cast_and_generic_type_errors.fire | see FIX; lines 16/12/19 dup other files, lines 23, 29 (`expects 2 type arguments`), 42 are unique-ish (42 dup of classes/constructor_call_arg_count.fire)

## Detailed evidence: INCORRECT / WEAK

### types/type_errors_comprehensive.fire
Demanded (9): 7 (SEM-0002), 11 (SEM-0002), 16 (SEM-0010 string+int), 38 (index non-array), 42 (non-int index), 45 (undefined var), 58 (if cond), 63 (while cond), 73 (duplicate decl).
NOT demanded / silently unchecked (verified by isolated check + full compile, repros s8/r3.fire, a3.fire, r4.fire):
- l.19 `mixed: int32[] = [1,2,"three",4]` : check accepts; full compile ICE (FLIRV-T1/FIRV-T8)
- l.23 `numbers[0] = "string"` : check accepts; full compile ICE FIRV-T8
- l.29 `takesInt("wrong type")`, l.33 `return "string"`, l.54/55 wrong call arity : accepted by check (known: invalid/known_issues/function_call_arg_type_mismatch, function_call_too_few_args, function_call_too_many_args, return_type_mismatch)
- l.48 `undefinedFunction(1,2,3)` : the file has an import, so the undefined-function check is "deferred" and never fires; full compile dies in lowering "call to unknown function" (compiler bug, repro r4.fire; the same call WITHOUT an import gives FS-PARSE-0012, which is what functions/function_errors.fire:29 relies on)
- l.69 `not_func(5)` : accepted (known: known_issues/call_non_function_variable)
So the doc-line "type mismatches in assignments, function calls, operators, conditions, indexing" is wrong for "function calls" and the file's header "These should all produce ... errors" is false for 8 lines. Each demanded line also duplicates type_mismatches.fire (7<->5, 11<->59, 16<->10, 38<->33, 42<->37, 58<->40); only `while(42)` (but control_flow_invalid.fire:17 covers while) and l.73 are not duplicated there. l.73 is a SAME-scope redeclaration but the compiler says "already declared in an outer scope; shadowing not allowed" (misleading message; scoping/scope_errors.fire:8 covers shadowing).
Recommendation: delete this file; the unchecked scenarios belong in known_issues (3 are already there; l.19, l.23, l.48 are not).

### types/type_mismatches.fire
No `import ...println/print`, so `print(...)` is undefined: 19 annotations (FS-PARSE-0012 @1/@5) are incidental, including the labelled "use before declaration" case (l.51 flagged because `print` is undefined, l.52 `int beforeDecl = 10;` is a C-style declaration, a parse error unrelated to use-before-declaration). `arr.append("x")`, `arr.insert(0,"y")`, `arr.insert("z",3)`, `arr.pop(1,2)`, `arr.pop("x")` all report only "Arrays are fixed-size; method X is not supported" (not wrong-arg-type/count as commented): five duplicates of array_method_call_errors.fire:9-11. `[1,2,"three"]` (l.13) is silently accepted (comment "error mixed types" unmet). Lines 5,10,16,33,37,40,47,55,59 are real and are dups of other tests (see grouping above: null -> nullable/nullable_errors.fire:5; nested array -> 2 other files; shadowing -> scoping/scope_errors.fire:8).

### types/semantic_modulo_mismatch.fire
`b: int64 = 6;` is annotated `//~ ERROR FS-SEM-0002 @5`. docs/reference/type_system.md:102-111 states "When you assign a literal to a variable with an explicit type, the literal automatically takes on that type" (`large: int64 = 9223372036854775807;`, `small: int8 = 42;`). The compiler rejects ALL of these (repro r7.fire: int8, uint16, float32, int64 all `Expected X, got int32/float64`). Either the docs are wrong or the compiler is; either way this test (and any test in the suite using unsuffixed literals for non-int32 types) encodes the current bug as expected behavior. All valid tests in the suite use suffixes (`100i64`), hiding the problem. The intended mod-mismatch error (line 6) is correct.

### arrays/array_errors.fire
Comment claims errors that are not produced:
- l.13 `arr[10]` on int32[5]: no error (docs arrays.md:51 says out-of-bounds is a RUNTIME error, so the comment "static checking" is stale rather than the compiler wrong).
- l.18 `int32[5] = [1,2,3]` (too few) and l.19 `int32[3] = [1,2,3,4,5]` (too many): accepted; docs/reference/arrays.md:27,30 say initializer size must match declared size -> "Error". Full compile also succeeds silently (repros c2.fire, c3.fire).
- l.24 `[1,"two",3]`: accepted by check; full compile ICE FLIRV-T1 (c4.fire).
- l.37 `arr1 = arr2` (int32[3] = int32[5]): accepted by check; ICE FIRV-L2 (c5.fire).
Demanded (6 lines): l.6 (2 diagnostics, 2nd is cascade `Expected assignment...`), 25, 30, 44, 50, 56. The first is a parse error ("Expected ']' after '[' in array type"), not a "size must be constant" semantic error as labelled. l.30 dup of array_edge_invalid.fire:8; l.50/56 dup of type_mismatches.fire:37,33.

### control_flow/control_flow_invalid.fire
`print` never imported -> l.4,13,16,17,20 incidental FS-PARSE-0012. `break;` / `continue;` at top level (l.5,9) produce `FS-PARSE-0010 Expected semicolon after statement` *in addition to* the intended `FS-SEM-0010 'break' statement not within a loop`; inside a function body only the SEM error appears (s8/r5.fire, a2.fire). The pinned PARSE-0010 is a top-level-statement-parsing quirk, not a language rule. Real value: l.5/9/13/17 SEM-0010 for break/continue/if-cond/while-cond (l.13 and l.17 dup type_errors_comprehensive.fire:58,63 and type_mismatches.fire:40). Better: put `break`/`continue` outside a loop inside a function (no PARSE error) and import println.

### arrays/array_edge_invalid.fire
Same missing-import problem (l.4,6,10,15,18). Real demanded: l.8 (assign array to int32; dup array_errors.fire:30), l.12/13 (unknown method remove/sort; dup array_method_call_errors.fire:23), l.16 nested arrays (3rd copy of the rule, see docs note below). Entire file is redundant once the `print` noise is removed.

### types/cast_and_generic_type_errors.fire
- l.39 `print(1, 2);` annotated FS-PARSE-0012 under the comment "Builtin arity error": the error is `Function 'print' is not defined` (no import). Not a builtin arity test.
- l.35 `e: int32 = pick(1, "two");` pins two diagnostics: SEM-0010 `Could not infer type arguments` (@12, the real one) and SEM-0002 `Expected int32, got T` (@1) which is a cascade (unresolved type var leaks as `T`). Same pair appears in generics/generic_function_inference_errors.fire:16.
- l.12 nested arrays: dup (see above). l.16 cast array: dup of cast_array_to_non_string. l.19: dup of expressions/cast_to_class_type.fire:14. l.42: dup of classes/constructor_call_arg_count.fire. Unique: l.23 (cast non-numeric class to int32), l.29 (explicit generic type-arg count).

### imports/import_errors.fire
Source uses `import "nonexistent_module";`, `import { undefined_symbol } from "std";`, `import * from "std";`, `import "io";` - none is firescript import syntax (docs/reference/imports.md uses dotted `import @firescript/std.io.println;` / `import mod.sym;`), so every case hits the same "Expected module name after 'import'" (:4,:14,:15,:19 identical rule; :7 also a 2nd cascade). Comments say nonexistent file / symbol, wildcard conflict, import-not-at-top: not tested. ImportNotFoundError (FS-IMP-0001) is only ever emitted as a log line (`Import resolution failed: Module not found`), never a coded diagnostic, so a compile-fail annotation can't currently express it; likewise importing a nonexistent *symbol* from an existing module has no test at all.

### imports/import_cycle_a.fire (+ import_cycle_b_provider.fire helper)
Annotated `FS-PARSE-0003 @40` on line 2. Actual output: `Variable 'ping' not defined` positioned at 2:40 (the line is only 36 chars; the position belongs to import_cycle_b_provider.fire:3, mapped through the wrong source). The designed diagnostic, FS-IMP-0002 `Cyclic import detected`, is never produced: _load_module's cycle branch (imports.py:176-180) is unreachable for a real cycle (documented in tests/python/imports/test_module_resolver.py:162-187). The test therefore passes only because it pins a wrong, confusing diagnostic. This belongs in known_issues (expecting FS-IMP-0002 / a coded diagnostic), not here.

### arrays/array_slice_errors.fire
l.7/9 FS-PARSE-0013 "slicing not supported" is the real rule (docs arrays.md:3,230 PLANNED) - the `"1"`/`true` bounds are irrelevant, so two cases = one rule. l.12/13 `println(badStart.length())` -> `Variable 'badStart' not defined` is purely a consequence of the declaration being discarded after the parse error. Second FS-PARSE-0010 on each slice line is also a cascade.

### control_flow/for_c_style_missing_semicolon.fire
`for (i: int32 = 0; i < 10 i++)`: real = `Expected ';' after for loop condition` @31. The second annotation `FS-PARSE-0003 Variable 'i' not defined` @31 is a recovery artifact (the declaration of `i` is lost), i.e. wrong-by-construction: a future recovery fix would break the test even though the behavior would be better.

### imports/export_visibility_private.fire
`import visibility_provider.hiddenValue;` of a non-exported symbol. Rejected (correct per docs/reference/modules.md "private by default") but reported as undefined-variable FS-PARSE-0003 at the import AND at the use site; no diagnostic says "not exported".

## Missing coverage (no test anywhere in slice)
Arrays: initializer-size mismatch (too few/too many) -> doc'd error, compiler accepts; mixed-type literal elements; element assignment with wrong type; assigning arrays of different declared sizes; passing wrong array type to function param; `arr.length` without parens; negative-index out-of-range; array of class/owned types misuse; index with float/bool; uninitialized non-sized array decl `x: int32[];`.
Types: function argument/return type mismatch & arity (only in known_issues); mixing int32+int64 / float32+float64 in arithmetic; comparison `<`/`>` on bool/string/class; unary `-` on string/bool; `**` type errors; string-to-numeric cast of non-numeric type; cast between incompatible class types; class-typed assignment mismatch (`a: A = B()`); unsuffixed-literal range errors docs promise (`int8 x = 200` per type_system.md:114) ; literal inference to non-int32 types (currently wrong, see bugs).
Imports: nonexistent module; nonexistent symbol from an existing module; importing from a module that exports nothing; duplicate import / name collision between two imports; alias collisions (`as`); wildcard import conflicts; import not at top of file (only inside-function covered); real cyclic import diagnostic (FS-IMP-0002); relative-import rejection (`import .foo`; only monkeypatched in tests/python).
Match: value-producing arms with mismatching types (`-> radius`, `-> "zero"`); non-exhaustive value-form match; match on a non-enum scrutinee (`n: int32`); pattern enum type different from scrutinee's enum (`B.P` on an `A`); tag-only variant given payload bindings is covered (verified `Shape.Point(x)` -> error) but not tested; wildcard-only duplicates (`_` twice reports "must be last" - fine but untested); match arm count zero (`match s { }`); pattern arity (binding fewer fields than variant has -- positional vs named); use of a payload binding outside its arm / type of binding misuse; match as statement with value arms.
Control flow: `if`/`while` with a class/array/null condition (only int/string); `for-in` over non-iterable (known_issues); `for` init/step type errors; `continue` outside loop inside a function; nested-loop break semantics; `else if` malformed; `yield` outside generator (known_issues); return in void fn (known_issues).

## Compiler bugs discovered (minimal repros)
1. Unsuffixed literals not inferred to the declared type (docs say they are): `b: int64 = 6;` -> `FS-SEM-0002 Expected int64, got int32`; also `small: int8 = 42;`, `medium: uint16 = 30000;`, `pi: float32 = 3.14;` (docs/reference/type_system.md:104-112). Pinned as "expected" by types/semantic_modulo_mismatch.fire:5.
2. Undefined free-function call in a file that has any import is accepted by --check (check is deferred, never fires): `import @firescript/std.io.println; undefinedFunction(1);` -> no diagnostic; full compile fails with plain log `FIR->FLIR lowering failed: call to unknown function undefinedFunction` (no code/location). Without the import it correctly reports FS-PARSE-0012 (statements.py:195-205). Missing from known_issues.
3. Array literal / element type mismatches not diagnosed by check; full compile gives internal compiler errors: `a: int32[3] = [1, "two", 3];` -> FLIRV-T1; `n: int32[] = [1,2,3]; n[0] = "string";` -> FIRV-T8; `a5: int32[3]=...; a6: int32[5]=...; a5 = a6;` -> FIRV-L2.
4. Array initializer length vs declared size not diagnosed (docs/reference/arrays.md:27 says "Error"): `a: int32[5] = [1,2,3];` and `b: int32[3] = [1,2,3,4,5];` both compile silently.
5. match: pattern of a different enum than the scrutinee (`s: A; match s { B.P -> {} _ -> {} }`) and a non-enum scrutinee (`n: int32; match n { _ -> {} }`) compile with no diagnostic; value-producing match with arm-type mismatch (`Shape.Circle(radius) -> radius, Shape.Point -> "zero"` assigned to float64) -> FIR ICE FIRV-L2 instead of a semantic error. (docs have no match-typing rules to cite, but the ICE is a bug regardless.)
6. Cyclic import detection is dead code; a cycle produces `Variable 'ping' not defined` at a position that is outside the reported file (imports.py:176; confirmed by tests/python/imports/test_module_resolver.py:162-187).
7. Top-level `break;` / `continue;` (outside any function) produce a bogus extra `FS-PARSE-0010 Expected semicolon after statement` alongside the correct SEM-0010 (repro s8/r6.fire / a2.fire). Inside functions only the SEM error appears.
8. Same-scope redeclaration (`duplicate: int32 = 1; duplicate: int32 = 2;`) is reported as "already declared in an outer scope; shadowing not allowed" - wrong message for same scope (type_errors_comprehensive.fire:73).
9. docs/reference/arrays.md:118-131 ("Nested Arrays ... not fully implemented", uses old `int8[3][3] matrix = [...]` syntax) vs. compiler rule "Array literals cannot directly contain arrays" pinned by 3 tests; the doc has no [PLANNED] marker on that section, which CLAUDE.md requires.
10. Non-exported import yields only "Variable not defined" (no export-visibility diagnostic) - minor diagnostics-quality gap.

## Cross-cutting patterns worth fixing
- Missing `import @firescript/std.io.println;` in 4 old-style tests (type_mismatches, array_edge_invalid, control_flow_invalid, cast_and_generic l.39) makes `print(...)` a source of ~30 incidental annotations that pass for the wrong reason and would mask real regressions.
- Many tests pin cascade diagnostics (3-4 annotations for one defect) - fragile and low-information: match_syntax_errors, match_pattern_bad_binding, array_access_syntax_errors, array_element_assignment_invalid_target, array_slice_errors, for_c_style_missing_semicolon, deferred_generic_call_errors.
- "Comprehensive" files carry commented-out or un-annotated error lines that appear to be tests but demand nothing (array_errors, type_errors_comprehensive, statement_form_errors l.30).
