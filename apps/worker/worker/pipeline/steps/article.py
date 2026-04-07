"""Article content fetching step for RSS article pipeline."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from integrations.providers.article_fetch import extract_article_text, fetch_article_html
from worker.pipeline.step_executor import utc_now_iso
from worker.pipeline.types import PipelineContext, StepExecution


async def step_fetch_article_content(
    ctx: PipelineContext,
    state: dict[str, Any],
    *,
    run_command: Callable[[PipelineContext, list[str]], Awaitable[Any]],
) -> StepExecution:
    """Fetch article full text from source URL and map to transcript for LLM steps."""
    source_url = str(state.get("source_url") or "").strip()
    title = state.get("title") or ""
    published_at = state.get("published_at")
    platform = state.get("platform") or "rss"
    video_uid = state.get("video_uid") or ""

    base_metadata = {
        "title": title,
        "platform": platform,
        "video_uid": video_uid,
        "source_url": source_url or None,
        "published_at": published_at,
        "provider": "article",
        "fetched_at": utc_now_iso(),
    }

    if not source_url:
        return StepExecution(
            status="failed",
            state_updates={
                "metadata": base_metadata,
                "transcript": "",
                "frames": [],
                "comments": [],
            },
            reason="source_url_missing",
            error="source_url_missing",
        )

    transcript = ""
    overrides = dict(state.get("overrides") or {})
    rss_content = str(overrides.get("rss_content") or "").strip()
    rss_summary = str(overrides.get("rss_summary") or "").strip()

    try:
        html = await fetch_article_html(source_url)
    except Exception as exc:
        transcript = _build_fallback_transcript(
            title=title,
            content=rss_content or rss_summary,
            link=source_url,
            published_at=published_at,
        )
        if transcript:
            return StepExecution(
                status="succeeded",
                output={"provider": "rss_fallback", "reason": str(exc)},
                state_updates={
                    "metadata": {**base_metadata, "fetch_error": str(exc)},
                    "transcript": transcript,
                    "frames": [],
                    "comments": [],
                },
                reason="http_fetch_failed_rss_fallback",
                degraded=True,
            )
        return StepExecution(
            status="failed",
            state_updates={
                "metadata": base_metadata,
                "transcript": "",
                "frames": [],
                "comments": [],
            },
            reason="http_fetch_failed",
            error=str(exc),
        )

    try:
        extracted = extract_article_text(html)
        if extracted:
            transcript = extracted
        else:
            transcript = _build_fallback_transcript(
                title=title,
                content=rss_content or rss_summary,
                link=source_url,
                published_at=published_at,
            )
            if not transcript:
                return StepExecution(
                    status="failed",
                    state_updates={
                        "metadata": base_metadata,
                        "transcript": "",
                        "frames": [],
                        "comments": [],
                    },
                    reason="trafilatura_empty_no_rss",
                    error="trafilatura_empty_no_rss",
                )
            return StepExecution(
                status="succeeded",
                output={"provider": "rss_fallback", "reason": "trafilatura_empty"},
                state_updates={
                    "metadata": base_metadata,
                    "transcript": transcript,
                    "frames": [],
                    "comments": [],
                },
                reason="trafilatura_empty_rss_fallback",
                degraded=True,
            )
    except ImportError:
        transcript = _build_fallback_transcript(
            title=title,
            content=rss_content or rss_summary,
            link=source_url,
            published_at=published_at,
        )
        if not transcript:
            return StepExecution(
                status="failed",
                state_updates={
                    "metadata": base_metadata,
                    "transcript": "",
                    "frames": [],
                    "comments": [],
                },
                reason="trafilatura_unavailable",
                error="trafilatura_unavailable",
            )
        return StepExecution(
            status="succeeded",
            output={"provider": "rss_fallback", "reason": "trafilatura_unavailable"},
            state_updates={
                "metadata": base_metadata,
                "transcript": transcript,
                "frames": [],
                "comments": [],
            },
            reason="trafilatura_unavailable_rss_fallback",
            degraded=True,
        )

    return StepExecution(
        status="succeeded",
        output={"provider": "trafilatura"},
        state_updates={
            "metadata": base_metadata,
            "transcript": transcript,
            "frames": [],
            "comments": [],
        },
    )


def _build_fallback_transcript(
    *,
    title: str,
    content: str,
    link: str,
    published_at: Any,
) -> str:
    parts: list[str] = []
    if title:
        parts.append(f"# {title}\n")
    if content:
        parts.append(content)
    if link:
        parts.append(f"\nSource: {link}")
    if published_at:
        parts.append(f"Published: {published_at}")
    return "\n".join(parts) if parts else ""
