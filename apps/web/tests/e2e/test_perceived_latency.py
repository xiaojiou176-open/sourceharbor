"""Perceived latency feedback regression checks.

Recommended run args:
- --web-e2e-cpu-throttle=4
- -k "perceived_latency"
"""

import re
import time

import pytest
from playwright.sync_api import Page, Route, expect

pytestmark = pytest.mark.web_e2e_cpu_throttle(4)


def _goto_feed_ready(page: Page) -> None:
    for attempt in range(3):
        page.goto("/feed", wait_until="domcontentloaded")
        try:
            expect(
                page.get_by_role("heading", name=re.compile(r"Digest Feed|主阅读流"))
            ).to_be_visible(timeout=12_000)
            return
        except AssertionError:
            body_text = page.locator("body").inner_text()
            if attempt < 2 and "Internal Server Error" in body_text:
                continue
            raise


def _delay_poll_ingest(route: Route) -> None:
    if route.request.method == "POST":
        time.sleep(0.7)  # e2e-strictness: allow-hard-wait
    route.continue_()


def test_perceived_latency_pending_feedback_with_cpu_throttle(page: Page) -> None:
    _goto_feed_ready(page)
    page.route("**/api/v1/ingest/poll", _delay_poll_ingest)
    sync_now_button = page.locator("button[data-feedback-state]")
    expect(sync_now_button).to_have_attribute("data-state", re.compile(r"idle|done|error"))
    page.evaluate(
        """
        () => {
            const btn = document.querySelector("button[data-feedback-state]");
            if (!(btn instanceof HTMLButtonElement)) {
                return;
            }
            window.__syncStateTrace = [];
            const trace = () => {
                window.__syncStateTrace.push({
                    t: performance.now(),
                    state: btn.getAttribute("data-state"),
                    busy: btn.getAttribute("aria-busy"),
                    feedback: btn.getAttribute("data-feedback-state")
                });
            };
            trace();
            const observer = new MutationObserver(trace);
            observer.observe(btn, {
                attributes: true,
                attributeFilter: ["data-state", "aria-busy", "data-feedback-state"]
            });
            window.__syncStateObserver = observer;
            window.__syncStateClickAt = performance.now();
        }
        """
    )
    sync_now_button.click()
    page.wait_for_timeout(450)  # e2e-strictness: allow-hard-wait
    trace_result = page.evaluate(
        """
        () => {
            const observer = window.__syncStateObserver;
            if (observer && typeof observer.disconnect === "function") {
                observer.disconnect();
            }
            const trace = Array.isArray(window.__syncStateTrace) ? window.__syncStateTrace : [];
            const clickAt =
                typeof window.__syncStateClickAt === "number"
                    ? window.__syncStateClickAt
                    : performance.now();
            const within450 = trace.filter((item) => item.t >= clickAt && item.t <= clickAt + 450);
            const hasBusy = within450.some((item) => item.busy === "true");
            const hasLoading = within450.some((item) => item.state === "loading");
            return { trace, within450, hasBusy, hasLoading };
        }
        """
    )
    assert trace_result["hasBusy"] or trace_result["hasLoading"], (
        f"expected pending/busy feedback within 450ms after click; trace={trace_result['trace']}"
    )
