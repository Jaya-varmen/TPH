from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Iterable

from dateutil.parser import isoparse
from sqlalchemy import select, func

from .config import get_settings
from .db import get_engine
from .models import videos, video_snapshots


def chunked(items: list[dict], size: int) -> Iterable[list[dict]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


async def load_data() -> None:
    settings = get_settings()
    json_path = Path(settings.data_json_path)

    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    engine = get_engine()
    async with engine.begin() as conn:
        existing = await conn.execute(select(func.count()).select_from(videos))
        if existing.scalar_one() > 0:
            return

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        video_rows: list[dict] = []
        snapshot_rows: list[dict] = []

        for v in payload.get("videos", []):
            video_rows.append(
                {
                    "id": v["id"],
                    "creator_id": v["creator_id"],
                    "video_created_at": isoparse(v["video_created_at"]),
                    "views_count": v["views_count"],
                    "likes_count": v["likes_count"],
                    "comments_count": v["comments_count"],
                    "reports_count": v["reports_count"],
                    "created_at": isoparse(v["created_at"]),
                    "updated_at": isoparse(v["updated_at"]),
                }
            )

            for s in v.get("snapshots", []):
                snapshot_rows.append(
                    {
                        "id": s["id"],
                        "video_id": s["video_id"],
                        "views_count": s["views_count"],
                        "likes_count": s["likes_count"],
                        "comments_count": s["comments_count"],
                        "reports_count": s["reports_count"],
                        "delta_views_count": s["delta_views_count"],
                        "delta_likes_count": s["delta_likes_count"],
                        "delta_comments_count": s["delta_comments_count"],
                        "delta_reports_count": s["delta_reports_count"],
                        "created_at": isoparse(s["created_at"]),
                        "updated_at": isoparse(s["updated_at"]),
                    }
                )

        if video_rows:
            await conn.execute(videos.insert(), video_rows)

        if snapshot_rows:
            for chunk in chunked(snapshot_rows, 5000):
                await conn.execute(video_snapshots.insert(), chunk)


if __name__ == "__main__":
    asyncio.run(load_data())
