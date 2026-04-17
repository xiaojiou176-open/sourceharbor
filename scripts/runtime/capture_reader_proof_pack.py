#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


def hide_dev_runtime_noise(page: Page) -> None:
    page.add_style_tag(
        content="""
        nextjs-portal {
          display: none !important;
        }
        """
    )


def open_reader_demo(page: Page, base_url: str) -> None:
    page.set_default_navigation_timeout(60000)
    page.goto(f"{base_url}/reader/demo", wait_until="commit", timeout=60000)
    page.locator("[data-route-heading]").wait_for(state="visible", timeout=30000)
    page.wait_for_timeout(200)


def wait_for_reader_route(base_url: str, timeout_seconds: int = 60) -> None:
    deadline = time.monotonic() + timeout_seconds
    target = f"{base_url}/reader/demo"
    last_error: str | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(target, timeout=5) as response:
                if 200 <= response.status < 500:
                    return
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
        time.sleep(1)
    message = (
        f"reader proof preflight failed: {target} did not become responsive within "
        f"{timeout_seconds}s"
    )
    if last_error:
        message = f"{message}; last_error={last_error}"
    raise RuntimeError(message)


def capture_reader_pack(base_url: str, output_dir: Path) -> list[dict[str, str]]:
    shots: list[dict[str, str]] = []
    wait_for_reader_route(base_url)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()

        desktop = browser.new_page(viewport={"width": 1440, "height": 1800})
        open_reader_demo(desktop, base_url)
        hide_dev_runtime_noise(desktop)
        desktop.wait_for_timeout(150)
        desktop.screenshot(
            path=str(output_dir / "desktop-reader-demo-clean.png"),
            full_page=True,
        )
        shots.append(
            {
                "name": "desktop-reader-demo-clean",
                "route": "/reader/demo",
                "mode": "desktop",
                "path": str(output_dir / "desktop-reader-demo-clean.png"),
            }
        )
        desktop.get_by_text("Story notes").click()
        desktop.wait_for_timeout(150)
        desktop.screenshot(
            path=str(output_dir / "desktop-reader-demo-expanded-clean.png"),
            full_page=True,
        )
        shots.append(
            {
                "name": "desktop-reader-demo-expanded-clean",
                "route": "/reader/demo#reader-notes",
                "mode": "desktop",
                "path": str(output_dir / "desktop-reader-demo-expanded-clean.png"),
            }
        )

        mobile_context = browser.new_context(
            viewport={"width": 390, "height": 844},
            is_mobile=True,
            device_scale_factor=3,
        )
        mobile = mobile_context.new_page()
        open_reader_demo(mobile, base_url)
        hide_dev_runtime_noise(mobile)
        mobile.wait_for_timeout(150)
        mobile.screenshot(
            path=str(output_dir / "mobile-reader-demo-top-clean.png"),
            full_page=False,
        )
        shots.append(
            {
                "name": "mobile-reader-demo-top-clean",
                "route": "/reader/demo",
                "mode": "mobile",
                "path": str(output_dir / "mobile-reader-demo-top-clean.png"),
            }
        )
        mobile.get_by_text("Story notes").click()
        mobile.wait_for_timeout(150)
        mobile.locator("#reader-notes").screenshot(
            path=str(output_dir / "mobile-reader-notes-clean.png")
        )
        shots.append(
            {
                "name": "mobile-reader-notes-clean",
                "route": "/reader/demo#reader-notes",
                "mode": "mobile",
                "path": str(output_dir / "mobile-reader-notes-clean.png"),
            }
        )

        browser.close()
    return shots


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture a clean local reader proof pack with dev overlay hidden."
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:3000",
        help="Base URL for the local web runtime.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(tempfile.gettempdir()) / "sourceharbor-reader-proof-clean"),
        help="Directory to write screenshot artifacts into.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    shots = capture_reader_pack(args.base_url.rstrip("/"), output_dir)
    manifest = {
        "artifact_root": str(output_dir),
        "base_url": args.base_url,
        "shots": shots,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    print(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
