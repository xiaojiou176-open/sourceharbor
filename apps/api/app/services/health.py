from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session


class HealthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_provider_health(self, *, window_hours: int = 24) -> dict[str, Any]:
        since = datetime.now(UTC) - timedelta(hours=max(1, window_hours))
        providers = ["rsshub", "youtube_data_api", "gemini", "resend"]
        stats: dict[str, dict[str, Any]] = {
            kind: {
                "provider": kind,
                "ok": 0,
                "warn": 0,
                "fail": 0,
                "last_status": None,
                "last_checked_at": None,
                "last_error_kind": None,
                "last_message": None,
            }
            for kind in providers
        }

        try:
            rows = (
                self.db.execute(
                    text(
                        """
                    SELECT
                        check_kind,
                        status,
                        COUNT(*) AS count
                    FROM provider_health_checks
                    WHERE checked_at >= :since
                    GROUP BY check_kind, status
                    """
                    ),
                    {"since": since},
                )
                .mappings()
                .all()
            )
        except DBAPIError:
            self.db.rollback()
            return {
                "window_hours": max(1, window_hours),
                "providers": [stats[name] for name in providers],
            }
        for row in rows:
            check_kind = row.get("check_kind")
            status = row.get("status")
            if check_kind not in stats:
                continue
            if status in {"ok", "warn", "fail"}:
                stats[check_kind][status] = int(row.get("count") or 0)

        try:
            latest_rows = (
                self.db.execute(
                    text(
                        """
                    SELECT DISTINCT ON (check_kind)
                        check_kind,
                        status,
                        checked_at,
                        error_kind,
                        message
                    FROM provider_health_checks
                    ORDER BY check_kind, checked_at DESC
                    """
                    )
                )
                .mappings()
                .all()
            )
        except DBAPIError:
            self.db.rollback()
            latest_rows = []
        for row in latest_rows:
            check_kind = row.get("check_kind")
            if check_kind not in stats:
                continue
            stats[check_kind]["last_status"] = row.get("status")
            stats[check_kind]["last_checked_at"] = row.get("checked_at")
            stats[check_kind]["last_error_kind"] = row.get("error_kind")
            stats[check_kind]["last_message"] = row.get("message")

        return {
            "window_hours": max(1, window_hours),
            "providers": [stats[name] for name in providers],
        }
