"""Team-league specialists (NBA/NFL/NCAAF/NHL/NCAAMB) -- Phase 0 wrappers.

Each league gets its own council member so later phases can deepen one league
without touching the others (NFL key-number margins, NBA pace-and-efficiency,
NHL goalie identity...). Phase 0 wraps the shipped generic
``TeamSportsIntelligenceSignal`` view and the sportsbook-consensus book with
zero behavior change.
"""
from __future__ import annotations

from typing import Any

from autonomy.live_odds import EspnSummaryBook
from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.specialists.base import SpecialistHealth
from autonomy.sports.espn import EspnClient, canonical_team


class TeamLeagueSpecialist:
    """One pro/college team league wrapped behind the specialist protocol."""

    def __init__(
        self,
        league: str,
        intelligence: Any,
        sportsbook: Any,
        seasons: Any = None,
        espn: EspnClient | None = None,
        live_book: EspnSummaryBook | None = None,
    ) -> None:
        self.name = league
        self.league = league
        self.intelligence = intelligence
        self.sportsbook = sportsbook
        self.seasons = seasons  # optional SeasonMonitor for health truth
        self.espn = espn or EspnClient()
        self.live_book = live_book or EspnSummaryBook(league=league)

    def _parsed(self, market: MarketView):
        from autonomy.signals.sports_intelligence import parse_sports_contract

        parsed = parse_sports_contract(market)
        if parsed is None or parsed.sport != self.league:
            return None
        return parsed

    def applicable(self, market: MarketView) -> bool:
        return market.vertical is Vertical.SPORTS and self._parsed(market) is not None

    def _live_game(self, market: MarketView):
        """Resolve this specialist's in-progress game, or fail closed."""
        parsed = self._parsed(market)
        if parsed is None or not parsed.competitors:
            return None
        if parsed.market_type == "winner":
            game = self.espn.find_matchup(
                self.league, parsed.competitors[0], parsed.competitors[1],
                parsed.date_yyyymmdd,
            )
        else:
            game = self.espn.find_matchup_names(
                self.league, parsed.competitors[0], parsed.competitors[1],
                parsed.date_yyyymmdd,
            )
        if game is None or game.status != "in":
            return None
        return parsed, game

    def forecast(self, market: MarketView) -> Signal | None:
        try:
            if self.intelligence is None or not self.applicable(market):
                return None
            return self.intelligence.generate(market)
        except Exception:
            return None

    def live_forecast(self, market: MarketView) -> Signal | None:
        try:
            if self.intelligence is None or self._live_game(market) is None:
                return None
            signal = self.intelligence.generate(market)
            if signal is not None and signal.features.get("live"):
                return signal
            return None
        except Exception:
            return None

    def book(self, market: MarketView) -> float | None:
        try:
            resolved = self._live_game(market)
            if resolved is not None:
                parsed, game = resolved
                # EspnSummaryBook currently exposes a two-way MONEYLINE only;
                # never misapply it to a spread/total contract.
                if parsed.market_type == "winner" and parsed.subject:
                    home_prob = self.live_book.home_win_probability(game.game_id)
                    if home_prob is not None:
                        subject = canonical_team(self.league, parsed.subject)
                        yes_is_home = subject == canonical_team(self.league, game.home)
                        return home_prob if yes_is_home else 1.0 - home_prob
            if self.sportsbook is not None and self.sportsbook.applicable(market):
                signal = self.sportsbook.generate(market)
                return signal.probability_yes if signal else None
            return None
        except Exception:
            return None

    def ejection_events(self, market: MarketView) -> tuple[dict[str, Any], ...]:
        try:
            resolved = self._live_game(market)
            if resolved is None:
                return ()
            _, game = resolved
            return self.live_book.ejection_events(game.game_id)
        except Exception:
            return ()

    def on_cycle_start(self) -> None:
        # Shared signal instances are warmed by the brain's registry cycle;
        # this private summary cache must be fresh each monitor pass.
        self.live_book.clear()

    def health(self) -> SpecialistHealth:
        details: dict[str, Any] = {
            "has_intelligence": self.intelligence is not None,
            "has_sportsbook": self.sportsbook is not None,
        }
        models = getattr(self.intelligence, "models", None)
        if isinstance(models, dict) and self.league in models:
            details["score_games_seen"] = getattr(models[self.league], "games_seen", None)
        status = "ok" if self.intelligence is not None else "cold"
        if self.seasons is not None:
            try:
                in_season = bool(self.seasons.active(self.league))
            except Exception:
                in_season = True  # health must never break on a feed error
            details["in_season"] = in_season
            if not in_season:
                status = "dormant"
        return SpecialistHealth(name=self.name, status=status, details=details)
