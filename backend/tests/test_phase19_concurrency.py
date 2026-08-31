"""
Phase 19 Test Suite: Distributed Concurrency Safety.
Tests exclusive entity lock acquisition and contention handling.
"""

import pytest
import asyncio
from fastapi import HTTPException
from app.core.concurrency import concurrency_guard


@pytest.mark.asyncio
async def test_concurrency_guard_sequential_locks():
    async with concurrency_guard.acquire_lock("test_entity", "ent-100"):
        res = "first_acquired"
    assert res == "first_acquired"

    async with concurrency_guard.acquire_lock("test_entity", "ent-100"):
        res_second = "second_acquired"
    assert res_second == "second_acquired"


@pytest.mark.asyncio
async def test_concurrency_guard_timeout_on_contention():
    # Hold lock in task 1
    lock_held = asyncio.Event()
    finish_task = asyncio.Event()

    async def holder():
        async with concurrency_guard.acquire_lock("test_domain", "item-1"):
            lock_held.set()
            await finish_task.wait()

    t = asyncio.create_task(holder())
    await lock_held.wait()

    # Try acquiring same lock in task 2 with very short timeout -> raises HTTPException 409
    with pytest.raises(HTTPException) as excinfo:
        async with concurrency_guard.acquire_lock("test_domain", "item-1", timeout_seconds=0.1):
            pass

    assert excinfo.value.status_code == 409

    finish_task.set()
    await t
