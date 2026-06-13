"""Minimal PE32+ import-directory reader (pure Python standard library).

Used by the test suite to verify firescript binaries import only
kernel32.dll, replacing the external `objdump -p`. Parses just enough of
the PE format to enumerate imported DLLs and function names.
"""

from __future__ import annotations

import struct
from typing import Optional


class PEFormatError(Exception):
    pass


def _u16(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]


def _u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def _u64(data: bytes, off: int) -> int:
    return struct.unpack_from("<Q", data, off)[0]


class _Section:
    __slots__ = ("name", "vaddr", "vsize", "raw_ptr", "raw_size")

    def __init__(self, name: str, vaddr: int, vsize: int, raw_ptr: int, raw_size: int):
        self.name = name
        self.vaddr = vaddr
        self.vsize = vsize
        self.raw_ptr = raw_ptr
        self.raw_size = raw_size

    def contains_rva(self, rva: int) -> bool:
        span = max(self.vsize, self.raw_size)
        return self.vaddr <= rva < self.vaddr + span


def _rva_to_off(sections: list[_Section], rva: int) -> Optional[int]:
    for s in sections:
        if s.contains_rva(rva):
            return s.raw_ptr + (rva - s.vaddr)
    return None


def _read_cstr(data: bytes, off: int) -> str:
    end = data.find(b"\x00", off)
    if end < 0:
        end = len(data)
    return data[off:end].decode("ascii", "replace")


def read_imports(path: str) -> dict[str, list[str]]:
    """Return {dll_name: [imported function names]} for a PE32+ file."""
    with open(path, "rb") as f:
        data = f.read()

    if data[:2] != b"MZ":
        raise PEFormatError("not an MZ image")
    pe_off = _u32(data, 0x3C)
    if data[pe_off:pe_off + 4] != b"PE\x00\x00":
        raise PEFormatError("missing PE signature")

    coff = pe_off + 4
    num_sections = _u16(data, coff + 2)
    opt_size = _u16(data, coff + 16)
    opt = coff + 20

    magic = _u16(data, opt)
    if magic != 0x20B:
        raise PEFormatError(f"not PE32+ (optional header magic {magic:#x})")

    # PE32+ data directories begin at optional-header offset 112; the import
    # directory is index 1 (RVA, size).
    import_dir_rva = _u32(data, opt + 112 + 1 * 8)
    if import_dir_rva == 0:
        return {}

    sec_table = opt + opt_size
    sections: list[_Section] = []
    for i in range(num_sections):
        base = sec_table + i * 40
        name = data[base:base + 8].rstrip(b"\x00").decode("ascii", "replace")
        vsize = _u32(data, base + 8)
        vaddr = _u32(data, base + 12)
        raw_size = _u32(data, base + 16)
        raw_ptr = _u32(data, base + 20)
        sections.append(_Section(name, vaddr, vsize, raw_ptr, raw_size))

    imports: dict[str, list[str]] = {}
    desc_off = _rva_to_off(sections, import_dir_rva)
    if desc_off is None:
        raise PEFormatError("import directory RVA not in any section")

    # Array of IMAGE_IMPORT_DESCRIPTOR (20 bytes), terminated by an all-zero entry.
    while True:
        ilt_rva = _u32(data, desc_off)
        name_rva = _u32(data, desc_off + 12)
        iat_rva = _u32(data, desc_off + 16)
        if ilt_rva == 0 and name_rva == 0 and iat_rva == 0:
            break

        dll_off = _rva_to_off(sections, name_rva)
        dll_name = _read_cstr(data, dll_off) if dll_off is not None else "<?>"
        funcs: list[str] = []

        # Prefer the Import Lookup Table; fall back to the IAT (bound thunks).
        thunk_rva = ilt_rva or iat_rva
        thunk_off = _rva_to_off(sections, thunk_rva) if thunk_rva else None
        if thunk_off is not None:
            entry = thunk_off
            while True:
                value = _u64(data, entry)
                if value == 0:
                    break
                if value & (1 << 63):
                    funcs.append(f"#ordinal:{value & 0xFFFF}")
                else:
                    hint_off = _rva_to_off(sections, value & 0x7FFFFFFF)
                    if hint_off is not None:
                        funcs.append(_read_cstr(data, hint_off + 2))
                entry += 8

        imports.setdefault(dll_name, []).extend(funcs)
        desc_off += 20

    return imports


def imported_dlls(path: str) -> list[str]:
    return sorted(read_imports(path).keys())
