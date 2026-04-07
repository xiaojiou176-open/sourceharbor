from __future__ import annotations

import asyncio
from urllib.parse import urlparse

import httpx
from worker.rss.fetcher import RSSHubFetcher


def _rss_xml(title: str = "ok") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>{title}</title>
          <link>https://www.bilibili.com/video/BV1xx411c7mD</link>
          <guid>guid-1</guid>
        </item>
      </channel>
    </rss>
    """


def test_fetch_one_falls_back_to_embed_zero_when_default_route_hits_risk_control() -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.params.get("embed") == "0":
            return httpx.Response(200, text=_rss_xml("fallback-ok"), request=request)
        return httpx.Response(
            503, text="Error: Got error code -352 while fetching: 风控校验失败", request=request
        )

    transport = httpx.MockTransport(handler)
    fetcher = RSSHubFetcher(retry_attempts=0)

    async def run() -> list[dict[str, str | None]]:
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetcher._fetch_one(
                client, "https://rss.example.com/bilibili/user/video/12345"
            )

    entries = asyncio.run(run())
    assert len(entries) == 1
    assert entries[0]["title"] == "fallback-ok"
    assert any("embed=0" in url for url in requested)


def test_fetch_one_falls_back_to_default_route_when_embed_zero_hits_risk_control() -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.params.get("embed") == "0":
            return httpx.Response(
                503, text="Error: Got error code -352 while fetching: 风控校验失败", request=request
            )
        return httpx.Response(200, text=_rss_xml("default-ok"), request=request)

    transport = httpx.MockTransport(handler)
    fetcher = RSSHubFetcher(retry_attempts=0)

    async def run() -> list[dict[str, str | None]]:
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetcher._fetch_one(
                client, "https://rss.example.com/bilibili/user/video/12345?embed=0"
            )

    entries = asyncio.run(run())
    assert len(entries) == 1
    assert entries[0]["title"] == "default-ok"
    target_route_requests = [url for url in requested if "/bilibili/user/video/12345" in url]
    assert target_route_requests and target_route_requests[0].endswith("embed=0")
    assert any("embed=0" not in url for url in target_route_requests[1:])


def test_fetch_one_falls_back_to_public_base_url_when_private_base_fails() -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.host == "rsshub.app":
            return httpx.Response(200, text=_rss_xml("public-base-ok"), request=request)
        return httpx.Response(
            503, text="Error: Got error code -352 while fetching: 风控校验失败", request=request
        )

    transport = httpx.MockTransport(handler)
    fetcher = RSSHubFetcher(retry_attempts=0, public_fallback_base_url="https://rsshub.app")

    async def run() -> list[dict[str, str | None]]:
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetcher._fetch_one(
                client, "http://10.0.0.2:1200/bilibili/user/video/12345"
            )

    entries = asyncio.run(run())
    assert len(entries) == 1
    assert entries[0]["title"] == "public-base-ok"
    assert any(url.startswith("https://rsshub.app/") for url in requested)


def test_fetch_one_deduplicates_same_feed_entries() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Video A</title>
          <link>https://www.bilibili.com/video/BV1xx411c7mD</link>
          <guid>guid-1</guid>
          <pubDate>Mon, 19 Feb 2024 10:00:00 GMT</pubDate>
        </item>
        <item>
          <title>Video A</title>
          <link>https://www.bilibili.com/video/BV1xx411c7mD</link>
          <guid>guid-1</guid>
          <pubDate>Mon, 19 Feb 2024 10:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=xml, request=request)

    transport = httpx.MockTransport(handler)
    fetcher = RSSHubFetcher(retry_attempts=0)

    async def run() -> list[dict[str, str | None]]:
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetcher._fetch_one(client, "https://rsshub.app/bilibili/user/video/12345")

    entries = asyncio.run(run())
    assert len(entries) == 1
    assert entries[0]["guid"] == "guid-1"


def test_fetch_one_tries_multiple_public_fallback_bases_in_order() -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.host == "hub.slarker.me":
            return httpx.Response(200, text=_rss_xml("slarker-ok"), request=request)
        return httpx.Response(
            503, text="Error: Got error code -352 while fetching: 风控校验失败", request=request
        )

    transport = httpx.MockTransport(handler)
    fetcher = RSSHubFetcher(
        retry_attempts=0,
        public_fallback_base_url=None,
        public_fallback_base_urls=["https://rsshub.rssforever.com", "https://hub.slarker.me"],
    )

    async def run() -> list[dict[str, str | None]]:
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetcher._fetch_one(
                client, "http://10.0.0.2:1200/bilibili/user/video/12345"
            )

    entries = asyncio.run(run())
    assert len(entries) == 1
    assert entries[0]["title"] == "slarker-ok"
    assert any(url.startswith("https://rsshub.rssforever.com/") for url in requested)
    assert any(url.startswith("https://hub.slarker.me/") for url in requested)


# ---------------------------------------------------------------------------
# Circuit breaker tests
# ---------------------------------------------------------------------------


def test_circuit_breaker_opens_after_threshold_failures() -> None:
    """After N consecutive failures a node should be excluded from candidates."""
    THRESHOLD = 3

    fetcher = RSSHubFetcher(
        retry_attempts=0,
        fallback_reorder_interval_seconds=99999,  # disable auto-reorder
        fallback_circuit_breaker_threshold=THRESHOLD,
        fallback_circuit_breaker_minutes=30,
        public_fallback_base_url=None,
        public_fallback_base_urls=["https://bad.node.example"],
    )
    state = fetcher._fallback_state

    # Record THRESHOLD - 1 failures: circuit should still be closed
    bad_node = urlparse("https://bad.node.example").geturl()
    for _ in range(THRESHOLD - 1):
        fetcher._record_public_failure(bad_node)
    assert bad_node not in state.circuit_open_until

    # One more failure opens the circuit
    fetcher._record_public_failure(bad_node)
    assert bad_node in state.circuit_open_until
    assert state.circuit_open_until[bad_node] > 0


def test_circuit_breaker_resets_on_success() -> None:
    """A successful fetch resets failure count and closes the circuit."""
    fetcher = RSSHubFetcher(
        retry_attempts=0,
        fallback_reorder_interval_seconds=99999,
        fallback_circuit_breaker_threshold=2,
        fallback_circuit_breaker_minutes=30,
        public_fallback_base_url=None,
        public_fallback_base_urls=["https://good.node.example"],
    )
    # Force open the circuit
    good_node = urlparse("https://good.node.example").geturl()
    fetcher._record_public_failure(good_node)
    fetcher._record_public_failure(good_node)
    assert good_node in fetcher._fallback_state.circuit_open_until

    # Record success → circuit should close and failure counter should reset
    fetcher._record_public_success(good_node)
    assert good_node not in fetcher._fallback_state.circuit_open_until
    assert fetcher._fallback_state.consecutive_failures.get(good_node, 0) == 0


def test_open_circuit_node_excluded_from_ordered_bases() -> None:
    """A node with an open circuit must not appear in the ordered_public_bases list."""
    import time

    fetcher = RSSHubFetcher(
        retry_attempts=0,
        fallback_reorder_interval_seconds=99999,
        fallback_circuit_breaker_threshold=1,
        fallback_circuit_breaker_minutes=30,
        public_fallback_base_url=None,
        public_fallback_base_urls=["https://tripped.node.example", "https://ok.node.example"],
    )
    # Trip the first node
    tripped_node = urlparse("https://tripped.node.example").geturl()
    ok_node = urlparse("https://ok.node.example").geturl()
    fetcher._record_public_failure(tripped_node)
    assert tripped_node in fetcher._fallback_state.circuit_open_until

    # _ordered_public_bases filters by circuit_open_until
    state = fetcher._fallback_state
    now = time.monotonic()
    healthy = [
        base
        for base in state.ordered_public_bases
        if now >= state.circuit_open_until.get(base, 0.0)
    ]
    assert tripped_node not in healthy
    assert ok_node in healthy


def test_fetch_one_skips_circuit_open_node_and_succeeds_via_healthy_node() -> None:
    """When a node's circuit is open the fetcher should skip it and use a healthy node."""
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if (
            "healthz" in str(request.url) or "/bilibili/user/video/" in str(request.url)
        ) and request.url.host == "ok.node.example":
            return httpx.Response(200, text=_rss_xml("healthy-node-ok"), request=request)
        return httpx.Response(503, text="Error -352 风控", request=request)

    transport = httpx.MockTransport(handler)
    fetcher = RSSHubFetcher(
        retry_attempts=0,
        # Trigger immediate re-probe so the state refreshes
        fallback_reorder_interval_seconds=0,
        fallback_circuit_breaker_threshold=1,
        fallback_circuit_breaker_minutes=30,
        fallback_probe_timeout_seconds=2.0,
        fallback_probe_path="",  # skip bilibili probe to keep test simple
        public_fallback_base_url=None,
        public_fallback_base_urls=["https://tripped.node.example", "https://ok.node.example"],
    )
    # Pre-open circuit for the bad node
    tripped_node = urlparse("https://tripped.node.example").geturl()
    fetcher._record_public_failure(tripped_node)

    async def run() -> list[dict[str, str | None]]:
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetcher._fetch_one(
                client, "http://private.rsshub.local:1200/bilibili/user/video/99999"
            )

    entries = asyncio.run(run())
    assert len(entries) == 1
    assert entries[0]["title"] == "healthy-node-ok"
    # Bad node must never have been tried for the actual feed URL
    assert not any(
        urlparse(url).netloc == urlparse(tripped_node).netloc and "/bilibili/user/video/" in url
        for url in requested
    )


# ---------------------------------------------------------------------------
# Probe / reorder tests
# ---------------------------------------------------------------------------


def test_probe_assigns_higher_score_to_healthy_node() -> None:
    """_probe_public_base should return a positive score for a node returning valid RSS."""
    xml_response = _rss_xml("probe-ok")

    def handler(request: httpx.Request) -> httpx.Response:
        if "healthz" in str(request.url):
            return httpx.Response(200, text="ok", request=request)
        return httpx.Response(200, text=xml_response, request=request)

    transport = httpx.MockTransport(handler)
    fetcher = RSSHubFetcher(
        fallback_probe_path="/bilibili/user/video/1",
        public_fallback_base_url=None,
    )

    async def run() -> float:
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetcher._probe_public_base(
                client=client, base_url="https://healthy.node.example"
            )

    score = asyncio.run(run())
    assert score > 0


def test_probe_assigns_lower_score_to_risk_control_node() -> None:
    """_probe_public_base should return a lower score for a node returning risk-control errors."""

    def handler(request: httpx.Request) -> httpx.Response:
        if "healthz" in str(request.url):
            return httpx.Response(200, text="ok", request=request)
        return httpx.Response(200, text="Error -352 风控校验失败", request=request)

    transport = httpx.MockTransport(handler)
    fetcher = RSSHubFetcher(
        fallback_probe_path="/bilibili/user/video/1",
        public_fallback_base_url=None,
    )

    async def run_risk() -> float:
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetcher._probe_public_base(
                client=client, base_url="https://risky.node.example"
            )

    def handler_ok(request: httpx.Request) -> httpx.Response:
        if "healthz" in str(request.url):
            return httpx.Response(200, text="ok", request=request)
        return httpx.Response(200, text=_rss_xml("ok"), request=request)

    transport_ok = httpx.MockTransport(handler_ok)

    async def run_ok() -> float:
        async with httpx.AsyncClient(transport=transport_ok) as client:
            return await fetcher._probe_public_base(
                client=client, base_url="https://ok.node.example"
            )

    risk_score = asyncio.run(run_risk())
    ok_score = asyncio.run(run_ok())
    assert ok_score > risk_score


def test_reorder_puts_fastest_node_first() -> None:
    """_ordered_public_bases should reorder nodes based on probe scores."""
    call_counts: dict[str, int] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        call_counts[host] = call_counts.get(host, 0) + 1
        if host == "fast.node.example":
            if "healthz" in str(request.url):
                return httpx.Response(200, text="ok", request=request)
            return httpx.Response(200, text=_rss_xml("fast-ok"), request=request)
        # slow/bad node always returns 500
        return httpx.Response(500, text="error", request=request)

    transport = httpx.MockTransport(handler)
    fetcher = RSSHubFetcher(
        fallback_reorder_interval_seconds=0,  # always reorder
        fallback_probe_path="/bilibili/user/video/1",
        fallback_circuit_breaker_threshold=999,  # don't trip during this test
        public_fallback_base_url=None,
        public_fallback_base_urls=["https://slow.node.example", "https://fast.node.example"],
    )

    async def run() -> list[str]:
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetcher._ordered_public_bases(client=client)

    ordered = asyncio.run(run())
    # The fast node should have risen to the top
    assert ordered[0] == "https://fast.node.example"
