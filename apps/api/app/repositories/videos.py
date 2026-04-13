from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..models import Video


class VideosRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(
        self,
        *,
        platform: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        filters: list[str] = []
        params: dict[str, object] = {"limit": limit}
        if platform is not None:
            filters.append("v.platform = :platform")
            params["platform"] = platform
        if status is not None:
            filters.append("lj.status = :status")
            params["status"] = status
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

        stmt = text(
            f"""
            SELECT
                v.id,
                v.platform,
                v.video_uid,
                v.source_url,
                v.title,
                v.published_at,
                v.first_seen_at,
                v.last_seen_at,
                lj.status AS latest_job_status,
                lj.id AS latest_job_id
            FROM videos v
            LEFT JOIN LATERAL (
                SELECT j.id, j.status
                FROM jobs j
                WHERE j.video_id = v.id
                ORDER BY j.created_at DESC
                LIMIT 1
            ) lj ON TRUE
            {where_clause}
            ORDER BY v.last_seen_at DESC
            LIMIT :limit
            """
        )

        rows = self.db.execute(stmt, params).mappings()
        return [dict(row) for row in rows]

    def list_recent(self, *, platform: str | None, limit: int) -> list[Video]:
        stmt = select(Video)
        if platform is not None:
            stmt = stmt.where(Video.platform == platform)
        stmt = stmt.order_by(Video.last_seen_at.desc()).limit(limit)
        return list(self.db.scalars(stmt).all())

    def list_by_ids(
        self,
        *,
        video_ids: Iterable[uuid.UUID],
        platform: str | None,
        limit: int,
    ) -> list[Video]:
        ordered_ids = list(dict.fromkeys(video_ids))
        if not ordered_ids:
            return []

        stmt = select(Video).where(Video.id.in_(ordered_ids))
        if platform is not None:
            stmt = stmt.where(Video.platform == platform)
        rows = list(self.db.scalars(stmt).all())
        rows_by_id = {row.id: row for row in rows}

        ordered_rows: list[Video] = []
        for video_id in ordered_ids:
            row = rows_by_id.get(video_id)
            if row is not None:
                ordered_rows.append(row)
            if len(ordered_rows) >= limit:
                break
        return ordered_rows

    def get_by_platform_uid(self, *, platform: str, video_uid: str) -> Video | None:
        stmt = select(Video).where(
            Video.platform == platform,
            Video.video_uid == video_uid,
        )
        return self.db.scalar(stmt)

    def get_by_source_url(self, *, source_url: str) -> Video | None:
        stmt = (
            select(Video).where(Video.source_url == source_url).order_by(Video.last_seen_at.desc())
        )
        return self.db.scalar(stmt)

    def upsert_for_processing(
        self,
        *,
        platform: str,
        video_uid: str,
        source_url: str,
        content_type: str = "video",
    ) -> Video:
        dialect_name = (self.db.bind.dialect.name if self.db.bind is not None else "").lower()
        if dialect_name == "postgresql":
            now = datetime.now(UTC)
            row = (
                self.db.execute(
                    text(
                        """
                    INSERT INTO videos (
                        id,
                        platform,
                        video_uid,
                        source_url,
                        content_type,
                        first_seen_at,
                        last_seen_at
                    )
                    VALUES (
                        CAST(:id AS UUID),
                        :platform,
                        :video_uid,
                        :source_url,
                        :content_type,
                        :now_ts,
                        :now_ts
                    )
                    ON CONFLICT (platform, video_uid)
                    DO UPDATE SET
                        source_url = EXCLUDED.source_url,
                        content_type = EXCLUDED.content_type,
                        last_seen_at = EXCLUDED.last_seen_at
                    RETURNING id
                    """
                    ),
                    {
                        "platform": platform,
                        "id": str(uuid.uuid4()),
                        "video_uid": video_uid,
                        "source_url": source_url,
                        "content_type": content_type,
                        "now_ts": now,
                    },
                )
                .mappings()
                .one()
            )
            self.db.commit()
            existing = self.db.get(Video, row["id"])
            if existing is None:
                raise RuntimeError("failed to load video after upsert")
            self.db.refresh(existing)
            return existing

        existing = self.get_by_platform_uid(platform=platform, video_uid=video_uid)
        now = datetime.now(UTC)
        if existing is not None:
            existing.source_url = source_url
            existing.last_seen_at = now
            self.db.commit()
            self.db.refresh(existing)
            return existing

        instance = Video(
            platform=platform,
            video_uid=video_uid,
            source_url=source_url,
            content_type=content_type,
            first_seen_at=now,
            last_seen_at=now,
        )
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance
