<!-- Audit shard report, 2026-11-18. Raw audit output; see README.md for the consolidated plan. Verdicts are recommendations, not applied changes. -->
# P4 audit: tests/python/{backend,cli,harness,float128}

Paths below are relative to /home/alec/Programming/firescript/tests/python/.
Verdicts: KEEP | REDUNDANT | TRIVIAL | WEAK | INCORRECT. "(dup)" names the test to keep.

## File counts (test functions; params expand some)
backend/test_asm_encoding.py       27 fn (96 param cases for test_encode)  KEEP 24 (1 = test_encode), REDUNDANT 1, TRIVIAL 1, dup-name 1
backend/test_assembler_unit.py     39 fn   KEEP 3, REDUNDANT 33, WEAK 10 (overlap), TRIVIAL 2
backend/test_pe_writer.py           5 fn   KEEP 5 (1 WEAK)
backend/test_pe_writer_more.py      4 fn   REDUNDANT 4 (all four duplicate test_pe_writer.py, with weaker assertions)
backend/test_pe_inspect.py          9 fn   KEEP 8, TRIVIAL 1
backend/test_flir_to_asm_errors.py  6 fn   KEEP 4, WEAK 1, KEEP-with-stale-docstring 1
backend/test_flir_to_asm_coverage.py 26 fn KEEP 10 (8 are tiny _escape_asciz unit tests), WEAK 8, TRIVIAL 4, REDUNDANT 4
cli/test_check.py                  11 fn   KEEP 3, WEAK 6, REDUNDANT 3 (overlap)
cli/test_compiler_pipeline.py       4 fn   KEEP 3, TRIVIAL 1
cli/test_diagnostics.py             2 fn   KEEP 1, REDUNDANT 1
cli/test_dir_batch.py               6 fn   KEEP 3, WEAK 2, INCORRECT(pins bug) 1
cli/test_emit.py                    6 fn   KEEP 6
cli/test_imports.py                 4 fn   KEEP 3, WEAK 1
cli/test_main_arg_errors.py        14 fn   KEEP 12, WEAK 1, INCORRECT(pins bug) 1
cli/test_main_check_output_flag.py  1 fn   KEEP 1
cli/test_main_internals.py         32 fn   KEEP 20, WEAK 5, TRIVIAL 4, REDUNDANT 3
cli/test_output.py                  2 fn   KEEP 2
cli/test_paths.py                   2 fn   KEEP 2
cli/test_targets.py                 2 fn   REDUNDANT 2
cli/test_targets_resolution.py     11 fn (14 extra param cases) KEEP 9, TRIVIAL 1, WEAK 1
harness/test_directives.py          8 fn   KEEP 8 (error cases WEAK: never check which error)
harness/test_expectations.py       13 fn   KEEP 13
harness/test_matrix.py              8 fn   KEEP 5, WEAK 1, TRIVIAL 2
harness/test_seeds.py               7 fn   KEEP 7
harness/test_selectors.py           7 fn   KEEP 7
float128/test_oracle_units.py      13 fn   KEEP 6, WEAK 6, REDUNDANT 1
float128/test_oracle_vectors.py     1 fn   TRIVIAL + REDUNDANT
Total 274 functions. Rough tally: KEEP ~163, REDUNDANT ~52, WEAK ~33 (overlapping), TRIVIAL ~16, INCORRECT 3 (+2 stale/misleading docstrings/names).

## Key meta-findings
* Differential `as` oracle in test_asm_encoding.py IS effective today: I ran all 96 CASES through our assembler vs the host GNU as (ELF path): 96 matched, 0 None (as rejected), 0 empty (oracle extraction failed), 0 mismatches. If extraction broke it would mismatch (ours non-empty), not silently pass. Weaknesses: (a) silent downgrade to `len(ours)>0` when `as` is absent or rejects a line (violates the project's no-silent-weakening spirit; should fail/ERROR when `as` missing on a host that claims to run it, and always assert len(ours)>0); (b) CASES omits call, jmp, jb, jae, je, jne, jnz, jz, js, mul, shr (all supported by the assembler) because no label forms are used. Mutation: changing _JCC["jb"] 0x82->0x83 survived ALL 211 backend python tests AND the e2e conversions tests (jb only used in fs_rt_mem_copy overlap path). Dropping 'dil' from the setcc REX-force set (4,5,6,7)->(4,5,6) also survived.
* The float128/ tests test the Python ORACLE (tests/support/float128_oracle.py, a test helper), not the compiler's soft-float runtime (std/internal/float128.fire). The runtime is covered only by 4 .fire files (~47 println total). The docs claim bit-exact fuzz validation vs the oracle but nothing like that is committed; oracle.vectors() is never replayed against the runtime.
* The oracle itself is CORRECT: I diffed it against glibc libquadmath (__float128, independent implementation) on 32,000 random add/sub/mul/div/lt/le/eq/to_f64 ops over edge-biased bit patterns (subnormal, inf/nan, near-1 exponents) = 0 mismatches; format_f/format_g on 6,030 values = 0 mismatches vs quadmath_snprintf("%.6Qf"/"%Qg"); parse vs Fraction/Decimal rounding on 11 strings incl. 1e4000/1e-5000/4.9e-4951 = 0 mismatches; test_oracle_units' constants all match. So no INCORRECT float128 test. But the units suite is too weak to protect the oracle: mutating _rne tie-to-even (never round-up on odd lsb) and mutating _round_digits tie-to-even (`prev % 2 == 1` -> `== 0`) each survive 14/14.
* CLI tests share REPO_ROOT/build/ with each other (test_check::test_check_valid_file removes then asserts absence of build/functions.exe while test_default_target_compiles and the test_output tests compile functions.fire from the same cwd). Latent flake under --jobs>1; I could not reproduce in 8 parallel runs (private copy).
* Large intra-slice duplication: test_assembler_unit.py duplicates test_asm_encoding.py almost completely (33 of 39), test_pe_writer_more.py duplicates test_pe_writer.py (4 of 4), flir_to_asm_coverage duplicates flir_to_asm_errors (4), cli/test_targets.py duplicates test_targets_resolution.py (2), several test_check/test_main_internals CLI tests duplicate stronger test_main_arg_errors tests.

## Per-test list

### DELETE-candidates (REDUNDANT / TRIVIAL)
backend/test_assembler_unit.py (keep the asm_encoding.py twin in each case):
- test_assembler_unit.py::test_lea_missing_closing_bracket_errors | REDUNDANT WEAK | (dup) test_asm_encoding.py::test_parse_mem_ptr_without_brackets_returns_none; no message needle
- ::test_mem_base_plus_xmm_index_errors | REDUNDANT | (dup) test_asm_encoding.py::test_parse_mem_bad_base_plus_index
- ::test_mem_unknown_base_errors | REDUNDANT | (dup) test_parse_mem_bad_base
- ::test_mem_unsupported_form_errors | REDUNDANT | (dup) test_parse_mem_unsupported_operand
- ::test_mov_reg16_reg16 | REDUNDANT WEAK | CASES has "mov ax, cx" with real byte compare
- ::test_alu_reg16_imm | REDUNDANT WEAK | CASES "add ax, 5"
- ::test_mov_mem_imm16 | REDUNDANT WEAK | CASES "mov word ptr [rbp-2], 5"
- ::test_mov_r8d_imm_forces_rex | REDUNDANT WEAK | CASES "mov r8d, 5"
- ::test_setcc_low_byte_reg_forces_rex | REDUNDANT WEAK | CASES "sete spl"
- ::test_movq_xmm_to_xmm | REDUNDANT WEAK | CASES "movq xmm0, xmm1"
- ::test_movq_xmm_to_xmm_extended_registers_force_rex | REDUNDANT WEAK | CASES "movq xmm8, xmm9"
- ::test_nop_alone | REDUNDANT WEAK | (dup) test_asm_encoding.py::test_nop_encodes_single_byte (asserts exact byte)
- ::test_mov_mem_mem_errors | REDUNDANT | (dup) test_mov_mem_mem_forms_raises
- ::test_mov_imm_size8_errors | REDUNDANT | (dup) test_mov_imm_to_8bit_reg_raises
- ::test_alu_mem_mem_errors | REDUNDANT | (dup) test_alu_unsupported_forms_raises (same branch/message)
- ::test_unsupported_mnemonic_errors | REDUNDANT | (dup) test_unsupported_mnemonic_raises
- ::test_unknown_section_directive_errors | REDUNDANT | (dup)
- ::test_unsupported_top_level_directive_errors | REDUNDANT | (dup) test_unsupported_directive_raises
- ::test_bad_asciz_errors | REDUNDANT WEAK | (dup) test_bad_asciz_raises (has needle)
- ::test_encode_failure_wraps_assertion | REDUNDANT | (dup) test_generic_python_exception_is_wrapped
- ::test_rip_reference_to_earlier_text_label | REDUNDANT | identical name+body in test_asm_encoding.py
- ::test_unresolved_numeric_local_label_errors | REDUNDANT | (dup) test_unresolved_numeric_label_raises
- ::test_jmp_into_rdata_section_defers_reloc | REDUNDANT | (dup) test_jmp_target_defined_in_rdata_defers_to_reloc
- ::test_bss_section_directive_plain_form | REDUNDANT WEAK | covered by test_bss_directive_accumulates_size
- ::test_text_and_data_directive_plain_forms | REDUNDANT | (dup) test_data_directive_switches_to_rdata
- ::test_space_directive_in_bss_accumulates_bss_size | REDUNDANT | (dup) test_bss_directive_accumulates_size
- ::test_space_directive_outside_bss_zero_fills | REDUNDANT (partial) | (dup) test_space_directive_in_text_emits_zeros, same buf() path, other section
- ::test_data_directive_in_bss_section_errors | REDUNDANT | (dup) test_bss_section_rejects_data_emission
- ::test_asciz_unrecognized_escape_falls_back_to_literal_char | REDUNDANT | (dup) test_asciz_unknown_escape_uses_char_code
- ::test_asciz_non_locale_char_falls_back_to_utf8 | REDUNDANT WEAK | host-locale dependent: on a UTF-8 Linux locale CJK encodes natively so the fallback branch is not exercised yet test passes; (dup, deterministic) test_asm_encoding.py::test_asciz_falls_back_to_utf8_when_locale_cannot_encode
- ::test_call_numeric_target_is_defensive_and_unreachable_via_source | REDUNDANT TRIVIAL | exact dup of test_asm_encoding.py::test_call_numeric_target_unsupported; both test an unreachable guard
- ::test_encode_emits_no_bytes_is_reported | TRIVIAL | monkeypatches _encode to a no-op to hit an unreachable guard (coverage-driven)
- test_asm_encoding.py::test_call_numeric_target_unsupported | TRIVIAL | unreachable guard, coverage-driven
backend/test_pe_writer_more.py (all REDUNDANT; test_pe_writer.py has the same four with equal/stronger needles):
- ::test_missing_entry_symbol_raises, ::test_bss_symbol_without_data_section_raises (needle only "bss"), ::test_unknown_symbol_section_raises, ::test_unsupported_reloc_kind_raises
backend/test_flir_to_asm_coverage.py:
- ::test_unhandled_instruction_raises | REDUNDANT | (dup) test_flir_to_asm_errors.py::test_emit_inst_rejects_unknown_instruction_opcode (checks message)
- ::test_binop_unsupported_float_op_raises | REDUNDANT | (dup) errors::test_emit_binop_rejects_unsupported_float_op
- ::test_binop_unsupported_int_op_raises | REDUNDANT | (dup) errors::test_emit_binop_rejects_unsupported_int_op
- ::test_float_param_via_stack | REDUNDANT TRIVIAL | (dup) errors::test_stack_spilled_parameters_beyond_fourth (asserts [rbp + 48]); this one asserts only label "fsf_g:" exists
- ::test_struct_param_via_stack, ::test_cvt_struct_to_ptr_bitcast_fallback, ::test_load_struct_value, ::test_store_struct_value | TRIVIAL | only assert "fsf_f:" in asm (the function label is always emitted); they only prove no exception
backend/test_pe_inspect.py:
- ::test_imported_dlls_sorted | TRIVIAL INCORRECT-NAME | feeds a PE with no imports; asserts [] so it never tests sorting (mutation: `sorted(...)` -> reversed list survived 211/211)
cli:
- cli/test_targets.py::test_host_platform_unknown_raises, ::test_host_arch_unknown_raises | REDUNDANT | (dup) test_targets_resolution.py::test_unknown_host_error_messages_name_the_value and ::test_resolve_target_unknown_host_propagates_only_when_flag_unset (which also check the message)
- cli/test_check.py::test_no_input_specified | REDUNDANT | (dup) test_main_arg_errors.py::test_no_input_error_message (checks message)
- cli/test_check.py::test_file_not_found | REDUNDANT WEAK | (dup) test_main_arg_errors.py::test_file_not_found_error_text
- cli/test_check.py::test_unsupported_target | REDUNDANT WEAK | (dup) test_main_arg_errors.py::test_unsupported_target_error_text_names_supported_targets
- cli/test_diagnostics.py::test_debug_mode | REDUNDANT | (dup) test_main_arg_errors.py::test_debug_flag_logs_parsed_args (same -d --check on good file, different marker string)
- cli/test_compiler_pipeline.py::test_full_pipeline_happy_path | TRIVIAL | asserts `analyzer is not None`; every compile exercises it
- cli/test_main_internals.py::test_compile_file_default_link_args_none | TRIVIAL | only hits `if link_args is None`; result True would occur either way
- ::test_compile_file_emit_ast_success_returns_path | REDUNDANT | test_emit.py::test_emit_ast
- ::test_compile_asm_emit_obj_unsupported | REDUNDANT | test_main_arg_errors.py::test_emit_obj_unsupported (CLI-level, checks message)
- ::test_main_dir_with_no_fire_files_warns_but_succeeds | REDUNDANT WEAK | test_dir_batch.py::test_dir_with_no_fire_files_warns (checks the warning text; this one doesn't)
- ::test_main_output_move_failure_exits_1 | REDUNDANT (partial) | test_emit.py::test_emit_ast_output_rename_failure_exits_nonzero covers the same branch end-to-end
- ::test_lint_text_import_resolution_exception_returns_parser_errors | TRIVIAL | asserts isinstance(list); see bug 2
- ::test_lint_text_preprocess_exception_returns_errors_so_far | TRIVIAL | isinstance(list)
- ::test_lint_text_semantic_analysis_exception_is_swallowed | TRIVIAL/WEAK | asserts no raise + list
harness:
- harness/test_matrix.py::test_sample_mode_differs_per_test_key | TRIVIAL | name says "differs", assertion only checks both contain O0 (its own comment admits it)
- harness/test_matrix.py::test_cell_ids_are_matrix_invariant_expectation_keys | TRIVIAL | `not hasattr(run_kind_cls, "expected_for_cell")`; documentation test
float128:
- float128/test_oracle_vectors.py::test_all_generated_vectors_are_self_consistent | TRIVIAL REDUNDANT | ~half of vectors() compute `expected` with the same oracle function being replayed (e.g. from_int(2**113), parse('0.1'), div(ONE,THREE), format_f(parse('123456.789'))); the rest are the same constants as test_oracle_units. vectors() is not used anywhere else (not replayed against the runtime)
- float128/test_oracle_units.py::test_cross_checks_large_int_round_trip | REDUNDANT | test_from_int_to_int already round-trips 0,1,-1,2**52,2**63,10**30 (only adds 2**113)

### MERGE-candidates
- test_assembler_unit.py::test_unary_reg16 (`not ax`) and ::test_mov_mem_imm8 (`mov byte ptr [rbp-1], 5`): forms not in CASES; move into CASES so they get byte-compared, delete the len>0 versions.
- test_assembler_unit.py::test_quad_and_long_directives: asserts only len==12; fold into test_asm_encoding exact-value directive tests.
- test_flir_to_asm_coverage.py 8 test_escape_asciz_* : fold into one @t.params table.
- test_main_internals.py 3 _normalize_cli_path tests -> one params test.
- test_check.py::test_invalid_platform_choice_rejected + test_invalid_arch_choice_rejected + test_main_arg_errors::test_invalid_emit_choice_rejected + test_invalid_message_format_rejected -> one params test checking rc==2 and "invalid choice".
- test_diagnostics.py::test_debug_mode + test_main_arg_errors::test_debug_flag_logs_parsed_args.

### FIX-ASSERTION (WEAK / INCORRECT)
- backend/test_flir_to_asm_coverage.py::test_cvt_u64_to_f64 | WEAK | asserts "cvtsi2sd" in asm, which the signed path also emits. Mutation: removed `or rax, rcx` (sticky-bit fixup) in the u64 branch: all 211 backend tests pass; e2e conversions (20/20) also pass. Should assert the test/js/shr/and/or/add sequence.
- ::test_cvt_f64_to_u64 | WEAK | substring "cvttsd2si" only
- ::test_cvt_int_to_bool | WEAK | "setne al" substring only
- ::test_cvt_float_to_narrow_int_kinds | WEAK | "movsx rax"/"movzx eax"/"mov eax, eax" substrings are emitted by many unrelated paths (loads/frame code); no per-conversion association
- ::test_struct_param_via_stack | WEAK | mutation: changed stack offset for 5th+ struct param (`16 + arg_index*8` -> `24 + ...`) survived all backend python tests; only e2e functions/functions_many_params.fire caught it (runtime timeout). Assert the [rbp + 48] read.
- ::test_call_struct_arg_on_stack | WEAK | `lea rax, [rbp` substring only
- ::test_call_extern_float_arg | WEAK | doesn't check the matching int register copy its comment promises
- ::test_emit_globals_f128_and_f32 | WEAK | only checks symbol labels present, not encoded data
- ::test_val_off_missing_slot_raises | WEAK | `except AsmError: pass` with no message check
- test_flir_to_asm_errors.py::test_f32_and_f64_globals_use_distinct_encoding_paths | WEAK | name claims distinct encodings but asserts labels and `.quad 42` for the I32 only; f32 packing (1.5 -> 0x3FC00000) never asserted
- test_flir_to_asm_errors.py::test_mutable_global_emits_bss_section | KEEP, but docstring is STALE/WRONG: claims driving runtime_state_get/set from .fire "currently segfaults"; std/internal/alloc.fire uses runtime_state_get/set in the allocator and every heap-using test passes. Same file/coverage.py header says u64<->float "known to fail assembly" (fixed by commit 913dd4c). Docstrings should be corrected.
- test_assembler_unit.py::test_align_directive_is_a_noop | WEAK | len>0 only; padding being emitted would still pass
- test_assembler_unit.py::test_lea_missing_closing_bracket_errors, ::test_bad_asciz_errors | WEAK | AssemblerError with no needle
- test_pe_writer.py::test_write_pe_smoke | WEAK | checks MZ/PE signature only; no section table/entry/import check
- backend/ (gap) pe_inspect name-import path: no unit test builds/reads a name-based import. Mutation: `funcs.append(_read_cstr(...))` -> `funcs.append('x')` survived 211/211; the run kind only checks DLL names (and a read_imports returning {} would let a binary importing user32/msvcrt pass).
- cli/test_check.py::test_check_invalid_file, test_no_link_rejected, test_input_is_directory | WEAK | returncode==1 with no message check
- cli/test_check.py::test_invalid_platform_choice_rejected / _arch_ | WEAK | rc 2 only
- cli/test_check.py::test_default_target_compiles | name misleading: pyunit.run_compiler appends --platform/--arch from FIRESCRIPT_TEST_TARGET, so on matrix/wine runs it is NOT testing the default target
- cli/test_dir_batch.py::test_dir_and_output_conflict, test_dir_not_found | WEAK | rc only
- cli/test_imports.py::test_import_with_syntax_error | WEAK | rc==1 only; no message; name suggests post-merge error ordering but nothing asserts it
- cli/test_main_arg_errors.py::test_invalid_message_format_rejected | WEAK | rc 2 only
- cli/test_main_internals.py::test_setup_logging_json_format | WEAK | asserts handler count only; never checks output is JSON
- cli/test_main_internals.py::test_lint_text_parser_errors_no_imports_returns_early | WEAK | `len(errors) > 0`; no line/col/message
- (gap) lint_text returning semantic errors is untested: mutation `errors.extend(analyzer.errors)` -> `pass` survived all 113 cli tests; lint_text has no other test (no LSP tests exist: grep).
- cli/test_targets_resolution.py::test_supported_targets_str_lists_every_supported_target | TRIVIAL | last assertion recomputes the implementation's own formula
- cli/test_targets_resolution.py::test_target_str_and_choices | WEAK | change-detector pinning exact PLATFORM_CHOICES list
- cli/test_dir_batch.py::test_dir_partial_failure | INCORRECT (pins a bug) | asserts returncode==0 while the output says "1 successful, 1 failed"; see bug 1
- cli/test_main_arg_errors.py::test_dir_with_unsupported_target_counts_failures | INCORRECT (pins a bug) | asserts returncode==0 with "0 successful, 1 failed"
- harness/test_matrix.py::test_default_registry_has_only_default_cell | WEAK | calls all_cells(axes=[]) explicitly so it never looks at the real AXES registry its docstring talks about
- harness/test_directives.py error tests (unknown key, misplaced, repeated, double space) | WEAK | catch DirectiveError with no message check; wrong-reason raises pass
- float128/test_oracle_units.py::test_arithmetic_spot_checks | WEAK | ~14 vectors, no rounding-tie case; `in (ZERO, o.pack(0,0,0))` is a one-element set (pack(0,0,0)==0)
- ::test_from_f64_to_f64 | WEAK | exact-representable values only; no subnormal/rounding/NaN payload
- ::test_parse | WEAK | exact values only; no rounding/overflow/underflow
- ::test_format_f, ::test_format_g | WEAK | mutation of the decimal tie-to-even rule survived (see below); format_g asserts ZERO twice
- ::test_cross_checks_add_sub_round_trip | WEAK | 3 vectors, tolerance 2^-112 relative
- ::test_cross_checks_parse_format_round_trip | WEAK | tolerance 1e-5 relative on 5 inputs
- Weak/INCORRECT-by-design: test_assembler_unit.py::test_alu_unsupported_forms_raises (in asm_encoding.py) pins that `add [rax], rcx` is "unsupported" though valid x86 (fine as a closed-grammar limitation; mention in test comment).

### KEEP (clusters)
- backend/test_asm_encoding.py::test_encode (96 cases; verified effective, see gaps above) and its unique error-path/directive tests (test_parse_mem_*, bss/section/directive tests, test_nop_encodes_single_byte, test_unsupported_mnemonic_raises, test_generic_python_exception_is_wrapped, test_mov_*_raises, test_alu_unsupported_forms_raises, test_unresolved_numeric_label_raises, test_rip_reference_to_earlier_text_label, test_jmp_*, test_asciz_*, test_long/byte/space directive tests).
- backend/test_assembler_unit.py: test_mem_unknown_base_plus_index_errors, test_call_to_undefined_runtime_symbol_errors, test_asciz_octal_escape.
- backend/test_pe_writer.py (5), backend/test_pe_inspect.py (8: rva/cstr helpers, non-MZ, missing PE sig, non-PE32+, zero import dir, dir RVA outside section, ordinal thunk).
- backend/test_flir_to_asm_errors.py: unknown opcode, unsupported float/int binop, stack-spilled float param.
- backend/test_flir_to_asm_coverage.py: 8 _escape_asciz tests, test_binop_int_and_or, test_cvt_f32_to_u64.
- cli/: test_version, test_check_valid_file (race hazard), test_message_format_json, test_dir_batch_compile, test_file_and_dir_together, test_dir_with_no_fire_files_warns, all of test_emit.py, test_emit_deps*, test_import_not_found_compile, test_main_arg_errors (12 others), test_main_check_output_flag, test_output (2), test_paths (2), test_compiler_pipeline guard tests (3), test_targets_resolution (9), test_main_internals (the compile_file/_compile_asm/_compile_runtime_file exception-branch tests, normalize/log tests, main() branches).
- harness/: test_directives (8), test_expectations (13), test_matrix (5), test_seeds (7), test_selectors (7).
- float128/test_oracle_units.py: test_unpack_hand_verified_constants, test_min_subnormal_value (independent Fraction), test_to_halves, test_comparisons, test_from_int_to_int, (values verified vs quadmath).

## Detailed evidence (mutations)
Private copy at /tmp/tmp.YI1nWilrne/repo (rsync of repo, no .git). Env: FIRESCRIPT_TEST_TARGET=windows/x86_64 FIRESCRIPT_TEST_RUN_PREFIX=wine WINEDEBUG=-all python tests/run.py <path> --no-coverage.
1. tests/support/float128_oracle.py::_rne: tie branch `if lsb:` -> `if False:` (ties never round up). `tests/python/float128`: 14/14 passed. SURVIVED.
2. float128_oracle.py::_round_digits: `if prev % 2 == 1:` -> `== 0` (decimal tie-to-even inverted). 14/14 passed. SURVIVED.
3. assembler.py _JCC["jb"]: 0x82 -> 0x83. tests/python/backend 211/211 passed; also e2e conversions uint64/int_float matrix passed. SURVIVED (jb only used in fs_rt_mem_copy overlap).
4. assembler.py setcc `force=r.num in (4,5,6,7)` -> `(4,5,6)`. backend 211/211 passed. SURVIVED.
5. flir_to_asm.py u64->float: removed `out.append("    or rax, rcx")`. backend 211/211, e2e conversions 20/20 passed. SURVIVED both.
6. flir_to_asm.py struct stack param offset 16 -> 24. backend 211/211 passed (SURVIVED unit), e2e functions_many_params.fire timeout (killed e2e).
7. main.py lint_text: removed `errors.extend(analyzer.errors)`. tests/python/cli 113/113 passed. SURVIVED.
8. pe_inspect.imported_dlls -> reversed unsorted list: backend 211/211 passed. SURVIVED. pe_inspect name-import `funcs.append(name)` -> `funcs.append('x')`: 211/211 passed. SURVIVED.
9. Oracle correctness (not a mutation): scripts in the scratchpad audit/ dir (fz.py, fz2.py, q.c) compare the oracle to libquadmath: 0 diffs.
Not reproduced: parallel race on build/functions.exe (8 runs of test_check+test_output with --jobs 8 all passed).

## Compiler bugs / questionable behaviours discovered
1. `python firescript/main.py --dir <dir>` exits 0 even when every file in the dir failed to compile (main.py ~L615-636 only logs "N successful, M failed"; no sys.exit(1)). Repro: dir containing bad.fire with `x: int32 = ;` -> exit=0. Two tests pin this (test_dir_partial_failure, test_dir_with_unsupported_target_counts_failures). Per project rule do not edit the tests to hide; decide intended behavior and fix both.
2. `lint_text("import definitely_missing_module_xyz.helper;\nx: int32 = helper(1);\n")` returns [] (no diagnostic) because resolve_imports exception is swallowed (`except Exception: return errors`). The LSP therefore shows nothing for an unresolved import while the CLI reports "Import resolution failed". Likely a bug (or at least untested; test only asserts isinstance list).
3. Stale docs in test comments: runtime_state_get/set "segfaults" (false), u64<->float "fails to assemble" (fixed in 913dd4c).
4. Assembler cannot encode `add qword ptr [mem], reg` (valid x86) - closed-grammar limitation pinned as an error; fine if the backend never emits it.
