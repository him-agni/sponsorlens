import asyncio
from collections import deque


class QueueClosed(Exception):
    """Raised by put on a closed queue, and by get once a closed queue is empty."""


class BoundedQueue[T]:
    """A FIFO queue with a fixed capacity, written by hand rather than using asyncio.Queue.

    Two conditions share one lock. put waits on not_full while the queue is at capacity, which is
    the backpressure: a fast producer slows to the pace of the workers. get waits on not_empty.
    close stops intake and wakes every waiter; items already queued can still be taken.
    """

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self.capacity = capacity
        self.peak = 0
        self.blocked_puts = 0
        self._items: deque[T] = deque()
        self._closed = False
        lock = asyncio.Lock()
        self._not_full = asyncio.Condition(lock)
        self._not_empty = asyncio.Condition(lock)

    def __len__(self) -> int:
        return len(self._items)

    @property
    def closed(self) -> bool:
        return self._closed

    async def put(self, item: T) -> None:
        async with self._not_full:
            if len(self._items) >= self.capacity:
                self.blocked_puts += 1
            await self._not_full.wait_for(lambda: self._closed or len(self._items) < self.capacity)
            if self._closed:
                raise QueueClosed
            self._items.append(item)
            self.peak = max(self.peak, len(self._items))
            self._not_empty.notify()

    async def get(self) -> T:
        async with self._not_empty:
            await self._not_empty.wait_for(lambda: self._closed or self._items)
            if not self._items:
                raise QueueClosed
            item = self._items.popleft()
            self._not_full.notify()
            return item

    async def close(self, discard_pending: bool = False) -> list[T]:
        """Stop intake. With discard_pending, also empty the queue and return what was in it."""
        async with self._not_full:
            self._closed = True
            pending = list(self._items) if discard_pending else []
            if discard_pending:
                self._items.clear()
            self._not_full.notify_all()
            self._not_empty.notify_all()
            return pending
