from __future__ import annotations

import asyncio

from sqlalchemy import text

from .db import get_engine


async def wait_for_db(retries: int = 60, delay: float = 1.0) -> None:
    engine = get_engine()
    last_error: Exception | None = None
    for _ in range(retries):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return
        except Exception as exc:  # pragma: no cover - start-up only
            last_error = exc
            await asyncio.sleep(delay)
    if last_error:
        raise last_error


if __name__ == "__main__":
    asyncio.run(wait_for_db())
