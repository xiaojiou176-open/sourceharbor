from __future__ import annotations

import base64
import json
import threading
import uuid
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from support.runtime_utils import utc_now, wait_http_ok

PING_IMAGE_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9sYfA8kAAAAASUVORK5CYII="
)
_HEALTH_DELAY_WAIT = threading.Event()

MOCK_JOB_ID = "00000000-0000-4000-8000-000000000001"
MOCK_VIDEO_ID = "00000000-0000-4000-8000-000000000002"
MOCK_VIDEO_DB_ID = "00000000-0000-4000-8000-000000000003"
MOCK_DELIVERY_ID = "00000000-0000-4000-8000-000000000004"
MOCK_WATCHLIST_ID = "wl-1"
MOCK_PREVIOUS_JOB_ID = "00000000-0000-4000-8000-000000000005"
MOCK_RSS_JOB_ID = "00000000-0000-4000-8000-000000000006"
SUBSCRIPTION_NAMESPACE = uuid.UUID("00000000-0000-4000-8000-0000000000aa")


def _is_valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except (ValueError, TypeError):
        return False


def _subscription_uuid(index: int) -> str:
    return str(uuid.uuid5(SUBSCRIPTION_NAMESPACE, f"mock-subscription-{index}"))


def _safe_origin_header(value: str | None) -> str | None:
    if not value:
        return None
    if any(ch in value for ch in ("\r", "\n")):
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


@dataclass
class MockApiState:
    lock: threading.Lock = field(default_factory=threading.Lock)
    condition: threading.Condition = field(init=False)
    subscriptions: list[dict[str, Any]] = field(default_factory=list)
    notification_config: dict[str, Any] = field(default_factory=dict)
    calls: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    job_id: str = MOCK_JOB_ID
    health_status: int = int(HTTPStatus.OK)
    health_delay_seconds: float = 0.0
    artifact_frame_files: list[str] = field(default_factory=list)
    videos: list[dict[str, Any]] = field(default_factory=list)
    feed_items: list[dict[str, Any]] = field(default_factory=list)
    feed_has_more: bool = False
    feed_next_cursor: str | None = None
    feed_error_status: int | None = None

    def __post_init__(self) -> None:
        self.condition = threading.Condition(self.lock)
        self.reset()

    def reset(self) -> None:
        with self.condition:
            now = utc_now()
            self.subscriptions = []
            self.notification_config = {
                "enabled": True,
                "to_email": "ops@example.com",
                "daily_digest_enabled": False,
                "daily_digest_hour_utc": None,
                "failure_alert_enabled": True,
                "category_rules": {},
                "created_at": now,
                "updated_at": now,
            }
            self.calls = {
                "http": [],
                "poll_ingest": [],
                "process_video": [],
                "upsert_subscription": [],
                "batch_update_subscription_category": [],
                "delete_subscription": [],
                "update_notification_config": [],
                "send_notification_test": [],
                "get_job": [],
                "get_artifact_markdown": [],
            }
            self.health_status = int(HTTPStatus.OK)
            self.health_delay_seconds = 0.0
            self.artifact_frame_files = [
                "screenshots/frame_0001.png",
                "screenshots/frame_0002.webp",
            ]
            self.videos = [
                {
                    "id": MOCK_VIDEO_ID,
                    "platform": "youtube",
                    "video_uid": "yt-e2e-001",
                    "source_url": "https://youtube.com/watch?v=e2e001",
                    "title": "E2E Demo",
                    "published_at": now,
                    "first_seen_at": now,
                    "last_seen_at": now,
                    "status": "running",
                    "last_job_id": self.job_id,
                }
            ]
            self.feed_items = []
            self.feed_has_more = False
            self.feed_next_cursor = None
            self.feed_error_status = None
            self.condition.notify_all()

    def record(self, key: str, payload: dict[str, Any]) -> None:
        with self.condition:
            self.calls[key].append(payload)
            self.condition.notify_all()

    def call_count(self, key: str) -> int:
        with self.lock:
            return len(self.calls[key])

    def last_call(self, key: str) -> dict[str, Any]:
        with self.lock:
            return dict(self.calls[key][-1])

    def current_job(self) -> dict[str, Any]:
        now = utc_now()
        return {
            "id": self.job_id,
            "video_id": MOCK_VIDEO_ID,
            "kind": "video_digest_v1",
            "status": "succeeded",
            "idempotency_key": "idem-e2e",
            "error_message": None,
            "artifact_digest_md": "artifacts/digest.md",
            "artifact_root": f"artifacts/{self.job_id}",
            "created_at": now,
            "updated_at": now,
            "step_summary": [
                {
                    "name": "fetch_transcript",
                    "status": "succeeded",
                    "attempt": 1,
                    "started_at": now,
                    "finished_at": now,
                    "error": None,
                },
                {
                    "name": "generate_markdown",
                    "status": "succeeded",
                    "attempt": 1,
                    "started_at": now,
                    "finished_at": now,
                    "error": None,
                },
            ],
            "steps": [],
            "degradations": [],
            "pipeline_final_status": "succeeded",
            "artifacts_index": {
                "digest_markdown": "artifacts/digest.md",
                "shots_zip": "artifacts/screenshots.zip",
            },
            "mode": "text_only",
        }

    def artifact_payload(self) -> dict[str, Any]:
        with self.lock:
            frame_files = list(self.artifact_frame_files)
        return {
            "markdown": "# Digest Summary\n\n- Key finding A\n- Key finding B\n",
            "meta": {
                "frame_files": frame_files,
                "job": {"id": self.job_id},
            },
        }


@dataclass(frozen=True)
class MockApiServer:
    base_url: str
    state: MockApiState


@dataclass(frozen=True)
class RunningMockServer:
    server: ThreadingHTTPServer
    thread: threading.Thread
    api_server: MockApiServer


def _mock_handler(state: MockApiState) -> type[BaseHTTPRequestHandler]:
    class MockHandler(BaseHTTPRequestHandler):
        server_version = "MockVDAPI/1.0"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _set_cors_headers(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")

        def _send_json(self, status: int, payload: Any) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self._set_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_text(
            self, status: int, body: str, content_type: str = "text/plain; charset=utf-8"
        ) -> None:
            raw = body.encode("utf-8")
            self.send_response(status)
            self._set_cors_headers()
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _send_binary(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self._set_cors_headers()
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_no_content(self) -> None:
            self.send_response(HTTPStatus.NO_CONTENT)
            self._set_cors_headers()
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _briefing_page_payload(self) -> dict[str, Any]:
            return {
                "context": {
                    "watchlist_id": MOCK_WATCHLIST_ID,
                    "watchlist_name": "Retry policy",
                    "story_id": None,
                    "selected_story_id": "story-1",
                    "story_headline": "Retries moved from optional advice to default posture",
                    "topic_key": "retry-policy",
                    "topic_label": "Retry policy",
                    "selection_basis": "suggested_story_id",
                    "question_seed": "Retries moved from optional advice to default posture",
                },
                "briefing": {
                    "watchlist": {
                        "id": MOCK_WATCHLIST_ID,
                        "name": "Retry policy",
                        "matcher_type": "topic_key",
                        "matcher_value": "retry-policy",
                        "delivery_channel": "dashboard",
                        "enabled": True,
                        "created_at": "2026-03-31T10:00:00Z",
                        "updated_at": "2026-04-01T10:00:00Z",
                    },
                    "summary": {
                        "overview": (
                            "Retry policy now reads like one shared story across YouTube, "
                            "Bilibili, and RSS sources."
                        ),
                        "source_count": 3,
                        "run_count": 3,
                        "story_count": 1,
                        "matched_cards": 5,
                        "primary_story_headline": "Retries moved from optional advice to default posture",
                        "signals": [
                            {
                                "story_key": "topic:retry-policy",
                                "headline": "Retry policy is stabilizing into the baseline path",
                                "matched_card_count": 5,
                                "latest_run_job_id": MOCK_RSS_JOB_ID,
                                "reason": "The newest runs repeat the same retry baseline across source types.",
                            }
                        ],
                    },
                    "differences": {
                        "latest_job_id": MOCK_RSS_JOB_ID,
                        "previous_job_id": MOCK_PREVIOUS_JOB_ID,
                        "added_topics": ["retry-policy"],
                        "removed_topics": [],
                        "added_claim_kinds": ["recommendation"],
                        "removed_claim_kinds": [],
                        "new_story_keys": ["topic:retry-policy"],
                        "removed_story_keys": [],
                        "compare": {
                            "job_id": MOCK_RSS_JOB_ID,
                            "has_previous": True,
                            "previous_job_id": MOCK_PREVIOUS_JOB_ID,
                            "changed": True,
                            "added_lines": 7,
                            "removed_lines": 2,
                            "diff_excerpt": "Retry handling moved into the default guidance instead of a footnote.",
                            "compare_route": f"/jobs?job_id={MOCK_RSS_JOB_ID}&via=briefing-compare",
                        },
                    },
                    "evidence": {
                        "suggested_story_id": "story-1",
                        "stories": [
                            {
                                "story_id": "story-1",
                                "story_key": "topic:retry-policy",
                                "headline": "Retries moved from optional advice to default posture",
                                "topic_key": "retry-policy",
                                "topic_label": "Retry policy",
                                "source_count": 3,
                                "run_count": 3,
                                "matched_card_count": 5,
                                "platforms": ["youtube", "bilibili", "rss"],
                                "claim_kinds": ["recommendation"],
                                "source_urls": ["https://example.com/retry-policy"],
                                "latest_run_job_id": MOCK_RSS_JOB_ID,
                                "evidence_cards": [
                                    {
                                        "card_id": "card-briefing-1",
                                        "job_id": MOCK_JOB_ID,
                                        "video_id": MOCK_VIDEO_ID,
                                        "platform": "youtube",
                                        "video_title": "AI Weekly",
                                        "source_url": "https://example.com/retry-policy",
                                        "created_at": "2026-04-01T10:00:00Z",
                                        "card_type": "claim",
                                        "card_title": "Retry baseline became explicit",
                                        "card_body": "Operators should treat retries as the default safe path.",
                                        "source_section": "digest",
                                        "topic_key": "retry-policy",
                                        "topic_label": "Retry policy",
                                        "claim_kind": "recommendation",
                                    }
                                ],
                                "routes": {
                                    "watchlist_trend": f"/trends?watchlist_id={MOCK_WATCHLIST_ID}",
                                    "briefing": f"/briefings?watchlist_id={MOCK_WATCHLIST_ID}&story_id=story-1&via=briefing-story",
                                    "ask": f"/ask?watchlist_id={MOCK_WATCHLIST_ID}&question=Retries+moved+from+optional+advice+to+default+posture&story_id=story-1&topic_key=retry-policy&via=briefing-story",
                                    "job_compare": f"/jobs?job_id={MOCK_RSS_JOB_ID}&via=briefing-compare",
                                    "job_bundle": f"/api/v1/jobs/{MOCK_RSS_JOB_ID}/bundle",
                                    "job_knowledge_cards": f"/knowledge?job_id={MOCK_RSS_JOB_ID}",
                                },
                            }
                        ],
                        "featured_runs": [
                            {
                                "job_id": MOCK_RSS_JOB_ID,
                                "video_id": MOCK_VIDEO_ID,
                                "platform": "rss",
                                "title": "RSS Digest",
                                "source_url": "https://example.com/retry-policy",
                                "created_at": "2026-04-01T11:00:00Z",
                                "matched_card_count": 2,
                                "routes": {
                                    "watchlist_trend": f"/trends?watchlist_id={MOCK_WATCHLIST_ID}",
                                    "briefing": f"/briefings?watchlist_id={MOCK_WATCHLIST_ID}&via=briefing-run",
                                    "ask": f"/ask?watchlist_id={MOCK_WATCHLIST_ID}&via=briefing-run",
                                    "job_compare": f"/jobs?job_id={MOCK_RSS_JOB_ID}&via=briefing-run",
                                    "job_bundle": f"/api/v1/jobs/{MOCK_RSS_JOB_ID}/bundle",
                                    "job_knowledge_cards": f"/knowledge?job_id={MOCK_RSS_JOB_ID}",
                                },
                            }
                        ],
                    },
                    "selection": {
                        "selected_story_id": "story-1",
                        "selection_basis": "suggested_story_id",
                        "story": None,
                    },
                },
                "selected_story": {
                    "story_id": "story-1",
                    "story_key": "topic:retry-policy",
                    "headline": "Retries moved from optional advice to default posture",
                    "topic_key": "retry-policy",
                    "topic_label": "Retry policy",
                    "source_count": 3,
                    "run_count": 3,
                    "matched_card_count": 5,
                    "platforms": ["youtube", "bilibili", "rss"],
                    "claim_kinds": ["recommendation"],
                    "source_urls": ["https://example.com/retry-policy"],
                    "latest_run_job_id": MOCK_RSS_JOB_ID,
                    "evidence_cards": [
                        {
                            "card_id": "card-briefing-1",
                            "job_id": MOCK_JOB_ID,
                            "video_id": MOCK_VIDEO_ID,
                            "platform": "youtube",
                            "video_title": "AI Weekly",
                            "source_url": "https://example.com/retry-policy",
                            "created_at": "2026-04-01T10:00:00Z",
                            "card_type": "claim",
                            "card_title": "Retry baseline became explicit",
                            "card_body": "Operators should treat retries as the default safe path.",
                            "source_section": "digest",
                            "topic_key": "retry-policy",
                            "topic_label": "Retry policy",
                            "claim_kind": "recommendation",
                        }
                    ],
                    "routes": {
                        "watchlist_trend": f"/trends?watchlist_id={MOCK_WATCHLIST_ID}",
                        "briefing": f"/briefings?watchlist_id={MOCK_WATCHLIST_ID}&story_id=story-1&via=briefing-story",
                        "ask": f"/ask?watchlist_id={MOCK_WATCHLIST_ID}&question=Retries+moved+from+optional+advice+to+default+posture&story_id=story-1&topic_key=retry-policy&via=briefing-story",
                        "job_compare": f"/jobs?job_id={MOCK_RSS_JOB_ID}&via=briefing-compare",
                        "job_bundle": f"/api/v1/jobs/{MOCK_RSS_JOB_ID}/bundle",
                        "job_knowledge_cards": f"/knowledge?job_id={MOCK_RSS_JOB_ID}",
                    },
                },
                "ask_route": f"/ask?watchlist_id={MOCK_WATCHLIST_ID}&question=Retries+moved+from+optional+advice+to+default+posture&story_id=story-1&topic_key=retry-policy&via=briefing-story",
                "compare_route": f"/jobs?job_id={MOCK_RSS_JOB_ID}&via=briefing-compare",
            }

        def do_OPTIONS(self) -> None:
            parsed = urlparse(self.path)
            self._record_http(
                method="OPTIONS",
                path=parsed.path,
                query=parsed.query,
                status=int(HTTPStatus.NO_CONTENT),
            )
            self._send_no_content()

        def _read_json(self) -> dict[str, Any]:
            raw_size = self.headers.get("Content-Length", "0")
            size = int(raw_size) if raw_size.isdigit() else 0
            if size <= 0:
                return {}
            raw = self.rfile.read(size).decode("utf-8")
            payload = json.loads(raw)
            return payload if isinstance(payload, dict) else {}

        def _record_http(
            self,
            *,
            method: str,
            path: str,
            query: str,
            status: int,
            payload: dict[str, Any] | None = None,
        ) -> None:
            state.record(
                "http",
                {
                    "method": method,
                    "path": path,
                    "query": query,
                    "status": status,
                    "payload": payload,
                },
            )

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)

            if path == "/api/v1/watchlists":
                payload = [
                    {
                        "id": MOCK_WATCHLIST_ID,
                        "name": "Retry policy",
                        "matcher_type": "topic_key",
                        "matcher_value": "retry-policy",
                        "delivery_channel": "dashboard",
                        "enabled": True,
                        "created_at": "2026-03-31T10:00:00Z",
                        "updated_at": "2026-04-01T10:00:00Z",
                    }
                ]
                self._record_http(
                    method="GET",
                    path=path,
                    query=parsed.query,
                    status=int(HTTPStatus.OK),
                )
                self._send_json(HTTPStatus.OK, payload)
                return

            if path in {
                f"/api/v1/watchlists/{MOCK_WATCHLIST_ID}/briefing",
                f"/api/v1/watchlists/{MOCK_WATCHLIST_ID}/briefing/page",
            }:
                briefing_payload = {
                    "watchlist": {
                        "id": MOCK_WATCHLIST_ID,
                        "name": "Retry policy",
                        "matcher_type": "topic_key",
                        "matcher_value": "retry-policy",
                        "delivery_channel": "dashboard",
                        "enabled": True,
                        "created_at": "2026-03-31T10:00:00Z",
                        "updated_at": "2026-04-01T10:00:00Z",
                    },
                    "summary": {
                        "overview": (
                            "Retry policy now reads like one shared story across YouTube, "
                            "Bilibili, and RSS sources."
                        ),
                        "source_count": 3,
                        "run_count": 3,
                        "story_count": 1,
                        "matched_cards": 5,
                        "primary_story_headline": "Retries moved from optional advice to default posture",
                        "signals": [
                            {
                                "story_key": "topic:retry-policy",
                                "headline": "Retry policy is stabilizing into the baseline path",
                                "matched_card_count": 5,
                                "latest_run_job_id": MOCK_RSS_JOB_ID,
                                "reason": "The newest runs repeat the same retry baseline across source types.",
                            }
                        ],
                    },
                    "differences": {
                        "latest_job_id": MOCK_RSS_JOB_ID,
                        "previous_job_id": MOCK_PREVIOUS_JOB_ID,
                        "added_topics": ["retry-policy"],
                        "removed_topics": [],
                        "added_claim_kinds": ["recommendation"],
                        "removed_claim_kinds": [],
                        "new_story_keys": ["topic:retry-policy"],
                        "removed_story_keys": [],
                        "compare": {
                            "job_id": MOCK_RSS_JOB_ID,
                            "has_previous": True,
                            "previous_job_id": MOCK_PREVIOUS_JOB_ID,
                            "changed": True,
                            "added_lines": 7,
                            "removed_lines": 2,
                            "diff_excerpt": "Retry handling moved into the default guidance instead of a footnote.",
                            "compare_route": f"/jobs?job_id={MOCK_RSS_JOB_ID}&via=briefing-compare",
                        },
                    },
                    "evidence": {
                        "suggested_story_id": "story-1",
                        "stories": [
                            {
                                "story_id": "story-1",
                                "story_key": "topic:retry-policy",
                                "headline": "Retries moved from optional advice to default posture",
                                "topic_key": "retry-policy",
                                "topic_label": "Retry policy",
                                "source_count": 3,
                                "run_count": 3,
                                "matched_card_count": 5,
                                "platforms": ["youtube", "bilibili", "rss"],
                                "claim_kinds": ["recommendation"],
                                "source_urls": ["https://example.com/retry-policy"],
                                "latest_run_job_id": MOCK_RSS_JOB_ID,
                                "evidence_cards": [
                                    {
                                        "card_id": "card-briefing-1",
                                        "job_id": MOCK_JOB_ID,
                                        "video_id": MOCK_VIDEO_ID,
                                        "platform": "youtube",
                                        "video_title": "AI Weekly",
                                        "source_url": "https://example.com/retry-policy",
                                        "created_at": "2026-04-01T10:00:00Z",
                                        "card_type": "claim",
                                        "card_title": "Retry baseline became explicit",
                                        "card_body": "Operators should treat retries as the default safe path.",
                                        "source_section": "digest",
                                        "topic_key": "retry-policy",
                                        "topic_label": "Retry policy",
                                        "claim_kind": "recommendation",
                                    }
                                ],
                                "routes": {
                                    "watchlist_trend": f"/trends?watchlist_id={MOCK_WATCHLIST_ID}",
                                    "briefing": f"/briefings?watchlist_id={MOCK_WATCHLIST_ID}&story_id=story-1&via=briefing-story",
                                    "ask": f"/ask?watchlist_id={MOCK_WATCHLIST_ID}&story_id=story-1&topic_key=retry-policy&via=briefing-story",
                                    "job_compare": f"/jobs?job_id={MOCK_RSS_JOB_ID}&via=briefing-compare",
                                    "job_bundle": f"/api/v1/jobs/{MOCK_RSS_JOB_ID}/bundle",
                                    "job_knowledge_cards": f"/knowledge?job_id={MOCK_RSS_JOB_ID}",
                                },
                            }
                        ],
                        "featured_runs": [
                            {
                                "job_id": MOCK_RSS_JOB_ID,
                                "video_id": MOCK_VIDEO_ID,
                                "platform": "rss",
                                "title": "RSS Digest",
                                "source_url": "https://example.com/retry-policy",
                                "created_at": "2026-04-01T11:00:00Z",
                                "matched_card_count": 2,
                                "routes": {
                                    "watchlist_trend": f"/trends?watchlist_id={MOCK_WATCHLIST_ID}",
                                    "briefing": f"/briefings?watchlist_id={MOCK_WATCHLIST_ID}&via=briefing-run",
                                    "ask": f"/ask?watchlist_id={MOCK_WATCHLIST_ID}&via=briefing-run",
                                    "job_compare": f"/jobs?job_id={MOCK_RSS_JOB_ID}&via=briefing-run",
                                    "job_bundle": f"/api/v1/jobs/{MOCK_RSS_JOB_ID}/bundle",
                                    "job_knowledge_cards": f"/knowledge?job_id={MOCK_RSS_JOB_ID}",
                                },
                            }
                        ],
                    },
                    "selection": {
                        "selected_story_id": "story-1",
                        "selection_basis": "suggested_story_id",
                        "story": None,
                    },
                }
                if path == f"/api/v1/watchlists/{MOCK_WATCHLIST_ID}/briefing/page":
                    payload = self._briefing_page_payload()
                    if parse_qs(parsed.query).get("story_id", [""])[0].strip():
                        payload["context"]["story_id"] = "story-1"
                        payload["context"]["selection_basis"] = "requested_story_id"
                else:
                    payload = briefing_payload
                self._record_http(
                    method="GET",
                    path=path,
                    query=parsed.query,
                    status=int(HTTPStatus.OK),
                )
                self._send_json(HTTPStatus.OK, payload)
                return

            if path == "/api/v1/subscriptions/templates":
                payload = {
                    "support_tiers": [
                        {
                            "id": "strong_supported",
                            "label": "Strong support",
                            "description": "Purpose-built video subscriptions.",
                            "content_profile": "video",
                            "supports_video_pipeline": True,
                            "verification_status": "verified_for_youtube_bilibili_only",
                        },
                        {
                            "id": "generic_supported",
                            "label": "Generic support",
                            "description": "Generic RSSHub/RSS substrate without route-by-route verification.",
                            "content_profile": "article",
                            "supports_video_pipeline": False,
                            "verification_status": "substrate_ready_not_route_by_route_verified",
                        },
                    ],
                    "templates": [
                        {
                            "id": "youtube_channel",
                            "label": "YouTube channel",
                            "description": "Strong preset for recurring YouTube intake when you already know the channel ID, handle, or landing URL.",
                            "support_tier": "strong_supported",
                            "platform": "youtube",
                            "source_type": "youtube_channel_id",
                            "adapter_type": "rsshub_route",
                            "content_profile": "video",
                            "category": "creator",
                            "source_value_placeholder": "UCxxxxxxxxxxxxxxxxxxxxxx",
                            "source_url_placeholder": "https://www.youtube.com/@channel",
                            "rsshub_route_hint": "/youtube/channel/{channel_id}",
                            "source_url_required": False,
                            "supports_video_pipeline": True,
                            "fill_now": "Start with the channel ID or a stable channel URL, then keep the RSSHub route aligned.",
                            "proof_boundary": "YouTube is a strong path today, but route health still matters if you depend on RSSHub for intake.",
                            "evidence_note": "Strongly supported video lane.",
                        },
                        {
                            "id": "bilibili_user_video",
                            "label": "Bilibili uploader",
                            "description": "Strong preset for Bilibili creators when the UID is known and you want a repeatable creator feed.",
                            "support_tier": "strong_supported",
                            "platform": "bilibili",
                            "source_type": "bilibili_uid",
                            "adapter_type": "rsshub_route",
                            "content_profile": "video",
                            "category": "creator",
                            "source_value_placeholder": "12345678",
                            "source_url_placeholder": "https://space.bilibili.com/12345678",
                            "rsshub_route_hint": "/bilibili/user/video/{uid}",
                            "source_url_required": False,
                            "supports_video_pipeline": True,
                            "fill_now": "Use the creator UID as the primary identifier and keep the companion RSSHub route ready.",
                            "proof_boundary": "Bilibili creator intake is productized, but route breakage or source-side changes still need monitoring.",
                            "evidence_note": "Strongly supported video lane.",
                        },
                        {
                            "id": "generic_rsshub_route",
                            "label": "Generic RSSHub route",
                            "description": "General preset for wider source coverage when RSSHub can normalize a route into a usable feed.",
                            "support_tier": "generic_supported",
                            "platform": "rsshub",
                            "source_type": "rsshub_route",
                            "adapter_type": "rsshub_route",
                            "content_profile": "article",
                            "category": "misc",
                            "source_value_placeholder": "/namespace/path",
                            "source_url_placeholder": "https://example.com/source",
                            "rsshub_route_hint": "/namespace/path",
                            "source_url_required": False,
                            "supports_video_pipeline": False,
                            "fill_now": "Bring the exact RSSHub route you want SourceHarbor to poll, then add a canonical source URL only if it helps operators recognize the feed.",
                            "proof_boundary": "Do not assume every RSSHub route is equally solid. Treat each route as proven only after it survives real runs.",
                            "evidence_note": "Substrate-ready route lane.",
                        },
                        {
                            "id": "generic_rss_feed",
                            "label": "Generic RSS or Atom feed",
                            "description": "General preset for any source that already exposes a clean RSS or Atom feed without a platform-specific shortcut.",
                            "support_tier": "generic_supported",
                            "platform": "generic",
                            "source_type": "url",
                            "adapter_type": "rss_generic",
                            "content_profile": "article",
                            "category": "misc",
                            "source_value_placeholder": "https://example.com/feed.xml",
                            "source_url_placeholder": "https://example.com/feed.xml",
                            "rsshub_route_hint": "https://example.com/feed.xml",
                            "source_url_required": False,
                            "supports_video_pipeline": False,
                            "fill_now": "Paste the exact RSS or Atom feed URL into Source value. Leave Source URL empty unless you want to store the same feed URL explicitly.",
                            "proof_boundary": "Feed quality varies a lot. If the feed is noisy or incomplete, the intake surface should stay honest about that.",
                            "evidence_note": "Use Source value for the exact feed URL; Source URL stays optional unless you want to store the same feed URL explicitly.",
                        },
                    ],
                }
                self._record_http(
                    method="GET",
                    path=path,
                    query=parsed.query,
                    status=int(HTTPStatus.OK),
                )
                self._send_json(HTTPStatus.OK, payload)
                return

            if path == "/api/v1/subscriptions/vendor-signals":
                payload = {
                    "signal_layers": [
                        {
                            "id": "confirmed",
                            "label": "Confirmed truth",
                            "description": "Official docs, changelog, release notes, status, and blog updates.",
                        },
                        {
                            "id": "observation",
                            "label": "Observation layer",
                            "description": "Fast signals such as official X posts that need confirmation before promotion.",
                        },
                    ],
                    "vendors": [
                        {
                            "id": "openai",
                            "label": "OpenAI",
                            "description": "Track official model, API, and product changes before downstream summaries drift.",
                            "official_first_move": "Start with the API changelog and status before repeating a claim.",
                            "x_policy_summary": "Treat OpenAI on X as a fast signal only until docs, status, or a longer-form post corroborates it.",
                            "starter_watchlist": {
                                "name": "OpenAI signals",
                                "matcher_type": "source_match",
                                "matcher_value": "openai",
                                "delivery_channel": "dashboard",
                                "briefing_goal": "What changed across official OpenAI channels this week?",
                            },
                            "confirmation_chain": [
                                {
                                    "id": "fast-signal",
                                    "label": "Fast signal",
                                    "description": "Use official X as observation only.",
                                },
                                {
                                    "id": "confirm",
                                    "label": "Confirm",
                                    "description": "Promote only after changelog, status, or release notes corroborate it.",
                                },
                            ],
                            "channels": [
                                {
                                    "id": "openai-api-changelog",
                                    "label": "API changelog",
                                    "url": "https://platform.openai.com/docs/changelog",
                                    "channel_kind": "changelog",
                                    "signal_layer": "confirmed",
                                    "why_it_matters": "Model and API contract truth lands here first.",
                                    "ingest_mode": "manual_url",
                                    "feed_url": None,
                                },
                                {
                                    "id": "openai-status",
                                    "label": "OpenAI status",
                                    "url": "https://status.openai.com/",
                                    "channel_kind": "status",
                                    "signal_layer": "confirmed",
                                    "why_it_matters": "Incident truth without guesswork.",
                                    "ingest_mode": "manual_url",
                                    "feed_url": None,
                                },
                                {
                                    "id": "openai-x",
                                    "label": "OpenAI on X",
                                    "url": "https://x.com/OpenAI",
                                    "channel_kind": "x_account",
                                    "signal_layer": "observation",
                                    "why_it_matters": "Fast hints and screenshots, not final truth.",
                                    "ingest_mode": "link_only",
                                    "feed_url": None,
                                },
                            ],
                        }
                    ],
                }
                self._record_http(
                    method="GET",
                    path=path,
                    query=parsed.query,
                    status=int(HTTPStatus.OK),
                )
                self._send_json(HTTPStatus.OK, payload)
                return

            if path == "/api/v1/subscriptions":
                with state.lock:
                    subscriptions = list(state.subscriptions)
                self._record_http(
                    method="GET",
                    path=path,
                    query=parsed.query,
                    status=int(HTTPStatus.OK),
                )
                self._send_json(HTTPStatus.OK, subscriptions)
                return

            if path == "/healthz":
                with state.lock:
                    delay_seconds = state.health_delay_seconds
                    status_code = state.health_status
                if delay_seconds > 0:
                    _HEALTH_DELAY_WAIT.wait(delay_seconds)
                status = HTTPStatus(status_code)
                self._record_http(
                    method="GET",
                    path=path,
                    query=parsed.query,
                    status=int(status),
                )
                self._send_json(status, {"status": "ok" if status == HTTPStatus.OK else "degraded"})
                return

            if path == "/api/v1/videos":
                with state.lock:
                    videos = list(state.videos)
                self._record_http(
                    method="GET",
                    path=path,
                    query=parsed.query,
                    status=int(HTTPStatus.OK),
                )
                self._send_json(HTTPStatus.OK, videos)
                return

            if path == "/api/v1/feed/digests":
                with state.lock:
                    feed_error_status = state.feed_error_status
                    feed_items = list(state.feed_items)
                    feed_has_more = state.feed_has_more
                    feed_next_cursor = state.feed_next_cursor
                if feed_error_status is not None:
                    status = HTTPStatus(feed_error_status)
                    self._record_http(
                        method="GET",
                        path=path,
                        query=parsed.query,
                        status=int(status),
                    )
                    self._send_json(status, {"detail": "mock feed failure"})
                    return
                self._record_http(
                    method="GET",
                    path=path,
                    query=parsed.query,
                    status=int(HTTPStatus.OK),
                )
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "items": feed_items,
                        "has_more": feed_has_more,
                        "next_cursor": feed_next_cursor,
                    },
                )
                return

            if path.startswith("/api/v1/jobs/"):
                requested_job_id = path.rsplit("/", 1)[-1]
                if not _is_valid_uuid(requested_job_id):
                    self._record_http(
                        method="GET",
                        path=path,
                        query=parsed.query,
                        status=int(HTTPStatus.UNPROCESSABLE_ENTITY),
                    )
                    self._send_json(
                        HTTPStatus.UNPROCESSABLE_ENTITY, {"detail": "job_id must be a valid UUID"}
                    )
                    return
                state.record("get_job", {"job_id": requested_job_id})
                if requested_job_id != state.job_id:
                    self._record_http(
                        method="GET",
                        path=path,
                        query=parsed.query,
                        status=int(HTTPStatus.NOT_FOUND),
                    )
                    self._send_json(HTTPStatus.NOT_FOUND, {"detail": "job not found"})
                    return
                self._record_http(
                    method="GET",
                    path=path,
                    query=parsed.query,
                    status=int(HTTPStatus.OK),
                )
                self._send_json(HTTPStatus.OK, state.current_job())
                return

            if path == "/api/v1/artifacts/markdown":
                job_id = query.get("job_id", [""])[0]
                video_url = query.get("video_url", [""])[0]
                if not job_id and not video_url:
                    self._record_http(
                        method="GET",
                        path=path,
                        query=parsed.query,
                        status=int(HTTPStatus.BAD_REQUEST),
                    )
                    self._send_json(
                        HTTPStatus.BAD_REQUEST, {"detail": "either job_id or video_url is required"}
                    )
                    return
                if job_id and not _is_valid_uuid(job_id):
                    self._record_http(
                        method="GET",
                        path=path,
                        query=parsed.query,
                        status=int(HTTPStatus.UNPROCESSABLE_ENTITY),
                    )
                    self._send_json(
                        HTTPStatus.UNPROCESSABLE_ENTITY, {"detail": "job_id must be a valid UUID"}
                    )
                    return
                state.record(
                    "get_artifact_markdown",
                    {
                        "job_id": job_id,
                        "video_url": video_url,
                        "include_meta": query.get("include_meta", [""])[0],
                    },
                )
                include_meta = query.get("include_meta", ["false"])[0].lower() == "true"
                payload = state.artifact_payload()
                if include_meta:
                    self._record_http(
                        method="GET",
                        path=path,
                        query=parsed.query,
                        status=int(HTTPStatus.OK),
                    )
                    self._send_json(HTTPStatus.OK, payload)
                    return
                self._record_http(
                    method="GET",
                    path=path,
                    query=parsed.query,
                    status=int(HTTPStatus.OK),
                )
                self._send_text(HTTPStatus.OK, payload["markdown"], "text/markdown; charset=utf-8")
                return

            if path == "/api/v1/artifacts/assets":
                job_id = query.get("job_id", [""])[0]
                path_param = query.get("path", [""])[0]
                if not job_id or not path_param:
                    self._record_http(
                        method="GET",
                        path=path,
                        query=parsed.query,
                        status=int(HTTPStatus.UNPROCESSABLE_ENTITY),
                    )
                    self._send_json(
                        HTTPStatus.UNPROCESSABLE_ENTITY, {"detail": "job_id and path are required"}
                    )
                    return
                if not _is_valid_uuid(job_id):
                    self._record_http(
                        method="GET",
                        path=path,
                        query=parsed.query,
                        status=int(HTTPStatus.UNPROCESSABLE_ENTITY),
                    )
                    self._send_json(
                        HTTPStatus.UNPROCESSABLE_ENTITY, {"detail": "job_id must be a valid UUID"}
                    )
                    return
                if job_id != state.job_id:
                    self._record_http(
                        method="GET",
                        path=path,
                        query=parsed.query,
                        status=int(HTTPStatus.NOT_FOUND),
                    )
                    self._send_json(HTTPStatus.NOT_FOUND, {"detail": "artifact asset not found"})
                    return
                path_param = path_param.lower()
                if path_param.endswith(".webp"):
                    self._record_http(
                        method="GET",
                        path=path,
                        query=parsed.query,
                        status=int(HTTPStatus.OK),
                    )
                    self._send_binary(HTTPStatus.OK, PING_IMAGE_BYTES, "image/webp")
                    return
                if path_param.endswith((".jpg", ".jpeg")):
                    self._record_http(
                        method="GET",
                        path=path,
                        query=parsed.query,
                        status=int(HTTPStatus.OK),
                    )
                    self._send_binary(HTTPStatus.OK, PING_IMAGE_BYTES, "image/jpeg")
                    return
                self._record_http(
                    method="GET",
                    path=path,
                    query=parsed.query,
                    status=int(HTTPStatus.OK),
                )
                self._send_binary(HTTPStatus.OK, PING_IMAGE_BYTES, "image/png")
                return

            if path == "/api/v1/notifications/config":
                with state.lock:
                    notification_config = dict(state.notification_config)
                self._record_http(
                    method="GET",
                    path=path,
                    query=parsed.query,
                    status=int(HTTPStatus.OK),
                )
                self._send_json(HTTPStatus.OK, notification_config)
                return

            self._record_http(
                method="GET",
                path=path,
                query=parsed.query,
                status=int(HTTPStatus.NOT_FOUND),
            )
            self._send_json(HTTPStatus.NOT_FOUND, {"detail": f"Unhandled GET path: {path}"})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            payload = self._read_json()

            if path == "/api/v1/retrieval/answer/page":
                query_text = str(payload.get("query", "")).strip()
                retrieval_items = (
                    [
                        {
                            "job_id": MOCK_RSS_JOB_ID,
                            "video_id": MOCK_VIDEO_ID,
                            "platform": "rss",
                            "video_uid": "rss-e2e-001",
                            "source_url": "https://example.com/retry-policy",
                            "title": "Retry policy roundup",
                            "kind": "video_digest_v1",
                            "mode": "full",
                            "source": "knowledge_cards",
                            "snippet": "Recent runs now describe retry handling as the default safe path.",
                            "score": 3.2,
                        },
                        {
                            "job_id": MOCK_JOB_ID,
                            "video_id": MOCK_VIDEO_ID,
                            "platform": "youtube",
                            "video_uid": "yt-e2e-001",
                            "source_url": "https://example.com/retry-policy",
                            "title": "AI Weekly",
                            "kind": "video_digest_v1",
                            "mode": "full",
                            "source": "digest",
                            "snippet": "Operators should treat retries as the baseline posture.",
                            "score": 2.7,
                        },
                    ]
                    if "retry" in query_text.lower()
                    else []
                )
                _briefing_payload = {
                    "watchlist": {
                        "id": MOCK_WATCHLIST_ID,
                        "name": "Retry policy",
                        "matcher_type": "topic_key",
                        "matcher_value": "retry-policy",
                        "delivery_channel": "dashboard",
                        "enabled": True,
                        "created_at": "2026-03-31T10:00:00Z",
                        "updated_at": "2026-04-01T10:00:00Z",
                    },
                    "summary": {
                        "overview": (
                            "Retry policy now reads like one shared story across YouTube, "
                            "Bilibili, and RSS sources."
                        ),
                        "source_count": 3,
                        "run_count": 3,
                        "story_count": 1,
                        "matched_cards": 5,
                        "primary_story_headline": "Retries moved from optional advice to default posture",
                        "signals": [
                            {
                                "story_key": "topic:retry-policy",
                                "headline": "Retry policy is stabilizing into the baseline path",
                                "matched_card_count": 5,
                                "latest_run_job_id": MOCK_RSS_JOB_ID,
                                "reason": "The newest runs repeat the same retry baseline across source types.",
                            }
                        ],
                    },
                    "differences": {
                        "latest_job_id": MOCK_RSS_JOB_ID,
                        "previous_job_id": MOCK_PREVIOUS_JOB_ID,
                        "added_topics": ["retry-policy"],
                        "removed_topics": [],
                        "added_claim_kinds": ["recommendation"],
                        "removed_claim_kinds": [],
                        "new_story_keys": ["topic:retry-policy"],
                        "removed_story_keys": [],
                        "compare": {
                            "job_id": MOCK_RSS_JOB_ID,
                            "has_previous": True,
                            "previous_job_id": MOCK_PREVIOUS_JOB_ID,
                            "changed": True,
                            "added_lines": 7,
                            "removed_lines": 2,
                            "diff_excerpt": "Retry handling moved into the default guidance instead of a footnote.",
                            "compare_route": f"/jobs?job_id={MOCK_RSS_JOB_ID}&via=briefing-compare",
                        },
                    },
                    "evidence": {
                        "suggested_story_id": "story-1",
                        "stories": [
                            {
                                "story_id": "story-1",
                                "story_key": "topic:retry-policy",
                                "headline": "Retries moved from optional advice to default posture",
                                "topic_key": "retry-policy",
                                "topic_label": "Retry policy",
                                "source_count": 3,
                                "run_count": 3,
                                "matched_card_count": 5,
                                "platforms": ["youtube", "bilibili", "rss"],
                                "claim_kinds": ["recommendation"],
                                "source_urls": ["https://example.com/retry-policy"],
                                "latest_run_job_id": MOCK_RSS_JOB_ID,
                                "evidence_cards": [
                                    {
                                        "card_id": "card-briefing-1",
                                        "job_id": MOCK_JOB_ID,
                                        "video_id": MOCK_VIDEO_ID,
                                        "platform": "youtube",
                                        "video_title": "AI Weekly",
                                        "source_url": "https://example.com/retry-policy",
                                        "created_at": "2026-04-01T10:00:00Z",
                                        "card_type": "claim",
                                        "card_title": "Retry baseline became explicit",
                                        "card_body": "Operators should treat retries as the default safe path.",
                                        "source_section": "digest",
                                        "topic_key": "retry-policy",
                                        "topic_label": "Retry policy",
                                        "claim_kind": "recommendation",
                                    }
                                ],
                                "routes": {
                                    "watchlist_trend": f"/trends?watchlist_id={MOCK_WATCHLIST_ID}",
                                    "briefing": f"/briefings?watchlist_id={MOCK_WATCHLIST_ID}&story_id=story-1&via=briefing-story",
                                    "ask": f"/ask?watchlist_id={MOCK_WATCHLIST_ID}&story_id=story-1&topic_key=retry-policy&via=briefing-story",
                                    "job_compare": f"/jobs?job_id={MOCK_RSS_JOB_ID}&via=briefing-compare",
                                    "job_bundle": f"/api/v1/jobs/{MOCK_RSS_JOB_ID}/bundle",
                                    "job_knowledge_cards": f"/knowledge?job_id={MOCK_RSS_JOB_ID}",
                                },
                            }
                        ],
                        "featured_runs": [
                            {
                                "job_id": MOCK_RSS_JOB_ID,
                                "video_id": MOCK_VIDEO_ID,
                                "platform": "rss",
                                "title": "RSS Digest",
                                "source_url": "https://example.com/retry-policy",
                                "created_at": "2026-04-01T11:00:00Z",
                                "matched_card_count": 2,
                                "routes": {
                                    "watchlist_trend": f"/trends?watchlist_id={MOCK_WATCHLIST_ID}",
                                    "briefing": f"/briefings?watchlist_id={MOCK_WATCHLIST_ID}&via=briefing-run",
                                    "ask": f"/ask?watchlist_id={MOCK_WATCHLIST_ID}&via=briefing-run",
                                    "job_compare": f"/jobs?job_id={MOCK_RSS_JOB_ID}&via=briefing-run",
                                    "job_bundle": f"/api/v1/jobs/{MOCK_RSS_JOB_ID}/bundle",
                                    "job_knowledge_cards": f"/knowledge?job_id={MOCK_RSS_JOB_ID}",
                                },
                            }
                        ],
                    },
                    "selection": {
                        "selected_story_id": "story-1",
                        "selection_basis": "suggested_story_id",
                        "story": None,
                    },
                }
                self._record_http(
                    method="POST",
                    path=path,
                    query=parsed.query,
                    status=int(HTTPStatus.OK),
                    payload=payload,
                )
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "question": query_text,
                        "mode": payload.get("mode", "keyword"),
                        "top_k": payload.get("top_k", 6),
                        "context": {
                            "watchlist_id": payload.get("watchlist_id"),
                            "watchlist_name": "Retry policy",
                            "story_id": payload.get("story_id") or "story-1",
                            "selected_story_id": "story-1",
                            "story_headline": "Retries moved from optional advice to default posture",
                            "topic_key": "retry-policy",
                            "topic_label": "Retry policy",
                            "selection_basis": "requested_story_id"
                            if payload.get("story_id")
                            else "suggested_story_id",
                            "mode": payload.get("mode", "keyword"),
                            "filters": payload.get("filters", {}),
                            "briefing_available": True,
                        },
                        "answer_state": "briefing_grounded",
                        "answer_headline": "Retries moved from optional advice to default posture",
                        "answer_summary": (
                            "Retry policy now reads like one shared story across YouTube, "
                            "Bilibili, and RSS sources."
                        ),
                        "answer_reason": (
                            '"Retries moved from optional advice to default posture" remains the selected '
                            "story focus, and the latest compare still shows movement around it."
                        ),
                        "answer_confidence": "grounded",
                        "story_change_summary": (
                            '"Retries moved from optional advice to default posture" remains the selected '
                            "story focus, and the latest compare still shows movement around it."
                        ),
                        "story_page": {
                            **self._briefing_page_payload(),
                            "context": {
                                **self._briefing_page_payload()["context"],
                                "story_id": payload.get("story_id") or "story-1",
                                "selection_basis": "requested_story_id"
                                if payload.get("story_id")
                                else "suggested_story_id",
                            },
                        },
                        "retrieval": {
                            "query": query_text,
                            "top_k": payload.get("top_k", 6),
                            "filters": payload.get("filters", {}),
                            "items": retrieval_items,
                        },
                        "citations": [
                            {
                                "kind": "briefing_story",
                                "label": "Retry policy is stabilizing into the baseline path",
                                "snippet": "Supported across 3 source families, 3 runs, and 5 matched cards.",
                                "source_url": None,
                                "job_id": MOCK_RSS_JOB_ID,
                                "route": f"/briefings?watchlist_id={MOCK_WATCHLIST_ID}&story_id=story-1&via=briefing-story",
                                "route_label": "Open briefing story",
                            },
                            {
                                "kind": "retrieval_hit",
                                "label": "knowledge_cards on rss (Retry policy roundup)",
                                "snippet": "Recent runs now describe retry handling as the default safe path.",
                                "source_url": "https://example.com/retry-policy",
                                "job_id": MOCK_RSS_JOB_ID,
                                "route": f"/jobs?job_id={MOCK_RSS_JOB_ID}",
                                "route_label": "Open job trace",
                            },
                        ],
                        "fallback_reason": None,
                        "fallback_next_step": None,
                        "fallback_actions": [],
                    },
                )
                return

            if path == "/api/v1/retrieval/answer":
                query_text = str(payload.get("query", "")).strip()
                retrieval_items = (
                    [
                        {
                            "job_id": MOCK_RSS_JOB_ID,
                            "video_id": MOCK_VIDEO_ID,
                            "platform": "rss",
                            "video_uid": "rss-e2e-001",
                            "source_url": "https://example.com/retry-policy",
                            "title": "Retry policy roundup",
                            "kind": "video_digest_v1",
                            "mode": "full",
                            "source": "knowledge_cards",
                            "snippet": "Recent runs now describe retry handling as the default safe path.",
                            "score": 3.2,
                        },
                        {
                            "job_id": MOCK_JOB_ID,
                            "video_id": MOCK_VIDEO_ID,
                            "platform": "youtube",
                            "video_uid": "yt-e2e-001",
                            "source_url": "https://example.com/retry-policy",
                            "title": "AI Weekly",
                            "kind": "video_digest_v1",
                            "mode": "full",
                            "source": "digest",
                            "snippet": "Operators should treat retries as the baseline posture.",
                            "score": 2.7,
                        },
                    ]
                    if "retry" in query_text.lower()
                    else []
                )
                self._record_http(
                    method="POST",
                    path=path,
                    query=parsed.query,
                    status=int(HTTPStatus.OK),
                    payload=payload,
                )
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "query": query_text,
                        "context": {
                            "watchlist_id": payload.get("watchlist_id"),
                            "watchlist_name": "Retry policy",
                            "story_id": payload.get("story_id"),
                            "selected_story_id": "story-1",
                            "story_headline": "Retries moved from optional advice to default posture",
                            "topic_key": "retry-policy",
                            "topic_label": "Retry policy",
                            "selection_basis": "query_match",
                            "mode": payload.get("mode", "keyword"),
                            "filters": payload.get("filters", {}),
                            "briefing_available": True,
                        },
                        "selected_story": {
                            "story_id": "story-1",
                            "story_key": "topic:retry-policy",
                            "headline": "Retries moved from optional advice to default posture",
                            "topic_key": "retry-policy",
                            "topic_label": "Retry policy",
                            "source_count": 3,
                            "run_count": 3,
                            "matched_card_count": 5,
                            "platforms": ["youtube", "bilibili", "rss"],
                            "claim_kinds": ["recommendation"],
                            "source_urls": ["https://example.com/retry-policy"],
                            "latest_run_job_id": MOCK_RSS_JOB_ID,
                            "routes": {
                                "watchlist_trend": f"/trends?watchlist_id={MOCK_WATCHLIST_ID}",
                                "briefing": f"/briefings?watchlist_id={MOCK_WATCHLIST_ID}&story_id=story-1&via=briefing-story",
                                "ask": f"/ask?watchlist_id={MOCK_WATCHLIST_ID}&story_id=story-1&topic_key=retry-policy&via=briefing-story",
                                "job_compare": f"/jobs?job_id={MOCK_RSS_JOB_ID}&via=briefing-compare",
                                "job_bundle": f"/api/v1/jobs/{MOCK_RSS_JOB_ID}/bundle",
                                "job_knowledge_cards": f"/knowledge?job_id={MOCK_RSS_JOB_ID}",
                            },
                        },
                        "answer": {
                            "direct_answer": (
                                f'For "{query_text}", the current briefing most strongly points to '
                                '"Retries moved from optional advice to default posture".'
                            ),
                            "summary": (
                                "Retry policy now reads like one shared story across YouTube, "
                                "Bilibili, and RSS sources. Added topics: retry-policy."
                            ),
                            "reason": (
                                '"Retries moved from optional advice to default posture" remains the selected '
                                "story focus, and the latest compare still shows movement around it."
                            ),
                            "confidence": "grounded",
                        },
                        "changes": {
                            "summary": "Added topics: retry-policy. New story keys: topic:retry-policy.",
                            "story_focus_summary": (
                                '"Retries moved from optional advice to default posture" remains the selected '
                                "story focus, and the latest compare still shows movement around it."
                            ),
                            "latest_job_id": MOCK_RSS_JOB_ID,
                            "previous_job_id": MOCK_PREVIOUS_JOB_ID,
                            "added_topics": ["retry-policy"],
                            "removed_topics": [],
                            "added_claim_kinds": ["recommendation"],
                            "removed_claim_kinds": [],
                            "new_story_keys": ["topic:retry-policy"],
                            "removed_story_keys": [],
                            "compare_excerpt": "Retry guidance moved from optional to default posture.",
                            "compare_route": f"/jobs?job_id={MOCK_RSS_JOB_ID}",
                            "has_previous": True,
                        },
                        "citations": [
                            {
                                "kind": "briefing_story",
                                "label": "Retry policy is stabilizing into the baseline path",
                                "snippet": "Supported across 3 source families, 3 runs, and 5 matched cards.",
                                "source_url": None,
                                "job_id": MOCK_RSS_JOB_ID,
                                "route": f"/briefings?watchlist_id={MOCK_WATCHLIST_ID}&story_id=story-1&via=briefing-story",
                                "route_label": "Open briefing story",
                            },
                            {
                                "kind": "retrieval_hit",
                                "label": "knowledge_cards on rss (Retry policy roundup)",
                                "snippet": "Recent runs now describe retry handling as the default safe path.",
                                "source_url": "https://example.com/retry-policy",
                                "job_id": MOCK_RSS_JOB_ID,
                                "route": f"/jobs?job_id={MOCK_RSS_JOB_ID}",
                                "route_label": "Open job trace",
                            },
                        ],
                        "evidence": {
                            "briefing_overview": (
                                "Retry policy now reads like one shared story across YouTube, "
                                "Bilibili, and RSS sources."
                            ),
                            "selected_story_id": "story-1",
                            "selected_story_headline": "Retries moved from optional advice to default posture",
                            "latest_job_id": MOCK_RSS_JOB_ID,
                            "citation_count": 2,
                            "retrieval_hit_count": len(retrieval_items),
                            "retrieval_items": retrieval_items,
                            "story_cards": [
                                {
                                    "card_id": "card-1",
                                    "job_id": MOCK_JOB_ID,
                                    "platform": "youtube",
                                    "source_url": "https://example.com/retry-policy",
                                    "title": "Retry policy became explicit",
                                    "body": "The workflow now treats retries as first-line safety.",
                                    "source_section": "Digest",
                                }
                            ],
                        },
                        "fallback": {
                            "status": "grounded",
                            "reason": None,
                            "suggested_next_step": None,
                            "actions": [],
                        },
                    },
                )
                return

            if path == "/api/v1/retrieval/search":
                query_text = str(payload.get("query", "")).strip().lower()
                items = (
                    [
                        {
                            "job_id": MOCK_RSS_JOB_ID,
                            "video_id": MOCK_VIDEO_ID,
                            "platform": "rss",
                            "video_uid": "rss-e2e-001",
                            "source_url": "https://example.com/retry-policy",
                            "title": "Retry policy roundup",
                            "kind": "video_digest_v1",
                            "mode": "full",
                            "source": "knowledge_cards",
                            "snippet": "Recent runs now describe retry handling as the default safe path.",
                            "score": 3.2,
                        },
                        {
                            "job_id": MOCK_JOB_ID,
                            "video_id": MOCK_VIDEO_ID,
                            "platform": "youtube",
                            "video_uid": "yt-e2e-001",
                            "source_url": "https://example.com/retry-policy",
                            "title": "AI Weekly",
                            "kind": "video_digest_v1",
                            "mode": "full",
                            "source": "digest",
                            "snippet": "Operators should treat retries as the baseline posture.",
                            "score": 2.7,
                        },
                    ]
                    if "retry" in query_text
                    else []
                )
                self._record_http(
                    method="POST",
                    path=path,
                    query=parsed.query,
                    status=int(HTTPStatus.OK),
                    payload=payload,
                )
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "query": payload.get("query", ""),
                        "top_k": payload.get("top_k", 6),
                        "filters": payload.get("filters", {}),
                        "items": items,
                    },
                )
                return

            if path == "/api/v1/ingest/poll":
                state.record("poll_ingest", payload)
                self._record_http(
                    method="POST",
                    path=path,
                    query=parsed.query,
                    status=int(HTTPStatus.ACCEPTED),
                    payload=payload,
                )
                self._send_json(
                    HTTPStatus.ACCEPTED,
                    {
                        "run_id": "11111111-1111-1111-1111-111111111111",
                        "workflow_id": "wf-e2e-ingest-001",
                        "status": "queued",
                        "enqueued": 2,
                        "candidates": [],
                    },
                )
                return

            if path == "/api/v1/videos/process":
                state.record("process_video", payload)
                response = {
                    "job_id": state.job_id,
                    "video_db_id": MOCK_VIDEO_DB_ID,
                    "video_uid": "yt-e2e-001",
                    "status": "queued",
                    "idempotency_key": "idem-e2e",
                    "mode": payload.get("mode", "full"),
                    "overrides": payload.get("overrides", {}),
                    "force": bool(payload.get("force", False)),
                    "reused": False,
                    "workflow_id": "wf-e2e-001",
                }
                self._record_http(
                    method="POST",
                    path=path,
                    query=parsed.query,
                    status=int(HTTPStatus.ACCEPTED),
                    payload=payload,
                )
                self._send_json(HTTPStatus.ACCEPTED, response)
                return

            if path == "/api/v1/subscriptions":
                state.record("upsert_subscription", payload)
                now = utc_now()
                platform = str(payload.get("platform", "youtube"))
                adapter_type = payload.get("adapter_type") or "rsshub_route"
                support_tier = (
                    "strong_supported"
                    if (
                        (
                            platform == "youtube"
                            and payload.get("source_type") == "youtube_channel_id"
                        )
                        or (platform == "bilibili" and payload.get("source_type") == "bilibili_uid")
                    )
                    else "generic_supported"
                )
                content_profile = (
                    "article"
                    if adapter_type == "rss_generic" or platform in {"rss", "rsshub", "generic"}
                    else "video"
                )
                with state.lock:
                    new_id = _subscription_uuid(len(state.subscriptions) + 1)
                    subscription = {
                        "id": new_id,
                        "platform": platform,
                        "source_type": payload.get("source_type", "url"),
                        "source_value": payload.get("source_value", ""),
                        "source_name": payload.get("source_name")
                        or payload.get("source_value", ""),
                        "support_tier": support_tier,
                        "content_profile": content_profile,
                        "adapter_type": adapter_type,
                        "source_url": payload.get("source_url"),
                        "rsshub_route": payload.get("rsshub_route") or "",
                        "category": payload.get("category") or "misc",
                        "tags": payload.get("tags") or [],
                        "priority": int(payload.get("priority", 50) or 50),
                        "enabled": bool(payload.get("enabled", False)),
                        "created_at": now,
                        "updated_at": now,
                    }
                    state.subscriptions.append(subscription)
                self._record_http(
                    method="POST",
                    path=path,
                    query=parsed.query,
                    status=int(HTTPStatus.OK),
                    payload=payload,
                )
                self._send_json(HTTPStatus.OK, {"subscription": subscription, "created": True})
                return

            if path == "/api/v1/subscriptions/batch-update-category":
                state.record("batch_update_subscription_category", payload)
                ids = payload.get("ids")
                category = payload.get("category")
                if not isinstance(ids, list) or not isinstance(category, str) or not category:
                    self._record_http(
                        method="POST",
                        path=path,
                        query=parsed.query,
                        status=int(HTTPStatus.BAD_REQUEST),
                        payload=payload,
                    )
                    self._send_json(
                        HTTPStatus.BAD_REQUEST, {"detail": "invalid batch update payload"}
                    )
                    return
                with state.lock:
                    id_set = {str(item) for item in ids}
                    updated = 0
                    for item in state.subscriptions:
                        if item.get("id") in id_set:
                            item["category"] = category
                            item["updated_at"] = utc_now()
                            updated += 1
                self._record_http(
                    method="POST",
                    path=path,
                    query=parsed.query,
                    status=int(HTTPStatus.OK),
                    payload=payload,
                )
                self._send_json(HTTPStatus.OK, {"updated": updated})
                return

            if path == "/api/v1/notifications/test":
                state.record("send_notification_test", payload)
                now = utc_now()
                to_email = payload.get("to_email") or "ops@example.com"
                self._record_http(
                    method="POST",
                    path=path,
                    query=parsed.query,
                    status=int(HTTPStatus.OK),
                    payload=payload,
                )
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "delivery_id": MOCK_DELIVERY_ID,
                        "status": "sent",
                        "provider_message_id": "provider-001",
                        "error_message": None,
                        "recipient_email": to_email,
                        "subject": payload.get("subject") or "SourceHarbor test notification",
                        "sent_at": now,
                        "created_at": now,
                    },
                )
                return

            self._record_http(
                method="POST",
                path=path,
                query=parsed.query,
                status=int(HTTPStatus.NOT_FOUND),
                payload=payload,
            )
            self._send_json(HTTPStatus.NOT_FOUND, {"detail": f"Unhandled POST path: {path}"})

        def do_PUT(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            payload = self._read_json()

            if path == "/api/v1/notifications/config":
                state.record("update_notification_config", payload)
                now = utc_now()
                with state.lock:
                    state.notification_config = {
                        "enabled": bool(payload.get("enabled", False)),
                        "to_email": payload.get("to_email"),
                        "daily_digest_enabled": bool(payload.get("daily_digest_enabled", False)),
                        "daily_digest_hour_utc": payload.get("daily_digest_hour_utc"),
                        "failure_alert_enabled": bool(payload.get("failure_alert_enabled", False)),
                        "category_rules": payload.get("category_rules") or {},
                        "created_at": state.notification_config.get("created_at", now),
                        "updated_at": now,
                    }
                    response = dict(state.notification_config)
                self._record_http(
                    method="PUT",
                    path=path,
                    query=parsed.query,
                    status=int(HTTPStatus.OK),
                    payload=payload,
                )
                self._send_json(HTTPStatus.OK, response)
                return

            self._record_http(
                method="PUT",
                path=path,
                query=parsed.query,
                status=int(HTTPStatus.NOT_FOUND),
                payload=payload,
            )
            self._send_json(HTTPStatus.NOT_FOUND, {"detail": f"Unhandled PUT path: {path}"})

        def do_DELETE(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            if path.startswith("/api/v1/subscriptions/"):
                subscription_id = path.rsplit("/", 1)[-1]
                if not _is_valid_uuid(subscription_id):
                    self._record_http(
                        method="DELETE",
                        path=path,
                        query=parsed.query,
                        status=int(HTTPStatus.UNPROCESSABLE_ENTITY),
                    )
                    self._send_json(
                        HTTPStatus.UNPROCESSABLE_ENTITY,
                        {"detail": "subscription id must be a valid UUID"},
                    )
                    return
                state.record("delete_subscription", {"id": subscription_id})
                with state.lock:
                    before = len(state.subscriptions)
                    state.subscriptions = [
                        item for item in state.subscriptions if item["id"] != subscription_id
                    ]
                    deleted = len(state.subscriptions) != before
                if not deleted:
                    self._record_http(
                        method="DELETE",
                        path=path,
                        query=parsed.query,
                        status=int(HTTPStatus.NOT_FOUND),
                    )
                    self._send_json(HTTPStatus.NOT_FOUND, {"detail": "subscription not found"})
                    return
                self._record_http(
                    method="DELETE",
                    path=path,
                    query=parsed.query,
                    status=int(HTTPStatus.NO_CONTENT),
                )
                self._send_no_content()
                return

            self._record_http(
                method="DELETE",
                path=path,
                query=parsed.query,
                status=int(HTTPStatus.NOT_FOUND),
            )
            self._send_json(HTTPStatus.NOT_FOUND, {"detail": f"Unhandled DELETE path: {path}"})

    return MockHandler


def start_mock_api_server() -> RunningMockServer:
    state = MockApiState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _mock_handler(state))
    port = int(server.server_address[1])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    wait_http_ok(f"{base_url}/api/v1/subscriptions")
    return RunningMockServer(
        server=server, thread=thread, api_server=MockApiServer(base_url=base_url, state=state)
    )


def stop_mock_api_server(running: RunningMockServer) -> None:
    running.server.shutdown()
    running.server.server_close()
    running.thread.join(timeout=5)


def seed_subscription(state: MockApiState, subscription_id: str, source_value: str) -> None:
    if not _is_valid_uuid(subscription_id):
        raise ValueError("subscription_id must be a valid UUID")
    now = utc_now()
    with state.lock:
        state.subscriptions = [
            {
                "id": subscription_id,
                "platform": "youtube",
                "source_type": "url",
                "source_value": source_value,
                "source_name": source_value,
                "support_tier": "strong_supported",
                "content_profile": "video",
                "adapter_type": "rsshub_route",
                "source_url": None,
                "rsshub_route": "/youtube/channel/seeded",
                "category": "misc",
                "tags": [],
                "priority": 50,
                "enabled": True,
                "created_at": now,
                "updated_at": now,
            }
        ]
