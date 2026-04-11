from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..repositories import FeedFeedbackRepository, JobsRepository
from .source_identity import build_identity_payload
from .source_names import resolve_source_name


class FeedService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.feedback_repo = FeedFeedbackRepository(db)
        self.jobs_repo = JobsRepository(db)

    def list_digest_feed(
        self,
        *,
        source: str | None = None,
        category: str | None = None,
        feedback: str | None = None,
        sort: str | None = None,
        subscription_id: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
        since: datetime | None = None,
    ) -> dict[str, Any]:
        safe_limit = max(1, min(limit, 100))
        normalized_sort = str(sort or "").strip().lower() or "recent"
        if normalized_sort not in {"recent", "curated"}:
            normalized_sort = "recent"
        cursor_rank, cursor_ts, cursor_job_id = self._parse_cursor(cursor, sort=normalized_sort)
        normalized_feedback = str(feedback or "").strip().lower() or None
        if normalized_feedback not in {
            None,
            "saved",
            "useful",
            "noisy",
            "dismissed",
            "archived",
        }:
            normalized_feedback = None
        params: dict[str, Any] = {
            "limit": safe_limit + 1,
            "source": source,
            "category": category.strip().lower()
            if isinstance(category, str) and category.strip()
            else None,
            "feedback": normalized_feedback,
            "sort": normalized_sort,
            "cursor_rank": cursor_rank,
            "subscription_id": subscription_id.strip()
            if isinstance(subscription_id, str) and subscription_id.strip()
            else None,
            "since": since,
            "cursor_ts": cursor_ts,
            "cursor_job_id": cursor_job_id,
        }
        if normalized_sort == "curated":
            cursor_predicate = """
                  AND (
                    CAST(:cursor_rank AS INTEGER) IS NULL
                    OR base.feedback_rank < CAST(:cursor_rank AS INTEGER)
                    OR (
                      base.feedback_rank = CAST(:cursor_rank AS INTEGER)
                      AND (
                        base.sort_ts < CAST(:cursor_ts AS TIMESTAMPTZ)
                        OR (
                          base.sort_ts = CAST(:cursor_ts AS TIMESTAMPTZ)
                          AND base.job_id < CAST(:cursor_job_id AS TEXT)
                        )
                      )
                    )
                  )
            """
            order_by = "ORDER BY base.feedback_rank DESC, base.sort_ts DESC, base.job_id DESC"
        else:
            cursor_predicate = """
                  AND (
                    CAST(:cursor_ts AS TIMESTAMPTZ) IS NULL
                    OR base.sort_ts < CAST(:cursor_ts AS TIMESTAMPTZ)
                    OR (
                      base.sort_ts = CAST(:cursor_ts AS TIMESTAMPTZ)
                      AND base.job_id < CAST(:cursor_job_id AS TEXT)
                    )
                  )
            """
            order_by = "ORDER BY base.sort_ts DESC, base.job_id DESC"

        rows = self.db.execute(
            text(
                f"""
                WITH base AS (
                    SELECT
                        CAST(j.id AS TEXT) AS job_id,
                        v.source_url,
                        v.platform AS source,
                        COALESCE(v.content_type, 'video') AS content_type,
                        v.title,
                        v.video_uid,
                        v.published_at,
                        j.created_at,
                        COALESCE(v.published_at, j.created_at) AS sort_ts,
                        COALESCE(
                            (
                                SELECT s.category
                                FROM ingest_events ie
                                JOIN subscriptions s ON s.id = ie.subscription_id
                                WHERE ie.video_id = v.id
                                ORDER BY ie.created_at DESC
                                LIMIT 1
                            ),
                            'misc'
                        ) AS category,
                        COALESCE(
                            (
                                SELECT s.source_type
                                FROM ingest_events ie
                                JOIN subscriptions s ON s.id = ie.subscription_id
                                WHERE ie.video_id = v.id
                                ORDER BY ie.created_at DESC
                                LIMIT 1
                            ),
                            ''
                        ) AS subscription_source_type,
                        COALESCE(
                            (
                                SELECT s.source_value
                                FROM ingest_events ie
                                JOIN subscriptions s ON s.id = ie.subscription_id
                                WHERE ie.video_id = v.id
                                ORDER BY ie.created_at DESC
                                LIMIT 1
                            ),
                            ''
                        ) AS subscription_source_value,
                        COALESCE(
                            (
                                SELECT CAST(s.id AS TEXT)
                                FROM ingest_events ie
                                JOIN subscriptions s ON s.id = ie.subscription_id
                                WHERE ie.video_id = v.id
                                ORDER BY ie.created_at DESC
                                LIMIT 1
                            ),
                            ''
                        ) AS subscription_id,
                        COALESCE(ff.saved, FALSE) AS feedback_saved,
                        ff.feedback_label,
                        CASE
                            WHEN COALESCE(ff.saved, FALSE) = TRUE AND ff.feedback_label = 'useful' THEN 4
                            WHEN COALESCE(ff.saved, FALSE) = TRUE THEN 3
                            WHEN ff.feedback_label = 'useful' THEN 2
                            WHEN ff.feedback_label = 'noisy' THEN -1
                            WHEN ff.feedback_label IN ('dismissed', 'archived') THEN -2
                            ELSE 0
                        END AS feedback_rank,
                        j.artifact_digest_md,
                        j.artifact_root
                    FROM jobs j
                    JOIN videos v ON v.id = j.video_id
                    LEFT JOIN feed_feedback ff ON ff.job_id = j.id
                    WHERE j.kind = 'video_digest_v1'
                      AND j.status = 'succeeded'
                      AND (CAST(:source AS TEXT) IS NULL OR v.platform = CAST(:source AS TEXT))
                      AND (CAST(:since AS TIMESTAMPTZ) IS NULL OR j.created_at >= CAST(:since AS TIMESTAMPTZ))
                )
                SELECT *
                FROM base
                WHERE (CAST(:category AS TEXT) IS NULL OR base.category = CAST(:category AS TEXT))
                  AND (
                    CAST(:feedback AS TEXT) IS NULL
                    OR (
                      CAST(:feedback AS TEXT) = 'saved'
                      AND COALESCE(base.feedback_saved, FALSE) = TRUE
                    )
                    OR (
                      CAST(:feedback AS TEXT) <> 'saved'
                      AND base.feedback_label = CAST(:feedback AS TEXT)
                    )
                  )
                  AND (
                    CAST(:subscription_id AS TEXT) IS NULL
                    OR base.subscription_id = CAST(:subscription_id AS TEXT)
                  )
                {cursor_predicate}
                {order_by}
                LIMIT :limit
                """
            ),
            params,
        ).mappings()

        items: list[dict[str, Any]] = []
        for row in rows:
            summary_md, artifact_type = self._resolve_summary(
                digest_path=row.get("artifact_digest_md"),
                artifact_root=row.get("artifact_root"),
            )
            if not summary_md:
                continue

            job_id = str(row.get("job_id") or "").strip()
            if not job_id:
                continue

            source_url = str(row.get("source_url") or "").strip()
            published_at = row.get("published_at") or row.get("sort_ts") or row.get("created_at")
            sort_ts = row.get("sort_ts") or row.get("created_at")
            source_platform = str(row.get("source") or "")
            content_type = self._normalize_content_type(row.get("content_type"))
            source_type = str(row.get("subscription_source_type") or "")
            source_value = str(row.get("subscription_source_value") or "")
            source_name = resolve_source_name(
                source_type=source_type,
                source_value=source_value,
                fallback=source_platform,
            )
            subscription_id = str(row.get("subscription_id") or "").strip() or None
            identity = build_identity_payload(
                platform=source_platform,
                display_name=source_name,
                source_homepage_url=source_url,
                source_url=source_url,
                source_universe_label=source_name or source_platform,
            )
            feedback_label = str(row.get("feedback_label") or "").strip().lower() or None
            if feedback_label not in {"useful", "noisy", "dismissed", "archived"}:
                feedback_label = None
            items.append(
                {
                    "feed_id": f"{self._iso(sort_ts)}__{job_id}",
                    "job_id": job_id,
                    "video_url": source_url,
                    "title": self._resolve_title(row),
                    "source": source_platform,
                    "source_name": source_name,
                    "canonical_source_name": source_name,
                    "canonical_author_name": source_name,
                    "subscription_id": subscription_id,
                    "affiliation_label": source_name if subscription_id else "Unmatched source",
                    "relation_kind": "matched_subscription"
                    if subscription_id
                    else "unmatched_source",
                    "thumbnail_url": identity.thumbnail_url,
                    "avatar_url": identity.avatar_url,
                    "avatar_label": identity.avatar_label,
                    "identity_status": identity.identity_status,
                    "category": str(row.get("category") or "misc"),
                    "published_at": self._iso(published_at),
                    "summary_md": summary_md,
                    "artifact_type": artifact_type,
                    "content_type": content_type,
                    "saved": bool(row.get("feedback_saved")),
                    "feedback_label": feedback_label,
                    "_cursor_feedback_rank": int(row.get("feedback_rank") or 0),
                    "_cursor_sort_ts": self._iso(sort_ts),
                }
            )

        has_more = len(items) > safe_limit
        if has_more:
            items = items[:safe_limit]

        next_cursor: str | None = None
        if has_more and items:
            last = items[-1]
            if normalized_sort == "curated":
                next_cursor = (
                    f"{last['_cursor_feedback_rank']}__{last['_cursor_sort_ts']}__{last['job_id']}"
                )
            else:
                next_cursor = f"{last['_cursor_sort_ts']}__{last['job_id']}"
        for item in items:
            item.pop("_cursor_feedback_rank", None)
            item.pop("_cursor_sort_ts", None)

        return {
            "items": items,
            "has_more": has_more,
            "next_cursor": next_cursor,
        }

    def get_feedback(self, *, job_id: uuid.UUID) -> dict[str, Any]:
        row = self.feedback_repo.get_by_job_id(job_id=job_id)
        if row is None:
            return {
                "job_id": job_id,
                "saved": False,
                "feedback_label": None,
                "exists": False,
                "created_at": None,
                "updated_at": None,
            }
        return {
            "job_id": row.job_id,
            "saved": row.saved,
            "feedback_label": row.feedback_label,
            "exists": True,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def set_feedback(
        self,
        *,
        job_id: uuid.UUID,
        saved: bool,
        feedback_label: str | None,
    ) -> dict[str, Any]:
        if self.jobs_repo.get(job_id) is None:
            raise ValueError("job not found")
        normalized_label = str(feedback_label or "").strip().lower() or None
        if normalized_label not in {None, "useful", "noisy", "dismissed", "archived"}:
            raise ValueError("invalid feedback label")
        row = self.feedback_repo.upsert(
            job_id=job_id,
            saved=saved,
            feedback_label=normalized_label,
        )
        return {
            "job_id": row.job_id,
            "saved": row.saved,
            "feedback_label": row.feedback_label,
            "exists": True,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def _resolve_summary(self, *, digest_path: Any, artifact_root: Any) -> tuple[str | None, str]:
        digest = self._read_digest_file(digest_path)
        if digest:
            return digest, "digest"

        outline = self._read_outline_fallback(artifact_root)
        if outline:
            return outline, "outline"
        return None, "outline"

    def _read_digest_file(self, digest_path: Any) -> str | None:
        if not isinstance(digest_path, str) or not digest_path.strip():
            return None
        path = Path(digest_path).expanduser()
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError:
            return None
        if not resolved.is_file():
            return None
        try:
            text_payload = resolved.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return text_payload or None

    def _read_outline_fallback(self, artifact_root: Any) -> str | None:
        if not isinstance(artifact_root, str) or not artifact_root.strip():
            return None
        outline_path = Path(artifact_root).expanduser() / "outline.json"
        try:
            resolved = outline_path.resolve(strict=True)
        except FileNotFoundError:
            return None
        if not resolved.is_file():
            return None
        try:
            payload = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None

        title = str(payload.get("title") or "").strip() or "Outline"
        summary = str(payload.get("summary") or "").strip()
        if summary:
            return f"# {title}\n\n{summary}"
        return f"# {title}\n\nOutline generated successfully."

    def _resolve_title(self, row: dict[str, Any]) -> str:
        title = str(row.get("title") or "").strip()
        if title:
            return title
        uid = str(row.get("video_uid") or "").strip()
        if uid:
            return uid
        source_url = str(row.get("source_url") or "").strip()
        if source_url:
            return source_url
        return "Untitled"

    def _iso(self, value: Any) -> str:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, str) and value.strip():
            return value
        return datetime.now(UTC).isoformat()

    def _parse_cursor(
        self, cursor: str | None, *, sort: str = "recent"
    ) -> tuple[int | None, str | None, str | None]:
        if not cursor or "__" not in cursor:
            return None, None, None

        parts = [part.strip() for part in cursor.split("__")]
        if sort == "curated":
            if len(parts) != 3:
                return None, None, None
            raw_rank, ts, job_id = parts
            if not raw_rank or not ts or not job_id:
                return None, None, None
            try:
                rank = int(raw_rank)
            except ValueError:
                return None, None, None
            return rank, ts, job_id

        if len(parts) != 2:
            return None, None, None
        ts, job_id = parts[0], parts[1]
        if not ts or not job_id:
            return None, None, None
        return None, ts, job_id

    def _normalize_content_type(self, value: Any) -> str:
        normalized = str(value or "").strip().lower()
        return "article" if normalized == "article" else "video"
