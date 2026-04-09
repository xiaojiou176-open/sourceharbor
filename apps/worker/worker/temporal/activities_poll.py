from __future__ import annotations

import json
import logging
from os import getenv, getpid
from typing import Any

from sqlalchemy import text

from worker.config import Settings
from worker.rss.adapters import poll_subscription_entries, resolve_feed_url
from worker.rss.normalizer import make_article_idempotency_key
from worker.state.mirrored_sqlite_store import MirroredSQLiteStateStore
from worker.state.postgres_store import PostgresBusinessStore
from worker.temporal.activities_timing import _utc_now_iso

try:
    from temporalio import activity
except ModuleNotFoundError:  # pragma: no cover

    class _ActivityFallback:
        @staticmethod
        def defn(name: str | None = None):
            def _decorator(func):
                return func

            return _decorator

    activity = _ActivityFallback()

logger = logging.getLogger(__name__)
SQLiteStateStore = MirroredSQLiteStateStore
_STRONG_VIDEO_SOURCES = {
    ("youtube", "youtube_channel_id"),
    ("bilibili", "bilibili_uid"),
}


def _build_runtime_sqlite_store(settings: Settings) -> Any:
    mirror_paths: list[str] = []
    api_state_path = str(getenv("SQLITE_STATE_PATH", "")).strip()
    if api_state_path:
        mirror_paths.append(api_state_path)
    store_cls = SQLiteStateStore
    if hasattr(store_cls, "from_paths"):
        return store_cls.from_paths(
            primary_path=settings.sqlite_path,
            mirror_paths=mirror_paths,
        )
    return store_cls(settings.sqlite_path)


def _mark_ingest_run_running(pg_store: PostgresBusinessStore, *, run_id: str | None) -> None:
    if not run_id:
        return
    with pg_store._engine.begin() as conn:  # noqa: SLF001
        conn.execute(
            text(
                """
                UPDATE ingest_runs
                SET status = 'running',
                    updated_at = NOW(),
                    error_message = NULL
                WHERE id = CAST(:run_id AS UUID)
                """
            ),
            {"run_id": run_id},
        )


def _complete_ingest_run(
    pg_store: PostgresBusinessStore,
    *,
    run_id: str | None,
    status: str,
    filters: dict[str, Any],
    summary: dict[str, Any],
    items: list[dict[str, Any]],
    error_message: str | None = None,
) -> None:
    if not run_id:
        return

    with pg_store._engine.begin() as conn:  # noqa: SLF001
        conn.execute(
            text("DELETE FROM ingest_run_items WHERE ingest_run_id = CAST(:run_id AS UUID)"),
            {"run_id": run_id},
        )
        for item in items:
            conn.execute(
                text(
                    """
                    INSERT INTO ingest_run_items (
                        ingest_run_id,
                        subscription_id,
                        video_id,
                        job_id,
                        ingest_event_id,
                        platform,
                        video_uid,
                        source_url,
                        title,
                        published_at,
                        entry_hash,
                        pipeline_mode,
                        content_type,
                        item_status,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        CAST(:run_id AS UUID),
                        CAST(:subscription_id AS UUID),
                        CAST(:video_id AS UUID),
                        CAST(:job_id AS UUID),
                        CAST(:ingest_event_id AS UUID),
                        :platform,
                        :video_uid,
                        :source_url,
                        :title,
                        :published_at,
                        :entry_hash,
                        :pipeline_mode,
                        :content_type,
                        :item_status,
                        NOW(),
                        NOW()
                    )
                    """
                ),
                {
                    "run_id": run_id,
                    "subscription_id": item.get("subscription_id"),
                    "video_id": item.get("video_id"),
                    "job_id": item.get("job_id"),
                    "ingest_event_id": item.get("ingest_event_id"),
                    "platform": item.get("platform"),
                    "video_uid": item.get("video_uid"),
                    "source_url": item.get("source_url"),
                    "title": item.get("title"),
                    "published_at": item.get("published_at"),
                    "entry_hash": item.get("entry_hash"),
                    "pipeline_mode": item.get("pipeline_mode"),
                    "content_type": item.get("content_type") or "video",
                    "item_status": item.get("item_status") or "queued",
                },
            )

        conn.execute(
            text(
                """
                UPDATE ingest_runs
                SET status = :status,
                    filters_json = CAST(:filters_json AS JSONB),
                    jobs_created = :jobs_created,
                    candidates_count = :candidates_count,
                    feeds_polled = :feeds_polled,
                    entries_fetched = :entries_fetched,
                    entries_normalized = :entries_normalized,
                    ingest_events_created = :ingest_events_created,
                    ingest_event_duplicates = :ingest_event_duplicates,
                    job_duplicates = :job_duplicates,
                    error_message = :error_message,
                    completed_at = NOW(),
                    updated_at = NOW()
                WHERE id = CAST(:run_id AS UUID)
                """
            ),
            {
                "run_id": run_id,
                "status": status,
                "filters_json": json.dumps(filters, ensure_ascii=False, sort_keys=True),
                "jobs_created": int(summary.get("jobs_created", 0)),
                "candidates_count": int(summary.get("candidates_count", 0)),
                "feeds_polled": int(summary.get("feeds_polled", 0)),
                "entries_fetched": int(summary.get("entries_fetched", 0)),
                "entries_normalized": int(summary.get("entries_normalized", 0)),
                "ingest_events_created": int(summary.get("ingest_events_created", 0)),
                "ingest_event_duplicates": int(summary.get("ingest_event_duplicates", 0)),
                "job_duplicates": int(summary.get("job_duplicates", 0)),
                "error_message": error_message,
            },
        )


async def run_poll_feeds_once(
    settings: Settings,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from worker.rss.fetcher import RSSHubFetcher

    filters = dict(filters or {})
    ingest_run_id = str(filters.get("ingest_run_id") or "").strip() or None

    sqlite_store = _build_runtime_sqlite_store(settings)
    pg_store = PostgresBusinessStore(settings.database_url)
    lock_owner = f"pid-{getpid()}"
    lock_key = "phase2.poll_feeds"
    lock_backend: str | None = None
    pg_lock_lease = None
    _mark_ingest_run_running(pg_store, run_id=ingest_run_id)

    advisory_supported, pg_lock_lease, advisory_reason = pg_store.try_acquire_advisory_lock(
        lock_key=lock_key
    )
    if advisory_supported:
        if pg_lock_lease is None:
            result = {"ok": True, "skipped": True, "reason": "lock_not_acquired"}
            _complete_ingest_run(
                pg_store,
                run_id=ingest_run_id,
                status="skipped",
                filters=filters,
                summary={
                    "jobs_created": 0,
                    "candidates_count": 0,
                    "feeds_polled": 0,
                    "entries_fetched": 0,
                    "entries_normalized": 0,
                    "ingest_events_created": 0,
                    "ingest_event_duplicates": 0,
                    "job_duplicates": 0,
                },
                items=[],
            )
            return result
        lock_backend = "postgres_advisory"
    else:
        logger.warning(
            "poll_advisory_lock_unavailable",
            extra={
                "trace_id": "missing_trace",
                "user": "poll_feeds_activity",
                "lock_key": lock_key,
                "reason": advisory_reason,
                "error": "advisory_lock_unavailable",
            },
        )
        if not sqlite_store.acquire_lock(lock_key, lock_owner, settings.lock_ttl_seconds):
            result = {"ok": True, "skipped": True, "reason": "lock_not_acquired"}
            _complete_ingest_run(
                pg_store,
                run_id=ingest_run_id,
                status="skipped",
                filters=filters,
                summary={
                    "jobs_created": 0,
                    "candidates_count": 0,
                    "feeds_polled": 0,
                    "entries_fetched": 0,
                    "entries_normalized": 0,
                    "ingest_events_created": 0,
                    "ingest_event_duplicates": 0,
                    "job_duplicates": 0,
                },
                items=[],
            )
            return result
        lock_backend = "sqlite_local"

    run_items: list[dict[str, Any]] = []
    try:
        subscriptions = pg_store.list_subscriptions(
            subscription_id=filters.get("subscription_id"),
            platform=filters.get("platform"),
        )

        feed_to_subscription: dict[str, dict[str, Any]] = {}
        for item in subscriptions:
            try:
                feed_url = resolve_feed_url(settings, item)
            except ValueError:
                continue
            feed_to_subscription[feed_url] = item

        feed_urls = list(feed_to_subscription.keys())
        fetcher = RSSHubFetcher(
            timeout_seconds=settings.request_timeout_seconds,
            retry_attempts=settings.request_retry_attempts,
            retry_backoff_seconds=settings.request_retry_backoff_seconds,
            public_fallback_base_url=settings.rsshub_public_fallback_base_url,
            public_fallback_base_urls=settings.rsshub_fallback_base_urls,
        )
        created_job_ids: list[str] = []
        candidates: list[dict[str, Any]] = []
        max_new = int(filters.get("max_new_videos") or 50)

        entries_fetched = 0
        entries_normalized = 0
        ingest_events_created = 0
        ingest_event_duplicates = 0
        job_duplicates = 0

        for feed_url in feed_urls:
            subscription = feed_to_subscription.get(feed_url)
            if not subscription:
                continue
            try:
                _, normalized_entries = await poll_subscription_entries(
                    settings=settings,
                    fetcher=fetcher,
                    subscription=subscription,
                )
            except ValueError:
                normalized_entries = []

            entries_fetched += len(normalized_entries)
            for normalized in normalized_entries:
                entries_normalized += 1

                platform = _resolve_platform(normalized=normalized, subscription=subscription)
                content_type = _resolve_content_type(
                    normalized=normalized,
                    subscription=subscription,
                )
                force_entry_hash_uid = (
                    content_type == "article"
                    and not _is_strong_video_subscription(subscription=subscription)
                )
                video_uid = _resolve_video_uid(
                    normalized=normalized,
                    force_entry_hash=force_entry_hash_uid,
                )
                job_idempotency_key = _resolve_job_idempotency_key(
                    normalized=normalized,
                    content_type=content_type,
                    force_article_key=force_entry_hash_uid,
                )

                video = pg_store.upsert_video(
                    platform=platform,
                    video_uid=video_uid,
                    source_url=normalized.get("link") or feed_url,
                    title=normalized.get("title") or None,
                    published_at=normalized.get("published_at"),
                    content_type=content_type,
                )

                ingest_event, event_created = pg_store.create_ingest_event(
                    subscription_id=subscription["id"],
                    feed_guid=normalized.get("guid"),
                    feed_link=normalized.get("link"),
                    entry_hash=normalized["entry_hash"],
                    video_id=video["id"],
                )
                if event_created:
                    ingest_events_created += 1
                else:
                    ingest_event_duplicates += 1

                existing_job = pg_store.find_active_job(idempotency_key=job_idempotency_key)
                if existing_job is not None:
                    job_duplicates += 1
                    continue

                pipeline_mode: str | None = "text_only" if content_type == "article" else None

                job_overrides: dict[str, Any] | None = None
                if content_type == "article":
                    job_overrides = {}
                    if normalized.get("content"):
                        job_overrides["rss_content"] = normalized["content"]
                    if normalized.get("summary"):
                        job_overrides["rss_summary"] = normalized["summary"]

                job, created = pg_store.create_queued_job(
                    video_id=video["id"],
                    idempotency_key=job_idempotency_key,
                    mode=pipeline_mode,
                    overrides_json=job_overrides,
                )
                if not created:
                    job_duplicates += 1
                    continue

                created_job_ids.append(job["id"])
                run_items.append(
                    {
                        "subscription_id": subscription["id"],
                        "video_id": video["id"],
                        "job_id": job["id"],
                        "ingest_event_id": ingest_event["id"],
                        "platform": video["platform"],
                        "video_uid": video["video_uid"],
                        "source_url": video["source_url"],
                        "title": video.get("title"),
                        "published_at": video.get("published_at"),
                        "entry_hash": normalized["entry_hash"],
                        "pipeline_mode": pipeline_mode,
                        "content_type": content_type,
                        "item_status": "pending_consume",
                    }
                )
                if len(candidates) < max_new:
                    rss_transcript = _build_rss_transcript(normalized)
                    candidates.append(
                        {
                            "job_id": job["id"],
                            "video_id": video["id"],
                            "platform": video["platform"],
                            "video_uid": video["video_uid"],
                            "source_url": video["source_url"],
                            "title": video.get("title"),
                            "published_at": video.get("published_at"),
                            "entry_hash": normalized["entry_hash"],
                            "ingest_event_id": ingest_event["id"],
                            "pipeline_mode": pipeline_mode,
                            "subscription_id": subscription["id"],
                            "content_type": content_type,
                            "rss_transcript": rss_transcript,
                        }
                    )

        result = {
            "ok": True,
            "phase": "phase2",
            "feeds_polled": len(feed_urls),
            "entries_fetched": entries_fetched,
            "entries_normalized": entries_normalized,
            "ingest_events_created": ingest_events_created,
            "ingest_event_duplicates": ingest_event_duplicates,
            "jobs_created": len(created_job_ids),
            "job_duplicates": job_duplicates,
            "created_job_ids": created_job_ids,
            "candidates": candidates,
            "at": _utc_now_iso(),
            "filters": filters,
        }
        _complete_ingest_run(
            pg_store,
            run_id=ingest_run_id,
            status="succeeded",
            filters=filters,
            summary={
                "jobs_created": len(created_job_ids),
                "candidates_count": len(run_items),
                "feeds_polled": len(feed_urls),
                "entries_fetched": entries_fetched,
                "entries_normalized": entries_normalized,
                "ingest_events_created": ingest_events_created,
                "ingest_event_duplicates": ingest_event_duplicates,
                "job_duplicates": job_duplicates,
            },
            items=run_items,
        )
        return result
    except Exception as exc:
        _complete_ingest_run(
            pg_store,
            run_id=ingest_run_id,
            status="failed",
            filters=filters,
            summary={
                "jobs_created": len(run_items),
                "candidates_count": len(run_items),
                "feeds_polled": 0,
                "entries_fetched": 0,
                "entries_normalized": 0,
                "ingest_events_created": 0,
                "ingest_event_duplicates": 0,
                "job_duplicates": 0,
            },
            items=run_items,
            error_message=str(exc),
        )
        raise
    finally:
        if lock_backend == "postgres_advisory" and pg_lock_lease is not None:
            pg_store.release_advisory_lock(pg_lock_lease)
        elif lock_backend == "sqlite_local":
            sqlite_store.release_lock(lock_key, lock_owner)


def _resolve_platform(*, normalized: dict[str, Any], subscription: dict[str, Any]) -> str:
    normalized_platform = str(normalized.get("video_platform") or "").strip().lower()
    if normalized_platform:
        return normalized_platform
    fallback_platform = str(subscription.get("platform") or "").strip().lower()
    return fallback_platform or "generic"


def _is_strong_video_subscription(*, subscription: dict[str, Any]) -> bool:
    platform = str(subscription.get("platform") or "").strip().lower()
    source_type = str(subscription.get("source_type") or "").strip().lower()
    if not source_type and platform in {"youtube", "bilibili"}:
        return True
    return (platform, source_type) in _STRONG_VIDEO_SOURCES


def _resolve_content_type(*, normalized: dict[str, Any], subscription: dict[str, Any]) -> str:
    content_type = str(normalized.get("content_type") or "video").strip().lower()
    if content_type not in ("video", "article"):
        content_type = "video"
    if content_type == "article":
        return "article"
    if _is_strong_video_subscription(subscription=subscription):
        return "video"
    return "article"


def _resolve_video_uid(*, normalized: dict[str, Any], force_entry_hash: bool = False) -> str:
    if force_entry_hash:
        entry_hash = str(normalized.get("entry_hash") or "").strip()
        if entry_hash:
            return entry_hash
    candidate = str(normalized.get("video_uid") or "").strip()
    if candidate:
        return candidate
    entry_hash = str(normalized.get("entry_hash") or "").strip()
    if entry_hash:
        return entry_hash
    return "unknown"


def _resolve_job_idempotency_key(
    *,
    normalized: dict[str, Any],
    content_type: str,
    force_article_key: bool = False,
) -> str:
    if content_type == "article" and force_article_key:
        entry_hash = str(normalized.get("entry_hash") or "").strip()
        if entry_hash:
            return make_article_idempotency_key(entry_hash)
    candidate = str(normalized.get("idempotency_key") or "").strip()
    if candidate:
        return candidate
    entry_hash = str(normalized.get("entry_hash") or "").strip()
    if entry_hash:
        return make_article_idempotency_key(entry_hash)
    return "unknown"


def _build_rss_transcript(normalized: dict[str, Any]) -> str | None:
    """Assemble a plain-text transcript from RSS entry fields for text-only pipeline."""
    parts: list[str] = []
    title = str(normalized.get("title") or "").strip()
    if title:
        parts.append(f"# {title}\n")
    content = str(normalized.get("content") or normalized.get("summary") or "").strip()
    if content:
        parts.append(content)
    link = str(normalized.get("link") or "").strip()
    if link:
        parts.append(f"\nSource: {link}")
    published = str(normalized.get("published_at") or "").strip()
    if published:
        parts.append(f"Published: {published}")
    return "\n".join(parts) if parts else None


@activity.defn(name="poll_feeds_activity")
async def poll_feeds_activity(filters: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = Settings.from_env()
    return await run_poll_feeds_once(settings, filters=filters)
