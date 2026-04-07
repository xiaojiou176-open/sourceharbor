from __future__ import annotations

from urllib.parse import urlencode


def build_video_probe_url(api_key: str, *, video_id: str = "dQw4w9WgXcQ") -> str:
    query = urlencode(
        {
            "part": "id",
            "id": video_id,
            "maxResults": 1,
            "key": api_key,
        }
    )
    return f"https://www.googleapis.com/youtube/v3/videos?{query}"
