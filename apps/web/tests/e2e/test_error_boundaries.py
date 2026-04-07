from __future__ import annotations

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, expect


def _goto_with_retry(page: Page, path: str, attempts: int = 3) -> None:
    for attempt in range(attempts):
        try:
            page.goto(path, wait_until="domcontentloaded")
            return
        except PlaywrightError as exc:
            if "ERR_ADDRESS_INVALID" not in str(exc):
                raise
            if attempt == attempts - 1:
                pytest.fail(
                    "Playwright runtime kept returning net::ERR_ADDRESS_INVALID after retries while loading "
                    f"{path!r}: {exc}"
                )
            page.wait_for_timeout(400)  # e2e-strictness: allow-hard-wait


def test_global_error_boundary_exposes_retry_page_button(page: Page) -> None:
    _goto_with_retry(page, "/e2e-error-boundary")

    trigger_button = page.get_by_role("button", name="触发错误边界")
    expect(trigger_button).to_be_visible(timeout=10_000)
    trigger_button.click()

    # The global error boundary should expose the retry action from app/global-error.tsx.
    retry_page_button = page.get_by_role("button", name="重试页面")
    expect(retry_page_button).to_be_visible(timeout=10_000)
    retry_page_button.click(timeout=3_000)

    # reset() should recover and re-render the original page.
    expect(trigger_button).to_be_visible(timeout=10_000)
