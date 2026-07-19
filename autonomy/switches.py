"""Operator control switches: one on/off surface for the whole system.

Gives the operator four kinds of switch, per the directive:
  * a real MAIN switch -- off idles the entire brain cycle (no scan / forecast
    / execute);
  * CRYPTO on/off;
  * SPORTS on/off, and per-LEAGUE on/off;
  * LLM backends (openrouter / claude / codex) on/off -- read by the model
    router (see model_router/llm_switches.py, same JSON).

Source of truth is ``configs/switches.json``; a per-key environment variable
overrides it (``DUMMY_MAIN_ENABLED``, ``DUMMY_CRYPTO_ENABLED``,
``DUMMY_SPORTS_ENABLED``, ``DUMMY_SPORTS_<LEAGUE>_ENABLED``,
``DUMMY_LLM_<BACKEND>_ENABLED`` = ``0``/``1``), so a scheduled task picks up a
setx toggle on its next fire. Fail-SAFE: a missing or broken file reads as
all-on, so a bad edit never silently disables trading -- except the two CLI
LLM backends, which default OFF (they bill personal subscriptions). Read fresh
each cycle; nothing here is cached across fires.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from autonomy.ontology import MarketView, Vertical

CONFIG_PATH = Path(__file__).parent.parent / "configs" / "switches.json"
KNOWN_LEAGUES = ("mlb", "nfl", "nba", "nhl", "ncaaf", "ncaamb", "wnba")
LLM_BACKENDS = ("openrouter", "claude", "codex")

# All-on defaults except the CLI LLM backends (personal-quota; opt-in).
_DEFAULTS: dict[str, Any] = {
    "main": True,
    "crypto": True,
    "sports": True,
    "leagues": {league: True for league in KNOWN_LEAGUES},
    "llm": {"openrouter": True, "claude": False, "codex": False},
}


def _env_flag(name: str) -> bool | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    return raw.strip() == "1" if raw.strip() in ("0", "1") else None


def _as_bool(value: Any, default: bool) -> bool:
    return bool(value) if isinstance(value, bool) else default


class Switches:
    def __init__(self, data: dict[str, Any] | None = None):
        self._data = data if data is not None else dict(_DEFAULTS)

    @classmethod
    def load(cls, path: Path | None = None) -> "Switches":
        target = path or CONFIG_PATH
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("not an object")
        except (OSError, ValueError, TypeError):
            raw = {}
        return cls(raw)

    # -- individual switches (env override -> file -> default) ----------------

    def main_enabled(self) -> bool:
        env = _env_flag("DUMMY_MAIN_ENABLED")
        return env if env is not None else _as_bool(self._data.get("main"), True)

    def crypto_enabled(self) -> bool:
        env = _env_flag("DUMMY_CRYPTO_ENABLED")
        return env if env is not None else _as_bool(self._data.get("crypto"), True)

    def sports_enabled(self) -> bool:
        env = _env_flag("DUMMY_SPORTS_ENABLED")
        return env if env is not None else _as_bool(self._data.get("sports"), True)

    def league_enabled(self, league: str) -> bool:
        league = (league or "").lower()
        if not self.sports_enabled():
            return False
        env = _env_flag(f"DUMMY_SPORTS_{league.upper()}_ENABLED")
        if env is not None:
            return env
        leagues = self._data.get("leagues")
        if isinstance(leagues, dict) and league in leagues:
            return _as_bool(leagues.get(league), True)
        return True   # unknown league: allow (sports gate already passed)

    def llm_enabled(self, backend: str) -> bool:
        backend = (backend or "").lower()
        env = _env_flag(f"DUMMY_LLM_{backend.upper()}_ENABLED")
        if env is not None:
            return env
        llm = self._data.get("llm")
        default = _DEFAULTS["llm"].get(backend, False)
        if isinstance(llm, dict) and backend in llm:
            return _as_bool(llm.get(backend), default)
        return default

    # -- market-level gate ----------------------------------------------------

    def market_allowed(self, market: MarketView) -> bool:
        """Whether the brain should price this market under the current
        switches. Main off blocks everything; crypto/sports (and per-league)
        gate their verticals; other verticals pass (governed elsewhere)."""
        if not self.main_enabled():
            return False
        if market.vertical is Vertical.CRYPTO:
            return self.crypto_enabled()
        if market.vertical is Vertical.SPORTS:
            if not self.sports_enabled():
                return False
            return self.league_enabled(_league_of(market))
        return True

    def summary(self) -> dict[str, Any]:
        return {
            "main": self.main_enabled(),
            "crypto": self.crypto_enabled(),
            "sports": self.sports_enabled(),
            "leagues": {lg: self.league_enabled(lg) for lg in KNOWN_LEAGUES},
            "llm": {b: self.llm_enabled(b) for b in LLM_BACKENDS},
        }


def _league_of(market: MarketView) -> str:
    """Best-effort league for a sports market, via the series registry."""
    try:
        from autonomy.sports_markets import spec_for

        spec = spec_for(market.ticker)
        return spec.league if spec is not None else ""
    except Exception:
        return ""
