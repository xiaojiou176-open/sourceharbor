from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import PublishedReaderDocument


class PublishedReaderDocumentsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_current(
        self,
        *,
        limit: int = 20,
        window_id: str | None = None,
    ) -> list[PublishedReaderDocument]:
        stmt = select(PublishedReaderDocument).where(PublishedReaderDocument.is_current.is_(True))
        if window_id is not None:
            stmt = stmt.where(PublishedReaderDocument.window_id == window_id)
        stmt = stmt.order_by(
            PublishedReaderDocument.created_at.desc(),
            PublishedReaderDocument.version.desc(),
        ).limit(limit)
        return list(self.db.scalars(stmt).all())

    def get(self, *, document_id: uuid.UUID) -> PublishedReaderDocument | None:
        return self.db.get(PublishedReaderDocument, document_id)

    def get_current_by_stable_key(self, *, stable_key: str) -> PublishedReaderDocument | None:
        stmt = (
            select(PublishedReaderDocument)
            .where(
                PublishedReaderDocument.stable_key == stable_key,
                PublishedReaderDocument.is_current.is_(True),
            )
            .order_by(PublishedReaderDocument.version.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def replace_current(
        self,
        *,
        stable_key: str,
        slug: str,
        window_id: str,
        topic_key: str | None,
        topic_label: str | None,
        title: str,
        summary: str | None,
        markdown: str,
        reader_output_locale: str,
        reader_style_profile: str,
        materialization_mode: str,
        published_with_gap: bool,
        source_item_count: int,
        warning_json: dict[str, Any],
        coverage_ledger_json: dict[str, Any],
        traceability_pack_json: dict[str, Any],
        source_refs_json: Sequence[dict[str, Any]],
        sections_json: Sequence[dict[str, Any]],
        repair_history_json: Sequence[dict[str, Any]],
        consumption_batch_id: uuid.UUID | None,
        cluster_verdict_manifest_id: uuid.UUID | None,
    ) -> PublishedReaderDocument:
        previous = self.get_current_by_stable_key(stable_key=stable_key)
        version = int(getattr(previous, "version", 0) or 0) + 1
        previous_id = None
        if previous is not None:
            previous.is_current = False
            previous_id = previous.id
            self.db.add(previous)
        document = PublishedReaderDocument(
            stable_key=stable_key,
            slug=slug,
            window_id=window_id,
            topic_key=topic_key,
            topic_label=topic_label,
            title=title,
            summary=summary,
            markdown=markdown,
            reader_output_locale=reader_output_locale,
            reader_style_profile=reader_style_profile,
            materialization_mode=materialization_mode,
            version=version,
            published_with_gap=published_with_gap,
            is_current=True,
            source_item_count=source_item_count,
            consumption_batch_id=consumption_batch_id,
            cluster_verdict_manifest_id=cluster_verdict_manifest_id,
            supersedes_document_id=previous_id,
            warning_json=warning_json,
            coverage_ledger_json=coverage_ledger_json,
            traceability_pack_json=traceability_pack_json,
            source_refs_json=list(source_refs_json),
            sections_json=list(sections_json),
            repair_history_json=list(repair_history_json),
        )
        self.db.add(document)
        self.db.flush()
        return document

    def get_by_slug(self, *, slug: str) -> PublishedReaderDocument | None:
        stmt = select(PublishedReaderDocument).where(PublishedReaderDocument.slug == slug).limit(1)
        return self.db.scalar(stmt)
