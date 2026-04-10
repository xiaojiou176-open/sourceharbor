from __future__ import annotations

import re
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from ..repositories import (
    ClusterVerdictManifestsRepository,
    ConsumptionBatchesRepository,
    PublishedReaderDocumentsRepository,
)
from .jobs import JobsService

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


class ReaderPipelineService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.batch_repo = ConsumptionBatchesRepository(db)
        self.manifest_repo = ClusterVerdictManifestsRepository(db)
        self.document_repo = PublishedReaderDocumentsRepository(db)
        self.jobs_service = JobsService(db)

    def get_manifest(self, *, batch_id: uuid.UUID):
        return self.manifest_repo.get_by_batch_id(consumption_batch_id=batch_id)

    def list_documents(
        self, *, limit: int = 20, window_id: str | None = None
    ) -> list[dict[str, Any]]:
        return self.list_published_documents(limit=limit, window_id=window_id)

    def get_navigation_brief(
        self, *, limit: int = 8, window_id: str | None = None
    ) -> dict[str, Any]:
        return self.build_navigation_brief(window_id=window_id, limit=limit)

    def get_document(self, *, document_id: uuid.UUID) -> dict[str, Any] | None:
        return self.get_published_document(document_id=document_id)

    def get_document_by_slug(self, *, slug: str) -> dict[str, Any] | None:
        document = self.document_repo.get_by_slug(slug=slug)
        if document is None:
            return None
        return self._to_document_payload(document)

    def get_published_document_by_slug(self, *, slug: str) -> dict[str, Any] | None:
        return self.get_document_by_slug(slug=slug)

    def judge_batch(self, *, batch_id: uuid.UUID) -> dict[str, Any]:
        batch = self.batch_repo.get_with_items(batch_id=batch_id)
        if batch is None:
            raise ValueError("consumption batch not found")
        if not batch.items:
            raise ValueError("consumption batch has no items to judge")

        items = [self._build_source_item_payload(item) for item in batch.items]
        cluster_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        singletons: list[dict[str, Any]] = []

        for item in items:
            cluster_key = str(item.get("cluster_key") or "").strip()
            if cluster_key.startswith("topic:"):
                cluster_groups[cluster_key].append(item)
            else:
                singletons.append(self._build_singleton_payload(item))

        clusters: list[dict[str, Any]] = []
        for cluster_key, members in sorted(cluster_groups.items()):
            if len(members) < 2:
                singletons.extend(self._build_singleton_payload(member) for member in members)
                continue
            clusters.append(self._build_cluster_payload(cluster_key=cluster_key, members=members))

        clusters.sort(
            key=lambda item: (item["source_item_count"], item["topic_label"], item["cluster_key"]),
            reverse=True,
        )
        singletons.sort(key=lambda item: (item["published_at"] or "", item["title"]), reverse=True)

        cluster_count = len(clusters)
        singleton_count = len(singletons)
        source_item_count = len(items)
        status = "gap_detected" if singleton_count and cluster_count == 0 else "ready"
        generated_at = datetime.now(UTC).isoformat()
        summary_markdown = self._build_summary_markdown(
            window_id=batch.window_id,
            source_item_count=source_item_count,
            clusters=clusters,
            singletons=singletons,
        )
        manifest = {
            "manifest_kind": "sourceharbor_cluster_verdict_manifest_v1",
            "generated_at": generated_at,
            "consumption_batch_id": str(batch.id),
            "window_id": batch.window_id,
            "status": status,
            "source_item_count": source_item_count,
            "cluster_count": cluster_count,
            "singleton_count": singleton_count,
            "clusters": clusters,
            "singletons": singletons,
        }
        instance = self.manifest_repo.upsert_for_batch(
            consumption_batch_id=batch.id,
            window_id=batch.window_id,
            status=status,
            manifest_json=manifest,
            source_item_count=source_item_count,
            cluster_count=cluster_count,
            singleton_count=singleton_count,
            summary_markdown=summary_markdown,
        )
        if hasattr(self.batch_repo, "mark_judged"):
            self.batch_repo.mark_judged(
                batch_id=batch.id,
                manifest_id=instance.id,
                manifest_status=status,
                cluster_count=cluster_count,
                singleton_count=singleton_count,
            )
        return self._to_manifest_payload(instance)

    def materialize_batch(
        self,
        *,
        batch_id: uuid.UUID,
        reader_output_locale: str = "zh-CN",
        reader_style_profile: str = "briefing",
    ) -> dict[str, Any]:
        batch = self.batch_repo.get_with_items(batch_id=batch_id)
        if batch is None:
            raise ValueError("consumption batch not found")
        manifest_instance = self.get_manifest(batch_id=batch_id)
        if manifest_instance is None:
            self.judge_batch(batch_id=batch_id)
            manifest_instance = self.get_manifest(batch_id=batch_id)
        if manifest_instance is None:
            raise ValueError("cluster verdict manifest not found")

        manifest = (
            manifest_instance.manifest_json
            if isinstance(manifest_instance.manifest_json, dict)
            else {}
        )
        item_payloads = [self._build_source_item_payload(item) for item in batch.items]
        for item_payload in item_payloads:
            item_payload["window_id"] = batch.window_id
        source_items = {str(item["source_item_id"]): item for item in item_payloads}

        documents = []
        for cluster in manifest.get("clusters") or []:
            if not isinstance(cluster, dict):
                continue
            source_refs = [
                source_items[source_item_id]
                for source_item_id in cluster.get("source_item_ids") or []
                if source_item_id in source_items
            ]
            if not source_refs:
                continue
            document = self._materialize_document(
                stable_key=self._stable_key(
                    topic_key=str(cluster.get("topic_key") or "").strip() or None,
                    source_item_id=str(source_refs[0]["source_item_id"]),
                    window_id=batch.window_id,
                ),
                base_slug=self._base_slug(
                    topic_key=str(cluster.get("topic_key") or "").strip() or None,
                    source_item_id=str(source_refs[0]["source_item_id"]),
                    window_id=batch.window_id,
                ),
                title=str(cluster.get("headline") or "").strip() or "Merged reader document",
                summary=self._cluster_summary(cluster=cluster, source_refs=source_refs),
                markdown=self._render_cluster_markdown(cluster=cluster, source_refs=source_refs),
                topic_key=str(cluster.get("topic_key") or "").strip() or None,
                topic_label=str(cluster.get("topic_label") or "").strip() or None,
                materialization_mode="merge_then_polish",
                source_refs=source_refs,
                window_id=batch.window_id,
                consumption_batch_id=batch.id,
                cluster_verdict_manifest_id=manifest_instance.id,
                reader_output_locale=reader_output_locale,
                reader_style_profile=reader_style_profile,
                strategy=None,
            )
            documents.append(document)

        for singleton in manifest.get("singletons") or []:
            if not isinstance(singleton, dict):
                continue
            source_item_id = str(singleton.get("source_item_id") or "").strip()
            source_ref = source_items.get(source_item_id)
            if source_ref is None:
                continue
            document = self._materialize_document(
                stable_key=self._stable_key(
                    topic_key=str(singleton.get("topic_key") or "").strip() or None,
                    source_item_id=source_item_id,
                    window_id=batch.window_id,
                ),
                base_slug=self._base_slug(
                    topic_key=str(singleton.get("topic_key") or "").strip() or None,
                    source_item_id=source_item_id,
                    window_id=batch.window_id,
                ),
                title=str(singleton.get("title") or "").strip() or "Reader document",
                summary=self._singleton_summary(source_ref),
                markdown=self._render_singleton_markdown(source_ref=source_ref),
                topic_key=str(singleton.get("topic_key") or "").strip() or None,
                topic_label=str(singleton.get("topic_label") or "").strip() or None,
                materialization_mode="polish_only",
                source_refs=[source_ref],
                window_id=batch.window_id,
                consumption_batch_id=batch.id,
                cluster_verdict_manifest_id=manifest_instance.id,
                reader_output_locale=reader_output_locale,
                reader_style_profile=reader_style_profile,
                strategy=None,
            )
            documents.append(document)

        self.db.commit()
        for document in documents:
            self.db.refresh(document)
        document_payloads = [self._to_document_payload(document) for document in documents]
        navigation_brief = self.build_navigation_brief(
            window_id=batch.window_id,
            limit=max(len(documents), 1),
        )
        return {
            "consumption_batch_id": str(batch.id),
            "cluster_verdict_manifest_id": str(manifest_instance.id),
            "window_id": batch.window_id,
            "document_count": len(documents),
            "published_document_count": len(documents),
            "published_with_gap_count": sum(
                1 for item in document_payloads if bool(item.get("published_with_gap"))
            ),
            "documents": document_payloads,
            "navigation_brief": navigation_brief,
        }

    def list_published_documents(
        self, *, limit: int = 20, window_id: str | None = None
    ) -> list[dict[str, Any]]:
        documents = self.document_repo.list_current(limit=limit, window_id=window_id)
        return [self._to_document_payload(item) for item in documents]

    def get_published_document(self, *, document_id: uuid.UUID) -> dict[str, Any] | None:
        document = self.document_repo.get(document_id=document_id)
        if document is None:
            return None
        return self._to_document_payload(document)

    def build_navigation_brief(
        self, *, window_id: str | None = None, limit: int = 8
    ) -> dict[str, Any]:
        documents = self.list_published_documents(limit=limit, window_id=window_id)
        resolved_window_id = window_id or (
            str(documents[0]["window_id"]) if documents else datetime.now(UTC).date().isoformat()
        )
        return self._navigation_payload_from_documents(
            documents=documents,
            window_id=resolved_window_id,
        )

    def repair_document(
        self,
        *,
        document_id: uuid.UUID,
        repair_mode: str | None = None,
        section_ids: list[str] | None = None,
        strategy: str | None = None,
    ) -> dict[str, Any]:
        document = self.document_repo.get(document_id=document_id)
        if document is None:
            raise ValueError("published reader document not found")

        normalized_strategy = str(repair_mode or strategy or "patch").strip().lower() or "patch"
        if normalized_strategy not in {"patch", "section", "cluster"}:
            raise ValueError("repair strategy must be one of: patch, section, cluster")

        if normalized_strategy == "cluster":
            if document.consumption_batch_id is None:
                raise ValueError("cluster repair requires consumption batch context")
            payload = self.materialize_batch(
                batch_id=document.consumption_batch_id,
                reader_output_locale=document.reader_output_locale,
                reader_style_profile=document.reader_style_profile,
            )
            stable_key = str(document.stable_key or "").strip()
            for candidate in payload.get("documents") or []:
                if (
                    isinstance(candidate, dict)
                    and str(candidate.get("stable_key") or "").strip() == stable_key
                ):
                    return candidate
            raise ValueError("cluster repair did not produce a replacement document")

        source_refs = [item for item in (document.source_refs_json or []) if isinstance(item, dict)]
        if not source_refs:
            raise ValueError("published reader document has no source refs to repair")

        if normalized_strategy == "patch":
            summary = str(document.summary or "").strip() or self._repair_summary(source_refs)
            sections = [
                item for item in (document.sections_json or []) if isinstance(item, dict)
            ] or self._build_singleton_sections(source_refs)
            markdown = self._render_sections_as_markdown(
                title=str(document.title),
                summary=summary,
                sections=sections,
                warning_json={},
            )
            materialization_mode = "repair_patch"
        else:
            summary = self._repair_summary(source_refs)
            sections = self._build_repair_sections(source_refs)
            markdown = self._render_sections_as_markdown(
                title=str(document.title),
                summary=summary,
                sections=sections,
                warning_json={},
            )
            materialization_mode = "repair_section"

        replacement = self._materialize_document(
            stable_key=str(document.stable_key),
            base_slug=self._base_slug(
                topic_key=str(document.topic_key or "").strip() or None,
                source_item_id=str(source_refs[0].get("source_item_id") or document.id),
                window_id=str(document.window_id),
            ),
            title=str(document.title),
            summary=summary,
            markdown=markdown,
            topic_key=str(document.topic_key or "").strip() or None,
            topic_label=str(document.topic_label or "").strip() or None,
            materialization_mode=materialization_mode,
            source_refs=source_refs,
            window_id=str(document.window_id),
            consumption_batch_id=document.consumption_batch_id,
            cluster_verdict_manifest_id=document.cluster_verdict_manifest_id,
            reader_output_locale=document.reader_output_locale,
            reader_style_profile=document.reader_style_profile,
            strategy=normalized_strategy,
            prior_repair_history=[
                item for item in (document.repair_history_json or []) if isinstance(item, dict)
            ],
            repaired_from_document_id=document.id,
            section_ids=section_ids or [],
        )
        self.db.commit()
        self.db.refresh(replacement)
        return self._to_document_payload(replacement)

    def _materialize_document(
        self,
        *,
        stable_key: str,
        base_slug: str,
        title: str,
        summary: str | None,
        markdown: str,
        topic_key: str | None,
        topic_label: str | None,
        materialization_mode: str,
        source_refs: list[dict[str, Any]],
        window_id: str,
        consumption_batch_id: uuid.UUID | None,
        cluster_verdict_manifest_id: uuid.UUID | None,
        reader_output_locale: str,
        reader_style_profile: str,
        strategy: str | None,
        prior_repair_history: list[dict[str, Any]] | None = None,
        repaired_from_document_id: uuid.UUID | None = None,
        section_ids: list[str] | None = None,
    ):
        previous = self.document_repo.get_current_by_stable_key(stable_key=stable_key)
        next_version = int(getattr(previous, "version", 0) or 0) + 1
        slug = f"{base_slug}-v{next_version}"
        sections = (
            self._build_cluster_sections(source_refs)
            if materialization_mode == "merge_then_polish"
            else self._build_singleton_sections(source_refs)
        )
        if materialization_mode.startswith("repair_"):
            sections = self._build_repair_sections(source_refs)
        coverage = self._build_coverage_ledger(source_refs=source_refs, sections=sections)
        traceability = self._build_traceability_pack(source_refs=source_refs, sections=sections)
        warning_json = self._build_warning_json(
            coverage_ledger=coverage,
            traceability_pack=traceability,
        )
        published_with_gap = bool(warning_json.get("published_with_gap"))
        repair_history = list(prior_repair_history or [])
        if strategy:
            repair_history.append(
                {
                    "strategy": strategy,
                    "repair_mode": strategy,
                    "section_ids": list(section_ids or []),
                    "repaired_from_document_id": str(repaired_from_document_id)
                    if repaired_from_document_id
                    else None,
                    "generated_at": datetime.now(UTC).isoformat(),
                }
            )
        document = self.document_repo.replace_current(
            stable_key=stable_key,
            slug=slug,
            window_id=window_id,
            topic_key=topic_key,
            topic_label=topic_label,
            title=title,
            summary=summary,
            markdown=self._render_sections_as_markdown(
                title=title,
                summary=summary,
                sections=sections,
                warning_json=warning_json,
                body_markdown=markdown,
            ),
            reader_output_locale=reader_output_locale,
            reader_style_profile=reader_style_profile,
            materialization_mode=materialization_mode,
            published_with_gap=published_with_gap,
            source_item_count=len(source_refs),
            warning_json=warning_json,
            coverage_ledger_json=coverage,
            traceability_pack_json=traceability,
            source_refs_json=source_refs,
            sections_json=sections,
            repair_history_json=repair_history,
            consumption_batch_id=consumption_batch_id,
            cluster_verdict_manifest_id=cluster_verdict_manifest_id,
        )
        coverage["published_doc_id"] = str(document.id)
        traceability["published_doc_id"] = str(document.id)
        traceability["stable_key"] = stable_key
        traceability["version"] = int(document.version or 0)
        traceability["warning_summary"] = warning_json if published_with_gap else None
        document.coverage_ledger_json = coverage
        document.traceability_pack_json = traceability
        self.db.add(document)
        return document

    def _build_source_item_payload(self, item: Any) -> dict[str, Any]:
        job_id = getattr(item, "job_id", None)
        digest_markdown: str | None = None
        knowledge_cards: list[dict[str, Any]] = []
        if isinstance(job_id, uuid.UUID):
            digest_markdown = self.jobs_service.get_artifact_digest_md(
                job_id=job_id, video_url=None
            )
            knowledge_cards = self.jobs_service.get_knowledge_cards(job_id=job_id) or []
        topic_counter: Counter[str] = Counter()
        topic_labels: dict[str, str] = {}
        claim_kinds: set[str] = set()
        for card in knowledge_cards:
            topic_key = str(card.get("topic_key") or "").strip()
            topic_label = str(card.get("topic_label") or "").strip()
            claim_kind = str(card.get("claim_kind") or "").strip()
            if topic_key:
                topic_counter[topic_key] += 1
                if topic_label and topic_key not in topic_labels:
                    topic_labels[topic_key] = topic_label
            if claim_kind:
                claim_kinds.add(claim_kind)

        dominant_topic_key = topic_counter.most_common(1)[0][0] if topic_counter else None
        dominant_topic_label = (
            topic_labels.get(dominant_topic_key or "")
            or self._humanize_topic_key(dominant_topic_key)
            or None
        )
        title = str(getattr(item, "title", None) or "").strip() or "Untitled source item"
        digest_preview = self._digest_preview(digest_markdown, fallback=title)
        return {
            "source_item_id": str(item.id),
            "ingest_run_item_id": str(getattr(item, "ingest_run_item_id", None) or "").strip()
            or None,
            "job_id": str(job_id) if isinstance(job_id, uuid.UUID) else None,
            "platform": str(getattr(item, "platform", "") or "").strip() or "unknown",
            "source_origin": str(getattr(item, "source_origin", "") or "").strip()
            or "subscription_tracked",
            "content_type": str(getattr(item, "content_type", "") or "").strip() or "video",
            "title": title,
            "source_url": str(getattr(item, "source_url", "") or "").strip() or None,
            "published_at": self._isoformat(getattr(item, "published_at", None)),
            "claim_kinds": sorted(claim_kinds),
            "topic_keys": sorted(topic_counter),
            "dominant_topic_key": dominant_topic_key,
            "topic_label": dominant_topic_label,
            "digest_markdown": digest_markdown,
            "digest_preview": digest_preview,
            "knowledge_cards": knowledge_cards,
            "cluster_key": (
                f"topic:{dominant_topic_key}" if dominant_topic_key else f"singleton:{item.id}"
            ),
            "window_id": None,
        }

    def _build_cluster_payload(
        self, *, cluster_key: str, members: list[dict[str, Any]]
    ) -> dict[str, Any]:
        topic_key = cluster_key.removeprefix("topic:").strip() or None
        topic_label = next(
            (
                str(item.get("topic_label") or "").strip()
                for item in members
                if str(item.get("topic_label") or "").strip()
            ),
            self._humanize_topic_key(topic_key),
        )
        claim_kinds = sorted(
            {
                claim_kind
                for item in members
                for claim_kind in (item.get("claim_kinds") or [])
                if isinstance(claim_kind, str) and claim_kind.strip()
            }
        )
        return {
            "cluster_id": f"cluster-{self._slugify(cluster_key)}",
            "cluster_key": cluster_key,
            "topic_key": topic_key,
            "topic_label": topic_label,
            "decision": "merge_then_polish",
            "source_item_count": len(members),
            "source_item_ids": [str(item["source_item_id"]) for item in members],
            "job_ids": [item["job_id"] for item in members if item.get("job_id")],
            "platforms": sorted(
                {
                    str(item.get("platform") or "").strip()
                    for item in members
                    if str(item.get("platform") or "").strip()
                }
            ),
            "claim_kinds": claim_kinds,
            "headline": topic_label or f"Cluster {cluster_key}",
            "digest_preview": members[0]["digest_preview"],
            "members": [self._to_member_payload(item) for item in members],
        }

    def _build_singleton_payload(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "singleton_id": f"singleton-{self._slugify(str(item['source_item_id']))}",
            "source_item_id": str(item["source_item_id"]),
            "ingest_run_item_id": item.get("ingest_run_item_id"),
            "job_id": item.get("job_id"),
            "platform": item.get("platform"),
            "source_origin": item.get("source_origin"),
            "content_type": item.get("content_type"),
            "title": item.get("title"),
            "source_url": item.get("source_url"),
            "published_at": item.get("published_at"),
            "topic_key": item.get("dominant_topic_key"),
            "topic_label": item.get("topic_label"),
            "claim_kinds": list(item.get("claim_kinds") or []),
            "decision": "polish_only",
            "digest_preview": item.get("digest_preview"),
        }

    def _to_member_payload(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "source_item_id": str(item["source_item_id"]),
            "job_id": item.get("job_id"),
            "platform": item.get("platform"),
            "source_origin": item.get("source_origin"),
            "title": item.get("title"),
            "source_url": item.get("source_url"),
            "published_at": item.get("published_at"),
            "claim_kinds": list(item.get("claim_kinds") or []),
            "digest_preview": item.get("digest_preview"),
        }

    def _to_manifest_payload(self, instance: Any) -> dict[str, Any]:
        manifest = instance.manifest_json if isinstance(instance.manifest_json, dict) else {}
        return {
            "id": str(instance.id),
            "consumption_batch_id": str(instance.consumption_batch_id),
            "window_id": instance.window_id,
            "status": instance.status,
            "source_item_count": instance.source_item_count,
            "cluster_count": instance.cluster_count,
            "singleton_count": instance.singleton_count,
            "summary_markdown": instance.summary_markdown,
            "manifest": manifest,
            "created_at": instance.created_at,
            "updated_at": instance.updated_at,
        }

    def _to_document_payload(self, instance: Any) -> dict[str, Any]:
        return {
            "id": str(instance.id),
            "stable_key": instance.stable_key,
            "slug": instance.slug,
            "window_id": instance.window_id,
            "topic_key": instance.topic_key,
            "topic_label": instance.topic_label,
            "title": instance.title,
            "summary": instance.summary,
            "markdown": instance.markdown,
            "reader_output_locale": instance.reader_output_locale,
            "reader_style_profile": instance.reader_style_profile,
            "materialization_mode": instance.materialization_mode,
            "version": instance.version,
            "published_with_gap": bool(instance.published_with_gap),
            "is_current": bool(instance.is_current),
            "source_item_count": int(instance.source_item_count or 0),
            "consumption_batch_id": str(instance.consumption_batch_id)
            if instance.consumption_batch_id
            else None,
            "cluster_verdict_manifest_id": str(instance.cluster_verdict_manifest_id)
            if instance.cluster_verdict_manifest_id
            else None,
            "supersedes_document_id": str(instance.supersedes_document_id)
            if instance.supersedes_document_id
            else None,
            "warning": dict(instance.warning_json or {}),
            "coverage_ledger": dict(instance.coverage_ledger_json or {}),
            "traceability_pack": dict(instance.traceability_pack_json or {}),
            "source_refs": list(instance.source_refs_json or []),
            "sections": [
                {
                    "section_id": str(item.get("section_id") or item.get("section_key") or ""),
                    "title": str(item.get("title") or ""),
                    "markdown": str(item.get("markdown") or ""),
                    "source_item_ids": list(item.get("source_item_ids") or []),
                }
                for item in (instance.sections_json or [])
                if isinstance(item, dict)
            ],
            "repair_history": list(instance.repair_history_json or []),
            "created_at": instance.created_at,
            "updated_at": instance.updated_at,
        }

    def _build_summary_markdown(
        self,
        *,
        window_id: str,
        source_item_count: int,
        clusters: list[dict[str, Any]],
        singletons: list[dict[str, Any]],
    ) -> str:
        lines = [
            f"# Cluster verdict manifest for {window_id}",
            "",
            f"- Source items: {source_item_count}",
            f"- Merge-ready clusters: {len(clusters)}",
            f"- Polish-only singletons: {len(singletons)}",
            "",
        ]
        if clusters:
            lines.append("## Merge-ready clusters")
            for cluster in clusters:
                lines.append(
                    f"- {cluster['headline']} ({cluster['source_item_count']} sources; decision = merge_then_polish)"
                )
            lines.append("")
        if singletons:
            lines.append("## Polish-only singletons")
            for item in singletons:
                lines.append(f"- {item['title']} ({item['platform']}; decision = polish_only)")
        return "\n".join(lines).strip()

    def _cluster_summary(
        self, *, cluster: dict[str, Any], source_refs: list[dict[str, Any]]
    ) -> str:
        headline = str(cluster.get("headline") or "").strip() or "Merged reader document"
        sources = len(source_refs)
        platforms = sorted(
            {
                str(item.get("platform") or "").strip()
                for item in source_refs
                if str(item.get("platform") or "").strip()
            }
        )
        platform_label = ", ".join(platforms) if platforms else "mixed sources"
        return (
            f"{headline} merges {sources} source items from {platform_label} into one "
            "reader-facing document."
        )

    def _singleton_summary(self, source_ref: dict[str, Any]) -> str:
        title = str(source_ref.get("title") or "").strip() or "Reader document"
        platform = str(source_ref.get("platform") or "").strip() or "unknown"
        return f"{title} remains a polish-only reader document from {platform}."

    def _build_cluster_sections(self, source_refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        topic_items = sorted(
            {
                str(card.get("topic_label") or card.get("topic_key") or "").strip()
                for source_ref in source_refs
                for card in (source_ref.get("knowledge_cards") or [])
                if isinstance(card, dict)
                and str(card.get("topic_label") or card.get("topic_key") or "").strip()
            }
        )
        claim_items = sorted(
            {
                str(claim_kind).strip()
                for source_ref in source_refs
                for claim_kind in (source_ref.get("claim_kinds") or [])
                if str(claim_kind).strip()
            }
        )
        overview_markdown = "\n".join(
            [f"- {item}" for item in topic_items[:6]]
            or [f"- {source_ref['digest_preview']}" for source_ref in source_refs[:3]]
        )
        signal_markdown = "\n".join(
            [f"- {item}" for item in claim_items[:6]]
            or [f"- {source_ref['digest_preview']}" for source_ref in source_refs[:3]]
        )
        source_notes = []
        for source_ref in source_refs:
            title = str(source_ref.get("title") or "").strip() or "Untitled source"
            preview = str(source_ref.get("digest_preview") or "").strip() or title
            source_url = str(source_ref.get("source_url") or "").strip()
            platform = str(source_ref.get("platform") or "").strip() or "unknown"
            source_notes.append(
                "\n".join(
                    [
                        f"### {title}",
                        f"- Platform: {platform}",
                        f"- Preview: {preview}",
                        f"- Source: {source_url}" if source_url else "- Source: unavailable",
                    ]
                )
            )
        all_source_item_ids = [str(item["source_item_id"]) for item in source_refs]
        return [
            {
                "section_key": "overview",
                "section_id": "overview",
                "title": "Overview",
                "kind": "overview",
                "markdown": overview_markdown,
                "source_item_ids": all_source_item_ids,
            },
            {
                "section_key": "key-signals",
                "section_id": "key-signals",
                "title": "Key Signals",
                "kind": "signals",
                "markdown": signal_markdown,
                "source_item_ids": all_source_item_ids,
            },
            {
                "section_key": "source-contributions",
                "section_id": "source-contributions",
                "title": "Source Contributions",
                "kind": "source_contributions",
                "markdown": "\n\n".join(source_notes),
                "source_item_ids": all_source_item_ids,
            },
        ]

    def _build_singleton_sections(self, source_refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        source_ref = source_refs[0]
        source_item_id = str(source_ref["source_item_id"])
        preview = str(source_ref.get("digest_preview") or "").strip() or "No preview available."
        source_url = str(source_ref.get("source_url") or "").strip()
        source_markdown = "\n".join(
            [
                f"- Platform: {str(source_ref.get('platform') or '').strip() or 'unknown'}",
                f"- Source origin: {str(source_ref.get('source_origin') or '').strip() or 'subscription_tracked'}",
                f"- Source: {source_url}" if source_url else "- Source: unavailable",
            ]
        )
        return [
            {
                "section_key": "summary",
                "section_id": "summary",
                "title": "Summary",
                "kind": "summary",
                "markdown": preview,
                "source_item_ids": [source_item_id],
            },
            {
                "section_key": "source-context",
                "section_id": "source-context",
                "title": "Source Context",
                "kind": "source_context",
                "markdown": source_markdown,
                "source_item_ids": [source_item_id],
            },
        ]

    def _build_repair_sections(self, source_refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sections = (
            self._build_cluster_sections(source_refs)
            if len(source_refs) > 1
            else self._build_singleton_sections(source_refs)
        )
        missing_ref_lines = []
        for source_ref in source_refs:
            title = str(source_ref.get("title") or "").strip() or "Untitled source"
            preview = str(source_ref.get("digest_preview") or "").strip() or "No preview available."
            missing_ref_lines.append(f"- {title}: {preview}")
        sections.append(
            {
                "section_key": "repair-notes",
                "section_id": "repair-notes",
                "title": "Repair Notes",
                "kind": "repair_notes",
                "markdown": "\n".join(missing_ref_lines),
                "source_item_ids": [str(item["source_item_id"]) for item in source_refs],
            }
        )
        return sections

    def _render_cluster_markdown(
        self, *, cluster: dict[str, Any], source_refs: list[dict[str, Any]]
    ) -> str:
        summary = self._cluster_summary(cluster=cluster, source_refs=source_refs)
        sections = self._build_cluster_sections(source_refs)
        return self._render_sections_as_markdown(
            title=str(cluster.get("headline") or "").strip() or "Merged reader document",
            summary=summary,
            sections=sections,
            warning_json={},
        )

    def _render_singleton_markdown(self, *, source_ref: dict[str, Any]) -> str:
        summary = self._singleton_summary(source_ref)
        sections = self._build_singleton_sections([source_ref])
        return self._render_sections_as_markdown(
            title=str(source_ref.get("title") or "").strip() or "Reader document",
            summary=summary,
            sections=sections,
            warning_json={},
        )

    def _render_sections_as_markdown(
        self,
        *,
        title: str,
        summary: str | None,
        sections: list[dict[str, Any]],
        warning_json: dict[str, Any],
        body_markdown: str | None = None,
    ) -> str:
        lines = [f"# {title}", ""]
        summary_text = str(summary or "").strip()
        if summary_text:
            lines.extend([summary_text, ""])
        if warning_json and bool(warning_json.get("published_with_gap")):
            lines.extend(
                [
                    "## Yellow Warning",
                    str(warning_json.get("summary") or "Coverage or traceability gap detected."),
                    "",
                ]
            )
        if body_markdown:
            body = str(body_markdown).strip()
            if body:
                lines.extend([body, ""])
        for section in sections:
            section_title = str(section.get("title") or "").strip()
            section_markdown = str(section.get("markdown") or "").strip()
            if not section_title or not section_markdown:
                continue
            lines.extend([f"## {section_title}", section_markdown, ""])
        return "\n".join(lines).strip()

    def _build_coverage_ledger(
        self, *, source_refs: list[dict[str, Any]], sections: list[dict[str, Any]]
    ) -> dict[str, Any]:
        section_index = {
            str(section.get("section_key") or "").strip(): [
                str(source_item_id).strip()
                for source_item_id in (section.get("source_item_ids") or [])
                if str(source_item_id).strip()
            ]
            for section in sections
            if isinstance(section, dict)
        }
        entries = []
        gap_count = 0
        for source_ref in source_refs:
            source_item_id = str(source_ref.get("source_item_id") or "").strip()
            missing_digest = not str(source_ref.get("digest_markdown") or "").strip()
            required_topics = sorted(
                {
                    str(card.get("topic_key") or "").strip()
                    for card in (source_ref.get("knowledge_cards") or [])
                    if isinstance(card, dict) and str(card.get("topic_key") or "").strip()
                }
            )
            coverage_sections = [
                section_key
                for section_key, source_item_ids in section_index.items()
                if source_item_id in source_item_ids
            ]
            covered_topics = required_topics if coverage_sections else []
            missing_topics = [] if covered_topics else required_topics
            gap_flags = []
            if missing_topics:
                gap_flags.append("missing_topics")
            if missing_digest:
                gap_flags.append("missing_digest")
            entry_status = "pass" if not gap_flags else "gap_detected"
            if entry_status != "pass":
                gap_count += 1
            entries.append(
                {
                    "source_item_id": source_item_id,
                    "required_topics": required_topics,
                    "covered_topics": covered_topics,
                    "missing_topics": missing_topics,
                    "sections": coverage_sections,
                    "missing_digest": missing_digest,
                    "gap_flags": gap_flags,
                    "status": entry_status,
                }
            )
        gap_reasons = sorted(
            {
                flag
                for entry in entries
                for flag in entry.get("gap_flags") or []
                if isinstance(flag, str) and flag.strip()
            }
        )
        return {
            "ledger_kind": "sourceharbor_coverage_ledger_v1",
            "coverage_ledger_id": str(uuid.uuid4()),
            "published_doc_id": None,
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "pass" if gap_count == 0 else "gap_detected",
            "gap_count": gap_count,
            "gap_reasons": gap_reasons,
            "entries": entries,
        }

    def _build_traceability_pack(
        self, *, source_refs: list[dict[str, Any]], sections: list[dict[str, Any]]
    ) -> dict[str, Any]:
        section_contributions = []
        for section in sections:
            source_item_ids = [
                str(item).strip()
                for item in (section.get("source_item_ids") or [])
                if str(item).strip()
            ]
            contributing_refs = [
                source_ref
                for source_ref in source_refs
                if str(source_ref.get("source_item_id") or "").strip() in source_item_ids
            ]
            job_ids = [
                str(item.get("job_id") or "").strip()
                for item in contributing_refs
                if str(item.get("job_id") or "").strip()
            ]
            section_contributions.append(
                {
                    "section_key": str(section.get("section_key") or "").strip(),
                    "section_id": str(
                        section.get("section_id") or section.get("section_key") or ""
                    ).strip(),
                    "section_heading": str(section.get("title") or "").strip(),
                    "section_title": str(section.get("title") or "").strip(),
                    "source_item_ids": source_item_ids,
                    "primary_source_item_ids": source_item_ids[:1],
                    "claim_refs": sorted(
                        {
                            str(claim_kind).strip()
                            for item in contributing_refs
                            for claim_kind in (item.get("claim_kinds") or [])
                            if str(claim_kind).strip()
                        }
                    ),
                    "evidence_anchor_refs": [f"/api/v1/jobs/{job_id}/bundle" for job_id in job_ids],
                    "job_ids": job_ids,
                }
            )
        source_item_map = []
        evidence_routes: dict[str, list[str]] = {
            "artifact_markdown": [],
            "job_bundle": [],
            "job_knowledge_cards": [],
        }
        for source_ref in source_refs:
            job_id = str(source_ref.get("job_id") or "").strip()
            routes = {
                "artifact_markdown": f"/api/v1/artifacts/markdown?job_id={job_id}&include_meta=true"
                if job_id
                else None,
                "job_bundle": f"/api/v1/jobs/{job_id}/bundle" if job_id else None,
                "job_knowledge_cards": f"/knowledge?job_id={job_id}" if job_id else None,
            }
            source_item_map.append(
                {
                    "source_item_id": str(source_ref.get("source_item_id") or "").strip(),
                    "job_id": job_id or None,
                    "title": str(source_ref.get("title") or "").strip() or "Untitled source",
                    "platform": str(source_ref.get("platform") or "").strip() or "unknown",
                    "source_url": str(source_ref.get("source_url") or "").strip() or None,
                    "published_at": source_ref.get("published_at"),
                    "raw_artifacts": {
                        "digest": str(source_ref.get("digest_markdown") or "").strip() or None,
                        "transcript": None,
                        "comments": None,
                        "outline": None,
                        "frames": None,
                    },
                    "routes": routes,
                }
            )
            for key, value in routes.items():
                if value:
                    evidence_routes[key].append(value)
        has_gap = any(not item["source_item_ids"] for item in section_contributions)
        return {
            "pack_kind": "sourceharbor_traceability_pack_v1",
            "generated_at": datetime.now(UTC).isoformat(),
            "published_doc_id": None,
            "stable_key": None,
            "version": None,
            "status": "gap_detected" if has_gap else "ready",
            "source_items": source_item_map,
            "source_item_map": source_item_map,
            "evidence_routes": evidence_routes,
            "section_contributions": section_contributions,
            "warning_summary": None,
        }

    def _build_warning_json(
        self, *, coverage_ledger: dict[str, Any], traceability_pack: dict[str, Any]
    ) -> dict[str, Any]:
        coverage_status = str(coverage_ledger.get("status") or "").strip()
        traceability_status = str(traceability_pack.get("status") or "").strip()
        if coverage_status == "pass" and traceability_status == "ready":
            return {
                "warning_kind": "none",
                "published_with_gap": False,
                "reasons": [],
                "failed_source_count": 0,
                "degraded_source_count": 0,
                "missing_digest_count": 0,
                "generated_at": datetime.now(UTC).isoformat(),
            }
        kind = "coverage_gap" if coverage_status != "pass" else "traceability_gap"
        reasons = []
        if coverage_status != "pass":
            missing_digest_count = sum(
                1
                for entry in (coverage_ledger.get("entries") or [])
                if isinstance(entry, dict) and entry.get("missing_digest")
            )
            if missing_digest_count:
                reasons.append(f"{missing_digest_count} source missing digest output")
            if "missing_topics" in set(coverage_ledger.get("gap_reasons") or []):
                reasons.append("coverage ledger reported uncovered source topics")
        if traceability_status != "ready":
            reasons.append("traceability pack reported incomplete section contributions")
        return {
            "warning_kind": kind,
            "kind": kind,
            "published_with_gap": True,
            "reasons": reasons,
            "failed_source_count": sum(
                1
                for entry in (coverage_ledger.get("entries") or [])
                if isinstance(entry, dict) and entry.get("status") != "pass"
            ),
            "degraded_source_count": 0,
            "missing_digest_count": sum(
                1
                for entry in (coverage_ledger.get("entries") or [])
                if isinstance(entry, dict) and entry.get("missing_digest")
            ),
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": "This reader document is readable, but coverage or traceability is still incomplete.",
            "affected_source_item_ids": [
                str(entry.get("source_item_id") or "").strip()
                for entry in (coverage_ledger.get("entries") or [])
                if isinstance(entry, dict) and entry.get("status") != "pass"
            ],
            "status": "published_with_gap",
        }

    def _repair_summary(self, source_refs: list[dict[str, Any]]) -> str:
        titles = [
            str(source_ref.get("title") or "").strip()
            for source_ref in source_refs
            if str(source_ref.get("title") or "").strip()
        ]
        joined = ", ".join(titles[:3]) if titles else "the current source set"
        return f"Repair pass rebuilt missing coverage and traceability around {joined}."

    def _stable_key(self, *, topic_key: str | None, source_item_id: str, window_id: str) -> str:
        date_key = str(window_id or "").split("@", 1)[0] or "window"
        if topic_key:
            return f"topic-{self._slugify(topic_key)}-{date_key}"
        return f"item-{self._slugify(source_item_id)}-{date_key}"

    def _base_slug(self, *, topic_key: str | None, source_item_id: str, window_id: str) -> str:
        date_key = str(window_id or "").split("@", 1)[0] or "window"
        if topic_key:
            return f"{self._slugify(topic_key)}-{date_key}"
        return f"item-{self._slugify(source_item_id)}-{date_key}"

    def _navigation_payload_from_documents(
        self,
        *,
        documents: list[dict[str, Any]],
        window_id: str,
    ) -> dict[str, Any]:
        ordered = sorted(
            documents,
            key=lambda item: (
                1 if item.get("published_with_gap") else 0,
                int(item.get("source_item_count") or 0),
                str(item.get("updated_at") or ""),
            ),
            reverse=True,
        )
        return {
            "brief_kind": "sourceharbor_navigation_brief_v1",
            "generated_at": datetime.now(UTC).isoformat(),
            "window_id": window_id,
            "document_count": len(ordered),
            "published_with_gap_count": sum(
                1 for item in ordered if bool(item.get("published_with_gap"))
            ),
            "summary": (
                f"Read {len(ordered)} published reader documents for {window_id}. "
                f"{sum(1 for item in ordered if bool(item.get('published_with_gap')))} still carry a yellow warning."
            ),
            "items": [
                {
                    "document_id": item["id"],
                    "title": item["title"],
                    "summary": item.get("summary"),
                    "topic_key": item.get("topic_key"),
                    "topic_label": item.get("topic_label"),
                    "published_with_gap": bool(item.get("published_with_gap")),
                    "source_item_count": int(item.get("source_item_count") or 0),
                    "route": f"/reader/{item['id']}",
                }
                for item in ordered
            ],
        }

    @staticmethod
    def _digest_preview(markdown: str | None, *, fallback: str) -> str:
        if not isinstance(markdown, str) or not markdown.strip():
            return fallback
        cleaned_lines = [
            line.strip()
            for line in markdown.splitlines()
            if line.strip()
            and not line.lstrip().startswith("#")
            and not line.lstrip().startswith(">")
        ]
        if not cleaned_lines:
            cleaned_lines = [line.strip() for line in markdown.splitlines() if line.strip()]
        preview = " ".join(cleaned_lines[:2]).strip()
        if len(preview) > 240:
            return preview[:237].rstrip() + "..."
        return preview or fallback

    @staticmethod
    def _humanize_topic_key(topic_key: str | None) -> str:
        raw = str(topic_key or "").strip()
        if not raw:
            return ""
        return raw.replace("-", " ").replace("_", " ").strip().title()

    @staticmethod
    def _slugify(value: str) -> str:
        tokens = _TOKEN_PATTERN.findall(value.lower())
        return "-".join(tokens[:8]) or "item"

    @staticmethod
    def _isoformat(value: Any) -> str | None:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC).isoformat()
            return value.astimezone(UTC).isoformat()
        return None
