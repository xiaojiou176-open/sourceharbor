from __future__ import annotations

import json
from pathlib import Path


def test_mcp_tools_schema_matches_shared_contracts() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    mcp_schema_path = repo_root / "apps/mcp/schemas/tools.json"
    shared_schema_path = repo_root / "contracts/generated/jsonschema/mcp-tools.schema.json"

    mcp_schema = json.loads(mcp_schema_path.read_text(encoding="utf-8"))
    shared_schema = json.loads(shared_schema_path.read_text(encoding="utf-8"))

    assert mcp_schema == shared_schema
