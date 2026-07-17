"""Licensed multi-book consensus signal (Wave-9).

The ESPN-embedded book (``sportsbook_consensus``) is one book. The Odds API
plan carries a MULTI-book market (8 US books on MLB, measured 2026-07-17); the
average de-vigged two-way price across sharp books is the closest thing to a
true fair line in sports and the anchor serious bettors price against.

This signal reuses ESPN only to resolve the matchup's identity (which teams,
which is home, is it still pre-game) and then reads the sharper multi-book
consensus from the credit-governed Odds API client for that game. Emitted
challenger-only: it reaches execution solely through the WS-14 ladder, graded
head-to-head against the single-book source and our own models.

Fully inert unless the governance slot is armed (``DUMMY_ODDS_API_KEY`` +
``DUMMY_ODDS_API_ENABLED=1``); when unarmed ``generate`` returns None, so the
ensemble is byte-identical to a build without a key. Fail-closed everywhere.
"""
from __future__ import annotations

from typing import Any

from autonomy.odds_api_client import OddsApiClient
from autonomy.odds_providers import devigged_home_probability
from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.signals.sports_elo import parse_game_ticker
from autonomy.sports.espn import EspnClient

# Our league keys -> The Odds API sport keys.
LEAGUE_TO_ODDS_SPORT: dict[str, str] = {
    "mlb": "baseball_mlb",
    "nfl": "americanfootball_nfl",
    "ncaaf": "americanfootball_ncaaf",
    "nba": "basketball_nba",
    "ncaamb": "basketball_ncaab",
    "nhl": "icehockey_nhl",
}


class LicensedConsensusSignal:
    name = "licensed_consensus"

    def __init__(self, espn: EspnClient | None = None, client: OddsApiClient | None = None):
        self.espn = espn or EspnClient()
        self.client = client or OddsApiClient()
        # Per-cycle memo of (sport_key -> events); the governor handles the
        # real cross-cycle TTL cache and budget, this only avoids refetching
        # the same sport twice within one scan.
        self._events: dict[str, list[dict[str, Any]]] = {}

    def on_cycle_start(self) -> None:
        self.espn.clear_cache()
        self._events.clear()

    def applicable(self, market: MarketView) -> bool:
        if not self.client.available:
            return False
        parsed = parse_game_ticker(market.ticker)
        return (
            market.vertical is Vertical.SPORTS
            and parsed is not None
            and parsed["league"] in LEAGUE_TO_ODDS_SPORT
        )

    def _sport_events(self, sport_key: str) -> list[dict[str, Any]]:
        if sport_key not in self._events:
            events, _source = self.client.consensus_odds(sport_key)
            self._events[sport_key] = events
        return self._events[sport_key]

    def generate(self, market: MarketView) -> Signal | None:
        if not self.client.available:
            return None
        parsed = parse_game_ticker(market.ticker)
        if parsed is None:
            return None
        sport_key = LEAGUE_TO_ODDS_SPORT.get(parsed["league"])
        if sport_key is None:
            return None
        game = self.espn.find_matchup(
            parsed["league"], parsed["subject"], parsed["opponent"],
            dates=parsed["date_yyyymmdd"])
        if game is None or game.status != "pre":
            return None   # never fight a settlement; a started line is stale
        home_name = game.home_name or game.home
        away_name = game.away_name or game.away
        if not home_name or not away_name:
            return None

        events = self._sport_events(sport_key)
        if not events:
            return None
        p_home = devigged_home_probability(events, home_name, away_name)
        if p_home is None:
            return None

        subject_home = game.home.upper() == parsed["subject"]
        p_subject = p_home if subject_home else 1.0 - p_home
        p_subject = min(0.98, max(0.02, p_subject))
        n_books = self._book_count(events, home_name, away_name)
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=p_subject,
            # Multi-book consensus is sharp; base uncertainty tightens with
            # book count, floored so it never claims false precision.
            uncertainty=max(0.05, 0.11 - 0.005 * min(8, n_books)),
            rationale=(
                f"licensed {n_books}-book consensus: {parsed['subject']} "
                f"devig={p_subject:.3f} ({home_name} vs {away_name})"
            ),
            features={
                "challenger_only": True,
                "devig_prob": p_subject,
                "book_count": n_books,
                "subject_home": subject_home,
                "consensus_source": "the_odds_api",
            },
        )

    @staticmethod
    def _book_count(events: list[dict[str, Any]], home: str, away: str) -> int:
        from autonomy.odds_providers import _match_event

        event = _match_event(events, home, away)
        if not event:
            return 0
        return sum(
            1 for b in event.get("bookmakers", []) or []
            if any(m.get("key") == "h2h" for m in b.get("markets", []) or [])
        )
