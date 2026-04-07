from __future__ import annotations

from typing import Any

from worker.comments import (
    BilibiliCommentCollector,
    YouTubeCommentCollector,
    empty_comments_payload,
)
from worker.pipeline.policies import (
    apply_comments_policy,
    coerce_int,
    default_comment_sort_for_platform,
)
from worker.pipeline.types import PipelineContext, StepExecution


async def step_collect_comments(
    ctx: PipelineContext,
    state: dict[str, Any],
    *,
    bilibili_collector_cls: type[BilibiliCommentCollector] = BilibiliCommentCollector,
    youtube_collector_cls: type[YouTubeCommentCollector] = YouTubeCommentCollector,
) -> StepExecution:
    platform = str(state.get("platform") or "").lower()
    source_url = str(state.get("source_url") or "")
    video_uid = str(state.get("video_uid") or "")
    comments_policy = dict(state.get("comments_policy") or {})
    top_n = max(1, coerce_int(comments_policy.get("top_n"), ctx.settings.comments_top_n))
    replies_per_comment = max(
        0,
        coerce_int(
            comments_policy.get("replies_per_comment"),
            ctx.settings.comments_replies_per_comment,
        ),
    )
    requested_sort = str(comments_policy.get("sort") or default_comment_sort_for_platform(platform))

    if platform == "bilibili":
        collector = bilibili_collector_cls(
            top_n=top_n,
            replies_per_comment=replies_per_comment,
            request_timeout_seconds=ctx.settings.comments_request_timeout_seconds,
            retry_attempts=ctx.settings.request_retry_attempts,
            retry_backoff_seconds=ctx.settings.request_retry_backoff_seconds,
            cookie=getattr(ctx.settings, "bilibili_cookie", None),
        )
        try:
            comments_payload = await collector.collect(source_url=source_url, video_uid=video_uid)
        except Exception as exc:
            return StepExecution(
                status="succeeded",
                output={"count": 0, "provider": "bilibili"},
                state_updates={
                    "comments": apply_comments_policy(
                        empty_comments_payload(sort=requested_sort),
                        policy=comments_policy,
                        platform=platform,
                    )
                },
                reason="comments_collection_failed_degraded",
                error=str(exc)[:500],
                degraded=True,
            )
    elif platform == "youtube":
        if not str(ctx.settings.youtube_api_key or "").strip():
            return StepExecution(
                status="succeeded",
                output={"count": 0, "provider": "youtube_data_api"},
                state_updates={
                    "comments": apply_comments_policy(
                        empty_comments_payload(sort=requested_sort),
                        policy=comments_policy,
                        platform=platform,
                    )
                },
                reason="youtube_api_key_missing",
                error="youtube_api_key_missing",
                error_kind="auth",
                degraded=True,
            )

        collector = youtube_collector_cls(
            api_key=str(ctx.settings.youtube_api_key or ""),
            top_n=top_n,
            replies_per_comment=replies_per_comment,
            request_timeout_seconds=ctx.settings.comments_request_timeout_seconds,
            retry_attempts=ctx.settings.request_retry_attempts,
            retry_backoff_seconds=ctx.settings.request_retry_backoff_seconds,
        )
        try:
            comments_payload = await collector.collect(source_url=source_url, video_uid=video_uid)
        except Exception as exc:
            return StepExecution(
                status="succeeded",
                output={"count": 0, "provider": "youtube_data_api"},
                state_updates={
                    "comments": apply_comments_policy(
                        empty_comments_payload(sort=requested_sort),
                        policy=comments_policy,
                        platform=platform,
                    )
                },
                reason="youtube_comments_collection_failed_degraded",
                error=str(exc)[:500],
                degraded=True,
            )
    else:
        return StepExecution(
            status="skipped",
            output={"count": 0},
            state_updates={
                "comments": apply_comments_policy(
                    empty_comments_payload(sort=requested_sort),
                    policy=comments_policy,
                    platform=platform,
                )
            },
            reason="comments_collection_skipped_platform_unsupported",
            degraded=True,
        )

    comments_payload = apply_comments_policy(
        dict(comments_payload or {}),
        policy=comments_policy,
        platform=platform,
    )
    top_comments = comments_payload.get("top_comments")
    count = len(top_comments) if isinstance(top_comments, list) else 0
    return StepExecution(
        status="succeeded",
        output={"count": count},
        state_updates={"comments": comments_payload},
    )
