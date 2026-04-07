from __future__ import annotations

import json
import sys
import types
import uuid
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.exc import DBAPIError

from apps.api.app.services import ui_audit as ui_audit_module
from apps.api.app.services.ui_audit import UiAuditService


@pytest.fixture(autouse=True)
def _clear_ui_audit_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UI_AUDIT_RUN_STORE_DIR", str(tmp_path / "ui-audit-runs"))
    with UiAuditService._store_lock:
        UiAuditService._run_store.clear()


def _install_fake_genai(monkeypatch: pytest.MonkeyPatch, response_text: str) -> None:
    class _FakeModels:
        def generate_content(self, **_kwargs: Any) -> Any:
            return types.SimpleNamespace(text=response_text)

    class _FakeClient:
        def __init__(self, api_key: str):
            self.api_key = api_key
            self.models = _FakeModels()

    class _FakePart:
        @staticmethod
        def from_bytes(*, data: bytes, mime_type: str) -> dict[str, Any]:
            return {"size": len(data), "mime_type": mime_type}

    class _FakeTypes:
        Part = _FakePart

        class GenerateContentConfig:
            def __init__(self, **kwargs: Any):
                self.kwargs = kwargs

        class ThinkingConfig:
            def __init__(self, **kwargs: Any):
                self.kwargs = kwargs

    fake_genai_module = types.ModuleType("google.genai")
    fake_genai_module.Client = _FakeClient
    fake_genai_module.types = _FakeTypes
    fake_google_module = types.ModuleType("google")
    fake_google_module.genai = fake_genai_module
    monkeypatch.setitem(sys.modules, "google", fake_google_module)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai_module)


def test_ui_audit_accessors_cover_missing_and_filtering_branches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    service = UiAuditService()
    assert service.get("missing") is None
    assert service.list_findings(run_id="missing") is None
    assert service.list_artifacts(run_id="missing") is None
    assert service.get_artifact(run_id="missing", key="artifact.json") is None

    service._save_run(  # noqa: SLF001
        {
            "run_id": "run-1",
            "status": "completed",
            "findings": [{"id": "f-1", "severity": "HIGH"}, "bad-shape"],
            "artifacts": "bad-shape",
        }
    )
    payload = service.get("run-1")
    assert payload is not None
    assert payload["summary"] == {"artifact_count": 0, "finding_count": 0, "severity_counts": {}}
    assert service.list_findings(run_id="run-1", severity=" high ") == [
        {"id": "f-1", "severity": "HIGH"}
    ]
    assert service.list_artifacts(run_id="run-1") == []

    service._save_run(  # noqa: SLF001
        {"run_id": "run-2", "artifacts": [{"key": "artifact.json", "path": 1}]}
    )
    assert service.get_artifact(run_id="run-2", key="missing-key") is None
    assert service.get_artifact(run_id="run-2", key="artifact.json") is None

    missing_file = tmp_path / "missing.json"
    service._save_run(  # noqa: SLF001
        {"run_id": "run-3", "artifacts": [{"key": "artifact.json", "path": str(missing_file)}]}
    )
    assert service.get_artifact(run_id="run-3", key="artifact.json") is None

    artifact_file = tmp_path / "artifact.json"
    artifact_file.write_text("{}", encoding="utf-8")
    service._save_run(  # noqa: SLF001
        {"run_id": "run-4", "artifacts": [{"key": "artifact.json", "path": str(artifact_file)}]}
    )
    original_read_bytes = Path.read_bytes

    def _raise_read_bytes(self: Path) -> bytes:
        if self == artifact_file:
            raise OSError("disk error")
        return original_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", _raise_read_bytes)
    assert service.get_artifact(run_id="run-4", key="artifact.json", include_base64=True) is None


def test_ui_audit_run_store_dir_uses_repo_root_for_relative_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "UI_AUDIT_RUN_STORE_DIR", ".runtime-cache/evidence/tests/custom-ui-audit-runs"
    )
    monkeypatch.setattr(
        ui_audit_module.Path,
        "cwd",
        classmethod(lambda _cls: (_ for _ in ()).throw(FileNotFoundError("cwd missing"))),
    )

    service = UiAuditService()

    assert service._run_store_dir() == (
        ui_audit_module._REPO_ROOT / ".runtime-cache/evidence/tests/custom-ui-audit-runs"
    )


def test_ui_audit_run_store_writes_runtime_metadata_for_repo_runtime_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "UI_AUDIT_RUN_STORE_DIR", ".runtime-cache/evidence/tests/custom-ui-audit-runs"
    )
    service = UiAuditService()

    payload = {
        "run_id": "run-with-metadata",
        "status": "completed",
        "created_at": "2026-04-05T16:20:26Z",
        "summary": {"artifact_count": 0, "finding_count": 0, "severity_counts": {}},
        "findings": [],
        "artifacts": [],
    }
    service._save_run(payload)  # noqa: SLF001

    file_path = service._run_store_path(payload["run_id"])  # noqa: SLF001
    meta_path = file_path.with_name(f"{file_path.name}.meta.json")
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    index_path = ui_audit_module._EVIDENCE_INDEX_ROOT / f"{payload['run_id']}.json"
    index_payload = json.loads(index_path.read_text(encoding="utf-8"))

    assert meta_path.is_file()
    assert index_path.is_file()
    assert metadata["artifact_path"] == file_path.relative_to(ui_audit_module._REPO_ROOT).as_posix()
    assert metadata["source_entrypoint"] == "apps.api.app.services.ui_audit.UiAuditService"
    assert metadata["source_run_id"] == payload["run_id"]
    assert metadata["verification_scope"] == "ui-audit-run-store"
    assert metadata["created_at"] == payload["created_at"]
    assert file_path.relative_to(ui_audit_module._REPO_ROOT).as_posix() in index_payload["evidence"]


def test_ui_audit_autofix_covers_non_dict_findings_and_no_findings_branch() -> None:
    service = UiAuditService()
    assert service.autofix(run_id="missing") is None

    service._save_run(  # noqa: SLF001
        {
            "run_id": "run-with-findings",
            "findings": ["bad-shape", {"severity": "critical"}],
            "gemini_suggested_actions": ["", "Use stricter assertions"],
        }
    )
    with_findings = service.autofix(run_id="run-with-findings", mode="apply")
    assert with_findings is not None
    assert with_findings["mode"] == "dry-run"
    assert with_findings["summary"]["high_or_worse_count"] == 1
    assert with_findings["guardrails"]["requested_mode"] == "apply"
    assert with_findings["guardrails"]["effective_mode"] == "dry-run"
    assert "Use stricter assertions" in with_findings["suggested_actions"]
    assert any(
        "Fix high-severity UI issues first" in item for item in with_findings["suggested_actions"]
    )

    service._save_run({"run_id": "run-empty", "findings": []})  # noqa: SLF001
    empty = service.autofix(run_id="run-empty")
    assert empty is not None
    assert "No findings detected; no code changes recommended." in empty["suggested_actions"]


def test_ui_audit_run_persists_to_disk_and_reload_reads_persisted_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UI_AUDIT_RUN_STORE_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("UI_AUDIT_ARTIFACT_BASE_ROOT", str(tmp_path))
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    (artifact_root / "playwright-axe-report.json").write_text(
        '{"violations":[{"id":"color-contrast","impact":"serious","help":"Color contrast","description":"Insufficient contrast"}]}',
        encoding="utf-8",
    )

    service = UiAuditService()
    run = service.run(artifact_root="artifacts")
    run_id = run["run_id"]

    with UiAuditService._store_lock:
        UiAuditService._run_store.clear()

    reloaded = service.get(run_id)
    assert reloaded is not None
    assert reloaded["run_id"] == run_id
    assert reloaded["summary"]["finding_count"] == 1
    assert reloaded["status"] == "completed_with_gemini_skipped"


def test_ui_audit_disk_payload_must_match_run_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UI_AUDIT_RUN_STORE_DIR", str(tmp_path / "runs"))
    service = UiAuditService()
    run_id = str(uuid.uuid4())
    file_path = service._run_store_path(run_id)  # noqa: SLF001
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        '{"run_id":"different-run-id","status":"completed"}',
        encoding="utf-8",
    )

    assert service.get(run_id) is None


def test_ui_audit_gemini_review_short_circuits_and_parse_fallbacks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    service = UiAuditService()
    monkeypatch.setenv("UI_AUDIT_GEMINI_ENABLED", "true")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    missing_key = service._run_gemini_review([])  # noqa: SLF001
    assert missing_key["meta"]["status"] == "skipped"
    assert missing_key["meta"]["reason_code"] == "missing_gemini_api_key"
    assert missing_key["findings"] == []

    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setitem(sys.modules, "google", types.ModuleType("google"))
    monkeypatch.delitem(sys.modules, "google.genai", raising=False)
    sdk_missing = service._run_gemini_review([])  # noqa: SLF001
    assert sdk_missing["meta"]["status"] == "failed"
    assert sdk_missing["meta"]["reason_code"] == "sdk_unavailable"
    assert sdk_missing["findings"][0]["rule"] == "gemini-ui-review-sdk-unavailable"
    assert sdk_missing["findings"][0]["severity"] == "high"

    _install_fake_genai(monkeypatch, "{}")
    no_artifacts = service._run_gemini_review([])  # noqa: SLF001
    assert no_artifacts["meta"]["status"] == "skipped"
    assert no_artifacts["meta"]["reason_code"] == "no_supported_artifacts"

    text_file = tmp_path / "trace.log"
    text_file.write_text("line 1", encoding="utf-8")
    review = service._run_gemini_review(  # noqa: SLF001
        [
            {
                "key": "missing.png",
                "path": str(tmp_path / "missing.png"),
                "mime_type": "image/png",
                "size_bytes": 100,
                "category": "artifact",
            },
            {
                "key": "trace.log",
                "path": str(text_file),
                "mime_type": "text/plain",
                "size_bytes": 6,
                "category": "artifact",
            },
        ]
    )
    assert review is not None
    assert review["findings"] == []
    assert review["meta"]["status"] == "passed"
    assert review["meta"]["reason_code"] == "ok"

    _install_fake_genai(monkeypatch, "   ")
    empty_response = service._run_gemini_review(  # noqa: SLF001
        [
            {
                "key": "trace.log",
                "path": str(text_file),
                "mime_type": "text/plain",
                "size_bytes": 6,
                "category": "artifact",
            }
        ]
    )
    assert empty_response["meta"]["status"] == "failed"
    assert empty_response["meta"]["reason_code"] == "empty_response"
    assert empty_response["findings"][0]["rule"] == "gemini-ui-review-empty-response"
    assert empty_response["findings"][0]["severity"] == "high"

    _install_fake_genai(monkeypatch, "not-json")
    invalid_json = service._run_gemini_review(  # noqa: SLF001
        [
            {
                "key": "trace.log",
                "path": str(text_file),
                "mime_type": "text/plain",
                "size_bytes": 6,
                "category": "artifact",
            }
        ]
    )
    assert invalid_json is not None
    assert invalid_json["meta"]["status"] == "failed"
    assert invalid_json["meta"]["reason_code"] == "invalid_json"
    assert invalid_json["findings"][0]["rule"] == "gemini-ui-review-invalid-json"
    assert invalid_json["findings"][0]["severity"] == "high"

    _install_fake_genai(monkeypatch, "{}")

    def _raise_provider_error(**_kwargs: Any) -> Any:
        raise RuntimeError("HTTP 429 provider throttled")

    monkeypatch.setattr(service, "_generate_with_timeout_and_retry", _raise_provider_error)  # noqa: SLF001
    provider_error = service._run_gemini_review(  # noqa: SLF001
        [
            {
                "key": "trace.log",
                "path": str(text_file),
                "mime_type": "text/plain",
                "size_bytes": 6,
                "category": "artifact",
            }
        ]
    )
    assert provider_error["meta"]["status"] == "failed"
    assert provider_error["meta"]["reason_code"] == "provider_error"
    assert provider_error["meta"]["provider_status"] == 429
    assert provider_error["findings"][0]["severity"] == "high"


def test_ui_audit_gemini_review_ignores_image_read_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("UI_AUDIT_GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    _install_fake_genai(monkeypatch, "{}")

    image_file = tmp_path / "screen.png"
    image_file.write_bytes(b"image-bytes")
    text_file = tmp_path / "trace.log"
    text_file.write_text("line 1", encoding="utf-8")

    original_read_bytes = Path.read_bytes

    def _raise_image_read(self: Path) -> bytes:
        if self == image_file:
            raise OSError("cannot read image")
        return original_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", _raise_image_read)
    service = UiAuditService()
    review = service._run_gemini_review(  # noqa: SLF001
        [
            {
                "key": "screen.png",
                "path": str(image_file),
                "mime_type": "image/png",
                "size_bytes": image_file.stat().st_size,
                "category": "artifact",
            },
            {
                "key": "trace.log",
                "path": str(text_file),
                "mime_type": "text/plain",
                "size_bytes": text_file.stat().st_size,
                "category": "artifact",
            },
        ]
    )
    assert review["overall_assessment"] == ""
    assert review["findings"] == []
    assert review["suggested_actions"] == []
    assert review["meta"]["status"] == "passed"
    assert review["meta"]["reason_code"] == "ok"


def test_generate_with_timeout_and_retry_wraps_non_timeout_exceptions() -> None:
    class _FailingModels:
        def generate_content(self, **_kwargs: Any) -> Any:
            raise ValueError("boom")

    fake_client = types.SimpleNamespace(models=_FailingModels())
    service = UiAuditService()

    with pytest.raises(RuntimeError, match="boom"):
        service._generate_with_timeout_and_retry(  # noqa: SLF001
            client=fake_client,
            model="gemini-test",
            contents=["prompt"],
            config={},
            timeout_seconds=1.0,
            max_retries=0,
        )


def test_resolve_artifact_root_covers_db_paths_and_dbapi_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base_root = tmp_path / "base"
    inside_root = base_root / "inside"
    outside_root = tmp_path / "outside"
    inside_root.mkdir(parents=True, exist_ok=True)
    outside_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UI_AUDIT_ARTIFACT_BASE_ROOT", str(base_root))

    service_no_db = UiAuditService(db=None)
    assert (
        service_no_db._resolve_artifact_root(  # noqa: SLF001
            job_id=uuid.uuid4(),
            artifact_root=None,
        )
        is None
    )

    class _ErrorDb:
        def __init__(self) -> None:
            self.rolled_back = False

        def execute(self, *_args: Any, **_kwargs: Any) -> Any:
            raise DBAPIError("stmt", {}, Exception("db-fail"))

        def rollback(self) -> None:
            self.rolled_back = True

    error_db = _ErrorDb()
    service_error_db = UiAuditService(db=error_db)  # type: ignore[arg-type]
    assert (
        service_error_db._resolve_artifact_root(  # noqa: SLF001
            job_id=uuid.uuid4(),
            artifact_root=None,
        )
        is None
    )
    assert error_db.rolled_back is True

    class _FakeResult:
        def __init__(self, row: dict[str, Any] | None) -> None:
            self._row = row

        def mappings(self) -> _FakeResult:
            return self

        def first(self) -> dict[str, Any] | None:
            return self._row

    class _RowDb:
        def __init__(self, row: dict[str, Any] | None) -> None:
            self._row = row

        def execute(self, *_args: Any, **_kwargs: Any) -> _FakeResult:
            return _FakeResult(self._row)

    service_invalid_root = UiAuditService(db=_RowDb({"artifact_root": 1}))  # type: ignore[arg-type]
    assert (
        service_invalid_root._resolve_artifact_root(  # noqa: SLF001
            job_id=uuid.uuid4(),
            artifact_root=None,
        )
        is None
    )

    service_outside_root = UiAuditService(  # type: ignore[arg-type]
        db=_RowDb({"artifact_root": str(outside_root)})
    )
    assert (
        service_outside_root._resolve_artifact_root(  # noqa: SLF001
            job_id=uuid.uuid4(),
            artifact_root=None,
        )
        is None
    )

    service_inside_root = UiAuditService(db=_RowDb({"artifact_root": str(inside_root)}))  # type: ignore[arg-type]
    resolved = service_inside_root._resolve_artifact_root(  # noqa: SLF001
        job_id=uuid.uuid4(),
        artifact_root=None,
    )
    assert resolved == inside_root.resolve(strict=False)


def test_ui_audit_artifact_collection_handles_limits_and_stat_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    service = UiAuditService()
    root = tmp_path / "artifacts"
    nested = root / "nested"
    root.mkdir(parents=True, exist_ok=True)
    nested.mkdir(parents=True, exist_ok=True)
    first = root / "first.json"
    second = root / "second.json"
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")

    original_stat = Path.stat
    second_key = str(second)
    stat_counts: dict[str, int] = {}

    def _patched_stat(self: Path, *args: Any, **kwargs: Any) -> Any:
        key = str(self)
        stat_counts[key] = stat_counts.get(key, 0) + 1
        if key == second_key and stat_counts[key] >= 2:
            raise OSError("stat failed")
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", _patched_stat)
    collected = service._collect_artifacts(root)  # noqa: SLF001
    assert any(item["key"] == "second.json" and item["size_bytes"] == 0 for item in collected)

    monkeypatch.setattr(ui_audit_module, "_MAX_SCAN_FILES", 1)
    limited = service._collect_artifacts(root)  # noqa: SLF001
    assert len(limited) == 1


def test_ui_audit_selection_and_parsing_helpers_cover_tail_branches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    service = UiAuditService()

    images = service._select_gemini_image_artifacts(  # noqa: SLF001
        [
            {"mime_type": "image/png", "size_bytes": 0},
            {"mime_type": "image/png", "size_bytes": 100, "key": "1"},
            {"mime_type": "image/jpeg", "size_bytes": 100, "key": "2"},
            {"mime_type": "image/webp", "size_bytes": 100, "key": "3"},
            {"mime_type": "image/gif", "size_bytes": 100, "key": "4"},
            {"mime_type": "image/png", "size_bytes": 100, "key": "5"},
        ]
    )
    assert len(images) == 4

    missing_path_snippet = {
        "key": "missing.log",
        "path": str(tmp_path / "missing.log"),
        "mime_type": "text/plain",
        "size_bytes": 1,
    }
    empty_file = tmp_path / "empty.log"
    empty_file.write_text("", encoding="utf-8")
    valid_paths = []
    for index in range(6):
        path = tmp_path / f"text-{index}.log"
        path.write_text(f"line-{index}", encoding="utf-8")
        valid_paths.append(
            {
                "key": f"text-{index}.log",
                "path": str(path),
                "mime_type": "text/plain",
                "size_bytes": path.stat().st_size,
            }
        )
    snippets = service._select_gemini_text_snippets(  # noqa: SLF001
        [
            missing_path_snippet,
            {
                "key": "empty.log",
                "path": str(empty_file),
                "mime_type": "text/plain",
                "size_bytes": 0,
            },
            *valid_paths,
        ]
    )
    assert len(snippets) == 4
    assert service._read_text_prefix(tmp_path / "no-file.log", max_chars=10) is None  # noqa: SLF001

    monkeypatch.setenv("UI_AUDIT_MODEL_TIMEOUT_SECONDS", "not-a-float")
    monkeypatch.setenv("UI_AUDIT_MODEL_MAX_RETRIES", "not-an-int")
    assert (
        service._read_float_env(
            "UI_AUDIT_MODEL_TIMEOUT_SECONDS", default=15.0, min_value=1.0, max_value=120.0
        )
        == 15.0
    )  # noqa: SLF001,E501
    assert (
        service._read_int_env("UI_AUDIT_MODEL_MAX_RETRIES", default=1, min_value=0, max_value=3)
        == 1
    )  # noqa: SLF001,E501

    normalized = service._normalize_gemini_review(  # noqa: SLF001
        {
            "overall_assessment": "ok",
            "findings": [
                "bad-shape",
                {"severity": "SEVERE", "title": "", "message": "needs fix"},
                {"severity": "low", "title": "ignored", "message": ""},
            ],
            "suggested_actions": ["  improve contrast  ", ""],
        }
    )
    assert normalized["overall_assessment"] == "ok"
    assert normalized["suggested_actions"] == ["improve contrast"]
    assert normalized["findings"] == [
        {
            "id": "gemini-finding-2",
            "severity": "medium",
            "title": "Gemini UI review finding",
            "message": "needs fix",
            "rule": None,
            "artifact_key": None,
        }
    ]

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad-json", encoding="utf-8")
    findings = service._collect_findings(  # noqa: SLF001
        [
            {"path": 1, "key": "bad"},
            {"path": str(bad_json), "key": "bad.json", "category": "artifact"},
        ]
    )
    assert findings == []

    assert service._extract_findings_from_json([], artifact_key="x") == []  # noqa: SLF001
    extracted = service._extract_findings_from_json(  # noqa: SLF001
        {
            "violations": ["bad", {"id": "rule-a", "impact": "serious", "help": "contrast"}],
            "findings": ["bad", {"title": "title", "message": "msg", "severity": "low"}],
        },
        artifact_key="artifact.json",
    )
    assert len(extracted) == 2

    assert service._load_json(tmp_path / "missing.json") is None  # noqa: SLF001
    assert service._load_json(bad_json) is None  # noqa: SLF001

    service._save_run({"status": "completed"})  # noqa: SLF001
    assert service.get("missing-run-id") is None
