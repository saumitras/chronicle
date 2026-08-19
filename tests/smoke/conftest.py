import os

import pytest
import httpx
import asyncio

GATEWAY = os.getenv("SMOKE_GATEWAY_URL", "http://localhost:8000")
ALERT_GEN = os.getenv("SMOKE_ALERT_GEN_URL", "http://localhost:8001")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def client():
    async with httpx.AsyncClient(base_url=GATEWAY, timeout=30) as c:
        yield c


@pytest.fixture(scope="session")
async def alert_client():
    async with httpx.AsyncClient(base_url=ALERT_GEN, timeout=30) as c:
        yield c


async def wait_for(fn, timeout=60, interval=2):
    """Poll fn() until it returns truthy or timeout."""
    for _ in range(timeout // interval):
        result = await fn()
        if result:
            return result
        await asyncio.sleep(interval)
    raise TimeoutError(f"Condition not met within {timeout}s")
