from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

import httpx


def build_health_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/healthz"


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _find_text(node: ET.Element, names: set[str]) -> str | None:
    for child in node:
        if _local_name(child.tag) in names and child.text:
            text = child.text.strip()
            if text:
                return text
    return None


def _extract_link(node: ET.Element) -> str | None:
    for child in node:
        if _local_name(child.tag) != "link":
            continue

        href = (child.attrib.get("href") or "").strip()
        if href:
            return href

        if child.text and child.text.strip():
            return child.text.strip()
    return None


def parse_feed(xml_content: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_content)
    root_name = _local_name(root.tag)

    if root_name == "rss":
        channel = next((c for c in root if _local_name(c.tag) == "channel"), None)
        items = [c for c in channel if _local_name(c.tag) == "item"] if channel is not None else []
    elif root_name == "feed":
        items = [c for c in root if _local_name(c.tag) == "entry"]
    else:
        items = []

    entries: list[dict[str, Any]] = []
    for item in items:
        entries.append(
            {
                "title": _find_text(item, {"title"}),
                "link": _extract_link(item),
                "guid": _find_text(item, {"guid", "id"}),
                "published_at": _find_text(item, {"pubDate", "published", "updated"}),
                "summary": _find_text(item, {"description", "summary"}),
                "content": _find_text(item, {"content", "encoded"}),
            }
        )
    return entries


def is_risk_control_response(response: httpx.Response) -> bool:
    body = response.text or ""
    return "-352" in body or "风控" in body or "412 Precondition Failed" in body
