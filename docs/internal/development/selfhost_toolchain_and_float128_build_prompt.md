# Build Prompt: Self-Hosted Native Toolchain + True binary128 float128

> Self-contained build prompt. Hand it to a developer or coding agent starting cold.
> It encodes all decisions already made; do not re-litigate them. Read the referenced
> design docs before writing code.

---

## Mission

Two independent tracks, one end state:

**Track A — Self-hosted toolchain.** Make the firescript compiler depend on **nothing but
Python** to produce a runnable native binary. Today the compiler emits GAS Intel-syntax
assembly and shells out to MinGW `as` (assemble) and `ld` (link), and the test suite uses
`objdump`. Replace all three with our own code: a pure-Python x86-64 assembler and a
pure-Python PE32+ writer/linker. After this track, compiling invokes **zero external
processes**.

**Track B — True binary128.** Replace the current `float128`-aliases-`float64` stopgap with
real IEEE 754 binary128: 16-byte values, correctly-rounded literal parsing, exact decimal
formatting, and a full software-float operation set (arithmetic, comparisons, conversions),
implemented in firescript over `uint64` pairs.

The compiler stays written in Python. The target stays **Windows x64**. The language runtime
stays implemented in firescript (`std/internal/runtime.fire`); Track B's soft-float lives
there too.

End-state pipeline (Track A):

```
Source → … → FLIR → FLIR→x86-64 GAS text (unchanged)
       → Python x86-64 assembler → object image (sections + symbols + relocations)
       → Python PE32+ writer → freestanding .exe importing only kernel32.dll
```

No `as`, no `ld`, no `objdump`, no `gcc`/`clang`, no import libraries, no pip packages —
Python standard library only.

## Locked Decisions

Decided by the project owner; treat as requirements:

1. **Assembler consumes the backend's existing GAS text.** Keep `codegen/flir_to_asm.py`
   and its textual output unchanged. Write a standalone Python x86-64 assembler that parses
   exactly the Intel-syntax instruction forms that backend emits (a closed, fully-controlled
   set) and encodes them to machine code. Rationale: the 88/88-passing backend is untouched,
   `--emit asm` keeps working, and the interim differential test becomes apples-to-apples
   (the *same* `.s` must produce a working binary through both `as`+`ld` and our toolchain).
2. **Keep the MinGW path behind a flag during bringup, then delete it.** Mirror the FIR
   migration's interim-C approach: bring up the Python assembler+linker alongside `as`/`ld`,
   validate differentially, then remove binutils entirely at cutover. A `--toolchain
   {binutils,self}` flag selects the path; default stays `binutils` until parity, flips to
   `self` at cutover, then both the flag and the binutils code are removed.
3. **Standard relocatable PE images.** Emit conventional PE32+ console executables with a
   base relocation table, `DYNAMICBASE`/`NXCOMPAT` DLL characteristics, and normal section
   layout, so the OS and antivirus treat them like ordinary programs. (A binutils-built
   binary already tripped Malwarebytes once; an unusual hand-rolled image is *more* likely to
   trip heuristics.) Prefer position-independent code (the backend already uses `lea
   [rip+…]` and IAT-indirect calls) so the relocation table is minimal, but the image must
   still be a valid, ASLR-compatible PE.
4. **True IEEE binary128 for float128, correctly rounded.** Round-to-nearest-even
   decimal→binary128 literal parsing; exact binary128→decimal formatting (same family of
   algorithm as the shipped f64 dtoa); the full soft-float op set. No approximations.

## Ground Rules (from CLAUDE.md — apply throughout)

- Project name is **firescript**, lowercase.
- Never edit a test to force it to pass; fix the compiler. Golden regeneration is allowed
  only for the documented float128-precision change (Track B) and must be reviewed
  diff-by-diff with a changelog entry.
- Every bug fix gets a regression test.
- New directives/intrinsics are internal-only and documented in
  `docs/internal/directives.md`.
- Keep `CLAUDE.md`'s feature status table accurate as features move.
- Commits are GPG-signed; run `git commit` in the background and pass the message via
  `-F <file>`. No AI co-author trailer.
- Commit at each phase gate; keep `main` green (the `binutils` toolchain stays the default
  until the Track A cutover).
- Python standard library only. No third-party packages, including for test vector
  generation (use `fractions`/`decimal`/`struct` from stdlib).

## Current State Inventory (verify before starting)

- Backend: `firescript/codegen/flir_to_asm.py` — `FLIRToAsmBackend.generate()` returns
  `.intel_syntax noprefix` GAS text: a `.text` section, `.rdata` (string literals as
  `.asciz`, float/global constants as `.quad`/`.long`), and (if any mutable globals) a
  `.bss` via `.space`. Entry symbol `firescript_entry`. Win64 ABI; rbp-based frames;
  page-probe prologues for frames ≥ 4 KiB; SSE2 scalar floats; kernel32 externs declared as
  `Win64Convention`-isolated calls. **This is the closed instruction set the assembler must
  cover** — enumerate every mnemonic/operand form it emits before writing the encoder.
- Driver: `firescript/main.py` `_compile_asm()` writes the `.s`, runs `as` then `ld`
  (`-e firescript_entry --subsystem console -L<dir> -lkernel32`), via `_find_binutil()` and
  `_kernel32_lib_dir()`.
- Test import check: `tests/golden_runner.py` `check_kernel32_only()` shells out to
  `objdump -p`.
- float128 today: lexer parses the `f128` suffix; `flir/lowering.py` maps `float128 → F64`
  (`_SCALARS["float128"] = F64`); `parser/base.py`/`type_system.py` accept `float128`;
  `docs` mark it `[IN DEVELOPMENT]`. Golden `float128_test.out` etc. show f64-precision
  output.
- Kernel32 externs currently used by the runtime (the import table the PE writer must build):
  `GetProcessHeap`, `HeapAlloc`, `HeapFree`, `GetStdHandle`, `WriteFile`, `ReadFile`,
  `CreateFileA`, `CloseHandle`, `DeleteFileA`, `MoveFileExA`, `CopyFileA`, `GetLastError`,
  `GetCommandLineA`, `GetFileSize`, `SetFilePointer`, `ExitProcess` (the set is whatever
  `flir_module.externs` contains — drive it from there, do not hardcode).
- Suites: `tests/golden_runner.py` (88), `tests/error_runner.py` (31), `tests/fir_snapshot_runner.py`
  (25 FIR+FLIR), `tests/fir_unit_tests.py` (9).

---

## Track A — Self-Hosted Assembler + PE Linker

### Phase A0 — Pure-Python PE inspector; toolchain flag

1. Add `firescript/backend/pe_inspect.py`: parse a PE32+ file's import directory and return
   `{dll: [function, ...]}`. Pure stdlib (`struct`). Used by tests; works on the current
   binutils-built binaries too.
2. Switch `golden_runner.check_kernel32_only()` to use it instead of `objdump`.
3. Add `--toolchain {binutils,self}` to `main.py` (default `binutils`); thread it into
   `_compile_asm`. `self` is a stub that errors until Phase A2.

**Gate A0**: full suite green on the `binutils` toolchain; the kernel32-only check runs in
Python; `objdump` is no longer invoked by the test suite.

### Phase A1 — x86-64 assembler

Add `firescript/backend/assembler.py`: parse the backend's GAS Intel text and encode to
machine code. Output an in-memory object: per-section byte buffers (`.text`, `.rdata`,
`.bss` size), a symbol table (label → section+offset, plus external/import symbols), and a
relocation list (site, target symbol, kind: `rel32` for `call`/`jmp`/`lea [rip+…]`,
`imm64`/`abs64` for any absolute data pointers, `rel32-import` for calls through the IAT).

- Cover **exactly** the mnemonic/operand forms `flir_to_asm.py` emits — enumerate them from
  the backend and the runtime's compiled output; assert-and-fail loudly on anything
  unrecognized so new backend forms can't silently miscompile.
- Correctly handle REX (incl. REX.W), ModRM, SIB (base+index*scale), displacement sizing
  (disp0/disp8/disp32), RIP-relative disp32, immediate sizing, two-/three-byte SSE opcodes
  (`0F`, `F2 0F`, `F3 0F`, `66 0F`), and the `setcc`/`movzx`/`movsx`/`movsxd`/`cvt*` forms.
- Local labels resolve intra-image; `call <import>` encodes as `call [rip+IAT_slot]` (the
  backend already routes externs this way — confirm and keep it position-independent).

Differential test (`tests/asm_encoding_tests.py`): for each test source, assemble the
backend's `.s` with **both** our assembler and `as`, and compare the `.text`/`.rdata` bytes.
Byte-identical is the bar where achievable; where `as` makes a different-but-valid encoding
choice (e.g. redundant REX, disp size), document the specific divergence and assert semantic
equivalence instead.

**Gate A1**: our assembler encodes every test source's `.s`; encodings match `as` (or are
documented equivalent); assembler output is byte-deterministic.

### Phase A2 — PE32+ writer / linker

Add `firescript/backend/pe.py`: lay out sections, resolve relocations, and write a valid
PE32+ console executable.

- DOS stub, COFF header, PE32+ optional header (ImageBase e.g. `0x140000000`,
  SectionAlignment `0x1000`, FileAlignment `0x200`, Subsystem = 3 console,
  DllCharacteristics = `DYNAMICBASE | NXCOMPAT | HIGH_ENTROPY_VA`), section headers,
  AddressOfEntryPoint = RVA of `firescript_entry`.
- Sections: `.text` (RX), `.rdata` (R, includes the import directory + ILT/IAT + string/float
  constants), `.data`/`.bss` (RW, mutable globals), `.reloc` (base relocations).
- Import directory built from `flir_module.externs` (drive it from the module, not a
  hardcoded list): one descriptor per DLL (only `kernel32.dll` today), ILT + IAT + hint/name
  table; the assembler's `call [rip+IAT_slot]` sites point at the IAT entries.
- Base relocations: keep code/data position-independent (RIP-relative) so the `.reloc` table
  is minimal/empty; still emit a valid `.reloc` and set `DYNAMICBASE` truthfully so the
  loader can ASLR the image.
- `_compile_asm(toolchain="self")` wires assembler → PE writer; no subprocess calls.

**Gate A2**: `--toolchain self` produces a runnable `.exe` for a representative subset
(fibonacci, classes, generics, generators, strings, syscalls/fs); each runs correctly and
the Python inspector reports only `kernel32.dll`.

### Phase A3 — Parity

Run the full suites under `--toolchain self`.

**Gate A3 (parity gate)**: 100% of the golden suite passes via `--toolchain self` with output
identical to the `binutils` toolchain; error suite unchanged; every binary imports only
`kernel32.dll`; binaries are valid PE32+ (loads and runs; spot-check on the owner's machine
for AV false positives given the prior Malwarebytes hit).

### Phase A4 — Cutover and deletion

1. Make `self` the only path. Remove `--toolchain`, `_find_binutil`, `_kernel32_lib_dir`,
   and all `as`/`ld` subprocess code from `main.py`.
2. Docs: README build requirements (now **Python only** — no MinGW/binutils); changelog
   breaking-change entry; `CLAUDE.md` feature table (native backend is self-contained);
   internal design doc `docs/internal/development/native_toolchain.md` (assembler scope, PE
   layout, relocation/import handling). Update CI to drop the binutils install.

**Gate A4**: see Completion Criteria. No `as`/`ld`/`objdump`/`gcc`/`clang`/binutils
references remain in `firescript/` or the test/CI path; compiling invokes zero external
processes.

---

## Track B — True binary128 float128

binary128: 16 bytes, 1 sign bit + 15 exponent bits (bias 16383) + 112 stored mantissa bits
(113 effective). No x86-64 hardware support → software float.

### Phase B0 — FLIR f128 type and memory plumbing

1. Add a 16-byte `f128` FLIR type (size 16, align 16). Map firescript `float128 → f128`
   (remove the `float128 → F64` alias). It is a by-value 16-byte value: stored in two
   `uint64` halves, passed to functions **by pointer** (Win64 passes >8-byte aggregates by
   pointer), and returned via a hidden result pointer — exactly the path structs already use,
   so **the assembler needs no new instruction encodings** (only `mov`/`lea` over 16-byte
   memory, which the backend already does for structs).
2. Compile-time literal parsing (Python): `1.25f128` etc. → a 128-bit pattern with
   round-to-nearest-even, using big-integer arithmetic (stdlib `fractions`/`int`). Emit as a
   16-byte `.rdata` constant.

**Gate B0**: float128 locals/params/returns/literals round-trip through memory; a first
`fs_rt_f128_to_str` (may start rough) prints something; no crashes.

### Phase B1 — Soft-float core (firescript)

Implement in `firescript/std/internal/float128.fire` (or extend `runtime.fire`) over
`uint64` hi/lo pairs, behind `directive enable_lowlevel_runtime`:
`fs_rt_f128_add/sub/mul/div` and comparisons (`eq/ne/lt/le/gt/ge`), correctly rounded
(round-to-nearest-even), with subnormal, infinity, NaN, and signed-zero handling.
Unit-test against vectors computed with stdlib only (`fractions`/`decimal`).

**Gate B1**: arithmetic and comparisons are correctly rounded across a vector suite
(normals, subnormals, inf, nan, ties).

### Phase B2 — Conversions, parse, exact format

`fs_rt_f128` conversions: f128↔f64, f128↔i64/u64 (narrower ints via i64/u64), and
string↔f128 — correctly-rounded parse and **exact** decimal formatting (`%f`/`%g` family,
generalizing the f64 dtoa to 113-bit mantissa and the binary128 exponent range).

**Gate B2**: casts in both directions and string parse/format are correct on a vector suite.

### Phase B3 — Integration and docs

1. Route all float128-typed FLIR ops (BinaryOp/compare/Cast/toString) to the `fs_rt_f128_*`
   runtime calls in lowering.
2. Regenerate the float128-affected goldens to true-precision output (review diff-by-diff;
   changelog entry — this is a documented behavior change from the alias).
3. Docs: `CLAUDE.md` feature table `float128 → [IMPLEMENTED]`; `docs/reference/type_system.md`
   drops the alias note; changelog; internal design doc
   `docs/internal/development/float128.md` (representation, ABI, soft-float algorithms).

**Gate B3**: full suite green; float128 behaves as true IEEE binary128.

---

## Completion Criteria

Done when ALL hold on a clean clone with **only Python installed** (no MinGW, binutils,
gcc/clang, or any pip package):

1. `python firescript/main.py <file>.fire` produces a runnable Windows x64 `.exe` and invokes
   **zero external processes** — no `as`/`ld`/`objdump`/`gcc`/`clang`. Putting (or removing)
   binutils on `PATH` has no effect on output.
2. A grep of `firescript/` finds no reference to `as`/`ld`/`objdump`/`gcc`/`clang`/binutils
   in the compile path; `subprocess` is not used for codegen/assembly/linking; `--cc` and
   `--toolchain` no longer exist.
3. Produced binaries are valid PE32+ console executables importing **only** `kernel32.dll`
   (verified by the pure-Python inspector), marked `DYNAMICBASE`/`NXCOMPAT`, ASLR-compatible,
   and run correctly. Spot-checked clean against the owner's AV.
4. `tests/golden_runner.py` 100% (every prior-passing case), `tests/error_runner.py` 31/31
   byte-identical, `tests/fir_snapshot_runner.py` deterministic, and `tests/fir_unit_tests.py`
   plus the new `tests/asm_encoding_tests.py` and float128 unit tests all pass. The test suite
   itself needs only Python.
5. The assembler and PE writer are byte-deterministic (same input → identical output bytes),
   with a determinism test.
6. `float128` is true IEEE binary128: 16-byte storage; correctly-rounded (round-to-nearest-
   even) literal parsing; exact decimal formatting; full arithmetic/comparison/conversion
   set; documented `[IMPLEMENTED]`. float128 goldens reflect true precision and the change is
   changelog-documented.
7. The binutils path existed only as an interim `--toolchain binutils` for differential
   validation and is fully removed at cutover (no flag, no `as`/`ld` code, no import-lib
   lookup).
8. Docs accurate: changelog (Python-only build, float128 now true precision), README build
   requirements (Python only; Windows x64), `CLAUDE.md` feature table, and the two internal
   design docs (`native_toolchain.md`, `float128.md`). CI installs only Python.
9. LSP server and VS Code extension behavior unchanged (front-end untouched).

## Known Risks / Watch Items

- **x86-64 encoding correctness** (REX.W, ModRM RIP-relative disp32, SIB index, multi-byte
  SSE opcodes, immediate/displacement sizing) is the single largest risk. The Phase A1
  byte-compare against `as` on the backend's own `.s` is the primary mitigation — do it for
  every test source, not a sample.
- **PE loader pickiness** (alignment, import directory/ILT/IAT layout, `.reloc` format,
  entry RVA). Mitigate by diffing structure against a binutils-built reference image and by
  actually loading on Windows.
- **AV false positives** on hand-rolled PEs — the owner already hit Malwarebytes once.
  Conventional layout + relocations + correct characteristics + (optionally) omitting a Rich
  header; test on the owner's machine before declaring A3 done.
- **binary128 soft-float correctness** (rounding, subnormals, NaN propagation, division,
  ties-to-even). Build a stdlib-only vector suite; division and exact dtoa are the hardest.
- **float128 Win64 ABI** consistency: 16-byte by pointer, hidden-pointer return, 16-byte slot
  alignment — keep caller, callee, and the soft-float runtime signatures in agreement.
- Keep the `binutils` toolchain runnable until Gate A3 passes — never strand `main` without a
  working default.
```
