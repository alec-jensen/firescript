"""Direct unit tests for firescript/targets.py: host platform/arch mapping,
resolve_target defaults and explicit values, is_supported and
supported_targets_str."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

import targets  # noqa: E402


class _FakeHost:
    """Context manager that fakes platform.system()/machine() on the module."""

    def __init__(self, system=None, machine=None):
        self.system = system
        self.machine = machine

    def __enter__(self):
        mod = targets._host_platform_module
        self._orig = (mod.system, mod.machine)
        if self.system is not None:
            mod.system = lambda: self.system
        if self.machine is not None:
            mod.machine = lambda: self.machine

    def __exit__(self, *exc):
        mod = targets._host_platform_module
        mod.system, mod.machine = self._orig


@t.params([
    ("Windows", targets.Platform.WINDOWS),
    ("Linux", targets.Platform.LINUX),
    ("Darwin", targets.Platform.MACOS),
])
def test_host_platform_mapping(case):
    system, expected = case
    with _FakeHost(system=system):
        t.require_eq(targets.host_platform(), expected)


@t.params([
    ("AMD64", targets.Arch.X86_64),
    ("x86_64", targets.Arch.X86_64),
    ("x86", targets.Arch.I686),
    ("i686", targets.Arch.I686),
    ("i386", targets.Arch.I686),
    ("ARM64", targets.Arch.AARCH64),
    ("arm64", targets.Arch.AARCH64),
    ("aarch64", targets.Arch.AARCH64),
    ("armv7l", targets.Arch.ARMV7),
    ("riscv64", targets.Arch.RISCV64),
    ("riscv32", targets.Arch.RISCV32),
])
def test_host_arch_mapping(case):
    machine, expected = case
    with _FakeHost(machine=machine):
        t.require_eq(targets.host_arch(), expected)


def test_unknown_host_error_messages_name_the_value():
    with _FakeHost(system="Plan9", machine="vax"):
        try:
            targets.host_platform()
            t.require(False, "expected UnknownHostError")
        except targets.UnknownHostError as e:
            t.require("'Plan9'" in str(e), str(e))
        try:
            targets.host_arch()
            t.require(False, "expected UnknownHostError")
        except targets.UnknownHostError as e:
            t.require("'vax'" in str(e), str(e))


def test_resolve_target_defaults_to_host():
    with _FakeHost(system="Linux", machine="aarch64"):
        tgt = targets.resolve_target(None, None)
    t.require_eq(tgt, targets.Target(targets.Platform.LINUX, targets.Arch.AARCH64))


def test_resolve_target_explicit_flags_override_host():
    with _FakeHost(system="Linux", machine="aarch64"):
        tgt = targets.resolve_target("windows", "x86_64")
    t.require_eq(tgt, targets.Target(targets.Platform.WINDOWS, targets.Arch.X86_64))


def test_resolve_target_mixed_explicit_and_host():
    with _FakeHost(system="Darwin", machine="arm64"):
        t.require_eq(targets.resolve_target("bare-metal", None),
                     targets.Target(targets.Platform.BARE_METAL, targets.Arch.AARCH64))
        t.require_eq(targets.resolve_target(None, "riscv32"),
                     targets.Target(targets.Platform.MACOS, targets.Arch.RISCV32))


def test_resolve_target_invalid_values_raise_value_error():
    for plat, arch in (("beos", "x86_64"), ("windows", "z80")):
        try:
            targets.resolve_target(plat, arch)
            t.require(False, f"expected ValueError for {plat}/{arch}")
        except ValueError:
            pass


def test_resolve_target_unknown_host_propagates_only_when_flag_unset():
    with _FakeHost(system="Plan9", machine="vax"):
        t.require_eq(targets.resolve_target("windows", "x86_64"),
                     targets.Target(targets.Platform.WINDOWS, targets.Arch.X86_64))
        try:
            targets.resolve_target(None, "x86_64")
            t.require(False, "expected UnknownHostError")
        except targets.UnknownHostError:
            pass


def test_target_str_and_choices():
    t.require_eq(str(targets.Target(targets.Platform.WINDOWS, targets.Arch.X86_64)), "windows/x86_64")
    t.require_eq(targets.PLATFORM_CHOICES, ["windows", "linux", "macos", "bare-metal"])
    t.require("riscv32" in targets.ARCH_CHOICES)


def test_is_supported():
    t.require(targets.is_supported(targets.Target(targets.Platform.WINDOWS, targets.Arch.X86_64)))
    t.require(not targets.is_supported(targets.Target(targets.Platform.LINUX, targets.Arch.X86_64)))
    t.require(not targets.is_supported(targets.Target(targets.Platform.WINDOWS, targets.Arch.AARCH64)))


def test_supported_targets_str_lists_every_supported_target():
    text = targets.supported_targets_str()
    for tgt in targets.SUPPORTED_TARGETS:
        t.require(str(tgt) in text, text)
    # The compiler's error text and docs name this target; pin it by literal.
    t.require("windows/x86_64" in text.split(", "), text)
