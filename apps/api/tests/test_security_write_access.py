from __future__ import annotations

import hashlib
import hmac
import time

import pytest
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from apps.api.app.security import (
    _allow_unauth_write,
    _is_valid_signed_session_token,
    _sign_session_bucket,
    _token_bucket,
    require_write_access,
    sanitize_exception_detail,
)


def _build_web_session_token(secret: str) -> str:
    bucket = int(time.time()) // (15 * 60)
    signature = hmac.new(
        secret.encode("utf-8"), str(bucket).encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{bucket}.{signature}"


def test_require_write_access_rejects_when_api_key_not_configured_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SOURCE_HARBOR_API_KEY", raising=False)
    monkeypatch.delenv("SOURCE_HARBOR_ALLOW_UNAUTH_WRITE", raising=False)
    with pytest.raises(HTTPException) as exc_info:
        require_write_access(
            bearer=None,
            api_key_header=None,
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "write access token required"


def test_require_write_access_allows_when_unauth_write_switch_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SOURCE_HARBOR_API_KEY", raising=False)
    monkeypatch.setenv("SOURCE_HARBOR_ALLOW_UNAUTH_WRITE", "true")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "apps/api/tests/test_security_write_access.py::test")
    require_write_access(
        bearer=None,
        api_key_header=None,
    )


def test_require_write_access_rejects_when_ci_opt_in_set_outside_pytest_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SOURCE_HARBOR_API_KEY", raising=False)
    monkeypatch.setenv("SOURCE_HARBOR_ALLOW_UNAUTH_WRITE", "true")
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("SOURCE_HARBOR_CI_ALLOW_UNAUTH_WRITE", "true")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    with pytest.raises(HTTPException) as exc_info:
        require_write_access(
            bearer=None,
            api_key_header=None,
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "write access token required"


def test_require_write_access_rejects_when_unauth_write_switch_enabled_outside_test_or_ci(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SOURCE_HARBOR_API_KEY", raising=False)
    monkeypatch.setenv("SOURCE_HARBOR_ALLOW_UNAUTH_WRITE", "true")
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("SOURCE_HARBOR_CI_ALLOW_UNAUTH_WRITE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    with pytest.raises(HTTPException) as exc_info:
        require_write_access(
            bearer=None,
            api_key_header=None,
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "write access token required"


def test_require_write_access_rejects_bearer_when_api_key_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SOURCE_HARBOR_API_KEY", raising=False)
    monkeypatch.delenv("SOURCE_HARBOR_ALLOW_UNAUTH_WRITE", raising=False)
    with pytest.raises(HTTPException) as exc_info:
        require_write_access(
            bearer=HTTPAuthorizationCredentials(scheme="Bearer", credentials="provided-token"),
            api_key_header=None,
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "write access token required"


def test_require_write_access_falls_back_to_x_api_key_when_auth_scheme_is_not_bearer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOURCE_HARBOR_API_KEY", "unit-test-token")
    require_write_access(
        bearer=HTTPAuthorizationCredentials(scheme="Basic", credentials="ignored"),
        api_key_header=" unit-test-token ",
    )


def test_require_write_access_rejects_when_no_usable_token_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOURCE_HARBOR_API_KEY", "unit-test-token")
    with pytest.raises(HTTPException) as exc_info:
        require_write_access(
            bearer=HTTPAuthorizationCredentials(scheme="Digest", credentials="ignored"),
            api_key_header="   ",
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "write access token required"


def test_require_write_access_prefers_bearer_and_rejects_mismatch_even_if_x_api_key_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOURCE_HARBOR_API_KEY", "unit-test-token")
    with pytest.raises(HTTPException) as exc_info:
        require_write_access(
            bearer=HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrong-token"),
            api_key_header="unit-test-token",
        )

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail == "invalid write access token"


def test_require_write_access_accepts_valid_web_session_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WEB_ACTION_SESSION_TOKEN", raising=False)
    monkeypatch.setenv("SOURCE_HARBOR_API_KEY", "unit-test-token")
    require_write_access(
        bearer=None,
        api_key_header=None,
        web_session_header=_build_web_session_token("unit-test-token"),
    )


def test_require_write_access_rejects_invalid_web_session_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WEB_ACTION_SESSION_TOKEN", raising=False)
    monkeypatch.setenv("SOURCE_HARBOR_API_KEY", "unit-test-token")
    with pytest.raises(HTTPException) as exc_info:
        require_write_access(
            bearer=None,
            api_key_header=None,
            web_session_header="bad-token",
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "write access token required"


def test_sanitize_exception_detail_uses_fallback_and_truncates() -> None:
    assert (
        sanitize_exception_detail(Exception("   "), fallback="fallback-value") == "fallback-value"
    )

    sanitized_secret = sanitize_exception_detail(Exception("Bearer " + ("a" * 600)), max_chars=40)
    assert sanitized_secret == "Bearer ***REDACTED***"

    long_plain = "x" * 600
    sanitized = sanitize_exception_detail(Exception(long_plain), max_chars=40)
    assert sanitized.endswith("...[truncated]")
    assert sanitized.startswith("x" * 40)


def test_signed_session_token_rejects_invalid_shape_and_stale_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "unit-test-token"
    current_bucket = _token_bucket()

    assert _is_valid_signed_session_token(secret, "bad-token") is False
    assert _is_valid_signed_session_token(secret, f"{current_bucket}.nothex") is False

    old_bucket = current_bucket - 2
    stale_signature = _sign_session_bucket(secret, old_bucket)
    assert _is_valid_signed_session_token(secret, f"{old_bucket}.{stale_signature}") is False


def test_allow_unauth_write_rejects_non_truthy_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOURCE_HARBOR_ALLOW_UNAUTH_WRITE", "0")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "apps/api/tests/test_security_write_access.py::test")
    assert _allow_unauth_write() is False
