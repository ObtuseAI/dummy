"""Governed splits aggregation.

Ties the pieces together for the signal: on a cycle it refreshes every armed
provider for the leagues in play (cache-first so a fire does not re-scrape,
each fetch archived to build proprietary history), indexes the reads by an
unordered normalized team pair (so home/away naming differences across sources
still match), and answers ``splits_for(home, away)`` with an
intelligently-weighted FusedSplits. Inert unless DUMMY_SPLITS_ENABLED=1;
fail-open throughout.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Callable

from autonomy.market_pressure.splits.fetch import PoliteFetcher
from autonomy.market_pressure.splits.model import FusedSplits, SplitsRead, combine_splits
from autonomy.market_pressure.splits.providers import (
    SplitsProvider,
    default_providers,
    normalize_team,
)

ENABLED_ENV = "DUMMY_SPLITS_ENABLED"
DEFAULT_TTL_SECONDS = 12 * 60.0        # splits move slowly; 12 min between scrapes
RUNTIME_DIR = Path("runtime/autonomy")
CACHE_DIR = RUNTIME_DIR / "splits_cache"
ARCHIVE_DIR = RUNTIME_DIR / "splits_archive"


def is_armed(env: dict[str, str] | None = None) -> bool:
    e = env if env is not None else os.environ
    return e.get(ENABLED_ENV) == "1"


def _pair_key(home: str, away: str) -> frozenset[str]:
    return frozenset({normalize_team(home), normalize_team(away)})


class SplitsService:
    def __init__(
        self,
        *,
        providers: list[SplitsProvider] | None = None,
        fetcher: PoliteFetcher | None = None,
        enabled: bool | None = None,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        cache_dir: Path | None = None,
        archive_dir: Path | None = None,
        now_fn: Callable[[], float] = time.time,
    ) -> None:
        self.providers = providers if providers is not None else default_providers()
        self.fetcher = fetcher or PoliteFetcher()
        self.enabled = is_armed() if enabled is None else enabled
        self.ttl_seconds = ttl_seconds
        self.cache_dir = cache_dir if cache_dir is not None else CACHE_DIR
        self.archive_dir = archive_dir if archive_dir is not None else ARCHIVE_DIR
        self._now = now_fn
        self._index: dict[frozenset[str], list[SplitsRead]] = {}

    # -- cache (fire-and-exit safe) -------------------------------------------

    def _cache_path(self, provider: str, league: str) -> Path:
        digest = hashlib.sha256(f"{provider}|{league}".encode()).hexdigest()[:20]
        return self.cache_dir / f"{digest}.json"

    def _cache_get(self, provider: str, league: str) -> list[SplitsRead] | None:
        path = self._cache_path(provider, league)
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if self._now() - float(entry.get("fetched_at", 0)) > self.ttl_seconds:
            return None
        return [SplitsRead(**row) for row in entry.get("reads", [])]

    def _cache_put(self, provider: str, league: str, reads: list[SplitsRead]) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._cache_path(provider, league).write_text(
                json.dumps({"fetched_at": self._now(),
                            "reads": [r.__dict__ for r in reads]}, sort_keys=True),
                encoding="utf-8")
        except OSError:
            pass

    def _archive(self, provider: str, league: str, reads: list[SplitsRead]) -> None:
        if not reads:
            return
        try:
            self.archive_dir.mkdir(parents=True, exist_ok=True)
            month = time.strftime("%Y-%m", time.gmtime(self._now()))
            line = json.dumps({"ts": self._now(), "provider": provider, "league": league,
                               "reads": [r.__dict__ for r in reads]}, sort_keys=True)
            with gzip.open(self.archive_dir / f"splits_{month}.jsonl.gz", "at",
                           encoding="utf-8") as fh:
                fh.write(line + "\n")
        except Exception:
            pass

    # -- refresh + query ------------------------------------------------------

    def refresh(self, leagues: list[str]) -> int:
        """Populate the per-game index for these leagues. Returns games indexed.
        No-op (empty index) when unarmed."""
        self._index = {}
        if not self.enabled:
            return 0
        now = self._now()
        for league in leagues:
            for provider in self.providers:
                reads = self._cache_get(provider.name, league)
                if reads is None:
                    try:
                        reads = provider.fetch(league, self.fetcher, now=now)
                    except Exception:
                        reads = []
                    self._cache_put(provider.name, league, reads)
                    self._archive(provider.name, league, reads)
                for read in reads:
                    self._index.setdefault(_pair_key(read.home_team, read.away_team), []).append(read)
        return len(self._index)

    def splits_for(self, home: str, away: str) -> FusedSplits:
        """Fused splits for one game (empty when unarmed / unmatched). The
        returned read is oriented to the caller's ``home``: if the matched
        sources listed the teams the other way round, sides are flipped."""
        reads = self._index.get(_pair_key(home, away))
        if not reads:
            return combine_splits([], now=self._now())
        target = normalize_team(home)
        oriented = [r if normalize_team(r.home_team) == target else _flip(r) for r in reads]
        return combine_splits(oriented, now=self._now())


def _flip(read: SplitsRead) -> SplitsRead:
    """Swap home/away so a source that listed the game the other way lines up."""
    return SplitsRead(
        source=read.source, home_team=read.away_team, away_team=read.home_team,
        home_ticket_pct=read.away_ticket_pct, away_ticket_pct=read.home_ticket_pct,
        home_money_pct=read.away_money_pct, away_money_pct=read.home_money_pct,
        as_of=read.as_of, market=read.market)
