from __future__ import annotations

import re

from playwright.sync_api import Page, expect


def test_reader_fail_close_links(page: Page) -> None:
    page.goto("/reader", wait_until="domcontentloaded")

    specimen_link = page.get_by_role("link", name="Open specimen detail").first
    expect(specimen_link).to_be_visible()
    specimen_link.click()
    expect(page).to_have_url(re.compile(r"/reader/demo$"))

    page.goto("/reader", wait_until="domcontentloaded")
    ops_link = page.get_by_role("link", name="Open ops desk")
    expect(ops_link).to_be_visible()
    ops_link.click()
    expect(page).to_have_url(re.compile(r"/ops(?:\?.*)?$"))

    page.goto("/reader", wait_until="domcontentloaded")
    source_intake_link = page.get_by_role("link", name="Source intake")
    expect(source_intake_link).to_be_visible()
    source_intake_link.click()
    expect(page).to_have_url(re.compile(r"/subscriptions(?:\?.*)?$"))

    page.goto("/reader", wait_until="domcontentloaded")
    briefings_link = page.get_by_role("link", name="Briefings")
    expect(briefings_link).to_be_visible()
    briefings_link.click()
    expect(page).to_have_url(re.compile(r"/briefings(?:\?.*)?$"))

    page.goto("/reader", wait_until="domcontentloaded")
    trends_link = page.get_by_role("link", name="Trends")
    expect(trends_link).to_be_visible()
    trends_link.click()
    expect(page).to_have_url(re.compile(r"/trends(?:\?.*)?$"))


def test_reader_detail_anchor_links(page: Page) -> None:
    page.goto("/reader/demo", wait_until="domcontentloaded")

    back_link = page.get_by_role("link", name="Back to reader")
    expect(back_link).to_be_visible()
    back_link.click()
    expect(page).to_have_url(re.compile(r"/reader(?:\?.*)?$"))

    page.goto("/reader/demo", wait_until="domcontentloaded")
    read_body_link = page.get_by_role("link", name="Read the body")
    expect(read_body_link).to_be_visible()
    read_body_link.click()
    expect(page).to_have_url(re.compile(r"/reader/demo#reader-body$"))
    expect(page.locator("#reader-body")).to_be_visible()

    warning_link = page.get_by_role("link", name="Keep the warning in mind")
    expect(warning_link).to_be_visible()
    warning_link.click()
    expect(page).to_have_url(re.compile(r"/reader/demo#reader-warning$"))
    expect(page.locator("#reader-warning")).to_be_visible()

    evidence_link = page.get_by_role("link", name="Open evidence when needed")
    expect(evidence_link).to_be_visible()
    evidence_link.click()
    expect(page).to_have_url(re.compile(r"/reader/demo#reader-evidence$"))
    expect(page.locator("#reader-evidence")).to_be_visible()

    coverage_link = page.get_by_role("link", name="Check coverage last")
    expect(coverage_link).to_be_visible()
    coverage_link.click()
    expect(page).to_have_url(re.compile(r"/reader/demo#reader-coverage$"))
    expect(page.locator("#reader-coverage")).to_be_visible()
