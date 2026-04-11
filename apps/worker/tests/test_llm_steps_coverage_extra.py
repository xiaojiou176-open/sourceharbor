from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from worker.config import Settings
from worker.pipeline.steps import llm_steps


def _settings(tmp_path: Path, **kwargs: Any) -> Settings:
    return Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifacts").resolve()),
        **kwargs,
    )


def _ctx(tmp_path: Path, **kwargs: Any) -> SimpleNamespace:
    return SimpleNamespace(settings=_settings(tmp_path, **kwargs))


def _outline_payload() -> dict[str, Any]:
    return {
        "title": "Outline Title",
        "tldr": ["Summary line"],
        "highlights": ["High value highlight sentence"],
        "recommended_actions": ["Do action A"],
        "risk_or_pitfalls": ["Risk A"],
        "chapters": [
            {
                "chapter_no": 1,
                "title": "Chapter One",
                "anchor": "chapter-one",
                "start_s": 0,
                "end_s": 30,
                "summary": "Chapter summary with enough semantic content",
                "bullets": ["Bullet with enough semantic length"],
                "key_terms": [],
                "code_snippets": [],
            }
        ],
        "timestamp_references": [],
    }


def _digest_payload() -> dict[str, Any]:
    return {
        "title": "Digest Title",
        "summary": "Digest summary with enough semantic content.",
        "tldr": ["TLDR line"],
        "highlights": ["Digest highlight with enough semantic content."],
        "action_items": ["Action one"],
        "code_blocks": [],
        "timestamp_references": [],
        "fallback_notes": [],
    }


def _base_state() -> dict[str, Any]:
    return {
        "content_type": "article",
        "metadata": {"title": "Demo"},
        "title": "Demo",
        "transcript": "transcript",
        "comments": {"top_comments": []},
        "frames": [],
        "media_path": "",
        "source_url": "https://www.youtube.com/watch?v=demo",
        "llm_input_mode": "text",
        "llm_policy": {},
    }


def test_unpack_and_signature_checks_and_provider_resolution(tmp_path: Path) -> None:
    legacy_text, legacy_mode, legacy_meta = llm_steps._unpack_gemini_result(("ok", "text"))
    assert legacy_text == "ok"
    assert legacy_mode == "text"
    assert legacy_meta["thinking"]["thought_signatures"] == ["legacy-signature-placeholder"]

    text, mode, meta = llm_steps._unpack_gemini_result(("ok", "text", None))
    assert text == "ok"
    assert mode == "text"
    assert meta == {}

    assert llm_steps._ensure_thought_signatures({}) == (
        False,
        "llm_thoughts_required:missing_thinking_metadata",
    )
    assert llm_steps._ensure_thought_signatures({"thinking": {"include_thoughts": False}}) == (
        False,
        "llm_thoughts_required:include_thoughts_must_be_true",
    )
    assert llm_steps._ensure_thought_signatures(
        {"thinking": {"include_thoughts": True, "thought_signatures": ["", " "]}}
    ) == (False, "llm_thoughts_required:missing_thought_signatures")
    assert llm_steps._ensure_thought_signatures(
        {"thinking": {"include_thoughts": True, "thought_signatures": ["sig"]}}
    ) == (True, "")

    no_key_reason, no_key_detail, no_key_kind = llm_steps._resolve_provider_failure(
        _settings(tmp_path, gemini_api_key=None),
        {},
    )
    assert no_key_reason == "gemini_api_key_missing"
    assert no_key_detail == "gemini_api_key_missing"
    assert no_key_kind == "auth"

    with_key_reason, with_key_detail, with_key_kind = llm_steps._resolve_provider_failure(
        _settings(tmp_path, gemini_api_key="k"),
        {"error_code": "x", "error_detail": "y", "error_kind": "z"},
    )
    assert with_key_reason == "x"
    assert with_key_detail == "y"
    assert with_key_kind == "z"


def test_translate_payload_to_chinese_paths(monkeypatch: Any, tmp_path: Path) -> None:
    settings = _settings(tmp_path, gemini_api_key="k")
    payload = _outline_payload()

    monkeypatch.setattr(
        llm_steps,
        "gemini_generate",
        lambda *args, **kwargs: (None, "text", {}),
    )
    assert (
        llm_steps._translate_payload_to_chinese(
            settings,
            payload,
            model="m",
            max_output_tokens=128,
            schema_label="outline",
            thinking_level="high",
        )
        is None
    )

    monkeypatch.setattr(
        llm_steps,
        "gemini_generate",
        lambda *args, **kwargs: ("not-json", "text", {}),
    )
    assert (
        llm_steps._translate_payload_to_chinese(
            settings,
            payload,
            model="m",
            max_output_tokens=128,
            schema_label="digest",
            thinking_level="high",
        )
        is None
    )

    monkeypatch.setattr(
        llm_steps,
        "gemini_generate",
        lambda *args, **kwargs: ("[]", "text", {}),
    )
    assert (
        llm_steps._translate_payload_to_chinese(
            settings,
            payload,
            model="m",
            max_output_tokens=128,
            schema_label="outline",
            thinking_level="high",
        )
        is None
    )

    translated_payload = {"title": "已翻译"}
    monkeypatch.setattr(
        llm_steps,
        "gemini_generate",
        lambda *args, **kwargs: (json.dumps(translated_payload), "text", {}),
    )
    assert (
        llm_steps._translate_payload_to_chinese(
            settings,
            payload,
            model="m",
            max_output_tokens=128,
            schema_label="digest",
            thinking_level="high",
        )
        == translated_payload
    )


def test_computer_use_options_injects_default_handler(monkeypatch: Any, tmp_path: Path) -> None:
    sentinel = {"handler": "ok"}
    monkeypatch.setattr(
        llm_steps,
        "build_computer_use_options",
        lambda *_: {"enable_computer_use": True},
    )
    monkeypatch.setattr(
        llm_steps,
        "build_default_computer_use_handler",
        lambda **_: sentinel,
    )
    options = llm_steps._computer_use_options(_ctx(tmp_path), _base_state(), {}, {})
    assert options["computer_use_handler"] is sentinel


def test_step_llm_outline_branches(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(llm_steps, "build_outline_prompt", lambda **_: "prompt")
    monkeypatch.setattr(llm_steps, "frame_paths_from_frames", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(llm_steps, "_computer_use_options", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(llm_steps, "_thinking_level_from_policy", lambda *_args, **_kwargs: "high")
    monkeypatch.setattr(llm_steps, "_media_resolution_from_policy", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(llm_steps, "_max_function_call_rounds", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(llm_steps, "should_include_frame_prompt", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(llm_steps, "_outline_quality_ok", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(llm_steps, "normalize_outline_payload", lambda parsed, _state: parsed)

    state = _base_state()
    ctx = _ctx(tmp_path, gemini_api_key="k")

    monkeypatch.setattr(llm_steps, "_include_thoughts_from_policy", lambda *_args, **_kwargs: False)
    execution = asyncio.run(
        llm_steps.step_llm_outline(
            ctx,
            state,
            gemini_generate_fn=lambda *_args, **_kwargs: (
                json.dumps(_outline_payload()),
                "text",
                {"thinking": {"include_thoughts": True, "thought_signatures": ["sig"]}},
            ),
        )
    )
    assert execution.reason == "llm_thoughts_required"

    monkeypatch.setattr(llm_steps, "_include_thoughts_from_policy", lambda *_args, **_kwargs: True)
    execution = asyncio.run(
        llm_steps.step_llm_outline(
            ctx,
            state,
            gemini_generate_fn=lambda *_args, **_kwargs: (
                "[]",
                "text",
                {"thinking": {"include_thoughts": True, "thought_signatures": ["sig"]}},
            ),
        )
    )
    assert execution.reason == "llm_output_invalid_json"

    monkeypatch.setattr(llm_steps, "outline_is_chinese", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        llm_steps, "_translate_payload_to_chinese", lambda *_args, **_kwargs: {"title": "x"}
    )
    execution = asyncio.run(
        llm_steps.step_llm_outline(
            ctx,
            state,
            gemini_generate_fn=lambda *_args, **_kwargs: (
                json.dumps(_outline_payload()),
                "text",
                {"thinking": {"include_thoughts": True, "thought_signatures": ["sig"]}},
            ),
        )
    )
    assert execution.reason == "llm_translation_failed"

    monkeypatch.setattr(
        llm_steps, "_translate_payload_to_chinese", lambda *_args, **_kwargs: _outline_payload()
    )
    execution = asyncio.run(
        llm_steps.step_llm_outline(
            ctx,
            state,
            gemini_generate_fn=lambda *_args, **_kwargs: (
                json.dumps(_outline_payload()),
                "text",
                {"thinking": {"include_thoughts": True, "thought_signatures": ["sig"]}},
            ),
        )
    )
    assert execution.reason == "llm_output_not_chinese"


def test_step_llm_digest_branches(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(llm_steps, "build_digest_prompt", lambda **_: "prompt")
    monkeypatch.setattr(llm_steps, "frame_paths_from_frames", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(llm_steps, "_computer_use_options", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(llm_steps, "_thinking_level_from_policy", lambda *_args, **_kwargs: "high")
    monkeypatch.setattr(llm_steps, "_media_resolution_from_policy", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(llm_steps, "_max_function_call_rounds", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(llm_steps, "should_include_frame_prompt", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(llm_steps, "_digest_quality_ok", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(llm_steps, "normalize_outline_payload", lambda parsed, _state: parsed)
    monkeypatch.setattr(llm_steps, "normalize_digest_payload", lambda parsed, _state: parsed)

    state = _base_state()
    state["outline"] = _outline_payload()
    ctx = _ctx(tmp_path, gemini_api_key="k")

    monkeypatch.setattr(llm_steps, "_include_thoughts_from_policy", lambda *_args, **_kwargs: False)
    execution = asyncio.run(
        llm_steps.step_llm_digest(
            ctx,
            state,
            gemini_generate_fn=lambda *_args, **_kwargs: (
                json.dumps(_digest_payload()),
                "text",
                {"thinking": {"include_thoughts": True, "thought_signatures": ["sig"]}},
            ),
        )
    )
    assert execution.reason == "llm_thoughts_required"

    monkeypatch.setattr(llm_steps, "_include_thoughts_from_policy", lambda *_args, **_kwargs: True)
    execution = asyncio.run(
        llm_steps.step_llm_digest(
            ctx,
            state,
            gemini_generate_fn=lambda *_args, **_kwargs: (
                "[]",
                "text",
                {"thinking": {"include_thoughts": True, "thought_signatures": ["sig"]}},
            ),
        )
    )
    assert execution.reason == "llm_output_invalid_json"

    monkeypatch.setattr(llm_steps, "digest_is_chinese", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        llm_steps, "_translate_payload_to_chinese", lambda *_args, **_kwargs: {"title": "x"}
    )
    execution = asyncio.run(
        llm_steps.step_llm_digest(
            ctx,
            state,
            gemini_generate_fn=lambda *_args, **_kwargs: (
                json.dumps(_digest_payload()),
                "text",
                {"thinking": {"include_thoughts": True, "thought_signatures": ["sig"]}},
            ),
        )
    )
    assert execution.reason == "llm_translation_failed"

    monkeypatch.setattr(
        llm_steps, "_translate_payload_to_chinese", lambda *_args, **_kwargs: _digest_payload()
    )
    execution = asyncio.run(
        llm_steps.step_llm_digest(
            ctx,
            state,
            gemini_generate_fn=lambda *_args, **_kwargs: (
                json.dumps(_digest_payload()),
                "text",
                {"thinking": {"include_thoughts": True, "thought_signatures": ["sig"]}},
            ),
        )
    )
    assert execution.reason == "llm_output_not_chinese"


def test_step_llm_outline_missing_thought_signatures(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(llm_steps, "build_outline_prompt", lambda **_: "prompt")
    monkeypatch.setattr(llm_steps, "frame_paths_from_frames", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(llm_steps, "_computer_use_options", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(llm_steps, "_thinking_level_from_policy", lambda *_args, **_kwargs: "high")
    monkeypatch.setattr(llm_steps, "_media_resolution_from_policy", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(llm_steps, "_max_function_call_rounds", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(llm_steps, "should_include_frame_prompt", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(llm_steps, "_include_thoughts_from_policy", lambda *_args, **_kwargs: True)

    execution = asyncio.run(
        llm_steps.step_llm_outline(
            _ctx(tmp_path, gemini_api_key="k"),
            _base_state(),
            gemini_generate_fn=lambda *_args, **_kwargs: (
                json.dumps(_outline_payload()),
                "text",
                {"thinking": {"include_thoughts": True, "thought_signatures": []}},
            ),
        )
    )
    assert execution.reason == "llm_thoughts_required"
    assert execution.error == "llm_thoughts_required:missing_thought_signatures"


def test_step_llm_digest_failure_and_success_paths(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(llm_steps, "build_digest_prompt", lambda **_: "prompt")
    monkeypatch.setattr(llm_steps, "frame_paths_from_frames", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(llm_steps, "_computer_use_options", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(llm_steps, "_thinking_level_from_policy", lambda *_args, **_kwargs: "high")
    monkeypatch.setattr(llm_steps, "_media_resolution_from_policy", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(llm_steps, "_max_function_call_rounds", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(llm_steps, "should_include_frame_prompt", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(llm_steps, "_include_thoughts_from_policy", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(llm_steps, "_digest_quality_ok", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(llm_steps, "normalize_outline_payload", lambda parsed, _state: parsed)
    monkeypatch.setattr(llm_steps, "normalize_digest_payload", lambda parsed, _state: dict(parsed))
    monkeypatch.setattr(llm_steps, "utc_now_iso", lambda: "2026-03-08T00:00:00Z")

    state = _base_state()
    state["outline"] = _outline_payload()
    ctx = _ctx(tmp_path, gemini_api_key="k")

    provider_failure = asyncio.run(
        llm_steps.step_llm_digest(
            ctx,
            state,
            gemini_generate_fn=lambda *_args, **_kwargs: (
                None,
                "text",
                {
                    "error_code": "llm_provider_unavailable",
                    "error_detail": "down",
                    "error_kind": "runtime",
                },
            ),
        )
    )
    assert provider_failure.reason == "llm_provider_unavailable"
    assert provider_failure.error == "down"

    signature_failure = asyncio.run(
        llm_steps.step_llm_digest(
            ctx,
            state,
            gemini_generate_fn=lambda *_args, **_kwargs: (
                json.dumps(_digest_payload()),
                "text",
                {"thinking": {"include_thoughts": True, "thought_signatures": []}},
            ),
        )
    )
    assert signature_failure.reason == "llm_thoughts_required"

    monkeypatch.setattr(llm_steps, "digest_is_chinese", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(llm_steps, "_translate_payload_to_chinese", lambda *_args, **_kwargs: None)
    translation_failure = asyncio.run(
        llm_steps.step_llm_digest(
            ctx,
            state,
            gemini_generate_fn=lambda *_args, **_kwargs: (
                json.dumps(_digest_payload()),
                "text",
                {"thinking": {"include_thoughts": True, "thought_signatures": ["sig"]}},
            ),
        )
    )
    assert translation_failure.reason == "llm_translation_failed"

    monkeypatch.setattr(llm_steps, "digest_is_chinese", lambda *_args, **_kwargs: True)
    success = asyncio.run(
        llm_steps.step_llm_digest(
            ctx,
            state,
            gemini_generate_fn=lambda *_args, **_kwargs: (
                json.dumps(_digest_payload()),
                "text",
                {"thinking": {"include_thoughts": True, "thought_signatures": ["sig"]}},
            ),
        )
    )
    assert success.status == "succeeded"
    assert success.state_updates["digest"]["generated_by"] == "gemini"
    assert success.state_updates["digest"]["generated_at"] == "2026-03-08T00:00:00Z"


def test_step_llm_outline_advanced_video_preprocess_uses_fast_text_mode(
    monkeypatch: Any, tmp_path: Path
) -> None:
    calls: list[dict[str, Any]] = []

    monkeypatch.setattr(llm_steps, "build_outline_prompt", lambda **_: "outline-prompt")
    monkeypatch.setattr(llm_steps, "frame_paths_from_frames", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(llm_steps, "_computer_use_options", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(llm_steps, "_thinking_level_from_policy", lambda *_args, **_kwargs: "high")
    monkeypatch.setattr(llm_steps, "_media_resolution_from_policy", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(llm_steps, "_max_function_call_rounds", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(llm_steps, "should_include_frame_prompt", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(llm_steps, "_include_thoughts_from_policy", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(llm_steps, "_outline_quality_ok", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(llm_steps, "outline_is_chinese", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(llm_steps, "normalize_outline_payload", lambda parsed, _state: dict(parsed))
    monkeypatch.setattr(llm_steps, "utc_now_iso", lambda: "2026-04-11T00:00:00Z")

    def _fake_generate(*_args: Any, **kwargs: Any) -> tuple[str, str, dict[str, Any]]:
        calls.append(dict(kwargs))
        return (
            json.dumps(_outline_payload()),
            "text",
            {"thinking": {"include_thoughts": True, "thought_signatures": ["sig-outline"]}},
        )

    state = _base_state()
    state.update(
        {
            "content_type": "video",
            "media_path": str((tmp_path / "video.mp4").resolve()),
            "llm_policy": {
                "analysis_mode": "advanced",
                "raw_stage": {
                    "analysis_mode": "advanced",
                    "preprocess_enabled": True,
                    "preprocess_model": "gemini-fast-preprocess",
                    "preprocess_input_mode": "text",
                    "video_first": True,
                    "video_input_required": True,
                    "review_required": True,
                    "review_input_mode": "video_text",
                },
            },
        }
    )
    ctx = _ctx(tmp_path, gemini_api_key="k")

    execution = asyncio.run(
        llm_steps.step_llm_outline(ctx, state, gemini_generate_fn=_fake_generate)
    )

    assert execution.status == "succeeded"
    assert calls[0]["llm_input_mode"] == "text"
    assert calls[0]["model"] == "gemini-fast-preprocess"
    assert calls[0]["media_path"] == ""
    assert execution.state_updates["raw_stage_contract"]["preprocess_enabled"] is True
    assert execution.state_updates["raw_stage_contract"]["preprocess_input_mode"] == "text"


def test_step_llm_digest_video_contract_runs_advanced_review_and_records_receipt(
    monkeypatch: Any, tmp_path: Path
) -> None:
    calls: list[dict[str, Any]] = []

    monkeypatch.setattr(llm_steps, "build_digest_prompt", lambda **_: "digest-prompt")
    monkeypatch.setattr(llm_steps, "build_digest_review_prompt", lambda **_: "digest-review-prompt")
    monkeypatch.setattr(llm_steps, "frame_paths_from_frames", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(llm_steps, "_computer_use_options", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(llm_steps, "_thinking_level_from_policy", lambda *_args, **_kwargs: "high")
    monkeypatch.setattr(llm_steps, "_media_resolution_from_policy", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(llm_steps, "_max_function_call_rounds", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(llm_steps, "should_include_frame_prompt", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(llm_steps, "_include_thoughts_from_policy", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(llm_steps, "_digest_quality_ok", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(llm_steps, "digest_is_chinese", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(llm_steps, "normalize_outline_payload", lambda parsed, _state: dict(parsed))
    monkeypatch.setattr(llm_steps, "normalize_digest_payload", lambda parsed, _state: dict(parsed))
    monkeypatch.setattr(llm_steps, "utc_now_iso", lambda: "2026-04-11T00:00:00Z")

    def _fake_generate(*_args: Any, **kwargs: Any) -> tuple[str, str, dict[str, Any]]:
        calls.append(dict(kwargs))
        return (
            json.dumps(_digest_payload()),
            "video_text",
            {
                "thinking": {
                    "include_thoughts": True,
                    "thought_signatures": [f"sig-{len(calls)}"],
                }
            },
        )

    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"video")
    state = _base_state()
    state.update(
        {
            "content_type": "video",
            "outline": _outline_payload(),
            "media_path": str(video_path.resolve()),
            "llm_policy": {
                "analysis_mode": "advanced",
                "raw_stage": {
                    "analysis_mode": "advanced",
                    "video_first": True,
                    "video_input_required": True,
                    "review_required": True,
                    "review_model": "gemini-review-pro",
                    "review_input_mode": "video_text",
                    "primary_input_mode": "video_text",
                },
            },
        }
    )
    ctx = _ctx(tmp_path, gemini_api_key="k")

    execution = asyncio.run(
        llm_steps.step_llm_digest(ctx, state, gemini_generate_fn=_fake_generate)
    )

    assert execution.status == "succeeded"
    assert len(calls) == 2
    assert calls[0]["llm_input_mode"] == "video_text"
    assert calls[1]["model"] == "gemini-review-pro"
    assert execution.output["review_required"] is True
    assert execution.output["review_completed"] is True
    assert execution.state_updates["raw_stage_contract"]["video_contract_satisfied"] is True
    assert execution.state_updates["raw_stage_contract"]["primary_media_input"] == "video_text"
    assert execution.state_updates["raw_stage_contract"]["review_media_input"] == "video_text"


def test_step_llm_digest_video_contract_fail_closes_on_frames_fallback(
    monkeypatch: Any, tmp_path: Path
) -> None:
    monkeypatch.setattr(llm_steps, "build_digest_prompt", lambda **_: "digest-prompt")
    monkeypatch.setattr(llm_steps, "frame_paths_from_frames", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(llm_steps, "_computer_use_options", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(llm_steps, "_thinking_level_from_policy", lambda *_args, **_kwargs: "high")
    monkeypatch.setattr(llm_steps, "_media_resolution_from_policy", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(llm_steps, "_max_function_call_rounds", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(llm_steps, "should_include_frame_prompt", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(llm_steps, "_include_thoughts_from_policy", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(llm_steps, "_digest_quality_ok", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(llm_steps, "digest_is_chinese", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(llm_steps, "normalize_outline_payload", lambda parsed, _state: dict(parsed))
    monkeypatch.setattr(llm_steps, "normalize_digest_payload", lambda parsed, _state: dict(parsed))

    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"video")
    state = _base_state()
    state.update(
        {
            "content_type": "video",
            "outline": _outline_payload(),
            "media_path": str(video_path.resolve()),
            "llm_policy": {
                "analysis_mode": "economy",
                "raw_stage": {
                    "analysis_mode": "economy",
                    "video_first": True,
                    "video_input_required": True,
                    "review_required": False,
                    "primary_input_mode": "video_text",
                },
            },
        }
    )
    ctx = _ctx(tmp_path, gemini_api_key="k")

    execution = asyncio.run(
        llm_steps.step_llm_digest(
            ctx,
            state,
            gemini_generate_fn=lambda *_args, **_kwargs: (
                json.dumps(_digest_payload()),
                "frames_text",
                {"thinking": {"include_thoughts": True, "thought_signatures": ["sig"]}},
            ),
        )
    )

    assert execution.status == "failed"
    assert execution.reason == "video_body_input_required"
    assert execution.output["contract_fail_close"] is True
