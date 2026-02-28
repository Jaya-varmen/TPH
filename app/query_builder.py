from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from sqlalchemy import Select, and_, distinct, func, select, text

from .models import videos, video_snapshots
from .query_plan import QueryPlan


def _metric_column(plan: QueryPlan):
    if plan.metric == "videos":
        return None
    if plan.source == "snapshots":
        name = f"delta_{plan.metric}_count" if plan.use_delta else f"{plan.metric}_count"
        return video_snapshots.c[name]
    return videos.c[f"{plan.metric}_count"]


def _date_bounds(plan: QueryPlan) -> tuple[datetime, datetime] | None:
    if plan.date_from is None and plan.date_to is None:
        return None
    date_from = plan.date_from or plan.date_to
    date_to = plan.date_to or plan.date_from
    if date_from is None or date_to is None:
        return None
    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start, end


def build_query(plan: QueryPlan) -> Select:
    if plan.source == "videos":
        date_col = videos.c.video_created_at
    else:
        date_col = video_snapshots.c.created_at

    metric_col = _metric_column(plan)

    if plan.aggregate == "sum":
        if metric_col is None:
            raise ValueError("sum requires metric")
        expr = func.coalesce(func.sum(metric_col), 0)
    else:
        if plan.metric == "videos":
            count_col = videos.c.id if plan.source == "videos" else video_snapshots.c.video_id
        else:
            count_col = metric_col
        if plan.distinct:
            expr = func.count(distinct(count_col))
        else:
            expr = func.count(count_col)

    stmt = select(expr)

    conditions: list = []

    # Join videos for snapshot queries that need publication-based filters.
    need_videos_join = (
        plan.source == "snapshots"
        and (plan.creator_id is not None or plan.hours_after_publication is not None)
    )
    if need_videos_join:
        stmt = stmt.select_from(video_snapshots.join(videos, video_snapshots.c.video_id == videos.c.id))

    if plan.source == "snapshots" and plan.creator_id:
        conditions.append(videos.c.creator_id == plan.creator_id)
    elif plan.source == "videos" and plan.creator_id:
        conditions.append(videos.c.creator_id == plan.creator_id)

    bounds = _date_bounds(plan)
    if bounds:
        start, end = bounds
        conditions.append(and_(date_col >= start, date_col < end))

    if plan.source == "snapshots" and plan.hours_after_publication is not None:
        hours = int(plan.hours_after_publication)
        interval_expr = text(f"INTERVAL '{hours} hour'")
        conditions.append(video_snapshots.c.created_at >= videos.c.video_created_at)
        conditions.append(video_snapshots.c.created_at < videos.c.video_created_at + interval_expr)

    if plan.threshold:
        threshold_col = metric_col
        if plan.source == "videos":
            threshold_col = videos.c[f"{plan.threshold.metric}_count"]
        elif plan.source == "snapshots" and plan.use_delta:
            threshold_col = video_snapshots.c[f"delta_{plan.threshold.metric}_count"]
        elif plan.source == "snapshots":
            threshold_col = video_snapshots.c[f"{plan.threshold.metric}_count"]

        op = plan.threshold.op
        if op == ">":
            conditions.append(threshold_col > plan.threshold.value)
        elif op == ">=":
            conditions.append(threshold_col >= plan.threshold.value)
        elif op == "<":
            conditions.append(threshold_col < plan.threshold.value)
        elif op == "<=":
            conditions.append(threshold_col <= plan.threshold.value)

    if plan.positive_only and metric_col is not None:
        conditions.append(metric_col > 0)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    return stmt
