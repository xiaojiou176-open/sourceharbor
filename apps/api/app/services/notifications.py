from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from html import escape

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from integrations.providers import resend as resend_provider

from ..config import settings
from ..models import NotificationConfig, NotificationDelivery

RESEND_API_URL = resend_provider.RESEND_API_URL


def _utc_now() -> datetime:
    return datetime.now(UTC)


def get_notification_config(db: Session) -> NotificationConfig:
    stmt = select(NotificationConfig).where(NotificationConfig.singleton_key == 1)
    config = db.scalar(stmt)
    if config is not None:
        return config

    config = NotificationConfig(singleton_key=1)
    db.add(config)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(stmt)
        if existing is None:
            raise
        return existing

    db.refresh(config)
    return config


def update_notification_config(
    db: Session,
    *,
    enabled: bool,
    to_email: str | None,
    daily_digest_enabled: bool,
    daily_digest_hour_utc: int | None,
    failure_alert_enabled: bool,
    category_rules: dict[str, object] | None = None,
) -> NotificationConfig:
    config = get_notification_config(db)
    normalized_to_email = _normalize_email(to_email)

    config.enabled = enabled
    config.to_email = normalized_to_email
    config.daily_digest_enabled = daily_digest_enabled
    config.daily_digest_hour_utc = daily_digest_hour_utc
    config.failure_alert_enabled = failure_alert_enabled
    if category_rules is not None:
        config.category_rules = category_rules if isinstance(category_rules, dict) else {}

    db.commit()
    db.refresh(config)
    return config


def send_test_email(
    db: Session,
    *,
    to_email: str | None = None,
    subject: str | None = None,
    body: str | None = None,
) -> NotificationDelivery:
    config = get_notification_config(db)
    recipient = _resolve_recipient_email(config, to_email)
    if recipient is None:
        raise ValueError("notification recipient email is not configured")

    return _dispatch_email(
        db,
        kind="test_email",
        recipient_email=recipient,
        subject=subject or "SourceHarbor test notification",
        text_body=body or "This is a test notification from SourceHarbor.",
        payload={"to_email": recipient},
        skip_reason=None,
    )


def send_failure_alert(
    db: Session,
    *,
    title: str,
    details: str,
    job_id: uuid.UUID | None = None,
    to_email: str | None = None,
) -> NotificationDelivery:
    config = get_notification_config(db)
    recipient = _resolve_recipient_email(config, to_email)
    if recipient is None:
        raise ValueError("notification recipient email is not configured")

    skip_reason: str | None = None
    if not config.enabled:
        skip_reason = "notification config is disabled"
    elif not config.failure_alert_enabled:
        skip_reason = "failure alert is disabled"

    return _dispatch_email(
        db,
        kind="failure_alert",
        recipient_email=recipient,
        subject=f"[SourceHarbor] Failure alert: {title}",
        text_body=details,
        payload={"job_id": str(job_id) if job_id else None, "title": title},
        job_id=job_id,
        skip_reason=skip_reason,
    )


def send_daily_digest(
    db: Session,
    *,
    digest_markdown: str,
    digest_date: date | None = None,
    to_email: str | None = None,
    subject: str | None = None,
) -> NotificationDelivery:
    config = get_notification_config(db)
    recipient = _resolve_recipient_email(config, to_email)
    if recipient is None:
        raise ValueError("notification recipient email is not configured")

    skip_reason: str | None = None
    if not config.enabled:
        skip_reason = "notification config is disabled"
    elif not config.daily_digest_enabled:
        skip_reason = "daily digest is disabled"

    effective_date = digest_date or datetime.now(UTC).date()

    return _dispatch_email(
        db,
        kind="daily_digest",
        recipient_email=recipient,
        subject=subject or f"[SourceHarbor] Daily digest {effective_date.isoformat()}",
        text_body=digest_markdown,
        payload={"digest_date": effective_date.isoformat()},
        skip_reason=skip_reason,
    )


def send_video_digest(
    db: Session,
    *,
    job_id: uuid.UUID,
    digest_markdown: str,
    to_email: str | None = None,
    subject: str | None = None,
) -> NotificationDelivery:
    config = get_notification_config(db)
    recipient = _resolve_recipient_email(config, to_email)
    if recipient is None:
        raise ValueError("notification recipient email is not configured")

    skip_reason: str | None = None
    if not config.enabled:
        skip_reason = "notification config is disabled"

    return _dispatch_email(
        db,
        kind="video_digest",
        recipient_email=recipient,
        subject=subject or "[SourceHarbor] Video digest",
        text_body=digest_markdown,
        payload={"job_id": str(job_id)},
        job_id=job_id,
        skip_reason=skip_reason,
    )


def send_category_digest(
    db: Session,
    *,
    category: str,
    digest_markdown: str,
    to_email: str | None = None,
    subject: str | None = None,
    priority: int | None = None,
    dispatch_key: str | None = None,
) -> NotificationDelivery:
    config = get_notification_config(db)
    recipient = _resolve_recipient_email(config, to_email)
    if recipient is None:
        raise ValueError("notification recipient email is not configured")

    normalized_category = category.strip().lower()
    normalized_dispatch_key = _normalize_dispatch_key(dispatch_key)
    skip_reason = _evaluate_category_rule(
        config=config,
        category=normalized_category,
        now_utc=_utc_now(),
        priority=priority,
    )

    return _dispatch_email(
        db,
        kind="daily_digest",
        recipient_email=recipient,
        subject=subject or f"[SourceHarbor] {normalized_category} digest",
        text_body=digest_markdown,
        payload={"category": normalized_category, "priority": priority},
        skip_reason=skip_reason,
        dispatch_key=normalized_dispatch_key,
    )


def send_daily_report_notification(
    db: Session,
    *,
    report_date: date | None = None,
    to_email: str | None = None,
    subject: str | None = None,
    body: str | None = None,
) -> NotificationDelivery:
    effective_date = report_date or datetime.now(UTC).date()
    return send_daily_digest(
        db,
        digest_markdown=body or f"SourceHarbor daily report for {effective_date.isoformat()}",
        digest_date=effective_date,
        to_email=to_email,
        subject=subject,
    )


def _dispatch_email(
    db: Session,
    *,
    kind: str,
    recipient_email: str,
    subject: str,
    text_body: str,
    payload: dict[str, object],
    job_id: uuid.UUID | None = None,
    skip_reason: str | None,
    dispatch_key: str | None = None,
) -> NotificationDelivery:
    normalized_dispatch_key = _normalize_dispatch_key(dispatch_key)
    if normalized_dispatch_key is not None:
        existing = _get_delivery_by_dispatch_key(
            db,
            kind=kind,
            dispatch_key=normalized_dispatch_key,
        )
        if existing is not None:
            return existing

    delivery = NotificationDelivery(
        kind=kind,
        status="queued",
        recipient_email=recipient_email,
        subject=subject,
        provider="resend",
        payload_json=payload,
        dispatch_key=normalized_dispatch_key,
        job_id=job_id,
    )
    db.add(delivery)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if normalized_dispatch_key is not None:
            existing = _get_delivery_by_dispatch_key(
                db,
                kind=kind,
                dispatch_key=normalized_dispatch_key,
            )
            if existing is not None:
                return existing
        if kind == "video_digest" and job_id is not None:
            existing = _get_video_digest_delivery(db, job_id=job_id)
            if existing is not None:
                return existing
        raise
    db.refresh(delivery)

    effective_skip_reason = skip_reason
    if effective_skip_reason is None and not settings.notification_enabled:
        effective_skip_reason = "notification is disabled by environment"

    if effective_skip_reason is not None:
        delivery.status = "skipped"
        delivery.error_message = effective_skip_reason
        db.commit()
        db.refresh(delivery)
        return delivery

    try:
        provider_message_id = _send_with_resend(
            to_email=recipient_email,
            subject=subject,
            text_body=text_body,
            resend_api_key=settings.resend_api_key,
            resend_from_email=settings.resend_from_email,
        )
        delivery.status = "sent"
        delivery.provider_message_id = provider_message_id
        delivery.sent_at = datetime.now(UTC)
        delivery.error_message = None
    except RuntimeError as exc:
        delivery.status = "failed"
        delivery.error_message = str(exc)
        db.commit()
        db.refresh(delivery)
        raise

    db.commit()
    db.refresh(delivery)
    return delivery


def _send_with_resend(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    resend_api_key: str | None,
    resend_from_email: str | None,
) -> str | None:
    return resend_provider.send_with_resend(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        resend_api_key=resend_api_key,
        resend_from_email=resend_from_email,
        http_post=httpx.post,
    )


def _resolve_recipient_email(config: NotificationConfig, override_email: str | None) -> str | None:
    if override_email is not None:
        normalized_override = _normalize_email(override_email)
        if normalized_override:
            return normalized_override
    return _normalize_email(config.to_email)


def _normalize_email(raw_email: str | None) -> str | None:
    return resend_provider.normalize_email(raw_email)


def _normalize_dispatch_key(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    cleaned = raw_value.strip()
    return cleaned or None


def _coerce_int(value: object, *, default: int | None = None) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            return default
    return default


def _extract_notification_rules(config: NotificationConfig, category: str) -> dict[str, object]:
    raw = config.category_rules if isinstance(config.category_rules, dict) else {}
    nested = raw.get("category_rules")
    if isinstance(nested, dict):
        category_rules = nested
        default_rule = raw.get("default_rule")
    else:
        category_rules = raw
        default_rule = None

    category_rule = category_rules.get(category)
    if isinstance(category_rule, dict):
        return category_rule
    if isinstance(default_rule, dict):
        return default_rule
    return {}


def _evaluate_category_rule(
    *,
    config: NotificationConfig,
    category: str,
    now_utc: datetime,
    priority: int | None,
) -> str | None:
    if not config.enabled:
        return "notification config is disabled"

    rule = _extract_notification_rules(config, category)
    if rule.get("enabled") is False:
        return f"category rule disabled: {category}"

    min_priority = _coerce_int(rule.get("min_priority"))
    if min_priority is not None and priority is not None and priority < min_priority:
        return f"priority below threshold: {priority} < {min_priority}"

    cadence = str(rule.get("cadence") or "instant").strip().lower()
    rule_hour = _coerce_int(rule.get("hour"), default=config.daily_digest_hour_utc)

    if cadence == "instant":
        return None

    if cadence == "daily":
        if rule_hour is None:
            return None
        if now_utc.hour != max(0, min(23, rule_hour)):
            return f"daily cadence mismatch hour={now_utc.hour}"
        return None

    if cadence == "weekly":
        weekday = _coerce_int(rule.get("weekday"), default=0)
        if weekday is None:
            weekday = 0
        weekday = max(0, min(6, weekday))
        if now_utc.weekday() != weekday:
            return f"weekly cadence mismatch weekday={now_utc.weekday()}"
        if rule_hour is None:
            return None
        if now_utc.hour != max(0, min(23, rule_hour)):
            return f"weekly cadence mismatch hour={now_utc.hour}"
        return None

    if cadence == "hourly":
        interval_hours = max(1, _coerce_int(rule.get("interval_hours"), default=1) or 1)
        if now_utc.hour % interval_hours != 0:
            return f"hourly cadence mismatch hour={now_utc.hour} interval={interval_hours}"
        return None

    return f"unsupported cadence: {cadence}"


def _render_markdown_html(text: str) -> str:
    try:
        import markdown as md  # type: ignore

        return md.markdown(
            text,
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
        lines = [escape(line) for line in text.splitlines()]
        return f"<div>{'<br/>'.join(lines)}</div>"


def _to_html(text: str) -> str:
    return resend_provider.to_html(text)


def _get_video_digest_delivery(
    db: Session,
    *,
    job_id: uuid.UUID,
) -> NotificationDelivery | None:
    stmt = (
        select(NotificationDelivery)
        .where(
            NotificationDelivery.kind == "video_digest",
            NotificationDelivery.job_id == job_id,
        )
        .order_by(NotificationDelivery.created_at.desc())
    )
    return db.scalar(stmt)


def _get_delivery_by_dispatch_key(
    db: Session,
    *,
    kind: str,
    dispatch_key: str,
) -> NotificationDelivery | None:
    stmt = (
        select(NotificationDelivery)
        .where(
            NotificationDelivery.kind == kind,
            NotificationDelivery.dispatch_key == dispatch_key,
        )
        .order_by(NotificationDelivery.created_at.desc())
    )
    return db.scalar(stmt)
