from __future__ import annotations

import re
from calendar import monthrange
from datetime import date
from typing import Literal

from .config import get_settings
from .llm import try_llm_parse
from .query_plan import QueryPlan, Threshold


MONTHS = {
    "январь": 1,
    "января": 1,
    "январе": 1,
    "февраль": 2,
    "февраля": 2,
    "феврале": 2,
    "март": 3,
    "марта": 3,
    "марте": 3,
    "апрель": 4,
    "апреля": 4,
    "апреле": 4,
    "май": 5,
    "мая": 5,
    "мае": 5,
    "июнь": 6,
    "июня": 6,
    "июне": 6,
    "июль": 7,
    "июля": 7,
    "июле": 7,
    "август": 8,
    "августа": 8,
    "августе": 8,
    "сентябрь": 9,
    "сентября": 9,
    "сентябре": 9,
    "октябрь": 10,
    "октября": 10,
    "октябре": 10,
    "ноябрь": 11,
    "ноября": 11,
    "ноябре": 11,
    "декабрь": 12,
    "декабря": 12,
    "декабре": 12,
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

PUBLISHED_KEYWORDS = ["вышло", "опублик", "загруж", "вылож", "опубликов", "появил"]

THRESHOLD_RE = re.compile(
    r"(не\s+менее|не\s+более|не\s+больше|больше|более|>=|меньше|менее|<=|>|<)\s*([0-9][0-9\s_]*)"
)
CREATOR_RE = re.compile(r"\b[0-9a-f]{32}\b")
HOURS_WORDS = {
    "один": 1,
    "одна": 1,
    "два": 2,
    "две": 2,
    "три": 3,
    "четыре": 4,
    "пять": 5,
    "шесть": 6,
    "семь": 7,
    "восемь": 8,
    "девять": 9,
    "десять": 10,
    "одиннадцать": 11,
    "двенадцать": 12,
    "тринадцать": 13,
    "четырнадцать": 14,
    "пятнадцать": 15,
    "шестнадцать": 16,
    "семнадцать": 17,
    "восемнадцать": 18,
    "девятнадцать": 19,
    "двадцать": 20,
    "двадцать один": 21,
    "двадцать два": 22,
    "двадцать три": 23,
    "двадцать четыре": 24,
}


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

    # pattern: с 1 ноября по 5 ноября 2025
    m = re.search(r"с\s+(\d{1,2})\s+([а-я]+)\s+по\s+(\d{1,2})\s+([а-я]+)\s+(\d{4})", text)
    if m:
        d1, month_word1, d2, month_word2, year = m.groups()
        month1 = MONTHS.get(month_word1)
        month2 = MONTHS.get(month_word2)
        if month1 and month2:
            return (
                date(int(year), month1, int(d1)),
                date(int(year), month2, int(d2)),
            )

    # pattern: за май 2025, в ноябре 2025, за май 2025г, за май 2025 года
    m = re.search(r"(?:за|в)\s+([а-я]+)\s+(\d{4})(?:\s*г(?:од(?:а)?)?)?", text)
    if m:
        month_word, year = m.groups()
        month = MONTHS.get(month_word)
        if month:
            y = int(year)
            last_day = monthrange(y, month)[1]
            return date(y, month, 1), date(y, month, last_day)

    # pattern: за 2025 год, в 2025г
    m = re.search(r"(?:за|в)\s+(\d{4})\s*г(?:од(?:а)?)?", text)
    if m:
        y = int(m.group(1))
        return date(y, 1, 1), date(y, 12, 31)

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
    digits_only = re.sub(r"\D", "", raw_value)
    if not digits_only:
        return None
    value = int(digits_only)
    norm = raw_op.strip()
    if norm in ("больше", "более", ">"):
        op = ">"
    elif norm in ("не менее", ">="):
        op = ">="
    elif norm in ("меньше", "менее", "<"):
        op = "<"
    elif norm in ("не более", "не больше", "<="):
        op = "<="
    else:
        return None
    return Threshold(metric=metric, op=op, value=value)


def parse_hours_after_publication(text: str) -> int | None:
    # examples:
    # "за первые 3 часа после публикации"
    # "за первых 24 часов после публикации"
    m = re.search(r"перв[а-я]*\s+([а-я]+(?:\s+[а-я]+)?|\d{1,3})\s+час[а-я]*\s+после\s+публик", text)
    if not m:
        return None
    raw_hours = m.group(1).strip()
    if raw_hours.isdigit():
        hours = int(raw_hours)
    else:
        hours = HOURS_WORDS.get(raw_hours)
        if hours is None:
            return None
    if hours <= 0:
        return None
    # Guardrail to avoid unrealistic values from malformed input/LLM.
    if hours > 720:
        return 720
    return hours


def parse_rules(text: str) -> QueryPlan | None:
    t = normalize(text)

    metric = detect_metric(t)
    count_question = any(word in t for word in ["сколько", "количество", "число"])
    has_video_word = any(word in t for word in ["видео", "ролик", "роликов", "ролика", "ролики"])
    video_count_intent = (
        re.search(r"(сколько|количество|число)\s+(?:видео|ролик(?:ов|а|и)?)", t) is not None
    )

    distinct = any(word in t for word in DISTINCT_KEYWORDS)
    creator_id = CREATOR_RE.search(t)
    creator_id_value = creator_id.group(0) if creator_id else None

    date_from, date_to = parse_date_range(t)
    has_date = date_from is not None

    threshold = parse_threshold(t, metric)
    hours_after_publication = parse_hours_after_publication(t)

    published_hint = any(word in t for word in PUBLISHED_KEYWORDS)
    is_published = has_video_word and published_hint
    delta_hint = any(word in t for word in DELTA_KEYWORDS)
    state_hint = (
        "на момент" in t
        or "по состоянию" in t
        or re.search(r"\bк\s+\d{1,2}\s+[а-я]+\s+\d{4}\b", t) is not None
        or re.search(r"\bна\s+\d{1,2}\s+[а-я]+\s+\d{4}\b", t) is not None
    )

    received_metric_hint = (
        metric is not None
        and re.search(r"получ[а-я]*\s+(?:[а-я]+\s+){0,4}(?:просмотр|лайк|комментар|жалоб|репорт)", t) is not None
    )

    # "positive only" applies to intents like "новые просмотры" and count-of-videos questions with "получили X".
    positive_only = bool(re.search(r"нов[а-я]*\s+(?:просмотр|лайк|комментар|жалоб|репорт)", t))
    if not positive_only and has_video_word and count_question and received_metric_hint:
        positive_only = True

    # Decide aggregate
    if count_question:
        if metric is not None and not video_count_intent and threshold is None and not distinct and not positive_only:
            aggregate = "sum"
        elif video_count_intent or (has_video_word and (distinct or threshold is not None or positive_only)):
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
    if hours_after_publication is not None:
        source = "snapshots"
    elif is_published:
        source = "videos"
    elif has_date:
        source = "snapshots"
    else:
        source = "videos"

    # "новые просмотры/лайки/..." для count по видео требует фильтр > 0.
    if positive_only and threshold is None and metric is not None and source == "snapshots":
        threshold = Threshold(metric=metric, op=">", value=0)

    # Decide metric target
    if aggregate == "count":
        metric_target: Literal["videos", "views", "likes", "comments", "reports"]
        if has_video_word and (video_count_intent or distinct or threshold is not None or positive_only):
            metric_target = "videos"
        elif metric is None or threshold is not None:
            metric_target = "videos"
        elif has_video_word and metric is None:
            metric_target = "videos"
        else:
            metric_target = metric
    else:
        if metric is None:
            return None
        metric_target = metric

    # Snapshot table can contain multiple rows per video per period, so for "count videos"
    # we should count unique video_ids even if user did not explicitly say "разных".
    if aggregate == "count" and metric_target == "videos" and source == "snapshots":
        distinct = True

    # Use delta?
    use_delta = False
    if source == "snapshots":
        if delta_hint or positive_only or hours_after_publication is not None:
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
        hours_after_publication=hours_after_publication,
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
