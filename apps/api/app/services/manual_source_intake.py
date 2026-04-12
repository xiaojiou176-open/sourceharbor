from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

from .source_identity import build_identity_payload
from .source_names import build_source_name_fallback
from .subscriptions import (
    SubscriptionsService,
    resolve_subscription_content_profile,
    resolve_subscription_support_tier,
)
from .videos import VideosService

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
_BILIBILI_HOSTS = {
    "bilibili.com",
    "www.bilibili.com",
    "m.bilibili.com",
    "space.bilibili.com",
    "b23.tv",
}
_FEED_HINT_RE = re.compile(
    r"(?:\.xml$|/feed(?:/|$)|/rss(?:/|$)|/atom(?:/|$)|/feed\.xml$|/rss\.xml$|/atom\.xml$)",
    re.IGNORECASE,
)
_YOUTUBE_CHANNEL_ID_RE = re.compile(r"^UC[0-9A-Za-z_-]{8,}$")
_BILIBILI_UID_RE = re.compile(r"^[1-9][0-9]{3,}$")
_BILIBILI_BV_RE = re.compile(r"(BV[0-9A-Za-z]+)")


@dataclass(frozen=True)
class ManualSourcePlan:
    target_kind: str
    recommended_action: str
    platform: str | None
    source_type: str | None
    source_value: str | None
    source_url: str | None
    rsshub_route: str | None
    adapter_type: str | None
    content_profile: str | None
    support_tier: str | None
    display_name: str | None
    message: str
    relation_kind: str | None = None
    matched_subscription_id: str | None = None
    matched_subscription_name: str | None = None
    matched_by: str | None = None
    match_confidence: str | None = None
    source_universe_label: str | None = None
    creator_display_name: str | None = None
    creator_handle: str | None = None
    thumbnail_url: str | None = None
    avatar_url: str | None = None
    avatar_label: str | None = None


class ManualSourceIntakeService:
    def __init__(
        self,
        *,
        subscriptions_service: SubscriptionsService,
        videos_service: VideosService,
    ) -> None:
        self.subscriptions_service = subscriptions_service
        self.videos_service = videos_service

    @staticmethod
    def iter_non_empty_lines(raw_input: str) -> list[tuple[int, str]]:
        lines: list[tuple[int, str]] = []
        for line_number, raw_line in enumerate(str(raw_input or "").splitlines(), start=1):
            value = raw_line.strip()
            if not value:
                continue
            lines.append((line_number, value))
        return lines

    def plan(self, raw_input: str) -> ManualSourcePlan:
        value = str(raw_input or "").strip()
        if not value:
            return ManualSourcePlan(
                target_kind="unsupported",
                recommended_action="unsupported",
                platform=None,
                source_type=None,
                source_value=None,
                source_url=None,
                rsshub_route=None,
                adapter_type=None,
                content_profile=None,
                support_tier=None,
                display_name=None,
                message="Empty line.",
            )

        if value.startswith("/"):
            return self._rsshub_route_plan(value)

        if _YOUTUBE_CHANNEL_ID_RE.fullmatch(value):
            return self._subscription_plan(
                platform="youtube",
                source_type="youtube_channel_id",
                source_value=value,
                source_url=None,
                rsshub_route=f"/youtube/channel/{value}",
                adapter_type="rsshub_route",
                message="YouTube channel ID accepted as a recurring subscription source.",
            )

        if value.startswith("@") and len(value) > 1:
            return self._subscription_plan(
                platform="youtube",
                source_type="youtube_user",
                source_value=value,
                source_url=f"https://www.youtube.com/{value}",
                rsshub_route=f"/youtube/user/{value}",
                adapter_type="rsshub_route",
                message="YouTube handle accepted as a recurring subscription source.",
            )

        if _BILIBILI_UID_RE.fullmatch(value):
            return self._subscription_plan(
                platform="bilibili",
                source_type="bilibili_uid",
                source_value=value,
                source_url=f"https://space.bilibili.com/{value}",
                rsshub_route=f"/bilibili/user/video/{value}",
                adapter_type="rsshub_route",
                message="Bilibili UID accepted as a recurring subscription source.",
            )

        parsed = urlparse(value)
        scheme = str(parsed.scheme or "").lower()
        if scheme not in {"http", "https"}:
            return ManualSourcePlan(
                target_kind="unsupported",
                recommended_action="unsupported",
                platform=None,
                source_type=None,
                source_value=None,
                source_url=None,
                rsshub_route=None,
                adapter_type=None,
                content_profile=None,
                support_tier=None,
                display_name=None,
                message="Unsupported input. Bring a URL, handle, UID, or RSSHub route.",
            )

        host = str(parsed.hostname or "").strip().lower()
        if host in _YOUTUBE_HOSTS:
            return self._plan_youtube_url(value, parsed)
        if host in _BILIBILI_HOSTS:
            return self._plan_bilibili_url(value, parsed)
        if self._looks_like_feed_url(value, parsed):
            return self._subscription_plan(
                platform="generic",
                source_type="url",
                source_value=value,
                source_url=value,
                rsshub_route=value,
                adapter_type="rss_generic",
                message="Feed URL accepted as a recurring subscription source.",
            )
        return ManualSourcePlan(
            target_kind="unsupported",
            recommended_action="unsupported",
            platform=None,
            source_type=None,
            source_value=None,
            source_url=value,
            rsshub_route=None,
            adapter_type=None,
            content_profile=None,
            support_tier=None,
            display_name=None,
            message=(
                "Direct article URLs are not wired into manual intake yet. "
                "Bring a feed URL, an RSSHub route, or a supported video URL."
            ),
        )

    async def submit(
        self,
        *,
        raw_input: str,
        category: str,
        tags: list[str] | None,
        priority: int,
        enabled: bool,
    ) -> dict[str, object]:
        results: list[dict[str, object]] = []
        created_subscriptions = 0
        updated_subscriptions = 0
        queued_manual_items = 0
        reused_manual_items = 0
        rejected_count = 0

        for line_number, value in self.iter_non_empty_lines(raw_input):
            plan = self.plan(value)
            result: dict[str, object] = {
                "line_number": line_number,
                "raw_input": value,
                "target_kind": plan.target_kind,
                "recommended_action": plan.recommended_action,
                "applied_action": None,
                "status": "rejected",
                "platform": plan.platform,
                "source_type": plan.source_type,
                "source_value": plan.source_value,
                "source_url": plan.source_url,
                "rsshub_route": plan.rsshub_route,
                "adapter_type": plan.adapter_type,
                "content_profile": plan.content_profile,
                "support_tier": plan.support_tier,
                "display_name": plan.display_name,
                "relation_kind": plan.relation_kind,
                "matched_subscription_id": plan.matched_subscription_id,
                "matched_subscription_name": plan.matched_subscription_name,
                "matched_by": plan.matched_by,
                "match_confidence": plan.match_confidence,
                "source_universe_label": plan.source_universe_label,
                "creator_display_name": plan.creator_display_name,
                "creator_handle": plan.creator_handle,
                "thumbnail_url": plan.thumbnail_url,
                "avatar_url": plan.avatar_url,
                "avatar_label": plan.avatar_label,
                "message": plan.message,
                "subscription_id": None,
                "job_id": None,
            }
            try:
                if plan.recommended_action == "save_subscription":
                    row, created = self.subscriptions_service.upsert_subscription(
                        platform=plan.platform or "generic",
                        source_type=plan.source_type or "url",
                        source_value=plan.source_value or "",
                        adapter_type=plan.adapter_type,
                        source_url=plan.source_url,
                        rsshub_route=plan.rsshub_route,
                        category=category,
                        tags=tags,
                        priority=priority,
                        enabled=enabled,
                    )
                    result["applied_action"] = "save_subscription"
                    result["status"] = "created" if created else "updated"
                    result["subscription_id"] = str(getattr(row, "id", "") or "") or None
                    result["display_name"] = build_source_name_fallback(
                        platform=getattr(row, "platform", plan.platform or ""),
                        source_type=getattr(row, "source_type", plan.source_type or ""),
                        source_value=getattr(row, "source_value", plan.source_value or ""),
                        source_url=getattr(row, "source_url", plan.source_url),
                        rsshub_route=getattr(row, "rsshub_route", plan.rsshub_route),
                    )
                    identity = build_identity_payload(
                        platform=getattr(row, "platform", plan.platform or ""),
                        display_name=result["display_name"],
                        creator_handle=self._creator_handle(
                            source_type=getattr(row, "source_type", plan.source_type or ""),
                            source_value=getattr(row, "source_value", plan.source_value or ""),
                        ),
                        source_homepage_url=getattr(row, "source_url", None)
                        or getattr(row, "rsshub_route", None),
                        source_url=getattr(row, "source_url", plan.source_url),
                        source_universe_label=result["display_name"],
                    )
                    relation_kind = "matched_subscription" if not created else "new_source_universe"
                    result["relation_kind"] = relation_kind
                    result["matched_subscription_id"] = (
                        result["subscription_id"] if not created else None
                    )
                    result["matched_subscription_name"] = (
                        result["display_name"] if not created else None
                    )
                    result["matched_by"] = self._match_basis(
                        source_type=getattr(row, "source_type", plan.source_type or ""),
                        source_url=getattr(row, "source_url", plan.source_url),
                        rsshub_route=getattr(row, "rsshub_route", plan.rsshub_route),
                    )
                    result["match_confidence"] = "exact" if not created else "new"
                    result["source_universe_label"] = identity.source_universe_label
                    result["creator_display_name"] = identity.creator_display_name
                    result["creator_handle"] = identity.creator_handle
                    result["thumbnail_url"] = identity.thumbnail_url
                    result["avatar_url"] = identity.avatar_url
                    result["avatar_label"] = identity.avatar_label
                    result["message"] = (
                        "Saved as a new subscription source."
                        if created
                        else "Updated the existing subscription source."
                    )
                    if created:
                        created_subscriptions += 1
                    else:
                        updated_subscriptions += 1
                elif plan.recommended_action == "add_to_today":
                    payload = await self.videos_service.process_video(
                        platform=plan.platform or "youtube",
                        url=plan.source_url or value,
                        video_id=None,
                        mode="full",
                        overrides={},
                        force=False,
                    )
                    result["applied_action"] = "add_to_today"
                    result["status"] = "reused" if bool(payload.get("reused")) else "queued"
                    result["job_id"] = str(payload.get("job_id") or "") or None
                    video_db_id = payload.get("video_db_id")
                    match = None
                    if isinstance(video_db_id, str) and video_db_id.strip():
                        match = self.videos_service.get_subscription_match_for_video(
                            video_db_id=uuid.UUID(video_db_id)
                        )
                    elif isinstance(video_db_id, uuid.UUID):
                        match = self.videos_service.get_subscription_match_for_video(
                            video_db_id=video_db_id
                        )
                    if match is not None:
                        relation_kind = "matched_subscription"
                        matched_subscription_id = str(match.get("subscription_id") or "").strip()
                        matched_subscription_name = (
                            str(match.get("display_name") or "").strip() or plan.display_name
                        )
                        matched_by = self._match_basis(
                            source_type=str(match.get("source_type") or ""),
                            source_url=str(match.get("source_url") or "") or None,
                            rsshub_route=str(match.get("rsshub_route") or "") or None,
                        )
                        match_confidence = "inferred_from_existing_ingest_event"
                        identity = build_identity_payload(
                            platform=str(match.get("platform") or plan.platform or "youtube"),
                            display_name=matched_subscription_name,
                            creator_handle=str(match.get("creator_handle") or "").strip()
                            or plan.creator_handle,
                            source_homepage_url=str(match.get("source_url") or "").strip()
                            or plan.source_url,
                            source_url=plan.source_url,
                            source_universe_label=matched_subscription_name,
                            identity_status="matched_subscription_identity",
                        )
                        result["message"] = (
                            "Added to today and matched back to an existing tracked universe."
                            if not payload.get("reused")
                            else "Already present in today and matched to an existing tracked universe."
                        )
                    else:
                        relation_kind = "manual_one_off"
                        matched_subscription_id = None
                        matched_subscription_name = None
                        matched_by = None
                        match_confidence = None
                        identity = build_identity_payload(
                            platform=plan.platform or "youtube",
                            display_name=plan.display_name,
                            creator_handle=plan.creator_handle,
                            source_homepage_url=plan.source_url,
                            source_url=plan.source_url,
                            source_universe_label=plan.source_universe_label or plan.display_name,
                        )
                        result["message"] = (
                            "Added to today through the existing one-off video lane."
                            if not payload.get("reused")
                            else "Already present in the current one-off video lane."
                        )
                    result["relation_kind"] = relation_kind
                    result["matched_subscription_id"] = matched_subscription_id
                    result["matched_subscription_name"] = matched_subscription_name
                    result["matched_by"] = matched_by
                    result["match_confidence"] = match_confidence
                    result["source_universe_label"] = identity.source_universe_label
                    result["creator_display_name"] = identity.creator_display_name
                    result["creator_handle"] = identity.creator_handle
                    result["thumbnail_url"] = identity.thumbnail_url
                    result["avatar_url"] = identity.avatar_url
                    result["avatar_label"] = identity.avatar_label
                    if payload.get("reused"):
                        reused_manual_items += 1
                    else:
                        queued_manual_items += 1
                else:
                    rejected_count += 1
            except ValueError as exc:
                result["message"] = str(exc)
                rejected_count += 1
            except Exception as exc:
                result["message"] = str(exc)
                rejected_count += 1
            results.append(result)

        processed_count = len(results)
        return {
            "processed_count": processed_count,
            "created_subscriptions": created_subscriptions,
            "updated_subscriptions": updated_subscriptions,
            "queued_manual_items": queued_manual_items,
            "reused_manual_items": reused_manual_items,
            "rejected_count": rejected_count,
            "results": results,
        }

    def _subscription_plan(
        self,
        *,
        platform: str,
        source_type: str,
        source_value: str,
        source_url: str | None,
        rsshub_route: str | None,
        adapter_type: str,
        message: str,
    ) -> ManualSourcePlan:
        return ManualSourcePlan(
            target_kind="subscription_source",
            recommended_action="save_subscription",
            platform=platform,
            source_type=source_type,
            source_value=source_value,
            source_url=source_url,
            rsshub_route=rsshub_route,
            adapter_type=adapter_type,
            content_profile=resolve_subscription_content_profile(
                platform=platform,
                source_type=source_type,
                adapter_type=adapter_type,
            ),
            support_tier=resolve_subscription_support_tier(
                platform=platform,
                source_type=source_type,
            ),
            display_name=build_source_name_fallback(
                platform=platform,
                source_type=source_type,
                source_value=source_value,
                source_url=source_url,
                rsshub_route=rsshub_route,
            ),
            relation_kind="subscription_candidate",
            matched_subscription_id=None,
            matched_subscription_name=None,
            matched_by=self._match_basis(
                source_type=source_type,
                source_url=source_url,
                rsshub_route=rsshub_route,
            ),
            match_confidence=None,
            source_universe_label=build_source_name_fallback(
                platform=platform,
                source_type=source_type,
                source_value=source_value,
                source_url=source_url,
                rsshub_route=rsshub_route,
            ),
            creator_display_name=build_source_name_fallback(
                platform=platform,
                source_type=source_type,
                source_value=source_value,
                source_url=source_url,
                rsshub_route=rsshub_route,
            ),
            creator_handle=self._creator_handle(
                source_type=source_type,
                source_value=source_value,
            ),
            message=message,
        )

    def _manual_video_plan(
        self, *, platform: str, source_url: str, message: str
    ) -> ManualSourcePlan:
        return ManualSourcePlan(
            target_kind="manual_source_item",
            recommended_action="add_to_today",
            platform=platform,
            source_type=None,
            source_value=None,
            source_url=source_url,
            rsshub_route=None,
            adapter_type=None,
            content_profile="video",
            support_tier="strong_supported",
            display_name=source_url,
            relation_kind="manual_one_off",
            matched_subscription_id=None,
            matched_subscription_name=None,
            matched_by=None,
            match_confidence=None,
            source_universe_label="Today lane",
            creator_display_name=source_url,
            creator_handle=None,
            message=message,
        )

    def _rsshub_route_plan(self, route: str) -> ManualSourcePlan:
        return self._subscription_plan(
            platform="rsshub",
            source_type="rsshub_route",
            source_value=route,
            source_url=None,
            rsshub_route=route,
            adapter_type="rsshub_route",
            message="RSSHub route accepted as a recurring subscription source.",
        )

    def _plan_youtube_url(self, value: str, parsed) -> ManualSourcePlan:
        segments = [segment for segment in (parsed.path or "").split("/") if segment]
        if parsed.netloc.lower() == "youtu.be":
            return self._manual_video_plan(
                platform="youtube",
                source_url=value,
                message="YouTube short URL accepted as a manual item for today.",
            )
        query_video_id = parsed.query and ("v=" in parsed.query)
        if query_video_id:
            return self._manual_video_plan(
                platform="youtube",
                source_url=value,
                message="YouTube watch URL accepted as a manual item for today.",
            )
        if segments and segments[0] in {"shorts", "live"} and len(segments) > 1:
            return self._manual_video_plan(
                platform="youtube",
                source_url=value,
                message="YouTube video URL accepted as a manual item for today.",
            )
        if segments and segments[0] == "channel" and len(segments) > 1:
            channel_id = segments[1].strip()
            return self._subscription_plan(
                platform="youtube",
                source_type="youtube_channel_id",
                source_value=channel_id,
                source_url=value,
                rsshub_route=f"/youtube/channel/{channel_id}",
                adapter_type="rsshub_route",
                message="YouTube channel URL accepted as a recurring subscription source.",
            )
        if segments and segments[0].startswith("@"):
            handle = segments[0].strip()
            return self._subscription_plan(
                platform="youtube",
                source_type="youtube_user",
                source_value=handle,
                source_url=value,
                rsshub_route=f"/youtube/user/{handle}",
                adapter_type="rsshub_route",
                message="YouTube handle URL accepted as a recurring subscription source.",
            )
        if segments and segments[0] in {"user", "c"} and len(segments) > 1:
            username = segments[1].strip()
            return self._subscription_plan(
                platform="youtube",
                source_type="youtube_user",
                source_value=username,
                source_url=value,
                rsshub_route=f"/youtube/user/{username}",
                adapter_type="rsshub_route",
                message="YouTube user URL accepted as a recurring subscription source.",
            )
        return ManualSourcePlan(
            target_kind="unsupported",
            recommended_action="unsupported",
            platform="youtube",
            source_type=None,
            source_value=None,
            source_url=value,
            rsshub_route=None,
            adapter_type=None,
            content_profile=None,
            support_tier=None,
            display_name=None,
            message="Unsupported YouTube URL. Bring a video URL, channel URL, or @handle.",
        )

    def _plan_bilibili_url(self, value: str, parsed) -> ManualSourcePlan:
        host = str(parsed.hostname or "").strip().lower()
        segments = [segment for segment in (parsed.path or "").split("/") if segment]
        if host == "space.bilibili.com" and segments:
            uid = segments[0].strip()
            if _BILIBILI_UID_RE.fullmatch(uid):
                return self._subscription_plan(
                    platform="bilibili",
                    source_type="bilibili_uid",
                    source_value=uid,
                    source_url=value,
                    rsshub_route=f"/bilibili/user/video/{uid}",
                    adapter_type="rsshub_route",
                    message="Bilibili creator page accepted as a recurring subscription source.",
                )
        if host == "b23.tv":
            return self._manual_video_plan(
                platform="bilibili",
                source_url=value,
                message="Bilibili short URL accepted as a manual item for today.",
            )
        if _BILIBILI_BV_RE.search(parsed.path or ""):
            return self._manual_video_plan(
                platform="bilibili",
                source_url=value,
                message="Bilibili video URL accepted as a manual item for today.",
            )
        return ManualSourcePlan(
            target_kind="unsupported",
            recommended_action="unsupported",
            platform="bilibili",
            source_type=None,
            source_value=None,
            source_url=value,
            rsshub_route=None,
            adapter_type=None,
            content_profile=None,
            support_tier=None,
            display_name=None,
            message="Unsupported Bilibili URL. Bring a space page URL or a direct video URL.",
        )

    @staticmethod
    def _looks_like_feed_url(value: str, parsed) -> bool:
        path = str(parsed.path or "").strip().lower()
        query = str(parsed.query or "").strip().lower()
        return bool(
            _FEED_HINT_RE.search(path)
            or "format=rss" in query
            or "format=atom" in query
            or "feed=" in query
            or "rss=" in query
        )

    @staticmethod
    def _creator_handle(*, source_type: str, source_value: str) -> str | None:
        normalized_type = str(source_type or "").strip().lower()
        normalized_value = str(source_value or "").strip()
        if normalized_value.startswith("@"):
            return normalized_value
        if normalized_type == "youtube_user" and normalized_value:
            return normalized_value
        return None

    @staticmethod
    def _match_basis(*, source_type: str, source_url: str | None, rsshub_route: str | None) -> str:
        normalized_type = str(source_type or "").strip().lower()
        if normalized_type in {"youtube_channel_id", "youtube_user", "bilibili_uid"}:
            return normalized_type
        if str(rsshub_route or "").strip():
            return "rsshub_route"
        if str(source_url or "").strip():
            return "source_url"
        return "source_value"
