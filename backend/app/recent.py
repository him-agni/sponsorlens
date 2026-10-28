from collections import OrderedDict


class Recent[K, V]:
    """A small least-recently-used map for per-process caches, so a public server's memory can't grow forever.

    Not thread-safe: it is only used from the event loop. The engine's sharded AnalysisCache is the
    one that adds locking and single-flight.
    """

    def __init__(self, capacity: int = 1024) -> None:
        self.capacity = capacity
        self._items: OrderedDict[K, V] = OrderedDict()

    def get(self, key: K) -> V | None:
        if key not in self._items:
            return None
        self._items.move_to_end(key)
        return self._items[key]

    def put(self, key: K, value: V) -> None:
        self._items[key] = value
        self._items.move_to_end(key)
        if len(self._items) > self.capacity:
            self._items.popitem(last=False)

    def __contains__(self, key: K) -> bool:
        return key in self._items

    def __len__(self) -> int:
        return len(self._items)
