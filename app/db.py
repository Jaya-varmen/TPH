from __future__ import annotations

from functools import lru_cache
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy import text

from .config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(settings.database_url, pool_pre_ping=True)


async def fetch_scalar(stmt, params: dict | None = None) -> int:
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(stmt, params or {})
        value = result.scalar_one_or_none()
        return 0 if value is None else int(value)


async def execute_sql(sql: str) -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text(sql))
