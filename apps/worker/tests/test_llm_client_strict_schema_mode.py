from __future__ import annotations

import sys
import types
from typing import Any

from worker.config import Settings
from worker.pipeline.steps import llm_client


def test_gemini_schema_retry_disabled_in_strict_mode(monkeypatch: Any) -> None:
    calls: list[dict[str, Any]] = []

    class _FakeModels:
        @staticmethod
        def generate_content(*, model: str, contents: Any, config: Any) -> Any:
            kwargs = dict(getattr(config, "kwargs", {}))
            calls.append(kwargs)
            if "response_json_schema" in kwargs:
                raise RuntimeError("invalid argument: schema failed")
            return types.SimpleNamespace(text='{"ok":true}')

    class _FakeClient:
        def __init__(self, *, api_key: str):
            self.api_key = api_key
            self.models = _FakeModels()
            self.files = object()
            self.caches = object()

    class _FakeThinkingConfig:
        def __init__(self, **kwargs: Any):
            self.kwargs = kwargs

    class _FakeGenerateContentConfig:
        def __init__(self, **kwargs: Any):
            self.kwargs = kwargs

    fake_types = types.SimpleNamespace(
        ThinkingConfig=_FakeThinkingConfig,
        GenerateContentConfig=_FakeGenerateContentConfig,
    )
    fake_genai = types.ModuleType("google.genai")
    fake_genai.Client = _FakeClient  # type: ignore[attr-defined]
    fake_genai.types = fake_types  # type: ignore[attr-defined]

    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    settings = Settings(gemini_api_key="key", gemini_strict_schema_mode=True)
    text, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt",
        llm_input_mode="text",
        response_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
        use_context_cache=False,
        enable_function_calling=False,
    )

    assert text is None
    assert media_input == "text"
    assert len(calls) == 1
    assert "response_json_schema" in calls[0]
    assert meta["error_code"] == "llm_invalid_request"


def test_gemini_schema_retry_enabled_when_strict_mode_off(monkeypatch: Any) -> None:
    calls: list[dict[str, Any]] = []

    class _FakeModels:
        @staticmethod
        def generate_content(*, model: str, contents: Any, config: Any) -> Any:
            kwargs = dict(getattr(config, "kwargs", {}))
            calls.append(kwargs)
            if "response_json_schema" in kwargs:
                raise RuntimeError("invalid argument: schema failed")
            return types.SimpleNamespace(text='{"ok":true}')

    class _FakeClient:
        def __init__(self, *, api_key: str):
            self.api_key = api_key
            self.models = _FakeModels()
            self.files = object()
            self.caches = object()

    class _FakeThinkingConfig:
        def __init__(self, **kwargs: Any):
            self.kwargs = kwargs

    class _FakeGenerateContentConfig:
        def __init__(self, **kwargs: Any):
            self.kwargs = kwargs

    fake_types = types.SimpleNamespace(
        ThinkingConfig=_FakeThinkingConfig,
        GenerateContentConfig=_FakeGenerateContentConfig,
    )
    fake_genai = types.ModuleType("google.genai")
    fake_genai.Client = _FakeClient  # type: ignore[attr-defined]
    fake_genai.types = fake_types  # type: ignore[attr-defined]

    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    settings = Settings(gemini_api_key="key", gemini_strict_schema_mode=False)
    text, media_input, _ = llm_client.gemini_generate(
        settings,
        "prompt",
        llm_input_mode="text",
        response_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
        use_context_cache=False,
        enable_function_calling=False,
    )

    assert text == '{"ok":true}'
    assert media_input == "text"
    assert len(calls) == 2
    assert "response_json_schema" in calls[0]
    assert "response_json_schema" not in calls[1]
