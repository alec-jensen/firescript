"""Deterministic textual serialization of FLIR modules."""

from __future__ import annotations

from flir.ir import FLIRFunction, FLIRModule, FLIRStruct, FValue


def dump_flir_module(module: FLIRModule) -> str:
    lines: list[str] = [f"flir module {module.name}"]
    if module.entry_function:
        lines.append(f"entry @{module.entry_function}")

    for symbol, (dll, ret, params) in sorted(module.externs.items()):
        params_text = ", ".join(p.render() for p in params)
        lines.append(f'extern @{symbol}({params_text}) -> {ret.render()} from "{dll}"')

    for name, gtype, literal in module.globals:
        lines.append("")
        lines.append(f"global {name}: {gtype.render()} = {literal}")

    for name, gtype in module.mutable_globals:
        lines.append("")
        lines.append(f"global mut {name}: {gtype.render()} = 0")

    for struct in module.structs:
        lines.append("")
        lines.extend(_format_struct(struct))

    for function in module.functions:
        lines.append("")
        lines.extend(_format_function(function))

    return "\n".join(lines) + "\n"


def _format_struct(struct: FLIRStruct) -> list[str]:
    lines = [f"struct {struct.name} {{ size: {struct.size}, align: {struct.align}, kind: {struct.kind}"]
    for name, field_type, offset in struct.fields:
        lines.append(f"  {name}: {field_type.render()} @ {offset}")
    lines.append("}")
    return lines


def _format_function(function: FLIRFunction) -> list[str]:
    value_names: dict[int, str] = {}
    counter = 0
    for block in function.blocks:
        for inst in block.instructions:
            if inst.has_result():
                value_names[id(inst)] = f"%{counter}"
                counter += 1

    def resolve(value: FValue) -> str:
        name = value_names.get(id(value.instruction))
        if name is None:
            raise ValueError(
                f"FLIR value from {value.instruction.opcode} not in function {function.name}"
            )
        return name

    params = ", ".join(f"{name}: {ptype.render()}" for name, ptype in function.params)
    lines = [f"func @{function.name}({params}) -> {function.return_type.render()} {{"]

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

    lines.append("}")
    return lines
