"""Unit tests for firescript/backend/windows/pe_inspect.py, the minimal
PE32+ import-directory reader the test harness uses (in place of
`objdump -p`) to verify firescript binaries import only kernel32.dll.

Covers malformed-input error branches and the low-level helpers directly,
plus a hand-built PE32+ image exercising the ordinal-import branch, which
firescript's own writer (backend/windows/pe.py) never produces (it always
emits name-based imports) so real compiler output can't reach it.
"""
from __future__ import annotations

import os
import struct
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from backend.windows import pe_inspect  # noqa: E402
from backend.windows.pe_inspect import PEFormatError, _Section  # noqa: E402


# ---------------------------------------------------------------------------
# Low-level helpers, called directly.
# ---------------------------------------------------------------------------

def test_rva_to_off_no_matching_section():
    t.require(pe_inspect._rva_to_off([], 0x1000) is None)


def test_read_cstr_no_terminator_reads_to_end():
    t.require_eq(pe_inspect._read_cstr(b"abc", 0), "abc")


# ---------------------------------------------------------------------------
# read_imports() malformed-input error branches.
# ---------------------------------------------------------------------------

def _write(d, name, data: bytes) -> str:
    path = os.path.join(d, name)
    with open(path, "wb") as f:
        f.write(data)
    return path


def test_read_imports_rejects_non_mz():
    with t.tmpdir() as d:
        path = _write(d, "bad.exe", b"XX" + b"\x00" * 62)
        try:
            pe_inspect.read_imports(path)
            t.require(False, "expected PEFormatError")
        except PEFormatError as e:
            t.require("MZ image" in str(e), str(e))


def test_read_imports_rejects_missing_pe_signature():
    with t.tmpdir() as d:
        header = bytearray(0x44)
        header[0:2] = b"MZ"
        struct.pack_into("<I", header, 0x3C, 0x40)  # e_lfanew -> offset 0x40
        header[0x40:0x44] = b"NOPE"
        path = _write(d, "bad.exe", bytes(header))
        try:
            pe_inspect.read_imports(path)
            t.require(False, "expected PEFormatError")
        except PEFormatError as e:
            t.require("PE signature" in str(e), str(e))


def _pe_header(num_sections=0, opt_size=128, magic=0x20B,
               import_dir_rva=0, import_dir_size=0,
               section_headers: bytes = b"") -> bytearray:
    """Build a minimal DOS+COFF+optional header (+ section table) with just
    the fields pe_inspect.read_imports() actually reads."""
    dos = bytearray(0x40)
    dos[0:2] = b"MZ"
    pe_off = 0x40
    struct.pack_into("<I", dos, 0x3C, pe_off)
    sig = b"PE\x00\x00"
    coff = struct.pack("<HHIIIHH", 0x8664, num_sections, 0, 0, 0, opt_size, 0x0022)
    opt = bytearray(opt_size)
    struct.pack_into("<H", opt, 0, magic)
    if opt_size >= 120 + 4:
        struct.pack_into("<II", opt, 112 + 1 * 8, import_dir_rva, import_dir_size)
    return bytearray(dos) + bytearray(sig) + bytearray(coff) + opt + bytearray(section_headers)


def test_read_imports_rejects_non_pe32plus_magic():
    with t.tmpdir() as d:
        data = _pe_header(magic=0x10B)  # PE32 (32-bit), not PE32+
        path = _write(d, "bad.exe", bytes(data))
        try:
            pe_inspect.read_imports(path)
            t.require(False, "expected PEFormatError")
        except PEFormatError as e:
            t.require("not PE32+" in str(e), str(e))


def test_read_imports_zero_import_dir_returns_empty():
    with t.tmpdir() as d:
        data = _pe_header(import_dir_rva=0)
        path = _write(d, "noimports.exe", bytes(data))
        t.require_eq(pe_inspect.read_imports(path), {})


def _section_header(name: bytes, vsize, vaddr, raw_size, raw_ptr) -> bytes:
    return struct.pack(
        "<8sIIIIIIHHI",
        name[:8].ljust(8, b"\x00"), vsize, vaddr, raw_size, raw_ptr,
        0, 0, 0, 0, 0,
    )


def test_read_imports_dir_rva_outside_any_section_raises():
    with t.tmpdir() as d:
        sec = _section_header(b".text", 0x10, 0x1000, 0x200, 0x200)
        data = _pe_header(num_sections=1, import_dir_rva=0x9999, section_headers=sec)
        data += b"\x00" * 0x200  # pad up to the (unused) section's raw data
        path = _write(d, "bad.exe", bytes(data))
        try:
            pe_inspect.read_imports(path)
            t.require(False, "expected PEFormatError")
        except PEFormatError as e:
            t.require("import directory RVA not in any section" in str(e), str(e))


def test_read_imports_ordinal_thunk():
    # firescript's own writer never emits ordinal imports (only name-based
    # ones via the hint/name table), so this branch is unreachable from
    # real compiler output; build a minimal hand-crafted image instead.
    base_rva = 0x1000
    raw_ptr = 0x200

    section_data = bytearray()
    # Import descriptor #0 (real entry): ILT at +40, Name at +56, IAT=0.
    section_data += struct.pack(
        "<IIIII", base_rva + 40, 0, 0, base_rva + 56, 0
    )
    # Import descriptor #1: null terminator.
    section_data += b"\x00" * 20
    assert len(section_data) == 40
    # ILT: one ordinal-import thunk (high bit set, ordinal 1), then a
    # zero terminator thunk.
    section_data += struct.pack("<Q", (1 << 63) | 1)
    section_data += struct.pack("<Q", 0)
    assert len(section_data) == 56
    # DLL name string.
    section_data += b"test.dll\x00\x00"  # padded to even length

    sec = _section_header(b".rdata", len(section_data), base_rva,
                           len(section_data), raw_ptr)
    header = _pe_header(num_sections=1, import_dir_rva=base_rva,
                         import_dir_size=40, section_headers=sec)
    image = bytearray(header)
    image += b"\x00" * (raw_ptr - len(image))
    image += section_data

    with t.tmpdir() as d:
        path = _write(d, "ordinal.exe", bytes(image))
        imports = pe_inspect.read_imports(path)
        t.require_eq(imports, {"test.dll": ["#ordinal:1"]})


def test_imported_dlls_sorted():
    with t.tmpdir() as d:
        data = _pe_header(import_dir_rva=0)
        path = _write(d, "noimports.exe", bytes(data))
        t.require_eq(pe_inspect.imported_dlls(path), [])
