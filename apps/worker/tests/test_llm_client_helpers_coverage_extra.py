from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from worker.pipeline.steps import llm_client_helpers as helpers


def test_part_and_text_extraction_paths() -> None:
    assert helpers._part_is_thought({"thought": True}) is True
    assert helpers._part_is_thought({"thought": "yes"}) is False
    assert helpers._part_is_thought(SimpleNamespace(thought=True)) is True

    response = SimpleNamespace(
        text="",
        candidates=[
            SimpleNamespace(content=SimpleNamespace(parts="invalid")),
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[
                        {"thought": True},
                        SimpleNamespace(text=" alpha "),
                        SimpleNamespace(text=" beta "),
                    ]
                )
            ),
        ],
    )
    assert helpers._extract_response_text(response) == "alpha\nbeta"


def test_media_resolution_and_part_resolution() -> None:
    assert helpers._normalize_media_resolution("ULTRA-HIGH") == "ultra_high"
    assert helpers._normalize_media_resolution("unknown", default="low") == "low"
    assert helpers._normalize_media_resolution_policy("HIGH") == {
        "default": "high",
        "frame": "high",
        "image": "high",
        "pdf": "high",
    }
    assert helpers._normalize_media_resolution_policy(
        {"default": "medium", "frame": "high", "image": "low", "pdf": "ultra-high"}
    ) == {
        "default": "medium",
        "frame": "high",
        "image": "low",
        "pdf": "ultra_high",
    }
    policy = {"default": "medium", "frame": "high", "image": "low", "pdf": "ultra_high"}
    assert helpers._part_media_resolution(policy, mime_type="image/png") == "low"
    assert helpers._part_media_resolution(policy, mime_type="application/pdf") == "ultra_high"
    assert helpers._part_media_resolution(policy, mime_type="video/mp4", kind="frame") == "high"
    assert helpers._part_media_resolution(policy, mime_type="application/octet-stream") == "medium"


def test_part_from_bytes_and_frame_parts(monkeypatch: Any, tmp_path: Path) -> None:
    missing_part = helpers._part_from_bytes(
        SimpleNamespace(),
        data=b"abc",
        mime_type="image/jpeg",
        media_resolution="high",
    )
    assert missing_part["media_resolution"] == "high"

    class RetryPart:
        attempts: list[dict[str, Any]] = []

        @classmethod
        def from_bytes(cls, **kwargs: Any) -> dict[str, Any]:
            cls.attempts.append(dict(kwargs))
            if len(cls.attempts) < 2:
                raise RuntimeError("fallback")
            return {"ok": True, **kwargs}

    resolved = helpers._part_from_bytes(
        SimpleNamespace(Part=RetryPart),
        data=b"xyz",
        mime_type="image/png",
        media_resolution="low",
    )
    assert resolved["ok"] is True
    assert len(RetryPart.attempts) == 2

    class AlwaysFailPart:
        @classmethod
        def from_bytes(cls, **_: Any) -> dict[str, Any]:
            raise RuntimeError("still fail")

    fallback = helpers._part_from_bytes(
        SimpleNamespace(Part=AlwaysFailPart),
        data=b"m",
        mime_type="image/png",
        media_resolution="medium",
    )
    assert fallback["mime_type"] == "image/png"

    class EnumPart:
        calls: list[dict[str, Any]] = []

        @classmethod
        def from_bytes(cls, **kwargs: Any) -> dict[str, Any]:
            cls.calls.append(dict(kwargs))
            return {"ok": True, **kwargs}

    class FakeResolutionEnum:
        MEDIA_RESOLUTION_MEDIUM = "MEDIA_RESOLUTION_MEDIUM"

    resolved_enum = helpers._part_from_bytes(
        SimpleNamespace(Part=EnumPart, PartMediaResolutionLevel=FakeResolutionEnum),
        data=b"enum",
        mime_type="image/png",
        media_resolution="medium",
    )
    assert resolved_enum["media_resolution"] == "MEDIA_RESOLUTION_MEDIUM"
    assert EnumPart.calls[0]["media_resolution"] == "MEDIA_RESOLUTION_MEDIUM"

    good = tmp_path / "good.jpg"
    empty = tmp_path / "empty.jpg"
    broken = tmp_path / "broken.jpg"
    good.write_bytes(b"\xff\xd8\xff")
    empty.write_bytes(b"")
    broken.write_bytes(b"\xff\xd8")

    original_read_bytes = Path.read_bytes

    def _patched_read_bytes(self: Path) -> bytes:
        if self.name == "broken.jpg":
            raise OSError("read-failed")
        return original_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", _patched_read_bytes)
    parts = helpers._build_frame_parts(
        SimpleNamespace(Part=RetryPart),
        [str(tmp_path / "missing.jpg"), str(broken), str(empty), str(good)],
        limit=10,
        media_resolution_policy={
            "default": "medium",
            "frame": "high",
            "image": "low",
            "pdf": "low",
        },
    )
    assert len(parts) == 1


def test_thinking_cache_and_tool_builders() -> None:
    class FakeThinkingConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    cfg = helpers._thinking_config(
        SimpleNamespace(ThinkingConfig=FakeThinkingConfig),
        thinking_level="invalid-level",
        include_thoughts=True,
    )
    assert cfg.kwargs["thinking_level"] == "HIGH"
    assert helpers._cache_meta_default()["cache_hit"] is False
    assert helpers._is_cache_error(RuntimeError("")) is False
    assert helpers._is_cache_error(RuntimeError("resource_exhausted")) is True

    assert helpers._build_computer_use_tool(SimpleNamespace()) == {"computer_use": {}}

    class FakeComputerUse:
        pass

    class FakeTool:
        calls: list[dict[str, Any]] = []

        def __init__(self, **kwargs: Any) -> None:
            FakeTool.calls.append(dict(kwargs))
            payload = kwargs.get("computer_use")
            if isinstance(payload, FakeComputerUse):
                raise RuntimeError("no-class-instance")
            if payload == {}:
                raise RuntimeError("no-empty")
            self.payload = payload

    tool = helpers._build_computer_use_tool(
        SimpleNamespace(Tool=FakeTool, ComputerUse=FakeComputerUse)
    )
    assert isinstance(tool, FakeTool)
    assert isinstance(tool.payload, dict)
    assert tool.payload["environment"] == "BROWSER"


def test_execute_computer_use_action_paths() -> None:
    blocked_no_handler = helpers.execute_computer_use_action(
        None,
        args={},
        require_confirmation=False,
        confirmed=False,
        timeout_seconds=0.1,
    )
    assert blocked_no_handler["status"] == "blocked"

    blocked_confirmation = helpers.execute_computer_use_action(
        lambda **_: {"ok": True},
        args={},
        require_confirmation=True,
        confirmed=False,
        timeout_seconds=0.1,
    )
    assert blocked_confirmation["status"] == "blocked"

    timeout = helpers.execute_computer_use_action(
        lambda **_: time.sleep(0.2) or {"ok": True},
        args={},
        require_confirmation=False,
        confirmed=True,
        timeout_seconds=0.001,
    )
    assert timeout["status"] == "failed"
    assert timeout["response"]["error"] == "computer_use_timeout"

    failed = helpers.execute_computer_use_action(
        lambda **_: (_ for _ in ()).throw(RuntimeError("boom")),
        args={},
        require_confirmation=False,
        confirmed=True,
        timeout_seconds=0.1,
    )
    assert failed["status"] == "failed"
    assert failed["response"]["error"] == "computer_use_execution_failed"

    wrapped = helpers.execute_computer_use_action(
        lambda **_: "ok",
        args={},
        require_confirmation=False,
        confirmed=True,
        timeout_seconds=0.1,
    )
    assert wrapped == {"status": "ok", "response": {"result": "ok"}}


def test_function_calls_and_response_building_paths() -> None:
    assert helpers._extract_function_calls(SimpleNamespace(candidates=None)) == []
    response = SimpleNamespace(
        candidates=[
            SimpleNamespace(content=SimpleNamespace(parts="invalid")),
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[
                        {"function_call": {"name": "fn1", "args": ["not-a-dict"]}},
                        SimpleNamespace(function_call=SimpleNamespace(name="", args={"x": 1})),
                    ]
                )
            ),
        ]
    )
    calls = helpers._extract_function_calls(response)
    assert calls == [{"name": "fn1", "args": {}}]

    limited = helpers._execute_function_call(
        {},
        tool_name="computer_use",
        args={},
        computer_use_handler=lambda **_: {"ok": True},
        computer_use_require_confirmation=False,
        computer_use_confirmed=True,
        computer_use_timeout_seconds=0.1,
        computer_use_step_limit=0,
        computer_use_steps_used=0,
    )
    assert limited["status"] == "blocked"

    computer_ok = helpers._execute_function_call(
        {},
        tool_name="computer_use",
        args={"action": "click"},
        computer_use_handler=lambda **_: {"ok": True},
        computer_use_require_confirmation=False,
        computer_use_confirmed=True,
        computer_use_timeout_seconds=0.1,
        computer_use_step_limit=5,
        computer_use_steps_used=1,
    )
    assert computer_ok["status"] == "ok"

    missing_tool = helpers._execute_function_call(
        {},
        tool_name="unknown",
        args={},
        computer_use_handler=None,
        computer_use_require_confirmation=False,
        computer_use_confirmed=True,
        computer_use_timeout_seconds=0.1,
        computer_use_step_limit=1,
        computer_use_steps_used=0,
    )
    assert missing_tool["status"] == "blocked"

    failed_tool = helpers._execute_function_call(
        {"fn": lambda **_: (_ for _ in ()).throw(ValueError("bad"))},
        tool_name="fn",
        args={},
        computer_use_handler=None,
        computer_use_require_confirmation=False,
        computer_use_confirmed=True,
        computer_use_timeout_seconds=0.1,
        computer_use_step_limit=1,
        computer_use_steps_used=0,
    )
    assert failed_tool["status"] == "failed"

    wrapped_tool = helpers._execute_function_call(
        {"fn": lambda **_: "result"},
        tool_name="fn",
        args={},
        computer_use_handler=None,
        computer_use_require_confirmation=False,
        computer_use_confirmed=True,
        computer_use_timeout_seconds=0.1,
        computer_use_step_limit=1,
        computer_use_steps_used=0,
    )
    assert wrapped_tool["response"] == {"result": "result"}

    assert helpers._extract_primary_candidate_content(SimpleNamespace(candidates=[])) is None
    content = SimpleNamespace(parts=["x"])
    assert (
        helpers._extract_primary_candidate_content(
            SimpleNamespace(candidates=[SimpleNamespace(content=content)])
        )
        is content
    )

    part = helpers._build_function_response_part(SimpleNamespace(), name="fn", payload={"x": 1})
    assert "function_response" in part

    class FailingPart:
        @staticmethod
        def from_function_response(**_: Any) -> dict[str, Any]:
            raise RuntimeError("cannot build")

    fallback_part = helpers._build_function_response_part(
        SimpleNamespace(Part=FailingPart), name="fn", payload={"x": 1}
    )
    assert fallback_part["function_response"]["name"] == "fn"

    class ContentWithFallbackRole:
        def __init__(self, *, role: str, parts: list[Any]) -> None:
            if role == "tool":
                raise RuntimeError("reject-tool")
            self.role = role
            self.parts = parts

    built_content = helpers._build_function_response_content(
        SimpleNamespace(Content=ContentWithFallbackRole),
        [{"name": "fn", "response": {"ok": True}}],
    )
    assert built_content.role == "user"

    class AlwaysFailContent:
        def __init__(self, **_: Any) -> None:
            raise RuntimeError("always-fail")

    dict_content = helpers._build_function_response_content(
        SimpleNamespace(Content=AlwaysFailContent),
        [{"name": "fn", "response": {"ok": True}}],
    )
    assert dict_content["role"] == "tool"


def test_thought_metadata_finish_reason_safety_and_exception_classification() -> None:
    thought_bytes = SimpleNamespace(thought=True, signature=b"\x0f")
    thought_string = SimpleNamespace(thought=True, thought_signature="sig-B")
    thought_text = SimpleNamespace(thought=True, text="fallback-thought")
    metadata = helpers._collect_thought_metadata(
        SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    content=SimpleNamespace(parts=[thought_bytes, thought_string, thought_text])
                )
            ],
            usage_metadata=SimpleNamespace(
                prompt_token_count=1,
                candidates_token_count=2,
                total_token_count=3,
                thoughts_token_count=4,
                ignored="x",
            ),
        )
    )
    assert metadata["thought_count"] == 3
    assert len(metadata["thought_signatures"]) == 3
    assert metadata["usage"]["total_token_count"] == 3
    assert metadata["thought_signature_digest"] is not None

    assert (
        helpers._extract_finish_reason(SimpleNamespace(candidates=[{"finish_reason": " STOP "}]))
        == "STOP"
    )
    assert helpers._extract_finish_reason(SimpleNamespace(candidates=[])) is None

    assert (
        helpers._response_is_safety_blocked(
            SimpleNamespace(candidates=[SimpleNamespace(finish_reason="SAFETY")])
        )
        is True
    )
    assert (
        helpers._response_is_safety_blocked(
            SimpleNamespace(candidates=[{"finish_reason": "STOP", "safety_ratings": [{"x": 1}]}])
        )
        is True
    )
    assert (
        helpers._response_is_safety_blocked(
            SimpleNamespace(candidates=[{"finish_reason": "STOP", "safety_ratings": []}])
        )
        is False
    )

    assert (
        helpers.classify_gemini_exception(RuntimeError("api key forbidden status=403"))[0]
        == "llm_auth_error"
    )
    assert (
        helpers.classify_gemini_exception(RuntimeError("quota exceeded"))[0] == "llm_quota_exceeded"
    )
    assert (
        helpers.classify_gemini_exception(RuntimeError("rate limit 429"))[0] == "llm_rate_limited"
    )
    assert (
        helpers.classify_gemini_exception(RuntimeError("safety blocked"))[0] == "llm_safety_blocked"
    )
    assert (
        helpers.classify_gemini_exception(RuntimeError("invalid argument bad request 400"))[0]
        == "llm_invalid_request"
    )
    assert helpers.classify_gemini_exception(RuntimeError("deadline timeout"))[0] == "llm_timeout"
    assert helpers.classify_gemini_exception(RuntimeError("internal 500"))[0] == "llm_upstream_5xx"
    assert (
        helpers.classify_gemini_exception(RuntimeError("network dns connection"))[0]
        == "llm_transport_error"
    )
    assert helpers.classify_gemini_exception(RuntimeError("unexpected"))[0] == "llm_unknown_error"


def test_collect_thought_metadata_skips_non_list_parts() -> None:
    metadata = helpers._collect_thought_metadata(
        SimpleNamespace(
            candidates=[
                SimpleNamespace(content=SimpleNamespace(parts="invalid")),
                SimpleNamespace(content=SimpleNamespace(parts=[])),
            ],
            usage_metadata=SimpleNamespace(total_token_count=1),
        )
    )
    assert metadata["thought_count"] == 0
    assert metadata["thought_signatures"] == []
