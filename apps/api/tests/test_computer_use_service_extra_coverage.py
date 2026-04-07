from __future__ import annotations

import base64
import concurrent.futures
import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest

from apps.api.app.services.computer_use import ComputerUseSafetyConfig, ComputerUseService


def _install_fake_genai(monkeypatch: pytest.MonkeyPatch, *, response: object) -> None:
    class _FakeModels:
        def __init__(self, payload: object) -> None:
            self.payload = payload

        def generate_content(self, **kwargs: Any) -> object:
            del kwargs
            return self.payload

    class _FakeClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.models = _FakeModels(response)

    class _FakePart:
        @staticmethod
        def from_bytes(*, data: bytes, mime_type: str) -> dict[str, object]:
            return {"size": len(data), "mime_type": mime_type}

    class _FakeTypes:
        Part = _FakePart

        class Tool:
            def __init__(self, **kwargs: Any) -> None:
                self.kwargs = kwargs

        class ComputerUse:
            pass

        class GenerateContentConfig:
            def __init__(self, **kwargs: Any) -> None:
                self.kwargs = kwargs

        class ThinkingConfig:
            def __init__(self, **kwargs: Any) -> None:
                self.kwargs = kwargs

    fake_genai = types.ModuleType("google.genai")
    fake_genai.Client = _FakeClient
    fake_genai.types = _FakeTypes
    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)


def test_run_omits_thinking_config_for_dedicated_computer_use_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_COMPUTER_USE_MODEL", "gemini-2.5-computer-use-preview-10-2025")

    captured: dict[str, object] = {}

    class _FakeModels:
        def generate_content(self, **kwargs: Any) -> object:
            captured.update(kwargs)
            return SimpleNamespace(
                text="done",
                candidates=[],
            )

    class _FakeClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.models = _FakeModels()

    class _FakePart:
        @staticmethod
        def from_bytes(*, data: bytes, mime_type: str) -> dict[str, object]:
            return {"size": len(data), "mime_type": mime_type}

    class _FakeTypes:
        Part = _FakePart

        class Tool:
            def __init__(self, **kwargs: Any) -> None:
                self.kwargs = kwargs

        class ComputerUse:
            pass

        class GenerateContentConfig:
            def __init__(self, **kwargs: Any) -> None:
                self.kwargs = kwargs

        class ThinkingConfig:
            def __init__(self, **kwargs: Any) -> None:
                self.kwargs = kwargs

    fake_genai = types.ModuleType("google.genai")
    fake_genai.Client = _FakeClient
    fake_genai.types = _FakeTypes
    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    service = ComputerUseService()
    service.run(
        instruction="open settings",
        screenshot_base64=base64.b64encode(b"pixels").decode("ascii"),
        safety=ComputerUseSafetyConfig(),
    )

    config = captured["config"]
    assert isinstance(config, _FakeTypes.GenerateContentConfig)
    assert "thinking_config" not in config.kwargs


def test_run_validates_instruction_and_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    service = ComputerUseService()
    payload = base64.b64encode(b"img").decode("ascii")

    with pytest.raises(ValueError, match="instruction must not be empty"):
        service.run(
            instruction="   ",
            screenshot_base64=payload,
            safety=ComputerUseSafetyConfig(),
        )
    with pytest.raises(ValueError, match="gemini_api_key_missing"):
        service.run(
            instruction="open settings",
            screenshot_base64=payload,
            safety=ComputerUseSafetyConfig(),
        )


def test_run_reports_sdk_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    service = ComputerUseService()
    payload = base64.b64encode(b"img").decode("ascii")

    real_import = __import__

    def _fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("google"):
            raise ImportError("google sdk missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _fake_import)

    with pytest.raises(ValueError, match="gemini_sdk_unavailable:"):
        service.run(
            instruction="click button",
            screenshot_base64=payload,
            safety=ComputerUseSafetyConfig(),
        )


def test_run_success_builds_actions_blocked_hits_and_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_COMPUTER_USE_MODEL", "gemini-2.5-computer-use-preview-10-2025")
    response = SimpleNamespace(
        text="",
        response_id="resp-1",
        candidates=[
            SimpleNamespace(
                finish_reason="STOP",
                content=SimpleNamespace(
                    parts=[
                        {
                            "function_call": {
                                "name": "click",
                                "args": {
                                    "action": "delete",
                                    "selector": "#danger",
                                    "text": "confirm",
                                    "reason": "needs delete",
                                },
                            }
                        }
                    ]
                ),
            )
        ],
    )
    _install_fake_genai(monkeypatch, response=response)
    service = ComputerUseService()

    result = service.run(
        instruction="remove stale row",
        screenshot_base64=base64.b64encode(b"pixels").decode("ascii"),
        safety=ComputerUseSafetyConfig(
            confirm_before_execute=False,
            blocked_actions=[" delete ", "DROP"],
            max_actions=4,
        ),
    )

    assert result["actions"][0]["action"] == "delete"
    assert result["blocked_actions"] == ["delete"]
    assert result["require_confirmation"] is True
    assert "blocked keywords were detected: delete" in result["final_text"]
    assert result["thought_metadata"]["request_id"] == "resp-1"
    assert result["thought_metadata"]["finish_reason"] == "STOP"
    assert result["thought_metadata"]["action_count"] == 1
    assert result["thought_metadata"]["model"] == "gemini-2.5-computer-use-preview-10-2025"


def test_generate_with_retry_raises_runtime_error_on_non_timeout_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    service = ComputerUseService()

    class _BadModels:
        def generate_content(self, **kwargs: Any) -> object:
            del kwargs
            raise RuntimeError("provider exploded")

    class _BadClient:
        models = _BadModels()

    with pytest.raises(RuntimeError, match="provider exploded"):
        service._generate_with_timeout_and_retry(  # noqa: SLF001
            client=_BadClient(),
            model="gemini-3.1-pro-preview",
            contents=["hello"],
            config={},
            timeout_seconds=1.0,
            max_retries=1,
        )


def test_helper_methods_cover_env_decoding_and_action_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    service = ComputerUseService()

    monkeypatch.setenv("COMPUTER_USE_MODEL_TIMEOUT_SECONDS", "200")
    assert (
        service._read_float_env(  # noqa: SLF001
            "COMPUTER_USE_MODEL_TIMEOUT_SECONDS",
            default=5.0,
            min_value=1.0,
            max_value=120.0,
        )
        == 120.0
    )
    monkeypatch.setenv("COMPUTER_USE_MODEL_TIMEOUT_SECONDS", "bad")
    assert (
        service._read_float_env(  # noqa: SLF001
            "COMPUTER_USE_MODEL_TIMEOUT_SECONDS",
            default=5.0,
            min_value=1.0,
            max_value=120.0,
        )
        == 5.0
    )

    monkeypatch.setenv("COMPUTER_USE_MODEL_MAX_RETRIES", "-3")
    assert (
        service._read_int_env(  # noqa: SLF001
            "COMPUTER_USE_MODEL_MAX_RETRIES",
            default=1,
            min_value=0,
            max_value=3,
        )
        == 0
    )
    monkeypatch.delenv("COMPUTER_USE_MODEL_MAX_RETRIES", raising=False)
    assert (
        service._read_int_env(  # noqa: SLF001
            "COMPUTER_USE_MODEL_MAX_RETRIES",
            default=2,
            min_value=0,
            max_value=3,
        )
        == 2
    )

    assert (
        service._decode_base64_image(  # noqa: SLF001
            "data:image/png;base64," + base64.b64encode(b"abc").decode("ascii")
        )
        == b"abc"
    )
    with pytest.raises(ValueError, match="screenshot must not be empty"):
        service._decode_base64_image("   ")  # noqa: SLF001
    with pytest.raises(ValueError, match="screenshot must be valid base64"):
        service._decode_base64_image("%%%")  # noqa: SLF001

    assert service._extract_finish_reason(SimpleNamespace(candidates=[])) is None  # noqa: SLF001
    assert (  # noqa: SLF001
        service._extract_finish_reason(SimpleNamespace(candidates=[{"finish_reason": "OK"}]))
        == "OK"
    )

    fallback_actions = service._extract_actions(SimpleNamespace(candidates=None), max_actions=1)  # noqa: SLF001
    assert fallback_actions[0]["action"] == "observe"
    parsed_actions = service._extract_actions(  # noqa: SLF001
        SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    content=SimpleNamespace(
                        parts=[
                            {
                                "function_call": {
                                    "name": "navigate",
                                    "args": {"url": "https://example.com"},
                                }
                            },
                            {
                                "function_call": {
                                    "name": "type",
                                    "args": {"input_text": "hello"},
                                }
                            },
                        ]
                    )
                )
            ]
        ),
        max_actions=1,
    )
    assert parsed_actions == [
        {
            "step": 1,
            "action": "navigate",
            "target": "https://example.com",
            "input_text": None,
            "reasoning": None,
        }
    ]

    blocked = service._detect_blocked_actions(  # noqa: SLF001
        actions=[
            {"action": "delete", "target": "#btn", "input_text": None, "reasoning": "safe"},
            {"action": "click", "target": "#link", "input_text": "drop table", "reasoning": ""},
        ],
        blocked_keywords=[" delete ", "DROP", "drop"],
    )
    assert blocked == ["delete", "drop"]
    assert "blocked keywords" in service._build_final_text(  # noqa: SLF001
        total_actions=2,
        require_confirmation=True,
        blocked_actions=blocked,
    )
    assert "Ready for execution" in service._build_final_text(  # noqa: SLF001
        total_actions=1,
        require_confirmation=False,
        blocked_actions=[],
    )
    assert service._to_str_or_none("  x  ") == "x"  # noqa: SLF001
    assert service._to_str_or_none("   ") is None  # noqa: SLF001


def test_generate_with_retry_timeout_error_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    service = ComputerUseService()

    class _SlowModels:
        def generate_content(self, **kwargs: Any) -> object:
            del kwargs
            raise concurrent.futures.TimeoutError

    class _SlowClient:
        models = _SlowModels()

    with pytest.raises(RuntimeError, match="computer_use model timeout after 1.0s"):
        service._generate_with_timeout_and_retry(  # noqa: SLF001
            client=_SlowClient(),
            model="gemini-3.1-pro-preview",
            contents=["hi"],
            config={},
            timeout_seconds=1.0,
            max_retries=0,
        )
