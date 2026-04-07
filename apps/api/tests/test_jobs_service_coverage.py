from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.exc import DBAPIError

from apps.api.app.services.jobs import JobsService


def _service() -> JobsService:
    return JobsService.__new__(JobsService)


class _DBResult:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self._row = row

    def mappings(self) -> _DBResult:
        return self

    def first(self) -> dict[str, Any] | None:
        return self._row


class _DBStub:
    def __init__(self, row: dict[str, Any] | None = None, *, raise_db_error: bool = False) -> None:
        self._row = row
        self._raise_db_error = raise_db_error
        self.rolled_back = False

    def execute(self, *_args: Any, **_kwargs: Any) -> _DBResult:
        if self._raise_db_error:
            raise DBAPIError("SELECT 1", {}, RuntimeError("boom"))
        return _DBResult(self._row)

    def rollback(self) -> None:
        self.rolled_back = True


class _RepoStub:
    def __init__(self) -> None:
        self.db = _DBStub()
        self._pipeline_status = None
        self._digest_by_job: str | None = None
        self._digest_by_url: str | None = None

    def get(self, _job_id: uuid.UUID) -> Any:
        return None

    def get_pipeline_final_status(self, *, job_id: uuid.UUID) -> str | None:
        del job_id
        return self._pipeline_status

    def get_artifact_digest_md(self, *, job_id: uuid.UUID) -> str | None:
        del job_id
        return self._digest_by_job

    def get_artifact_digest_md_by_video_url(self, *, video_url: str) -> str | None:
        del video_url
        return self._digest_by_url


def test_get_pipeline_final_status_prefers_repo_and_fallback() -> None:
    service = _service()
    repo = _RepoStub()
    service.repo = repo  # type: ignore[assignment]

    repo._pipeline_status = "degraded"
    assert service.get_pipeline_final_status(uuid.uuid4(), fallback_status="queued") == "degraded"

    repo._pipeline_status = "running"
    assert service.get_pipeline_final_status(uuid.uuid4(), fallback_status="failed") == "failed"
    assert service.get_pipeline_final_status(uuid.uuid4(), fallback_status="running") is None


def test_get_steps_returns_empty_when_sqlite_connect_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service()

    def _raise_connect(_path: str) -> sqlite3.Connection:
        raise sqlite3.Error("connect failed")

    monkeypatch.setattr("apps.api.app.services.jobs.sqlite3.connect", _raise_connect)
    assert service.get_steps(uuid.uuid4()) == []


def test_get_steps_returns_empty_when_sql_query_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service()

    class _Conn:
        row_factory = None

        def execute(self, *_args: Any, **_kwargs: Any) -> Any:
            raise sqlite3.Error("query failed")

        def close(self) -> None:
            return None

    monkeypatch.setattr("apps.api.app.services.jobs.sqlite3.connect", lambda _path: _Conn())
    assert service.get_steps(uuid.uuid4()) == []


def test_get_steps_parses_rows_and_json_payloads(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE step_runs (
          job_id TEXT,
          step_name TEXT,
          status TEXT,
          attempt INTEGER,
          started_at TEXT,
          finished_at TEXT,
          error_json TEXT,
          error_kind TEXT,
          retry_meta_json TEXT,
          result_json TEXT,
          cache_key TEXT
        )
        """
    )
    job_id = str(uuid.uuid4())
    result_payload = {
        "llm_meta": {
            "provider": "gemini",
            "thinking": {
                "enabled": True,
                "include_thoughts": True,
                "thought_signatures": ["sig-1"],
                "usage": {"thoughts_token_count": 3},
            },
        }
    }
    conn.execute(
        """
        INSERT INTO step_runs (
          job_id, step_name, status, attempt, started_at, finished_at,
          error_json, error_kind, retry_meta_json, result_json, cache_key
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            "llm_digest",
            "failed",
            1,
            "2026-01-01T00:00:00Z",
            "2026-01-01T00:00:01Z",
            json.dumps({"reason": "rate_limited"}),
            "timeout",
            json.dumps({"attempt": 1}),
            json.dumps(result_payload),
            "cache-1",
        ),
    )
    conn.execute(
        """
        INSERT INTO step_runs (
          job_id, step_name, status, attempt, started_at, finished_at,
          error_json, error_kind, retry_meta_json, result_json, cache_key
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            "subtitles",
            "succeeded",
            2,
            "2026-01-01T00:00:02Z",
            "2026-01-01T00:00:03Z",
            "not-json",
            None,
            "[]",
            "not-json",
            None,
        ),
    )
    conn.commit()
    conn.close()

    original_connect = sqlite3.connect
    monkeypatch.setattr(
        "apps.api.app.services.jobs.sqlite3.connect", lambda _path: original_connect(db_path)
    )

    service = _service()
    rows = service.get_steps(uuid.UUID(job_id))

    assert len(rows) == 2
    assert rows[0]["error"] == {"reason": "rate_limited"}
    assert rows[0]["retry_meta"] == {"attempt": 1}
    assert rows[0]["result"] == result_payload
    assert rows[0]["thought_metadata"]["provider"] == "gemini"
    assert rows[1]["error"] == {"raw": "not-json"}
    assert rows[1]["retry_meta"] is None
    assert rows[1]["result"] == {"raw": "not-json"}


def test_get_step_summary_maps_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service()
    monkeypatch.setattr(
        service,
        "get_steps",
        lambda _job_id: [
            {
                "name": "write_artifacts",
                "status": "failed",
                "attempt": 1,
                "started_at": "s",
                "finished_at": "f",
                "error": {"reason": "x"},
                "extra": "ignored",
            }
        ],
    )
    assert service.get_step_summary(uuid.uuid4()) == [
        {
            "name": "write_artifacts",
            "status": "failed",
            "attempt": 1,
            "started_at": "s",
            "finished_at": "f",
            "error": {"reason": "x"},
        }
    ]


def test_get_notification_retry_handles_db_errors_and_missing_rows() -> None:
    service = _service()
    repo = _RepoStub()
    service.repo = repo  # type: ignore[assignment]

    repo.db = _DBStub(raise_db_error=True)
    assert service.get_notification_retry(uuid.uuid4()) is None
    assert repo.db.rolled_back is True

    repo.db = _DBStub(row=None)
    assert service.get_notification_retry(uuid.uuid4()) is None


def test_get_notification_retry_returns_normalized_mapping() -> None:
    service = _service()
    repo = _RepoStub()
    service.repo = repo  # type: ignore[assignment]
    repo.db = _DBStub(
        row={
            "delivery_id": "d1",
            "status": "failed",
            "attempt_count": None,
            "next_retry_at": "2026-01-02T00:00:00Z",
            "last_error_kind": "timeout",
        }
    )

    payload = service.get_notification_retry(uuid.uuid4())
    assert payload == {
        "delivery_id": "d1",
        "status": "failed",
        "attempt_count": 0,
        "next_retry_at": "2026-01-02T00:00:00Z",
        "last_error_kind": "timeout",
    }


def test_get_degradations_prefers_meta_else_builds_from_steps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    monkeypatch.setattr(
        service, "_read_artifact_meta", lambda **_kwargs: {"degradations": [{"step": "llm"}, "x"]}
    )

    assert service.get_degradations(artifact_root=None, artifact_digest_md=None, steps=[]) == [
        {"step": "llm"}
    ]

    monkeypatch.setattr(service, "_read_artifact_meta", lambda **_kwargs: {})
    fallback = service.get_degradations(
        artifact_root=None,
        artifact_digest_md=None,
        steps=[
            {
                "name": "llm_digest",
                "status": "failed",
                "error": {
                    "reason": "r1",
                    "error": "e1",
                    "error_kind": "timeout",
                    "retry_meta": {"n": 1},
                },
                "result": {"cache_meta": {"hit": False}},
            },
            {
                "name": "subtitles",
                "status": "skipped",
                "error": "raw-error",
                "result": {
                    "reason": "r2",
                    "error": "e2",
                    "error_kind": "degraded",
                    "retry_meta": {"n": 2},
                },
            },
            {"name": "ok", "status": "succeeded", "result": {"degraded": True, "reason": "r3"}},
        ],
    )

    assert len(fallback) == 3
    assert fallback[0]["reason"] == "r1"
    assert fallback[1]["error"] == "raw-error"
    assert fallback[2]["reason"] == "r3"


def test_get_artifacts_index_uses_step_output_then_filesystem(tmp_path: Path) -> None:
    service = _service()

    from_steps = service.get_artifacts_index(
        artifact_root=None,
        artifact_digest_md=None,
        steps=[
            {"name": "write_artifacts", "result": {"output": {"files": {"digest": "/tmp/d.md"}}}}
        ],
    )
    assert from_steps == {"digest": "/tmp/d.md"}

    root = tmp_path / "artifacts"
    root.mkdir()
    (root / "meta.json").write_text("{}", encoding="utf-8")
    (root / "digest.md").write_text("# digest", encoding="utf-8")
    digest_file = root / "digest.md"

    from_fs = service.get_artifacts_index(
        artifact_root=str(root),
        artifact_digest_md=str(digest_file),
        steps=[],
    )
    assert "meta" in from_fs
    assert "digest" in from_fs


def test_get_artifact_payload_and_digest_md_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    service = _service()
    repo = _RepoStub()
    service.repo = repo  # type: ignore[assignment]

    assert service.get_artifact_payload(job_id=None, video_url=None) is None
    assert service.get_artifact_digest_md(job_id=None, video_url=None) is None

    repo._digest_by_job = str(tmp_path / "missing.md")
    assert service.get_artifact_payload(job_id=uuid.uuid4(), video_url=None) is None

    digest = tmp_path / "digest.md"
    digest.write_text("hello", encoding="utf-8")
    (tmp_path / "meta.json").write_text(
        json.dumps({"degradations": [{"step": "x"}]}), encoding="utf-8"
    )
    repo._digest_by_job = str(digest)

    payload = service.get_artifact_payload(job_id=uuid.uuid4(), video_url=None)
    assert payload == {"markdown": "hello", "meta": {"degradations": [{"step": "x"}]}}
    assert service.get_artifact_digest_md(job_id=uuid.uuid4(), video_url=None) == "hello"

    monkeypatch.setattr(
        Path, "read_text", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("deny"))
    )
    assert service.get_artifact_payload(job_id=uuid.uuid4(), video_url=None) is None


def test_get_artifact_asset_path_guardrails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service()
    root = tmp_path / "bundle"
    root.mkdir()
    meta = root / "meta.json"
    meta.write_text("{}", encoding="utf-8")
    frame = root / "frame_001.jpg"
    frame.write_text("img", encoding="utf-8")
    bad = root / "note.txt"
    bad.write_text("x", encoding="utf-8")

    job_id = uuid.uuid4()
    monkeypatch.setattr(service, "get_job", lambda _job_id: None)
    assert service.get_artifact_asset(job_id=job_id, path="meta") is None

    monkeypatch.setattr(
        service,
        "get_job",
        lambda _job_id: SimpleNamespace(artifact_root=str(root), artifact_digest_md=None),
    )
    assert service.get_artifact_asset(job_id=job_id, path=" ") is None
    assert service.get_artifact_asset(job_id=job_id, path="meta") == meta.resolve()
    assert service.get_artifact_asset(job_id=job_id, path="frame_001.jpg") == frame.resolve()
    assert service.get_artifact_asset(job_id=job_id, path="note.txt") is None
    assert service.get_artifact_asset(job_id=job_id, path="../outside.txt") is None


def test_private_artifact_helpers_cover_edge_cases(tmp_path: Path) -> None:
    service = _service()

    assert service._normalize_artifact_asset_path("  DIGEST  ") == "digest.md"
    assert service._normalize_artifact_asset_path("  ") == ""

    digest_path = tmp_path / "nested" / "digest.md"
    digest_path.parent.mkdir()
    digest_path.write_text("ok", encoding="utf-8")
    assert (
        service._resolve_artifact_root(artifact_root=None, digest_path=str(digest_path))
        == digest_path.parent.resolve()
    )
    assert (
        service._resolve_artifact_root(artifact_root=str(tmp_path / "missing"), digest_path=None)
        is None
    )

    assert service._is_allowed_artifact_asset("meta.json") is True
    assert service._is_allowed_artifact_asset("frame_001.png") is True
    assert service._is_allowed_artifact_asset("folder/frame_001.png") is True
    assert service._is_allowed_artifact_asset("frame_001.txt") is False
    assert service._is_allowed_artifact_asset("/") is False

    assert service._json_loads(None) is None
    assert service._json_loads('{"ok":1}') == {"ok": 1}
    assert service._json_loads("not-json") == {"raw": "not-json"}

    meta_file = tmp_path / "meta.json"
    meta_file.write_text('{"ok":1}', encoding="utf-8")
    assert service._read_artifact_meta(artifact_root=str(tmp_path), digest_path=None) == {"ok": 1}
    meta_file.write_text("bad-json", encoding="utf-8")
    assert service._read_artifact_meta(artifact_root=str(tmp_path), digest_path=None) == {}

    assert service._artifacts_from_steps([{"name": "x", "result": {}}]) == {}
    assert service._artifacts_from_steps(
        [
            {
                "name": "write_artifacts",
                "result": {"state_updates": {"artifacts": {"digest": "/tmp/d.md", "x": 1}}},
            }
        ]
    ) == {"digest": "/tmp/d.md"}
