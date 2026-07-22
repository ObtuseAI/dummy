"""Sports signal: spread & total pricing from the lake scoring model (challenger).

Where the rating analytics price the winner, this prices the SPREAD and the
TOTAL -- the "by how much" and "how many" that those markets settle on -- from
:class:`autonomy.sports.scoring_model.LakeScoringModel` (expected margin/total
from point-in-time scoring rates). Self-scopes to spread/total markets (abstains
on winner/props), across every league the scoring model covers.

Reuses the canonical :func:`autonomy.signals.sports_intelligence.parse_sports_contract`
for market_type + subject + the real line (``floor_strike``). Challenger-only +
fail-closed: abstains when history is thin, the game has started, the line is
missing, or anything raises; earns weight only through the contested-Brier gate.
"""
from __future__ import annotations

from typing import Any

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.sports.espn import LEAGUE_TO_ESPN, EspnClient, canonical_team
from autonomy.sports.history_store import SportsHistoryStore
from autonomy.sports.scoring_model import LakeScoringModel

_SPREAD_TYPES = {"spread"}
_TOTAL_TYPES = {"total", "total_runs"}


class SportsScoringSignal:
    name = "sports_scoring"

    def __init__(self, espn: EspnClient | None = None,
                 store: SportsHistoryStore | None = None, seasons: Any = None) -> None:
        from autonomy.specialists.seasons import SeasonMonitor

        self.espn = espn or EspnClient()
        self._store = store
        self._as_of: str | None = None
        self.seasons = seasons or SeasonMonitor(espn=self.espn)

    def _now(self) -> str:
        from datetime import datetime, timezone

        return self._as_of or datetime.now(timezone.utc).isoformat()

    def store(self) -> SportsHistoryStore | None:
        if self._store is None:
            try:
                self._store = SportsHistoryStore()
            except Exception:  # noqa: BLE001
                return None
        return self._store

    def on_cycle_start(self, as_of: str | None = None) -> None:
        self.espn.clear_cache()
        self._as_of = as_of

    def _contract(self, market: MarketView):
        from autonomy.signals.sports_intelligence import parse_sports_contract

        try:
            return parse_sports_contract(market)
        except Exception:  # noqa: BLE001
            return None

    def applicable(self, market: MarketView) -> bool:
        if market.vertical is not Vertical.SPORTS:
            return False
        c = self._contract(market)
        return bool(c and c.market_type in (_SPREAD_TYPES | _TOTAL_TYPES) and c.threshold is not None)

    def generate(self, market: MarketView) -> Signal | None:
        c = self._contract(market)
        if c is None or c.threshold is None or c.competitors is None:
            return None
        league = c.sport
        if league not in LEAGUE_TO_ESPN:
            return None
        line = float(c.threshold)

        store = self.store()
        if store is None:
            return None
        try:
            game = self.espn.find_matchup(league, c.competitors[0], c.competitors[1],
                                          dates=c.date_yyyymmdd)
        except Exception:  # noqa: BLE001
            game = None
        if game is None or game.status != "pre":
            return None
        home, away = game.home, game.away
        model = LakeScoringModel(store, league=league)
        now = self._now()

        try:
            if c.market_type in _SPREAD_TYPES:
                if not c.subject:
                    return None
                subject_home = canonical_team(league, home) == canonical_team(league, c.subject)
                if subject_home:
                    p = model.p_home_covers(home, away, now, -line)       # P(margin > line)
                else:
                    ph = model.p_home_covers(home, away, now, line)
                    p = None if ph is None else 1.0 - ph                  # P(away wins by > line)
                detail = f"spread {c.subject} by {line:+.1f}"
            else:                                                          # total / total_runs
                p = model.p_over(home, away, now, line)                   # YES = over
                detail = f"total over {line:.1f}"
        except Exception:  # noqa: BLE001
            p = None
        if p is None:
            return None
        p_yes = min(0.98, max(0.02, p))

        rh, ra = model._rates(home, now), model._rates(away, now)
        n = min(rh[2], ra[2]) if rh and ra else 0
        coldness = 0.20 if n < 5 else (0.11 if n < 12 else 0.05)
        uncertainty = min(0.5, max(0.06, 0.20 - 0.20 * abs(p_yes - 0.5) + coldness))
        exp_m = model.expected_margin(home, away, now)
        exp_t = model.expected_total(home, away, now)

        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=p_yes,
            uncertainty=uncertainty,
            rationale=f"{league.upper()} scoring {home} vs {away} {detail} "
                      f"(E[margin]={exp_m:.1f}, E[total]={exp_t:.1f}, n={n})"
                      if exp_m is not None and exp_t is not None else f"{league.upper()} scoring {detail}",
            features={
                "line": line,
                "expected_margin": round(exp_m, 2) if exp_m is not None else None,
                "expected_total": round(exp_t, 2) if exp_t is not None else None,
                "market_type": c.market_type,
                "min_games": n,
                "challenger_only": True,
                "promotion_eligible": True,
                "point_in_time": True,
                "public_read_only": True,
                "sport": league,
            },
        )
