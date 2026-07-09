"""Compiler flag matrix engine (spec sec.7). Today the compiler has no
optimization levels, so the registry has exactly one real axis-less cell
("default"). This module and its expansion/sampling logic are fully
implemented and exercised by the harness's own tests via a fake axis, so
that adding a real axis later (e.g. -O1/-O2) is a one-line change to AXES.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from harness import seeds


@dataclass(frozen=True)
class Axis:
    name: str
    variants: dict  # variant_name -> list[str] (extra compiler flags)


# The only place to touch when -O1/-O2 (or other axes) land.
AXES: list[Axis] = []


@dataclass(frozen=True)
class Cell:
    id: str
    flags: list = field(default_factory=list)


DEFAULT_CELL = Cell(id="default", flags=[])


def all_cells(axes: list[Axis] | None = None) -> list[Cell]:
    """Full cartesian product of all axis variants. With zero axes, this is
    just [DEFAULT_CELL]."""
    axes = AXES if axes is None else axes
    if not axes:
        return [DEFAULT_CELL]
    cells: list[Cell] = [Cell(id="default", flags=[])]
    for axis in axes:
        new_cells = []
        for cell in cells:
            for variant_name, variant_flags in axis.variants.items():
                cell_id = variant_name if cell.id == "default" else f"{cell.id}+{variant_name}"
                new_cells.append(Cell(id=cell_id, flags=cell.flags + variant_flags))
        cells = new_cells
    return cells


def select_cells(mode: str, master_seed: str, test_key: str, axes: list[Axis] | None = None) -> list[Cell]:
    """Cells to run for one test, given --matrix mode.

    - quick: [default] only.
    - full: full cartesian product.
    - sample=K: default cell + K additional cells chosen per-test (seeded).
    """
    cells = all_cells(axes)
    default = next((c for c in cells if c.id == "default"), cells[0])

    if mode == "quick":
        return [default]
    if mode == "full":
        return cells
    if mode.startswith("sample="):
        k = int(mode.split("=", 1)[1])
        others = [c for c in cells if c.id != default.id]
        picked = seeds.pick(master_seed, f"matrix:{test_key}", others, k)
        return [default] + picked
    raise ValueError(f"unknown matrix mode '{mode}'")
