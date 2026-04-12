from __future__ import annotations

import os
import re

import pytest
from playwright.sync_api import Page, TimeoutError, expect


def _select_option(page: Page, label: str, option_name: str) -> None:
    trigger = page.get_by_role("combobox", name=label)
    trigger.click()
    option = page.get_by_role("option", name=option_name)
    try:
        option.first.click(timeout=3_000)
    except TimeoutError:
        page.locator("[data-slot='select-content']").get_by_text(
            option_name, exact=True
        ).first.click()


def _goto_feed_ready(page: Page) -> None:
    page.goto("/feed", wait_until="domcontentloaded")
    expect(page.get_by_role("heading", name="Digest Feed")).to_be_visible()


def _require_mock_api_state(pytestconfig: pytest.Config, request: pytest.FixtureRequest):
    option_value = pytestconfig.getoption("--web-e2e-use-mock-api")
    env_value = os.environ.get("WEB_E2E_USE_MOCK_API")
    enabled = any(
        str(value).strip().lower() in {"1", "true", "yes", "on"}
        for value in (option_value, env_value)
        if value is not None
    )
    if not enabled:
        pytest.skip("mock-api feed coverage tests require --web-e2e-use-mock-api=1")
    return request.getfixturevalue("mock_api_state")


def test_feed_filter_submit_and_clear(page: Page) -> None:
    _goto_feed_ready(page)

    submit_button = page.get_by_role("button", name="Filter")
    expect(submit_button).to_be_visible()
    submit_button.click()
    expect(page).to_have_url(re.compile(r"/feed(?:\?.*)?$"))

    page.goto("/feed?source=youtube&category=creator", wait_until="domcontentloaded")
    clear_button = page.get_by_role("link", name="Clear")
    expect(clear_button).to_be_visible()

    clear_button.click()
    expect(page).to_have_url(re.compile(r"/feed$"))


def test_feed_empty_state_or_main_flow_renders_without_error(page: Page) -> None:
    _goto_feed_ready(page)

    empty_state = page.get_by_text("No AI digest entries yet")
    if empty_state.count() > 0:
        expect(empty_state).to_be_visible()
        expect(page.get_by_role("link", name="Go to subscriptions")).to_be_visible()
        return

    expect(page.locator(".feed-main-flow")).to_be_visible()
    expect(page.locator(".feed-entry-list")).to_be_visible()

    entry_links = page.locator(".feed-entry-link")
    if entry_links.count() > 0:
        entry_links.first.click()
        expect(
            page.locator("[data-reading-state='content'], [data-reading-state='loading']")
        ).to_be_visible()


def test_feed_pagination_links_with_mock_api(
    page: Page, pytestconfig: pytest.Config, request: pytest.FixtureRequest
) -> None:
    mock_api_state = _require_mock_api_state(pytestconfig, request)
    with mock_api_state.lock:
        mock_api_state.feed_items = [
            {
                "feed_id": "feed-e2e-1",
                "job_id": mock_api_state.job_id,
                "video_url": "https://youtube.com/watch?v=e2e001",
                "title": "Paged Digest",
                "source": "youtube",
                "source_name": "E2E Channel",
                "category": "tech",
                "published_at": "2026-03-01T00:00:00Z",
                "summary_md": "## page",
                "artifact_type": "digest",
            }
        ]
        mock_api_state.feed_has_more = True
        mock_api_state.feed_next_cursor = "cursor-next"
        mock_api_state.feed_error_status = None

    page.goto(
        "/feed?source=youtube&category=tech&page=2&cursor=cursor-current&prev_cursor=cursor-prev",
        wait_until="domcontentloaded",
    )
    previous_link = page.get_by_role("link", name="← Previous page")
    expect(previous_link).to_be_visible()
    expect(previous_link).to_have_attribute(
        "href", "/feed?source=youtube&category=tech&cursor=cursor-prev"
    )
    next_link = page.get_by_role("link", name="Next page →")
    expect(next_link).to_be_visible()
    expect(next_link).to_have_attribute(
        "href",
        "/feed?source=youtube&category=tech&page=3&cursor=cursor-next&prev_cursor=cursor-current",
    )

    previous_link.click()
    expect(page).to_have_url(re.compile(r"/feed\?source=youtube&category=tech&cursor=cursor-prev$"))

    page.goto(
        "/feed?source=youtube&category=tech&page=2&cursor=cursor-current&prev_cursor=cursor-prev",
        wait_until="domcontentloaded",
    )
    page.get_by_role("link", name="Next page →").click()
    expect(page).to_have_url(
        re.compile(
            r"/feed\?source=youtube&category=tech&page=3&cursor=cursor-next&prev_cursor=cursor-current$"
        )
    )


def test_feed_retry_link_on_error_with_mock_api(
    page: Page, pytestconfig: pytest.Config, request: pytest.FixtureRequest
) -> None:
    mock_api_state = _require_mock_api_state(pytestconfig, request)
    with mock_api_state.lock:
        mock_api_state.feed_items = []
        mock_api_state.feed_has_more = False
        mock_api_state.feed_next_cursor = None
        mock_api_state.feed_error_status = 500

    page.goto("/feed?source=youtube&page=2&cursor=cursor-current", wait_until="domcontentloaded")
    retry_link = page.get_by_role("link", name="Retry current page")
    expect(retry_link).to_be_visible()
    expect(retry_link).to_have_attribute(
        "href", "/feed?source=youtube&page=2&cursor=cursor-current"
    )
    retry_link.click()
    expect(page).to_have_url(re.compile(r"/feed\?source=youtube&page=2&cursor=cursor-current$"))


def test_feed_empty_state_primary_link_click_with_mock_api(
    page: Page, pytestconfig: pytest.Config, request: pytest.FixtureRequest
) -> None:
    mock_api_state = _require_mock_api_state(pytestconfig, request)
    with mock_api_state.lock:
        mock_api_state.feed_items = []
        mock_api_state.feed_has_more = False
        mock_api_state.feed_next_cursor = None
        mock_api_state.feed_error_status = None

    page.goto("/feed", wait_until="domcontentloaded")
    manage_link = page.get_by_role("link", name="Go to subscriptions")
    expect(manage_link).to_be_visible()
    manage_link.click()
    expect(page).to_have_url(re.compile(r"/subscriptions(?:\?.*)?$"))


def test_feed_reading_links_and_retry_button_click_with_mock_api(
    page: Page, pytestconfig: pytest.Config, request: pytest.FixtureRequest
) -> None:
    mock_api_state = _require_mock_api_state(pytestconfig, request)
    with mock_api_state.lock:
        mock_api_state.feed_items = [
            {
                "feed_id": "feed-e2e-reading",
                "job_id": mock_api_state.job_id,
                "video_url": "https://youtube.com/watch?v=e2e001",
                "title": "Reading Pane Coverage",
                "source": "youtube",
                "source_name": "E2E Channel",
                "subscription_id": "00000000-0000-4000-8000-000000000101",
                "category": "tech",
                "published_at": "2026-03-01T00:00:00Z",
                "summary_md": "## reading",
                "artifact_type": "digest",
                "published_document_title": "Reader edition one",
                "published_document_publish_status": "published",
                "reader_route": "/reader/doc-1",
            }
        ]
        mock_api_state.feed_has_more = False
        mock_api_state.feed_next_cursor = None
        mock_api_state.feed_error_status = None

    page.goto(f"/feed?item={mock_api_state.job_id}", wait_until="domcontentloaded")
    original_link = page.get_by_role("link", name="Open original")
    expect(original_link).to_be_visible()
    with page.expect_popup() as popup_info:
        original_link.click()
    popup = popup_info.value
    expect(popup).to_have_url(re.compile(r"youtube\.com/watch\?v=e2e001"))
    popup.close()

    reader_link = page.get_by_role("link", name="Open reader edition")
    expect(reader_link).to_be_visible()
    reader_link.click()
    expect(page).to_have_url(re.compile(r"/reader/doc-1$"))

    page.goto(f"/feed?item={mock_api_state.job_id}", wait_until="domcontentloaded")
    tracked_universe_link = page.get_by_role("link", name="Open tracked universe")
    expect(tracked_universe_link).to_be_visible()
    tracked_universe_link.click()
    expect(page).to_have_url(re.compile(r"/feed\?sub=00000000-0000-4000-8000-000000000101$"))

    page.goto("/feed?item=not-a-uuid", wait_until="domcontentloaded")
    retry_button = page.get_by_role("button", name="Retry")
    expect(retry_button).to_be_visible()
    retry_button.click()
    page.wait_for_load_state("domcontentloaded")
    expect(page.get_by_role("button", name="Retry")).to_be_visible()
