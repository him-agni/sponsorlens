import asyncio
from pathlib import Path

import pytest

from app.engine.log import GroupCommitLog, JsonlLogStore


async def test_records_survive_a_reopen(tmp_path: Path) -> None:
    log = GroupCommitLog(JsonlLogStore(tmp_path / "log.jsonl"), interval=0.01)
    log.start()
    await log.append({"type": "done", "job_id": "a"})
    await log.close()

    records = await JsonlLogStore(tmp_path / "log.jsonl").replay()
    assert [r["job_id"] for r in records] == ["a"]
    assert "ts" in records[0]


async def test_concurrent_appends_share_one_write(tmp_path: Path) -> None:
    log = GroupCommitLog(JsonlLogStore(tmp_path / "log.jsonl"), interval=0.05)
    log.start()
    await asyncio.gather(*(log.append({"job_id": str(i)}) for i in range(50)))
    await log.close()

    assert log.metrics.counters["log_records"] == 50
    assert log.metrics.counters["log_flushes"] == 1
    assert len(await JsonlLogStore(tmp_path / "log.jsonl").replay()) == 50


async def test_replaying_twice_gives_the_same_records(tmp_path: Path) -> None:
    store = JsonlLogStore(tmp_path / "log.jsonl")
    await store.append_batch([{"job_id": str(i)} for i in range(5)])
    assert await store.replay() == await store.replay()


async def test_a_half_written_last_line_is_skipped_and_cut_off(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    path.write_bytes(b'{"job_id":"a"}\n{"job_id":"b"}\n{"job_id":"c","sig')
    store = JsonlLogStore(path)

    assert [r["job_id"] for r in await store.replay()] == ["a", "b"]
    assert store.skipped == 1

    await store.append_batch([{"job_id": "d"}])
    assert [r["job_id"] for r in await store.replay()] == ["a", "b", "d"]


async def test_killing_the_writer_mid_buffer_loses_no_record_already_reported_durable(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    log = GroupCommitLog(JsonlLogStore(path), interval=0.05)
    log.start()
    await log.append({"job_id": "reported-done"})

    pending = log.append({"job_id": "still-buffered"})
    log._task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await log._task

    # The buffered record never reached disk, and its waiter is told so rather than left hanging.
    assert [r["job_id"] for r in await JsonlLogStore(path).replay()] == ["reported-done"]
    with pytest.raises(RuntimeError, match="stopped"):
        await pending


async def test_close_flushes_the_buffer(tmp_path: Path) -> None:
    log = GroupCommitLog(JsonlLogStore(tmp_path / "log.jsonl"), interval=10)
    log.start()
    log.append({"job_id": "a"})
    await asyncio.wait_for(log.close(), timeout=1)
    assert len(await JsonlLogStore(tmp_path / "log.jsonl").replay()) == 1
    with pytest.raises(RuntimeError):
        log.append({"job_id": "late"})
