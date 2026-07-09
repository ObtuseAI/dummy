"""Sportsbook-consensus signal: de-vigged moneyline probability + steam.

The sharpest public forecast of a game is the sportsbook line itself — books
put millions at risk on these numbers and move them under sharp pressure.
ESPN's scoreboard embeds a book's moneyline for both sides, with BOTH the
opening and current line, so one snapshot carries:

  1. Consensus probability: de-vig the two-way moneyline (normalize the
     implied probabilities so they sum to 1) -> the book's true P(win).
  2. Steam: the movement from open to current in probability space. A line
     that moved toward a side means real money arrived on it; a forecast that
     fights fresh steam is usually the fish.

This source doubles as the trap detector: when our Elo forecast disagrees
hard with the de-vigged book, the fusion's earned trust weights decide who
is believed — and the book will earn that trust fast on the contested
record. Fail-closed: no both-sides moneyline, no opinion.
"""
from __future__ import annotations

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.signals.sports_elo import parse_game_ticker
from autonomy.sports.espn import EspnClient


def american_to_prob(odds: int | None) -> float | None:
    """Implied probability (vig included) of one american moneyline."""
    if odds is None or odds == 0:
        return None
    if odds > 0:
        return 100.0 / (odds + 100.0)
    return -odds / (-odds + 100.0)


def devig_two_way(side_odds: int | None, other_odds: int | None) -> float | None:
    """True P(side) after removing the book's margin from a two-way market."""
    p_side = american_to_prob(side_odds)
    p_other = american_to_prob(other_odds)
    if p_side is None or p_other is None:
        return None
    total = p_side + p_other
    if total <= 0:
        return None
    return p_side / total


class SportsbookConsensusSignal:
    name = "sportsbook_consensus"

    def __init__(self, espn: EspnClient | None = None):
        self.espn = espn or EspnClient()

    def on_cycle_start(self) -> None:
        self.espn.clear_cache()

    def applicable(self, market: MarketView) -> bool:
        return market.vertical is Vertical.SPORTS and parse_game_ticker(market.ticker) is not None

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_game_ticker(market.ticker)
        if parsed is None:
            return None
        game = self.espn.find_matchup(parsed["league"], parsed["subject"], parsed["opponent"],
                                      dates=parsed["date_yyyymmdd"])
        # Never fight a settlement; and a started game's line is stale.
        if game is None or game.status != "pre":
            return None
        subject_home = game.home.upper() == parsed["subject"]
        if subject_home:
            subject_ml, opponent_ml = game.home_ml, game.away_ml
            subject_open, opponent_open = game.home_ml_open, game.away_ml_open
        else:
            subject_ml, opponent_ml = game.away_ml, game.home_ml
            subject_open, opponent_open = game.away_ml_open, game.home_ml_open

        p_subject = devig_two_way(subject_ml, opponent_ml)
        if p_subject is None:
            return None
        p_subject = min(0.98, max(0.02, p_subject))

        # Steam: probability-space movement toward/away from the subject since
        # the line opened. Positive = money arrived on the subject.
        steam = None
        p_open = devig_two_way(subject_open, opponent_open)
        if p_open is not None:
            steam = p_subject - p_open

        # Books are sharp: tight base uncertainty. A big move since open means
        # the line is still finding its level — widen slightly.
        uncertainty = 0.07 + (min(0.04, abs(steam)) if steam is not None else 0.01)
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=p_subject,
            uncertainty=uncertainty,
            rationale=(
                f"{(game.odds_provider or 'book')}: {parsed['subject']} ml={subject_ml} "
                f"vs {parsed['opponent']} ml={opponent_ml} devig={p_subject:.3f}"
                + (f" steam={steam:+.3f} since open" if steam is not None else "")
            ),
            features={
                "subject_ml": subject_ml,
                "opponent_ml": opponent_ml,
                "devig_prob": p_subject,
                "steam_since_open": steam,
                "provider": game.odds_provider,
                "subject_home": subject_home,
            },
        )
