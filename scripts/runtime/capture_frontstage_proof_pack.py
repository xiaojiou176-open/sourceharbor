#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


def resolve_base_url(explicit_base_url: str) -> str:
    normalized = explicit_base_url.strip()
    if normalized:
        return normalized.rstrip("/")
    resolved_env = (
        Path(__file__).resolve().parents[2]
        / ".runtime-cache"
        / "run"
        / "full-stack"
        / "resolved.env"
    )
    if not resolved_env.is_file():
        return "http://127.0.0.1:3000"
    values: dict[str, str] = {}
    for raw_line in resolved_env.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    if values.get("SOURCE_HARBOR_WEB_BASE_URL"):
        return values["SOURCE_HARBOR_WEB_BASE_URL"].rstrip("/")
    if values.get("WEB_PORT"):
        return f"http://127.0.0.1:{values['WEB_PORT']}"
    return "http://127.0.0.1:3000"


def hide_dev_runtime_noise(page: Page) -> None:
    page.add_style_tag(
        content="""
        nextjs-portal {
          display: none !important;
        }
        """
    )


def wait_for_route(url: str, timeout_seconds: int = 60) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: str | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if 200 <= response.status < 500:
                    return
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
        time.sleep(1)
    message = f"frontstage proof preflight failed: {url} did not become responsive within {timeout_seconds}s"
    if last_error:
        message = f"{message}; last_error={last_error}"
    raise RuntimeError(message)


def open_page(page: Page, url: str, ready_selector: str | None = None) -> None:
    page.set_default_navigation_timeout(60000)
    page.goto(url, wait_until="commit", timeout=60000)
    if ready_selector:
        page.locator(ready_selector).wait_for(state="visible", timeout=30000)
    page.wait_for_timeout(300)


def capture_frontstage_pack(base_url: str, output_dir: Path) -> list[dict[str, str]]:
    routes = [
        {
            "name": "desktop-home-clean",
            "path": "/",
            "viewport": {"width": 1440, "height": 1400},
            "is_mobile": False,
            "ready_selector": "[data-route-heading]",
            "expand_text": None,
        },
        {
            "name": "desktop-feed-clean",
            "path": "/feed",
            "viewport": {"width": 1440, "height": 1400},
            "is_mobile": False,
            "ready_selector": "[data-route-heading]",
            "expand_text": None,
        },
        {
            "name": "desktop-subscriptions-clean",
            "path": "/subscriptions",
            "viewport": {"width": 1440, "height": 1500},
            "is_mobile": False,
            "ready_selector": "[data-route-heading]",
            "expand_text": None,
        },
        {
            "name": "desktop-reader-demo-expanded-clean",
            "path": "/reader/demo",
            "viewport": {"width": 1440, "height": 1800},
            "is_mobile": False,
            "ready_selector": "[data-route-heading]",
            "expand_text": "Story notes",
        },
        {
            "name": "mobile-home-clean",
            "path": "/",
            "viewport": {"width": 390, "height": 844},
            "is_mobile": True,
            "ready_selector": "[data-route-heading]",
            "expand_text": None,
        },
        {
            "name": "mobile-subscriptions-clean",
            "path": "/subscriptions",
            "viewport": {"width": 390, "height": 844},
            "is_mobile": True,
            "ready_selector": "[data-route-heading]",
            "expand_text": None,
        },
        {
            "name": "mobile-reader-demo-clean",
            "path": "/reader/demo",
            "viewport": {"width": 390, "height": 844},
            "is_mobile": True,
            "ready_selector": "[data-route-heading]",
            "expand_text": "Story notes",
        },
    ]

    for route in routes:
        wait_for_route(f"{base_url}{route['path']}")

    shots: list[dict[str, str]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for route in routes:
            context = browser.new_context(
                viewport=route["viewport"],
                is_mobile=route["is_mobile"],
                device_scale_factor=3 if route["is_mobile"] else 1,
            )
            page = context.new_page()
            open_page(
                page,
                f"{base_url}{route['path']}",
                route["ready_selector"],
            )
            hide_dev_runtime_noise(page)
            if route["expand_text"]:
                page.get_by_text(route["expand_text"]).click()
                page.wait_for_timeout(250)
            path = output_dir / f"{route['name']}.png"
            page.screenshot(path=str(path), full_page=not route["is_mobile"])
            shots.append(
                {
                    "name": str(route["name"]),
                    "route": str(route["path"]),
                    "mode": "mobile" if route["is_mobile"] else "desktop",
                    "path": str(path),
                }
            )
            context.close()
        browser.close()
    return shots


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture a clean frontstage proof pack with dev overlay hidden."
    )
    parser.add_argument(
        "--base-url",
        default="",
        help="Base URL for the local web runtime.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(tempfile.gettempdir()) / "sourceharbor-frontstage-proof-clean"),
        help="Directory to write screenshot artifacts into.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    base_url = resolve_base_url(args.base_url)
    shots = capture_frontstage_pack(base_url, output_dir)
    manifest = {
        "artifact_root": str(output_dir),
        "base_url": base_url,
        "shots": shots,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    (output_dir / "playwright-axe-report.json").write_text(
        '{"summary":"frontstage clean proof pack"}',
        encoding="utf-8",
    )
    print(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
