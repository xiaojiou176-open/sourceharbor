from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class DigestFeedItem(BaseModel):
    feed_id: str
    job_id: str
    video_url: str
    title: str
    source: str
    source_name: str
    canonical_source_name: str | None = None
    canonical_author_name: str | None = None
    subscription_id: str | None = None
    source_item_id: str | None = None
    affiliation_label: str | None = None
    relation_kind: str | None = None
    thumbnail_url: str | None = None
    avatar_url: str | None = None
    avatar_label: str | None = None
    identity_status: str | None = None
    published_document_id: str | None = None
    published_document_slug: str | None = None
    published_document_title: str | None = None
    published_document_publish_status: str | None = None
    published_with_gap: bool | None = None
    reader_route: str | None = None
    category: str
    published_at: str
    summary_md: str
    artifact_type: str
    content_type: Literal["video", "article"]
    saved: bool = False
    feedback_label: Literal["useful", "noisy", "dismissed", "archived"] | None = None


class DigestFeedResponse(BaseModel):
    items: list[DigestFeedItem]
    has_more: bool
    next_cursor: str | None
