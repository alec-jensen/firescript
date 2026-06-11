"""FIR type system.

FIR types preserve the firescript-level view of a value: fixed-width
numerics, strings, arrays, user classes, generic instances, and
generators. Value category ("copyable" vs "owned") is carried on every
type so ownership passes do not need to consult the type environment.
"""

from __future__ import annotations

from typing import Optional

# Built-in types whose values are copied on assignment / call.
COPYABLE_BUILTINS: frozenset[str] = frozenset(
    {
        "int8",
        "int16",
        "int32",
        "int64",
        "uint8",
        "uint16",
        "uint32",
        "uint64",
        "float32",
        "float64",
        "float128",
        "bool",
        "char",
        "void",
    }
)


class FIRType:
    """Base class for all FIR types."""

    category: str = "owned"

    def is_owned(self) -> bool:
        return self.category == "owned"

    def is_copyable(self) -> bool:
        return self.category == "copyable"

    def render(self) -> str:
        """Deterministic textual form used in FIR dumps."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.render()}>"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, FIRType) and self.render() == other.render()

    def __hash__(self) -> int:
        return hash(self.render())


class SimpleType(FIRType):
    """Scalar or named type: int32, string, bool, or a user class."""

    def __init__(
        self,
        name: str,
        category: str = "owned",
        nullable: bool = False,
        metadata: Optional[dict] = None,
    ):
        self.name = name
        self.category = category
        self.nullable = nullable
        self.metadata = metadata or {}

    def render(self) -> str:
        return f"{self.name}?" if self.nullable else self.name


class ArrayType(FIRType):
    """Fixed-size array type: T[N] (or T[] when the size is unknown)."""

    category = "owned"

    def __init__(self, element_type: FIRType, size: Optional[int] = None):
        self.element_type = element_type
        self.size = size

    def render(self) -> str:
        size_text = "" if self.size is None else str(self.size)
        return f"{self.element_type.render()}[{size_text}]"


class GenericInstanceType(FIRType):
    """A generic class applied to type arguments: Box<int32>."""

    category = "owned"

    def __init__(self, base_name: str, type_args: list[FIRType]):
        self.base_name = base_name
        self.type_args = type_args

    def render(self) -> str:
        args = ", ".join(t.render() for t in self.type_args)
        return f"{self.base_name}<{args}>"


class GeneratorType(FIRType):
    """generator<T>: a lazy sequence of T values."""

    category = "owned"

    def __init__(self, element_type: FIRType):
        self.element_type = element_type

    def render(self) -> str:
        return f"generator<{self.element_type.render()}>"


class FunctionType(FIRType):
    """Function type: (T1, T2) -> R. Used for signatures, not values."""

    category = "copyable"

    def __init__(
        self,
        param_types: list[FIRType],
        return_type: Optional[FIRType] = None,
        param_borrowing: Optional[list[bool]] = None,
    ):
        self.param_types = param_types
        self.return_type = return_type
        self.param_borrowing = param_borrowing or [False] * len(param_types)

    def render(self) -> str:
        params = ", ".join(t.render() for t in self.param_types)
        ret = self.return_type.render() if self.return_type else "void"
        return f"({params}) -> {ret}"


def make_simple(name: str, nullable: bool = False, metadata: Optional[dict] = None) -> SimpleType:
    """Create a SimpleType, inferring value category for built-in types.

    Non-builtin names default to "owned"; the AST->FIR converter overrides
    the category for user classes declared `copyable`.
    """
    category = "copyable" if name in COPYABLE_BUILTINS else "owned"
    return SimpleType(name, category=category, nullable=nullable, metadata=metadata)


VOID = SimpleType("void", category="copyable")
