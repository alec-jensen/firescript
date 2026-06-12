"""Interim FLIR -> C backend (differential test harness).

This backend exists to prove the FIR/FLIR pipeline semantics against the
legacy AST->C backend before the native assembly backend is written. It
is deliberately thin: FLIR is already explicit, so emission is largely
1:1. It is deleted at the end of the FIR migration.

Naming: generated functions get an `fsf_` prefix, structs `fst_`,
globals `fsg_` to avoid collisions with libc and the legacy runtime.
fs_rt_* runtime calls are mapped onto the legacy C runtime via static
shims emitted into the output.
"""

from __future__ import annotations

from flir.ir import (
    BinOp,
    Br,
    Call,
    ConstBool,
    ConstFloat,
    ConstInt,
    ConstNull,
    ConstStr,
    Cvt,
    FLIRFunction,
    FLIRModule,
    FLIRStruct,
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
)

_C_TYPES = {
    "i8": "int8_t",
    "i16": "int16_t",
    "i32": "int32_t",
    "i64": "int64_t",
    "u8": "uint8_t",
    "u16": "uint16_t",
    "u32": "uint32_t",
    "u64": "uint64_t",
    "f32": "float",
    "f64": "double",
    "bool": "bool",
    "ptr": "void*",
    "void": "void",
}

_BINOPS = {
    "add": "+",
    "sub": "-",
    "mul": "*",
    "div": "/",
    "mod": "%",
    "eq": "==",
    "ne": "!=",
    "lt": "<",
    "le": "<=",
    "gt": ">",
    "ge": ">=",
    "and": "&&",
    "or": "||",
}

# The complete runtime is implemented in firescript
# (std/internal/runtime.fire). Only two true primitives remain at the
# backend level; the asm backend later emits these natively (rep movsb /
# movq). All other fs_rt_* symbols must resolve to firescript
# implementations -- an unresolved one is a porting bug and fails at link.
_RUNTIME_PRIMITIVES = r"""
/* ---- backend primitives (everything else is firescript code) ---- */
static void fs_rt_mem_copy(void* dst, const void* src, uint64_t n) {
    unsigned char* d = (unsigned char*)dst;
    const unsigned char* s = (const unsigned char*)src;
    if (d < s) {
        for (uint64_t i = 0; i < n; i++) d[i] = s[i];
    } else {
        for (uint64_t i = n; i > 0; i--) d[i - 1] = s[i - 1];
    }
}
static uint64_t fs_rt_f64_bits(double v) {
    uint64_t bits;
    unsigned char* src = (unsigned char*)&v;
    unsigned char* dst = (unsigned char*)&bits;
    for (int i = 0; i < 8; i++) dst[i] = src[i];
    return bits;
}
"""


class FLIRToCBackend:
    def __init__(self, module: FLIRModule):
        self.module = module
        self.out: list[str] = []

    # -- types -------------------------------------------------------------

    def c_type(self, t: FLIRType) -> str:
        if t.kind == "struct":
            return f"fst_{t.struct_name}"
        if t.kind == "ptr" and t.pointee and t.pointee not in _C_TYPES:
            return f"fst_{t.pointee}*"
        if t.kind == "ptr" and t.pointee == "i8":
            return "char*"
        return _C_TYPES[t.kind]

    # -- emission ------------------------------------------------------------

    def generate(self) -> str:
        self.out = [
            "#include <stdlib.h>",
            "#include <stdbool.h>",
            "#include <stdint.h>",
            "",
        ]

        # Win32 extern prototypes (resolved by the kernel32 import library).
        for symbol, (dll, ret, params) in sorted(self.module.externs.items()):
            params_text = ", ".join(self.c_type(p) for p in params) or "void"
            self.out.append(f"extern {self.c_type(ret)} __stdcall {symbol}({params_text});")
        if self.module.externs:
            self.out.append("")

        for struct in self.module.structs:
            self._emit_struct(struct)

        self.out.append(_RUNTIME_PRIMITIVES)

        for gname, gtype, literal in self.module.globals:
            self.out.append(f"static const {self.c_type(gtype)} fsg_{gname} = {literal};")
        for gname, gtype in self.module.mutable_globals:
            self.out.append(f"static {self.c_type(gtype)} fsg_mut_{gname} = 0;")
        if self.module.globals or self.module.mutable_globals:
            self.out.append("")

        # Forward declarations (order independence).
        for func in self.module.functions:
            self.out.append(self._signature(func) + ";")
        self.out.append("")

        for func in self.module.functions:
            self._emit_function(func)

        if self.module.entry_function:
            # Process args come from GetCommandLineA inside the firescript
            # runtime; the host entry only calls the program.
            self.out.append("int main(void) {")
            self.out.append(f"    fsf_{self.module.entry_function}();")
            self.out.append("    return 0;")
            self.out.append("}")

        return "\n".join(self.out) + "\n"

    def _emit_struct(self, struct: FLIRStruct) -> None:
        self.out.append(f"typedef struct fst_{struct.name} {{")
        for name, ftype, _offset in struct.fields:
            self.out.append(f"    {self.c_type(ftype)} {name};")
        if not struct.fields:
            self.out.append("    char _empty;")
        self.out.append(f"}} fst_{struct.name};")
        self.out.append("")

    def _signature(self, func: FLIRFunction) -> str:
        params = ", ".join(f"{self.c_type(ptype)} l_{pname}" for pname, ptype in func.params)
        if not params:
            params = "void"
        return f"static {self.c_type(func.return_type)} fsf_{func.name}({params})"

    def _emit_function(self, func: FLIRFunction) -> None:
        self.out.append(self._signature(func) + " {")

        # Hoist all slots and value temps to the top of the function so goto
        # never jumps over declarations into their scope.
        value_names: dict[int, str] = {}
        counter = 0
        decls: list[str] = []
        param_names = {p for p, _ in func.params}
        for block in func.blocks:
            for inst in block.instructions:
                if isinstance(inst, SlotDecl) and inst.name not in param_names:
                    decls.append(f"    {self.c_type(inst.slot_type)} l_{inst.name};")
                if inst.has_result():
                    name = f"t{counter}"
                    counter += 1
                    value_names[id(inst)] = name
                    decls.append(f"    {self.c_type(inst.result_type)} {name};")
        self.out.extend(decls)

        def ref(value: FValue) -> str:
            return value_names[id(value.instruction)]

        for block in func.blocks:
            self.out.append(f"{block.id}:;")
            for inst in block.instructions:
                line = self._emit_inst(inst, ref, func)
                if line:
                    self.out.append(f"    {line}")

        self.out.append("}")
        self.out.append("")

    def _emit_inst(self, inst, ref, func: FLIRFunction) -> str:
        if isinstance(inst, SlotDecl):
            return ""  # hoisted
        if isinstance(inst, ConstInt):
            suffix = ""
            if inst.result_type.kind == "i64":
                suffix = "LL"
            elif inst.result_type.kind == "u64":
                suffix = "ULL"
            return f"{ref(inst.result())} = ({self.c_type(inst.result_type)})({inst.text}{suffix});"
        if isinstance(inst, ConstFloat):
            return f"{ref(inst.result())} = ({self.c_type(inst.result_type)})({inst.text});"
        if isinstance(inst, ConstBool):
            return f"{ref(inst.result())} = {'true' if inst.value else 'false'};"
        if isinstance(inst, ConstStr):
            return f'{ref(inst.result())} = "{self._escape_c_string(inst.text)}";'
        if isinstance(inst, ConstNull):
            return f"{ref(inst.result())} = NULL;"
        if isinstance(inst, GlobalLoad):
            mutable_names = {n for n, _ in self.module.mutable_globals}
            prefix = "fsg_mut_" if inst.name in mutable_names else "fsg_"
            return f"{ref(inst.result())} = {prefix}{inst.name};"
        if isinstance(inst, GlobalStore):
            return f"fsg_mut_{inst.name} = {ref(inst.operands[0])};"
        if isinstance(inst, BinOp):
            op = _BINOPS[inst.op]
            lhs = ref(inst.operands[0])
            rhs = ref(inst.operands[1])
            return f"{ref(inst.result())} = ({lhs} {op} {rhs});"
        if isinstance(inst, Not):
            return f"{ref(inst.result())} = !({ref(inst.operands[0])});"
        if isinstance(inst, Neg):
            return f"{ref(inst.result())} = -({ref(inst.operands[0])});"
        if isinstance(inst, Cvt):
            return f"{ref(inst.result())} = ({self.c_type(inst.result_type)})({ref(inst.operands[0])});"
        if isinstance(inst, Load):
            ctype = self.c_type(inst.result_type)
            base = ref(inst.operands[0])
            return f"{ref(inst.result())} = *({ctype}*)((char*)({base}) + {inst.offset});"
        if isinstance(inst, Store):
            ctype = self.c_type(inst.value_type)
            base = ref(inst.operands[0])
            value = ref(inst.operands[1])
            return f"*({ctype}*)((char*)({base}) + {inst.offset}) = {value};"
        if isinstance(inst, PtrAdd):
            base = ref(inst.operands[0])
            index = ref(inst.operands[1])
            return f"{ref(inst.result())} = (void*)((char*)({base}) + (int64_t)({index}) * {inst.scale});"
        if isinstance(inst, SlotLoad):
            return f"{ref(inst.result())} = l_{inst.name};"
        if isinstance(inst, SlotStore):
            return f"l_{inst.name} = {ref(inst.operands[0])};"
        if isinstance(inst, SlotAddr):
            return f"{ref(inst.result())} = (void*)&l_{inst.name};"
        if isinstance(inst, Call):
            if inst.callee.startswith("fs_rt_") or inst.callee in self.module.externs:
                callee = inst.callee
            else:
                callee = f"fsf_{inst.callee}"
            # Cast arguments to the callee's declared parameter types where
            # known: GCC treats incompatible pointer types as errors, and the
            # firescript-implemented runtime uses char* where callers may
            # hold struct pointers.
            target = self._function_by_name(inst.callee)
            arg_texts = []
            for i, op in enumerate(inst.operands):
                text = ref(op)
                if target is not None and i < len(target.params):
                    ptype = target.params[i][1]
                    if ptype.kind != "struct":
                        text = f"({self.c_type(ptype)})({text})"
                arg_texts.append(text)
            call_text = f"{callee}({', '.join(arg_texts)})"
            if inst.has_result():
                if inst.result_type.kind != "struct":
                    return f"{ref(inst.result())} = ({self.c_type(inst.result_type)})({call_text});"
                return f"{ref(inst.result())} = {call_text};"
            return f"{call_text};"
        if isinstance(inst, Ret):
            if inst.operands:
                return f"return {ref(inst.operands[0])};"
            return "return;"
        if isinstance(inst, Br):
            return (
                f"if ({ref(inst.operands[0])}) goto {inst.true_block}; "
                f"else goto {inst.false_block};"
            )
        if isinstance(inst, Jmp):
            return f"goto {inst.target};"
        if isinstance(inst, Unreachable):
            return "abort();"
        raise NotImplementedError(f"C backend cannot emit {inst.opcode}")

    @staticmethod
    def _escape_c_string(text: str) -> str:
        """Escape literal control characters for a C string literal.
        Backslash escape sequences already present in the source text are
        preserved as-is (mirrors the legacy backend's behavior)."""
        out = []
        for ch in text:
            if ch == "\n":
                out.append("\\n")
            elif ch == "\t":
                out.append("\\t")
            elif ch == "\r":
                out.append("\\r")
            else:
                out.append(ch)
        return "".join(out)

    def _function_by_name(self, name: str):
        for func in self.module.functions:
            if func.name == name:
                return func
        return None

    def _slot_c_type(self, func: FLIRFunction, name: str) -> str:
        for pname, ptype in func.params:
            if pname == name:
                return self.c_type(ptype)
        for block in func.blocks:
            for inst in block.instructions:
                if isinstance(inst, SlotDecl) and inst.name == name:
                    return self.c_type(inst.slot_type)
        return ""
