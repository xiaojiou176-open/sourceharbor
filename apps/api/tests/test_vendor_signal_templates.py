from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.app.routers import subscriptions as subscriptions_router
from apps.api.app.services.vendor_signal_templates import load_vendor_signal_catalog


def test_vendor_signal_catalog_exposes_official_and_observation_layers() -> None:
    payload = load_vendor_signal_catalog()

    layer_ids = {item["id"] for item in payload["signal_layers"]}
    assert layer_ids == {"confirmed", "observation"}

    vendors = {item["id"]: item for item in payload["vendors"]}
    assert {"openai", "anthropic", "gemini", "xai"} <= set(vendors)

    openai = vendors["openai"]
    assert openai["starter_watchlist"]["matcher_type"] == "source_match"
    assert openai["starter_watchlist"]["matcher_value"] == "openai"
    assert any(
        channel["channel_kind"] == "x_account"
        and channel["signal_layer"] == "observation"
        for channel in openai["channels"]
    )
    assert any(
        channel["channel_kind"] == "changelog"
        and channel["signal_layer"] == "confirmed"
        for channel in openai["channels"]
    )


def test_vendor_signal_router_returns_catalog() -> None:
    app = FastAPI()
    app.include_router(subscriptions_router.router)
    client = TestClient(app)

    response = client.get("/api/v1/subscriptions/vendor-signals")

    assert response.status_code == 200
    payload = response.json()
    assert {item["id"] for item in payload["signal_layers"]} == {
        "confirmed",
        "observation",
    }
    vendors = {item["id"]: item for item in payload["vendors"]}
    assert "openai" in vendors
    assert vendors["openai"]["starter_watchlist"]["name"] == "OpenAI signals"
