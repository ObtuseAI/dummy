"""Sports signal: Glicko-2 win probability from the history lake (challenger).

The Glicko-2 analog of :mod:`autonomy.signals.sports_elo`: it parses the same
Kalshi game tickers and resolves home/away on ESPN, but sources its matchup
probability from :class:`autonomy.sports.glicko.LakeGlickoRatings` warmed off
the persistent history lake. Glicko-2 carries a rating *deviation* per team, so
this source is honestly less certain about lightly-observed teams -- surfaced
as a wider ``uncertainty`` -- where plain Elo is falsely confident.

Challenger-only + fail-closed: it abstains (returns None) whenever the lake is
missing, the ticker doesn't parse, the game has already started, or anything
raises. It earns ensemble weight only through the normal contested-Brier
promotion gate.
"""
from __future__ import annotations

from typing import Any

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.signals.sports_elo import parse_game_ticker
from autonomy.sports.espn import LEAGUE_TO_ESPN, EspnClient
from autonomy.sports.glicko import LakeGlickoRatings
from autonomy.sports.history_store import SportsHistoryStore

# Home-field/court/ice advantage in rating points (tuner can refine per league).
_HOME_ADVANTAGE = {
    "nfl": 45.0, "ncaaf": 55.0, "nba": 40.0, "wnba": 35.0,
    "ncaamb": 50.0, "nhl": 30.0, "mlb": 24.0,
}


class SportsGlickoSignal:
    name = "sports_glicko"

    def __init__(self, espn: EspnClient | None = None,
                 store: SportsHistoryStore | None = None, seasons: Any = None,
                 ratings_dir: Any = None) -> None:
        from pathlib import Path

        from autonomy.specialists.seasons import SeasonMonitor

        self.espn = espn or EspnClient()
        self._store = store
        self._ratings: dict[str, LakeGlickoRatings] = {}
        self._as_of: str | None = None
        self.ratings_dir = Path(ratings_dir) if ratings_dir else Path("runtime/autonomy")
        self.seasons = seasons or SeasonMonitor(espn=self.espn)

    # ---- lake-backed ratings, cached per league per cycle ----------------
    def _now(self) -> str:
        from datetime import datetime, timezone

        return self._as_of or datetime.now(timezone.utc).isoformat()

    def store(self) -> SportsHistoryStore | None:
        if self._store is None:
            try:
                self._store = SportsHistoryStore()
            except Exception:  # noqa: BLE001 -- no lake yet => abstain, never crash
                return None
        return self._store

    def _ratings_for(self, league: str) -> LakeGlickoRatings | None:
        if league in self._ratings:
            return self._ratings[league]
        store = self.store()
        if store is None:
            return None
        # Load persisted ratings, then fold in only games settled since the last
        # save (already-seen games skipped) -> no full multi-season replay each
        # cycle once the lake is deep. Persist the caught-up state.
        path = self.ratings_dir / f"glicko_{league}.json"
        try:
            ratings = LakeGlickoRatings.load(store, league, path).warm(self._now())
            try:
                ratings.save(path)
            except Exception:  # noqa: BLE001 -- a failed save must not block pricing
                pass
        except Exception:  # noqa: BLE001
            return None
        self._ratings[league] = ratings
        return ratings

    def on_cycle_start(self, as_of: str | None = None) -> None:
        """Re-warm ratings against the freshest lake state at cycle start."""
        self.espn.clear_cache()
        self._as_of = as_of
        self._ratings.clear()

    # ---- signal contract -------------------------------------------------
    def applicable(self, market: MarketView) -> bool:
        return market.vertical is Vertical.SPORTS and parse_game_ticker(market.ticker) is not None

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_game_ticker(market.ticker)
        if parsed is None:
            return None
        league = parsed["league"]
        if league not in LEAGUE_TO_ESPN:
            return None
        subject, opponent = parsed["subject"], parsed["opponent"]

        try:
            game = self.espn.find_matchup(league, subject, opponent, dates=parsed["date_yyyymmdd"])
        except Exception:  # noqa: BLE001
            game = None
        # Never fight a settlement: skip games already started/finished.
        if game is not None and game.status != "pre":
            return None
        subject_home = None if game is None else (game.home.upper() == subject)

        ratings = self._ratings_for(league)
        if ratings is None:
            return None
        hadv = _HOME_ADVANTAGE.get(league, 35.0)
        if subject_home is True:
            p_yes = ratings.matchup_prob(subject, opponent, home_advantage=hadv)
        elif subject_home is False:
            p_yes = 1.0 - ratings.matchup_prob(opponent, subject, home_advantage=hadv)
        else:
            p_yes = ratings.matchup_prob(subject, opponent, home_advantage=0.0)
        p_yes = min(0.98, max(0.02, p_yes))

        rd_s, rd_o = ratings.deviation(subject), ratings.deviation(opponent)
        rd_avg = (rd_s + rd_o) / 2.0
        coldness = 0.18 if rd_avg > 200 else (0.10 if rd_avg > 110 else 0.04)
        site_penalty = 0.06 if subject_home is None else 0.0
        uncertainty = min(0.5, max(0.05, 0.20 - 0.28 * abs(p_yes - 0.5) + coldness + site_penalty))

        r_s, r_o = ratings.rating(subject), ratings.rating(opponent)
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=p_yes,
            uncertainty=uncertainty,
            rationale=(
                f"{league.upper()} Glicko-2 {subject}({r_s:.0f}±{rd_s:.0f}) "
                f"vs {opponent}({r_o:.0f}±{rd_o:.0f}) home={subject_home}"
            ),
            features={
                "subject_rating": round(r_s, 1), "opponent_rating": round(r_o, 1),
                "subject_rd": round(rd_s, 1), "opponent_rd": round(rd_o, 1),
                "subject_home": subject_home,
            },
        )
