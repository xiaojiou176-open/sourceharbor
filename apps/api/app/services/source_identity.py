from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, quote, urlparse


@dataclass(frozen=True)
class SourceIdentityPayload:
    creator_display_name: str | None
    creator_handle: str | None
    source_homepage_url: str | None
    avatar_url: str | None
    avatar_label: str | None
    thumbnail_url: str | None
    source_universe_label: str | None
    identity_status: str


_PLATFORM_SWATCHES: dict[str, tuple[str, str]] = {
    "youtube": ("#FF0033", "#FFF1F2"),
    "bilibili": ("#0EA5E9", "#E0F2FE"),
    "rsshub": ("#7C3AED", "#F5F3FF"),
    "generic": ("#0F766E", "#ECFEFF"),
}


def _platform_palette(platform: str) -> tuple[str, str]:
    return _PLATFORM_SWATCHES.get(platform.strip().lower(), ("#18181B", "#F4F4F5"))


def _build_initials(label: str | None) -> str:
    value = str(label or "").strip()
    if not value:
        return "SH"
    segments = [segment for segment in value.replace("-", " ").split() if segment]
    if len(segments) >= 2:
        return f"{segments[0][0]}{segments[1][0]}".upper()
    trimmed = "".join(ch for ch in value if ch.isalnum())
    return (trimmed[:2] or "SH").upper()


def _build_svg_data_url(
    *, primary_text: str, secondary_text: str, platform: str, square: bool
) -> str:
    foreground, background = _platform_palette(platform)
    radius = "24" if square else "48"
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="512" height="320" viewBox="0 0 512 320" role="img" aria-label="{primary_text}">
      <rect width="512" height="320" rx="{radius}" fill="{background}" />
      <rect x="24" y="24" width="464" height="272" rx="{radius}" fill="rgba(255,255,255,0.56)" />
      <text x="40" y="126" font-family="Arial, Helvetica, sans-serif" font-size="72" font-weight="700" fill="{foreground}">
        {secondary_text}
      </text>
      <text x="40" y="214" font-family="Arial, Helvetica, sans-serif" font-size="30" fill="#18181B">
        {primary_text[:42]}
      </text>
    </svg>
    """.strip()
    return f"data:image/svg+xml;utf8,{quote(svg)}"


def _extract_youtube_video_id(source_url: str | None) -> str | None:
    value = str(source_url or "").strip()
    if not value:
        return None
    parsed = urlparse(value)
    host = str(parsed.hostname or "").strip().lower()
    if host == "youtu.be":
        candidate = str(parsed.path or "").strip("/")
        return candidate or None
    query_id = parse_qs(parsed.query).get("v", [])
    if query_id and query_id[0].strip():
        return query_id[0].strip()
    segments = [segment for segment in str(parsed.path or "").split("/") if segment]
    if len(segments) >= 2 and segments[0] in {"shorts", "live"}:
        return segments[1].strip() or None
    return None


def build_identity_payload(
    *,
    platform: str,
    display_name: str | None,
    creator_handle: str | None = None,
    source_homepage_url: str | None = None,
    source_url: str | None = None,
    source_universe_label: str | None = None,
    identity_status: str = "derived_identity",
) -> SourceIdentityPayload:
    resolved_platform = str(platform or "").strip().lower() or "generic"
    resolved_name = str(display_name or "").strip() or None
    resolved_universe = str(source_universe_label or "").strip() or resolved_name
    initials = _build_initials(resolved_name or resolved_universe)
    avatar_url = _build_svg_data_url(
        primary_text=resolved_name or "SourceHarbor",
        secondary_text=initials,
        platform=resolved_platform,
        square=False,
    )
    thumbnail_url: str | None = None
    youtube_video_id = _extract_youtube_video_id(source_url)
    if youtube_video_id:
        thumbnail_url = f"https://i.ytimg.com/vi/{youtube_video_id}/hqdefault.jpg"
    else:
        thumbnail_url = _build_svg_data_url(
            primary_text=resolved_name or "SourceHarbor",
            secondary_text=(resolved_platform or "source").upper()[:6],
            platform=resolved_platform,
            square=True,
        )
    return SourceIdentityPayload(
        creator_display_name=resolved_name,
        creator_handle=str(creator_handle or "").strip() or None,
        source_homepage_url=str(source_homepage_url or source_url or "").strip() or None,
        avatar_url=avatar_url,
        avatar_label=initials,
        thumbnail_url=thumbnail_url,
        source_universe_label=resolved_universe,
        identity_status=identity_status,
    )
