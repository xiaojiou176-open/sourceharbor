from __future__ import annotations

import asyncio
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from integrations.providers.rsshub import (
    build_health_url,
    is_risk_control_response,
    parse_feed,
)


class RSSHubFetcher:
    @dataclass
    class _FallbackState:
        ordered_public_bases: list[str]
        last_reordered_at: float = 0.0
        consecutive_failures: dict[str, int] = field(default_factory=dict)
        circuit_open_until: dict[str, float] = field(default_factory=dict)

    _fallback_states: dict[tuple[str, ...], _FallbackState] = {}

    def __init__(
        self,
        timeout_seconds: float = 20.0,
        retry_attempts: int = 2,
        retry_backoff_seconds: float = 0.5,
        public_fallback_base_url: str | None = "https://rsshub.app",
        public_fallback_base_urls: list[str] | None = None,
        fallback_reorder_interval_seconds: int = 10800,
        fallback_probe_timeout_seconds: float = 5.0,
        fallback_probe_path: str = "/bilibili/user/video/1132916",
        fallback_circuit_breaker_threshold: int = 3,
        fallback_circuit_breaker_minutes: int = 30,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._retry_attempts = max(0, retry_attempts)
        self._retry_backoff_seconds = max(0.0, retry_backoff_seconds)
        self._fallback_reorder_interval_seconds = max(0, int(fallback_reorder_interval_seconds))
        self._fallback_probe_timeout_seconds = max(0.1, float(fallback_probe_timeout_seconds))
        self._fallback_probe_path = str(fallback_probe_path or "").strip()
        if self._fallback_probe_path and not self._fallback_probe_path.startswith("/"):
            self._fallback_probe_path = f"/{self._fallback_probe_path}"
        self._fallback_circuit_breaker_threshold = max(1, int(fallback_circuit_breaker_threshold))
        self._fallback_circuit_breaker_minutes = max(1, int(fallback_circuit_breaker_minutes))
        fallback_candidates: list[str] = []
        if public_fallback_base_urls:
            fallback_candidates.extend(public_fallback_base_urls)
        fallback_candidates.append(str(public_fallback_base_url or ""))
        normalized_fallbacks: list[str] = []
        seen_fallbacks: set[str] = set()
        for raw in fallback_candidates:
            item = str(raw or "").strip().rstrip("/")
            if not item or item in seen_fallbacks:
                continue
            seen_fallbacks.add(item)
            normalized_fallbacks.append(item)
        self._public_fallback_base_urls = normalized_fallbacks
        self._fallback_state = self._get_or_init_fallback_state(self._public_fallback_base_urls)
        self._headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
        }

    @classmethod
    def _get_or_init_fallback_state(cls, public_bases: list[str]) -> _FallbackState:
        key = tuple(public_bases)
        state = cls._fallback_states.get(key)
        if state is None:
            state = cls._FallbackState(ordered_public_bases=list(public_bases))
            cls._fallback_states[key] = state
        return state

    @staticmethod
    def _is_bilibili_user_video_url(feed_url: str) -> bool:
        parsed = urlparse(feed_url)
        return "/bilibili/user/video/" in parsed.path

    @staticmethod
    def _with_base_url(feed_url: str, base_url: str) -> str:
        feed = urlparse(feed_url)
        base = urlparse(base_url)
        if not base.scheme or not base.netloc:
            return feed_url
        return urlunparse(feed._replace(scheme=base.scheme, netloc=base.netloc))

    @staticmethod
    def _dedupe_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[str, str, str, str]] = set()
        deduped: list[dict[str, Any]] = []
        for entry in entries:
            key = (
                str(entry.get("guid") or "").strip(),
                str(entry.get("link") or "").strip(),
                str(entry.get("title") or "").strip(),
                str(entry.get("published_at") or "").strip(),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(entry)
        return deduped

    async def _fallback_candidates(
        self,
        *,
        client: httpx.AsyncClient,
        feed_url: str,
    ) -> list[str]:
        candidates: list[str] = [feed_url]
        if self._is_bilibili_user_video_url(feed_url):
            parsed = urlparse(feed_url)
            query_items = parse_qsl(parsed.query, keep_blank_values=True)
            query_dict = dict(query_items)

            # Fallback A: add embed=0 to reduce route-specific anti-bot failures.
            if query_dict.get("embed") != "0":
                with_embed = dict(query_items)
                with_embed["embed"] = "0"
                candidates.append(urlunparse(parsed._replace(query=urlencode(with_embed))))
            else:
                # Fallback B: some UIDs fail on embed=0 but pass on default route.
                without_embed = {k: v for k, v in query_items if k != "embed"}
                candidates.append(urlunparse(parsed._replace(query=urlencode(without_embed))))

        ordered_public_bases = await self._ordered_public_bases(client=client)
        if ordered_public_bases:
            for base_url in ordered_public_bases:
                for primary_candidate in list(candidates):
                    public_candidate = self._with_base_url(primary_candidate, base_url)
                    candidates.append(public_candidate)

        unique_candidates: list[str] = []
        seen_urls: set[str] = set()
        for candidate in candidates:
            if candidate in seen_urls:
                continue
            seen_urls.add(candidate)
            unique_candidates.append(candidate)
        return unique_candidates

    async def _ordered_public_bases(self, *, client: httpx.AsyncClient) -> list[str]:
        if not self._public_fallback_base_urls:
            return []

        now = time.monotonic()
        state = self._fallback_state
        if (
            self._fallback_reorder_interval_seconds == 0
            or now - state.last_reordered_at >= self._fallback_reorder_interval_seconds
        ):
            scored: list[tuple[float, str]] = []
            for base_url in state.ordered_public_bases:
                score = await self._probe_public_base(client=client, base_url=base_url)
                failures = state.consecutive_failures.get(base_url, 0)
                score -= min(3, failures)
                scored.append((score, base_url))
            scored.sort(key=lambda item: item[0], reverse=True)
            state.ordered_public_bases = [base for _, base in scored]
            state.last_reordered_at = now

        return [
            base
            for base in state.ordered_public_bases
            if now >= state.circuit_open_until.get(base, 0.0)
        ]

    async def _probe_public_base(self, *, client: httpx.AsyncClient, base_url: str) -> float:
        score = 0.0
        timeout = httpx.Timeout(self._fallback_probe_timeout_seconds)
        health_url = build_health_url(base_url)
        try:
            response = await client.get(health_url, follow_redirects=True, timeout=timeout)
            if 200 <= response.status_code < 300:
                score += 2.0
            elif response.status_code < 500:
                score += 0.5
            else:
                score -= 1.0
        except Exception:
            score -= 1.0

        if self._fallback_probe_path:
            probe_url = f"{base_url}{self._fallback_probe_path}"
            try:
                response = await client.get(probe_url, follow_redirects=True, timeout=timeout)
                text = response.text or ""
                if response.status_code == 200 and "<rss" in text:
                    score += 3.0
                elif "-352" in text or "风控" in text or "412 Precondition Failed" in text:
                    score -= 0.5
                elif response.status_code < 500:
                    score += 0.25
                else:
                    score -= 1.0
            except Exception:
                score -= 1.0
        return score

    @staticmethod
    def _base_url(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _record_public_success(self, base_url: str) -> None:
        if base_url not in self._fallback_state.ordered_public_bases:
            return
        self._fallback_state.consecutive_failures[base_url] = 0
        self._fallback_state.circuit_open_until.pop(base_url, None)

    def _record_public_failure(self, base_url: str) -> None:
        if base_url not in self._fallback_state.ordered_public_bases:
            return
        failures = self._fallback_state.consecutive_failures.get(base_url, 0) + 1
        self._fallback_state.consecutive_failures[base_url] = failures
        if failures >= self._fallback_circuit_breaker_threshold:
            self._fallback_state.circuit_open_until[base_url] = (
                time.monotonic() + self._fallback_circuit_breaker_minutes * 60
            )

    async def _fetch_one(
        self,
        client: httpx.AsyncClient,
        feed_url: str,
    ) -> list[dict[str, Any]]:
        last_error: Exception | None = None
        for candidate_url in await self._fallback_candidates(client=client, feed_url=feed_url):
            candidate_base = self._base_url(candidate_url)
            is_public_candidate = candidate_base in self._fallback_state.ordered_public_bases
            candidate_succeeded = False
            for attempt in range(self._retry_attempts + 1):
                try:
                    response = await client.get(candidate_url, follow_redirects=True)
                    if response.status_code >= 400:
                        if is_risk_control_response(response):
                            raise httpx.HTTPStatusError(
                                f"risk_control_or_precondition: {response.status_code}",
                                request=response.request,
                                response=response,
                            )
                        response.raise_for_status()
                    candidate_succeeded = True
                    if is_public_candidate:
                        self._record_public_success(candidate_base)
                    return self._dedupe_entries(parse_feed(response.text))
                except httpx.HTTPStatusError as exc:
                    last_error = exc
                    status_code = exc.response.status_code
                    # Retry server errors; for known anti-bot errors, switch candidate route immediately.
                    if status_code < 500 or is_risk_control_response(exc.response):
                        break
                except (httpx.RequestError, ValueError) as exc:
                    last_error = exc

                if attempt >= self._retry_attempts:
                    break
                await asyncio.sleep(self._retry_backoff_seconds * (2**attempt))
            if is_public_candidate and not candidate_succeeded:
                self._record_public_failure(candidate_base)

        if last_error is not None:
            raise last_error
        return []

    async def fetch_many(self, feed_urls: Iterable[str]) -> dict[str, list[dict[str, Any]]]:
        urls = list(feed_urls)
        if not urls:
            return {}

        timeout = httpx.Timeout(self._timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, headers=self._headers) as client:
            tasks = [self._fetch_one(client, url) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        by_feed: dict[str, list[dict[str, Any]]] = {}
        for feed_url, result in zip(urls, results, strict=False):
            if isinstance(result, asyncio.CancelledError):
                raise result
            if isinstance(result, Exception):
                by_feed[feed_url] = []
                continue
            if isinstance(result, BaseException):
                raise result
            by_feed[feed_url] = result
        return by_feed
