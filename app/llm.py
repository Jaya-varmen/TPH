from __future__ import annotations

import asyncio
import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import httpx

from .config import get_settings
from .query_plan import QueryPlan, Threshold

SYSTEM_PROMPT = """
Ты помощник, который преобразует запросы на русском в JSON план запроса к БД.

Схема БД:
- videos: id, creator_id, video_created_at, views_count, likes_count, comments_count, reports_count
- video_snapshots: id, video_id, views_count, likes_count, comments_count, reports_count,
  delta_views_count, delta_likes_count, delta_comments_count, delta_reports_count, created_at

Верни ТОЛЬКО JSON со следующими полями:
{
  "source": "videos" | "snapshots",
  "aggregate": "count" | "sum",
  "metric": "videos" | "views" | "likes" | "comments" | "reports",
  "use_delta": true | false,
  "distinct": true | false,
  "date_from": "YYYY-MM-DD" | null,
  "date_to": "YYYY-MM-DD" | null,
  "creator_id": "..." | null,
  "threshold": {"metric": "views|likes|comments|reports", "op": ">|>=|<|<=", "value": number} | null,
  "positive_only": true | false
}

Правила:
- Вопросы про публикацию видео ("вышло", "опубликовано") => source=videos, фильтр по video_created_at.
- Вопросы про прирост/рост/новые показатели за дату => source=snapshots, use_delta=true, фильтр по created_at.
- "Сколько видео" => aggregate=count, metric=videos.
- "Сколько просмотров/лайков/комментариев/жалоб" => aggregate=sum, metric=views|likes|comments|reports.
- "Сколько разных/уникальных видео" => distinct=true и metric=videos.
- Если указан creator id (32 hex), положи в creator_id.
- Если есть порог (больше/меньше N просмотров и т.п.), заполни threshold.
- Если запрос про новые просмотры, поставь positive_only=true.

Даты в формате "28 ноября 2025" приводи к ISO (YYYY-MM-DD). Если один день, date_from=date_to.
""".strip()

ALLOWED_SOURCE = {"videos", "snapshots"}
ALLOWED_AGG = {"count", "sum"}
ALLOWED_METRIC = {"videos", "views", "likes", "comments", "reports"}
ALLOWED_OP = {">", ">=", "<", "<="}

_token_lock = asyncio.Lock()
_token_value: str | None = None
_token_expires_at: datetime | None = None


def _parse_date(value: Any) -> date | None:
    if value in (None, "", "null"):
        return None
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _validate(payload: dict[str, Any]) -> QueryPlan | None:
    try:
        source = payload["source"]
        aggregate = payload["aggregate"]
        metric = payload["metric"]
        use_delta = bool(payload["use_delta"])
        distinct = bool(payload["distinct"])
        date_from = _parse_date(payload.get("date_from"))
        date_to = _parse_date(payload.get("date_to"))
        creator_id = payload.get("creator_id") or None
        positive_only = bool(payload.get("positive_only", False))
    except Exception:
        return None

    if source not in ALLOWED_SOURCE or aggregate not in ALLOWED_AGG or metric not in ALLOWED_METRIC:
        return None

    threshold_data = payload.get("threshold")
    threshold: Threshold | None = None
    if threshold_data:
        try:
            t_metric = threshold_data["metric"]
            t_op = threshold_data["op"]
            t_value = int(threshold_data["value"])
        except Exception:
            return None
        if t_metric not in {"views", "likes", "comments", "reports"}:
            return None
        if t_op not in ALLOWED_OP:
            return None
        threshold = Threshold(metric=t_metric, op=t_op, value=t_value)

    return QueryPlan(
        source=source,  # type: ignore[arg-type]
        aggregate=aggregate,  # type: ignore[arg-type]
        metric=metric,  # type: ignore[arg-type]
        use_delta=use_delta,
        distinct=distinct,
        date_from=date_from,
        date_to=date_to,
        creator_id=creator_id,
        threshold=threshold,
        positive_only=positive_only,
    )


def _cached_token_valid(now: datetime) -> bool:
    return (
        _token_value is not None
        and _token_expires_at is not None
        and _token_expires_at > now + timedelta(seconds=30)
    )


async def _fetch_token() -> str | None:
    global _token_value, _token_expires_at

    settings = get_settings()
    if not settings.gigachat_auth_key:
        return None

    now = datetime.now(timezone.utc)
    if _cached_token_valid(now):
        return _token_value

    async with _token_lock:
        now = datetime.now(timezone.utc)
        if _cached_token_valid(now):
            return _token_value

        headers = {
            "Authorization": f"Basic {settings.gigachat_auth_key}",
            "RqUID": str(uuid4()),
            "Content-Type": "application/x-www-form-urlencoded",
        }

        async with httpx.AsyncClient(timeout=25, verify=settings.gigachat_verify_ssl) as client:
            response = await client.post(
                settings.gigachat_oauth_url,
                headers=headers,
                data={"scope": settings.gigachat_scope},
            )

        if response.status_code >= 400:
            return None

        payload = response.json()
        token = payload.get("access_token")
        if not token:
            return None

        expires_at_raw = payload.get("expires_at")
        if isinstance(expires_at_raw, int):
            expires_at = datetime.fromtimestamp(expires_at_raw / 1000, tz=timezone.utc)
        else:
            expires_at = now + timedelta(minutes=29)

        _token_value = token
        _token_expires_at = expires_at
        return token


def _extract_text_content(raw_content: Any) -> str:
    if isinstance(raw_content, str):
        return raw_content.strip()

    if isinstance(raw_content, list):
        texts: list[str] = []
        for item in raw_content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    texts.append(text)
        return "\n".join(texts).strip()

    return ""


async def _call_chat_completion(text: str, token: str) -> str | None:
    settings = get_settings()
    url = f"{settings.gigachat_api_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.gigachat_model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
    }

    async with httpx.AsyncClient(timeout=40, verify=settings.gigachat_verify_ssl) as client:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )

    if response.status_code >= 400:
        return None

    data = response.json()
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return None

    message = choices[0].get("message", {})
    return _extract_text_content(message.get("content"))


async def try_llm_parse(text: str) -> QueryPlan | None:
    token = await _fetch_token()
    if not token:
        return None

    content = await _call_chat_completion(text, token)
    if not content:
        return None

    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, re.DOTALL)
    if fenced:
        content = fenced.group(1).strip()

    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return None

    return _validate(payload)
