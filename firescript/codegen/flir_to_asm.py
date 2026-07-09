"""FLIR -> x86-64 assembly backend (Windows x86_64, GAS Intel syntax).

Strategy: simplest correct code. Every FLIR value and slot lives in a
stack slot; each instruction loads its operands into volatile scratch
registers (rax/rcx/rdx + xmm0/xmm1), computes, and stores the result.
No register allocator.

ABI:
- External (kernel32) calls follow the Win64 convention: rcx/rdx/r8/r9
  + xmm0..3, 32-byte shadow space, rsp 16-byte aligned at the call.
  Only scalar/pointer args are ever passed to externs.
- Internal calls use a private convention identical to Win64 for
  scalars, except by-value structs are always passed by pointer (the
  caller copies to a temp and passes its address) and struct returns
  use a hidden leading result-pointer parameter. Stack args beyond 4
  are pushed in the same layout Win64 uses (rsp+0x20, 0x28, ...).
- Frames are rbp-based, 16-byte aligned; frames >= 4 KiB emit page
  probes (no CRT __chkstk).

The calling-convention pieces are kept in Win64Convention so a SysV
target can slot in later.
"""

from __future__ import annotations

import struct as _struct
from typing import Optional

from flir.ir import (
    BinOp,
    Br,
    Call,
    ConstBool,
    ConstF128,
    ConstFloat,
    ConstInt,
    ConstNull,
    ConstStr,
    Cvt,
    F128_STRUCT_NAME,
    FLIRFunction,
    FLIRModule,
    FLIRType,
    FValue,
    GlobalLoad,
    GlobalStore,
    Jmp,
    Load,
    Neg,
    Not,
    PtrAdd,
    Ret,
    SlotAddr,
    SlotDecl,
    SlotLoad,
    SlotStore,
    Store,
    Unreachable,
    align_up,
)

_INT_KINDS = {"i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64", "bool", "ptr"}

_SIZES = {"i8": 1, "i16": 2, "i32": 4, "i64": 8, "u8": 1, "u16": 2, "u32": 4, "u64": 8,
          "bool": 1, "ptr": 8, "f32": 4, "f64": 8}

_WORD = {1: "byte ptr", 2: "word ptr", 4: "dword ptr", 8: "qword ptr"}
_RAX = {1: "al", 2: "ax", 4: "eax", 8: "rax"}
_RCX = {1: "cl", 2: "cx", 4: "ecx", 8: "rcx"}
_RDX = {1: "dl", 2: "dx", 4: "edx", 8: "rdx"}


class AsmError(Exception):
    pass


class Win64Convention:
    """Win64 calling convention facts (isolated for future SysV support)."""

    int_arg_regs = ["rcx", "rdx", "r8", "r9"]
    int_arg_regs_32 = ["ecx", "edx", "r8d", "r9d"]
    float_arg_regs = ["xmm0", "xmm1", "xmm2", "xmm3"]
    shadow_space = 32


class FLIRToAsmBackend:
    def __init__(self, module: FLIRModule):
        self.module = module
        self.out: list[str] = []
        self.rodata: list[str] = []
        self.str_labels: dict[str, str] = {}
        self.f128_labels: dict[tuple[int, int], str] = {}  # (lo, hi) -> label
        self.label_counter = 0
        self.cc = Win64Convention()

    def _f128_label(self, lo_bits: int, hi_bits: int) -> str:
        """Emit a 16-byte float128 constant to .rdata and return its label."""
        key = (lo_bits, hi_bits)
        if key in self.f128_labels:
            return self.f128_labels[key]
        label = f".Lf128_{len(self.f128_labels)}"
        self.f128_labels[key] = label
        # Align to 16 bytes (assembler ignores .align but it's correct for as).
        self.rodata.append(f"    .align 16")
        self.rodata.append(f"{label}:")
        # Little-endian layout: lo qword first (bytes 0..7), hi qword second (bytes 8..15).
        self.rodata.append(f"    .quad {lo_bits}")
        self.rodata.append(f"    .quad {hi_bits}")
        return label

    # ------------------------------------------------------------------

    def generate(self) -> str:
        self.out = [
            ".intel_syntax noprefix",
            '.section .text',
        ]
        self.rodata = [".section .rdata"]

        self._emit_globals()
        self._emit_primitives()
        for func in self.module.functions:
            self._emit_function(func)
        if self.module.entry_function:
            self._emit_entry()

        self._emit_mutable_globals()
        return "\n".join(self.out + [""] + self.rodata) + "\n"

    # -- data ------------------------------------------------------------

    def _struct_size(self, t: FLIRType) -> int:
        return t.size(self.module)

    def _value_size(self, t: FLIRType) -> int:
        if t.kind == "struct":
            return align_up(self._struct_size(t), 8)
        return 8  # scalars occupy a full slot for simplicity

    def _str_label(self, text: str) -> str:
        if text in self.str_labels:
            return self.str_labels[text]
        label = f".Lstr{len(self.str_labels)}"
        self.str_labels[text] = label
        self.rodata.append(f"{label}:")
        self.rodata.append(f'    .asciz "{self._escape_asciz(text)}"')
        return label

    @staticmethod
    def _escape_asciz(text: str) -> str:
        """Escape FIR string-literal text (which keeps source escape
        sequences verbatim) for a GAS .asciz directive."""
        out: list[str] = []
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == "\\" and i + 1 < len(text):
                nxt = text[i + 1]
                if nxt in ("n", "t", "r", "0"):
                    out.append("\\" + nxt)
                elif nxt == "\\":
                    out.append("\\\\")
                elif nxt == '"':
                    out.append('\\"')
                elif nxt == "'":
                    out.append("'")
                else:
                    # Unknown escape: keep the backslash literally.
                    out.append("\\\\")
                    i += 1
                    continue
                i += 2
                continue
            if ch == '"':
                out.append('\\"')
            elif ch == "\\":
                out.append("\\\\")
            elif ord(ch) < 32:
                out.append("\\%03o" % ord(ch))
            else:
                # Non-ASCII passes through unchanged: the front-end reads
                # source with the locale encoding and the .s file is written
                # with the same encoding, so the original bytes round-trip
                # (mirrors the legacy C backend's behavior).
                out.append(ch)
            i += 1
        return "".join(out)

    def _emit_globals(self) -> None:
        for name, gtype, literal in self.module.globals:
            label = f"fsg_{name}"
            self.rodata.append(f"{label}:")
            # float128 global constant: emit two quads from the parsed literal.
            if gtype.kind == "struct" and gtype.struct_name == F128_STRUCT_NAME:
                from flir.lowering import _decimal_to_f128_bits
                lo, hi = _decimal_to_f128_bits(literal)
                self.rodata.append(f"    .align 16")
                self.rodata.append(f"    .quad {lo}")
                self.rodata.append(f"    .quad {hi}")
                continue
            # Globals are loaded as full qwords; store f32 bits in the low half.
            if gtype.kind == "f32":
                bits32 = _struct.unpack("<I", _struct.pack("<f", float(literal)))[0]
                self.rodata.append(f"    .quad {bits32}")
            elif gtype.is_float() or "." in literal or "e" in literal or "E" in literal:
                bits = _struct.unpack("<Q", _struct.pack("<d", float(literal)))[0]
                self.rodata.append(f"    .quad {bits}")
            else:
                self.rodata.append(f"    .quad {int(literal) & 0xFFFFFFFFFFFFFFFF}")

    def _emit_mutable_globals(self) -> None:
        if not self.module.mutable_globals:
            return
        self.rodata.append(".section .bss")
        for name, gtype in self.module.mutable_globals:
            self.rodata.append(f"fsg_mut_{name}:")
            self.rodata.append(f"    .space {max(8, _SIZES.get(gtype.kind, 8))}")

    # -- primitives ----------------------------------------------------------

    def _emit_primitives(self) -> None:
        # fs_rt_mem_copy(dst rcx, src rdx, n r8) -- forward/backward safe
        self.out.extend([
            ".globl fs_rt_mem_copy",
            "fs_rt_mem_copy:",
            "    cmp rcx, rdx",
            "    jb 1f",
            "    # copy backward",
            "    test r8, r8",
            "    jz 3f",
            "2:",
            "    mov al, byte ptr [rdx + r8 - 1]",
            "    mov byte ptr [rcx + r8 - 1], al",
            "    dec r8",
            "    jnz 2b",
            "    jmp 3f",
            "1:",
            "    xor r9, r9",
            "4:",
            "    cmp r9, r8",
            "    jae 3f",
            "    mov al, byte ptr [rdx + r9]",
            "    mov byte ptr [rcx + r9], al",
            "    inc r9",
            "    jmp 4b",
            "3:",
            "    ret",
            "",
            ".globl fs_rt_f64_bits",
            "fs_rt_f64_bits:",
            "    movq rax, xmm0",
            "    ret",
            "",
        ])

    def _emit_entry(self) -> None:
        self.out.extend([
            ".globl firescript_entry",
            "firescript_entry:",
            "    and rsp, -16",
            "    sub rsp, 32",
            f"    call {self._sym(self.module.entry_function)}",
            "    xor ecx, ecx",
            "    call ExitProcess",
            "    int3",
            "",
        ])

    # -- functions ---------------------------------------------------------

    @staticmethod
    def _sym(name: str) -> str:
        return f"fsf_{name}"

    def _emit_function(self, func: FLIRFunction) -> None:
        # Frame layout: slots for params, locals, and every value.
        offsets: dict[str, int] = {}
        value_offsets: dict[int, int] = {}
        frame = 0

        struct_ret = func.return_type.kind == "struct"
        # Hidden return-pointer slot.
        if struct_ret:
            frame += 8
            offsets["__retptr"] = -frame

        for pname, ptype in func.params:
            size = self._value_size(ptype)
            frame = align_up(frame + size, 8)
            offsets[pname] = -frame

        max_call_args = 0
        for block in func.blocks:
            for inst in block.instructions:
                if isinstance(inst, SlotDecl) and inst.name not in offsets:
                    size = self._value_size(inst.slot_type)
                    frame = align_up(frame + size, 8)
                    offsets[inst.name] = -frame
                if inst.has_result():
                    size = self._value_size(inst.result_type)
                    frame = align_up(frame + size, 8)
                    value_offsets[id(inst)] = -frame
                if isinstance(inst, Call):
                    n_args = len(inst.operands)
                    if inst.result_type.kind == "struct":
                        n_args += 1
                    # struct args need a copy temp
                    for op in inst.operands:
                        if op.value_type is not None and op.value_type.kind == "struct":
                            size = self._value_size(op.value_type)
                            frame = align_up(frame + size, 8)
                    max_call_args = max(max_call_args, n_args)

        # struct-arg copy temps are assigned at emission time from a bump
        # region; reserve it by tracking the high-water mark above.
        out_arg_space = self.cc.shadow_space + max(0, max_call_args - 4) * 8
        out_arg_space = align_up(out_arg_space, 16)
        frame_size = align_up(frame, 16) + out_arg_space
        # keep rsp 16-aligned: after push rbp, rsp % 16 == 0; frame_size
        # must stay a multiple of 16.
        frame_size = align_up(frame_size, 16)

        self.out.append(f".globl {self._sym(func.name)}")
        self.out.append(f"{self._sym(func.name)}:")
        self.out.append("    push rbp")
        self.out.append("    mov rbp, rsp")
        if frame_size >= 4096:
            # Page-touch probe loop (no CRT __chkstk): commit whole pages
            # one at a time, then the remainder.
            pages = frame_size // 4096
            remainder = frame_size % 4096
            self.out.append(f"    mov r11, {pages}")
            self.out.append("9:")
            self.out.append("    sub rsp, 4096")
            self.out.append("    mov qword ptr [rsp], 0")
            self.out.append("    dec r11")
            self.out.append("    jnz 9b")
            if remainder:
                self.out.append(f"    sub rsp, {remainder}")
        else:
            self.out.append(f"    sub rsp, {frame_size}")

        # Spill incoming parameters to their slots.
        int_regs = self.cc.int_arg_regs
        arg_index = 0
        if struct_ret:
            self.out.append(f"    mov qword ptr [rbp{offsets['__retptr']}], rcx")
            arg_index = 1
        for pname, ptype in func.params:
            off = offsets[pname]
            if ptype.kind == "struct":
                # Passed by pointer (private convention): copy into the slot.
                if arg_index < 4:
                    self.out.append(f"    mov r10, {int_regs[arg_index]}")
                else:
                    self.out.append(f"    mov r10, qword ptr [rbp + {16 + arg_index * 8}]")
                self._emit_copy_to_frame(off, "r10", self._struct_size(ptype))
            elif ptype.is_float():
                if arg_index < 4:
                    self.out.append(
                        f"    movq qword ptr [rbp{off}], {self.cc.float_arg_regs[arg_index]}"
                    )
                else:
                    self.out.append(f"    mov rax, qword ptr [rbp + {16 + arg_index * 8}]")
                    self.out.append(f"    mov qword ptr [rbp{off}], rax")
            else:
                if arg_index < 4:
                    self.out.append(f"    mov qword ptr [rbp{off}], {int_regs[arg_index]}")
                else:
                    self.out.append(f"    mov rax, qword ptr [rbp + {16 + arg_index * 8}]")
                    self.out.append(f"    mov qword ptr [rbp{off}], rax")
            arg_index += 1

        ctx = _EmitCtx(func, offsets, value_offsets, struct_ret)
        for block in func.blocks:
            self.out.append(f".L{func.name}_{block.id}:")
            for inst in block.instructions:
                self._emit_inst(inst, ctx)

        self.out.append("")

    def _emit_copy_to_frame(self, dst_off: int, src_reg: str, size: int) -> None:
        """Byte-copy size bytes from [src_reg] to [rbp+dst_off] via rax."""
        for i in range(0, size - size % 8, 8):
            self.out.append(f"    mov rax, qword ptr [{src_reg} + {i}]")
            self.out.append(f"    mov qword ptr [rbp{dst_off + i:+d}], rax")
        base = size - size % 8
        for i in range(base, size):
            self.out.append(f"    mov al, byte ptr [{src_reg} + {i}]")
            self.out.append(f"    mov byte ptr [rbp{dst_off + i:+d}], al")

    def _emit_copy_from_frame(self, dst_reg: str, src_off: int, size: int) -> None:
        for i in range(0, size - size % 8, 8):
            self.out.append(f"    mov rax, qword ptr [rbp{src_off + i:+d}]")
            self.out.append(f"    mov qword ptr [{dst_reg} + {i}], rax")
        base = size - size % 8
        for i in range(base, size):
            self.out.append(f"    mov al, byte ptr [rbp{src_off + i:+d}]")
            self.out.append(f"    mov byte ptr [{dst_reg} + {i}], al")

    # -- value access -----------------------------------------------------

    def _val_off(self, value: FValue, ctx: "_EmitCtx") -> int:
        off = ctx.value_offsets.get(id(value.instruction))
        if off is None:
            raise AsmError(f"value of {value.instruction.opcode} has no slot")
        return off

    def _load_int(self, value: FValue, reg_map: dict[int, str], ctx: "_EmitCtx") -> str:
        """Load an integer/pointer value into the given register family."""
        t = value.value_type
        size = _SIZES.get(t.kind, 8)
        off = self._val_off(value, ctx)
        reg64 = reg_map[8]
        if size == 8:
            self.out.append(f"    mov {reg64}, qword ptr [rbp{off:+d}]")
        elif t.kind in ("i8", "i16", "i32"):
            mov = "movsx" if size < 4 else "movsxd"
            if size == 4:
                self.out.append(f"    movsxd {reg64}, dword ptr [rbp{off:+d}]")
            else:
                self.out.append(f"    movsx {reg64}, {_WORD[size]} [rbp{off:+d}]")
        else:
            if size == 4:
                self.out.append(f"    mov {reg_map[4]}, dword ptr [rbp{off:+d}]")
            else:
                self.out.append(f"    movzx {reg_map[4]}, {_WORD[size]} [rbp{off:+d}]")
        return reg64

    def _store_result(self, inst, reg64: str, ctx: "_EmitCtx") -> None:
        off = ctx.value_offsets[id(inst)]
        self.out.append(f"    mov qword ptr [rbp{off:+d}], {reg64}")

    # -- instruction emission ----------------------------------------------

    def _emit_inst(self, inst, ctx: "_EmitCtx") -> None:
        out = self.out
        func = ctx.func

        if isinstance(inst, SlotDecl):
            return

        if isinstance(inst, ConstInt):
            value = int(inst.text, 0)
            # Two's-complement wrap for the target width happens naturally.
            off = ctx.value_offsets[id(inst)]
            if -(2**31) <= value < 2**31:
                out.append(f"    mov qword ptr [rbp{off:+d}], {value}")
            else:
                out.append(f"    mov rax, {value & 0xFFFFFFFFFFFFFFFF}")
                out.append(f"    mov qword ptr [rbp{off:+d}], rax")
            return

        if isinstance(inst, ConstFloat):
            if inst.result_type.kind == "f32":
                bits = _struct.unpack("<I", _struct.pack("<f", float(inst.text)))[0]
            else:
                bits = _struct.unpack("<Q", _struct.pack("<d", float(inst.text)))[0]
            off = ctx.value_offsets[id(inst)]
            out.append(f"    mov rax, {bits}")
            out.append(f"    mov qword ptr [rbp{off:+d}], rax")
            return

        if isinstance(inst, ConstF128):
            # Load 16-byte float128 constant from .rdata into the struct slot.
            label = self._f128_label(inst.lo_bits, inst.hi_bits)
            off = ctx.value_offsets[id(inst)]
            out.append(f"    lea r10, [rip + {label}]")
            out.append(f"    lea r11, [rbp{off:+d}]")
            self._emit_copy_regs(16)
            return

        if isinstance(inst, ConstBool):
            off = ctx.value_offsets[id(inst)]
            out.append(f"    mov qword ptr [rbp{off:+d}], {1 if inst.value else 0}")
            return

        if isinstance(inst, ConstStr):
            label = self._str_label(inst.text)
            off = ctx.value_offsets[id(inst)]
            out.append(f"    lea rax, [rip + {label}]")
            out.append(f"    mov qword ptr [rbp{off:+d}], rax")
            return

        if isinstance(inst, ConstNull):
            off = ctx.value_offsets[id(inst)]
            out.append(f"    mov qword ptr [rbp{off:+d}], 0")
            return

        if isinstance(inst, GlobalLoad):
            off = ctx.value_offsets[id(inst)]
            mutable = any(n == inst.name for n, _ in self.module.mutable_globals)
            label = f"fsg_mut_{inst.name}" if mutable else f"fsg_{inst.name}"
            out.append(f"    mov rax, qword ptr [rip + {label}]")
            out.append(f"    mov qword ptr [rbp{off:+d}], rax")
            return

        if isinstance(inst, GlobalStore):
            self._load_int(inst.operands[0], _RAX, ctx)
            out.append(f"    mov qword ptr [rip + fsg_mut_{inst.name}], rax")
            return

        if isinstance(inst, BinOp):
            self._emit_binop(inst, ctx)
            return

        if isinstance(inst, Not):
            self._load_int(inst.operands[0], _RAX, ctx)
            out.append("    test rax, rax")
            out.append("    sete al")
            out.append("    movzx eax, al")
            self._store_result(inst, "rax", ctx)
            return

        if isinstance(inst, Neg):
            if inst.result_type.is_float():
                self._load_float(inst.operands[0], "xmm0", ctx)
                if inst.result_type.kind == "f32":
                    out.append("    mov eax, 2147483648")
                    out.append("    movd xmm1, eax")
                    out.append("    xorps xmm0, xmm1")
                else:
                    out.append("    mov rax, -9223372036854775808")
                    out.append("    movq xmm1, rax")
                    out.append("    xorpd xmm0, xmm1")
                self._store_float_result(inst, "xmm0", ctx)
            else:
                self._load_int(inst.operands[0], _RAX, ctx)
                out.append("    neg rax")
                self._store_result(inst, "rax", ctx)
            return

        if isinstance(inst, Cvt):
            self._emit_cvt(inst, ctx)
            return

        if isinstance(inst, Load):
            self._emit_load(inst, ctx)
            return

        if isinstance(inst, Store):
            self._emit_store(inst, ctx)
            return

        if isinstance(inst, PtrAdd):
            self._load_int(inst.operands[0], _RAX, ctx)
            self._load_int(inst.operands[1], _RCX, ctx)
            if inst.scale != 1:
                out.append(f"    imul rcx, rcx, {inst.scale}")
            out.append("    add rax, rcx")
            self._store_result(inst, "rax", ctx)
            return

        if isinstance(inst, SlotLoad):
            off = ctx.offsets[inst.name]
            roff = ctx.value_offsets[id(inst)]
            if inst.result_type.kind == "struct":
                size = self._struct_size(inst.result_type)
                out.append(f"    lea r10, [rbp{off:+d}]")
                out.append(f"    lea r11, [rbp{roff:+d}]")
                self._emit_copy_regs(size)
            else:
                out.append(f"    mov rax, qword ptr [rbp{off:+d}]")
                out.append(f"    mov qword ptr [rbp{roff:+d}], rax")
            return

        if isinstance(inst, SlotStore):
            off = ctx.offsets[inst.name]
            value = inst.operands[0]
            if value.value_type is not None and value.value_type.kind == "struct":
                size = self._struct_size(value.value_type)
                voff = self._val_off(value, ctx)
                out.append(f"    lea r10, [rbp{voff:+d}]")
                out.append(f"    lea r11, [rbp{off:+d}]")
                self._emit_copy_regs(size)
            else:
                self._load_int(value, _RAX, ctx) if not value.value_type.is_float() else self._load_float_as_int(value, ctx)
                out.append(f"    mov qword ptr [rbp{off:+d}], rax")
            return

        if isinstance(inst, SlotAddr):
            off = ctx.offsets[inst.name]
            roff = ctx.value_offsets[id(inst)]
            out.append(f"    lea rax, [rbp{off:+d}]")
            out.append(f"    mov qword ptr [rbp{roff:+d}], rax")
            return

        if isinstance(inst, Call):
            self._emit_call(inst, ctx)
            return

        if isinstance(inst, Ret):
            if inst.operands:
                value = inst.operands[0]
                if value.value_type is not None and value.value_type.kind == "struct":
                    # Copy into the hidden return pointer; return that pointer.
                    size = self._struct_size(value.value_type)
                    voff = self._val_off(value, ctx)
                    out.append(f"    mov r11, qword ptr [rbp{ctx.offsets['__retptr']:+d}]")
                    out.append(f"    lea r10, [rbp{voff:+d}]")
                    self._emit_copy_regs(size, dst_reg="r11", src_reg="r10")
                    out.append("    mov rax, r11")
                elif value.value_type is not None and value.value_type.is_float():
                    self._load_float(value, "xmm0", ctx)
                else:
                    self._load_int(value, _RAX, ctx)
            out.append("    mov rsp, rbp")
            out.append("    pop rbp")
            out.append("    ret")
            return

        if isinstance(inst, Br):
            self._load_int(inst.operands[0], _RAX, ctx)
            out.append("    test rax, rax")
            out.append(f"    jnz .L{func.name}_{inst.true_block}")
            out.append(f"    jmp .L{func.name}_{inst.false_block}")
            return

        if isinstance(inst, Jmp):
            out.append(f"    jmp .L{func.name}_{inst.target}")
            return

        if isinstance(inst, Unreachable):
            out.append("    int3")
            return

        raise AsmError(f"asm backend cannot emit {inst.opcode}")

    def _emit_copy_regs(self, size: int, dst_reg: str = "r11", src_reg: str = "r10") -> None:
        for i in range(0, size - size % 8, 8):
            self.out.append(f"    mov rax, qword ptr [{src_reg} + {i}]")
            self.out.append(f"    mov qword ptr [{dst_reg} + {i}], rax")
        base = size - size % 8
        for i in range(base, size):
            self.out.append(f"    mov al, byte ptr [{src_reg} + {i}]")
            self.out.append(f"    mov byte ptr [{dst_reg} + {i}], al")

    # -- floats ------------------------------------------------------------

    def _load_float(self, value: FValue, xmm: str, ctx: "_EmitCtx") -> None:
        off = self._val_off(value, ctx)
        if value.value_type.kind == "f32":
            self.out.append(f"    movss {xmm}, dword ptr [rbp{off:+d}]")
        else:
            self.out.append(f"    movsd {xmm}, qword ptr [rbp{off:+d}]")

    def _load_float_as_int(self, value: FValue, ctx: "_EmitCtx") -> str:
        off = self._val_off(value, ctx)
        self.out.append(f"    mov rax, qword ptr [rbp{off:+d}]")
        return "rax"

    def _store_float_result(self, inst, xmm: str, ctx: "_EmitCtx") -> None:
        off = ctx.value_offsets[id(inst)]
        if inst.result_type.kind == "f32":
            self.out.append(f"    movss dword ptr [rbp{off:+d}], {xmm}")
            self.out.append(f"    mov dword ptr [rbp{off + 4:+d}], 0")
        else:
            self.out.append(f"    movsd qword ptr [rbp{off:+d}], {xmm}")

    # -- binops --------------------------------------------------------------

    _CMP_SET = {"eq": "sete", "ne": "setne", "lt": "setl", "le": "setle", "gt": "setg", "ge": "setge"}
    _CMP_SET_U = {"eq": "sete", "ne": "setne", "lt": "setb", "le": "setbe", "gt": "seta", "ge": "setae"}
    _CMP_SET_F = {"eq": "sete", "ne": "setne", "lt": "setb", "le": "setbe", "gt": "seta", "ge": "setae"}

    def _emit_binop(self, inst: BinOp, ctx: "_EmitCtx") -> None:
        out = self.out
        op = inst.op
        t = inst.operand_type

        if t.is_float():
            self._load_float(inst.operands[0], "xmm0", ctx)
            self._load_float(inst.operands[1], "xmm1", ctx)
            suffix = "ss" if t.kind == "f32" else "sd"
            if op in ("add", "sub", "mul", "div"):
                out.append(f"    {op}{suffix} xmm0, xmm1")
                self._store_float_result(inst, "xmm0", ctx)
                return
            if op in self._CMP_SET_F:
                out.append(f"    comi{suffix} xmm0, xmm1")
                out.append(f"    {self._CMP_SET_F[op]} al")
                out.append("    movzx eax, al")
                self._store_result(inst, "rax", ctx)
                return
            raise AsmError(f"float binop {op}")

        signed = t.kind in ("i8", "i16", "i32", "i64")
        self._load_int(inst.operands[0], _RAX, ctx)
        self._load_int(inst.operands[1], _RCX, ctx)

        if op == "add":
            out.append("    add rax, rcx")
        elif op == "sub":
            out.append("    sub rax, rcx")
        elif op == "mul":
            out.append("    imul rax, rcx")
        elif op in ("div", "mod"):
            if signed:
                out.append("    cqo")
                out.append("    idiv rcx")
            else:
                out.append("    xor edx, edx")
                out.append("    div rcx")
            if op == "mod":
                out.append("    mov rax, rdx")
        elif op in ("and", "or"):
            out.append(f"    {'and' if op == 'and' else 'or'} rax, rcx")
        elif op in self._CMP_SET:
            out.append("    cmp rax, rcx")
            table = self._CMP_SET if signed else self._CMP_SET_U
            out.append(f"    {table[op]} al")
            out.append("    movzx eax, al")
        else:
            raise AsmError(f"int binop {op}")

        # Narrow results wrap to their width (two's complement) so later
        # sign/zero extension from the slot is correct.
        rt = inst.result_type
        if rt.kind in ("i8", "i16", "i32") and op in ("add", "sub", "mul", "div", "mod"):
            out.append("    movsxd rax, eax" if rt.kind == "i32" else
                       f"    movsx rax, {_RAX[_SIZES[rt.kind]]}")
        elif rt.kind in ("u8", "u16", "u32") and op in ("add", "sub", "mul", "div", "mod"):
            if rt.kind == "u32":
                out.append("    mov eax, eax")
            else:
                out.append(f"    movzx eax, {_RAX[_SIZES[rt.kind]]}")
        self._store_result(inst, "rax", ctx)

    # -- conversions ----------------------------------------------------------

    def _emit_cvt(self, inst: Cvt, ctx: "_EmitCtx") -> None:
        out = self.out
        src = inst.from_type
        dst = inst.result_type

        if src.kind in _INT_KINDS and dst.kind in _INT_KINDS:
            self._load_int(inst.operands[0], _RAX, ctx)
            size = _SIZES[dst.kind]
            if dst.kind in ("i8", "i16"):
                out.append(f"    movsx rax, {_RAX[size]}")
            elif dst.kind == "i32":
                out.append("    movsxd rax, eax")
            elif dst.kind in ("u8", "u16"):
                out.append(f"    movzx eax, {_RAX[size]}")
            elif dst.kind == "u32":
                out.append("    mov eax, eax")
            elif dst.kind == "bool":
                out.append("    test rax, rax")
                out.append("    setne al")
                out.append("    movzx eax, al")
            self._store_result(inst, "rax", ctx)
            return

        if src.is_float() and dst.is_float():
            self._load_float(inst.operands[0], "xmm0", ctx)
            if src.kind == "f32" and dst.kind == "f64":
                out.append("    cvtss2sd xmm0, xmm0")
            elif src.kind == "f64" and dst.kind == "f32":
                out.append("    cvtsd2ss xmm0, xmm0")
            self._store_float_result(inst, "xmm0", ctx)
            return

        if src.kind in _INT_KINDS and dst.is_float():
            self._load_int(inst.operands[0], _RAX, ctx)
            suffix = "ss" if dst.kind == "f32" else "sd"
            if src.kind == "u64":
                # Unsigned 64 -> float: handle the high bit.
                label = self.label_counter
                self.label_counter += 1
                out.append("    test rax, rax")
                out.append(f"    js .Lu2f{label}")
                out.append(f"    cvtsi2{suffix} xmm0, rax")
                out.append(f"    jmp .Lu2fd{label}")
                out.append(f".Lu2f{label}:")
                out.append("    mov rcx, rax")
                out.append("    shr rax, 1")
                out.append("    and rcx, 1")
                out.append("    or rax, rcx")
                out.append(f"    cvtsi2{suffix} xmm0, rax")
                out.append(f"    add{suffix} xmm0, xmm0")
                out.append(f".Lu2fd{label}:")
            else:
                out.append(f"    cvtsi2{suffix} xmm0, rax")
            self._store_float_result(inst, "xmm0", ctx)
            return

        if src.is_float() and dst.kind in _INT_KINDS:
            self._load_float(inst.operands[0], "xmm0", ctx)
            suffix = "ss" if src.kind == "f32" else "sd"
            if dst.kind == "u64":
                label = self.label_counter
                self.label_counter += 1
                # Values >= 2^63 need the subtract trick.
                bits = _struct.unpack("<Q", _struct.pack("<d", 9.223372036854776e18))[0]
                out.append(f"    mov rax, {bits}")
                out.append("    movq xmm1, rax")
                if suffix == "ss":
                    out.append("    cvtss2sd xmm0, xmm0")
                out.append("    comisd xmm0, xmm1")
                out.append(f"    jae .Lf2u{label}")
                out.append("    cvttsd2si rax, xmm0")
                out.append(f"    jmp .Lf2ud{label}")
                out.append(f".Lf2u{label}:")
                out.append("    subsd xmm0, xmm1")
                out.append("    cvttsd2si rax, xmm0")
                out.append("    mov rcx, -9223372036854775808")
                out.append("    xor rax, rcx")
                out.append(f".Lf2ud{label}:")
            else:
                out.append(f"    cvtt{suffix}2si rax, xmm0")
                size = _SIZES[dst.kind]
                if dst.kind in ("i8", "i16"):
                    out.append(f"    movsx rax, {_RAX[size]}")
                elif dst.kind == "i32":
                    out.append("    movsxd rax, eax")
                elif dst.kind in ("u8", "u16"):
                    out.append(f"    movzx eax, {_RAX[size]}")
                elif dst.kind == "u32":
                    out.append("    mov eax, eax")
            self._store_result(inst, "rax", ctx)
            return

        # ptr <-> int bitcasts and everything else pointer-sized.
        self._load_int(inst.operands[0], _RAX, ctx)
        self._store_result(inst, "rax", ctx)

    # -- memory ----------------------------------------------------------------

    def _emit_load(self, inst: Load, ctx: "_EmitCtx") -> None:
        out = self.out
        t = inst.result_type
        self._load_int(inst.operands[0], _RCX, ctx)
        roff = ctx.value_offsets[id(inst)]
        if t.kind == "struct":
            size = self._struct_size(t)
            out.append(f"    lea r10, [rcx + {inst.offset}]")
            out.append(f"    lea r11, [rbp{roff:+d}]")
            self._emit_copy_regs(size)
            return
        size = _SIZES[t.kind]
        if t.kind in ("i8", "i16"):
            out.append(f"    movsx rax, {_WORD[size]} [rcx + {inst.offset}]")
        elif t.kind == "i32":
            out.append(f"    movsxd rax, dword ptr [rcx + {inst.offset}]")
        elif size == 8:
            out.append(f"    mov rax, qword ptr [rcx + {inst.offset}]")
        elif size == 4:
            out.append(f"    mov eax, dword ptr [rcx + {inst.offset}]")
        else:
            out.append(f"    movzx eax, {_WORD[size]} [rcx + {inst.offset}]")
        out.append(f"    mov qword ptr [rbp{roff:+d}], rax")

    def _emit_store(self, inst: Store, ctx: "_EmitCtx") -> None:
        out = self.out
        t = inst.value_type
        self._load_int(inst.operands[0], _RCX, ctx)
        value = inst.operands[1]
        if t.kind == "struct":
            size = self._struct_size(t)
            voff = self._val_off(value, ctx)
            out.append(f"    lea r10, [rbp{voff:+d}]")
            out.append(f"    lea r11, [rcx + {inst.offset}]")
            self._emit_copy_regs(size)
            return
        voff = self._val_off(value, ctx)
        out.append(f"    mov rax, qword ptr [rbp{voff:+d}]")
        size = _SIZES[t.kind]
        out.append(f"    mov {_WORD[size]} [rcx + {inst.offset}], {_RAX[size]}")

    # -- calls -------------------------------------------------------------------

    def _emit_call(self, inst: Call, ctx: "_EmitCtx") -> None:
        out = self.out
        is_extern = inst.callee in self.module.externs
        is_primitive = inst.callee in ("fs_rt_mem_copy", "fs_rt_f64_bits")
        callee = inst.callee if (is_extern or is_primitive) else self._sym(inst.callee)

        struct_ret = inst.result_type.kind == "struct"
        args: list[tuple[str, FValue]] = [("val", op) for op in inst.operands]

        # Stage argument values into arg registers / stack.
        # Build the logical arg list: hidden ret ptr first when needed.
        total_args = len(args) + (1 if struct_ret else 0)

        # Stack args (index >= 4) go to [rsp + 0x20 + (i-4)*8].
        # We first compute/copy struct temps, then load registers last so
        # nothing clobbers them.
        slot_index = 0
        staged: list[tuple[int, str]] = []  # (arg index, asm operand source)

        if struct_ret:
            roff = ctx.value_offsets[id(inst)]
            staged.append((0, f"lea:{roff}"))
            slot_index = 1

        for op in inst.operands:
            t = op.value_type
            if t is not None and t.kind == "struct":
                voff = self._val_off(op, ctx)
                staged.append((slot_index, f"lea:{voff}"))
            elif t is not None and t.is_float():
                voff = self._val_off(op, ctx)
                staged.append((slot_index, f"fmem:{voff}"))
            else:
                voff = self._val_off(op, ctx)
                staged.append((slot_index, f"mem:{voff}"))
            slot_index += 1

        int_regs = self.cc.int_arg_regs
        for index, source in staged:
            kind, off_text = source.split(":")
            off = int(off_text)
            if index < 4:
                if kind == "lea":
                    out.append(f"    lea {int_regs[index]}, [rbp{off:+d}]")
                elif kind == "fmem":
                    out.append(f"    movsd {self.cc.float_arg_regs[index]}, qword ptr [rbp{off:+d}]")
                    if is_extern:
                        # Win64 varargs/externs also want the value in the
                        # matching integer register.
                        out.append(f"    mov {int_regs[index]}, qword ptr [rbp{off:+d}]")
                else:
                    out.append(f"    mov {int_regs[index]}, qword ptr [rbp{off:+d}]")
            else:
                if kind == "lea":
                    out.append(f"    lea rax, [rbp{off:+d}]")
                else:
                    out.append(f"    mov rax, qword ptr [rbp{off:+d}]")
                out.append(f"    mov qword ptr [rsp + {32 + (index - 4) * 8}], rax")

        out.append(f"    call {callee}")

        if struct_ret:
            return  # result already written through the hidden pointer
        if inst.has_result():
            if inst.result_type.is_float():
                self._store_float_result(inst, "xmm0", ctx)
            else:
                self._store_result(inst, "rax", ctx)


class _EmitCtx:
    def __init__(self, func: FLIRFunction, offsets, value_offsets, struct_ret: bool):
        self.func = func
        self.offsets = offsets
        self.value_offsets = value_offsets
        self.struct_ret = struct_ret
