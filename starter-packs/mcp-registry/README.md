# SourceHarbor MCP Registry Submission Template

This directory holds the official MCP Registry metadata template for
SourceHarbor.

Use it when you want:

- a current `server.json` draft shaped for the official MCP Registry
- a single place to keep namespace, package, and environment-variable metadata
- a shared canonical profile you can also reuse for `MCP.so`, `PulseMCP`, and `mcpservers.org`
- the real Python package lane that produces `sourceharbor-mcp`
- an honest reminder that MCP Registry publication still depends on a public
  install method and verified namespace ownership

What this is:

- a submission-ready metadata template tied to the root Python package

What this is not:

- proof that SourceHarbor is already published in the official MCP Registry
- proof that the package identifier below is already live on PyPI

Current boundary:

- the official MCP Registry exists
- the repo now has a real Python package + console-script install lane
- the repo now also tracks `config/public/mcp-directory-profile.json` and the public distribution ledger as the shared non-registry directory listing layer
- registry publication still requires live PyPI publish/read-back, namespace
  verification, and an actual registry submission receipt
