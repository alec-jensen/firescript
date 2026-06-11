"""Ownership tracking for FIR functions.

The semantic analyzer proves moves/borrows/drops are valid before FIR is
built; the OwnershipMap preserves its conclusions on the IR so later
passes (and lowering) can consume them without re-running the analysis.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from fir.ir_node import FIRValue


class OwnershipState(Enum):
    """State of a binding in ownership tracking."""

    VALID = "valid"  # Binding can be used
    MOVED = "moved"  # Ownership transferred; binding is invalid
    MAYBE_MOVED = "maybe_moved"  # Moved on some control-flow paths
    BORROWED = "borrowed"  # Currently borrowed


class OwnershipMap:
    """Tracks the ownership state of named bindings in a function."""

    def __init__(self):
        self.binding_states: dict[str, OwnershipState] = {}
        # Move instruction value -> name of the binding it invalidated
        self.move_invalidations: dict["FIRValue", str] = {}
        # Binding -> (start block id, end block id) of its active borrow
        self.borrow_lifetimes: dict[str, tuple[str, str]] = {}

    def declare(self, name: str) -> None:
        self.binding_states[name] = OwnershipState.VALID

    def record_move(self, source_var: str, move_value: Optional["FIRValue"] = None) -> None:
        self.binding_states[source_var] = OwnershipState.MOVED
        if move_value is not None:
            self.move_invalidations[move_value] = source_var

    def record_maybe_move(self, source_var: str) -> None:
        self.binding_states[source_var] = OwnershipState.MAYBE_MOVED

    def record_borrow(self, source_var: str, start_block: str, end_block: str) -> None:
        self.binding_states[source_var] = OwnershipState.BORROWED
        self.borrow_lifetimes[source_var] = (start_block, end_block)

    def release_borrow(self, source_var: str) -> None:
        if self.binding_states.get(source_var) == OwnershipState.BORROWED:
            self.binding_states[source_var] = OwnershipState.VALID
        self.borrow_lifetimes.pop(source_var, None)

    def state_of(self, var: str) -> Optional[OwnershipState]:
        return self.binding_states.get(var)

    def is_valid(self, var: str) -> bool:
        return self.binding_states.get(var) == OwnershipState.VALID
