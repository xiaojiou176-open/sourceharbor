from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..security import require_write_access, sanitize_exception_detail
from ..services.reader_pipeline import ReaderPipelineService

router = APIRouter(prefix="/api/v1/reader", tags=["reader"])


class ClusterManifestMemberResponse(BaseModel):
    source_item_id: str
    job_id: str | None = None
    platform: str
    source_origin: str
    title: str
    source_url: str | None = None
    published_at: str | None = None
    claim_kinds: list[str] = Field(default_factory=list)
    digest_preview: str


class ClusterVerdictResponse(BaseModel):
    cluster_id: str
    cluster_key: str
    topic_key: str | None = None
    topic_label: str
    decision: str
    source_item_count: int
    source_item_ids: list[str] = Field(default_factory=list)
    job_ids: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    claim_kinds: list[str] = Field(default_factory=list)
    headline: str
    digest_preview: str
    members: list[ClusterManifestMemberResponse] = Field(default_factory=list)


class SingletonVerdictResponse(BaseModel):
    singleton_id: str
    source_item_id: str
    ingest_run_item_id: str | None = None
    job_id: str | None = None
    platform: str
    source_origin: str
    content_type: str
    title: str
    source_url: str | None = None
    published_at: str | None = None
    topic_key: str | None = None
    topic_label: str | None = None
    claim_kinds: list[str] = Field(default_factory=list)
    decision: str
    digest_preview: str


class ClusterVerdictManifestPayloadResponse(BaseModel):
    manifest_kind: str
    generated_at: str
    consumption_batch_id: str
    window_id: str
    status: str
    source_item_count: int
    cluster_count: int
    singleton_count: int
    clusters: list[ClusterVerdictResponse] = Field(default_factory=list)
    singletons: list[SingletonVerdictResponse] = Field(default_factory=list)


class ClusterVerdictManifestResponse(BaseModel):
    id: str
    consumption_batch_id: str
    window_id: str
    status: str
    source_item_count: int
    cluster_count: int
    singleton_count: int
    summary_markdown: str | None = None
    manifest: ClusterVerdictManifestPayloadResponse
    created_at: datetime
    updated_at: datetime


class MaterializeBatchRequest(BaseModel):
    reader_output_locale: str = "zh-CN"
    reader_style_profile: str = "briefing"


class RepairDocumentRequest(BaseModel):
    repair_mode: str = "patch"
    section_ids: list[str] = Field(default_factory=list)


class PublishedReaderDocumentResponse(BaseModel):
    id: str
    stable_key: str
    slug: str
    window_id: str
    topic_key: str | None = None
    topic_label: str | None = None
    title: str
    summary: str | None = None
    markdown: str
    reader_output_locale: str
    reader_style_profile: str
    materialization_mode: str
    version: int
    published_with_gap: bool
    is_current: bool
    source_item_count: int
    consumption_batch_id: str | None = None
    cluster_verdict_manifest_id: str | None = None
    supersedes_document_id: str | None = None
    warning: dict[str, Any] = Field(default_factory=dict)
    coverage_ledger: dict[str, Any] = Field(default_factory=dict)
    traceability_pack: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    sections: list[dict[str, Any]] = Field(default_factory=list)
    repair_history: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class PublishedReaderDocumentListResponse(BaseModel):
    items: list[PublishedReaderDocumentResponse] = Field(default_factory=list)


class MaterializeBatchResponse(BaseModel):
    consumption_batch_id: str
    cluster_verdict_manifest_id: str
    window_id: str
    published_document_count: int
    published_with_gap_count: int
    documents: list[PublishedReaderDocumentResponse] = Field(default_factory=list)
    navigation_brief: dict[str, Any] = Field(default_factory=dict)


def _coerce_manifest_payload(payload: dict[str, Any]) -> ClusterVerdictManifestResponse:
    return ClusterVerdictManifestResponse(
        id=str(payload["id"]),
        consumption_batch_id=str(payload["consumption_batch_id"]),
        window_id=str(payload["window_id"]),
        status=str(payload["status"]),
        source_item_count=int(payload.get("source_item_count") or 0),
        cluster_count=int(payload.get("cluster_count") or 0),
        singleton_count=int(payload.get("singleton_count") or 0),
        summary_markdown=payload.get("summary_markdown"),
        manifest=ClusterVerdictManifestPayloadResponse.model_validate(payload["manifest"]),
        created_at=payload["created_at"],
        updated_at=payload["updated_at"],
    )


def _coerce_document_payload(payload: dict[str, Any]) -> PublishedReaderDocumentResponse:
    return PublishedReaderDocumentResponse(
        id=str(payload["id"]),
        stable_key=str(payload["stable_key"]),
        slug=str(payload["slug"]),
        window_id=str(payload["window_id"]),
        topic_key=payload.get("topic_key"),
        topic_label=payload.get("topic_label"),
        title=str(payload["title"]),
        summary=payload.get("summary"),
        markdown=str(payload["markdown"]),
        reader_output_locale=str(payload.get("reader_output_locale") or "zh-CN"),
        reader_style_profile=str(payload.get("reader_style_profile") or "briefing"),
        materialization_mode=str(payload["materialization_mode"]),
        version=int(payload.get("version") or 1),
        published_with_gap=bool(payload.get("published_with_gap")),
        is_current=bool(payload.get("is_current")),
        source_item_count=int(payload.get("source_item_count") or 0),
        consumption_batch_id=payload.get("consumption_batch_id"),
        cluster_verdict_manifest_id=payload.get("cluster_verdict_manifest_id"),
        supersedes_document_id=payload.get("supersedes_document_id"),
        warning=dict(payload.get("warning") or {}),
        coverage_ledger=dict(payload.get("coverage_ledger") or {}),
        traceability_pack=dict(payload.get("traceability_pack") or {}),
        source_refs=list(payload.get("source_refs") or []),
        sections=list(payload.get("sections") or []),
        repair_history=list(payload.get("repair_history") or []),
        created_at=payload["created_at"],
        updated_at=payload["updated_at"],
    )


@router.post(
    "/batches/{batch_id}/judge",
    response_model=ClusterVerdictManifestResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_write_access)],
)
def judge_consumption_batch(batch_id: uuid.UUID, db: Session = Depends(get_db)):
    service = ReaderPipelineService(db)
    try:
        payload = service.judge_batch(batch_id=batch_id)
    except ValueError as exc:
        detail = sanitize_exception_detail(exc)
        code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return _coerce_manifest_payload(payload)


@router.get(
    "/batches/{batch_id}/manifest",
    response_model=ClusterVerdictManifestResponse,
)
def get_cluster_verdict_manifest(batch_id: uuid.UUID, db: Session = Depends(get_db)):
    service = ReaderPipelineService(db)
    instance = service.get_manifest(batch_id=batch_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="cluster verdict manifest not found")
    payload = {
        "id": str(instance.id),
        "consumption_batch_id": str(instance.consumption_batch_id),
        "window_id": instance.window_id,
        "status": instance.status,
        "source_item_count": instance.source_item_count,
        "cluster_count": instance.cluster_count,
        "singleton_count": instance.singleton_count,
        "summary_markdown": instance.summary_markdown,
        "manifest": instance.manifest_json if isinstance(instance.manifest_json, dict) else {},
        "created_at": instance.created_at,
        "updated_at": instance.updated_at,
    }
    return _coerce_manifest_payload(payload)


@router.post(
    "/batches/{batch_id}/materialize",
    response_model=MaterializeBatchResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_write_access)],
)
def materialize_consumption_batch(
    batch_id: uuid.UUID,
    payload: MaterializeBatchRequest | None = None,
    db: Session = Depends(get_db),
):
    service = ReaderPipelineService(db)
    body = payload or MaterializeBatchRequest()
    try:
        result = service.materialize_batch(
            batch_id=batch_id,
            reader_output_locale=body.reader_output_locale,
            reader_style_profile=body.reader_style_profile,
        )
    except ValueError as exc:
        detail = sanitize_exception_detail(exc)
        code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return MaterializeBatchResponse(
        consumption_batch_id=result["consumption_batch_id"],
        cluster_verdict_manifest_id=result["cluster_verdict_manifest_id"],
        window_id=result["window_id"],
        published_document_count=int(result.get("published_document_count") or 0),
        published_with_gap_count=int(result.get("published_with_gap_count") or 0),
        documents=[
            _coerce_document_payload(item)
            for item in result.get("documents") or []
            if isinstance(item, dict)
        ],
        navigation_brief=dict(result.get("navigation_brief") or {}),
    )


@router.get("/documents", response_model=list[PublishedReaderDocumentResponse])
def list_published_reader_documents(
    limit: int = Query(default=20, ge=1, le=100),
    window_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    service = ReaderPipelineService(db)
    return [
        _coerce_document_payload(item)
        for item in service.list_published_documents(limit=limit, window_id=window_id)
    ]


@router.get("/documents/slug/{slug}", response_model=PublishedReaderDocumentResponse)
def get_published_reader_document_by_slug(slug: str, db: Session = Depends(get_db)):
    service = ReaderPipelineService(db)
    payload = service.get_published_document_by_slug(slug=slug)
    if payload is None:
        raise HTTPException(status_code=404, detail="published reader document not found")
    return _coerce_document_payload(payload)


@router.get("/documents/{document_id}", response_model=PublishedReaderDocumentResponse)
def get_published_reader_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    service = ReaderPipelineService(db)
    payload = service.get_published_document(document_id=document_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="published reader document not found")
    return _coerce_document_payload(payload)


@router.post(
    "/documents/{document_id}/repair",
    response_model=PublishedReaderDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_write_access)],
)
def repair_published_reader_document(
    document_id: uuid.UUID,
    payload: RepairDocumentRequest,
    db: Session = Depends(get_db),
):
    service = ReaderPipelineService(db)
    try:
        result = service.repair_document(
            document_id=document_id,
            repair_mode=payload.repair_mode,
            section_ids=payload.section_ids,
        )
    except ValueError as exc:
        detail = sanitize_exception_detail(exc)
        code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return _coerce_document_payload(result)


@router.get("/navigation-brief")
def get_navigation_brief(
    window_id: str | None = Query(default=None),
    limit: int = Query(default=8, ge=1, le=20),
    db: Session = Depends(get_db),
):
    service = ReaderPipelineService(db)
    return dict(service.build_navigation_brief(window_id=window_id, limit=limit))
