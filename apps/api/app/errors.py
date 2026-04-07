from __future__ import annotations


def build_error_payload(
    *,
    detail: str,
    error_code: str,
    error_kind: str | None = None,
) -> dict[str, str]:
    payload: dict[str, str] = {
        "detail": detail,
        "error_code": error_code,
    }
    if error_kind:
        payload["error_kind"] = error_kind
    return payload


class ApiServiceError(RuntimeError):
    def __init__(
        self,
        *,
        detail: str,
        error_code: str,
        status_code: int = 503,
        error_kind: str = "upstream_error",
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.error_code = error_code
        self.status_code = status_code
        self.error_kind = error_kind

    def to_payload(self) -> dict[str, str]:
        return build_error_payload(
            detail=self.detail,
            error_code=self.error_code,
            error_kind=self.error_kind,
        )


class ApiTimeoutError(ApiServiceError):
    def __init__(
        self,
        *,
        detail: str,
        error_code: str,
        status_code: int = 504,
    ) -> None:
        super().__init__(
            detail=detail,
            error_code=error_code,
            status_code=status_code,
            error_kind="timeout",
        )
