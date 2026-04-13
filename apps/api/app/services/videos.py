from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import logging
import re
import subprocess
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from integrations.binaries.media_commands import yt_dlp_metadata_command

from ..config import settings
from ..errors import ApiTimeoutError
from ..repositories import JobsRepository, PublishedReaderDocumentsRepository, VideosRepository
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


def _validate_external_source_url(raw_url: str) -> str:
    value = str(raw_url or "").strip()
    if not value:
        raise ValueError("source_url_empty")

    parsed = urlparse(value)
    scheme = str(parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise ValueError("source_url_invalid_scheme")

    host = str(parsed.hostname or "").strip().lower()
    if not host:
        raise ValueError("source_url_host_required")

    if host in BLOCKED_HOSTS or any(host.endswith(suffix) for suffix in BLOCKED_HOST_SUFFIXES):
        raise ValueError("source_url_blocked_internal_host")

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None

    if ip is not None:
        raise ValueError("source_url_ip_literal_blocked")
    return value


def _validate_video_source_url(raw_url: str) -> str:
    try:
        value = _validate_external_source_url(raw_url)
    except ValueError as exc:
        detail = str(exc)
        if detail == "source_url_empty":
            raise ValueError("video_url_empty") from exc
        if detail == "source_url_invalid_scheme":
            raise ValueError("video_url_invalid_scheme") from exc
        if detail == "source_url_host_required":
            raise ValueError("video_url_host_required") from exc
        if detail == "source_url_blocked_internal_host":
            raise ValueError("video_url_blocked_internal_host") from exc
        if detail == "source_url_ip_literal_blocked":
            raise ValueError("video_url_ip_literal_blocked") from exc
        raise
    host = str(urlparse(value).hostname or "").strip().lower()
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


def _normalize_analysis_mode(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace("-", "_")
    if text in {"advanced", "economy"}:
        return text
    return None


def _normalize_raw_stage_overrides(raw_stage: object | None) -> dict[str, object]:
    if not isinstance(raw_stage, dict):
        return {}

    # The public API may choose the top-level analysis mode, but worker-owned
    # fail-close booleans must not be caller-controlled.
    analysis_mode = _normalize_analysis_mode(
        raw_stage.get("mode") or raw_stage.get("analysis_mode")
    )
    if analysis_mode is None:
        return {}
    return {"mode": analysis_mode}


def _normalize_overrides(overrides: dict[str, object] | None) -> dict[str, object]:
    normalized = dict(overrides or {})
    llm = normalized.get("llm")
    canonical_llm = dict(llm) if isinstance(llm, dict) else {}
    raw_stage_payload = _normalize_raw_stage_overrides(normalized.get("raw_stage"))
    analysis_mode = _normalize_analysis_mode(
        raw_stage_payload.get("mode")
        or canonical_llm.get("analysis_mode")
        or normalized.get("analysis_mode")
        or normalized.get("raw_stage_mode")
    )
    if analysis_mode is not None:
        canonical_llm["analysis_mode"] = analysis_mode
    if canonical_llm:
        normalized["llm"] = canonical_llm
    if raw_stage_payload:
        normalized["raw_stage"] = raw_stage_payload
    else:
        normalized.pop("raw_stage", None)
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

    async def _dispatch_processing_job(
        self,
        *,
        video_row: object,
        platform: str,
        source_uid: str,
        mode: str,
        overrides: dict[str, object] | None,
        force: bool,
        trace: str,
        actor: str,
        log_event_prefix: str,
    ) -> dict[str, object]:
        normalized_mode = _normalize_mode(mode)
        normalized_overrides = _normalize_overrides(overrides)
        base_idempotency_key = _build_process_idempotency_key(
            platform=platform,
            video_uid=source_uid,
            mode=normalized_mode,
            overrides=normalized_overrides,
        )
        idempotency_key = (
            f"{base_idempotency_key}:force:{uuid4().hex}" if force else base_idempotency_key
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
                "%s_dispatch_started",
                log_event_prefix,
                extra={
                    "trace_id": trace,
                    "user": actor,
                    "platform": platform,
                    "source_uid": source_uid,
                    "video_uid": source_uid,
                    "job_id": str(job_row.id),
                },
            )
            try:
                from temporalio.client import Client
                from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
            except Exception as exc:  # pragma: no cover
                logger.exception(
                    "%s_temporal_client_import_failed",
                    log_event_prefix,
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
                    "%s_temporal_connect_timeout",
                    log_event_prefix,
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
                    "%s_temporal_start_timeout",
                    log_event_prefix,
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
                    "%s_temporal_start_failed",
                    log_event_prefix,
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
                "%s_reused_existing_job",
                log_event_prefix,
                extra={
                    "trace_id": trace,
                    "user": actor,
                    "platform": platform,
                    "source_uid": source_uid,
                    "video_uid": source_uid,
                    "job_id": str(job_row.id),
                },
            )

        return {
            "job_id": job_row.id,
            "video_db_id": video_row.id,
            "video_uid": source_uid,
            "status": job_row.status,
            "idempotency_key": job_row.idempotency_key,
            "mode": job_row.mode or normalized_mode,
            "overrides": normalized_overrides,
            "force": force,
            "reused": not needs_dispatch,
            "workflow_id": workflow_id,
        }

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
        resolved_video_uid = (video_id or "").strip() or _extract_video_uid(
            platform=platform,
            url=validated_url,
        )

        video_row = self.video_repo.upsert_for_processing(
            platform=platform,
            video_uid=resolved_video_uid,
            source_url=validated_url,
        )
        return await self._dispatch_processing_job(
            video_row=video_row,
            platform=platform,
            source_uid=resolved_video_uid,
            mode=mode,
            overrides=overrides,
            force=force,
            trace=trace,
            actor=actor,
            log_event_prefix="video_process",
        )

    async def process_article(
        self,
        *,
        url: str,
        mode: str = "text_only",
        overrides: dict[str, object] | None = None,
        force: bool = False,
        trace_id: str | None = None,
        user: str | None = None,
    ) -> dict[str, object]:
        trace = str(trace_id or "missing_trace")
        actor = str(user or "system")
        validated_url = _validate_external_source_url(url)
        existing_row = self.video_repo.get_by_source_url(source_url=validated_url)
        platform = str(getattr(existing_row, "platform", "") or "").strip().lower() or "generic"
        resolved_source_uid = (
            str(getattr(existing_row, "video_uid", "") or "").strip() if existing_row else ""
        ) or _url_hash(validated_url)
        video_row = existing_row or self.video_repo.upsert_for_processing(
            platform=platform,
            video_uid=resolved_source_uid,
            source_url=validated_url,
            content_type="article",
        )
        return await self._dispatch_processing_job(
            video_row=video_row,
            platform=platform,
            source_uid=resolved_source_uid,
            mode=mode,
            overrides=overrides,
            force=force,
            trace=trace,
            actor=actor,
            log_event_prefix="article_process",
        )

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

    def infer_subscription_match_for_source(
        self,
        *,
        platform: str,
        source_url: str,
    ) -> dict[str, str] | None:
        identity = self._probe_source_identity(source_url=source_url)
        if not identity:
            return None

        candidate_values: set[str] = set()
        candidate_routes: set[str] = set()
        candidate_source_urls: set[str] = {
            value
            for value in (
                str(identity.get("uploader_url") or "").strip(),
                str(identity.get("channel_url") or "").strip(),
            )
            if value
        }
        channel_id = str(identity.get("channel_id") or "").strip()
        uploader_id = str(identity.get("uploader_id") or "").strip()
        if platform == "youtube":
            if channel_id:
                candidate_values.add(channel_id)
                candidate_routes.add(f"/youtube/channel/{channel_id}")
            if uploader_id:
                candidate_values.add(uploader_id)
                if uploader_id.startswith("@"):
                    candidate_values.add(uploader_id.removeprefix("@"))
                    candidate_routes.add(f"/youtube/user/{uploader_id}")
                else:
                    candidate_values.add(f"@{uploader_id}")
                    candidate_routes.add(f"/youtube/user/{uploader_id}")
        elif platform == "bilibili" and uploader_id:
            candidate_values.add(uploader_id)
            candidate_routes.add(f"/bilibili/user/video/{uploader_id}")

        rows = (
            self.db.execute(
                text(
                    """
                    SELECT
                        CAST(id AS TEXT) AS subscription_id,
                        platform,
                        source_type,
                        source_value,
                        source_url,
                        rsshub_route
                    FROM subscriptions
                    WHERE platform = :platform
                    ORDER BY updated_at DESC, created_at DESC
                    """
                ),
                {"platform": platform},
            )
            .mappings()
            .all()
        )

        for row in rows:
            source_value = str(row.get("source_value") or "").strip()
            source_url_value = str(row.get("source_url") or "").strip()
            rsshub_route = str(row.get("rsshub_route") or "").strip()
            if (
                source_value in candidate_values
                or source_url_value in candidate_source_urls
                or rsshub_route in candidate_routes
            ):
                return self._normalize_subscription_match_row(row)
        return None

    @staticmethod
    def _probe_source_identity(*, source_url: str) -> dict[str, str] | None:
        try:
            result = subprocess.run(
                yt_dlp_metadata_command(source_url),
                capture_output=True,
                text=True,
                check=False,
                timeout=20,
            )
        except (FileNotFoundError, subprocess.SubprocessError, OSError, TimeoutError):
            return None
        if result.returncode != 0:
            return None
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return {
            "channel_id": str(payload.get("channel_id") or "").strip(),
            "channel_url": str(payload.get("channel_url") or "").strip(),
            "uploader_id": str(payload.get("uploader_id") or "").strip(),
            "uploader_url": str(payload.get("uploader_url") or "").strip(),
        }

    @staticmethod
    def _normalize_subscription_match_row(row: dict[str, object]) -> dict[str, str]:
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

    def get_reader_bridge_for_job(self, *, job_id: UUID | str) -> dict[str, str | bool] | None:
        safe_job_id = str(job_id or "").strip()
        if not safe_job_id:
            return None

        repo = PublishedReaderDocumentsRepository(self.db)
        try:
            current_documents = repo.list_current(limit=64)
        except Exception:
            return None

        for document in current_documents:
            publish_status = (
                "published_with_gap"
                if bool(getattr(document, "published_with_gap", False))
                else "published"
            )
            for source_ref in list(getattr(document, "source_refs_json", None) or []):
                if not isinstance(source_ref, dict):
                    continue
                if str(source_ref.get("job_id") or "").strip() != safe_job_id:
                    continue
                return {
                    "id": str(document.id),
                    "title": str(document.title),
                    "publish_status": publish_status,
                    "reader_route": f"/reader/{document.id}",
                    "published_with_gap": bool(getattr(document, "published_with_gap", False)),
                }
        return None
