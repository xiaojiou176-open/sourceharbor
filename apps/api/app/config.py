from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime


def _parse_bool(raw: str | None, *, default: bool) -> bool:
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _is_blank(value: str | None) -> bool:
    return value is None or not value.strip()


def _read_required_env(name: str) -> str:
    value = os.getenv(name)
    if _is_blank(value):
        raise RuntimeError(f"{name} is not configured")
    return value.strip()


def _read_positive_float_env(name: str, *, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if value <= 0:
        return default
    return value


def _sourceharbor_cache_root() -> str:
    raw = os.getenv("SOURCE_HARBOR_CACHE_ROOT")
    return (
        os.path.expanduser(raw.strip())
        if raw and raw.strip()
        else os.path.expanduser("~/.cache/sourceharbor")
    )


def _system_timezone_name() -> str:
    local_tz = datetime.now().astimezone().tzinfo
    tz_name = getattr(local_tz, "key", None) or getattr(local_tz, "zone", None)
    if isinstance(tz_name, str) and tz_name.strip():
        return tz_name.strip()
    return "UTC"


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    database_url: str
    temporal_target_host: str
    temporal_namespace: str
    temporal_task_queue: str
    api_temporal_connect_timeout_seconds: float
    api_temporal_start_timeout_seconds: float
    api_temporal_result_timeout_seconds: float
    api_retrieval_embedding_timeout_seconds: float
    sqlite_state_path: str
    pipeline_artifact_root: str
    notification_enabled: bool
    resend_api_key: str | None
    resend_from_email: str | None
    llm_provider: str
    gemini_api_key: str | None
    gemini_model: str
    gemini_computer_use_model: str
    gemini_embedding_model: str
    gemini_thinking_level: str
    ui_audit_gemini_enabled: bool
    digest_local_timezone: str

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            app_name=os.getenv("APP_NAME", "SourceHarbor API"),
            app_version=os.getenv("APP_VERSION", "0.1.18"),
            database_url=_read_required_env("DATABASE_URL"),
            temporal_target_host=_read_required_env("TEMPORAL_TARGET_HOST"),
            temporal_namespace=_read_required_env("TEMPORAL_NAMESPACE"),
            temporal_task_queue=_read_required_env("TEMPORAL_TASK_QUEUE"),
            api_temporal_connect_timeout_seconds=_read_positive_float_env(
                "API_TEMPORAL_CONNECT_TIMEOUT_SECONDS",
                default=5.0,
            ),
            api_temporal_start_timeout_seconds=_read_positive_float_env(
                "API_TEMPORAL_START_TIMEOUT_SECONDS",
                default=10.0,
            ),
            api_temporal_result_timeout_seconds=_read_positive_float_env(
                "API_TEMPORAL_RESULT_TIMEOUT_SECONDS",
                default=180.0,
            ),
            api_retrieval_embedding_timeout_seconds=_read_positive_float_env(
                "API_RETRIEVAL_EMBEDDING_TIMEOUT_SECONDS",
                default=8.0,
            ),
            sqlite_state_path=_read_required_env("SQLITE_STATE_PATH"),
            pipeline_artifact_root=os.getenv(
                "PIPELINE_ARTIFACT_ROOT",
                os.path.join(_sourceharbor_cache_root(), "artifacts"),
            ),
            notification_enabled=_parse_bool(
                os.getenv("NOTIFICATION_ENABLED"),
                default=False,
            ),
            resend_api_key=os.getenv("RESEND_API_KEY"),
            resend_from_email=os.getenv("RESEND_FROM_EMAIL"),
            llm_provider=(os.getenv("LLM_PROVIDER", "gemini") or "gemini").strip().lower(),
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview"),
            gemini_computer_use_model=os.getenv(
                "GEMINI_COMPUTER_USE_MODEL",
                "gemini-2.5-computer-use-preview-10-2025",
            ),
            gemini_embedding_model=os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"),
            gemini_thinking_level=os.getenv("GEMINI_THINKING_LEVEL", "high"),
            ui_audit_gemini_enabled=_parse_bool(
                os.getenv("UI_AUDIT_GEMINI_ENABLED"),
                default=True,
            ),
            digest_local_timezone=(
                os.getenv("DIGEST_LOCAL_TIMEZONE", _system_timezone_name()).strip() or "UTC"
            ),
        )

    def validate(self) -> Settings:
        required_fields = {
            "DATABASE_URL": self.database_url,
            "TEMPORAL_TARGET_HOST": self.temporal_target_host,
            "TEMPORAL_NAMESPACE": self.temporal_namespace,
            "TEMPORAL_TASK_QUEUE": self.temporal_task_queue,
            "SQLITE_STATE_PATH": self.sqlite_state_path,
        }
        for key, value in required_fields.items():
            if _is_blank(value):
                raise RuntimeError(f"{key} is not configured")

        if self.notification_enabled:
            if _is_blank(self.resend_api_key):
                raise RuntimeError("RESEND_API_KEY is not configured")
            if _is_blank(self.resend_from_email):
                raise RuntimeError("RESEND_FROM_EMAIL is not configured")
        if self.llm_provider != "gemini":
            raise RuntimeError("LLM_PROVIDER must be 'gemini' in Gemini-only mode")
        return self


settings = Settings.from_env().validate()
