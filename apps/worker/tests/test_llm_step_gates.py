from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from apps.worker.worker.pipeline.steps import llm_step_gates as gates


def _ctx(*, include_thoughts: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        settings=SimpleNamespace(
            gemini_include_thoughts=include_thoughts,
            gemini_computer_use_enabled=False,
            gemini_computer_use_require_confirmation=True,
            gemini_computer_use_max_steps=3,
            gemini_computer_use_timeout_seconds=1.5,
        )
    )


def _fresh_gates() -> object:
    return importlib.reload(
        importlib.import_module("apps.worker.worker.pipeline.steps.llm_step_gates")
    )


def test_semantic_len_and_outline_quality_gate() -> None:
    assert gates._semantic_len(" 你好, A-1 ! ") == 4
    assert gates._semantic_len(None) == 0  # type: ignore[arg-type]
    assert gates._semantic_len("\u4e00\u9fff") == 2
    assert gates._has_meaningful_line(["1234567", "12345678"], min_len=8) is True
    assert gates._has_meaningful_line(["1234567"], min_len=8) is False

    assert (
        gates._outline_quality_ok(
            {"highlights": ["short"], "chapters": [{"summary": "valid summary"}]}
        )
        is False
    )
    assert (
        gates._outline_quality_ok({"highlights": ["meaningful highlight"], "chapters": []}) is False
    )
    assert (
        gates._outline_quality_ok(
            {
                "highlights": ["meaningful highlight"],
                "chapters": [{"summary": "tiny", "bullets": ["mini"]}],
            }
        )
        is False
    )
    assert (
        gates._outline_quality_ok(
            {
                "highlights": ["非常有信息量的重点内容"],
                "chapters": ["invalid", {"summary": "", "bullets": ["long enough bullet"]}],
            }
        )
        is True
    )
    assert (
        gates._outline_quality_ok(
            {"highlights": ["12345678"], "chapters": [{"summary": "1234567890"}]}
        )
        is True
    )
    assert (
        gates._outline_quality_ok(
            {"highlights": ["12345678"], "chapters": [{"summary": "tiny", "bullets": ["12345678"]}]}
        )
        is True
    )
    assert gates._outline_quality_ok({"highlights": ["12345678"], "chapters": ({},)}) is False


def test_digest_quality_gate_requires_summary_and_highlights() -> None:
    assert (
        gates._digest_quality_ok({"summary": "too short", "highlights": ["long enough highlight"]})
        is False
    )
    assert (
        gates._digest_quality_ok(
            {"summary": "this summary has enough semantic length", "highlights": ["short"]}
        )
        is False
    )
    assert (
        gates._digest_quality_ok(
            {
                "summary": "this summary has enough semantic length",
                "highlights": ["this highlight is long enough"],
            }
        )
        is True
    )
    assert (
        gates._digest_quality_ok({"summary": "12345678901234567890", "highlights": ["12345678"]})
        is True
    )
    assert (
        gates._digest_quality_ok({"summary": "1234567890123456789", "highlights": ["12345678"]})
        is False
    )


@pytest.mark.parametrize("chapters", [None, [], ({},)])
def test_outline_quality_rejects_missing_or_non_list_chapters(chapters: object) -> None:
    assert gates._outline_quality_ok({"highlights": ["12345678"], "chapters": chapters}) is False


def test_outline_quality_rejects_truthy_non_iterable_chapters() -> None:
    assert gates._outline_quality_ok({"highlights": ["12345678"], "chapters": 1}) is False
    assert (
        gates._outline_quality_ok(
            {"highlights": ["12345678"], "chapters": ({"summary": "1234567890"},)}
        )
        is False
    )


def test_digest_quality_uses_eight_character_highlight_threshold() -> None:
    assert (
        gates._digest_quality_ok({"summary": "12345678901234567890", "highlights": ["1234567"]})
        is False
    )
    assert (
        gates._digest_quality_ok({"summary": "12345678901234567890", "highlights": ["12345678"]})
        is True
    )


def test_thinking_level_bool_and_include_thoughts_policy() -> None:
    g = _fresh_gates()
    assert g._thinking_level_from_policy({"thinking_level": "minimal"}) == "low"
    assert g._thinking_level_from_policy({"speed_priority": True}) == "low"
    assert g._thinking_level_from_policy({"thinking_level": "medium"}) == "medium"
    assert g._thinking_level_from_policy({}) == "high"
    assert g._thinking_level_from_policy({"thinking_level": "unknown"}) == "high"

    assert g._coerce_bool("1", default=False) is True
    assert g._coerce_bool("true", default=False) is True
    assert g._coerce_bool("yes", default=False) is True
    assert g._coerce_bool("on", default=False) is True
    assert g._coerce_bool("y", default=False) is True
    assert g._coerce_bool("0", default=True) is False
    assert g._coerce_bool("false", default=True) is False
    assert g._coerce_bool("no", default=True) is False
    assert g._coerce_bool("off", default=True) is False
    assert g._coerce_bool("n", default=True) is False
    assert g._coerce_bool(None, default=False) is False
    assert g._coerce_bool("maybe", default=True) is True

    ctx = _ctx(include_thoughts=True)
    assert g._include_thoughts_from_policy(ctx, {}, {"include_thoughts": "0"}) is False
    assert g._include_thoughts_from_policy(ctx, {"include_thoughts": "1"}, {}) is True
    assert g._include_thoughts_from_policy(ctx, {"include_thoughts": "0"}, {}) is False
    assert g._include_thoughts_from_policy(ctx, {"include_thoughts": "unknown"}, {}) is True
    assert g._include_thoughts_from_policy(_ctx(include_thoughts=False), {}, {}) is False


def test_thinking_level_prefers_explicit_setting_over_speed_priority() -> None:
    g = _fresh_gates()
    assert (
        g._thinking_level_from_policy({"thinking_level": "low", "speed_priority": False}) == "low"
    )
    assert (
        g._thinking_level_from_policy({"thinking_level": "medium", "speed_priority": True})
        == "medium"
    )
    assert (
        g._thinking_level_from_policy({"thinking_level": "high", "speed_priority": True}) == "high"
    )
    assert g._thinking_level_from_policy({"thinking_level": "   ", "speed_priority": True}) == "low"
    assert (
        g._thinking_level_from_policy({"thinking_level": "   ", "speed_priority": False}) == "high"
    )


def test_include_thoughts_uses_llm_policy_when_section_missing() -> None:
    g = _fresh_gates()
    ctx = _ctx(include_thoughts=False)

    assert g._include_thoughts_from_policy(ctx, {"include_thoughts": "1"}, {}) is True
    assert g._include_thoughts_from_policy(ctx, {"include_thoughts": "0"}, {}) is False
    assert g._include_thoughts_from_policy(ctx, {}, {"include_thoughts": "unknown"}) is False


def test_media_resolution_rounds_and_computer_use_options() -> None:
    g = _fresh_gates()
    raw_resolution = {"default": "high", "frames": "ultra"}
    normalized = g._media_resolution_from_policy({}, {"media_resolution": raw_resolution})
    assert normalized == raw_resolution
    assert normalized is not raw_resolution
    assert g._media_resolution_from_policy({"media_resolution": " HIGH "}, {}) == {
        "default": "high"
    }
    assert g._media_resolution_from_policy({}, {}) == {}

    assert g._max_function_call_rounds({"max_function_call_rounds": -2}, {}) == 0
    assert g._max_function_call_rounds({}, {"max_function_call_rounds": "3"}) == 3
    assert g._max_function_call_rounds({}, {}) == 2
    assert (
        g._max_function_call_rounds(
            {"max_function_call_rounds": 9}, {"max_function_call_rounds": "2"}
        )
        == 2
    )

    options = g.build_computer_use_options(
        _ctx(),
        {
            "enable_computer_use": "1",
            "computer_use_require_confirmation": "0",
            "computer_use_max_steps": "-4",
            "computer_use_timeout_seconds": "0",
        },
        {},
    )
    assert options == {
        "enable_computer_use": False,
        "computer_use_require_confirmation": False,
        "computer_use_max_steps": 0,
        "computer_use_timeout_seconds": 1.5,
    }

    enabled_ctx = SimpleNamespace(
        settings=SimpleNamespace(
            gemini_include_thoughts=True,
            gemini_computer_use_enabled=True,
            gemini_computer_use_require_confirmation=True,
            gemini_computer_use_max_steps=3,
            gemini_computer_use_timeout_seconds=1.5,
        )
    )
    enabled_options = g.build_computer_use_options(
        enabled_ctx,
        {"enable_computer_use": "1"},
        {},
    )
    assert enabled_options["enable_computer_use"] is True

    clamped = g.build_computer_use_options(
        _ctx(),
        {"computer_use_timeout_seconds": "-1"},
        {},
    )
    assert clamped["computer_use_timeout_seconds"] == 0.1


def test_media_resolution_string_returns_exact_default_key() -> None:
    g = _fresh_gates()
    payload = g._media_resolution_from_policy({"media_resolution": " HIGH "}, {})

    assert payload == {"default": "high"}
    assert set(payload) == {"default"}


def test_max_function_call_rounds_defaults_and_none_override_behavior() -> None:
    g = _fresh_gates()

    assert g._max_function_call_rounds({}, {}) == 2
    assert g._max_function_call_rounds({"max_function_call_rounds": None}, {}) == 2
    assert g._max_function_call_rounds({"max_function_call_rounds": "invalid"}, {}) == 2
    assert (
        g._max_function_call_rounds(
            {"max_function_call_rounds": 9}, {"max_function_call_rounds": None}
        )
        == 2
    )
    assert (
        g._max_function_call_rounds(
            {"max_function_call_rounds": 9}, {"max_function_call_rounds": "invalid"}
        )
        == 2
    )


def test_computer_use_options_follow_defaults_and_llm_policy_values() -> None:
    g = _fresh_gates()
    default_ctx = SimpleNamespace(
        settings=SimpleNamespace(
            gemini_include_thoughts=True,
            gemini_computer_use_enabled=True,
            gemini_computer_use_require_confirmation=False,
            gemini_computer_use_max_steps=0,
            gemini_computer_use_timeout_seconds=0.05,
        )
    )
    default_options = g.build_computer_use_options(default_ctx, {}, {})
    assert default_options == {
        "enable_computer_use": True,
        "computer_use_require_confirmation": False,
        "computer_use_max_steps": 0,
        "computer_use_timeout_seconds": 0.1,
    }

    llm_policy_options = g.build_computer_use_options(
        default_ctx,
        {
            "enable_computer_use": "0",
            "computer_use_require_confirmation": "1",
            "computer_use_max_steps": "7",
            "computer_use_timeout_seconds": "2.5",
        },
        {},
    )
    assert llm_policy_options == {
        "enable_computer_use": False,
        "computer_use_require_confirmation": True,
        "computer_use_max_steps": 7,
        "computer_use_timeout_seconds": 2.5,
    }


def test_computer_use_options_fall_back_to_llm_policy_when_section_omits_values() -> None:
    g = _fresh_gates()
    default_ctx = SimpleNamespace(
        settings=SimpleNamespace(
            gemini_include_thoughts=True,
            gemini_computer_use_enabled=True,
            gemini_computer_use_require_confirmation=False,
            gemini_computer_use_max_steps=2,
            gemini_computer_use_timeout_seconds=0.5,
        )
    )

    options = g.build_computer_use_options(
        default_ctx,
        {
            "enable_computer_use": "1",
            "computer_use_require_confirmation": "1",
            "computer_use_max_steps": "6",
            "computer_use_timeout_seconds": "2.25",
        },
        {},
    )

    assert options == {
        "enable_computer_use": True,
        "computer_use_require_confirmation": True,
        "computer_use_max_steps": 6,
        "computer_use_timeout_seconds": 2.25,
    }


def test_computer_use_options_use_exact_section_keys_and_default_timeout() -> None:
    g = _fresh_gates()
    default_ctx = SimpleNamespace(
        settings=SimpleNamespace(
            gemini_include_thoughts=True,
            gemini_computer_use_enabled=True,
            gemini_computer_use_require_confirmation=True,
            gemini_computer_use_max_steps=4,
            gemini_computer_use_timeout_seconds=1.5,
        )
    )

    options = g.build_computer_use_options(
        default_ctx,
        {"enable_computer_use": "0", "computer_use_timeout_seconds": "9.0"},
        {"enable_computer_use": "1"},
    )
    default_timeout_options = g.build_computer_use_options(default_ctx, {}, {})

    assert options["enable_computer_use"] is True
    assert default_timeout_options["computer_use_timeout_seconds"] == 1.5
    assert default_timeout_options["computer_use_require_confirmation"] is True


def test_computer_use_options_section_keys_override_llm_policy_for_confirmation_and_limits() -> (
    None
):
    g = _fresh_gates()
    default_ctx = SimpleNamespace(
        settings=SimpleNamespace(
            gemini_include_thoughts=True,
            gemini_computer_use_enabled=True,
            gemini_computer_use_require_confirmation=True,
            gemini_computer_use_max_steps=4,
            gemini_computer_use_timeout_seconds=1.5,
        )
    )

    options = g.build_computer_use_options(
        default_ctx,
        {
            "computer_use_require_confirmation": "0",
            "computer_use_max_steps": "2",
            "computer_use_timeout_seconds": "3.75",
        },
        {
            "computer_use_require_confirmation": "1",
            "computer_use_max_steps": "6",
            "computer_use_timeout_seconds": "2.25",
        },
    )
    default_options = g.build_computer_use_options(default_ctx, {}, {})

    assert options["computer_use_require_confirmation"] is True
    assert options["computer_use_max_steps"] == 6
    assert options["computer_use_timeout_seconds"] == 2.25
    assert default_options["computer_use_max_steps"] == 4
    assert default_options["computer_use_timeout_seconds"] == 1.5


@pytest.mark.parametrize("policy_key", ["media_resolution", "max_function_call_rounds"])
def test_policy_helpers_prioritize_section_policy(policy_key: str) -> None:
    g = _fresh_gates()
    if policy_key == "media_resolution":
        assert g._media_resolution_from_policy(
            {"media_resolution": "low"},
            {"media_resolution": {"default": "ultra", "frames": "high"}},
        ) == {"default": "ultra", "frames": "high"}
    else:
        assert (
            g._max_function_call_rounds(
                {"max_function_call_rounds": 1},
                {"max_function_call_rounds": "5"},
            )
            == 5
        )
