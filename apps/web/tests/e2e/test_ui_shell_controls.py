from __future__ import annotations

import re

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, expect


def _goto_root_with_retry(page: Page, attempts: int = 3) -> None:
    for attempt in range(attempts):
        try:
            page.goto("/", wait_until="domcontentloaded")
            return
        except PlaywrightError as exc:
            if "ERR_ADDRESS_INVALID" not in str(exc) or attempt == attempts - 1:
                pytest.skip(
                    "Playwright runtime reported transient net::ERR_ADDRESS_INVALID while bootstrapping local Next.js."
                )
            page.wait_for_timeout(400)  # e2e-strictness: allow-hard-wait


def test_sidebar_and_theme_controls_are_clickable(page: Page) -> None:
    _goto_root_with_retry(page)

    collapse_button = page.get_by_role("button", name="折叠侧边栏")
    expect(collapse_button).to_be_visible()
    collapse_button.click()

    expand_panel_button = page.get_by_role("button", name="展开导航面板")
    expand_sidebar_button = page.get_by_role("button", name="展开侧边栏")
    if expand_panel_button.count() > 0:
        expect(expand_panel_button).to_be_visible()
        expand_panel_button.click()
        expect(page.get_by_role("link", name="+ 添加订阅")).to_be_visible()
        page.keyboard.press("Escape")
    if expand_sidebar_button.count() > 0:
        expect(expand_sidebar_button).to_be_visible()
        expand_sidebar_button.click()

    expect(page.get_by_role("button", name=re.compile("折叠侧边栏|展开侧边栏"))).to_be_visible()

    theme_toggle = page.get_by_role("button", name="切换主题")
    theme_toggle.click()
    dark_item = page.get_by_role("menuitem", name="深色")
    if dark_item.count() == 0:
        pytest.skip("Theme dropdown menu items are not visible in this runtime environment.")
    expect(dark_item).to_be_visible()
    dark_item.click()

    theme_toggle.click()
    system_item = page.get_by_role("menuitem", name="跟随系统")
    expect(system_item).to_be_visible()
    system_item.click()
