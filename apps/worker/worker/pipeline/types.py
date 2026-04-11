from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from worker.config import Settings
from worker.state.postgres_store import PostgresBusinessStore
from worker.state.sqlite_store import SQLiteStateStore

StepStatus = Literal["succeeded", "failed", "skipped"]
PipelineStatus = Literal["succeeded", "degraded", "failed"]
RetryCategory = Literal["transient", "rate_limit", "auth", "fatal"]
PipelineMode = Literal["full", "text_only", "refresh_comments", "refresh_llm"]
LLMInputMode = Literal["auto", "text", "video_text", "frames_text"]
ContentType = Literal["video", "article"]

PIPELINE_STEPS: list[str] = [
    "fetch_metadata",
    "download_media",
    "collect_subtitles",
    "collect_comments",
    "extract_frames",
    "llm_outline",
    "llm_digest",
    "build_embeddings",
    "write_artifacts",
]

STEP_VERSIONS: dict[str, str] = dict.fromkeys(PIPELINE_STEPS, "v1")
STEP_VERSIONS["download_media"] = "v2"
STEP_VERSIONS["collect_subtitles"] = "v2"
STEP_VERSIONS["collect_comments"] = "v4"
STEP_VERSIONS["llm_outline"] = "v6"
STEP_VERSIONS["llm_digest"] = "v7"
STEP_VERSIONS["build_embeddings"] = "v1"
STEP_VERSIONS["write_artifacts"] = "v3"

ARTICLE_PIPELINE_STEPS: list[str] = [
    "fetch_article_content",
    "llm_outline",
    "llm_digest",
    "build_embeddings",
    "write_artifacts",
]

ARTICLE_STEP_VERSIONS: dict[str, str] = {
    "fetch_article_content": "v1",
    "llm_outline": "v5",
    "llm_digest": "v6",
    "build_embeddings": "v1",
    "write_artifacts": "v2",
}

STEP_VERSIONS["fetch_article_content"] = "v1"

NON_DEGRADING_SKIP_REASONS = {
    "cache_hit",
    "legacy_cache_hit",
    "checkpoint_recovered",
    "mode_matrix_skip",
}

PIPELINE_MODE_SKIP_STEPS: dict[PipelineMode, set[str]] = {
    "full": set(),
    "text_only": {"download_media", "collect_subtitles", "extract_frames"},
    "refresh_comments": set(),
    "refresh_llm": set(),
}

PIPELINE_MODE_FORCE_STEPS: dict[PipelineMode, set[str]] = {
    "full": set(),
    "text_only": set(),
    "refresh_comments": {
        "collect_comments",
        "llm_outline",
        "llm_digest",
        "build_embeddings",
        "write_artifacts",
    },
    "refresh_llm": {"llm_outline", "llm_digest", "build_embeddings", "write_artifacts"},
}

PIPELINE_MODE_SKIP_UPDATES: dict[str, dict[str, Any]] = {
    "download_media": {"media_path": None, "download_mode": "text_only"},
    "collect_subtitles": {"transcript": "", "subtitle_files": []},
    "extract_frames": {"frames": []},
}

STEP_INPUT_KEYS: dict[str, tuple[str, ...]] = {
    "fetch_article_content": (
        "source_url",
        "title",
        "platform",
        "video_uid",
        "published_at",
        "overrides",
    ),
    "fetch_metadata": ("source_url", "title", "platform", "video_uid", "published_at"),
    "download_media": ("source_url",),
    "collect_subtitles": ("media_path", "download_mode", "source_url", "platform", "video_uid"),
    "collect_comments": ("source_url", "platform", "video_uid", "comments_policy"),
    "extract_frames": ("media_path", "frame_policy"),
    "llm_outline": (
        "content_type",
        "title",
        "metadata",
        "transcript",
        "comments",
        "frames",
        "source_url",
        "llm_input_mode",
        "llm_media_input",
        "llm_policy",
    ),
    "llm_digest": (
        "content_type",
        "title",
        "metadata",
        "outline",
        "transcript",
        "comments",
        "frames",
        "source_url",
        "llm_input_mode",
        "llm_media_input",
        "llm_policy",
    ),
    "build_embeddings": (
        "video_uid",
        "transcript",
        "outline",
    ),
    "write_artifacts": (
        "content_type",
        "source_url",
        "platform",
        "video_uid",
        "metadata",
        "digest",
        "outline",
        "comments",
        "transcript",
        "degradations",
        "frames",
        "raw_stage_contract",
    ),
}

STEP_SETTING_KEYS: dict[str, tuple[str, ...]] = {
    "fetch_article_content": ("request_retry_attempts", "request_retry_backoff_seconds"),
    "fetch_metadata": ("pipeline_subprocess_timeout_seconds",),
    "download_media": ("pipeline_subprocess_timeout_seconds", "bilibili_downloader"),
    "collect_subtitles": (
        "pipeline_subprocess_timeout_seconds",
        "youtube_transcript_fallback_enabled",
        "asr_fallback_enabled",
        "asr_model_size",
    ),
    "collect_comments": (
        "comments_top_n",
        "comments_replies_per_comment",
        "comments_request_timeout_seconds",
        "request_retry_attempts",
        "request_retry_backoff_seconds",
    ),
    "extract_frames": (
        "pipeline_subprocess_timeout_seconds",
        "pipeline_frame_interval_seconds",
        "pipeline_max_frames",
    ),
    "llm_outline": (
        "gemini_model",
        "gemini_outline_model",
        "gemini_fast_model",
        "gemini_thinking_level",
        "gemini_include_thoughts",
        "gemini_context_cache_enabled",
        "gemini_context_cache_ttl_seconds",
        "gemini_context_cache_min_chars",
        "gemini_strict_schema_mode",
        "gemini_computer_use_enabled",
        "gemini_computer_use_require_confirmation",
        "gemini_computer_use_max_steps",
        "gemini_computer_use_timeout_seconds",
        "pipeline_max_frames",
        "pipeline_llm_input_mode",
    ),
    "llm_digest": (
        "gemini_model",
        "gemini_digest_model",
        "gemini_fast_model",
        "gemini_thinking_level",
        "gemini_include_thoughts",
        "gemini_context_cache_enabled",
        "gemini_context_cache_ttl_seconds",
        "gemini_context_cache_min_chars",
        "gemini_strict_schema_mode",
        "gemini_computer_use_enabled",
        "gemini_computer_use_require_confirmation",
        "gemini_computer_use_max_steps",
        "gemini_computer_use_timeout_seconds",
        "pipeline_max_frames",
        "pipeline_llm_input_mode",
    ),
    "build_embeddings": ("gemini_embedding_model",),
    "write_artifacts": ("digest_template_path",),
}


@dataclass
class CommandResult:
    ok: bool
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    reason: str | None = None


@dataclass
class StepExecution:
    status: StepStatus
    output: dict[str, Any] = field(default_factory=dict)
    state_updates: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None
    error: str | None = None
    error_kind: RetryCategory | None = None
    retry_meta: dict[str, Any] = field(default_factory=dict)
    cache_meta: dict[str, Any] = field(default_factory=dict)
    degraded: bool = False

    def to_record(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "output": self.output,
            "state_updates": self.state_updates,
            "reason": self.reason,
            "error": self.error,
            "error_kind": self.error_kind,
            "retry_meta": self.retry_meta,
            "cache_meta": self.cache_meta,
            "degraded": self.degraded,
        }

    @classmethod
    def from_record(cls, payload: dict[str, Any]) -> StepExecution:
        return cls(
            status=str(payload.get("status", "failed")),  # type: ignore[arg-type]
            output=dict(payload.get("output") or {}),
            state_updates=dict(payload.get("state_updates") or {}),
            reason=payload.get("reason"),
            error=payload.get("error"),
            error_kind=payload.get("error_kind"),
            retry_meta=dict(payload.get("retry_meta") or {}),
            cache_meta=dict(payload.get("cache_meta") or {}),
            degraded=bool(payload.get("degraded", False)),
        )


@dataclass
class PipelineContext:
    settings: Settings
    sqlite_store: SQLiteStateStore
    pg_store: PostgresBusinessStore
    job_id: str
    attempt: int
    job_record: dict[str, Any]
    work_dir: Path
    cache_dir: Path
    download_dir: Path
    frames_dir: Path
    artifacts_dir: Path
