"""Pure-Python PE32+ writer/linker.

Turns an assembler ObjectImage into a runnable Windows x86_64 console
executable, building the kernel32 import table by hand. No external tools.

The backend emits fully position-independent code (RIP-relative data
references; import calls go through the IAT via `call [rip+slot]`), so the
image has no absolute addresses and therefore no base relocations. We still
mark it DYNAMICBASE/NXCOMPAT and leave RELOCS_STRIPPED clear, so the loader
treats it as a normal relocatable, ASLR-eligible, DEP-compatible program.
"""

from __future__ import annotations

import struct

from backend.x86_64.assembler import ObjectImage, RIP32, RIP32_IMPORT

IMAGE_BASE = 0x140000000
SECTION_ALIGN = 0x1000
FILE_ALIGN = 0x200


def _align(n: int, a: int) -> int:
    return (n + a - 1) & ~(a - 1)


class _Section:
    def __init__(self, name, characteristics):
        self.name = name
        self.characteristics = characteristics
        self.data = bytearray()
        self.virtual_size = 0      # may exceed len(data) for .bss
        self.rva = 0
        self.file_off = 0

    @property
    def raw_size(self):
        return _align(len(self.data), FILE_ALIGN)


# Section characteristic flags
_CODE = 0x60000020       # CNT_CODE | MEM_EXECUTE | MEM_READ
_RDATA = 0x40000040      # CNT_INITIALIZED_DATA | MEM_READ
_DATA = 0xC0000040       # CNT_INITIALIZED_DATA | MEM_READ | MEM_WRITE


def write_pe(obj: ObjectImage, out_path: str, import_dll_map: dict | None = None) -> None:
    """Write `obj` to a PE32+ console .exe at out_path.

    import_dll_map: symbol name -> DLL name (defaults all imports to
    kernel32.dll, which is the only DLL the runtime uses).
    """
    if "firescript_entry" not in obj.symbols:
        raise ValueError("object has no firescript_entry symbol")

    dll_of = {}
    for sym in sorted(obj.import_symbols):
        dll_of[sym] = (import_dll_map or {}).get(sym, "kernel32.dll")

    # --- group imports by DLL (deterministic order) ---
    by_dll: dict[str, list[str]] = {}
    for sym in sorted(obj.import_symbols):
        by_dll.setdefault(dll_of[sym], []).append(sym)

    text = _Section(b".text", _CODE)
    text.data = bytearray(obj.text)
    rdata = _Section(b".rdata", _RDATA)
    rdata.data = bytearray(obj.rdata)

    has_bss = obj.bss_size > 0
    data_sec = _Section(b".data", _DATA) if has_bss else None

    # --- assign RVAs/file offsets (headers first) ---
    num_sections = 2 + (1 if has_bss else 0)
    headers_size = 0x40 + len(_DOS_STUB) + 4 + 20 + 240 + 40 * num_sections
    headers_size = _align(headers_size, FILE_ALIGN)

    rva = _align(headers_size, SECTION_ALIGN)
    file_off = headers_size

    text.rva = rva
    text.file_off = file_off

    # The import structures live at the end of .rdata; reserve space by
    # computing their size, then append to rdata.data before finalizing.
    rdata.rva = _align(text.rva + max(len(text.data), 1), SECTION_ALIGN)

    # Build import blob now that we know rdata.rva and the offset where the
    # blob will start within rdata.
    iat_entries: dict[str, int] = {}  # symbol -> IAT slot RVA
    import_blob, import_dir_rva, import_dir_size, iat_rva, iat_size = _build_imports(
        by_dll, rdata.rva, len(rdata.data), iat_entries
    )
    rdata.data += import_blob

    text.file_off = file_off
    rdata.file_off = _align(text.file_off + text.raw_size, FILE_ALIGN)

    text.virtual_size = len(text.data)
    rdata.virtual_size = len(rdata.data)

    next_rva = _align(rdata.rva + max(len(rdata.data), 1), SECTION_ALIGN)
    next_file = _align(rdata.file_off + rdata.raw_size, FILE_ALIGN)
    if has_bss:
        data_sec.rva = next_rva
        data_sec.file_off = next_file
        data_sec.virtual_size = obj.bss_size
        data_sec.data = bytearray()  # uninitialized; loader zero-fills
        next_rva = _align(data_sec.rva + obj.bss_size, SECTION_ALIGN)

    # --- symbol RVA resolution ---
    def sym_rva(name: str) -> int:
        section, off = obj.symbols[name]
        if section == "text":
            return text.rva + off
        if section == "rdata":
            return rdata.rva + off
        if section == "bss":
            if not has_bss:
                raise ValueError("bss symbol but no .data section")
            return data_sec.rva + off
        raise ValueError(f"unknown section {section}")

    # --- apply relocations (RIP-relative disp32 fixups) ---
    for r in obj.relocs:
        assert r.section == "text"
        site_rva = text.rva + r.offset
        next_ip_rva = text.rva + r.next_ip
        if r.kind == RIP32_IMPORT:
            target_rva = iat_entries[r.symbol]
        elif r.kind == RIP32:
            target_rva = sym_rva(r.symbol)
        else:
            raise ValueError(f"unsupported reloc kind {r.kind}")
        disp = target_rva - next_ip_rva + r.addend
        struct.pack_into("<i", text.data, r.offset, disp)

    entry_rva = sym_rva("firescript_entry")
    size_of_image = _align(next_rva, SECTION_ALIGN)

    # --- assemble the file ---
    sections = [text, rdata] + ([data_sec] if has_bss else [])
    out = bytearray()
    out += _dos_header_and_stub()
    out += b"PE\x00\x00"
    out += _coff_header(num_sections)
    out += _optional_header(
        sections, entry_rva, size_of_image, headers_size,
        import_dir_rva, import_dir_size, iat_rva, iat_size,
    )
    for s in sections:
        out += _section_header(s)
    # pad to first section file offset
    out += b"\x00" * (text.file_off - len(out))
    for s in sections:
        if len(out) < s.file_off:
            out += b"\x00" * (s.file_off - len(out))
        out += s.data
        pad = s.raw_size - len(s.data)
        if pad > 0:
            out += b"\x00" * pad

    with open(out_path, "wb") as f:
        f.write(out)


def _build_imports(by_dll, rdata_rva, blob_start_off, iat_entries):
    """Build the import directory/ILT/IAT/hint-name blob.

    Layout within the blob (all RVA-relative to rdata_rva + blob_start_off):
      [ import descriptors (N+1) ][ per-dll ILT ][ per-dll IAT ]
      [ dll name strings ][ hint/name entries ]
    Returns (blob, import_dir_rva, import_dir_size, iat_rva, iat_size).
    """
    base = rdata_rva + blob_start_off
    descs = list(by_dll.items())
    n = len(descs)

    desc_size = (n + 1) * 20
    # Each DLL gets an ILT and an IAT, both (count+1) thunks of 8 bytes.
    ilt_offs = {}
    iat_offs = {}
    cursor = desc_size
    for dll, syms in descs:
        ilt_offs[dll] = cursor
        cursor += (len(syms) + 1) * 8
    iat_region_start = cursor
    for dll, syms in descs:
        iat_offs[dll] = cursor
        cursor += (len(syms) + 1) * 8
    iat_region_end = cursor

    # String/hint-name area.
    name_offs = {}
    hint_offs = {}
    strings = bytearray()
    for dll, syms in descs:
        name_offs[dll] = cursor + len(strings)
        strings += dll.encode("ascii") + b"\x00"
        if len(strings) & 1:
            strings += b"\x00"
    for dll, syms in descs:
        for s in syms:
            hint_offs[s] = cursor + len(strings)
            strings += struct.pack("<H", 0) + s.encode("ascii") + b"\x00"
            if len(strings) & 1:
                strings += b"\x00"

    blob = bytearray(cursor + len(strings))

    # Import descriptors.
    off = 0
    for dll, syms in descs:
        ilt_rva = base + ilt_offs[dll]
        iat_rva_dll = base + iat_offs[dll]
        name_rva = base + name_offs[dll]
        struct.pack_into("<IIIII", blob, off,
                         ilt_rva, 0, 0, name_rva, iat_rva_dll)
        off += 20
    # null terminator descriptor already zero.

    # ILT and IAT thunks (identical contents pre-load: RVA to hint/name).
    for dll, syms in descs:
        ilt = ilt_offs[dll]
        iat = iat_offs[dll]
        for i, s in enumerate(syms):
            thunk = base + hint_offs[s]
            struct.pack_into("<Q", blob, ilt + i * 8, thunk)
            struct.pack_into("<Q", blob, iat + i * 8, thunk)
            iat_entries[s] = base + iat + i * 8
        # terminators already zero
    blob[cursor:cursor + len(strings)] = strings

    import_dir_rva = base
    import_dir_size = desc_size
    iat_rva = base + iat_region_start
    iat_size = iat_region_end - iat_region_start
    return blob, import_dir_rva, import_dir_size, iat_rva, iat_size


_DOS_STUB = (
    b"\x0e\x1f\xba\x0e\x00\xb4\x09\xcd\x21\xb8\x01\x4c\xcd\x21"
    b"This program cannot be run in DOS mode.\r\r\n$"
    + b"\x00" * 7
)


def _dos_header_and_stub() -> bytes:
    out = bytearray(0x40)
    out[0:2] = b"MZ"
    # e_lfanew at 0x3C -> PE header right after the stub.
    pe_off = 0x40 + len(_DOS_STUB)
    struct.pack_into("<I", out, 0x3C, pe_off)
    return bytes(out) + _DOS_STUB


def _coff_header(num_sections: int) -> bytes:
    machine = 0x8664
    characteristics = 0x0022  # EXECUTABLE_IMAGE | LARGE_ADDRESS_AWARE
    return struct.pack("<HHIIIHH", machine, num_sections, 0, 0, 0, 240, characteristics)


def _optional_header(sections, entry_rva, size_of_image, size_of_headers,
                     import_dir_rva, import_dir_size, iat_rva, iat_size) -> bytes:
    text = sections[0]
    code_size = sum(s.raw_size for s in sections if s.characteristics == _CODE)
    init_size = sum(s.raw_size for s in sections if s.characteristics != _CODE)
    base_of_code = text.rva

    h = bytearray()
    h += struct.pack("<H", 0x20B)          # Magic PE32+
    h += struct.pack("<BB", 14, 0)         # linker version
    h += struct.pack("<I", code_size)
    h += struct.pack("<I", init_size)
    h += struct.pack("<I", 0)              # uninitialized data size
    h += struct.pack("<I", entry_rva)
    h += struct.pack("<I", base_of_code)
    h += struct.pack("<Q", IMAGE_BASE)
    h += struct.pack("<I", SECTION_ALIGN)
    h += struct.pack("<I", FILE_ALIGN)
    h += struct.pack("<HH", 6, 0)          # OS version
    h += struct.pack("<HH", 0, 0)          # image version
    h += struct.pack("<HH", 6, 0)          # subsystem version
    h += struct.pack("<I", 0)              # Win32VersionValue
    h += struct.pack("<I", size_of_image)
    h += struct.pack("<I", size_of_headers)
    h += struct.pack("<I", 0)              # checksum (0 = not computed)
    h += struct.pack("<H", 3)              # Subsystem = console
    # DllCharacteristics: HIGH_ENTROPY_VA | DYNAMIC_BASE | NX_COMPAT
    h += struct.pack("<H", 0x0020 | 0x0040 | 0x0100)
    h += struct.pack("<Q", 0x100000)       # stack reserve
    h += struct.pack("<Q", 0x1000)         # stack commit
    h += struct.pack("<Q", 0x100000)       # heap reserve
    h += struct.pack("<Q", 0x1000)         # heap commit
    h += struct.pack("<I", 0)              # loader flags
    h += struct.pack("<I", 16)             # number of data directories

    dirs = [(0, 0)] * 16
    dirs[1] = (import_dir_rva, import_dir_size)   # Import
    dirs[12] = (iat_rva, iat_size)                # IAT
    for r, s in dirs:
        h += struct.pack("<II", r, s)
    assert len(h) == 240, len(h)
    return bytes(h)


def _section_header(s: _Section) -> bytes:
    name = s.name[:8].ljust(8, b"\x00")
    virtual_size = max(s.virtual_size, len(s.data))
    raw_size = s.raw_size
    return struct.pack(
        "<8sIIIIIIHHI",
        name,
        virtual_size,
        s.rva,
        raw_size,
        s.file_off if raw_size else 0,
        0, 0, 0, 0,
        s.characteristics,
    )
