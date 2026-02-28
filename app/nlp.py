from __future__ import annotations

import re
from datetime import date
from typing import Literal

from .config import get_settings
from .llm import try_llm_parse
from .query_plan import QueryPlan, Threshold


MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}

METRIC_ALIASES = {
    "views": ["просмотр", "просмотров", "просмотры"],
    "likes": ["лайк", "лайков", "лайки"],
    "comments": ["комментар", "комментариев", "комменты"],
    "reports": ["жалоб", "репорт", "репортов", "репорты", "жалобы"],
}

DELTA_KEYWORDS = [
    "прирост",
    "вырос",
    "выросли",
    "увелич",
    "прибав",
    "рост",
    "новые",
    "добав",
]

DISTINCT_KEYWORDS = ["разных", "уникальных", "различных"]

PUBLISHED_KEYWORDS = ["вышло", "опублик", "загруж", "вылож", "опубликов"]

STATE_KEYWORDS = ["на момент", "по состоянию", "к "]

THRESHOLD_RE = re.compile(r"(больше|более|не менее|>=|меньше|менее|<=)\s*([0-9][0-9 _]*)")
CREATOR_RE = re.compile(r"\b[0-9a-f]{32}\b")


def normalize(text: str) -> str:
    return (
        text.lower()
        .replace("ё", "е")
        .replace("—", "-")
        .replace("–", "-")
    )


def detect_metric(text: str) -> Literal["views", "likes", "comments", "reports"] | None:
    for metric, aliases in METRIC_ALIASES.items():
        for alias in aliases:
            if alias in text:
                return metric  # type: ignore[return-value]
    return None


def parse_date_range(text: str) -> tuple[date | None, date | None]:
    # pattern: с 1 по 5 ноября 2025
    m = re.search(r"с\s+(\d{1,2})\s+по\s+(\d{1,2})\s+([а-я]+)\s+(\d{4})", text)
    if m:
        d1, d2, month_word, year = m.groups()
        month = MONTHS.get(month_word)
        if month:
            return date(int(year), month, int(d1)), date(int(year), month, int(d2))

    # pattern: с 1 ноября 2025 по 5 ноября 2025
    m = re.search(
        r"с\s+(\d{1,2})\s+([а-я]+)\s+(\d{4})\s+по\s+(\d{1,2})\s+([а-я]+)\s+(\d{4})",
        text,
    )
    if m:
        d1, month_word1, y1, d2, month_word2, y2 = m.groups()
        month1 = MONTHS.get(month_word1)
        month2 = MONTHS.get(month_word2)
        if month1 and month2:
            return (
                date(int(y1), month1, int(d1)),
                date(int(y2), month2, int(d2)),
            )

    # single date
    m = re.search(r"(\d{1,2})\s+([а-я]+)\s+(\d{4})", text)
    if m:
        d1, month_word, year = m.groups()
        month = MONTHS.get(month_word)
        if month:
            single = date(int(year), month, int(d1))
            return single, single

    return None, None


def parse_threshold(text: str, metric: str | None) -> Threshold | None:
    if metric is None:
        return None
    m = THRESHOLD_RE.search(text)
    if not m:
        return None
    raw_op, raw_value = m.groups()
    value = int(raw_value.replace(" ", "").replace("_", ""))
    if raw_op in ("больше", "более", ">="):
        op = ">=" if raw_op == ">=" else ">"
    else:
        op = "<=" if raw_op == "<=" else "<"
    return Threshold(metric=metric, op=op, value=value)


def parse_rules(text: str) -> QueryPlan | None:
    t = normalize(text)

    metric = detect_metric(t)
    has_video_word = "видео" in t
    video_count_intent = re.search(r"(сколько|количество|число)\s+видео", t) is not None

    distinct = any(word in t for word in DISTINCT_KEYWORDS)
    creator_id = CREATOR_RE.search(t)
    creator_id_value = creator_id.group(0) if creator_id else None

    date_from, date_to = parse_date_range(t)
    has_date = date_from is not None

    threshold = parse_threshold(t, metric)

    is_published = any(word in t for word in PUBLISHED_KEYWORDS)
    delta_hint = any(word in t for word in DELTA_KEYWORDS)
    state_hint = any(word in t for word in STATE_KEYWORDS)

    positive_only = "новые" in t or "получали" in t or "получили" in t

    # Decide aggregate
    if any(word in t for word in ["сколько", "количество", "число"]):
        if video_count_intent:
            aggregate = "count"
        elif metric:
            aggregate = "sum"
        elif has_video_word:
            aggregate = "count"
        else:
            aggregate = "count"
    elif any(word in t for word in ["сумма", "суммар", "в сумме"]):
        aggregate = "sum"
    else:
        if metric:
            aggregate = "sum"
        elif has_video_word:
            aggregate = "count"
        else:
            return None

    # Decide source table
    if is_published:
        source = "videos"
    elif has_date:
        source = "snapshots"
    else:
        source = "videos"

    # Decide metric target
    if aggregate == "count":
        metric_target: Literal["videos", "views", "likes", "comments", "reports"]
        if video_count_intent or metric is None or threshold is not None:
            metric_target = "videos"
        elif has_video_word and metric is None:
            metric_target = "videos"
        else:
            metric_target = metric
    else:
        if metric is None:
            return None
        metric_target = metric

    # Use delta?
    use_delta = False
    if source == "snapshots":
        if delta_hint or positive_only:
            use_delta = True
        elif has_date and metric_target != "videos" and not state_hint:
            # default to per-day growth for metric queries with date
            use_delta = True

    return QueryPlan(
        source=source,
        aggregate=aggregate,
        metric=metric_target,
        use_delta=use_delta,
        distinct=distinct,
        date_from=date_from,
        date_to=date_to,
        creator_id=creator_id_value,
        threshold=threshold,
        positive_only=positive_only,
    )


async def parse_query(text: str) -> QueryPlan:
    plan = parse_rules(text)
    if plan:
        return plan

    settings = get_settings()
    if settings.llm_enabled and settings.gigachat_auth_key:
        llm_plan = await try_llm_parse(text)
        if llm_plan:
            return llm_plan

    raise ValueError("Не удалось распознать запрос")
