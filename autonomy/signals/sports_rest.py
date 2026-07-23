"""Sports signal: rest/travel MEAN shift on the winner (challenger).

Prices the winner as the point-in-time scoring-model home win probability
shifted by the two teams' rest differential, using a per-league coefficient
the daily tuner earns walk-forward (autonomy.sports.tuner.tune_league ->
"rest_shift"). Where rest does not predict the winner the tuned coefficient
is 0.0 and this signal abstains -- it never emits a zero-information duplicate
of the scoring winner. Self-scopes to leagues the scoring model covers;
challenger-only + fail-closed. Earns weight only through the contested-Brier
gate.
"""
from __future__ import annotations

from typing import Any

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.signals.sports_elo import parse_game_ticker
from autonomy.sports.espn import LEAGUE_TO_ESPN, EspnClient
from autonomy.sports.history_store import SportsHistoryStore


class SportsRestSignal:
    name = "sports_rest"

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

    def applicable(self, market: MarketView) -> bool:
        return (
            market.vertical is Vertical.SPORTS
            and parse_game_ticker(market.ticker) is not None
        )

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_game_ticker(market.ticker)
        if parsed is None or parsed["league"] not in LEAGUE_TO_ESPN:
            return None
        league = parsed["league"]
        store = self.store()
        if store is None:
            return None

        from autonomy.sports.rest import apply_rest_shift, rest_logit_shift, rest_state
        from autonomy.sports.scoring_model import LakeScoringModel
        from autonomy.sports.tuner import load_tuned

        coefficient = load_tuned(league, "rest_shift", "coefficient", 0.0)
        if coefficient == 0.0:
            return None  # rest un-predictive for this league -> σ-only fallback

        try:
            game = self.espn.find_matchup(
                league, parsed["subject"], parsed["opponent"],
                dates=parsed["date_yyyymmdd"],
            )
        except Exception:  # noqa: BLE001
            game = None
        if game is None or game.status != "pre":
            return None
        home, away, now = game.home, game.away, self._now()

        model = LakeScoringModel(store, league=league)
        base = model.p_home_covers(home, away, now, 0.0)
        if base is None:
            return None
        state = rest_state(store, home, away, now, league)
        if state["rest_diff_days"] is None:
            return None  # no point-in-time rest data -> abstain fail-closed
        shift = rest_logit_shift(
            state["home_rest_days"], state["away_rest_days"], coefficient,
        )
        if shift == 0.0:
            return None  # equal rest -> no mean information to add

        subject_is_home = str(parsed["subject"]).upper() == str(home).upper()
        p_home = apply_rest_shift(base, shift)
        p_yes = p_home if subject_is_home else 1.0 - p_home
        p_yes = min(0.98, max(0.02, p_yes))

        rh, ra = model._rates(home, now), model._rates(away, now)
        n = min(rh[2], ra[2]) if rh and ra else 0
        uncertainty = min(0.5, max(0.08, 0.22 - 0.20 * abs(p_yes - 0.5)))
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=p_yes,
            uncertainty=uncertainty,
            rationale=(
                f"{league.upper()} rest shift {home} vs {away}: "
                f"home_rest={state['home_rest_days']}d away_rest={state['away_rest_days']}d "
                f"(coef={coefficient}, shift={shift:+.3f})"
            ),
            features={
                "rest_coefficient": coefficient,
                "rest_logit_shift": round(shift, 4),
                "base_home_win_prob": round(base, 4),
                "min_games": n,
                "challenger_only": True,
                "promotion_eligible": True,
                "point_in_time": True,
                "public_read_only": True,
                "sport": league,
                **state,
            },
        )
