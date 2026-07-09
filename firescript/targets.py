"""Compilation target selection: platform (OS) x architecture.

The choices here mirror the support matrix in README.md's "Platforms"
table exactly, so every combination documented there is a valid
--platform/--arch pair on the CLI, even before the backend actually
implements it. `SUPPORTED_TARGETS` is the much smaller set of combinations
the backend can actually build today; anything else fails with a clear
compiler error naming what *is* supported, rather than argparse's generic
"invalid choice" (which would only reject values absent from the README
matrix, not merely-unimplemented ones).
"""

from __future__ import annotations

import platform as _host_platform_module
from dataclasses import dataclass
from enum import Enum


class Platform(Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    BARE_METAL = "bare-metal"


class Arch(Enum):
    X86_64 = "x86_64"
    I686 = "i686"
    AARCH64 = "aarch64"
    ARMV7 = "armv7"
    RISCV64 = "riscv64"
    RISCV32 = "riscv32"


PLATFORM_CHOICES = [p.value for p in Platform]
ARCH_CHOICES = [a.value for a in Arch]


@dataclass(frozen=True)
class Target:
    platform: Platform
    arch: Arch

    def __str__(self) -> str:
        return f"{self.platform.value}/{self.arch.value}"


# Keep in sync with the checkmarks in README.md's Platforms table.
SUPPORTED_TARGETS: frozenset[Target] = frozenset({
    Target(Platform.WINDOWS, Arch.X86_64),
})


class UnknownHostError(Exception):
    """Raised when a --platform/--arch flag is left unset and the host
    machine can't be mapped onto one of our Platform/Arch values."""


_HOST_PLATFORM_MAP = {
    "Windows": Platform.WINDOWS,
    "Linux": Platform.LINUX,
    "Darwin": Platform.MACOS,
}

# platform.machine() spellings vary by OS (e.g. Windows reports "AMD64",
# Linux/macOS report "x86_64"), so both are mapped.
_HOST_ARCH_MAP = {
    "AMD64": Arch.X86_64,
    "x86_64": Arch.X86_64,
    "x86": Arch.I686,
    "i686": Arch.I686,
    "i386": Arch.I686,
    "ARM64": Arch.AARCH64,
    "arm64": Arch.AARCH64,
    "aarch64": Arch.AARCH64,
    "armv7l": Arch.ARMV7,
    "riscv64": Arch.RISCV64,
    "riscv32": Arch.RISCV32,
}


def host_platform() -> Platform:
    system = _host_platform_module.system()
    try:
        return _HOST_PLATFORM_MAP[system]
    except KeyError:
        raise UnknownHostError(f"Unrecognized host OS: {system!r}") from None


def host_arch() -> Arch:
    machine = _host_platform_module.machine()
    try:
        return _HOST_ARCH_MAP[machine]
    except KeyError:
        raise UnknownHostError(f"Unrecognized host architecture: {machine!r}") from None


def resolve_target(platform_str: str | None, arch_str: str | None) -> Target:
    """Resolve --platform/--arch CLI values to a Target.

    An unset flag defaults to the corresponding property of the host
    machine (cross-compilation only kicks in when the user asks for it
    explicitly).
    """
    target_platform = Platform(platform_str) if platform_str else host_platform()
    target_arch = Arch(arch_str) if arch_str else host_arch()
    return Target(target_platform, target_arch)


def is_supported(target: Target) -> bool:
    return target in SUPPORTED_TARGETS


def supported_targets_str() -> str:
    return ", ".join(str(t) for t in sorted(SUPPORTED_TARGETS, key=str))
