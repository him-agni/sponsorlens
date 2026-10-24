import asyncio

import pytest

from app.engine.queue import BoundedQueue, QueueClosed


async def settle() -> None:
    """Let every ready task run until it blocks."""
    for _ in range(5):
        await asyncio.sleep(0)


async def test_fifo_order() -> None:
    queue = BoundedQueue[int](3)
    for i in range(3):
        await queue.put(i)
    assert [await queue.get() for _ in range(3)] == [0, 1, 2]


async def test_put_blocks_when_full_until_a_get() -> None:
    queue = BoundedQueue[int](2)
    await queue.put(1)
    await queue.put(2)
    blocked = asyncio.create_task(queue.put(3))
    await settle()
    assert not blocked.done()
    assert queue.blocked_puts == 1

    assert await queue.get() == 1
    await settle()
    assert blocked.done()
    assert len(queue) == 2
    assert queue.peak == 2


async def test_get_blocks_when_empty_until_a_put() -> None:
    queue = BoundedQueue[str](1)
    waiting = asyncio.create_task(queue.get())
    await settle()
    assert not waiting.done()
    await queue.put("job")
    assert await waiting == "job"


async def test_close_wakes_blocked_getters_and_putters() -> None:
    queue = BoundedQueue[int](1)
    getter = asyncio.create_task(queue.get())
    await settle()
    await queue.close()
    with pytest.raises(QueueClosed):
        await getter

    full = BoundedQueue[int](1)
    await full.put(1)
    putter = asyncio.create_task(full.put(2))
    await settle()
    await full.close()
    with pytest.raises(QueueClosed):
        await putter


async def test_closed_queue_still_hands_out_queued_items() -> None:
    queue = BoundedQueue[int](3)
    await queue.put(1)
    await queue.put(2)
    await queue.close()
    with pytest.raises(QueueClosed):
        await queue.put(3)
    assert await queue.get() == 1
    assert await queue.get() == 2
    with pytest.raises(QueueClosed):
        await queue.get()


async def test_close_can_discard_pending_items() -> None:
    queue = BoundedQueue[int](3)
    await queue.put(1)
    await queue.put(2)
    assert await queue.close(discard_pending=True) == [1, 2]
    assert len(queue) == 0


async def test_many_producers_and_consumers_lose_nothing() -> None:
    queue = BoundedQueue[int](4)
    received: list[int] = []

    async def consume() -> None:
        while True:
            try:
                received.append(await queue.get())
            except QueueClosed:
                return

    consumers = [asyncio.create_task(consume()) for _ in range(3)]
    await asyncio.gather(*(queue.put(i) for i in range(100)))
    await queue.close()
    await asyncio.wait_for(asyncio.gather(*consumers), timeout=5)
    assert sorted(received) == list(range(100))
    assert queue.peak == 4


def test_capacity_must_be_positive() -> None:
    with pytest.raises(ValueError):
        BoundedQueue[int](0)
