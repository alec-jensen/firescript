"""Kind plugin registry (spec sec.3.3).

Adding a future kind = adding one module here + registering it below. The
core (discovery driver, scheduler, reporter, CLI) must never need edits for
a new kind. This is the load-bearing design property of the harness --
review any change against it.
"""
from __future__ import annotations

_REGISTRY: dict = {}


def register(kind_cls) -> None:
    _REGISTRY[kind_cls.name] = kind_cls


def get(name: str):
    if name not in _REGISTRY:
        raise KeyError(f"unknown test kind '{name}'")
    return _REGISTRY[name]


def all_kinds() -> dict:
    return dict(_REGISTRY)


def _register_builtin_kinds() -> None:
    from harness.kinds import (
        run as run_kind,
        compile_fail as compile_fail_kind,
        python_unit as python_unit_kind,
        snapshot as snapshot_kind,
        determinism as determinism_kind,
        bootstrap as bootstrap_kind,
    )

    register(run_kind.RunKind)
    register(compile_fail_kind.CompileFailKind)
    register(python_unit_kind.PythonUnitKind)
    register(snapshot_kind.SnapshotKind)
    register(determinism_kind.DeterminismKind)
    register(bootstrap_kind.BootstrapKind)


_register_builtin_kinds()
