from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import text

from .db import get_engine


async def run_migrations() -> None:
    migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
    sql_files = sorted(migrations_dir.glob("*.sql"))

    if not sql_files:
        return

    engine = get_engine()
    async with engine.begin() as conn:
        for path in sql_files:
            sql = path.read_text(encoding="utf-8")
            for statement in sql.split(";"):
                stmt = statement.strip()
                if stmt:
                    await conn.execute(text(stmt))


if __name__ == "__main__":
    asyncio.run(run_migrations())
