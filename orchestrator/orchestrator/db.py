import os

import asyncpg

DB_URL = os.getenv("CHRONICLE_DB_URL", "postgresql://chronicle:chronicle@postgres:5432/chronicle")

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        url = DB_URL.replace("postgresql+asyncpg://", "postgresql://")
        _pool = await asyncpg.create_pool(url, min_size=1, max_size=10)
    return _pool
