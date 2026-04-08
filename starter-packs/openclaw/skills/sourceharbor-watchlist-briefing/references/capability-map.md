# SourceHarbor Capability Map

This skill focuses on the SourceHarbor surfaces that help answer one operator question from one watchlist.

## Relevant MCP capability groups

- `sourceharbor.health.get`
- `sourceharbor.retrieval.search`
- `sourceharbor.jobs.get`
- `sourceharbor.jobs.compare`
- `sourceharbor.artifacts.get`
- `sourceharbor.reports.daily_send`
- `sourceharbor.workflows.run`
- `sourceharbor.subscriptions.manage`
- `sourceharbor.notifications.manage`

## Best default order

1. health
2. watchlist + briefing payload
3. retrieval / ask-style evidence lookup
4. jobs or artifacts only when the answer needs proof of what changed
