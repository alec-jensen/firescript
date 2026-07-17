"""Registry of `@builtin_method`-decorated firescript functions.

Stdlib authors add a built-in dot-method on a primitive receiver type
(`string`, `array`) by writing a plain firescript function under
`std/internal/` and tagging it with `@builtin_method(family, name, **flags)`.
This module scans that directory once per process, builds a lookup table
from (family, method name) to the backing function's signature, and is
consulted by `parser/type_system.py` (type-checking) and `ast_to_fir.py`
(FIR call emission) instead of hand-written per-method dispatch tables.

See docs/internal/development/builtin_methods.md for the authoring contract.
"""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field
from typing import Optional

from enums import NodeTypes


@dataclass(frozen=True)
class BuiltinMethodSpec:
    receiver_family: str                   # "string" | "array" (open-ended)
    method_name: str
    fir_name: str                          # backing function name, e.g. "fs_rt_str_upper"
    type_params: tuple[str, ...]           # () for string methods, ("T",) for array methods
    public_param_types: tuple[str, ...]    # non-receiver, non-length param types (may be "T")
    public_param_modes: tuple[str, ...]    # "own" | "borrow" | "borrow_mut", parallel to the above
    receiver_mode: str                     # "own" | "borrow" | "borrow_mut"
    return_type: str                       # may be "T" for a type-parameterized return
    needs_length: bool = False             # auto-inject the array length as the 2nd argument
    const_fold: bool = False               # eligible for a compile-time constant instead of a call
    source_file: str = ""


@dataclass
class BuiltinMethodRegistry:
    by_family: dict[str, dict[str, BuiltinMethodSpec]] = field(default_factory=dict)

    def lookup(self, family: str, method_name: str) -> Optional[BuiltinMethodSpec]:
        return self.by_family.get(family, {}).get(method_name)

    def methods_for(self, family: str) -> dict[str, BuiltinMethodSpec]:
        return self.by_family.get(family, {})


class BuiltinMethodRegistryError(RuntimeError):
    """Raised when std/internal/*.fire contains an invalid @builtin_method declaration."""


_PARSED_FILE_CACHE: dict[str, tuple] = {}


def parse_internal_file_cached(path: str):
    """Lex+parse a std/internal/*.fire file once per process, cached by
    path, for signature-harvesting purposes only (this module's own
    @builtin_method decorator scan, and main.py's cross-file signature
    pre-scan) -- never for a real compile.

    Parsed with `defer_undefined_identifiers=True` unconditionally: a
    std/internal/ file routinely calls a function defined in a sibling
    file (e.g. a string primitive calling into alloc.fire's allocator)
    with no import connecting them, and a bare (non-expression-context)
    call to a not-yet-registered function name would otherwise be rejected
    at parse time by parse_function_call's "is not defined" check
    (parser/statements.py). That's fine here since only each declaration's
    own shape (name/params/decorators/return type) is read back out --
    whether a file's body actually type-checks against its sibling calls
    is decided later, by the real (seeded) compile in main.py.
    """
    if path not in _PARSED_FILE_CACHE:
        from lexer import Lexer
        from parser import Parser
        from utils.file_utils import safe_relpath

        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
        rel = safe_relpath(path)
        tokens = Lexer(source).tokenize()
        parser_instance = Parser(tokens, source, rel, defer_undefined_identifiers=True)
        ast = parser_instance.parse()
        _PARSED_FILE_CACHE[path] = (ast, parser_instance)
    return _PARSED_FILE_CACHE[path]


def _param_type_str(param) -> str:
    t = param.var_type or ""
    if getattr(param, "is_array", False):
        t += "[]"
    return t


def _param_mode(param) -> str:
    if getattr(param, "is_mutable_borrow", False):
        return "borrow_mut"
    if getattr(param, "is_borrowed", False):
        return "borrow"
    return "own"


def _spec_from_function_def(func_node, decorator: dict, source_file: str) -> BuiltinMethodSpec:
    positional = decorator["positional"]
    kwargs = decorator["kwargs"]
    if len(positional) != 2:
        raise BuiltinMethodRegistryError(
            f"{source_file}: @builtin_method on '{func_node.name}' requires exactly 2 "
            f"positional arguments (family, method_name), got {positional!r}"
        )
    family, method_name = positional
    needs_length = bool(kwargs.get("needs_length", False))
    const_fold = bool(kwargs.get("const_fold", False))

    params = [c for c in func_node.children if c.node_type == NodeTypes.PARAMETER]
    if not params:
        raise BuiltinMethodRegistryError(
            f"{source_file}: @builtin_method function '{func_node.name}' must declare "
            f"a receiver parameter"
        )
    receiver_param = params[0]
    rest = params[1:]
    if needs_length:
        if not rest:
            raise BuiltinMethodRegistryError(
                f"{source_file}: @builtin_method(needs_length=true) function "
                f"'{func_node.name}' must declare a length parameter after the receiver"
            )
        rest = rest[1:]

    return BuiltinMethodSpec(
        receiver_family=family,
        method_name=method_name,
        fir_name=func_node.name,
        type_params=tuple(getattr(func_node, "type_params", None) or []),
        public_param_types=tuple(_param_type_str(p) for p in rest),
        public_param_modes=tuple(_param_mode(p) for p in rest),
        receiver_mode=_param_mode(receiver_param),
        return_type=func_node.return_type or "void",
        needs_length=needs_length,
        const_fold=const_fold,
        source_file=source_file,
    )


def _scan_internal_dir() -> BuiltinMethodRegistry:
    internal_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "std", "internal")
    # sorted() for deterministic scan order (see CLAUDE.md determinism rule).
    files = sorted(glob.glob(os.path.join(internal_dir, "*.fire")))
    registry = BuiltinMethodRegistry()
    for path in files:
        ast, parser_instance = parse_internal_file_cached(path)
        if parser_instance.errors:
            raise BuiltinMethodRegistryError(
                f"{path} failed to parse while scanning for @builtin_method: "
                f"{len(parser_instance.errors)} error(s)"
            )
        for child in ast.children:
            if child.node_type != NodeTypes.FUNCTION_DEFINITION:
                continue
            decorators = getattr(child, "decorators", None) or []
            for dec in decorators:
                if dec["name"] != "builtin_method":
                    continue
                if "enable_builtin_methods" not in parser_instance.directives:
                    raise BuiltinMethodRegistryError(
                        f"{path}: function '{child.name}' uses @builtin_method without "
                        f"'directive enable_builtin_methods;' in this file"
                    )
                spec = _spec_from_function_def(child, dec, path)
                registry.by_family.setdefault(spec.receiver_family, {})[spec.method_name] = spec
    return registry


_REGISTRY_CACHE: Optional[BuiltinMethodRegistry] = None
_BUILDING = False


def get_builtin_method_registry() -> BuiltinMethodRegistry:
    """Return the process-wide, deterministically-built builtin-method
    registry, scanning firescript/std/internal/*.fire on first use."""
    global _REGISTRY_CACHE, _BUILDING
    if _REGISTRY_CACHE is not None:
        return _REGISTRY_CACHE
    if _BUILDING:
        raise BuiltinMethodRegistryError(
            "builtin-method registry construction re-entered -- a std/internal/*.fire "
            "file appears to call a @builtin_method-dispatched method on itself, which "
            "that directory's own house rule forbids"
        )
    _BUILDING = True
    try:
        _REGISTRY_CACHE = _scan_internal_dir()
    finally:
        _BUILDING = False
    return _REGISTRY_CACHE
