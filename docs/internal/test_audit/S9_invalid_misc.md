<!-- Audit shard report, 2026-11-18. Raw audit output; see README.md for the consolidated plan. Verdicts are recommendations, not applied changes. -->
# S9 audit: tests/sources/invalid/{syntax,expressions,enums,strings,functions,scoping,operators,declarations,nullable,literals,generators,known_issues}

All paths relative to /home/alec/Programming/firescript/tests/sources/invalid/. 50 files, no `//@ helper` files in this slice.
Observed with: python firescript/main.py --platform windows --arch x86_64 --check --message-format json <file>. Scratch repros live in
/tmp/claude-1000/-home-alec-Programming-firescript/2f6fea08-4b29-4fbd-9b67-4bb973797cf6/scratchpad/audit/x/ (not in repo).
tests/python/* has no message/diagnostic-level coverage of any of these diagnostics (grepped), so the .fire files are the only coverage; redundancy is judged against other invalid/ files.

Key background facts found while auditing
- Comments are ordinary tokens inside the parser (firescript/parser/base.py `_COMMENT_TOKEN_TYPES`, "stripped ad hoc by each parse loop"). The test-harness `//~` comments therefore can CHANGE compiler behaviour: two tests below pin diagnostics that exist only because the annotation comment is there (see INCORRECT section).
- Un-imported `print`/`println` yields FS-PARSE-0012 "Function 'print' is not defined", and that error SUPPRESSES the missing-semicolon error on the same statement (repro ms2 vs ms1), so legacy tests that call `print` without importing it are partly testing nothing.

## DELETE-candidate
syntax/syntax_comprehensive.fire | INCORRECT, WEAK, REDUNDANT | Heavily overlaps syntax/syntax_errors.fire (unclosed paren, unclosed array literal, `@#$%`, missing `;`, `else {`); 5 of its 10 cases (lines 30-50) produce no diagnostic at all in-file (swallowed by an unclosed string); line 41 annotation is a cascade of the unclosed string. Only unique idea: `while {` (no condition parens) - move it elsewhere first.
functions/function_errors.fire | INCORRECT, WEAK | 8 of 9 documented cases (missing return, wrong arg count/type, call non-function, duplicate fn, 2 return mismatches) emit NO diagnostic; passes only on 2 incidental errors (un-imported `println`, undefined fn). Rewrite or split: imported println, keep the undefined-function case, move rest to known_issues/ (call non-function, arg count/type, return mismatches already exist there; duplicate fn and missing-return do not).
strings/string_length_arg_count.fire | REDUNDANT | strings/string_method_errors.fire:5 is the same input `s.length(1)` -> FS-SEM-0010 @18; arrays/array_method_call_errors.fire:27 also covers `s.length(1)`.
strings/string_unknown_method.fire | REDUNDANT | strings/string_method_errors.fire:11 (`s.foo()` -> FS-SEM-0010 "Unknown method ... for type 'string'") is the same rule; manifest says arrays/array_method_call_errors also covers unknown string methods.
expressions/cast_to_class_type.fire | REDUNDANT | types/cast_and_generic_type_errors.fire:19 (`b: int32 = 5 as Widget;` -> FS-SEM-0010 @17) same rule ("Cannot cast to unknown or non-numeric type Widget").
expressions/implicit_assign_undefined_rhs.fire | REDUNDANT | control_flow/assignment_undefined_chain.fire (`x = y;` -> PARSE-0003 @9 + @5) is the same case; both even carry the same explanatory sentence.
functions/builtin_arg_count_errors.fire | INCORRECT, REDUNDANT | `typeof` is not a builtin (docs/reference/type_system.md:464 says typeof is planned); the diagnostic comes from a hardcoded legacy branch (firescript/parser/type_system.py:876) shared with functions/reserved_name_typeof_arg_count.fire. By language rules `typeof()` should be "function not defined". Keep at most one of the two.

## MERGE-candidate
operators/logical_and_increment_errors.fire | REDUNDANT (partial) | `!a` = types/semantic_unary_not_non_bool.fire:5 and types/unary_operator_type_errors.fire:4; `true && a` = types/semantic_logical_non_bool.fire:6 / binary_operator_type_errors.fire:12; `undefined_var++` = types/semantic_unary_incdec_undefined.fire:4 / unary_operator_type_errors.fire:14. Only `a || true` (non-bool LEFT of `||`) is arguably new. Fold into types/.
syntax/statement_dispatch_errors.fire | REDUNDANT (partial) | line 11 (import in function) is identical to imports/import_inside_function.fire; line 26 (missing `;` after for condition) = control_flow/for_c_style_missing_semicolon.fire; line 32 (`yield ;`) = generators/generator_def_errors.fire g10. Keep the backtick char, `if ()`, `while ()` cases.
syntax/declaration_dispatch_errors.fire | WEAK, REDUNDANT (partial) | `fn bad_constraint<T: >` = generics/generic_def_syntax_errors.fire:11 (`<T:>`, same 3 diags); `import @;` = imports/import_syntax_errors.fire:19; `identity_empty<>` same path as `badParam<(`. Only `T: Box<int32>` (nested generic constraint, unsupported) is unique, and it pins a 3-diagnostic cascade + a PARSE-0003 on `x`.
syntax/expression_operand_errors.fire | WEAK, REDUNDANT (partial) | `j += ;` = expressions/compound_assignment_missing_rhs.fire; `arr[0] = ;` = arrays/array_element_assignment_missing_expr.fire (+ control_flow/statement_form_errors.fire:25/33); `arr[0:1]` slicing PARSE-0013 = arrays/array_slice_errors.fire; `5 as ;` ~ expressions/cast_to_non_type_token.fire. Binary-operator lines (||, &&, ==, +, *, **) may each hit a distinct precedence-level parse function so are probably fine; every one pins a 2-diagnostic pair (0012 "Unexpected token ;" + 0010 "Expected initializer expression") and `-;` pins three, `new;` two at the same column.
functions/builtin_arg_count_errors.fire + functions/reserved_name_typeof_arg_count.fire | see above | one of them.
enums/enum_generic_unsupported.fire, enums/enum_variant_arity_mismatch.fire, nullable/nullable_errors.fire | cosmetic | contain stale `// EXPECT: ...` header comments (leftover from the old harness); harmless but misleading (EXPECT is a real harness keyword).

## FIX-EXPECTATION
operators/operator_errors.fire | FIX-EXPECTATION (line 60) + INCORRECT (lines 36, 47) + WEAK (lines 19-20, 53-54 emit nothing)
  - CONFIRMED diagnosis: the failing diagnostic is exactly line 60 `x += "hello";` (x: int32) -> FS-SEM-0010 @7 "Operator '+=' not supported between types int32 and string". Column 7 is the `+=` token (4-space indent, `x`=5, space=6, `+=`=7), consistent with operators/compound_assignment_type_errors.fire where the operator column is annotated. The program is invalid per docs/reference/operators.md ("require both sides to be the same type"). The change came from HEAD~2 commit 2322a7d "Type-check compound assignment instead of failing in the FIR verifier". Observed diagnostics = 13, annotations = 12; the only extra is 60:7.
  - CORRECT FIX: change line 60 to `    x += "hello";  // Type mismatch  //~ ERROR FS-SEM-0010 @7`. (Equivalent: add `//~ ERROR FS-SEM-0010 @7` on that line.) Nothing else needs to change for it to pass.
syntax/syntax_errors.fire | INCORRECT/WEAK | see detail
syntax/syntax_comprehensive.fire | (delete candidate above)
enums/enum_body_syntax_errors.fire | INCORRECT | second 10:6 annotation (and arguably the first) pins comment-token bug, see detail
enums/enum_def_errors.fire | INCORRECT (3 spurious annotations) + WEAK | see detail
expressions/expression_at_eof.fire | INCORRECT | its own annotation comment creates the 5:15 FS-PARSE-0012 diagnostic, see detail
literals/literal_errors.fire | WEAK/INCORRECT | see detail
scoping/scope_errors.fire | WEAK/INCORRECT | see detail

## KEEP
syntax/directive_errors.fire | KEEP | 3 distinct directive parse paths (missing name, unknown name, missing `;`), each a single clean diagnostic.
syntax/export_errors.fire | KEEP | 5 distinct export rejections, one diagnostic each (line 4 intentionally lacks `;`, harmless).
expressions/cast_to_non_type_token.fire | KEEP | `x as 5` -> "Expected type after 'as'" single clean diag (minor overlap with expression_operand_errors `5 as ;`).
expressions/compound_assignment_missing_rhs.fire | KEEP, WEAK | the dedicated home for `x +=;`; but it also pins a cascade `3:46 Expected '}' to close scope` (recovery eats the closing brace). Fragile to recovery changes.
expressions/implicit_assign_undefined_receiver.fire | KEEP (partial overlap) | scoping/bare_assignment_without_declaration_errors.fire:23 (`n = w.getV();` w undefined) has the same shape; only the builtin `.length()` receiver differs.
expressions/postfix_cast_after_broken_paren.fire | KEEP, WEAK | first diag (0012 @20) is the true error; 2 further diags at 5:22 are cascades.
enums/enum_construct_errors.fire | KEEP | `Color.;` (2nd diag at same col is a cascade) and unknown variant; unique.
enums/enum_construct_move_errors.fire | KEEP | enum-payload move path, distinct regression; use-after-move FS-SEM-0001 @9 is correct.
enums/enum_generic_unsupported.fire | KEEP | generic enums are [PLANNED] in CLAUDE.md status table; error is single and clean.
enums/enum_variant_arity_mismatch.fire | KEEP | too many args / args on payload-less variant, two clean diags (code FS-PARSE-0012 though it is semantic in nature; fine).
strings/string_implicit_conv_error.fire | KEEP | string + int32, string + bool (docs/operators.md:36); missing reversed operand order (see missing coverage).
strings/string_method_errors.fire | KEEP | the one string-method test worth keeping.
functions/function_def_syntax_errors.fire | KEEP, WEAK | 6 distinct parse paths each with one clean diag. Comment on line 8 "Missing parameter type" is wrong: `fn badParamType(!)` tests "Expected parameter name", the same diag/path as line 17 `missingParamName(: int32)`; the two `[` cases (return type vs param type) share the `_parse_type_expression` path.
functions/reserved_name_typeof_arg_count.fire | KEEP (only if legacy typeof check stays) | documents a legacy hardcoded rule; consider removing along with that rule.
scoping/bare_assignment_without_declaration_errors.fire | KEEP | `name = expr;` never declared; all 5 diags are real (use of undefined w/n and the assignment targets).
scoping/parameter_shadowing_errors.fire | KEEP | free-fn and constructor params shadowing a global; clean.
operators/compound_assignment_type_errors.fire | KEEP | verified: `u = u + 1` (uint8 + int literal) is also rejected so `u += 1` is consistent; columns are the operator token. Caveat: `f %= 2.0` relies on "% is integer-only", which docs/reference/operators.md does not state (docs gap, see below).
declarations/builtin_method_decorator_outside_std_internal.fire | KEEP | unique.
declarations/const_missing_type.fire | KEEP (TRIVIAL) | one-line, unique, "Expected ':' after variable name" @10 (the `;`).
nullable/nullable_errors.fire | KEEP (partial overlap) | `a: int32 = null` also in types/type_mismatches.fire:16; string init and reassignment-to-null are unique. Narrow: see missing coverage.
generators/generator_def_errors.fire | KEEP | g1/g2/g3 each one clean diag; g10 `yield;` is also in statement_dispatch_errors (keep here, drop there).
known_issues/call_non_function_variable.fire | KEEP | valid claim (`x(10)` with x: int32 is plainly invalid); currently no diagnostic. Unused `import println`.
known_issues/for_in_non_iterable.fire | KEEP | valid claim (for-in is over arrays/strings/generators per control_flow docs); currently no diagnostic.
known_issues/function_call_arg_type_mismatch.fire | KEEP | valid; slightly non-minimal (call nested in println) - harmless.
known_issues/function_call_too_few_args.fire | KEEP | valid (`add(1)` for 2-param fn).
known_issues/function_call_too_many_args.fire | KEEP | valid.
known_issues/generic_class_method_arg_type_mismatch.fire | KEEP | valid; mirrors classes/instance_method_arg_type.fire (which uses FS-SEM-0010 @col).
known_issues/return_missing_value.fire | KEEP | valid.
known_issues/return_type_mismatch.fire | KEEP | valid; see code-choice note.
known_issues/return_value_in_void_function.fire | KEEP | valid. Unused `import println`.
known_issues/yield_outside_generator.fire | KEEP | valid.
known_issues/yield_type_mismatch.fire | KEEP | valid; see code-choice note.

Known-issues notes (all 11 verified: with --check the compiler reports NO diagnostics for each, so they genuinely fail as intended; I did not run the non-check pipeline, so the "internal FIR verifier error FIRV-T4/T5/G1, FLIRV-T4" claims in the headers are UNVERIFIED by me).
- Annotation codes: argument-count/type mismatches -> FS-SEM-0010 matches every existing analogue (classes/instance_method_arg_type.fire etc.). For return/yield TYPE mismatch the codebase uses FS-SEM-0002 ("Type mismatch for variable ...", TypeError) for assignment-like mismatches (types/type_mismatches.fire:5, generics/generics_errors.fire:15), so FS-SEM-0002 may be the more natural code for return_type_mismatch / yield_type_mismatch / return_missing_value; the maintainer should decide before the check is written. 
- No file pins a column (`@N`), so once the check lands they will not verify location. Suggest adding columns: argument token for the arg-type cases, `return`/value token for return cases.
- Missing-known-issue siblings: duplicate function definition and "missing return in non-void function" (both documented as errors in function_errors.fire comments) have no known_issues file. Also: undefined function used inside an expression (see bugs).

## Detailed evidence: INCORRECT and WEAK findings

### syntax/syntax_errors.fire (INCORRECT + WEAK + REDUNDANT with syntax_comprehensive)
- 9 of 22 annotated diagnostics are "Function 'print' is not defined" (FS-PARSE-0012) because `print` is never imported. They are real errors but incidental noise unrelated to the test intent.
- Line 4 `print("-- invalid syntax: missing semicolons --")` is missing a `;` but that error is NOT reported: the undefined-function error masks it (repro: `println("a")\nx: int32 = 1;` without import -> only PARSE-0012; with import -> `PARSE-0010 Expected semicolon after statement`). So the first "missing semicolon" case is untested.
- Line 28 `else { print(1); }` = control_flow/dangling_else_errors.fire (same FS-PARSE-0012 "Unexpected 'else' without matching 'if'"). Line 20 `if 1) {` and 24 `while 1 < 2 {` ~ loop_header_errors.fire / syntax_comprehensive.
- Fix suggestion: import println, use println, add the semicolons that are not the thing under test.

### syntax/syntax_comprehensive.fire (INCORRECT + WEAK + REDUNDANT)
Bisecting the file (truncate at line N, scratch copies):
- Line 34 `s: string = "hello;` : the unclosed string literal runs to the next `"` (the one in line 41 `"orphan else"`); truncated at line 38 the compiler reports 34:14 and 37:17, but with the `else {` block present those diagnostics vanish. In-file, the cases at lines 30-50 (missing block braces, unclosed string, `bad_arr: int32[ = 5;`, "dangling" else, `fn test() -> void;`, `fn badFunc {`) produce NO diagnostics of their own; I verified `bad_arr: int32[ = 5;` (1:17 PARSE-0010), `fn test() -> void;` (1:18 PARSE-0010 "Expected '{' to start function body"), `fn badFunc {` (1:12 PARSE-0010) each DO error when isolated. So these cases are untested here.
- Line 41 annotation (`FS-PARSE-0010 @14`, "Expected semicolon after statement") is a cascade of the unclosed string, not a dangling-else diagnostic. Actually the `else` attaches to the brace-less `if (true) y: int32 = 5;` (braceless if bodies are supported: control_flow/unterminated_if_body.fire), so it is not dangling at all.
- Lines 17 and 22 annotate "Function 'println' is not defined" (println not imported): incidental, as in syntax_errors.
- Line 53 `Expected '}' to close scope @23` is the true error for the final unclosed fn; line 12 pins two diags at the same column (the second is a cascade).
- "Missing block braces" (`if (true)\n y: int32 = 5;`) compiles clean; the comment says "should produce errors". Either the language supports braceless bodies (docs/control_flow.md line 7 says "use curly braces", so docs and compiler disagree - not verified further) or this is a missing diagnostic.

### expressions/expression_at_eof.fire (INCORRECT)
Message of the pinned 5:15 FS-PARSE-0012 is literally `Unexpected token //~ ERROR FS-PARSE-0012 @15` - the annotation comment itself is lexed as a token the parser trips on. Without the annotation (file `fn f() -> void {\n    x: int32 =` ) only 2 diagnostics are produced: `2:15 Expected initializer expression in variable declaration` and `1:16 Expected '}' to close scope`. So the FS-PARSE-0012 annotation pins an artifact of the test harness's own comment, and the manifest's "also produces a parse-level unexpected token" rationalises it. Also the 4:32 annotation is a cascade.

### enums/enum_body_syntax_errors.fire (INCORRECT) and enums/enum_def_errors.fire (INCORRECT + WEAK)
Root cause is a real compiler bug (see bugs #1): firescript/parser/declarations.py:1437-1440 checks `current_token.type != "CLOSE_BRACE"` after the last variant without skipping comment tokens, so a comment after the last variant (without trailing comma) yields a spurious "Expected ',' or '}' after enum variant". The `//~` annotations are comments, so:
- enum_body_syntax_errors.fire: `A  //~ ...` then EOF. Without the comment only `Expected '}' to close enum body` (2:6) is produced (repro eofc). The annotated pair at 10:6 includes the spurious one; the file's own comment explains it away as "also missing a ',' or '}'".
- enum_def_errors.fire: annotations at 11:6, 33:26 and 45:6 (`//~^ ERROR FS-PARSE-0010 @6/@26/@6`) are all this spurious diagnostic. Isolated without comments: Dup -> 1 diag (0012 @5), DupField -> 1 diag, MissingComma -> 1 diag (@5). (Bisect: truncating the real file at 13 lines still shows 11:6; a valid `enum E { A,\n B  // c\n}` also errors.)
- Also WEAK: `V(x: !)` and `V(: int32)` each pin 4 diagnostics at the same position (true first: "Expected type" / "Expected payload field name"; the other three are recovery noise), and `enum {` pins a cascade "Expected assignment, function call, or method call" at 5:5.

### operators/operator_errors.fire (INCORRECT lines 36, 47; WEAK lines 19-20, 53-54)
- Line 36 `a and b`: firescript has no `and` operator (docs/operators.md:143-145 even uses `and`/`not` as variable NAMES). The 3 pinned diagnostics (PARSE-0010 @22, @26, FS-SEM-0002 @5 "Expected bool, got int32") are cascades of `a` followed by identifier. The intended rule (logical op on non-bool) is covered correctly by types/semantic_logical_non_bool.fire and operators/logical_and_increment_errors.fire.
- Line 47 `not x`: same - `not` parsed as an identifier ("Variable 'not' not defined" + PARSE-0010); intended rule covered by types/semantic_unary_not_non_bool.fire.
- Lines 19-20 `10 / 0`, `15 % 0` ("if statically checked"): no diagnostic; docs do not promise one. Lines 53-54 `5 = 10;`, `(5 + 3) = 10;`: no diagnostic even though clearly invalid (see bugs #5). These unannotated cases make the file look like it covers more than it does.
- Line 7 `a + b` (int32 + string) is reported as "Cannot implicitly convert 'int32' to 'string'" @23 (points at `b`... actually at the string operand's position) - correct rule per docs (no implicit conversion) though the message is odd for an int + string; redundant with types/type_errors_comprehensive.fire:16 (`text + number`).
- Lines 11, 14, 27, 29, 44, 66 are correct and each is a real rule (string `-`, int * string, `<` int vs string, string ordering (docs/operators.md:127), unary `-` on string, `++` on string).

### literals/literal_errors.fire (WEAK/INCORRECT)
- Line 5 `too_big: int32 = 99999999999999999999;` and `a: int32 = 3000000000;` and `128i8` produce NO diagnostic although docs/type_system.md:117,150-153 say compile-time overflow is an error (note `x: int8 = 200;` IS reported, as FS-SEM-0002 "got int32"). Unannotated, comment claims an error.
- Line 15 `"hello\q"` invalid escape: no diagnostic.
- Line 10 `0xGHIJ` and 27 `123abc` pass only through lexer-split artifacts: error is "Expected assignment, function call, or method call" at the stray identifier token, not an invalid-literal diagnostic.
- Line 20 unclosed string pins 3 diagnostics (0012 @19, 0010 @20 x2).
- Lines 37-38 `True`/`False` -> FS-PARSE-0003: true, but trivially "undefined identifier"; line 32 `x: int32 = 3.14;` FS-SEM-0002 fine.
- Should split: keep the cases that do error; move overflow and bad-escape to known_issues/.

### scoping/scope_errors.fire (WEAK/INCORRECT)
- Line 13 `println(future_var);` before `future_var: int32 = 100;` at top level: NO diagnostic, although docs/reference/scoping.md:259-262 lists this as an error. (Inside a function the same pattern IS reported as PARSE-0003 - repro ubd2 - so this is a global-scope bug.) The annotation-free line makes the file silently not test it.
- Lines 29-30 "Duplicate parameter names": both diagnostics (29:20, 29:30) are FS-SEM-0010 "already declared in an outer scope" because `x` is ALSO a global (line 6); the test cannot distinguish a duplicate-parameter error from a shadowing error. Isolated `fn f(a: int32, a: int32)` -> 1:16 FS-SEM-0010 on the second only (classes/class_method_duplicate_param.fire covers the method form; no clean free-function duplicate-param test exists).
- Line 8 block shadowing: partially redundant with types/type_mismatches.fire:47 and parameter_shadowing_errors.fire.
- Lines 20/26 (out-of-scope use after block / after for loop) are fine and not covered elsewhere in this slice.

### syntax/declaration_dispatch_errors.fire (WEAK)
Each of the 3 generic-header cases pins a "first real error + 2 cascade errors (`Expected '=' in variable declaration`, `Expected assignment, function call, or method call`) + PARSE-0003 for `x` in the body". Recovery-dependent (fragile). `fn identity2<T: Box<int32>>` is not in docs as a legal constraint (docs allow unions of types/aliases), so this documents a limitation via cascade rather than a rule.

### functions/function_errors.fire (INCORRECT)
Pinned: line 5 `println("no return!")` -> FS-PARSE-0012 "Function 'println' is not defined" (not the "missing return" the header claims) and line 29 `undefined_function(5);` (real). Not diagnosed: missing return in non-void fn (line 4), takes_two(5) / takes_two(5,10,15), takes_int("string"), `x(10)` non-function, duplicate `duplicate_func`, `return "string"` in int32 fn, `return 42` in string fn.

## Missing coverage (no test anywhere in my slice; not writing tests)
- Use-before-declaration in a function body (only the broken global case is mentioned, in scope_errors; types/type_mismatches.fire:51 uses the obsolete `int beforeDecl` syntax).
- Same-scope redeclaration (`count: int8 = 5; count: int8 = 10;` documented in scoping.md:252) - currently reported with the misleading "already declared in an outer scope" message; no dedicated test.
- Clean free-function duplicate-parameter test (no global of the same name).
- Duplicate function definition; missing return in non-void fn; undefined function inside an expression (`y: int32 = nothere();`).
- Nullable: nullable -> non-nullable assignment (`x: int32? = null; y: int32 = x;` accepted), `null` argument to non-nullable parameter, `null` returned from non-nullable fn, null in arithmetic. nullable_errors.fire covers only init/reassign-null for int32/string.
- Literals: int8/int16/uint overflow suffix forms (`128i8`), negative literal for unsigned, float literal precision/exponent malformations, bad char literals (`''`, `'ab'`), unterminated block comment, invalid escape.
- Strings: reversed-order concatenation `42 + "x"`, string `<`/`>` ordering is only in operator_errors:29, `string.substring/indexOf/replace` wrong arg counts/types, `+=` string with int (covered), string index assignment.
- Operators: assignment to non-lvalue (`5 = 10`), `++` on bool/float/const, prefix `++x` (docs say unsupported), `**` with negative/float exponent types, `!` / `-` on arrays, operand-type errors for `&`/`|`/`^` if they exist, comparison chaining.
- Enums: duplicate enum name, enum name colliding with class name, payload of unknown type, use of variant without enum qualifier, construction of payload variant with wrong arg TYPE (only arity tested).
- Generators: `yield` with wrong type, `yield` outside generator (known_issue only), generator with non-void `return value`, `generator<void>`.
- Casts: `as` to bool/char/string from invalid sources, string-to-class cast, cast of class instance.
- Functions: calling a function with named/labelled arguments incorrectly (functions.md:143 shows named-arg call form), recursion-less checks like returning a borrowed local, `void` function used in an expression, parameter with `void` type.
- Syntax: lone `}` at top level, stray `)`, missing `->` before return type, `fn` without name, unterminated block comment, `else if` without `if`, `for` with empty header `for (;;)`, duplicate `export`.
- Declarations: `const` with reassignment (memory notes say const decided; no invalid test in slice), missing initializer `x: int32;` at top level (docs: variables must be initialized), `x: = 5;`, `x int32 = 5;`.

## Compiler bugs discovered (wrong/missing diagnostics)
1. Parser: comment token after the last enum variant (no trailing comma) is rejected. Repro:
   ```
   enum E {
       A,
       B  // trailing comment
   }
   ```
   -> `3:6 FS-PARSE-0010 Expected ',' or '}' after enum variant`; also `enum E { A, B /* c */ }` and `B(x: int32)  // c`. Cause: firescript/parser/declarations.py ~1437-1440 doesn't skip comment tokens before the CLOSE_BRACE test. Valid program rejected. Two tests (enum_def_errors, enum_body_syntax_errors) currently pin the bogus diagnostic.
2. Parser leaks `//~`/comment text as a token at EOF: `fn f() -> void {\n    x: int32 =  //~ ERROR ...` gives `Unexpected token //~ ERROR ...` (FS-PARSE-0012); same family as bug 1 (comments are ordinary tokens).
3. Undefined function in an expression is silently accepted: `y: int32 = nothere(1,2);` (top level or inside fn) -> no diagnostic with --check; only the statement form `nothere(1);` -> FS-PARSE-0012. (Likely falls through to a later IR error.)
4. Top-level use-before-declaration accepted: `println(fv);\nfv: int32 = 1;` -> no diagnostic (docs/reference/scoping.md:259-262 says error). In a function body it is correctly reported.
5. Assignment to a non-lvalue accepted silently: `5 = 10;` and `(5 + 3) = 10;` produce no diagnostic under --check.
6. Integer literal overflow not diagnosed for int32 (`a: int32 = 3000000000;`, `99999999999999999999`) nor `128i8` though docs/type_system.md:150-153 requires a compile-time error; `x: int8 = 200;` is reported (as FS-SEM-0002 "got int32", an unhelpful message). Invalid string escape `"\q"` not diagnosed.
7. Duplicate function definitions and missing `return` in a non-void function: no diagnostics (not documented as errors, but function_errors.fire claims them).
8. Nullable -> non-nullable not checked: `x: int32? = null; y: int32 = x;` and `f(null)` for a non-nullable parameter both accepted silently (medium confidence it should error; docs/variables.md only states "cannot be assigned null").
9. Misleading message: same-scope redeclaration (`a: int32 = 1; a: int32 = 2;`) and duplicate parameter report "already declared in an outer scope; shadowing not allowed".
10. `typeof(...)` is accepted by the type checker without error for any call except a hardcoded arity check (`typeof(1)` assigned to `string` passes), though docs say typeof is not implemented; the legacy check at firescript/parser/type_system.py:876 reports arity as if it were a builtin.
11. Brace-less `while (true)\n x: int32 = 1;` / `if (cond) stmt;` accepted while docs/control_flow.md:7 says control flow uses curly braces (docs/compiler mismatch; low confidence it is a bug).
12. Error-recovery noise (not bugs per se but fragile, pinned by tests): duplicate/at-same-position cascades for malformed enum payloads (4 diags per case), unclosed string literal (swallows to the next `"`), generic-header errors (3 diags each).

## Verdict counts (50 files; a file may carry several)
KEEP-only (no problem or minor note): 22 (directive_errors, export_errors, cast_to_non_type_token, implicit_assign_undefined_receiver*, enum_construct_errors, enum_construct_move_errors, enum_generic_unsupported, enum_variant_arity_mismatch, string_implicit_conv_error, string_method_errors, function_def_syntax_errors, reserved_name_typeof_arg_count, bare_assignment_without_declaration_errors, parameter_shadowing_errors, compound_assignment_type_errors, builtin_method_decorator_*, const_missing_type, nullable_errors, generator_def_errors, + 11 known_issues files counted in KEEP below)
Overall: KEEP 33 (incl. 11 known_issues), REDUNDANT 9 (string_length_arg_count, string_unknown_method, cast_to_class_type, implicit_assign_undefined_rhs, builtin_arg_count_errors, logical_and_increment_errors, + partial: statement_dispatch_errors, declaration_dispatch_errors, expression_operand_errors), INCORRECT 8 (syntax_errors, syntax_comprehensive, expression_at_eof, enum_body_syntax_errors, enum_def_errors, function_errors, scope_errors, operator_errors, literal_errors counted as WEAK/INCORRECT; builtin_arg_count_errors), WEAK 7 (declaration_dispatch_errors, expression_operand_errors, compound_assignment_missing_rhs, postfix_cast_after_broken_paren, literal_errors, function_def_syntax_errors(minor), nullable_errors(narrow)), TRIVIAL 1 (const_missing_type), FIX-EXPECTATION 1 (operator_errors line 60).
