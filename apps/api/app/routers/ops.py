from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..security import sanitize_exception_detail
from ..services.ops import OpsService

router = APIRouter(prefix="/api/v1/ops", tags=["ops"])
logger = logging.getLogger(__name__)


def get_ops_service(db: Session = Depends(get_db)) -> OpsService:
    return OpsService(db)


@router.get("/inbox")
def get_ops_inbox(
    limit: int = Query(default=5, ge=1, le=20),
    window_hours: int = Query(default=24, ge=1, le=168),
    service: OpsService = Depends(get_ops_service),
):
    try:
        return service.get_inbox(limit=limit, window_hours=window_hours)
    except ValueError as exc:
        logger.info(
            "ops_inbox_invalid_request",
            extra={"error": sanitize_exception_detail(exc)},
        )
        raise HTTPException(status_code=400, detail="invalid ops inbox request") from exc
    except Exception as exc:
        logger.exception(
            "ops_inbox_unavailable",
            extra={"error": sanitize_exception_detail(exc)},
        )
        raise HTTPException(
            status_code=503,
            detail="ops inbox unavailable",
        ) from exc
