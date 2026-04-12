from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import logging
import re
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings
from ..errors import ApiTimeoutError
from ..repositories import JobsRepository, VideosRepository
from .source_names import build_source_name_fallback, resolve_source_name

YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
BILIBILI_HOSTS = {"bilibili.com", "www.bilibili.com", "m.bilibili.com", "b23.tv"}
ALLOWED_VIDEO_HOST_BASES = ("youtube.com", "youtu.be", "bilibili.com", "b23.tv")
BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata",
    "metadata.google.internal",
    "metadata.google.internal.",
    "100.100.100.200",
    "169.254.169.254",
}
BLOCKED_HOST_SUFFIXES = (".localhost", ".local", ".internal", ".home.arpa")
SUPPORTED_MODES = {"full", "text_only", "refresh_comments", "refresh_llm"}
MODE_ALIASES = {
    "text-only": "text_only",
    "refresh-comments": "refresh_comments",
    "refresh-llm": "refresh_llm",
}
logger = logging.getLogger(__name__)


def _is_allowed_video_host(host: str) -> bool:
    return any(host == base or host.endswith(f".{base}") for base in ALLOWED_VIDEO_HOST_BASES)


def _validate_video_source_url(raw_url: str) -> str:
    value = str(raw_url or "").strip()
    if not value:
        raise ValueError("video_url_empty")

    parsed = urlparse(value)
    scheme = str(parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise ValueError("video_url_invalid_scheme")

    host = str(parsed.hostname or "").strip().lower()
    if not host:
        raise ValueError("video_url_host_required")

    if host in BLOCKED_HOSTS or any(host.endswith(suffix) for suffix in BLOCKED_HOST_SUFFIXES):
        raise ValueError("video_url_blocked_internal_host")

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None

    if ip is not None:
        raise ValueError("video_url_ip_literal_blocked")

    if not _is_allowed_video_host(host):
        raise ValueError("video_url_domain_not_allowed")

    return value


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _url_hash(url: str) -> str:
    return _sha256(url.strip().lower())


def _extract_video_uid(*, platform: str, url: str) -> str:
    parsed = urlparse(url)
    host = str(parsed.hostname or "").strip().lower()
    path = parsed.path or ""
    query = parse_qs(parsed.query)

    if platform == "youtube" and host in YOUTUBE_HOSTS:
        if query.get("v"):
            return str(query["v"][0]).strip()
        if host == "youtu.be":
            candidate = str(path.strip("/").split("/")[0]).strip()
            if candidate:
                return candidate
        return _url_hash(url)

    if platform == "bilibili" and host in BILIBILI_HOSTS:
        bv_match = re.search(r"(BV[0-9A-Za-z]+)", path)
        if bv_match:
            return bv_match.group(1)
        return _url_hash(url)

    return _url_hash(url)


def _build_process_idempotency_key(
    *,
    platform: str,
    video_uid: str,
    mode: str,
    overrides: dict[str, object] | None,
) -> str:
    try:
        normalized_overrides = json.dumps(overrides or {}, ensure_ascii=False, sort_keys=True)
    except TypeError as exc:
        raise ValueError("overrides must be JSON-serializable") from exc
    return _sha256(f"{platform}:{video_uid}:{mode}:{normalized_overrides}")


def _normalize_mode(raw_mode: str) -> str:
    candidate = raw_mode.strip().lower()
    normalized = MODE_ALIASES.get(candidate, candidate)
    if normalized not in SUPPORTED_MODES:
        raise ValueError(f"unsupported mode: {raw_mode}")
    return normalized


def _normalize_overrides(overrides: dict[str, object] | None) -> dict[str, object]:
    normalized = dict(overrides or {})
    llm = normalized.get("llm")
    canonical_llm = dict(llm) if isinstance(llm, dict) else {}
    raw_stage = normalized.get("raw_stage")
    raw_stage_payload = dict(raw_stage) if isinstance(raw_stage, dict) else {}
    analysis_mode = (
        raw_stage_payload.get("mode")
        or raw_stage_payload.get("analysis_mode")
        or canonical_llm.get("analysis_mode")
        or normalized.get("analysis_mode")
        or normalized.get("raw_stage_mode")
    )
    if analysis_mode is not None:
        text = str(analysis_mode).strip().lower().replace("-", "_")
        if text in {"advanced", "economy"}:
            canonical_llm["analysis_mode"] = text
    if canonical_llm:
        normalized["llm"] = canonical_llm
    normalized.pop("analysis_mode", None)
    normalized.pop("raw_stage_mode", None)
    return normalized


def _build_process_workflow_id(job_id: UUID) -> str:
    return f"process-job-{job_id}"


class VideosService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.video_repo = VideosRepository(db)
        self.jobs_repo = JobsRepository(db)

    def list_videos(
        self, *, platform: str | None = None, status: str | None = None, limit: int | None = None
    ):
        resolved_limit = 50 if limit is None else limit
        return self.video_repo.list(platform=platform, status=status, limit=resolved_limit)

    async def process_video(
        self,
        *,
        platform: str,
        url: str,
        video_id: str | None,
        mode: str,
        overrides: dict[str, object] | None,
        force: bool,
        trace_id: str | None = None,
        user: str | None = None,
    ) -> dict[str, object]:
        trace = str(trace_id or "missing_trace")
        actor = str(user or "system")
        validated_url = _validate_video_source_url(url)
        normalized_mode = _normalize_mode(mode)
        normalized_overrides = _normalize_overrides(overrides)
        resolved_video_uid = (video_id or "").strip() or _extract_video_uid(
            platform=platform,
            url=validated_url,
        )
        base_idempotency_key = _build_process_idempotency_key(
            platform=platform,
            video_uid=resolved_video_uid,
            mode=normalized_mode,
            overrides=normalized_overrides,
        )
        idempotency_key = (
            f"{base_idempotency_key}:force:{uuid4().hex}" if force else base_idempotency_key
        )

        video_row = self.video_repo.upsert_for_processing(
            platform=platform,
            video_uid=resolved_video_uid,
            source_url=validated_url,
        )
        job_row, needs_dispatch = self.jobs_repo.create_or_reuse(
            video_id=video_row.id,
            kind="video_digest_v1",
            mode=normalized_mode,
            overrides_json=normalized_overrides,
            idempotency_key=idempotency_key,
            force=force,
        )

        workflow_id: str | None = None
        if needs_dispatch:
            logger.info(
                "video_process_dispatch_started",
                extra={
                    "trace_id": trace,
                    "user": actor,
                    "platform": platform,
                    "video_uid": resolved_video_uid,
                    "job_id": str(job_row.id),
                },
            )
            try:
                from temporalio.client import Client
                from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
            except Exception as exc:  # pragma: no cover
                logger.exception(
                    "video_process_temporal_client_import_failed",
                    extra={"trace_id": trace, "user": actor, "error": str(exc)},
                )
                raise RuntimeError(f"temporal client not available: {exc}") from exc

            try:
                client = await asyncio.wait_for(
                    Client.connect(
                        settings.temporal_target_host,
                        namespace=settings.temporal_namespace,
                    ),
                    timeout=settings.api_temporal_connect_timeout_seconds,
                )
            except TimeoutError as exc:
                logger.error(
                    "video_process_temporal_connect_timeout",
                    extra={
                        "trace_id": trace,
                        "user": actor,
                        "job_id": str(job_row.id),
                        "timeout_seconds": settings.api_temporal_connect_timeout_seconds,
                        "error": str(exc),
                    },
                )
                raise ApiTimeoutError(
                    detail=(
                        "temporal connect timed out "
                        f"after {settings.api_temporal_connect_timeout_seconds:.1f}s"
                    ),
                    error_code="TEMPORAL_CONNECT_TIMEOUT",
                ) from exc
            workflow_id = _build_process_workflow_id(job_row.id)
            try:
                await asyncio.wait_for(
                    client.start_workflow(
                        "ProcessJobWorkflow",
                        str(job_row.id),
                        id=workflow_id,
                        task_queue=settings.temporal_task_queue,
                        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
                    ),
                    timeout=settings.api_temporal_start_timeout_seconds,
                )
            except TimeoutError as exc:
                dispatch_error = (
                    "temporal workflow start timed out "
                    f"after {settings.api_temporal_start_timeout_seconds:.1f}s"
                )
                logger.error(
                    "video_process_temporal_start_timeout",
                    extra={
                        "trace_id": trace,
                        "user": actor,
                        "job_id": str(job_row.id),
                        "workflow_id": workflow_id,
                        "timeout_seconds": settings.api_temporal_start_timeout_seconds,
                        "error": str(exc),
                    },
                )
                self.jobs_repo.mark_dispatch_failed(
                    job_id=job_row.id,
                    error_message=dispatch_error,
                    reason="dispatch_timeout",
                )
                raise ApiTimeoutError(
                    detail=dispatch_error,
                    error_code="TEMPORAL_WORKFLOW_START_TIMEOUT",
                ) from exc
            except Exception as exc:
                dispatch_error = str(exc)
                logger.exception(
                    "video_process_temporal_start_failed",
                    extra={
                        "trace_id": trace,
                        "user": actor,
                        "job_id": str(job_row.id),
                        "workflow_id": workflow_id,
                        "error": dispatch_error,
                    },
                )
                self.jobs_repo.mark_dispatch_failed(job_id=job_row.id, error_message=dispatch_error)
                raise RuntimeError(f"failed to start ProcessJobWorkflow: {dispatch_error}") from exc
        else:
            logger.info(
                "video_process_reused_existing_job",
                extra={
                    "trace_id": trace,
                    "user": actor,
                    "platform": platform,
                    "video_uid": resolved_video_uid,
                    "job_id": str(job_row.id),
                },
            )

        return {
            "job_id": job_row.id,
            "video_db_id": video_row.id,
            "video_uid": resolved_video_uid,
            "status": job_row.status,
            "idempotency_key": job_row.idempotency_key,
            "mode": job_row.mode or normalized_mode,
            "overrides": normalized_overrides,
            "force": force,
            "reused": not needs_dispatch,
            "workflow_id": workflow_id,
        }

    def get_subscription_match_for_video(self, *, video_db_id: UUID) -> dict[str, str] | None:
        row = (
            self.db.execute(
                text(
                    """
                SELECT
                    CAST(s.id AS TEXT) AS subscription_id,
                    s.platform,
                    s.source_type,
                    s.source_value,
                    s.source_url,
                    s.rsshub_route
                FROM ingest_events ie
                JOIN subscriptions s ON s.id = ie.subscription_id
                WHERE ie.video_id = CAST(:video_id AS UUID)
                ORDER BY ie.created_at DESC
                LIMIT 1
                """
                ),
                {"video_id": str(video_db_id)},
            )
            .mappings()
            .first()
        )
        if row is None:
            return None

        platform = str(row.get("platform") or "").strip()
        source_type = str(row.get("source_type") or "").strip()
        source_value = str(row.get("source_value") or "").strip()
        source_url = str(row.get("source_url") or "").strip() or None
        rsshub_route = str(row.get("rsshub_route") or "").strip() or None
        display_name = resolve_source_name(
            source_type=source_type,
            source_value=source_value,
            fallback=build_source_name_fallback(
                platform=platform,
                source_type=source_type,
                source_value=source_value,
                source_url=source_url,
                rsshub_route=rsshub_route,
            ),
        )
        creator_handle = source_value if source_value.startswith("@") else None
        return {
            "subscription_id": str(row.get("subscription_id") or "").strip(),
            "platform": platform,
            "source_type": source_type,
            "source_value": source_value,
            "source_url": source_url or "",
            "rsshub_route": rsshub_route or "",
            "display_name": display_name,
            "creator_handle": creator_handle or "",
        }
