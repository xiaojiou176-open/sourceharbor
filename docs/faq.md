# FAQ

## What is SourceHarbor in one sentence?

It is a reader-first system for turning long-form sources into searchable knowledge, traceable jobs, and reusable delivery workflows.

## Is this a hosted service?

No. SourceHarbor is a public, source-first repository. You can inspect it, run it, extend it, and prove it locally. It is not currently presented as a turnkey hosted SaaS.

## Why does the repo expose API, MCP, worker, and web at the same time?

Because SourceHarbor is designed as one system with multiple entry surfaces:

- operators use the reader-first web surfaces
- integrations use the API
- assistants and automation use MCP
- background orchestration runs in the worker

## Is this only useful for video?

No. The strongest current story is around long-form video, but the feed and retrieval surfaces already model both `video` and `article` content types.

## Why should I star it if I am still evaluating?

Because SourceHarbor is useful as both:

- an inspectable source-first system
- a reference architecture for source intake, digest pipelines, retrieval, and MCP reuse

Even if you do not deploy it this week, it is the kind of repo you are likely to revisit.

## What should I read first after the README?

1. [start-here.md](./start-here.md)
2. [proof.md](./proof.md)
3. [architecture.md](./architecture.md)

## Where should questions go?

- Bugs and feature requests: GitHub Issues
- Product, workflow, and adoption questions: GitHub Discussions
- Sensitive security reports: private path in [SECURITY.md](../SECURITY.md)
