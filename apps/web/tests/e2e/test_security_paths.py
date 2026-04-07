from __future__ import annotations

from playwright.sync_api import Page, expect


def test_jobs_page_rejects_unsafe_job_id(page: Page) -> None:
    page.goto("/jobs?job_id=..%2Funsafe-path", wait_until="domcontentloaded")
    expect(page.get_by_text("标识符格式不合法。")).to_be_visible()
