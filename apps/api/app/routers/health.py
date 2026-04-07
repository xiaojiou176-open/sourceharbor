from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.health import HealthService

router = APIRouter(prefix="/api/v1/health", tags=["health"])


class ProviderHealthSummary(BaseModel):
    provider: str
    ok: int
    warn: int
    fail: int
    last_status: str | None = None
    last_checked_at: datetime | None = None
    last_error_kind: str | None = None
    last_message: str | None = None


class ProviderHealthResponse(BaseModel):
    window_hours: int
    providers: list[ProviderHealthSummary]


@router.get("/providers", response_model=ProviderHealthResponse)
def get_provider_health(
    window_hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
) -> ProviderHealthResponse:
    service = HealthService(db)
    payload = service.get_provider_health(window_hours=window_hours)
    return ProviderHealthResponse(**payload)
