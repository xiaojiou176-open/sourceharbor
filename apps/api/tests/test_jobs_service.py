from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from apps.api.app.services import jobs as jobs_module
from apps.api.app.services.jobs import JobsService


def _service() -> JobsService:
    return JobsService.__new__(JobsService)


class _JobsRepoStub:
    def __init__(self) -> None:
        self.job = SimpleNamespace(artifact_root=None, artifact_digest_md=None)
        self.final_status: str | None = None
        self.digest_path: str | None = None
        self.digest_by_url_path: str | None = None
        self.db = SimpleNamespace(execute=lambda *_args, **_kwargs: None, rollback=lambda: None)

    def get(self, job_id: uuid.UUID) -> object:
        if self.job is None:
            return None
        self.job.job_id = job_id
        return self.job

    def get_pipeline_final_status(self, *, job_id: uuid.UUID) -> str | None:
        self.last_final_status_job_id = job_id
        return self.final_status

    def get_artifact_digest_md(self, *, job_id: uuid.UUID) -> str | None:
        self.last_digest_job_id = job_id
        return self.digest_path

    def get_artifact_digest_md_by_video_url(self, *, video_url: str) -> str | None:
        self.last_digest_video_url = video_url
        return self.digest_by_url_path


def test_build_evidence_bundle_returns_none_when_job_is_missing() -> None:
    service = _service()
    repo = _JobsRepoStub()
    repo.job = None
    service.repo = repo

    assert service.build_evidence_bundle(job_id=uuid.uuid4()) is None


def test_build_evidence_bundle_uses_current_helpers_and_shapes_payload() -> None:
    service = _service()
    job_id = uuid.uuid4()
    row = SimpleNamespace(
        id=job_id,
        video_id=uuid.uuid4(),
        kind="video_digest_v1",
        status="succeeded",
        mode="full",
        created_at=jobs_module.datetime.now(jobs_module.UTC),
        updated_at=jobs_module.datetime.now(jobs_module.UTC),
        error_message=None,
        artifact_root="/tmp/artifacts",
        artifact_digest_md="/tmp/artifacts/digest.md",
        llm_required=True,
        llm_gate_passed=True,
        hard_fail_reason=None,
    )
    repo = _JobsRepoStub()
    repo.job = row
    service.repo = repo
    steps = [
        {
            "name": "collect",
            "status": "succeeded",
            "attempt": 1,
            "started_at": "2026-04-01T10:00:00Z",
            "finished_at": "2026-04-01T10:01:00Z",
            "error": None,
        }
    ]
    service.get_steps = lambda job_id: steps
    service.compare_with_previous = lambda job_id: {"has_previous": False}
    service.get_knowledge_cards = lambda job_id: [{"id": "card-1"}]
    service.get_artifact_payload = lambda job_id, video_url=None: {
        "markdown": "# Digest",
        "meta": {"source": "artifact"},
    }
    service.resolve_llm_gate_fields = lambda **kwargs: (True, True, None)
    service.get_pipeline_final_status = lambda job_id, fallback_status: "succeeded"
    service.get_artifacts_index = lambda artifact_root, artifact_digest_md, steps: {
        "digest": "digest.md"
    }
    service.get_degradations = lambda artifact_root, artifact_digest_md, steps: []
    service.get_notification_retry = lambda job_id: {"status": "idle"}

    payload = service.build_evidence_bundle(job_id=job_id)

    assert payload is not None
    assert payload["bundle_kind"] == "sourceharbor_job_evidence_bundle_v1"
    assert payload["job"]["id"] == str(job_id)
    assert payload["trace_summary"]["step_count"] == 1
    assert payload["trace_summary"]["notification_retry"] == {"status": "idle"}
    assert payload["digest"] == "# Digest"
    assert payload["comparison"] == {"has_previous": False}
    assert payload["knowledge_cards"] == [{"id": "card-1"}]
    assert payload["artifact_manifest"] == {"digest": "digest.md"}
    assert payload["step_summary"] == steps


def test_build_evidence_bundle_flattens_meta_and_surfaces_rich_evidence() -> None:
    service = _service()
    job_id = uuid.uuid4()
    row = SimpleNamespace(
        id=job_id,
        video_id=uuid.uuid4(),
        kind="video_digest_v1",
        status="succeeded",
        mode="full",
        created_at=jobs_module.datetime.now(jobs_module.UTC),
        updated_at=jobs_module.datetime.now(jobs_module.UTC),
        error_message=None,
        artifact_root="/tmp/artifacts",
        artifact_digest_md="/tmp/artifacts/digest.md",
        llm_required=True,
        llm_gate_passed=True,
        hard_fail_reason=None,
    )
    repo = _JobsRepoStub()
    repo.job = row
    service.repo = repo
    service.get_steps = lambda job_id: []
    service.compare_with_previous = lambda job_id: None
    service.get_knowledge_cards = lambda job_id: []
    service.get_artifact_payload = lambda job_id, video_url=None: {
        "markdown": "# Digest",
        "meta": {
            "metadata": {
                "uploader": "demo-up",
                "thumbnail": "https://img.example/thumb.jpg",
                "uploader_mid": "12345",
                "uploader_url": "https://space.bilibili.com/12345",
                "view_count": 999,
                "site_objects": {"owner": {"mid": "12345"}},
            },
            "raw_stage_contract": {"video_contract_satisfied": True},
            "danmaku": {
                "status": "available",
                "entry_count": 1,
                "entries": [{"content": "hello"}],
            },
        },
    }
    service.resolve_llm_gate_fields = lambda **kwargs: (True, True, None)
    service.get_pipeline_final_status = lambda job_id, fallback_status: "succeeded"
    service._build_commentary_evidence = lambda artifact_root, digest_path: {
        "top_comment_count": 2,
        "reply_bucket_count": 1,
        "top_threads": [{"author": "demo-user", "like_count": 12, "reply_count": 3}],
    }
    service.get_artifacts_index = lambda artifact_root, artifact_digest_md, steps: {
        "digest": "digest.md",
        "danmaku": "danmaku.json",
        "comments": "comments.json",
    }
    service.get_degradations = lambda artifact_root, artifact_digest_md, steps: []
    service.get_notification_retry = lambda job_id: None

    payload = service.build_evidence_bundle(job_id=job_id)

    assert payload is not None
    assert payload["digest_meta"]["uploader"] == "demo-up"
    assert payload["digest_meta"]["uploader_mid"] == "12345"
    assert payload["digest_meta"]["raw_stage_contract"]["video_contract_satisfied"] is True
    assert payload["rich_evidence"]["danmaku"]["entry_count"] == 1
    assert payload["rich_evidence"]["site_objects"]["owner"]["mid"] == "12345"
    assert payload["rich_evidence"]["commentary"]["top_comment_count"] == 2
    assert payload["artifact_manifest"]["danmaku"] == "danmaku.json"


def test_build_commentary_evidence_reads_digest_parent_and_falls_back_to_reply_buckets(
    tmp_path: Path,
) -> None:
    digest_root = tmp_path / "digest-root"
    digest_root.mkdir(parents=True, exist_ok=True)
    digest_path = digest_root / "digest.md"
    digest_path.write_text("# digest", encoding="utf-8")
    comments_path = digest_root / "comments.json"
    comments_path.write_text(
        json.dumps(
            {
                "sort": "hot",
                "top_comments": [
                    {"comment_id": 101, "author": "alice", "content": "top", "like_count": 7},
                    "skip-me",
                    {
                        "comment_id": 202,
                        "author": "bob",
                        "content": "inline replies",
                        "like_count": 3,
                        "replies": [{"id": 1}, {"id": 2}],
                    },
                ],
                "replies": {"101": [{"id": 11}, {"id": 12}, {"id": 13}]},
            }
        ),
        encoding="utf-8",
    )

    service = _service()
    service._resolve_artifact_root = lambda **_: None  # type: ignore[method-assign]

    payload = service._build_commentary_evidence(
        artifact_root=None,
        digest_path=str(digest_path),
    )

    assert payload == {
        "sort": "hot",
        "top_comment_count": 3,
        "reply_bucket_count": 1,
        "top_threads": [
            {
                "author": "alice",
                "content": "top",
                "like_count": 7,
                "reply_count": 3,
            },
            {
                "author": "bob",
                "content": "inline replies",
                "like_count": 3,
                "reply_count": 2,
            },
        ],
    }


def test_build_commentary_evidence_returns_none_for_non_dict_comments_payload() -> None:
    service = _service()
    service._read_artifact_json = lambda **_: ["not-a-dict"]  # type: ignore[method-assign]

    assert service._build_commentary_evidence(artifact_root="/tmp", digest_path=None) is None


def test_read_artifact_json_skips_invalid_root_file_and_uses_digest_parent(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    digest_root = tmp_path / "digest-root"
    digest_root.mkdir(parents=True, exist_ok=True)
    digest_path = digest_root / "digest.md"
    digest_path.write_text("# digest", encoding="utf-8")
    (artifact_root / "comments.json").write_text("{bad-json", encoding="utf-8")
    expected_payload = {"top_comments": [{"comment_id": 1}]}
    (digest_root / "comments.json").write_text(json.dumps(expected_payload), encoding="utf-8")

    service = _service()

    payload = service._read_artifact_json(
        artifact_root=str(artifact_root),
        digest_path=str(digest_path),
        filename="comments.json",
    )

    assert payload == expected_payload


def test_extract_thought_metadata_supports_legacy_payload() -> None:
    payload = {
        "thought_metadata": {
            "provider": "gemini",
            "thought_tokens": 42,
            "planner": "legacy_planner",
        }
    }

    metadata = _service()._extract_thought_metadata(payload)

    assert metadata["provider"] == "gemini"
    assert metadata["planner"] == "legacy_planner"
    assert metadata["thinking"]["usage"]["thoughts_token_count"] == 42
    assert metadata["thought_count"] == 0
    assert metadata["thought_signatures"] == []


def test_extract_thought_metadata_supports_llm_meta_thinking_payload() -> None:
    payload = {
        "llm_meta": {
            "provider": "gemini",
            "thinking": {
                "enabled": True,
                "level": "HIGH",
                "include_thoughts": True,
                "thought_count": 2,
                "thought_signatures": ["sig-A", "sig-B"],
                "thought_signature_digest": "digest-1",
                "usage": {"thoughts_token_count": 12, "total_token_count": 144},
            },
        }
    }

    metadata = _service()._extract_thought_metadata(payload)

    assert metadata["provider"] == "gemini"
    assert metadata["thinking"]["enabled"] is True
    assert metadata["thinking"]["level"] == "high"
    assert metadata["thinking"]["include_thoughts"] is True
    assert metadata["thinking"]["thought_count"] == 2
    assert metadata["thought_count"] == 2
    assert metadata["thought_signatures"] == ["sig-A", "sig-B"]
    assert metadata["thought_signature_digest"] == "digest-1"


def test_extract_thought_metadata_returns_empty_structure_when_missing() -> None:
    metadata = _service()._extract_thought_metadata({"result": "ok"})

    assert metadata == {
        "thinking": {
            "enabled": None,
            "level": None,
            "include_thoughts": None,
            "thought_count": 0,
            "thought_signatures": [],
            "thought_signature_digest": None,
            "usage": {},
        },
        "thought_count": 0,
        "thought_signatures": [],
        "thought_signature_digest": None,
    }


@pytest.mark.parametrize("payload", [None, "bad-payload", 123, ["list"]])
def test_extract_thought_metadata_returns_empty_structure_for_non_dict_payloads(
    payload: object,
) -> None:
    service = _service()

    assert service._extract_thought_metadata(payload) == {
        "thinking": {
            "enabled": None,
            "level": None,
            "include_thoughts": None,
            "thought_count": 0,
            "thought_signatures": [],
            "thought_signature_digest": None,
            "usage": {},
        },
        "thought_count": 0,
        "thought_signatures": [],
        "thought_signature_digest": None,
    }


@pytest.mark.parametrize("legacy_key", ["thinking_metadata", "thoughts_metadata", "thoughts"])
def test_extract_thought_metadata_supports_extra_legacy_keys(legacy_key: str) -> None:
    payload = {
        legacy_key: {
            "provider": "legacy-provider",
            "thought_signatures": ["sig-legacy"],
        },
        "llm_meta": {"provider": "llm-provider"},
    }

    metadata = _service()._extract_thought_metadata(payload)

    assert metadata["provider"] == "legacy-provider"
    assert metadata["thought_signatures"] == ["sig-legacy"]
    assert metadata["thought_count"] == 1


def test_extract_thought_metadata_provider_fallback_priority() -> None:
    payload_from_thinking = {
        "thought_metadata": {"provider": "   "},
        "llm_meta": {"provider": "llm-provider", "thinking": {"provider": "thinking-provider"}},
    }
    assert (
        _service()._extract_thought_metadata(payload_from_thinking)["provider"]
        == "thinking-provider"
    )

    payload_from_llm_meta = {
        "thought_metadata": {"provider": "   "},
        "llm_meta": {"provider": "llm-provider", "thinking": {"provider": "   "}},
    }
    assert _service()._extract_thought_metadata(payload_from_llm_meta)["provider"] == "llm-provider"


def test_normalize_thinking_payload_handles_invalid_source_and_boundaries() -> None:
    service = _service()

    # Truthy non-dict llm payload should return the empty structure.
    assert service._normalize_thinking_payload({}, "bad") == service._empty_thinking_payload()  # type: ignore[arg-type]

    normalized = service._normalize_thinking_payload(
        {"enabled": True},
        {
            "enabled": True,
            "include_thoughts": False,
            "level": " HIGH ",
            "thought_count": 0,
            "thought_signatures": [" sig-1 ", 1, ""],
            "thought_tokens": 5,
        },
    )
    assert normalized["enabled"] is True
    assert normalized["include_thoughts"] is False
    assert normalized["level"] == "high"
    assert normalized["thought_signatures"] == ["sig-1"]
    assert normalized["thought_count"] == 1
    assert normalized["usage"] == {"thoughts_token_count": 5}

    usage = {"thoughts_token_count": 9}
    copied_usage = service._normalize_thinking_payload({}, {"usage": usage})["usage"]
    assert copied_usage == usage
    assert copied_usage is not usage


def test_normalize_thinking_payload_returns_empty_for_non_dict_sources() -> None:
    service = _service()
    empty = service._empty_thinking_payload()

    assert service._normalize_thinking_payload({}, "bad") == empty  # type: ignore[arg-type]
    assert service._normalize_thinking_payload({}, 1) == empty  # type: ignore[arg-type]


def test_extract_thought_metadata_prefers_llm_thinking_and_copies_signatures() -> None:
    llm_signatures = ["sig-a", " sig-b "]
    payload = {
        "thought_metadata": {
            "provider": "legacy-provider",
            "thought_count": 99,
            "thought_signatures": ["legacy-sig"],
        },
        "llm_meta": {
            "thinking": {
                "thought_count": -5,
                "thought_signatures": llm_signatures,
            }
        },
    }

    metadata = _service()._extract_thought_metadata(payload)

    assert metadata["provider"] == "legacy-provider"
    assert metadata["thinking"]["thought_count"] == 2
    assert metadata["thought_count"] == 2
    assert metadata["thinking"]["thought_signatures"] == ["sig-a", "sig-b"]
    assert metadata["thought_signatures"] == ["sig-a", "sig-b"]
    assert metadata["thinking"]["thought_signatures"] is not llm_signatures
    assert metadata["thought_signatures"] is not metadata["thinking"]["thought_signatures"]


def test_normalize_thinking_payload_prefers_llm_payload_over_legacy_payload() -> None:
    normalized = _service()._normalize_thinking_payload(
        {
            "enabled": True,
            "include_thoughts": True,
            "level": "low",
            "thought_count": 9,
            "thought_signatures": ["legacy-sig"],
        },
        {
            "enabled": False,
            "include_thoughts": False,
            "level": "HIGH",
            "thought_count": -1,
            "thought_signatures": [" llm-sig "],
            "usage": {"thoughts_token_count": 7},
        },
    )

    assert normalized["enabled"] is False
    assert normalized["include_thoughts"] is False
    assert normalized["level"] == "high"
    assert normalized["thought_count"] == 1
    assert normalized["thought_signatures"] == ["llm-sig"]
    assert normalized["usage"] == {"thoughts_token_count": 7}


def test_resolve_llm_gate_fields_honors_explicit_gate_values() -> None:
    service = _service()

    required, passed, reason = service.resolve_llm_gate_fields(
        llm_required=None,
        llm_gate_passed=False,
        hard_fail_reason="hard-fail",
        steps=[],
    )
    assert (required, passed, reason) == (True, False, "hard-fail")

    required2, passed2, reason2 = service.resolve_llm_gate_fields(
        llm_required=False,
        llm_gate_passed=True,
        hard_fail_reason="ignored",
        steps=[],
    )
    assert (required2, passed2, reason2) == (False, True, None)

    required3, passed3, reason3 = service.resolve_llm_gate_fields(
        llm_required=None,
        llm_gate_passed=False,
        hard_fail_reason=None,
        steps=[{"name": "llm_outline", "status": "failed"}],
    )
    assert (required3, passed3, reason3) == (True, False, None)


def test_resolve_llm_gate_fields_handles_missing_failed_and_pending_steps() -> None:
    service = _service()

    assert service.resolve_llm_gate_fields(
        llm_required=True,
        llm_gate_passed=None,
        hard_fail_reason="from-input",
        steps=[{"name": "subtitles", "status": "succeeded"}],
    ) == (True, None, "from-input")

    assert service.resolve_llm_gate_fields(
        llm_required=True,
        llm_gate_passed=None,
        hard_fail_reason="from-input",
        steps=[{"name": "llm_outline", "status": "running"}],
    ) == (True, None, "from-input")

    failed = service.resolve_llm_gate_fields(
        llm_required=True,
        llm_gate_passed=None,
        hard_fail_reason="from-input",
        steps=[{"name": "llm_outline", "status": "failed", "error": {"error": " step failed "}}],
    )
    assert failed == (True, False, "step failed")

    default_reason = service.resolve_llm_gate_fields(
        llm_required=True,
        llm_gate_passed=None,
        hard_fail_reason=None,
        steps=[{"name": "llm_digest", "status": "failed", "error": "boom"}],
    )
    assert default_reason == (True, False, "llm_step_failed")

    all_ok = service.resolve_llm_gate_fields(
        llm_required=True,
        llm_gate_passed=None,
        hard_fail_reason="unused",
        steps=[
            {"name": "llm_outline", "status": "succeeded"},
            {"name": "llm_digest", "status": "skipped"},
        ],
    )
    assert all_ok == (True, True, None)


def test_resolve_llm_gate_fields_prefers_reason_key_and_ignores_non_llm_failures() -> None:
    service = _service()

    resolved = service.resolve_llm_gate_fields(
        llm_required=None,
        llm_gate_passed=None,
        hard_fail_reason="fallback",
        steps=[
            {"name": "subtitles", "status": "failed", "error": {"reason": "ignore-this"}},
            {
                "name": "llm_outline",
                "status": "failed",
                "error": {"reason": " preferred ", "error": "secondary"},
            },
            {"name": "llm_digest", "status": "running"},
        ],
    )

    assert resolved == (True, False, "preferred")


def test_resolve_llm_gate_fields_pending_without_hard_fail_reason_returns_none_reason() -> None:
    resolved = _service().resolve_llm_gate_fields(
        llm_required=True,
        llm_gate_passed=None,
        hard_fail_reason=None,
        steps=[{"name": "llm_digest", "status": "running"}],
    )
    assert resolved == (True, None, None)


def test_normalize_artifact_asset_path_maps_alias_and_preserves_custom_path() -> None:
    service = _service()
    assert service._normalize_artifact_asset_path(" Meta ") == "meta.json"
    assert service._normalize_artifact_asset_path("frames/frame_001.JPG") == "frames/frame_001.JPG"
    assert service._normalize_artifact_asset_path("   ") == ""


def test_is_allowed_artifact_asset_enforces_whitelist_and_frame_rules() -> None:
    service = _service()

    assert service._is_allowed_artifact_asset("meta.json") is True
    assert service._is_allowed_artifact_asset("frames/frame_001.JPG") is True
    assert service._is_allowed_artifact_asset("frames/notframe_001.jpg") is False
    assert service._is_allowed_artifact_asset("nested/meta.json") is False
    assert service._is_allowed_artifact_asset("") is False


def test_get_artifact_asset_allows_alias_and_blocks_absolute_path_outside_root(tmp_path) -> None:
    job_id = uuid.uuid4()
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    meta_path = artifact_root / "meta.json"
    meta_path.write_text("{}", encoding="utf-8")
    outside_path = tmp_path / "secret.txt"
    outside_path.write_text("secret", encoding="utf-8")

    service = _service()
    service.get_job = lambda _job_id: SimpleNamespace(  # type: ignore[method-assign]
        artifact_root=str(artifact_root),
        artifact_digest_md=None,
    )

    assert service.get_artifact_asset(job_id=job_id, path="meta") == meta_path.resolve()
    assert service.get_artifact_asset(job_id=job_id, path=str(outside_path.resolve())) is None


def test_get_artifact_asset_uses_digest_parent_when_artifact_root_is_missing(tmp_path) -> None:
    job_id = uuid.uuid4()
    digest_root = tmp_path / "digest-root"
    digest_root.mkdir(parents=True, exist_ok=True)
    digest_path = digest_root / "digest.md"
    digest_path.write_text("# digest", encoding="utf-8")
    frame_dir = digest_root / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    frame_path = frame_dir / "frame_001.PNG"
    frame_path.write_bytes(b"image")

    service = _service()
    service.get_job = lambda _job_id: SimpleNamespace(  # type: ignore[method-assign]
        artifact_root=str(tmp_path / "missing-root"),
        artifact_digest_md=str(digest_path),
    )

    assert service.get_artifact_asset(job_id=job_id, path="digest") == digest_path.resolve()
    assert (
        service.get_artifact_asset(job_id=job_id, path="frames/frame_001.PNG")
        == frame_path.resolve()
    )


def test_get_job_and_pipeline_final_status_cover_repo_and_fallback_paths() -> None:
    repo = _JobsRepoStub()
    job_id = uuid.uuid4()
    repo.job = SimpleNamespace(id=job_id, artifact_root=None, artifact_digest_md=None)
    repo.final_status = "degraded"

    service = _service()
    service.repo = repo  # type: ignore[attr-defined]

    assert service.get_job(job_id) is repo.job
    assert service.get_pipeline_final_status(job_id, fallback_status="queued") == "degraded"

    repo.final_status = "queued"
    assert service.get_pipeline_final_status(job_id, fallback_status="failed") == "failed"
    assert service.get_pipeline_final_status(job_id, fallback_status="queued") is None


@pytest.mark.parametrize("repo_status", ["succeeded", "degraded", "failed"])
def test_get_pipeline_final_status_prefers_terminal_repo_status(repo_status: str) -> None:
    repo = _JobsRepoStub()
    repo.final_status = repo_status
    service = _service()
    service.repo = repo  # type: ignore[attr-defined]
    job_id = uuid.uuid4()

    # Use a non-terminal fallback so terminal repo status must win, including "failed".
    assert service.get_pipeline_final_status(job_id, fallback_status="queued") == repo_status
    assert repo.last_final_status_job_id == job_id


@pytest.mark.parametrize("fallback_status", ["succeeded", "degraded", "failed"])
def test_get_pipeline_final_status_accepts_all_terminal_fallbacks(fallback_status: str) -> None:
    repo = _JobsRepoStub()
    repo.final_status = "running"
    service = _service()
    service.repo = repo  # type: ignore[attr-defined]

    assert (
        service.get_pipeline_final_status(uuid.uuid4(), fallback_status=fallback_status)
        == fallback_status
    )


def test_get_steps_and_step_summary_read_sqlite_rows(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = uuid.UUID(int=1)
    db_path = tmp_path / "state.db"
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE step_runs (
                job_id TEXT NOT NULL,
                step_name TEXT NOT NULL,
                status TEXT NOT NULL,
                attempt INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                error_json TEXT,
                error_kind TEXT,
                retry_meta_json TEXT,
                result_json TEXT,
                cache_key TEXT
            );
            """
        )
        conn.execute(
            """
            INSERT INTO step_runs (
                job_id, step_name, status, attempt, started_at, finished_at,
                error_json, error_kind, retry_meta_json, result_json, cache_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(job_id),
                "llm_outline",
                "failed",
                1,
                "2026-03-01T00:00:00+00:00",
                "2026-03-01T00:01:00+00:00",
                json.dumps({"reason": "bad"}),
                "fatal",
                json.dumps({"attempts": 2}),
                json.dumps(
                    {
                        "degraded": True,
                        "thought_metadata": {"provider": "gemini", "thought_signatures": ["sig-1"]},
                    }
                ),
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
                str(job_id),
                "write_artifacts",
                "succeeded",
                2,
                "2026-03-01T00:02:00+00:00",
                "2026-03-01T00:03:00+00:00",
                None,
                None,
                None,
                json.dumps({"output": {"files": {"digest": "/tmp/digest.md"}}}),
                "cache-2",
            ),
        )

    monkeypatch.setattr(jobs_module, "settings", SimpleNamespace(sqlite_state_path=str(db_path)))
    service = _service()
    service.repo = _JobsRepoStub()  # type: ignore[attr-defined]

    steps = service.get_steps(job_id)

    assert len(steps) == 2
    assert steps[0]["name"] == "llm_outline"
    assert steps[0]["error"] == {"reason": "bad"}
    assert steps[0]["error_kind"] == "fatal"
    assert steps[0]["retry_meta"] == {"attempts": 2}
    assert steps[0]["thought_metadata"]["provider"] == "gemini"
    assert steps[0]["cache_key"] == "cache-1"
    assert steps[1]["result"] == {"output": {"files": {"digest": "/tmp/digest.md"}}}

    summary = service.get_step_summary(job_id)
    assert summary == [
        {
            "name": "llm_outline",
            "status": "failed",
            "attempt": 1,
            "started_at": "2026-03-01T00:00:00+00:00",
            "finished_at": "2026-03-01T00:01:00+00:00",
            "error": {"reason": "bad"},
        },
        {
            "name": "write_artifacts",
            "status": "succeeded",
            "attempt": 2,
            "started_at": "2026-03-01T00:02:00+00:00",
            "finished_at": "2026-03-01T00:03:00+00:00",
            "error": None,
        },
    ]


def test_get_steps_projects_fields_with_case_sensitive_row_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _StrictRow(dict[str, Any]):
        def __getitem__(self, key: str) -> Any:
            if key not in self:
                raise KeyError(key)
            return super().__getitem__(key)

    class _Cursor:
        def __init__(self, rows: list[_StrictRow]) -> None:
            self._rows = rows

        def fetchall(self) -> list[_StrictRow]:
            return self._rows

    class _Conn:
        def __init__(self, rows: list[_StrictRow]) -> None:
            self.row_factory: Any = None
            self.closed = False
            self.rows = rows
            self.executed_params: Any = None

        def execute(self, _sql: str, params: tuple[str]) -> _Cursor:
            self.executed_params = params
            return _Cursor(self.rows)

        def close(self) -> None:
            self.closed = True

    job_id = uuid.UUID(int=11)
    rows = [
        _StrictRow(
            {
                "step_name": "llm_digest",
                "status": "succeeded",
                "attempt": 2,
                "started_at": "2026-03-05T00:00:00+00:00",
                "finished_at": "2026-03-05T00:01:00+00:00",
                "error_json": json.dumps({"reason": "none"}),
                "error_kind": "none",
                "retry_meta_json": json.dumps({"attempts": 1}),
                "result_json": json.dumps({"ok": True}),
                "cache_key": "cache-k",
            }
        )
    ]
    conn = _Conn(rows)

    monkeypatch.setattr(
        jobs_module, "settings", SimpleNamespace(sqlite_state_path="/tmp/unused.db")
    )
    monkeypatch.setattr(jobs_module.sqlite3, "connect", lambda *_args, **_kwargs: conn)

    service = _service()
    service.repo = _JobsRepoStub()  # type: ignore[attr-defined]
    steps = service.get_steps(job_id)

    assert conn.row_factory is sqlite3.Row
    assert conn.executed_params == (str(job_id),)
    assert conn.closed is True
    assert len(steps) == 1
    assert steps[0]["name"] == "llm_digest"
    assert steps[0]["status"] == "succeeded"
    assert steps[0]["attempt"] == 2
    assert steps[0]["error"] == {"reason": "none"}
    assert steps[0]["retry_meta"] == {"attempts": 1}
    assert steps[0]["result"] == {"ok": True}
    assert steps[0]["cache_key"] == "cache-k"


def test_get_steps_returns_empty_when_sqlite_open_or_query_fails(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service()
    service.repo = _JobsRepoStub()  # type: ignore[attr-defined]

    monkeypatch.setattr(
        jobs_module,
        "settings",
        SimpleNamespace(sqlite_state_path=str(tmp_path / "missing.db")),
    )

    class _BoomConn:
        row_factory = None

        def execute(self, *_args: Any, **_kwargs: Any):
            raise sqlite3.Error("boom")

        def close(self) -> None:
            return None

    monkeypatch.setattr(jobs_module.sqlite3, "connect", lambda *_args, **_kwargs: _BoomConn())
    assert service.get_steps(uuid.UUID(int=2)) == []

    def _raise_connect(*_args: Any, **_kwargs: Any):
        raise sqlite3.Error("cannot open")

    monkeypatch.setattr(jobs_module.sqlite3, "connect", _raise_connect)
    assert service.get_steps(uuid.UUID(int=3)) == []


def test_get_steps_and_step_summary_return_empty_on_successful_empty_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Cursor:
        def fetchall(self) -> list[dict[str, Any]]:
            return []

    class _Conn:
        def __init__(self) -> None:
            self.row_factory: Any = None
            self.closed = False

        def execute(self, _sql: str, _params: tuple[str]) -> _Cursor:
            return _Cursor()

        def close(self) -> None:
            self.closed = True

    conn = _Conn()
    monkeypatch.setattr(
        jobs_module, "settings", SimpleNamespace(sqlite_state_path="/tmp/unused-empty.db")
    )
    monkeypatch.setattr(jobs_module.sqlite3, "connect", lambda *_args, **_kwargs: conn)

    service = _service()
    service.repo = _JobsRepoStub()  # type: ignore[attr-defined]
    job_id = uuid.UUID(int=12)
    assert service.get_steps(job_id) == []
    assert service.get_step_summary(job_id) == []
    assert conn.closed is True


def test_get_steps_normalizes_invalid_json_and_non_dict_payloads(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = uuid.UUID(int=10)
    db_path = tmp_path / "state-invalid.db"
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE step_runs (
                job_id TEXT NOT NULL,
                step_name TEXT NOT NULL,
                status TEXT NOT NULL,
                attempt INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                error_json TEXT,
                error_kind TEXT,
                retry_meta_json TEXT,
                result_json TEXT,
                cache_key TEXT
            );
            """
        )
        conn.execute(
            """
            INSERT INTO step_runs (
                job_id, step_name, status, attempt, started_at, finished_at,
                error_json, error_kind, retry_meta_json, result_json, cache_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(job_id),
                "llm_digest",
                "failed",
                1,
                "2026-03-03T00:00:00+00:00",
                "2026-03-03T00:01:00+00:00",
                "{bad-json",
                "transient",
                json.dumps(["not-a-dict"]),
                json.dumps("not-a-dict"),
                None,
            ),
        )

    monkeypatch.setattr(jobs_module, "settings", SimpleNamespace(sqlite_state_path=str(db_path)))
    service = _service()
    service.repo = _JobsRepoStub()  # type: ignore[attr-defined]

    steps = service.get_steps(job_id)

    assert len(steps) == 1
    assert steps[0]["error"] == {"raw": "{bad-json"}
    assert steps[0]["retry_meta"] is None
    assert steps[0]["result"] is None
    assert steps[0]["thought_metadata"] == service._empty_thought_metadata()


def test_get_step_summary_projects_expected_fields_only() -> None:
    job_id = uuid.uuid4()
    service = _service()
    calls: list[uuid.UUID] = []

    sample_steps = [
        {
            "name": "llm_outline",
            "status": "failed",
            "attempt": 3,
            "started_at": "2026-03-04T00:00:00+00:00",
            "finished_at": "2026-03-04T00:01:00+00:00",
            "error": {"reason": "boom"},
            "error_kind": "transient",
            "result": {"degraded": True},
        }
    ]

    def _fake_get_steps(query_job_id: uuid.UUID) -> list[dict[str, object]]:
        calls.append(query_job_id)
        return sample_steps

    service.get_steps = _fake_get_steps  # type: ignore[method-assign]

    assert service.get_step_summary(job_id) == [
        {
            "name": "llm_outline",
            "status": "failed",
            "attempt": 3,
            "started_at": "2026-03-04T00:00:00+00:00",
            "finished_at": "2026-03-04T00:01:00+00:00",
            "error": {"reason": "boom"},
        }
    ]
    assert calls == [job_id]


def test_notification_retry_and_artifact_helpers_cover_success_and_fallbacks(tmp_path) -> None:
    repo = _JobsRepoStub()
    artifact_root = tmp_path / "artifact-root"
    artifact_root.mkdir()
    meta_path = artifact_root / "meta.json"
    meta_path.write_text(
        json.dumps({"degradations": [{"step": "llm_digest", "status": "failed"}]}), encoding="utf-8"
    )
    digest_path = artifact_root / "digest.md"
    digest_path.write_text("# digest", encoding="utf-8")

    class _Mappings:
        def __init__(self, row: dict[str, Any] | None) -> None:
            self._row = row

        def first(self) -> dict[str, Any] | None:
            return self._row

    class _ExecuteResult:
        def __init__(self, row: dict[str, Any] | None) -> None:
            self._row = row

        def mappings(self) -> _Mappings:
            return _Mappings(self._row)

    captured_execute: dict[str, Any] = {}

    def _execute(query: Any, params: Any = None) -> _ExecuteResult:
        captured_execute["query"] = query
        captured_execute["params"] = params
        return _ExecuteResult(
            {
                "delivery_id": "d1",
                "status": "retrying",
                "attempt_count": 2,
                "next_retry_at": "2026-03-02T00:00:00+00:00",
                "last_error_kind": "timeout",
            }
        )

    repo.db = SimpleNamespace(execute=_execute, rollback=lambda: None)
    repo.digest_path = str(digest_path)
    repo.digest_by_url_path = str(digest_path)

    service = _service()
    service.repo = repo  # type: ignore[attr-defined]

    retry = service.get_notification_retry(uuid.UUID(int=4))
    assert retry == {
        "delivery_id": "d1",
        "status": "retrying",
        "attempt_count": 2,
        "next_retry_at": "2026-03-02T00:00:00+00:00",
        "last_error_kind": "timeout",
    }
    assert captured_execute["params"] == {"job_id": str(uuid.UUID(int=4))}
    query_text = str(captured_execute["query"])
    assert "FROM notification_deliveries" in query_text
    assert "kind = 'video_digest'" in query_text

    payload = service.get_artifact_payload(job_id=uuid.UUID(int=5), video_url=None)
    assert payload == {
        "markdown": "# digest",
        "meta": {"degradations": [{"step": "llm_digest", "status": "failed"}]},
    }
    assert service.get_artifact_digest_md(job_id=uuid.UUID(int=5), video_url=None) == "# digest"

    index = service.get_artifacts_index(
        artifact_root=str(artifact_root),
        artifact_digest_md=str(digest_path),
        steps=[],
    )
    assert index["digest"] == str(digest_path.resolve())
    assert index["meta"] == str(meta_path.resolve())

    degradations = service.get_degradations(
        artifact_root=str(artifact_root),
        artifact_digest_md=str(digest_path),
        steps=[],
    )
    assert degradations == [{"step": "llm_digest", "status": "failed"}]


def test_get_artifacts_index_prefers_write_artifacts_step_index_over_filesystem_scan(
    tmp_path,
) -> None:
    service = _service()
    artifact_root = tmp_path / "artifact-root"
    artifact_root.mkdir()
    (artifact_root / "meta.json").write_text("{}", encoding="utf-8")
    (artifact_root / "digest.md").write_text("# disk digest", encoding="utf-8")

    step_index = {
        "digest": str((tmp_path / "step-digest.md").resolve()),
        "meta": str((tmp_path / "step-meta.json").resolve()),
    }
    steps = [
        {
            "name": "write_artifacts",
            "result": {"output": {"files": step_index}},
        }
    ]

    index = service.get_artifacts_index(
        artifact_root=str(artifact_root),
        artifact_digest_md=str(artifact_root / "digest.md"),
        steps=steps,
    )

    assert index == step_index


def test_get_artifacts_index_short_circuits_to_artifacts_from_steps_result(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    artifact_root = tmp_path / "artifact-root"
    artifact_root.mkdir()
    (artifact_root / "meta.json").write_text("{}", encoding="utf-8")
    (artifact_root / "digest.md").write_text("# filesystem digest", encoding="utf-8")

    steps = [{"name": "write_artifacts", "result": {"output": {"files": {"digest": "ignored"}}}}]
    sentinel_index = {
        "digest": "/sentinel/from-steps/digest.md",
        "meta": "/sentinel/from-steps/meta.json",
    }
    captured_steps: list[list[dict[str, object]]] = []

    def _fake_artifacts_from_steps(current_steps: list[dict[str, object]]) -> dict[str, str]:
        captured_steps.append(current_steps)
        return sentinel_index

    monkeypatch.setattr(service, "_artifacts_from_steps", _fake_artifacts_from_steps)

    index = service.get_artifacts_index(
        artifact_root=str(artifact_root),
        artifact_digest_md=str(artifact_root / "digest.md"),
        steps=steps,
    )

    assert index is sentinel_index
    assert captured_steps == [steps]
    assert index["digest"] == "/sentinel/from-steps/digest.md"
    assert index["meta"] == "/sentinel/from-steps/meta.json"


def test_get_degradations_reads_meta_via_artifact_root_without_digest_path(tmp_path) -> None:
    service = _service()
    artifact_root = tmp_path / "artifact-root"
    artifact_root.mkdir()
    (artifact_root / "meta.json").write_text(
        json.dumps({"degradations": [{"step": "write_artifacts", "status": "degraded"}]}),
        encoding="utf-8",
    )

    degradations = service.get_degradations(
        artifact_root=str(artifact_root),
        artifact_digest_md=None,
        steps=[],
    )

    assert degradations == [{"step": "write_artifacts", "status": "degraded"}]


def test_get_degradations_uses_meta_before_fallback_step_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()

    def _fake_read_artifact_meta(
        *, artifact_root: str | None, digest_path: str | None
    ) -> dict[str, object]:
        assert artifact_root == "/tmp/meta-root"
        assert digest_path == "/tmp/meta-root/digest.md"
        return {"degradations": [{"step": "from-meta", "status": "failed"}]}

    monkeypatch.setattr(service, "_read_artifact_meta", _fake_read_artifact_meta)

    degradations = service.get_degradations(
        artifact_root="/tmp/meta-root",
        artifact_digest_md="/tmp/meta-root/digest.md",
        steps=[
            {
                "name": "llm_digest",
                "status": "failed",
                "error": {"reason": "fallback-should-not-win"},
                "result": {"degraded": True},
            }
        ],
    )

    assert degradations == [{"step": "from-meta", "status": "failed"}]


def test_get_degradations_passes_exact_meta_lookup_arguments_and_prefers_meta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    captured_calls: list[dict[str, str | None]] = []
    sentinel_meta = {"degradations": [{"step": "from-meta", "status": "degraded"}]}

    def _fake_read_artifact_meta(
        *, artifact_root: str | None, digest_path: str | None
    ) -> dict[str, object]:
        captured_calls.append({"artifact_root": artifact_root, "digest_path": digest_path})
        return sentinel_meta

    monkeypatch.setattr(service, "_read_artifact_meta", _fake_read_artifact_meta)

    fallback_steps = [
        {
            "name": "llm_outline",
            "status": "failed",
            "error": {"reason": "should-not-win"},
            "result": {"degraded": True},
        }
    ]

    degradations = service.get_degradations(
        artifact_root="/tmp/custom-root",
        artifact_digest_md="/tmp/custom-root/digest.md",
        steps=fallback_steps,
    )

    assert degradations == [{"step": "from-meta", "status": "degraded"}]
    assert captured_calls == [
        {
            "artifact_root": "/tmp/custom-root",
            "digest_path": "/tmp/custom-root/digest.md",
        }
    ]


def test_get_degradations_fallback_skips_non_collectable_steps_without_breaking_iteration() -> None:
    service = _service()

    degradations = service.get_degradations(
        artifact_root=None,
        artifact_digest_md=None,
        steps=[
            {
                "name": "fetch_metadata",
                "status": "succeeded",
                "error": None,
                "result": {"degraded": False},
            },
            {
                "name": "llm_digest",
                "status": "failed",
                "error": {"reason": "provider_unavailable"},
                "result": {"degraded": True},
            },
        ],
    )

    assert degradations == [
        {
            "step": "llm_digest",
            "status": "failed",
            "reason": "provider_unavailable",
        }
    ]


def test_get_degradations_fallback_copies_retry_meta_from_step_result_when_error_omits_it() -> None:
    service = _service()
    retry_meta = {"attempts": 2, "history": ["transient", "fatal"]}

    degradations = service.get_degradations(
        artifact_root=None,
        artifact_digest_md=None,
        steps=[
            {
                "name": "llm_outline",
                "status": "failed",
                "error": {"reason": "provider_unavailable"},
                "result": {
                    "degraded": True,
                    "retry_meta": retry_meta,
                    "cache_meta": {"source": "cache"},
                },
            }
        ],
    )

    assert degradations == [
        {
            "step": "llm_outline",
            "status": "failed",
            "reason": "provider_unavailable",
            "retry_meta": retry_meta,
            "cache_meta": {"source": "cache"},
        }
    ]


def test_get_degradations_collects_skipped_steps_even_without_degraded_result() -> None:
    service = _service()

    degradations = service.get_degradations(
        artifact_root=None,
        artifact_digest_md=None,
        steps=[
            {
                "name": "collect_comments",
                "status": "skipped",
                "error": {"reason": "mode_matrix_skip"},
                "result": {"degraded": False},
            }
        ],
    )

    assert degradations == [
        {
            "step": "collect_comments",
            "status": "skipped",
            "reason": "mode_matrix_skip",
        }
    ]


def test_get_degradations_fallback_copies_error_fields_from_error_dict() -> None:
    service = _service()
    retry_meta = {"attempts": 3}

    degradations = service.get_degradations(
        artifact_root=None,
        artifact_digest_md=None,
        steps=[
            {
                "name": "llm_digest",
                "status": "failed",
                "error": {
                    "reason": "provider_unavailable",
                    "error": "upstream_timeout",
                    "error_kind": "transient",
                    "retry_meta": retry_meta,
                },
                "result": {"degraded": True},
            }
        ],
    )

    assert degradations == [
        {
            "step": "llm_digest",
            "status": "failed",
            "reason": "provider_unavailable",
            "error": "upstream_timeout",
            "error_kind": "transient",
            "retry_meta": retry_meta,
        }
    ]


def test_get_degradations_fallback_does_not_emit_error_key_when_error_is_none() -> None:
    service = _service()

    degradations = service.get_degradations(
        artifact_root=None,
        artifact_digest_md=None,
        steps=[
            {
                "name": "llm_outline",
                "status": "failed",
                "error": None,
                "result": {"degraded": True},
            }
        ],
    )

    assert degradations == [
        {
            "step": "llm_outline",
            "status": "failed",
        }
    ]


def test_artifacts_from_steps_reads_output_files_path_exactly() -> None:
    service = _service()
    output_index = {
        "digest": "/sentinel/output/digest.md",
        "meta": "/sentinel/output/meta.json",
    }
    state_updates_index = {"digest": "/sentinel/state/digest.md"}

    index = service._artifacts_from_steps(
        [
            {
                "name": "write_artifacts",
                "result": {
                    "output": {"files": output_index},
                    "state_updates": {"artifacts": state_updates_index},
                },
            }
        ]
    )

    assert index == output_index


def test_artifacts_from_steps_reads_state_updates_artifacts_when_output_files_missing() -> None:
    service = _service()
    state_updates_index = {
        "digest": "/sentinel/state/digest.md",
        "meta": "/sentinel/state/meta.json",
    }

    index = service._artifacts_from_steps(
        [
            {
                "name": "write_artifacts",
                "result": {"state_updates": {"artifacts": state_updates_index}},
            }
        ]
    )

    assert index == state_updates_index


def test_get_notification_retry_handles_missing_row_and_empty_attempt_count() -> None:
    repo = _JobsRepoStub()
    service = _service()
    service.repo = repo  # type: ignore[attr-defined]

    class _Mappings:
        def __init__(self, row: dict[str, Any] | None) -> None:
            self._row = row

        def first(self) -> dict[str, Any] | None:
            return self._row

    class _ExecuteResult:
        def __init__(self, row: dict[str, Any] | None) -> None:
            self._row = row

        def mappings(self) -> _Mappings:
            return _Mappings(self._row)

    repo.db = SimpleNamespace(
        execute=lambda *_args, **_kwargs: _ExecuteResult(None), rollback=lambda: None
    )
    assert service.get_notification_retry(uuid.UUID(int=20)) is None

    repo.db = SimpleNamespace(
        execute=lambda *_args, **_kwargs: _ExecuteResult(
            {
                "delivery_id": "d-empty-attempt",
                "status": "retrying",
                "attempt_count": None,
                "next_retry_at": None,
                "last_error_kind": None,
            }
        ),
        rollback=lambda: None,
    )
    assert service.get_notification_retry(uuid.UUID(int=21)) == {
        "delivery_id": "d-empty-attempt",
        "status": "retrying",
        "attempt_count": 0,
        "next_retry_at": None,
        "last_error_kind": None,
    }


def test_get_notification_retry_normalizes_attempt_count_from_string() -> None:
    repo = _JobsRepoStub()
    service = _service()
    service.repo = repo  # type: ignore[attr-defined]

    class _Mappings:
        def __init__(self, row: dict[str, Any]) -> None:
            self._row = row

        def first(self) -> dict[str, Any]:
            return self._row

    class _ExecuteResult:
        def __init__(self, row: dict[str, Any]) -> None:
            self._row = row

        def mappings(self) -> _Mappings:
            return _Mappings(self._row)

    repo.db = SimpleNamespace(
        execute=lambda *_args, **_kwargs: _ExecuteResult(
            {
                "delivery_id": "d-string-attempt",
                "status": "retrying",
                "attempt_count": "7",
                "next_retry_at": "2026-03-02T00:00:00+00:00",
                "last_error_kind": "timeout",
            }
        ),
        rollback=lambda: None,
    )

    payload = service.get_notification_retry(uuid.UUID(int=22))
    assert payload is not None
    assert payload["attempt_count"] == 7
    assert isinstance(payload["attempt_count"], int)


def test_get_artifact_payload_supports_video_url_and_job_id_precedence(tmp_path) -> None:
    repo = _JobsRepoStub()
    service = _service()
    service.repo = repo  # type: ignore[attr-defined]

    job_root = tmp_path / "job"
    job_root.mkdir()
    job_digest = job_root / "digest.md"
    job_digest.write_text("# job digest", encoding="utf-8")

    video_root = tmp_path / "video"
    video_root.mkdir()
    video_digest = video_root / "digest.md"
    video_digest.write_text("# video digest", encoding="utf-8")

    repo.digest_path = str(job_digest)
    repo.digest_by_url_path = str(video_digest)

    both_payload = service.get_artifact_payload(
        job_id=uuid.UUID(int=30),
        video_url="https://www.youtube.com/watch?v=job-priority",
    )
    assert both_payload is not None
    assert both_payload["markdown"] == "# job digest"
    assert repo.last_digest_job_id == uuid.UUID(int=30)

    video_only_payload = service.get_artifact_payload(
        job_id=None,
        video_url="https://www.youtube.com/watch?v=video-lookup",
    )
    assert video_only_payload is not None
    assert video_only_payload["markdown"] == "# video digest"
    assert repo.last_digest_video_url == "https://www.youtube.com/watch?v=video-lookup"
    assert (
        service.get_artifact_digest_md(
            job_id=None,
            video_url="https://www.youtube.com/watch?v=video-lookup",
        )
        == "# video digest"
    )


def test_get_artifact_payload_reads_digest_with_explicit_utf8_encoding(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _JobsRepoStub()
    service = _service()
    service.repo = repo  # type: ignore[attr-defined]

    digest_path = tmp_path / "digest.md"
    digest_path.write_text("# digest", encoding="utf-8")
    repo.digest_path = str(digest_path)

    original_read_text = Path.read_text
    read_encodings: list[Any] = []

    def _spy_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
        if self == digest_path:
            read_encodings.append(kwargs.get("encoding"))
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _spy_read_text)

    payload = service.get_artifact_payload(job_id=uuid.UUID(int=32), video_url=None)
    assert payload is not None
    assert payload["markdown"] == "# digest"
    assert read_encodings == ["utf-8"]


def test_get_artifact_payload_returns_none_when_digest_read_fails(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _JobsRepoStub()
    service = _service()
    service.repo = repo  # type: ignore[attr-defined]

    digest_path = tmp_path / "digest.md"
    digest_path.write_text("# digest", encoding="utf-8")
    repo.digest_path = str(digest_path)

    original_read_text = Path.read_text

    def _raise_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
        if self == digest_path:
            raise OSError("cannot read")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _raise_read_text)

    assert service.get_artifact_payload(job_id=uuid.UUID(int=31), video_url=None) is None


def test_get_artifact_payload_returns_none_when_digest_path_is_directory(tmp_path) -> None:
    repo = _JobsRepoStub()
    service = _service()
    service.repo = repo  # type: ignore[attr-defined]

    digest_dir = tmp_path / "digest-directory"
    digest_dir.mkdir()
    repo.digest_path = str(digest_dir)

    assert service.get_artifact_payload(job_id=uuid.UUID(int=33), video_url=None) is None


def test_get_artifact_digest_md_returns_none_for_non_string_markdown() -> None:
    service = _service()

    def _payload(*, job_id: uuid.UUID | None, video_url: str | None) -> dict[str, Any]:
        del job_id, video_url
        return {"markdown": 123}

    service.get_artifact_payload = _payload  # type: ignore[method-assign]
    assert service.get_artifact_digest_md(job_id=uuid.UUID(int=34), video_url=None) is None


def test_artifact_and_notification_helpers_cover_error_fallback_paths(tmp_path) -> None:
    repo = _JobsRepoStub()
    service = _service()
    service.repo = repo  # type: ignore[attr-defined]

    class _BrokenDB:
        def execute(self, *_args: Any, **_kwargs: Any):
            raise jobs_module.DBAPIError("SELECT 1", {}, Exception("boom"))  # type: ignore[arg-type]

        def rollback(self) -> None:
            self.rolled_back = True

    repo.db = _BrokenDB()
    assert service.get_notification_retry(uuid.UUID(int=6)) is None
    assert getattr(repo.db, "rolled_back", False) is True

    assert service.get_artifact_payload(job_id=None, video_url=None) is None

    missing_digest = tmp_path / "missing" / "digest.md"
    repo.digest_path = str(missing_digest)
    assert service.get_artifact_payload(job_id=uuid.UUID(int=7), video_url=None) is None

    fallback_steps = [
        {
            "name": "llm_outline",
            "status": "failed",
            "error": {"reason": "provider_unavailable", "error_kind": "transient"},
            "result": {"degraded": True, "cache_meta": {"source": "cache"}},
        }
    ]
    degradations = service.get_degradations(
        artifact_root=None,
        artifact_digest_md=None,
        steps=fallback_steps,
    )
    assert degradations == [
        {
            "step": "llm_outline",
            "status": "failed",
            "reason": "provider_unavailable",
            "error_kind": "transient",
            "cache_meta": {"source": "cache"},
        }
    ]


def test_get_degradations_collects_failed_without_degraded_flag_and_keeps_error_retry_meta() -> (
    None
):
    service = _service()

    degradations = service.get_degradations(
        artifact_root=None,
        artifact_digest_md=None,
        steps=[
            {
                "name": "llm_digest",
                "status": "failed",
                "error": {"reason": "boom", "retry_meta": {"attempt": 2}},
                "result": {},
            }
        ],
    )

    assert degradations == [
        {
            "step": "llm_digest",
            "status": "failed",
            "reason": "boom",
            "retry_meta": {"attempt": 2},
        }
    ]


def test_get_artifacts_index_scans_comments_file_and_ignores_directory_digest_path(
    tmp_path,
) -> None:
    service = _service()
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    comments_path = artifact_root / "comments.json"
    comments_path.write_text("[]", encoding="utf-8")
    digest_dir = tmp_path / "digest-dir"
    digest_dir.mkdir(parents=True, exist_ok=True)

    index = service.get_artifacts_index(
        artifact_root=str(artifact_root),
        artifact_digest_md=str(digest_dir),
        steps=[],
    )

    assert index["comments"] == str(comments_path.resolve())
    assert "digest" not in index


def test_normalize_thinking_payload_keeps_explicit_positive_thought_count() -> None:
    service = _service()

    normalized = service._normalize_thinking_payload(
        {},
        {
            "thought_count": 5,
            "thought_signatures": ["sig-a", "sig-b"],
        },
    )

    assert normalized["thought_count"] == 5
    assert normalized["thought_signatures"] == ["sig-a", "sig-b"]


def test_get_artifact_asset_passes_job_id_and_handles_missing_row_attributes() -> None:
    service = _service()
    expected_job_id = uuid.uuid4()
    seen: list[uuid.UUID] = []

    def _strict_get_job(job_id: uuid.UUID) -> object:
        seen.append(job_id)
        return SimpleNamespace()

    service.get_job = _strict_get_job  # type: ignore[method-assign]

    assert service.get_artifact_asset(job_id=expected_job_id, path="meta") is None
    assert seen == [expected_job_id]


def test_read_artifact_meta_reads_lowercase_meta_from_digest_parent(tmp_path) -> None:
    service = _service()
    digest_dir = tmp_path / "digest-root"
    digest_dir.mkdir(parents=True, exist_ok=True)
    digest_path = digest_dir / "digest.md"
    digest_path.write_text("# digest", encoding="utf-8")
    meta_path = digest_dir / "meta.json"
    meta_path.write_text(json.dumps({"source": "digest-parent"}), encoding="utf-8")

    assert service._read_artifact_meta(artifact_root=None, digest_path=str(digest_path)) == {
        "source": "digest-parent"
    }


def test_artifacts_from_steps_skips_latest_invalid_write_step_and_uses_previous_valid_one() -> None:
    service = _service()
    expected_index = {"digest": "/tmp/expected-digest.md"}

    index = service._artifacts_from_steps(
        [
            {"name": "write_artifacts", "result": {"output": {"files": expected_index}}},
            {"name": "write_artifacts", "result": "not-a-dict"},
        ]
    )

    assert index == expected_index


def test_artifacts_from_steps_filters_non_string_or_empty_entries() -> None:
    service = _service()

    index = service._artifacts_from_steps(
        [
            {
                "name": "write_artifacts",
                "result": {
                    "output": {
                        "files": {
                            "digest": "/tmp/digest.md",
                            "meta": "",
                            "outline": None,
                            1: "/tmp/bad-key.md",
                            "comments": 2,
                        }
                    }
                },
            }
        ]
    )

    assert index == {"digest": "/tmp/digest.md"}


def test_read_artifact_meta_tries_digest_parent_when_artifact_root_meta_missing(tmp_path) -> None:
    service = _service()
    artifact_root = tmp_path / "artifact-root"
    artifact_root.mkdir(parents=True, exist_ok=True)
    digest_root = tmp_path / "digest-root"
    digest_root.mkdir(parents=True, exist_ok=True)
    digest_path = digest_root / "digest.md"
    digest_path.write_text("# digest", encoding="utf-8")
    digest_meta = digest_root / "meta.json"
    digest_meta.write_text(json.dumps({"from": "digest"}), encoding="utf-8")

    payload = service._read_artifact_meta(
        artifact_root=str(artifact_root),
        digest_path=str(digest_path),
    )

    assert payload == {"from": "digest"}


def test_read_artifact_meta_uses_lowercase_meta_filename_for_digest_parent(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    digest_root = tmp_path / "digest-root-lowercase"
    digest_root.mkdir(parents=True, exist_ok=True)
    digest_path = digest_root / "digest.md"
    digest_path.write_text("# digest", encoding="utf-8")
    (digest_root / "meta.json").write_text(json.dumps({"ok": True}), encoding="utf-8")

    seen_names: list[str] = []
    original_read_text = Path.read_text

    def _spy_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
        if self.parent == digest_root:
            seen_names.append(self.name)
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _spy_read_text)

    payload = service._read_artifact_meta(artifact_root=None, digest_path=str(digest_path))

    assert payload == {"ok": True}
    assert "meta.json" in seen_names
    assert "META.JSON" not in seen_names


def test_artifacts_from_steps_ignores_latest_non_write_step_and_returns_earlier_write_index() -> (
    None
):
    service = _service()
    expected = {"digest": "/tmp/from-earlier-step.md"}

    index = service._artifacts_from_steps(
        [
            {"name": "write_artifacts", "result": {"output": {"files": expected}}},
            {"name": "llm_digest", "result": {"output": {"files": {"digest": "/tmp/ignored.md"}}}},
        ]
    )

    assert index == expected


def test_artifacts_from_steps_skips_latest_write_step_with_non_dict_files_and_uses_earlier_one() -> (
    None
):
    service = _service()
    expected = {"digest": "/tmp/from-earlier-valid.md"}

    index = service._artifacts_from_steps(
        [
            {"name": "write_artifacts", "result": {"output": {"files": expected}}},
            {"name": "write_artifacts", "result": {"output": {"files": "bad-files"}}},
        ]
    )

    assert index == expected


def test_compare_with_previous_returns_none_when_job_missing() -> None:
    service = _service()

    class _Repo:
        def get(self, _job_id: uuid.UUID):
            return None

    service.repo = _Repo()

    assert service.compare_with_previous(job_id=uuid.uuid4()) is None


def test_compare_with_previous_without_previous_digest_returns_empty_diff(tmp_path: Path) -> None:
    current_digest = tmp_path / "current.md"
    current_digest.write_text("current digest", encoding="utf-8")
    current_job_id = uuid.uuid4()

    service = _service()

    class _Repo:
        def get(self, _job_id: uuid.UUID):
            return SimpleNamespace(id=current_job_id, artifact_digest_md=str(current_digest))

        def get_previous_successful_job(self, *, job_id: uuid.UUID):
            assert job_id == current_job_id
            return

    service.repo = _Repo()

    payload = service.compare_with_previous(job_id=current_job_id)

    assert payload == {
        "job_id": str(current_job_id),
        "previous_job_id": None,
        "has_previous": False,
        "current_digest": "current digest",
        "previous_digest": None,
        "diff_markdown": "",
        "stats": {"added_lines": 0, "removed_lines": 0, "changed": False},
    }


def test_compare_with_previous_builds_diff_stats(tmp_path: Path) -> None:
    previous_digest = tmp_path / "previous.md"
    current_digest = tmp_path / "current.md"
    previous_digest.write_text("line-a\nline-b\n", encoding="utf-8")
    current_digest.write_text("line-a\nline-c\nline-d\n", encoding="utf-8")
    current_job_id = uuid.uuid4()
    previous_job_id = uuid.uuid4()

    service = _service()

    class _Repo:
        def get(self, _job_id: uuid.UUID):
            return SimpleNamespace(id=current_job_id, artifact_digest_md=str(current_digest))

        def get_previous_successful_job(self, *, job_id: uuid.UUID):
            assert job_id == current_job_id
            return SimpleNamespace(id=previous_job_id, artifact_digest_md=str(previous_digest))

    service.repo = _Repo()

    payload = service.compare_with_previous(job_id=current_job_id)

    assert payload["has_previous"] is True
    assert payload["previous_job_id"] == str(previous_job_id)
    assert payload["stats"]["added_lines"] == 2
    assert payload["stats"]["removed_lines"] == 1
    assert payload["stats"]["changed"] is True
    assert f"job:{previous_job_id}" in payload["diff_markdown"]
    assert f"job:{current_job_id}" in payload["diff_markdown"]


def test_get_knowledge_cards_handles_missing_root_invalid_payload_and_filters_dicts(
    tmp_path: Path,
) -> None:
    service = _service()
    job_id = uuid.uuid4()
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)

    class _Repo:
        def get(self, requested_job_id: uuid.UUID):
            assert requested_job_id == job_id
            return SimpleNamespace(
                id=job_id,
                artifact_root=str(artifact_root),
                artifact_digest_md=None,
            )

    service.repo = _Repo()

    assert service.get_knowledge_cards(job_id=job_id) == []

    cards_path = artifact_root / "knowledge_cards.json"
    cards_path.write_text('{"not":"a list"}', encoding="utf-8")
    assert service.get_knowledge_cards(job_id=job_id) == []

    cards_path.write_text(
        json.dumps([{"id": "card-1"}, "skip-me", {"id": "card-2"}], ensure_ascii=False),
        encoding="utf-8",
    )
    assert service.get_knowledge_cards(job_id=job_id) == [{"id": "card-1"}, {"id": "card-2"}]
