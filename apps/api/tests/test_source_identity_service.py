from __future__ import annotations

from apps.api.app.services.source_identity import build_identity_payload


def test_build_identity_payload_defaults_initials_and_supports_youtu_be_urls() -> None:
    payload = build_identity_payload(
        platform="youtube",
        display_name=None,
        source_url="https://youtu.be/demo123",
    )

    assert payload.avatar_label == "SH"
    assert payload.thumbnail_url == "https://i.ytimg.com/vi/demo123/hqdefault.jpg"
    assert payload.source_homepage_url == "https://youtu.be/demo123"


def test_build_identity_payload_extracts_thumbnail_from_youtube_shorts_urls() -> None:
    payload = build_identity_payload(
        platform="youtube",
        display_name="Clips Desk",
        source_url="https://www.youtube.com/shorts/short123",
    )

    assert payload.avatar_label == "CD"
    assert payload.thumbnail_url == "https://i.ytimg.com/vi/short123/hqdefault.jpg"
