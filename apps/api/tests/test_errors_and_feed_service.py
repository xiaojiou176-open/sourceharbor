from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apps.api.app.errors import ApiServiceError, ApiTimeoutError, build_error_payload
from apps.api.app.services import feed as feed_module
from apps.api.app.services.feed import FeedService


class _FakeResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> list[dict[str, Any]]:
        return list(self._rows)


class _FakeDocument:
    def __init__(
        self,
        *,
        document_id: str,
        slug: str,
        title: str,
        published_with_gap: bool,
        source_refs_json: list[dict[str, Any]],
    ) -> None:
        self.id = uuid.UUID(document_id)
        self.slug = slug
        self.title = title
        self.published_with_gap = published_with_gap
        self.source_refs_json = source_refs_json


class _FakeDB:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[dict[str, Any]] = []

    def execute(self, stmt: Any, params: dict[str, Any]) -> _FakeResult:
        self.calls.append({"stmt": str(stmt), "params": dict(params)})
        return _FakeResult(self.rows)


def test_build_error_payload_and_service_error_roundtrip() -> None:
    payload = build_error_payload(detail="upstream failed", error_code="UPSTREAM_FAILED")
    assert payload == {"detail": "upstream failed", "error_code": "UPSTREAM_FAILED"}

    err = ApiServiceError(
        detail="broken", error_code="BROKEN", status_code=502, error_kind="gateway"
    )
    assert str(err) == "broken"
    assert err.to_payload() == {
        "detail": "broken",
        "error_code": "BROKEN",
        "error_kind": "gateway",
    }


def test_api_timeout_error_uses_timeout_defaults() -> None:
    err = ApiTimeoutError(detail="timed out", error_code="TIMEOUT")

    assert err.status_code == 504
    assert err.error_kind == "timeout"
    assert err.to_payload()["error_kind"] == "timeout"


def test_feed_service_reads_digest_and_outline_fallback(tmp_path: Path) -> None:
    service = FeedService(db=None)  # type: ignore[arg-type]

    digest_path = tmp_path / "digest.md"
    digest_path.write_text("# digest", encoding="utf-8")
    assert service._read_digest_file(str(digest_path)) == "# digest"

    broken_outline_root = tmp_path / "broken"
    broken_outline_root.mkdir(parents=True)
    (broken_outline_root / "outline.json").write_text("{invalid", encoding="utf-8")
    assert service._read_outline_fallback(str(broken_outline_root)) is None

    outline_root = tmp_path / "outline-ok"
    outline_root.mkdir(parents=True)
    (outline_root / "outline.json").write_text(
        json.dumps({"title": "Recap", "summary": "核心结论"}, ensure_ascii=False),
        encoding="utf-8",
    )
    assert service._read_outline_fallback(str(outline_root)) == "# Recap\n\n核心结论"


def test_feed_service_list_digest_feed_applies_cursor_filters_and_has_more(
    tmp_path: Path, monkeypatch
) -> None:
    ts1 = datetime(2026, 2, 25, 10, 0, tzinfo=UTC)
    ts2 = datetime(2026, 2, 25, 9, 0, tzinfo=UTC)
    ts3 = datetime(2026, 2, 25, 8, 0, tzinfo=UTC)
    job_id_1 = "11111111-1111-1111-1111-111111111111"
    job_id_2 = "22222222-2222-2222-2222-222222222222"
    job_id_3 = "33333333-3333-3333-3333-333333333333"

    digest_1 = tmp_path / "digest-1.md"
    digest_2 = tmp_path / "digest-2.md"
    digest_3 = tmp_path / "digest-3.md"
    digest_1.write_text("# d1", encoding="utf-8")
    digest_2.write_text("# d2", encoding="utf-8")
    digest_3.write_text("# d3", encoding="utf-8")

    rows = [
        {
            "job_id": job_id_3,
            "source_url": "https://example.com/v3",
            "source": "youtube",
            "content_type": "article",
            "title": "",
            "video_uid": "v-3",
            "published_at": ts1,
            "created_at": ts1,
            "sort_ts": ts1,
            "category": "tech",
            "subscription_source_type": "url",
            "subscription_source_value": "https://youtube.com/@demo",
            "subscription_id": "sub-tech-1",
            "feedback_saved": False,
            "feedback_label": None,
            "artifact_digest_md": str(digest_1),
            "artifact_root": None,
        },
        {
            "job_id": job_id_2,
            "source_url": "https://example.com/v2",
            "source": "youtube",
            "content_type": "video",
            "title": "Video 2",
            "video_uid": "v-2",
            "published_at": ts2,
            "created_at": ts2,
            "sort_ts": ts2,
            "category": "tech",
            "subscription_source_type": "url",
            "subscription_source_value": "https://youtube.com/@demo",
            "subscription_id": "sub-tech-1",
            "feedback_saved": True,
            "feedback_label": "useful",
            "artifact_digest_md": str(digest_2),
            "artifact_root": None,
        },
        {
            "job_id": job_id_1,
            "source_url": "https://example.com/v1",
            "source": "youtube",
            "content_type": "video",
            "title": "Video 1",
            "video_uid": "v-1",
            "published_at": ts3,
            "created_at": ts3,
            "sort_ts": ts3,
            "category": "tech",
            "subscription_source_type": "url",
            "subscription_source_value": "https://youtube.com/@demo",
            "subscription_id": "sub-tech-2",
            "feedback_saved": False,
            "feedback_label": None,
            "artifact_digest_md": str(digest_3),
            "artifact_root": None,
        },
    ]

    fake_db = _FakeDB(rows)
    service = FeedService(db=fake_db)  # type: ignore[arg-type]
    result = service.list_digest_feed(
        source="youtube",
        category=" Tech ",
        subscription_id=" sub-tech-1 ",
        limit=2,
        cursor="2026-02-24T09:00:00+00:00__job-0",
    )

    params = fake_db.calls[0]["params"]
    assert params["category"] == "tech"
    assert params["subscription_id"] == "sub-tech-1"
    assert params["limit"] == 3
    assert params["cursor_ts"] == "2026-02-24T09:00:00+00:00"
    assert params["cursor_job_id"] == "job-0"

    assert result["has_more"] is True
    assert len(result["items"]) == 2
    assert result["next_cursor"] == f"{ts2.isoformat()}__{job_id_2}"
    assert result["items"][0]["title"] == "v-3"
    assert result["items"][0]["source_name"] in {"youtube", "Demo Channel"}
    assert result["items"][0]["artifact_type"] == "digest"
    assert result["items"][0]["content_type"] == "article"
    assert result["items"][1]["content_type"] == "video"
    assert result["items"][1]["saved"] is True
    assert result["items"][1]["feedback_label"] == "useful"


def test_feed_service_lists_reader_bridge_when_source_item_matches_current_document(
    tmp_path: Path, monkeypatch
) -> None:
    ts = datetime(2026, 2, 25, 10, 0, tzinfo=UTC)
    digest = tmp_path / "digest.md"
    digest.write_text("# digest", encoding="utf-8")

    rows = [
        {
            "job_id": "11111111-1111-1111-1111-111111111111",
            "source_url": "https://example.com/v1",
            "source": "youtube",
            "content_type": "video",
            "title": "Video 1",
            "video_uid": "v-1",
            "published_at": ts,
            "created_at": ts,
            "sort_ts": ts,
            "category": "tech",
            "subscription_source_type": "youtube_user",
            "subscription_source_value": "@demo",
            "subscription_id": "sub-tech-1",
            "source_item_id": "source-item-1",
            "feedback_saved": False,
            "feedback_label": None,
            "artifact_digest_md": str(digest),
            "artifact_root": None,
        }
    ]
    fake_db = _FakeDB(rows)
    service = FeedService(db=fake_db)  # type: ignore[arg-type]
    published_document_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    monkeypatch.setattr(
        service,
        "_build_reader_bridge_index",
        lambda *, limit: (
            {
                "source-item-1": {
                    "id": str(published_document_id),
                    "slug": "reader-doc-1",
                    "title": "Reader Doc 1",
                    "publish_status": "published",
                    "published_with_gap": False,
                    "reader_route": f"/reader/{published_document_id}",
                }
            },
            {},
        ),
    )

    result = service.list_digest_feed()

    assert result["items"][0]["published_document_id"] == str(published_document_id)
    assert result["items"][0]["reader_route"] == f"/reader/{published_document_id}"
    assert result["items"][0]["published_document_publish_status"] == "published"


def test_feed_service_build_reader_bridge_index_maps_source_item_and_job_ids() -> None:
    service = FeedService(db=object())  # type: ignore[arg-type]
    documents = [
        _FakeDocument(
            document_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            slug="reader-doc-1",
            title="Reader Doc 1",
            published_with_gap=False,
            source_refs_json=[
                {"source_item_id": "source-item-1", "job_id": "job-1"},
                {"source_item_id": "source-item-2", "job_id": "job-2"},
            ],
        ),
        _FakeDocument(
            document_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            slug="reader-doc-2",
            title="Reader Doc 2",
            published_with_gap=True,
            source_refs_json=[{"source_item_id": "source-item-3", "job_id": "job-3"}],
        ),
    ]

    class _Repo:
        def __init__(self, db) -> None:
            self.db = db

        def list_current(self, *, limit: int):
            return documents

    original_repo = feed_module.PublishedReaderDocumentsRepository
    feed_module.PublishedReaderDocumentsRepository = _Repo
    try:
        by_source_item, by_job_id = service._build_reader_bridge_index(limit=20)
    finally:
        feed_module.PublishedReaderDocumentsRepository = original_repo

    assert by_source_item["source-item-1"]["reader_route"] == (
        "/reader/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    )
    assert by_job_id["job-2"]["title"] == "Reader Doc 1"
    assert by_source_item["source-item-3"]["publish_status"] == "published_with_gap"


def test_feed_service_build_reader_bridge_index_handles_reader_repo_failure() -> None:
    service = FeedService(db=object())  # type: ignore[arg-type]

    class _Repo:
        def __init__(self, db) -> None:
            self.db = db

        def list_current(self, *, limit: int):
            raise RuntimeError("boom")

    original_repo = feed_module.PublishedReaderDocumentsRepository
    feed_module.PublishedReaderDocumentsRepository = _Repo
    try:
        by_source_item, by_job_id = service._build_reader_bridge_index(limit=20)
    finally:
        feed_module.PublishedReaderDocumentsRepository = original_repo

    assert by_source_item == {}
    assert by_job_id == {}


def test_feed_service_list_digest_feed_applies_feedback_filter_param(tmp_path: Path) -> None:
    ts = datetime(2026, 2, 25, 10, 0, tzinfo=UTC)
    digest = tmp_path / "digest.md"
    digest.write_text("# d1", encoding="utf-8")

    fake_db = _FakeDB(
        [
            {
                "job_id": "11111111-1111-1111-1111-111111111111",
                "source_url": "https://example.com/v1",
                "source": "youtube",
                "content_type": "video",
                "title": "Video 1",
                "video_uid": "v-1",
                "published_at": ts,
                "created_at": ts,
                "sort_ts": ts,
                "category": "tech",
                "subscription_source_type": "url",
                "subscription_source_value": "https://youtube.com/@demo",
                "subscription_id": "sub-tech-1",
                "feedback_saved": True,
                "feedback_label": "useful",
                "artifact_digest_md": str(digest),
                "artifact_root": None,
            }
        ]
    )
    service = FeedService(db=fake_db)  # type: ignore[arg-type]

    result = service.list_digest_feed(feedback=" Useful ")

    assert result["items"][0]["saved"] is True
    assert result["items"][0]["feedback_label"] == "useful"
    assert fake_db.calls[0]["params"]["feedback"] == "useful"


def test_feed_service_list_digest_feed_supports_curated_sort_cursor(tmp_path: Path) -> None:
    ts1 = datetime(2026, 2, 25, 10, 0, tzinfo=UTC)
    ts2 = datetime(2026, 2, 25, 9, 0, tzinfo=UTC)
    digest_1 = tmp_path / "digest-curated-1.md"
    digest_2 = tmp_path / "digest-curated-2.md"
    digest_1.write_text("# curated-1", encoding="utf-8")
    digest_2.write_text("# curated-2", encoding="utf-8")

    fake_db = _FakeDB(
        [
            {
                "job_id": "11111111-1111-1111-1111-111111111111",
                "source_url": "https://example.com/v1",
                "source": "youtube",
                "content_type": "video",
                "title": "Useful and saved",
                "video_uid": "v-1",
                "published_at": ts1,
                "created_at": ts1,
                "sort_ts": ts1,
                "category": "tech",
                "subscription_source_type": "url",
                "subscription_source_value": "https://youtube.com/@demo",
                "subscription_id": "sub-tech-1",
                "feedback_saved": True,
                "feedback_label": "useful",
                "feedback_rank": 4,
                "artifact_digest_md": str(digest_1),
                "artifact_root": None,
            },
            {
                "job_id": "22222222-2222-2222-2222-222222222222",
                "source_url": "https://example.com/v2",
                "source": "youtube",
                "content_type": "video",
                "title": "Neutral",
                "video_uid": "v-2",
                "published_at": ts2,
                "created_at": ts2,
                "sort_ts": ts2,
                "category": "tech",
                "subscription_source_type": "url",
                "subscription_source_value": "https://youtube.com/@demo",
                "subscription_id": "sub-tech-1",
                "feedback_saved": False,
                "feedback_label": None,
                "feedback_rank": 0,
                "artifact_digest_md": str(digest_2),
                "artifact_root": None,
            },
        ]
    )
    service = FeedService(db=fake_db)  # type: ignore[arg-type]

    result = service.list_digest_feed(
        sort="curated",
        limit=1,
        cursor="4__2026-02-24T09:00:00+00:00__job-0",
    )

    params = fake_db.calls[0]["params"]
    assert params["sort"] == "curated"
    assert params["cursor_rank"] == 4
    assert params["cursor_ts"] == "2026-02-24T09:00:00+00:00"
    assert params["cursor_job_id"] == "job-0"
    assert result["has_more"] is True
    assert result["next_cursor"] == f"4__{ts1.isoformat()}__11111111-1111-1111-1111-111111111111"
    assert result["items"][0]["saved"] is True
    assert result["items"][0]["feedback_label"] == "useful"


def test_feed_service_marks_manual_injected_rows_as_manual_one_off(tmp_path: Path) -> None:
    ts = datetime(2026, 2, 25, 10, 0, tzinfo=UTC)
    digest = tmp_path / "digest-manual.md"
    digest.write_text("# manual", encoding="utf-8")

    fake_db = _FakeDB(
        [
            {
                "job_id": "11111111-1111-1111-1111-111111111111",
                "source_url": "https://www.youtube.com/watch?v=demo",
                "source": "youtube",
                "content_type": "video",
                "title": "Manual source",
                "video_uid": "demo",
                "published_at": ts,
                "created_at": ts,
                "sort_ts": ts,
                "category": "creator",
                "subscription_source_type": "",
                "subscription_source_value": "",
                "subscription_id": "",
                "source_item_id": "source-item-1",
                "source_origin": "manual_injected",
                "feedback_saved": False,
                "feedback_label": None,
                "artifact_digest_md": str(digest),
                "artifact_root": None,
            }
        ]
    )
    service = FeedService(db=fake_db)  # type: ignore[arg-type]

    result = service.list_digest_feed()

    assert result["items"][0]["relation_kind"] == "manual_one_off"
    assert result["items"][0]["affiliation_label"] == "Today lane"


def test_feed_service_parse_cursor_and_title_resolution() -> None:
    service = FeedService(db=None)  # type: ignore[arg-type]

    assert service._parse_cursor(None) == (None, None, None)
    assert service._parse_cursor("invalid") == (None, None, None)
    assert service._parse_cursor("ts__") == (None, None, None)
    assert service._parse_cursor("ts__job-1") == (None, "ts", "job-1")
    assert service._parse_cursor("4__ts__job-1") == (None, None, None)
    assert service._parse_cursor("4__ts__job-1", sort="curated") == (4, "ts", "job-1")
    assert service._parse_cursor("bad__ts__job-1", sort="curated") == (None, None, None)

    assert service._resolve_title({"title": "  T  "}) == "T"
    assert service._resolve_title({"title": "", "video_uid": "vid-1"}) == "vid-1"
    assert (
        service._resolve_title({"title": "", "video_uid": "", "source_url": "https://x"})
        == "https://x"
    )
    assert service._resolve_title({"title": "", "video_uid": "", "source_url": ""}) == "Untitled"


def test_feed_service_list_digest_feed_skips_invalid_rows_and_uses_outline_fallback(
    tmp_path: Path,
) -> None:
    ts = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
    outline_root = tmp_path / "outline-root"
    outline_root.mkdir(parents=True)
    (outline_root / "outline.json").write_text(
        json.dumps({"title": "No Summary"}, ensure_ascii=False),
        encoding="utf-8",
    )

    rows = [
        {
            "job_id": "job-no-summary",
            "source_url": "https://example.com/no-summary",
            "source": "rss",
            "content_type": "video",
            "title": "No summary",
            "video_uid": "v0",
            "published_at": ts,
            "created_at": ts,
            "sort_ts": ts,
            "category": "misc",
            "subscription_source_type": "",
            "subscription_source_value": "",
            "subscription_id": "s0",
            "artifact_digest_md": None,
            "artifact_root": None,
        },
        {
            "job_id": "",
            "source_url": "https://example.com/no-job",
            "source": "rss",
            "content_type": "article",
            "title": "No job",
            "video_uid": "v1",
            "published_at": ts,
            "created_at": ts,
            "sort_ts": ts,
            "category": "misc",
            "subscription_source_type": "",
            "subscription_source_value": "",
            "subscription_id": "s1",
            "artifact_digest_md": None,
            "artifact_root": str(outline_root),
        },
        {
            "job_id": "job-outline",
            "source_url": "https://example.com/outline",
            "source": "rss",
            "content_type": "unexpected",
            "title": "",
            "video_uid": "",
            "published_at": None,
            "created_at": ts,
            "sort_ts": ts,
            "category": "misc",
            "subscription_source_type": "",
            "subscription_source_value": "",
            "subscription_id": "s2",
            "artifact_digest_md": None,
            "artifact_root": str(outline_root),
        },
    ]

    fake_db = _FakeDB(rows)
    service = FeedService(db=fake_db)  # type: ignore[arg-type]
    result = service.list_digest_feed(limit=0)

    assert len(result["items"]) == 1
    assert result["items"][0]["job_id"] == "job-outline"
    assert result["items"][0]["artifact_type"] == "outline"
    assert result["items"][0]["summary_md"] == "# No Summary\n\nOutline generated successfully."
    assert result["items"][0]["content_type"] == "video"
    assert fake_db.calls[0]["params"]["limit"] == 2


def test_feed_service_resolve_summary_and_digest_io_edge_cases(tmp_path: Path, monkeypatch) -> None:
    service = FeedService(db=None)  # type: ignore[arg-type]

    digest_dir = tmp_path / "digest-dir"
    digest_dir.mkdir(parents=True)
    assert service._read_digest_file(str(digest_dir)) is None
    assert service._read_digest_file("") is None
    assert service._read_digest_file(str(tmp_path / "missing-digest.md")) is None

    digest_file = tmp_path / "digest.md"
    digest_file.write_text("payload", encoding="utf-8")

    def _raise_oserror(self, encoding: str = "utf-8") -> str:  # pragma: no cover - behavior mock
        raise OSError("read failure")

    with monkeypatch.context() as m:
        m.setattr(Path, "read_text", _raise_oserror)
        assert service._read_digest_file(str(digest_file)) is None

    outline_root = tmp_path / "outline-nondict"
    outline_root.mkdir(parents=True)
    (outline_root / "outline.json").write_text('["not-dict"]', encoding="utf-8")
    assert service._read_outline_fallback(str(outline_root)) is None
    assert service._read_outline_fallback(str(tmp_path / "missing-outline-root")) is None

    outline_file_root = tmp_path / "outline-file"
    outline_file_root.mkdir(parents=True)
    (outline_file_root / "outline.json").mkdir(parents=True)
    assert service._read_outline_fallback(str(outline_file_root)) is None

    missing_summary, artifact_type = service._resolve_summary(digest_path=None, artifact_root=None)
    assert (missing_summary, artifact_type) == (None, "outline")

    assert service._normalize_content_type("article") == "article"
    assert service._normalize_content_type(" anything ") == "video"
    assert service._iso(" ") != " "
    assert service._parse_cursor(" 2026-03-01T00:00:00Z __ job-1 ") == (
        None,
        "2026-03-01T00:00:00Z",
        "job-1",
    )
    assert isinstance(service._iso(None), str)
