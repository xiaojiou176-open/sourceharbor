from __future__ import annotations

import re
from typing import Any, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SelectionBasis = Literal[
    "requested_story_id",
    "query_match",
    "suggested_story_id",
    "first_story",
    "none",
]

_QUERY_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def build_briefing_page_payload(
    *,
    briefing: dict[str, Any] | None,
    story_id: str | None = None,
    selection_query: str | None = None,
    ask_question: str | None = None,
) -> dict[str, Any]:
    selected_story, selection_basis = select_story_from_briefing(
        briefing=briefing,
        story_id=story_id,
        query=selection_query or "",
    )
    question_seed = build_story_question_seed(
        story=selected_story,
        briefing=briefing,
        explicit_question=ask_question,
    )
    selected_story_id = (
        str(selected_story.get("story_id") or "").strip()
        if isinstance(selected_story, dict)
        else ""
    )
    story_headline = (
        str(selected_story.get("headline") or "").strip()
        if isinstance(selected_story, dict)
        else ""
    )
    topic_key = (
        str(selected_story.get("topic_key") or "").strip()
        if isinstance(selected_story, dict)
        else ""
    )
    topic_label = (
        str(selected_story.get("topic_label") or "").strip()
        if isinstance(selected_story, dict)
        else ""
    )
    return {
        "selection": {
            "requested_story_id": str(story_id or "").strip() or None,
            "selected_story_id": selected_story_id or None,
            "story_headline": story_headline or None,
            "topic_key": topic_key or None,
            "topic_label": topic_label or None,
            "selection_basis": selection_basis,
            "question_seed": question_seed,
        },
        "selected_story": selected_story,
        "routes": _build_page_routes(
            briefing=briefing,
            selected_story=selected_story,
            question_seed=question_seed,
        ),
    }


def select_story_from_briefing(
    briefing: dict[str, Any] | None,
    *,
    story_id: str | None,
    query: str,
) -> tuple[dict[str, Any] | None, SelectionBasis]:
    if not isinstance(briefing, dict):
        return None, "none"
    evidence = briefing.get("evidence")
    if not isinstance(evidence, dict):
        return None, "none"
    stories = evidence.get("stories")
    if not isinstance(stories, list):
        return None, "none"
    normalized_story_id = str(story_id or "").strip()
    if normalized_story_id:
        for story in stories:
            if not isinstance(story, dict):
                continue
            if str(story.get("story_id") or "").strip() == normalized_story_id:
                return story, "requested_story_id"

    scored: list[tuple[int, int, dict[str, Any]]] = []
    for index, story in enumerate(stories):
        if not isinstance(story, dict):
            continue
        score = _score_story_match(story=story, query=query)
        scored.append((score, -index, story))
    if scored:
        best_score, _, best_story = max(scored, key=lambda item: (item[0], item[1]))
        if best_score > 0:
            return best_story, "query_match"

    suggested_story_id = str(evidence.get("suggested_story_id") or "").strip()
    if suggested_story_id:
        for story in stories:
            if not isinstance(story, dict):
                continue
            if str(story.get("story_id") or "").strip() == suggested_story_id:
                return story, "suggested_story_id"

    for story in stories:
        if isinstance(story, dict):
            return story, "first_story"
    return None, "none"


def _score_story_match(*, story: dict[str, Any], query: str) -> int:
    tokens = _query_tokens(query)
    if not tokens:
        return 0
    cards = story.get("evidence_cards")
    card_segments: list[str] = []
    if isinstance(cards, list):
        for item in cards:
            if not isinstance(item, dict):
                continue
            for key in ("card_title", "card_body", "topic_key", "topic_label", "claim_kind"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    card_segments.append(value.strip().lower())
    haystack = "\n".join(
        [
            str(story.get("headline") or "").strip().lower(),
            str(story.get("topic_key") or "").strip().lower(),
            str(story.get("topic_label") or "").strip().lower(),
            " ".join(str(item).strip().lower() for item in story.get("claim_kinds") or []),
            *card_segments,
        ]
    )
    return sum(1 for token in tokens if token in haystack)


def _query_tokens(query: str) -> set[str]:
    return {token for token in _QUERY_TOKEN_PATTERN.findall(query.strip().lower()) if token}


def build_story_question_seed(
    *,
    story: dict[str, Any] | None,
    briefing: dict[str, Any] | None,
    watchlist: dict[str, Any] | None = None,
    explicit_question: str | None = None,
) -> str | None:
    explicit = str(explicit_question or "").strip()
    if explicit:
        return explicit
    candidates = [
        str(story.get("headline") or "").strip() if isinstance(story, dict) else "",
        str(story.get("topic_label") or "").strip() if isinstance(story, dict) else "",
        str(story.get("topic_key") or "").strip() if isinstance(story, dict) else "",
    ]
    if isinstance(briefing, dict):
        summary = briefing.get("summary")
        if isinstance(summary, dict):
            candidates.append(str(summary.get("primary_story_headline") or "").strip())
        if watchlist is None:
            briefing_watchlist = briefing.get("watchlist")
            if isinstance(briefing_watchlist, dict):
                watchlist = briefing_watchlist
    if isinstance(watchlist, dict):
        candidates.append(str(watchlist.get("matcher_value") or "").strip())
        candidates.append(str(watchlist.get("name") or "").strip())
    for candidate in candidates:
        if candidate:
            return candidate
    return None


def _build_page_routes(
    *,
    briefing: dict[str, Any] | None,
    selected_story: dict[str, Any] | None,
    question_seed: str | None,
) -> dict[str, Any]:
    watchlist = briefing.get("watchlist") if isinstance(briefing, dict) else None
    watchlist_id = str(watchlist.get("id") or "").strip() if isinstance(watchlist, dict) else ""
    story_routes = (
        selected_story.get("routes")
        if isinstance(selected_story, dict) and isinstance(selected_story.get("routes"), dict)
        else {}
    )
    story_id = (
        str(selected_story.get("story_id") or "").strip()
        if isinstance(selected_story, dict)
        else ""
    )
    topic_key = (
        str(selected_story.get("topic_key") or "").strip()
        if isinstance(selected_story, dict)
        else ""
    )
    compare = briefing.get("differences", {}).get("compare") if isinstance(briefing, dict) else None
    compare_dict = compare if isinstance(compare, dict) else {}
    watchlist_trend = (
        str(story_routes.get("watchlist_trend") or "").strip()
        or _build_route("/trends", watchlist_id=watchlist_id)
        or "/trends"
    )
    base_ask_route = (
        str(story_routes.get("ask") or "").strip()
        or _build_route(
            "/ask",
            watchlist_id=watchlist_id,
            story_id=story_id or None,
            topic_key=topic_key or None,
        )
        or "/ask"
    )
    return {
        "watchlist_trend": watchlist_trend,
        "briefing": (
            str(story_routes.get("briefing") or "").strip()
            or _build_route("/briefings", watchlist_id=watchlist_id, story_id=story_id or None)
        ),
        "ask": _with_query_param(base_ask_route, key="question", value=question_seed),
        "job_compare": (
            str(compare_dict.get("compare_route") or "").strip()
            or str(story_routes.get("job_compare") or "").strip()
            or None
        ),
        "job_bundle": str(story_routes.get("job_bundle") or "").strip() or None,
        "job_knowledge_cards": str(story_routes.get("job_knowledge_cards") or "").strip() or None,
    }


def _build_route(path: str, **params: str | None) -> str | None:
    filtered = {key: value for key, value in params.items() if value}
    if filtered:
        return f"{path}?{urlencode(filtered)}"
    return path if path else None


def _with_query_param(route: str | None, *, key: str, value: str | None) -> str | None:
    safe_route = str(route or "").strip()
    safe_value = str(value or "").strip()
    if not safe_route or not safe_value:
        return safe_route or None
    split = urlsplit(safe_route)
    query_items = parse_qsl(split.query, keep_blank_values=True)
    if not any(existing_key == key for existing_key, _ in query_items):
        query_items.append((key, safe_value))
    return urlunsplit(
        (split.scheme, split.netloc, split.path, urlencode(query_items), split.fragment)
    )
