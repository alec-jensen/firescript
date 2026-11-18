<!-- Audit shard report, 2026-11-18. Raw audit output; see README.md for the consolidated plan. Verdicts are recommendations, not applied changes. -->
# P1 audit: tests/python/{parser,lexer,preprocessor,semantic,imports}

Method: read every test + code under test; per-test line coverage (coverage.py, private copy) compared against the union of ALL 505 tests/sources/**/*.fire compiled with --check (front-end only) and against the other tests in this slice; mutation runs in a private copy (/tmp/p1audit.F5e6/mut). Read-only on the shared repo.

Test case count discovered: 218 (matches the sum below). Bucket totals: DELETE=134, MERGE=27, FIX=17, KEEP=40
Verdict tags (a test can carry several): INCORRECT=11, KEEP=58, PINS-BUG=4, REDUNDANT=60, TRIVIAL=83, WEAK=36

## Per-file counts (DELETE / MERGE / FIX / KEEP)

- tests/python/parser/test_ast_node.py: 2 tests | DELETE 1 | MERGE 0 | FIX-ASSERTION 0 | KEEP 1
- tests/python/parser/test_declarations_coverage.py: 19 tests | DELETE 16 | MERGE 2 | FIX-ASSERTION 0 | KEEP 1
- tests/python/parser/test_declarations_dead_guards.py: 4 tests | DELETE 4 | MERGE 0 | FIX-ASSERTION 0 | KEEP 0
- tests/python/parser/test_declarations_dead_guards_more.py: 8 tests | DELETE 8 | MERGE 0 | FIX-ASSERTION 0 | KEEP 0
- tests/python/parser/test_expressions_dead_guards.py: 7 tests | DELETE 7 | MERGE 0 | FIX-ASSERTION 0 | KEEP 0
- tests/python/parser/test_generic_self_reference.py: 3 tests | DELETE 0 | MERGE 0 | FIX-ASSERTION 0 | KEEP 3
- tests/python/parser/test_parser_base.py: 51 tests | DELETE 27 | MERGE 13 | FIX-ASSERTION 1 | KEEP 10
- tests/python/parser/test_statements_coverage.py: 3 tests | DELETE 0 | MERGE 0 | FIX-ASSERTION 3 | KEEP 0
- tests/python/parser/test_statements_dead_guards.py: 16 tests | DELETE 16 | MERGE 0 | FIX-ASSERTION 0 | KEEP 0
- tests/python/parser/test_type_system.py: 3 tests | DELETE 1 | MERGE 0 | FIX-ASSERTION 0 | KEEP 2
- tests/python/parser/test_type_system_coverage.py: 1 tests | DELETE 0 | MERGE 0 | FIX-ASSERTION 1 | KEEP 0
- tests/python/parser/test_type_system_dead_guards.py: 10 tests | DELETE 10 | MERGE 0 | FIX-ASSERTION 0 | KEEP 0
- tests/python/parser/test_type_system_dead_guards_more.py: 18 tests | DELETE 18 | MERGE 0 | FIX-ASSERTION 0 | KEEP 0
- tests/python/lexer/test_lexer_internals.py: 1 tests | DELETE 1 | MERGE 0 | FIX-ASSERTION 0 | KEEP 0
- tests/python/preprocessor/test_preprocessor_internals.py: 14 tests | DELETE 4 | MERGE 1 | FIX-ASSERTION 6 | KEEP 3
- tests/python/semantic/test_semantic_analyzer_internals.py: 22 tests | DELETE 4 | MERGE 10 | FIX-ASSERTION 2 | KEEP 6
- tests/python/semantic/test_semantic_analyzer_report_error.py: 4 tests | DELETE 3 | MERGE 1 | FIX-ASSERTION 0 | KEEP 0
- tests/python/imports/test_module_resolver.py: 16 tests | DELETE 13 | MERGE 0 | FIX-ASSERTION 1 | KEEP 2
- tests/python/imports/test_module_resolver_extra.py: 16 tests | DELETE 1 | MERGE 0 | FIX-ASSERTION 3 | KEEP 12

## Policy note (applies to every `*dead_guards*` / `*_internals` / `*_coverage` file)

CLAUDE.md says: 'Line coverage is a diagnostic ... defensive or unreachable lines don't need contrived tests.' Roughly 100 of the 218 tests do exactly that: they monkeypatch `consume`, hand-build ASTNodes, bypass ASTNode's None-guard, or swap the lexer regex purely to execute a line no source can reach. Their only effect is to freeze dead code in place. Recommended: delete the tests, and (where the maintainer is certain it is dead) the guards. A second systemic problem: tests/python/parser/test_type_system_dead_guards_more.py does `from _helpers import ...` WITHOUT inserting its own directory in sys.path; it only imports because another module loaded earlier did the insert (running that file alone in a fresh interpreter raises ModuleNotFoundError; I hit this when running tests individually; the harness discovers/imports all modules in one process so it passes there). Also three different helper modules (_helpers, _dead_guard_helpers, _dead_guard_helpers2) duplicate each other.

## Per-test verdicts

### DELETE-candidate

- tests/python/parser/test_ast_node.py::test_repr_matches_str | TRIVIAL | asserts repr(x)==str(x); one-line __repr__ delegate, no plausible bug caught
- tests/python/parser/test_declarations_coverage.py::test_function_definition_rejects_non_type_return | REDUNDANT, WEAK | `fn foo() -> + {}`: lines all hit by invalid/generics/generic_def_syntax_errors.fire (`-> Q`) and functions/function_def_syntax_errors.fire; asserts only result None + any FS-PARSE-0010
- tests/python/parser/test_declarations_coverage.py::test_function_definition_rejects_malformed_array_return_bracket | REDUNDANT | same shape as `fn badRet() -> int32[ {` in invalid/functions/function_def_syntax_errors.fire which also pins code+column
- tests/python/parser/test_declarations_coverage.py::test_function_definition_generic_type_param_missing_name | REDUNDANT | `fn badParam<(x: T)` in invalid/generics/generic_def_syntax_errors.fire
- tests/python/parser/test_declarations_coverage.py::test_function_definition_generic_constraint_missing_type | REDUNDANT | `fn badConstraint<T:>` in generic_def_syntax_errors.fire
- tests/python/parser/test_declarations_coverage.py::test_function_definition_generic_missing_close_angle | REDUNDANT, WEAK | `fn unclosed<T(x: T)` in generic_def_syntax_errors.fire; this test asserts only `result is None` (no code)
- tests/python/parser/test_declarations_coverage.py::test_function_definition_array_param_bad_size_token | INCORRECT, REDUNDANT | name says 'bad size token' but the source is the valid `xs: int32[3]`; asserts array_size==3, duplicating tests/sources/functions/functions_sized_array_param.fire
- tests/python/parser/test_declarations_coverage.py::test_function_definition_close_paren_missing | REDUNDANT | `fn unclosedParams(x: int32 {` in function_def_syntax_errors.fire
- tests/python/parser/test_declarations_coverage.py::test_generator_definition_borrowed_param | REDUNDANT | tests/sources/generators/generators_borrow_param.fire (run test) uses a `&` generator param; same _parse_function_definition path as any fn
- tests/python/parser/test_declarations_coverage.py::test_generator_definition_missing_close_paren | REDUNDANT | identical code path to close_paren_missing (generators are plain fn); invalid/generators/generator_def_errors.fire
- tests/python/parser/test_declarations_coverage.py::test_generator_definition_missing_body_brace | REDUNDANT | `fn noBody(x: int32) -> void` case in function_def_syntax_errors.fire
- tests/python/parser/test_declarations_coverage.py::test_import_symbol_group_bad_identifier | REDUNDANT | `import utils.{5}` in invalid/imports/import_syntax_errors.fire
- tests/python/parser/test_declarations_coverage.py::test_import_at_missing_identifier_after_at | REDUNDANT | `import @;` in import_syntax_errors.fire
- tests/python/parser/test_declarations_coverage.py::test_import_at_missing_identifier_after_slash | REDUNDANT, WEAK | `import @firescript/;` in import_syntax_errors.fire hits the same lines; the extra 'recovers and returns a node' assertion pins error-recovery shape only
- tests/python/parser/test_declarations_coverage.py::test_import_symbol_missing_after_dot | REDUNDANT | `import utils.!;` and invalid/imports/import_trailing_dot_eof.fire
- tests/python/parser/test_declarations_coverage.py::test_import_symbol_group_missing_close_brace | REDUNDANT | `import utils.{helper` in import_syntax_errors.fire
- tests/python/parser/test_declarations_coverage.py::test_import_module_alias | REDUNDANT | tests/sources/imports/imports_alias.fire (`utils as U`) exercises the same parse; a wrong alias would break the run test
- tests/python/parser/test_declarations_dead_guards.py::test_parse_import_symbol_group_handles_none_from_consume | REDUNDANT, TRIVIAL | dead guard (forced consume None); exact duplicate of _more::test_import_symbol_group_consume_failure_is_dead (same lines declarations.py:713-714)
- tests/python/parser/test_declarations_dead_guards.py::test_parse_class_definition_handles_none_class_consume | REDUNDANT, TRIVIAL | dead guard; duplicate of _more::test_class_definition_missing_class_token_is_dead (both hit declarations.py:981)
- tests/python/parser/test_declarations_dead_guards.py::test_parse_class_definition_handles_none_type_param_consume | INCORRECT, REDUNDANT | claims to force the type-param consume to fail but forces the FIRST consume (the `class` keyword, cursor is on '<'), so it hits declarations.py:981 exactly like the test above and never reaches the type-param guard (line 1005, covered only by _more::...type_param_consume_failure_is_dead)
- tests/python/parser/test_declarations_dead_guards.py::test_parse_constraint_declaration_handles_none_constraint_consume | TRIVIAL | dead guard (declarations.py:919); asserts only `result is None`
- tests/python/parser/test_declarations_dead_guards_more.py::test_function_definition_type_param_consume_failure_is_dead_but_guarded | TRIVIAL | dead guard declarations.py:59; asserts only None
- tests/python/parser/test_declarations_dead_guards_more.py::test_top_level_skips_blank_placeholder_identifier_token | TRIVIAL | covers a branch for blank IDENTIFIER tokens the real lexer can never emit (lexer.py skips whitespace and IDENTIFIER regex needs >=1 char)
- tests/python/parser/test_declarations_dead_guards_more.py::test_export_pending_flag_before_constraint_dispatch_is_dead | WEAK | hand-sets _pending_export; asserts only len(errors)>=1 so any error passes (does not check the 'Constraint exports are not supported' message/code)
- tests/python/parser/test_declarations_dead_guards_more.py::test_import_symbol_group_consume_failure_is_dead | REDUNDANT, TRIVIAL | dup of declarations_dead_guards::test_parse_import_symbol_group_handles_none_from_consume
- tests/python/parser/test_declarations_dead_guards_more.py::test_import_at_branch_missing_identifier_after_at_is_dead | TRIVIAL | dead guard declarations.py:755-756; asserts None only
- tests/python/parser/test_declarations_dead_guards_more.py::test_import_at_branch_slash_identifier_consume_failure_is_dead | TRIVIAL | dead guard declarations.py:766-767; asserts exact error list (good) but for an impossible state
- tests/python/parser/test_declarations_dead_guards_more.py::test_class_definition_missing_class_token_is_dead | REDUNDANT, TRIVIAL | dup of declarations_dead_guards::test_parse_class_definition_handles_none_class_consume
- tests/python/parser/test_declarations_dead_guards_more.py::test_class_definition_type_param_consume_failure_is_dead | TRIVIAL | only test reaching declarations.py:1005 (dead guard); asserts None only
- tests/python/parser/test_expressions_dead_guards.py::test_parse_array_literal_without_open_bracket_is_defensive_none | TRIVIAL | dead guard expressions.py:743-744 (callers pre-check '[')
- tests/python/parser/test_expressions_dead_guards.py::test_parse_array_access_without_open_bracket_is_defensive_none | TRIVIAL | dead guard expressions.py:772-773
- tests/python/parser/test_expressions_dead_guards.py::test_parse_match_expression_without_match_token_is_defensive_none | TRIVIAL, WEAK | dead guard expressions.py:622; asserts only None
- tests/python/parser/test_expressions_dead_guards.py::test_parse_compound_assignment_without_identifier_is_defensive_none | TRIVIAL | dead guard expressions.py:805-807
- tests/python/parser/test_expressions_dead_guards.py::test_parse_compound_assignment_wrong_operator_reports_error | TRIVIAL | dead branch expressions.py:839-843 (statement dispatcher pre-checks operator)
- tests/python/parser/test_expressions_dead_guards.py::test_parse_increment_or_decrement_without_identifier_is_defensive_none | TRIVIAL | dead guard expressions.py:849-851
- tests/python/parser/test_expressions_dead_guards.py::test_parse_increment_or_decrement_wrong_operator_reports_error | TRIVIAL, REDUNDANT | same shape as compound_assignment_wrong_operator test
- tests/python/parser/test_parser_base.py::test_field_not_found_error_records_error | TRIVIAL, WEAK | helper has NO production callers (grep); asserts len(errors)==1 only; mutant swapping FieldNotFoundError->MethodNotFoundError SURVIVED
- tests/python/parser/test_parser_base.py::test_method_not_found_error_records_error | TRIVIAL | helper has no production callers; len==1 only
- tests/python/parser/test_parser_base.py::test_constructor_not_found_error_records_error | TRIVIAL | helper has no production callers; len==1 only
- tests/python/parser/test_parser_base.py::test_invalid_operator_error_records_error | TRIVIAL | helper has no production callers; len==1 only
- tests/python/parser/test_parser_base.py::test_control_flow_error_records_error | TRIVIAL | helper has no production callers; len==1 only
- tests/python/parser/test_parser_base.py::test_invalid_super_error_records_error | TRIVIAL | helper has no production callers; len==1 only
- tests/python/parser/test_parser_base.py::test_undefined_identifier_error_records_error | TRIVIAL, REDUNDANT | helper used in 4 places, all hit by invalid/*.fire (FS-PARSE-0003 annotations); len==1 only
- tests/python/parser/test_parser_base.py::test_missing_identifier_error_records_error | TRIVIAL | helper has no production callers; len==1 only
- tests/python/parser/test_parser_base.py::test_invalid_array_access_error_records_error | TRIVIAL, REDUNDANT | one real caller (expressions.py:782) covered by invalid/arrays; len==1 only
- tests/python/parser/test_parser_base.py::test_expect_records_unexpected_token_error | TRIVIAL | ParserBase.expect() has NO callers anywhere (grep); weak assertion (1 error); delete with the method
- tests/python/parser/test_parser_base.py::test_expect_succeeds_and_advances | TRIVIAL | tests dead method expect() (mutation killed, but method is unused)
- tests/python/parser/test_parser_base.py::test_expect_returns_none_at_eof | TRIVIAL | dead method expect()
- tests/python/parser/test_parser_base.py::test_skip_comment_at_eof_is_noop | WEAK | asserts current_token None after _skip_comment at EOF; no plausible bug
- tests/python/parser/test_parser_base.py::test_parser_base_parse_expression_is_not_implemented | TRIVIAL | pins an abstract-method raise; Parser always overrides it
- tests/python/parser/test_parser_base.py::test_invalid_field_access_error_records_error | TRIVIAL | helper has no production callers
- tests/python/parser/test_parser_base.py::test_bare_error_method_records_error | TRIVIAL | ParserBase.error() has no production callers; len==1 only (mutant replacing message SURVIVED)
- tests/python/parser/test_parser_base.py::test_type_error_and_invalid_type_error_record_errors | TRIVIAL, REDUNDANT | invalid_type_error has 61 callers (covered by invalid/types/*.fire); asserts count 2 only
- tests/python/parser/test_parser_base.py::test_advance_skips_whitespace_placeholder_tokens | TRIVIAL | tests branch for blank IDENTIFIER tokens the real lexer never emits
- tests/python/parser/test_parser_base.py::test_peek_skips_whitespace_placeholder_tokens | TRIVIAL | same: unreachable scaffolding
- tests/python/parser/test_parser_base.py::test_skip_ws_from_skips_placeholder_tokens | TRIVIAL | same: unreachable scaffolding
- tests/python/parser/test_parser_base.py::test_parse_statement_dot_dispatch_handles_none_from_parse_primary | REDUNDANT, TRIVIAL | dead guard statements.py:574; exact duplicate of statements_dead_guards::test_parse_statement_dot_lhs_none_is_defensive
- tests/python/parser/test_parser_base.py::test_parse_statement_directive_without_declarations_mixin_errors | REDUNDANT | dup of statements_dead_guards::test_parse_statement_directive_without_declarations_mixin (this one additionally checks message text)
- tests/python/parser/test_parser_base.py::test_parse_scope_without_open_brace_records_error | REDUNDANT | dup of statements_dead_guards::test_parse_scope_missing_open_brace_is_defensive
- tests/python/parser/test_parser_base.py::test_recover_to_statement_boundary_stops_at_semicolon | TRIVIAL | _recover_to_statement_boundary has no callers (grep); tests are correct but guard dead code
- tests/python/parser/test_parser_base.py::test_recover_to_statement_boundary_stops_at_close_brace | TRIVIAL | same: dead method
- tests/python/parser/test_parser_base.py::test_recover_to_statement_boundary_stops_at_strong_starter | TRIVIAL | same: dead method (mutation-killed but irrelevant)
- tests/python/parser/test_parser_base.py::test_recover_to_statement_boundary_runs_to_eof | TRIVIAL | same: dead method
- tests/python/parser/test_statements_dead_guards.py::test_parse_if_statement_returns_none_when_not_at_if_token | TRIVIAL | dead guard statements.py:29
- tests/python/parser/test_statements_dead_guards.py::test_parse_while_statement_returns_none_when_not_at_while_token | TRIVIAL | dead guard statements.py:228
- tests/python/parser/test_statements_dead_guards.py::test_parse_for_statement_returns_none_when_not_at_for_token | TRIVIAL | dead guard statements.py:268
- tests/python/parser/test_statements_dead_guards.py::test_if_statement_condition_none_with_close_paren_still_present | TRIVIAL | monkeypatches parse_expression to None; mutation-verified but pins recovery for an impossible state
- tests/python/parser/test_statements_dead_guards.py::test_while_statement_condition_none_with_close_paren_still_present | TRIVIAL | same, while version
- tests/python/parser/test_statements_dead_guards.py::test_if_statement_then_branch_none_is_defensive | WEAK | monkeypatched parse_scope; asserts len(errors)>=1 (any error)
- tests/python/parser/test_statements_dead_guards.py::test_while_statement_body_none_is_defensive | TRIVIAL | dead guard statements.py:247; asserts None only
- tests/python/parser/test_statements_dead_guards.py::test_for_in_statement_body_none_is_defensive | TRIVIAL | dead guard statements.py:307
- tests/python/parser/test_statements_dead_guards.py::test_for_c_style_statement_body_none_is_defensive | TRIVIAL | dead guard statements.py:391
- tests/python/parser/test_statements_dead_guards.py::test_parse_variable_assignment_identifier_none_is_defensive | TRIVIAL | dead guard statements.py:152-154
- tests/python/parser/test_statements_dead_guards.py::test_parse_variable_assignment_missing_assign_is_defensive | TRIVIAL | dead guard statements.py:158-160
- tests/python/parser/test_statements_dead_guards.py::test_parse_function_call_missing_name_is_defensive | TRIVIAL | dead guard statements.py:184-186
- tests/python/parser/test_statements_dead_guards.py::test_parse_function_call_missing_open_paren_is_defensive | TRIVIAL | dead guard statements.py:190-192
- tests/python/parser/test_statements_dead_guards.py::test_parse_statement_dot_lhs_none_is_defensive | TRIVIAL | dead guard statements.py:574 (same as parser_base dup)
- tests/python/parser/test_statements_dead_guards.py::test_parse_scope_missing_open_brace_is_defensive | TRIVIAL | dead guard statements.py:647-648 (dup of parser_base)
- tests/python/parser/test_statements_dead_guards.py::test_parse_statement_directive_without_declarations_mixin | TRIVIAL | tests a stripped-down StatementsMixin-only parser that is never constructed in production
- tests/python/parser/test_type_system.py::test_annotate_value_category_swallows_exception | REDUNDANT | one of THREE copies of the same test (also dead_guards.py and dead_guards_more.py); keep exactly one. Note it pins a bare `except Exception: pass` that hides real bugs
- tests/python/parser/test_type_system_dead_guards.py::test_get_node_type_literal_fallback_infers_from_token_type | REDUNDANT | dead fallback; duplicate (subset: 4 of 6 types) of _more::test_get_node_type_literal_fallback_is_dead
- tests/python/parser/test_type_system_dead_guards.py::test_get_node_type_function_call_array_suffix_is_unreachable_via_type_check_node | REDUNDANT, WEAK | dup of _more::..function_call_array_fallback_is_dead; mutant removing the whole array-suffix trim is EQUIVALENT (the [] is re-appended), so the branch is no-op code
- tests/python/parser/test_type_system_dead_guards.py::test_get_node_type_method_call_array_suffix | INCORRECT, REDUNDANT | docstring claims class methods cannot return arrays: FALSE today (verified `fn all(&this) -> int32[]` compiles). dup of _more::..method_call_array_fallback_is_dead
- tests/python/parser/test_type_system_dead_guards.py::test_get_node_type_super_call_is_unreachable_via_type_check_node | REDUNDANT | dup of _more::..super_call_fallback_is_dead
- tests/python/parser/test_type_system_dead_guards.py::test_annotate_value_category_swallows_exceptions | TRIVIAL | ends with `t.require(True)` - tautology; also dup of two other tests
- tests/python/parser/test_type_system_dead_guards.py::test_infer_generic_type_args_unknown_function_returns_none | REDUNDANT | dup of _more::..name_not_generic_is_defensive
- tests/python/parser/test_type_system_dead_guards.py::test_infer_generic_type_args_empty_type_params_returns_empty_list | REDUNDANT | dup of _more::..empty_type_params_is_defensive
- tests/python/parser/test_type_system_dead_guards.py::test_infer_generic_type_args_missing_function_def_returns_none | REDUNDANT | dup of _more::..missing_function_definition_is_defensive
- tests/python/parser/test_type_system_dead_guards.py::test_cast_to_array_type_is_rejected | REDUNDANT | dead branch (parser cannot produce `as int32[]`; verified it is a parse error); dup of _more::test_cast_to_array_type_is_defensive (this one is the stronger copy: asserts FS-SEM-0010)
- tests/python/parser/test_type_system_dead_guards.py::test_function_call_return_type_already_always_set_by_parser | TRIVIAL | constructs an ASTNode and asserts hasattr(node,'return_type'): tests the constructor, not the compiler
- tests/python/parser/test_type_system_dead_guards_more.py::test_annotate_value_category_swallows_exceptions | REDUNDANT | 3rd copy
- tests/python/parser/test_type_system_dead_guards_more.py::test_get_node_type_literal_fallback_is_dead | TRIVIAL | dead fallback (every real LITERAL has return_type); keep this superset copy only if the fallback is kept
- tests/python/parser/test_type_system_dead_guards_more.py::test_get_node_type_array_literal_element_node_none_is_defensive | TRIVIAL | bypasses ASTNode's own None-child guard to reach a dead branch
- tests/python/parser/test_type_system_dead_guards_more.py::test_get_node_type_function_call_array_fallback_is_dead | TRIVIAL | dead; equivalent-mutant branch
- tests/python/parser/test_type_system_dead_guards_more.py::test_get_node_type_super_call_fallback_is_dead | TRIVIAL | dead
- tests/python/parser/test_type_system_dead_guards_more.py::test_get_node_type_method_call_array_fallback_is_dead | INCORRECT | comment 'class methods can't be declared with an array return type' is stale/false (verified)
- tests/python/parser/test_type_system_dead_guards_more.py::test_function_call_return_type_fallback_assignment_is_dead | INCORRECT | `del node.return_type` then asserts the buggy outcome; its own comment admits it pins a latent authoring bug (`not hasattr(node,'return_type')` is never True because ASTNode always sets return_type=None). It asserts incorrect behavior rather than flagging it
- tests/python/parser/test_type_system_dead_guards_more.py::test_get_node_type_array_access_child_none_is_defensive | TRIVIAL | dead guard; bypasses ASTNode None-guard
- tests/python/parser/test_type_system_dead_guards_more.py::test_infer_generic_type_args_name_not_generic_is_defensive | TRIVIAL | dead guard type_system.py:297
- tests/python/parser/test_type_system_dead_guards_more.py::test_infer_generic_type_args_empty_type_params_is_defensive | TRIVIAL | dead guard type_system.py:301
- tests/python/parser/test_type_system_dead_guards_more.py::test_infer_generic_type_args_missing_function_definition_is_defensive | TRIVIAL | dead guard type_system.py:311
- tests/python/parser/test_type_system_dead_guards_more.py::test_unary_missing_operand_is_defensive | TRIVIAL | dead guard type_system.py:661-662
- tests/python/parser/test_type_system_dead_guards_more.py::test_unary_unsupported_operator_is_defensive | TRIVIAL | dead branch type_system.py:695-696 (parser only builds + - ! ++ --)
- tests/python/parser/test_type_system_dead_guards_more.py::test_binary_unsupported_operator_is_defensive | TRIVIAL | dead branch type_system.py:635; no assertion on the error emitted
- tests/python/parser/test_type_system_dead_guards_more.py::test_cast_to_array_type_is_defensive | REDUNDANT | weaker dup (asserts None only) of dead_guards::test_cast_to_array_type_is_rejected
- tests/python/parser/test_type_system_dead_guards_more.py::test_function_call_expected_arg_types_loop_is_defensive | TRIVIAL | body is `t.require(True)` - literally a tautology; documents dead code in a test
- tests/python/parser/test_type_system_dead_guards_more.py::test_super_call_no_enclosing_class_is_defensive | TRIVIAL | dead guard type_system.py:1037-1038
- tests/python/parser/test_type_system_dead_guards_more.py::test_super_call_not_in_constructor_is_defensive | TRIVIAL | dead guard type_system.py:1044-1045
- tests/python/lexer/test_lexer_internals.py::test_tokenize_handles_successful_match_with_no_named_group | TRIVIAL | swaps the compiled regex for a fake to reach lexer.py:184-186, a branch that cannot occur (every alternative is a named group). Contradicts CLAUDE.md ('defensive or unreachable lines don't need contrived tests'). NOTE: tests/python/lexer has no real lexer test at all
- tests/python/preprocessor/test_preprocessor_internals.py::test_collect_identifier_names_none_returns_empty_set | TRIVIAL, INCORRECT | name says returns empty set; body only runs enable_and_insert_drops on `return;` and asserts nothing ('must not raise'); never calls _collect_identifier_names
- tests/python/preprocessor/test_preprocessor_internals.py::test_return_transferred_identifiers_walk_none_receiver | TRIVIAL | no assertion; targets an impossible METHOD_CALL-with-no-children
- tests/python/preprocessor/test_preprocessor_internals.py::test_break_outside_loop_drains_innermost_scope_fallback | TRIVIAL | assertion is `any(...) or True` (tautology). mutant making the fallback drain nothing SURVIVED
- tests/python/preprocessor/test_preprocessor_internals.py::test_continue_outside_loop_drains_innermost_scope_fallback | TRIVIAL | no assertion
- tests/python/semantic/test_semantic_analyzer_internals.py::test_borrow_info_stores_fields | TRIVIAL | constructs BorrowInfo and checks its constructor assigned fields
- tests/python/semantic/test_semantic_analyzer_internals.py::test_error_convenience_method | TRIVIAL | error() wrapper; message-in-message only
- tests/python/semantic/test_semantic_analyzer_internals.py::test_is_direct_borrow_view_false_for_unrelated_node_type | REDUNDANT | no unique line; fallthrough `return False` hit by every borrow .fire test
- tests/python/semantic/test_semantic_analyzer_internals.py::test_collect_function_signatures_none_is_noop | TRIVIAL | asserts signatures == {} after passing None
- tests/python/semantic/test_semantic_analyzer_report_error.py::test_report_error_without_node_uses_no_line_info | REDUNDANT | dup of internals::test_report_error_without_node_appends_directly
- tests/python/semantic/test_semantic_analyzer_report_error.py::test_report_error_index_out_of_range_falls_back_gracefully | WEAK, REDUNDANT | name says falls back gracefully; asserts source_file but error() pre-fills it so mutant removing the fallback default SURVIVED (only internals variant catches it). Only the count check kills the 'append' mutant
- tests/python/semantic/test_semantic_analyzer_report_error.py::test_report_error_negative_index_falls_back_gracefully | WEAK, REDUNDANT | asserts len==1 only; same except-branch as previous
- tests/python/imports/test_module_resolver.py::test_default_import_root_is_project_root | REDUNDANT, WEAK | dup of _extra::test_default_import_root_defaults_to_project_root; both recompute the implementation's own formula
- tests/python/imports/test_module_resolver.py::test_dotted_to_path_stdlib_missing_returns_init_path | REDUNDANT | dup of _extra::..fallback_when_neither_form_exists
- tests/python/imports/test_module_resolver.py::test_path_to_dotted_outside_root_uses_basename | REDUNDANT | dup of _extra::..outside_import_root_uses_basename
- tests/python/imports/test_module_resolver.py::test_parse_file_missing_file_raises_file_not_found | REDUNDANT | dup of _extra
- tests/python/imports/test_module_resolver.py::test_parse_file_with_syntax_error_raises_runtime_error | REDUNDANT | dup of _extra
- tests/python/imports/test_module_resolver.py::test_load_module_cyclic_import_raises_runtime_error | INCORRECT, REDUNDANT | tests a branch that real recursion can never reach (docstring says so). Cyclic-import detection is DEAD while docs/reference/imports.md:159 marks it [IMPLEMENTED] (compiler bug #1). Dup of _extra::test_cycle_detection_branch...
- tests/python/imports/test_module_resolver.py::test_load_module_external_import_rejected | REDUNDANT | dup of _extra::..external_import_raises, but uses deep global monkeypatching (os.path.isfile, Module.__post_init__, ModuleResolver.parse_file) - the _extra version injects an AST via an instance attribute only
- tests/python/imports/test_module_resolver.py::test_load_module_relative_import_rejected | REDUNDANT | dup of _extra (same reason)
- tests/python/imports/test_module_resolver.py::test_load_module_not_found_raises_file_not_found | REDUNDANT | dup of _extra::..import_not_found_raises_file_not_found and tests/python/cli/test_imports.py::test_import_not_found_compile
- tests/python/imports/test_module_resolver.py::test_resolve_for_entry_skips_external_in_topo_visit | INCORRECT, TRIVIAL | name/comment claim an external import is skipped in the topo visit but the entry has no imports at all; asserts dotted=='entry' and len(topo)>=1
- tests/python/imports/test_module_resolver.py::test_build_merged_ast_skips_export_with_no_name | INCORRECT, REDUNDANT | claims to test append_export's empty-name guard, but exports[''] is dropped earlier at append_symbol_with_deps `node is None` (imports.py:352), the same line as _extra::test_append_symbol_with_deps_node_none_...; _extra's own NOTE says the empty-name guard is unreachable
- tests/python/imports/test_module_resolver.py::test_build_merged_ast_conflicting_import_symbols_first_wins | REDUNDANT | dup of _extra::test_append_export_skips_duplicate_symbol_name_across_modules; both mutation-killed. NOTE: pins behavior where the conflict is only LOGGED and compile succeeds (bug #2)
- tests/python/imports/test_module_resolver.py::test_build_merged_ast_entry_conflict_value_error_fallback_is_exercised | INCORRECT | docstring: 'exercised here purely to cover the ValueError branch, not to assert it is correct' and the asserted outcome (entry def silently dropped, imported one wins) is the OPPOSITE of the 'Prefer entry's definition' comment in imports.py:392. Patches ASTNode.__init__ globally. Pins a bug
- tests/python/imports/test_module_resolver_extra.py::test_resolve_for_entry_topo_sort_skips_external_kind_modules | WEAK, TRIVIAL | mutation-verified EQUIVALENT: replacing the `continue` with `pass` at imports.py:234 passes all 32 tests (the later `if dep in self.modules` already filters). The guarded branch is no-op code and this test cannot fail

### MERGE-candidate

- tests/python/parser/test_declarations_coverage.py::test_function_definition_rejects_missing_name | KEEP | lines declarations.py:379-380 reached by NO .fire test (verified `fn + () -> int32` is reachable via normal parse); move into function_def_syntax_errors.fire as //~ annotation and delete
- tests/python/parser/test_declarations_coverage.py::test_function_definition_missing_open_paren | KEEP | lines declarations.py:388-389 reached by no .fire test (verified reachable: `fn foo {}`); convert to //~ line in function_def_syntax_errors.fire
- tests/python/parser/test_parser_base.py::test_infer_literal_type_integer_no_suffix_defaults_int32 | KEEP | merge the 6 _infer_literal_type tests into one @t.params table
- tests/python/parser/test_parser_base.py::test_infer_literal_type_float_suffixes | KEEP | merge into one table
- tests/python/parser/test_parser_base.py::test_infer_literal_type_float_no_suffix_defaults_float32 | KEEP | mutation-verified (float32 default flipped -> fails); merge into table
- tests/python/parser/test_parser_base.py::test_infer_literal_type_double_literal_is_float64 | KEEP | merge into table
- tests/python/parser/test_parser_base.py::test_infer_literal_type_unknown_token_type_returns_empty | KEEP | merge into table
- tests/python/parser/test_parser_base.py::test_is_type_token_none_returns_false | KEEP | merge with previous
- tests/python/parser/test_parser_base.py::test_advance_at_eof_is_noop | WEAK | merge the four EOF tests (advance/peek/_current_token_index/consume_name at EOF) into one
- tests/python/parser/test_parser_base.py::test_peek_returns_none_at_eof | WEAK | see above
- tests/python/parser/test_parser_base.py::test_current_token_index_is_minus_one_at_eof | WEAK | see above
- tests/python/parser/test_parser_base.py::test_consume_name_returns_none_at_eof | WEAK | see above
- tests/python/parser/test_parser_base.py::test_looks_like_generic_constructor_call_false_when_not_less_than | KEEP | merge the 3 into one parametrized negative-case test
- tests/python/parser/test_parser_base.py::test_looks_like_generic_constructor_call_false_when_no_open_paren | KEEP | merge; only one with real lookahead; no POSITIVE-case test exists (bug: a '<T>(' true case is untested at unit level)
- tests/python/parser/test_parser_base.py::test_looks_like_generic_constructor_call_false_at_eof | KEEP | merge
- tests/python/preprocessor/test_preprocessor_internals.py::test_collect_directive_true_when_already_present | REDUNDANT | covered by next test (a wrong return would produce a duplicate directive there)
- tests/python/semantic/test_semantic_analyzer_internals.py::test_report_error_without_node_appends_directly | REDUNDANT | duplicates report_error.py::test_report_error_without_node_uses_no_line_info; keep one (this one checks source_file)
- tests/python/semantic/test_semantic_analyzer_internals.py::test_expr_is_owned_value_false_for_non_identifier_no_return_type | KEEP | merge with the other False case
- tests/python/semantic/test_semantic_analyzer_internals.py::test_merge_state_pair_both_movedish_yields_moved | WEAK | merge the 3 into one params truth table; the table omits the (MOVED,VALID)->MAYBE_MOVED row: mutant returning MOVED instead SURVIVED (22/22 pass)
- tests/python/semantic/test_semantic_analyzer_internals.py::test_merge_state_pair_borrowed_wins | WEAK | see above
- tests/python/semantic/test_semantic_analyzer_internals.py::test_merge_state_pair_default_valid | WEAK | see above
- tests/python/semantic/test_semantic_analyzer_internals.py::test_analyze_node_none_is_noop | WEAK | merge the 'no children -> return' guards (method_call/if/match/while/none) into one params test
- tests/python/semantic/test_semantic_analyzer_internals.py::test_analyze_node_method_call_no_children_returns_early | KEEP | mutation-verified (guard removal -> IndexError) though only asserts no raise
- tests/python/semantic/test_semantic_analyzer_internals.py::test_analyze_node_if_statement_no_children_returns_early | WEAK | no assertion; merge
- tests/python/semantic/test_semantic_analyzer_internals.py::test_analyze_node_match_expression_no_children_returns_early | WEAK | no assertion; merge
- tests/python/semantic/test_semantic_analyzer_internals.py::test_analyze_node_while_statement_no_children_returns_early | WEAK | no assertion; merge
- tests/python/semantic/test_semantic_analyzer_report_error.py::test_report_error_without_source_code_uses_no_line_info | KEEP | asserts line==0; only distinct case (source_code=None)

### FIX-ASSERTION

- tests/python/parser/test_parser_base.py::test_report_error_with_no_token_anchors_after_last_real_token | WEAK, REDUNDANT | asserts only line>0; mutant `index = 0` (anchor at file start) SURVIVED. Line-anchoring at EOF is pinned by .fire //~ annotations (e.g. invalid/imports/import_trailing_dot_eof.fire). If kept, assert the exact line/column
- tests/python/parser/test_statements_coverage.py::test_array_access_as_bare_statement_parses | KEEP, PINS-BUG | asserts the parser accepts `arr[0];` but the compiler then crashes in AST->FIR with an internal 'Unsupported statement node ARRAY_ACCESS' + traceback (verified). Either reject at parse time or lower it; add tests/sources known_issue
- tests/python/parser/test_statements_coverage.py::test_nested_directive_inside_function_parses | KEEP, PINS-BUG | asserts a `directive x;` inside a function body parses; compile then fails 'Unsupported statement node DIRECTIVE' (verified). Same remedy
- tests/python/parser/test_statements_coverage.py::test_generic_class_nested_type_argument_parses | KEEP, PINS-BUG | comment about nested generic FLIR bug is still TRUE (verified FLIRV-T4 on Pair<Pair<int32,int32>,int32>); the bug has no known_issues test
- tests/python/parser/test_type_system_coverage.py::test_method_call_deferred_lookup_for_composite_generic_type | WEAK, REDUNDANT | assertions (None + no errors) are fine, but deferred composite-generic method calls are exercised end-to-end by every std.types Option/Result import (zero unique lines). Keep only if you want a fast unit probe
- tests/python/preprocessor/test_preprocessor_internals.py::test_mentions_var_false_when_absent | WEAK, REDUNDANT | no line unique (run tests exercise drop insertion); does not cover child recursion, so a mutant dropping the recursion would survive
- tests/python/preprocessor/test_preprocessor_internals.py::test_mentions_var_true_direct_identifier | WEAK, REDUNDANT | same: only the direct-identifier case, not the recursive one
- tests/python/preprocessor/test_preprocessor_internals.py::test_return_function_call_with_borrow_flags_marks_transferred_arg | WEAK | no assertion. Mutant `transferred.add(arg.name)`->`pass` in the FUNCTION_CALL branch SURVIVED (14/14 pass). Should assert str_var is not dropped after `return consume(str_var)`
- tests/python/preprocessor/test_preprocessor_internals.py::test_return_constructor_call_with_borrow_flags_marks_transferred_arg | WEAK | no assertion; both mutants (never record / inverted borrowed flag) in the CONSTRUCTOR_CALL branch SURVIVED
- tests/python/preprocessor/test_preprocessor_internals.py::test_implicit_declaration_from_method_call_on_constructor_receiver | WEAK | no assertion; mutant `inferred_class = None` SURVIVED. Should assert a drop(v1) was inserted
- tests/python/preprocessor/test_preprocessor_internals.py::test_implicit_declaration_from_method_call_on_identifier_receiver | WEAK | same mutant SURVIVED
- tests/python/semantic/test_semantic_analyzer_internals.py::test_expr_is_owned_value_array_return_type | WEAK | NO assertion (just `analyzer._expr_is_owned_value(node)`); mutant replacing the array branch with `return False` SURVIVED. Assert True for Box[]
- tests/python/semantic/test_semantic_analyzer_internals.py::test_analyze_node_elif_else_recurse_into_children | WEAK | asserts nothing about recursion ('must not raise'); a mutant skipping recursion passes
- tests/python/imports/test_module_resolver.py::test_build_merged_ast_entry_symbol_replaces_imported_one | KEEP, PINS-BUG | asserts entry def replaces imported one, but production only logs an 'error' and the compile succeeds (bug #2); decide intended semantics, then make it a compile-fail/ warning .fire
- tests/python/imports/test_module_resolver_extra.py::test_default_import_root_defaults_to_project_root | WEAK | keep one of the two copies; tautological formula copy
- tests/python/imports/test_module_resolver_extra.py::test_cycle_detection_branch_is_unreachable_via_real_recursion_but_direct_call_hits_it | INCORRECT | self-documents that the cycle branch is dead for real cycles; the test passes while real cycles are NOT detected. Replace by a test that a real A<->B cycle yields FS-IMP-0002 (currently fails: bug #1) in tests/sources/invalid/known_issues
- tests/python/imports/test_module_resolver_extra.py::test_append_symbol_with_deps_skips_node_already_emitted | WEAK | mutant disabling the `emitted_for_module` guard SURVIVED (append_export's `seen` dedup hides it; only a logging.error differs). Assert no 'Conflicting top-level symbol' log

### KEEP

- tests/python/parser/test_ast_node.py::test_constructor_rejects_none_in_children | KEEP | only test of ASTNode's None-children guard (ast_node.py:31-35 unique to it); message check 'None' is weak but the ValueError is the contract
- tests/python/parser/test_declarations_coverage.py::test_function_definition_owned_array_param | KEEP | only test of `owned xs: int32[]` param parse; asserts is_owned+is_array (no .fire has owned array params)
- tests/python/parser/test_generic_self_reference.py::test_static_factory_returning_enclosing_generic_class_no_imports | KEEP | mutation-verified: neutering _current_generic_class_name assignment (declarations.py:1020) makes it fail
- tests/python/parser/test_generic_self_reference.py::test_self_call_inside_generic_class_no_imports | KEEP | mutation-verified: removing type_system.py:449 assignment makes it fail
- tests/python/parser/test_generic_self_reference.py::test_explicit_type_arg_static_call_on_enclosing_class_no_imports | KEEP | mutation-verified (declarations.py:1020)
- tests/python/parser/test_parser_base.py::test_report_error_skips_trailing_multiline_comment_block | KEEP | mutation-verified (skip of MULTI_LINE_COMMENT_END -> line 4 instead of 1 fails); lines base.py:576-580 reached by no other test
- tests/python/parser/test_parser_base.py::test_consume_name_accepts_as_and_owned_keywords | KEEP | asserts the exact token types for AS/OWNED-as-names
- tests/python/parser/test_parser_base.py::test_infer_literal_type_integer_suffixes | KEEP | table covers all 8 suffixes with exact type; precise and cheap
- tests/python/parser/test_parser_base.py::test_is_type_token_recognizes_registered_user_type | KEEP | small, exact
- tests/python/parser/test_parser_base.py::test_scan_matching_gt_returns_minus_one_at_eof_without_boundary | KEEP | mutation-verified (return 0 at EOF fails)
- tests/python/parser/test_parser_base.py::test_constructor_with_borrowed_and_owned_regular_params_parses | KEEP | parse-level only, but the full program triggers a REAL compiler bug (see bugs section #3); should be paired with a known_issues .fire
- tests/python/parser/test_parser_base.py::test_last_non_comment_token_returns_none_when_all_comments | KEEP | exact None contract on a live helper; unique line base.py:585
- tests/python/parser/test_parser_base.py::test_report_error_comment_token_at_eof_falls_back_to_last_token_index | KEEP | unique lines base.py:603; asserts only line>0 (WEAK assertion, strengthen to exact line)
- tests/python/parser/test_parser_base.py::test_report_error_sets_source_file_when_missing | KEEP | asserts the filename fallback
- tests/python/parser/test_parser_base.py::test_report_error_swallows_position_lookup_exception | KEEP | mutation-verified (narrowing the except fails)
- tests/python/parser/test_type_system.py::test_annotate_value_category_owned | KEEP | exact 'Owned' assertion
- tests/python/parser/test_type_system.py::test_annotate_value_category_copyable | KEEP | exact 'Copyable' assertion
- tests/python/preprocessor/test_preprocessor_internals.py::test_enable_and_insert_drops_does_not_duplicate_existing_directive | KEEP | asserts count==1
- tests/python/preprocessor/test_preprocessor_internals.py::test_is_drop_call_matches_var_name | KEEP | asserts both True and False
- tests/python/preprocessor/test_preprocessor_internals.py::test_for_loop_with_none_clause_preserved | KEEP | mutation-verified (dropping None clause -> 3 != 4 fails)
- tests/python/semantic/test_semantic_analyzer_internals.py::test_report_error_with_out_of_range_node_falls_back | KEEP | mutation-verified: dropping the source_file default in the except branch fails ONLY this test; the report_error.py variants miss it
- tests/python/semantic/test_semantic_analyzer_internals.py::test_expr_is_owned_value_false_for_no_binding_no_return_type | KEEP | exact False; only test of semantic_analyzer.py:310 outside .fire
- tests/python/semantic/test_semantic_analyzer_internals.py::test_definitely_terminates_false_for_unrelated_node | KEEP | mutation-verified (default True fails)
- tests/python/semantic/test_semantic_analyzer_internals.py::test_validate_match_arms_empty_arms_reports_error | KEEP | asserts 1 error with message; reachability from source unverified (parser may reject empty match first)
- tests/python/semantic/test_semantic_analyzer_internals.py::test_validate_match_arms_enum_mismatch_and_unknown_enum | KEEP | mutation-verified (inverted != fails). These branches ARE reachable from real source (verified `match c { Color.Red -> .. Shape.Circle -> .. Unknown.X -> .. }`) yet no .fire compile-fail test covers them: add invalid/match fixture
- tests/python/semantic/test_semantic_analyzer_internals.py::test_validate_borrow_reports_error_for_copyable_type | KEEP | mutation-verified; reachable from source (`fn f(&x: int32)`, verified) but NO invalid .fire asserts 'Cannot borrow Copyable type' -> add invalid/borrow fixture
- tests/python/imports/test_module_resolver.py::test_stdlib_package_for_regular_file_strips_last_component | KEEP | only direct test of non-init stdlib package stripping
- tests/python/imports/test_module_resolver.py::test_stdlib_package_for_non_stdlib_returns_none | KEEP | only direct test of the None return
- tests/python/imports/test_module_resolver_extra.py::test_dotted_to_path_stdlib_fallback_when_neither_form_exists | KEEP | keep this copy
- tests/python/imports/test_module_resolver_extra.py::test_path_to_dotted_outside_import_root_uses_basename | KEEP | keep this copy
- tests/python/imports/test_module_resolver_extra.py::test_parse_file_missing_file_raises_file_not_found | KEEP | keep this copy
- tests/python/imports/test_module_resolver_extra.py::test_parse_file_with_syntax_error_raises_runtime_error | KEEP | keep this copy
- tests/python/imports/test_module_resolver_extra.py::test_load_module_external_import_raises | KEEP | keep this copy: good explanation of why the parser pre-empts the guard
- tests/python/imports/test_module_resolver_extra.py::test_load_module_relative_import_raises | KEEP | keep this copy
- tests/python/imports/test_module_resolver_extra.py::test_load_module_import_not_found_raises_file_not_found | KEEP | keep (real file tree, no patching)
- tests/python/imports/test_module_resolver_extra.py::test_stdlib_sibling_relative_import_resolves_within_package | KEEP | only test of sibling-relative stdlib import resolution (imports.py:205-208; no stdlib module or .fire uses it)
- tests/python/imports/test_module_resolver_extra.py::test_build_merged_ast_skips_source_read_failure_silently | KEEP | asserts the swallow (no crash) - fine, low value
- tests/python/imports/test_module_resolver_extra.py::test_append_export_skips_duplicate_symbol_name_across_modules | KEEP | mutation-verified; the better copy of the dup pair
- tests/python/imports/test_module_resolver_extra.py::test_append_symbol_with_deps_node_none_when_export_missing_from_top_level | KEEP | only test of imports.py:352
- tests/python/imports/test_module_resolver_extra.py::test_mutual_recursion_hits_resolving_guard | KEEP | mutation-verified (guard removal -> RecursionError)

## Detailed evidence for INCORRECT and WEAK findings

Mutation harness: `rsync -a --exclude .git --exclude build repo/ $W/mut/`; mutate one line; `FIRESCRIPT_TEST_TARGET=windows/x86_64 FIRESCRIPT_TEST_RUN_PREFIX=wine WINEDEBUG=-all python tests/run.py <path> --no-coverage`. Baseline of every file was green before mutating.

| # | Mutation (file:line) | Test file run | Result |
|---|---|---|---|
| M1 | preprocessor.py:473 `inferred_class = method_return_types.get(...)` -> `None` | test_preprocessor_internals.py | 14/14 PASS (survived): both implicit-declaration tests WEAK |
| M2b | preprocessor.py:288 `transferred.add(arg.name)` -> `pass` (FUNCTION_CALL branch) | same | survived: return_function_call... WEAK |
| M2c | preprocessor.py:296 same in CONSTRUCTOR_CALL branch; also inverted `borrowed` flag (294) | same | survived: return_constructor_call... WEAK |
| M3 | preprocessor.py:708 fallback drain `append(...)` -> `pass` | same | survived: break/continue fallback tests TRIVIAL (`or True`) |
| M4 | preprocessor.py:723 `new_children.append(None)` -> `pass` | same | killed (3 != 4): for_loop_with_none_clause KEEP |
| M5a | base.py:649 field_not_found_error raises MethodNotFoundError instead | test_parser_base.py | 51/51 PASS (survived) |
| M5c | base.py:625 error() message blanked | same | survived |
| M5d/e | base.py:539/553 expect() mutated | same | killed (but expect() has no callers) |
| M10b | base.py:573 block-comment skip disabled | same | killed (line 4 != 1): KEEP |
| M11 | base.py:617 `except Exception` -> narrower | same | killed: KEEP |
| M12 | base.py:446 `return -1` -> `return 0` | same | killed: KEEP |
| M13 | base.py:730 strong-starter break disabled | same | killed (dead method) |
| M14 | base.py:860 float default -> float64 | same | killed: KEEP |
| M16 | base.py:610 no-token anchor `index = last.index+len` -> `0` | same | test_report_error_with_no_token... PASS (survived) -> WEAK; `len(self.file)` mutant killed |
| M19 | semantic_analyzer.py:400 MAYBE_MOVED -> MOVED | test_semantic_analyzer_internals.py | 22/22 PASS (survived): merge_state tests miss the (MOVED,VALID) row |
| M20 | semantic_analyzer.py:307 array branch -> `return False` | same | survived: expr_is_owned_value_array_return_type has no assertion |
| M22 | semantic_analyzer.py:708 METHOD_CALL guard `return`->`pass` | same | killed (IndexError): KEEP |
| M23 | semantic_analyzer.py:428 default False -> True | same | killed |
| M24 | semantic_analyzer.py:461 enum-mismatch condition inverted | same | killed |
| M25 | semantic_analyzer.py:568 `not is_owned` inverted | same | killed |
| M6 | semantic_analyzer.py:130 except-branch `errors.append` -> `pass` | semantic report_error tests | killed (2 tests) |
| M6b | semantic_analyzer.py:128 source_file default dropped | report_error.py + internals | only internals::...out_of_range killed; report_error.py out_of_range test SURVIVED (error() pre-fills source_file) |
| M7a/b | declarations.py:1020 / type_system.py:449 `_current_generic_class_name` assignment removed | test_generic_self_reference.py | killed (2/3 and 1/3): KEEP |
| M8 | statements.py:39 `consume("CLOSE_PAREN")` removed | statements_dead_guards | killed (but impossible state) |
| M9 | type_system.py:247 METHOD_CALL `is_array = ...endswith` -> False | type_system_dead_guards | 10/10 PASS: EQUIVALENT mutant - result string is identical either way, the array-suffix trimming in _get_node_type FUNCTION_CALL/METHOD_CALL/SUPER_CALL is a no-op |
| M17 | imports.py:234 external `continue` -> `pass` | tests/python/imports | 32/32 PASS: EQUIVALENT; both topo-sort-external tests can never fail |
| M26 | imports.py:298 duplicate-symbol `return` -> `pass` | imports | killed (3 tests) -> dups |
| M29 | imports.py:346 `emitted_for_module` guard disabled | imports | survived: skips_node_already_emitted WEAK |
| M30 | imports.py:348 `resolving_for_module` guard disabled | imports | killed (RecursionError): mutual_recursion KEEP |

INCORRECT findings (details):
1. test_declarations_dead_guards.py::test_parse_class_definition_handles_none_type_param_consume - advances 2 tokens then calls `_parse_class_definition()`, which first does consume("CLASS") on the '<' token; the monkeypatch forces that FIRST consume to fail. Per-test coverage shows it executes only declarations.py:981 (same as the class-token test). It never reaches the type-param guard it names.
2. test_declarations_coverage.py::test_function_definition_array_param_bad_size_token - name contradicts body (valid `int32[3]`).
3. test_type_system_dead_guards(_more).py method_call array tests - docstring/comment 'class methods can't declare array return types' is false: `class Foo { fn all(&this) -> int32[] {..} static fn mk() -> int32[] }` passes --check.
4. test_type_system_dead_guards_more.py::test_function_call_return_type_fallback_assignment_is_dead - deliberately `del node.return_type` and asserts the buggy outcome; admits in a comment it pins a latent bug.
5. test_module_resolver.py::test_resolve_for_entry_skips_external_in_topo_visit - never has an external import.
6. test_module_resolver.py::test_build_merged_ast_skips_export_with_no_name - misattributes which guard it hits (see list).
7. test_module_resolver.py::..entry_conflict_value_error_fallback_is_exercised - pins a bug on purpose (docstring says so).
8. test_module_resolver(.py/_extra.py) cyclic tests - pass only via artificial load_stack; real cycles undetected (bug #1).
9. test_preprocessor_internals.py::test_collect_identifier_names_none_returns_empty_set - never calls the function it names; no assertion.

## Compiler bugs discovered (all reproduced in the private copy)

1. Cyclic-import detection is dead code. imports.py `_load_module` checks `dotted in self.modules` (and returns) before the `dotted in load_stack` check, and sets `self.modules[dotted]=mod` before recursing, so a real A<->B cycle never raises CyclicImportError (FS-IMP-0002). docs/reference/imports.md:159 says `[IMPLEMENTED] Cyclic import detection`. Repro: `python firescript/main.py --check tests/sources/invalid/imports/import_cycle_a.fire` prints "Variable 'ping' not defined" (FS-PARSE-0003) attributed to import_cycle_b_provider.fire:2:40 - a symptom, which tests/sources/invalid/imports/import_cycle_a.fire currently pins as the expected output.
2. Duplicate top-level symbol conflicts are only logged, never fail the compile. Repro: a.fire and b.fire each `export fn shared() -> int32`, main.fire `import a.shared; import b.shared; println(shared());` compiles and produces an exe (first wins), stderr shows `[ERROR] Conflicting top-level symbol 'shared' from imports`. Same for an entry-defined `fn shared()` shadowing an import ("Top-level symbol 'shared' in entry conflicts with imported symbol"): exe produced. build_merged_ast's docstring says conflicts 'produce an error'.
3. Constructor with a borrowed regular param plus an owned param mis-assigns ownership. Repro: `class Inner{v:int32; fn Inner(&mut this, v:int32){this.v=v;}} class Outer{total:int32; fn Outer(&mut this, &a: Inner, owned b: Inner){this.total=a.v+b.v;}} x:Inner=Inner(1); y:Inner=Inner(2); o:Outer=Outer(x,y); println(o.total);` -> `FIRV-O2 in main: use of 'x', which is moved` (internal compiler error). (test_parser_base.py::test_constructor_with_borrowed_and_owned_regular_params_parses comment hints at this.) Likely receiver/param index misalignment in ctor borrow flags.
4. Bare `arr[0];` statement and a `directive x;` inside a function body are accepted by the parser but crash AST->FIR with `FIRConversionError: Unsupported statement node ARRAY_ACCESS|DIRECTIVE` (Python traceback printed). Pinned as 'works' by test_statements_coverage.py.
5. Nested generic class instantiation as a type argument (`nested: Pair<Pair<int32,int32>,int32> = Pair(Pair(1,2),3);`) fails FLIR verification FLIRV-T4 ("argument 0 has type i32, expected ptr"); still reproducible; not in tests/sources/**/known_issues (only invalid/known_issues exists).
6. (Possible, unverified end-to-end) type_system.py:~950 `not hasattr(node,'return_type')` is never True because ASTNode always defines return_type; if the parser ever leaves return_type None for a user function call the fallback lookup in self.user_functions is skipped. The test that reaches it (`..fallback_assignment_is_dead`) pins that.
7. Missing coverage for reachable behavior (not bugs): 'Cannot borrow Copyable type' (`fn f(&x: int32)`), match arms mixing enums / unknown enum, `fn foo {}` and `fn + () ...` (missing '(' / missing name) have no tests/sources compile-fail fixtures; the only coverage is the Python unit tests above.

## Could not verify
- Coverage union uses `main.py --check` (front-end through semantic/FIR verifier, no codegen) over tests/sources; I did not run the real harness (wine) so a few .fire `run` tests might alter branch coverage only in the back-end, which does not matter for this slice.
- Whether preprocessor return-transfer / implicit-declaration behaviors are pinned end-to-end by any wine-run .fire test (the unit tests there are WEAK either way; I did not run the full run-test suite against the surviving mutants).
- Whether `match x {}` with zero arms is reachable from source (affects the empty-arms semantic test).
