# firescript Test Suite

This document provides an overview of the test suite for the firescript compiler.

## Test Organization

Test source files live under `tests/sources/<category>/`, grouped by feature area (e.g. `tests/sources/arrays/`, `tests/sources/classes/`). Invalid/error-triggering sources live under the mirrored `tests/sources/invalid/<category>/`. All expectations for a `.fire` test live **inside the test file itself** as magic-comment directives and a trailing output block — there are no sidecar golden files (the one exception is FIR/FLIR IR snapshots; see "Snapshot Tests" below). Python-based tests (compiler-infrastructure unit tests, CLI invocation tests) live under `tests/python/<category>/test_*.py` and always run alongside the `.fire` suite.

The single entry point for every kind of test is `tests/run.py` (`python tests/run.py`). It replaces the previous eight separate runners (`golden_runner.py`, `error_runner.py`, `cli_runner.py`, `asm_encoding_tests.py`, `fir_unit_tests.py`, `fir_snapshot_runner.py`, `run_tests.py`, `float128_oracle.py`'s self-tests). See `docs/internal/development/test_harness_v2.md` for the full harness architecture spec.

Helper/provider modules that are imported by other tests but never compiled standalone (e.g. `utils.fire`, `math_utils.fire`, files ending in `_provider.fire`) live alongside the tests that import them, since imports resolve relative to the importing file's own directory, and carry a `//@ helper` directive so the harness never treats them as a standalone test case.

## Running Tests

```bash
# Run everything (all kinds: run, compile-fail, snapshot, python)
python tests/run.py

# Run a specific test file (works for .fire and .py)
python tests/run.py tests/sources/operators/operators_arithmetic.fire

# Run everything under a category (checks both sources/<cat> and python/<cat>)
python tests/run.py arrays

# Run only one kind
python tests/run.py kind:run
python tests/run.py kind:compile-fail
python tests/run.py kind:snapshot
python tests/run.py kind:python

# Run one Python test function
python tests/run.py tests/python/cli/test_emit.py::test_emit_ast

# Glob test ids by name
python tests/run.py name:generics_*

# Bless mode: rewrite in-file EXPECT blocks / //~ annotations / snapshots to
# match current output (review the diff before committing!)
python tests/run.py --update

# List matching test ids without running them (also the discovery debugging tool)
python tests/run.py --list

# Verbose per-case output, stop after first failure, parallelism, fixed seed
python tests/run.py --verbose
python tests/run.py --fail-fast
python tests/run.py --jobs 4
python tests/run.py --seed 0x1c9e4d2ab0f37e51

# Coverage report (on by default for unfiltered runs when `coverage` is installed)
python tests/run.py --coverage
python tests/run.py --uncovered   # show only uncovered lines

# CI profile (quick matrix, full determinism sampling)
python tests/run.py --profile ci
```

The master seed for the run is always printed as the first and last line of
output (`Seed: 0x...`) so any run -- including anything that used sampling
(matrix cells, determinism sampling) -- is exactly reproducible with `--seed`.

### `run` kind (golden tests)

Discovers every `tests/sources/**/*.fire` not under `invalid/` and not marked
`//@ helper`. Compiles the file, runs the binary (verifying it imports only
`kernel32.dll` via the pure-Python PE inspector -- firescript binaries are
freestanding), and compares normalized stdout against the trailing `/* EXPECT
... */` block in the source file (see "EXPECT Block Format" below).

### `compile-fail` kind (error tests)

Discovers every `tests/sources/invalid/**/*.fire` not marked `//@ helper`.
Invokes `firescript/main.py --check --message-format json` in a subprocess
and compares the JSON diagnostic events against the file's `//~ ERROR`
line-anchored annotations (see "Invalid Tests" below). Message wording can
change freely without breaking tests; only the diagnostic code, line, and
(optionally) column are checked.

### `snapshot` kind (FIR/FLIR IR dumps)

Discovers every `.fire` file carrying `//@ snapshot: fir` and/or `//@
snapshot: flir` (a small, curated subset of the feature surface -- 25 cases
today). Compiles each case twice via `--emit-fir`/`--emit-flir` (the two
dumps must be byte-identical -- an IR-dump determinism check) and compares
against the golden file at `tests/snapshots/<category>/<name>.fir` /
`.flir`. This is the **one deliberate sidecar exception**: IR dumps are
large, machine-generated, and would harm readability if inlined into the
test source.

### `python` kind (compiler-infrastructure and CLI tests)

Discovers every `tests/python/**/test_*.py`; every top-level `test_*`
callable is one test case, run in a worker process using the `pyunit`
micro-framework (`from harness import pyunit as t`; see
`tests/harness/pyunit.py` for the full API: `t.require`, `t.require_eq`,
`t.tmpdir()`, `t.run_compiler()`, `t.subtest()`, `t.params()`; there is no
`t.skip()` -- this harness has no skip capability, see CLAUDE.md).
Plain `assert` also works. Covers:

- `tests/python/parser/` -- direct (in-process) unit tests for
  `firescript/parser/`'s defensive "impossible" branches and dead guards
  that can't be reached by compiling a full real source file: `test_parser_base.py`
  (error-reporting wrappers, literal-suffix inference, comment-anchored
  diagnostic positions, EOF edge cases), `test_declarations_dead_guards.py`
  and `test_declarations_coverage.py` (`_parse_import_symbol_group`,
  `_parse_class_definition`, `_parse_constraint_declaration`,
  `_parse_function_definition`/`_parse_generator_definition` guards
  duplicating checks the top-level `parse()` dispatcher already performed),
  `test_expressions_dead_guards.py` (`parse_array_access`,
  `parse_increment_or_decrement` defensive None branches),
  `test_type_system.py` and `test_type_system_dead_guards.py`
  (`_annotate_value_category`, `_get_node_type` fallbacks unreachable
  because the parser always pre-annotates `return_type`,
  `_infer_generic_type_args` edge cases, array-cast rejection), and
  `test_ast_node.py` (`ASTNode`'s None-children rejection and
  `__repr__`==`__str__`). `_dead_guard_helpers.py` is a shared (non-test)
  helper module, not a test file itself. `test_declarations_dead_guards_more.py`
  (with its own shared helper module `_dead_guard_helpers2.py`, a
  differently-shaped API from `_dead_guard_helpers.py`) adds further
  declarations.py dead-guard coverage: `_parse_function_definition`'s
  invalid-return-type/missing-name/unclosed-array-bracket/missing-open-paren/
  missing-body-brace/type-param-consume-failure branches,
  `_parse_generator_definition`'s missing-GENERATOR-token and
  missing-body-brace branches, `_parse_import`'s `@`-segment
  consume-failure branch, `_parse_import_symbol_group`'s consume-failure
  branch, `_parse_class_definition`'s missing-CLASS-token and
  type-param-consume-failure branches, `parse()`'s top-level
  blank-placeholder-token skip and pending-export-before-constraint-dispatch
  branches. `test_statements_dead_guards.py`/`test_statements_coverage.py`
  and `test_type_system_dead_guards_more.py`/`test_type_system_coverage.py`
  (with their own shared helper `_helpers.py`) push
  `firescript/parser/statements.py` to 100% and `firescript/parser/type_system.py`
  to 99%: dead-guard coverage for `parse_if_statement`/`parse_while_statement`/
  `parse_for_statement` off-token direct calls, `parse_scope`'s brace guard,
  `parse_variable_assignment`/`parse_function_call` precondition rechecks,
  for-in's redundant type/identifier/`in`-keyword rechecks, `_get_node_type`'s
  dead node-kind fallbacks, and `_infer_generic_type_args`/unary/binary/cast
  defensive branches; plus real-syntax coverage for a nested `directive`/a
  function returning `generator<T>` defined inside a function body (which
  `ast_to_fir.py` cannot lower -- a newly-found, not-fixed crash, see the
  test module docstrings) and a generic function reusing the same type
  parameter for multiple arguments.
- `tests/python/cli/` -- `firescript/main.py` invocation behavior never
  exercised by the golden/error/snapshot kinds (`-v`, `--check`, `--emit
  ast`/`asm`/`--emit-fir`, `--emit-deps`, `-o` renaming, `--dir` batch
  compilation, `--message-format json`, `-d` debug mode, import-resolution
  errors), split by area: `test_check.py`, `test_emit.py`,
  `test_dir_batch.py`, `test_output.py`, `test_diagnostics.py`,
  `test_imports.py`, `test_paths.py` (`safe_relpath` cross-drive fallback).
  `test_main_internals.py` covers the rest of `main.py` in-process
  (not via subprocess): `_normalize_cli_path`, `setup_logging` re-entry,
  `_compile_asm`/`_compile_runtime_file`'s
  exception branches, `compile_file()`'s per-stage exception
  handling (monkeypatching `CompilerPipeline`/`ASTToFIRConverter`/
  `FIRToFLIRLowering` methods to raise), `lint_text()`'s early-exit
  branches, and `main()`'s CLI-level error branches (invalid path args,
  unsupported target, output-move failure), driven by monkeypatched
  `sys.argv` and caught `SystemExit`.
  `test_compiler_pipeline.py` covers `firescript/compiler_pipeline.py`'s
  `CompilerPipeline` (the parse()-must-precede-later-stages guard clauses
  on `resolve_imports`/`preprocess`/`analyze_semantics`, and a full
  happy-path run) in-process. `test_frontend_pipeline.py` covers
  `firescript/frontend_pipeline.py`'s import-merge and deferred-identifier
  logic in-process (real small on-disk import graphs via
  `CompilerPipeline`, plus a direct call with a hand-built resolver return
  value for the one branch -- a resolver-key mismatch on a stdlib-style
  short relative sibling import -- only reachable by editing
  `firescript/std/` itself). Note: these two call the pipeline in-process
  rather than via `t.run_compiler()` (subprocess), since subprocess runs
  don't register against this process's coverage measurement.
- `tests/python/backend/test_asm_encoding.py` -- differential + unit tests
  for the pure-Python x86-64 assembler; unit assertions always run,
  differential comparison against MinGW `as` only when `as` is on `PATH`.
  `test_assembler_unit.py` adds further coverage-targeted error/edge
  branches not exercised by the differential CASES table: malformed memory
  operands, 16-bit ALU/mov/unary forms, `movq xmm,xmm` (including
  extended-register REX forcing), unsupported mnemonics/operand-form
  errors, directive dispatch (`.text`/`.data`/`.bss`/`.space`/`.quad`/
  `.long`/`.align`), `.asciz` octal/unrecognized escapes and
  non-locale-encodable characters, and the relocation/fixup resolution
  paths (backward rip-relative code labels, a rip-relative branch into
  `.rdata`, unresolved runtime-call symbols); also drives two internals
  directly for guards provably unreachable from any assemble()-able
  source text (a numeric `call` target, and `_encode` emitting zero
  bytes).
- `tests/python/backend/test_flir_to_asm_errors.py` -- unit tests for
  `firescript/codegen/x86_64/flir_to_asm.py` branches impractical to reach
  through a full `.fire` compile (mutable-global `.bss` emission, f32/f64
  global encoding, the catch-all `AsmError` for an unhandled FLIR opcode,
  unsupported float/int `BinOp` operators, stack-spilled parameters beyond
  the 4th). FLIR modules are hand-built directly from `flir.ir` objects and
  handed straight to `FLIRToAsmBackend`, same construction style as
  `tests/python/flir/test_verifier_structure.py`. Also documents a known
  bug: driving the mutable-global path through actual `.fire` source
  (`runtime_state_get`/`runtime_state_set`) compiles but segfaults at
  runtime.
- `tests/python/backend/test_flir_to_asm_coverage.py` -- coverage-focused
  unit tests for `firescript/codegen/x86_64/flir_to_asm.py`, driving
  `FLIRToAsmBackend` directly against hand-built `flir.ir` modules (no
  assembler invoked): the `.asciz` escape-mapping branches, float128/f32
  module-level globals, 5th+ struct/float parameters and call arguments
  passed on the stack, the dangling-value/unhandled-opcode/unsupported-binop
  defensive `AsmError` paths, and the u64<->float and narrow-int conversion
  branches (exercised directly so the known *assembler*-stage uint64<->float
  bug -- see `tests/sources/known_issues/` -- doesn't block codegen coverage).
- `tests/python/backend/test_pe_writer.py`/`test_pe_writer_more.py` -- unit
  tests for `firescript/backend/windows/pe.py`'s `write_pe`, hand-building
  `ObjectImage`/`Reloc` instances to hit its defensive error branches
  (missing `firescript_entry` symbol, a `bss`-section symbol with no
  `.data` section, an unknown symbol section, an unsupported reloc kind)
  that a normal successful compile never reaches.
- `tests/python/fir/` -- unit tests for `firescript/fir/`: builder
  construction (`test_builder.py`, including `BasicBlock.set_terminator`'s
  double-terminator guard), textual dump format verified against
  the spec example in `docs/internal/development/fir_spec.md`
  (`test_dump.py`, including char-literal/`Borrow`/`Clone`/`Unreachable`
  rendering, a global-constant dump, and the unsupported-operand-kind
  `TypeError` guard), the Tier-1 FIR verifier
  (`docs/internal/development/ir_verifier_spec.md`) -- structural/def-use
  rules (FIRV-S, FIRV-D) in `test_verifier_structure.py`, type/local/
  generator rules (FIRV-T, FIRV-L1-L2, FIRV-G1-G3) in
  `test_verifier_types.py`, and Tier-2 ownership dataflow rules (FIRV-O1-O7,
  FIRV-L3, FIRV-G4, FIRV-E1) in `test_verifier_ownership.py` plus
  `test_verifier_ownership_extra.py` (dataflow-merge divergent-state
  behavior, rarely hit identifier-resolution/enum-guard branches, and a
  few pure helper functions -- some cases call `verify_ownership`/
  `verify_no_shadowing`/`verify_generator_dominance`/
  `verify_enum_payload_guards` directly against a hand-built
  FIRFunction/CFG/idom, bypassing `FIRModule.validate()`'s Tier-1 pass, to
  reach a few Tier-2 branches Tier-1 would otherwise always intercept
  first). `test_ir_analysis.py` covers the shared CFG/dominance helpers in
  `firescript/ir_analysis.py` (used by both the FIR and FLIR verifiers)
  directly: `dominates()`'s missing-node and cyclic-idom-chain guards, and
  a basic `compute_dominators()` diamond shape. `test_verifier_more.py`
  fills further Tier-1 FIR verifier gaps (T5-T9 branches: call-result type
  mismatch, unknown struct field store, array-index/value type checks,
  `Allocate`'s unregistered-class/explicit-constructor/argument-type
  branches, `_type_assignable`'s array-size-mismatch and invalid-operand
  skip cases). Also
  `test_ast_to_fir_errors.py` -- coverage-focused unit tests for
  `firescript/ast_to_fir.py`'s internal defensive branches and edge cases
  (malformed/edge-case AST shapes semantic analysis normally rejects
  first, or that no current parser rule can produce): every
  `FIRConversionError` site (unsupported statement/expression node shapes,
  break/continue outside a loop, enum-variant construction arity,
  match-as-expression block-arm rejection, ungated directive intrinsics,
  unsupported array methods, unresolved `super()`, etc.),
  `_expr_type`/`_fir_type` fallback branches, directive-gating,
  generic-construction type-arg inference, and
  `_seal_open_blocks`/`_synthesize_zero` edge cases. Drives
  `ASTToFIRConverter` directly with hand-built `ASTNode` trees (there is no
  builder for the AST layer), following `test_verifier_heap.py`'s "build IR
  objects by hand" pattern one layer up the pipeline. These errors carry no
  `FS-*` code for the `//~ ERROR <CODE>` compile-fail convention, so they
  can't be exercised through `tests/sources/**/*.fire`.
  `test_ast_to_fir_pipeline_errors.py` covers a different slice of the same
  file's `FIRConversionError` branches -- ones only reachable by feeding
  `ASTToFIRConverter` a real parsed/preprocessed/semantically-analyzed AST
  built from small malformed-at-the-FIR-level source snippets (driven
  directly through `compiler_pipeline.py`, since `--check` never reaches
  AST->FIR conversion), rather than a hand-built AST; it also documents
  several newly-found, not-fixed bugs (a `for-in`/`FIRV-T4` verifier crash
  for array-returning functions; `const string`/`const bool`/`const char`
  each failing to compile end-to-end for three separate, unrelated reasons
  downstream of `ast_to_fir.py`). Also
  `test_verifier_ownership_extra.py` -- additional gap-filling cases
  (FIRV-O6 via Clone, FIRV-O4 via a doubled `borrow_mut` argument, FIRV-O7
  via a LoadVar-wrapped borrow parameter, the arg_modes/args
  length-mismatch no-cascade guard, and small pure helpers
  `_ident_text`/`_generator_identity`/`_enum_type_name`).
- `tests/python/flir/` -- unit tests for `firescript/flir/`'s verifier
  (`docs/internal/development/ir_verifier_spec.md`), FLIR modules built
  directly from `flir.ir` objects (there is no FLIRBuilder helper):
  structural rules (FLIRV-S) in `test_verifier_structure.py`, type/memory
  rules (FLIRV-T, FLIRV-M1-M3) in `test_verifier_types.py`, and Tier-2
  heap-token allocation-lifecycle rules (FLIRV-A1-A5, FLIRV-M4) in
  `test_verifier_heap.py`, and defensive/unreachable-from-source guards in
  the same Tier-2 heap-token verifier (`_meet_states([])`, `_HeapChecker
  .run()` on a function with no blocks or with a block outside
  `cfg.reachable`, and `_ident_text`'s dead `"slot"`-kind branch) in
  `test_heap_verifier_defensive.py`, driven directly against the internal
  classes since flir/verifier.py's Tier-1 gate rules out all of these at
  the real pipeline's entry point. `test_verifier_extra.py` fills remaining Tier-1
  coverage gaps (struct layout edge cases, an empty function/block, the
  rest of the T1-T6/M1-M3 branches) and directly unit-tests
  `_binop_operand_ok`/`_ptr_lenient_eq`/`_resolve_struct_type` (the last of
  which is dead code -- see its test's comment). `test_dump.py` covers
  `firescript/flir/textual.py` (mutable/immutable global dump lines, the
  foreign-value ValueError path). `test_ir_helpers.py` covers small
  standalone helpers in `firescript/flir/ir.py` (FLIRType predicates/
  dunder methods, `FLIRStruct.field`, `FInst`'s default `format()`, block/
  function guard clauses) not otherwise exercised elsewhere. Also unit
  tests for `firescript/flir/lowering.py`
  (FIRToFLIRLowering), driven directly via `fir.FIRBuilder` rather than
  through the full compiler, covering internal branches that are either
  unreachable through any valid FIR the real pipeline produces (defensive
  `LoweringError`s, `SyscallResult`-without-runtime-module bootstrapping)
  or awkward to force through the parser: `test_lowering_defensive_errors.py`
  (every `LoweringError`/assert site, plus the MoveInst/BorrowInst/CloneInst
  passthrough and non-short-circuit `&&`/`||` fallback that ast_to_fir.py
  never actually emits) and `test_lowering_type_edge_cases.py` (lower_type/
  lower_type_str/render_concrete/ensure_struct branches for `SyscallResult`,
  unsubstituted generic parameters, and `GeneratorType`/`FunctionType`/
  `GenericInstanceType` shapes lowered outside their normal call sites).
  Also `test_lowering_float128.py` -- the compile-time decimal-string ->
  IEEE binary128 literal parser (`_decimal_to_f128_bits`): signs, scientific
  notation, exponent overflow/underflow, subnormals, round-half-even ties
  (cross-checked against `tests/support/float128_oracle.py`, an independent
  implementation), and malformed input -- distinct from
  `tests/python/float128/`'s *runtime* soft-float oracle tests.
  `test_lowering_f128_decimal.py` covers further `_decimal_to_f128_bits`/
  `_round_half_even` edge cases (inf/nan aliases, `f128` suffix stripping,
  malformed text, subnormal clamping/rounding, zero-denominator fallback).
  `test_lowering_f128_decimal_more.py` adds further cases (rounding-carry
  overflow to infinity, subnormal significand clamping, the exponent-
  correction `elif` branch proven mathematically unreachable). `test_textual_dump.py` covers `firescript/flir/textual.py`'s foreign-value
  rejection, global-constant rendering, and `FLIRFunction.validate()`'s
  throwaway-module wrapper.
- `tests/python/float128/` -- self-tests for the binary128 correctness
  oracle (`tests/support/float128_oracle.py`): hand-verified constants and
  arithmetic/comparison/parse/format checks (`test_oracle_units.py`), plus
  self-consistency of every generated test vector (`test_oracle_vectors.py`).
- `tests/python/harness/` -- the harness's own tests (directive parser,
  EXPECT/`//~` parsing and rewriting, seed derivation, matrix engine,
  selector matching). The harness ships with its own test coverage since it
  is the arbiter of every other test.
- `tests/python/imports/test_module_resolver.py` -- direct unit tests for
  `firescript/imports.py`'s `ModuleResolver` and `build_merged_ast`: default
  `import_root`, `dotted_to_path`/`path_to_dotted` fallback branches,
  `parse_file`'s FileNotFoundError/parse-error branches, cycle/external/
  relative-import rejection in `_load_module` (via monkeypatching
  `parse_file`/`dotted_to_path`/`Module.__post_init__` to inject hand-built
  ASTs), and `build_merged_ast`'s no-name-export, duplicate-import-symbol,
  and entry-vs-import conflict (including its `ValueError` fallback)
  branches. Documents a suspected bug: `_load_module`'s cycle-detection
  branch is effectively unreachable for a genuine A->B->A import cycle,
  since `self.modules[dotted]` is populated before recursing into that
  module's dependencies (see the test's docstring and
  `tests/sources/invalid/imports/import_cycle_a.fire`, which is caught by a
  downstream undefined-symbol error instead of `CyclicImportError`).
  `test_module_resolver_extra.py` adds further `ModuleResolver`/
  `build_merged_ast` gap-filling cases (mutual-recursion resolving-guard,
  stdlib sibling-relative-import resolution within a package, topo-sort's
  external-kind skip, `append_symbol_with_deps`/`append_export` dedup
  branches) using the same hand-built-AST-injection technique.
- `tests/python/semantic/test_semantic_analyzer_internals.py` -- direct unit
  tests for `firescript/semantic_analyzer.py`'s less-common branches:
  `BorrowInfo` construction, `report_error()`'s node-less and
  index-out-of-range-fallback branches, `error()`'s convenience wrapper,
  `_is_direct_borrow_view`/`_expr_is_owned_value` fallbacks,
  `_merge_state_pair`'s BORROWED/VALID/both-moved branches,
  `_definitely_terminates`'s default-False fallback, `_validate_match_arms`'
  empty-arms/enum-mismatch/unknown-enum branches, `_validate_borrow`'s
  error-reporting branch, and several "no children -> return early" guards
  in `_analyze_node`'s dispatch (METHOD_CALL, IF_STATEMENT,
  MATCH_EXPRESSION, WHILE_STATEMENT) plus the ELIF/ELSE recurse branch.
  Also `test_semantic_analyzer_report_error.py` -- `report_error()`/`error()`
  called with no `source_code` and with an out-of-range/negative `node.index`.
- `tests/python/preprocessor/test_preprocessor_internals.py` -- direct unit
  tests for `firescript/preprocessor.py`'s internal helpers and
  `enable_and_insert_drops()`'s less-common branches: directive-already-
  present, unmentioned-variable, `_is_drop_call` var_name matching,
  return-expression walk helpers (including FUNCTION_CALL/CONSTRUCTOR_CALL
  borrow-flag-driven transfer detection), implicit-declaration inference
  from a method call on a constructor or identifier receiver, break/continue
  outside any recorded loop boundary (fallback drain), and a C-style
  for-loop with an omitted (`None`) middle clause.
- `tests/python/lexer/test_lexer_internals.py` -- direct unit test for
  `firescript/lexer.py`'s `Lexer.tokenize()` defensive `token_type is None`
  fallback (a successful regex match whose `.lastgroup` is `None`). Every
  alternative in the master token regex is a named group requiring at least
  one character, so this branch looks structurally unreachable through any
  real input; it is exercised only by monkeypatching the compiled regex
  object to return a fake match, purely to cover the branch's own
  formatting logic.
- `tests/python/log_formatter/test_log_formatter_internals.py` -- direct
  unit tests for `firescript/log_formatter.py`'s two hard-to-reach branches:
  `Colors`' Windows-console VT-mode setup (module-level code that only runs
  when `sys.stdout.isatty()` is True on Windows; exercised by monkeypatching
  `isatty` and reloading the module) and `JsonFormatter.format()`'s
  `except ImportError` fallback (forced via the `sys.modules[name] = None`
  trick).

## Test Categories

Each heading below is a directory under `tests/sources/`.

### `operators/`
- **operators_arithmetic.fire** - All arithmetic operators (+, -, *, /, %, **), compound assignment (+=, -=, etc.), increment/decrement. Includes `**` with float operands (routes through `fs_rt_pow_f64`, not the integer `fs_rt_pow_i64` path).
- **operators_boolean.fire** - Boolean operator behavior
- **operators_comparison.fire** - Equality (==, !=), relational (<, >, <=, >=) for all numeric types and strings
- **operators_logical.fire** - Logical operators (`&&`, `||`, `!`) including nested and combined conditions
- **unary_test.fire** - Unary numeric operators (-, +)

### `control_flow/`
- **control_flow_if.fire** - if/else/else-if chains, nested if
- **control_flow_while.fire** - while loops, break, continue, nested while
- **control_flow_mixed_nesting.fire** - Interaction between for/if/while nested together
- **for_c_style.fire** - C-style for loop variations (including break/continue, nesting)
- **for_in.fire** - For-in loop over arrays (including break/continue)
- **for_in_and_match_temporaries.fire** - `for-in` over a non-identifier collection (array literal, function-call-returning string) and `match` over a non-identifier scrutinee (function-call result), exercising `ast_to_fir.py`'s temporary-value ownership-drop paths; also a sized-array declaration with no initializer and one initialized from another array identifier (not an array literal). Documents that `char` cannot be used as a `for-in` loop-variable type (the parser's for-in header only recognizes built-in type keywords).
- **empty_statements.fire** - Empty statement forms (bare `;`, empty scope `{}`) parsing cleanly in various statement positions
- **for_in_braceless_body.fire** - `for-in` loop with a braceless (single-statement) body
- **control_flow_regression_conditional_move.fire** - An owned local moved into an outer variable on only one arm of an `if`/`else` (the other arm only borrows it): previously either leaked on the borrowing arm (FIRV-O3) or double-dropped on the moving arm (FIRV-O2) once tracking was fixed to notice it, since a single trailing drop after the whole `if`/`else` can't be correct for only one of two diverging paths.

### `generators/`
- **generators_basic.fire** - Generator functions (`fn` returning `generator<T>`), `yield`, stdlib `range`/`rangeFrom`/`rangeStep`, user-defined generators, for-in over generators
- **generators_break_continue.fire** - `break`/`continue` inside a for-in loop over a generator, and nested for-in-over-generator loops
- **generators_multi_yield_sites.fire** - A generator with two distinct (syntactic) `yield` statements, forcing the multi-way resume-state dispatch chain in `lower_generator` (`generators_basic.fire`'s single-yield-site `countdown()` only ever needs a single resume block).
- **generators_frame_zero_init_types.fire** - A generator with `bool`/`float128`/copyable-class local variables, exercising `_zero_value`'s per-`FLIRType`-kind branches used to zero-initialize the generator's frame struct up front. Documents a newly-found bug: a *pointer*-kind generator local (`string`, a non-copyable class, or an array) currently crashes the compiler with an internal `FLIRV-T1` type-mismatch error, so this file intentionally avoids that combination.
- **generators_advanced.fire** - Early `return` from within a generator body (exhaustion before the loop condition would naturally end it), multiple `yield` points in one generator, and calling the same generator function from two separate for-in sites (exercises the FLIR lowering's "generator already lowered" guard). Note: a third case (a generator's body containing a for-in loop over another generator call) was tried and found to trigger an internal compiler error in `flir/lowering.py`'s generator frame lowering; see the comment in the file.

### `enums/`
- **enum_tag_only.fire** - Tag-only (no data payload) enum declarations, variant construction (`EnumName.Variant`), and reassignment (verifies the previously-held owned enum value is dropped without corrupting later allocations).
- **enum_payload_construct.fire** - Enum variants with named data payloads (e.g. `Circle(radius: float64)`), positional construction with arguments, and reassignment across variants with different payload shapes sharing the same tagged-union storage.
- **enum_owned_payload_drop.fire** - Owned payload data (a `string` field, and a class field elsewhere) is dropped correctly when the active variant goes out of scope; the destructor is tag-dispatched so only the active variant's owned fields are ever freed (never a different variant's, since payload storage is shared/overlapping). Also covers a class with an owned-enum-typed field, and 5000 construct/match/drop cycles as a leak/double-free sanity check.
- **enum_field_in_class_drop.fire** - Regression: an owned identifier (a class instance) passed as an enum variant's payload argument (`Slot.Holds(b)`) must be moved into the payload, not also auto-dropped at its own scope exit. Covers both a plain owned field (`Holder.note: Note`) and a nested owned-class-inside-enum-inside-class field (`Shelf.slot: Slot` where `Slot.Holds` carries a `Box`), verifying the payload's data survives to the point it's read via `match`.
- **enum_owned_payload_no_destructor_needed.fire** - Companion to `enum_owned_payload_drop.fire`: an owned-class payload field whose class has *no* owned fields of its own (`class_needs_destructor` is False for it), so the enum's generated destructor must free it directly via `fs_rt_free` instead of calling a nested per-class destructor.

### `match/`
- **match_statement_basic.fire** - Statement-form `match` over a tag-only enum with per-arm print side effects
- **match_payload_destructure.fire** - Payload variants destructured by declared field name, including renaming a field to a different local (`field: local`) and omitting fields a given arm doesn't need
- **match_expression_value.fire** - `match` used as a value-producing expression: as a function's `return` expression and as a variable declaration's initializer
- **match_wildcard.fire** - A `_` wildcard arm covering multiple variants not listed explicitly

### `types/`
Per-type min/max value and overflow/underflow behavior, split by numeric type:
- **types_int8.fire** / **types_int16.fire** / **types_int32.fire** / **types_int64.fire**
- **types_uint8.fire** / **types_uint16.fire** / **types_uint32.fire** / **types_uint64.fire**
- **types_float32.fire** / **types_float64.fire**
- **types_bool.fire**
- **types_tests.fire** - Basic type operations and comparisons
- **types_deep.fire** - Deep type testing (arithmetic across all widths with arbitrary values, distinct focus from the `types_<type>.fire` min/max-boundary files above)
- **char_type.fire** - `char` type: literals (`'A'`, escape chars `'\t'` `'\n'` `'\\'`), copyability, cast to string, and an unrecognized escape sequence (`'\d'`) falling back to the escaped character's own code point
- **const_declarations.fire** - Top-level `const` declarations (int32/float64/float32) becoming module-level constants; documents that `const string`/`const bool`/`const char` currently each fail to compile end-to-end for three separate, unrelated bugs (see `tests/python/fir/test_ast_to_fir_pipeline_errors.py`)
- **const_declarations_wide_types.fire** - Top-level `const float32`, and string literal escape edge cases (`\'`, trailing `\\`) that exercise the asm backend's `.asciz` escaping. Also declares (but never reads) a `const float128` to exercise the global-constant rodata emission path; see the in-file note about a real bug where reading a `float128` global back via `GlobalLoad` loses its high qword.

### `conversions/`
Split by conversion category:
- **conversions_int_widening.fire** - int8->int16->int32->int64 upcasting, chained conversions
- **conversions_int_narrowing.fire** - int64->int32->int16->int8 downcasting (potential data loss)
- **conversions_signed_unsigned.fire** - Signed<->unsigned reinterpretation
- **conversions_int_float.fire** - int<->float, float-to-int truncation
- **conversions_float_precision.fire** - float32<->float64
- **conversions_in_expressions.fire** - Casts combined with arithmetic operations
- **conversions_to_string.fire** - Numeric/bool `as string`
- **numeric_casts.fire** - Numeric type casting (downcast-focused, distinct scenarios from the `conversions_*` files above)
- **string_cast_test.fire** - String casting operations
- **string_to_numeric_casts.fire** - `as` casts from `string` to `int32`/`int64`/`uint64`/`float32`/`float64` (string -> bool and string -> char are not supported casts)
- **builtin_conversions.fire** - Free-function conversion builtins (`toInt`, `toFloat`, `toDouble`, `toBool`, `toChar`, `toString`) called directly rather than via `as` casting. Note: `toChar` on a string takes its first character's code point, it does not parse the string as a numeric char code.
- **builtin_conversions_numeric_source.fire** - Same conversion builtins as `builtin_conversions.fire`, but called with a numeric (non-string) source argument, e.g. `toInt(9.75)`, `toBool(0)`.
- **int_float_cast_matrix.fire** - `float64`/`float32` -> `uint64` (including large values requiring the sign-bit correction dance) and `float64` -> narrow `int8`/`int16`/`uint8`/`uint16`/`uint32`. Notes two real bugs found and not worked around: `int32 as bool` (and other numeric-to-bool casts) is rejected by the frontend even though `flir/lowering.py`'s `Cvt` lowering and `flir_to_asm.py`'s `_emit_cvt` both have code for an int-to-bool target, and `uint64 as float64`/`float32` always fails to assemble ("unsupported mnemonic: js") because the backend emits a `js` instruction the self-hosted assembler doesn't support.

### `strings/`
Split from a single `string_operations_comprehensive.fire` into per-behavior files (see "Splitting large test files" below):
- **strings_basics.fire** - Declaration, empty string, long strings
- **strings_concatenation.fire** - Concatenation (literal, repeated, with a cast expression, via variables)
- **strings_escapes.fire** - Escape sequences (`\n`, `\t`, `\"`, `\\`)
- **strings_comparison.fire** - `==` / `!=`
- **strings_unicode.fire** - Emoji and accented characters
- **strings_upper_lower.fire** - `.upper()` / `.lower()` ASCII case folding (mixed case, already-uppercase, empty string); implemented via `@builtin_method` in `firescript/std/internal/strings.fire`
- **string_escape_edge_cases.fire** - A redundant `\'` escape and an unrecognized escape sequence (`\q`) inside a double-quoted string literal, exercising `codegen/x86_64/flir_to_asm.py`'s `_escape_asciz()` fallback branches (the lexer's `STRING_LITERAL` regex accepts `\.` for any character, not just a fixed escape set)
- **strings_for_in.fire** - for-in iteration over strings: bare-identifier vs. fresh-expression collection, and `break`/`continue` inside the loop
- **strings_for_in_regression_conditional_move.fire** - `for (chr: string in s)` where the loop variable is moved into an outer variable on only one arm of an `if`/`else` (the run-length-encoding accumulator pattern): previously crashed with an internal FIR verifier error (FIRV-O2, "possibly moved on some paths") because the automatic per-iteration drop of the loop variable was inserted unconditionally after the whole `if`/`else` instead of only on the arm that didn't already move it.
- **strings_for_in_regression_conditional_move_mid_body.fire** - Harder variant of the above: the conditionally-moving `if`/`else` is *not* the last statement in the loop body (more code follows before the iteration ends), and the move itself isn't the last statement of its own branch either. Exercises `ast_to_fir.py`'s per-branch continuation-duplication in `_convert_for_in_string_body`/`_convert_for_in_string_if`, needed because a runtime "moved" flag can't satisfy the ownership verifier's purely-static analysis.
- **strings_for_in_regression_conditional_move_break.fire** - `break` reached immediately after the for-in-string loop variable was moved into an outer variable, inside an `if`/`else` whose other arm leaves it untouched. Exercises the interaction between the per-branch moved-tracking and `break`/`continue`'s own exit path (`_drop_loop_cleanup`).

### `arrays/`
Split from a single `array_operations_comprehensive.fire` into per-behavior files, plus pre-existing focused tests:
- **arrays_basics.fire** - Declaration, indexing, `.length()`, empty array, large array, bounds access
- **arrays_typed.fire** - int8/int64/float32/float64/string/bool element arrays
- **arrays_mutation.fire** - Element reassignment
- **arrays_iteration_for_in.fire** - for-in iteration
- **arrays_iteration_c_style.fire** - C-style for iteration
- **arrays_iteration_while.fire** - while-loop iteration
- **arrays_function_param.fire** - Array passed to a function and summed
- **arrays_length_param.fire** - `.length()` / `.size()` called on a borrowed array function parameter (size not statically known at the call site, unlike a local from an array literal)
- **arrays_move_assign_from_var.fire** - Declaring an array-typed local whose initializer is another array variable (a move), not an array literal
- **array_tests.fire** - Basic array operations
- **array_to_string.fire** - `array as string` conversion for int32, float64, string, and empty arrays (`[a, b, c]` formatting)
- **array_index_count.fire** - `.index()` / `.count()` array methods
- **array_negative_indexing.fire** - Negative index access
- **array_length_propagation.fire** - Length propagation when an unsized-array local is initialized from another array: from a runtime-length-tracked function parameter (slot metadata) and from a statically-sized array literal (const metadata).
- **arrays_of_class_instances.fire** - Arrays whose element type is a user class (owned and copyable), forcing element/index/store lowering to resolve a bare class name string through `lower_type_str`'s typedef-lookup and generic-instance branches rather than `lower_type`'s `FIRType`-object path.
- **array_dynamic_alloc.fire** - `fs_rt_array_new<T>`/`fs_rt_array_copy<T>` (compiler intrinsics gated behind `directive enable_lowlevel_runtime;`, private to `std/collections/`): allocate a `T[]` buffer of a runtime-determined element count, write/read elements, copy into a larger buffer, for `int32` and `string` element types. The primitive `std.collections.Vec<T>` (`tests/sources/std/collections/`) is built on.

### `functions/`
- **functions_basic_params.fire** - No/single/multiple parameters, return values
- **functions_calling_functions.fire** - One function calling another, multi-step internal logic
- **functions_recursion.fire** - Recursive functions (factorial)
- **functions_return_types.fire** - float/bool/string return types; also fallthrough functions (no explicit `return` on every path -- firescript doesn't enforce all-paths-return) with `bool`/`float128` return types, and an if/else where both arms already `return` (dead join block), exercising `ast_to_fir.py`'s implicit-zero-return synthesis and dead-block pruning
- **functions_array_params.fire** - Array parameters
- **functions_array_return.fire** - Array-typed function return value used in further expressions (array access)
- **functions_early_and_multiple_returns.fire** - Early return, multiple return paths
- **functions_void.fire** - Void functions with side effects
- **functions_missing_return_fallthrough.fire** - A non-void function (no "missing return" diagnostic exists in firescript) falling off the end without an explicit `return`: ast_to_fir.py's `_synthesize_zero()` emits an implicit zero-valued return for scalar return types (int/float/bool/char). Documents a newly-found bug: the same fallthrough for a *non-scalar* return type (e.g. `string`) crashes the compiler with an internal `FLIRV-T4` verifier error instead of a clean diagnostic or a working implicit return.
- **functions_rare_constructs.fire** - `.length()` called on an array *parameter* (size not statically known, vs. a locally-sized array) and `for-in` over a named array identifier (vs. an array literal), exercising less-common `ast_to_fir.py` array-size-lookup paths
- **functions_fallthrough_return.fire** - Non-void (float64/bool) function whose only `if` has no `else`; falling off the end synthesizes a zero value of the declared return type
- **functions_many_params.fire** - Functions with more than 4 parameters (int, float, and copyable-struct), exercising the Windows x64 calling convention's stack-spill path for the 5th+ argument (only the first 4 are passed in registers)
- **functions.fire** - Basic function examples (multi-return-type, array param, string concat, void with multiple args — a different set of scenarios from the `functions_*` files above)
- **functions_sized_array_param.fire** - Fixed-size array parameter type (`int32[N]`), distinct from the unsized `int32[]` form
- **functions_nullable_scalar_param.fire** - A nullable *scalar* function parameter (`count: int32?`): a legitimate zero argument is distinguishable from an omitted (`null`) one via the implicit trailing has-value companion parameter `_function_params` appends. See `ast_to_fir.py`'s "Nullable scalars" section.

### `scoping/`
- **scoping_block_nesting.fire** - Global/block scope, deeply nested blocks, complex nesting across block/if/while
- **scoping_control_flow.fire** - if/else, while, for, for-in loop scope
- **scoping_function.fire** - Function scope (parameters and locals not visible outside)
- **scoping_variable_declaration_order.fire** - Declared-before-use, same names in separate sibling scopes
- **scope_stray_token_recovery.fire** - Parser error-recovery around a stray/unexpected token in statement position, verifying the recovered scope's remaining valid statements still resolve correctly
- **scope_tests.fire** - Basic scoping tests

### `expressions/`
- **expressions_function_calls.fire** - Function call expressions, nested function calls
- **expressions_array_and_string.fire** - Array indexing arithmetic, string concatenation expressions
- **expressions_casts.fire** - Casts within expressions, mixed-type expressions
- **expressions_unary_and_incdec.fire** - Unary +/-, increment/decrement
- **expressions_nested_and_conditional.fire** - Complex nested parenthesized expressions, conditional value via if/else
- **operator_precedence.fire** - Operator precedence (each expression commented with the expected value, so a wrong precedence produces an obviously-wrong number)

### `edge_cases/`
- **edge_cases_zero_values.fire** - Zero/empty values across types
- **edge_cases_numeric_bounds.fire** - Min/max values, very large/small numbers
- **edge_cases_arithmetic.fire** - Division and modulo edge cases
- **edge_cases_overflow_underflow.fire** - int8/uint8 overflow, int8 underflow
- **edge_cases_arrays.fire** - Empty array, single-element array, identical elements
- **edge_cases_strings.fire** - Single-char and whitespace-only strings
- **edge_cases_comparisons.fire** - Equality/relational edge cases
- **edge_cases_loops.fire** - Zero-iteration and single-iteration loops
- **edge_cases_nesting_and_functions.fire** - Deeply nested blocks, minimal function, all-paths return function
- **edge_cases.fire** - Various edge case scenarios

### `memory/`
- **memory_branching.fire** - Memory behavior with branching
- **memory_break_continue_owned.fire** - Owned vars correctly dropped on break/continue
- **memory_class_owned_fields.fire** - Classes with owned fields (string) use generated destructors
- **memory_constructor_move.fire** - Owned objects moved into a constructor not double-freed
- **memory_early_exit_precision.fire** - Precise drop insertion around early exits (only variables actually in scope at the exit point are dropped)
- **memory_early_return.fire** - Memory with early returns
- **memory_move_no_use_after_free.fire** - Moving an owned value via declaration/assignment does not drop the moved-from variable (no use-after-free / double-drop)
- **memory_reassign.fire** - Memory during reassignment (int and string)
- **memory_scopes.fire** - Memory in different scopes
- **ownership_demo.fire** - Ownership model demonstration
- **ownership_test.fire** - Ownership testing
- **move_semantics_test.fire** - Move semantics
- **borrow_test.fire** - Borrowing tests
- **copyable_test.fire** - Copyable type testing
- **copyable_local_drop.fire** - A copyable class local going out of scope inside a function body (`copyable_test.fire` only exercises a copy-then-use case at top level). Documents that no `DropInst` is ever emitted for a copyable local (`is_owned()` never treats a copyable class as owned), making `lower_drop`'s `is_copyable_class_str(...)` early-return in `firescript/flir/lowering.py` unreachable dead code.
- **receiver_mut.fire** - `&this` / `&mut this` borrow receivers on class methods
- **memory_owned_function_param.fire** - Explicit `owned` keyword on a plain (non-receiver) function parameter
- **memory_implicit_receiver_borrow.fire** - Regression: a method declared with no receiver parameter at all (found while building `std.collections.Vec<T>`) now correctly defaults its implicit `this` to borrowed instead of owned; the object survives repeated calls instead of being destroyed on the first one (previously affected any such method on a class with an owned field, including `Option<T>.isSome()`/`isNone()`)

### `classes/`
- **classes_smoke.fire** - Basic class smoke tests
- **classes_field_access.fire** - Class field access
- **classes_methods.fire** - Class methods
- **classes_nested.fire** - Nested classes
- **classes_deep.fire** - Deep class testing
- **classes_static_methods.fire** - Static methods
- **inheritance.fire** - Class inheritance, `super()`, multi-level (double/triple/quad) inheritance chains
- **return_class_test.fire** - Returning a class instance from a function
- **classes_nested_copyable_field.fire** - A class holding a copyable (by-value) struct field: whole-struct assignment/read (not just scalar sub-field access), including a method returning the nested struct by value and field-to-field struct assignment (`l.start = l.end;`). Exercises the struct-sized Load/Store codegen paths.
- **classes_method_nullable_param.fire** - A regular (non-constructor) instance method with a nullable parameter (`name: string?`)
- **classes_explicit_constructor_call.fire** - Explicit type-qualified constructor call `ClassName.ClassName(args)`, parsed as `TYPE_METHOD_CALL` where the resolved method is the constructor itself
- **classes_constructor_owned_borrowed_param.fire** - Constructor with `owned`/borrowed markers on regular (non-receiver) parameters, following an explicit receiver
- **classes_new_constructor_syntax.fire** - Java-like `new ClassName(args)` constructor syntax, an alternate to the direct `ClassName(args)` form
- **type_method_call_constructor_form.fire** - Type-qualified `ClassName.methodName(args)` call form resolving to a static method (as opposed to the constructor-via-`ClassName.ClassName(args)` case covered by `classes_explicit_constructor_call.fire`)
- **classes_owned_this_constructor.fire** - Regression: `owned this` as a constructor receiver (moved back from `known_issues/` — see "Known-Failing Regression Tests" below)
- **classes_array_field.fire** - An unsized array-typed class field (`data: int32[];`): construction (via a value round-tripped through a free function's owned `int32[]` parameter/return, the only way to produce a genuinely unsized-typed array value before `fs_rt_array_new<T>` existed), field element read/write, and destructor-frees-the-buffer (the null-guarded free path, since the field is always owned) on scope exit. Precursor to `std.collections.Vec<T>`, which stores its backing buffer the same way.
- **classes_nullable_scalar_field.fire** - A nullable *scalar* class field (`balance: int32?;`, not `string?`/a class-typed field, which are already unambiguously null-able via their pointer's 0 value): constructor parameter, field assignment, and a `!= null`/`== null` field read all correctly distinguish "no value" from a stored zero. See `ast_to_fir.py`'s "Nullable scalars" section.

### `generics/`
- **generics_basic.fire** - Basic generic functions
- **generics_simple.fire** - Simple generic examples
- **generics_clamp.fire** - Generic clamp function
- **generics_constraint.fire** - Type constraints on generics
- **generics_swap.fire** - Generic swap function
- **constraint_alias_test.fire** - Constraint aliases
- **nested_constraint_test.fire** - Nested constraints
- **math_with_constraints.fire** - Math operations with constraints
- **generics_class_basic.fire** - Generic classes (`class Pair<T, U>`) with explicit type arguments at both declaration and construction sites
- **generics_class_inferred_construct.fire** - Generic class construction with type arguments omitted at the call site (`Pair<int32, string> p = Pair(1, "x");`), inferred from the declared variable type
- **constraint_intersection.fire** / **generic_intersection_constraint.fire** - Constraint/generic-function declarations using the intersection (`&`) operator to combine a primitive type with an interface/alias name (`T: int32 & Comparable`)
- **generic_function_same_type_param_modulo.fire** - Generic function reusing the same type parameter for multiple arguments (`fn<T>(a: T, b: T)` both typed `T`), exercising type-parameter unification during call inference
- **generics_array_param_inference.fire** - A generic function taking an array parameter (`&arr: T[]`) infers `T` from the argument's *element* type, not the whole array type (regression: `int32[]` used to infer `T="int32[]"` instead of `T=int32`); also exercises the implicit array-length ABI parameter across a generic call, previously skipped for generic calls entirely

### `identifiers/`
- **identifiers_keyword_prefix.fire** - Regression: an identifier starting with a keyword-like literal token as a prefix (`false_flag`, `true_flag`, `nullable_count`) lexes as a single `IDENTIFIER`, not the literal token (`true`/`false`/`null`) followed by a stray remainder identifier (see `firescript/lexer.py`'s `BOOLEAN_LITERAL`/`NULL_LITERAL`/`VOID_LITERAL` patterns, which were missing the trailing `\b` word boundary every other keyword pattern has)

### `imports/`
- **imports_single.fire** - Single symbol import
- **imports_multi.fire** - Multiple symbol imports (merges `math_utils` and `string_utils`)
- **imports_symbols.fire** - Specific symbol imports (`utils`)
- **imports_wildcard.fire** - Wildcard imports (`utils.*`)
- **export_visibility.fire** - Importing an explicitly exported symbol (`visibility_provider.addOne`)
- **utils.fire**, **math_utils.fire**, **string_utils.fire**, **visibility_provider.fire** - Helper modules, not standalone tests
- **imports_alias.fire** - Import aliasing (`as`) on a symbol import and on a whole-module import; calls through the symbol alias. Qualified access through a module alias (e.g. `U.helper(...)`) is still `[PLANNED]` (see `docs/reference/imports.md`), so the whole-module alias is imported but only called through its unaliased import
- **imports_symbol_alias.fire** - Regression: calling through an aliased symbol import (`import x.y as z; z();`) (moved back from `known_issues/` — see "Known-Failing Regression Tests" below)

### `io/`
- **io_test.fire** - Input/output functions

### `performance/`
- **fibonacci.fire** - Recursive fibonacci (also used for benchmarking)
- **stress_array_bounds.fire** - Array boundary access stress test (off-by-one, index validation)
- **stress_deep_recursion.fire** - Deep recursion stress test
- **stress_integer_overflow.fire** - Integer overflow behavior under repeated operations
- **stress_string_operations.fire** - Heavy string concatenation/manipulation
- **stress_type_conversions.fire** - Repeated type conversion stress test

### `special_types/`
- **float128_test.fire** - 128-bit float testing
- **float128_ops.fire** - binary128 soft-float: arithmetic (`+ - * /`, unary `-`), comparisons, and conversions (int, float64, string parse)
- **float128_narrow_casts.fire** - float128 <-> narrower numeric types not covered by `float128_ops.fire` (which only covers float128 <-> int64/uint64/float64): int8/int16/int32 -> float128 (widened via int64), float128 -> int8/int16/int32 (narrowed via int64), and float128 <-> float32.
- **float128_narrow_conversions.fire** - float128 narrowing to int8/int16/int32/float32, and widening from int8/int16/int32/float32 to float128

### `std/regex/`
- **std_regex_basic.fire** - `is_match` over literals, `.`, alternation, quantifiers (`* + ?`), groups, character classes (including ranges and negation), and `last_error` for invalid patterns
- **std_regex_anchor_simple.fire** / **std_regex_anchors.fire** - Anchor handling (`^`, `$`) in `is_match`
- **std_regex_find_at.fire** / **std_regex_find_at_anchors.fire** - Position-aware matching via `find_at`, with and without anchors
- **std_regex_validate_anchors.fire** / **std_regex_validate_anchors2.fire** - Pattern validation with anchors
- **std_regex_regression_generic_matcher.fire** - Regression: quantifier/group/class patterns (`xy?z`, `(cd)+e`, `[b-d]+`, `x*z`) must go through the generic matcher; guards against reintroducing per-pattern hard-coded results in `is_match`

### `std/fs/`
- **std_fs_basic.fire** - Basic `File`/`FileResult` usage
- **std_fs_helpers.fire** - Filesystem helper functions
- **std_fs_path_ops.fire** - Path manipulation operations

### `std/cli/`
- **std_cli_args_basic.fire** - Basic `std.cli.args` usage
- **std_cli_args_parser.fire** - Argument parser behavior
- **std_cli_args_with_argv.fire** / **std_cli_args_edge_with_argv.fire** - Argument handling with real argv input (`.args` sidecar supplies the process's own command-line tokens)

### `std/fcl/`
- **std_fcl_lexer.fire** - FCL (firescript config language) lexer: tokens, kinds, lexemes, positions

### `std/types/`
- **std_types_test.fire** - `std.types` `Tuple`/`Option` basic usage
- **option_issome_isnone.fire** - Regression: `Option`/`CopyableOption`'s `isSome()`/`isNone()` resolve correctly through a same-file vs. cross-module generic-method lookup
- **option_null_vs_zero.fire** - Regression: `Option<int32>`/`CopyableOption<bool>` (a primitive payload type) correctly distinguish `null` from a legitimately-stored `0`/`false`, now that `Option`'s own `value: T?` field gets real nullable-scalar-field compiler support (see `ast_to_fir.py`'s "Nullable scalars" section) with zero changes to `Option`'s own source

### `std/collections/`
- **vec_push_pop.fire** - `Vec<int32>` basic `push`/`pop`/`get`/`length`
- **vec_growth.fire** - Enough pushes (25) to force several capacity-doubling grow-and-copy cycles
- **vec_get_set.fire** - `set()` overwriting an existing element by index
- **vec_of_strings.fire** - `Vec<string>` (an Owned element type): `push`/`pop`/`set` correctly transfer ownership (`pop` shrinks the tracked length before reading, so it never aliases a slot the destructor would also try to free); 2000 construct/populate/drop cycles double as a leak/double-free sanity check for the `@owns_elements` destructor hook (same technique as `tests/sources/enums/enum_owned_payload_drop.fire`)
- **vec_enumerate.fire** - `enumerate<T>` generator yielding `Tuple<int32,T>` (index, value) pairs while iterating a `Vec<int32>` via `for`-in. Regression coverage for a compound-generic-type substitution bug (`Tuple<int32, T>`'s nested `T` was never resolved) and a generic-generator type-argument inference gap, both fixed alongside this test — see `docs/changelog.md`'s 0.6.0 Bug Fixes.
- **hashmap_int_keys.fire** - `HashMap<int32,int32>` basic `set`/`get`/`has`/`remove`, including overwriting an existing key
- **hashmap_string_keys.fire** - `HashMap<string,int32>` string keys (`fs_rt_hash_string`), including overwrite-by-equal-key and removal
- **hashmap_growth.fire** - 50 inserts starting from capacity 8 to force several capacity-doubling rehash cycles, verifying every key remains reachable afterward (linear-probing collisions surviving a rehash into a differently-sized table)
- **hashmap_of_owned_values.fire** - `HashMap<int32,string>` (an Owned value type): `remove()` safely transfers ownership out and tombstones the slot in the same operation, matching `Vec<T>.pop()`'s equivalent safety argument; 1000 construct/populate/remove/drop cycles with both `K` and `V` owned (`HashMap<string,string>`, leaving 2 of 3 entries live each cycle so the destructor's states-guarded sweep is exercised, not just `remove()`'s own drop) double as a leak/double-free sanity check for the `@owns_elements` destructor hook's occupancy-aware sweep

### `std/syscalls/`
- **syscall_basic.fire** - Low-level syscall intrinsics (open/read/write/close/etc.)

### `nullable/`
- **nullable_basic.fire** - Nullable variables, `== null` / `!= null` checks
- **nullable_advanced.fire** - Nullable class fields
- **nullable_scalar_local.fire** - A nullable *scalar* local variable (`int32?`, not `string?`/a class?/an array?, which are already unambiguously null-able via 0): a nullable int32 holding the value `0` must still compare not-equal to `null`, via the compiler-tracked has-value companion binding. See `ast_to_fir.py`'s "Nullable scalars" section.
- **nullable_scalar_return.fire** - A plain function declared `-> int32?` (a nullable-scalar return type): the callee is actually compiled to return an internal `__NullableReturn<T>` struct (`ast_to_fir.py`'s "Nullable-scalar return values" section), unwrapped transparently at the call site; also confirms a side-effecting nullable-scalar-returning call is evaluated exactly once even when both its value and has-value flag are needed.

### `integration/`
Larger multi-feature programs (coding-challenge solutions used as integration-style tests, not focused unit tests):
- **hackathon8_mission1.fire** / **hackathon8_mission2.fire** - `std.io` + `std.fs` combined usage
- **run_length_encoding.fire** - Run-length-encodes a CLI argument (`std.cli.args` + `std.io` + `for`-in-`string`); the for-in-string loop variable is conditionally moved into an outer variable across an if/else-if chain, the real-world pattern behind `strings_for_in_regression_conditional_move*.fire`

## Splitting large test files

Prefer many small, single-behavior `.fire` files over one large multi-assertion file — a failure in a 10-line file tells you exactly what broke; a failure in a 150-line file with a dozen unrelated assertions does not. When a category needs more than one file, name them `<category>_<specific_behavior>.fire` (e.g. `arrays_iteration_for_in.fire`, `strings_escapes.fire`). This is the standard convention going forward; all of the original `*_comprehensive.fire` files have been split (see `arrays/`, `strings/`, `control_flow/`, `conversions/`, `edge_cases/`, `expressions/`, `functions/`, `scoping/`, `types/` above). When splitting, drop redundant content already covered by a sibling file in the same category (noted inline above where it applies) and drop commented-out "not yet implemented" placeholder assertions rather than preserving them.

## Known-Failing Regression Tests

`tests/sources/known_issues/*.fire` cases are **expected to fail** under the `run` kind right now — they were added to lock in known compiler bugs before a fix lands, per CLAUDE.md's "always add a test that would have failed before the fix" rule, applied here in advance of the fix rather than alongside it. Do not "fix" them by editing the EXPECT block or deleting the case; they should start passing once the underlying bug referenced in each file's header comment is fixed, at which point re-run with `--update`, review the diff, and move the file into its normal feature category. The three prior entries (`Option`/`CopyableOption` `isSome()`/`isNone()` wrong values, and two generic-call FIR->FLIR lowering crashes) were all traced to one root cause in `ast_to_fir.py`'s `_find_method_def()`/`_expr_type()` (methods/calls on a class or function imported from another module could resolve against a stale or unsubstituted generic type instead of the concrete instantiation) and fixed; the regression tests now live at `std/types/option_issome_isnone.fire`, `generics/generic_nested_call.fire`, and `generics/generic_method_if_condition.fire`. Three more entries were fixed since: `owned this` constructor receivers dropping `this` before the constructor's synthesized return, and aliased-import call sites never being rewritten to the original symbol name (regression tests now at `classes/classes_owned_this_constructor.fire` and `imports/imports_symbol_alias.fire`); and a generic generator function's compound yield type (e.g. `enumerate<T>`'s `generator<Tuple<int32, T>>`) mis-lowering its per-yield "out" value slot -- traced to `flir/lowering.py`'s `lower_type_str` substituting a compound generic type string's *outer* type but never the type parameters nested inside it, plus generators having no type-argument inference/monomorphization at all (regression test now at `std/collections/vec_enumerate.fire`). As of this writing the category is empty.

This category is specifically for currently-known, not-yet-fixed bugs (expected to fail). Normal regression tests added alongside a fix (per CLAUDE.md's standard "Bug Fix Tests" workflow — a test that would have failed before the fix and passes after) go in their feature's regular category directory, not here.

## Invalid Tests

Tests in `tests/sources/invalid/<category>/` are expected to fail compilation and test error handling. Categories:

- **arrays/** - `array_edge_invalid.fire`, `array_errors.fire`, `array_index_count_errors.fire`, `array_slice_errors.fire`, `array_method_call_errors.fire` (mutation methods on fixed-size arrays, wrong arg counts/types for length/index/count, unknown array/string methods), `array_access_undefined_index_errors.fire`/`array_access_undefined_index.fire` (indexing with an undefined-variable index reports only the undefined-variable error, not a second misleading index-type error), `array_literal_undefined_element_errors.fire`/`array_literal_undefined_element.fire` (an array literal's first element being an undefined variable reports only the undefined-variable error, not a second misleading element-type error), `array_index_assignment_target_errors.fire` (malformed index expression on an array-index assignment target), `array_length_arg_count.fire` (`.length()` called with the wrong argument count), `array_access_and_method_errors.fire`, `array_element_assignment_invalid_target.fire`, `array_element_assignment_missing_expr.fire`, `array_literal_unresolvable_element.fire`, `array_size_literal_suffix.fire`
- **borrow/** - `borrow_alias_escape_errors.fire`, `borrow_escape_projection_errors.fire`, `borrow_move_errors.fire`, `branch_move_errors.fire`, `constructor_borrow_move_errors.fire`, `constructor_move_errors.fire`, `for_in_move_errors.fire`, `loop_move_errors.fire`, `method_move_errors.fire`, `memory_errors.fire` (use-after-move, invalid borrows, out-of-bounds access)
- **classes/** - `class_errors.fire`, `class_static_method_errors.fire`, `receiver_readonly_mutation_errors.fire`, `super_call_errors.fire` (`this.super(...)` with no base class, outside a constructor, and wrong arg count/type; also `super_call_no_base.fire`/`super_call_base_no_ctor.fire`/`super_call_arg_count.fire`/`super_call_arg_type.fire` single-case variants), `constructor_and_type_method_call_errors.fire` (`new` constructor arg count/type mismatches, unknown `Type.method(...)`, instance method called in type-call form, static method arg count/type mismatches; also `constructor_call_arg_count.fire`/`constructor_call_arg_type.fire`/`constructor_call_no_ctor.fire`/`type_method_call_arg_count.fire`/`type_method_call_arg_type.fire`/`type_method_call_unknown.fire`/`type_method_call_constructor_form.fire`/`instance_method_arg_count.fire`/`instance_method_arg_type.fire`/`instance_method_unknown.fire` single-case variants), `field_access_errors.fire`/`field_access_unknown_field.fire` (unknown field on a class type, field access on a non-class type), `constructor_param_syntax_errors.fire`/`constructor_amp_not_this.fire`/`constructor_param_array_unsupported.fire`/`constructor_param_bad_type.fire`/`constructor_static_with_receiver.fire` (malformed constructor parameter lists and static-constructor-with-receiver double error), `class_method_syntax_errors.fire`, `new_constructor_syntax_errors.fire`/`new_missing_paren.fire`/`new_unknown_type.fire`, `method_duplicate_param_shadow.fire`, `constructor_arg_type_mismatch_errors.fire`, `class_constructor_syntax_errors.fire`, `class_new_constructor_errors.fire`, `class_method_duplicate_param.fire`, `constructor_call_arg_errors.fire`, `field_access_missing_identifier.fire`, `field_access_type_errors.fire`, `implicit_var_method_call_on_untyped.fire`, `instance_method_arg_errors.fire`, `static_and_type_method_errors.fire`, `unknown_instance_method.fire`
- **control_flow/** - `control_flow_invalid.fire`, `dangling_else_errors.fire` (dangling-else case split out to avoid error-recovery interaction with an adjacent malformed-statement case), `if_condition_syntax_errors.fire` (malformed if-condition expression where recovery lands directly on the closing `)`), `assignment_target_errors.fire`, `assignment_undefined_chain.fire`, `for_c_style_missing_semicolon.fire`, `for_in_extra_tokens.fire`, `unterminated_if_body.fire`
- **declarations/** - `const_missing_type.fire` (a `const` declaration missing its type token), `builtin_method_decorator_outside_std_internal.fire` (`@builtin_method` is restricted to `firescript/std/internal/`; a user source file declaring one is rejected at parse time)
- **enums/** - `enum_generic_unsupported.fire` (generic enums `enum Foo<T>` are rejected with a clear, intentional "not yet supported" error rather than a confusing parse failure), `enum_variant_arity_mismatch.fire` (constructing a payload variant with too many/too few arguments is rejected with a clear arity-mismatch error), `enum_construct_move_errors.fire` (regression: passing an owned identifier as an enum variant's payload argument moves it, so using that identifier afterward is a use-after-move error, same as passing it to a function/constructor/method call), `enum_body_syntax_errors.fire` (malformed enum variant declarations)
- **expressions/** - `cast_to_class_type.fire`, `cast_to_non_type_token.fire`, `compound_assignment_missing_rhs.fire`, `expression_at_eof.fire` (missing initializer expression at true EOF; also produces a parse-level "unexpected token" alongside the higher-level "expected expression" diagnostic), `implicit_assign_undefined_receiver.fire`, `implicit_assign_undefined_rhs.fire`, `postfix_cast_after_broken_paren.fire`
- **functions/** - `function_errors.fire`, `reserved_name_typeof_arg_count.fire`, `builtin_arg_count_errors.fire`
- **generics/** - `generics_errors.fire`, `generic_declaration_errors.fire`, `generic_constraint_violation_errors.fire`/`generic_call_constraint_violation.fire` (explicit type argument that violates a union-of-types constraint), `generic_class_template_field_errors.fire`/`generic_class_field_access_unknown.fire` (unknown field access inside a generic class template's own method body, before any concrete instantiation), `nested_generic_missing_close_errors.fire` (nested generic type-argument list in a variable declaration missing its own closing `>`), `generic_func_empty_type_args.fire`, `new_constructor_empty_type_args.fire`, `generic_class_nested_type_arg_errors.fire`, `generic_class_nested_unclosed_type_args.fire`, `generic_class_type_arg_errors.fire`, `generic_class_unclosed_type_args.fire`, `generic_class_unknown_field.fire`, `generic_function_inference_errors.fire`
- **imports/** - `import_errors.fire`, `export_visibility_private.fire` (importing a non-exported symbol), `visibility_provider.fire` (helper, not a standalone test), `deferred_generic_call_empty_type_args.fire`/`deferred_generic_call_errors.fire`, `stdlib_import_path_errors.fire`, `import_trailing_dot_eof.fire` (dotted import path ending right at EOF after the trailing `.`), `import_inside_function.fire` (import statement nested inside a function body)
- **literals/** - `literal_errors.fire`
- **match/** - `match_non_exhaustive.fire` (missing variant arms and no `_` wildcard), `match_duplicate_variant.fire` (same variant matched twice), `match_wildcard_not_last.fire` (arms after a wildcard `_` are unreachable), `match_unknown_variant.fire` (pattern references a variant that doesn't exist on the enum), `match_unknown_payload_field.fire` (pattern binds a field name the variant doesn't declare), `match_duplicate_field_binding.fire` (the same payload field is bound twice in one pattern), `match_syntax_errors.fire` (malformed match expression syntax), `match_missing_scrutinee.fire`, `match_pattern_bad_binding.fire`, `match_pattern_missing_variant.fire`
- **nullable/** - `nullable_errors.fire`
- **operators/** - `operator_errors.fire`, `logical_and_increment_errors.fire`
- **scoping/** - `scope_errors.fire` (variable shadowing not allowed, use before declaration, out-of-scope access), `parameter_shadowing_errors.fire` (function and class-constructor parameters that shadow an outer-scope variable), `bare_assignment_without_declaration_errors.fire` (bare `name = expr;` to a never-declared name is always rejected, even when the RHS is a constructor call or an instance method call whose type could plausibly be inferred)
- **strings/** - `string_implicit_conv_error.fire`, `string_length_arg_count.fire`, `string_unknown_method.fire`, `string_method_errors.fire`
- **syntax/** - `syntax_errors.fire`, `syntax_comprehensive.fire` (missing semicolons, unclosed parens/braces, invalid tokens, malformed control flow), `export_errors.fire` (invalid uses of `export`), `expression_operand_errors.fire` (missing right-hand operands and malformed primary expressions), `declaration_dispatch_errors.fire`, `statement_dispatch_errors.fire`
- **types/** - `type_mismatches.fire`, `type_errors_comprehensive.fire` (type mismatches in assignments, function calls, operators, conditions, indexing), `field_access_on_primitive.fire`, `semantic_equality_mismatch.fire`, `semantic_logical_non_bool.fire`, `semantic_modulo_mismatch.fire`, `semantic_operator_errors.fire`, `semantic_unary_incdec_undefined.fire`, `semantic_unary_minus_undefined.fire`, `semantic_unary_not_non_bool.fire`, `binary_operator_type_errors.fire`, `cast_array_to_non_string.fire`, `cast_undefined_operand.fire`, `unary_operator_type_errors.fire`

### Error Test System

- **Location**: `tests/sources/invalid/<category>/*.fire`
- **Expected diagnostics**: in-file `//~ ERROR <CODE> [@<column>]` annotations, anchored to the offending source line (see "Directive Reference" below) -- no sidecar files.
- **Kind**: `compile-fail` (`python tests/run.py kind:compile-fail`)

### How It Works

1. `firescript/main.py --check --message-format json` is invoked in a subprocess against the invalid source.
2. Structured JSON diagnostic events are parsed from its output.
3. Diagnostics are compared against the file's `//~ ERROR` annotations: the multiset of `(code, line, column?)` must match exactly (column is only checked when the annotation specifies one).
4. Test passes when all annotations match with no missing or extra diagnostics.

### Benefits

- **Message-Independent**: Error message text can evolve without brittle test churn (an optional quoted substring can still assert on wording when useful).
- **Regression Prevention**: Error code and location regressions are caught immediately.
- **Location Accuracy**: Ensures diagnostics point to the right source coordinates.
- **Self-Maintaining Line Numbers**: `//~^` caret-stacking anchors an annotation to a line *relative to itself*, so annotations don't silently go stale when lines are inserted/removed elsewhere in the file (the classic problem with absolute-line-number sidecar files).

## Test Coverage Summary

| Feature Category | Coverage |
|-----------------|----------|
| Operators | ✅ Comprehensive |
| Control Flow | ✅ Comprehensive |
| Types | ✅ Comprehensive |
| Type Conversions | ✅ Comprehensive |
| Strings | ✅ Comprehensive |
| Arrays | ✅ Comprehensive |
| Functions | ✅ Comprehensive |
| Scoping | ✅ Comprehensive |
| Expressions | ✅ Comprehensive |
| Memory Management | ✅ Good |
| Classes/OOP | ⚠️ Partial (feature in development) |
| Generics | ✅ Good |
| Imports | ✅ Good |
| Edge Cases | ✅ Comprehensive |

## Adding New Tests

### A golden (`run` kind) test

1. Pick (or create) the matching category subdirectory under `tests/sources/`, e.g. `tests/sources/arrays/`. Prefer one focused behavior per file over adding more assertions to an existing file — see "Splitting large test files" above.
2. Write the `.fire` file with test cases producing expected output via `println()`. Add any `//@` header directives it needs (`//@ args:`, `//@ exit-code:`, etc. -- see "Directive Reference" below).
3. Run `python tests/run.py tests/sources/<category>/<name>.fire --update` to write the trailing `/* EXPECT ... */` block *into the file itself*.
4. Review the EXPECT block the update wrote (it's part of the diff now, not a separate golden file).
5. Commit the source file.
6. Update this manifest.

### An error (`compile-fail` kind) test

1. Add the file to `tests/sources/invalid/<category>/`.
2. Either hand-write `//~ ERROR <CODE> [@<column>]` annotations on the offending lines, or run `python tests/run.py tests/sources/invalid/<category>/<name>.fire --update` to have the harness insert them from the compiler's actual diagnostics.
3. Review the inserted annotations.
4. Commit the source file.

### A Python test

Add a `test_*` function to an existing (or new) `tests/python/<category>/test_*.py` module; it always runs, no registration needed. Use `from harness import pyunit as t` for assertions/helpers.

## EXPECT Block Format

The trailing `/* EXPECT ... */` block (or its `// EXPECT: <line>` fallback form, used only when the expected output itself contains a `*/`) holds the expected stdout from running the compiled test binary, normalized the same way the actual output is: Unix-style line endings (`\n`), trailing whitespace stripped per line. It must be the last non-blank content in the file. `--update` rewrites it in place.

## Directive Reference

Header directives (`//@ key: value` in `.fire` files, `#@ key: value` in `.py` files) must appear in the leading comment block at the top of the file -- one found after the first code token is a discovery-time error, never a silent skip. `//~` diagnostic annotations are the opposite: only valid *after* code starts, anchored to source lines.

**There is no skip directive and no skip capability anywhere in this harness, on purpose** -- see CLAUDE.md's "never skip tests" rule. A test that can't currently pass must fail or error loudly (optionally moved into a `known_issues/` directory with a header comment explaining why, per the conventions above), never silently disappear from the results.

| Directive | Applies to | Meaning |
|---|---|---|
| `//@ mode: run \| compile-fail` | `.fire` | Explicit kind override; normally inferred from location (`invalid/` -> compile-fail). Conflicting with location is a discovery error. |
| `//@ helper` | `.fire` | File is imported by other tests; never a standalone test case. |
| `//@ args: <tokens>` | `.fire` | argv for the compiled binary, shlex-split (repeatable, concatenates with `arg:` in file order). |
| `//@ arg: <verbatim>` | `.fire` | One argv token, verbatim to end of line (repeatable). |
| `//@ stdin: <text>` | `.fire` | One line of stdin (repeatable, joined with `\n`). Mutually exclusive with `stdin-file:`. |
| `//@ stdin-file: <path>` | `.fire` | stdin from a file, path relative to the test file. |
| `//@ exit-code: <int>` | `.fire` | Expected binary exit code (default 0). |
| `//@ timeout: <seconds>` | `.fire` | Binary run timeout (default: harness config). |
| `//@ compile-timeout: <seconds>` | `.fire` | Compile timeout (default: harness config). |
| `//@ compile-flags: <flags>` | `.fire` | Extra flags appended to the compiler invocation. |
| `//@ snapshot: fir[, flir]` | `.fire` | Opt into the `snapshot` kind in addition to `run`. |
| `//@ no-matrix` | `.fire` | Run only in the default matrix cell. |
| `//@ no-determinism: <reason>` | `.fire` | Exclude from determinism-kind sampling; reason required. |
| `//~ [^*] ERROR <CODE> [@<col>] ["substr"]` | `.fire` (`invalid/`) | Expected diagnostic, anchored to its own line minus one per leading `^`. |

Unknown directive keys, and directives outside the rules above (misplaced `//@`, a `compile-fail` file with zero `//~` annotations, a duplicate EXPECT block), are always loud discovery errors -- never silently skipped.

## Test Naming Conventions

- `<category>_<specific_behavior>.fire` - One focused behavior per file, in the `<category>/` directory (the standard convention — see "Splitting large test files"). Do not introduce new `*_comprehensive.fire` multi-assertion files.
- `<feature>_test.fire` - Specific feature test
- `<feature>_<variant>.fire` - Specific variant of a feature (e.g., for_c_style, for_in)

## Continuous Integration

Tests run automatically on GitHub Actions for:
- Push to main branch
- Pull requests to main
- Changes to workflow, compiler, or tests

See `.github/workflows/windows_x86_64_test.yml` for CI configuration.
