"""Reduced-motion route transition regression checks.

Recommended run args:
- --web-e2e-reduced-motion=reduce
- -k "reduced_motion"
"""

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.web_e2e_reduced_motion("reduce")


def _collect_route_motion_snapshot(page: Page) -> dict[str, object]:
    return page.evaluate(
        """
        () => {
            const transition = document.querySelector(".route-transition");
            const indicator = document.querySelector(".route-progress-indicator");
            const bar = document.querySelector(".route-progress-bar");
            const styleInfo = (el) => {
                if (!el) return null;
                const style = window.getComputedStyle(el);
                return {
                    animationName: style.animationName,
                    animationDuration: style.animationDuration,
                    transitionDuration: style.transitionDuration
                };
            };
            const runningRouteAnimations = document
                .getAnimations({ subtree: true })
                .filter((animation) => {
                    const target = animation.effect && animation.effect.target;
                    return (
                        target instanceof Element &&
                        (target.classList.contains("route-transition") ||
                            target.classList.contains("route-progress-indicator") ||
                            target.classList.contains("route-progress-bar"))
                    );
                })
                .map((animation) => ({
                    playState: animation.playState,
                    target:
                        animation.effect && animation.effect.target instanceof Element
                            ? animation.effect.target.className
                            : "unknown"
                }));

            return {
                mediaReduced: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
                transition: styleInfo(transition),
                indicator: styleInfo(indicator),
                bar: styleInfo(bar),
                runningRouteAnimations
            };
        }
        """
    )


def _collect_dashboard_surface_motion_snapshot(page: Page) -> list[dict[str, str]]:
    return page.evaluate(
        """
        () =>
            Array.from(
                document.querySelectorAll(".route-transition [data-slot='card']")
            )
                .slice(0, 4)
                .map((el) => {
                    const style = window.getComputedStyle(el);
                    return {
                        animationName: style.animationName,
                        animationDuration: style.animationDuration,
                        transitionDuration: style.transitionDuration
                    };
                })
        """
    )


def test_reduced_motion_route_transition_has_no_lingering_animation(page: Page) -> None:
    page.goto("/", wait_until="domcontentloaded")
    expect(page.get_by_role("navigation", name="主导航")).to_be_visible()
    page.get_by_role("link", name="设置").click()
    expect(page).to_have_url(re.compile(r"/settings$"))
    expect(page.get_by_role("heading", name="通知配置")).to_be_visible()

    snapshot = _collect_route_motion_snapshot(page)
    assert snapshot["mediaReduced"] is True, (
        "expected prefers-reduced-motion: reduce; run with --web-e2e-reduced-motion=reduce"
    )

    page.wait_for_timeout(450)  # e2e-strictness: allow-hard-wait
    settled = _collect_route_motion_snapshot(page)
    for key in ("transition", "indicator", "bar"):
        style = settled[key]
        assert isinstance(style, dict), f"missing route style snapshot for {key}"
        assert style["animationName"] == "none", f"{key} animation should be disabled: {style}"
    running = [
        item
        for item in settled["runningRouteAnimations"]
        if isinstance(item, dict) and item.get("playState") == "running"
    ]
    assert not running, f"route transition has lingering running animations: {running}"


def test_reduced_motion_disables_dashboard_surface_stagger_effect(page: Page) -> None:
    page.goto("/", wait_until="domcontentloaded")
    expect(page.get_by_role("heading", name="拉取采集")).to_be_visible()

    snapshot = _collect_dashboard_surface_motion_snapshot(page)
    assert len(snapshot) >= 3, (
        "expected dashboard to render card surfaces under .route-transition > .stack; "
        f"snapshot={snapshot}"
    )
    for index, style in enumerate(snapshot, start=1):
        assert style["animationName"] == "none", (
            "expected reduced-motion dashboard surfaces to disable stagger animation; "
            f"card_index={index} style={style}"
        )
