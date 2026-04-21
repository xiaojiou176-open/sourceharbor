from __future__ import annotations

import re
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from ..models import Subscription
from ..repositories import (
    ClusterVerdictManifestsRepository,
    ConsumptionBatchesRepository,
    PublishedReaderDocumentsRepository,
)
from .jobs import JobsService
from .source_identity import build_identity_payload
from .source_names import build_source_name_fallback, resolve_source_name

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
        if document is None or not self._is_publicly_published_document(document):
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
        baseline_versions = [
            str(value).strip()
            for value in (getattr(batch, "base_published_doc_versions", []) or [])
            if str(value).strip()
        ]
        cluster_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        singletons: list[dict[str, Any]] = []

        for item in items:
            cluster_key = str(item.get("cluster_key") or "").strip()
            if cluster_key.startswith("topic:"):
                cluster_groups[cluster_key].append(item)
            else:
                singletons.append(
                    self._build_singleton_payload(
                        item,
                        window_id=batch.window_id,
                        baseline_versions=baseline_versions,
                    )
                )

        clusters: list[dict[str, Any]] = []
        for cluster_key, members in sorted(cluster_groups.items()):
            if len(members) < 2:
                singletons.extend(
                    self._build_singleton_payload(
                        member,
                        window_id=batch.window_id,
                        baseline_versions=baseline_versions,
                    )
                    for member in members
                )
                continue
            clusters.append(
                self._build_cluster_payload(
                    cluster_key=cluster_key,
                    members=members,
                    window_id=batch.window_id,
                    baseline_versions=baseline_versions,
                )
            )

        clusters.sort(
            key=lambda item: (item["source_item_count"], item["topic_label"], item["cluster_key"]),
            reverse=True,
        )
        singletons.sort(key=lambda item: (item["published_at"] or "", item["title"]), reverse=True)

        cluster_count = len(clusters)
        singleton_count = len(singletons)
        source_item_count = len(items)
        affected_document_keys = sorted(
            {
                str(item.get("stable_key") or "").strip()
                for item in [*clusters, *singletons]
                if str(item.get("rebuild_scope") or "").strip() != "new_document"
                and str(item.get("stable_key") or "").strip()
            }
        )
        judge_gap_flags = sorted(
            {
                str(flag).strip()
                for item in [*clusters, *singletons]
                for flag in (item.get("judge_gap_flags") or [])
                if str(flag).strip()
            }
        )
        status = "ready" if not judge_gap_flags else "gap_detected"
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
            "base_published_doc_versions": baseline_versions,
            "affected_document_keys": affected_document_keys,
            "judge_gap_flags": judge_gap_flags,
            "judge_input_contract": {
                "inputs": [
                    "consumption_batch.items",
                    "job.digest_markdown",
                    "job.knowledge_cards",
                    "job.evidence_bundle",
                    "base_published_doc_versions",
                    "previous_published_document_summary",
                    "previous_coverage_ledger",
                    "previous_traceability_pack",
                ],
                "grouping_rule": "dominant_topic_key",
                "singleton_fallback": "no_dominant_topic",
                "rebuild_semantics": "affected_cluster_rebuild",
            },
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
        process_results = [
            {
                "document_id": item["id"],
                "stable_key": item["stable_key"],
                "publish_status": item["publish_status"],
                "published_with_gap": bool(item.get("published_with_gap")),
                "ok": True,
            }
            for item in document_payloads
        ]
        if hasattr(self.batch_repo, "mark_materialized"):
            self.batch_repo.mark_materialized(batch_id=batch.id, process_results=process_results)
        navigation_brief = self.build_navigation_brief(
            window_id=batch.window_id,
            limit=max(len(documents), 1),
        )
        return {
            "consumption_batch_id": str(batch.id),
            "cluster_verdict_manifest_id": str(manifest_instance.id),
            "window_id": batch.window_id,
            "document_count": len(documents),
            "published_document_count": sum(
                1
                for item in document_payloads
                if self._is_public_publish_status(item.get("publish_status"))
            ),
            "published_with_gap_count": sum(
                1 for item in document_payloads if bool(item.get("published_with_gap"))
            ),
            "documents": document_payloads,
            "navigation_brief": navigation_brief,
        }

    def list_published_documents(
        self, *, limit: int = 20, window_id: str | None = None
    ) -> list[dict[str, Any]]:
        # Public reader routes are capped to a small window, so fetch that full window
        # before filtering out gap-bearing versions.
        fetch_limit = max(int(limit or 0), 100)
        documents = self.document_repo.list_current(limit=fetch_limit, window_id=window_id)
        public_documents = [
            item for item in documents if self._is_publicly_published_document(item)
        ]
        return [self._to_document_payload(item) for item in public_documents[:limit]]

    def get_published_document(self, *, document_id: uuid.UUID) -> dict[str, Any] | None:
        document = self.document_repo.get(document_id=document_id)
        if document is None or not self._is_publicly_published_document(document):
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
        existing_sections = [
            item for item in (document.sections_json or []) if isinstance(item, dict)
        ]
        gap_report = self._build_gap_report(
            coverage_ledger=dict(document.coverage_ledger_json or {}),
            traceability_pack=dict(document.traceability_pack_json or {}),
            warning_json=dict(document.warning_json or {}),
        )
        normalized_section_ids = [
            str(value).strip() for value in (section_ids or []) if str(value).strip()
        ]

        if normalized_strategy == "patch":
            summary = str(document.summary or "").strip() or self._repair_summary(
                source_refs, gap_report=gap_report
            )
            sections = existing_sections or self._build_singleton_sections(source_refs)
            markdown = self._render_sections_as_markdown(
                title=str(document.title),
                summary=summary,
                sections=sections,
                warning_json={},
            )
            materialization_mode = "repair_patch"
        else:
            summary = self._repair_summary(source_refs, gap_report=gap_report)
            sections = self._build_repair_sections(
                source_refs,
                existing_sections=existing_sections,
                target_section_ids=normalized_section_ids,
                gap_report=gap_report,
            )
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
            section_ids=normalized_section_ids,
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
        sections = (
            self._build_cluster_sections(source_refs)
            if materialization_mode == "merge_then_polish"
            else self._build_singleton_sections(source_refs)
        )
        if materialization_mode.startswith("repair_"):
            sections = self._build_repair_sections(
                source_refs,
                existing_sections=None,
                target_section_ids=list(section_ids or []),
                gap_report=None,
            )
        coverage = self._build_coverage_ledger(
            source_refs=source_refs,
            sections=sections,
            repair_history=repair_history,
        )
        traceability = self._build_traceability_pack(
            source_refs=source_refs,
            sections=sections,
            repair_history=repair_history,
        )
        warning_json = self._build_warning_json(
            coverage_ledger=coverage,
            traceability_pack=traceability,
            repair_history=repair_history,
        )
        published_with_gap = bool(warning_json.get("published_with_gap"))
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
        coverage["stable_key"] = stable_key
        coverage["version"] = int(document.version or 0)
        traceability["published_doc_id"] = str(document.id)
        traceability["stable_key"] = stable_key
        traceability["version"] = int(document.version or 0)
        traceability["warning_summary"] = warning_json if published_with_gap else None
        warning_json["version"] = int(document.version or 0)
        warning_json["publish_status"] = self._derive_publish_status(
            is_current=True,
            published_with_gap=published_with_gap,
        )
        document.markdown = self._render_sections_as_markdown(
            title=title,
            summary=summary,
            sections=sections,
            warning_json=warning_json,
            body_markdown=markdown,
        )
        document.warning_json = warning_json
        document.coverage_ledger_json = coverage
        document.traceability_pack_json = traceability
        self.db.add(document)
        return document

    def _build_source_item_payload(self, item: Any) -> dict[str, Any]:
        job_id = getattr(item, "job_id", None)
        job_id_uuid = job_id if isinstance(job_id, uuid.UUID) else None
        digest_markdown: str | None = None
        knowledge_cards: list[dict[str, Any]] = []
        evidence_bundle: dict[str, Any] = {}
        if job_id_uuid is not None:
            digest_markdown = self.jobs_service.get_artifact_digest_md(
                job_id=job_id_uuid, video_url=None
            )
            knowledge_cards = self.jobs_service.get_knowledge_cards(job_id=job_id_uuid) or []
            if hasattr(self.jobs_service, "build_evidence_bundle"):
                evidence_bundle = self.jobs_service.build_evidence_bundle(job_id=job_id_uuid) or {}
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
        digest_meta = evidence_bundle.get("digest_meta")
        if not isinstance(digest_meta, dict):
            digest_meta = {}
        raw_stage_contract = dict(digest_meta.get("raw_stage_contract") or {})
        trace_summary = evidence_bundle.get("trace_summary")
        if not isinstance(trace_summary, dict):
            trace_summary = {}
        artifact_manifest = evidence_bundle.get("artifact_manifest")
        if not isinstance(artifact_manifest, dict):
            artifact_manifest = {}
        evidence_routes = self._build_source_evidence_routes(
            job_id=str(job_id_uuid) if job_id_uuid else None,
            source_url=str(getattr(item, "source_url", "") or "").strip() or None,
            artifact_manifest=artifact_manifest,
        )
        frame_routes = self._frame_asset_routes(
            job_id=str(job_id_uuid) if job_id_uuid else None,
            artifact_manifest=artifact_manifest,
        )
        pipeline_final_status = None
        job_payload = evidence_bundle.get("job")
        if isinstance(job_payload, dict):
            pipeline_final_status = (
                str(job_payload.get("pipeline_final_status") or "").strip() or None
            )
        degradation_flags = [
            str(item).strip()
            for item in (trace_summary.get("degradations") or [])
            if str(item).strip()
        ]
        source_origin = (
            str(getattr(item, "source_origin", "") or "").strip() or "subscription_tracked"
        )
        subscription_id = getattr(item, "subscription_id", None)
        subscription_row = (
            self.db.get(Subscription, subscription_id)
            if isinstance(subscription_id, uuid.UUID) and hasattr(self.db, "get")
            else None
        )
        resolved_platform = str(getattr(item, "platform", "") or "").strip() or "unknown"
        resolved_source_url = str(getattr(item, "source_url", "") or "").strip() or None
        source_name = title
        creator_handle: str | None = None
        metadata_uploader = str(digest_meta.get("uploader") or "").strip() or None
        metadata_thumbnail = str(digest_meta.get("thumbnail") or "").strip() or None
        identity_status = "derived_identity"
        relation_kind = "manual_one_off" if source_origin == "manual_injected" else source_origin
        affiliation_label: str | None = (
            "Reading today" if source_origin == "manual_injected" else None
        )
        if subscription_row is not None:
            source_name = resolve_source_name(
                source_type=str(getattr(subscription_row, "source_type", "") or ""),
                source_value=str(getattr(subscription_row, "source_value", "") or ""),
                fallback=build_source_name_fallback(
                    platform=str(getattr(subscription_row, "platform", "") or ""),
                    source_type=str(getattr(subscription_row, "source_type", "") or ""),
                    source_value=str(getattr(subscription_row, "source_value", "") or ""),
                    source_url=getattr(subscription_row, "source_url", None),
                    rsshub_route=getattr(subscription_row, "rsshub_route", None),
                ),
            )
            source_value = str(getattr(subscription_row, "source_value", "") or "").strip()
            creator_handle = source_value if source_value.startswith("@") else None
            identity_status = "matched_subscription_identity"
            relation_kind = "matched_subscription"
            affiliation_label = source_name
        identity = build_identity_payload(
            platform=str(
                getattr(subscription_row, "platform", resolved_platform) or resolved_platform
            ),
            display_name=source_name,
            creator_handle=creator_handle,
            source_homepage_url=getattr(subscription_row, "source_url", None)
            or getattr(subscription_row, "rsshub_route", None)
            or resolved_source_url,
            source_url=resolved_source_url,
            source_universe_label=source_name
            if subscription_row is not None
            else affiliation_label or title,
            identity_status=identity_status,
            thumbnail_url=metadata_thumbnail,
        )
        judge_gap_flags = []
        if not dominant_topic_key:
            judge_gap_flags.append("insufficient_topic_signal")
        if not digest_markdown:
            judge_gap_flags.append("missing_digest")
        if degradation_flags:
            judge_gap_flags.append("degraded_extraction")
        if job_id_uuid is not None and not evidence_bundle:
            judge_gap_flags.append("missing_evidence_bundle")
        if (
            str(getattr(item, "content_type", "") or "").strip().lower() == "video"
            and raw_stage_contract.get("video_contract_satisfied") is not True
        ):
            judge_gap_flags.append("video_contract_gap")
        return {
            "source_item_id": str(item.id),
            "ingest_run_item_id": str(getattr(item, "ingest_run_item_id", None) or "").strip()
            or None,
            "job_id": str(job_id_uuid) if job_id_uuid else None,
            "platform": resolved_platform,
            "source_origin": source_origin,
            "content_type": str(getattr(item, "content_type", "") or "").strip() or "video",
            "title": title,
            "source_url": resolved_source_url,
            "published_at": self._isoformat(getattr(item, "published_at", None)),
            "claim_kinds": sorted(claim_kinds),
            "topic_keys": sorted(topic_counter),
            "required_topics": sorted(topic_counter),
            "required_claim_kinds": sorted(claim_kinds),
            "dominant_topic_key": dominant_topic_key,
            "topic_label": dominant_topic_label,
            "digest_markdown": digest_markdown,
            "digest_preview": digest_preview,
            "knowledge_cards": knowledge_cards,
            "evidence_bundle": evidence_bundle,
            "artifact_manifest": artifact_manifest,
            "trace_summary": trace_summary,
            "evidence_routes": evidence_routes,
            "pipeline_final_status": pipeline_final_status,
            "degradation_flags": degradation_flags,
            "degraded_extraction": bool(degradation_flags),
            "raw_stage_contract": raw_stage_contract,
            "subscription_id": str(subscription_id)
            if isinstance(subscription_id, uuid.UUID)
            else None,
            "matched_subscription_name": source_name if subscription_row is not None else None,
            "relation_kind": relation_kind,
            "affiliation_label": affiliation_label,
            "canonical_source_name": source_name if subscription_row is not None else None,
            "canonical_author_name": metadata_uploader
            or (source_name if subscription_row is not None else None),
            "creator_display_name": metadata_uploader or identity.creator_display_name,
            "creator_handle": identity.creator_handle,
            "thumbnail_url": identity.thumbnail_url,
            "avatar_url": identity.avatar_url,
            "avatar_label": identity.avatar_label,
            "identity_status": identity.identity_status,
            "job_bundle_route": str(evidence_routes.get("job_bundle") or "").strip() or None,
            "frame_routes": frame_routes,
            "judge_gap_flags": sorted(set(judge_gap_flags)),
            "cluster_key": (
                f"topic:{dominant_topic_key}" if dominant_topic_key else f"singleton:{item.id}"
            ),
            "window_id": None,
        }

    def _build_cluster_payload(
        self,
        *,
        cluster_key: str,
        members: list[dict[str, Any]],
        window_id: str,
        baseline_versions: list[str],
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
        stable_key = self._stable_key(
            topic_key=topic_key,
            source_item_id=str(members[0]["source_item_id"]),
            window_id=window_id,
        )
        previous_document = self.document_repo.get_current_by_stable_key(stable_key=stable_key)
        rebuild_scope = (
            "affected_cluster_rebuild"
            if previous_document is not None or stable_key in baseline_versions
            else "new_document"
        )
        return {
            "cluster_id": f"cluster-{self._slugify(cluster_key)}",
            "cluster_key": cluster_key,
            "stable_key": stable_key,
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
            "judge_gap_flags": sorted(
                {
                    str(flag).strip()
                    for member in members
                    for flag in (member.get("judge_gap_flags") or [])
                    if str(flag).strip()
                }
            ),
            "judge_inputs": self._judge_input_list(
                previous_document=previous_document,
                baseline_versions=baseline_versions,
            ),
            "rebuild_scope": rebuild_scope,
            "previous_document": self._previous_document_summary(previous_document),
            "members": [self._to_member_payload(item) for item in members],
        }

    def _build_singleton_payload(
        self,
        item: dict[str, Any],
        *,
        window_id: str,
        baseline_versions: list[str],
    ) -> dict[str, Any]:
        stable_key = self._stable_key(
            topic_key=item.get("dominant_topic_key"),
            source_item_id=str(item["source_item_id"]),
            window_id=window_id,
        )
        previous_document = self.document_repo.get_current_by_stable_key(stable_key=stable_key)
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
            "stable_key": stable_key,
            "topic_key": item.get("dominant_topic_key"),
            "topic_label": item.get("topic_label"),
            "claim_kinds": list(item.get("claim_kinds") or []),
            "decision": "polish_only",
            "digest_preview": item.get("digest_preview"),
            "judge_gap_flags": list(item.get("judge_gap_flags") or []),
            "judge_inputs": self._judge_input_list(
                previous_document=previous_document,
                baseline_versions=baseline_versions,
            ),
            "rebuild_scope": (
                "affected_cluster_rebuild"
                if previous_document is not None or stable_key in baseline_versions
                else "new_document"
            ),
            "previous_document": self._previous_document_summary(previous_document),
        }

    @staticmethod
    def _normalize_relation_kind(relation_kind: Any, *, source_origin: Any) -> str | None:
        normalized_relation = str(relation_kind or "").strip()
        normalized_origin = str(source_origin or "").strip()
        if normalized_relation == "manual_injected":
            return "manual_one_off"
        if normalized_relation:
            return normalized_relation
        if normalized_origin == "manual_injected":
            return "manual_one_off"
        return normalized_origin or None

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
            "subscription_id": item.get("subscription_id"),
            "matched_subscription_name": item.get("matched_subscription_name"),
            "relation_kind": self._normalize_relation_kind(
                item.get("relation_kind"), source_origin=item.get("source_origin")
            ),
            "affiliation_label": item.get("affiliation_label"),
            "canonical_source_name": item.get("canonical_source_name"),
            "canonical_author_name": item.get("canonical_author_name"),
            "creator_display_name": item.get("creator_display_name"),
            "creator_handle": item.get("creator_handle"),
            "thumbnail_url": item.get("thumbnail_url"),
            "avatar_url": item.get("avatar_url"),
            "avatar_label": item.get("avatar_label"),
            "identity_status": item.get("identity_status"),
            "raw_stage_contract": dict(item.get("raw_stage_contract") or {}),
            "job_bundle_route": item.get("job_bundle_route"),
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
        publish_status = self._derive_publish_status(
            is_current=bool(instance.is_current),
            published_with_gap=bool(instance.published_with_gap),
        )
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
            "publish_status": publish_status,
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
            "source_refs": [
                {
                    **item,
                    "relation_kind": self._normalize_relation_kind(
                        item.get("relation_kind"), source_origin=item.get("source_origin")
                    ),
                }
                for item in (instance.source_refs_json or [])
                if isinstance(item, dict)
            ],
            "sections": [
                {
                    "section_id": str(item.get("section_id") or item.get("section_key") or ""),
                    "section_key": str(item.get("section_key") or item.get("section_id") or ""),
                    "title": str(item.get("title") or ""),
                    "kind": str(item.get("kind") or ""),
                    "markdown": str(item.get("markdown") or ""),
                    "source_item_ids": list(item.get("source_item_ids") or []),
                    "primary_source_item_ids": list(item.get("primary_source_item_ids") or []),
                    "topic_refs": list(item.get("topic_refs") or []),
                    "claim_refs": list(item.get("claim_refs") or []),
                    "evidence_anchor_refs": list(item.get("evidence_anchor_refs") or []),
                    "status": str(item.get("status") or ""),
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
        topic_items = self._all_topic_refs(source_refs)
        claim_items = self._all_claim_refs(source_refs)
        all_source_item_ids = [str(item["source_item_id"]) for item in source_refs]
        merged_markdown = "\n".join(
            [
                f"- Theme focus: {', '.join(topic_items[:4])}"
                if topic_items
                else "- Theme focus: mixed sources",
                f"- Cross-source signals: {', '.join(claim_items[:4])}"
                if claim_items
                else "- Cross-source signals: editorial synthesis",
                f"- Source count: {len(source_refs)}",
            ]
        )
        sections = [
            self._section_payload(
                section_key="merged-thesis",
                title="Merged Thesis",
                kind="merged_thesis",
                markdown=merged_markdown,
                source_item_ids=all_source_item_ids,
                primary_source_item_ids=all_source_item_ids[:1],
                topic_refs=topic_items,
                claim_refs=claim_items,
                evidence_anchor_refs=self._all_evidence_anchor_refs(source_refs),
            ),
            self._section_payload(
                section_key="cross-source-signals",
                title="Cross-Source Signals",
                kind="cross_source_signals",
                markdown="\n".join(
                    [
                        f"- {self._source_title(source_ref)}: {self._source_preview(source_ref)}"
                        for source_ref in source_refs
                    ]
                ),
                source_item_ids=all_source_item_ids,
                primary_source_item_ids=all_source_item_ids[:2],
                topic_refs=topic_items,
                claim_refs=claim_items,
                evidence_anchor_refs=self._all_evidence_anchor_refs(source_refs),
            ),
        ]
        for source_ref in source_refs:
            source_item_id = str(source_ref["source_item_id"])
            sections.append(
                self._section_payload(
                    section_key=f"source-contribution-{self._slugify(source_item_id)}",
                    title=f"Source Contribution · {self._source_title(source_ref)}",
                    kind="source_contribution",
                    markdown="\n".join(
                        [
                            f"- Platform: {self._source_platform(source_ref)}",
                            f"- Topics: {', '.join(self._source_topic_refs(source_ref)) or 'none captured'}",
                            f"- Claim kinds: {', '.join(self._source_claim_refs(source_ref)) or 'none captured'}",
                            f"- Preview: {self._source_preview(source_ref)}",
                            f"- Source: {source_ref.get('source_url')}"
                            if source_ref.get("source_url")
                            else "- Source: unavailable",
                        ]
                    ),
                    source_item_ids=[source_item_id],
                    primary_source_item_ids=[source_item_id],
                    topic_refs=self._source_topic_refs(source_ref),
                    claim_refs=self._source_claim_refs(source_ref),
                    evidence_anchor_refs=self._source_evidence_anchor_refs(source_ref),
                )
            )
        return sections

    def _build_singleton_sections(self, source_refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        source_ref = source_refs[0]
        source_item_id = str(source_ref["source_item_id"])
        preview = self._source_preview(source_ref)
        source_url = str(source_ref.get("source_url") or "").strip()
        return [
            self._section_payload(
                section_key="summary",
                title="Summary",
                kind="summary",
                markdown=preview,
                source_item_ids=[source_item_id],
                primary_source_item_ids=[source_item_id],
                topic_refs=self._source_topic_refs(source_ref),
                claim_refs=self._source_claim_refs(source_ref),
                evidence_anchor_refs=self._source_evidence_anchor_refs(source_ref),
            ),
            self._section_payload(
                section_key="source-context",
                title="Source Context",
                kind="source_context",
                markdown="\n".join(
                    [
                        f"- Platform: {self._source_platform(source_ref)}",
                        f"- Source origin: {str(source_ref.get('source_origin') or '').strip() or 'subscription_tracked'}",
                        f"- Topics: {', '.join(self._source_topic_refs(source_ref)) or 'none captured'}",
                        f"- Claim kinds: {', '.join(self._source_claim_refs(source_ref)) or 'none captured'}",
                        f"- Source: {source_url}" if source_url else "- Source: unavailable",
                    ]
                ),
                source_item_ids=[source_item_id],
                primary_source_item_ids=[source_item_id],
                topic_refs=self._source_topic_refs(source_ref),
                claim_refs=self._source_claim_refs(source_ref),
                evidence_anchor_refs=self._source_evidence_anchor_refs(source_ref),
            ),
        ]

    def _build_repair_sections(
        self,
        source_refs: list[dict[str, Any]],
        *,
        existing_sections: list[dict[str, Any]] | None,
        target_section_ids: list[str],
        gap_report: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        rebuilt_sections = (
            self._build_cluster_sections(source_refs)
            if len(source_refs) > 1
            else self._build_singleton_sections(source_refs)
        )
        if not existing_sections:
            sections = list(rebuilt_sections)
        elif target_section_ids:
            rebuilt_map = {
                str(section.get("section_id") or section.get("section_key") or "").strip(): section
                for section in rebuilt_sections
            }
            sections = []
            replaced = set()
            for section in existing_sections:
                section_id = str(
                    section.get("section_id") or section.get("section_key") or ""
                ).strip()
                if section_id in target_section_ids and section_id in rebuilt_map:
                    sections.append(rebuilt_map[section_id])
                    replaced.add(section_id)
                else:
                    sections.append(section)
            for section_id in target_section_ids:
                if section_id not in replaced and section_id in rebuilt_map:
                    sections.append(rebuilt_map[section_id])
        else:
            sections = list(rebuilt_sections)
        if gap_report:
            gap_section = self._gap_report_section(source_refs=source_refs, gap_report=gap_report)
            if gap_section is not None:
                sections = [
                    section
                    for section in sections
                    if str(section.get("section_id") or section.get("section_key") or "").strip()
                    != "gap-report"
                ]
                sections.append(gap_section)
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
        self,
        *,
        source_refs: list[dict[str, Any]],
        sections: list[dict[str, Any]],
        repair_history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        section_index = [
            {
                "section_id": str(
                    section.get("section_id") or section.get("section_key") or ""
                ).strip(),
                "title": str(section.get("title") or "").strip(),
                "source_item_ids": [
                    str(source_item_id).strip()
                    for source_item_id in (section.get("source_item_ids") or [])
                    if str(source_item_id).strip()
                ],
                "topic_refs": [
                    str(topic).strip()
                    for topic in (section.get("topic_refs") or [])
                    if str(topic).strip()
                ],
                "claim_refs": [
                    str(claim).strip()
                    for claim in (section.get("claim_refs") or [])
                    if str(claim).strip()
                ],
                "evidence_anchor_refs": [
                    str(route).strip()
                    for route in (section.get("evidence_anchor_refs") or [])
                    if str(route).strip()
                ],
            }
            for section in sections
            if isinstance(section, dict)
        ]
        entries = []
        gap_count = 0
        repair_budget = 2
        repair_attempts = len(repair_history)
        affected_source_item_ids: list[str] = []
        for source_ref in source_refs:
            source_item_id = str(source_ref.get("source_item_id") or "").strip()
            missing_digest = not str(source_ref.get("digest_markdown") or "").strip()
            required_topics = self._source_topic_refs(source_ref)
            required_claim_kinds = self._source_claim_refs(source_ref)
            coverage_sections = [
                section for section in section_index if source_item_id in section["source_item_ids"]
            ]
            covered_topics = sorted(
                {
                    topic
                    for section in coverage_sections
                    for topic in section.get("topic_refs") or []
                    if topic in required_topics
                }
            )
            covered_claim_kinds = sorted(
                {
                    claim
                    for section in coverage_sections
                    for claim in section.get("claim_refs") or []
                    if claim in required_claim_kinds
                }
            )
            missing_topics = sorted(set(required_topics) - set(covered_topics))
            missing_claim_kinds = sorted(set(required_claim_kinds) - set(covered_claim_kinds))
            missing_evidence_routes = [
                key
                for key in ("artifact_markdown", "job_bundle", "job_knowledge_cards")
                if not str((source_ref.get("evidence_routes") or {}).get(key) or "").strip()
            ]
            degraded_extraction = bool(source_ref.get("degraded_extraction"))
            gap_flags = []
            if missing_topics:
                gap_flags.append("missing_topics")
            if missing_claim_kinds:
                gap_flags.append("missing_claim_kinds")
            if missing_digest:
                gap_flags.append("missing_digest")
            if missing_evidence_routes:
                gap_flags.append("missing_evidence_routes")
            if degraded_extraction:
                gap_flags.append("degraded_extraction")
            raw_stage_contract = source_ref.get("raw_stage_contract")
            if not isinstance(raw_stage_contract, dict):
                raw_stage_contract = {}
            if (
                str(source_ref.get("content_type") or "").strip().lower() == "video"
                and raw_stage_contract.get("video_contract_satisfied") is not True
            ):
                gap_flags.append("video_contract_gap")
            entry_status = "pass"
            if gap_flags:
                entry_status = (
                    "repair_exhausted" if repair_attempts >= repair_budget else "gap_detected"
                )
                affected_source_item_ids.append(source_item_id)
            if entry_status != "pass":
                gap_count += 1
            entries.append(
                {
                    "source_item_id": source_item_id,
                    "coverage_ledger_id": str(uuid.uuid4()),
                    "required_topics": required_topics,
                    "covered_topics": covered_topics,
                    "missing_topics": missing_topics,
                    "required_claim_kinds": required_claim_kinds,
                    "covered_claim_kinds": covered_claim_kinds,
                    "missing_claim_kinds": missing_claim_kinds,
                    "sections": [
                        {
                            "section_id": section["section_id"],
                            "title": section["title"],
                        }
                        for section in coverage_sections
                    ],
                    "missing_digest": missing_digest,
                    "missing_evidence_routes": missing_evidence_routes,
                    "degraded_extraction": degraded_extraction,
                    "raw_stage_contract": raw_stage_contract,
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
        status = "pass"
        if any(entry.get("status") == "repair_exhausted" for entry in entries):
            status = "repair_exhausted"
        elif gap_count:
            status = "gap_detected"
        return {
            "ledger_kind": "sourceharbor_coverage_ledger_v1",
            "coverage_ledger_id": str(uuid.uuid4()),
            "published_doc_id": None,
            "generated_at": datetime.now(UTC).isoformat(),
            "status": status,
            "gap_count": gap_count,
            "gap_reasons": gap_reasons,
            "affected_source_item_ids": sorted(set(affected_source_item_ids)),
            "repair_budget": repair_budget,
            "repair_attempts": repair_attempts,
            "entries": entries,
        }

    def _build_traceability_pack(
        self,
        *,
        source_refs: list[dict[str, Any]],
        sections: list[dict[str, Any]],
        repair_history: list[dict[str, Any]],
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
            evidence_anchor_refs = sorted(
                {
                    str(route).strip()
                    for route in (
                        list(section.get("evidence_anchor_refs") or [])
                        + [
                            route
                            for source_ref in contributing_refs
                            for route in self._source_evidence_anchor_refs(source_ref)
                        ]
                    )
                    if str(route).strip()
                }
            )
            section_status = "ready" if source_item_ids and evidence_anchor_refs else "gap_detected"
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
                        set(section.get("claim_refs") or [])
                        | {
                            str(claim_kind).strip()
                            for item in contributing_refs
                            for claim_kind in (item.get("claim_kinds") or [])
                            if str(claim_kind).strip()
                        }
                    ),
                    "topic_refs": sorted(
                        set(section.get("topic_refs") or [])
                        | {
                            topic
                            for item in contributing_refs
                            for topic in self._source_topic_refs(item)
                        }
                    ),
                    "evidence_anchor_refs": evidence_anchor_refs,
                    "job_ids": job_ids,
                    "status": section_status,
                }
            )
        source_item_map = []
        evidence_routes: dict[str, list[str]] = {
            "artifact_markdown": [],
            "job_bundle": [],
            "job_knowledge_cards": [],
            "artifact_meta": [],
            "artifact_transcript": [],
            "artifact_comments": [],
            "artifact_outline": [],
            "source_url": [],
        }
        affected_source_item_ids: list[str] = []
        for source_ref in source_refs:
            job_id = str(source_ref.get("job_id") or "").strip()
            routes = dict(source_ref.get("evidence_routes") or {})
            available_routes = {key: value for key, value in routes.items() if value}
            artifact_manifest = source_ref.get("artifact_manifest")
            if not isinstance(artifact_manifest, dict):
                artifact_manifest = {}
            raw_stage_contract = source_ref.get("raw_stage_contract")
            if not isinstance(raw_stage_contract, dict):
                raw_stage_contract = {}
            evidence_status = "ready"
            if (
                not available_routes
                or not dict(source_ref.get("evidence_bundle") or {})
                or bool(source_ref.get("degraded_extraction"))
                or (
                    str(source_ref.get("content_type") or "").strip().lower() == "video"
                    and raw_stage_contract.get("video_contract_satisfied") is not True
                )
            ):
                evidence_status = "gap_detected"
                affected_source_item_ids.append(str(source_ref.get("source_item_id") or "").strip())
            source_item_map.append(
                {
                    "source_item_id": str(source_ref.get("source_item_id") or "").strip(),
                    "job_id": job_id or None,
                    "title": str(source_ref.get("title") or "").strip() or "Untitled source",
                    "platform": str(source_ref.get("platform") or "").strip() or "unknown",
                    "source_url": str(source_ref.get("source_url") or "").strip() or None,
                    "published_at": source_ref.get("published_at"),
                    "raw_artifacts": {
                        "digest": str(routes.get("artifact_markdown") or "").strip() or None,
                        "meta": str(routes.get("artifact_meta") or "").strip() or None,
                        "transcript": str(routes.get("artifact_transcript") or "").strip() or None,
                        "comments": str(routes.get("artifact_comments") or "").strip() or None,
                        "outline": str(routes.get("artifact_outline") or "").strip() or None,
                        "knowledge_cards": str(routes.get("job_knowledge_cards") or "").strip()
                        or None,
                        "frames": list(source_ref.get("frame_routes") or []),
                    },
                    "routes": routes,
                    "artifact_manifest": artifact_manifest,
                    "degradation_flags": list(source_ref.get("degradation_flags") or []),
                    "raw_stage_contract": raw_stage_contract,
                    "subscription_id": source_ref.get("subscription_id"),
                    "matched_subscription_name": source_ref.get("matched_subscription_name"),
                    "relation_kind": source_ref.get("relation_kind"),
                    "affiliation_label": source_ref.get("affiliation_label"),
                    "canonical_source_name": source_ref.get("canonical_source_name"),
                    "canonical_author_name": source_ref.get("canonical_author_name"),
                    "creator_display_name": source_ref.get("creator_display_name"),
                    "creator_handle": source_ref.get("creator_handle"),
                    "thumbnail_url": source_ref.get("thumbnail_url"),
                    "avatar_url": source_ref.get("avatar_url"),
                    "avatar_label": source_ref.get("avatar_label"),
                    "identity_status": source_ref.get("identity_status"),
                    "pipeline_final_status": source_ref.get("pipeline_final_status"),
                    "status": evidence_status,
                }
            )
            for key, value in available_routes.items():
                if value:
                    evidence_routes[key].append(value)
        has_gap = any(item.get("status") != "ready" for item in section_contributions) or any(
            item.get("status") != "ready" for item in source_item_map
        )
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
            "affected_source_item_ids": sorted(set(affected_source_item_ids)),
            "repair_attempts": len(repair_history),
            "warning_summary": None,
        }

    def _build_warning_json(
        self,
        *,
        coverage_ledger: dict[str, Any],
        traceability_pack: dict[str, Any],
        repair_history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        coverage_status = str(coverage_ledger.get("status") or "").strip()
        traceability_status = str(traceability_pack.get("status") or "").strip()
        warning_kinds: list[str] = []
        if coverage_status != "pass":
            warning_kinds.append("coverage_gap")
        if traceability_status != "ready":
            warning_kinds.append("traceability_gap")
        if any(
            bool(entry.get("degraded_extraction"))
            for entry in (coverage_ledger.get("entries") or [])
            if isinstance(entry, dict)
        ):
            warning_kinds.append("degraded_extraction")
        if coverage_status == "repair_exhausted" or len(repair_history) >= 2:
            warning_kinds.append("repair_budget_exhausted")
        if coverage_status == "pass" and traceability_status == "ready":
            return {
                "warning_kind": "none",
                "warning_kinds": [],
                "published_with_gap": False,
                "reasons": [],
                "failed_source_count": 0,
                "degraded_source_count": 0,
                "missing_digest_count": 0,
                "affected_scope": {
                    "source_item_ids": [],
                    "section_ids": [],
                    "source_item_count": 0,
                    "section_count": 0,
                },
                "version": None,
                "generated_at": datetime.now(UTC).isoformat(),
            }
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
            if "missing_claim_kinds" in set(coverage_ledger.get("gap_reasons") or []):
                reasons.append("coverage ledger reported uncovered source claim kinds")
            if "video_contract_gap" in set(coverage_ledger.get("gap_reasons") or []):
                reasons.append(
                    "video raw-stage contract failed to satisfy video-first requirements"
                )
        if traceability_status != "ready":
            reasons.append("traceability pack reported incomplete section contributions")
        if "degraded_extraction" in warning_kinds:
            reasons.append("source extraction degraded and still needs a cleaner evidence chain")
        if "repair_budget_exhausted" in warning_kinds:
            reasons.append("repair budget has been exhausted for the current stable key")
        affected_section_ids = [
            str(item.get("section_id") or "").strip()
            for item in (traceability_pack.get("section_contributions") or [])
            if isinstance(item, dict) and item.get("status") != "ready"
        ]
        affected_source_item_ids = sorted(
            {
                *[
                    str(item).strip()
                    for item in (coverage_ledger.get("affected_source_item_ids") or [])
                    if str(item).strip()
                ],
                *[
                    str(item).strip()
                    for item in (traceability_pack.get("affected_source_item_ids") or [])
                    if str(item).strip()
                ],
            }
        )
        return {
            "warning_kind": warning_kinds[0],
            "warning_kinds": warning_kinds,
            "kind": warning_kinds[0],
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
            "summary": "This reader document is readable, but it is still published with gap until coverage and traceability both pass.",
            "readable_why": "正文仍然可读，已有可用的合并/单源内容与现有证据入口。",
            "not_fully_sealed_why": "Coverage, traceability, or repair-budget contract is still incomplete for at least one source.",
            "affected_source_item_ids": affected_source_item_ids,
            "affected_scope": {
                "source_item_ids": affected_source_item_ids,
                "section_ids": affected_section_ids,
                "source_item_count": len(affected_source_item_ids),
                "section_count": len(affected_section_ids),
            },
            "version": None,
            "status": "published_with_gap",
        }

    def _repair_summary(
        self, source_refs: list[dict[str, Any]], *, gap_report: dict[str, Any] | None = None
    ) -> str:
        titles = [
            str(source_ref.get("title") or "").strip()
            for source_ref in source_refs
            if str(source_ref.get("title") or "").strip()
        ]
        joined = ", ".join(titles[:3]) if titles else "the current source set"
        if not gap_report:
            return f"Repair pass rebuilt missing coverage and traceability around {joined}."
        missing_topics = ", ".join(gap_report.get("missing_topics") or [])
        missing_claims = ", ".join(gap_report.get("missing_claim_kinds") or [])
        focus = missing_topics or missing_claims or "the current gap report"
        return f"Repair pass targeted {focus} around {joined}."

    @staticmethod
    def _derive_publish_status(*, is_current: bool, published_with_gap: bool) -> str:
        if not is_current:
            return "superseded"
        return "published_with_gap" if published_with_gap else "published"

    @classmethod
    def _is_public_publish_status(cls, publish_status: Any) -> bool:
        return str(publish_status or "").strip() == "published"

    @classmethod
    def _is_publicly_published_document(cls, instance: Any) -> bool:
        return cls._is_public_publish_status(
            cls._derive_publish_status(
                is_current=bool(getattr(instance, "is_current", False)),
                published_with_gap=bool(getattr(instance, "published_with_gap", False)),
            )
        )

    def _judge_input_list(
        self,
        *,
        previous_document: Any | None,
        baseline_versions: list[str],
    ) -> list[str]:
        inputs = [
            "consumption_batch.items",
            "job.digest_markdown",
            "job.knowledge_cards",
            "job.evidence_bundle",
        ]
        if previous_document is not None:
            inputs.extend(
                [
                    "previous_published_document_summary",
                    "previous_coverage_ledger",
                    "previous_traceability_pack",
                ]
            )
        if baseline_versions:
            inputs.append("base_published_doc_versions")
        return inputs

    def _previous_document_summary(self, document: Any | None) -> dict[str, Any] | None:
        if document is None:
            return None
        return {
            "document_id": str(document.id),
            "version": int(getattr(document, "version", 0) or 0),
            "published_with_gap": bool(getattr(document, "published_with_gap", False)),
            "summary": str(getattr(document, "summary", "") or "").strip() or None,
            "coverage_status": str(
                (getattr(document, "coverage_ledger_json", {}) or {}).get("status") or ""
            ).strip()
            or None,
            "traceability_status": str(
                (getattr(document, "traceability_pack_json", {}) or {}).get("status") or ""
            ).strip()
            or None,
        }

    @staticmethod
    def _build_source_evidence_routes(
        *, job_id: str | None, source_url: str | None, artifact_manifest: dict[str, Any]
    ) -> dict[str, str | None]:
        return {
            "artifact_markdown": f"/api/v1/artifacts/markdown?job_id={job_id}&include_meta=true"
            if job_id
            else None,
            "job_bundle": f"/api/v1/jobs/{job_id}/bundle" if job_id else None,
            "job_knowledge_cards": f"/knowledge?job_id={job_id}" if job_id else None,
            "artifact_meta": (
                ReaderPipelineService._artifact_asset_route(job_id, "meta")
                if ReaderPipelineService._artifact_manifest_has(artifact_manifest, "meta")
                else None
            ),
            "artifact_transcript": (
                ReaderPipelineService._artifact_asset_route(job_id, "transcript")
                if ReaderPipelineService._artifact_manifest_has(artifact_manifest, "transcript")
                else None
            ),
            "artifact_comments": (
                ReaderPipelineService._artifact_asset_route(job_id, "comments")
                if ReaderPipelineService._artifact_manifest_has(artifact_manifest, "comment")
                else None
            ),
            "artifact_outline": (
                ReaderPipelineService._artifact_asset_route(job_id, "outline")
                if ReaderPipelineService._artifact_manifest_has(artifact_manifest, "outline")
                else None
            ),
            "source_url": source_url or None,
        }

    @staticmethod
    def _artifact_manifest_has(artifact_manifest: dict[str, Any], keyword: str) -> bool:
        return keyword.lower() in str(artifact_manifest).lower()

    @staticmethod
    def _artifact_asset_route(job_id: str | None, alias: str) -> str | None:
        if not job_id:
            return None
        return f"/api/v1/artifacts/assets?job_id={job_id}&path={alias}"

    @staticmethod
    def _frame_asset_routes(job_id: str | None, artifact_manifest: dict[str, Any]) -> list[str]:
        if not job_id or not isinstance(artifact_manifest, dict):
            return []
        frame_keys = sorted(
            key for key in artifact_manifest if isinstance(key, str) and key.startswith("frame_")
        )
        return [f"/api/v1/artifacts/assets?job_id={job_id}&path={key}" for key in frame_keys]

    @staticmethod
    def _source_title(source_ref: dict[str, Any]) -> str:
        return str(source_ref.get("title") or "").strip() or "Untitled source"

    @staticmethod
    def _source_platform(source_ref: dict[str, Any]) -> str:
        return str(source_ref.get("platform") or "").strip() or "unknown"

    @staticmethod
    def _source_preview(source_ref: dict[str, Any]) -> str:
        return str(source_ref.get("digest_preview") or "").strip() or "No preview available."

    @staticmethod
    def _source_topic_refs(source_ref: dict[str, Any]) -> list[str]:
        return sorted(
            {
                str(card.get("topic_key") or "").strip()
                for card in (source_ref.get("knowledge_cards") or [])
                if isinstance(card, dict) and str(card.get("topic_key") or "").strip()
            }
        )

    @staticmethod
    def _source_claim_refs(source_ref: dict[str, Any]) -> list[str]:
        return sorted(
            {
                str(claim).strip()
                for claim in (source_ref.get("claim_kinds") or [])
                if str(claim).strip()
            }
        )

    def _source_evidence_anchor_refs(self, source_ref: dict[str, Any]) -> list[str]:
        return sorted(
            {
                str(route).strip()
                for route in (source_ref.get("evidence_routes") or {}).values()
                if str(route).strip()
            }
        )

    def _all_topic_refs(self, source_refs: list[dict[str, Any]]) -> list[str]:
        return sorted(
            {topic for source_ref in source_refs for topic in self._source_topic_refs(source_ref)}
        )

    def _all_claim_refs(self, source_refs: list[dict[str, Any]]) -> list[str]:
        return sorted(
            {claim for source_ref in source_refs for claim in self._source_claim_refs(source_ref)}
        )

    def _all_evidence_anchor_refs(self, source_refs: list[dict[str, Any]]) -> list[str]:
        return sorted(
            {
                route
                for source_ref in source_refs
                for route in self._source_evidence_anchor_refs(source_ref)
            }
        )

    @staticmethod
    def _section_payload(
        *,
        section_key: str,
        title: str,
        kind: str,
        markdown: str,
        source_item_ids: list[str],
        primary_source_item_ids: list[str],
        topic_refs: list[str],
        claim_refs: list[str],
        evidence_anchor_refs: list[str],
    ) -> dict[str, Any]:
        status = "ready" if source_item_ids and evidence_anchor_refs else "gap_detected"
        return {
            "section_key": section_key,
            "section_id": section_key,
            "title": title,
            "kind": kind,
            "markdown": markdown,
            "source_item_ids": source_item_ids,
            "primary_source_item_ids": primary_source_item_ids,
            "topic_refs": topic_refs,
            "claim_refs": claim_refs,
            "evidence_anchor_refs": evidence_anchor_refs,
            "status": status,
        }

    def _build_gap_report(
        self,
        *,
        coverage_ledger: dict[str, Any],
        traceability_pack: dict[str, Any],
        warning_json: dict[str, Any],
    ) -> dict[str, Any]:
        missing_topics = sorted(
            {
                str(topic).strip()
                for entry in (coverage_ledger.get("entries") or [])
                if isinstance(entry, dict)
                for topic in (entry.get("missing_topics") or [])
                if str(topic).strip()
            }
        )
        missing_claim_kinds = sorted(
            {
                str(claim).strip()
                for entry in (coverage_ledger.get("entries") or [])
                if isinstance(entry, dict)
                for claim in (entry.get("missing_claim_kinds") or [])
                if str(claim).strip()
            }
        )
        warning_kinds = [
            str(value).strip()
            for value in (warning_json.get("warning_kinds") or [])
            if str(value).strip()
        ]
        if not warning_kinds:
            warning_kind = str(warning_json.get("warning_kind") or "").strip()
            if warning_kind and warning_kind != "none":
                warning_kinds = [warning_kind]
        return {
            "missing_topics": missing_topics,
            "missing_claim_kinds": missing_claim_kinds,
            "warning_kinds": warning_kinds,
            "affected_source_item_ids": [
                str(value).strip()
                for value in (warning_json.get("affected_source_item_ids") or [])
                if str(value).strip()
            ],
            "affected_section_ids": [
                str(item.get("section_id") or "").strip()
                for item in (traceability_pack.get("section_contributions") or [])
                if isinstance(item, dict) and item.get("status") != "ready"
            ],
        }

    def _gap_report_section(
        self, *, source_refs: list[dict[str, Any]], gap_report: dict[str, Any]
    ) -> dict[str, Any] | None:
        warning_kinds = list(gap_report.get("warning_kinds") or [])
        missing_topics = list(gap_report.get("missing_topics") or [])
        missing_claim_kinds = list(gap_report.get("missing_claim_kinds") or [])
        if not warning_kinds and not missing_topics and not missing_claim_kinds:
            return None
        lines = []
        if warning_kinds:
            lines.append(f"- Warning kinds: {', '.join(warning_kinds)}")
        if missing_topics:
            lines.append(f"- Missing topics: {', '.join(missing_topics)}")
        if missing_claim_kinds:
            lines.append(f"- Missing claim kinds: {', '.join(missing_claim_kinds)}")
        source_item_ids = [str(item["source_item_id"]) for item in source_refs]
        return self._section_payload(
            section_key="gap-report",
            title="Gap Report",
            kind="gap_report",
            markdown="\n".join(lines),
            source_item_ids=source_item_ids,
            primary_source_item_ids=source_item_ids[:1],
            topic_refs=missing_topics,
            claim_refs=missing_claim_kinds,
            evidence_anchor_refs=self._all_evidence_anchor_refs(source_refs),
        )

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
