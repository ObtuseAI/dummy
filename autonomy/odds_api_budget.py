"""Credit governor for The Odds API (Wave-9).

The licensed slot is a metered resource: the operator's plan is 20,000 credits
per month (measured 2026-07-17: one ``/odds`` call = markets x regions = 3
credits and returns the whole slate; the free ``/sports`` list is 0 credits).
The scanner runs continuously, so a naive fetch-per-cycle loop would exhaust a
month of credits in hours. This governor makes every licensed fetch:

  * TTL-CACHED across cycles (persisted to runtime/autonomy/odds_api_cache/),
    so a sport is pulled at most once per ``ttl`` regardless of cycle rate;
  * BUDGETED against a daily cap (default 500/day ≈ 15k/month, buffer under
    the plan) AND the live ``x-requests-remaining`` header the API returns;
  * IN-SEASON GATED — only sports the free ``/sports`` list marks active are
    ever spent on (an offseason league still costs 3 credits per empty call);
  * FAIL-CLOSED — no budget and no fresh cache yields stale cache if any
    exists, else nothing. The governor never blows past the cap.

Deterministic and injectable (clock, fetch, paths) so the whole policy is
unit-tested without a network or a wall clock.

Wave-12 adds the PAYLOAD ARCHIVE: every PAID live fetch is appended to a
gzip-compressed monthly JSONL shard before the TTL cache eventually discards
it. Historical odds cost extra money on the API, so the archive is the only
record of data already paid for; it is what lets a future de-vig variant, steam
detector, or multi-book CLV anchor regrade HISTORY instead of waiting weeks of
wall clock for new evidence. Strictly fail-open: an archive error never
disturbs the fetch path. Free endpoints (cost 0) are re-fetchable and skipped.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

RUNTIME_DIR = Path("runtime/autonomy")
BUDGET_PATH = RUNTIME_DIR / "odds_api_budget.json"
CACHE_DIR = RUNTIME_DIR / "odds_api_cache"
ARCHIVE_DIR = RUNTIME_DIR / "odds_api_archive"
# Operator override for the archive location (e.g. a roomier drive on the live
# box). The archive is append-only telemetry, safe to relocate at any time.
ARCHIVE_DIR_ENV = "DUMMY_ODDS_ARCHIVE_DIR"

# Wave-31 rebalance. The 20k/month plan is ~645 credits/day; the old 500 cap
# left the plan under-used AND, worse, was consumed early each day by per-event
# player-prop fetches -- starving the game-line feed the line-movement pipeline
# depends on. Two fixes: raise the daily cap into the plan, and RESERVE a slice
# of it for the game-line ("line") class so prop fetches can never exhaust the
# feed. A monthly cap guards the plan so raising the daily number can't overrun
# it. All three are env-tunable on the live box.
DEFAULT_DAILY_CREDITS = 640          # ≈ 19.8k/month, just under the 20k plan
# Default reserve is a FRACTION of the resolved daily cap so it scales if the
# cap is retuned; an absolute override via LINE_RESERVE_ENV wins.
DEFAULT_LINE_RESERVE_FRACTION = 0.4  # 40% of the day reserved for game lines
DEFAULT_MONTHLY_CREDITS = 20000      # the plan ceiling; never overrun it
DAILY_CREDITS_ENV = "DUMMY_ODDS_DAILY_CREDITS"
LINE_RESERVE_ENV = "DUMMY_ODDS_LINE_RESERVE"
MONTHLY_CREDITS_ENV = "DUMMY_ODDS_MONTHLY_CREDITS"
# Fetch classes for the reservation. "line" = the game-line slate (the movement
# feed); everything else (props) yields the reserved slice to it.
LINE_CLASS = "line"

DEFAULT_TTL_SECONDS = 1200           # 20 min: a sport is pulled at most 3x/hr
ODDS_CALL_COST = 3                   # markets(h2h,totals,spreads) x regions(us)
SPORTS_LIST_TTL_SECONDS = 6 * 3600   # in-season set changes slowly; cache 6h


def _env_int(name: str, default: int) -> int:
    """Positive-int env override, else the default (fail-safe on garbage)."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
        return value if value >= 0 else default
    except (TypeError, ValueError):
        return default


@dataclass
class BudgetState:
    day: str
    spent_today: int
    month: str
    spent_month: int
    remaining_reported: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day, "spent_today": self.spent_today,
            "month": self.month, "spent_month": self.spent_month,
            "remaining_reported": self.remaining_reported,
        }


class OddsApiBudget:
    def __init__(
        self,
        *,
        daily_credits: int | None = None,
        line_reserve: int | None = None,
        monthly_credits: int | None = None,
        budget_path: Path | None = None,
        cache_dir: Path | None = None,
        archive_dir: Path | None = None,
        now_fn: Callable[[], float] | None = None,
    ) -> None:
        # Explicit args win (tests); otherwise the env override, else the
        # default. The reserve is clamped below the cap so props always keep a
        # positive ceiling.
        self.daily_credits = int(
            daily_credits if daily_credits is not None
            else _env_int(DAILY_CREDITS_ENV, DEFAULT_DAILY_CREDITS))
        self.monthly_credits = int(
            monthly_credits if monthly_credits is not None
            else _env_int(MONTHLY_CREDITS_ENV, DEFAULT_MONTHLY_CREDITS))
        proportional = int(DEFAULT_LINE_RESERVE_FRACTION * self.daily_credits)
        reserve = int(
            line_reserve if line_reserve is not None
            else _env_int(LINE_RESERVE_ENV, proportional))
        self.line_reserve = max(0, min(reserve, self.daily_credits))
        self.budget_path = Path(budget_path or BUDGET_PATH)
        self.cache_dir = Path(cache_dir or CACHE_DIR)
        env_archive = os.environ.get(ARCHIVE_DIR_ENV)
        self.archive_dir = Path(
            archive_dir if archive_dir is not None
            else (env_archive or ARCHIVE_DIR))
        self._now = now_fn or time.time

    # -- clock helpers ---------------------------------------------------------

    def _day_key(self) -> str:
        return time.strftime("%Y-%m-%d", time.gmtime(self._now()))

    def _month_key(self) -> str:
        return time.strftime("%Y-%m", time.gmtime(self._now()))

    # -- budget state ----------------------------------------------------------

    def _load(self) -> BudgetState:
        raw: dict[str, Any] = {}
        if self.budget_path.exists():
            try:
                raw = json.loads(self.budget_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, ValueError):
                raw = {}
        day, month = self._day_key(), self._month_key()
        state = BudgetState(
            day=raw.get("day", day),
            spent_today=int(raw.get("spent_today", 0)),
            month=raw.get("month", month),
            spent_month=int(raw.get("spent_month", 0)),
            remaining_reported=raw.get("remaining_reported"),
        )
        # Roll the day / month counters when the clock advances.
        if state.day != day:
            state.day, state.spent_today = day, 0
        if state.month != month:
            state.month, state.spent_month = month, 0
        return state

    def _save(self, state: BudgetState) -> None:
        self.budget_path.parent.mkdir(parents=True, exist_ok=True)
        self.budget_path.write_text(
            json.dumps(state.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    def _daily_ceiling(self, reserve_class: str) -> int:
        """The game-line class may spend the whole day; every other class
        stops at the cap minus the reserved line slice."""
        if reserve_class == LINE_CLASS:
            return self.daily_credits
        return self.daily_credits - self.line_reserve

    def status(self) -> dict[str, Any]:
        state = self._load()
        return {
            **state.to_dict(),
            "daily_credits": self.daily_credits,
            "daily_remaining": max(0, self.daily_credits - state.spent_today),
            "line_reserve": self.line_reserve,
            "prop_remaining": max(
                0, self._daily_ceiling("prop") - state.spent_today),
            "monthly_credits": self.monthly_credits,
            "monthly_remaining": max(0, self.monthly_credits - state.spent_month),
        }

    def can_spend(self, cost: int, reserve_class: str = "other") -> bool:
        state = self._load()
        if state.spent_today + cost > self._daily_ceiling(reserve_class):
            return False
        if state.spent_month + cost > self.monthly_credits:
            return False
        if state.remaining_reported is not None and state.remaining_reported < cost:
            return False
        return True

    def record_spend(self, cost: int, remaining_header: int | None = None) -> None:
        state = self._load()
        state.spent_today += cost
        state.spent_month += cost
        if remaining_header is not None:
            state.remaining_reported = int(remaining_header)
        elif state.remaining_reported is not None:
            state.remaining_reported = max(0, state.remaining_reported - cost)
        self._save(state)

    # -- TTL cache -------------------------------------------------------------

    def _cache_path(self, cache_key: str) -> Path:
        digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()[:24]
        return self.cache_dir / f"{digest}.json"

    def cache_get(self, cache_key: str, ttl: float) -> tuple[Any, bool] | None:
        """(payload, is_fresh) or None when nothing is cached."""
        path = self._cache_path(cache_key)
        if not path.exists():
            return None
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            return None
        age = self._now() - float(entry.get("fetched_at", 0))
        return entry.get("payload"), age <= ttl

    def cache_put(self, cache_key: str, payload: Any) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_path(cache_key).write_text(
            json.dumps({"fetched_at": self._now(), "payload": payload}, sort_keys=True),
            encoding="utf-8")

    # -- payload archive (Wave-12) ---------------------------------------------

    def _archive_path(self) -> Path:
        month = time.strftime("%Y-%m", time.gmtime(self._now()))
        return self.archive_dir / f"odds_{month}.jsonl.gz"

    def archive_payload(self, cache_key: str, payload: Any, remaining: int | None) -> None:
        """Append one paid fetch to the monthly gzip shard. FAIL-OPEN: the
        archive is telemetry; no exception may ever reach the fetch path."""
        try:
            self.archive_dir.mkdir(parents=True, exist_ok=True)
            line = json.dumps({
                "ts": self._now(),
                "key": cache_key,
                "remaining": remaining,
                "payload": payload,
            }, sort_keys=True)
            # "at" appends a fresh gzip member; concatenated members are a
            # valid gzip stream, so shards stay readable with one gzip.open.
            with gzip.open(self._archive_path(), "at", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except Exception:
            pass

    # -- the governed fetch ----------------------------------------------------

    def budgeted_fetch(
        self,
        cache_key: str,
        fetch_fn: Callable[[], tuple[Any, int | None]],
        *,
        cost: int = ODDS_CALL_COST,
        ttl: float = DEFAULT_TTL_SECONDS,
        reserve_class: str = "other",
    ) -> tuple[Any, str]:
        """Return (payload, source) where source is one of
        ``cache`` | ``live`` | ``stale`` | ``budget_exhausted`` | ``error``.

        ``fetch_fn`` returns ``(payload, remaining_header_or_None)``; it is
        called ONLY when a fresh cache miss coincides with available budget.
        ``reserve_class`` gates against the class ceiling: the game-line class
        (``LINE_CLASS``) may spend the full daily cap, props stop at the cap
        minus the reserved line slice so the movement feed never starves.
        """
        cached = self.cache_get(cache_key, ttl)
        if cached is not None and cached[1]:
            return cached[0], "cache"
        if self.can_spend(cost, reserve_class):
            try:
                payload, remaining = fetch_fn()
            except Exception:
                if cached is not None:
                    return cached[0], "stale"
                return None, "error"
            self.record_spend(cost, remaining)
            self.cache_put(cache_key, payload)
            if cost > 0:
                # Paid data is not re-fetchable without buying it again;
                # archive it. Free endpoints (cost 0) are skipped.
                self.archive_payload(cache_key, payload, remaining)
            return payload, "live"
        if cached is not None:
            return cached[0], "stale"
        return None, "budget_exhausted"
