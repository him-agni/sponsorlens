from collections import Counter

import pytest

from app.engine.ring import HashRing

COMPANIES = [f"company-{i}" for i in range(2000)]


def test_the_same_key_always_lands_on_the_same_shard() -> None:
    assert HashRing(4).shard_for("stripe") == HashRing(4).shard_for("stripe")


def test_adding_a_shard_moves_about_one_in_n_keys() -> None:
    ring = HashRing(4)
    before = {c: ring.shard_for(c) for c in COMPANIES}
    ring.add("4")
    moved = [c for c in COMPANIES if ring.shard_for(c) != before[c]]

    # With 5 shards, the new one should take about 1/5 of the keys, and every moved key goes to it.
    assert 0.12 < len(moved) / len(COMPANIES) < 0.28
    assert all(ring.shard_for(c) == "4" for c in moved)


def test_modulo_hashing_would_move_most_keys() -> None:
    """The baseline the ring is measured against."""
    moved = sum(hash(c) % 4 != hash(c) % 5 for c in COMPANIES)
    assert moved / len(COMPANIES) > 0.7


def test_virtual_nodes_spread_keys_evenly() -> None:
    counts = Counter(HashRing(4, vnodes=64).shard_for(c) for c in COMPANIES)
    assert set(counts) == {"0", "1", "2", "3"}
    assert max(counts.values()) / min(counts.values()) < 1.6


def test_a_ring_needs_a_shard() -> None:
    with pytest.raises(ValueError):
        HashRing([])
