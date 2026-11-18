<!-- Audit shard report, 2026-11-18. Raw audit output; see README.md for the consolidated plan. Verdicts are recommendations, not applied changes. -->
# P3 audit: tests/python/flir/ (17 files, 343 tests; baseline 343/343 pass in a private copy)

Method: read every test and the code under test (flir/verifier.py, heap_verifier.py, ir.py, textual.py, lowering.py `_decimal_to_f128_bits`, ir_analysis.py); mutation runs in a private rsync copy (never the shared repo). Mutation script: scratchpad/p3_work/mut.py.
Path prefix below: `tests/python/flir/`. "types"=test_verifier_types, "extra"=test_verifier_extra, "checks"=test_verifier_checks, "hchecks"=test_heap_verifier_checks, "loops"=test_heap_verifier_loops.

Process note: the scratchpad `audit/` directory is shared with sibling audit agents; a sibling overwrote `audit/mut.py` and `audit/W.txt` while I was working, so one of my mutation commands (3 invocations) accidentally ran THEIR FIR-mutation script (in their private copy only, never the shared repo) before I stopped it. If a sibling saw odd/duplicated mutation output around 09:31, that was me. My later work used `scratchpad/p3_work/` only.

## Per-file counts (tests: KEEP / MERGE / FIX / DELETE)
- test_verifier_structure.py: 18 : 16 / 1 / 0 / 1
- test_verifier_types.py: 34 : 26 / 2 / 2 / 4
- test_verifier_extra.py: 41 : 11 / 0 / 1 / 29
- test_verifier_checks.py: 40 : 38 / 0 / 2 / 0
- test_verifier_heap.py: 8 : 4 / 4 / 0 / 0
- test_heap_verifier_checks.py: 44 : 38 / 2 / 4 / 0
- test_heap_verifier_loops.py: 10 : 4 / 5 / 1 / 0
- test_heap_verifier_defensive.py: 4 : 0 / 0 / 0 / 4 (contrived)
- test_ir_analysis_edges.py: 28 : 25 / 0 / 1 / 2
- test_dump.py: 3 : 0 / 0 / 0 / 3
- test_textual_dump.py: 3 : 1 / 0 / 0 / 2
- test_ir_helpers.py: 11 : 3 / 2 / 0 / 6
- test_lowering_defensive_errors.py: 25 : 3 / 0 / 1 / 21 (contrived, owner policy call)
- test_lowering_type_edge_cases.py: 14 : 10 / 0 / 0 / 4 (contrived SyscallResult bootstrap; owner call)
- test_lowering_float128.py: 16 : 8 / 0 / 0 / 8
- test_lowering_f128_decimal.py: 21 : 17 / 0 / 1 / 3
- test_lowering_f128_decimal_more.py: 23 : 5 / 0 / 0 / 18
Totals approx: KEEP 210, MERGE 16, FIX 13, DELETE-candidate 104 (26 of those are "contrived unreachable-guard" tests the owner may choose to keep).

Verdict tallies (a test can have several): REDUNDANT ~85, TRIVIAL ~17 (+ ~25 contrived-guard), WEAK 11, INCORRECT 5.

---------------------------------------------------------------------------
## DELETE candidates

### test_verifier_structure.py
- structure::test_s2_rejects_field_referencing_unresolved_struct | INCORRECT, TRIVIAL | name says "rejects", body asserts `validate()` does NOT raise (ptr field to missing struct). Contradicts its name and spec S2 text ("ptr<S> pointees naming structs resolve"). The real S2 field check (struct-typed field) is tested by extra::test_s2_field_references_unresolved_struct. Delete (or rename to "ptr pointee is not struct-checked" if that narrowing is intended; note spec 8.1 does not list it).

### test_verifier_types.py (duplicated by checks/extra with stronger asserts)
- types::test_t4_call_argument_count_mismatch | REDUNDANT | checks::test_t4_call_to_module_function_argument_count_mismatch (same input, asserts message).
- types::test_t3_ret_type_mismatch | REDUNDANT | checks::test_t3_ret_pointer_in_scalar_function_is_rejected (same ptr-into-scalar, asserts message).
- types::test_m3_ptradd_nonpositive_scale | REDUNDANT | checks::test_m3_ptradd_with_zero_scale_... (also has valid twin).
- types::test_t2_binop_operand_type_does_not_match_operand_type | REDUNDANT | checks::test_t2_wider_int_operand_into_narrower_binop_is_rejected (identical i64-into-i32, asserts "lhs type 'i64'").

### test_verifier_extra.py (29 of 41 are duplicates; all assert only the rule id)
Helpers/dead code:
- extra::test_resolve_struct_type_is_dead_code_but_correct_if_called | TRIVIAL | `_resolve_struct_type` has no callers (grep: only its definition, verifier.py:131). The test pins dead code and would block its removal. Delete test and function together.
- extra::test_binop_operand_ok_narrowing | REDUNDANT | checks::test_t2_narrow_int_operand_feeds_wider_binop_without_cvt / ..._wider_int_operand_..._rejected / float_operand test drive the same helper through validate().
- extra::test_ptr_lenient_eq_plain_type_equality | REDUNDANT | checks::test_t3_ret_pointer_with_different_pointee_is_accepted, test_t4_call_to_extern_accepts_pointer_with_any_pointee, test_t5_slot_pointer_pointee_difference_is_tolerated.
Exact duplicates (same inputs, same rule) of other files:
- extra::test_s2_duplicate_struct_name | REDUNDANT | structure::test_s2_rejects_duplicate_struct_name
- extra::test_s2_duplicate_global_name | REDUNDANT | structure::test_s2_rejects_duplicate_global_name
- extra::test_s3_struct_size_not_multiple_of_align | REDUNDANT | structure::test_s3_rejects_size_not_multiple_of_align
- extra::test_s3_field_exceeds_struct_size | REDUNDANT + WEAK | structure::test_s3_rejects_field_exceeding_struct_size; and it passes for the wrong reason (see evidence E1)
- extra::test_s3_enum_variant_field_overlaps_tag | REDUNDANT | structure::test_s3_rejects_variant_field_overlapping_tag
- extra::test_s3_enum_variant_fields_overlap_each_other | REDUNDANT | structure::test_s3_rejects_overlapping_variant_fields
- extra::test_t1_operand_has_no_value_void | REDUNDANT | checks::test_t3_ret_of_valueless_operand_reports_only_t1 (stronger: asserts only T1 and message)
- extra::test_t2_binop_lhs_type_mismatch / test_t2_binop_rhs_type_mismatch | REDUNDANT | checks::test_t2_wider_int_operand_into_narrower_binop_is_rejected (lhs); types::test_t2_binop_rhs_operand_type_does_not_match_operand_type (rhs)
- extra::test_t2_comparison_must_produce_bool | REDUNDANT | types::test_t2_comparison_must_produce_bool (verbatim)
- extra::test_t2_unknown_binop | REDUNDANT | types::test_t2_unknown_binop
- extra::test_t2_not_type_mismatch | REDUNDANT | types::test_t2_not_requires_bool
- extra::test_t2_neg_type_mismatch | REDUNDANT | types::test_t2_neg_result_type_mismatch
- extra::test_t2_cvt_from_type_not_scalar | REDUNDANT + WEAK | types::test_t2_cvt_from_type_not_scalar (identical; both WEAK, E2)
- extra::test_t2_cvt_to_type_not_scalar | REDUNDANT | types::test_t2_cvt_to_type_not_scalar
- extra::test_t3_bare_ret_in_nonvoid_function / test_t3_ret_carries_value_in_void_function | REDUNDANT | types:: same-named tests
- extra::test_t4_call_argument_type_mismatch | REDUNDANT | checks::test_t4_call_to_module_function_argument_type_mismatch
- extra::test_t4_call_result_type_mismatch | REDUNDANT | checks::test_t4_call_to_extern_result_type_mismatch (same `_check_call_against` line; module-function kind only differs in message text)
- extra::test_t5_slotload_type_mismatch | REDUNDANT | checks::test_t5_parameter_slotload_type_mismatch_is_reported (same line; also says "FIRV-T5" in a message typo)
- extra::test_t5_slotstore_type_mismatch | REDUNDANT | types::test_t5_slotstore_value_type_mismatch
- extra::test_t6_gload_undeclared_global / gload_type_mismatch / gstore_undeclared_global / gstore_value_type_mismatch | REDUNDANT | the four same-named tests in types (identical bodies)
- extra::test_m3_ptradd_base_non_pointer | REDUNDANT | types::test_m3_ptradd_base_non_pointer

### test_heap_verifier_defensive.py (4/4): TRIVIAL / contrived
All four drive unreachable guards by hand (`_meet_states([])`, `run()` with no blocks, `run()` with a block outside cfg.reachable, `_ident_text(("slot", ..))` which the file itself says is dead). Project philosophy (CLAUDE.md "defensive or unreachable lines don't need contrived tests") says delete; they also pin dead branches and block cleanup.
- heap_defensive::test_meet_states_of_empty_list_returns_default_state | TRIVIAL
- heap_defensive::test_run_on_function_with_no_blocks_returns_immediately | TRIVIAL
- heap_defensive::test_run_skips_block_not_in_cfg_reachable | TRIVIAL
- heap_defensive::test_ident_text_slot_kind_branch | TRIVIAL (tests dead branch)

### test_ir_analysis_edges.py
- edges::test_jmp_null_and_float_constant_formatting_via_dump | TRIVIAL, REDUNDANT | formatting; tests/snapshots/**/*.flir contain `fconst` (2 snapshots), `nullconst` (6), `jmp` (all).
- edges::test_struct_field_lookup_returns_entry_and_raises_for_missing | REDUNDANT | ir_helpers::test_flir_struct_field_lookup_unknown_field_raises (same KeyError); lookup half is trivial.

### Dump / textual / ir_helpers
- test_dump::test_dump_module_with_mutable_global | REDUNDANT | edges::test_dump_includes_entry_externs_and_globals_in_deterministic_order asserts the same line; every snapshot .flir contains `global mut`.
- test_dump::test_dump_module_with_immutable_global | REDUNDANT | edges (same) + textual_dump::test_global_constant_dump_rendering.
- test_dump::test_foreign_value_rejected_in_flir_dump | REDUNDANT | textual_dump::test_resolve_rejects_foreign_value is a byte-for-byte equivalent.
- test_textual_dump::test_global_constant_dump_rendering | REDUNDANT | edges (same line).
- test_textual_dump::test_function_validate_wraps_self_in_throwaway_module | REDUNDANT, TRIVIAL | ir_helpers::test_flir_function_validate_wraps_single_function is identical; asserts only "no exception".
- ir_helpers::test_flir_type_struct_size_and_align_with_module | TRIVIAL | attribute read; used by every struct lowering/e2e test.
- ir_helpers::test_flir_type_signed_and_unsigned_predicates | TRIVIAL
- ir_helpers::test_flir_type_hash_and_repr | TRIVIAL
- ir_helpers::test_finst_default_format_joins_resolved_operands | TRIVIAL | asserts `"," in text`; the test's own comment says no concrete instruction uses the base format().
- ir_helpers::test_flir_struct_field_lookup_unknown_field_raises | REDUNDANT | edges version.
- ir_helpers::test_unreachable_format | TRIVIAL

### Lowering: contrived unreachable-guard tests (policy call for owner; all CORRECT but low value)
test_lowering_defensive_errors.py error-message tests, each asserting only a substring of an internal LoweringError for FIR the frontend never produces: test_lower_type_rejects_unknown_fir_type, test_ensure_struct_rejects_unknown_class, test_request_function_rejects_unknown_function, test_val_rejects_unsupported_operand_kind, test_val_rejects_fir_value_with_no_lowered_value, test_lower_inst_rejects_unsupported_instruction (also contains dead setup: unused module/x/y and a rambling comment), test_lower_terminator_rejects_unsupported_terminator, test_lower_binary_rejects_unsupported_string_operator, test_lower_binary_rejects_unsupported_operator, test_lower_unary_rejects_unsupported_operator, test_to_string_rejects_unconvertible_source_type, test_lower_load_var_rejects_undeclared_local, test_lower_conversion_call_rejects_unsupported_name, test_lower_method_call_rejects_unknown_method, test_gen_slot_of_rejects_non_generator_operand, test_lower_yield_rejects_yield_outside_generator (FIR verifier FIRV-G1 rejects first), test_array_length_call_rejects_unknown_size; plus pins of unreachable paths: test_val_loads_param_value_from_slot (ParamValue never produced), test_lower_inst_passes_through_move_borrow_clone, test_lower_binary_non_short_circuit_and_or_fallback, test_fir_type_str_of_returns_void_for_none_result_type.
Note: the substring assertions are weak against a wrong-site raise but fine for what they claim.
Also contrived: test_lowering_type_edge_cases::test_ensure_struct_bootstraps_syscall_result_without_runtime_module, test_is_copyable_class_str_treats_bootstrap_syscall_result_as_copyable, test_lower_type_bootstraps_syscall_result, test_lower_type_str_bootstraps_syscall_result (real pipeline always supplies the runtime module; the 4 overlap each other on the same fallback).

### float128 literal-converter tests (three files exercise one pure function with heavy overlap)
Keep test_lowering_float128.py (oracle-based) + test_lowering_f128_decimal.py as canonical; drop the rest.
- float128::test_positive_sign_prefix, test_infinity_positive, test_infinity_named_infinity, test_infinity_negative, test_nan, test_malformed_text_falls_back_to_zero, test_zero_division_falls_back_to_zero, test_f128_suffix_is_stripped | REDUNDANT | f128_decimal has the same inputs with exact-bit asserts (test_leading_plus_sign, test_inf_text, test_infinity_alias_text, test_negative_infinity, test_nan_text, test_malformed_text_falls_back_to_zero, test_zero_denominator..., test_f128_suffix_is_stripped). `1/0` is not a possible literal (TRIVIAL).
- f128_decimal::test_scientific_notation | WEAK, REDUNDANT | asserts only `!= (0,0)`; float128::test_scientific_notation compares to the expanded decimal.
- f128_decimal::test_zero_denominator_value_error_variant_falls_back_to_zero | TRIVIAL | `1/0` can't be lexed as a float literal.
- f128_decimal::test_elif_exponent_correction_branch_is_unreachable | TRIVIAL | never calls compiler code; asserts a math inequality over small ints (and is true for ALL num/den, not only coprime, so its stated premise is wrong). Passes under any mutation of lowering.py.
- f128_decimal_more.py: 18 of 23 REDUNDANT: test_positive_zero, test_negative_zero (dec: test_positive_zero/test_negative_zero_sets_sign_bit_only), test_explicit_plus_sign, test_suffix_stripped_f128, test_nan (weaker than dec), test_negative_nan, test_infinity_forms, test_negative_infinity, test_scientific_notation, test_negative_scientific_notation (asserts sign bit only), test_malformed_text_falls_back_to_zero, test_overflow_to_infinity, test_underflow_to_zero, test_subnormal_nonzero, test_rounding_carry_into_exponent_without_overflow (dec: carry_bumps_exponent, same branch), test_rounding_carry_overflows_to_infinity (same branch as dec: both reach "overflow after rounding"; verified, see E6), test_round_half_even_rounds_up, test_round_half_even_rounds_down_to_even.
  KEEP from this file (merge elsewhere): test_suffix_stripped_other_float_suffixes (only f64/f32/f16 coverage), test_negative_overflow_to_infinity, test_negative_underflow_to_zero (sign on inf / -0), test_round_half_even_below_half, test_round_half_even_above_half (only <0.5 / >0.5 helper cases).

---------------------------------------------------------------------------
## MERGE candidates (valid but duplicate a sibling; keep one)
- structure::test_s1_rejects_unknown_branch_target | REDUNDANT-low | checks::test_s1_jmp_to_missing_block_is_reported + test_s1_br_false_target_missing... (assert message and exclusivity).
- types::test_m1_load_offset_not_a_field, types::test_m1_load_type_mismatch_at_field_offset | REDUNDANT-low | same `_check_typed_access` lines covered by checks::test_m1_store_at_offset_without_field_is_reported, test_m1_store_field_type_mismatch_is_reported, test_m1_load_at_enum_variant_offset_with_foreign_type_is_rejected (only difference is the Load wrapper; one load case suffices).
- verifier_heap::test_a1_double_free | REDUNDANT | hchecks::test_a1_double_free_message_says_freed_again
- verifier_heap::test_a2_use_after_free | REDUNDANT | hchecks::test_a2_use_after_free_via_load_through_token (only consumer differs: fs_rt_stdout vs fs_rt_str_length, both non-escaping borrows)
- verifier_heap::test_a4_local_leak_at_return | REDUNDANT | hchecks::test_a4_leak_reports_the_allocating_position (stronger)
- verifier_heap::test_verifier_heap_accepts_clean_module | REDUNDANT | hchecks::test_valid_alloc_use_free_is_clean
  (Note: spec section 9 asks "one negative test per rule id"; if the owner wants a canonical smoke file, keep verifier_heap and delete the hchecks copies instead.)
- hchecks::test_alloc_and_free_within_each_loop_iteration_is_clean | REDUNDANT | loops::test_valid_alloc_and_free_inside_loop_body_is_clean (identical shape)
- hchecks::test_free_after_loop_that_only_uses_token_is_clean | REDUNDANT | loops::test_valid_pre_loop_allocation_freed_after_loop_exit_is_clean
  (Evidence E7: neither pair member can fail under the loop-header bug; only loops' negative tests detect it.)
- loops::test_valid_alloc_and_free_inside_loop_body_is_clean / test_valid_pre_loop_allocation_freed_after_loop_exit_is_clean (keep one of each pair above), and loops::test_nested_loops_pre_loop_allocation_leak_is_reported, test_nested_loops_free_in_inner_body_is_reported, test_nested_loops_use_in_inner_free_after_exit_is_clean | REDUNDANT-low | forward_dataflow has no nesting-specific logic; the nested tests add nothing over the single-loop ones (M16 broke simple and nested equally).
- ir_helpers::test_flir_type_struct_size_requires_module_context + test_flir_type_struct_align_requires_module_context | MERGE into one test.

---------------------------------------------------------------------------
## FIX-ASSERTION
- types::test_t2_cvt_from_type_not_scalar_not_checked (types::test_t2_cvt_from_type_not_scalar) | WEAK | E2: the corrupt Cvt(p: ptr, from_type=struct, to I32) ALSO violates the from_type==operand-type rule, so the not-scalar check can be deleted with zero test failures. Needs an operand whose actual type is the struct (e.g. a Load returning a struct) so only the scalar rule fires.
- types::test_m2_load_misaligned_offset | INCORRECT/WEAK | name says M2, asserts FLIRV-M1 (offset 5 is also "not a field"); E3: deleting the M2 check does not fail it. Use an offset that lands on a field but is misaligned (checks::test_m2_store_misaligned_offset_is_reported is the only real M2 test; add a Load variant or rename).
- extra::test_s1_empty_block | WEAK | E4: the second block is unreachable, which also yields FLIRV-S1, so the empty-block check can be deleted without failure. Make the empty block the only problem (e.g. empty non-entry block that is a jump target).
- extra::test_s2_mutable_global_name_collides_with_immutable | KEEP but MISNAMED | it declares ("g") twice in mutable_globals; no immutable global involved (mutable-vs-immutable is structure::test_s2_rejects_global_and_mutable_global_name_collision). Rename to ..._duplicate_mutable_global.
- hchecks::test_m4_store_through_slot_loaded_string_literal_alias_is_not_resolved | INCORRECT | pins a gap as desired behavior; spec 5.3 M4 says a strconst-derived pointer "directly or via must-alias slot propagation" must never be a store base. Implementation resolves only temp-token aliases (`_resolved_origin`), so the test would FAIL when the verifier is fixed to spec. Move to a known-issue style (or document in spec 8.2 as a narrowing, then it is correct).
- hchecks::test_token_allocated_on_only_one_branch_is_dropped_at_join and hchecks::test_slot_bound_to_different_tokens_on_each_branch_loses_alias_at_join | WEAK | E5: changing the meet from intersect to keep-union for `tokens` fails no test in the directory; the alias-dropping half is covered but the token-drop half is not (neither test can show a token that is LIVE and slot-aliased surviving).
- hchecks::test_user_function_returning_scalar_is_not_a_token | WEAK | E5b: treating scalar-returning calls as fresh tokens fails no test (a scalar result is an unnamed temp, which A4 deliberately ignores). To be meaningful it should store the scalar into a slot so A4 would fire.
- hchecks names that contradict content (CORRECT behavior, bad names): test_a2_use_after_free_via_load_through_token (uses call, no load), test_a2_branching_on_nothing_but_using_freed_pointer_in_store_base (no branch), test_escape_by_storing_into_a_field_is_not_a_leak_and_later_free_is_untracked (no later free). Two tests hold two cases each (test_user_function_returned_pointer_freed_once_is_clean_and_twice_is_a1, test_destroy_call_frees_token_and_double_destroy_is_a1; checks::test_m3_ptradd_with_zero_scale_...): first failure hides the second; split.
- loops::test_a2_use_after_free_across_back_edge_is_reported | WEAK | asserts rule in (A1, A2); the input yields both, so removing the A2 check does not fail it (E5c). Assert A2 "possibly freed" specifically.
- edges::test_cfg_rpo_is_deterministic_across_builds | WEAK | builds the CFG 5 times in one process; hash randomization is fixed per process, so it cannot detect the nondeterminism it names. A real test would run subprocesses with different PYTHONHASHSEED (CLAUDE.md determinism section) or assert exact expected RPO order for LOOP.
- checks::test_t4_extern_shadowed_by_module_function_uses_module_signature | QUESTIONABLE | pins an unspecified precedence; spec T4 says the callee resolves to "exactly one of" function/extern/runtime, which arguably makes a name present as both invalid.
- checks::test_m1_access_through_raw_pointer_is_not_checked | QUESTIONABLE | pins that a misaligned `store i32 @ offset 3` through a raw ptr passes; spec M2 says every load/store is alignment-checked. Code only checks for known-struct pointees. Document the narrowing in spec 8.1 or drop the pin.
- f128_decimal::test_subnormal_rounding_clamps_at_max_subnormal_significand | INCORRECT | pins a compiler bug (E6, bug B1).
- defensive::test_lower_binary_rejects_unsupported_float128_operator | INCORRECT (pins a user-reachable bug) | asserts that `float128 ** float128` raises LoweringError. That input is reachable from user source and crashes the compiler with a Python traceback (bug B2); the proper form is a tests/sources known-issue case, and this unit test would break when fixed.

---------------------------------------------------------------------------
## KEEP (summaries)
- structure (16): S1 missing/duplicate/unreachable/mid-block terminator, S2 duplicate function/entry/global/mutable collision/duplicate struct, S3 size/overlap/misaligned/exceeds/variant tag/variant overlap, clean twin. Each verified exclusive by reading (the corrupt IR violates only the target rule). Mutation: dropping S3 exceed-size fails structure::..field_exceeding (only); dropping tag-overlap fails structure + extra.
- types (26): T1 unreachable/foreign, T2 result mismatch / not / cvt-from-mismatch / rhs / bool-compare / neg / unknown / cvt-to, T3 br / bare ret / ret value in void, T4 unresolved callee / extern arg / runtime ABI count, T5 slot twice / slotstore / slotaddr, T6 five, M1 base none, M3 base, clean twin. (types::test_t1_operand_from_unreachable_or_foreign_block name says "foreign" but only tests unreachable; foreign is extra::test_t1_operand_foreign...)
- extra (11): s1 no blocks, s2 unresolved struct field (mutation-verified), t1 foreign + dump fallback (validated: function_dump == ''), t1 non-dominating, slotaddr accepts, m1 load/store non-pointer base, store value-type T1, load/store "skip when base unresolved" pair.
- checks (38): excellent. Each test corrupts one thing, asserts rule AND message, valid boundary twins exist (narrow-int, null-check, pointee leniency, enum variant union, mutable gstore, diamond CFG, tier gating, ordering). Mutation: removing the Tier-1 gate fails test_tier2_is_skipped (E8), dropping M2 fails test_m2_store_misaligned (E3), off-by-one in `instruction_dominates` is caught by edges (E9).
- verifier_heap (4): a3 literal free, a5 free struct with owned fields (only positive class case), a5 own-destructor exemption (only), m4 store to literal (only).
- hchecks (38): straight-line, joins (freed both/one/none, possibly-freed wording), escape by return/store/call, borrow-only, rebinding, user-function tokens, impl_ prefix, A3 four shapes + parameter negative, A5 enum/plain/shallow/unknown/untyped/destroy. Mutations: removing A2 fails 4 tests, removing named-only A4 filter fails the anonymous-temporary test, MAYBE->FREED meet fails the two "possibly freed" tests.
- loops (4): pre-loop leak, pre-loop freed in body, while conditional free, while conditional use then free. Only loops' negative tests detect a broken TOP-sentinel (E7).
- edges (25): CFG, dominators, dominates, instruction_dominates (strict index; E9), forward_dataflow (diamond, loop fixpoint, reachable-only, entry seed, single block), Violation location/format, struct finalize x2, dump of entry/externs (sorted; the only test catching unsorted externs, M15)/globals, no-entry dump. Note: half of this file's tests exercise ir.py/textual.py, not ir_analysis.py (misfiled). test_dominates_is_reflexive_even_for_unknown_blocks pins a quirk (low value).
- textual_dump::test_resolve_rejects_foreign_value (keep one copy), ir_helpers: test_const_f128_format (no f128const in any snapshot), test_block_add_after_terminated_raises, test_flir_function_validate_wraps_single_function (keep one copy).
- defensive: test_ensure_slot_is_idempotent, test_gen_slot_of_finds_slot_from_direct_gen_new, test_lower_driver_skips_runtime_prefixed_and_generic_class_method_functions (reachable behavior).
- type_edge (10): lower_type / lower_type_str shape fallbacks (generic param -> ptr, generator, function type, array suffix, generator prefix, generic instance owned/copyable, unknown bare name). Correct, but note they pin lenient fallbacks (unknown named type silently becomes ptr), which could mask a frontend bug.
- float128 (8): negative sign bit, scientific x2 (relative), oracle cross-checks for overflow, subnormal, underflow, carry-into-exponent, half-even ties (the only independent, bit-exact checks of ordinary values).
- f128_decimal (17): exact-bit nan/-nan/inf/infinity/-infinity, +sign, suffix, malformed fallback, +0/-0, overflow, underflow, subnormal exponent field, ties (lo==4 both sides; verified both are true ties), carry bump, carry overflow, _round_half_even helper.

---------------------------------------------------------------------------
## Detailed evidence (mutations in private copy; each run = whole tests/python/flir, 343 tests)
- E1 Drop S3 `offset + fsize > struct.size` check (verifier.py `if False:`): 1 failure = structure::test_s3_rejects_field_exceeding_struct_size. extra::test_s3_field_exceeds_struct_size still passes because it sets struct.size = 6 with align 4, which trips the separate "size not multiple of align" S3 check (its comment "shrink to isolate" is wrong). WEAK.
- E2 Drop `if inst.from_type.kind not in scalar_kinds` (cvt from_type not scalar): 0 failures. types and extra "cvt_from_type_not_scalar" both build Cvt(ptr value, from_type=struct Point) which already violates "from_type equals operand's actual type" (T2), so both pass for the wrong reason. The rule is effectively untested.
- E3 Drop M2 alignment emit: only checks::test_m2_store_misaligned_offset_is_reported fails; types::test_m2_load_misaligned_offset passes (it asserts M1; its offset 5 isn't a field).
- E4 Drop the empty-block S1 emit: 0 failures; extra::test_s1_empty_block still passes via the other (unreachable) block.
- E5 Heap meet keeps tokens missing from a predecessor (`pass` instead of `del`): 0 failures. E5b Treat any call result as a fresh token (drop `kind != "ptr"` guard): 0 failures. E5c Rename A2 emit to a bogus id: 5 failures but loops::test_a2_use_after_free_across_back_edge_is_reported is NOT among them (A1 satisfies it).
- E6 Subnormal rounding. Mutation: replace `sig = min(sig, (1<<112)-1)` by carrying into the min normal (what IEEE and the independent oracle tests/support/float128_oracle.py do): the only failing test is test_subnormal_rounding_clamps_at_max_subnormal_significand. Direct check for that text "3.3621...e-4932": lowering returns (0xffffffffffffffff, 0xffffffffffff) (largest subnormal), oracle returns (0x0, 0x1000000000000) (smallest normal); frac*2^16494 = 2^112 - 0.4 so correct rounding is up to 2^112 = min normal. => compiler bug B1; the test pins the wrong answer and its comment rationalizes it.
  Also verified: both "overflow after rounding" tests (f128_decimal ...overflows_to_infinity and _more ...overflows_to_infinity) reach the same branch (inputs are 0.6 ulp and exactly 0.5 ulp above max finite; both match the oracle); f128_decimal's comment calls its input "just below the largest finite" which is wrong (it is above).
  Mutations show the three float128 files overlap: round-half-even tie -> always-up fails 4 tests across all three files; EXP_BIAS off by one fails 6 tests across 3 files; dropping the NaN sign bit fails 2 (one each in decimal and _more).
- E7 Loop-header TOP sentinel removed (`live = states`): 6 failures, all in loops file (a4 pre-loop, a1 pre-loop, a2, nested x2, while). None of hchecks' loop tests nor any valid-twin loop test fails.
- E8 Tier-1 gate removed (`if function.blocks:`): fails checks::test_tier2_is_skipped_for_function_with_tier1_violation only (A4 cascade appears).
- E9 `instruction_dominates` `<` -> `<=`: only edges::test_instruction_dominates_same_block_orders_by_index_strictly fails (no verifier test depends on same-index; fine).
- Verified valid: heap A5 positive/negative cases, test_verifier_checks assertions, M12 (tag overlap) caught by 2 tests, M11 (S2 struct-field) caught by extra only (it errors with KeyError when check removed; structure's pseudo-test cannot).

## Compiler bugs discovered
- B1 (lowering.py `_decimal_to_f128_bits`, subnormal branch, ~line 126): a float128 literal in the subnormal range whose rounded significand reaches 2^112 is clamped to the largest subnormal (0x...ffff) instead of rounding up to the smallest normal (hi=0x0001000000000000, lo=0). 1 ulp error. Repro (no .fire needed):
  `from flir.lowering import _decimal_to_f128_bits as d; d("3.36210314311209350626267781732175234359107456732546680313127e-4932")` -> (0xffffffffffffffff, 0xffffffffffff); oracle: (0, 0x1000000000000). Extremely obscure literal; fix is `if sig >= 1<<112: return (0, sign<<63 | 1<<48)` which makes only the pinning test fail.
- B2 (flir/lowering.py:1023 lower_binary): `float128 ** float128` crashes the compiler with an uncaught Python traceback `flir.lowering.LoweringError: unsupported float128 operator **` instead of a user diagnostic. Repro (private copy): file with
  ```
  import @firescript/std.io.println;
  a: float128 = 2.0f128;
  b: float128 = 3.0f128;
  c: float128 = a ** b;
  println(c);
  ```
  `python firescript/main.py x.fire --platform windows --arch x86_64 -o x.exe`. No tests/sources known_issues entry exists for it (only this unit test's comment mentions it).
- Observation (not run to ground): spec 5.3 M4 (slot-propagated strconst store) and M2 (raw pointer alignment) are looser in code than in the spec; see FIX list.
