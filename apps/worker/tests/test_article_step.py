"""Tests for article pipeline step_fetch_article_content."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import worker.pipeline.steps.article as article_step
from worker.pipeline.steps.article import step_fetch_article_content


def _patch_fetch_article_html(
    monkeypatch,
    *,
    response_text: str = "<html></html>",
    fetch_error: Exception | None = None,
) -> None:
    async def _fake_fetch_article_html(_source_url: str) -> str:
        if fetch_error is not None:
            raise fetch_error
        return response_text

    monkeypatch.setattr(article_step, "fetch_article_html", _fake_fetch_article_html)


def _patch_extract_article_text(
    monkeypatch,
    *,
    extracted: str | None = None,
    extract_error: Exception | None = None,
) -> None:
    def _fake_extract_article_text(_html: str) -> str | None:
        if extract_error is not None:
            raise extract_error
        return extracted

    monkeypatch.setattr(article_step, "extract_article_text", _fake_extract_article_text)


def test_step_fetch_article_content_fails_when_source_url_missing() -> None:
    async def _run() -> Any:
        return await step_fetch_article_content(
            SimpleNamespace(),
            {},
            run_command=lambda _ctx, _cmd: asyncio.sleep(0),
        )

    execution = asyncio.run(_run())
    assert execution.status == "failed"
    assert execution.reason == "source_url_missing"
    assert execution.state_updates.get("transcript") == ""
    assert execution.state_updates.get("frames") == []
    assert execution.state_updates.get("comments") == []


def test_step_fetch_article_content_fails_when_http_fails_without_rss_fallback(monkeypatch) -> None:
    state = {
        "source_url": "https://example.com/article/2",
        "title": "",
        "overrides": {},
    }
    _patch_fetch_article_html(monkeypatch, fetch_error=Exception("Connection refused"))

    async def _run() -> Any:
        return await step_fetch_article_content(
            SimpleNamespace(),
            state,
            run_command=lambda _ctx, _cmd: asyncio.sleep(0),
        )

    execution = asyncio.run(_run())
    assert execution.status == "succeeded"
    assert execution.degraded is True
    assert execution.reason == "http_fetch_failed_rss_fallback"
    assert "Source: https://example.com/article/2" in execution.state_updates.get("transcript", "")


def test_step_fetch_article_content_uses_rss_fallback_when_http_fails() -> None:
    state = {
        "source_url": "https://example.com/article/1",
        "title": "Test Article",
        "platform": "rss",
        "video_uid": "hash123",
        "overrides": {"rss_content": "Full article body from RSS.", "rss_summary": "Short summary"},
    }

    async def _run() -> Any:
        with patch.object(
            article_step,
            "fetch_article_html",
            AsyncMock(side_effect=Exception("Connection refused")),
        ):
            return await step_fetch_article_content(
                SimpleNamespace(),
                state,
                run_command=lambda _ctx, _cmd: asyncio.sleep(0),
            )

    execution = asyncio.run(_run())
    assert execution.status == "succeeded"
    assert execution.degraded is True
    assert "Full article body from RSS" in (execution.state_updates.get("transcript") or "")
    assert execution.state_updates.get("frames") == []
    assert execution.state_updates.get("comments") == []


def test_step_fetch_article_content_uses_trafilatura_when_available(monkeypatch) -> None:
    state = {"source_url": "https://example.com/article/3", "title": "Article"}
    _patch_fetch_article_html(monkeypatch, response_text="<article>Hello</article>")
    _patch_extract_article_text(monkeypatch, extracted="extracted body")

    async def _run() -> Any:
        return await step_fetch_article_content(
            SimpleNamespace(),
            state,
            run_command=lambda _ctx, _cmd: asyncio.sleep(0),
        )

    execution = asyncio.run(_run())
    assert execution.status == "succeeded"
    assert execution.output == {"provider": "trafilatura"}
    assert execution.state_updates.get("transcript") == "extracted body"


def test_step_fetch_article_content_uses_rss_fallback_when_trafilatura_empty(monkeypatch) -> None:
    state = {
        "source_url": "https://example.com/article/4",
        "title": "Fallback article",
        "overrides": {"rss_summary": "rss summary"},
    }
    _patch_fetch_article_html(monkeypatch, response_text="<article>empty</article>")
    _patch_extract_article_text(monkeypatch, extracted=None)

    async def _run() -> Any:
        return await step_fetch_article_content(
            SimpleNamespace(),
            state,
            run_command=lambda _ctx, _cmd: asyncio.sleep(0),
        )

    execution = asyncio.run(_run())
    assert execution.status == "succeeded"
    assert execution.degraded is True
    assert execution.reason == "trafilatura_empty_rss_fallback"
    assert "rss summary" in (execution.state_updates.get("transcript") or "")


def test_step_fetch_article_content_fails_when_trafilatura_empty_and_no_rss(monkeypatch) -> None:
    state = {"source_url": "https://example.com/article/5", "title": ""}
    _patch_fetch_article_html(monkeypatch, response_text="<article>empty</article>")
    _patch_extract_article_text(monkeypatch, extracted=None)

    async def _run() -> Any:
        return await step_fetch_article_content(
            SimpleNamespace(),
            state,
            run_command=lambda _ctx, _cmd: asyncio.sleep(0),
        )

    execution = asyncio.run(_run())
    assert execution.status == "succeeded"
    assert execution.degraded is True
    assert execution.reason == "trafilatura_empty_rss_fallback"


def test_step_fetch_article_content_handles_missing_trafilatura(monkeypatch) -> None:
    state = {
        "source_url": "https://example.com/article/6",
        "title": "Import fallback",
        "overrides": {"rss_content": "rss content"},
    }
    _patch_fetch_article_html(monkeypatch, response_text="<article>hello</article>")
    _patch_extract_article_text(monkeypatch, extract_error=ImportError("missing dependency"))

    async def _run() -> Any:
        return await step_fetch_article_content(
            SimpleNamespace(),
            state,
            run_command=lambda _ctx, _cmd: asyncio.sleep(0),
        )

    execution = asyncio.run(_run())
    assert execution.status == "succeeded"
    assert execution.degraded is True
    assert execution.reason == "trafilatura_unavailable_rss_fallback"
    assert "rss content" in (execution.state_updates.get("transcript") or "")


def test_step_fetch_article_content_fails_when_trafilatura_missing_and_no_rss(monkeypatch) -> None:
    state = {"source_url": "https://example.com/article/7", "title": ""}
    _patch_fetch_article_html(monkeypatch, response_text="<article>hello</article>")
    _patch_extract_article_text(monkeypatch, extract_error=ImportError("missing dependency"))

    async def _run() -> Any:
        return await step_fetch_article_content(
            SimpleNamespace(),
            state,
            run_command=lambda _ctx, _cmd: asyncio.sleep(0),
        )

    execution = asyncio.run(_run())
    assert execution.status == "succeeded"
    assert execution.degraded is True
    assert execution.reason == "trafilatura_unavailable_rss_fallback"


def test_step_fetch_article_content_succeeds_with_trafilatura_extract() -> None:
    state = {
        "source_url": "https://example.com/article/2",
        "title": "Extracted Article",
        "platform": "rss",
        "video_uid": "hash456",
    }

    async def _run() -> Any:
        with (
            patch.object(
                article_step,
                "fetch_article_html",
                AsyncMock(return_value="<html><body>article</body></html>"),
            ),
            patch.object(article_step, "extract_article_text", return_value="Extracted full text"),
        ):
            return await step_fetch_article_content(
                SimpleNamespace(),
                state,
                run_command=lambda _ctx, _cmd: asyncio.sleep(0),
            )

    execution = asyncio.run(_run())
    assert execution.status == "succeeded"
    assert execution.degraded is False
    assert execution.output == {"provider": "trafilatura"}
    assert execution.state_updates["transcript"] == "Extracted full text"


def test_step_fetch_article_content_fails_when_trafilatura_empty_and_no_rss_fallback() -> None:
    state = {
        "source_url": "https://example.com/article/3",
        "title": "No Fallback",
        "platform": "rss",
        "video_uid": "hash789",
    }

    async def _run() -> Any:
        with (
            patch.object(
                article_step,
                "fetch_article_html",
                AsyncMock(return_value="<html><body>empty</body></html>"),
            ),
            patch.object(article_step, "extract_article_text", return_value=None),
        ):
            return await step_fetch_article_content(
                SimpleNamespace(),
                state,
                run_command=lambda _ctx, _cmd: asyncio.sleep(0),
            )

    execution = asyncio.run(_run())
    assert execution.status == "succeeded"
    assert execution.degraded is True
    assert execution.reason == "trafilatura_empty_rss_fallback"
    assert "# No Fallback" in execution.state_updates["transcript"]


def test_step_fetch_article_content_uses_rss_fallback_when_trafilatura_missing() -> None:
    state = {
        "source_url": "https://example.com/article/4",
        "title": "Import Error",
        "platform": "rss",
        "video_uid": "hash000",
        "published_at": "2026-03-08T00:00:00Z",
        "overrides": {"rss_summary": "summary body"},
    }

    async def _run() -> Any:
        with (
            patch.object(
                article_step,
                "fetch_article_html",
                AsyncMock(return_value="<html><body>content</body></html>"),
            ),
            patch.object(
                article_step, "extract_article_text", side_effect=ImportError("trafilatura")
            ),
        ):
            return await step_fetch_article_content(
                SimpleNamespace(),
                state,
                run_command=lambda _ctx, _cmd: asyncio.sleep(0),
            )

    execution = asyncio.run(_run())
    assert execution.status == "succeeded"
    assert execution.degraded is True
    assert execution.reason == "trafilatura_unavailable_rss_fallback"
    assert "summary body" in execution.state_updates["transcript"]
