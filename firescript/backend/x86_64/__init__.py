"""Arch-specific native backend: x86-64 instruction encoding.

Turns the FLIR backend's GAS-syntax assembly text into an `ObjectImage`
(section bytes, symbol table, relocations). Platform-agnostic — any
executable format writer (PE, ELF, Mach-O, ...) consumes its output.
"""
