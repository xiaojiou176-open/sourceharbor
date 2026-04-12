from __future__ import annotations

import os
import re

import pytest
from playwright.sync_api import Page, expect


def _require_mock_api(pytestconfig: pytest.Config) -> None:
    option_value = pytestconfig.getoption("--web-e2e-use-mock-api")
    env_value = os.environ.get("WEB_E2E_USE_MOCK_API")
    enabled = any(
        str(value).strip().lower() in {"1", "true", "yes", "on"}
        for value in (option_value, env_value)
        if value is not None
    )
    if not enabled:
        pytest.skip("mock-api briefing coverage requires --web-e2e-use-mock-api=1")


def test_briefings_page_with_mock_api(page: Page, pytestconfig: pytest.Config) -> None:
    _require_mock_api(pytestconfig)

    page.goto("/briefings?watchlist_id=wl-1", wait_until="domcontentloaded")

    expect(page.get_by_role("heading", name="Unified briefings")).to_be_visible()
    expect(page.get_by_text("What the story is saying now")).to_be_visible()
    expect(page.get_by_text("What changed recently")).to_be_visible()
    expect(page.get_by_text("Evidence drill-down")).to_be_visible()
    expect(
        page.get_by_text(re.compile(r"Retry policy now reads like one shared story", re.I))
    ).to_be_visible()

    compare_link = page.get_by_role("link", name="Open compare")
    expect(compare_link).to_have_attribute(
        "href", re.compile(r"/jobs\?job_id=.*via=briefing-compare")
    )

    knowledge_links = page.get_by_role("link", name="Open knowledge").all()
    assert knowledge_links, "expected knowledge drill-down links on the briefing page"
    for link in knowledge_links:
        expect(link).to_have_attribute("href", re.compile(r"/knowledge\?job_id="))

    source_link = page.get_by_role("link", name="Open source").first
    expect(source_link).to_have_attribute("href", "https://example.com/retry-policy")


def test_briefings_to_ask_flow_with_mock_api(page: Page, pytestconfig: pytest.Config) -> None:
    _require_mock_api(pytestconfig)

    page.goto("/briefings?watchlist_id=wl-1", wait_until="domcontentloaded")

    ask_link = page.get_by_role("link", name="Ask this briefing")
    expect(ask_link).to_have_attribute(
        "href",
        re.compile(
            r"/ask\?watchlist_id=wl-1.*story_id=story-1.*topic_key=retry-policy.*via=briefing-story"
        ),
    )
    ask_link.click()

    expect(page).to_have_url(
        re.compile(
            r"/ask\?watchlist_id=wl-1.*story_id=story-1.*topic_key=retry-policy.*via=briefing-story"
        )
    )
    expect(page.get_by_role("heading", name="Ask your sources")).to_be_visible()
    expect(page.get_by_role("heading", name="Story focus driving this answer")).to_be_visible()
    expect(page.get_by_role("heading", name="Best current answer")).to_be_visible()
    expect(page.get_by_role("heading", name="What changed recently")).to_be_visible()
    expect(page.get_by_role("heading", name="Evidence drill-down")).to_be_visible()
    expect(page.get_by_role("heading", name="Citations behind this answer")).to_be_visible()
    expect(
        page.get_by_role(
            "heading",
            name="Retries moved from optional advice to default posture",
            exact=True,
        )
    ).to_be_visible()
    expect(page.get_by_role("link", name="Open selected briefing").first).to_have_attribute(
        "href",
        re.compile(r"/briefings\?watchlist_id=wl-1.*story_id=story-1.*via=briefing-story"),
    )
