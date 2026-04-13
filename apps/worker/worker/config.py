from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


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


def _parse_optional_int(raw: str | None) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _parse_optional_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _read_required_env(name: str) -> str:
    value = os.getenv(name)
    if _is_blank(value):
        raise RuntimeError(f"{name} is not configured")
    return value.strip()


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
    rsshub_base_url: str = "https://rsshub.app"
    rsshub_public_fallback_base_url: str | None = "https://rsshub.app"
    rsshub_fallback_base_urls: list[str] = field(default_factory=list)
    feed_paths: list[str] = field(default_factory=list)
    request_timeout_seconds: float = 15.0
    request_retry_attempts: int = 3
    request_retry_backoff_seconds: float = 0.5
    comments_top_n: int = 10
    comments_replies_per_comment: int = 10
    comments_request_timeout_seconds: float = 10.0

    sqlite_path: str = os.path.join(_sourceharbor_cache_root(), "state", "worker_state.db")
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/sourceharbor"

    temporal_target_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "sourceharbor-worker"

    lock_ttl_seconds: int = 90
    pipeline_workspace_dir: str = os.path.join(_sourceharbor_cache_root(), "workspace")
    pipeline_artifact_root: str = os.path.join(_sourceharbor_cache_root(), "artifacts")
    pipeline_retry_attempts: int = 2
    pipeline_retry_backoff_seconds: float = 1.0
    pipeline_subprocess_timeout_seconds: int = 180
    bilibili_downloader: str = "auto"
    bilibili_cookie: str | None = None
    youtube_transcript_fallback_enabled: bool = True
    asr_fallback_enabled: bool = False
    asr_model_size: str = "small"
    pipeline_max_frames: int = 6
    pipeline_frame_interval_seconds: int = 30
    pipeline_llm_input_mode: str = "auto"
    pipeline_llm_include_frames: bool = False
    pipeline_llm_hard_required: bool = True
    pipeline_llm_fail_on_provider_error: bool = True
    pipeline_llm_max_retries: int | None = None
    pipeline_retry_transient_attempts: int | None = None
    pipeline_retry_transient_backoff_seconds: float | None = None
    pipeline_retry_transient_max_backoff_seconds: float | None = None
    pipeline_retry_rate_limit_attempts: int | None = None
    pipeline_retry_rate_limit_backoff_seconds: float | None = None
    pipeline_retry_rate_limit_max_backoff_seconds: float | None = None
    pipeline_retry_auth_attempts: int | None = None
    pipeline_retry_auth_backoff_seconds: float | None = None
    pipeline_retry_auth_max_backoff_seconds: float | None = None
    pipeline_retry_fatal_attempts: int | None = None
    llm_provider: str = "gemini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.1-pro-preview"
    gemini_outline_model: str = "gemini-3.1-pro-preview"
    gemini_digest_model: str = "gemini-3.1-pro-preview"
    gemini_fast_model: str = "gemini-3-flash-preview"
    gemini_computer_use_model: str = "gemini-3.1-pro-preview"
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_thinking_level: str = "high"
    gemini_include_thoughts: bool = True
    gemini_context_cache_enabled: bool = True
    gemini_context_cache_ttl_seconds: int = 21600
    gemini_context_cache_min_chars: int = 4096
    gemini_context_cache_max_keys: int = 1000
    gemini_context_cache_local_ttl_seconds: int = 21600
    gemini_context_cache_sweep_interval_seconds: int = 300
    gemini_strict_schema_mode: bool = True
    gemini_computer_use_enabled: bool = False
    gemini_computer_use_require_confirmation: bool = True
    gemini_computer_use_max_steps: int = 3
    gemini_computer_use_timeout_seconds: float = 30.0
    youtube_api_key: str | None = None
    notification_enabled: bool = False
    resend_api_key: str | None = None
    resend_from_email: str | None = None
    digest_local_timezone: str = "UTC"
    digest_daily_local_hour: int = 9
    digest_template_path: str = str(
        Path(__file__).resolve().parent.parent / "templates" / "digest.md.mustache"
    )

    @property
    def feed_urls(self) -> list[str]:
        urls: list[str] = []
        for path in self.feed_paths:
            if path.startswith(("http://", "https://")):
                urls.append(path)
                continue

            base = self.rsshub_base_url.rstrip("/")
            relative = path if path.startswith("/") else f"/{path}"
            urls.append(f"{base}{relative}")
        return urls

    @classmethod
    def from_env(cls) -> Settings:
        feed_paths = _split_csv(os.getenv("FEED_URLS"))
        settings = cls(
            rsshub_base_url=os.getenv("RSSHUB_BASE_URL", "https://rsshub.app"),
            rsshub_public_fallback_base_url=(
                os.getenv("RSSHUB_PUBLIC_FALLBACK_BASE_URL", "https://rsshub.app").strip() or None
            ),
            rsshub_fallback_base_urls=_split_csv(os.getenv("RSSHUB_FALLBACK_BASE_URLS")),
            feed_paths=feed_paths,
            request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "15")),
            request_retry_attempts=int(os.getenv("REQUEST_RETRY_ATTEMPTS", "3")),
            request_retry_backoff_seconds=float(os.getenv("REQUEST_RETRY_BACKOFF_SECONDS", "0.5")),
            comments_top_n=int(os.getenv("COMMENTS_TOP_N", "10")),
            comments_replies_per_comment=int(os.getenv("COMMENTS_REPLIES_PER_COMMENT", "10")),
            comments_request_timeout_seconds=float(
                os.getenv("COMMENTS_REQUEST_TIMEOUT_SECONDS", "10")
            ),
            sqlite_path=_read_required_env("SQLITE_PATH"),
            database_url=_read_required_env("DATABASE_URL"),
            temporal_target_host=_read_required_env("TEMPORAL_TARGET_HOST"),
            temporal_namespace=_read_required_env("TEMPORAL_NAMESPACE"),
            temporal_task_queue=_read_required_env("TEMPORAL_TASK_QUEUE"),
            lock_ttl_seconds=int(os.getenv("LOCK_TTL_SECONDS", "90")),
            pipeline_workspace_dir=_read_required_env("PIPELINE_WORKSPACE_DIR"),
            pipeline_artifact_root=_read_required_env("PIPELINE_ARTIFACT_ROOT"),
            pipeline_retry_attempts=int(os.getenv("PIPELINE_RETRY_ATTEMPTS", "2")),
            pipeline_retry_backoff_seconds=float(
                os.getenv("PIPELINE_RETRY_BACKOFF_SECONDS", "1.0")
            ),
            pipeline_subprocess_timeout_seconds=int(
                os.getenv("PIPELINE_SUBPROCESS_TIMEOUT_SECONDS", "180")
            ),
            bilibili_downloader=os.getenv("BILIBILI_DOWNLOADER", "auto"),
            bilibili_cookie=os.getenv("BILIBILI_COOKIE"),
            youtube_transcript_fallback_enabled=_parse_bool(
                os.getenv("YOUTUBE_TRANSCRIPT_FALLBACK_ENABLED"),
                default=True,
            ),
            asr_fallback_enabled=_parse_bool(
                os.getenv("ASR_FALLBACK_ENABLED"),
                default=False,
            ),
            asr_model_size=os.getenv("ASR_MODEL_SIZE", "small"),
            pipeline_max_frames=int(os.getenv("PIPELINE_MAX_FRAMES", "6")),
            pipeline_frame_interval_seconds=int(os.getenv("PIPELINE_FRAME_INTERVAL_SECONDS", "30")),
            pipeline_llm_input_mode=os.getenv("PIPELINE_LLM_INPUT_MODE", "auto"),
            pipeline_llm_include_frames=_parse_bool(
                os.getenv("PIPELINE_LLM_INCLUDE_FRAMES"),
                default=False,
            ),
            pipeline_llm_hard_required=_parse_bool(
                os.getenv("PIPELINE_LLM_HARD_REQUIRED"),
                default=True,
            ),
            pipeline_llm_fail_on_provider_error=_parse_bool(
                os.getenv("PIPELINE_LLM_FAIL_ON_PROVIDER_ERROR"),
                default=True,
            ),
            pipeline_llm_max_retries=(
                max(0, parsed_retries)
                if (parsed_retries := _parse_optional_int(os.getenv("PIPELINE_LLM_MAX_RETRIES")))
                is not None
                else None
            ),
            pipeline_retry_transient_attempts=_parse_optional_int(
                os.getenv("PIPELINE_RETRY_TRANSIENT_ATTEMPTS")
            ),
            pipeline_retry_transient_backoff_seconds=_parse_optional_float(
                os.getenv("PIPELINE_RETRY_TRANSIENT_BACKOFF_SECONDS")
            ),
            pipeline_retry_transient_max_backoff_seconds=_parse_optional_float(
                os.getenv("PIPELINE_RETRY_TRANSIENT_MAX_BACKOFF_SECONDS")
            ),
            pipeline_retry_rate_limit_attempts=_parse_optional_int(
                os.getenv("PIPELINE_RETRY_RATE_LIMIT_ATTEMPTS")
            ),
            pipeline_retry_rate_limit_backoff_seconds=_parse_optional_float(
                os.getenv("PIPELINE_RETRY_RATE_LIMIT_BACKOFF_SECONDS")
            ),
            pipeline_retry_rate_limit_max_backoff_seconds=_parse_optional_float(
                os.getenv("PIPELINE_RETRY_RATE_LIMIT_MAX_BACKOFF_SECONDS")
            ),
            pipeline_retry_auth_attempts=_parse_optional_int(
                os.getenv("PIPELINE_RETRY_AUTH_ATTEMPTS")
            ),
            pipeline_retry_auth_backoff_seconds=_parse_optional_float(
                os.getenv("PIPELINE_RETRY_AUTH_BACKOFF_SECONDS")
            ),
            pipeline_retry_auth_max_backoff_seconds=_parse_optional_float(
                os.getenv("PIPELINE_RETRY_AUTH_MAX_BACKOFF_SECONDS")
            ),
            pipeline_retry_fatal_attempts=_parse_optional_int(
                os.getenv("PIPELINE_RETRY_FATAL_ATTEMPTS")
            ),
            llm_provider=(os.getenv("LLM_PROVIDER", "gemini") or "gemini").strip().lower(),
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview"),
            gemini_outline_model=os.getenv(
                "GEMINI_OUTLINE_MODEL",
                "gemini-3.1-pro-preview",
            ),
            gemini_digest_model=os.getenv(
                "GEMINI_DIGEST_MODEL",
                "gemini-3.1-pro-preview",
            ),
            gemini_fast_model=os.getenv("GEMINI_FAST_MODEL", "gemini-3-flash-preview"),
            gemini_computer_use_model=os.getenv(
                "GEMINI_COMPUTER_USE_MODEL",
                "gemini-3.1-pro-preview",
            ),
            gemini_embedding_model=os.getenv(
                "GEMINI_EMBEDDING_MODEL",
                "gemini-embedding-001",
            ),
            gemini_thinking_level=os.getenv("GEMINI_THINKING_LEVEL", "high"),
            gemini_include_thoughts=_parse_bool(
                os.getenv("GEMINI_INCLUDE_THOUGHTS"),
                default=True,
            ),
            gemini_context_cache_enabled=_parse_bool(
                os.getenv("GEMINI_CONTEXT_CACHE_ENABLED"),
                default=True,
            ),
            gemini_context_cache_ttl_seconds=int(
                os.getenv("GEMINI_CONTEXT_CACHE_TTL_SECONDS", "21600")
            ),
            gemini_context_cache_min_chars=int(os.getenv("GEMINI_CONTEXT_CACHE_MIN_CHARS", "4096")),
            gemini_context_cache_max_keys=int(os.getenv("GEMINI_CONTEXT_CACHE_MAX_KEYS", "1000")),
            gemini_context_cache_local_ttl_seconds=int(
                os.getenv("GEMINI_CONTEXT_CACHE_LOCAL_TTL_SECONDS", "21600")
            ),
            gemini_context_cache_sweep_interval_seconds=int(
                os.getenv("GEMINI_CONTEXT_CACHE_SWEEP_INTERVAL_SECONDS", "300")
            ),
            gemini_strict_schema_mode=_parse_bool(
                os.getenv("GEMINI_STRICT_SCHEMA_MODE"),
                default=True,
            ),
            gemini_computer_use_enabled=_parse_bool(
                os.getenv("GEMINI_COMPUTER_USE_ENABLED"),
                default=False,
            ),
            gemini_computer_use_require_confirmation=_parse_bool(
                os.getenv("GEMINI_COMPUTER_USE_REQUIRE_CONFIRMATION"),
                default=True,
            ),
            gemini_computer_use_max_steps=int(os.getenv("GEMINI_COMPUTER_USE_MAX_STEPS", "3")),
            gemini_computer_use_timeout_seconds=float(
                os.getenv("GEMINI_COMPUTER_USE_TIMEOUT_SECONDS", "30")
            ),
            youtube_api_key=os.getenv("YOUTUBE_API_KEY"),
            notification_enabled=_parse_bool(
                os.getenv("NOTIFICATION_ENABLED"),
                default=False,
            ),
            resend_api_key=os.getenv("RESEND_API_KEY"),
            resend_from_email=os.getenv("RESEND_FROM_EMAIL"),
            digest_local_timezone=os.getenv("DIGEST_LOCAL_TIMEZONE", _system_timezone_name()),
            digest_daily_local_hour=int(os.getenv("DIGEST_DAILY_LOCAL_HOUR", "9")),
            digest_template_path=os.getenv(
                "DIGEST_TEMPLATE_PATH",
                str(Path(__file__).resolve().parent.parent / "templates" / "digest.md.mustache"),
            ),
        )
        return settings.validate()

    def validate(self) -> Settings:
        required_fields = {
            "DATABASE_URL": self.database_url,
            "TEMPORAL_TARGET_HOST": self.temporal_target_host,
            "TEMPORAL_NAMESPACE": self.temporal_namespace,
            "TEMPORAL_TASK_QUEUE": self.temporal_task_queue,
            "SQLITE_PATH": self.sqlite_path,
            "PIPELINE_WORKSPACE_DIR": self.pipeline_workspace_dir,
            "PIPELINE_ARTIFACT_ROOT": self.pipeline_artifact_root,
        }
        for key, value in required_fields.items():
            if _is_blank(value):
                raise RuntimeError(f"{key} is not configured")

        if self.notification_enabled:
            if _is_blank(self.resend_api_key):
                raise RuntimeError("RESEND_API_KEY is not configured")
            if _is_blank(self.resend_from_email):
                raise RuntimeError("RESEND_FROM_EMAIL is not configured")
        if self.digest_daily_local_hour < 0 or self.digest_daily_local_hour > 23:
            raise RuntimeError("DIGEST_DAILY_LOCAL_HOUR must be within [0, 23]")
        bilibili_downloader = str(self.bilibili_downloader or "").strip().lower()
        if bilibili_downloader not in {"auto", "yt-dlp", "bbdown"}:
            raise RuntimeError("BILIBILI_DOWNLOADER must be one of: auto, yt-dlp, bbdown")
        if _is_blank(self.asr_model_size):
            raise RuntimeError("ASR_MODEL_SIZE is not configured")
        if self.llm_provider != "gemini":
            raise RuntimeError("LLM_PROVIDER must be 'gemini' in Gemini-only mode")
        if _is_blank(self.gemini_outline_model):
            raise RuntimeError("GEMINI_OUTLINE_MODEL is not configured")
        if _is_blank(self.gemini_digest_model):
            raise RuntimeError("GEMINI_DIGEST_MODEL is not configured")
        thinking_level = str(self.gemini_thinking_level or "").strip().lower()
        if thinking_level not in {"minimal", "low", "medium", "high"}:
            raise RuntimeError("GEMINI_THINKING_LEVEL must be one of: minimal, low, medium, high")
        if self.gemini_context_cache_ttl_seconds < 60:
            raise RuntimeError("GEMINI_CONTEXT_CACHE_TTL_SECONDS must be >= 60")
        if self.gemini_context_cache_min_chars < 0:
            raise RuntimeError("GEMINI_CONTEXT_CACHE_MIN_CHARS must be >= 0")
        if self.gemini_context_cache_max_keys < 1:
            raise RuntimeError("GEMINI_CONTEXT_CACHE_MAX_KEYS must be >= 1")
        if self.gemini_context_cache_local_ttl_seconds < 60:
            raise RuntimeError("GEMINI_CONTEXT_CACHE_LOCAL_TTL_SECONDS must be >= 60")
        if self.gemini_context_cache_sweep_interval_seconds < 30:
            raise RuntimeError("GEMINI_CONTEXT_CACHE_SWEEP_INTERVAL_SECONDS must be >= 30")
        if self.gemini_computer_use_max_steps < 0:
            raise RuntimeError("GEMINI_COMPUTER_USE_MAX_STEPS must be >= 0")
        if self.gemini_computer_use_timeout_seconds <= 0:
            raise RuntimeError("GEMINI_COMPUTER_USE_TIMEOUT_SECONDS must be > 0")
        return self
