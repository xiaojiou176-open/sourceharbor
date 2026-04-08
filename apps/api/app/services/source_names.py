from __future__ import annotations

import json
from functools import lru_cache
from urllib.parse import urlparse

from apps.runtime_paths import get_runtime_config_root

_MAPPING_FILE = get_runtime_config_root() / "source-names" / "subscriptions.up_names.json"


@lru_cache(maxsize=1)
def _load_mappings() -> dict[str, dict[str, str]]:
    try:
        payload = json.loads(_MAPPING_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    result: dict[str, dict[str, str]] = {}
    for source_type, values in payload.items():
        if not isinstance(source_type, str) or not isinstance(values, dict):
            continue
        normalized_values: dict[str, str] = {}
        for key, value in values.items():
            if isinstance(key, str) and isinstance(value, str):
                normalized_values[key.strip()] = value.strip()
        result[source_type.strip().lower()] = normalized_values
    return result


def resolve_source_name(*, source_type: str, source_value: str, fallback: str) -> str:
    mappings = _load_mappings()
    key = source_type.strip().lower()
    value = source_value.strip()
    if key and value:
        resolved = mappings.get(key, {}).get(value)
        if resolved:
            return resolved
    fallback_value = fallback.strip()
    return fallback_value or value or "Unknown"


def build_source_name_fallback(
    *,
    platform: str,
    source_type: str,
    source_value: str,
    source_url: str | None,
    rsshub_route: str | None,
) -> str:
    normalized_platform = str(platform or "").strip().lower()
    normalized_source_type = str(source_type or "").strip().lower()
    normalized_source_value = str(source_value or "").strip()
    if normalized_source_value and normalized_source_type not in {"rsshub_route", "url"}:
        return normalized_source_value

    normalized_source_url = str(source_url or "").strip()
    allow_route_fallback = normalized_source_type in {"rsshub_route", "url"}
    if normalized_source_url and allow_route_fallback:
        parsed = urlparse(normalized_source_url)
        host = str(parsed.netloc or "").strip()
        path = str(parsed.path or "").strip("/")
        if host and path:
            return f"{host}/{path}"
        if host:
            return host
        return normalized_source_url

    normalized_route = str(rsshub_route or "").strip()
    if normalized_route and allow_route_fallback:
        if normalized_route.startswith("/"):
            return f"RSSHub {normalized_route}"
        return normalized_route

    if normalized_source_value and normalized_source_type and normalized_source_type != "url":
        return f"{normalized_platform or normalized_source_type}:{normalized_source_value}"
    return normalized_source_value or "Unknown"
