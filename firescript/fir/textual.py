"""Deterministic textual serialization of FIR modules.

Dumping the same module twice always yields byte-identical text: value
numbers are assigned in (block order, instruction order) within each
function, and module items are emitted in insertion order (which the
AST->FIR converter keeps equal to source order).

Example output:

    module firescript

    type Point copyable {
      x: int32
      y: int32
    }

    function main() -> void {
      block_0:
        %0 = IntLiteral(10, int32)
        Drop(%0)
        Return()
    }
"""

from __future__ import annotations

from fir.ir_module import FIRFunction, FIRModule, GlobalConstant, TypeDef
from fir.ir_node import FIRValue, ParamValue, Value


def dump_module(module: FIRModule) -> str:
    lines: list[str] = [f"module {module.name}"]

    for constant in module.constants:
        lines.append("")
        lines.append(_format_constant(constant))

    for type_def in module.types:
        lines.append("")
        lines.extend(_format_type(type_def))

    for function in module.functions:
        lines.append("")
        lines.extend(_format_function(function))

    return "\n".join(lines) + "\n"


def _format_constant(constant: GlobalConstant) -> str:
    return f"const {constant.name}: {constant.const_type.render()} = {constant.literal_text}"


def _format_type(type_def: TypeDef) -> list[str]:
    generics = ""
    if type_def.generic_params:
        generics = "<" + ", ".join(type_def.generic_params) + ">"
    base = f" : {type_def.base}" if type_def.base else ""
    lines = [f"type {type_def.name}{generics} {type_def.category}{base} {{"]
    for field_name, field_type in type_def.fields:
        lines.append(f"  {field_name}: {field_type.render()}")
    lines.append("}")
    return lines


def _format_function(function: FIRFunction) -> list[str]:
    # Assign deterministic %N names to instruction results.
    value_names: dict[int, str] = {}
    counter = 0
    for block in function.blocks:
        for inst in block.instructions:
            if inst.has_result():
                value_names[id(inst)] = f"%{counter}"
                counter += 1

    def resolve(value: Value) -> str:
        if isinstance(value, ParamValue):
            return value.name
        if isinstance(value, FIRValue):
            name = value_names.get(id(value.instruction))
            if name is None:
                raise ValueError(
                    f"value produced by {value.instruction.opcode} is not in function {function.name}"
                )
            return name
        raise TypeError(f"unsupported operand kind: {type(value).__name__}")

    generics = ""
    if function.generic_params:
        generics = "<" + ", ".join(function.generic_params) + ">"

    # Render borrow modes explicitly: own -> "name: T", borrow -> "name: &T",
    # borrow_mut -> "name: &mut T".
    rendered_params = []
    for (name, ptype), mode in zip(function.params, function.param_modes):
        if mode == "borrow":
            rendered_params.append(f"{name}: &{ptype.render()}")
        elif mode == "borrow_mut":
            rendered_params.append(f"{name}: &mut {ptype.render()}")
        else:
            rendered_params.append(f"{name}: {ptype.render()}")
    params = ", ".join(rendered_params)

    ret = function.return_type.render() if function.return_type else "void"
    keyword = "generator" if function.is_generator else "function"
    lines = [f"{keyword}{generics} {function.name}({params}) -> {ret} {{"]

    first = True
    for block in function.blocks:
        if not first:
            lines.append("")
        first = False
        lines.append(f"  {block.id}:")
        for inst in block.instructions:
            text = inst.format(resolve)
            if inst.has_result():
                lines.append(f"    {value_names[id(inst)]} = {text}")
            else:
                lines.append(f"    {text}")
        if block.terminator is not None:
            lines.append(f"    {block.terminator.format(resolve)}")

    lines.append("}")
    return lines
