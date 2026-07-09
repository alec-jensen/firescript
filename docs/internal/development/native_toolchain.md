# Native Toolchain (self-hosted assembler + PE writer) [IMPLEMENTED]

firescript produces native Windows x86_64 executables with **no external tools** —
no `as`, `ld`, `objdump`, gcc, or clang, and no third-party Python packages. The
back of the pipeline is:

```
FLIR → codegen/flir_to_asm.py → x86-64 GAS text
     → backend/assembler.py    → object image (bytes + symbols + relocs)
     → backend/pe.py           → PE32+ .exe importing only kernel32.dll
```

Everything runs in-process from `main.py:_compile_asm`.

## Assembler (`firescript/backend/assembler.py`)

`assemble(text) -> ObjectImage` parses the exact Intel-syntax grammar that
`flir_to_asm.py` emits — a closed, controlled set — and encodes it to machine
code. Anything outside the grammar raises `AssemblerError` so a new backend form
can't be silently miscompiled.

- **Coverage**: mov family (incl. `movabs`, byte/word/dword/qword memory and
  immediates, the accumulator imm32 short forms), add/sub/and/or/xor/cmp,
  imul (2- and 3-operand), idiv/div/neg/not/inc/dec, test, lea, push/pop,
  ret/cqo/int3, jmp/jcc, call, setcc, movzx/movsx/movsxd, and the SSE2 scalar
  set (`mov{ss,sd}`, add/sub/mul/div, `comis{s,d}`, `cvt*`, `xorp{s,d}`,
  movd/movq). Addressing: register, `[base+disp]`, `[base+index*scale±disp]`
  (SIB), and `[rip+label]`, with correct REX.W/R/X/B, ModRM, and SIB bytes.
- **Deterministic, relaxation-free**: jmp/jcc/call always use the rel32 form and
  RIP-relative data references always use disp32, so instruction lengths are
  fixed at parse time (no branch relaxation pass). base+disp uses disp8 when it
  fits, else disp32; rbp/r13 always carry a displacement, rsp/r12 always use a
  SIB byte.
- **Two passes**: encode to bytes recording label offsets and fixups; then patch
  intra-`.text` rel32 fixups (named labels and GAS numeric `Nf`/`Nb` locals).
  Cross-section RIP references (to `.rdata`/`.bss`) and import calls become
  `Reloc` entries the PE writer resolves at layout time.
- **Import calls**: `call <kernel32 fn>` is encoded as `FF /2` RIP-indirect
  through the IAT (`call [rip+slot]`) with a `RIP32_IMPORT` reloc — keeping the
  code position-independent.
- **String bytes**: `.asciz` literals are decoded with the locale codec (matching
  how the backend writes, and `as` would read, the `.s`), and octal escapes
  (`\012`) take precedence over the `\0` NUL escape — both were real parity bugs
  found by the differential test.

Validation: `tests/asm_encoding_tests.py` differentially byte-compares 87
instruction forms against MinGW `as` when present (and skips cleanly when not,
so the suite needs only Python).

## PE writer (`firescript/backend/pe.py`)

`write_pe(obj, out_path, import_dll_map)` lays out sections and writes a PE32+
console executable by hand:

- Sections: `.text` (RX), `.rdata` (R; also holds the import directory, ILT/IAT,
  and hint/name table), and `.data` (RW, uninitialized) for mutable globals.
- Import table built from the module's externs (only `kernel32.dll` today):
  one descriptor per DLL, ILT + IAT thunks pointing at hint/name entries; the
  assembler's import-call sites are fixed up to the IAT slot RVAs.
- Relocations: the backend's code is fully position-independent (RIP-relative
  data refs, IAT-indirect calls), so the image has **no absolute addresses and
  no base relocations**. It is still marked
  `DYNAMICBASE | NXCOMPAT | HIGH_ENTROPY_VA` with `RELOCS_STRIPPED` clear, so the
  loader treats it as a normal relocatable, ASLR-eligible, DEP-compatible
  program — important for antivirus friendliness.
- Headers: PE32+ optional header, console subsystem, entry point at
  `firescript_entry`, ImageBase `0x140000000`, SectionAlignment `0x1000`,
  FileAlignment `0x200`, import + IAT data directories.

Output is byte-deterministic. `backend/pe_inspect.py` is a stdlib-only PE import
reader used by the test suite (replacing `objdump`) to assert binaries import
only kernel32.

## Why text-in/assembler-out

The backend keeps emitting GAS text (unchanged, tested at parity), and the
assembler consumes it. During bringup this made validation apples-to-apples: the
*same* `.s` had to turn into a working binary through both `as`+`ld` and our
toolchain. The interim `--toolchain {binutils,self}` flag is gone now that the
self toolchain is the only path.
