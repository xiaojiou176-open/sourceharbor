from __future__ import annotations

import importlib
from typing import Any

import httpx


async def fetch_article_html(
    source_url: str,
    *,
    timeout_seconds: float = 30.0,
    follow_redirects: bool = True,
    async_client_cls: Any = httpx.AsyncClient,
) -> str:
    async with async_client_cls(
        timeout=timeout_seconds, follow_redirects=follow_redirects
    ) as client:
        response = await client.get(source_url)
        response.raise_for_status()
        return response.text


def extract_article_text(
    html: str,
    *,
    import_module: Any = importlib.import_module,
) -> str | None:
    trafilatura = import_module("trafilatura")
    extracted = trafilatura.extract(html, include_comments=False, include_tables=True)
    if extracted and extracted.strip():
        return extracted.strip()
    return None
