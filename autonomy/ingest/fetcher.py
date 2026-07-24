"""Phase 1: one polite HTTP fetch framework for every history-lake source.

Free public GETs only. Built to be *sustainable* — so a multi-season backfill
never gets us rate-limited or IP-banned — and *idempotent* — so re-running a
backfill costs zero network:

  * on-disk response cache keyed by url+params (a re-run is all cache hits);
  * per-host rate limiting with a minimum interval between real fetches;
  * exponential backoff that honors ``Retry-After`` on 429/503;
  * a descriptive User-Agent; structured provenance + call stats.

Transport, clock, and sleep are injectable so the whole thing is deterministic
under test with no network and no real waiting. Nothing here mutates a remote
or authenticates; bypassing a paywall/login/CAPTCHA is explicitly out of scope.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

DEFAULT_UA = (
    "DummyResearchBot/1.0 (+https://github.com/ObtuseAI/dummy; "
    "read-only public sports data for private research)"
)
_RETRY_STATUSES = (429, 500, 502, 503, 504)
# Named rather than an inline literal in __init__: a fetcher built without an
# explicit cache_dir otherwise created and filled the LIVE ingest cache during
# the test suite.  Value unchanged (repo-root-relative, as before).
DEFAULT_CACHE_DIR = Path("runtime/autonomy/ingest_cache")


@dataclass
class Response:
    status: int
    text: str
    url: str
    from_cache: bool = False
    headers: dict[str, str] | None = None

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


def _default_transport(url: str, params: dict[str, Any] | None, headers: dict[str, str]):
    import httpx

    resp = httpx.get(url, params=params, headers=headers, timeout=30, follow_redirects=True)
    return resp.status_code, resp.text, dict(resp.headers)


class PoliteFetcher:
    def __init__(
        self,
        cache_dir: Path | str | None = None,
        *,
        transport: Callable[..., tuple[int, str, dict[str, str]]] | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        user_agent: str = DEFAULT_UA,
        min_interval: float = 1.5,
        max_retries: int = 4,
        cache_ttl: float | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else Path(DEFAULT_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._transport = transport or _default_transport
        self._clock = clock
        self._sleep = sleep
        self.user_agent = user_agent
        self.min_interval = float(min_interval)
        self.max_retries = int(max_retries)
        self.cache_ttl = cache_ttl
        self._last_call: dict[str, float] = {}
        self.stats = {"calls": 0, "cache_hits": 0, "retries": 0, "errors": 0}

    # ---- cache -----------------------------------------------------------
    def _key(self, url: str, params: dict[str, Any] | None) -> Path:
        raw = url + "?" + json.dumps(params or {}, sort_keys=True)
        return self.cache_dir / (hashlib.sha256(raw.encode()).hexdigest() + ".json")

    def _read_cache(self, key: Path) -> dict[str, Any] | None:
        try:
            blob = json.loads(key.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None
        if self.cache_ttl is not None:
            if (self._clock() - float(blob.get("ts", 0))) > self.cache_ttl:
                return None
        return blob

    def _write_cache(self, key: Path, resp: Response) -> None:
        tmp = key.with_suffix(".tmp")
        tmp.write_text(json.dumps({
            "status": resp.status, "text": resp.text, "headers": resp.headers or {},
            "url": resp.url, "ts": self._clock(),
        }), encoding="utf-8")
        tmp.replace(key)

    # ---- fetch -----------------------------------------------------------
    def get(
        self, url: str, params: dict[str, Any] | None = None, *,
        headers: dict[str, str] | None = None, force: bool = False,
    ) -> Response:
        key = self._key(url, params)
        if not force:
            cached = self._read_cache(key)
            if cached is not None:
                self.stats["cache_hits"] += 1
                return Response(cached["status"], cached["text"], cached.get("url", url),
                                from_cache=True, headers=cached.get("headers"))

        host = urlparse(url).netloc
        req_headers = {"User-Agent": self.user_agent, **(headers or {})}
        attempt = 0
        while True:
            self._respect_rate_limit(host)
            status, text, resp_headers = self._transport(url, params, req_headers)
            self._last_call[host] = self._clock()
            self.stats["calls"] += 1
            resp = Response(status, text, url, from_cache=False, headers=_lower(resp_headers))
            if resp.ok:
                self._write_cache(key, resp)
                return resp
            if status in _RETRY_STATUSES and attempt < self.max_retries:
                self._sleep(self._backoff(resp.headers or {}, attempt))
                self.stats["retries"] += 1
                attempt += 1
                continue
            self.stats["errors"] += 1
            return resp

    def _respect_rate_limit(self, host: str) -> None:
        last = self._last_call.get(host)
        if last is None or self.min_interval <= 0:
            return
        elapsed = self._clock() - last
        if elapsed < self.min_interval:
            self._sleep(self.min_interval - elapsed)

    def _backoff(self, headers: dict[str, str], attempt: int) -> float:
        retry_after = headers.get("retry-after")
        if retry_after is not None:
            try:
                return float(retry_after)
            except (TypeError, ValueError):
                pass
        return min(60.0, self.min_interval * (2 ** attempt) + 0.5)


def _lower(headers: dict[str, str] | None) -> dict[str, str]:
    return {str(k).lower(): str(v) for k, v in (headers or {}).items()}
