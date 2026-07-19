"""Phase 1: the polite fetch framework — cache, per-host rate limit, backoff.

All deterministic: the transport, clock, and sleep are injected, so no test
ever touches the network or a real wall clock.
"""
from __future__ import annotations

from autonomy.ingest.fetcher import PoliteFetcher


class FakeTransport:
    def __init__(self, script):
        self.script = list(script)      # list of (status, text, headers)
        self.calls = []

    def __call__(self, url, params, headers):
        self.calls.append((url, params))
        return self.script.pop(0)


def test_caches_and_rate_limits(tmp_path):
    now = [1000.0]
    slept = []

    def sleep(s):
        slept.append(s)
        now[0] += s

    tr = FakeTransport([(200, "A", {}), (200, "B", {})])
    f = PoliteFetcher(cache_dir=tmp_path, transport=tr, clock=lambda: now[0], sleep=sleep, min_interval=2.0)

    r1 = f.get("http://x/a")
    assert r1.text == "A" and r1.from_cache is False
    # same url -> served from cache: no transport call, no sleep
    r1b = f.get("http://x/a")
    assert r1b.text == "A" and r1b.from_cache is True
    assert len(tr.calls) == 1 and slept == []
    # different url, same host -> rate-limited before the real fetch
    r2 = f.get("http://x/b")
    assert r2.text == "B"
    assert slept and slept[0] >= 2.0 - 1e-9
    assert f.stats["cache_hits"] == 1 and f.stats["calls"] == 2


def test_backoff_honors_retry_after(tmp_path):
    slept = []
    tr = FakeTransport([(429, "", {"Retry-After": "5"}), (200, "OK", {})])
    f = PoliteFetcher(cache_dir=tmp_path, transport=tr, clock=lambda: 0.0,
                      sleep=lambda s: slept.append(s), min_interval=0.0)
    r = f.get("http://x/a")
    assert r.status == 200 and r.text == "OK"
    assert 5 in slept                      # honored Retry-After
    assert f.stats["retries"] >= 1


def test_gives_up_after_max_retries(tmp_path):
    tr = FakeTransport([(503, "", {})] * 6)
    f = PoliteFetcher(cache_dir=tmp_path, transport=tr, clock=lambda: 0.0,
                      sleep=lambda s: None, min_interval=0.0, max_retries=3)
    r = f.get("http://x/a")
    assert r.status == 503 and r.ok is False
    assert len(tr.calls) == 4               # initial + 3 retries
