"""Mobile profile regression checks for the reader-first front door."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.web_e2e_device("mobile")


def _goto_home_ready(page: Page) -> None:
    for attempt in range(3):
        page.goto("/", wait_until="domcontentloaded")
        try:
            expect(page.locator("[data-route-heading]")).to_be_visible(timeout=12_000)
            expect(page.get_by_role("link", name="Open Reader")).to_be_visible()
            return
        except AssertionError:
            body_text = page.locator("body").inner_text()
            if attempt < 2 and "Internal Server Error" in body_text:
                continue
            raise


def _goto_feed_ready(page: Page) -> None:
    for attempt in range(3):
        page.goto("/feed", wait_until="domcontentloaded")
        try:
            expect(
                page.get_by_role("heading", name=re.compile(r"Timeline|Main reading flow"))
            ).to_be_visible(timeout=12_000)
            return
        except AssertionError:
            body_text = page.locator("body").inner_text()
            if attempt < 2 and "Internal Server Error" in body_text:
                continue
            raise


def _assert_no_horizontal_overflow(page: Page, route: str) -> None:
    metrics = page.evaluate(
        """
        () => {
            const doc = document.documentElement;
            const body = document.body;
            const rootScrollWidth = Math.max(
                doc.scrollWidth,
                body ? body.scrollWidth : 0
            );
            const offenders = [];
            for (const el of Array.from(document.querySelectorAll("*"))) {
                const rect = el.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) {
                    continue;
                }
                if (rect.right > doc.clientWidth + 1) {
                    offenders.push(
                        `${el.tagName.toLowerCase()}.${String(el.className || "").slice(0, 48)}`
                    );
                }
                if (offenders.length >= 8) {
                    break;
                }
            }
            return {
                clientWidth: doc.clientWidth,
                scrollWidth: rootScrollWidth,
                offenders
            };
        }
        """
    )
    assert metrics["scrollWidth"] <= metrics["clientWidth"] + 1, (
        f"{route} has horizontal overflow on mobile profile: "
        f"scrollWidth={metrics['scrollWidth']} clientWidth={metrics['clientWidth']} "
        f"offenders={metrics['offenders']}"
    )


def _assert_mobile_shell_keeps_reader_stage_primary(page: Page, route: str) -> None:
    metrics = page.evaluate(
        """
        () => {
            const main = document.getElementById("main-content");
            const mainRect = main ? main.getBoundingClientRect() : null;
            const visibleSidebars = Array.from(
                document.querySelectorAll('aside[aria-label="Sidebar navigation"]')
            )
                .map((el) => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    const visible =
                        style.display !== "none" &&
                        style.visibility !== "hidden" &&
                        rect.width > 0 &&
                        rect.height > 0;
                    return {
                        visible,
                        width: rect.width,
                        position: style.position,
                    };
                })
                .filter((item) => item.visible);
            return {
                mainLeft: mainRect ? mainRect.left : null,
                mainTop: mainRect ? mainRect.top : null,
                visibleSidebars,
            };
        }
        """
    )
    assert metrics["mainLeft"] is not None and metrics["mainLeft"] <= 72, (
        f"{route} main stage is pushed too far right on mobile: {metrics}"
    )
    assert metrics["mainTop"] is not None and metrics["mainTop"] <= 72, (
        f"{route} main stage starts too low on mobile: {metrics}"
    )
    blocking_sidebars = [
        item
        for item in metrics["visibleSidebars"]
        if item["width"] > 96 and item["position"] != "fixed"
    ]
    assert not blocking_sidebars, (
        f"{route} is still showing a desktop-width sidebar before the mobile sheet opens: "
        f"{blocking_sidebars}"
    )


def test_mobile_home_layout_and_primary_cta_visibility(page: Page) -> None:
    _goto_home_ready(page)

    viewport = page.viewport_size
    assert viewport is not None
    assert viewport["width"] <= 430, (
        "expected mobile viewport width <= 430; run with --web-e2e-device-profile=mobile"
    )

    _assert_no_horizontal_overflow(page, "/")
    _assert_mobile_shell_keeps_reader_stage_primary(page, "/")
    expect(page.get_by_text("Reading specimen")).to_be_visible()
    expect(page.get_by_role("link", name="Open Reader")).to_be_visible()


def test_mobile_feed_layout_keeps_main_reading_flow_visible(page: Page) -> None:
    _goto_feed_ready(page)

    _assert_no_horizontal_overflow(page, "/feed")
    _assert_mobile_shell_keeps_reader_stage_primary(page, "/feed")
    expect(page.get_by_role("button", name="Open navigation panel")).to_be_visible()

    empty_state = page.get_by_text("No AI digest entries yet")
    if empty_state.count() > 0:
        expect(empty_state).to_be_visible()
        expect(page.get_by_role("link", name="Go to subscriptions")).to_be_visible()
        return

    expect(page.locator(".feed-main-flow")).to_be_visible()
    expect(page.locator(".feed-entry-list")).to_be_visible()


def test_mobile_sidebar_sheet_trigger_opens_navigation_dialog(page: Page) -> None:
    _goto_home_ready(page)
    menu_trigger = page.get_by_role("button", name="Open navigation panel")
    expect(menu_trigger).to_be_visible()
    menu_trigger.click()
    expect(page.get_by_role("dialog")).to_be_visible()
    expect(page.get_by_role("complementary", name="Sidebar navigation")).to_be_visible()


def test_mobile_internal_frontdoor_links_are_clickable(page: Page) -> None:
    page.goto("/subscriptions", wait_until="domcontentloaded")
    paste_source = page.get_by_role("link", name="Paste a source")
    expect(paste_source).to_be_visible()
    paste_source.click()

    open_saved_sources_after = page.get_by_role(
        "link", name="Open saved sources after you paste the first one"
    )
    if open_saved_sources_after.count():
        open_saved_sources_after.click()

    follow_first_source = page.get_by_role("link", name="Follow the first source")
    if follow_first_source.count():
        follow_first_source.click()

    menu_trigger = page.get_by_role("button", name="Open navigation panel")
    if menu_trigger.count():
        menu_trigger.click()
        open_following = page.get_by_role("link", name="Open Following")
        if open_following.count():
            open_following.click()

    page.goto("/feed", wait_until="domcontentloaded")
    start_with_story = page.get_by_role("link", name="Start with this story")
    if start_with_story.count():
        start_with_story.click()

    inspect_job_trace = page.get_by_role("link", name="Inspect job trace")
    if inspect_job_trace.count():
        inspect_job_trace.click()

    open_source_desk = page.get_by_role("link", name="Open source desk")
    if open_source_desk.count():
        open_source_desk.click()
