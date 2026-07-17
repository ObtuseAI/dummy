"""Basketball first-half markets: 3-way winner, total, spread (Wave-13).

Kalshi lists a first-half surface per basketball game (verified live on the
WNBA slate 2026-07-17): ``KX<LG>1HWINNER`` with an explicit TIE leg,
``KX<LG>1HTOTAL`` and ``KX<LG>1HSPREAD`` at half-point strikes. This signal
prices them off the same learned ``TeamScoreModel`` state the full-game
``TeamSportsIntelligenceSignal`` warms every cycle, split through the
``basketball_segments`` half kernel (share-based, continuity-corrected tie).

One instance per in-season league (v1 registers WNBA; NBA/NCAAMB flip on at
their season starts). Pre-game only -- a half line is stale once the half is
underway -- and challenger-only: each market type emits its own source
(``<league>_1h_winner`` / ``<league>_1h_total`` / ``<league>_1h_spread``) so
each earns its own grading scope through the promotion ladder. The model file
is reloaded each cycle (read-only) so this signal always prices off the
freshest warmup without ever retraining state it does not own.
"""
from __future__ import annotations

import re
from pathlib import Path

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.signals.sports_intelligence import MODEL_DIR
from autonomy.sports.basketball_segments import (
    SEGMENT_MODEL_VERSION,
    first_half_outcome_probabilities,
    first_half_spread_probability,
    first_half_total_probability,
)
from autonomy.sports.espn import EspnClient, canonical_team
from autonomy.sports.team_scores import LEAGUE_SCORE_CONFIGS, TeamScoreModel
from autonomy.sports_markets import H1, SPREAD, TOTAL, WINNER, classify

# parts[1] of a game ticker: YY MON DD [HHMM] TEAMS [G<n>]. Spread titles on
# the half surface carry no "A vs B" clause ("Will Phoenix win the 1H by over
# 6.5 points?", verified live), so the classifier's title-based team extraction
# comes back empty there; the opponent is recovered from this token instead,
# anchored on the subject abbreviation (same method parse_game_ticker uses).
_GAME_TOKEN_RE = re.compile(r"^(\d{2})([A-Z]{3})(\d{2})(?:\d{4})?([A-Z]+?)(?:G\d)?$")


def _opponent_from_ticker(ticker: str, subject: str) -> str | None:
    parts = ticker.upper().split("-")
    if len(parts) < 3:
        return None
    match = _GAME_TOKEN_RE.match(parts[1])
    if match is None:
        return None
    teams = match.group(4)
    if teams.startswith(subject):
        opponent = teams[len(subject):]
    elif teams.endswith(subject):
        opponent = teams[: -len(subject)]
    else:
        return None
    return opponent or None


class BasketballSegmentSignal:
    """First-half pricing for one basketball league (classify-driven)."""

    def __init__(
        self,
        league: str = "wnba",
        espn: EspnClient | None = None,
        model: TeamScoreModel | None = None,
        model_dir: Path | None = None,
    ) -> None:
        self.league = league
        self.name = f"{league}_segments"
        self.espn = espn or EspnClient()
        self.model_dir = model_dir or MODEL_DIR
        self._injected_model = model
        self.model = model or TeamScoreModel.load(
            league, self.model_dir / f"team_scores_{league}.json")

    def on_cycle_start(self) -> None:
        self.espn.clear_cache()
        if self._injected_model is None:
            # Reload (never retrain) the state the full-game signal warms --
            # same read-only discipline as the ncaaf Elo reload.
            try:
                self.model = TeamScoreModel.load(
                    self.league, self.model_dir / f"team_scores_{self.league}.json")
            except Exception:
                pass  # keep the last-loaded state rather than go cold on a blip

    def _handles(self, info) -> bool:
        return (
            info is not None
            and info.league == self.league
            and info.segment == H1
            and info.market_type in (WINNER, TOTAL, SPREAD)
        )

    def applicable(self, market: MarketView) -> bool:
        return market.vertical is Vertical.SPORTS and self._handles(classify(market))

    def generate(self, market: MarketView) -> Signal | None:
        info = classify(market)
        if not self._handles(info):
            return None
        if info.teams is not None:
            game = self.espn.find_matchup_names(
                self.league, info.teams[0], info.teams[1], dates=info.date_yyyymmdd)
        elif info.subject and info.subject != "TIE":
            opponent = _opponent_from_ticker(market.ticker, info.subject)
            if opponent is None:
                return None
            game = self.espn.find_matchup(
                self.league, info.subject, opponent, dates=info.date_yyyymmdd)
        else:
            return None
        # Pre-game only: a first-half line is stale once the half is underway.
        if game is None or game.status != "pre":
            return None
        prediction = self.model.predict(game)
        margin_sigma = LEAGUE_SCORE_CONFIGS[self.league].margin_sigma
        home = canonical_team(self.league, game.home)
        away = canonical_team(self.league, game.away)

        subject_home = False
        if info.market_type == WINNER:
            p_home, p_tie, p_away = first_half_outcome_probabilities(
                prediction, margin_sigma)
            if info.is_tie:
                probability, label = p_tie, "tie"
            else:
                if not info.subject:
                    return None
                subject = canonical_team(self.league, info.subject)
                if subject == home:
                    probability, label, subject_home = p_home, subject, True
                elif subject == away:
                    probability, label = p_away, subject
                else:
                    return None
            source = f"{self.league}_1h_winner"
            detail = f"first-half {label}"
        elif info.market_type == TOTAL:
            if info.threshold is None:
                return None
            probability = first_half_total_probability(prediction, info.threshold)
            source = f"{self.league}_1h_total"
            detail = f"first-half over {info.threshold:g}"
        else:  # SPREAD
            if info.threshold is None or not info.subject:
                return None
            subject = canonical_team(self.league, info.subject)
            if subject == home:
                subject_home = True
            elif subject != away:
                return None
            probability = first_half_spread_probability(
                prediction, subject_home, info.threshold, margin_sigma)
            source = f"{self.league}_1h_spread"
            detail = f"{subject} first-half by >{info.threshold:g}"

        # Half-splitting a full-game read adds real model risk on top of the
        # underlying score model's own uncertainty; widen and floor it.
        uncertainty = min(0.48, prediction.winner_uncertainty + 0.08)
        return Signal(
            source=source,
            market_ticker=market.ticker,
            probability_yes=min(0.99, max(0.01, probability)),
            uncertainty=uncertainty,
            rationale=(
                f"{self.league.upper()} {detail}: {game.away}@{game.home}; "
                f"expected {prediction.expected_away_score:.1f}+"
                f"{prediction.expected_home_score:.1f}={prediction.expected_total:.1f} "
                f"({SEGMENT_MODEL_VERSION})"
            ),
            features={
                "challenger_only": True,
                "market_type": info.market_type,
                "segment": info.segment,
                "subject_home": subject_home,
                "segment_model_version": SEGMENT_MODEL_VERSION,
                "sample_games": prediction.sample_games,
            },
        )
