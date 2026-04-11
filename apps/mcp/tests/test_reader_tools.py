from __future__ import annotations

from collections.abc import Callable
from typing import Any

from apps.mcp.tools.reader import register_reader_tools

UUID_1 = "11111111-1111-1111-1111-111111111111"


class _FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, Callable[..., dict[str, Any]]] = {}

    def tool(self, *, name: str, description: str):
        def _decorator(func: Callable[..., dict[str, Any]]):
            self.tools[name] = func
            return func

        return _decorator


def test_reader_documents_list_rejects_invalid_limit() -> None:
    mcp = _FakeMCP()
    register_reader_tools(mcp, lambda *_args, **_kwargs: {"ok": True})

    payload = mcp.tools["sourceharbor.reader.documents.list"](limit=0)

    assert payload["code"] == "INVALID_ARGUMENT"
    assert payload["details"]["field"] == "limit"


def test_reader_document_get_rejects_invalid_uuid() -> None:
    mcp = _FakeMCP()
    register_reader_tools(mcp, lambda *_args, **_kwargs: {"ok": True})

    payload = mcp.tools["sourceharbor.reader.documents.get"](document_id="doc-1")

    assert payload["code"] == "INVALID_ARGUMENT"
    assert payload["details"]["field"] == "document_id"


def test_reader_tools_normalize_document_and_navigation_payloads() -> None:
    mcp = _FakeMCP()

    def fake_api_call(method: str, path: str, **kwargs: Any) -> Any:
        if method == "GET" and path == "/api/v1/reader/documents":
            return [
                {
                    "id": UUID_1,
                    "stable_key": "topic-ai-agents-2026-04-09",
                    "slug": "topic-ai-agents-2026-04-09-v1",
                    "window_id": "2026-04-09@America/Los_Angeles",
                    "topic_key": "ai-agents",
                    "topic_label": "AI Agents",
                    "title": "AI Agents · 2026-04-09",
                    "summary": "A merged reader doc.",
                    "markdown": "# AI Agents",
                    "materialization_mode": "merge_then_polish",
                    "version": 1,
                    "publish_status": "published_with_gap",
                    "published_with_gap": True,
                    "source_item_count": 2,
                    "warning": {"warning_kind": "yellow_warning"},
                }
            ]
        if method == "GET" and path == f"/api/v1/reader/documents/{UUID_1}":
            return {
                "id": UUID_1,
                "stable_key": "topic-ai-agents-2026-04-09",
                "slug": "topic-ai-agents-2026-04-09-v1",
                "window_id": "2026-04-09@America/Los_Angeles",
                "title": "AI Agents · 2026-04-09",
                "markdown": "# AI Agents",
                "materialization_mode": "merge_then_polish",
                "version": 1,
                "publish_status": "published",
                "published_with_gap": False,
                "source_item_count": 2,
                "warning": {"warning_kind": "clear"},
                "coverage_ledger": {},
                "traceability_pack": {},
                "source_refs": [],
                "sections": [],
                "created_at": "2026-04-09T00:00:00Z",
                "updated_at": "2026-04-09T00:00:00Z",
            }
        if method == "GET" and path == "/api/v1/reader/navigation-brief":
            return {
                "brief_kind": "sourceharbor_navigation_brief_v1",
                "generated_at": "2026-04-09T00:00:00Z",
                "window_id": "2026-04-09@America/Los_Angeles",
                "document_count": 1,
                "published_with_gap_count": 1,
                "summary": "Read the yellow-warning document first.",
                "items": [{"document_id": UUID_1, "route": "/reader/doc-1"}],
            }
        raise AssertionError(f"unexpected api call: {method} {path} {kwargs}")

    register_reader_tools(mcp, fake_api_call)

    list_payload = mcp.tools["sourceharbor.reader.documents.list"](limit=5)
    detail_payload = mcp.tools["sourceharbor.reader.documents.get"](document_id=UUID_1)
    navigation_payload = mcp.tools["sourceharbor.reader.navigation.get"](limit=3)

    assert list_payload["items"][0]["stable_key"] == "topic-ai-agents-2026-04-09"
    assert list_payload["items"][0]["publish_status"] == "published_with_gap"
    assert detail_payload["id"] == UUID_1
    assert detail_payload["publish_status"] == "published"
    assert navigation_payload["document_count"] == 1
