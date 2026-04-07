from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from worker.temporal import activities_reports


def test_safe_read_text_handles_missing_and_os_errors(monkeypatch, tmp_path: Path) -> None:
    assert activities_reports._safe_read_text(None) is None
    assert activities_reports._safe_read_text(str(tmp_path / "missing.txt")) is None

    sample = tmp_path / "digest.md"
    sample.write_text(" content \n", encoding="utf-8")
    assert activities_reports._safe_read_text(str(sample)) == "content"

    with monkeypatch.context() as m:
        m.setattr(Path, "expanduser", lambda self: (_ for _ in ()).throw(OSError("bad path")))
        assert activities_reports._safe_read_text("~/digest.md") is None

    with monkeypatch.context() as m:
        m.setattr(
            Path,
            "read_text",
            lambda self, encoding="utf-8": (_ for _ in ()).throw(OSError("read failed")),
        )
        assert activities_reports._safe_read_text(str(sample)) is None


def test_build_video_digest_markdown_with_and_without_source_url() -> None:
    base_job = {
        "job_id": "job-1",
        "platform": "youtube",
        "video_uid": "vid-1",
        "status": "succeeded",
    }

    fallback = activities_reports._build_video_digest_markdown(base_job, "")
    assert "## 视频摘要" in fallback
    assert "（摘要文件不存在或为空）" in fallback
    assert "- 原视频：" not in fallback

    with_source = activities_reports._build_video_digest_markdown(
        {**base_job, "source_url": "https://example.com/watch?v=1"},
        "## Digest\n\nBody",
    )
    assert "## Digest" in with_source
    assert "- 原视频：https://example.com/watch?v=1" in with_source


def test_build_daily_digest_markdown_empty_jobs_contains_notice() -> None:
    markdown = activities_reports._build_daily_digest_markdown(
        digest_day=date(2026, 2, 25),
        offset_minutes=0,
        timezone_name="UTC",
        jobs=[],
    )
    assert "- Total jobs: 0" in markdown
    assert "_No succeeded/degraded jobs for this date._" in markdown


class _FakeMappingsResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _CaptureConn:
    def __init__(self, rows):
        self.rows = rows
        self.statement = ""
        self.params = {}

    def execute(self, statement, params=None):
        self.statement = str(statement)
        self.params = params or {}
        return _FakeMappingsResult(self.rows)


def test_load_daily_digest_jobs_uses_window_and_returns_rows(monkeypatch) -> None:
    start = datetime(2026, 2, 24, 16, 0, tzinfo=UTC)
    end = datetime(2026, 2, 25, 16, 0, tzinfo=UTC)
    monkeypatch.setattr(
        activities_reports,
        "_build_local_day_window_utc",
        lambda **_: (start, end),
    )
    conn = _CaptureConn(
        [
            {
                "job_id": "job-1",
                "status": "succeeded",
                "pipeline_final_status": "degraded",
                "platform": "youtube",
            }
        ]
    )

    rows = activities_reports._load_daily_digest_jobs(
        conn,
        digest_day=date(2026, 2, 25),
        timezone_name="Asia/Shanghai",
        offset_minutes=480,
    )

    assert rows == [
        {
            "job_id": "job-1",
            "status": "succeeded",
            "pipeline_final_status": "degraded",
            "platform": "youtube",
        }
    ]
    assert "FROM jobs" in conn.statement
    assert conn.params == {"window_start_utc": start, "window_end_utc": end}
