from __future__ import annotations

import json
import subprocess
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from worker.config import Settings
from worker.pipeline.steps import llm_client, llm_video_inputs


class _FakeGenerateContentConfig:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class _FakeCreateCachedContentConfig:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class _FakeThinkingConfig:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


def _install_fake_google_genai(monkeypatch: Any, client_cls: type[Any]) -> None:
    fake_types = types.SimpleNamespace(
        GenerateContentConfig=_FakeGenerateContentConfig,
        CreateCachedContentConfig=_FakeCreateCachedContentConfig,
        ThinkingConfig=_FakeThinkingConfig,
    )
    fake_genai = types.ModuleType("google.genai")
    fake_genai.Client = client_cls  # type: ignore[attr-defined]
    fake_genai.types = fake_types  # type: ignore[attr-defined]
    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)


def test_cache_helpers_cover_dict_hit_trim_sweep_and_missing_name() -> None:
    old_cache = dict(llm_client._CACHE_NAME_BY_KEY)
    old_sweep = dict(llm_client._CACHE_SWEEP_STATE)
    llm_client._CACHE_NAME_BY_KEY.clear()
    llm_client._CACHE_SWEEP_STATE["last_sweep_at"] = 0.0
    try:
        llm_client._CACHE_NAME_BY_KEY["hit"] = {
            "name": "cache-hit",
            "created_at": 10_000_000_000.0,
            "last_used_at": 0.0,
        }
        direct = llm_client._create_cached_content(
            SimpleNamespace(caches=SimpleNamespace(create=lambda **_: None)),
            SimpleNamespace(CreateCachedContentConfig=_FakeCreateCachedContentConfig),
            model="m",
            prompt="prompt",
            cache_key="hit",
            ttl_seconds=300,
            max_keys=5,
            local_ttl_seconds=3600,
        )
        assert direct == "cache-hit"
        assert llm_client._CACHE_NAME_BY_KEY["hit"]["last_used_at"] > 0

        created = llm_client._create_cached_content(
            SimpleNamespace(caches=SimpleNamespace(create=lambda **_: SimpleNamespace(name="  "))),
            SimpleNamespace(CreateCachedContentConfig=_FakeCreateCachedContentConfig),
            model="m",
            prompt="prompt",
            cache_key="new",
            ttl_seconds=10,
            max_keys=5,
            local_ttl_seconds=3600,
        )
        assert created is None

        llm_client._CACHE_NAME_BY_KEY.clear()
        llm_client._CACHE_NAME_BY_KEY.update(
            {
                "a": {"name": "a", "last_used_at": 1},
                "b": {"name": "b", "last_used_at": 2},
                "c": {"name": "c", "last_used_at": 3},
            }
        )
        llm_client._trim_local_cache(max_keys=1)
        assert len(llm_client._CACHE_NAME_BY_KEY) == 1
        assert "c" in llm_client._CACHE_NAME_BY_KEY

        llm_client._CACHE_NAME_BY_KEY.update(
            {
                "expired": {"name": "x", "created_at": 1.0},
                "fresh": {"name": "y", "created_at": 10_000_000_000.0},
            }
        )
        llm_client._sweep_local_cache(local_ttl_seconds=60, sweep_interval_seconds=0)
        assert "expired" not in llm_client._CACHE_NAME_BY_KEY

        llm_client._drop_cached_content("")
    finally:
        llm_client._CACHE_NAME_BY_KEY.clear()
        llm_client._CACHE_NAME_BY_KEY.update(old_cache)
        llm_client._CACHE_SWEEP_STATE.clear()
        llm_client._CACHE_SWEEP_STATE.update(old_sweep)


def test_prepare_video_proxy_for_gemini_reuses_small_mp4_and_builds_proxy(
    monkeypatch: Any, tmp_path: Path
) -> None:
    small_mp4 = tmp_path / "small.mp4"
    small_mp4.write_bytes(b"mp4")
    assert llm_client._prepare_video_proxy_for_gemini(str(small_mp4)) == str(small_mp4)

    source = tmp_path / "source.webm"
    source.write_bytes(b"video-data")
    proxy = tmp_path / "source.gemini-proxy.mp4"

    monkeypatch.setattr(llm_video_inputs.shutil, "which", lambda _name: "/usr/bin/ffmpeg")

    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        proxy.write_bytes(b"proxy-data")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(llm_video_inputs.subprocess, "run", _fake_run)
    resolved = llm_client._prepare_video_proxy_for_gemini(str(source))
    assert resolved == str(proxy)
    assert calls
    assert calls[0][-1] == str(proxy)


def test_gemini_generate_import_and_client_init_failures(monkeypatch: Any, tmp_path: Path) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "w").resolve()),
        pipeline_artifact_root=str((tmp_path / "a").resolve()),
        gemini_api_key="k",
    )

    monkeypatch.setitem(sys.modules, "google", types.ModuleType("google"))
    monkeypatch.delitem(sys.modules, "google.genai", raising=False)
    _, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt",
        llm_input_mode="text",
    )
    assert media_input == "none"
    assert meta["error_code"] == "llm_runtime_import_failed"

    class _ClientInitFails:
        def __init__(self, *, api_key: str) -> None:  # noqa: ARG002
            raise RuntimeError("forbidden status=403")

    _install_fake_google_genai(monkeypatch, _ClientInitFails)
    _, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt",
        llm_input_mode="text",
    )
    assert media_input == "none"
    assert meta["error_code"] == "llm_auth_error"
    assert meta["http_status"] == 403


def test_gemini_generate_loop_termination_paths(monkeypatch: Any, tmp_path: Path) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "w").resolve()),
        pipeline_artifact_root=str((tmp_path / "a").resolve()),
        gemini_api_key="k",
        gemini_context_cache_enabled=False,
    )

    class _NoTextClient:
        def __init__(self, *, api_key: str) -> None:  # noqa: ARG002
            self.models = SimpleNamespace(
                generate_content=lambda **_: SimpleNamespace(text=None, candidates=[])
            )
            self.files = SimpleNamespace(upload=lambda **_: {"kind": "video"})
            self.caches = SimpleNamespace(create=lambda **_: SimpleNamespace(name="cache"))

    _install_fake_google_genai(monkeypatch, _NoTextClient)
    _, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt",
        llm_input_mode="text",
        enable_function_calling=False,
        use_context_cache=False,
        temperature=0.1,
        max_output_tokens=128,
    )
    assert media_input == "text"
    assert meta["function_calling"]["termination_reason"] == "function_calling_disabled"

    class _NoFunctionCallClient:
        def __init__(self, *, api_key: str) -> None:  # noqa: ARG002
            part = SimpleNamespace(text=None)
            candidate = SimpleNamespace(content=SimpleNamespace(parts=[part]))
            self.models = SimpleNamespace(
                generate_content=lambda **_: SimpleNamespace(text=None, candidates=[candidate])
            )
            self.files = SimpleNamespace(upload=lambda **_: {"kind": "video"})
            self.caches = SimpleNamespace(create=lambda **_: SimpleNamespace(name="cache"))

    _install_fake_google_genai(monkeypatch, _NoFunctionCallClient)
    _, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt",
        llm_input_mode="text",
        enable_function_calling=True,
        use_context_cache=False,
    )
    assert media_input == "text"
    assert meta["function_calling"]["termination_reason"] == "no_function_call"

    class _CallObj:
        def __init__(self, name: str, args: Any) -> None:
            self.name = name
            self.args = args

    class _MaxRoundClient:
        def __init__(self, *, api_key: str) -> None:  # noqa: ARG002
            call_part = SimpleNamespace(function_call=_CallObj("select_supporting_frames", ["bad"]))
            thought_part = SimpleNamespace(thought=True)
            candidate = SimpleNamespace(content=SimpleNamespace(parts=[call_part, thought_part]))
            self.models = SimpleNamespace(
                generate_content=lambda **_: SimpleNamespace(text=None, candidates=[candidate])
            )
            self.files = SimpleNamespace(upload=lambda **_: {"kind": "video"})
            self.caches = SimpleNamespace(create=lambda **_: SimpleNamespace(name="cache"))

    _install_fake_google_genai(monkeypatch, _MaxRoundClient)
    _, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt",
        llm_input_mode="text",
        enable_function_calling=True,
        max_function_call_rounds=0,
        use_context_cache=False,
    )
    assert media_input == "text"
    assert meta["function_calling"]["termination_reason"] == "max_function_call_rounds_reached"


def test_gemini_generate_video_frames_and_cache_branches(monkeypatch: Any, tmp_path: Path) -> None:
    video_path = tmp_path / "video.mp4"
    frame_path = tmp_path / "frame.jpg"
    video_path.write_bytes(b"video")
    frame_path.write_bytes(b"\xff\xd8\xff")

    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "w").resolve()),
        pipeline_artifact_root=str((tmp_path / "a").resolve()),
        gemini_api_key="k",
        gemini_context_cache_enabled=True,
        gemini_context_cache_min_chars=10_000,
    )

    class _VideoSuccessClient:
        def __init__(self, *, api_key: str) -> None:  # noqa: ARG002
            self.models = SimpleNamespace(
                generate_content=lambda **_: SimpleNamespace(text='{"ok":true}')
            )
            self.files = SimpleNamespace(upload=lambda **_: {"kind": "video"})
            self.caches = SimpleNamespace(create=lambda **_: SimpleNamespace(name="cache"))

    _install_fake_google_genai(monkeypatch, _VideoSuccessClient)
    text, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt",
        media_path=str(video_path),
        llm_input_mode="video_text",
        use_context_cache=False,
    )
    assert text == '{"ok":true}'
    assert media_input == "video_text"
    assert meta["cache_bypass_reason"] == "non_text_mode"

    class _VideoUploadFailClient:
        def __init__(self, *, api_key: str) -> None:  # noqa: ARG002
            self.models = SimpleNamespace(generate_content=lambda **_: SimpleNamespace(text=None))
            self.files = SimpleNamespace(
                upload=lambda **_: (_ for _ in ()).throw(RuntimeError("upload-fail"))
            )
            self.caches = SimpleNamespace(create=lambda **_: SimpleNamespace(name="cache"))

    _install_fake_google_genai(monkeypatch, _VideoUploadFailClient)
    _, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt",
        media_path=str(video_path),
        llm_input_mode="video_text",
        use_context_cache=False,
    )
    assert media_input == "video_text"
    assert meta["error_code"] in {"llm_unknown_error", "llm_invalid_request"}

    class _FramesFailClient:
        def __init__(self, *, api_key: str) -> None:  # noqa: ARG002
            self.models = SimpleNamespace(
                generate_content=lambda **_: (_ for _ in ()).throw(RuntimeError("frames failed"))
            )
            self.files = SimpleNamespace(upload=lambda **_: {"kind": "video"})
            self.caches = SimpleNamespace(create=lambda **_: SimpleNamespace(name="cache"))

    _install_fake_google_genai(monkeypatch, _FramesFailClient)
    _, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt",
        frame_paths=[str(frame_path)],
        llm_input_mode="frames_text",
        use_context_cache=False,
    )
    assert media_input == "frames_text"
    assert meta["error_code"] in {"llm_unknown_error", "llm_invalid_request"}

    class _TextClient:
        def __init__(self, *, api_key: str) -> None:  # noqa: ARG002
            self.models = SimpleNamespace(
                generate_content=lambda **_: SimpleNamespace(text='{"ok":true}')
            )
            self.files = SimpleNamespace(upload=lambda **_: {"kind": "video"})
            self.caches = SimpleNamespace(create=lambda **_: SimpleNamespace(name="cache"))

    _install_fake_google_genai(monkeypatch, _TextClient)
    text, media_input, meta = llm_client.gemini_generate(
        settings,
        "tiny",
        llm_input_mode="text",
        enable_function_calling=False,
        use_context_cache=True,
    )
    assert text == '{"ok":true}'
    assert media_input == "text"
    assert meta["cache_bypass_reason"] == "prompt_too_short"


def test_wait_for_uploaded_file_ready_polls_until_active() -> None:
    class _File:
        def __init__(self, *, name: str, state: Any) -> None:
            self.name = name
            self.state = state

    states = [
        _File(name="files/demo", state=SimpleNamespace(name="PROCESSING")),
        _File(name="files/demo", state=SimpleNamespace(name="ACTIVE")),
    ]

    class _Files:
        def get(self, *, name: str) -> Any:
            assert name == "files/demo"
            return states.pop(0)

    client = SimpleNamespace(files=_Files())
    ready = llm_client._wait_for_uploaded_file_ready(
        client,
        _File(name="files/demo", state=SimpleNamespace(name="PROCESSING")),
        timeout_seconds=2,
        poll_interval_seconds=0.01,
    )
    assert llm_video_inputs.uploaded_file_state_name(ready) == "ACTIVE"


def test_uploaded_file_state_name_handles_none_value_and_string_fallbacks() -> None:
    assert llm_video_inputs.uploaded_file_state_name(SimpleNamespace(state=None)) == ""
    assert (
        llm_video_inputs.uploaded_file_state_name(
            SimpleNamespace(state=SimpleNamespace(value=" processing "))
        )
        == "PROCESSING"
    )
    assert (
        llm_video_inputs.uploaded_file_state_name(SimpleNamespace(state="FileState.active"))
        == "ACTIVE"
    )


def test_wait_for_uploaded_file_ready_handles_short_circuit_failed_and_timeout(
    monkeypatch: Any,
) -> None:
    uploaded = SimpleNamespace(name="", state=SimpleNamespace(name="PROCESSING"))
    client_without_get = SimpleNamespace(files=SimpleNamespace())
    assert llm_video_inputs.wait_for_uploaded_file_ready(client_without_get, uploaded) is uploaded

    failed_file = SimpleNamespace(name="files/demo", state=SimpleNamespace(name="FAILED"))
    try:
        llm_video_inputs.wait_for_uploaded_file_ready(
            SimpleNamespace(files=SimpleNamespace(get=lambda **_: failed_file)),
            failed_file,
            timeout_seconds=1,
            poll_interval_seconds=0.01,
        )
    except RuntimeError as exc:
        assert str(exc) == "uploaded_file_failed:files/demo"
    else:
        raise AssertionError("expected uploaded_file_failed runtime error")

    processing_file = SimpleNamespace(
        name="files/demo",
        state=SimpleNamespace(name="PROCESSING"),
    )
    moments = iter((100.0, 102.0))
    monkeypatch.setattr(llm_video_inputs.time, "time", lambda: next(moments))
    try:
        llm_video_inputs.wait_for_uploaded_file_ready(
            SimpleNamespace(files=SimpleNamespace(get=lambda **_: processing_file)),
            processing_file,
            timeout_seconds=1.0,
            poll_interval_seconds=0.01,
        )
    except RuntimeError as exc:
        assert str(exc) == "uploaded_file_not_ready:files/demo:processing"
    else:
        raise AssertionError("expected uploaded_file_not_ready runtime error")


def test_prepare_video_proxy_for_gemini_covers_proxy_reuse_and_fallback_paths(
    monkeypatch: Any, tmp_path: Path
) -> None:
    missing = tmp_path / "missing.webm"
    assert llm_video_inputs.prepare_video_proxy_for_gemini(str(missing)) == str(missing)

    proxy_source = tmp_path / "clip.gemini-proxy.mp4"
    proxy_source.write_bytes(b"proxy")
    assert llm_video_inputs.prepare_video_proxy_for_gemini(str(proxy_source)) == str(proxy_source)

    source = tmp_path / "source.webm"
    source.write_bytes(b"video-data")
    monkeypatch.setattr(llm_video_inputs.shutil, "which", lambda _name: None)
    assert llm_video_inputs.prepare_video_proxy_for_gemini(str(source)) == str(source)

    proxy = tmp_path / "source.gemini-proxy.mp4"
    proxy.write_bytes(b"proxy-data")
    source.touch()
    proxy.touch()
    original_stat = llm_video_inputs.Path.stat
    source_stat = source.stat()
    proxy_stat = proxy.stat()

    def _fake_stat(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self == proxy:
            return proxy_stat
        if self == source:
            return source_stat
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(llm_video_inputs.Path, "stat", _fake_stat)
    monkeypatch.setattr(llm_video_inputs.shutil, "which", lambda _name: "/usr/bin/ffmpeg")
    assert llm_video_inputs.prepare_video_proxy_for_gemini(str(source)) == str(proxy)

    proxy.unlink()

    def _source_only_stat(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self == source:
            return source_stat
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(llm_video_inputs.Path, "stat", _source_only_stat)

    def _raise_called_process_error(*_args: Any, **_kwargs: Any) -> None:
        raise subprocess.CalledProcessError(1, "ffmpeg")

    monkeypatch.setattr(llm_video_inputs.subprocess, "run", _raise_called_process_error)
    assert llm_video_inputs.prepare_video_proxy_for_gemini(str(source)) == str(source)


def test_gemini_generate_cache_recreate_fallback(monkeypatch: Any, tmp_path: Path) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "w").resolve()),
        pipeline_artifact_root=str((tmp_path / "a").resolve()),
        gemini_api_key="k",
        gemini_context_cache_enabled=True,
        gemini_context_cache_min_chars=0,
    )

    class _CacheAwareClient:
        def __init__(self, *, api_key: str) -> None:  # noqa: ARG002
            self.models = SimpleNamespace(generate_content=self._generate_content)
            self.files = SimpleNamespace(upload=lambda **_: {"kind": "video"})
            self.caches = SimpleNamespace(create=lambda **_: SimpleNamespace(name="cache"))

        @staticmethod
        def _generate_content(*, model: str, contents: Any, config: Any) -> Any:  # noqa: ARG004
            kwargs = dict(getattr(config, "kwargs", {}))
            if kwargs.get("cached_content"):
                raise RuntimeError("cached_content not found")
            return SimpleNamespace(text=json.dumps({"ok": True}))

    _install_fake_google_genai(monkeypatch, _CacheAwareClient)
    calls = {"count": 0}

    def _fake_create_cached_content(*_args: Any, **_kwargs: Any) -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            return "cache-1"
        raise RuntimeError("cannot recreate")

    monkeypatch.setattr(llm_client, "_create_cached_content", _fake_create_cached_content)
    text, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt long enough for cache",
        llm_input_mode="text",
        enable_function_calling=False,
        use_context_cache=True,
    )
    assert text == '{"ok": true}'
    assert media_input == "text"
    assert meta["cache_hit"] is False
    assert meta["cache_recreate"] is False
    assert meta["cache_bypass_reason"] == "cache_recreate_failed"


def test_cache_helpers_create_success_and_trim_noop() -> None:
    old_cache = dict(llm_client._CACHE_NAME_BY_KEY)
    old_sweep = dict(llm_client._CACHE_SWEEP_STATE)
    llm_client._CACHE_NAME_BY_KEY.clear()
    llm_client._CACHE_SWEEP_STATE["last_sweep_at"] = 0.0
    try:
        llm_client._CACHE_NAME_BY_KEY["legacy"] = " legacy-cache "
        reused = llm_client._create_cached_content(
            SimpleNamespace(
                caches=SimpleNamespace(create=lambda **_: SimpleNamespace(name="unused"))
            ),
            SimpleNamespace(CreateCachedContentConfig=_FakeCreateCachedContentConfig),
            model="m",
            prompt="prompt",
            cache_key="legacy",
            ttl_seconds=10,
            max_keys=4,
            local_ttl_seconds=300,
        )
        assert reused == "legacy-cache"
        assert llm_client._CACHE_NAME_BY_KEY["legacy"]["name"] == "legacy-cache"

        created = llm_client._create_cached_content(
            SimpleNamespace(
                caches=SimpleNamespace(create=lambda **_: SimpleNamespace(name="cache-new"))
            ),
            SimpleNamespace(CreateCachedContentConfig=_FakeCreateCachedContentConfig),
            model="m",
            prompt="prompt",
            cache_key="fresh",
            ttl_seconds=10,
            max_keys=4,
            local_ttl_seconds=300,
        )
        assert created == "cache-new"
        snapshot = dict(llm_client._CACHE_NAME_BY_KEY)
        llm_client._trim_local_cache(max_keys=999)
        assert snapshot == llm_client._CACHE_NAME_BY_KEY
    finally:
        llm_client._CACHE_NAME_BY_KEY.clear()
        llm_client._CACHE_NAME_BY_KEY.update(old_cache)
        llm_client._CACHE_SWEEP_STATE.clear()
        llm_client._CACHE_SWEEP_STATE.update(old_sweep)


def test_gemini_generate_function_loop_signature_and_tool_trace(
    monkeypatch: Any, tmp_path: Path
) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "w").resolve()),
        pipeline_artifact_root=str((tmp_path / "a").resolve()),
        gemini_api_key="k",
        gemini_context_cache_enabled=False,
    )

    class _FunctionLoopClient:
        instances: list[Any] = []

        def __init__(self, *, api_key: str) -> None:  # noqa: ARG002
            self.calls: list[Any] = []
            self.models = SimpleNamespace(generate_content=self._generate_content)
            self.files = SimpleNamespace(upload=lambda **_: {"kind": "video"})
            self.caches = SimpleNamespace(create=lambda **_: SimpleNamespace(name="cache"))
            _FunctionLoopClient.instances.append(self)

        def _generate_content(self, *, model: str, contents: Any, config: Any) -> Any:  # noqa: ARG002
            self.calls.append(contents)
            if len(self.calls) == 1:
                thought = SimpleNamespace(thought=True, thought_signature="sig-1")
                call = SimpleNamespace(
                    function_call=SimpleNamespace(name="unknown_tool", args={"x": 1})
                )
                candidate = SimpleNamespace(content=SimpleNamespace(parts=[thought, call]))
                usage = SimpleNamespace(
                    prompt_token_count=1,
                    candidates_token_count=2,
                    total_token_count=3,
                )
                return SimpleNamespace(
                    text=None,
                    response_id="req-1",
                    candidates=[candidate],
                    usage_metadata=usage,
                )
            return SimpleNamespace(text='{"ok":true}', response_id="req-2", candidates=[])

    _install_fake_google_genai(monkeypatch, _FunctionLoopClient)
    text, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt",
        llm_input_mode="text",
        enable_function_calling=True,
        use_context_cache=False,
        max_function_call_rounds=3,
    )

    assert text == '{"ok":true}'
    assert media_input == "text"
    assert meta["thinking"]["thought_signature_digest"]
    assert meta["function_calling"]["rounds_used"] == 2
    assert meta["function_calling"]["calls"][0]["name"] == "unknown_tool"

    second_round = _FunctionLoopClient.instances[0].calls[1]
    carry_entries = [
        item
        for item in second_round
        if isinstance(item, dict)
        and isinstance(item.get("parts"), list)
        and item.get("parts")
        and "preserved thought signatures" in str(item["parts"][0].get("text", ""))
    ]
    assert carry_entries


def test_gemini_generate_multi_round_missing_signatures_contract_failure(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "w").resolve()),
        pipeline_artifact_root=str((tmp_path / "a").resolve()),
        gemini_api_key="k",
        gemini_context_cache_enabled=False,
    )

    class _MissingSignaturesClient:
        def __init__(self, *, api_key: str) -> None:  # noqa: ARG002
            self.calls = 0
            self.models = SimpleNamespace(generate_content=self._generate_content)
            self.files = SimpleNamespace(upload=lambda **_: {"kind": "video"})
            self.caches = SimpleNamespace(create=lambda **_: SimpleNamespace(name="cache"))

        def _generate_content(self, *, model: str, contents: Any, config: Any) -> Any:  # noqa: ARG002
            self.calls += 1
            if self.calls == 1:
                thought = SimpleNamespace(thought=True)
                call = SimpleNamespace(
                    function_call=SimpleNamespace(name="unknown_tool", args={"x": 1})
                )
                candidate = SimpleNamespace(content=SimpleNamespace(parts=[thought, call]))
                usage = SimpleNamespace(total_token_count=3)
                return SimpleNamespace(text=None, candidates=[candidate], usage_metadata=usage)
            return SimpleNamespace(text='{"ok":true}', candidates=[])

    _install_fake_google_genai(monkeypatch, _MissingSignaturesClient)
    text, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt",
        llm_input_mode="text",
        enable_function_calling=True,
        use_context_cache=False,
        max_function_call_rounds=3,
    )
    assert text is None
    assert media_input == "text"
    assert meta["error_code"] == "llm_thoughts_required"
    assert meta["termination_reason"] == "missing_thought_signatures"


def test_gemini_generate_text_cache_paths_and_tools(monkeypatch: Any, tmp_path: Path) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "w").resolve()),
        pipeline_artifact_root=str((tmp_path / "a").resolve()),
        gemini_api_key="k",
        gemini_context_cache_enabled=True,
        gemini_context_cache_min_chars=0,
    )
    captured_tools: list[Any] = []

    class _CacheClient:
        def __init__(self, *, api_key: str) -> None:  # noqa: ARG002
            self.models = SimpleNamespace(generate_content=self._generate_content)
            self.files = SimpleNamespace(upload=lambda **_: {"kind": "video"})
            self.caches = SimpleNamespace(create=lambda **_: SimpleNamespace(name="cache"))

        def _generate_content(self, *, model: str, contents: Any, config: Any) -> Any:  # noqa: ARG002
            kwargs = dict(getattr(config, "kwargs", {}))
            if "tools" in kwargs:
                captured_tools.extend(list(kwargs["tools"]))
            cached = kwargs.get("cached_content")
            if cached == "cache-stale":
                raise RuntimeError("cached_content not found")
            return SimpleNamespace(text='{"ok":true}', candidates=[])

    _install_fake_google_genai(monkeypatch, _CacheClient)
    monkeypatch.setattr(
        llm_client, "_build_computer_use_tool", lambda _types: {"computer_use": "ok"}
    )

    tool_text, _, tool_meta = llm_client.gemini_generate(
        settings,
        "prompt",
        llm_input_mode="text",
        enable_function_calling=False,
        enable_computer_use=True,
        use_context_cache=False,
    )
    assert tool_text == '{"ok":true}'
    assert captured_tools == [{"computer_use": "ok"}]
    assert tool_meta["cache_bypass_reason"] == "cache_incompatible_with_tools"

    monkeypatch.setattr(llm_client, "_create_cached_content", lambda *_args, **_kwargs: "cache-hit")
    text, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt long enough for cache",
        llm_input_mode="text",
        enable_function_calling=False,
        use_context_cache=True,
    )
    assert text == '{"ok":true}'
    assert media_input == "text"
    assert meta["cache_hit"] is True
    assert meta["cache_recreate"] is False
    assert meta["cache_bypass_reason"] is None

    monkeypatch.setattr(
        llm_client,
        "_create_cached_content",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("cache-down")),
    )
    text, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt long enough for cache",
        llm_input_mode="text",
        enable_function_calling=False,
        use_context_cache=True,
    )
    assert text == '{"ok":true}'
    assert media_input == "text"
    assert meta["cache_bypass_reason"] == "cache_create_failed:ValueError"

    create_calls = {"count": 0}

    def _recreate_success(*_args: Any, **_kwargs: Any) -> str:
        create_calls["count"] += 1
        return "cache-stale" if create_calls["count"] == 1 else "cache-new"

    monkeypatch.setattr(llm_client, "_create_cached_content", _recreate_success)
    text, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt long enough for cache",
        llm_input_mode="text",
        enable_function_calling=False,
        use_context_cache=True,
    )
    assert text == '{"ok":true}'
    assert media_input == "text"
    assert meta["cache_recreate"] is True


def test_gemini_generate_video_frames_and_error_fallback_paths(
    monkeypatch: Any, tmp_path: Path
) -> None:
    video_path = tmp_path / "video.mp4"
    frame_path = tmp_path / "frame.jpg"
    video_path.write_bytes(b"video")
    frame_path.write_bytes(b"\xff\xd8\xff")
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "w").resolve()),
        pipeline_artifact_root=str((tmp_path / "a").resolve()),
        gemini_api_key="k",
        gemini_context_cache_enabled=False,
    )

    class _NoTextClient:
        def __init__(self, *, api_key: str) -> None:  # noqa: ARG002
            self.models = SimpleNamespace(
                generate_content=lambda **_: SimpleNamespace(text=None, candidates=[])
            )
            self.files = SimpleNamespace(upload=lambda **_: {"kind": "video"})
            self.caches = SimpleNamespace(create=lambda **_: SimpleNamespace(name="cache"))

    _install_fake_google_genai(monkeypatch, _NoTextClient)
    _, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt",
        media_path=str(video_path),
        llm_input_mode="video_text",
        enable_function_calling=False,
        use_context_cache=False,
    )
    assert media_input == "video_text"
    assert meta["termination_reason"] == "function_calling_disabled"

    _, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt",
        frame_paths=[str(frame_path)],
        llm_input_mode="frames_text",
        enable_function_calling=False,
        use_context_cache=False,
    )
    assert media_input == "frames_text"
    assert meta["termination_reason"] == "function_calling_disabled"

    monkeypatch.setattr(
        llm_client,
        "_build_frame_parts",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("frame-parts-fail")),
    )
    _, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt",
        frame_paths=[str(frame_path)],
        llm_input_mode="frames_text",
        enable_function_calling=False,
        use_context_cache=False,
    )
    assert media_input == "frames_text"
    assert meta["error_code"] in {"llm_unknown_error", "llm_invalid_request"}

    _, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt",
        llm_input_mode="frames_text",
        enable_function_calling=False,
        use_context_cache=False,
    )
    assert media_input == "none"
    assert meta["error_code"] == "llm_no_response"


def test_gemini_generate_cached_exception_and_outer_text_exception_paths(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "w").resolve()),
        pipeline_artifact_root=str((tmp_path / "a").resolve()),
        gemini_api_key="k",
        gemini_context_cache_enabled=True,
        gemini_context_cache_min_chars=0,
    )

    class _StableTextClient:
        def __init__(self, *, api_key: str) -> None:  # noqa: ARG002
            self.models = SimpleNamespace(
                generate_content=lambda **_: SimpleNamespace(text='{"ok":true}', candidates=[])
            )
            self.files = SimpleNamespace(upload=lambda **_: {"kind": "video"})
            self.caches = SimpleNamespace(create=lambda **_: SimpleNamespace(name="cache"))

    _install_fake_google_genai(monkeypatch, _StableTextClient)

    call_count = {"count": 0}

    def _cache_error_then_ok(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        call_count["count"] += 1
        if call_count["count"] == 1:
            raise RuntimeError("cached_content broken")
        return {"thought_count": 0, "thought_signatures": [], "usage": {}}

    create_calls = {"count": 0}

    def _create_cache_then_none(*_args: Any, **_kwargs: Any) -> str | None:
        create_calls["count"] += 1
        return "cache-hit" if create_calls["count"] == 1 else None

    monkeypatch.setattr(llm_client, "_collect_thought_metadata", _cache_error_then_ok)
    monkeypatch.setattr(llm_client, "_create_cached_content", _create_cache_then_none)
    text, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt long enough for cache",
        llm_input_mode="text",
        enable_function_calling=False,
        use_context_cache=True,
    )
    assert text == '{"ok":true}'
    assert media_input == "text"
    assert meta["cache_bypass_reason"] == "cache_recreate_failed"

    non_cache_calls = {"count": 0}

    def _non_cache_then_ok(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        non_cache_calls["count"] += 1
        if non_cache_calls["count"] == 1:
            raise RuntimeError("boom")
        return {"thought_count": 0, "thought_signatures": [], "usage": {}}

    monkeypatch.setattr(llm_client, "_collect_thought_metadata", _non_cache_then_ok)
    monkeypatch.setattr(llm_client, "_create_cached_content", lambda *_args, **_kwargs: "cache-hit")
    text, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt long enough for cache",
        llm_input_mode="text",
        enable_function_calling=False,
        use_context_cache=True,
    )
    assert text == '{"ok":true}'
    assert media_input == "text"
    assert meta["cache_bypass_reason"].startswith("cache_bypass:RuntimeError")

    monkeypatch.setattr(
        llm_client,
        "_collect_thought_metadata",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("fatal")),
    )
    _, media_input, meta = llm_client.gemini_generate(
        settings,
        "prompt",
        llm_input_mode="text",
        enable_function_calling=False,
        use_context_cache=False,
    )
    assert media_input == "text"
    assert meta["error_code"] in {"llm_unknown_error", "llm_invalid_request"}
