from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlparse


def extract_youtube_video_id(source_url: str | None, video_uid: str | None) -> str:
    uid = str(video_uid or "").strip()
    if uid:
        return uid

    raw = str(source_url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower()
    if host == "youtu.be":
        return parsed.path.strip("/").split("/")[0]
    if "youtube.com" not in host:
        return ""

    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    candidate = str(query.get("v") or "").strip()
    if candidate:
        return candidate

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "shorts":
        return parts[1]
    return ""


def fetch_youtube_transcript_text(video_id: str) -> str:
    from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore[import-not-found]

    languages = ["zh-Hans", "zh-Hant", "zh", "en", "en-US"]
    entries: Any = None

    if hasattr(YouTubeTranscriptApi, "get_transcript"):
        entries = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
    else:
        api = YouTubeTranscriptApi()  # type: ignore[operator]
        if hasattr(api, "get_transcript"):
            entries = api.get_transcript(video_id, languages=languages)  # type: ignore[call-arg]
        elif hasattr(api, "fetch"):
            try:
                entries = api.fetch(video_id, languages=languages)  # type: ignore[call-arg]
            except TypeError:
                entries = api.fetch(video_id)  # type: ignore[call-arg]

    lines: list[str] = []
    iterable = entries if isinstance(entries, list) else list(entries or [])
    for item in iterable:
        if isinstance(item, dict):
            text = str(item.get("text") or "").strip()
        else:
            text = str(getattr(item, "text", "") or "").strip()
        if text:
            lines.append(text)
    return "\n".join(lines).strip()
