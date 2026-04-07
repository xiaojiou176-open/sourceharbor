from __future__ import annotations

import uuid
from datetime import date as date_type
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..security import require_write_access, sanitize_exception_detail
from ..services.notifications import (
    get_notification_config,
    send_category_digest,
    send_daily_report_notification,
    send_test_email,
    update_notification_config,
)

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])
reports_router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


class NotificationConfigResponse(BaseModel):
    enabled: bool
    to_email: str | None
    daily_digest_enabled: bool
    daily_digest_hour_utc: int | None
    failure_alert_enabled: bool
    category_rules: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class NotificationConfigUpdateRequest(BaseModel):
    enabled: bool = True
    to_email: str | None = None
    daily_digest_enabled: bool = False
    daily_digest_hour_utc: int | None = Field(default=None, ge=0, le=23)
    failure_alert_enabled: bool = True
    category_rules: dict[str, object] | None = None


class NotificationTestRequest(BaseModel):
    to_email: str | None = None
    subject: str | None = None
    body: str | None = None


class NotificationSendResponse(BaseModel):
    delivery_id: uuid.UUID
    status: str
    provider_message_id: str | None
    error_message: str | None
    recipient_email: str
    subject: str
    sent_at: datetime | None
    created_at: datetime


class DailyReportSendRequest(BaseModel):
    date: date_type | None = None
    to_email: str | None = None
    subject: str | None = None
    body: str | None = None


class DailyReportSendResponse(BaseModel):
    sent: bool
    status: str
    delivery_id: uuid.UUID
    date: date_type
    recipient_email: str
    subject: str
    error_message: str | None
    sent_at: datetime | None
    created_at: datetime


class CategoryDigestSendRequest(BaseModel):
    category: str = Field(min_length=1)
    body: str = Field(min_length=1)
    to_email: str | None = None
    subject: str | None = None
    priority: int | None = Field(default=None, ge=0, le=100)
    dispatch_key: str | None = None


@router.get("/config", response_model=NotificationConfigResponse)
def get_config(db: Session = Depends(get_db)):
    row = get_notification_config(db)
    return NotificationConfigResponse(
        enabled=row.enabled,
        to_email=row.to_email,
        daily_digest_enabled=row.daily_digest_enabled,
        daily_digest_hour_utc=row.daily_digest_hour_utc,
        failure_alert_enabled=row.failure_alert_enabled,
        category_rules=row.category_rules if isinstance(row.category_rules, dict) else {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.put(
    "/config",
    response_model=NotificationConfigResponse,
    dependencies=[Depends(require_write_access)],
)
def put_config(payload: NotificationConfigUpdateRequest, db: Session = Depends(get_db)):
    row = update_notification_config(
        db,
        enabled=payload.enabled,
        to_email=payload.to_email,
        daily_digest_enabled=payload.daily_digest_enabled,
        daily_digest_hour_utc=payload.daily_digest_hour_utc,
        failure_alert_enabled=payload.failure_alert_enabled,
        category_rules=payload.category_rules,
    )
    return NotificationConfigResponse(
        enabled=row.enabled,
        to_email=row.to_email,
        daily_digest_enabled=row.daily_digest_enabled,
        daily_digest_hour_utc=row.daily_digest_hour_utc,
        failure_alert_enabled=row.failure_alert_enabled,
        category_rules=row.category_rules if isinstance(row.category_rules, dict) else {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post(
    "/test",
    response_model=NotificationSendResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_write_access)],
)
def post_test_notification(payload: NotificationTestRequest, db: Session = Depends(get_db)):
    try:
        row = send_test_email(
            db,
            to_email=payload.to_email,
            subject=payload.subject,
            body=payload.body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=sanitize_exception_detail(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=sanitize_exception_detail(exc)) from exc

    return NotificationSendResponse(
        delivery_id=row.id,
        status=row.status,
        provider_message_id=row.provider_message_id,
        error_message=row.error_message,
        recipient_email=row.recipient_email,
        subject=row.subject,
        sent_at=row.sent_at,
        created_at=row.created_at,
    )


@reports_router.post(
    "/daily/send",
    response_model=DailyReportSendResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_write_access)],
)
def post_daily_report_send(payload: DailyReportSendRequest, db: Session = Depends(get_db)):
    try:
        row = send_daily_report_notification(
            db,
            report_date=payload.date,
            to_email=payload.to_email,
            subject=payload.subject,
            body=payload.body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=sanitize_exception_detail(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=sanitize_exception_detail(exc)) from exc

    digest_date = payload.date
    if digest_date is None and isinstance(row.payload_json, dict):
        payload_date = row.payload_json.get("digest_date")
        if isinstance(payload_date, str):
            try:
                digest_date = date_type.fromisoformat(payload_date)
            except ValueError:
                digest_date = None

    return DailyReportSendResponse(
        sent=row.status == "sent",
        status=row.status,
        delivery_id=row.id,
        date=digest_date or date_type.today(),
        recipient_email=row.recipient_email,
        subject=row.subject,
        error_message=row.error_message,
        sent_at=row.sent_at,
        created_at=row.created_at,
    )


@router.post(
    "/category/send",
    response_model=NotificationSendResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_write_access)],
)
def post_category_send(payload: CategoryDigestSendRequest, db: Session = Depends(get_db)):
    try:
        row = send_category_digest(
            db,
            category=payload.category,
            digest_markdown=payload.body,
            to_email=payload.to_email,
            subject=payload.subject,
            priority=payload.priority,
            dispatch_key=payload.dispatch_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=sanitize_exception_detail(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=sanitize_exception_detail(exc)) from exc

    return NotificationSendResponse(
        delivery_id=row.id,
        status=row.status,
        provider_message_id=row.provider_message_id,
        error_message=row.error_message,
        recipient_email=row.recipient_email,
        subject=row.subject,
        sent_at=row.sent_at,
        created_at=row.created_at,
    )
