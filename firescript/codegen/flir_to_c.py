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

_RUNTIME_SHIMS = r"""
/* ---- fs_rt_* runtime shims over the legacy C runtime ---- */
static void* fs_rt_alloc_zeroed(int64_t n) {
    void* p = firescript_malloc((size_t)n);
    if (p) memset(p, 0, (size_t)n);
    return p;
}
static void fs_rt_free(void* p) { firescript_free(p); }
static void fs_rt_zero_memory(void* p, int64_t n) { memset(p, 0, (size_t)n); }
static void fs_rt_mem_copy(void* dst, const void* src, uint64_t n) { memmove(dst, src, (size_t)n); }
static char* fs_rt_str_dup(const char* s) { return firescript_strdup(s ? s : ""); }
static char* fs_rt_str_concat(const char* a, const char* b) { return firescript_strcat(a, b); }
static bool fs_rt_str_eq(const char* a, const char* b) { return firescript_strcmp(a ? a : "", b ? b : ""); }
static int32_t fs_rt_str_length(const char* s) { return firescript_str_length(s); }
static char* fs_rt_str_char_at(const char* s, int32_t i) { return firescript_str_char_at(s, i); }
static int8_t fs_rt_str_char_code_at(const char* s, int32_t i) {
    if (!s) return 0;
    int32_t len = (int32_t)strlen(s);
    if (i < 0 || i >= len) return 0;
    return (int8_t)s[i];
}
static int8_t fs_rt_str_char_code(const char* s) { return (s && s[0]) ? (int8_t)s[0] : 0; }
static int32_t fs_rt_str_index_of(const char* h, const char* n) { return firescript_str_index_of(h, n); }
static char* fs_rt_str_slice(const char* s, int32_t a, int32_t b) { return firescript_str_slice(s, a, b); }
static char* fs_rt_i32_to_str(int32_t v) { return firescript_toString_impl_int32(v); }
static char* fs_rt_i64_to_str(int64_t v) { return firescript_toString_impl_int64(v); }
static char* fs_rt_u32_to_str(uint32_t v) { return firescript_toString_impl_uint32(v); }
static char* fs_rt_u64_to_str(uint64_t v) { return firescript_toString_impl_uint64(v); }
static char* fs_rt_f32_to_str(float v) { return firescript_toString_impl_float(v); }
static char* fs_rt_f64_to_str(double v) { return firescript_toString_impl_double(v); }
static char* fs_rt_f32_to_repr(float v) { return firescript_f32_to_str(v); }
static char* fs_rt_f64_to_repr(double v) { return firescript_f64_to_str(v); }
static char* fs_rt_bool_to_str(bool v) { return firescript_toString_impl_bool(v); }
static char* fs_rt_char_to_str(int8_t c) {
    char buf[2] = { (char)c, '\0' };
    return firescript_strdup(buf);
}
static int32_t fs_rt_str_to_i32(const char* s) { return (int32_t)atoi(s ? s : "0"); }
static int64_t fs_rt_str_to_i64(const char* s) { return (int64_t)atoll(s ? s : "0"); }
static double fs_rt_str_to_f64(const char* s) { return atof(s ? s : "0"); }
static bool fs_rt_str_to_bool(const char* s) { return firescript_toBool_impl_string(s ? s : ""); }
static int64_t fs_rt_pow_i64(int64_t base, int64_t exp) {
    int64_t r = 1;
    while (exp > 0) { r *= base; exp--; }
    return r;
}
static double fs_rt_pow_f64(double base, double exp) {
    double r = 1.0;
    if (exp < 0.0) {
        double acc = 1.0;
        int64_t e = (int64_t)(-exp);
        while (e > 0) { acc *= base; e--; }
        return 1.0 / acc;
    }
    int64_t e = (int64_t)exp;
    while (e > 0) { r *= base; e--; }
    return r;
}
static void fs_rt_stdout(const char* s) { printf("%s", s ? s : ""); }
static int32_t fs_rt_argc(void) { return firescript_argc(); }
static char* fs_rt_argv_at(int32_t i) { return firescript_argv_at(i); }
"""

_SYSCALL_SHIM_TEMPLATE = """static fst_SyscallResult fs_rt_syscall_{name}({params}) {{
    SyscallResult r = firescript_syscall_{name}({args});
    fst_SyscallResult out;
    out.status = r.status;
    out.data = r.data;
    return out;
}}
"""

_SYSCALL_SIGS = {
    "open": [("path", "const char*"), ("mode", "const char*")],
    "read": [("fd", "int32_t"), ("n", "int32_t")],
    "write": [("fd", "int32_t"), ("buf", "const char*")],
    "close": [("fd", "int32_t")],
    "remove": [("path", "const char*")],
    "rename": [("a", "const char*"), ("b", "const char*")],
    "move": [("a", "const char*"), ("b", "const char*")],
}


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
            "#include <stdio.h>",
            "#include <stdlib.h>",
            "#include <stdbool.h>",
            "#include <stdint.h>",
            "#include <inttypes.h>",
            "#include <string.h>",
            '#include "firescript/runtime/runtime.h"',
            '#include "firescript/runtime/conversions.h"',
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

        uses_syscalls = self._uses_syscalls()
        self.out.append(_RUNTIME_SHIMS)
        if uses_syscalls:
            for name, params in _SYSCALL_SIGS.items():
                params_text = ", ".join(f"{ctype} {pname}" for pname, ctype in params)
                args_text = ", ".join(pname for pname, _ in params)
                self.out.append(
                    _SYSCALL_SHIM_TEMPLATE.format(name=name, params=params_text, args=args_text)
                )

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
            self.out.append("int main(int argc, char **argv) {")
            self.out.append("    firescript_set_process_args(argc, argv);")
            self.out.append(f"    fsf_{self.module.entry_function}();")
            self.out.append("    firescript_cleanup();")
            self.out.append("    return 0;")
            self.out.append("}")

        return "\n".join(self.out) + "\n"

    def _uses_syscalls(self) -> bool:
        for func in self.module.functions:
            for block in func.blocks:
                for inst in block.instructions:
                    if isinstance(inst, Call) and inst.callee.startswith("fs_rt_syscall_"):
                        return True
        return False

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
