"""Season auto-gating: leagues wake for preseason and sleep after postseason.

Operator directive 2026-07-12: build every league engine now and switch the
subagents on/off automatically around their seasons.

No hardcoded calendar (calendars rot). A league is ACTIVE when ESPN's
scoreboard shows ANY game inside a -LOOKBACK/+LOOKAHEAD day window around
now. Preseason games appear on the scoreboard weeks ahead, so a league
auto-wakes before its first exhibition; after the last postseason game
drifts out of the lookback the league auto-sleeps. Verdicts are cached with
a TTL and persisted so restarts remember.

Failure discipline: the gate exists for efficiency and health truth, not
capital safety (challenger-only + fail-closed already guard capital). The
check therefore uses the RAISING scoreboard read (``games_or_raise``) so a
dead feed is distinguishable from an empty offseason scoreboard: on error
the last known verdict is kept (sticky), and a league never checked
successfully defaults to ACTIVE -- wrongly-active wastes one warmup,
wrongly-dormant would silence a live league for hours.

There is deliberately NO wake backfill: at a genuine wake the league is
coming out of an offseason with no completed games behind it, and after a
false-dormant blip (bounded by the TTL) the signals' own recent-days
warmup window covers everything missed. Full-year rebuilds remain with
scripts/run_dummy_sports_model_warmup.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

LOOKBACK_DAYS = 7
LOOKAHEAD_DAYS = 21
CHECK_TTL_HOURS = 6.0
STATE_PATH = Path("runtime/autonomy/season_state.json")


class SeasonMonitor:
    """ESPN-scoreboard-driven per-league season activity."""

    def __init__(
        self,
        espn: Any = None,
        state_path: Path | None = None,
        now_fn: Callable[[], datetime] | None = None,
        lookback_days: int = LOOKBACK_DAYS,
        lookahead_days: int = LOOKAHEAD_DAYS,
        ttl_hours: float = CHECK_TTL_HOURS,
    ) -> None:
        if espn is None:
            from autonomy.sports.espn import EspnClient

            espn = EspnClient()
        self.espn = espn
        self.state_path = state_path or STATE_PATH
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self.lookback_days = lookback_days
        self.lookahead_days = lookahead_days
        self.ttl_hours = ttl_hours
        self._state: dict[str, dict[str, Any]] = self._load()

    # -- persistence -----------------------------------------------------
    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (OSError, json.JSONDecodeError, ValueError):
            return {}

    def _save(self) -> None:
        """Read-merge-write: several monitors (team/elo/mlb signals) share
        this file, each tracking different leagues -- a blind overwrite
        would clobber the others' verdicts."""
        try:
            merged = {**self._load(), **self._state}
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.state_path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(merged, indent=2, sort_keys=True), encoding="utf-8")
            temporary.replace(self.state_path)
        except OSError:
            pass  # persistence is a convenience; the in-memory verdict rules

    # -- detection --------------------------------------------------------
    def _window(self) -> str:
        now = self.now_fn()
        start = (now - timedelta(days=self.lookback_days)).strftime("%Y%m%d")
        end = (now + timedelta(days=self.lookahead_days)).strftime("%Y%m%d")
        return f"{start}-{end}"

    def _check(self, league: str) -> bool:
        """One live scoreboard read: any game in the window means active.

        Uses the RAISING read -- ``games`` swallows fetch errors into an
        empty list, which is indistinguishable from a real offseason and
        would silently bench a live league on a feed blip.
        """
        reader = getattr(self.espn, "games_or_raise", None)
        if reader is None:  # duck-typed fakes without the strict variant
            reader = self.espn.games
        return bool(reader(league, self._window()))

    def active(self, league: str) -> bool:
        """Cached per-league season verdict (TTL + sticky-on-error)."""
        now = self.now_fn()
        entry = self._state.get(league) or {}
        checked_at = entry.get("checked_at")
        if checked_at:
            try:
                age_h = (now - datetime.fromisoformat(checked_at)).total_seconds() / 3600.0
                if 0 <= age_h < self.ttl_hours:
                    return bool(entry.get("active", True))
            except (TypeError, ValueError):
                pass
        previously_active = entry.get("active")  # None = never checked
        try:
            verdict = self._check(league)
        except Exception:
            # Sticky: keep the last known verdict; unknown leagues fail OPEN
            # (active) so a feed hiccup can't silence a league for hours.
            verdict = bool(previously_active) if previously_active is not None else True
            self._state[league] = {
                **entry,
                "active": verdict,
                "checked_at": now.isoformat(),
                "last_check_error": True,
            }
            self._save()
            return verdict
        self._state[league] = {
            "active": verdict,
            "checked_at": now.isoformat(),
            "last_check_error": False,
            "woke_at": (
                now.isoformat() if verdict and previously_active is False
                else entry.get("woke_at")
            ),
        }
        self._save()
        return verdict

    def snapshot(self) -> dict[str, dict[str, Any]]:
        """Read-only copy for health/dashboard reporting."""
        return {league: dict(entry) for league, entry in self._state.items()}
