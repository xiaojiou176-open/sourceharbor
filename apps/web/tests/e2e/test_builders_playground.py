from __future__ import annotations

import re

from playwright.sync_api import Page, expect


def test_builders_resource_links(page: Page) -> None:
    page.goto("/builders", wait_until="domcontentloaded")

    codex_bundle_link = page.get_by_role("link", name="Inspect Codex bundle").first
    expect(codex_bundle_link).to_be_visible()
    with page.expect_popup() as popup_info:
        codex_bundle_link.click()
    popup = popup_info.value
    expect(popup).to_have_url(
        re.compile(r"github\\.com/.*/starter-packs/codex/sourceharbor-codex-plugin/README\\.md")
    )
    popup.close()

    claude_bundle_link = page.get_by_role("link", name="Inspect Claude bundle").first
    expect(claude_bundle_link).to_be_visible()
    with page.expect_popup() as popup_info:
        claude_bundle_link.click()
    popup = popup_info.value
    expect(popup).to_have_url(
        re.compile(r"github\\.com/.*/starter-packs/claude-code/sourceharbor-claude-plugin/README\\.md")
    )
    popup.close()

    openclaw_pack_link = page.get_by_role("link", name="Inspect OpenClaw pack").first
    expect(openclaw_pack_link).to_be_visible()
    with page.expect_popup() as popup_info:
        openclaw_pack_link.click()
    popup = popup_info.value
    expect(popup).to_have_url(re.compile(r"github\\.com/.*/starter-packs/openclaw/README\\.md"))
    popup.close()

    mcp_registry_template_link = page.get_by_role(
        "link", name="Inspect MCP registry template"
    ).first
    expect(mcp_registry_template_link).to_be_visible()
    with page.expect_popup() as popup_info:
        mcp_registry_template_link.click()
    popup = popup_info.value
    expect(popup).to_have_url(re.compile(r"github\\.com/.*/starter-packs/mcp-registry/README\\.md"))
    popup.close()

    current_status_board_link = page.get_by_role("link", name="Open current status board").first
    expect(current_status_board_link).to_be_visible()
    with page.expect_popup() as popup_info:
        current_status_board_link.click()
    popup = popup_info.value
    expect(popup).to_have_url(re.compile(r"github\\.com/.*/docs/project-status\\.md"))
    popup.close()

    public_skills_guide_link = page.get_by_role("link", name="Open public skills guide").first
    expect(public_skills_guide_link).to_be_visible()
    with page.expect_popup() as popup_info:
        public_skills_guide_link.click()
    popup = popup_info.value
    expect(popup).to_have_url(re.compile(r"github\\.com/.*/docs/public-skills\\.md"))
    popup.close()

    media_kit_link = page.get_by_role("link", name="Open media kit").first
    expect(media_kit_link).to_be_visible()
    with page.expect_popup() as popup_info:
        media_kit_link.click()
    popup = popup_info.value
    expect(popup).to_have_url(re.compile(r"github\\.com/.*/docs/media-kit\\.md"))
    popup.close()


def test_playground_navigation_links(page: Page) -> None:
    page.goto("/playground", wait_until="domcontentloaded")

    compounder_link = page.get_by_role("link", name="Open compounder front door")
    expect(compounder_link).to_be_visible()
    compounder_link.click()
    expect(page).to_have_url(re.compile(r"/trends(?:\?.*)?$"))

    page.goto("/playground", wait_until="domcontentloaded")
    live_watchlists_link = page.get_by_role("link", name="Open live watchlists")
    expect(live_watchlists_link).to_be_visible()
    live_watchlists_link.click()
    expect(page).to_have_url(re.compile(r"/watchlists(?:\?.*)?$"))

    page.goto("/playground", wait_until="domcontentloaded")
    research_use_case_link = page.get_by_role("link", name="Open research use case")
    expect(research_use_case_link).to_be_visible()
    research_use_case_link.click()
    expect(page).to_have_url(re.compile(r"/use-cases/research-pipeline(?:\?.*)?$"))
