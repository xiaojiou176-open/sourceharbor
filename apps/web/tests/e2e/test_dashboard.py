from __future__ import annotations

import os
import re

import pytest
from playwright.sync_api import Page, TimeoutError, expect
from support.runtime_utils import parse_external_web_base_url


def test_external_web_base_url_option_parsing() -> None:
    assert parse_external_web_base_url(None) is None
    assert parse_external_web_base_url("") is None
    assert parse_external_web_base_url("  http://127.0.0.1:3300/  ") == "http://127.0.0.1:3300"

    with pytest.raises(RuntimeError, match="absolute http\\(s\\) URL"):
        parse_external_web_base_url("not-a-url")


def test_external_web_base_url_option_validation_message() -> None:
    with pytest.raises(RuntimeError, match="absolute http\\(s\\) URL"):
        parse_external_web_base_url("ftp://127.0.0.1:3300")


def _select_option(page: Page, label: str, option_name: str) -> None:
    page.get_by_role("combobox", name=label).click()
    page.get_by_role("option", name=option_name).click()


def _require_mock_api_state(pytestconfig: pytest.Config, request: pytest.FixtureRequest):
    option_value = pytestconfig.getoption("--web-e2e-use-mock-api")
    env_value = os.environ.get("WEB_E2E_USE_MOCK_API")
    enabled = any(
        str(value).strip().lower() in {"1", "true", "yes", "on"}
        for value in (option_value, env_value)
        if value is not None
    )
    if not enabled:
        pytest.skip("mock-api dashboard coverage tests require --web-e2e-use-mock-api=1")
    return request.getfixturevalue("mock_api_state")


def test_dashboard_trigger_ingest_poll_button(page: Page) -> None:
    for attempt in range(5):
        page.goto("/", wait_until="domcontentloaded")
        trigger_button = page.get_by_role("button", name="触发采集")
        expect(trigger_button).to_be_visible()
        expect(trigger_button).to_have_attribute("data-slot", "button")
        trigger_button.click()
        try:
            success_banner = page.locator("p.alert.success")
            error_banner = page.locator("p.alert.error")
            success_banner.first.wait_for(state="visible", timeout=3000)
            if success_banner.count() > 0 and "已触发采集任务。" in success_banner.inner_text():
                break
            if error_banner.count() == 0 and "code=ERR_" not in page.url:
                break
        except (AssertionError, TimeoutError):
            if "code=POLL_INGEST_OK" in page.url and page.locator("p.alert.error").count() == 0:
                break
            body_text = page.locator("body").inner_text()
            has_transient_error = (
                "Internal Server Error" in body_text
                or "code=ERR_REQUEST_FAILED" in page.url
                or ("status=" not in page.url and page.url.endswith("/"))
            )
            if attempt < 4 and has_transient_error:
                continue
            raise
    expect(page.locator("p.alert.error")).to_have_count(0)


def test_layout_health_chip_states(page: Page) -> None:
    page.goto("/", wait_until="domcontentloaded")
    expect(page.get_by_role("link", name=re.compile(r"API 状态："))).to_be_visible()


def test_dashboard_start_processing_button(page: Page) -> None:
    page.goto("/", wait_until="domcontentloaded")
    start_button = page.get_by_role("button", name="开始处理")
    expect(start_button).to_have_attribute("data-slot", "button")
    url_input = page.get_by_label("视频链接 *")
    # Cross-browser stable guard: validate the field validity state instead of relying
    # on browser-specific disabled transitions for the submit button.
    url_input.fill("invalid-url")
    assert url_input.evaluate("el => el.validity.valid") is False
    page.get_by_label("视频链接 *").fill("https://www.youtube.com/watch?v=e2e001")
    assert url_input.evaluate("el => el.validity.valid") is True
    expect(start_button).to_be_enabled()
    _select_option(page, "模式 *", "纯文本")
    page.get_by_role("checkbox", name="强制执行").check()
    for attempt in range(2):
        start_button.click()
        try:
            expect(page).to_have_url(
                re.compile(r".*status=success.*code=PROCESS_VIDEO_OK"),
                timeout=12000,
            )
            break
        except AssertionError:
            if attempt == 0 and "code=ERR_REQUEST_FAILED" in page.url:
                page.goto("/", wait_until="domcontentloaded")
                start_button = page.get_by_role("button", name="开始处理")
                page.get_by_label("视频链接 *").fill("https://www.youtube.com/watch?v=e2e001")
                _select_option(page, "模式 *", "纯文本")
                page.get_by_role("checkbox", name="强制执行").check()
                continue
            raise
    expect(page.locator("p.alert.success")).to_contain_text("已创建处理任务。")


def test_dashboard_navigation_links_and_skip_link(page: Page) -> None:
    page.goto("/", wait_until="domcontentloaded")

    english_skip_link = page.get_by_role("link", name="Skip to main content")
    expect(english_skip_link).to_have_attribute("href", "#main-content")
    english_skip_link.evaluate("el => { el.style.left = '8px'; }")
    english_skip_link.click()
    expect(page).to_have_url(re.compile(r"/#main-content$"))
    expect(page.locator("#main-content")).to_be_focused()

    page.goto("/", wait_until="domcontentloaded")
    skip_link = page.get_by_role("link", name="跳至主内容")
    expect(skip_link).to_have_attribute("href", "#main-content")
    skip_link.evaluate("el => { el.style.left = '8px'; }")
    skip_link.click()
    expect(page).to_have_url(re.compile(r"/#main-content$"))
    expect(page.locator("#main-content")).to_be_focused()

    expect(page.get_by_role("link", name="查看任务队列 →")).to_have_attribute("href", "/jobs")
    page.get_by_role("link", name="查看任务队列 →").click()
    expect(page).to_have_url(re.compile(r"/jobs(?:\?.*)?$"))

    page.goto("/", wait_until="domcontentloaded")
    expect(page.get_by_role("link", name="查看任务详情 →")).to_have_attribute("href", "/jobs")
    page.get_by_role("link", name="查看任务详情 →").click()
    expect(page).to_have_url(re.compile(r"/jobs(?:\?.*)?$"))

    page.goto("/", wait_until="domcontentloaded")
    open_reader_link = page.get_by_role("link", name="Open Reader")
    expect(open_reader_link).to_be_visible()
    open_reader_link.click()
    expect(page).to_have_url(re.compile(r"/reader(?:\?.*)?$"))

    page.goto("/", wait_until="domcontentloaded")
    open_briefings_link = page.get_by_role("link", name="Open Briefings").first
    expect(open_briefings_link).to_be_visible()
    open_briefings_link.click()
    expect(page).to_have_url(re.compile(r"/briefings(?:\?.*)?$"))

    page.goto("/", wait_until="domcontentloaded")
    builders_guide_link = page.get_by_role("link", name="Open builders guide").first
    expect(builders_guide_link).to_be_visible()
    builders_guide_link.click()
    expect(page).to_have_url(re.compile(r"/builders(?:\?.*)?$"))

    page.goto("/", wait_until="domcontentloaded")
    distribution_link = page.get_by_role("link", name="Open distribution ledger").first
    expect(distribution_link).to_be_visible()
    with page.expect_popup() as popup_info:
        distribution_link.click()
    popup = popup_info.value
    expect(popup).to_have_url(re.compile(r"github\.com/.*/docs/public-distribution\.md"))
    popup.close()

    page.goto("/", wait_until="domcontentloaded")
    theme_toggle = page.get_by_role("button", name="Switch theme")
    expect(theme_toggle).to_be_visible()
    theme_toggle.click()
    dark_item = page.get_by_role("menuitem", name="Dark")
    if dark_item.count() > 0:
        expect(dark_item).to_be_visible()
        dark_item.click()


def test_dashboard_empty_subscription_and_tasks_links_with_mock_api(
    page: Page, pytestconfig: pytest.Config, request: pytest.FixtureRequest
) -> None:
    mock_api_state = _require_mock_api_state(pytestconfig, request)
    with mock_api_state.lock:
        mock_api_state.videos = [
            {
                "id": "00000000-0000-4000-8000-000000000101",
                "platform": "youtube",
                "video_uid": "yt-failed-001",
                "source_url": "https://youtube.com/watch?v=failed001",
                "title": "Failed E2E Demo",
                "published_at": "2026-03-01T00:00:00Z",
                "first_seen_at": "2026-03-01T00:00:00Z",
                "last_seen_at": "2026-03-01T00:00:00Z",
                "status": "failed",
                "last_job_id": "00000000-0000-4000-8000-000000000201",
            }
        ]

    page.goto("/", wait_until="domcontentloaded")

    add_subscription_link = page.get_by_role("link", name="添加第一个订阅 →")
    expect(add_subscription_link).to_be_visible()
    expect(add_subscription_link).to_have_attribute("href", "/subscriptions")
    add_subscription_link.click()
    if not re.search(r"/subscriptions(?:\?.*)?$", page.url):
        add_subscription_link.press("Enter")
    expect(page).to_have_url(re.compile(r"/subscriptions(?:\?.*)?$"))

    page.goto("/", wait_until="domcontentloaded")
    failed_tasks_link = page.get_by_role("link", name="查看失败任务 →")
    expect(failed_tasks_link).to_be_visible()
    expect(failed_tasks_link).to_have_attribute("href", "/jobs")
    failed_tasks_link.click()
    if not re.search(r"/jobs(?:\?.*)?$", page.url):
        failed_tasks_link.press("Enter")
    expect(page).to_have_url(re.compile(r"/jobs(?:\?.*)?$"))

    page.goto("/", wait_until="domcontentloaded")
    all_tasks_link = page.get_by_role("link", name="查看全部任务 →")
    expect(all_tasks_link).to_be_visible()
    expect(all_tasks_link).to_have_attribute("href", "/jobs")
    all_tasks_link.click()
    if not re.search(r"/jobs(?:\?.*)?$", page.url):
        all_tasks_link.press("Enter")
    expect(page).to_have_url(re.compile(r"/jobs(?:\?.*)?$"))
