"""Licensed multi-book consensus signal (Wave-9, widened Wave-11).

The ESPN-embedded book (``sportsbook_consensus``) is one book. The Odds API
plan carries a MULTI-book market (8 US books on MLB, measured 2026-07-17); the
average de-vigged two-way price across sharp books is the closest thing to a
true fair line in sports and the anchor serious bettors price against.

This signal reuses ESPN only to resolve the matchup's identity (which teams,
which is home, is it still pre-game) and then reads the sharper multi-book
consensus from the credit-governed Odds API client for that game. Emitted
challenger-only: it reaches execution solely through the WS-14 ladder, graded
head-to-head against the single-book source and our own models.

Wave-11: the Wave-9 slate call already buys ``h2h,totals,spreads`` in ONE
3-credit fetch, so full-game TOTAL and SPREAD markets now price from the same
cached payload at zero extra credits. Each market type emits its own source
(``licensed_consensus`` / ``licensed_consensus_total`` /
``licensed_consensus_spread``) so each earns its own grading scope. Book team
totals stay deferred: The Odds API meters ``team_totals`` per-event only, a
poor credit trade while dummy's own run model prices them (``mlb_team_total``).

Fully inert unless the governance slot is armed (``DUMMY_ODDS_API_KEY`` +
``DUMMY_ODDS_API_ENABLED=1``); when unarmed ``generate`` returns None, so the
ensemble is byte-identical to a build without a key. Fail-closed everywhere:
started games, unmatched events, non-half-point lines, and books quoting a
different line all abstain rather than approximate.
"""
from __future__ import annotations

from typing import Any

from autonomy.odds_api_client import OddsApiClient
from autonomy.odds_providers import (
    devigged_home_probability,
    devigged_spread_probability,
    devigged_total_probability,
)
from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.signals.sports_elo import parse_game_ticker
from autonomy.sports.espn import EspnClient, canonical_team
from autonomy.sports_markets import FULL, SPREAD, TOTAL, classify

# Our league keys -> The Odds API sport keys.
LEAGUE_TO_ODDS_SPORT: dict[str, str] = {
    "mlb": "baseball_mlb",
    "nfl": "americanfootball_nfl",
    "ncaaf": "americanfootball_ncaaf",
    "nba": "basketball_nba",
    "ncaamb": "basketball_ncaab",
    "nhl": "icehockey_nhl",
    "wnba": "basketball_wnba",
}

# Full-game line types priced off the slate payload (Wave-11). Segments (F5,
# halves, quarters) are NOT here: the slate quotes full-game lines only.
_LINE_TYPES = (TOTAL, SPREAD)


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

    def _line_info(self, market: MarketView):
        """Registry classification when this is a full-game total/spread we can
        price from the slate; None otherwise."""
        info = classify(market)
        if (
            info is None
            or info.is_prop
            or info.segment != FULL
            or info.market_type not in _LINE_TYPES
            or info.league not in LEAGUE_TO_ODDS_SPORT
        ):
            return None
        return info

    def applicable(self, market: MarketView) -> bool:
        if not self.client.available:
            return False
        if market.vertical is not Vertical.SPORTS:
            return False
        parsed = parse_game_ticker(market.ticker)
        if parsed is not None and parsed["league"] in LEAGUE_TO_ODDS_SPORT:
            return True
        return self._line_info(market) is not None

    def _sport_events(self, sport_key: str) -> list[dict[str, Any]]:
        if sport_key not in self._events:
            events, _source = self.client.consensus_odds(sport_key)
            self._events[sport_key] = events
        return self._events[sport_key]

    def generate(self, market: MarketView) -> Signal | None:
        if not self.client.available:
            return None
        parsed = parse_game_ticker(market.ticker)
        if parsed is not None and parsed["league"] in LEAGUE_TO_ODDS_SPORT:
            return self._generate_winner(market, parsed)
        info = self._line_info(market)
        if info is not None:
            return self._generate_line(market, info)
        return None

    # ---- winner (Wave-9 path, unchanged behavior) ------------------------------

    def _generate_winner(self, market: MarketView, parsed: dict[str, Any]) -> Signal | None:
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

    # ---- full-game totals / spreads (Wave-11) ----------------------------------

    def _generate_line(self, market: MarketView, info: Any) -> Signal | None:
        if info.threshold is None or info.teams is None:
            return None
        game = self.espn.find_matchup_names(
            info.league, info.teams[0], info.teams[1], dates=info.date_yyyymmdd)
        if game is None or game.status != "pre":
            return None
        home_name = game.home_name or game.home
        away_name = game.away_name or game.away
        if not home_name or not away_name:
            return None

        events = self._sport_events(LEAGUE_TO_ODDS_SPORT[info.league])
        if not events:
            return None

        subject_home = False
        if info.market_type == TOTAL:
            devigged = devigged_total_probability(
                events, home_name, away_name, info.threshold)
            detail = f"total over {info.threshold:g}"
        else:  # SPREAD
            if not info.subject:
                return None
            subject = canonical_team(info.league, info.subject)
            home_abbr = canonical_team(info.league, game.home)
            away_abbr = canonical_team(info.league, game.away)
            if subject == home_abbr:
                subject_name, subject_home = home_name, True
            elif subject == away_abbr:
                subject_name = away_name
            else:
                return None
            devigged = devigged_spread_probability(
                events, home_name, away_name, subject_name, info.threshold)
            detail = f"{subject} by >{info.threshold:g}"
        if devigged is None:
            return None
        probability, n_books = devigged
        probability = min(0.98, max(0.02, probability))
        return Signal(
            source=f"{self.name}_{info.market_type}",
            market_ticker=market.ticker,
            probability_yes=probability,
            # Line markets are thinner than the moneyline; slightly wider base
            # than the winner path, tightening with book count.
            uncertainty=max(0.06, 0.12 - 0.005 * min(8, n_books)),
            rationale=(
                f"licensed {n_books}-book consensus: {info.league} {detail} "
                f"devig={probability:.3f} ({away_name} @ {home_name})"
            ),
            features={
                "challenger_only": True,
                "devig_prob": probability,
                "book_count": n_books,
                "market_type": info.market_type,
                "line": info.threshold,
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
