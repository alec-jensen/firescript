"""Unit tests for the pure-Python PE32+ writer/linker in
firescript/backend/windows/pe.py.

Most of write_pe()'s error branches (bad section references, unsupported
relocation kinds, missing entry point) are internal-consistency checks
that the compiler's own pipeline can never trip -- so we build small,
hand-crafted ObjectImage instances directly and feed them to write_pe()
to exercise those branches.
"""
from __future__ import annotations

import os
import struct
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from backend.x86_64.assembler import ObjectImage, Reloc, RIP32  # noqa: E402
from backend.windows.pe import write_pe  # noqa: E402


def _minimal_obj() -> ObjectImage:
    """An ObjectImage with just enough to write a valid PE: a single `ret`
    instruction at the entry point, no imports, no data."""
    obj = ObjectImage()
    obj.text = bytearray(b"\xc3")  # ret
    obj.symbols["firescript_entry"] = ("text", 0)
    return obj


def test_write_pe_requires_entry_symbol():
    obj = ObjectImage()
    obj.text = bytearray(b"\xc3")
    with t.tmpdir() as d:
        out = os.path.join(d, "out.exe")
        try:
            write_pe(obj, out)
            t.require(False, "expected ValueError")
        except ValueError as e:
            t.require("firescript_entry" in str(e), str(e))


def test_write_pe_smoke():
    # Sanity check the minimal-object helper itself produces a valid image
    # (MZ + PE signature present), so the error-path tests below are
    # exercising real divergences from a working baseline.
    obj = _minimal_obj()
    with t.tmpdir() as d:
        out = os.path.join(d, "out.exe")
        write_pe(obj, out)
        with open(out, "rb") as f:
            data = f.read()
        t.require(data[:2] == b"MZ")
        pe_off = struct.unpack_from("<I", data, 0x3C)[0]
        t.require(data[pe_off:pe_off + 4] == b"PE\x00\x00")


def test_write_pe_bss_symbol_without_data_section_raises():
    # A symbol claiming section "bss" while obj.bss_size == 0 (so no .data
    # section is allocated) is an internal-consistency violation: sym_rva()
    # must refuse to resolve it.
    obj = _minimal_obj()
    obj.text = bytearray(b"\xc3" + b"\x00\x00\x00\x00")  # ret + disp32 slot
    obj.symbols["stray_bss_sym"] = ("bss", 0)
    obj.relocs.append(Reloc("text", 1, RIP32, "stray_bss_sym", 5))
    with t.tmpdir() as d:
        out = os.path.join(d, "out.exe")
        try:
            write_pe(obj, out)
            t.require(False, "expected ValueError")
        except ValueError as e:
            t.require("bss symbol but no .data section" in str(e), str(e))


def test_write_pe_unknown_section_raises():
    obj = _minimal_obj()
    obj.text = bytearray(b"\xc3" + b"\x00\x00\x00\x00")
    obj.symbols["weird"] = ("weird_section", 0)
    obj.relocs.append(Reloc("text", 1, RIP32, "weird", 5))
    with t.tmpdir() as d:
        out = os.path.join(d, "out.exe")
        try:
            write_pe(obj, out)
            t.require(False, "expected ValueError")
        except ValueError as e:
            t.require("unknown section" in str(e), str(e))


def test_write_pe_unsupported_reloc_kind_raises():
    obj = _minimal_obj()
    obj.text = bytearray(b"\xc3" + b"\x00\x00\x00\x00")
    obj.relocs.append(Reloc("text", 1, "bogus_kind", "firescript_entry", 5))
    with t.tmpdir() as d:
        out = os.path.join(d, "out.exe")
        try:
            write_pe(obj, out)
            t.require(False, "expected ValueError")
        except ValueError as e:
            t.require("unsupported reloc kind" in str(e), str(e))
