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
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

RUNTIME_DIR = Path("runtime/autonomy")
BUDGET_PATH = RUNTIME_DIR / "odds_api_budget.json"
CACHE_DIR = RUNTIME_DIR / "odds_api_cache"

DEFAULT_DAILY_CREDITS = 500          # ≈ 15k/month; buffer under a 20k plan
DEFAULT_TTL_SECONDS = 1200           # 20 min: a sport is pulled at most 3x/hr
ODDS_CALL_COST = 3                   # markets(h2h,totals,spreads) x regions(us)
SPORTS_LIST_TTL_SECONDS = 6 * 3600   # in-season set changes slowly; cache 6h


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
        daily_credits: int = DEFAULT_DAILY_CREDITS,
        budget_path: Path | None = None,
        cache_dir: Path | None = None,
        now_fn: Callable[[], float] | None = None,
    ) -> None:
        self.daily_credits = int(daily_credits)
        self.budget_path = Path(budget_path or BUDGET_PATH)
        self.cache_dir = Path(cache_dir or CACHE_DIR)
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

    def status(self) -> dict[str, Any]:
        state = self._load()
        return {
            **state.to_dict(),
            "daily_credits": self.daily_credits,
            "daily_remaining": max(0, self.daily_credits - state.spent_today),
        }

    def can_spend(self, cost: int) -> bool:
        state = self._load()
        if state.spent_today + cost > self.daily_credits:
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

    # -- the governed fetch ----------------------------------------------------

    def budgeted_fetch(
        self,
        cache_key: str,
        fetch_fn: Callable[[], tuple[Any, int | None]],
        *,
        cost: int = ODDS_CALL_COST,
        ttl: float = DEFAULT_TTL_SECONDS,
    ) -> tuple[Any, str]:
        """Return (payload, source) where source is one of
        ``cache`` | ``live`` | ``stale`` | ``budget_exhausted`` | ``error``.

        ``fetch_fn`` returns ``(payload, remaining_header_or_None)``; it is
        called ONLY when a fresh cache miss coincides with available budget.
        """
        cached = self.cache_get(cache_key, ttl)
        if cached is not None and cached[1]:
            return cached[0], "cache"
        if self.can_spend(cost):
            try:
                payload, remaining = fetch_fn()
            except Exception:
                if cached is not None:
                    return cached[0], "stale"
                return None, "error"
            self.record_spend(cost, remaining)
            self.cache_put(cache_key, payload)
            return payload, "live"
        if cached is not None:
            return cached[0], "stale"
        return None, "budget_exhausted"
