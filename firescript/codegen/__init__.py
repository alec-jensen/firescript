"""firescript code generation backends.

The compiler pipeline is AST -> FIR -> FLIR -> arch-specific assembly.
Each `codegen.<arch>` subpackage implements one architecture's backend;
see `codegen.x86_64.flir_to_asm.FLIRToAsmBackend` for the only one
implemented today (see `firescript/targets.py` for the support matrix).
"""

from codegen.x86_64.flir_to_asm import FLIRToAsmBackend

__all__ = ["FLIRToAsmBackend"]
