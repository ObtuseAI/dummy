"""Responsible fetcher for the scraped-splits tier.

Betting-splits pages are public but their terms generally forbid automated
access; this is the operator's own system and accepted risk (directive
2026-07-18). The contract that makes it responsible lives here: a realistic
identifying header, a per-host minimum interval (splits move slowly -- there
is no reason to hammer), exponential backoff that honours 429/Retry-After, a
short timeout, and FAIL-OPEN behaviour so a scrape error never raises into a
cycle. The network call is injected so every path is testable without a
socket.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 dummy-research/1.0"
)
DEFAULT_TIMEOUT = 12.0
DEFAULT_MIN_INTERVAL = 2.0        # seconds between requests to one host
DEFAULT_MAX_RETRIES = 3


@dataclass
class FetchResult:
    ok: bool
    status: int | None
    text: str | None
    retry_after: float | None = None


# A raw opener: (url, headers, timeout) -> FetchResult. Injected for tests.
Opener = Callable[[str, dict[str, str], float], FetchResult]


def _urllib_opener(url: str, headers: dict[str, str], timeout: float) -> FetchResult:
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return FetchResult(True, getattr(response, "status", 200), body)
    except urllib.error.HTTPError as exc:
        retry_after = None
        try:
            retry_after = float(exc.headers.get("Retry-After")) if exc.headers else None
        except (TypeError, ValueError):
            retry_after = None
        return FetchResult(False, exc.code, None, retry_after)
    except (urllib.error.URLError, OSError, ValueError):
        return FetchResult(False, None, None)


@dataclass
class PoliteFetcher:
    opener: Opener = _urllib_opener
    timeout: float = DEFAULT_TIMEOUT
    min_interval: float = DEFAULT_MIN_INTERVAL
    max_retries: int = DEFAULT_MAX_RETRIES
    now_fn: Callable[[], float] = time.time
    sleep_fn: Callable[[float], None] = time.sleep
    _last_hit: dict[str, float] = field(default_factory=dict)

    def _host(self, url: str) -> str:
        try:
            return url.split("/", 3)[2]
        except IndexError:
            return url

    def _respect_interval(self, host: str) -> None:
        last = self._last_hit.get(host)
        now = self.now_fn()
        if last is not None:
            wait = self.min_interval - (now - last)
            if wait > 0:
                self.sleep_fn(wait)
        self._last_hit[host] = self.now_fn()

    def get_text(self, url: str, *, headers: dict[str, str] | None = None) -> str | None:
        """Fetch a URL as text, with rate limiting and backoff. None on failure
        (fail-open: never raises)."""
        hdrs = {"User-Agent": USER_AGENT, "Accept": "*/*"}
        if headers:
            hdrs.update(headers)
        backoff = 1.0
        for attempt in range(self.max_retries):
            self._respect_interval(self._host(url))
            result = self.opener(url, hdrs, self.timeout)
            if result.ok and result.text is not None:
                return result.text
            # Retry only on rate-limit / server errors; give up on 4xx else.
            if result.status in (429, 500, 502, 503, 504):
                wait = result.retry_after if result.retry_after else backoff
                if attempt < self.max_retries - 1:
                    self.sleep_fn(min(wait, 30.0))
                    backoff *= 2
                    continue
            return None
        return None

    def get_json(self, url: str, *, headers: dict[str, str] | None = None) -> Any | None:
        text = self.get_text(url, headers={"Accept": "application/json", **(headers or {})})
        if text is None:
            return None
        try:
            return json.loads(text)
        except (ValueError, TypeError):
            return None
