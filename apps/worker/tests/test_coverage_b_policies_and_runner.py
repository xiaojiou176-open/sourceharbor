from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from apps.worker.worker.config import Settings
from apps.worker.worker.pipeline import policies, runner


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifacts").resolve()),
    )


def test_policies_override_and_classification_branches(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)

    assert policies.pipeline_llm_hard_required(settings, {"hard_required": "0"}) is False
    assert policies.pipeline_llm_hard_required(settings, {"hard_required": "maybe"}) is True
    assert (
        policies.pipeline_llm_fail_on_provider_error(settings, {"fail_on_provider_error": "false"})
        is False
    )
    assert (
        policies.pipeline_llm_fail_on_provider_error(
            settings, {"fail_on_provider_error": "unexpected"}
        )
        is True
    )
    assert policies.pipeline_llm_max_retries(settings, {"max_retries": "-1"}) is None
    assert policies.pipeline_llm_max_retries(settings, {"max_retries": "3"}) == 3
    settings_without_retry = SimpleNamespace(pipeline_llm_max_retries=None)
    settings_negative_retry = SimpleNamespace(pipeline_llm_max_retries=-2)
    settings_hard_required_false = SimpleNamespace(pipeline_llm_hard_required=False)
    settings_fail_on_provider_error_false = SimpleNamespace(
        pipeline_llm_fail_on_provider_error=False
    )
    assert policies.pipeline_llm_max_retries(settings_without_retry, None) is None
    assert policies.pipeline_llm_max_retries(settings_negative_retry, None) == 0
    assert policies.pipeline_llm_hard_required(settings_hard_required_false, None) is False
    assert (
        policies.pipeline_llm_fail_on_provider_error(settings_fail_on_provider_error_false, None)
        is False
    )
    assert policies.retry_delay_seconds({"backoff": 0, "max_backoff": 8}, retries_used=4) == 0.0
    assert policies.classify_error("429", "too many request") == "rate_limit"
    assert policies.classify_error(None, "invalid api key") == "auth"
    assert policies.classify_error("unknown", "no known tokens") == "fatal"


def test_runner_policy_wrappers_delegate_to_policy_impls(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)

    retry_policy = runner._build_retry_policy(settings, step_name="llm_outline")
    assert isinstance(retry_policy, dict)
    assert set(retry_policy.keys()) == {"transient", "rate_limit", "auth", "fatal"}
    assert runner._retry_delay_seconds({"backoff": 0.5, "max_backoff": 1.0}, retries_used=2) == 1.0
    assert runner._classify_error("429", None) == "rate_limit"


def test_pipeline_llm_retry_flags_respect_explicit_settings_defaults_and_policy_values() -> None:
    settings_missing_flags = SimpleNamespace()
    settings_flags_none = SimpleNamespace(
        pipeline_llm_hard_required=None,
        pipeline_llm_fail_on_provider_error=None,
    )
    settings_flags_invalid = SimpleNamespace(
        pipeline_llm_hard_required="mystery",
        pipeline_llm_fail_on_provider_error="mystery",
    )

    # Missing flag attributes should use the hardcoded True fallback.
    assert policies.pipeline_llm_hard_required(settings_missing_flags, None) is True
    assert policies.pipeline_llm_fail_on_provider_error(settings_missing_flags, None) is True
    # None/invalid values should still coerce using the True default in fallback path.
    assert policies.pipeline_llm_hard_required(settings_flags_none, None) is True
    assert policies.pipeline_llm_fail_on_provider_error(settings_flags_none, None) is True
    assert policies.pipeline_llm_hard_required(settings_flags_invalid, None) is True
    assert policies.pipeline_llm_fail_on_provider_error(settings_flags_invalid, None) is True

    assert (
        policies.pipeline_llm_hard_required(
            SimpleNamespace(pipeline_llm_hard_required=False),
            None,
        )
        is False
    )
    assert (
        policies.pipeline_llm_fail_on_provider_error(
            SimpleNamespace(pipeline_llm_fail_on_provider_error=False),
            None,
        )
        is False
    )
    assert (
        policies.pipeline_llm_hard_required(
            SimpleNamespace(pipeline_llm_hard_required=True),
            {"hard_required": "maybe"},
        )
        is True
    )
    assert (
        policies.pipeline_llm_fail_on_provider_error(
            SimpleNamespace(pipeline_llm_fail_on_provider_error=True),
            {"fail_on_provider_error": "unexpected"},
        )
        is True
    )
    assert (
        policies.pipeline_llm_max_retries(SimpleNamespace(pipeline_llm_max_retries=None), None)
        is None
    )
    assert (
        policies.pipeline_llm_max_retries(SimpleNamespace(pipeline_llm_max_retries=-2), None) == 0
    )
    assert (
        policies.pipeline_llm_max_retries(SimpleNamespace(pipeline_llm_max_retries="4"), None) == 4
    )
    assert policies.pipeline_llm_max_retries(SimpleNamespace(), None) is None
    assert (
        policies.pipeline_llm_max_retries(
            SimpleNamespace(pipeline_llm_max_retries="invalid"),
            None,
        )
        == 0
    )
    assert (
        policies.pipeline_llm_max_retries(
            SimpleNamespace(pipeline_llm_max_retries=5),
            {"max_retries": "invalid"},
        )
        is None
    )
    assert (
        policies.pipeline_llm_max_retries(
            SimpleNamespace(pipeline_llm_max_retries=5),
            {"max_retries": None},
        )
        is None
    )
    assert (
        policies.pipeline_llm_max_retries(
            SimpleNamespace(pipeline_llm_max_retries=5),
            {"max_retries": 0},
        )
        == 0
    )
    assert (
        policies.pipeline_llm_max_retries(
            SimpleNamespace(pipeline_llm_max_retries=5), {"max_retries": "-1"}
        )
        is None
    )
    assert (
        policies.pipeline_llm_max_retries(
            SimpleNamespace(pipeline_llm_max_retries=5), {"max_retries": "3"}
        )
        == 3
    )
    assert (
        policies.pipeline_llm_hard_required(
            SimpleNamespace(pipeline_llm_hard_required=False),
            {"hard_required": None},
        )
        is True
    )
    assert (
        policies.pipeline_llm_hard_required(
            SimpleNamespace(pipeline_llm_hard_required=False),
            {"HARD_REQUIRED": True},
        )
        is False
    )
    assert (
        policies.pipeline_llm_fail_on_provider_error(
            SimpleNamespace(pipeline_llm_fail_on_provider_error=False),
            {"fail_on_provider_error": None},
        )
        is True
    )
    assert (
        policies.pipeline_llm_fail_on_provider_error(
            SimpleNamespace(pipeline_llm_fail_on_provider_error=False),
            {"FAIL_ON_PROVIDER_ERROR": True},
        )
        is False
    )
    assert (
        policies.pipeline_llm_max_retries(
            SimpleNamespace(pipeline_llm_max_retries=5),
            {"max_retries": True},
        )
        == 1
    )
    assert (
        policies.pipeline_llm_max_retries(
            SimpleNamespace(pipeline_llm_max_retries=5),
            {"max_retries": False},
        )
        == 0
    )
    assert (
        policies.pipeline_llm_max_retries(SimpleNamespace(pipeline_llm_max_retries=True), None) == 1
    )
    assert (
        policies.pipeline_llm_max_retries(SimpleNamespace(pipeline_llm_max_retries=False), None)
        == 0
    )


def test_build_llm_policy_merges_section_overrides_and_settings_defaults(tmp_path: Path) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifacts").resolve()),
        pipeline_llm_hard_required=False,
        pipeline_llm_fail_on_provider_error=False,
        pipeline_llm_max_retries=6,
        gemini_thinking_level="high",
    )
    overrides = {
        "llm": {
            "hard_required": "1",
            "fail_on_provider_error": "0",
            "max_retries": "3",
            "thinking_level": "low",
        }
    }

    policy = policies.build_llm_policy(settings, overrides)

    assert policy["hard_required"] is True
    assert policy["fail_on_provider_error"] is False
    assert policy["max_retries"] == 3
    assert policy["thinking_level"] == "low"

    default_policy = policies.build_llm_policy(settings, {})
    assert default_policy["hard_required"] is False
    assert default_policy["fail_on_provider_error"] is False
    assert default_policy["max_retries"] == 6
    assert default_policy["thinking_level"] == "high"


def test_build_llm_policy_uses_llm_section_fail_on_provider_error_override(tmp_path: Path) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifacts").resolve()),
        pipeline_llm_fail_on_provider_error=False,
    )

    policy = policies.build_llm_policy(settings, {"llm": {"fail_on_provider_error": "1"}})
    assert policy["fail_on_provider_error"] is True


def test_build_retry_policy_uses_step_specific_and_llm_retry_values() -> None:
    settings = SimpleNamespace(
        pipeline_retry_attempts=2,
        pipeline_retry_backoff_seconds=0.5,
        pipeline_retry_transient_attempts=4,
        pipeline_retry_transient_backoff_seconds=1.5,
        pipeline_retry_transient_max_backoff_seconds=9.0,
        pipeline_retry_rate_limit_attempts=5,
        pipeline_retry_rate_limit_backoff_seconds=2.5,
        pipeline_retry_rate_limit_max_backoff_seconds=12.0,
        pipeline_retry_auth_attempts=1,
        pipeline_retry_auth_backoff_seconds=3.5,
        pipeline_retry_auth_max_backoff_seconds=7.0,
        pipeline_retry_fatal_attempts=0,
        pipeline_llm_max_retries=6,
    )

    non_llm = policies.build_retry_policy(settings, step_name="fetch_metadata")
    assert non_llm == {
        "transient": {"retries": 4, "backoff": 1.5, "max_backoff": 9.0},
        "rate_limit": {"retries": 5, "backoff": 2.5, "max_backoff": 12.0},
        "auth": {"retries": 1, "backoff": 3.5, "max_backoff": 7.0},
        "fatal": {"retries": 0, "backoff": 0.0, "max_backoff": 0.0},
    }

    llm = policies.build_retry_policy(
        settings,
        step_name="llm_outline",
        llm_policy={"max_retries": "3"},
    )
    assert llm["transient"]["retries"] == 3
    assert llm["rate_limit"]["retries"] == 3
    assert llm["auth"]["retries"] == 3
    assert llm["fatal"]["retries"] == 3
    assert llm["transient"]["backoff"] == 1.5
    assert llm["rate_limit"]["max_backoff"] == 12.0


def test_build_retry_policy_uses_expected_default_fallbacks_when_category_settings_missing() -> (
    None
):
    settings = SimpleNamespace(
        pipeline_retry_attempts=2,
        pipeline_retry_backoff_seconds=0.5,
    )

    policy = policies.build_retry_policy(settings, step_name="fetch_metadata")

    assert policy == {
        "transient": {"retries": 2, "backoff": 0.5, "max_backoff": 4.0},
        "rate_limit": {"retries": 3, "backoff": 1.0, "max_backoff": 8.0},
        "auth": {"retries": 0, "backoff": 0.5, "max_backoff": 1.0},
        "fatal": {"retries": 0, "backoff": 0.0, "max_backoff": 0.0},
    }


def test_build_retry_policy_clamps_negative_category_values() -> None:
    settings = SimpleNamespace(
        pipeline_retry_attempts=-5,
        pipeline_retry_backoff_seconds=-0.5,
        pipeline_retry_transient_attempts=-1,
        pipeline_retry_transient_backoff_seconds=-2.0,
        pipeline_retry_transient_max_backoff_seconds=-3.0,
        pipeline_retry_rate_limit_attempts=-4,
        pipeline_retry_rate_limit_backoff_seconds=-5.0,
        pipeline_retry_rate_limit_max_backoff_seconds=-6.0,
        pipeline_retry_auth_attempts=-7,
        pipeline_retry_auth_backoff_seconds=-8.0,
        pipeline_retry_auth_max_backoff_seconds=-9.0,
        pipeline_retry_fatal_attempts=-10,
    )

    policy = policies.build_retry_policy(settings, step_name="fetch_metadata")

    assert policy == {
        "transient": {"retries": 0, "backoff": 0.0, "max_backoff": 0.0},
        "rate_limit": {"retries": 0, "backoff": 0.0, "max_backoff": 0.0},
        "auth": {"retries": 0, "backoff": 0.0, "max_backoff": 0.0},
        "fatal": {"retries": 0, "backoff": 0.0, "max_backoff": 0.0},
    }


def test_build_retry_policy_base_retry_default_and_zero_are_distinct() -> None:
    missing_base = SimpleNamespace(pipeline_retry_backoff_seconds=0.5)
    missing_policy = policies.build_retry_policy(missing_base, step_name="fetch_metadata")
    assert missing_policy["transient"]["retries"] == 2
    assert missing_policy["rate_limit"]["retries"] == 3

    explicit_zero_base = SimpleNamespace(
        pipeline_retry_attempts=0,
        pipeline_retry_backoff_seconds=0.5,
    )
    zero_policy = policies.build_retry_policy(explicit_zero_base, step_name="fetch_metadata")
    assert zero_policy["transient"]["retries"] == 0
    assert zero_policy["rate_limit"]["retries"] == 3


def test_build_retry_policy_base_backoff_default_and_zero_are_distinct() -> None:
    missing_backoff = SimpleNamespace()
    missing_policy = policies.build_retry_policy(missing_backoff, step_name="fetch_metadata")
    assert missing_policy["transient"]["backoff"] == 1.0
    assert missing_policy["rate_limit"]["backoff"] == 2.0

    explicit_zero_backoff = SimpleNamespace(pipeline_retry_backoff_seconds=0.0)
    zero_policy = policies.build_retry_policy(explicit_zero_backoff, step_name="fetch_metadata")
    assert zero_policy["transient"]["backoff"] == 0.0
    assert zero_policy["transient"]["max_backoff"] == 0.0
    assert zero_policy["rate_limit"]["backoff"] == 0.0
    assert zero_policy["rate_limit"]["max_backoff"] == 1.0


def test_build_retry_policy_rate_limit_defaults_obey_base_thresholds() -> None:
    settings = SimpleNamespace(
        pipeline_retry_attempts=7,
        pipeline_retry_backoff_seconds=0.01,
    )

    policy = policies.build_retry_policy(settings, step_name="fetch_metadata")

    assert policy["transient"] == {"retries": 7, "backoff": 0.01, "max_backoff": 0.08}
    assert policy["rate_limit"] == {"retries": 7, "backoff": 0.02, "max_backoff": 1.0}
    assert policy["auth"] == {"retries": 0, "backoff": 0.01, "max_backoff": 0.02}
    assert policy["fatal"] == {"retries": 0, "backoff": 0.0, "max_backoff": 0.0}


def test_build_retry_policy_llm_override_applies_only_for_supported_steps_and_valid_retries() -> (
    None
):
    settings = SimpleNamespace(
        pipeline_retry_attempts=3,
        pipeline_retry_backoff_seconds=1.0,
        pipeline_retry_transient_attempts=8,
        pipeline_retry_rate_limit_attempts=9,
        pipeline_retry_auth_attempts=2,
        pipeline_retry_fatal_attempts=1,
        pipeline_llm_max_retries=6,
    )

    llm_digest_policy = policies.build_retry_policy(
        settings,
        step_name="llm_digest",
        llm_policy={"max_retries": "4"},
    )
    assert llm_digest_policy["transient"]["retries"] == 4
    assert llm_digest_policy["rate_limit"]["retries"] == 4
    assert llm_digest_policy["auth"]["retries"] == 4
    assert llm_digest_policy["fatal"]["retries"] == 4

    llm_outline_invalid = policies.build_retry_policy(
        settings,
        step_name="llm_outline",
        llm_policy={"max_retries": "-1"},
    )
    assert llm_outline_invalid["transient"]["retries"] == 8
    assert llm_outline_invalid["rate_limit"]["retries"] == 9
    assert llm_outline_invalid["auth"]["retries"] == 2
    assert llm_outline_invalid["fatal"]["retries"] == 1

    non_llm_step = policies.build_retry_policy(
        settings,
        step_name="fetch_metadata",
        llm_policy={"max_retries": "0"},
    )
    assert non_llm_step["transient"]["retries"] == 8
    assert non_llm_step["rate_limit"]["retries"] == 9
    assert non_llm_step["auth"]["retries"] == 2
    assert non_llm_step["fatal"]["retries"] == 1


def test_retry_delay_seconds_clamps_growth_and_handles_non_positive_backoff() -> None:
    assert policies.retry_delay_seconds({"backoff": 0, "max_backoff": 8}, retries_used=4) == 0.0
    assert policies.retry_delay_seconds({"backoff": -1, "max_backoff": 8}, retries_used=1) == 0.0
    assert policies.retry_delay_seconds({"backoff": 0.5, "max_backoff": 10}, retries_used=-3) == 0.5
    assert policies.retry_delay_seconds({"backoff": 0.5, "max_backoff": 10}, retries_used=3) == 4.0
    assert policies.retry_delay_seconds({"backoff": 0.5, "max_backoff": 1.0}, retries_used=4) == 1.0
    assert (
        policies.retry_delay_seconds({"backoff": 1.0, "max_backoff": 10.0}, retries_used=0) == 1.0
    )
    assert policies.retry_delay_seconds({"backoff": 2.0, "max_backoff": 0.0}, retries_used=2) == 0.0


def test_classify_error_covers_auth_transient_and_fatal_tokens() -> None:
    assert policies.classify_error("429", "too many request") == "rate_limit"
    assert policies.classify_error(None, "invalid api key") == "auth"
    assert policies.classify_error("401 unauthorized", None) == "auth"
    assert policies.classify_error(None, "authentication required") == "auth"
    assert policies.classify_error("provider_error", None) == "transient"
    assert policies.classify_error(None, "service unavailable") == "transient"
    assert policies.classify_error(None, "ECONNRESET") == "transient"
    assert policies.classify_error(None, "connection reset by peer") == "transient"
    assert policies.classify_error("unknown", "no known tokens") == "fatal"


def test_classify_error_matches_numeric_and_single_keyword_tokens() -> None:
    assert policies.classify_error("429", None) == "rate_limit"
    assert policies.classify_error("401", None) == "auth"
    assert policies.classify_error("403", None) == "auth"
    assert policies.classify_error(None, "forbidden") == "auth"
    assert policies.classify_error(None, "timeout") == "transient"


def test_classify_error_matches_cross_field_rate_limit_phrase() -> None:
    assert policies.classify_error("too many", "request") == "rate_limit"


def test_classify_error_category_precedence_and_extended_tokens() -> None:
    assert policies.classify_error("429 too many requests", "invalid api key") == "rate_limit"
    assert policies.classify_error("403 forbidden", "network timeout") == "auth"
    assert policies.classify_error("api_key_missing", "temporary provider issue") == "auth"
    assert policies.classify_error(None, "permission denied to llm provider") == "auth"
    assert policies.classify_error(None, "NON_ZERO_EXIT: provider unavailable") == "transient"
    assert policies.classify_error(None, "LLM_OUTPUT_INVALID") == "transient"


@pytest.mark.parametrize(
    ("reason", "error", "expected"),
    [
        ("rate limit exceeded", None, "rate_limit"),
        (None, "too many request while polling", "rate_limit"),
        (None, "unauthorized request", "auth"),
        (None, "timed out while contacting upstream", "transient"),
        (None, "network jitter from provider", "transient"),
        (None, "temporary gateway issue", "transient"),
        (None, "provider_unavailable in this region", "transient"),
        (None, "gemini_error from backend", "transient"),
        (None, "llm_provider returned invalid response", "transient"),
        (None, "unexpected unrelated text", "fatal"),
    ],
)
def test_classify_error_token_matrix(reason: str | None, error: str | None, expected: str) -> None:
    assert policies.classify_error(reason, error) == expected


def test_retry_delay_seconds_defaults_when_policy_fields_missing() -> None:
    assert policies.retry_delay_seconds({}, retries_used=5) == 0.0
    assert policies.retry_delay_seconds({"backoff": 0.25}, retries_used=4) == 0.25
    assert (
        policies.retry_delay_seconds({"backoff": "0.5", "max_backoff": "2.0"}, retries_used=3)
        == 2.0
    )


def test_build_retry_policy_uses_global_defaults_and_llm_override_zero() -> None:
    settings = SimpleNamespace()
    policy = policies.build_retry_policy(
        settings,
        step_name="llm_outline",
        llm_policy={"max_retries": 0},
    )

    assert policy == {
        "transient": {"retries": 0, "backoff": 1.0, "max_backoff": 8.0},
        "rate_limit": {"retries": 0, "backoff": 2.0, "max_backoff": 16.0},
        "auth": {"retries": 0, "backoff": 1.0, "max_backoff": 2.0},
        "fatal": {"retries": 0, "backoff": 0.0, "max_backoff": 0.0},
    }


def test_build_retry_policy_llm_step_uses_settings_retries_when_override_absent() -> None:
    settings = SimpleNamespace(
        pipeline_retry_attempts=1,
        pipeline_retry_backoff_seconds=0.5,
        pipeline_llm_max_retries=5,
    )
    policy = policies.build_retry_policy(settings, step_name="llm_outline")
    assert policy["transient"]["retries"] == 5
    assert policy["rate_limit"]["retries"] == 5
    assert policy["auth"]["retries"] == 5
    assert policy["fatal"]["retries"] == 5


def test_runner_step_wrappers_delegate_to_impls(monkeypatch: Any, tmp_path: Path) -> None:
    ctx = SimpleNamespace()
    state: dict[str, Any] = {"k": "v"}
    fetch_capture: dict[str, Any] = {}
    embedding_capture: dict[str, Any] = {}

    async def _fake_fetch_impl(
        current_ctx: Any,
        current_state: dict[str, Any],
        *,
        run_command: Any,
    ) -> runner.StepExecution:
        fetch_capture["ctx"] = current_ctx
        fetch_capture["state"] = current_state
        fetch_capture["run_command"] = run_command
        return runner.StepExecution(status="succeeded", output={"wrapped": "fetch"})

    async def _fake_embedding_impl(
        current_ctx: Any, current_state: dict[str, Any]
    ) -> runner.StepExecution:
        embedding_capture["ctx"] = current_ctx
        embedding_capture["state"] = current_state
        return runner.StepExecution(status="succeeded", output={"wrapped": "embedding"})

    monkeypatch.setattr(runner, "_step_fetch_metadata_impl", _fake_fetch_impl)
    monkeypatch.setattr(runner, "_step_build_embeddings_impl", _fake_embedding_impl)

    fetch_execution = asyncio.run(runner._step_fetch_metadata(ctx, state))
    embedding_execution = asyncio.run(runner._step_build_embeddings(ctx, state))

    assert fetch_execution.output == {"wrapped": "fetch"}
    assert fetch_capture["ctx"] is ctx
    assert fetch_capture["state"] is state
    assert fetch_capture["run_command"] is runner._run_command
    assert embedding_execution.output == {"wrapped": "embedding"}
    assert embedding_capture["ctx"] is ctx
    assert embedding_capture["state"] is state
