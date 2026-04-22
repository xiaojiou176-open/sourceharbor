# @sourceharbor/sdk

Thin TypeScript SDK for the current SourceHarbor HTTP API.

This first public SDK intentionally stays small:

- grounded search
- story-aware Ask page payload
- job lookup
- watchlist listing
- subscription template and vendor signal discovery
- opt-in write helpers for ingest poll and video processing

It does **not** try to mirror every operator-only web helper. The SDK is meant
to stay close to the public HTTP contract in
`contracts/source/openapi.yaml`, not re-implement SourceHarbor business logic in
package form.

## Install

From a SourceHarbor checkout:

```bash
npm install ./packages/sourceharbor-sdk
```

If you later publish this package to a registry, replace the local path with
the published package name.

## Example

```ts
import { createSourceHarborClient } from "@sourceharbor/sdk";

const client = createSourceHarborClient({
  baseUrl:
    process.env.SOURCE_HARBOR_API_BASE_URL ??
    `http://127.0.0.1:${process.env.API_PORT ?? "9000"}`,
});

const result = await client.search({
  query: "agent workflows",
  mode: "keyword",
  topK: 5,
});

console.log(result.items.map((item) => item.title));
```

If you just booted the repo-managed stack locally, source
`.runtime-cache/run/full-stack/resolved.env` first so
`SOURCE_HARBOR_API_BASE_URL` and `API_PORT` match the actual API port instead of
assuming `9000`.

## Boundary

- This is a **builder-facing API package**, not a replacement for the repo-local
  operator commands in `./bin/sourceharbor`.
- For MCP-driven agent reuse, keep using `./bin/dev-mcp` or the documented MCP
  quickstart.
- For full local runtime management, use the repo-local `bin/*` entrypoints.
