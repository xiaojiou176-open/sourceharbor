from __future__ import annotations

import sys
import time
import types
from pathlib import Path
from typing import Any

from worker.config import Settings
from worker.pipeline import runner
from worker.pipeline.steps import llm_client
from worker.pipeline.steps.llm_computer_use import build_default_computer_use_handler


def test_gemini_multimodal_falls_back_from_video_to_frames(
    monkeypatch: Any, tmp_path: Path
) -> None:
    video_path = tmp_path / "video.mp4"
    frame_path = tmp_path / "frame_001.jpg"
    video_path.write_bytes(b"not-a-real-video")
    frame_path.write_bytes(b"\xff\xd8\xff")

    calls: list[Any] = []

    class _FakeModels:
        def generate_content(self, *, model: str, contents: Any, config: Any) -> Any:
            calls.append({"model": model, "contents": contents, "config": config})
            if isinstance(contents, list) and any(
                isinstance(item, dict) and item.get("kind") == "video" for item in contents
            ):
                raise RuntimeError("video-input-failed")
            if isinstance(contents, list) and any(
                isinstance(item, dict) and str(item.get("mime_type", "")).startswith("image/")
                for item in contents
            ):
                return types.SimpleNamespace(text='{"ok":true}')
            return types.SimpleNamespace(text=None)

    class _FakeFiles:
        @staticmethod
        def upload(*, file: str) -> dict[str, str]:
            return {"kind": "video", "path": file}

    class _FakeClient:
        def __init__(self, *, api_key: str):
            self.api_key = api_key
            self.models = _FakeModels()
            self.files = _FakeFiles()

    class _FakePart:
        @staticmethod
        def from_bytes(*, data: bytes, mime_type: str) -> dict[str, Any]:
            return {"mime_type": mime_type, "size": len(data)}

    class _FakeThinkingConfig:
        def __init__(self, **kwargs: Any):
            self.kwargs = kwargs

    class _FakeGenerateContentConfig:
        def __init__(self, **kwargs: Any):
            self.kwargs = kwargs

    fake_types = types.SimpleNamespace(
        Part=_FakePart,
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

    settings = Settings(gemini_api_key="key", pipeline_max_frames=4)
    text, media_input, meta = runner._gemini_generate(
        settings,
        "prompt",
        media_path=str(video_path),
        frame_paths=[str(frame_path)],
        llm_input_mode="auto",
    )

    assert text == '{"ok":true}'
    assert media_input == "frames_text"
    assert len(calls) >= 2
    assert isinstance(meta, dict)


def test_gemini_function_calling_loop_and_thought_metadata(
    monkeypatch: Any, tmp_path: Path
) -> None:
    frame_path = tmp_path / "frame_001.jpg"
    frame_path.write_bytes(b"\xff\xd8\xff")

    calls: list[Any] = []
    first_round = {"value": True}

    class _FunctionCall:
        def __init__(self, name: str, args: dict[str, Any]):
            self.name = name
            self.args = args

    class _Part:
        def __init__(
            self,
            *,
            text: str | None = None,
            thought: bool = False,
            function_call: Any = None,
            signature: str | None = None,
        ):
            self.text = text
            self.thought = thought
            self.function_call = function_call
            self.signature = signature

        @staticmethod
        def from_bytes(**kwargs: Any) -> dict[str, Any]:
            return dict(kwargs)

        @staticmethod
        def from_function_response(*, name: str, response: dict[str, Any]) -> dict[str, Any]:
            return {"function_response": {"name": name, "response": response}}

    class _FakeModels:
        def generate_content(self, *, model: str, contents: Any, config: Any) -> Any:
            calls.append({"model": model, "contents": contents, "config": config})
            if first_round["value"]:
                first_round["value"] = False
                function_call = _FunctionCall(
                    name="select_supporting_frames",
                    args={
                        "frame_summaries": [{"timestamp_s": 12, "path": "/tmp/f.jpg"}],
                        "max_items": 1,
                    },
                )
                part_call = _Part(function_call=function_call)
                part_thought = _Part(text="internal", thought=True, signature="sig-A")
                content = types.SimpleNamespace(parts=[part_call, part_thought])
                return types.SimpleNamespace(
                    text=None,
                    candidates=[types.SimpleNamespace(content=content)],
                    usage_metadata=types.SimpleNamespace(
                        prompt_token_count=10,
                        candidates_token_count=5,
                        total_token_count=15,
                        thoughts_token_count=2,
                    ),
                )

            content = types.SimpleNamespace(parts=[_Part(text='{"ok":true}')])
            return types.SimpleNamespace(
                text='{"ok":true}',
                candidates=[types.SimpleNamespace(content=content)],
            )

    class _FakeFiles:
        @staticmethod
        def upload(*, file: str) -> dict[str, str]:
            return {"kind": "video", "path": file}

    class _FakeClient:
        def __init__(self, *, api_key: str):
            self.api_key = api_key
            self.models = _FakeModels()
            self.files = _FakeFiles()

    class _FakeThinkingConfig:
        def __init__(self, **kwargs: Any):
            self.kwargs = kwargs

    class _FakeGenerateContentConfig:
        def __init__(self, **kwargs: Any):
            self.kwargs = kwargs

    fake_types = types.SimpleNamespace(
        Part=_Part,
        ThinkingConfig=_FakeThinkingConfig,
        GenerateContentConfig=_FakeGenerateContentConfig,
        Content=lambda **kwargs: dict(kwargs),
    )
    fake_genai = types.ModuleType("google.genai")
    fake_genai.Client = _FakeClient  # type: ignore[attr-defined]
    fake_genai.types = fake_types  # type: ignore[attr-defined]

    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    settings = Settings(gemini_api_key="key", pipeline_max_frames=4)
    text, media_input, meta = runner._gemini_generate(
        settings,
        "prompt",
        frame_paths=[str(frame_path)],
        llm_input_mode="frames_text",
        include_thoughts=True,
        max_function_call_rounds=2,
        media_resolution={"frame": "high"},
    )

    assert text == '{"ok":true}'
    assert media_input == "frames_text"
    assert len(calls) == 2
    first_contents = calls[0]["contents"]
    assert isinstance(first_contents, list)
    assert any(
        isinstance(item, dict)
        and item.get("mime_type", "").startswith("image/")
        and item.get("media_resolution") == "high"
        for item in first_contents
    )
    function_meta = meta["function_calling"]
    assert function_meta["rounds_used"] == 2
    assert function_meta["calls"][0]["name"] == "select_supporting_frames"
    thinking_meta = meta["thinking"]
    assert thinking_meta["include_thoughts"] is True
    assert thinking_meta["thought_count"] == 1
    assert thinking_meta["thought_signatures"] == ["sig-A"]


def test_llm_cache_signature_includes_input_mode_and_media_dimension(tmp_path: Path) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifact").resolve()),
    )
    ctx = runner.PipelineContext(
        settings=settings,
        sqlite_store=None,  # type: ignore[arg-type]
        pg_store=None,  # type: ignore[arg-type]
        job_id="job",
        attempt=1,
        job_record={},
        work_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        download_dir=tmp_path / "download",
        frames_dir=tmp_path / "frames",
        artifacts_dir=tmp_path / "artifacts",
    )

    base_state = {
        "title": "Demo",
        "metadata": {},
        "transcript": "hello",
        "comments": {"top_comments": []},
        "frames": [],
        "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "llm_input_mode": "auto",
        "llm_media_input": {"video_available": False, "frame_count": 0},
    }
    sig_1 = runner._build_step_cache_info(ctx, base_state, "llm_outline")["signature"]

    changed_mode = dict(base_state)
    changed_mode["llm_input_mode"] = "text"
    sig_2 = runner._build_step_cache_info(ctx, changed_mode, "llm_outline")["signature"]

    changed_media = dict(base_state)
    changed_media["llm_media_input"] = {"video_available": True, "frame_count": 2}
    sig_3 = runner._build_step_cache_info(ctx, changed_media, "llm_outline")["signature"]

    assert sig_1 != sig_2
    assert sig_1 != sig_3


def test_gemini_text_cache_self_heals_on_stale_cached_content(monkeypatch: Any) -> None:
    prompt = "cache-self-heal-prompt"
    cache_key = llm_client._cache_key("gemini-3.1-pro-preview", prompt, "text")
    llm_client._CACHE_NAME_BY_KEY[cache_key] = "stale-cache"

    class _FakeModels:
        def generate_content(self, *, model: str, contents: Any, config: Any) -> Any:
            kwargs = dict(getattr(config, "kwargs", {}))
            cached_content = kwargs.get("cached_content")
            if cached_content == "stale-cache":
                raise RuntimeError("cached_content not found")
            return types.SimpleNamespace(text='{"ok":true}')

    class _FakeCaches:
        @staticmethod
        def create(*, model: str, config: Any) -> Any:
            return types.SimpleNamespace(name="fresh-cache")

    class _FakeClient:
        def __init__(self, *, api_key: str):
            self.api_key = api_key
            self.models = _FakeModels()
            self.files = object()
            self.caches = _FakeCaches()

    class _FakeThinkingConfig:
        def __init__(self, **kwargs: Any):
            self.kwargs = kwargs

    class _FakeGenerateContentConfig:
        def __init__(self, **kwargs: Any):
            self.kwargs = kwargs

    class _FakeCreateCachedContentConfig:
        def __init__(self, **kwargs: Any):
            self.kwargs = kwargs

    fake_types = types.SimpleNamespace(
        ThinkingConfig=_FakeThinkingConfig,
        GenerateContentConfig=_FakeGenerateContentConfig,
        CreateCachedContentConfig=_FakeCreateCachedContentConfig,
    )
    fake_genai = types.ModuleType("google.genai")
    fake_genai.Client = _FakeClient  # type: ignore[attr-defined]
    fake_genai.types = fake_types  # type: ignore[attr-defined]

    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    settings = Settings(
        gemini_api_key="key",
        gemini_context_cache_enabled=True,
        gemini_context_cache_min_chars=1,
    )
    text, media_input, meta = llm_client.gemini_generate(
        settings,
        prompt,
        llm_input_mode="text",
        use_context_cache=True,
        enable_function_calling=False,
    )

    assert text == '{"ok":true}'
    assert media_input == "text"
    assert meta["cache_hit"] is True
    assert meta["cache_recreate"] is True
    assert meta["cache_bypass_reason"] is None
    assert llm_client._CACHE_NAME_BY_KEY[cache_key]["name"] == "fresh-cache"
    llm_client._CACHE_NAME_BY_KEY.pop(cache_key, None)


def test_gemini_text_cache_bypassed_when_function_calling_enabled(monkeypatch: Any) -> None:
    class _FakeModels:
        @staticmethod
        def generate_content(*, model: str, contents: Any, config: Any) -> Any:
            kwargs = dict(getattr(config, "kwargs", {}))
            assert "cached_content" not in kwargs
            return types.SimpleNamespace(text='{"ok":true}')

    class _FakeCaches:
        @staticmethod
        def create(*, model: str, config: Any) -> Any:
            raise AssertionError("cache create should be bypassed when tools are enabled")

    class _FakeClient:
        def __init__(self, *, api_key: str):
            self.api_key = api_key
            self.models = _FakeModels()
            self.files = object()
            self.caches = _FakeCaches()

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

    settings = Settings(
        gemini_api_key="key",
        gemini_context_cache_enabled=True,
        gemini_context_cache_min_chars=1,
    )
    text, media_input, meta = llm_client.gemini_generate(
        settings,
        "cache-conflict-prompt",
        llm_input_mode="text",
        use_context_cache=True,
        enable_function_calling=True,
    )

    assert text == '{"ok":true}'
    assert media_input == "text"
    assert meta["cache_hit"] is False
    assert meta["cache_bypass_reason"] == "cache_incompatible_with_tools"


def test_gemini_computer_use_requires_confirmation(monkeypatch: Any) -> None:
    class _FunctionCall:
        def __init__(self, name: str, args: dict[str, Any]):
            self.name = name
            self.args = args

    class _Part:
        def __init__(self, *, text: str | None = None, function_call: Any = None):
            self.text = text
            self.function_call = function_call

    class _FakeModels:
        def __init__(self) -> None:
            self.round = 0

        def generate_content(self, *, model: str, contents: Any, config: Any) -> Any:
            self.round += 1
            if self.round == 1:
                content = types.SimpleNamespace(
                    parts=[_Part(function_call=_FunctionCall("computer_use", {"action": "click"}))]
                )
                return types.SimpleNamespace(
                    text=None, candidates=[types.SimpleNamespace(content=content)]
                )
            content = types.SimpleNamespace(parts=[_Part(text='{"ok":true}')])
            return types.SimpleNamespace(
                text='{"ok":true}', candidates=[types.SimpleNamespace(content=content)]
            )

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
        Content=lambda **kwargs: dict(kwargs),
    )
    fake_genai = types.ModuleType("google.genai")
    fake_genai.Client = _FakeClient  # type: ignore[attr-defined]
    fake_genai.types = fake_types  # type: ignore[attr-defined]

    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    def _should_not_run(**_: Any) -> dict[str, Any]:
        raise AssertionError("computer_use handler should not run without confirmation")

    settings = Settings(gemini_api_key="key")
    text, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt",
        llm_input_mode="text",
        use_context_cache=False,
        enable_function_calling=False,
        enable_computer_use=True,
        computer_use_handler=_should_not_run,
        computer_use_require_confirmation=True,
        computer_use_confirmed=False,
    )

    assert text == '{"ok":true}'
    assert media_input == "text"
    call_meta = meta["function_calling"]["calls"]
    assert call_meta[0]["name"] == "computer_use"
    assert call_meta[0]["status"] == "blocked"
    assert meta["computer_use"]["steps_used"] == 0


def test_gemini_computer_use_default_handler_avoids_handler_missing(monkeypatch: Any) -> None:
    class _FunctionCall:
        def __init__(self, name: str, args: dict[str, Any]):
            self.name = name
            self.args = args

    class _Part:
        def __init__(self, *, text: str | None = None, function_call: Any = None):
            self.text = text
            self.function_call = function_call

    class _FakeModels:
        def __init__(self) -> None:
            self.round = 0

        def generate_content(self, *, model: str, contents: Any, config: Any) -> Any:
            self.round += 1
            if self.round == 1:
                content = types.SimpleNamespace(
                    parts=[_Part(function_call=_FunctionCall("computer_use", {"action": "click"}))]
                )
                return types.SimpleNamespace(
                    text=None, candidates=[types.SimpleNamespace(content=content)]
                )
            content = types.SimpleNamespace(parts=[_Part(text='{"ok":true}')])
            return types.SimpleNamespace(
                text='{"ok":true}', candidates=[types.SimpleNamespace(content=content)]
            )

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
        Content=lambda **kwargs: dict(kwargs),
    )
    fake_genai = types.ModuleType("google.genai")
    fake_genai.Client = _FakeClient  # type: ignore[attr-defined]
    fake_genai.types = fake_types  # type: ignore[attr-defined]

    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    handler = build_default_computer_use_handler(
        state={
            "source_url": "https://www.youtube.com/watch?v=demo",
            "computer_use": {"executor": "browser_stub"},
        },
        llm_policy={},
        section_policy={},
    )
    settings = Settings(gemini_api_key="key")
    text, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt",
        llm_input_mode="text",
        use_context_cache=False,
        enable_function_calling=False,
        enable_computer_use=True,
        computer_use_handler=handler,
        computer_use_require_confirmation=False,
        computer_use_confirmed=True,
    )

    assert text == '{"ok":true}'
    assert media_input == "text"
    call_meta = meta["function_calling"]["calls"]
    assert call_meta[0]["name"] == "computer_use"
    assert call_meta[0]["status"] == "ok"


def test_gemini_computer_use_honors_max_steps(monkeypatch: Any) -> None:
    class _FunctionCall:
        def __init__(self, name: str, args: dict[str, Any]):
            self.name = name
            self.args = args

    class _Part:
        def __init__(self, *, text: str | None = None, function_call: Any = None):
            self.text = text
            self.function_call = function_call

    class _FakeModels:
        def __init__(self) -> None:
            self.round = 0

        def generate_content(self, *, model: str, contents: Any, config: Any) -> Any:
            self.round += 1
            if self.round in {1, 2}:
                content = types.SimpleNamespace(
                    parts=[_Part(function_call=_FunctionCall("computer_use", {"action": "click"}))]
                )
                return types.SimpleNamespace(
                    text=None, candidates=[types.SimpleNamespace(content=content)]
                )
            content = types.SimpleNamespace(parts=[_Part(text='{"ok":true}')])
            return types.SimpleNamespace(
                text='{"ok":true}', candidates=[types.SimpleNamespace(content=content)]
            )

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
        Content=lambda **kwargs: dict(kwargs),
    )
    fake_genai = types.ModuleType("google.genai")
    fake_genai.Client = _FakeClient  # type: ignore[attr-defined]
    fake_genai.types = fake_types  # type: ignore[attr-defined]

    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    def _handler(**_: Any) -> dict[str, Any]:
        return {"ok": True}

    settings = Settings(gemini_api_key="key")
    text, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt",
        llm_input_mode="text",
        use_context_cache=False,
        enable_function_calling=False,
        enable_computer_use=True,
        computer_use_handler=_handler,
        computer_use_require_confirmation=False,
        computer_use_confirmed=True,
        computer_use_max_steps=1,
        computer_use_timeout_seconds=1.0,
    )

    assert text == '{"ok":true}'
    assert media_input == "text"
    calls = meta["function_calling"]["calls"]
    assert calls[0]["status"] == "ok"
    assert calls[1]["status"] == "blocked"
    assert meta["computer_use"]["steps_used"] == 1


def test_gemini_computer_use_honors_timeout(monkeypatch: Any) -> None:
    class _FunctionCall:
        def __init__(self, name: str, args: dict[str, Any]):
            self.name = name
            self.args = args

    class _Part:
        def __init__(self, *, text: str | None = None, function_call: Any = None):
            self.text = text
            self.function_call = function_call

    class _FakeModels:
        def __init__(self) -> None:
            self.round = 0

        def generate_content(self, *, model: str, contents: Any, config: Any) -> Any:
            self.round += 1
            if self.round == 1:
                content = types.SimpleNamespace(
                    parts=[_Part(function_call=_FunctionCall("computer_use", {"action": "click"}))]
                )
                return types.SimpleNamespace(
                    text=None, candidates=[types.SimpleNamespace(content=content)]
                )
            content = types.SimpleNamespace(parts=[_Part(text='{"ok":true}')])
            return types.SimpleNamespace(
                text='{"ok":true}', candidates=[types.SimpleNamespace(content=content)]
            )

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
        Content=lambda **kwargs: dict(kwargs),
    )
    fake_genai = types.ModuleType("google.genai")
    fake_genai.Client = _FakeClient  # type: ignore[attr-defined]
    fake_genai.types = fake_types  # type: ignore[attr-defined]

    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    def _slow_handler(**_: Any) -> dict[str, Any]:
        time.sleep(1.2)
        return {"ok": True}

    settings = Settings(gemini_api_key="key")
    text, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt",
        llm_input_mode="text",
        use_context_cache=False,
        enable_function_calling=False,
        enable_computer_use=True,
        computer_use_handler=_slow_handler,
        computer_use_require_confirmation=False,
        computer_use_confirmed=True,
        computer_use_max_steps=2,
        computer_use_timeout_seconds=0.1,
    )

    assert text == '{"ok":true}'
    assert media_input == "text"
    calls = meta["function_calling"]["calls"]
    assert calls[0]["status"] == "failed"
    assert meta["computer_use"]["steps_used"] == 0
