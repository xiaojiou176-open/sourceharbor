from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from urllib.parse import urlencode
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from ..models import NotificationConfig
from .notifications import get_notification_config
from .story_read_model import (
    build_briefing_page_payload,
    build_story_question_seed,
)

WATCHLIST_MATCHER_TYPES = {"topic_key", "claim_kind", "platform", "source_match"}
WATCHLIST_DELIVERY_CHANNELS = {"dashboard", "email"}


class WatchlistsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_watchlists(self) -> list[dict[str, Any]]:
        config = get_notification_config(self.db)
        return self._read_watchlists(config)

    def upsert_watchlist(
        self,
        *,
        watchlist_id: str | None,
        name: str,
        matcher_type: str,
        matcher_value: str,
        delivery_channel: str,
        enabled: bool,
    ) -> dict[str, Any]:
        config = get_notification_config(self.db)
        items = self._read_watchlists(config)
        now = datetime.now(UTC).isoformat()
        normalized_matcher_type = self._normalize_matcher_type(matcher_type)
        normalized_delivery = self._normalize_delivery_channel(delivery_channel)

        if watchlist_id:
            for item in items:
                if item["id"] == watchlist_id:
                    item.update(
                        {
                            "name": name.strip(),
                            "matcher_type": normalized_matcher_type,
                            "matcher_value": matcher_value.strip(),
                            "delivery_channel": normalized_delivery,
                            "enabled": enabled,
                            "updated_at": now,
                        }
                    )
                    self._write_watchlists(config, items)
                    return item

        created = {
            "id": str(uuid4()),
            "name": name.strip(),
            "matcher_type": normalized_matcher_type,
            "matcher_value": matcher_value.strip(),
            "delivery_channel": normalized_delivery,
            "enabled": enabled,
            "created_at": now,
            "updated_at": now,
        }
        items.append(created)
        self._write_watchlists(config, items)
        return created

    def delete_watchlist(self, *, watchlist_id: str) -> bool:
        config = get_notification_config(self.db)
        items = self._read_watchlists(config)
        remaining = [item for item in items if item["id"] != watchlist_id]
        if len(remaining) == len(items):
            return False
        self._write_watchlists(config, remaining)
        return True

    def get_watchlist_trend(
        self,
        *,
        watchlist_id: str,
        limit_runs: int = 3,
        limit_cards: int = 18,
    ) -> dict[str, Any] | None:
        watchlist = next(
            (item for item in self.list_watchlists() if item["id"] == watchlist_id),
            None,
        )
        if watchlist is None:
            return None

        rows = self._load_matching_cards(
            matcher_type=watchlist["matcher_type"],
            matcher_value=watchlist["matcher_value"],
            limit_cards=max(limit_cards, limit_runs * 6),
        )
        grouped: dict[str, dict[str, Any]] = {}
        cards_per_job: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            job_id = row["job_id"]
            cards_per_job[job_id].append(row)
            if job_id not in grouped:
                grouped[job_id] = {
                    "job_id": job_id,
                    "video_id": row["video_id"],
                    "platform": row["platform"],
                    "title": row["video_title"] or row["job_id"],
                    "source_url": row["source_url"],
                    "created_at": row["created_at"],
                }

        recent_runs = sorted(grouped.values(), key=lambda item: item["created_at"], reverse=True)[
            :limit_runs
        ]

        timeline: list[dict[str, Any]] = []
        previous_topics: set[str] = set()
        previous_claims: set[str] = set()
        for run in recent_runs:
            cards = cards_per_job.get(run["job_id"], [])
            topics = {
                str(card.get("topic_key") or "").strip()
                for card in cards
                if str(card.get("topic_key") or "").strip()
            }
            claims = {
                str(card.get("claim_kind") or "").strip()
                for card in cards
                if str(card.get("claim_kind") or "").strip()
            }
            timeline.append(
                {
                    **run,
                    "matched_card_count": len(cards),
                    "cards": cards[:limit_cards],
                    "topics": sorted(topics),
                    "claim_kinds": sorted(claims),
                    "added_topics": sorted(topics - previous_topics),
                    "removed_topics": sorted(previous_topics - topics),
                    "added_claim_kinds": sorted(claims - previous_claims),
                    "removed_claim_kinds": sorted(previous_claims - claims),
                }
            )
            previous_topics = topics
            previous_claims = claims

        return {
            "watchlist": watchlist,
            "summary": {
                "recent_runs": len(timeline),
                "matched_cards": len(rows),
                "matcher_type": watchlist["matcher_type"],
                "matcher_value": watchlist["matcher_value"],
            },
            "timeline": timeline,
            "merged_stories": self._build_merged_stories(rows=rows, limit_cards=limit_cards),
        }

    def get_watchlist_briefing(
        self,
        *,
        watchlist_id: str,
        limit_runs: int = 4,
        limit_cards: int = 18,
        limit_stories: int = 4,
        limit_evidence_per_story: int = 3,
    ) -> dict[str, Any] | None:
        trend = self.get_watchlist_trend(
            watchlist_id=watchlist_id,
            limit_runs=max(limit_runs, 2),
            limit_cards=max(limit_cards, limit_stories * max(limit_evidence_per_story, 1)),
        )
        if trend is None:
            return None

        timeline = list(trend.get("timeline") or [])[:limit_runs]
        merged_stories = list(trend.get("merged_stories") or [])[:limit_stories]
        source_urls = {
            source_url
            for item in merged_stories
            for source_url in (item.get("source_urls") or [])
            if isinstance(source_url, str) and source_url.strip()
        }
        platforms = {
            platform
            for item in merged_stories
            for platform in (item.get("platforms") or [])
            if isinstance(platform, str) and platform.strip()
        } or {
            str(run.get("platform") or "").strip()
            for run in timeline
            if str(run.get("platform") or "").strip()
        }
        latest_run = timeline[0] if timeline else None
        previous_run = timeline[1] if len(timeline) > 1 else None
        latest_story_keys = self._story_keys_for_run(
            merged_stories=merged_stories,
            job_id=str(latest_run.get("job_id") or "").strip() if latest_run else None,
        )
        previous_story_keys = self._story_keys_for_run(
            merged_stories=merged_stories,
            job_id=str(previous_run.get("job_id") or "").strip() if previous_run else None,
        )
        compare = self._build_briefing_compare(latest_run=latest_run)
        evidence_stories = [
            self._build_briefing_evidence_story(
                watchlist_id=watchlist_id,
                watchlist=trend["watchlist"],
                briefing={
                    "watchlist": trend["watchlist"],
                    "summary": {
                        "primary_story_headline": (
                            str(merged_stories[0].get("headline") or "").strip() or None
                            if merged_stories
                            else None
                        )
                    },
                },
                story=story,
                latest_run=latest_run,
                limit_evidence_per_story=limit_evidence_per_story,
            )
            for story in merged_stories
        ]

        return {
            "watchlist": trend["watchlist"],
            "summary": {
                "overview": self._build_briefing_overview(
                    watchlist=trend["watchlist"],
                    merged_stories=merged_stories,
                    source_count=max(len(source_urls), len(platforms)),
                    run_count=len(timeline),
                    matched_cards=int(trend["summary"].get("matched_cards") or 0),
                ),
                "source_count": max(len(source_urls), len(platforms)),
                "run_count": len(timeline),
                "story_count": len(merged_stories),
                "matched_cards": int(trend["summary"].get("matched_cards") or 0),
                "primary_story_headline": (
                    str(merged_stories[0].get("headline") or "").strip() or None
                    if merged_stories
                    else None
                ),
                "signals": [
                    self._build_briefing_signal(
                        story=story,
                        latest_run=latest_run,
                        latest_story_keys=latest_story_keys,
                    )
                    for story in merged_stories[:3]
                ],
            },
            "differences": {
                "latest_job_id": str(latest_run.get("job_id") or "").strip() or None
                if latest_run
                else None,
                "previous_job_id": str(previous_run.get("job_id") or "").strip() or None
                if previous_run
                else None,
                "added_topics": list(latest_run.get("added_topics") or []) if latest_run else [],
                "removed_topics": list(latest_run.get("removed_topics") or [])
                if latest_run
                else [],
                "added_claim_kinds": list(latest_run.get("added_claim_kinds") or [])
                if latest_run
                else [],
                "removed_claim_kinds": list(latest_run.get("removed_claim_kinds") or [])
                if latest_run
                else [],
                "new_story_keys": sorted(latest_story_keys - previous_story_keys),
                "removed_story_keys": sorted(previous_story_keys - latest_story_keys),
                "compare": compare,
            },
            "evidence": {
                "suggested_story_id": evidence_stories[0]["story_id"] if evidence_stories else None,
                "stories": evidence_stories,
                "featured_runs": [
                    {
                        "job_id": run["job_id"],
                        "video_id": run["video_id"],
                        "platform": run["platform"],
                        "title": run["title"],
                        "source_url": run.get("source_url"),
                        "created_at": run["created_at"],
                        "matched_card_count": int(run.get("matched_card_count") or 0),
                        "routes": self._build_briefing_routes(
                            watchlist_id=watchlist_id,
                            job_id=str(run["job_id"]),
                        ),
                    }
                    for run in timeline
                ],
            },
        }

    def get_watchlist_briefing_page(
        self,
        *,
        watchlist_id: str,
        story_id: str | None = None,
        limit_runs: int = 4,
        limit_cards: int = 18,
        limit_stories: int = 4,
        limit_evidence_per_story: int = 3,
        query: str | None = None,
    ) -> dict[str, Any] | None:
        briefing = self.get_watchlist_briefing(
            watchlist_id=watchlist_id,
            limit_runs=limit_runs,
            limit_cards=limit_cards,
            limit_stories=limit_stories,
            limit_evidence_per_story=limit_evidence_per_story,
        )
        if not isinstance(briefing, dict):
            return None

        page_payload = build_briefing_page_payload(
            briefing=briefing,
            story_id=story_id,
            selection_query=str(query or ""),
        )
        selection = page_payload["selection"]
        selected_story = page_payload["selected_story"]
        selection_basis = selection["selection_basis"]
        watchlist = briefing.get("watchlist") if isinstance(briefing.get("watchlist"), dict) else {}
        compare = (
            briefing.get("differences", {}).get("compare")
            if isinstance(briefing.get("differences"), dict)
            else None
        )
        compare_dict = compare if isinstance(compare, dict) else {}
        question_seed = selection["question_seed"]
        routes = page_payload["routes"]
        ask_route = str(routes.get("ask") or "").strip() or None
        story_change_summary = self._build_story_focus_summary(
            story=selected_story,
            new_story_keys=[
                str(item).strip()
                for item in (briefing.get("differences", {}).get("new_story_keys") or [])
                if str(item).strip()
            ]
            if isinstance(briefing.get("differences"), dict)
            else [],
            removed_story_keys=[
                str(item).strip()
                for item in (briefing.get("differences", {}).get("removed_story_keys") or [])
                if str(item).strip()
            ]
            if isinstance(briefing.get("differences"), dict)
            else [],
            compare_excerpt=str(compare_dict.get("diff_excerpt") or "").strip() or None,
        )
        fallback = self._build_briefing_page_fallback(
            watchlist_id=watchlist_id,
            story_id=story_id,
            selected_story=selected_story,
        )

        return {
            "context": {
                "watchlist_id": watchlist_id,
                "watchlist_name": str(watchlist.get("name") or "").strip() or None,
                "story_id": selection["requested_story_id"],
                "selected_story_id": selection["selected_story_id"],
                "story_headline": selection["story_headline"],
                "topic_key": selection["topic_key"],
                "topic_label": selection["topic_label"],
                "selection_basis": selection_basis,
                "question_seed": question_seed,
            },
            "briefing": {
                **briefing,
                "selection": {
                    "selected_story_id": str(selected_story.get("story_id") or "").strip()
                    if isinstance(selected_story, dict)
                    else None,
                    "selection_basis": selection_basis,
                    "story": None,
                },
            },
            "selected_story": selected_story,
            "story_change_summary": story_change_summary,
            "citations": self._build_briefing_page_citations(
                selected_story=selected_story,
                compare=compare_dict,
            ),
            "routes": routes,
            "compare_route": str(compare_dict.get("compare_route") or "").strip() or None,
            "ask_route": ask_route,
            "fallback_reason": str(fallback.get("reason") or "").strip() or None,
            "fallback_next_step": str(fallback.get("suggested_next_step") or "").strip() or None,
            "fallback_actions": list(fallback.get("actions") or []),
        }

    def _build_briefing_overview(
        self,
        *,
        watchlist: dict[str, Any],
        merged_stories: list[dict[str, Any]],
        source_count: int,
        run_count: int,
        matched_cards: int,
    ) -> str:
        name = str(watchlist.get("name") or "").strip() or "This watchlist"
        if not merged_stories:
            return (
                f"{name} does not have a repeated cross-source story yet. "
                f"The system still found {matched_cards} matched cards across {run_count} recent runs."
            )
        story_labels = [
            str(
                item.get("headline") or item.get("topic_label") or item.get("story_key") or ""
            ).strip()
            for item in merged_stories[:3]
        ]
        story_labels = [item for item in story_labels if item]
        joined = ", ".join(story_labels)
        return (
            f"{name} currently converges on {joined}. "
            f"These storylines are supported across {source_count} source families and {run_count} recent runs."
        )

    def _build_story_focus_summary(
        self,
        *,
        story: dict[str, Any] | None,
        new_story_keys: list[str],
        removed_story_keys: list[str],
        compare_excerpt: str | None,
    ) -> str | None:
        if not isinstance(story, dict):
            return None
        headline = str(story.get("headline") or "").strip() or "The selected story"
        story_key = str(story.get("story_key") or "").strip()
        source_count = int(story.get("source_count") or 0)
        run_count = int(story.get("run_count") or 0)
        matched_card_count = int(story.get("matched_card_count") or 0)
        if story_key and story_key in new_story_keys:
            return (
                f'"{headline}" is newly surfaced in the latest briefing and is already backed by '
                f"{source_count} source families."
            )
        if story_key and story_key in removed_story_keys:
            return f'"{headline}" was removed from the latest story set, so treat this story focus as stale context.'
        if compare_excerpt:
            return (
                f'"{headline}" remains the selected story focus, and the latest compare still shows movement '
                "around it."
            )
        if matched_card_count > 0:
            return (
                f'"{headline}" is the current story focus across {run_count} runs and '
                f"{matched_card_count} matched evidence cards."
            )
        if source_count > 0:
            return f'"{headline}" remains the strongest story focus across {source_count} source families.'
        return f'"{headline}" is the current story focus for this briefing.'

    def _build_briefing_page_citations(
        self,
        *,
        selected_story: dict[str, Any] | None,
        compare: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        citations: list[dict[str, Any]] = []
        if isinstance(selected_story, dict):
            routes = (
                selected_story.get("routes")
                if isinstance(selected_story.get("routes"), dict)
                else {}
            )
            citations.append(
                {
                    "kind": "briefing_story",
                    "label": str(
                        selected_story.get("headline") or "Selected briefing story"
                    ).strip(),
                    "snippet": self._story_support_snippet(selected_story),
                    "source_url": None,
                    "job_id": str(selected_story.get("latest_run_job_id") or "").strip() or None,
                    "route": str(routes.get("briefing") or "").strip() or None,
                    "route_label": "Open briefing story",
                }
            )
            cards = selected_story.get("evidence_cards")
            if isinstance(cards, list):
                for card in cards[:2]:
                    if not isinstance(card, dict):
                        continue
                    citations.append(
                        {
                            "kind": "briefing_card",
                            "label": str(
                                card.get("card_title")
                                or card.get("topic_label")
                                or card.get("source_section")
                                or "Briefing evidence card"
                            ).strip(),
                            "snippet": str(card.get("card_body") or "").strip(),
                            "source_url": str(card.get("source_url") or "").strip() or None,
                            "job_id": str(card.get("job_id") or "").strip() or None,
                            "route": str(routes.get("job_knowledge_cards") or "").strip() or None,
                            "route_label": "Open knowledge cards",
                        }
                    )
        compare_dict = compare if isinstance(compare, dict) else {}
        compare_excerpt = str(compare_dict.get("diff_excerpt") or "").strip()
        if compare_excerpt:
            citations.append(
                {
                    "kind": "job_compare",
                    "label": "Latest compare excerpt",
                    "snippet": compare_excerpt,
                    "source_url": None,
                    "job_id": str(compare_dict.get("job_id") or "").strip() or None,
                    "route": str(compare_dict.get("compare_route") or "").strip() or None,
                    "route_label": "Open compare",
                }
            )
        return citations[:6]

    def _build_briefing_page_fallback(
        self,
        *,
        watchlist_id: str,
        story_id: str | None,
        selected_story: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if isinstance(story_id, str) and story_id.strip() and not isinstance(selected_story, dict):
            return {
                "reason": "The requested story_id was not found inside the current briefing context.",
                "suggested_next_step": "Use the selected story from the current briefing or return to the watchlist overview.",
                "actions": [
                    {
                        "kind": "open_briefing",
                        "label": "Open watchlist briefing",
                        "route": f"/briefings?watchlist_id={watchlist_id}",
                    },
                    {
                        "kind": "open_trend",
                        "label": "Open trend timeline",
                        "route": f"/trends?watchlist_id={watchlist_id}",
                    },
                ],
            }
        if not isinstance(selected_story, dict):
            return {
                "reason": "This watchlist does not yet expose a selected story.",
                "suggested_next_step": "Open the trend timeline or wait for more matched evidence to accumulate.",
                "actions": [
                    {
                        "kind": "open_trend",
                        "label": "Open trend timeline",
                        "route": f"/trends?watchlist_id={watchlist_id}",
                    }
                ],
            }
        return {"reason": None, "suggested_next_step": None, "actions": []}

    def _build_briefing_signal(
        self,
        *,
        story: dict[str, Any],
        latest_run: dict[str, Any] | None,
        latest_story_keys: set[str],
    ) -> dict[str, Any]:
        latest_job_id = str(latest_run.get("job_id") or "").strip() if latest_run else None
        story_key = str(story.get("story_key") or "").strip()
        if story_key in latest_story_keys:
            reason = "Appears in the latest matched run."
        else:
            reason = "Most repeated merged storyline across recent runs."
        return {
            "story_key": story_key,
            "headline": str(story.get("headline") or "").strip(),
            "matched_card_count": int(story.get("matched_card_count") or 0),
            "latest_run_job_id": latest_job_id
            if latest_job_id in list(story.get("run_ids") or [])
            else None,
            "reason": reason,
        }

    def _build_briefing_evidence_story(
        self,
        *,
        watchlist_id: str,
        watchlist: dict[str, Any],
        briefing: dict[str, Any],
        story: dict[str, Any],
        latest_run: dict[str, Any] | None,
        limit_evidence_per_story: int,
    ) -> dict[str, Any]:
        cards = list(story.get("cards") or [])[: max(limit_evidence_per_story, 1)]
        latest_job_id = str(latest_run.get("job_id") or "").strip() if latest_run else None
        story_run_ids = list(story.get("run_ids") or [])
        evidence_job_id = (
            latest_job_id
            if latest_job_id in story_run_ids
            else (str(story_run_ids[0]).strip() if story_run_ids else None)
        )
        story_id = str(story.get("id") or "").strip() or None
        topic_key = str(story.get("topic_key") or "").strip() or None
        return {
            "story_id": story_id,
            "story_key": str(story.get("story_key") or "").strip(),
            "headline": str(story.get("headline") or "").strip(),
            "topic_key": story.get("topic_key"),
            "topic_label": story.get("topic_label"),
            "source_count": len(list(story.get("source_urls") or [])),
            "run_count": len(list(story.get("run_ids") or [])),
            "matched_card_count": int(story.get("matched_card_count") or 0),
            "platforms": list(story.get("platforms") or []),
            "claim_kinds": list(story.get("claim_kinds") or []),
            "source_urls": list(story.get("source_urls") or []),
            "latest_run_job_id": evidence_job_id,
            "evidence_cards": cards,
            "routes": self._build_briefing_routes(
                watchlist_id=watchlist_id,
                job_id=evidence_job_id,
                story_id=story_id,
                topic_key=topic_key,
                question=build_story_question_seed(
                    story=story,
                    briefing=briefing,
                    watchlist=watchlist,
                ),
            ),
        }

    def _build_briefing_compare(
        self, *, latest_run: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        latest_job_id = str(latest_run.get("job_id") or "").strip() if latest_run else ""
        if not latest_job_id:
            return None

        try:
            job_uuid = UUID(latest_job_id)
        except ValueError:
            return None

        from .jobs import JobsService

        payload = JobsService(self.db).compare_with_previous(job_id=job_uuid)
        if payload is None:
            return None
        diff_markdown = str(payload.get("diff_markdown") or "")
        excerpt = "\n".join(diff_markdown.splitlines()[:8]).strip() or None
        stats = payload.get("stats") if isinstance(payload.get("stats"), dict) else {}
        return {
            "job_id": latest_job_id,
            "has_previous": bool(payload.get("has_previous")),
            "previous_job_id": payload.get("previous_job_id"),
            "changed": bool(stats.get("changed")) if stats else False,
            "added_lines": int(stats.get("added_lines") or 0) if stats else 0,
            "removed_lines": int(stats.get("removed_lines") or 0) if stats else 0,
            "diff_excerpt": excerpt,
            "compare_route": f"/jobs?job_id={latest_job_id}",
        }

    def _build_briefing_routes(
        self,
        *,
        watchlist_id: str,
        job_id: str | None,
        story_id: str | None = None,
        topic_key: str | None = None,
        question: str | None = None,
    ) -> dict[str, Any]:
        return {
            "watchlist_trend": f"/trends?watchlist_id={watchlist_id}",
            "briefing": self._build_briefing_href(
                watchlist_id=watchlist_id,
                story_id=story_id,
            ),
            "ask": self._build_ask_href(
                watchlist_id=watchlist_id,
                story_id=story_id,
                topic_key=topic_key,
                question=question,
            ),
            "job_compare": f"/jobs?job_id={job_id}" if job_id else None,
            "job_bundle": f"/api/v1/jobs/{job_id}/bundle" if job_id else None,
            "job_knowledge_cards": f"/knowledge?job_id={job_id}" if job_id else None,
        }

    def _build_briefing_href(
        self,
        *,
        watchlist_id: str,
        story_id: str | None = None,
    ) -> str:
        params = {"watchlist_id": watchlist_id}
        if story_id:
            params["story_id"] = story_id
        return f"/briefings?{urlencode(params)}"

    def _build_ask_href(
        self,
        *,
        watchlist_id: str,
        story_id: str | None = None,
        topic_key: str | None = None,
        question: str | None = None,
    ) -> str:
        params = {"watchlist_id": watchlist_id}
        normalized_question = str(question or "").strip()
        if normalized_question:
            params["question"] = normalized_question
        if story_id:
            params["story_id"] = story_id
        if topic_key:
            params["topic_key"] = topic_key
        return f"/ask?{urlencode(params)}"

    def _story_keys_for_run(
        self,
        *,
        merged_stories: list[dict[str, Any]],
        job_id: str | None,
    ) -> set[str]:
        if not job_id:
            return set()
        return {
            str(story.get("story_key") or "").strip()
            for story in merged_stories
            if job_id in list(story.get("run_ids") or [])
        }

    def _build_merged_stories(
        self,
        *,
        rows: list[dict[str, Any]],
        limit_cards: int,
    ) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            story_key = self._resolve_story_key(row)
            created_at = str(row.get("created_at") or "").strip()
            source_url = str(row.get("source_url") or "").strip()
            platform = str(row.get("platform") or "").strip() or "unknown"
            claim_kind = str(row.get("claim_kind") or "").strip()
            topic_key = str(row.get("topic_key") or "").strip()
            topic_label = str(row.get("topic_label") or "").strip()
            job_id = str(row.get("job_id") or "").strip()

            group = grouped.setdefault(
                story_key,
                {
                    "id": self._story_id(story_key),
                    "story_key": story_key,
                    "headline": self._resolve_story_headline(row),
                    "topic_key": topic_key or None,
                    "topic_label": topic_label or None,
                    "latest_created_at": created_at,
                    "matched_card_count": 0,
                    "platforms": set(),
                    "claim_kinds": set(),
                    "source_urls": set(),
                    "run_ids": set(),
                    "cards": [],
                },
            )
            if created_at and created_at > str(group["latest_created_at"] or ""):
                group["latest_created_at"] = created_at
            if topic_key and not group["topic_key"]:
                group["topic_key"] = topic_key
            if topic_label and not group["topic_label"]:
                group["topic_label"] = topic_label
            if platform:
                group["platforms"].add(platform)
            if claim_kind:
                group["claim_kinds"].add(claim_kind)
            if source_url:
                group["source_urls"].add(source_url)
            if job_id:
                group["run_ids"].add(job_id)
            group["matched_card_count"] += 1
            if len(group["cards"]) < limit_cards:
                group["cards"].append(row)

        stories = []
        for item in grouped.values():
            stories.append(
                {
                    "id": item["id"],
                    "story_key": item["story_key"],
                    "headline": item["headline"],
                    "topic_key": item["topic_key"],
                    "topic_label": item["topic_label"],
                    "latest_created_at": item["latest_created_at"],
                    "matched_card_count": item["matched_card_count"],
                    "platforms": sorted(item["platforms"]),
                    "claim_kinds": sorted(item["claim_kinds"]),
                    "source_urls": sorted(item["source_urls"]),
                    "run_ids": sorted(item["run_ids"]),
                    "cards": item["cards"],
                }
            )
        stories.sort(
            key=lambda item: (item["latest_created_at"], item["matched_card_count"]),
            reverse=True,
        )
        return stories

    def _load_matching_cards(
        self,
        *,
        matcher_type: str,
        matcher_value: str,
        limit_cards: int,
    ) -> list[dict[str, Any]]:
        normalized_type = self._normalize_matcher_type(matcher_type)
        normalized_value = matcher_value.strip().lower()
        conditions = {
            "topic_key": "LOWER(COALESCE(k.metadata_json->>'topic_key', '')) = :matcher_value",
            "claim_kind": "LOWER(COALESCE(k.metadata_json->>'claim_kind', '')) = :matcher_value",
            "platform": "LOWER(COALESCE(v.platform, '')) = :matcher_value",
            "source_match": (
                "LOWER(COALESCE(v.source_url, '')) LIKE :matcher_like "
                "OR LOWER(COALESCE(v.title, '')) LIKE :matcher_like"
            ),
        }
        statement = text(
            f"""
            SELECT
                CAST(k.id AS TEXT) AS card_id,
                CAST(k.job_id AS TEXT) AS job_id,
                CAST(k.video_id AS TEXT) AS video_id,
                COALESCE(v.platform, '') AS platform,
                COALESCE(v.title, '') AS video_title,
                COALESCE(v.source_url, '') AS source_url,
                CAST(j.created_at AS TEXT) AS created_at,
                COALESCE(k.card_type, '') AS card_type,
                COALESCE(k.title, '') AS card_title,
                COALESCE(k.body, '') AS card_body,
                COALESCE(k.source_section, '') AS source_section,
                COALESCE(k.metadata_json->>'topic_key', '') AS topic_key,
                COALESCE(k.metadata_json->>'topic_label', '') AS topic_label,
                COALESCE(k.metadata_json->>'claim_kind', '') AS claim_kind
            FROM knowledge_cards k
            JOIN jobs j ON j.id = k.job_id
            JOIN videos v ON v.id = k.video_id
            WHERE {conditions[normalized_type]}
            ORDER BY j.created_at DESC, k.ordinal ASC
            LIMIT :limit_cards
            """
        )
        params = {
            "matcher_value": normalized_value,
            "matcher_like": f"%{normalized_value}%",
            "limit_cards": max(1, limit_cards),
        }
        try:
            rows = self.db.execute(statement, params).mappings().all()
        except DBAPIError:
            self.db.rollback()
            return []
        return [
            {
                "card_id": row["card_id"],
                "job_id": row["job_id"],
                "video_id": row["video_id"],
                "platform": row["platform"] or "unknown",
                "video_title": row["video_title"] or None,
                "source_url": row["source_url"] or None,
                "created_at": row["created_at"],
                "card_type": row["card_type"] or "unknown",
                "card_title": row["card_title"] or None,
                "card_body": row["card_body"] or "",
                "source_section": row["source_section"] or "",
                "topic_key": row["topic_key"] or None,
                "topic_label": row["topic_label"] or None,
                "claim_kind": row["claim_kind"] or None,
            }
            for row in rows
        ]

    def _read_watchlists(self, config: NotificationConfig) -> list[dict[str, Any]]:
        raw = config.category_rules if isinstance(config.category_rules, dict) else {}
        normalized_root = self._normalize_category_rules_root(raw)
        items = normalized_root.get("watchlists")
        if not isinstance(items, list):
            return []
        normalized_items: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                normalized_items.append(
                    {
                        "id": str(item.get("id") or "").strip(),
                        "name": str(item.get("name") or "").strip(),
                        "matcher_type": self._normalize_matcher_type(
                            str(item.get("matcher_type") or "")
                        ),
                        "matcher_value": str(item.get("matcher_value") or "").strip(),
                        "delivery_channel": self._normalize_delivery_channel(
                            str(item.get("delivery_channel") or "")
                        ),
                        "enabled": bool(item.get("enabled", True)),
                        "created_at": str(item.get("created_at") or "").strip(),
                        "updated_at": str(item.get("updated_at") or "").strip(),
                    }
                )
            except ValueError:
                continue
        return [
            item
            for item in normalized_items
            if item["id"] and item["name"] and item["matcher_value"]
        ]

    def _write_watchlists(self, config: NotificationConfig, items: list[dict[str, Any]]) -> None:
        raw = config.category_rules if isinstance(config.category_rules, dict) else {}
        normalized_root = self._normalize_category_rules_root(raw)
        normalized_root["watchlists"] = items
        config.category_rules = normalized_root
        self.db.commit()
        self.db.refresh(config)

    def _normalize_category_rules_root(self, raw: dict[str, Any]) -> dict[str, Any]:
        if isinstance(raw.get("category_rules"), dict):
            normalized = dict(raw)
            normalized["category_rules"] = dict(raw["category_rules"])
            return normalized

        category_rules = {
            key: value
            for key, value in raw.items()
            if isinstance(value, dict) and key != "watchlists"
        }
        normalized: dict[str, Any] = {"category_rules": category_rules}
        default_rule = raw.get("default_rule")
        if isinstance(default_rule, dict):
            normalized["default_rule"] = default_rule
        watchlists = raw.get("watchlists")
        if isinstance(watchlists, list):
            normalized["watchlists"] = watchlists
        return normalized

    def _normalize_matcher_type(self, raw: str) -> str:
        value = raw.strip().lower()
        if value not in WATCHLIST_MATCHER_TYPES:
            raise ValueError("invalid matcher_type")
        return value

    def _normalize_delivery_channel(self, raw: str) -> str:
        value = raw.strip().lower() or "dashboard"
        if value not in WATCHLIST_DELIVERY_CHANNELS:
            raise ValueError("invalid delivery_channel")
        return value

    def _resolve_story_key(self, row: dict[str, Any]) -> str:
        topic_key = str(row.get("topic_key") or "").strip().lower()
        if topic_key:
            return f"topic:{topic_key}"
        source_url = str(row.get("source_url") or "").strip().lower()
        if source_url:
            return f"source:{source_url}"
        card_title = str(row.get("card_title") or "").strip().lower()
        if card_title:
            return f"title:{card_title}"
        card_id = str(row.get("card_id") or "").strip() or "unknown-card"
        return f"card:{card_id}"

    def _resolve_story_headline(self, row: dict[str, Any]) -> str:
        for key in ("topic_label", "card_title", "video_title", "source_url"):
            value = str(row.get(key) or "").strip()
            if value:
                return value
        return "Merged story"

    @staticmethod
    def _story_support_snippet(story: dict[str, Any]) -> str:
        source_count = int(story.get("source_count") or 0)
        run_count = int(story.get("run_count") or 0)
        matched_card_count = int(story.get("matched_card_count") or 0)
        return (
            f"Supported across {source_count} source families, {run_count} runs, "
            f"and {matched_card_count} matched cards."
        )

    def _story_id(self, story_key: str) -> str:
        return sha256(story_key.encode("utf-8")).hexdigest()[:16]
