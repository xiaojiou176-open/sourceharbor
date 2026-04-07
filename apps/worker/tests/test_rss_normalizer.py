from __future__ import annotations

import hashlib
from datetime import datetime

from worker.rss.normalizer import (
    extract_video_identity,
    make_article_idempotency_key,
    make_job_idempotency_key,
    normalize_entry,
)


def test_extract_video_identity_supports_youtube_and_bilibili() -> None:
    yt_platform, yt_uid = extract_video_identity("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    bili_platform, bili_uid = extract_video_identity("https://www.bilibili.com/video/BV1xx411c7mD")

    assert yt_platform == "youtube"
    assert yt_uid == "dQw4w9WgXcQ"
    assert bili_platform == "bilibili"
    assert bili_uid == "BV1xx411c7mD"


def test_normalize_entry_generates_entry_hash_and_datetime() -> None:
    raw = {
        "title": "Demo Video",
        "link": "https://www.youtube.com/watch?v=abc123",
        "guid": "guid-abc",
        "published_at": "2024-02-20T12:00:00Z",
        "summary": "summary",
    }

    normalized = normalize_entry(raw, "https://rsshub.app/youtube/channel/demo")

    assert normalized["video_platform"] == "youtube"
    assert normalized["video_uid"] == "abc123"
    assert isinstance(normalized["published_at"], datetime)
    assert normalized["entry_hash"]
    assert normalized["source"]["feed_url"] == "https://rsshub.app/youtube/channel/demo"


def test_normalize_entry_sets_content_type_video_for_youtube_bilibili() -> None:
    yt_raw = {
        "title": "YT",
        "link": "https://youtube.com/watch?v=abc",
        "guid": "g1",
        "published_at": "",
    }
    bili_raw = {
        "title": "B",
        "link": "https://bilibili.com/video/BV1xx",
        "guid": "g2",
        "published_at": "",
    }
    assert normalize_entry(yt_raw, "https://feed")["content_type"] == "video"
    assert normalize_entry(bili_raw, "https://feed")["content_type"] == "video"


def test_normalize_entry_sets_content_type_article_for_generic_url() -> None:
    raw = {
        "title": "Blog Post",
        "link": "https://example.com/blog/123",
        "guid": "g3",
        "published_at": "2024-01-01T00:00:00Z",
    }
    normalized = normalize_entry(raw, "https://feed")
    assert normalized["content_type"] == "article"
    assert normalized["video_platform"] is None


def test_make_job_idempotency_key_is_deterministic() -> None:
    key_1 = make_job_idempotency_key("youtube", "abc123")
    key_2 = make_job_idempotency_key("youtube", "abc123")
    key_3 = make_job_idempotency_key("youtube", "another")
    new_formula = hashlib.sha256(b"youtube:abc123:video_digest_v1").hexdigest()
    old_formula = hashlib.sha256(b"youtube:abc123:phase2_ingest_stub").hexdigest()

    assert key_1 == key_2
    assert key_1 != key_3
    assert key_1 == new_formula
    assert key_1 != old_formula


def test_make_article_idempotency_key_is_deterministic() -> None:
    key_1 = make_article_idempotency_key("entry-hash-1")
    key_2 = make_article_idempotency_key("entry-hash-1")
    key_3 = make_article_idempotency_key("entry-hash-2")

    assert key_1 == key_2
    assert key_1 != key_3
