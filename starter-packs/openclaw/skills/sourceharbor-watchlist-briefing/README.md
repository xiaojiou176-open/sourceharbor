# SourceHarbor Watchlist Briefing

This skill is the OpenClaw-facing watchlist briefing card for SourceHarbor.

It is designed to behave like a lightweight plugin bundle:

- one skill prompt that teaches the agent the workflow
- one MCP/HTTP setup reference
- one capability map over the SourceHarbor operator surfaces
- one example output that keeps the answer shape stable

Use it when the agent should start from one watchlist, reuse the current story/briefing context, and answer one operator question with evidence.
