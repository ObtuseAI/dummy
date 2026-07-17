"""Licensed player-prop signal (Wave-10).

The app's Player Props tab -- home runs, strikeouts, hits, H+R+RBI, total bases,
outs, RBIs, stolen bases -- is now part of the arsenal. dummy has no first-party
per-player projection yet, so v1 prices these off the licensed multi-book
consensus: for the matched (player, line) it de-vigs each book's Over/Under and
averages, the same de-vig that anchors the game lines. That is a genuinely sharp
number -- the market's own fair player line -- carried in as challenger evidence.

Player props live only on The Odds API's per-event endpoint and are metered per
market, so every fetch runs through the Wave-9 credit governor (per-event TTL
cache + daily cap); if the budget is spent, props yield to the game lines and
this signal simply abstains. Fully inert unless the slot is armed
(``DUMMY_ODDS_API_KEY`` + ``DUMMY_ODDS_API_ENABLED=1``). Fail-closed everywhere:
no matched event, no matching (player, line), or an unarmed slot -> None.

MLB only in v1 (the reference league, and where Kalshi's prop surface is
deepest). Each stat family emits its own source scope so it is graded on its own
merits. Challenger-only; reaches execution solely through the promotion ladder.
"""
from __future__ import annotations

from typing import Any

from autonomy.odds_api_client import OddsApiClient
from autonomy.odds_providers import _match_event, _norm
from autonomy.ontology import MarketView, Signal
from autonomy.player_props import parse_event_props
from autonomy.signals.mlb_segments import _teams_from_ticker
from autonomy.sports.espn import EspnClient
from autonomy.sports_markets import (
    STAT_HITS,
    STAT_HITS_RUNS_RBIS,
    STAT_HOME_RUNS,
    STAT_OUTS,
    STAT_RBIS,
    STAT_STOLEN_BASES,
    STAT_STRIKEOUTS,
    STAT_TOTAL_BASES,
    classify,
)

# Our canonical prop stat -> The Odds API market key (verified live 2026-07-17:
# batter_* / pitcher_*). "Strikeouts" and "Outs Recorded" are pitcher markets;
# the rest are batter markets.
STAT_TO_MARKET_KEY: dict[str, str] = {
    STAT_HOME_RUNS: "batter_home_runs",
    STAT_STRIKEOUTS: "pitcher_strikeouts",
    STAT_HITS: "batter_hits",
    STAT_HITS_RUNS_RBIS: "batter_hits_runs_rbis",
    STAT_TOTAL_BASES: "batter_total_bases",
    STAT_OUTS: "pitcher_outs",
    STAT_RBIS: "batter_rbis",
    STAT_STOLEN_BASES: "batter_stolen_bases",
}
LEAGUE_TO_ODDS_SPORT: dict[str, str] = {"mlb": "baseball_mlb"}


class LicensedPlayerPropSignal:
    name = "licensed_player_prop"

    def __init__(self, espn: EspnClient | None = None, client: OddsApiClient | None = None):
        self.espn = espn or EspnClient()
        self.client = client or OddsApiClient()
        # Per-cycle memoisation so one game's event id and prop payload are
        # resolved once even though it exposes many prop markets/players.
        self._event_id: dict[str, str | None] = {}
        self._props: dict[str, list[Any]] = {}

    def on_cycle_start(self) -> None:
        self.espn.clear_cache()
        self._event_id.clear()
        self._props.clear()

    def applicable(self, market: MarketView) -> bool:
        if not self.client.available:
            return False
        info = classify(market)
        return (
            info is not None
            and info.is_prop
            and info.league in LEAGUE_TO_ODDS_SPORT
            and info.stat in STAT_TO_MARKET_KEY
        )

    def _resolve_event_id(self, sport: str, home_name: str, away_name: str) -> str | None:
        cache_key = f"{sport}|{home_name}|{away_name}"
        if cache_key in self._event_id:
            return self._event_id[cache_key]
        events, _ = self.client.list_events(sport)
        event = _match_event(events, home_name, away_name) if events else None
        event_id = str(event.get("id")) if event and event.get("id") else None
        self._event_id[cache_key] = event_id
        return event_id

    def _event_quotes(self, sport: str, event_id: str, market_key: str) -> list[Any]:
        cache_key = f"{sport}|{event_id}|{market_key}"
        if cache_key not in self._props:
            event, _ = self.client.event_player_props(sport, event_id, market_key)
            self._props[cache_key] = parse_event_props(event) if event else []
        return self._props[cache_key]

    def generate(self, market: MarketView) -> Signal | None:
        if not self.client.available:
            return None
        info = classify(market)
        if info is None or not info.is_prop:
            return None
        sport = LEAGUE_TO_ODDS_SPORT.get(info.league)
        market_key = STAT_TO_MARKET_KEY.get(info.stat or "")
        player = info.subject
        if sport is None or market_key is None or not player or info.threshold is None:
            return None

        teams = _teams_from_ticker(market.ticker)
        if teams is None:
            return None
        game = self.espn.find_matchup("mlb", teams[0], teams[1], info.date_yyyymmdd)
        if game is None or game.status != "pre":
            return None   # props settle per game; price only pre-game
        home_name = game.home_name or game.home
        away_name = game.away_name or game.away
        if not home_name or not away_name:
            return None

        event_id = self._resolve_event_id(sport, home_name, away_name)
        if event_id is None:
            return None
        quotes = self._event_quotes(sport, event_id, market_key)

        player_key = _norm(player)
        prob_over: float | None = None
        n_books = 0
        for quote in quotes:
            if (
                quote.market_key == market_key
                and _norm(quote.player) == player_key
                and abs(quote.point - info.threshold) <= 1e-9
            ):
                prob_over = quote.prob_over
                n_books = quote.n_books
                break
        if prob_over is None:
            return None   # no matching (player, line) -> abstain

        source = f"licensed_prop_{info.stat}"
        return Signal(
            source=source,
            market_ticker=market.ticker,
            probability_yes=min(0.98, max(0.02, prob_over)),
            # Consensus is sharp; base uncertainty tightens with book count.
            uncertainty=max(0.05, 0.12 - 0.006 * min(8, n_books)),
            rationale=(
                f"licensed {n_books}-book {info.stat} consensus: {player} "
                f"over {info.threshold:g} devig={prob_over:.3f}"
            ),
            features={
                "challenger_only": True,
                "prop": True,
                "stat": info.stat,
                "book_count": n_books,
                "consensus_source": "the_odds_api",
            },
        )
