from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from apps.runtime_paths import get_runtime_config_root

_TEMPLATE_FILE = (
    get_runtime_config_root() / "source-templates" / "vendor_signal_templates.json"
)


def _normalize_signal_layer(item: Any) -> dict[str, str] | None:
    if not isinstance(item, dict):
        return None
    normalized = {
        "id": str(item.get("id") or "").strip(),
        "label": str(item.get("label") or "").strip(),
        "description": str(item.get("description") or "").strip(),
    }
    if not all(normalized.values()):
        return None
    return normalized


def _normalize_confirmation_step(item: Any) -> dict[str, str] | None:
    if not isinstance(item, dict):
        return None
    normalized = {
        "id": str(item.get("id") or "").strip(),
        "label": str(item.get("label") or "").strip(),
        "description": str(item.get("description") or "").strip(),
    }
    if not all(normalized.values()):
        return None
    return normalized


def _normalize_starter_watchlist(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    normalized = {
        "name": str(item.get("name") or "").strip(),
        "matcher_type": str(item.get("matcher_type") or "").strip(),
        "matcher_value": str(item.get("matcher_value") or "").strip(),
        "delivery_channel": str(item.get("delivery_channel") or "dashboard").strip()
        or "dashboard",
        "briefing_goal": str(item.get("briefing_goal") or "").strip(),
    }
    if not normalized["name"] or not normalized["matcher_type"] or not normalized["matcher_value"]:
        return None
    if normalized["delivery_channel"] not in {"dashboard", "email"}:
        normalized["delivery_channel"] = "dashboard"
    return normalized


def _normalize_channel(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    normalized = {
        "id": str(item.get("id") or "").strip(),
        "label": str(item.get("label") or "").strip(),
        "url": str(item.get("url") or "").strip(),
        "channel_kind": str(item.get("channel_kind") or "").strip(),
        "signal_layer": str(item.get("signal_layer") or "").strip(),
        "why_it_matters": str(item.get("why_it_matters") or "").strip(),
        "ingest_mode": str(item.get("ingest_mode") or "").strip(),
    }
    if not all(normalized.values()):
        return None
    normalized["feed_url"] = str(item.get("feed_url") or "").strip() or None
    return normalized


def _normalize_vendor(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    normalized = {
        "id": str(item.get("id") or "").strip(),
        "label": str(item.get("label") or "").strip(),
        "description": str(item.get("description") or "").strip(),
        "official_first_move": str(item.get("official_first_move") or "").strip(),
        "x_policy_summary": str(item.get("x_policy_summary") or "").strip(),
        "starter_watchlist": _normalize_starter_watchlist(item.get("starter_watchlist")),
        "confirmation_chain": [
            step
            for raw_step in item.get("confirmation_chain", [])
            if (step := _normalize_confirmation_step(raw_step)) is not None
        ],
        "channels": [
            channel
            for raw_channel in item.get("channels", [])
            if (channel := _normalize_channel(raw_channel)) is not None
        ],
    }
    if not normalized["id"] or not normalized["label"] or not normalized["description"]:
        return None
    if normalized["starter_watchlist"] is None or not normalized["channels"]:
        return None
    return normalized


@lru_cache(maxsize=1)
def _load_vendor_signal_catalog_cached() -> dict[str, list[dict[str, Any]]]:
    payload = json.loads(_TEMPLATE_FILE.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("vendor signal catalog must be a JSON object")

    signal_layers = [
        normalized
        for item in payload.get("signal_layers", [])
        if (normalized := _normalize_signal_layer(item)) is not None
    ]
    vendors = [
        normalized
        for item in payload.get("vendors", [])
        if (normalized := _normalize_vendor(item)) is not None
    ]
    return {"signal_layers": signal_layers, "vendors": vendors}


def load_vendor_signal_catalog() -> dict[str, list[dict[str, Any]]]:
    try:
        payload = _load_vendor_signal_catalog_cached()
    except (OSError, ValueError, json.JSONDecodeError):
        return {"signal_layers": [], "vendors": []}

    return {
        "signal_layers": [dict(item) for item in payload["signal_layers"]],
        "vendors": [
            {
                **dict(item),
                "starter_watchlist": dict(item["starter_watchlist"]),
                "confirmation_chain": [dict(step) for step in item["confirmation_chain"]],
                "channels": [dict(channel) for channel in item["channels"]],
            }
            for item in payload["vendors"]
        ],
    }
