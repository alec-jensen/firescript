"""FIR module structure: modules, functions, type definitions, constants."""

from __future__ import annotations

from typing import Optional

from fir.ir_node import BasicBlock, ParamValue
from fir.ir_types import FIRType
from fir.ownership import OwnershipMap


class EnumVariantDef:
    """One variant of an enum type: a name plus its positional payload fields.

    `payload` is empty for tag-only variants; data-carrying variants are a
    planned follow-up (payload fields are stored by position, not name).
    """

    def __init__(self, name: str, payload: Optional[list[FIRType]] = None):
        self.name = name
        self.payload = payload or []


class TypeDef:
    """A class or enum definition preserved at the FIR level."""

    def __init__(
        self,
        name: str,
        category: str = "owned",
        fields: Optional[list[tuple[str, FIRType]]] = None,
        generic_params: Optional[list[str]] = None,
        base: Optional[str] = None,
        kind: str = "class",
        variants: Optional[list[EnumVariantDef]] = None,
    ):
        self.name = name
        self.category = category  # "owned" | "copyable"
        self.fields = fields or []
        self.generic_params = generic_params or []
        self.base = base  # name of the parent class, if any
        self.kind = kind  # "class" | "enum"
        self.variants = variants or []  # only meaningful when kind == "enum"


class GlobalConstant:
    """A module-level constant with a literal initializer."""

    def __init__(self, name: str, const_type: FIRType, literal_text: str):
        self.name = name
        self.const_type = const_type
        self.literal_text = literal_text


class FIRFunction:
    """A function (or method, or generator) in FIR form."""

    def __init__(
        self,
        name: str,
        params: Optional[list[tuple[str, FIRType]]] = None,
        return_type: Optional[FIRType] = None,
        generic_params: Optional[list[str]] = None,
        param_modes: Optional[list[str]] = None,
        is_generator: bool = False,
    ):
        self.name = name
        self.params = params or []
        # Per-parameter passing mode: "own" | "borrow" | "borrow_mut"
        self.param_modes = param_modes or ["own"] * len(self.params)
        self.return_type = return_type
        self.generic_params = generic_params or []
        self.is_generator = is_generator
        self.blocks: list[BasicBlock] = []
        self.ownership = OwnershipMap()
        self.metadata: dict = {}
        self._block_counter = 0
        self._param_values: dict[str, ParamValue] = {
            p_name: ParamValue(p_name, p_type) for p_name, p_type in self.params
        }
        for p_name, _ in self.params:
            self.ownership.declare(p_name)

    def param_value(self, name: str) -> ParamValue:
        """The Value representing a parameter, usable as an operand."""
        return self._param_values[name]

    def new_block(self) -> BasicBlock:
        block = BasicBlock(f"block_{self._block_counter}")
        self._block_counter += 1
        self.blocks.append(block)
        return block

    def validate(self) -> None:
        """Check structural invariants; raises ValueError on violation."""
        if not self.blocks:
            raise ValueError(f"function {self.name} has no blocks")
        block_ids = set()
        for block in self.blocks:
            if block.id in block_ids:
                raise ValueError(f"function {self.name} has duplicate block id {block.id}")
            block_ids.add(block.id)
            if block.terminator is None:
                raise ValueError(f"block {block.id} in function {self.name} has no terminator")
        for block in self.blocks:
            term = block.terminator
            targets = []
            if hasattr(term, "true_block"):
                targets.extend([term.true_block, term.false_block])
            if hasattr(term, "target_block"):
                targets.append(term.target_block)
            for target in targets:
                if target not in block_ids:
                    raise ValueError(
                        f"block {block.id} in function {self.name} targets unknown block {target}"
                    )


class FIRModule:
    """Top-level FIR container for one compiled program."""

    def __init__(self, name: str = "firescript"):
        self.name = name
        self.types: list[TypeDef] = []
        self.functions: list[FIRFunction] = []
        self.constants: list[GlobalConstant] = []

    def add_type(self, type_def: TypeDef) -> TypeDef:
        self.types.append(type_def)
        return type_def

    def add_function(self, function: FIRFunction) -> FIRFunction:
        self.functions.append(function)
        return function

    def add_constant(self, constant: GlobalConstant) -> GlobalConstant:
        self.constants.append(constant)
        return constant

    def validate(self) -> None:
        for function in self.functions:
            function.validate()
