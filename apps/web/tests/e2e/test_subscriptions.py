from __future__ import annotations

import re
from uuid import uuid4

from playwright.sync_api import Locator, Page, TimeoutError, expect


def _select_option(page: Page, label_pattern: str, option_pattern: str) -> None:
    trigger = page.get_by_role("combobox", name=re.compile(label_pattern))
    trigger.click()
    option = page.get_by_role("option", name=re.compile(option_pattern))
    try:
        option.first.click(timeout=3_000)
    except TimeoutError:
        page.locator("[data-slot='select-content']").get_by_text(
            re.compile(option_pattern)
        ).first.click()


def _create_subscription_form(page: Page) -> Locator:
    _open_advanced_workbench(page)
    create_form = page.get_by_role(
        "button", name=re.compile(r"(保存订阅|Save subscription)")
    ).locator("xpath=ancestor::form[1]")
    expect(create_form).to_be_visible()
    return create_form


def _open_advanced_workbench(page: Page) -> None:
    save_button = page.get_by_role("button", name=re.compile(r"(保存订阅|Save subscription)"))
    if save_button.first.is_visible():
        return
    advanced_toggle = page.get_by_text(
        re.compile(r"Open the template, proof, and current source controls only when you need them")
    )
    advanced_toggle.click()


def _subscription_row(page: Page, source_value: str) -> Locator:
    return page.locator("tbody tr:visible").filter(has_text=source_value).last


def _create_subscription_via_form(page: Page, source_value: str) -> None:
    create_form = _create_subscription_form(page)
    create_form.locator('[name="source_value"]').fill(source_value)
    _select_option(page, r"(适配器类型|Adapter type)", r"(RSSHub 路由|RSSHub route)")
    create_form.locator('[name="rsshub_route"]').fill("/youtube/channel/sourceharbor-e2e")
    _select_option(page, r"(分类|Category)", r"(创作者|Creator)")
    create_form.locator('[name="tags"]').fill("ai,weekly")
    create_form.evaluate("(form) => form.requestSubmit()")


def _create_generic_rsshub_route_via_form(page: Page, route_value: str) -> None:
    create_form = _create_subscription_form(page)
    create_form.locator('[name="source_value"]').fill(route_value)
    create_form.locator('[name="rsshub_route"]').fill(route_value)
    create_form.locator('[name="tags"]').fill("rsshub,route")
    create_form.evaluate("(form) => form.requestSubmit()")


def _expect_subscription_success(page: Page) -> None:
    expect(
        page,
    ).to_have_url(
        re.compile(r"/subscriptions\?status=success&code=SUBSCRIPTION_(CREATED|UPDATED)"),
        timeout=15_000,
    )
    expect(page.locator(".alert.success")).to_contain_text(
        re.compile(r"(订阅已创建。|订阅已更新。|Subscription created\.|Subscription updated\.)"),
        timeout=15_000,
    )


def test_subscriptions_save_subscription_button(page: Page) -> None:
    source_value = f"https://www.youtube.com/@sourceharbor-e2e-{uuid4().hex[:8]}"
    page.goto("/subscriptions", wait_until="domcontentloaded")
    _create_subscription_via_form(page, source_value)

    _expect_subscription_success(page)
    _open_advanced_workbench(page)
    created_row = _subscription_row(page, source_value)
    expect(created_row).to_be_visible(timeout=15_000)


def test_subscriptions_delete_button(page: Page) -> None:
    source_value = f"https://www.youtube.com/@sourceharbor-delete-{uuid4().hex[:8]}"
    page.goto("/subscriptions", wait_until="domcontentloaded")
    _create_subscription_via_form(page, source_value)

    _expect_subscription_success(page)
    row = _subscription_row(page, source_value)
    _open_advanced_workbench(page)
    expect(row).to_be_visible()
    row.get_by_role("button", name=re.compile(r"(删除|Delete)")).click()
    row.get_by_test_id("subscription-confirm-delete").click()

    expect(page).to_have_url(
        re.compile(r"/subscriptions\?status=success&code=SUBSCRIPTION_DELETED")
    )
    expect(page.locator("tbody tr").filter(has_text=source_value)).to_have_count(0)
    expect(page.locator(".alert.success")).to_contain_text(
        re.compile(r"(订阅已删除。|Subscription deleted\.)")
    )


def test_subscriptions_batch_update_category(page: Page) -> None:
    source_value = f"https://www.youtube.com/@sourceharbor-batch-{uuid4().hex[:8]}"
    page.goto("/subscriptions", wait_until="domcontentloaded")
    _create_subscription_via_form(page, source_value)

    _expect_subscription_success(page)
    row = _subscription_row(page, source_value)
    _open_advanced_workbench(page)
    expect(row).to_be_visible(timeout=15_000)
    row.get_by_role("checkbox").click()
    _select_option(page, r"(批量设分类|Bulk category)", r"(运维|Operations)")
    page.get_by_test_id("subscription-apply-category").click()

    expect(_subscription_row(page, source_value)).to_contain_text(re.compile(r"(运维|Operations)"))
    undo_button = page.get_by_test_id("subscription-undo-category")
    expect(undo_button).to_be_visible()
    undo_button.click()
    expect(_subscription_row(page, source_value)).to_contain_text(re.compile(r"(创作者|Creator)"))


def test_subscriptions_save_generic_rsshub_route_template(page: Page) -> None:
    route_value = f"/namespace/path-{uuid4().hex[:8]}"
    page.goto(
        "/subscriptions?template=generic_rsshub_route",
        wait_until="domcontentloaded",
    )
    _create_generic_rsshub_route_via_form(page, route_value)

    _expect_subscription_success(page)
    _open_advanced_workbench(page)
    expect(_subscription_row(page, route_value)).to_be_visible(timeout=15_000)


def test_subscriptions_frontstage_links(page: Page) -> None:
    page.goto("/subscriptions", wait_until="domcontentloaded")

    paste_link = page.get_by_role("link", name="Paste a source").first
    expect(paste_link).to_be_visible()
    expect(paste_link).to_have_attribute("href", "#manual-source-intake-input")

    saved_sources_link = (
        page.get_by_role("link", name="Open saved sources after you paste the first one")
        .or_(page.get_by_role("link", name="Open saved sources"))
        .first
    )
    expect(saved_sources_link).to_be_visible()
    expect(saved_sources_link).to_have_attribute("href", "#tracked-universes")


def test_vendor_sources_route_into_prefilled_watchlist(page: Page) -> None:
    page.goto("/subscriptions", wait_until="domcontentloaded")

    expect(page.get_by_role("heading", name="Vendor sources")).to_be_visible()
    starter_link = page.get_by_role("link", name="Create vendor watchlist").first
    starter_href = starter_link.get_attribute("href")
    assert starter_href is not None
    page.goto(starter_href, wait_until="domcontentloaded")

    expect(page).to_have_url(
        re.compile(
            r"/watchlists\?compose=1&name=OpenAI\+signals&matcher_type=source_match&matcher_value=openai&delivery_channel=dashboard#create-watchlist"
        )
    )
    expect(page.get_by_text("Continue with OpenAI")).to_be_visible(timeout=15_000)
    expect(page.locator('[name="name"]')).to_have_value("OpenAI signals")
    expect(page.locator('[name="matcher_value"]')).to_have_value("openai")
