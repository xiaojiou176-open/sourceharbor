from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from apps.runtime_paths import get_runtime_config_root

_TEMPLATE_FILE = get_runtime_config_root() / "source-templates" / "subscriptions.intake_templates.json"


def _normalize_template(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    required = (
        "id",
        "label",
        "description",
        "support_tier",
        "platform",
        "source_type",
        "adapter_type",
        "content_profile",
    )
    normalized = {
        key: item.get(key)
        for key in (
            *required,
            "category",
            "source_value_placeholder",
            "source_url_placeholder",
            "rsshub_route_hint",
            "source_url_required",
            "supports_video_pipeline",
            "fill_now",
            "proof_boundary",
            "evidence_note",
        )
    }
    if not all(
        isinstance(normalized.get(key), str) and str(normalized[key]).strip() for key in required
    ):
        return None
    normalized["source_url_required"] = bool(normalized.get("source_url_required", False))
    normalized["supports_video_pipeline"] = bool(normalized.get("supports_video_pipeline", False))
    for key, value in list(normalized.items()):
        if isinstance(value, str):
            normalized[key] = value.strip()
    return normalized


def _normalize_support_tier(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    required = ("id", "label", "description", "content_profile", "verification_status")
    normalized = {key: item.get(key) for key in required + ("supports_video_pipeline",)}
    if not all(
        isinstance(normalized.get(key), str) and str(normalized[key]).strip() for key in required
    ):
        return None
    normalized["supports_video_pipeline"] = bool(normalized.get("supports_video_pipeline", False))
    for key, value in list(normalized.items()):
        if isinstance(value, str):
            normalized[key] = value.strip()
    return normalized


@lru_cache(maxsize=1)
def _load_subscription_template_catalog_cached() -> dict[str, list[dict[str, Any]]]:
    payload = json.loads(_TEMPLATE_FILE.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise ValueError("subscription template catalog must be a JSON object")

    support_tiers = [
        normalized
        for item in payload.get("support_tiers", [])
        if (normalized := _normalize_support_tier(item)) is not None
    ]
    templates = [
        normalized
        for item in payload.get("templates", [])
        if (normalized := _normalize_template(item)) is not None
    ]
    return {"support_tiers": support_tiers, "templates": templates}


def load_subscription_template_catalog() -> dict[str, list[dict[str, Any]]]:
    try:
        payload = _load_subscription_template_catalog_cached()
    except (OSError, ValueError, json.JSONDecodeError):
        return {"support_tiers": [], "templates": []}

    # Return fresh containers so callers cannot mutate the cached catalog shared by later tests.
    return {
        "support_tiers": [dict(item) for item in payload["support_tiers"]],
        "templates": [dict(item) for item in payload["templates"]],
    }
