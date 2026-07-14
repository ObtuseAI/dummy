"""League-specific point-in-time live-state challengers.

The pre-game team engines estimate matchup scoring strength.  This module
conditions those estimates on the score and clock that are actually visible
in ESPN's live scoreboard.  It deliberately owns no feed and learns no state:
callers must supply a point-in-time ``Game`` observation and a pre-game
prediction trained only on settled games.

NFL and NCAAF use separate compound-Poisson scoring-event priors.  Football
scores are discrete and clustered around field goals/touchdowns, so a normal
diffusion is the wrong shape near live spread strikes.  The two public model
classes share only deterministic convolution machinery; their scoring mixes,
model versions, and uncertainty policies remain league-specific calibration
targets.  NCAAMB uses a separate 40-minute/two-half normal remainder because
reusing NBA's 48-minute/four-quarter clock would be dimensionally wrong.

These are observational challengers, not capital authorization.  Missing or
invalid period/clock/score inputs return ``None`` at the integration layer.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass


NFL_LIVE_MODEL_VERSION = "nfl_live_compound_poisson_v1"
NCAAF_LIVE_MODEL_VERSION = "ncaaf_live_compound_poisson_v1"
NCAAMB_LIVE_MODEL_VERSION = "ncaamb_live_40m_normal_v1"

FOOTBALL_REGULATION_MINUTES = 60.0
FOOTBALL_PERIOD_MINUTES = 15.0
NCAAMB_REGULATION_MINUTES = 40.0
NCAAMB_HALF_MINUTES = 20.0

# Auditable scoring-event priors, intentionally separate by league.  They are
# propose-then-promote calibration targets, not claimed fitted frequencies.
NFL_SCORING_MIX: dict[int, float] = {2: 0.03, 3: 0.34, 6: 0.04, 7: 0.57, 8: 0.02}
NCAAF_SCORING_MIX: dict[int, float] = {2: 0.04, 3: 0.26, 6: 0.06, 7: 0.59, 8: 0.05}


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(float(value) / math.sqrt(2.0)))


def _clamp_probability(value: float) -> float:
    return min(0.9995, max(0.0005, float(value)))


def parse_clock_minutes(display_clock: str | None, period_minutes: float) -> float | None:
    """Parse ESPN ``M:SS`` and validate it against the period length."""
    if not display_clock:
        return None
    match = re.fullmatch(r"(\d+):(\d{2})", str(display_clock).strip())
    if match is None:
        return None
    minutes, seconds = int(match.group(1)), int(match.group(2))
    value = minutes + seconds / 60.0
    if seconds >= 60 or value < 0.0 or value > float(period_minutes):
        return None
    return value


def football_minutes_remaining(period: int | None, display_clock: str | None) -> float | None:
    """Regulation minutes remaining for NFL/NCAAF; overtime abstains."""
    if period is None or period < 1 or period > 4:
        return None
    clock = parse_clock_minutes(display_clock, FOOTBALL_PERIOD_MINUTES)
    if clock is None:
        return None
    return (4 - period) * FOOTBALL_PERIOD_MINUTES + clock


def ncaamb_minutes_remaining(period: int | None, display_clock: str | None) -> float | None:
    """Minutes left for men's college basketball (two halves, 5m OTs)."""
    if period is None or period < 1:
        return None
    period_length = NCAAMB_HALF_MINUTES if period <= 2 else 5.0
    clock = parse_clock_minutes(display_clock, period_length)
    if clock is None:
        return None
    if period <= 2:
        return (2 - period) * NCAAMB_HALF_MINUTES + clock
    # ESPN increments the period for each overtime.  Only the current OT can
    # be known to exist at the observation time, so never invent future OTs.
    return clock


def _normalize(distribution: dict[int, float]) -> dict[int, float]:
    total = sum(distribution.values())
    if total <= 0.0:
        return {0: 1.0}
    return {key: value / total for key, value in distribution.items() if value > 0.0}


def _convolve(left: dict[int, float], right: dict[int, float]) -> dict[int, float]:
    result: dict[int, float] = {}
    for left_value, left_prob in left.items():
        for right_value, right_prob in right.items():
            key = left_value + right_value
            result[key] = result.get(key, 0.0) + left_prob * right_prob
    return result


def compound_poisson_points(expected_points: float, scoring_mix: dict[int, float]) -> dict[int, float]:
    """PMF for remaining points from Poisson scoring events.

    ``expected_points`` determines the event rate via the mix's mean points
    per event.  The Poisson tail is truncated far beyond eight standard
    deviations and the retained mass is normalized; this keeps the function
    deterministic and bounded without silently assigning tail mass to a
    fabricated score.
    """
    target = max(0.0, float(expected_points))
    if target == 0.0:
        return {0: 1.0}
    mix = _normalize({int(points): float(prob) for points, prob in scoring_mix.items()})
    mean_event_points = sum(points * prob for points, prob in mix.items())
    if mean_event_points <= 0.0:
        return {0: 1.0}
    rate = target / mean_event_points
    max_events = min(48, max(18, int(math.ceil(rate + 8.0 * math.sqrt(rate + 1.0)))))

    count_probability = math.exp(-rate)
    event_sum = {0: 1.0}
    result: dict[int, float] = {0: count_probability}
    for count in range(1, max_events + 1):
        count_probability *= rate / count
        event_sum = _convolve(event_sum, mix)
        for points, conditional_probability in event_sum.items():
            result[points] = result.get(points, 0.0) + count_probability * conditional_probability
    return _normalize(result)


@dataclass(frozen=True)
class FootballLiveForecast:
    home_win_probability: float
    expected_home_score: float
    expected_away_score: float
    expected_total: float
    minutes_remaining: float
    margin_pmf: dict[int, float]
    total_pmf: dict[int, float]
    model_version: str

    def cover_probability(self, subject_is_home: bool, threshold: float) -> float:
        probability = sum(
            mass for margin, mass in self.margin_pmf.items()
            if (margin if subject_is_home else -margin) > float(threshold)
        )
        return _clamp_probability(probability)

    def total_probability(self, threshold: float) -> float:
        probability = sum(
            mass for total, mass in self.total_pmf.items() if total > float(threshold)
        )
        return _clamp_probability(probability)


class _FootballLiveModel:
    scoring_mix: dict[int, float]
    model_version: str

    def forecast(
        self,
        expected_home_score: float,
        expected_away_score: float,
        home_score: int,
        away_score: int,
        minutes_remaining: float,
    ) -> FootballLiveForecast:
        fraction = min(1.0, max(0.0, float(minutes_remaining)) / FOOTBALL_REGULATION_MINUTES)
        home_remaining = compound_poisson_points(float(expected_home_score) * fraction, self.scoring_mix)
        away_remaining = compound_poisson_points(float(expected_away_score) * fraction, self.scoring_mix)

        margin_pmf: dict[int, float] = {}
        total_pmf: dict[int, float] = {}
        for home_points, home_mass in home_remaining.items():
            for away_points, away_mass in away_remaining.items():
                mass = home_mass * away_mass
                final_home = int(home_score) + home_points
                final_away = int(away_score) + away_points
                margin = final_home - final_away
                total = final_home + final_away
                margin_pmf[margin] = margin_pmf.get(margin, 0.0) + mass
                total_pmf[total] = total_pmf.get(total, 0.0) + mass
        margin_pmf = _normalize(margin_pmf)
        total_pmf = _normalize(total_pmf)
        positive = sum(mass for margin, mass in margin_pmf.items() if margin > 0)
        home_win = positive + 0.5 * margin_pmf.get(0, 0.0)
        expected_home = int(home_score) + sum(points * mass for points, mass in home_remaining.items())
        expected_away = int(away_score) + sum(points * mass for points, mass in away_remaining.items())
        return FootballLiveForecast(
            home_win_probability=_clamp_probability(home_win),
            expected_home_score=expected_home,
            expected_away_score=expected_away,
            expected_total=expected_home + expected_away,
            minutes_remaining=float(minutes_remaining),
            margin_pmf=margin_pmf,
            total_pmf=total_pmf,
            model_version=self.model_version,
        )


class NflLiveModel(_FootballLiveModel):
    """NFL-specific live scoring-event model."""

    scoring_mix = NFL_SCORING_MIX
    model_version = NFL_LIVE_MODEL_VERSION


class NcaafLiveModel(_FootballLiveModel):
    """NCAAF-specific live model with its own higher-variance scoring mix."""

    scoring_mix = NCAAF_SCORING_MIX
    model_version = NCAAF_LIVE_MODEL_VERSION


@dataclass(frozen=True)
class NcaambLiveForecast:
    home_win_probability: float
    expected_home_score: float
    expected_away_score: float
    expected_total: float
    expected_margin: float
    margin_sigma_remaining: float
    total_sigma_remaining: float
    minutes_remaining: float
    model_version: str = NCAAMB_LIVE_MODEL_VERSION

    def cover_probability(self, subject_is_home: bool, threshold: float) -> float:
        margin = self.expected_margin if subject_is_home else -self.expected_margin
        z = (margin - float(threshold)) / self.margin_sigma_remaining
        return _clamp_probability(_normal_cdf(z))

    def total_probability(self, threshold: float) -> float:
        z = (self.expected_total - float(threshold)) / self.total_sigma_remaining
        return _clamp_probability(_normal_cdf(z))


class NcaambLiveModel:
    """40-minute/two-half NCAAMB live residual model."""

    model_version = NCAAMB_LIVE_MODEL_VERSION

    def forecast(
        self,
        expected_home_score: float,
        expected_away_score: float,
        margin_sigma: float,
        total_sigma: float,
        home_score: int,
        away_score: int,
        minutes_remaining: float,
    ) -> NcaambLiveForecast:
        fraction = min(1.0, max(0.0, float(minutes_remaining)) / NCAAMB_REGULATION_MINUTES)
        expected_home = int(home_score) + float(expected_home_score) * fraction
        expected_away = int(away_score) + float(expected_away_score) * fraction
        expected_margin = expected_home - expected_away
        margin_sigma_remaining = max(0.25, float(margin_sigma) * math.sqrt(fraction))
        total_sigma_remaining = max(0.25, float(total_sigma) * math.sqrt(fraction))
        return NcaambLiveForecast(
            home_win_probability=_clamp_probability(
                _normal_cdf(expected_margin / margin_sigma_remaining)),
            expected_home_score=expected_home,
            expected_away_score=expected_away,
            expected_total=expected_home + expected_away,
            expected_margin=expected_margin,
            margin_sigma_remaining=margin_sigma_remaining,
            total_sigma_remaining=total_sigma_remaining,
            minutes_remaining=float(minutes_remaining),
        )
