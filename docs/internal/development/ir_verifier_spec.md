# FIR/FLIR Verifier Specification [IMPLEMENTED]

Mandatory validity verification for both IR levels, run on **every**
compilation. If a FIR or FLIR module violates any rule below, compilation
fails. There is no flag to disable the verifier.

Related docs: [fir_spec.md](fir_spec.md), [flir_spec.md](flir_spec.md),
[fir_flir_overview.md](fir_flir_overview.md).

## 1. Philosophy

The rules in this document are **normative, not descriptive**. They are not
derived from what `ast_to_fir.py` or `flir/lowering.py` happen to emit today;
they are derived from what safe IR *must* look like:

- every value is well-typed and defined before it is used,
- every owned value is consumed exactly once on every control-flow path
  (no leaks, no double drops, no use-after-move),
- every memory access is in bounds, aligned, and type-correct against a
  known layout,
- every heap allocation is freed exactly once and never touched afterwards.

Consequences of this stance:

1. **A verifier failure is a compiler bug.** Valid firescript source must
   never produce invalid IR. Verifier diagnostics are internal-compiler-error
   diagnostics, not user-facing source diagnostics.
2. **When the verifier fires on IR the current pipeline emits, the emitter
   gets fixed — not the rule.** A rule may only be narrowed with a written
   rationale in this document explaining why the narrower rule is still safe.
3. **The verifier trusts nothing it can recompute.** In particular it does
   not trust `fir.ownership.OwnershipMap`; it recomputes ownership facts by
   dataflow and (Tier 2, rule O8) cross-checks the recorded map against them.

The existing checks (`FIRFunction.validate`, `FLIRFunction.validate`:
terminator presence, duplicate block ids, branch-target existence) are
subsumed by this spec and migrate into the new verifiers.

## 2. Scope and non-goals

In scope: module-level and intraprocedural verification of FIR (post
AST→FIR, including the runtime FIR module) and FLIR (post lowering,
including synthesized functions: destructors, generator init/next,
monomorphized instances).

Non-goals:

- **Interprocedural analysis.** Ownership transfer across calls is verified
  against declared signatures (`param_modes`, the runtime ABI registry),
  not by inlining. A pointer that escapes into a call is treated as consumed.
- **Runtime-value properties.** Division by zero, array index range at
  runtime, arithmetic overflow — these are runtime or earlier-stage concerns.
- **Replacing semantic analysis.** The borrow checker on the AST remains the
  user-facing gate; the verifier is the last line of defense that the IR the
  backend consumes actually has the properties semantic analysis promised.

## 3. Architecture

### 3.1 New modules

| File | Contents |
|---|---|
| `firescript/ir_analysis.py` | Shared machinery: CFG construction, reverse-postorder, iterative dominance, generic forward dataflow driver, deterministic error collection. Parameterized over "block" so both IRs use it. |
| `firescript/fir/verifier.py` | `verify_fir_module(module) -> None`, raises `IRVerificationError`. Implements FIRV-* rules. |
| `firescript/flir/verifier.py` | `verify_flir_module(module) -> None`. Implements FLIRV-* rules. |
| `firescript/flir/runtime_abi.py` | Canonical `fs_rt_*` signature registry: `name -> (param FLIRTypes, return FLIRType, memory effect)`. Memory effect is one of `returns_fresh` (caller owns result: `fs_rt_alloc_zeroed`, `fs_rt_str_dup`, `fs_rt_str_concat`, `fs_rt_str_slice`, …), `frees_arg0` (`fs_rt_free`), `borrows` (reads args only: `fs_rt_str_eq`, `fs_rt_stdout`, …). Used by lowering when emitting calls and by the verifier when checking them. Today these signatures are implicit at each `rt_call` site; centralizing them is part of this work. |

### 3.2 Hook points (always on)

- **FIR:** at the end of `ASTToFIRConverter.convert()` (replaces the current
  `self.module.validate()` at `ast_to_fir.py:320`). Also applied to the
  runtime module built by `_runtime_fir_module()` in `main.py`.
- **FLIR:** at the end of `FIRToFLIRLowering.lower()` (replaces
  `self.flir.validate()` at `flir/lowering.py:629`), i.e. after
  monomorphization, destructor synthesis, and generator lowering.
- `FIRModule.validate()` / `FLIRModule.validate()` become thin wrappers over
  the verifiers so existing callers and tests keep working.
- Verification time is reported via the existing `-d` stage-timing lines.

### 3.3 Error reporting

New error class in `firescript/errors.py`:

```python
class IRVerificationError(Exception):
    """Internal compiler error: generated IR violates a validity rule."""
```

(Not a `CompileTimeError` subclass: verifier failures have no source
line/column contract and must never be silently collected alongside user
diagnostics — they abort compilation unconditionally.)

Each violation records: rule id, IR level, function name, block id,
instruction index, the instruction's deterministic `format(...)` text, and a
one-line explanation. The verifier collects **all** violations in a module
(structure order, deterministic), then raises once with the full list plus
the textual dump of the first offending function appended for debugging.
Message prefix: `internal compiler error: FIR verification failed (FIRV-O1): ...`
with a note asking the user to file a bug, since their source is not at fault.

### 3.4 Determinism

The verifier iterates functions, blocks, and instructions strictly in module
order and never iterates over unordered sets when emitting diagnostics.
Dataflow fixpoints use worklists seeded in reverse-postorder with
deterministic tie-breaking. (Required by the project determinism rule; the
`determinism` test kind must stay green.)

## 4. FIR rule catalog

Rule ids: `FIRV-<letter><n>`. Tier 1 rules are pure structural/type checks;
Tier 2 rules require dataflow.

### 4.1 Structure (FIRV-S) — Tier 1

- **S1** Every function has ≥ 1 block; the first block is the entry.
- **S2** Block ids are unique within a function.
- **S3** Every block has exactly one terminator, held in
  `BasicBlock.terminator`; no `Terminator` instance appears in
  `block.instructions`.
- **S4** Every `Branch`/`Jump` target names a block in the same function.
- **S5** Every block is reachable from the entry block. (The converter must
  not emit orphan blocks; dead blocks hide bugs and skew later dataflow.)
- **S6** Module level: function names, type names, and global-constant names
  are unique; every named type reference (`SimpleType` naming a user type,
  `GenericInstanceType.base_name`) resolves to a `TypeDef`, with type-argument
  count equal to `generic_params`; `TypeDef.base` chains resolve and are
  acyclic; enum `TypeDef`s have ≥ 1 variant and no `base`.

### 4.2 Definitions and uses (FIRV-D) — Tier 1

- **D1** Every `FIRValue` operand is produced by an instruction that belongs
  to the same function, and the definition **dominates** the use.
- **D2** Every `ParamValue` operand names a parameter of the enclosing
  function.
- **D3** An instruction may only be used as an operand if it produces a
  value (`result_type` is non-None and not `void`).

### 4.3 Types (FIRV-T) — Tier 1

- **T1** `BinaryOp`: per-op typing table. Arithmetic (`+ - * / % **`): both
  operands the same numeric type, result that type (plus `string + string ->
  string`). Comparisons (`== != < <= > >=`): operands the same comparable
  type, result `bool`. Logical (`&& ||`): `bool` operands, `bool` result.
- **T2** `UnaryOp`: `!` on `bool -> bool`; `-` on numeric -> same type.
- **T3** `Cast` follows the language cast-legality table (numeric ↔ numeric,
  built-ins → string, string → numeric). No casts between owned class types.
- **T4** `Branch` condition is `bool`. `Return v` requires `v`'s type to
  equal the function return type; a value-less `Return()` is valid **only**
  in `void` functions. (Normative: a non-void function must return a typed
  value on every path — "fall off the end" IR is invalid; see §8.)
- **T5** `Call`: callee resolves to a module function or known intrinsic;
  argument count, argument types, and `arg_modes` match the callee's
  signature and `param_modes`; each mode ∈ {`own`, `borrow`, `borrow_mut`};
  result type equals the callee return type.
- **T6** `MethodCall`: the receiver's class (following the base chain, or
  the concrete generic instance) defines the method; args checked as in T5.
- **T7** `LoadField`/`StoreField`: the object operand is a class type; the
  field exists (including inherited fields); the loaded/stored type equals
  the declared field type. Field access on enum types is invalid (enums are
  only touched via `ConstructVariant`/`ExtractTag`/`ExtractPayloadField`).
- **T8** `IndexArray`/`StoreArray`: array operand has `ArrayType`; index is
  an integer type; element type matches. A constant negative-or-out-of-range
  index against a statically known `ArrayType.size` is invalid.
- **T9** `Allocate`: the class exists and constructor arity/types match.
- **T10** `ConstructVariant`: result type is an enum; the variant exists;
  payload arity and types match the variant declaration.
- **T11** `ExtractTag` operand is an enum value. `ExtractPayloadField`:
  variant exists, `field_index` in range, result type equals the payload
  field type.
- **T12** Literals: `IntLiteral` text parses and fits the stated fixed-width
  type; `FloatLiteral` type is a float type; `NullLiteral` type is nullable.

### 4.4 Locals (FIRV-L) — Tier 1 (L1–L2), Tier 2 (L3)

- **L1** Every `LoadVar`/`StoreVar` names either a parameter or a local
  whose `DeclareLocal` dominates the use.
- **L2** `LoadVar` result type and `StoreVar` value type equal the declared
  local type (or the parameter type).
- **L3** No `DeclareLocal` is dominated by another `DeclareLocal` of the
  same name (FIR-level shadowing must have been renamed by the converter),
  and no local shadows a parameter name.

### 4.5 Ownership (FIRV-O) — Tier 2

These rules are the FIR-level memory-safety core. They are checked by a
forward dataflow analysis over binding states
(`OWNED / MOVED / MAYBE_MOVED / DEAD`) and over owned temporaries
(instruction results of owned type), independent of the recorded
`OwnershipMap`.

A value/binding is **consumed** by exactly these: being passed as an `own`
argument; being returned; being stored into a local, field, array slot, or
variant payload; being the operand of `Drop`; being the operand of `Move`
(which produces a new owned value).

- **O1** *No use after move:* once a binding is consumed on a path, any
  `LoadVar`/`ParamValue` use of it before a re-`StoreVar` is invalid.
  If it is consumed on only some paths into a block (`MAYBE_MOVED`), any use
  is likewise invalid.
- **O2** *No double consume:* an owned value (temporary or binding) must not
  be consumed twice on any path — this subsumes double-drop and
  drop-after-move.
- **O3** *No leaks:* on every path to every `Return`, every owned temporary
  and every owned local binding has been consumed exactly once. An owned
  instruction result that is never consumed on some path is a leak and is
  invalid. (`Unreachable` terminators are exempt.)
- **O4** *Borrows don't consume:* passing a binding with mode `borrow` /
  `borrow_mut` leaves it owned and usable. Within a single call, the same
  binding must not be passed both as `own` and as any borrow, nor as
  `borrow_mut` twice.
- **O5** `Drop` operands must have owned type. Dropping a copyable value is
  invalid.
- **O6** `Move`/`Clone` operands must have owned type (copying a copyable
  value is a plain use, not a `Move`).
- **O7** *Parameter contracts:* an `own`-mode parameter must be consumed on
  every path (the callee owns it). A `borrow`/`borrow_mut` parameter must
  **never** be consumed (not dropped, not moved out, not returned as owned,
  not passed onward as `own`).
- **O8** *Metadata honesty:* where the recorded `OwnershipMap` states a fact
  (a binding marked `MOVED`/`BORROWED`), that fact must agree with the
  recomputed dataflow. Disagreement is an error. (Staged last; see §8.)

### 4.6 Generators (FIRV-G) — Tier 1 (G1–G3), Tier 2 (G4)

- **G1** `Yield` appears only in functions with `is_generator`; the yielded
  type equals the generator element type.
- **G2** A generator function's `Return` carries no value (return =
  exhaustion).
- **G3** `GenNew` references a generator function with matching arity and
  argument types; the result `generator<T>` matches the callee element type.
  `GenNext`/`GenValue` operands are `generator<T>` values; `GenNext` yields
  `bool`; `GenValue` yields `T`.
- **G4** Every `GenValue` is dominated by a `GenNext` on the same generator
  value.

### 4.7 Enum payload safety (FIRV-E) — Tier 2

- **E1** Every `ExtractPayloadField(v, variant, i)` must be *tag-guarded*:
  dominated by the true edge of a `Branch` whose condition is
  `ExtractTag(v) == IntLiteral(tag_index(variant))` (the exact comparison
  shape the match lowering emits). Reading an inactive variant's payload is
  a wrong-type read of overlapped union memory — the FIR-level equivalent of
  an out-of-bounds access.

## 5. FLIR rule catalog

### 5.1 Structure (FLIRV-S) — Tier 1

- **S1** Blocks: unique ids, every block non-empty and terminated by exactly
  one terminator (`ret`/`br`/`jmp`/`unreachable`) as its **last** instruction,
  no terminator opcode mid-block; all targets exist; all blocks reachable
  from the first block.
- **S2** Module: function names unique; struct names unique;
  `entry_function`, when set, names a defined function; global and
  mutable-global names unique and disjoint; every `struct` type reference
  (`FLIRType.struct_name`, `ptr<S>` pointees naming structs) resolves.
- **S3** Struct layout soundness: for every struct, each field's
  `offset % field.align == 0`, `offset + field.size <= struct.size`,
  `struct.size % struct.align == 0`, and non-enum fields do not overlap.
  For enums: the `tag` field does not overlap the payload region; each
  variant's payload fields do not overlap *each other* (different variants
  may overlap, union-style).

### 5.2 Values and types (FLIRV-T) — Tier 1

- **T1** Every `FValue` operand is produced in the same function and its
  definition dominates its use; operands are non-void.
- **T2** `binop`: both operands' types equal `operand_type`; arithmetic
  results equal `operand_type`; comparison results are `bool`. `not` takes
  and yields `bool`; `neg` numeric. `cvt`: `from_type` equals the operand's
  actual type; both sides are scalar kinds.
- **T3** `br` condition is `bool`; `ret` value type equals the function
  return type (and bare `ret` only in void functions).
- **T4** `call`: the callee resolves to exactly one of (a) a module
  function, (b) an entry in `module.externs`, or (c) the `fs_rt_*` runtime
  ABI registry — and the argument count/types and result type match that
  signature exactly. Unknown callees are invalid.
- **T5** Slots: every `slotload`/`slotstore`/`slotaddr` names a parameter or
  a slot whose `slot` declaration dominates the use; a slot is declared at
  most once per function; `slotload` result type and `slotstore` value type
  equal the declared slot type.
- **T6** `gload`/`gstore` name a declared (mutable) global of the same type;
  `gstore` only targets `mutable_globals`.

### 5.3 Memory access (FLIRV-M) — Tier 1 (M1–M3), Tier 2 (M4–M5)

- **M1** *Typed access within known layouts:* for `load`/`store` whose base
  is `ptr<S>` with `S` a known struct: the access must land exactly on a
  declared field (or enum tag / variant-payload field) — offset equal to the
  field offset and value type equal to the field type. Accessing padding or
  past `S.size` is invalid.
- **M2** *Alignment:* every `load`/`store` offset satisfies
  `(offset % value_type.align) == 0` relative to the base's alignment
  guarantee.
- **M3** `ptradd` base is a pointer, `scale > 0`; a raw-`ptr` result may
  only be consumed by `load`/`store` of a type whose size ≤ `scale`, by
  further `ptradd`, or by calls.
- **M4** *Read-only data:* a pointer derived from `strconst` (directly or
  via must-alias slot propagation) must never be the base of a `store` and
  never freed.
- **M5** *Null discipline:* a value that may be `nullconst` along some path
  (per the Tier-2 dataflow of §5.4) must not be used as a `load`/`store`
  base without a dominating null test. (Matches the null-check pattern the
  destructor generator already emits.)

### 5.4 Allocation lifecycle (FLIRV-A) — Tier 2

An intraprocedural forward dataflow tracks the state of *heap tokens*:
values returned by registry calls marked `returns_fresh`, tracked through
must-alias slot stores/loads. States: `LIVE`, `FREED`, `ESCAPED` (stored to
a field/array/global, passed to a call other than a freeing one, or
returned).

- **A1** *No double free:* a token in state `FREED` must not be freed again
  (`fs_rt_free` or any `*__destroy` call) on any path.
- **A2** *No use after free:* a `FREED` token must not be used at all —
  not as a load/store base, not as a call argument, not returned.
- **A3** *Free provenance:* the argument of `fs_rt_free`/`*__destroy` must
  be a possible heap-allocation base pointer. Freeing a `strconst`, a
  `slotaddr`, a global address, or a `ptradd`-derived interior pointer is
  invalid.
- **A4** *No local leaks:* a token still `LIVE` at a `ret` (neither freed
  nor escaped on that path) is a leak and is invalid.
- **A5** *Destructor totality:* `fs_rt_free` must not be called directly on
  a `ptr<S>` where struct `S` has owned fields (i.e. lowering's
  `_struct_needs_destructor(S)` holds) — the destructor must be called
  instead, otherwise the owned fields leak.

## 6. What the verifier explicitly does not assume

To keep the rules normative, the verifier resolves signatures only from
declared sources: FIR function signatures + `param_modes`, the FLIR module's
functions and `externs` (per-target, e.g.
`platforms/windows.py::WINDOWS_RUNTIME_EXTERNS`), and the new runtime ABI
registry. If lowering emits a call the registry doesn't describe, that is a
verifier error and the registry must be extended deliberately — implicit
call-site ABIs are exactly the class of bug this work eliminates.

## 7. Implementation plan

Each phase lands separately and must leave `python tests/run.py` fully green
(including the `determinism` kind) with the new checks **enabled
unconditionally** before the next phase starts.

1. **Phase 0 — plumbing.** `ir_analysis.py` (CFG, RPO, dominators, dataflow
   driver), `IRVerificationError` + reporting format, `runtime_abi.py`
   registry populated from the current `rt_call` sites, and lowering
   refactored to consult the registry when emitting runtime calls.
2. **Phase 1 — FIR Tier 1.** FIRV-S, D, T, L1–L2, G1–G3. Wire into
   `ASTToFIRConverter.convert()` and the runtime-module build. Fix all
   emitter fallout (expected: T4 return-shape issues, see §8).
3. **Phase 2 — FLIR Tier 1.** FLIRV-S, T, M1–M3. Wire into
   `FIRToFLIRLowering.lower()`. This retroactively verifies synthesized code
   (destructors, generator machinery, monomorphized bodies) too.
4. **Phase 3 — FIR Tier 2.** FIRV-O1–O7, L3, G4, E1. The ownership dataflow
   is the largest single piece of this project. FIRV-O8 lands last, after
   the converter's `OwnershipMap` recording is audited.
5. **Phase 4 — FLIR Tier 2.** FLIRV-A1–A5, M4–M5 (token dataflow with
   must-alias slot tracking).
6. **Phase 5 — docs.** Update `fir_spec.md` / `flir_spec.md` to link here;
   flip this spec's marker to [IMPLEMENTED]. No changelog entry: the
   verifier is internal and, once the pipeline is clean, invisible to users
   compiling valid programs.

## 8. Known tensions with today's emitters

Places where the current pipeline is expected to violate the normative rules.
Per §1, these are fixed at the emitter (or the rule is narrowed *here*, in
writing) — the verifier is never quietly weakened:

1. **Void `Return` with a value / non-void fall-off — resolved in Phase 1.**
   `ast_to_fir.py` now synthesizes a type-appropriate zero literal (or, for a
   script-style `return N;` inside the void synthetic `main`, drops the
   value after evaluating it for side effects) at every point that used to
   emit a bare, type-mismatched `Return`. No FIRV-T4 narrowing was needed;
   `_seal_open_blocks` also now prunes blocks left with no predecessor (an
   if/else join point where every arm already returns), which the same
   fall-off logic could otherwise write an invalid trailing `Return` into
   (FIRV-S5). See `ASTToFIRConverter._synthesize_zero` /
   `_seal_open_blocks`. A residual gap remains for a non-void, non-generator
   function whose *owned* (non-scalar) return type has no safe synthesized
   zero and that still falls off every path with no explicit return on some
   path — semantic analysis does not yet reject this source-level shape, so
   FIRV-T4 is the backstop for it; no case has surfaced in the test corpus.
2. **`Move`/`Clone` on copyable values** (FIRV-O6): the converter likely
   emits these today since lowering treats them as pass-through
   (`flir/lowering.py:823–824`). Fix in the converter.
3. **Generator frame ownership.** Frames live in caller stack slots and
   `Drop` of a `generator<T>` is a no-op (`flir/lowering.py:1624`), but a
   suspended frame can hold owned locals/params that nothing frees. FIRV-O3 /
   FLIRV-A4 will surface this. Resolution (frame destructor vs. documented
   leak-freedom carve-out for generator frames) must be decided in Phase 3;
   if a carve-out is chosen it gets written into §4.5 explicitly.
4. **Arrays carry no length header** and generic instantiations drop the
   implicit `_len` parameter (legacy parity). FLIRV-T4 signature checking
   must model the implicit-trailing-length ABI exactly as specified in
   [flir_spec.md](flir_spec.md); any instantiation path that can't be
   described that precisely is a bug to fix, not to accommodate.
5. **`OwnershipMap` completeness** (FIRV-O8): recording is best-effort
   today; expect disagreements. That's why O8 is staged after O1–O7.
6. **Pointer pointee is not load-bearing for FLIRV-T2–T5 signature/slot
   matching (narrowed, Phase 2).** `ptr<S>` pointee is documentary at the
   type-equality level used for binop operand types, `ret`/call
   argument/result types, and slot load/store types: a raw generic
   allocator (`fs_rt_alloc_zeroed`) and pointer-typed helpers legitimately
   reinterpret a pointer's pointee at each use site (object/array
   allocation, generator frame slots, destructor field frees, `mem_copy`
   pointer args). `flir/verifier.py::_ptr_lenient_eq` treats any two
   `kind == "ptr"` types as equal for these checks; **M1 typed-field-access
   checking is unaffected** — it still requires an exact field-type match
   once a pointer's pointee names a known struct.
7. **Narrow-integer arithmetic promotes implicitly (narrowed, Phase 2).** A
   `binop`'s declared `operand_type` may be wider than an actual i8/i16/u8/
   u16 operand (any signedness pairing, e.g. `u8` feeding an `i32` binop);
   sub-i32 values are promoted without an explicit `cvt` in current lowering
   (byte/word loop counters, array-element comparisons). See
   `flir/verifier.py::_binop_operand_ok`.
8. **Nullable-value-type equality against `null` compares a boxed pointer,
   not `operand_type` (narrowed, Phase 2).** `std/types/option.fire`'s
   `this.value == null` (for `T?` instantiated with a copyable/value `T`,
   e.g. `Option<int32>`) lowers to an `eq`/`ne` `binop` whose declared
   `operand_type` reflects `T` (`i32`), but the actual compared value is the
   nullable's boxed-pointer representation (`ptr`) versus `nullconst`. Any
   `eq`/`ne` binop with a bare-`ptr`-kind operand is accepted regardless of
   `operand_type`, matching this null-check pattern.
9. **`char` (I8) crossing a `uint8`-declared runtime boundary — resolved in
   Phase 2.** `std/internal/runtime.fire` declares `fs_rt_char_to_str`,
   `fs_rt_str_char_code`, and `fs_rt_str_char_code_at` with `uint8`
   parameters/returns, but firescript's `char` always lowers to `I8`
   (`_SCALARS["char"]`). Fixed at the three call sites in
   `flir/lowering.py` with an explicit `Cvt` bridging `I8`/`U8` (same
   width, bit-pattern-preserving) rather than weakening FLIRV-T1/T2/T4.
10. **Anonymous expression-temporary lifetime is out of scope for FIRV-O1-O3
    (narrowed, Phase 3).** `fir/ownership_verifier.py::_identifier_of`
    tracks only named bindings (parameters, `DeclareLocal` locals) and
    deliberately does *not* track a bare instruction result used directly
    as a sub-expression and never bound to a name (e.g. a `Cast`/`BinaryOp`
    string-concatenation result passed straight into a call argument).
    `ast_to_fir.py` has no expression-temporary lifetime tracking at all
    today -- nothing in the pipeline ever drops such a value -- so treating
    every one as a trackable, must-be-consumed identifier surfaces a real
    but enormous, untargeted leak class spanning nearly every
    string-producing sub-expression in the corpus (`println`'s own `value
    as string` cast was a representative, now-fixed instance: see
    `std/io.fire`, which now binds the cast to a name so it *is* tracked).
    Properly closing this gap needs dedicated expression-temporary
    lifetime infrastructure in `ast_to_fir.py` (something akin to a
    per-statement temporary drop list), not a narrow emitter patch;
    tracked here as a known, deliberately scoped-out gap for follow-up
    work, not something Tier 2 silently accepts as safe.
11. **Container-owning synthesized locals need their own explicit `Drop`
    (resolved in Phase 3, case by case).** Compiler-synthesized locals
    that FIR-level ownership tracking doesn't otherwise see (the
    preprocessor's drop insertion only ever looks at real
    `VARIABLE_DECLARATION` nodes in the *source* AST) leaked before this
    phase: match's `__match_scrutinee_N` (`ast_to_fir.py::_convert_match`,
    now drops the scrutinee at the join block once every arm has run) and
    `for (x in expr)`'s `__arr_<var>` array-container temp
    (`_convert_for_in_array`, now dropped at the loop's exit block; this
    frees the array's own backing buffer only -- an array of *owned*
    elements has no per-element destructor at all today, a separate,
    still-open gap, not one this fix papers over). Generator-related
    synthesized locals (`__gen_*`) were not audited in this phase and are
    a known residual leak source; see open question below.
12. **A handful of preprocessor drop-insertion bugs, fixed in Phase 3
    (`preprocessor.py`).** Recorded here because each was a genuine,
    previously invisible correctness bug the ownership dataflow exposed,
    not a verifier accommodation:
    - Own-mode function/method **parameters** were never registered for
      automatic drop insertion at all (only `VARIABLE_DECLARATION` locals
      were) -- fixed by registering them into the same scope-tracking
      frame at function entry, with a matching trailing-drop step for
      control falling off the end without consuming them.
    - `RETURN_STATEMENT` and (previously) nowhere else cleared
      `scope_stack` frame *contents* in place after inserting its drops.
      Frames are shared, mutable list objects visible to every sibling
      branch (both arms of an if/elif/else, or code after the whole
      if-statement) -- clearing them made every *later* return or
      scope-exit in the function believe an outer variable handled on one
      path needed no drop on any other path, silently leaking it. Removed
      entirely (matching the pre-existing, deliberate non-clearing
      behavior already documented on Break/Continue: an occasional
      redundant drop is harmless since the runtime allocator's free path
      is idempotent against untracked/already-freed pointers -- but a
      missing drop is a real leak).
    - Move-semantics helpers (`_move_source_identifier`,
      `_apply_move_semantics`) excluded any identifier whose scope origin
      was `"param"` from ever being removed from drop tracking. Harmless
      before parameters were tracked at all; once they were, this made a
      parameter threaded through a constructor/method/`super()` call look
      doubly-consumed (the call's own move plus the enclosing function's
      unconditional trailing drop). Both helpers now apply move semantics
      uniformly regardless of origin.
    - Bare `ClassName(args)` construction parses as a `NodeTypes.
      FUNCTION_CALL` (not a distinct constructor-call node) -- move-
      semantics and return-transfer analysis now check `ctor_sigs` first
      for such calls, and (for a `ClassName(args).method(...)` receiver
      chain specifically) resolve the receiver's class from that
      constructor call too, so the *method's* real borrow flags are used
      instead of falling through to a conservative default.
    - `this.super(args)` (a distinct `SUPER_CALL` node) had no move-
      semantics handling at all; `ast_to_fir.py::_convert_super_call`
      always passes every argument `own` regardless of the base
      constructor's own borrow flags, so `SUPER_CALL` arguments are now
      unconditionally treated as moved, matching that.
    - The return-statement drop-insertion's "don't drop what this return
      expression still needs" check was tried, for one iteration, as a
      *precise* transfer analysis (only the bare returned identifier, or
      an identifier passed to a non-borrowed parameter, was exempted).
      That is wrong for this specific purpose: the drops it inserts run
      *before* the return statement, so an identifier the expression
      merely *reads* (a borrowed sub-argument, e.g. `return
      fs_rt_str_dup(view);`) must also not be dropped first, or the read
      is a use-after-drop -- a real bug, strictly worse than the leak it
      was trying to fix. Reverted to the conservative superset (any
      identifier referenced anywhere in the return expression is
      exempted from pre-return dropping); the narrower borrowed-in-return
      case is fixed at specific call sites instead (see
      `std/internal/runtime.fire::fs_rt_argv_at`).
13. **Two-phase dataflow reporting (architectural fix, Phase 3).**
    `ir_analysis.forward_dataflow`'s worklist driver calls `transfer()`
    repeatedly per block across fixpoint rounds, on intermediate,
    not-yet-converged states -- `fir/ownership_verifier.py` originally
    called `self.emit(...)` as a side effect *inside* that transfer
    function, which both duplicated genuine violations (one emission per
    visit) and fabricated spurious ones (a static instruction inside a
    loop body, revisited on a later fixpoint round, would see its *own*
    prior-iteration `MOVED` state and report a use-after-move against
    itself). Fixed by converging silently first (`self._reporting =
    False`), then running exactly one more, side-effect-enabled pass per
    block using each block's final converged in-state
    (`self._reporting = True`). Any dataflow-based Tier-2 checker (FLIR's
    heap-token analysis in Phase 4 included) must follow the same
    two-phase shape.
14. **FLIRV-A4 narrowed to named-slot-tracked tokens (Phase 4).** Same
    root cause and same fix as item 10 (anonymous expression temporaries):
    `flir/heap_verifier.py`'s heap-token dataflow tracks a token's
    identity through must-alias slot stores/loads, but a fresh allocation
    that is only ever read as an anonymous sub-expression (e.g. an
    intermediate concatenation result in a chain like `"a" + x + "b"`,
    never bound to a slot) is still `LIVE` at every `ret` -- flagging it
    as a leak would surface the exact same enormous, untargeted,
    pre-existing gap the FIR ownership verifier already deliberately
    scopes out. `FLIRV-A4` therefore only reports a token currently
    referenced by a named slot; A1-A3 and A5 are unaffected (they fire on
    an actual use/free, not merely on "unfreed at return").
15. **FLIRV-A5 exempts a struct's own `<S>__destroy` and shallow-free
    releases (Phase 4).** Two legitimate direct-`fs_rt_free` sites would
    otherwise be misflagged as "should have called the destructor":
    - `<S>__destroy` itself (`flir/lowering.py::ensure_destructor` /
      `ensure_enum_destructor`) frees `S`'s own backing allocation as its
      terminal step, *after* already recursively freeing/destroying each
      owned field individually earlier in the same function -- exempted
      structurally when the verified function's name is
      `f"{pointee}__destroy"`.
    - `ast_to_fir.py::_convert_super_call` releases a temporary
      base-class object after splicing its fields onto `this`, without
      running the base class's destructor (the fields already transferred
      ownership to `this`; running the destructor too would free them a
      second time once `this` is later dropped). Lowered from a distinct
      FIR-level `free_shallow` intrinsic, which collapses to the same
      `fs_rt_free` call as any other free at the FLIR level -- so
      `flir/lowering.py::lower_call` tags the emitted `Call`'s
      (`flir/ir.py::FInst.metadata`) with `shallow_free: True`, and the
      verifier exempts calls carrying that tag.
16. **The array-to-string and `println<T>` leaks the verifier caught
    (Phase 4, fixed at the emitter).** Both real, pre-existing bugs, not
    verifier false positives:
    - `flir/lowering.py::_array_to_string` built its `"[a, b, c]"`
      accumulator via repeated `str_concat` + `slotstore` without ever
      freeing the accumulator's previous value or each element's
      converted-to-string result -- every array-to-string conversion
      leaked one allocation per element. Fixed by freeing the superseded
      accumulator value and the per-element conversion result once each
      has been read by the next `str_concat`.
    - `std/io.fire::println<T>` built `(value as string) + "\n"` inline;
      the intermediate cast result was never freed (the same anonymous-
      expression-temporary gap as items 10 and 14, just one that happened
      to be a *named* function's own leak rather than caller-side).
      Fixed by binding the cast to a name (`cast_text`) and dropping it
      after the concatenation.

## 9. Testing

- **Negative unit tests** (the main new coverage): construct invalid IR
  directly and assert the exact rule id fires.
  - `tests/python/fir/test_verifier_structure.py`, `..._types.py`,
    `..._ownership.py`, `..._generators.py` — built with `FIRBuilder`,
    following the existing `tests/python/fir/test_validation.py` pattern
    (whose two cases migrate into the structure module).
  - `tests/python/flir/test_verifier_structure.py`, `..._types.py`,
    `..._memory.py`, `..._alloc.py` — FLIR modules built directly from
    `flir.ir` objects.
  - One test per rule id minimum, plus a passing "clean module" case per
    verifier proving no false positives on well-formed IR.
- **Positive corpus:** the entire existing suite (`python tests/run.py`) —
  every `run`/`snapshot`/`determinism` test now implicitly asserts that real
  programs verify at both IR levels. No new `.fire` tests are needed for the
  verifier itself (it is unobservable from valid source), but any compiler
  bug it uncovers gets a regression `.fire` test per the usual rule.
- `tests/TEST_MANIFEST.md` gains entries for the new python test modules.

## 10. Open questions

- **Generator frames** (§8.3): destructor for suspended frames, or a
  documented carve-out?
- **FIRV-E1 guard shape:** if match lowering ever emits jump-table-style
  dispatch instead of `tag == k` branch chains, the guard-recognition
  pattern must grow with it (the *rule* — no unguarded payload reads —
  stays).
- **Verification cost:** Tier-2 dataflow is linear per function in practice
  but should be measured on the largest std modules (`std/internal/
  runtime.fire`) once Phase 3 lands; if it ever dominates compile time the
  answer is algorithmic (better sparse analysis), not sampling or skipping.
