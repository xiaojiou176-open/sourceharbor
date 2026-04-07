from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError


@dataclass
class AdvisoryLockLease:
    connection: Any
    lock_key: str


class PostgresBusinessStore:
    def __init__(self, database_url: str) -> None:
        self._engine: Engine = create_engine(database_url, future=True, pool_pre_ping=True)

    def try_acquire_advisory_lock(
        self,
        *,
        lock_key: str,
    ) -> tuple[bool, AdvisoryLockLease | None, str | None]:
        """Try to acquire a session-level advisory lock.

        Returns:
            - supported: whether advisory lock SQL is available.
            - lease: lock lease when acquired; None when busy/unavailable.
            - reason: unavailability reason when supported is False.
        """
        try:
            conn = self._engine.connect()
        except Exception as exc:
            return False, None, f"connect_failed:{exc.__class__.__name__}"

        try:
            acquired = conn.execute(
                text("SELECT pg_try_advisory_lock(hashtext(:lock_key))"),
                {"lock_key": lock_key},
            ).scalar()
        except Exception as exc:
            conn.close()
            return False, None, f"advisory_unsupported:{exc.__class__.__name__}"

        if bool(acquired):
            return True, AdvisoryLockLease(connection=conn, lock_key=lock_key), None

        conn.close()
        return True, None, None

    def release_advisory_lock(self, lease: AdvisoryLockLease) -> None:
        conn = lease.connection
        try:
            conn.execute(
                text("SELECT pg_advisory_unlock(hashtext(:lock_key))"),
                {"lock_key": lease.lock_key},
            )
        finally:
            conn.close()

    def list_subscriptions(
        self,
        *,
        subscription_id: str | None = None,
        platform: str | None = None,
    ) -> list[dict[str, Any]]:
        filters = ["enabled = TRUE"]
        params: dict[str, Any] = {}
        if subscription_id is not None:
            filters.append("id = CAST(:subscription_id AS UUID)")
            params["subscription_id"] = subscription_id
        if platform is not None:
            filters.append("platform = :platform")
            params["platform"] = platform

        where_clause = " AND ".join(filters)
        with self._engine.begin() as conn:
            rows = (
                conn.execute(
                    text(
                        f"""
                    SELECT
                        id::text AS id,
                        platform,
                        source_type,
                        source_value,
                        adapter_type,
                        source_url,
                        rsshub_route,
                        enabled
                    FROM subscriptions
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    """
                    ),
                    params,
                )
                .mappings()
                .all()
            )
        return [dict(row) for row in rows]

    def upsert_video(
        self,
        *,
        platform: str,
        video_uid: str,
        source_url: str,
        title: str | None,
        published_at: datetime | None,
        content_type: str = "video",
    ) -> dict[str, Any]:
        with self._engine.begin() as conn:
            row = (
                conn.execute(
                    text(
                        """
                    INSERT INTO videos (
                        platform,
                        video_uid,
                        source_url,
                        title,
                        published_at,
                        first_seen_at,
                        last_seen_at,
                        content_type
                    )
                    VALUES (
                        :platform,
                        :video_uid,
                        :source_url,
                        :title,
                        :published_at,
                        NOW(),
                        NOW(),
                        :content_type
                    )
                    ON CONFLICT (platform, video_uid) DO UPDATE SET
                        source_url = EXCLUDED.source_url,
                        title = COALESCE(EXCLUDED.title, videos.title),
                        published_at = COALESCE(EXCLUDED.published_at, videos.published_at),
                        content_type = EXCLUDED.content_type,
                        last_seen_at = NOW()
                    RETURNING
                        id::text AS id,
                        platform,
                        video_uid,
                        source_url,
                        title,
                        published_at,
                        content_type
                    """
                    ),
                    {
                        "platform": platform,
                        "video_uid": video_uid,
                        "source_url": source_url,
                        "title": title,
                        "published_at": published_at,
                        "content_type": content_type,
                    },
                )
                .mappings()
                .one()
            )
        return dict(row)

    def get_ingest_event(
        self,
        *,
        subscription_id: str,
        entry_hash: str,
    ) -> dict[str, Any] | None:
        with self._engine.begin() as conn:
            row = (
                conn.execute(
                    text(
                        """
                    SELECT id::text AS id, video_id::text AS video_id
                    FROM ingest_events
                    WHERE subscription_id = CAST(:subscription_id AS UUID)
                      AND entry_hash = :entry_hash
                    LIMIT 1
                    """
                    ),
                    {
                        "subscription_id": subscription_id,
                        "entry_hash": entry_hash,
                    },
                )
                .mappings()
                .first()
            )
        return dict(row) if row else None

    def create_ingest_event(
        self,
        *,
        subscription_id: str,
        feed_guid: str | None,
        feed_link: str | None,
        entry_hash: str,
        video_id: str,
    ) -> tuple[dict[str, Any], bool]:
        with self._engine.begin() as conn:
            row = (
                conn.execute(
                    text(
                        """
                    INSERT INTO ingest_events (
                        subscription_id,
                        feed_guid,
                        feed_link,
                        entry_hash,
                        video_id,
                        created_at
                    )
                    VALUES (
                        CAST(:subscription_id AS UUID),
                        :feed_guid,
                        :feed_link,
                        :entry_hash,
                        CAST(:video_id AS UUID),
                        NOW()
                    )
                    ON CONFLICT (subscription_id, entry_hash) DO NOTHING
                    RETURNING id::text AS id, video_id::text AS video_id
                    """
                    ),
                    {
                        "subscription_id": subscription_id,
                        "feed_guid": feed_guid,
                        "feed_link": feed_link,
                        "entry_hash": entry_hash,
                        "video_id": video_id,
                    },
                )
                .mappings()
                .first()
            )

        if row:
            return dict(row), True

        existing = self.get_ingest_event(subscription_id=subscription_id, entry_hash=entry_hash)
        if existing is None:
            raise RuntimeError("failed to create or fetch ingest_event")
        return existing, False

    def find_active_job(self, *, idempotency_key: str) -> dict[str, Any] | None:
        with self._engine.begin() as conn:
            row = (
                conn.execute(
                    text(
                        """
                    SELECT id::text AS id, status
                    FROM jobs
                    WHERE idempotency_key = :idempotency_key
                      AND status IN ('queued', 'running', 'succeeded')
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                    ),
                    {"idempotency_key": idempotency_key},
                )
                .mappings()
                .first()
            )
        return dict(row) if row else None

    def find_job_by_idempotency_key(self, *, idempotency_key: str) -> dict[str, Any] | None:
        with self._engine.begin() as conn:
            row = (
                conn.execute(
                    text(
                        """
                    SELECT id::text AS id, status
                    FROM jobs
                    WHERE idempotency_key = :idempotency_key
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                    ),
                    {"idempotency_key": idempotency_key},
                )
                .mappings()
                .first()
            )
        return dict(row) if row else None

    def create_queued_job(
        self,
        *,
        video_id: str,
        idempotency_key: str,
        mode: str | None = None,
        overrides_json: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], bool]:
        overrides_raw = json.dumps(overrides_json) if overrides_json else None
        try:
            with self._engine.begin() as conn:
                row = (
                    conn.execute(
                        text(
                            """
                        INSERT INTO jobs (
                            video_id,
                            kind,
                            status,
                            idempotency_key,
                            mode,
                            overrides_json,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            CAST(:video_id AS UUID),
                            'video_digest_v1',
                            'queued',
                            :idempotency_key,
                            :mode,
                            CAST(:overrides_json AS JSONB),
                            NOW(),
                            NOW()
                        )
                        RETURNING id::text AS id, status, mode
                        """
                        ),
                        {
                            "video_id": video_id,
                            "idempotency_key": idempotency_key,
                            "mode": mode,
                            "overrides_json": overrides_raw,
                        },
                    )
                    .mappings()
                    .one()
                )
                return dict(row), True
        except IntegrityError:
            existing = self.find_job_by_idempotency_key(idempotency_key=idempotency_key)
            if existing is None:
                raise
            return existing, False

    def mark_job_running(self, *, job_id: str) -> dict[str, Any]:
        with self._engine.begin() as conn:
            row = (
                conn.execute(
                    text(
                        """
                    UPDATE jobs
                    SET status = 'running',
                        error_message = NULL,
                        hard_fail_reason = NULL,
                        updated_at = NOW()
                    WHERE id = CAST(:job_id AS UUID)
                      AND status = 'queued'
                    RETURNING id::text AS id, status
                    """
                    ),
                    {"job_id": job_id},
                )
                .mappings()
                .first()
            )

            if row is not None:
                payload = dict(row)
                payload["transitioned"] = True
                return payload

            existing = (
                conn.execute(
                    text(
                        """
                    SELECT id::text AS id, status
                    FROM jobs
                    WHERE id = CAST(:job_id AS UUID)
                    """
                    ),
                    {"job_id": job_id},
                )
                .mappings()
                .first()
            )
            if existing is None:
                raise ValueError(f"job not found: {job_id}")
            payload = dict(existing)
            payload["transitioned"] = False
            payload["conflict"] = "already_running" if payload.get("status") == "running" else None
            return payload

    def fail_stale_queued_jobs(
        self,
        *,
        timeout_seconds: int,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        safe_timeout_seconds = max(60, int(timeout_seconds))
        safe_limit = max(1, int(limit))
        with self._engine.begin() as conn:
            rows = (
                conn.execute(
                    text(
                        """
                    WITH stale_jobs AS (
                        SELECT id
                        FROM jobs
                        WHERE status = 'queued'
                          AND updated_at <= NOW() - (CAST(:timeout_seconds AS TEXT) || ' seconds')::INTERVAL
                        ORDER BY updated_at ASC
                        LIMIT :limit
                        FOR UPDATE SKIP LOCKED
                    )
                    UPDATE jobs AS j
                    SET
                        status = 'failed',
                        error_message = CASE
                            WHEN COALESCE(j.error_message, '') = '' THEN :error_message
                            ELSE j.error_message
                        END,
                        pipeline_final_status = 'failed',
                        hard_fail_reason = 'dispatch_timeout',
                        updated_at = NOW()
                    FROM stale_jobs
                    WHERE j.id = stale_jobs.id
                    RETURNING
                        j.id::text AS id,
                        j.status,
                        j.updated_at,
                        j.hard_fail_reason,
                        j.error_message
                    """
                    ),
                    {
                        "timeout_seconds": safe_timeout_seconds,
                        "limit": safe_limit,
                        "error_message": "workflow_dispatch_timeout",
                    },
                )
                .mappings()
                .all()
            )
        return [dict(row) for row in rows]

    def get_job_with_video(self, *, job_id: str) -> dict[str, Any]:
        with self._engine.begin() as conn:
            row = (
                conn.execute(
                    text(
                        """
                    SELECT
                        j.id::text AS job_id,
                        j.status AS job_status,
                        j.kind AS job_kind,
                        j.mode AS mode,
                        j.overrides_json AS overrides_json,
                        j.idempotency_key AS idempotency_key,
                        v.id::text AS video_id,
                        v.platform AS platform,
                        v.video_uid AS video_uid,
                        v.source_url AS source_url,
                        v.title AS title,
                        v.published_at AS published_at,
                        COALESCE(v.content_type, 'video') AS content_type
                    FROM jobs j
                    JOIN videos v ON v.id = j.video_id
                    WHERE j.id = CAST(:job_id AS UUID)
                    LIMIT 1
                    """
                    ),
                    {"job_id": job_id},
                )
                .mappings()
                .first()
            )
            if row is None:
                raise ValueError(f"job not found: {job_id}")
        return dict(row)

    @staticmethod
    def _to_vector_literal(values: list[float]) -> str:
        if not values:
            raise ValueError("embedding vector is empty")
        return "[" + ",".join(f"{float(value):.10f}" for value in values) + "]"

    @staticmethod
    def _video_embeddings_table_exists(conn: Any) -> bool:
        exists = conn.execute(
            text("SELECT to_regclass('public.video_embeddings') IS NOT NULL")
        ).scalar()
        return bool(exists)

    def upsert_video_embeddings(
        self,
        *,
        video_id: str,
        job_id: str,
        model: str,
        items: list[dict[str, Any]],
    ) -> int:
        if not items:
            return 0

        with self._engine.begin() as conn:
            if not self._video_embeddings_table_exists(conn):
                return 0
            conn.execute(
                text(
                    """
                    DELETE FROM video_embeddings
                    WHERE job_id = CAST(:job_id AS UUID)
                    """
                ),
                {"job_id": job_id},
            )

            for item in items:
                content_type = str(item.get("content_type") or "").strip().lower()
                if content_type not in {"transcript", "outline"}:
                    raise ValueError(f"invalid embedding content_type: {content_type}")
                embedding = item.get("embedding")
                if not isinstance(embedding, list) or not embedding:
                    raise ValueError("embedding payload missing numeric vector")
                conn.execute(
                    text(
                        """
                        INSERT INTO video_embeddings (
                            video_id,
                            job_id,
                            content_type,
                            chunk_index,
                            chunk_text,
                            embedding_model,
                            embedding,
                            metadata_json,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            CAST(:video_id AS UUID),
                            CAST(:job_id AS UUID),
                            :content_type,
                            :chunk_index,
                            :chunk_text,
                            :embedding_model,
                            CAST(:embedding AS vector(768)),
                            CAST(:metadata_json AS JSONB),
                            NOW(),
                            NOW()
                        )
                        """
                    ),
                    {
                        "video_id": video_id,
                        "job_id": job_id,
                        "content_type": content_type,
                        "chunk_index": int(item.get("chunk_index") or 0),
                        "chunk_text": str(item.get("chunk_text") or ""),
                        "embedding_model": model,
                        "embedding": self._to_vector_literal([float(v) for v in embedding]),
                        "metadata_json": json.dumps(item.get("metadata") or {}, ensure_ascii=False),
                    },
                )
        return len(items)

    def search_video_embeddings(
        self,
        *,
        query_embedding: list[float],
        limit: int = 8,
        video_id: str | None = None,
        content_type: str | None = None,
    ) -> list[dict[str, Any]]:
        if not query_embedding:
            return []

        normalized_limit = max(1, int(limit))
        normalized_content_type = str(content_type or "").strip().lower() or None
        with self._engine.begin() as conn:
            if not self._video_embeddings_table_exists(conn):
                return []
            rows = (
                conn.execute(
                    text(
                        """
                    SELECT
                        id::text AS id,
                        video_id::text AS video_id,
                        job_id::text AS job_id,
                        content_type,
                        chunk_index,
                        chunk_text,
                        embedding_model,
                        metadata_json,
                        1 - (embedding <=> CAST(:query_embedding AS vector(768))) AS score
                    FROM video_embeddings
                    WHERE (:video_id IS NULL OR video_id = CAST(:video_id AS UUID))
                      AND (:content_type IS NULL OR content_type = :content_type)
                    ORDER BY embedding <=> CAST(:query_embedding AS vector(768)) ASC
                    LIMIT :limit
                    """
                    ),
                    {
                        "query_embedding": self._to_vector_literal(
                            [float(v) for v in query_embedding]
                        ),
                        "video_id": video_id,
                        "content_type": normalized_content_type,
                        "limit": normalized_limit,
                    },
                )
                .mappings()
                .all()
            )
        return [dict(row) for row in rows]

    @staticmethod
    def _knowledge_cards_table_exists(conn: Any) -> bool:
        exists = conn.execute(
            text("SELECT to_regclass('public.knowledge_cards') IS NOT NULL")
        ).scalar()
        return bool(exists)

    def replace_knowledge_cards(
        self,
        *,
        video_id: str,
        job_id: str,
        items: list[dict[str, Any]],
    ) -> int:
        if not items:
            return 0

        with self._engine.begin() as conn:
            if not self._knowledge_cards_table_exists(conn):
                return 0
            conn.execute(
                text(
                    """
                    DELETE FROM knowledge_cards
                    WHERE job_id = CAST(:job_id AS UUID)
                    """
                ),
                {"job_id": job_id},
            )
            for item in items:
                conn.execute(
                    text(
                        """
                        INSERT INTO knowledge_cards (
                            video_id,
                            job_id,
                            card_type,
                            source_section,
                            title,
                            body,
                            ordinal,
                            metadata_json,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            CAST(:video_id AS UUID),
                            CAST(:job_id AS UUID),
                            :card_type,
                            :source_section,
                            :title,
                            :body,
                            :ordinal,
                            CAST(:metadata_json AS JSONB),
                            NOW(),
                            NOW()
                        )
                        """
                    ),
                    {
                        "video_id": video_id,
                        "job_id": job_id,
                        "card_type": str(item.get("card_type") or "takeaway"),
                        "source_section": str(item.get("source_section") or "highlights"),
                        "title": str(item.get("title") or "") or None,
                        "body": str(item.get("body") or ""),
                        "ordinal": int(item.get("ordinal") or 0),
                        "metadata_json": json.dumps(item.get("metadata") or {}, ensure_ascii=False),
                    },
                )
        return len(items)

    def mark_job_succeeded(
        self,
        *,
        job_id: str,
        status: str = "succeeded",
        artifact_digest_md: str | None = None,
        artifact_root: str | None = None,
        pipeline_final_status: str | None = None,
        degradation_count: int | None = None,
        last_error_code: str | None = None,
        llm_required: bool | None = None,
        llm_gate_passed: bool | None = None,
        hard_fail_reason: str | None = None,
    ) -> dict[str, Any]:
        if status not in {"succeeded"}:
            raise ValueError(f"invalid succeeded status: {status}")
        final_status = pipeline_final_status or status
        if final_status not in {"succeeded", "degraded", "failed"}:
            raise ValueError(f"invalid pipeline_final_status: {final_status}")
        if degradation_count is not None and degradation_count < 0:
            raise ValueError("degradation_count must be >= 0")
        return self._mark_job_status(
            job_id=job_id,
            status=status,
            error_message=None,
            artifact_digest_md=artifact_digest_md,
            artifact_root=artifact_root,
            pipeline_final_status=final_status,
            degradation_count=degradation_count,
            last_error_code=last_error_code,
            llm_required=llm_required,
            llm_gate_passed=llm_gate_passed,
            hard_fail_reason=hard_fail_reason,
        )

    def mark_job_failed(
        self,
        *,
        job_id: str,
        error_message: str,
        pipeline_final_status: str | None = None,
        degradation_count: int | None = None,
        last_error_code: str | None = None,
        llm_required: bool | None = None,
        llm_gate_passed: bool | None = None,
        hard_fail_reason: str | None = None,
    ) -> dict[str, Any]:
        final_status = pipeline_final_status or "failed"
        if final_status not in {"succeeded", "degraded", "failed"}:
            raise ValueError(f"invalid pipeline_final_status: {final_status}")
        if degradation_count is not None and degradation_count < 0:
            raise ValueError("degradation_count must be >= 0")
        return self._mark_job_status(
            job_id=job_id,
            status="failed",
            error_message=error_message,
            artifact_digest_md=None,
            artifact_root=None,
            pipeline_final_status=final_status,
            degradation_count=degradation_count,
            last_error_code=last_error_code,
            llm_required=llm_required,
            llm_gate_passed=llm_gate_passed,
            hard_fail_reason=hard_fail_reason,
        )

    def _mark_job_status(
        self,
        *,
        job_id: str,
        status: str,
        error_message: str | None,
        artifact_digest_md: str | None,
        artifact_root: str | None,
        pipeline_final_status: str | None,
        degradation_count: int | None,
        last_error_code: str | None,
        llm_required: bool | None,
        llm_gate_passed: bool | None,
        hard_fail_reason: str | None,
    ) -> dict[str, Any]:
        with self._engine.begin() as conn:
            row = (
                conn.execute(
                    text(
                        """
                    UPDATE jobs
                    SET status = :status,
                        error_message = :error_message,
                        artifact_digest_md = COALESCE(:artifact_digest_md, artifact_digest_md),
                        artifact_root = COALESCE(:artifact_root, artifact_root),
                        pipeline_final_status = :pipeline_final_status,
                        degradation_count = :degradation_count,
                        last_error_code = :last_error_code,
                        llm_required = COALESCE(:llm_required, llm_required),
                        llm_gate_passed = :llm_gate_passed,
                        hard_fail_reason = :hard_fail_reason,
                        updated_at = NOW()
                    WHERE id = CAST(:job_id AS UUID)
                      AND status IN ('queued', 'running')
                    RETURNING
                        id::text AS id,
                        status,
                        pipeline_final_status,
                        degradation_count,
                        last_error_code,
                        llm_required,
                        llm_gate_passed,
                        hard_fail_reason
                    """
                    ),
                    {
                        "job_id": job_id,
                        "status": status,
                        "error_message": error_message,
                        "artifact_digest_md": artifact_digest_md,
                        "artifact_root": artifact_root,
                        "pipeline_final_status": pipeline_final_status,
                        "degradation_count": degradation_count,
                        "last_error_code": last_error_code,
                        "llm_required": llm_required,
                        "llm_gate_passed": llm_gate_passed,
                        "hard_fail_reason": hard_fail_reason,
                    },
                )
                .mappings()
                .first()
            )
            if row is not None:
                payload = dict(row)
                payload["transitioned"] = True
                return payload

            existing = (
                conn.execute(
                    text(
                        """
                    SELECT
                        id::text AS id,
                        status,
                        pipeline_final_status,
                        degradation_count,
                        last_error_code,
                        llm_required,
                        llm_gate_passed,
                        hard_fail_reason
                    FROM jobs
                    WHERE id = CAST(:job_id AS UUID)
                    """
                    ),
                    {"job_id": job_id},
                )
                .mappings()
                .first()
            )
            if existing is None:
                raise ValueError(f"job not found: {job_id}")
            payload = dict(existing)
            payload["transitioned"] = False
            payload["conflict"] = (
                "terminal_status" if payload.get("status") in {"succeeded", "failed"} else None
            )
            return payload
