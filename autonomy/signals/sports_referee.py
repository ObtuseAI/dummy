"""Sports signal: referee/official total adjustment (challenger).

For a TOTAL market on an upcoming game whose officials are already assigned,
this nudges the scoring model's expected total by the assigned crew's
historical total lean (autonomy.sports.referees) and reprices over/under.
An over-leaning crew (more fouls / a tighter strike zone) raises the total;
an under-leaning crew lowers it.

Fail-closed: abstains unless the officials are posted for the game and the
crew has enough historical sample. Challenger-only; earns weight only through
the contested-Brier gate.
"""
from __future__ import annotations

import json
from typing import Any

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.sports.espn import LEAGUE_TO_ESPN, EspnClient
from autonomy.sports.history_store import SportsHistoryStore

_TOTAL_TYPES = {"total", "total_runs"}


class SportsRefereeSignal:
    name = "sports_referee"

    def __init__(self, espn: EspnClient | None = None,
                 store: SportsHistoryStore | None = None, seasons: Any = None,
                 fetcher: Any = None) -> None:
        from autonomy.specialists.seasons import SeasonMonitor

        self.espn = espn or EspnClient()
        self._store = store
        self._fetcher = fetcher
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

    def fetcher(self):
        if self._fetcher is None:
            from autonomy.ingest.fetcher import PoliteFetcher

            self._fetcher = PoliteFetcher()
        return self._fetcher

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
        return bool(c and c.market_type in _TOTAL_TYPES and c.threshold is not None)

    def _officials(self, league: str, event_id: str) -> list[str]:
        from autonomy.ingest.referee_lake import summary_url
        from autonomy.sports.referees import parse_officials

        url = summary_url(league, event_id)
        if url is None:
            return []
        try:
            resp = self.fetcher().get(url)
            if not getattr(resp, "ok", False):
                return []
            return parse_officials(json.loads(resp.text))
        except Exception:  # noqa: BLE001
            return []

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
            game = self.espn.find_matchup(
                league, c.competitors[0], c.competitors[1], dates=c.date_yyyymmdd,
            )
        except Exception:  # noqa: BLE001
            game = None
        if game is None or game.status != "pre":
            return None

        crew = self._officials(league, str(game.game_id))
        if not crew:
            return None  # officials not posted -> fail-closed abstain

        from autonomy.sports.referees import RefereeTendencies
        from autonomy.sports.scoring_model import LakeScoringModel

        crew_lean = RefereeTendencies().crew_total_delta(league, crew)
        if crew_lean is None:
            return None  # crew too thin -> abstain

        model = LakeScoringModel(store, league=league)
        now = self._now()
        base_total = model.expected_total(game.home, game.away, now)
        if base_total is None:
            return None
        adjusted_total = base_total + crew_lean["delta"]
        # Reprice over/under at the adjusted expected total using the model's
        # own total sigma (a shifted mean, same dispersion).
        from autonomy.sports.scoring_model import _norm_cdf

        z = (adjusted_total - line) / max(1e-6, model.sigma_total)
        p_over = _norm_cdf(z)
        p_yes = min(0.98, max(0.02, p_over))

        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=p_yes,
            uncertainty=min(0.5, max(0.10, 0.24 - 0.20 * abs(p_yes - 0.5))),
            rationale=(
                f"{league.upper()} referee total {game.home} vs {game.away}: crew "
                f"{'+' if crew_lean['delta'] >= 0 else ''}{crew_lean['delta']} vs base "
                f"{base_total:.1f} -> {adjusted_total:.1f} over {line:.1f}"
            ),
            features={
                "line": line,
                "base_expected_total": round(base_total, 2),
                "crew_total_delta": crew_lean["delta"],
                "adjusted_expected_total": round(adjusted_total, 2),
                "qualified_referees": crew_lean["qualified_referees"],
                "market_type": c.market_type,
                "challenger_only": True,
                "promotion_eligible": True,
                "public_read_only": True,
                "sport": league,
            },
        )
