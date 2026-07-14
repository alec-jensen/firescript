"""Unit tests for the pure-Python PE32+ writer/linker
(firescript/backend/windows/pe.py), driving write_pe directly with hand-built
ObjectImage instances to hit its defensive error branches (missing entry
symbol, bss-without-.data, unknown symbol section, unsupported reloc kind)
that cannot be reached from a normal successful compile."""
from __future__ import annotations

import os
import sys
import tempfile

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from backend.x86_64.assembler import ObjectImage, Reloc, RIP32  # noqa: E402
from backend.windows import pe  # noqa: E402


def _out_path() -> str:
    fd, path = tempfile.mkstemp(suffix=".exe")
    os.close(fd)
    return path


def test_missing_entry_symbol_raises():
    obj = ObjectImage()
    obj.text = bytearray(b"\xc3")  # ret
    out_path = _out_path()
    try:
        raised = False
        try:
            pe.write_pe(obj, out_path)
        except ValueError as e:
            raised = True
            t.require("firescript_entry" in str(e), f"unexpected message: {e}")
        t.require(raised, "expected ValueError for missing firescript_entry symbol")
    finally:
        os.remove(out_path)


def test_bss_symbol_without_data_section_raises():
    obj = ObjectImage()
    obj.text = bytearray(b"\x00\x00\x00\x00\xc3")
    obj.symbols["firescript_entry"] = ("text", 0)
    obj.symbols["counter"] = ("bss", 0)
    obj.bss_size = 0  # no .data section will be created
    obj.relocs.append(Reloc(section="text", offset=0, kind=RIP32, symbol="counter", next_ip=4))
    out_path = _out_path()
    try:
        raised = False
        try:
            pe.write_pe(obj, out_path)
        except ValueError as e:
            raised = True
            t.require("bss" in str(e), f"unexpected message: {e}")
        t.require(raised, "expected ValueError for bss symbol without .data section")
    finally:
        os.remove(out_path)


def test_unknown_symbol_section_raises():
    obj = ObjectImage()
    obj.text = bytearray(b"\x00\x00\x00\x00\xc3")
    obj.symbols["firescript_entry"] = ("text", 0)
    obj.symbols["weird"] = ("mystery", 0)
    obj.relocs.append(Reloc(section="text", offset=0, kind=RIP32, symbol="weird", next_ip=4))
    out_path = _out_path()
    try:
        raised = False
        try:
            pe.write_pe(obj, out_path)
        except ValueError as e:
            raised = True
            t.require("unknown section" in str(e), f"unexpected message: {e}")
        t.require(raised, "expected ValueError for unknown symbol section")
    finally:
        os.remove(out_path)


def test_unsupported_reloc_kind_raises():
    obj = ObjectImage()
    obj.text = bytearray(b"\x00\x00\x00\x00\xc3")
    obj.symbols["firescript_entry"] = ("text", 0)
    obj.relocs.append(Reloc(section="text", offset=0, kind="bogus_kind", symbol="firescript_entry", next_ip=4))
    out_path = _out_path()
    try:
        raised = False
        try:
            pe.write_pe(obj, out_path)
        except ValueError as e:
            raised = True
            t.require("unsupported reloc kind" in str(e), f"unexpected message: {e}")
        t.require(raised, "expected ValueError for unsupported reloc kind")
    finally:
        os.remove(out_path)
