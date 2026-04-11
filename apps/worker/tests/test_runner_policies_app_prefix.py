from __future__ import annotations

import importlib

import pytest

from apps.worker.worker.config import Settings
from apps.worker.worker.pipeline import runner_policies


def _settings() -> Settings:
    return Settings(
        pipeline_workspace_dir="/tmp/workspace",
        pipeline_artifact_root="/tmp/artifacts",
        comments_top_n=8,
        comments_replies_per_comment=3,
        pipeline_max_frames=5,
        gemini_include_thoughts=False,
        gemini_computer_use_enabled=True,
        gemini_computer_use_require_confirmation=True,
        gemini_computer_use_max_steps=4,
        gemini_computer_use_timeout_seconds=12.0,
        gemini_model="gemini-pro",
        gemini_fast_model="gemini-flash",
        gemini_outline_model="gemini-outline",
        gemini_digest_model="gemini-digest",
    )


def test_coercion_helpers_cover_bool_numeric_and_defaults() -> None:
    apps_runner_policies = importlib.reload(
        importlib.import_module("apps.worker.worker.pipeline.runner_policies")
    )

    assert runner_policies.coerce_bool.__defaults__ == (False,)
    assert apps_runner_policies.coerce_bool.__defaults__ == (False,)
    assert apps_runner_policies.coerce_bool(True) is True
    assert apps_runner_policies.coerce_bool(None) is False
    assert apps_runner_policies.coerce_bool(None, default=True) is True
    assert apps_runner_policies.coerce_bool("1") is True
    assert apps_runner_policies.coerce_bool("yes") is True
    assert apps_runner_policies.coerce_bool("on") is True
    assert apps_runner_policies.coerce_bool("y") is True
    assert apps_runner_policies.coerce_bool("Y") is True
    assert apps_runner_policies.coerce_bool("0", default=True) is False
    assert apps_runner_policies.coerce_bool("no", default=True) is False
    assert apps_runner_policies.coerce_bool("NO", default=True) is False
    assert apps_runner_policies.coerce_bool("n", default=True) is False
    assert apps_runner_policies.coerce_bool("off", default=True) is False
    assert apps_runner_policies.coerce_bool("unknown", default=True) is True
    assert apps_runner_policies.coerce_bool("unknown") is False
    assert apps_runner_policies.coerce_bool(None, default=None) is False
    assert apps_runner_policies.coerce_bool("unknown", default=1) is True

    assert apps_runner_policies.coerce_int("4", default=9) == 4
    assert apps_runner_policies.coerce_int("bad", default=9) == 9
    assert apps_runner_policies.coerce_int("bad") == 0
    assert apps_runner_policies.coerce_float("1.5", default=None) == 1.5
    assert apps_runner_policies.coerce_float("bad", default=2.5) == 2.5


def test_media_resolution_normalization_and_override_helpers() -> None:
    assert runner_policies._normalize_media_resolution.__kwdefaults__ == {"default": "medium"}
    assert runner_policies._normalize_media_resolution_policy.__kwdefaults__ == {
        "default": "medium"
    }
    assert runner_policies._normalize_media_resolution("Ultra High") == "ultra_high"
    assert runner_policies._normalize_media_resolution(" ultra-high ") == "ultra_high"
    assert runner_policies._normalize_media_resolution(None) == "medium"
    assert runner_policies._normalize_media_resolution("weird") == "medium"
    assert runner_policies._normalize_media_resolution("weird", default="low") == "low"
    assert runner_policies._normalize_media_resolution_policy("high") == {
        "default": "high",
        "frame": "high",
        "image": "high",
        "pdf": "high",
    }
    assert runner_policies._normalize_media_resolution_policy({}) == {
        "default": "medium",
        "frame": "medium",
        "image": "medium",
        "pdf": "medium",
    }
    assert runner_policies._normalize_media_resolution_policy(
        {"default": "medium", "frame": "high", "image": "low", "pdf": "bad"},
        default="low",
    ) == {
        "default": "medium",
        "frame": "high",
        "image": "low",
        "pdf": "medium",
    }
    assert runner_policies._normalize_media_resolution_policy(
        {"frame": "high"},
        default="low",
    ) == {
        "default": "low",
        "frame": "high",
        "image": "low",
        "pdf": "low",
    }
    assert runner_policies.normalize_overrides_payload(["bad"]) == {}
    assert runner_policies.override_section({"comments": {"top_n": 4}}, "comments") == {"top_n": 4}
    assert runner_policies.override_section({"comments": "bad"}, "comments") == {}


def test_comments_and_frame_policies_normalize_inputs() -> None:
    settings = _settings()
    comments = runner_policies.build_comments_policy(
        settings,
        {"comments": {"top_n": 0, "replies_per_comment": -3, "sort": "bad"}},
        platform="youtube",
    )
    comments_defaults = runner_policies.build_comments_policy(
        settings,
        {"comments": {}},
        platform="bilibili",
    )
    frames = runner_policies.build_frame_policy(
        settings,
        {"frames": {"method": "bad", "max_frames": 0}},
    )
    frames_scene = runner_policies.build_frame_policy(
        settings,
        {"frames": {"method": " Scene ", "max_frames": "3"}},
    )

    assert comments == {"top_n": 1, "replies_per_comment": 0, "sort": "hot"}
    assert comments_defaults == {"top_n": 8, "replies_per_comment": 3, "sort": "like"}
    assert frames == {"method": "fps", "max_frames": 1}
    assert frames_scene == {"method": "scene", "max_frames": 3}
    assert runner_policies.default_comment_sort_for_platform("youtube") == "hot"
    assert runner_policies.default_comment_sort_for_platform("bilibili") == "like"


def test_llm_policy_section_and_build_llm_policy_cover_overrides() -> None:
    settings = _settings()
    section = runner_policies.build_llm_policy_section(
        "default-model",
        {
            "model": " section-model ",
            "temperature": 9,
            "max_output_tokens": "256",
            "max_function_call_rounds": "-1",
            "include_thoughts": "true",
            "enable_computer_use": "true",
            "computer_use_require_confirmation": "false",
            "computer_use_max_steps": "-2",
            "computer_use_timeout_seconds": "0",
            "media_resolution": {"default": "high", "frame": "low"},
        },
        allow_computer_use=True,
    )
    section_no_computer_use = runner_policies.build_llm_policy_section(
        "default-model",
        {
            "temperature": "-3",
            "max_output_tokens": "0",
            "enable_computer_use": "true",
        },
        allow_computer_use=False,
    )
    policy = runner_policies.build_llm_policy(
        settings,
        {
            "llm": {
                "speed_priority": True,
                "thinking_level": "bad",
                "include_thoughts": "true",
                "media_resolution": {"default": "high"},
                "enable_computer_use": "true",
            },
            "llm_outline": {"model": "outline-override"},
            "llm_digest": {"model": "digest-override"},
        },
    )
    policy_without_speed_priority = runner_policies.build_llm_policy(
        settings,
        {"llm": {"thinking_level": "bad"}},
    )

    assert section["model"] == "section-model"
    assert section["temperature"] == 2.0
    assert section["max_output_tokens"] == 256
    assert section["max_function_call_rounds"] == 0
    assert section["include_thoughts"] is True
    assert section["enable_computer_use"] is True
    assert section["computer_use_require_confirmation"] is False
    assert section["computer_use_max_steps"] == 0
    assert section["computer_use_timeout_seconds"] == 30.0
    assert section["media_resolution"]["frame"] == "low"
    assert section_no_computer_use["temperature"] == 0.0
    assert section_no_computer_use["max_output_tokens"] is None
    assert section_no_computer_use["enable_computer_use"] is False

    assert policy["model"] == "gemini-flash"
    assert policy["thinking_level"] == "low"
    assert policy["outline"]["model"] == "outline-override"
    assert policy["digest"]["model"] == "digest-override"
    assert policy["enable_computer_use"] is True
    assert policy_without_speed_priority["speed_priority"] is False
    assert policy_without_speed_priority["thinking_level"] == "high"
    assert policy_without_speed_priority["model"] == "gemini-pro"


def test_llm_policy_section_and_policy_cover_token_and_thinking_edge_cases() -> None:
    settings_with_thoughts = Settings(
        pipeline_workspace_dir="/tmp/workspace",
        pipeline_artifact_root="/tmp/artifacts",
        gemini_include_thoughts=True,
        gemini_computer_use_enabled=True,
        gemini_computer_use_require_confirmation=True,
        gemini_computer_use_max_steps=4,
        gemini_computer_use_timeout_seconds=12.0,
        gemini_model="gemini-pro",
        gemini_fast_model="gemini-flash",
        gemini_outline_model="gemini-outline",
        gemini_digest_model="gemini-digest",
    )

    section_invalid_tokens = runner_policies.build_llm_policy_section(
        "fallback-model",
        {
            "model": " ",
            "temperature": "bad",
            "max_output_tokens": "bad",
            "computer_use_timeout_seconds": "bad",
        },
        allow_computer_use=True,
    )
    section_one_token = runner_policies.build_llm_policy_section(
        "fallback-model",
        {"max_output_tokens": "1"},
        allow_computer_use=True,
    )
    policy_minimal = runner_policies.build_llm_policy(
        settings_with_thoughts,
        {"llm": {"thinking_level": "minimal"}},
    )
    policy_medium = runner_policies.build_llm_policy(
        settings_with_thoughts,
        {"llm": {"thinking_level": "MEDIUM", "include_thoughts": "off"}},
    )

    assert section_invalid_tokens["model"] == "fallback-model"
    assert section_invalid_tokens["temperature"] is None
    assert section_invalid_tokens["max_output_tokens"] is None
    assert section_invalid_tokens["computer_use_require_confirmation"] is True
    assert section_invalid_tokens["computer_use_timeout_seconds"] == 30.0
    assert section_one_token["max_output_tokens"] == 1

    assert policy_minimal["thinking_level"] == "minimal"
    assert policy_minimal["include_thoughts"] is True
    assert policy_medium["thinking_level"] == "medium"
    assert policy_medium["include_thoughts"] is False


def test_llm_policy_section_and_policy_cover_non_default_max_steps_and_timeout_floor() -> None:
    settings = _settings()
    section = runner_policies.build_llm_policy_section(
        "fallback-model",
        {
            "computer_use_max_steps": "7",
            "computer_use_timeout_seconds": "0.05",
        },
        allow_computer_use=True,
    )
    policy = runner_policies.build_llm_policy(
        settings,
        {"llm": {"max_output_tokens": "77"}},
    )

    assert section["computer_use_max_steps"] == 7
    assert section["computer_use_timeout_seconds"] == 0.1
    assert policy["max_output_tokens"] == 77


def test_llm_policy_turns_off_computer_use_when_globally_disabled() -> None:
    settings = Settings(
        pipeline_workspace_dir="/tmp/workspace",
        pipeline_artifact_root="/tmp/artifacts",
        gemini_include_thoughts=False,
        gemini_computer_use_enabled=False,
        gemini_computer_use_require_confirmation=True,
        gemini_computer_use_max_steps=4,
        gemini_computer_use_timeout_seconds=12.0,
        gemini_model="gemini-pro",
        gemini_fast_model="gemini-flash",
        gemini_outline_model="gemini-outline",
        gemini_digest_model="gemini-digest",
    )

    policy = runner_policies.build_llm_policy(
        settings,
        {
            "llm": {
                "speed_priority": True,
                "enable_computer_use": True,
                "computer_use_require_confirmation": False,
            },
            "llm_outline": {"enable_computer_use": True},
            "llm_digest": {"enable_computer_use": True},
        },
    )

    assert policy["model"] == "gemini-flash"
    assert policy["enable_computer_use"] is False
    assert policy["outline"]["enable_computer_use"] is False
    assert policy["digest"]["enable_computer_use"] is False


def test_build_llm_policy_defaults_speed_priority_to_false() -> None:
    policy = runner_policies.build_llm_policy(
        _settings(),
        {"llm": {"thinking_level": "bad"}},
    )

    assert policy["speed_priority"] is False
    assert policy["thinking_level"] == "high"


def test_llm_policy_defaults_are_stable_without_overrides() -> None:
    settings = _settings()

    section = runner_policies.build_llm_policy_section(
        "default-model",
        {},
        allow_computer_use=True,
    )
    policy = runner_policies.build_llm_policy(settings, {})

    assert section == {
        "model": "default-model",
        "temperature": None,
        "max_output_tokens": None,
        "max_function_call_rounds": 2,
        "include_thoughts": False,
        "enable_computer_use": False,
        "computer_use_require_confirmation": True,
        "computer_use_max_steps": 0,
        "computer_use_timeout_seconds": 30.0,
        "media_resolution": {
            "default": "medium",
            "frame": "medium",
            "image": "medium",
            "pdf": "medium",
        },
    }
    assert policy == {
        "model": "gemini-pro",
        "temperature": None,
        "max_output_tokens": None,
        "max_function_call_rounds": 2,
        "speed_priority": False,
        "thinking_level": "high",
        "analysis_mode": "advanced",
        "include_thoughts": False,
        "enable_computer_use": True,
        "computer_use_require_confirmation": True,
        "computer_use_max_steps": 4,
        "computer_use_timeout_seconds": 12.0,
        "media_resolution": {
            "default": "medium",
            "frame": "medium",
            "image": "medium",
            "pdf": "medium",
        },
        "raw_stage": {
            "analysis_mode": "advanced",
            "content_type": "video",
            "video_first": True,
            "video_input_required": True,
            "preprocess_enabled": True,
            "preprocess_model": "gemini-flash",
            "preprocess_input_mode": "text",
            "primary_input_mode": "video_text",
            "review_required": True,
            "review_model": "gemini-pro",
            "review_input_mode": "video_text",
        },
        "outline": {
            **section,
            "model": "gemini-outline",
        },
        "digest": {
            **section,
            "model": "gemini-digest",
        },
    }


def test_llm_policy_respects_explicit_false_and_clamped_values() -> None:
    settings = _settings()

    policy = runner_policies.build_llm_policy(
        settings,
        {
            "llm": {
                "speed_priority": "false",
                "thinking_level": "LOW",
                "include_thoughts": "false",
                "temperature": -99,
                "max_output_tokens": "0",
                "max_function_call_rounds": "-9",
                "enable_computer_use": "false",
                "computer_use_require_confirmation": "false",
                "computer_use_max_steps": "-7",
                "computer_use_timeout_seconds": "-9",
                "media_resolution": {"default": "LOW", "pdf": "ULTRA HIGH"},
            },
            "llm_outline": {
                "enable_computer_use": "true",
                "max_output_tokens": "32",
            },
            "llm_digest": {
                "temperature": "1.75",
                "max_function_call_rounds": "5",
            },
        },
    )

    assert policy["speed_priority"] is False
    assert policy["thinking_level"] == "low"
    assert policy["analysis_mode"] == "advanced"
    assert policy["include_thoughts"] is False
    assert policy["temperature"] == 0.0
    assert policy["max_output_tokens"] is None
    assert policy["max_function_call_rounds"] == 0
    assert policy["enable_computer_use"] is False
    assert policy["computer_use_require_confirmation"] is False
    assert policy["computer_use_max_steps"] == 0
    assert policy["computer_use_timeout_seconds"] == 0.1
    assert policy["media_resolution"] == {
        "default": "low",
        "frame": "low",
        "image": "low",
        "pdf": "ultra_high",
    }
    assert policy["outline"]["enable_computer_use"] is True
    assert policy["outline"]["max_output_tokens"] == 32
    assert policy["digest"]["temperature"] == 1.75
    assert policy["digest"]["max_function_call_rounds"] == 5
    assert policy["raw_stage"]["video_input_required"] is True
    assert policy["raw_stage"]["review_required"] is True


def test_llm_policy_speed_priority_uses_explicit_model_and_blank_subsection_fallbacks() -> None:
    settings = _settings()
    policy = runner_policies.build_llm_policy(
        settings,
        {
            "llm": {
                "speed_priority": True,
                "model": "explicit-main-model",
            },
            "llm_outline": {
                "model": "   ",
            },
            "llm_digest": {
                "model": "explicit-digest-model",
            },
        },
    )

    assert policy["speed_priority"] is True
    assert policy["model"] == "explicit-main-model"
    assert policy["outline"]["model"] == "gemini-outline"
    assert policy["digest"]["model"] == "explicit-digest-model"
    assert policy["raw_stage"]["analysis_mode"] == "advanced"


def test_llm_policy_speed_priority_uses_fast_models_without_any_model_overrides() -> None:
    policy = runner_policies.build_llm_policy(
        _settings(),
        {"llm": {"speed_priority": True}},
    )

    assert policy["model"] == "gemini-flash"
    assert policy["outline"]["model"] == "gemini-flash"
    assert policy["digest"]["model"] == "gemini-flash"
    assert policy["raw_stage"]["preprocess_model"] == "gemini-flash"


def test_llm_policy_speed_priority_blank_main_model_uses_section_defaults() -> None:
    policy = runner_policies.build_llm_policy(
        _settings(),
        {"llm": {"speed_priority": True, "model": "   "}},
    )

    assert policy["model"] == "gemini-pro"
    assert policy["outline"]["model"] == "gemini-outline"
    assert policy["digest"]["model"] == "gemini-digest"


def test_llm_policy_keeps_explicit_high_and_clamps_top_level_temperature() -> None:
    policy = runner_policies.build_llm_policy(
        _settings(),
        {"llm": {"thinking_level": "high", "temperature": 9}},
    )

    assert policy["thinking_level"] == "high"
    assert policy["temperature"] == 2.0


def test_llm_policy_inherits_include_thoughts_and_media_resolution_to_subsections() -> None:
    policy = runner_policies.build_llm_policy(
        _settings(),
        {
            "llm": {
                "include_thoughts": "true",
                "media_resolution": {"default": "high", "frame": "low"},
            }
        },
    )

    assert policy["include_thoughts"] is True
    assert policy["outline"]["include_thoughts"] is True
    assert policy["digest"]["include_thoughts"] is True
    assert policy["outline"]["media_resolution"] == {
        "default": "high",
        "frame": "low",
        "image": "high",
        "pdf": "high",
    }
    assert policy["digest"]["media_resolution"] == {
        "default": "high",
        "frame": "low",
        "image": "high",
        "pdf": "high",
    }


def test_build_llm_policy_supports_video_raw_stage_modes_and_article_opt_out() -> None:
    video_policy = runner_policies.build_llm_policy(
        _settings(),
        {
            "llm": {
                "analysis_mode": "economy",
                "review_required": False,
            }
        },
        content_type="video",
    )
    article_policy = runner_policies.build_llm_policy(
        _settings(),
        {},
        content_type="article",
    )

    assert video_policy["analysis_mode"] == "economy"
    assert video_policy["raw_stage"]["analysis_mode"] == "economy"
    assert video_policy["raw_stage"]["preprocess_enabled"] is False
    assert video_policy["raw_stage"]["review_required"] is False
    assert article_policy["raw_stage"]["content_type"] == "article"
    assert article_policy["raw_stage"]["video_first"] is False
    assert article_policy["raw_stage"]["video_input_required"] is False


def test_llm_policy_section_accepts_bool_token_budget_values() -> None:
    section = runner_policies.build_llm_policy_section(
        "default-model",
        {"max_output_tokens": True},
        allow_computer_use=True,
    )
    assert section["max_output_tokens"] == 1


def test_apply_comments_policy_and_mode_helpers_cover_sorting_and_lists() -> None:
    payload = runner_policies.apply_comments_policy(
        {
            "sort": "",
            "top_comments": [
                {
                    "comment_id": "older",
                    "like_count": 9,
                    "published_at": "2024-01-01T00:00:00Z",
                    "replies": [{"reply_id": "1"}, {"reply_id": "2"}],
                },
                {
                    "comment_id": "newer",
                    "like_count": 1,
                    "published_at": "2024-01-02T00:00:00Z",
                    "replies": [{"reply_id": "3"}],
                },
                "bad",
            ],
        },
        policy={"sort": "new", "top_n": 1, "replies_per_comment": 1},
        platform="youtube",
    )
    fallback_sort_payload = runner_policies.apply_comments_policy(
        {
            "sort": "",
            "top_n": 2,
            "replies_per_comment": 1,
            "top_comments": [
                {"comment_id": "c1", "like_count": 1, "replies": [{"reply_id": "r1"}]},
                {"comment_id": "c2", "like_count": 9, "replies": [{"reply_id": "r2"}]},
            ],
        },
        policy={"sort": "bad"},
        platform="bilibili",
    )

    assert payload["sort"] == "new"
    assert payload["top_comments"][0]["comment_id"] == "newer"
    assert payload["replies"] == {"newer": [{"reply_id": "3"}]}
    assert fallback_sort_payload["sort"] == "like"
    assert fallback_sort_payload["top_n"] == 2
    assert fallback_sort_payload["replies_per_comment"] == 1
    assert fallback_sort_payload["top_comments"][0]["comment_id"] == "c2"
    assert runner_policies.normalize_pipeline_mode("refresh_llm") == "refresh_llm"
    assert runner_policies.normalize_pipeline_mode("weird") == "full"
    assert runner_policies.normalize_llm_input_mode("frames_text") == "frames_text"
    assert runner_policies.normalize_llm_input_mode("odd") == "auto"
    assert runner_policies.frame_paths_from_frames(
        [{"path": "a"}, {"path": "a"}, {"path": "b"}, {}],
        limit=2,
    ) == ["a", "b"]
    state = {"media_path": "/tmp/video.mp4", "frames": [{"path": "a"}, {"path": "b"}]}
    assert runner_policies.llm_media_input_dimension(state) == {
        "video_available": True,
        "frame_count": 2,
    }
    runner_policies.refresh_llm_media_input_dimension(state)
    assert state["llm_media_input"]["frame_count"] == 2


def test_apply_comments_policy_skips_blank_comment_ids_and_platform_fallback_sort() -> None:
    payload = runner_policies.apply_comments_policy(
        {
            "sort": "invalid",
            "top_comments": [
                {
                    "comment_id": "   ",
                    "like_count": 1,
                    "replies": [{"reply_id": "x"}],
                },
                {
                    "comment_id": "keep",
                    "like_count": 8,
                    "replies": [{"reply_id": "y"}, "bad"],
                },
            ],
        },
        policy={"sort": "not-supported", "top_n": 2, "replies_per_comment": 2},
        platform="youtube",
    )

    assert payload["sort"] == "invalid"
    assert [item["comment_id"] for item in payload["top_comments"]] == ["keep", "   "]
    assert payload["replies"] == {"keep": [{"reply_id": "y"}]}


def test_apply_comments_policy_falls_back_to_platform_default_when_sort_missing_everywhere() -> (
    None
):
    payload = runner_policies.apply_comments_policy(
        {"top_comments": [{"comment_id": "a", "like_count": 1}]},
        policy={"top_n": 1},
        platform="youtube",
    )

    assert payload["sort"] == "hot"


def test_apply_comments_policy_falls_back_to_payload_sort_before_platform_default() -> None:
    payload = runner_policies.apply_comments_policy(
        {
            "sort": "hot",
            "top_comments": [
                {"comment_id": "a", "like_count": 1, "published_at": "2024-01-01T00:00:00Z"},
                {"comment_id": "b", "like_count": 5, "published_at": "2024-01-02T00:00:00Z"},
            ],
        },
        policy={"sort": "invalid", "top_n": 2, "replies_per_comment": 1},
        platform="bilibili",
    )

    assert payload["sort"] == "hot"
    assert [item["comment_id"] for item in payload["top_comments"]] == ["b", "a"]
    assert payload["top_n"] == 2
    assert payload["replies_per_comment"] == 1


def test_apply_comments_policy_uses_payload_defaults_and_reply_floor() -> None:
    payload = runner_policies.apply_comments_policy(
        {
            "sort": "hot",
            "top_comments": [
                {"comment_id": "c1", "like_count": 1, "replies": [{"reply_id": "r1"}, "bad"]},
                {"comment_id": "c2", "like_count": 2, "replies": [{"reply_id": "r2"}]},
            ],
        },
        policy={"top_n": "bad", "replies_per_comment": -3, "sort": ""},
        platform="youtube",
    )

    assert payload["sort"] == "hot"
    assert payload["top_n"] == 10
    assert payload["replies_per_comment"] == 0
    assert [item["comment_id"] for item in payload["top_comments"]] == ["c2", "c1"]
    assert payload["replies"] == {"c2": [], "c1": []}


def test_apply_comments_policy_handles_missing_and_invalid_lists() -> None:
    payload = runner_policies.apply_comments_policy(
        {
            "sort": "",
            "top_n": "bad",
            "replies_per_comment": "bad",
            "top_comments": {"not": "a-list"},
        },
        policy={"top_n": None, "replies_per_comment": None, "sort": None},
        platform="youtube",
    )

    assert payload["sort"] == "hot"
    assert payload["top_n"] == 10
    assert payload["replies_per_comment"] == 10
    assert payload["top_comments"] == []
    assert payload["replies"] == {}


def test_apply_comments_policy_handles_missing_sort_and_ids_and_field_defaults() -> None:
    payload = runner_policies.apply_comments_policy(
        {
            "sort": "",
            "top_comments": [
                {"comment_id": "dated", "published_at": "2024-01-01T00:00:00Z"},
                {"comment_id": "missing-published"},
                {"like_count": 9, "replies": [{"reply_id": "x"}]},
            ],
        },
        policy={"sort": "new", "top_n": 3, "replies_per_comment": 1},
        platform="youtube",
    )
    hot_payload = runner_policies.apply_comments_policy(
        {
            "sort": "hot",
            "top_comments": [
                {"comment_id": "no-like"},
                {"comment_id": "has-like", "like_count": 2},
            ],
        },
        policy={"top_n": 2, "replies_per_comment": 0},
        platform="youtube",
    )

    assert [item.get("comment_id") for item in payload["top_comments"][:2]] == [
        "dated",
        "missing-published",
    ]
    assert "XXXX" not in payload["replies"]
    assert [item.get("comment_id") for item in hot_payload["top_comments"]] == [
        "has-like",
        "no-like",
    ]


def test_apply_comments_policy_treats_missing_like_count_as_zero_for_hot_sort() -> None:
    payload = runner_policies.apply_comments_policy(
        {
            "sort": "hot",
            "top_comments": [
                {"comment_id": "zero-like", "like_count": 0},
                {"comment_id": "missing-like"},
            ],
        },
        policy={"top_n": 2, "replies_per_comment": 0},
        platform="youtube",
    )

    assert [item.get("comment_id") for item in payload["top_comments"]] == [
        "zero-like",
        "missing-like",
    ]


def test_string_and_language_helpers_cover_json_and_cjk_detection() -> None:
    values = runner_policies.coerce_str_list(
        [" a ", {"text": "b"}, {"summary": "c"}, 7, None],
        limit=4,
    )
    deduped = runner_policies.dedupe_keep_order(["a", "a", "b", "", "c"], limit=2)
    json_text = runner_policies.extract_json_object('```json\n{"ok": true}\n```')
    fallback_json = runner_policies.extract_json_object('prefix {"x":1} suffix')
    outline_payload = {"title": "你好", "chapters": [{"title": "章节", "summary": "摘要"}]}
    digest_payload = {"title": "总结", "summary": "内容", "tldr": ["重点"]}

    assert values == ["a", "b", "c", "7"]
    assert deduped == ["a", "b"]
    assert json_text == '{"ok": true}'
    assert fallback_json == '{"x":1}'
    assert runner_policies.contains_cjk("hello你好") is True
    assert runner_policies.contains_cjk("plain english") is False
    assert runner_policies.outline_is_chinese(outline_payload) is True
    assert runner_policies.digest_is_chinese(digest_payload) is True


def test_language_helpers_cover_negative_and_nested_cjk_paths() -> None:
    assert runner_policies.contains_cjk("12345 !!!") is False
    assert runner_policies.outline_is_chinese({"title": "hello", "chapters": []}) is False
    assert (
        runner_policies.outline_is_chinese(
            {"title": "", "chapters": [{"title": "", "summary": "包含中文摘要"}]}
        )
        is True
    )
    assert (
        runner_policies.digest_is_chinese({"title": "report", "summary": "english only"}) is False
    )
    assert (
        runner_policies.digest_is_chinese({"title": "", "summary": "", "highlights": ["关键点"]})
        is True
    )


def test_language_helpers_cover_title_summary_and_slice_boundaries() -> None:
    assert runner_policies.outline_is_chinese({"title": "中文标题", "chapters": []}) is True
    assert (
        runner_policies.outline_is_chinese(
            {
                "title": "english",
                "chapters": [
                    {"title": "a", "summary": "b"},
                    {"title": "c", "summary": "d"},
                    {"title": "e", "summary": "f"},
                    {"title": "g", "summary": "h"},
                    {"title": "章节五", "summary": "fifth"},
                ],
            }
        )
        is False
    )

    assert runner_policies.digest_is_chinese({"title": "中文", "summary": "english"}) is True
    assert runner_policies.digest_is_chinese({"title": "english", "summary": "中文摘要"}) is True
    assert (
        runner_policies.digest_is_chinese(
            {
                "title": "",
                "summary": "",
                "highlights": ["a", "b", "c", "d", "第五条中文"],
            }
        )
        is False
    )
    assert (
        runner_policies.digest_is_chinese(
            {"title": "", "summary": "", "action_items": ["立即处理中文任务"]}
        )
        is True
    )


def test_language_helpers_detect_chinese_from_chapter_title_after_non_dict_entries() -> None:
    outline_payload = {
        "title": "english",
        "chapters": ["skip-me", {"title": "章节中文", "summary": "plain english"}],
    }
    digest_payload = {
        "title": "english",
        "summary": "plain english",
        "tldr": ["仅这一条中文"],
    }

    assert runner_policies.outline_is_chinese(outline_payload) is True
    assert runner_policies.digest_is_chinese(digest_payload) is True


def test_app_prefix_helpers_cover_default_argument_branches() -> None:
    apps_runner_policies = importlib.import_module("apps.worker.worker.pipeline.runner_policies")

    assert apps_runner_policies.coerce_bool.__defaults__ == (False,)
    assert apps_runner_policies.coerce_bool(None) is False
    assert apps_runner_policies._normalize_media_resolution("weird") == "medium"
    assert apps_runner_policies._normalize_media_resolution_policy({}) == {
        "default": "medium",
        "frame": "medium",
        "image": "medium",
        "pdf": "medium",
    }


def test_string_and_language_helpers_cover_empty_and_non_list_paths() -> None:
    assert runner_policies.coerce_str_list("bad", limit=3) == []
    assert runner_policies.coerce_str_list([{}, {"value": "x"}, {"content": " y "}], limit=2) == [
        "x",
        "y",
    ]
    assert runner_policies.dedupe_keep_order([" a ", "a", " ", "b", "c"], limit=3) == [
        "a",
        "b",
        "c",
    ]
    assert runner_policies.extract_json_object("no braces here") == "no braces here"
    assert (
        runner_policies.outline_is_chinese(
            {"title": None, "chapters": ["bad", {"title": None, "summary": None}]}
        )
        is False
    )
    assert (
        runner_policies.digest_is_chinese({"title": None, "summary": None, "tldr": "bad"}) is False
    )


def test_extract_json_object_prefers_fenced_json_even_with_extra_braces_after_block() -> None:
    text = """```JSON
{"ok": true}
```
tail {"noise": false}
"""
    assert runner_policies.extract_json_object(text) == '{"ok": true}'


def test_extract_json_object_keeps_first_open_to_last_close_for_plain_text() -> None:
    assert (
        runner_policies.extract_json_object('{"first": 1} middle {"second": 2}')
        == '{"first": 1} middle {"second": 2}'
    )
    assert runner_policies.extract_json_object('{"only": 1} trailing text') == '{"only": 1}'
    assert runner_policies.extract_json_object("just-closing-brace }") == "just-closing-brace }"


def test_mode_normalizers_cover_text_llm_input_mode() -> None:
    assert runner_policies.normalize_llm_input_mode(" text ") == "text"


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (
            [f" item-{index} " for index in range(1, 14)],
            [f"item-{index}" for index in range(1, 13)],
        ),
        (
            [{"value": f"value-{index}"} for index in range(1, 14)],
            [f"value-{index}" for index in range(1, 13)],
        ),
    ],
)
def test_coerce_str_list_uses_default_limit_boundary(
    values: list[object], expected: list[str]
) -> None:
    assert runner_policies.coerce_str_list(values) == expected


@pytest.mark.parametrize("limit", [0, -1])
def test_coerce_str_list_returns_empty_for_non_positive_limit(limit: int) -> None:
    assert runner_policies.coerce_str_list(["a", "b"], limit=limit) == []


def test_dedupe_keep_order_uses_default_limit_boundary() -> None:
    values = [f"item-{index}" for index in range(1, 14)]
    assert runner_policies.dedupe_keep_order(values) == [f"item-{index}" for index in range(1, 13)]


@pytest.mark.parametrize("limit", [0, -3])
def test_dedupe_keep_order_returns_empty_for_non_positive_limit(limit: int) -> None:
    assert runner_policies.dedupe_keep_order(["a", "b", "c"], limit=limit) == []


def test_dedupe_keep_order_preserves_single_item_limit() -> None:
    assert runner_policies.dedupe_keep_order(["a", "b", "a"], limit=1) == ["a"]


def test_mode_normalizers_strip_and_lower_supported_values() -> None:
    assert runner_policies.normalize_pipeline_mode("full") == "full"
    assert runner_policies.normalize_pipeline_mode("  FULL  ") == "full"
    assert runner_policies.normalize_pipeline_mode("refresh_comments") == "refresh_comments"
    assert runner_policies.normalize_pipeline_mode(None) == "full"
    assert runner_policies.normalize_pipeline_mode("  TEXT_ONLY  ") == "text_only"
    assert runner_policies.normalize_llm_input_mode("  VIDEO_TEXT ") == "video_text"
