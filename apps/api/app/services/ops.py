from __future__ import annotations

import logging
import os
import sys
import tempfile
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from apps.runtime_paths import get_runtime_root

from ..config import Settings
from ..models import NotificationConfig
from ..security import sanitize_exception_detail
from .health import HealthService

logger = logging.getLogger(__name__)
OPS_SECTION_ERROR_MESSAGE = "diagnostic data temporarily unavailable"
REPO_ROOT = get_runtime_root()


@lru_cache(maxsize=1)
def _load_disk_governance_helpers() -> tuple[Any, Any]:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from scripts.runtime.disk_space_common import load_policy
    from scripts.runtime.report_disk_space import (
        build_disk_governance_operator_summary,
    )

    return load_policy, build_disk_governance_operator_summary


def build_disk_governance_gate(payload: dict[str, Any]) -> dict[str, Any]:
    status = str(payload.get("status") or "unavailable").lower()
    if status not in {"ready", "warn", "blocked"}:
        status = "warn"
    return {
        "status": status,
        "summary": str(payload.get("summary") or "Disk governance summary unavailable."),
        "next_step": str(
            payload.get("next_step")
            or "Run ./bin/disk-space-audit and ./bin/disk-space-cleanup --wave repo-tmp."
        ),
        "details": dict(payload.get("details") or {}),
    }


def build_retrieval_gate(
    *,
    videos: int | None,
    jobs_with_artifacts: int | None,
    knowledge_cards: int | None,
    video_embeddings: int | None,
) -> dict[str, Any]:
    values = [videos, jobs_with_artifacts, knowledge_cards, video_embeddings]
    if any(value is None for value in values):
        return {
            "status": "warn",
            "summary": "Retrieval wiring exists, but corpus counts are unavailable right now.",
            "next_step": "Verify the live database/schema, then re-check jobs, knowledge cards, and embeddings.",
            "details": {
                "videos": videos,
                "jobs_with_artifacts": jobs_with_artifacts,
                "knowledge_cards": knowledge_cards,
                "video_embeddings": video_embeddings,
                "keyword_path": "implemented",
                "semantic_path": "implemented_experimental",
            },
        }

    if (
        int(jobs_with_artifacts or 0) == 0
        and int(knowledge_cards or 0) == 0
        and int(video_embeddings or 0) == 0
    ):
        return {
            "status": "blocked",
            "summary": "Retrieval routes are alive, but the current corpus is still effectively empty.",
            "next_step": "Seed one real job that writes artifact_root and knowledge cards, then rerun retrieval on the same environment.",
            "details": {
                "videos": int(videos or 0),
                "jobs_with_artifacts": int(jobs_with_artifacts or 0),
                "knowledge_cards": int(knowledge_cards or 0),
                "video_embeddings": int(video_embeddings or 0),
                "keyword_path": "implemented",
                "semantic_path": "implemented_experimental",
            },
        }

    if int(video_embeddings or 0) == 0:
        return {
            "status": "warn",
            "summary": "Keyword retrieval is ready, but semantic and hybrid quality still lack embedding-backed proof.",
            "next_step": "Validate semantic and hybrid modes only after embeddings exist in the current database.",
            "details": {
                "videos": int(videos or 0),
                "jobs_with_artifacts": int(jobs_with_artifacts or 0),
                "knowledge_cards": int(knowledge_cards or 0),
                "video_embeddings": int(video_embeddings or 0),
                "keyword_path": "ready",
                "semantic_path": "experimental_without_embeddings",
            },
        }

    return {
        "status": "ready",
        "summary": "Retrieval has corpus and embedding coverage in the current database.",
        "next_step": "Run live keyword and semantic quality checks against a known non-empty query set.",
        "details": {
            "videos": int(videos or 0),
            "jobs_with_artifacts": int(jobs_with_artifacts or 0),
            "knowledge_cards": int(knowledge_cards or 0),
            "video_embeddings": int(video_embeddings or 0),
            "keyword_path": "ready",
            "semantic_path": "ready_experimental",
        },
    }


def build_notifications_gate(
    *,
    notification_enabled: bool,
    config_enabled: bool,
    resend_api_key_present: bool,
    resend_from_email_present: bool,
    to_email: str | None,
) -> dict[str, Any]:
    if not resend_api_key_present or not resend_from_email_present:
        missing_requirements: list[str] = []
        if not resend_api_key_present:
            missing_requirements.append("RESEND_API_KEY")
        if not resend_from_email_present:
            missing_requirements.append("RESEND_FROM_EMAIL")
        return {
            "status": "blocked",
            "summary": "Notification send paths exist, but live delivery is blocked by missing Resend provider configuration.",
            "next_step": (
                f"Provide {', '.join(missing_requirements)}, then rerun the existing notification test send."
            ),
            "details": {
                "notification_enabled": notification_enabled,
                "config_enabled": config_enabled,
                "resend_api_key_present": resend_api_key_present,
                "resend_from_email_present": resend_from_email_present,
                "missing_requirements": missing_requirements,
                "to_email_present": bool((to_email or "").strip()),
            },
        }

    if not config_enabled:
        return {
            "status": "warn",
            "summary": "Notification delivery exists, but the current notification config is turned off.",
            "next_step": "Enable notifications in Settings before treating delivery as operator-ready.",
            "details": {
                "notification_enabled": notification_enabled,
                "config_enabled": config_enabled,
                "resend_api_key_present": resend_api_key_present,
                "resend_from_email_present": resend_from_email_present,
                "to_email_present": bool((to_email or "").strip()),
            },
        }

    if not (to_email or "").strip():
        return {
            "status": "warn",
            "summary": "Notification infrastructure is present, but no recipient email is configured yet.",
            "next_step": "Set a recipient email in Settings before treating delivery as operator-ready.",
            "details": {
                "notification_enabled": notification_enabled,
                "config_enabled": config_enabled,
                "resend_api_key_present": resend_api_key_present,
                "resend_from_email_present": resend_from_email_present,
                "to_email_present": False,
            },
        }

    if not notification_enabled:
        return {
            "status": "warn",
            "summary": "Notification delivery is configured but currently disabled by environment.",
            "next_step": "Turn on notification delivery in the environment before treating external send as ready.",
            "details": {
                "notification_enabled": notification_enabled,
                "config_enabled": config_enabled,
                "resend_api_key_present": resend_api_key_present,
                "resend_from_email_present": resend_from_email_present,
                "to_email_present": True,
            },
        }

    return {
        "status": "ready",
        "summary": "Notification send path, recipient config, and provider secrets are all present.",
        "next_step": "Run a minimal live test send and confirm the delivery record moves to sent.",
        "details": {
            "notification_enabled": notification_enabled,
            "config_enabled": config_enabled,
            "resend_api_key_present": resend_api_key_present,
            "resend_from_email_present": resend_from_email_present,
            "to_email_present": True,
        },
    }


def build_ui_audit_gate(
    *,
    artifact_base_root: str,
    gemini_review_enabled: bool,
    gemini_api_key_present: bool,
) -> dict[str, Any]:
    if gemini_review_enabled and not gemini_api_key_present:
        return {
            "status": "ready",
            "summary": "Base UI audit is ready today; only the Gemini review layer is blocked by a missing Gemini key.",
            "next_step": "Use job_id or artifact_root under the configured base root for baseline findings; add GEMINI_API_KEY only when you want Gemini review enabled.",
            "details": {
                "artifact_input_contract": "job_id or artifact_root",
                "artifact_base_root": artifact_base_root,
                "gemini_review_enabled": gemini_review_enabled,
                "gemini_api_key_present": gemini_api_key_present,
            },
        }

    return {
        "status": "ready",
        "summary": "UI audit can run with a valid job_id or artifact_root under the configured base root.",
        "next_step": "Feed it a real artifact bundle to collect baseline findings, then use Gemini review only when desired.",
        "details": {
            "artifact_input_contract": "job_id or artifact_root",
            "artifact_base_root": artifact_base_root,
            "gemini_review_enabled": gemini_review_enabled,
            "gemini_api_key_present": gemini_api_key_present,
        },
    }


def build_computer_use_gate(
    *,
    gemini_api_key_present: bool,
    model: str,
) -> dict[str, Any]:
    if not gemini_api_key_present:
        return {
            "status": "blocked",
            "summary": "Computer use is implemented, but the live run is currently blocked by a missing Gemini API key.",
            "next_step": "Provide GEMINI_API_KEY, then rerun the existing instruction + screenshot contract on the configured preview model.",
            "details": {
                "input_contract": "instruction + screenshot_base64 + safety",
                "model": model,
                "provider": "gemini",
            },
        }

    return {
        "status": "ready",
        "summary": "Computer use has the required provider secret and can proceed to preview-model runtime validation.",
        "next_step": "Run one constrained instruction + screenshot scenario and confirm require_confirmation / blocked_actions behavior.",
        "details": {
            "input_contract": "instruction + screenshot_base64 + safety",
            "model": model,
            "provider": "gemini",
        },
    }


class OpsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_inbox(self, *, limit: int = 5, window_hours: int = 24) -> dict[str, Any]:
        settings = Settings.from_env()
        failed_jobs = self._load_failed_jobs(limit=limit)
        failed_ingest_runs = self._load_failed_ingest_runs(limit=limit)
        notification_deliveries = self._load_notification_deliveries(limit=limit)
        retrieval_counts = self._load_retrieval_counts()
        notification_config = self._load_notification_config()
        provider_health = HealthService(self.db).get_provider_health(window_hours=window_hours)
        try:
            load_policy, build_disk_governance_operator_summary = _load_disk_governance_helpers()
            disk_governance_summary = build_disk_governance_operator_summary(
                REPO_ROOT, load_policy(REPO_ROOT)
            )
        except (OSError, ValueError):
            disk_governance_summary = {
                "status": "warn",
                "summary": OPS_SECTION_ERROR_MESSAGE,
                "next_step": "Run ./bin/disk-space-audit --json manually and fix the reported disk governance policy/report issue before treating this gate as current truth.",
                "details": {},
            }

        retrieval_gate = build_retrieval_gate(**retrieval_counts)
        notifications_gate = build_notifications_gate(
            notification_enabled=settings.notification_enabled,
            config_enabled=bool(notification_config.get("enabled")),
            resend_api_key_present=bool((settings.resend_api_key or "").strip()),
            resend_from_email_present=bool((settings.resend_from_email or "").strip()),
            to_email=notification_config.get("to_email"),
        )
        ui_audit_gate = build_ui_audit_gate(
            artifact_base_root=str(notification_config.get("ui_audit_artifact_base_root")),
            gemini_review_enabled=bool(notification_config.get("ui_audit_gemini_enabled")),
            gemini_api_key_present=bool((settings.gemini_api_key or "").strip()),
        )
        computer_use_gate = build_computer_use_gate(
            gemini_api_key_present=bool((settings.gemini_api_key or "").strip()),
            model=settings.gemini_computer_use_model,
        )
        disk_governance_gate = build_disk_governance_gate(disk_governance_summary)
        gates = {
            "retrieval": retrieval_gate,
            "notifications": notifications_gate,
            "disk_governance": disk_governance_gate,
            "ui_audit": ui_audit_gate,
            "computer_use": computer_use_gate,
        }

        inbox_items = self._build_inbox_items(
            failed_jobs=failed_jobs["items"],
            failed_ingest_runs=failed_ingest_runs["items"],
            notification_deliveries=notification_deliveries["items"],
            provider_health=provider_health.get("providers", []),
            gates=gates,
        )
        inbox_items.sort(
            key=lambda item: (
                0 if item["severity"] == "critical" else 1,
                -(item["timestamp_rank"]),
            )
        )

        provider_issue_count = sum(
            1
            for item in provider_health.get("providers", [])
            if str(item.get("last_status") or "").lower() in {"warn", "fail"}
        )
        non_ready_gate_count = sum(1 for item in gates.values() if item["status"] != "ready")

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "overview": {
                "attention_items": len(inbox_items),
                "failed_jobs": failed_jobs["total"],
                "failed_ingest_runs": failed_ingest_runs["total"],
                "notification_or_gate_issues": notification_deliveries["total"]
                + provider_issue_count
                + non_ready_gate_count,
            },
            "failed_jobs": failed_jobs,
            "failed_ingest_runs": failed_ingest_runs,
            "notification_deliveries": notification_deliveries,
            "provider_health": provider_health,
            "gates": gates,
            "inbox_items": [
                {key: value for key, value in item.items() if key != "timestamp_rank"}
                for item in inbox_items
            ],
        }

    def _load_failed_jobs(self, *, limit: int) -> dict[str, Any]:
        statement = text(
            """
            SELECT
                CAST(j.id AS TEXT) AS id,
                COALESCE(v.title, '') AS title,
                COALESCE(v.platform, '') AS platform,
                j.status AS status,
                j.pipeline_final_status AS pipeline_final_status,
                COALESCE(j.error_message, '') AS error_message,
                COALESCE(j.hard_fail_reason, '') AS hard_fail_reason,
                COALESCE(j.degradation_count, 0) AS degradation_count,
                j.updated_at AS updated_at
            FROM jobs j
            LEFT JOIN videos v ON v.id = j.video_id
            WHERE j.status = 'failed'
               OR j.pipeline_final_status IN ('failed', 'degraded')
            ORDER BY j.updated_at DESC
            LIMIT :limit
            """
        )
        count_statement = text(
            """
            SELECT COUNT(*)
            FROM jobs
            WHERE status = 'failed'
               OR pipeline_final_status IN ('failed', 'degraded')
            """
        )
        try:
            rows = self.db.execute(statement, {"limit": limit}).mappings().all()
            total = int(self.db.execute(count_statement).scalar_one())
        except DBAPIError as exc:
            self.db.rollback()
            logger.exception(
                "ops_failed_jobs_unavailable",
                extra={"error": sanitize_exception_detail(exc), "section": "failed_jobs"},
            )
            return self._error_section(error=OPS_SECTION_ERROR_MESSAGE)

        items = []
        for row in rows:
            items.append(
                {
                    "id": row["id"],
                    "title": row["title"] or row["id"],
                    "platform": row["platform"] or "unknown",
                    "status": row["status"],
                    "pipeline_final_status": row["pipeline_final_status"],
                    "error_message": row["error_message"] or row["hard_fail_reason"] or None,
                    "degradation_count": int(row["degradation_count"] or 0),
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                }
            )
        return {"status": "ok", "total": total, "error": None, "items": items}

    def _load_failed_ingest_runs(self, *, limit: int) -> dict[str, Any]:
        statement = text(
            """
            SELECT
                CAST(id AS TEXT) AS id,
                COALESCE(platform, '') AS platform,
                status,
                COALESCE(error_message, '') AS error_message,
                jobs_created,
                candidates_count,
                created_at
            FROM ingest_runs
            WHERE status IN ('failed', 'skipped')
               OR error_message IS NOT NULL
            ORDER BY created_at DESC
            LIMIT :limit
            """
        )
        count_statement = text(
            """
            SELECT COUNT(*)
            FROM ingest_runs
            WHERE status IN ('failed', 'skipped')
               OR error_message IS NOT NULL
            """
        )
        try:
            rows = self.db.execute(statement, {"limit": limit}).mappings().all()
            total = int(self.db.execute(count_statement).scalar_one())
        except DBAPIError as exc:
            self.db.rollback()
            logger.exception(
                "ops_failed_ingest_runs_unavailable",
                extra={"error": sanitize_exception_detail(exc), "section": "failed_ingest_runs"},
            )
            return self._error_section(error=OPS_SECTION_ERROR_MESSAGE)

        items = []
        for row in rows:
            items.append(
                {
                    "id": row["id"],
                    "platform": row["platform"] or "all",
                    "status": row["status"],
                    "error_message": row["error_message"] or None,
                    "jobs_created": int(row["jobs_created"] or 0),
                    "candidates_count": int(row["candidates_count"] or 0),
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                }
            )
        return {"status": "ok", "total": total, "error": None, "items": items}

    def _load_notification_deliveries(self, *, limit: int) -> dict[str, Any]:
        statement = text(
            """
            SELECT
                CAST(id AS TEXT) AS id,
                kind,
                status,
                recipient_email,
                subject,
                attempt_count,
                next_retry_at,
                last_error_kind,
                error_message,
                created_at
            FROM notification_deliveries
            WHERE status <> 'sent'
            ORDER BY created_at DESC
            LIMIT :limit
            """
        )
        count_statement = text(
            """
            SELECT COUNT(*)
            FROM notification_deliveries
            WHERE status <> 'sent'
            """
        )
        try:
            rows = self.db.execute(statement, {"limit": limit}).mappings().all()
            total = int(self.db.execute(count_statement).scalar_one())
        except DBAPIError as exc:
            self.db.rollback()
            logger.exception(
                "ops_notification_deliveries_unavailable",
                extra={
                    "error": sanitize_exception_detail(exc),
                    "section": "notification_deliveries",
                },
            )
            return self._error_section(error=OPS_SECTION_ERROR_MESSAGE)

        items = []
        for row in rows:
            items.append(
                {
                    "id": row["id"],
                    "kind": row["kind"],
                    "status": row["status"],
                    "recipient_email": row["recipient_email"],
                    "subject": row["subject"],
                    "attempt_count": int(row["attempt_count"] or 0),
                    "next_retry_at": row["next_retry_at"].isoformat()
                    if row["next_retry_at"]
                    else None,
                    "last_error_kind": row["last_error_kind"] or None,
                    "error_message": row["error_message"] or None,
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                }
            )
        return {"status": "ok", "total": total, "error": None, "items": items}

    def _load_retrieval_counts(self) -> dict[str, int | None]:
        statement = text(
            """
            SELECT
                (SELECT COUNT(*) FROM videos) AS videos,
                (SELECT COUNT(*) FROM jobs WHERE artifact_root IS NOT NULL) AS jobs_with_artifacts,
                (SELECT COUNT(*) FROM knowledge_cards) AS knowledge_cards,
                (SELECT COUNT(*) FROM video_embeddings) AS video_embeddings
            """
        )
        try:
            row = self.db.execute(statement).mappings().first()
        except DBAPIError:
            self.db.rollback()
            return {
                "videos": None,
                "jobs_with_artifacts": None,
                "knowledge_cards": None,
                "video_embeddings": None,
            }
        if row is None:
            return {
                "videos": 0,
                "jobs_with_artifacts": 0,
                "knowledge_cards": 0,
                "video_embeddings": 0,
            }
        return {
            "videos": int(row.get("videos") or 0),
            "jobs_with_artifacts": int(row.get("jobs_with_artifacts") or 0),
            "knowledge_cards": int(row.get("knowledge_cards") or 0),
            "video_embeddings": int(row.get("video_embeddings") or 0),
        }

    def _load_notification_config(self) -> dict[str, Any]:
        settings = Settings.from_env()
        stmt = select(NotificationConfig).where(NotificationConfig.singleton_key == 1)
        try:
            row = self.db.scalar(stmt)
        except DBAPIError:
            self.db.rollback()
            row = None
        return {
            "to_email": getattr(row, "to_email", None),
            "enabled": bool(getattr(row, "enabled", False)),
            "failure_alert_enabled": bool(getattr(row, "failure_alert_enabled", False)),
            "ui_audit_artifact_base_root": os.getenv(
                "UI_AUDIT_ARTIFACT_BASE_ROOT",
                tempfile.gettempdir(),
            ),
            "ui_audit_gemini_enabled": bool(settings.ui_audit_gemini_enabled),
        }

    def _build_inbox_items(
        self,
        *,
        failed_jobs: list[dict[str, Any]],
        failed_ingest_runs: list[dict[str, Any]],
        notification_deliveries: list[dict[str, Any]],
        provider_health: list[dict[str, Any]],
        gates: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for job in failed_jobs:
            severity = "critical" if job.get("status") == "failed" else "warning"
            detail = job.get("error_message") or "Job needs operator attention."
            items.append(
                self._inbox_item(
                    kind="job_failed",
                    severity=severity,
                    title=str(job.get("title") or "Failed job"),
                    detail=str(detail),
                    status_label=str(
                        job.get("pipeline_final_status") or job.get("status") or "unknown"
                    ),
                    last_seen_at=job.get("updated_at"),
                    href=f"/jobs?job_id={job.get('id')}",
                    action_label="Open job",
                )
            )

        for run in failed_ingest_runs:
            items.append(
                self._inbox_item(
                    kind="ingest_failed",
                    severity="critical" if run.get("status") == "failed" else "warning",
                    title=f"Ingest run {run.get('id')}",
                    detail=str(run.get("error_message") or "Ingest run needs review."),
                    status_label=str(run.get("status") or "unknown"),
                    last_seen_at=run.get("created_at"),
                    href=f"/ingest-runs?run_id={run.get('id')}",
                    action_label="Open ingest run",
                )
            )

        for delivery in notification_deliveries:
            items.append(
                self._inbox_item(
                    kind="notification_delivery",
                    severity="critical" if delivery.get("status") == "failed" else "warning",
                    title=f"Notification {delivery.get('kind')}",
                    detail=str(
                        delivery.get("error_message")
                        or delivery.get("last_error_kind")
                        or "Notification delivery is pending or failed."
                    ),
                    status_label=str(delivery.get("status") or "unknown"),
                    last_seen_at=delivery.get("created_at"),
                    href="#notification-readiness",
                    action_label="Open notification readiness",
                )
            )

        for provider in provider_health:
            last_status = str(provider.get("last_status") or "").lower()
            if last_status not in {"warn", "fail"}:
                continue
            items.append(
                self._inbox_item(
                    kind="provider_health",
                    severity="critical" if last_status == "fail" else "warning",
                    title=f"Provider health: {provider.get('provider')}",
                    detail=str(
                        provider.get("last_message")
                        or provider.get("last_error_kind")
                        or "Provider health requires operator attention."
                    ),
                    status_label=last_status,
                    last_seen_at=provider.get("last_checked_at"),
                    href="#provider-health",
                    action_label="Open provider health",
                )
            )

        for gate_name, gate in gates.items():
            if gate["status"] == "ready":
                continue
            severity = "critical" if gate["status"] == "blocked" else "warning"
            href = "#hardening-gates"
            action_label = "Open gate"
            if gate_name == "notifications":
                href = "/settings"
                action_label = "Open settings"
            items.append(
                self._inbox_item(
                    kind="hardening_gate",
                    severity=severity,
                    title=f"{gate_name.replace('_', ' ')} gate",
                    detail=str(gate["summary"]),
                    status_label=str(gate["status"]),
                    last_seen_at=None,
                    href=href,
                    action_label=action_label if gate_name == "notifications" else "Open gate",
                )
            )
        return items

    def _inbox_item(
        self,
        *,
        kind: str,
        severity: str,
        title: str,
        detail: str,
        status_label: str,
        last_seen_at: str | None,
        href: str,
        action_label: str,
    ) -> dict[str, Any]:
        return {
            "kind": kind,
            "severity": severity,
            "title": title,
            "detail": detail,
            "status_label": status_label,
            "last_seen_at": last_seen_at,
            "href": href,
            "action_label": action_label,
            "timestamp_rank": self._timestamp_rank(last_seen_at),
        }

    def _timestamp_rank(self, value: str | datetime | None) -> int:
        if not value:
            return 0
        if isinstance(value, datetime):
            timestamp = value
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
            return int(timestamp.timestamp())
        normalized = value.replace("Z", "+00:00")
        try:
            return int(datetime.fromisoformat(normalized).timestamp())
        except ValueError:
            return 0

    def _error_section(self, *, error: str) -> dict[str, Any]:
        return {
            "status": "unavailable",
            "total": 0,
            "error": error,
            "items": [],
        }
