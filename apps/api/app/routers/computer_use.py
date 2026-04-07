from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..security import require_write_access, sanitize_exception_detail
from ..services.computer_use import ComputerUseSafetyConfig, ComputerUseService

router = APIRouter(prefix="/api/v1/computer-use", tags=["computer_use"])


class ComputerUseSafety(BaseModel):
    confirm_before_execute: bool = True
    blocked_actions: list[str] = Field(default_factory=list)
    max_actions: int = Field(default=8, ge=1, le=20)


class ComputerUseRunRequest(BaseModel):
    instruction: str = Field(min_length=1)
    screenshot_base64: str = Field(min_length=1)
    safety: ComputerUseSafety = Field(default_factory=ComputerUseSafety)


class ComputerUseAction(BaseModel):
    step: int = Field(ge=1)
    action: str
    target: str | None = None
    input_text: str | None = None
    reasoning: str | None = None


class ComputerUseRunResponse(BaseModel):
    actions: list[ComputerUseAction]
    require_confirmation: bool
    blocked_actions: list[str]
    final_text: str
    thought_metadata: dict[str, Any]


@router.post(
    "/run",
    response_model=ComputerUseRunResponse,
    dependencies=[Depends(require_write_access)],
)
def run_computer_use(payload: ComputerUseRunRequest) -> ComputerUseRunResponse:
    service = ComputerUseService()
    try:
        result = service.run(
            instruction=payload.instruction,
            screenshot_base64=payload.screenshot_base64,
            safety=ComputerUseSafetyConfig(
                confirm_before_execute=payload.safety.confirm_before_execute,
                blocked_actions=payload.safety.blocked_actions,
                max_actions=payload.safety.max_actions,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=sanitize_exception_detail(exc)) from exc

    return ComputerUseRunResponse(**result)
