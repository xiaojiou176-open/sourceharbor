from __future__ import annotations

import importlib
from pathlib import Path

import pytest

REQUIRED_API_ENV = {
    "DATABASE_URL": "sqlite+pysqlite:///:memory:",
    "TEMPORAL_TARGET_HOST": "127.0.0.1:7233",
    "TEMPORAL_NAMESPACE": "default",
    "TEMPORAL_TASK_QUEUE": "sourceharbor-worker",
}


def _load_api_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **overrides: str | None):
    for key, value in REQUIRED_API_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("SQLITE_STATE_PATH", str((tmp_path / "state.db").resolve()))
    monkeypatch.delenv("UI_AUDIT_GEMINI_ENABLED", raising=False)

    for key, value in overrides.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)

    module = importlib.import_module("apps.api.app.config")
    return importlib.reload(module)


def test_api_parse_helpers_cover_truthy_falsy_and_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_module = _load_api_config(monkeypatch, tmp_path)

    assert config_module._parse_bool("YES", default=False) is True
    assert config_module._parse_bool("off", default=True) is False
    assert config_module._parse_bool("invalid", default=True) is True

    monkeypatch.setenv("API_TEMPORAL_CONNECT_TIMEOUT_SECONDS", "2.5")
    assert (
        config_module._read_positive_float_env("API_TEMPORAL_CONNECT_TIMEOUT_SECONDS", default=5.0)
        == 2.5
    )

    monkeypatch.setenv("API_TEMPORAL_CONNECT_TIMEOUT_SECONDS", "0")
    assert (
        config_module._read_positive_float_env("API_TEMPORAL_CONNECT_TIMEOUT_SECONDS", default=5.0)
        == 5.0
    )

    monkeypatch.setenv("API_TEMPORAL_CONNECT_TIMEOUT_SECONDS", "not-a-number")
    assert (
        config_module._read_positive_float_env("API_TEMPORAL_CONNECT_TIMEOUT_SECONDS", default=5.0)
        == 5.0
    )


def test_api_settings_from_env_uses_expected_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_module = _load_api_config(monkeypatch, tmp_path)

    settings = config_module.Settings.from_env()

    assert settings.app_name == "SourceHarbor API"
    assert settings.api_temporal_connect_timeout_seconds == 5.0
    assert settings.api_temporal_start_timeout_seconds == 10.0
    assert settings.api_temporal_result_timeout_seconds == 180.0
    assert settings.api_retrieval_embedding_timeout_seconds == 8.0
    assert settings.notification_enabled is False
    assert settings.ui_audit_gemini_enabled is True


def test_api_validate_rejects_missing_resend_config_when_notifications_enabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    with pytest.raises(RuntimeError, match="RESEND_API_KEY is not configured"):
        _load_api_config(
            monkeypatch,
            tmp_path,
            NOTIFICATION_ENABLED="true",
            RESEND_API_KEY="  ",
            RESEND_FROM_EMAIL="noreply@example.com",
        )


def test_api_read_required_env_rejects_blank(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_module = _load_api_config(monkeypatch, tmp_path)

    monkeypatch.setenv("TEMPORAL_TARGET_HOST", "   ")
    with pytest.raises(RuntimeError, match="TEMPORAL_TARGET_HOST is not configured"):
        config_module._read_required_env("TEMPORAL_TARGET_HOST")


def test_source_name_mapping_and_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = importlib.import_module("apps.api.app.services.source_names")
    source_names = importlib.reload(module)
    mapping_file = tmp_path / "subscriptions.up_names.json"
    mapping_file.write_text(
        '{"youtube": {"  @channel  ": "  Channel Name  "}, "other": 123}',
        encoding="utf-8",
    )
    monkeypatch.setattr(source_names, "_MAPPING_FILE", mapping_file)
    source_names._load_mappings.cache_clear()

    resolved = source_names.resolve_source_name(
        source_type=" YouTube ",
        source_value="@channel",
        fallback="Fallback Name",
    )
    fallback_unknown = source_names.resolve_source_name(
        source_type="unknown",
        source_value="",
        fallback="  ",
    )

    assert resolved == "Channel Name"
    assert fallback_unknown == "Unknown"


def test_source_name_loader_returns_empty_for_invalid_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = importlib.import_module("apps.api.app.services.source_names")
    source_names = importlib.reload(module)
    mapping_file = tmp_path / "bad.json"
    mapping_file.write_text("[1, 2, 3]", encoding="utf-8")
    monkeypatch.setattr(source_names, "_MAPPING_FILE", mapping_file)
    source_names._load_mappings.cache_clear()

    assert source_names._load_mappings() == {}
