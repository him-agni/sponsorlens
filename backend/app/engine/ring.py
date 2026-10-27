import bisect
import hashlib


def _hash(value: str) -> int:
    """A stable 64-bit hash. Python's hash() is salted per process, so it cannot place keys across restarts."""
    return int.from_bytes(hashlib.blake2b(value.encode(), digest_size=8).digest(), "big")


class HashRing:
    """Consistent hashing with virtual nodes: maps a key (a company) to a shard.

    Each shard owns many points on a ring of 64-bit hashes; a key belongs to the first point at or
    after its own hash. Adding a shard takes over only the arcs before its new points, so about 1/N
    of keys move, where a plain hash(key) % N would move almost all of them. Virtual nodes spread
    each shard over many small arcs, which evens out the load.
    """

    def __init__(self, shards: list[str] | int, vnodes: int = 64) -> None:
        if isinstance(shards, int):
            shards = [str(i) for i in range(shards)]
        if not shards:
            raise ValueError("a ring needs at least one shard")
        self.vnodes = vnodes
        self._points: list[int] = []
        self._owners: dict[int, str] = {}
        for shard in shards:
            self.add(shard)

    @property
    def shards(self) -> list[str]:
        return sorted(set(self._owners.values()))

    def add(self, shard: str) -> None:
        for i in range(self.vnodes):
            point = _hash(f"{shard}#{i}")
            if point not in self._owners:
                bisect.insort(self._points, point)
                self._owners[point] = shard

    def shard_for(self, key: str) -> str:
        index = bisect.bisect_left(self._points, _hash(key))
        return self._owners[self._points[index % len(self._points)]]
