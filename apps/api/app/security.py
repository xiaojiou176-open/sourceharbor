from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets
import time

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

_bearer_security = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_web_session_header = APIKeyHeader(name="X-Web-Session", auto_error=False)
logger = logging.getLogger(__name__)
_WEB_ACTION_SESSION_TTL_SECONDS = 15 * 60

_SENSITIVE_TEXT_PATTERNS = (
    (re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE), "Bearer ***REDACTED***"),
    (re.compile(r"Basic\s+[A-Za-z0-9+/=._\-]+", re.IGNORECASE), "Basic ***REDACTED***"),
    (
        re.compile(r"([a-z][a-z0-9+.\-]*://)([^:@/\s]+):([^@/\s]+)@", re.IGNORECASE),
        r"\1***:***@",
    ),
    (re.compile(r"(sk-[A-Za-z0-9]{20,})"), "sk-***REDACTED***"),
    (re.compile(r"(ghp_[A-Za-z0-9]{20,})"), "ghp_***REDACTED***"),
    (re.compile(r"(AKIA[0-9A-Z]{16})"), "AKIA***REDACTED***"),
    (re.compile(r"(ASIA[0-9A-Z]{16})"), "ASIA***REDACTED***"),
    (
        re.compile(
            r"([?&](?:api[_-]?key|apikey|key|token|access[_-]?token|refresh[_-]?token|id[_-]?token|oauth[_-]?token|jwt|secret|client[_-]?secret|password|passwd|session(?:id)?|auth(?:orization)?|signature)=)[^&\s]+",
            re.IGNORECASE,
        ),
        r"\1***REDACTED***",
    ),
    (
        re.compile(
            r"((?:^|[{,\s])(?:\"|')?(?:password|passwd|token|access[_-]?token|refresh[_-]?token|id[_-]?token|oauth[_-]?token|api[_-]?key|apikey|secret|client[_-]?secret|session(?:id)?|signature)(?:\"|')?\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^,\s}\]&]+)",
            re.IGNORECASE,
        ),
        r"\1***REDACTED***",
    ),
)


def sanitize_exception_detail(
    exc: Exception, *, fallback: str = "internal_error", max_chars: int = 500
) -> str:
    detail = str(exc).strip()
    if not detail:
        return fallback
    sanitized = detail
    for pattern, replacement in _SENSITIVE_TEXT_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    if len(sanitized) > max_chars:
        return f"{sanitized[:max_chars]}...[truncated]"
    return sanitized


def _configured_api_key() -> str | None:
    configured = os.getenv("SOURCE_HARBOR_API_KEY")
    if configured is None:
        return None
    value = configured.strip()
    return value or None


def _configured_web_session_secret() -> str | None:
    configured = os.getenv("WEB_ACTION_SESSION_TOKEN") or os.getenv("SOURCE_HARBOR_API_KEY")
    if configured is None:
        return None
    value = configured.strip()
    return value or None


def _token_bucket(now_ms: int | None = None) -> int:
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    return now // 1000 // _WEB_ACTION_SESSION_TTL_SECONDS


def _sign_session_bucket(secret: str, bucket: int) -> str:
    return hmac.new(secret.encode("utf-8"), str(bucket).encode("utf-8"), hashlib.sha256).hexdigest()


def _is_valid_signed_session_token(secret: str, candidate: str) -> bool:
    parts = candidate.split(".")
    if len(parts) != 2:
        return False
    bucket_raw, signature_raw = parts
    if not bucket_raw.isdigit() or not re.fullmatch(r"[A-Fa-f0-9]{64}", signature_raw):
        return False

    bucket = int(bucket_raw)
    current_bucket = _token_bucket()
    if bucket > current_bucket + 1 or current_bucket - bucket > 1:
        return False

    expected_signature = _sign_session_bucket(secret, bucket)
    return secrets.compare_digest(expected_signature, signature_raw.lower())


def _allow_unauth_write() -> bool:
    raw = os.getenv("SOURCE_HARBOR_ALLOW_UNAUTH_WRITE")
    if raw is None:
        return False
    value = raw.strip().lower()
    if value not in {"1", "true", "yes", "on"}:
        return False

    return bool(os.getenv("PYTEST_CURRENT_TEST"))


def _actor_label(
    bearer: HTTPAuthorizationCredentials | None,
    api_key_header: str | None,
) -> str:
    if bearer is not None and bearer.credentials:
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            str(bearer.credentials).encode("utf-8"),
            b"sourceharbor-actor-label",
            600_000,
        ).hex()[:12]
        return f"bearer_sha256:{digest}"
    if isinstance(api_key_header, str) and api_key_header.strip():
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            api_key_header.strip().encode("utf-8"),
            b"sourceharbor-actor-label",
            600_000,
        ).hex()[:12]
        return f"api_key_sha256:{digest}"
    return "anonymous"


def _log_write_access_denied(
    *,
    trace_id: str,
    actor: str,
    reason: str,
    status_code: int,
) -> None:
    logger.warning(
        "auth_write_access_denied",
        extra={
            "trace_id": trace_id,
            "user": actor,
            "error": reason,
            "status_code": status_code,
        },
    )


def require_write_access(
    bearer: HTTPAuthorizationCredentials | None = Security(_bearer_security),
    api_key_header: str | None = Security(_api_key_header),
    web_session_header: str | None = Security(_web_session_header),
) -> None:
    trace_id = secrets.token_hex(8)
    actor = _actor_label(bearer, api_key_header)
    web_session_secret = _configured_web_session_secret()
    web_session_candidate = (
        web_session_header.strip() if isinstance(web_session_header, str) else None
    )
    if (
        web_session_secret is not None
        and web_session_candidate
        and (
            _is_valid_signed_session_token(web_session_secret, web_session_candidate)
            or secrets.compare_digest(web_session_candidate, web_session_secret)
        )
    ):
        return

    expected = _configured_api_key()
    if expected is None:
        if _allow_unauth_write():
            logger.info(
                "auth_write_access_bypassed",
                extra={"trace_id": trace_id, "user": actor, "reason": "allow_unauth_write"},
            )
            return
        _log_write_access_denied(
            trace_id=trace_id,
            actor=actor,
            reason="api_key_not_configured",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="write access token required",
        )

    provided: str | None = None
    if bearer is not None and bearer.scheme.lower() == "bearer":
        provided = bearer.credentials
    if provided is None and isinstance(api_key_header, str) and api_key_header.strip():
        provided = api_key_header.strip()

    if provided is None:
        _log_write_access_denied(
            trace_id=trace_id,
            actor=actor,
            reason="missing_write_token",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="write access token required",
        )
    if not secrets.compare_digest(provided, expected):
        _log_write_access_denied(
            trace_id=trace_id,
            actor=actor,
            reason="invalid_write_token",
            status_code=status.HTTP_403_FORBIDDEN,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid write access token",
        )
