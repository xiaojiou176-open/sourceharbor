"""Mobile profile regression checks.

Recommended run args:
- --web-e2e-device-profile=mobile
- -k "mobile"
"""

import re
from collections.abc import Callable

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.web_e2e_device("mobile")


def _goto_dashboard(page: Page) -> None:
    page.goto("/", wait_until="domcontentloaded")
    expect(page.get_by_role("heading", name="拉取采集")).to_be_visible()


def _select_option(page: Page, label: str, option_name: str) -> None:
    page.get_by_role("combobox", name=label).click()
    page.get_by_role("option", name=option_name).click()


def _expect_action_result(page: Page, success_code: str, success_message: str) -> None:
    expect(page).to_have_url(
        re.compile(rf".*status=(success|error).*(code={success_code}|code=ERR_REQUEST_FAILED)"),
        timeout=12_000,
    )
    if success_code in page.url:
        expect(page.locator("p.alert.success")).to_contain_text(success_message)
        return
    expect(page.locator("p.alert.error")).to_contain_text("请求失败，请稍后重试。")


def _click_dashboard_action(
    page: Page,
    *,
    button_name: str,
    success_code: str,
    success_message: str,
    prepare: Callable[[], object] | None = None,
) -> None:
    for attempt in range(2):
        _goto_dashboard(page)
        if prepare is not None:
            prepare()
        button = page.get_by_role("button", name=button_name)
        expect(button).to_be_visible()
        expect(button).to_be_enabled()
        button.click()
        try:
            _expect_action_result(page, success_code, success_message)
            return
        except AssertionError:
            body_text = page.locator("body").inner_text()
            has_transient_error = (
                "Internal Server Error" in body_text or "code=ERR_REQUEST_FAILED" in page.url
            )
            if attempt == 0 and has_transient_error:
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


def test_mobile_profile_layout_and_cta_visibility(page: Page) -> None:
    _goto_dashboard(page)

    viewport = page.viewport_size
    assert viewport is not None
    assert viewport["width"] <= 430, (
        "expected mobile viewport width <= 430; run with --web-e2e-device-profile=mobile"
    )

    expect(page.get_by_role("heading", name="拉取采集")).to_be_visible()
    expect(page.get_by_role("button", name="触发采集")).to_be_visible()
    expect(page.get_by_role("button", name="开始处理")).to_be_visible()

    _click_dashboard_action(
        page,
        button_name="触发采集",
        success_code="POLL_INGEST_OK",
        success_message="已触发采集任务。",
    )
    _click_dashboard_action(
        page,
        button_name="开始处理",
        success_code="PROCESS_VIDEO_OK",
        success_message="已创建处理任务。",
        prepare=lambda: (
            page.get_by_label("视频链接 *").fill("https://www.youtube.com/watch?v=e2emobile001"),
            _select_option(page, "模式 *", "纯文本"),
            page.get_by_role("checkbox", name="强制执行").check(),
        ),
    )

    _assert_no_horizontal_overflow(page, "/")
    page.get_by_role("link", name=re.compile(r"设置|任务")).first.click()
    expect(page).to_have_url(re.compile(r"/(settings|jobs)$"))
    _assert_no_horizontal_overflow(page, page.url)


def test_mobile_sidebar_sheet_trigger_opens_navigation_dialog(page: Page) -> None:
    page.goto("/", wait_until="domcontentloaded")
    menu_trigger = page.get_by_role("button", name=re.compile(r"导航|菜单|打开侧边栏"))
    expect(menu_trigger).to_be_visible()
    menu_trigger.click()
    expect(page.get_by_role("dialog")).to_be_visible()
    expect(page.get_by_role("complementary", name="侧边栏导航")).to_be_visible()
