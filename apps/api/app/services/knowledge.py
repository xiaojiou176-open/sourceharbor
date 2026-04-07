from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from ..repositories import KnowledgeCardsRepository


class KnowledgeService:
    def __init__(self, db: Session) -> None:
        self.repo = KnowledgeCardsRepository(db)

    def list_cards(
        self,
        *,
        job_id: uuid.UUID | None = None,
        video_id: uuid.UUID | None = None,
        card_type: str | None = None,
        topic_key: str | None = None,
        claim_kind: str | None = None,
        limit: int = 50,
    ):
        rows = self.repo.list(
            job_id=job_id,
            video_id=video_id,
            card_type=card_type,
            limit=max(limit * 4, limit),
        )
        normalized_topic = str(topic_key or "").strip().lower() or None
        normalized_claim_kind = str(claim_kind or "").strip().lower() or None
        filtered = []
        for row in rows:
            metadata = row.metadata_json if isinstance(row.metadata_json, dict) else {}
            if normalized_topic is not None:
                row_topic = str(metadata.get("topic_key") or "").strip().lower()
                if row_topic != normalized_topic:
                    continue
            if normalized_claim_kind is not None:
                row_claim_kind = str(metadata.get("claim_kind") or "").strip().lower()
                if row_claim_kind != normalized_claim_kind:
                    continue
            filtered.append(row)
            if len(filtered) >= limit:
                break
        return filtered
