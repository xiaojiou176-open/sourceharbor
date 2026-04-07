from __future__ import annotations

import base64
import sys
import time
import types
from pathlib import Path

import pytest

from apps.api.app.services.computer_use import ComputerUseSafetyConfig, ComputerUseService
from apps.api.app.services.subscriptions import SubscriptionsService
from apps.api.app.services.ui_audit import UiAuditService


class _FakeSubscriptionsRepo:
    def __init__(self) -> None:
        self.kwargs = None

    def upsert(self, **kwargs):
        self.kwargs = kwargs
        return types.SimpleNamespace(id="sub-1"), True


def test_subscriptions_blocks_localhost_source_value() -> None:
    repo = _FakeSubscriptionsRepo()
    service = SubscriptionsService(db=None, repo=repo)

    with pytest.raises(ValueError, match="source_value points to a blocked internal host"):
        service.upsert_subscription(
            platform="youtube",
            source_type="url",
            source_value="http://localhost/feed.xml",
            adapter_type="rsshub_route",
            source_url=None,
            rsshub_route=None,
            category="misc",
            tags=[],
            priority=50,
            enabled=True,
        )


def test_subscriptions_blocks_private_source_url() -> None:
    repo = _FakeSubscriptionsRepo()
    service = SubscriptionsService(db=None, repo=repo)

    with pytest.raises(ValueError, match="source_url points to a blocked internal address"):
        service.upsert_subscription(
            platform="youtube",
            source_type="youtube_channel_id",
            source_value="UC-demo",
            adapter_type="rss_generic",
            source_url="http://10.0.0.8/feed.xml",
            rsshub_route=None,
            category="misc",
            tags=[],
            priority=50,
            enabled=True,
        )


def test_subscriptions_allows_public_source_url() -> None:
    repo = _FakeSubscriptionsRepo()
    service = SubscriptionsService(db=None, repo=repo)

    service.upsert_subscription(
        platform="youtube",
        source_type="youtube_channel_id",
        source_value="UC-demo",
        adapter_type="rss_generic",
        source_url="https://example.com/feed.xml",
        rsshub_route=None,
        category="misc",
        tags=[],
        priority=50,
        enabled=True,
    )

    assert repo.kwargs is not None
    assert repo.kwargs["source_url"] == "https://example.com/feed.xml"


def test_ui_audit_blocks_artifact_root_outside_base(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base_root = tmp_path / "base"
    outside_root = tmp_path / "outside"
    base_root.mkdir(parents=True, exist_ok=True)
    outside_root.mkdir(parents=True, exist_ok=True)
    (outside_root / "playwright-log.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("UI_AUDIT_ARTIFACT_BASE_ROOT", str(base_root))

    service = UiAuditService()
    payload = service.run(artifact_root="outside")

    assert payload["status"] == "not_found"
    assert payload["artifact_root"] is None


def test_ui_audit_blocks_artifact_root_equal_to_base(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base_root = tmp_path / "base"
    base_root.mkdir(parents=True, exist_ok=True)
    (base_root / "playwright-log.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("UI_AUDIT_ARTIFACT_BASE_ROOT", str(base_root))

    service = UiAuditService()
    payload = service.run(artifact_root="")

    assert payload["status"] == "not_found"
    assert payload["artifact_root"] is None


def test_ui_audit_text_snippet_uses_stream_read(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base_root = tmp_path / "ui-audit"
    base_root.mkdir(parents=True, exist_ok=True)
    log_path = base_root / "large.log"
    log_path.write_text("A" * 50_000, encoding="utf-8")

    original_read_text = Path.read_text

    def _guard_read_text(self: Path, *args, **kwargs):
        if self == log_path:
            raise AssertionError("read_text should not be used for text snippet extraction")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _guard_read_text)

    service = UiAuditService()
    snippets = service._select_gemini_text_snippets(  # noqa: SLF001
        [
            {
                "key": "large.log",
                "path": str(log_path),
                "mime_type": "text/plain",
                "size_bytes": log_path.stat().st_size,
                "category": "artifact",
            }
        ]
    )

    assert len(snippets) == 1
    assert len(snippets[0]["snippet"]) == 2_000


def test_computer_use_timeout_retries_then_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setenv("COMPUTER_USE_MODEL_TIMEOUT_SECONDS", "1")
    monkeypatch.setenv("COMPUTER_USE_MODEL_MAX_RETRIES", "1")

    class _FakeModels:
        def generate_content(self, **kwargs):
            del kwargs
            calls["count"] += 1
            time.sleep(1.2)
            return types.SimpleNamespace(text='{"ok": true}')

    class _FakeClient:
        def __init__(self, api_key: str):
            self.api_key = api_key
            self.models = _FakeModels()

    class _FakePart:
        @staticmethod
        def from_bytes(*, data, mime_type):
            return {"size": len(data), "mime_type": mime_type}

    class _FakeTypes:
        Part = _FakePart

        class Tool:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class ComputerUse:
            pass

        class GenerateContentConfig:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class ThinkingConfig:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

    fake_genai_module = types.ModuleType("google.genai")
    fake_genai_module.Client = _FakeClient
    fake_genai_module.types = _FakeTypes
    fake_google_module = types.ModuleType("google")
    fake_google_module.genai = fake_genai_module
    monkeypatch.setitem(sys.modules, "google", fake_google_module)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai_module)

    service = ComputerUseService()
    screenshot_b64 = base64.b64encode(b"fake-image").decode("ascii")
    with pytest.raises(ValueError, match="computer_use_provider_error:computer_use model timeout"):
        service.run(
            instruction="open settings",
            screenshot_base64=screenshot_b64,
            safety=ComputerUseSafetyConfig(),
        )
    assert calls["count"] == 2


def test_ui_audit_gemini_timeout_retries_then_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = {"count": 0}
    base_root = tmp_path / "ui-base"
    artifact_root = base_root / "run-1"
    artifact_root.mkdir(parents=True, exist_ok=True)
    (artifact_root / "playwright.log").write_text("sample log", encoding="utf-8")

    monkeypatch.setenv("UI_AUDIT_ARTIFACT_BASE_ROOT", str(base_root))
    monkeypatch.setenv("UI_AUDIT_GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setenv("UI_AUDIT_MODEL_TIMEOUT_SECONDS", "1")
    monkeypatch.setenv("UI_AUDIT_MODEL_MAX_RETRIES", "1")

    class _FakeModels:
        def generate_content(self, **kwargs):
            del kwargs
            calls["count"] += 1
            time.sleep(1.2)
            return types.SimpleNamespace(text="{}")

    class _FakeClient:
        def __init__(self, api_key: str):
            self.api_key = api_key
            self.models = _FakeModels()

    class _FakePart:
        @staticmethod
        def from_bytes(*, data, mime_type):
            return {"size": len(data), "mime_type": mime_type}

    class _FakeTypes:
        Part = _FakePart

        class GenerateContentConfig:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class ThinkingConfig:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

    fake_genai_module = types.ModuleType("google.genai")
    fake_genai_module.Client = _FakeClient
    fake_genai_module.types = _FakeTypes
    fake_google_module = types.ModuleType("google")
    fake_google_module.genai = fake_genai_module
    monkeypatch.setitem(sys.modules, "google", fake_google_module)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai_module)

    service = UiAuditService()
    payload = service.run(artifact_root="run-1")

    assert payload["status"] == "completed_with_gemini_failure"
    assert payload["gemini_review"]["status"] == "failed"
    assert payload["gemini_review"]["reason_code"] == "provider_error"
    assert calls["count"] == 2
    assert any(
        item.get("rule") == "gemini-ui-review-provider-error" for item in payload["findings"]
    )
