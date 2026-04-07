from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from worker.comments.youtube import YouTubeCommentCollector
from worker.config import Settings
from worker.pipeline import runner


def test_youtube_comment_collector_maps_threads_and_replies(monkeypatch: Any) -> None:
    collector = YouTubeCommentCollector(
        api_key="test-key",
        top_n=2,
        replies_per_comment=2,
        request_timeout_seconds=5.0,
        retry_attempts=0,
    )

    async def _fake_request_json(_: Any, path: str, *, params: dict[str, Any]) -> dict[str, Any]:
        if path == "/commentThreads":
            assert params["videoId"] == "abc123xyz09"
            return {
                "items": [
                    {
                        "id": "thread-1",
                        "snippet": {
                            "totalReplyCount": 2,
                            "topLevelComment": {
                                "id": "comment-1",
                                "snippet": {
                                    "authorDisplayName": "alice",
                                    "textDisplay": "Top comment",
                                    "likeCount": 12,
                                    "publishedAt": "2024-01-01T00:00:00Z",
                                },
                            },
                        },
                        "replies": {
                            "comments": [
                                {
                                    "id": "reply-1",
                                    "snippet": {
                                        "authorDisplayName": "bob",
                                        "textDisplay": "reply text",
                                        "likeCount": 3,
                                        "publishedAt": "2024-01-01T00:01:00Z",
                                    },
                                }
                            ]
                        },
                    }
                ]
            }
        assert path == "/comments"
        assert params["parentId"] == "comment-1"
        return {
            "items": [
                {
                    "id": "reply-2",
                    "snippet": {
                        "authorDisplayName": "charlie",
                        "textDisplay": "fetched by parentId",
                        "likeCount": 1,
                        "publishedAt": "2024-01-01T00:02:00Z",
                    },
                }
            ]
        }

    monkeypatch.setattr(collector, "_request_json", _fake_request_json)
    payload = asyncio.run(
        collector.collect(
            source_url="https://www.youtube.com/watch?v=abc123xyz09",
            video_uid="",
        )
    )

    assert payload["sort"] == "hot"
    assert len(payload["top_comments"]) == 1
    first = payload["top_comments"][0]
    assert first["comment_id"] == "comment-1"
    assert first["author"] == "alice"
    assert first["reply_count"] == 2
    assert len(first["replies"]) == 2
    assert first["replies"][0]["reply_id"] == "reply-1"
    assert first["replies"][1]["reply_id"] == "reply-2"


def test_step_collect_comments_youtube_without_api_key_degrades(tmp_path: Path) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifact").resolve()),
        youtube_api_key=None,
    )
    ctx = runner.PipelineContext(
        settings=settings,
        sqlite_store=None,  # type: ignore[arg-type]
        pg_store=None,  # type: ignore[arg-type]
        job_id="job",
        attempt=1,
        job_record={},
        work_dir=tmp_path,
        cache_dir=tmp_path,
        download_dir=tmp_path,
        frames_dir=tmp_path,
        artifacts_dir=tmp_path,
    )
    state = {
        "platform": "youtube",
        "source_url": "https://www.youtube.com/watch?v=abc123xyz09",
        "video_uid": "abc123xyz09",
    }
    execution = asyncio.run(runner._step_collect_comments(ctx, state))

    assert execution.status == "succeeded"
    assert execution.degraded is True
    assert execution.error_kind == "auth"
    comments = execution.state_updates["comments"]
    assert comments["sort"] == "hot"
    assert comments["top_comments"] == []
