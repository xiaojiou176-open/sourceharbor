# SourceHarbor Claude Code Plugin Bundle

This bundle is the strongest official-surface-ready Claude Code artifact the
repo can ship today.

Use it when you want:

- a Claude plugin directory you can submit or load locally
- a SourceHarbor MCP template with the repo-root placeholder already wired
- a public watchlist-briefing skill without repo-private `.agents`

What is inside:

- `.claude-plugin/plugin.json`
- `.mcp.json`
- `skills/sourceharbor-watchlist-briefing/SKILL.md`

How to use it:

1. Copy this whole directory into a Claude plugin directory, or use it as the
   submission artifact when preparing an Anthropic marketplace entry.
2. Replace `__REPLACE_WITH_SOURCEHARBOR_REPO_ROOT__` in `.mcp.json` with the
   absolute path to your SourceHarbor checkout.
3. Start from the included skill or point Claude Code at the MCP template.

Honest boundary:

- this is a plugin-grade Claude bundle and submission-ready artifact
- it is not proof that Anthropic has already listed SourceHarbor in an official marketplace
- official listing still depends on Anthropic review and directory policy
