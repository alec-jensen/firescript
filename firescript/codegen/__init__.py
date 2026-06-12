"""firescript code generation backends.

The compiler pipeline is AST -> FIR -> FLIR -> x86-64 assembly; see
flir_to_asm.FLIRToAsmBackend.
"""

from codegen.flir_to_asm import FLIRToAsmBackend

__all__ = ["FLIRToAsmBackend"]
