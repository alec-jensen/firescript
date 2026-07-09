"""Pure-Python x86-64 assembler for the FLIR backend's GAS Intel-syntax output.

Consumes exactly the instruction/operand grammar that
`codegen/x86_64/flir_to_asm.py` emits (a closed, controlled set) and
produces an `ObjectImage`: per-section bytes, a symbol table, and a
relocation list the executable writer (e.g. `backend/windows/pe.py`)
resolves at layout time. No external tools.

Encoding choices kept deterministic and relaxation-free:
- jmp/jcc/call always use the rel32 form (no short-branch relaxation).
- RIP-relative data references always use disp32.
- base+disp uses disp8 when it fits in a signed byte, else disp32 (rbp/r13
  always carry at least disp8; rsp/r12 always use a SIB byte).

Anything outside the grammar raises AssemblerError loudly so a new backend
form can't be silently miscompiled.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from typing import Optional


class AssemblerError(Exception):
    pass


# ---------------------------------------------------------------------------
# Registers
# ---------------------------------------------------------------------------

# name -> (number 0..15, size in bits, is_xmm)
_GP = {}
_names64 = ["rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi",
            "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"]
_names32 = ["eax", "ecx", "edx", "ebx", "esp", "ebp", "esi", "edi",
            "r8d", "r9d", "r10d", "r11d", "r12d", "r13d", "r14d", "r15d"]
_names16 = ["ax", "cx", "dx", "bx", "sp", "bp", "si", "di",
            "r8w", "r9w", "r10w", "r11w", "r12w", "r13w", "r14w", "r15w"]
# Low-byte registers with REX semantics (spl/bpl/sil/dil require REX).
_names8 = ["al", "cl", "dl", "bl", "spl", "bpl", "sil", "dil",
           "r8b", "r9b", "r10b", "r11b", "r12b", "r13b", "r14b", "r15b"]
for i, n in enumerate(_names64):
    _GP[n] = (i, 64, False)
for i, n in enumerate(_names32):
    _GP[n] = (i, 32, False)
for i, n in enumerate(_names16):
    _GP[n] = (i, 16, False)
for i, n in enumerate(_names8):
    _GP[n] = (i, 8, False)
# Legacy high-byte names not used by the backend; low-byte ah/ch/dh/bh omitted.
_XMM = {f"xmm{i}": (i, 128, True) for i in range(16)}


@dataclass
class Reg:
    num: int
    size: int
    is_xmm: bool


@dataclass
class Mem:
    size: Optional[int]          # operand size in bits, or None if unknown
    base: Optional[int]          # GP register number, or None
    disp: int = 0
    rip_label: Optional[str] = None  # RIP-relative target symbol
    index: Optional[int] = None  # GP register number for base+index addressing
    scale: int = 1               # 1/2/4/8


@dataclass
class Imm:
    value: int


@dataclass
class Sym:
    name: str                    # jump/call target label


def _parse_reg(tok: str) -> Optional[Reg]:
    if tok in _GP:
        n, s, _ = _GP[tok]
        return Reg(n, s, False)
    if tok in _XMM:
        n, s, _ = _XMM[tok]
        return Reg(n, s, True)
    return None


_PTR_SIZES = {"byte": 8, "word": 16, "dword": 32, "qword": 64}


def _parse_mem(tok: str) -> Optional[Mem]:
    size = None
    m = re.match(r"^(byte|word|dword|qword)\s+ptr\s+(.*)$", tok)
    if m:
        size = _PTR_SIZES[m.group(1)]
        tok = m.group(2).strip()
    if not (tok.startswith("[") and tok.endswith("]")):
        return None
    inner = tok[1:-1].strip()
    if inner.startswith("rip"):
        rest = inner[3:].strip()
        # forms: rip + label  /  rip+label
        rest = rest.lstrip("+").strip()
        return Mem(size=size, base=None, rip_label=rest)
    # base + index [* scale] [+/- disp]
    m = re.match(
        r"^([a-z][a-z0-9]*)\s*\+\s*([a-z][a-z0-9]*)(?:\s*\*\s*(\d+))?\s*"
        r"([+-]\s*(?:0x[0-9a-fA-F]+|\d+))?$",
        inner,
    )
    if m:
        base_reg = _parse_reg(m.group(1))
        index_reg = _parse_reg(m.group(2))
        if base_reg is None or index_reg is None or base_reg.is_xmm or index_reg.is_xmm:
            raise AssemblerError(f"bad base+index operand: [{inner}]")
        scale = int(m.group(3)) if m.group(3) else 1
        disp = int(m.group(4).replace(" ", ""), 0) if m.group(4) else 0
        return Mem(size=size, base=base_reg.num, index=index_reg.num, scale=scale, disp=disp)
    # base [+/- disp]
    m = re.match(r"^([a-z0-9]+)\s*([+-]\s*(?:0x[0-9a-fA-F]+|\d+))?$", inner)
    if not m:
        raise AssemblerError(f"unsupported memory operand: [{inner}]")
    base_reg = _parse_reg(m.group(1))
    if base_reg is None or base_reg.is_xmm:
        raise AssemblerError(f"bad memory base: {m.group(1)}")
    disp = 0
    if m.group(2):
        disp = int(m.group(2).replace(" ", ""), 0)
    return Mem(size=size, base=base_reg.num, disp=disp)


def _parse_operand(tok: str):
    tok = tok.strip()
    r = _parse_reg(tok)
    if r is not None:
        return r
    if tok.startswith("[") or re.match(r"^(byte|word|dword|qword)\s+ptr", tok):
        return _parse_mem(tok)
    if re.match(r"^\d+[bf]$", tok):  # GAS numeric local label ref (1f / 2b)
        return Sym(tok)
    if re.match(r"^-?\d", tok) or tok.startswith("0x") or tok.startswith("-0x"):
        return Imm(int(tok, 0))
    return Sym(tok)


# ---------------------------------------------------------------------------
# Object image
# ---------------------------------------------------------------------------

# Relocation kinds resolved by the PE writer (cross-section / imports).
RIP32 = "rip32"        # RIP-relative disp32 to a data symbol (rdata/bss)
RIP32_IMPORT = "rip32_import"  # RIP-relative disp32 to an import IAT slot


@dataclass
class Reloc:
    section: str
    offset: int          # byte offset of the disp32 field within the section
    kind: str
    symbol: str
    next_ip: int         # section offset just past the instruction (for RIP math)
    addend: int = 0


@dataclass
class ObjectImage:
    text: bytearray = field(default_factory=bytearray)
    rdata: bytearray = field(default_factory=bytearray)
    bss_size: int = 0
    # symbol name -> (section, offset). section in {"text","rdata","bss"}
    symbols: dict = field(default_factory=dict)
    globals: set = field(default_factory=set)
    relocs: list = field(default_factory=list)
    import_symbols: set = field(default_factory=set)  # referenced but undefined (kernel32)


# ---------------------------------------------------------------------------
# Encoding primitives
# ---------------------------------------------------------------------------

def _rex(w: int, r: int, x: int, b: int, force: bool = False) -> Optional[int]:
    val = 0x40 | (w << 3) | ((r & 8) >> 1) | ((x & 8) >> 2) | ((b & 8) >> 3)
    if w or (r & 8) or (x & 8) or (b & 8) or force:
        return val
    return None


def _modrm(mod: int, reg: int, rm: int) -> int:
    return (mod << 6) | ((reg & 7) << 3) | (rm & 7)


def _mem_encode(reg_field: int, mem: Mem):
    """Return (rex_r, rex_x, rex_b, modrm_and_sib_and_disp_bytes, rip_fixup).

    rip_fixup is None or ('rip', label, disp_offset_within_returned_bytes).
    reg_field is the /r register number (for the reg operand).
    """
    out = bytearray()
    if mem.rip_label is not None:
        # mod=00, rm=101 => RIP + disp32
        out.append(_modrm(0, reg_field, 5))
        disp_off = len(out)
        out += b"\x00\x00\x00\x00"
        return (reg_field, 0, 0, out, ("rip", mem.rip_label, disp_off))

    base = mem.base
    disp = mem.disp
    _SCALE_BITS = {1: 0, 2: 1, 4: 2, 8: 3}
    # base+index, or rsp/r12 base (always needs SIB).
    needs_sib = mem.index is not None or (base & 7) == 4
    # rbp / r13 (rm==5 / SIB base 101) cannot use mod=00; force a disp.
    base_is_bp = (base & 7) == 5
    if disp == 0 and not base_is_bp:
        mod = 0
    elif -128 <= disp <= 127:
        mod = 1
    else:
        mod = 2

    index_num = 0
    if needs_sib:
        out.append(_modrm(mod, reg_field, 4))
        if mem.index is not None:
            index_num = mem.index
            sib = (_SCALE_BITS[mem.scale] << 6) | ((index_num & 7) << 3) | (base & 7)
        else:
            # no index (rsp/r12 base): index field = 100 (none)
            sib = (0 << 6) | (4 << 3) | (base & 7)
        out.append(sib)
    else:
        out.append(_modrm(mod, reg_field, base & 7))

    if mod == 1:
        out += struct.pack("<b", disp)
    elif mod == 2:
        out += struct.pack("<i", disp)
    return (reg_field, index_num, base, out, None)


# ---------------------------------------------------------------------------
# Assembler
# ---------------------------------------------------------------------------

# Two-byte jcc opcodes (second byte); rel32 form: 0F 8x cd.
_JCC = {"jnz": 0x85, "jz": 0x84, "jb": 0x82, "jae": 0x83, "je": 0x84, "jne": 0x85}
_SETCC = {
    "sete": 0x94, "setne": 0x95, "setb": 0x92, "setbe": 0x96,
    "seta": 0x97, "setae": 0x93, "setl": 0x9C, "setle": 0x9E,
    "setg": 0x9F, "setge": 0x9D,
}
_ALU = {  # name -> (/r opcode for r/m,r ; /digit for imm)
    "add": (0x01, 0), "or": (0x09, 1), "and": (0x21, 4), "sub": (0x29, 5),
    "xor": (0x31, 6), "cmp": (0x39, 7),
}
# Accumulator-with-imm32 short forms (no ModRM); matches `as` for rax/eax dst.
_ALU_ACC = {"add": 0x05, "or": 0x0D, "and": 0x25, "sub": 0x2D, "xor": 0x35, "cmp": 0x3D}
_SSE = {  # name -> (prefix bytes, opcode2, reg_is_dst_for_load)
    "movss": ("F3", 0x10), "movsd": ("F2", 0x10),
    "addss": ("F3", 0x58), "addsd": ("F2", 0x58),
    "subss": ("F3", 0x5C), "subsd": ("F2", 0x5C),
    "mulss": ("F3", 0x59), "mulsd": ("F2", 0x59),
    "divss": ("F3", 0x5E), "divsd": ("F2", 0x5E),
    "cvtss2sd": ("F3", 0x5A), "cvtsd2ss": ("F2", 0x5A),
    "cvtsi2ss": ("F3", 0x2A), "cvtsi2sd": ("F2", 0x2A),
    "cvttss2si": ("F3", 0x2C), "cvttsd2si": ("F2", 0x2C),
    "comiss": ("NP", 0x2F), "comisd": ("66", 0x2F),
    "xorps": ("NP", 0x57), "xorpd": ("66", 0x57),
}
_PREFIX_BYTE = {"F3": 0xF3, "F2": 0xF2, "66": 0x66, "NP": None}


class _Fixup:
    __slots__ = ("offset", "kind", "target", "next_ip")

    def __init__(self, offset, kind, target, next_ip):
        self.offset = offset      # offset of disp32/rel32 field in .text
        self.kind = kind          # 'rel32' (code label) | 'rip32' (data) | 'import'
        self.target = target
        self.next_ip = next_ip


def assemble(text: str) -> ObjectImage:
    return _Assembler(text).run()


class _Assembler:
    def __init__(self, text: str):
        self.lines = text.splitlines()
        self.obj = ObjectImage()
        self.section = "text"
        self.text = self.obj.text
        self.fixups: list[_Fixup] = []
        # numeric local labels: number -> list of text offsets (sorted)
        self.numeric_defs: dict[int, list[int]] = {}
        self.numeric_fixups: list[tuple] = []  # (offset, number, direction, next_ip)
        self.globls: set[str] = set()

    # -- section buffer helpers --
    def buf(self) -> bytearray:
        if self.section == "text":
            return self.obj.text
        if self.section == "rdata":
            return self.obj.rdata
        raise AssemblerError(f"cannot emit bytes into section {self.section}")

    def run(self) -> ObjectImage:
        for raw in self.lines:
            self._line(raw)
        self._resolve_local_fixups()
        self.obj.globals = self.globls
        return self.obj

    # -- line dispatch --
    def _line(self, raw: str):
        line = raw.split("#", 1)[0].strip() if not raw.strip().startswith("#") else ""
        # keep '#' inside strings: .asciz handled before comment strip
        s = raw.strip()
        if s.startswith(".asciz"):
            self._asciz(s)
            return
        if not line:
            return
        # Labels (including local .L… labels) end with ':' and must be checked
        # before the directive branch, since .L labels also start with '.'.
        if line.endswith(":"):
            self._label(line[:-1].strip())
            return
        if line.startswith("."):
            self._directive(line)
            return
        self._instruction(line)

    def _directive(self, line: str):
        parts = line.split(None, 1)
        d = parts[0]
        arg = parts[1].strip() if len(parts) > 1 else ""
        if d == ".intel_syntax":
            return
        if d == ".section":
            name = arg.lstrip(".")
            if name.startswith("text"):
                self.section = "text"
            elif name.startswith("rdata") or name.startswith("rodata") or name.startswith("data"):
                self.section = "rdata"
            elif name.startswith("bss"):
                self.section = "bss"
            else:
                raise AssemblerError(f"unknown section {arg}")
            return
        if d in (".text",):
            self.section = "text"; return
        if d in (".data", ".rodata"):
            self.section = "rdata"; return
        if d == ".bss":
            self.section = "bss"; return
        if d == ".globl":
            self.globls.add(arg)
            return
        if d == ".space":
            n = int(arg, 0)
            if self.section == "bss":
                self.obj.bss_size += n
            else:
                self.buf().extend(b"\x00" * n)
            return
        if d == ".quad":
            self.buf().extend(struct.pack("<Q", int(arg, 0) & 0xFFFFFFFFFFFFFFFF))
            return
        if d == ".long":
            self.buf().extend(struct.pack("<I", int(arg, 0) & 0xFFFFFFFF))
            return
        if d == ".byte":
            self.buf().extend(struct.pack("<B", int(arg, 0) & 0xFF))
            return
        if d in (".align", ".p2align"):
            return
        raise AssemblerError(f"unsupported directive: {line}")

    def _asciz(self, s: str):
        m = re.match(r'^\.asciz\s+"(.*)"\s*$', s)
        if not m:
            raise AssemblerError(f"bad .asciz: {s}")
        self.buf().extend(_decode_gas_string(m.group(1)))
        self.buf().append(0)

    def _label(self, name: str):
        off = len(self._cur_section_buf_for_label())
        if name.isdigit():
            self.numeric_defs.setdefault(int(name), []).append(off)
            return
        self.obj.symbols[name] = (self.section, off)

    def _cur_section_buf_for_label(self):
        if self.section == "bss":
            # bss labels map to current bss size
            class _S:
                def __init__(self, n): self.n = n
                def __len__(self): return self.n
            return _S(self.obj.bss_size)
        return self.buf()

    # -- instruction encoding --
    def _instruction(self, line: str):
        parts = line.split(None, 1)
        mnem = parts[0]
        ops = [o.strip() for o in parts[1].split(",")] if len(parts) > 1 else []
        operands = [_parse_operand(o) for o in ops]
        start = len(self.text)
        try:
            self._encode(mnem, operands)
        except AssemblerError:
            raise
        except Exception as e:  # noqa: BLE001
            raise AssemblerError(f"failed to encode '{line}': {e}") from e
        if len(self.text) == start and mnem not in ("nop",):
            raise AssemblerError(f"no bytes emitted for '{line}'")

    def _emit(self, *bytes_):
        for b in bytes_:
            if isinstance(b, (bytes, bytearray)):
                self.text.extend(b)
            else:
                self.text.append(b & 0xFF)

    def _encode(self, mnem: str, ops: list):
        # --- no-operand ---
        if mnem == "ret":
            self._emit(0xC3); return
        if mnem == "int3":
            self._emit(0xCC); return
        if mnem == "cqo":
            self._emit(0x48, 0x99); return
        if mnem == "nop":
            self._emit(0x90); return

        # --- control flow ---
        if mnem == "jmp" or mnem in _JCC:
            self._branch(mnem, ops[0]); return
        if mnem == "call":
            self._call(ops[0]); return

        # --- push/pop ---
        if mnem in ("push", "pop"):
            r = ops[0]
            assert isinstance(r, Reg) and r.size == 64
            rex = _rex(0, 0, 0, r.num)
            if rex is not None:
                self._emit(rex)
            self._emit((0x50 if mnem == "push" else 0x58) + (r.num & 7))
            return

        # --- unary r/m ---
        if mnem in ("neg", "not", "inc", "dec", "idiv", "div", "mul", "imul") and len(ops) == 1:
            self._unary(mnem, ops[0]); return

        # --- setcc ---
        if mnem in _SETCC:
            r = ops[0]
            assert isinstance(r, Reg) and r.size == 8
            rex = _rex(0, 0, 0, r.num, force=r.num in (4, 5, 6, 7))
            if rex is not None:
                self._emit(rex)
            self._emit(0x0F, _SETCC[mnem], _modrm(3, 0, r.num))
            return

        # --- lea ---
        if mnem == "lea":
            dst, mem = ops
            assert isinstance(dst, Reg) and isinstance(mem, Mem)
            self._emit_rm(0x8D, dst, mem, opsize=64)
            return

        # --- mov family ---
        if mnem == "mov":
            self._mov(ops); return
        if mnem in ("movzx", "movsx"):
            self._movx(mnem, ops); return
        if mnem == "movsxd":
            dst, src = ops
            assert isinstance(dst, Reg)
            self._emit_rm(0x63, dst, src, opsize=64)
            return

        # --- ALU reg,reg / reg,imm ---
        if mnem in _ALU:
            self._alu(mnem, ops); return
        if mnem == "test":
            a, b = ops
            assert isinstance(a, Reg) and isinstance(b, Reg)
            self._emit_rr(0x85, b, a, a.size)  # 85 /r : r/m, r  (test a,b)
            return
        if mnem == "imul" and len(ops) >= 2:
            self._imul(ops); return

        # --- SSE ---
        if mnem in _SSE:
            self._sse(mnem, ops); return
        if mnem in ("movd", "movq"):
            self._movd_q(mnem, ops); return

        raise AssemblerError(f"unsupported mnemonic: {mnem}")

    # -- branch / call --
    def _branch(self, mnem: str, target):
        assert isinstance(target, Sym)
        if mnem == "jmp":
            self._emit(0xE9)
        else:
            self._emit(0x0F, _JCC[mnem])
        self._emit_code_rel32(target.name)

    def _call(self, target):
        assert isinstance(target, Sym)
        name = target.name
        if name.isdigit():
            raise AssemblerError("numeric call target unsupported")
        # Imports (kernel32) are not defined in this object; emit an indirect
        # call through the IAT slot: FF 15 disp32 (RIP-relative).
        if not (name.startswith("fsf_") or name.startswith("fs_rt_")
                or name == "firescript_entry"):
            self.obj.import_symbols.add(name)
            self._emit(0xFF, _modrm(0, 2, 5))  # /2, rm=101 RIP
            off = len(self.text)
            self._emit(b"\x00\x00\x00\x00")
            self.obj.relocs.append(Reloc("text", off, RIP32_IMPORT, name, off + 4))
            return
        self._emit(0xE8)
        self._emit_code_rel32(name)

    def _emit_code_rel32(self, name: str):
        off = len(self.text)
        self._emit(b"\x00\x00\x00\x00")
        next_ip = len(self.text)
        if re.match(r"^\d+[bf]$", name):
            num = int(name[:-1]); direction = name[-1]
            self.numeric_fixups.append((off, num, direction, next_ip))
        else:
            self.fixups.append(_Fixup(off, "rel32", name, next_ip))

    # -- unary r/m --
    def _unary(self, mnem: str, op):
        assert isinstance(op, Reg)
        digit = {"not": 2, "neg": 3, "mul": 4, "imul": 5, "div": 6, "idiv": 7}.get(mnem)
        if mnem in ("inc", "dec"):
            opcode = 0xFE if op.size == 8 else 0xFF
            self._emit_unary_rm(opcode, 0 if mnem == "inc" else 1, op)
            return
        opcode = 0xF6 if op.size == 8 else 0xF7
        self._emit_unary_rm(opcode, digit, op)

    def _emit_unary_rm(self, opcode: int, digit: int, op: Reg):
        w = 1 if op.size == 64 else 0
        rex = _rex(w, 0, 0, op.num)
        if op.size == 16:
            self._emit(0x66)
        if rex is not None:
            self._emit(rex)
        self._emit(opcode, _modrm(3, digit, op.num))

    # -- mov --
    def _mov(self, ops):
        dst, src = ops
        if isinstance(dst, Reg) and isinstance(src, Reg):
            self._emit_rr(0x89, src, dst, dst.size)  # 89 /r : r/m,r
            return
        if isinstance(dst, Reg) and isinstance(src, Imm):
            self._mov_ri(dst, src.value); return
        if isinstance(dst, Reg) and isinstance(src, Mem):
            opcode = 0x8A if dst.size == 8 else 0x8B
            self._emit_rm(opcode, dst, src, opsize=dst.size); return
        if isinstance(dst, Mem) and isinstance(src, Reg):
            opcode = 0x88 if src.size == 8 else 0x89
            self._emit_rm(opcode, src, dst, opsize=src.size); return
        if isinstance(dst, Mem) and isinstance(src, Imm):
            self._mov_mi(dst, src.value); return
        raise AssemblerError(f"unsupported mov forms: {dst}, {src}")

    def _mov_ri(self, dst: Reg, value: int):
        if dst.size == 64 and -(2**31) <= value < 2**31:
            # C7 /0 id  (sign-extended imm32)
            rex = _rex(1, 0, 0, dst.num)
            self._emit(rex, 0xC7, _modrm(3, 0, dst.num))
            self._emit(struct.pack("<i", value))
            return
        if dst.size == 64:
            rex = _rex(1, 0, 0, dst.num)
            self._emit(rex, 0xB8 + (dst.num & 7))
            self._emit(struct.pack("<Q", value & 0xFFFFFFFFFFFFFFFF))
            return
        if dst.size == 32:
            rex = _rex(0, 0, 0, dst.num)
            if rex is not None:
                self._emit(rex)
            self._emit(0xB8 + (dst.num & 7))
            self._emit(struct.pack("<I", value & 0xFFFFFFFF))
            return
        raise AssemblerError(f"unsupported mov imm size {dst.size}")

    def _mov_mi(self, dst: Mem, value: int):
        size = dst.size or 64
        w = 1 if size == 64 else 0
        if size == 16:
            self._emit(0x66)
        opcode = 0xC6 if size == 8 else 0xC7
        self._emit_rm_mem(opcode, 0, dst, w)
        if size == 8:
            self._emit(struct.pack("<b", value) if value < 128 else struct.pack("<B", value & 0xFF))
        elif size == 16:
            self._emit(struct.pack("<h", value))
        else:
            self._emit(struct.pack("<i", value))

    # -- movzx/movsx --
    def _movx(self, mnem: str, ops):
        dst, src = ops
        assert isinstance(dst, Reg)
        src_size = src.size if isinstance(src, Reg) else (src.size or 8)
        op2 = (0xB6 if src_size == 8 else 0xB7) if mnem == "movzx" else (0xBE if src_size == 8 else 0xBF)
        w = 1 if dst.size == 64 else 0
        if isinstance(src, Reg):
            rex = _rex(w, dst.num, 0, src.num, force=(src_size == 8 and src.num in (4, 5, 6, 7)))
            if rex is not None:
                self._emit(rex)
            self._emit(0x0F, op2, _modrm(3, dst.num, src.num))
        else:
            self._emit_rm_twobyte(op2, dst, src, w)

    # -- ALU --
    def _alu(self, mnem: str, ops):
        opcode_rr, digit = _ALU[mnem]
        dst, src = ops
        if isinstance(dst, Reg) and isinstance(src, Reg):
            self._emit_rr(opcode_rr, src, dst, dst.size)
            return
        if isinstance(dst, Reg) and isinstance(src, Imm):
            self._alu_ri(mnem, digit, dst, src.value)
            return
        raise AssemblerError(f"unsupported {mnem} forms")

    def _alu_ri(self, mnem: str, digit: int, dst: Reg, value: int):
        w = 1 if dst.size == 64 else 0
        rex = _rex(w, 0, 0, dst.num)
        if dst.size == 16:
            self._emit(0x66)
        if -128 <= value <= 127:
            if rex is not None:
                self._emit(rex)
            self._emit(0x83, _modrm(3, digit, dst.num), struct.pack("<b", value))
        elif dst.num == 0 and dst.size in (32, 64):
            # Accumulator short form: <op> eAX/rAX, imm32 (no ModRM).
            if rex is not None:
                self._emit(rex)
            self._emit(_ALU_ACC[mnem], struct.pack("<i", value))
        else:
            if rex is not None:
                self._emit(rex)
            self._emit(0x81, _modrm(3, digit, dst.num), struct.pack("<i", value))

    def _imul(self, ops):
        if len(ops) == 2:
            dst, src = ops
            assert isinstance(dst, Reg) and isinstance(src, Reg)
            w = 1 if dst.size == 64 else 0
            rex = _rex(w, dst.num, 0, src.num)
            if rex is not None:
                self._emit(rex)
            self._emit(0x0F, 0xAF, _modrm(3, dst.num, src.num))
            return
        dst, src, imm = ops
        assert isinstance(dst, Reg) and isinstance(src, Reg) and isinstance(imm, Imm)
        w = 1 if dst.size == 64 else 0
        rex = _rex(w, dst.num, 0, src.num)
        if -128 <= imm.value <= 127:
            if rex is not None:
                self._emit(rex)
            self._emit(0x6B, _modrm(3, dst.num, src.num), struct.pack("<b", imm.value))
        else:
            if rex is not None:
                self._emit(rex)
            self._emit(0x69, _modrm(3, dst.num, src.num), struct.pack("<i", imm.value))

    # -- SSE --
    def _sse(self, mnem: str, ops):
        prefix, op2 = _SSE[mnem]
        dst, src = ops
        # movss/movsd have a store form (mem,reg) using opcode+1.
        if mnem in ("movss", "movsd") and isinstance(dst, Mem):
            self._sse_emit(prefix, op2 + 1, src, dst); return
        self._sse_emit(prefix, op2, dst, src)

    def _sse_emit(self, prefix: str, op2: int, reg_operand, rm_operand):
        pb = _PREFIX_BYTE[prefix]
        if pb is not None:
            self._emit(pb)
        reg = reg_operand
        assert isinstance(reg, Reg)
        if isinstance(rm_operand, Reg):
            w = 1 if (reg.size == 64 or rm_operand.size == 64) and not reg.is_xmm else 0
            # cvtsi2sd/ss with 64-bit GPR source needs REX.W.
            if reg.is_xmm and not rm_operand.is_xmm and rm_operand.size == 64:
                w = 1
            if (not reg.is_xmm) and rm_operand.is_xmm and reg.size == 64:
                w = 1
            rex = _rex(w, reg.num, 0, rm_operand.num)
            if rex is not None:
                self._emit(rex)
            self._emit(0x0F, op2, _modrm(3, reg.num, rm_operand.num))
        else:
            self._emit_rm_twobyte(op2, reg, rm_operand, w=0)

    def _movd_q(self, mnem: str, ops):
        dst, src = ops
        w = 1 if mnem == "movq" else 0
        # forms: xmm <- gpr (66 0F 6E), gpr <- xmm (66 0F 7E), xmm<-xmm (F3 0F 7E for movq)
        if isinstance(dst, Reg) and isinstance(src, Reg) and dst.is_xmm and src.is_xmm:
            # movq xmm,xmm : F3 0F 7E
            self._emit(0xF3)
            rex = _rex(0, dst.num, 0, src.num)
            if rex is not None:
                self._emit(rex)
            self._emit(0x0F, 0x7E, _modrm(3, dst.num, src.num))
            return
        if isinstance(dst, Reg) and dst.is_xmm:
            gpr = src
            self._emit(0x66)
            rex = _rex(w, dst.num, 0, gpr.num)
            if rex is not None:
                self._emit(rex)
            self._emit(0x0F, 0x6E, _modrm(3, dst.num, gpr.num))
            return
        if isinstance(dst, Mem):
            # movq qword [mem], xmm  -> 66 0F D6
            self._emit(0x66)
            self._emit_rm_twobyte(0xD6, src, dst, w=0)
            return
        # gpr <- xmm
        gpr = dst; xmm = src
        self._emit(0x66)
        rex = _rex(w, xmm.num, 0, gpr.num)
        if rex is not None:
            self._emit(rex)
        self._emit(0x0F, 0x7E, _modrm(3, xmm.num, gpr.num))

    # -- shared r/m emitters --
    def _emit_rr(self, opcode: int, reg: Reg, rm: Reg, size: int):
        w = 1 if size == 64 else 0
        if size == 16:
            self._emit(0x66)
        force = size == 8 and (reg.num in (4, 5, 6, 7) or rm.num in (4, 5, 6, 7))
        rex = _rex(w, reg.num, 0, rm.num, force=force)
        if rex is not None:
            self._emit(rex)
        self._emit(opcode, _modrm(3, reg.num, rm.num))

    def _emit_rm(self, opcode: int, reg: Reg, mem, opsize: int):
        """opcode /r with reg and a memory (or reg) operand; single-byte opcode."""
        if isinstance(mem, Reg):
            self._emit_rr(opcode, reg, mem, opsize)
            return
        w = 1 if opsize == 64 else 0
        if opsize == 16:
            self._emit(0x66)
        self._emit_rm_mem(opcode, reg.num, mem, w)

    def _emit_rm_twobyte(self, op2: int, reg: Reg, mem: Mem, w: int):
        # 0F op2 with memory operand
        base = mem.base if mem.base is not None else 0
        index = mem.index if mem.index is not None else 0
        rex = _rex(w, reg.num, index, base, force=False)
        if rex is not None:
            self._emit(rex)
        self._emit(0x0F, op2)
        self._emit_modrm_mem(reg.num, mem)

    def _emit_rm_mem(self, opcode: int, reg_field: int, mem: Mem, w: int):
        base = mem.base if mem.base is not None else 0
        index = mem.index if mem.index is not None else 0
        rex = _rex(w, reg_field, index, base)
        if rex is not None:
            self._emit(rex)
        self._emit(opcode)
        self._emit_modrm_mem(reg_field, mem)

    def _emit_modrm_mem(self, reg_field: int, mem: Mem):
        _, _, _, bytes_, rip = _mem_encode(reg_field, mem)
        site = len(self.text)
        self.text.extend(bytes_)
        if rip is not None:
            _, label, disp_off = rip
            field_off = site + disp_off
            next_ip = len(self.text)
            if label in self.obj.symbols and self.obj.symbols[label][0] == "text":
                self.fixups.append(_Fixup(field_off, "rel32", label, next_ip))
            else:
                kind = RIP32
                self.obj.relocs.append(Reloc("text", field_off, kind, label, next_ip))

    # -- fixups --
    def _resolve_local_fixups(self):
        # numeric local labels
        for off, num, direction, next_ip in self.numeric_fixups:
            defs = self.numeric_defs.get(num, [])
            target = None
            if direction == "b":
                cands = [d for d in defs if d <= off]
                target = max(cands) if cands else None
            else:
                cands = [d for d in defs if d >= next_ip - 4]
                target = min(cands) if cands else None
            if target is None:
                raise AssemblerError(f"unresolved numeric label {num}{direction}")
            rel = target - next_ip
            struct.pack_into("<i", self.text, off, rel)
        # named code labels
        deferred = []
        for fx in self.fixups:
            if fx.kind != "rel32":
                deferred.append(fx); continue
            if fx.target not in self.obj.symbols:
                # data symbol referenced via rip but in another section that
                # ended up undefined: treat as import only if truly unknown.
                deferred.append(fx); continue
            sect, off = self.obj.symbols[fx.target]
            if sect == "text":
                rel = off - fx.next_ip
                struct.pack_into("<i", self.text, fx.offset, rel)
            else:
                # rip-relative to rdata/bss -> defer to PE writer
                self.obj.relocs.append(Reloc("text", fx.offset, RIP32, fx.target, fx.next_ip))
        for fx in deferred:
            if fx.target in self.obj.symbols:
                sect, off = self.obj.symbols[fx.target]
                self.obj.relocs.append(Reloc("text", fx.offset, RIP32, fx.target, fx.next_ip))
            else:
                raise AssemblerError(f"unresolved symbol: {fx.target}")


import locale as _locale

# The backend reads source files and writes the .s with the locale codec, so
# `as` would assemble the original source bytes. The assembler consumes the
# in-memory .s text, so it must encode literal characters with the same codec
# to reproduce those exact bytes.
_LOCALE_ENCODING = _locale.getpreferredencoding(False) or "utf-8"


def _decode_gas_string(s: str) -> bytes:
    """Decode a GAS .asciz string body (backslash escapes) to raw bytes."""
    out = bytearray()
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]
            # Octal escapes take precedence: \012 is one byte (0x0A), not
            # \0 (NUL) followed by "12". GAS reads 1-3 octal digits.
            if n in "01234567":
                m = re.match(r"[0-7]{1,3}", s[i + 1:])
                val = int(m.group(0), 8); out.append(val & 0xFF); i += 1 + len(m.group(0)); continue
            simple = {"n": 10, "t": 9, "r": 13, "\\": 92, '"': 34, "'": 39}
            if n in simple:
                out.append(simple[n]); i += 2; continue
            out.append(ord(n)); i += 2; continue
        try:
            out += c.encode(_LOCALE_ENCODING)
        except UnicodeEncodeError:
            out += c.encode("utf-8")
        i += 1
    return bytes(out)
