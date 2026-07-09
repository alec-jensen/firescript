"""Single source of randomness for the whole harness (spec sec.8).

No random.random() / random.seed() global state anywhere in the harness;
always random.Random(derive(...)) instances.
"""
from __future__ import annotations

import hashlib
import random
import secrets


def new_master_seed() -> str:
    """A fresh random master seed, hex-encoded (no 0x prefix)."""
    return secrets.token_hex(8)


def parse_master_seed(value: str) -> str:
    """Normalize a user-supplied --seed value to the canonical hex form."""
    v = value.lower()
    if v.startswith("0x"):
        v = v[2:]
    int(v, 16)  # validate
    return v


def format_seed(master_hex: str) -> str:
    return f"0x{master_hex}"


def derive(master_hex: str, *labels: str) -> int:
    """Derive a stable 64-bit integer seed from the master seed and labels."""
    h = hashlib.sha256()
    h.update(bytes.fromhex(master_hex))
    for label in labels:
        h.update(b"\0")
        h.update(label.encode("utf-8"))
    digest = h.digest()
    return int.from_bytes(digest[:8], "big")


def rng_for(master_hex: str, *labels: str) -> random.Random:
    """A Random instance seeded deterministically from the master seed + labels."""
    return random.Random(derive(master_hex, *labels))


def pick(master_hex: str, purpose: str, population: list, k: int) -> list:
    """Deterministically pick k items from population, seeded by purpose."""
    rng = rng_for(master_hex, purpose)
    k = max(0, min(k, len(population)))
    return rng.sample(population, k)
