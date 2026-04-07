from __future__ import annotations

from typing import Any

import httpx

from integrations.providers import resend as resend_provider

RESEND_API_URL = resend_provider.RESEND_API_URL


def normalize_email(raw_email: Any) -> str | None:
    return resend_provider.normalize_email(raw_email)


def is_sensitive_query_key(key: str) -> bool:
    return resend_provider.is_sensitive_query_key(key)


def sanitize_url_for_payload(raw_url: str) -> str:
    return resend_provider.sanitize_url_for_payload(raw_url)


def sanitize_text_preview(text_value: str, *, max_chars: int = 500) -> str:
    return resend_provider.sanitize_text_preview(text_value, max_chars=max_chars)


def render_markdown_html(text_value: str) -> str:
    return resend_provider.render_markdown_html(text_value)


def to_html(text_value: str) -> str:
    return resend_provider.to_html(text_value)


def send_with_resend(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    resend_api_key: str | None,
    resend_from_email: str | None,
    idempotency_key: str | None = None,
) -> str | None:
    return resend_provider.send_with_resend(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        resend_api_key=resend_api_key,
        resend_from_email=resend_from_email,
        idempotency_key=idempotency_key,
        http_post=httpx.post,
    )
