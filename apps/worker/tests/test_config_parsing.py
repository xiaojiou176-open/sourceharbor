from __future__ import annotations

import importlib
from pathlib import Path

import pytest

REQUIRED_WORKER_ENV = {
    "SQLITE_PATH": "{tmp}/state.db",
    "DATABASE_URL": "postgresql+psycopg://postgres:postgres@localhost:5432/sourceharbor",
    "TEMPORAL_TARGET_HOST": "localhost:7233",
    "TEMPORAL_NAMESPACE": "default",
    "TEMPORAL_TASK_QUEUE": "sourceharbor-worker",
    "PIPELINE_WORKSPACE_DIR": "{tmp}/workspace",
    "PIPELINE_ARTIFACT_ROOT": "{tmp}/artifacts",
}


def _load_worker_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **overrides: str | None):
    for key, value in REQUIRED_WORKER_ENV.items():
        monkeypatch.setenv(key, value.format(tmp=tmp_path))

    for key, value in overrides.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)

    module = importlib.import_module("worker.config")
    return importlib.reload(module)


def test_worker_from_env_parses_csv_optional_values_and_retry_floor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_module = _load_worker_config(
        monkeypatch,
        tmp_path,
        FEED_URLS=" /youtube/channel/demo , https://rss.example/feed ",
        PIPELINE_LLM_MAX_RETRIES="-5",
        PIPELINE_RETRY_TRANSIENT_ATTEMPTS="invalid",
        PIPELINE_RETRY_TRANSIENT_BACKOFF_SECONDS="bad-float",
    )

    settings = config_module.Settings.from_env()

    assert settings.feed_paths == ["/youtube/channel/demo", "https://rss.example/feed"]
    assert settings.feed_urls == [
        "https://rsshub.app/youtube/channel/demo",
        "https://rss.example/feed",
    ]
    assert settings.pipeline_llm_max_retries == 0
    assert settings.pipeline_retry_transient_attempts is None
    assert settings.pipeline_retry_transient_backoff_seconds is None


def test_worker_from_env_ignores_unknown_legacy_feed_var_when_feed_urls_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_module = _load_worker_config(
        monkeypatch,
        tmp_path,
        FEED_URLS=None,
        LEGACY_FEED_PATHS="/a,/b",
    )

    settings = config_module.Settings.from_env()

    assert settings.feed_paths == []
    assert settings.feed_urls == []


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"DIGEST_DAILY_LOCAL_HOUR": "24"}, "DIGEST_DAILY_LOCAL_HOUR must be within \\[0, 23\\]"),
        (
            {"BILIBILI_DOWNLOADER": "wget"},
            "BILIBILI_DOWNLOADER must be one of: auto, yt-dlp, bbdown",
        ),
        (
            {"GEMINI_THINKING_LEVEL": "ultra"},
            "GEMINI_THINKING_LEVEL must be one of: minimal, low, medium, high",
        ),
        (
            {"GEMINI_CONTEXT_CACHE_TTL_SECONDS": "59"},
            "GEMINI_CONTEXT_CACHE_TTL_SECONDS must be >= 60",
        ),
        (
            {"GEMINI_COMPUTER_USE_TIMEOUT_SECONDS": "0"},
            "GEMINI_COMPUTER_USE_TIMEOUT_SECONDS must be > 0",
        ),
    ],
)
def test_worker_validate_rejects_invalid_boundaries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    overrides: dict[str, str],
    error: str,
) -> None:
    config_module = _load_worker_config(monkeypatch, tmp_path, **overrides)

    with pytest.raises(RuntimeError, match=error):
        config_module.Settings.from_env()


def test_worker_validate_requires_resend_keys_when_notifications_enabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_module = _load_worker_config(
        monkeypatch,
        tmp_path,
        NOTIFICATION_ENABLED="true",
        RESEND_API_KEY="   ",
        RESEND_FROM_EMAIL="bot@example.com",
    )

    with pytest.raises(RuntimeError, match="RESEND_API_KEY is not configured"):
        config_module.Settings.from_env()
