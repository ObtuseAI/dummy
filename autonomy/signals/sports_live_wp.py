"""Sports signal: live win probability from the PBP comeback matrices (challenger).

Consumes the empirical comeback matrices in the play-by-play knowledge lake
(runtime/autonomy/sports_pbp_params.json, built by autonomy.ingest.pbp_lake):
P(home win | home lead entering the next period). For an in-progress winner
market it reads the current period and score from the live ESPN scoreboard and
returns the historical hold/comeback rate for that exact lead bucket. This is a
non-parametric live win-probability prior grounded in tens of thousands of real
games, not a model extrapolation.

Fail-closed: abstains unless the game is genuinely in progress, a regulation
period has completed, and the matched comeback cell has enough historical
sample. Challenger-only; earns weight only through the contested-Brier gate.
"""
from __future__ import annotations

from typing import Any

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.signals.sports_elo import parse_game_ticker
from autonomy.sports.espn import LEAGUE_TO_ESPN, EspnClient
from autonomy.sports.pbp_params import in_game_home_win_prior

MIN_LIVE_CELL_SAMPLE = 40


class SportsLiveWpSignal:
    name = "sports_live_wp"

    def __init__(self, espn: EspnClient | None = None, seasons: Any = None) -> None:
        from autonomy.specialists.seasons import SeasonMonitor

        self.espn = espn or EspnClient()
        self._as_of: str | None = None
        self.seasons = seasons or SeasonMonitor(espn=self.espn)

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
        try:
            game = self.espn.find_matchup(
                league, parsed["subject"], parsed["opponent"],
                dates=parsed["date_yyyymmdd"],
            )
        except Exception:  # noqa: BLE001
            game = None
        # Live only: a pre/post game has no in-progress state to price.
        if game is None or getattr(game, "status", None) != "in":
            return None
        period = getattr(game, "current_period", None)
        home_score = getattr(game, "home_score", None)
        away_score = getattr(game, "away_score", None)
        if period is None or home_score is None or away_score is None:
            return None
        period_completed = int(period) - 1
        if period_completed < 1:
            return None  # still in the first period -> no completed-period cell

        home_lead = int(home_score) - int(away_score)
        prior = in_game_home_win_prior(
            league,
            period_completed=period_completed,
            home_lead=home_lead,
            min_cell_n=MIN_LIVE_CELL_SAMPLE,
        )
        if prior is None:
            return None  # thin/absent comeback cell -> fail-closed abstain

        subject_is_home = str(parsed["subject"]).upper() == str(game.home).upper()
        p_home = float(prior["home_win_rate"])
        p_yes = p_home if subject_is_home else 1.0 - p_home
        p_yes = min(0.99, max(0.01, p_yes))

        # Uncertainty shrinks with historical sample size in the matched cell.
        n = int(prior["n"])
        uncertainty = min(0.4, max(0.04, 0.30 - 0.00025 * min(n, 800)))
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=p_yes,
            uncertainty=uncertainty,
            rationale=(
                f"{league.upper()} live WP {game.home} vs {game.away}: "
                f"after period {period_completed}, home lead {home_lead:+d} "
                f"({prior['lead_bucket']}) -> hist home win {p_home:.3f} (n={n})"
            ),
            features={
                "period_completed": period_completed,
                "home_lead": home_lead,
                "lead_bucket": prior["lead_bucket"],
                "historical_home_win_rate": round(p_home, 4),
                "historical_sample": n,
                "phase": "live",
                "challenger_only": True,
                "promotion_eligible": True,
                "public_read_only": True,
                "sport": league,
            },
        )
