from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

from worker.temporal.activities_timing import (
    _build_local_day_window_utc,
    _resolve_local_timezone,
)


def _safe_read_text(path: str | None) -> str | None:
    if not path:
        return None
    try:
        file_path = Path(path).expanduser()
    except OSError:
        return None
    if not file_path.is_file():
        return None
    try:
        return file_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _build_video_digest_markdown(job: dict[str, Any], digest_markdown: str | None) -> str:
    source_url = str(job.get("source_url") or "").strip()
    digest_body = str(digest_markdown or "").strip()
    if not digest_body:
        digest_body = "## 视频摘要\n\n（摘要文件不存在或为空）"

    metadata_lines = [
        "## 投递信息",
        "",
        f"- Job ID：{job['job_id']}",
        f"- 平台：{job.get('platform') or 'unknown'}",
        f"- 视频 UID：{job.get('video_uid') or 'unknown'}",
        f"- 状态：{job.get('status') or 'unknown'}",
    ]
    if source_url:
        metadata_lines.append(f"- 原视频：{source_url}")

    return f"{digest_body}\n\n---\n\n" + "\n".join(metadata_lines).strip()


def _build_daily_digest_markdown(
    *,
    digest_day: date,
    offset_minutes: int = 0,
    timezone_name: str | None = None,
    jobs: list[dict[str, Any]],
) -> str:
    local_tz, tz_label = _resolve_local_timezone(
        timezone_name=timezone_name,
        offset_minutes=offset_minutes,
    )
    generated_at = datetime.now(UTC).astimezone(local_tz).replace(microsecond=0)
    succeeded_count = sum(
        1
        for item in jobs
        if str(item.get("status")) == "succeeded"
        and str(item.get("pipeline_final_status") or "") != "degraded"
    )
    degraded_count = sum(
        1 for item in jobs if str(item.get("pipeline_final_status") or "") == "degraded"
    )

    lines = [
        f"# Daily Digest {digest_day.isoformat()}",
        "",
        f"- Generated at: {generated_at.isoformat()}",
        f"- Timezone: {tz_label}",
        f"- Timezone offset minutes: {int(generated_at.utcoffset().total_seconds() // 60) if generated_at.utcoffset() else 0}",
        f"- Total jobs: {len(jobs)}",
        f"- Succeeded: {succeeded_count}",
        f"- Degraded: {degraded_count}",
        "",
    ]

    if not jobs:
        lines.append("_No succeeded/degraded jobs for this date._")
        return "\n".join(lines).strip()

    lines.extend(
        [
            "| Updated (UTC) | Job ID | Status | Platform | Title |",
            "|---|---|---|---|---|",
        ]
    )
    for item in jobs:
        updated_at = item.get("updated_at")
        updated_text = (
            updated_at.astimezone(UTC).replace(microsecond=0).isoformat()
            if isinstance(updated_at, datetime)
            else "-"
        )
        title = str(item.get("title") or "Untitled").replace("|", "\\|")
        lines.append(
            "| {updated} | {job_id} | {status} | {platform} | {title} |".format(
                updated=updated_text,
                job_id=item.get("job_id") or "-",
                status=item.get("status") or "-",
                platform=item.get("platform") or "-",
                title=title,
            )
        )

    return "\n".join(lines).strip()


def _load_daily_digest_jobs(
    conn: Any,
    *,
    digest_day: date,
    timezone_name: str | None,
    offset_minutes: int,
) -> list[dict[str, Any]]:
    window_start_utc, window_end_utc = _build_local_day_window_utc(
        local_day=digest_day,
        timezone_name=timezone_name,
        offset_minutes=offset_minutes,
    )
    rows = (
        conn.execute(
            text(
                """
            SELECT
                j.id::text AS job_id,
                j.status,
                j.pipeline_final_status,
                j.updated_at,
                j.artifact_digest_md,
                v.platform,
                v.video_uid,
                v.title,
                v.source_url
            FROM jobs j
            JOIN videos v ON v.id = j.video_id
            WHERE j.status = 'succeeded'
              AND j.updated_at >= :window_start_utc
              AND j.updated_at < :window_end_utc
            ORDER BY j.updated_at DESC
            """
            ),
            {
                "window_start_utc": window_start_utc,
                "window_end_utc": window_end_utc,
            },
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]
