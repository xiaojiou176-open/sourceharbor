from __future__ import annotations

import re
from html import escape
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

RESEND_API_URL = "https://api.resend.com/emails"
RESEND_DOMAINS_URL = "https://api.resend.com/domains"
SENSITIVE_QUERY_KEY_MARKERS = ("key", "token", "secret", "password", "auth", "signature")
SENSITIVE_TEXT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE), "Bearer ***REDACTED***"),
    (
        re.compile(r"\b([A-Za-z][A-Za-z0-9]{1,15})-([A-Za-z0-9]{20,})\b"),
        r"\1-***REDACTED***",
    ),
    (re.compile(r"(ghp_[A-Za-z0-9]{20,})"), "ghp_***REDACTED***"),
    (re.compile(r"(AKIA[0-9A-Z]{16})"), "AKIA***REDACTED***"),
)


def normalize_email(raw_email: Any) -> str | None:
    if not isinstance(raw_email, str):
        return None
    cleaned = raw_email.strip()
    return cleaned or None


def is_sensitive_query_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    return any(marker in normalized for marker in SENSITIVE_QUERY_KEY_MARKERS)


def sanitize_url_for_payload(raw_url: str) -> str:
    try:
        parsed = urlsplit(raw_url)
    except ValueError:
        return raw_url

    redacted_items: list[tuple[str, str]] = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if is_sensitive_query_key(key):
            redacted_items.append((key, "***REDACTED***"))
            continue
        redacted_items.append((key, value))
    sanitized_query = urlencode(redacted_items, doseq=True)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, sanitized_query, parsed.fragment))


def sanitize_text_preview(text_value: str, *, max_chars: int = 500) -> str:
    sanitized = text_value
    for pattern, replacement in SENSITIVE_TEXT_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    if len(sanitized) > max_chars:
        return f"{sanitized[:max_chars]}...[truncated]"
    return sanitized


def render_markdown_html(text_value: str) -> str:
    try:
        import markdown as md  # type: ignore

        return md.markdown(
            text_value,
            extensions=[
                "extra",
                "fenced_code",
                "tables",
                "sane_lists",
                "nl2br",
            ],
            output_format="html5",
        )
    except Exception:
        lines = [escape(line) for line in text_value.splitlines()]
        return f"<div>{'<br/>'.join(lines)}</div>"


def to_html(text_value: str) -> str:
    body = render_markdown_html(text_value)
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        "<style>"
        "body{margin:0;padding:0;background:#f5f7fb;color:#0f172a;"
        "font-family:'PingFang SC','Microsoft YaHei',-apple-system,BlinkMacSystemFont,sans-serif;}"
        ".container{max-width:860px;margin:0 auto;padding:24px;}"
        ".card{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:20px 24px;"
        "box-shadow:0 8px 24px rgba(15,23,42,0.06);line-height:1.65;font-size:15px;}"
        "h1,h2,h3{line-height:1.35;margin:22px 0 12px;color:#0b1324;}h1{font-size:28px;}h2{font-size:22px;}h3{font-size:18px;}"
        "p{margin:10px 0;}ul,ol{margin:8px 0 12px 22px;padding:0;}li{margin:4px 0;}"
        "code{background:#f1f5f9;padding:2px 6px;border-radius:6px;font-size:13px;}"
        "pre{background:#0f172a;color:#e2e8f0;padding:12px;border-radius:8px;overflow:auto;}"
        "pre code{background:transparent;color:inherit;padding:0;}"
        "a{color:#1d4ed8;text-decoration:none;}a:hover{text-decoration:underline;}"
        "blockquote{border-left:4px solid #94a3b8;margin:12px 0;padding:4px 0 4px 12px;color:#475569;}"
        "table{border-collapse:collapse;width:100%;margin:12px 0;}"
        "th,td{border:1px solid #dbe3ee;padding:6px 8px;text-align:left;vertical-align:top;}"
        "img{max-width:100%;height:auto;border-radius:8px;border:1px solid #e2e8f0;}"
        "hr{border:none;border-top:1px solid #e2e8f0;margin:20px 0;}"
        '</style></head><body><div class="container"><article class="card">'
        f"{body}</article></div></body></html>"
    )


def send_with_resend(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    resend_api_key: str | None,
    resend_from_email: str | None,
    idempotency_key: str | None = None,
    http_post: Callable[..., Any] = httpx.post,
) -> str | None:
    if not resend_api_key or not resend_api_key.strip():
        raise RuntimeError("RESEND_API_KEY is not configured")
    if not resend_from_email or not resend_from_email.strip():
        raise RuntimeError("RESEND_FROM_EMAIL is not configured")

    payload = {
        "from": resend_from_email,
        "to": [to_email],
        "subject": subject,
        "text": text_body,
        "html": to_html(text_body),
    }
    headers = {
        "Authorization": f"Bearer {resend_api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "sourceharbor/1.0 (+https://local.sourceharbor)",
    }
    if isinstance(idempotency_key, str) and idempotency_key.strip():
        headers["Idempotency-Key"] = idempotency_key.strip()

    try:
        response = http_post(
            RESEND_API_URL,
            headers=headers,
            json=payload,
            timeout=10.0,
        )
    except httpx.RequestError as exc:
        raise RuntimeError(f"Resend request failed: {exc}") from exc
    if response.status_code >= 400:
        raise RuntimeError(f"Resend API returned {response.status_code}: {response.text[:500]}")

    try:
        parsed = response.json()
    except ValueError:
        return None
    message_id = parsed.get("id")
    if isinstance(message_id, str):
        return message_id
    return None


def build_domains_probe_request(api_key: str) -> tuple[str, dict[str, str]]:
    return RESEND_DOMAINS_URL, {"Authorization": f"Bearer {api_key}"}
