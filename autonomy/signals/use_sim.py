"""Universal Sports Engine simulation challenger (Wave-22).

Prices dummy's per-game market surface from the USE sidecar's champion
ensemble ForecastMoments (``runtime/autonomy/use_predictions.json``): winner,
full-game total/spread/team totals, and every share-table segment -- an
INDEPENDENT simulation-derived view beside dummy's own analytical models and
the book de-vigs, graded head-to-head under its own source family
(``use_sim_<league>``) through the unchanged two-door promotion ladder.

Fail-closed: no artifact, a stale artifact, an unmatched game, a missing
strike, or a non-half-point line all abstain. Challenger-only. The signal
never imports the engine -- the ARTIFACT is the boundary, so a broken or
absent sidecar cannot touch the scan path.
"""
from __future__ import annotations

import math
from typing import Any

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.signals.basketball_segments import _opponent_from_ticker
from autonomy.sports.espn import canonical_team
from autonomy.sports.segment_shares import segment_share
from autonomy.sports_markets import (
    FULL,
    SPREAD,
    TEAM_TOTAL,
    TOTAL,
    WINNER,
    classify,
)
from autonomy.use_bridge import LEAGUE_TO_USE, load_predictions


def _normal_over(mean: float, sd: float, line: float) -> float:
    z = (line - mean) / max(0.5, sd)
    return min(0.995, max(0.005, 1.0 - 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))))


class UseSimSignal:
    name = "use_sim"

    def __init__(self, predictions_loader=None):
        self._load = predictions_loader or load_predictions
        self._rows: dict[str, dict[str, Any]] = {}

    def on_cycle_start(self) -> None:
        try:
            self._rows = self._load()
        except Exception:
            self._rows = {}

    def _handles(self, info) -> bool:
        if info is None or info.is_prop or info.league not in LEAGUE_TO_USE:
            return False
        if info.market_type in (WINNER, TOTAL, SPREAD, TEAM_TOTAL):
            return info.segment == FULL or segment_share(
                info.league, info.segment) is not None
        return False

    def applicable(self, market: MarketView) -> bool:
        return (
            bool(self._rows)
            and market.vertical is Vertical.SPORTS
            and self._handles(classify(market))
        )

    def _match(self, info, ticker: str) -> tuple[dict[str, Any], bool] | None:
        """(prediction row, subject_is_home) for this market's game."""
        subject = None
        if info.subject and info.subject != "TIE":
            subject = canonical_team(info.league, info.subject)
            opponent = _opponent_from_ticker(ticker, info.subject)
            opponent = canonical_team(info.league, opponent) if opponent else None
            if opponent:
                home_key = f"{info.league}|{subject}|{opponent}"
                away_key = f"{info.league}|{opponent}|{subject}"
                if home_key in self._rows:
                    return self._rows[home_key], True
                if away_key in self._rows:
                    return self._rows[away_key], False
        # No subject anchor (totals, tie legs): scan for the matchup by the
        # ticker's team token via either orientation of any row this league.
        for key, row in self._rows.items():
            league, home, away = key.split("|", 2)
            if league != info.league:
                continue
            token = ticker.upper().split("-")[1] if "-" in ticker else ""
            if home in token and away in token:
                if subject is not None:
                    return row, subject == home
                return row, False
        return None

    def generate(self, market: MarketView) -> Signal | None:
        info = classify(market)
        if not self._handles(info) or not self._rows:
            return None
        matched = self._match(info, market.ticker)
        if matched is None:
            return None
        row, subject_home = matched
        share = 1.0 if info.segment == FULL else segment_share(info.league, info.segment)
        if share is None:
            return None
        scale = math.sqrt(share)

        if info.market_type == WINNER and info.segment == FULL and not info.is_tie:
            p_home = float(row["home_win_probability"])
            probability = p_home if subject_home else 1.0 - p_home
            detail = "winner"
        elif info.market_type == WINNER:
            margin_mean = float(row["margin_mean"]) * share
            margin_sd = max(0.5, float(row["margin_sd"]) * scale)
            p_home = 1.0 - 0.5 * (1.0 + math.erf((0.5 - margin_mean) / (margin_sd * math.sqrt(2.0))))
            p_away = 0.5 * (1.0 + math.erf((-0.5 - margin_mean) / (margin_sd * math.sqrt(2.0))))
            if info.is_tie:
                probability = max(0.0, 1.0 - p_home - p_away)
            else:
                probability = p_home if subject_home else p_away
            detail = f"{info.segment} winner"
        elif info.market_type == TOTAL:
            if info.threshold is None:
                return None
            probability = _normal_over(
                float(row["total_mean"]) * share,
                float(row["total_sd"]) * scale,
                info.threshold)
            detail = f"{info.segment} total over {info.threshold:g}"
        elif info.market_type == SPREAD:
            if info.threshold is None:
                return None
            margin = float(row["margin_mean"]) * share
            mean = margin if subject_home else -margin
            probability = _normal_over(
                mean, float(row["margin_sd"]) * scale, info.threshold)
            detail = f"{info.segment} spread >{info.threshold:g}"
        else:  # TEAM_TOTAL (full game)
            if info.threshold is None:
                return None
            mean = float(row["home_mean"] if subject_home else row["away_mean"])
            sd = math.sqrt(float(row["total_sd"]) ** 2 + float(row["margin_sd"]) ** 2) / 2.0
            probability = _normal_over(mean, sd, info.threshold)
            detail = f"team total over {info.threshold:g}"

        return Signal(
            source=f"use_sim_{info.league}",
            market_ticker=market.ticker,
            probability_yes=min(0.99, max(0.01, probability)),
            # An untuned reference ensemble is honest about its width; the
            # sidecar's recursive tuning narrows this as champions earn in.
            uncertainty=0.30 if row.get("provenance") == "reference_ensemble" else 0.18,
            rationale=(
                f"USE sim {info.league} {detail}: {row['away']}@{row['home']} "
                f"({row.get('provenance')})"
            ),
            features={
                "challenger_only": True,
                "market_type": info.market_type,
                "segment": info.segment,
                "subject_home": subject_home,
                "use_provenance": row.get("provenance"),
            },
        )
