"""Self-tests for harness.seeds (spec sec.8, sec.11 phase 1)."""
from __future__ import annotations

from harness import pyunit as t
from harness import seeds


def test_derive_is_deterministic():
    a = seeds.derive("deadbeef00000000", "determinism", "sample")
    b = seeds.derive("deadbeef00000000", "determinism", "sample")
    t.require_eq(a, b)


def test_derive_differs_by_label():
    a = seeds.derive("deadbeef00000000", "a")
    b = seeds.derive("deadbeef00000000", "b")
    t.require(a != b)


def test_derive_differs_by_master_seed():
    a = seeds.derive("deadbeef00000000", "x")
    b = seeds.derive("00000000deadbeef", "x")
    t.require(a != b)


def test_parse_master_seed_accepts_0x_prefix():
    t.require_eq(seeds.parse_master_seed("0xABCDEF"), "abcdef")
    t.require_eq(seeds.parse_master_seed("abcdef"), "abcdef")


def test_pick_is_deterministic_and_reproducible():
    population = list(range(100))
    a = seeds.pick("deadbeef00000000", "determinism", population, 5)
    b = seeds.pick("deadbeef00000000", "determinism", population, 5)
    t.require_eq(a, b)
    t.require_eq(len(a), 5)


def test_pick_clamps_k_to_population_size():
    population = [1, 2, 3]
    picked = seeds.pick("deadbeef00000000", "x", population, 10)
    t.require_eq(len(picked), 3)


def test_rng_for_never_touches_global_random_state():
    import random

    before = random.getstate()
    seeds.rng_for("deadbeef00000000", "x").random()
    after = random.getstate()
    t.require(before == after)
