from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal


@dataclass
class Threshold:
    metric: Literal["views", "likes", "comments", "reports"]
    op: Literal[">", ">=", "<", "<="]
    value: int


@dataclass
class QueryPlan:
    source: Literal["videos", "snapshots"]
    aggregate: Literal["count", "sum"]
    metric: Literal["videos", "views", "likes", "comments", "reports"]
    use_delta: bool
    distinct: bool
    date_from: date | None
    date_to: date | None
    hours_after_publication: int | None
    creator_id: str | None
    threshold: Threshold | None
    positive_only: bool
