from __future__ import annotations

from integrations.providers.bilibili_evidence import (
    build_bilibili_rich_metadata,
    parse_bilibili_danmaku_xml,
)


def test_parse_bilibili_danmaku_xml_extracts_entries_and_limits_output() -> None:
    payload = parse_bilibili_danmaku_xml(
        "<i>"
        '<d p="1.5,1,25,16777215,1710000000,0,abc,1">hello</d>'
        '<d p="2.0,1,25,16777215,1710000001,0,def,2">world</d>'
        "</i>",
        limit=1,
    )

    assert payload["status"] == "available"
    assert payload["entry_count"] == 1
    assert payload["total_count"] == 2
    assert payload["sampled"] is True
    assert payload["entries"][0]["content"] == "hello"
    assert payload["entries"][0]["progress_s"] == 1.5


def test_build_bilibili_rich_metadata_extracts_creator_stats_and_pages() -> None:
    payload = build_bilibili_rich_metadata(
        {
            "aid": 123,
            "bvid": "BV1demo",
            "cid": 99,
            "tid": 7,
            "tname": "Science",
            "pic": "https://img.example/thumb.jpg",
            "owner": {"mid": 456, "name": "demo-up", "face": "https://img.example/avatar.jpg"},
            "stat": {"view": 9, "like": 3, "reply": 2, "danmaku": 4, "coin": 5},
            "pages": [{"cid": 99, "page": 1, "part": "Part 1", "duration": 30}],
        },
        creator_profile={
            "sign": "Archive reader",
            "level": 6,
            "official": {"title": "Science creator"},
        },
        creator_relation={"follower": 3200, "following": 12},
    )

    assert payload["uploader_mid"] == "456"
    assert payload["uploader_url"] == "https://space.bilibili.com/456"
    assert payload["view_count"] == 9
    assert payload["comment_count"] == 2
    assert payload["category"] == "Science"
    assert payload["chapters"][0]["title"] == "Part 1"
    assert payload["site_objects"]["owner"]["name"] == "demo-up"
    assert payload["site_objects"]["stat"]["danmaku"] == 4
    assert payload["uploader_sign"] == "Archive reader"
    assert payload["uploader_follower_count"] == 3200
    assert payload["site_objects"]["creator_relation"]["follower"] == 3200
    assert payload["site_objects"]["creator_profile"]["official_title"] == "Science creator"
