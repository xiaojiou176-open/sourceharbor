from __future__ import annotations

import json
import os
import re
from urllib import request as urllib_request

import pytest
from conftest import WEB_E2E_WRITE_TOKEN
from playwright.sync_api import Page, expect


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _mock_api_enabled(pytestconfig: pytest.Config) -> bool:
    option_value = pytestconfig.getoption("--web-e2e-use-mock-api")
    env_value = os.environ.get("WEB_E2E_USE_MOCK_API")
    return _is_truthy(None if option_value is None else str(option_value)) or _is_truthy(env_value)


def _real_api_base_url(pytestconfig: pytest.Config) -> str:
    return str(pytestconfig.getoption("--web-e2e-api-base-url")).strip().rstrip("/")


def _create_real_job(pytestconfig: pytest.Config) -> str:
    payload = json.dumps(
        {
            "video": {
                "platform": "youtube",
                "url": "https://www.youtube.com/watch?v=e2e001",
            },
            "mode": "text_only",
        }
    ).encode("utf-8")
    request = urllib_request.Request(
        f"{_real_api_base_url(pytestconfig)}/api/v1/videos/process",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": WEB_E2E_WRITE_TOKEN,
        },
        method="POST",
    )
    with urllib_request.urlopen(request, timeout=20) as response:  # noqa: S310
        body = json.loads(response.read().decode("utf-8"))
    return str(body["job_id"])


def test_jobs_to_feed_item_navigation(page: Page, pytestconfig: pytest.Config) -> None:
    """Jobs page 'View in digest feed' link navigates to /feed?item=job_id."""
    job_id = "00000000-0000-4000-8000-000000000001"

    if _mock_api_enabled(pytestconfig):
        page.goto("/jobs", wait_until="domcontentloaded")
        page.get_by_label("Job ID *").fill(job_id)
        page.get_by_role("button", name="Search").click()
        expect(page).to_have_url(re.compile(rf"/jobs\?job_id={re.escape(job_id)}(?:&.*)?$"))
        expect(page.get_by_role("heading", name="Find a job")).to_be_visible()

        feed_link = page.get_by_role("link", name="View in digest feed")
        expect(feed_link).to_have_attribute("href", re.compile(rf"/feed\?item={re.escape(job_id)}"))
        feed_link.click()
    else:
        job_id = _create_real_job(pytestconfig)
        page.goto(f"/jobs?job_id={job_id}", wait_until="domcontentloaded")
        expect(page).to_have_url(re.compile(rf"/jobs\?job_id={re.escape(job_id)}(?:&.*)?$"))
        expect(page.get_by_role("heading", name="Find a job")).to_be_visible()
        expect(page.get_by_label("Job ID *")).to_have_value(job_id)
        feed_link = page.get_by_role("link", name="View in digest feed")
        expect(feed_link).to_have_attribute("href", re.compile(rf"/feed\?item={re.escape(job_id)}"))
        feed_link.click()

    expect(page).to_have_url(re.compile(rf"/feed\?(?:.*&)?item={re.escape(job_id)}(?:&.*)?$"))


def test_jobs_context_navigation_links(page: Page) -> None:
    page.goto("/jobs", wait_until="domcontentloaded")
    home_link = page.get_by_role("link", name="recent videos on the home page")
    expect(home_link).to_have_attribute("href", "/")
    home_link.click()
    expect(page).to_have_url(re.compile(r"/(?:\?.*)?(?:#.*)?$"))

    page.goto("/jobs", wait_until="domcontentloaded")
    feed_link = page.get_by_role("link", name="the digest feed")
    expect(feed_link).to_have_attribute("href", "/feed")
    feed_link.click()
    expect(page).to_have_url(re.compile(r"/feed(?:\?.*)?$"))


def test_jobs_lookup_form_requires_job_id(page: Page) -> None:
    job_id = "00000000-0000-4000-8000-0000000000ff"
    page.goto(f"/jobs?job_id={job_id}", wait_until="domcontentloaded")
    expect(page).to_have_url(re.compile(rf"/jobs\?job_id={re.escape(job_id)}(?:&.*)?$"))
    expect(page.get_by_label("Job ID *")).to_have_value(job_id)
