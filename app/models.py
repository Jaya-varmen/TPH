from __future__ import annotations

from sqlalchemy import (
    MetaData,
    Table,
    Column,
    String,
    Integer,
    DateTime,
    ForeignKey,
    Index,
)

metadata = MetaData()

videos = Table(
    "videos",
    metadata,
    Column("id", String, primary_key=True),
    Column("creator_id", String, index=True, nullable=False),
    Column("video_created_at", DateTime(timezone=True), index=True, nullable=False),
    Column("views_count", Integer, nullable=False),
    Column("likes_count", Integer, nullable=False),
    Column("comments_count", Integer, nullable=False),
    Column("reports_count", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

video_snapshots = Table(
    "video_snapshots",
    metadata,
    Column("id", String, primary_key=True),
    Column("video_id", String, ForeignKey("videos.id"), index=True, nullable=False),
    Column("views_count", Integer, nullable=False),
    Column("likes_count", Integer, nullable=False),
    Column("comments_count", Integer, nullable=False),
    Column("reports_count", Integer, nullable=False),
    Column("delta_views_count", Integer, nullable=False),
    Column("delta_likes_count", Integer, nullable=False),
    Column("delta_comments_count", Integer, nullable=False),
    Column("delta_reports_count", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), index=True, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

Index("ix_snapshots_created_at_video", video_snapshots.c.created_at, video_snapshots.c.video_id)
