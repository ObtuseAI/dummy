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


NFL_LIVE_MODEL_VERSION = "nfl_live_possession_ot_v2"
NCAAF_LIVE_MODEL_VERSION = "ncaaf_live_possession_ot_v2"
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


@dataclass(frozen=True)
class FootballOvertimeState:
    """Observed ESPN overtime possession state.

    ``completed_possessions`` contains team abbreviations for completed
    overtime drives.  For NCAA it is restricted to the current overtime
    round; for NFL it covers the full overtime period.  A current possession
    is mandatory: without it the live model abstains instead of guessing who
    has the ball.
    """

    period: int
    possession_team: str
    completed_possessions: tuple[str, ...]
    clock_minutes: float | None = None


def parse_football_overtime_state(
    summary: dict | None,
    *,
    league: str,
    period: int | None,
    display_clock: str | None,
) -> FootballOvertimeState | None:
    """Parse possession and completed OT drives from an ESPN summary.

    ESPN's live summary exposes the active drive under ``drives.current`` and
    finished drives under ``drives.previous``.  NCAA period numbers identify
    each untimed overtime round; NFL uses period 5 for its timed overtime.
    The parser intentionally does not infer possession from score changes.
    """
    if league not in {"nfl", "ncaaf"} or period is None or period <= 4:
        return None
    drives = (summary or {}).get("drives") or {}
    if not isinstance(drives, dict):
        return None
    current = drives.get("current") or {}
    possession = str(((current.get("team") or {}).get("abbreviation") or "")).upper()
    if not possession:
        return None
    completed: list[str] = []
    for drive in drives.get("previous") or []:
        if not isinstance(drive, dict):
            continue
        try:
            drive_period = int((((drive.get("start") or {}).get("period") or {}).get("number")))
        except (TypeError, ValueError):
            continue
        if drive_period <= 4 or (league == "ncaaf" and drive_period != period):
            continue
        team = str(((drive.get("team") or {}).get("abbreviation") or "")).upper()
        if team:
            completed.append(team)
    clock = parse_clock_minutes(display_clock, 10.0) if league == "nfl" else None
    if league == "nfl" and clock is None:
        return None
    return FootballOvertimeState(
        period=period,
        possession_team=possession,
        completed_possessions=tuple(completed),
        clock_minutes=clock,
    )


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
    overtime: bool = False
    possession_team: str | None = None
    overtime_possessions_completed: int = 0

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

    def _drive_distribution(self, expected_score: float) -> dict[int, float]:
        """Auditable one-possession score prior derived from the pregame mean.

        A football team averages roughly 10.5 offensive possessions per game.
        The pregame score mean therefore supplies expected points per drive;
        the league-specific scoring-event mix supplies the conditional shape.
        This is a challenger calibration target, not a fitted live coefficient.
        """
        mix = _normalize(self.scoring_mix)
        conditional_mean = sum(points * mass for points, mass in mix.items())
        event_probability = min(
            0.72,
            max(0.12, float(expected_score) / 10.5 / max(conditional_mean, 1e-9)),
        )
        result = {0: 1.0 - event_probability}
        for points, mass in mix.items():
            result[points] = result.get(points, 0.0) + event_probability * mass
        return _normalize(result)

    @staticmethod
    def _finish(
        outcomes: dict[tuple[int, int], float],
        *,
        home_score: int,
        away_score: int,
        state: FootballOvertimeState,
        model_version: str,
    ) -> FootballLiveForecast:
        total_mass = sum(outcomes.values())
        if total_mass <= 0.0:
            outcomes = {(home_score, away_score): 1.0}
            total_mass = 1.0
        margin_pmf: dict[int, float] = {}
        total_pmf: dict[int, float] = {}
        expected_home = expected_away = 0.0
        home_win = 0.0
        for (final_home, final_away), raw_mass in outcomes.items():
            mass = raw_mass / total_mass
            margin = final_home - final_away
            total = final_home + final_away
            margin_pmf[margin] = margin_pmf.get(margin, 0.0) + mass
            total_pmf[total] = total_pmf.get(total, 0.0) + mass
            expected_home += final_home * mass
            expected_away += final_away * mass
            home_win += mass if margin > 0 else 0.5 * mass if margin == 0 else 0.0
        return FootballLiveForecast(
            home_win_probability=_clamp_probability(home_win),
            expected_home_score=expected_home,
            expected_away_score=expected_away,
            expected_total=expected_home + expected_away,
            minutes_remaining=float(state.clock_minutes or 0.0),
            margin_pmf=_normalize(margin_pmf),
            total_pmf=_normalize(total_pmf),
            model_version=model_version,
            overtime=True,
            possession_team=state.possession_team,
            overtime_possessions_completed=len(state.completed_possessions),
        )

    @staticmethod
    def _sudden_death_outcomes(
        home_score: int,
        away_score: int,
        possession_is_home: bool,
        home_drive: dict[int, float],
        away_drive: dict[int, float],
    ) -> dict[tuple[int, int], float]:
        """One exact geometric sudden-death cycle, normalized over repeats."""
        offense = home_drive if possession_is_home else away_drive
        defense = away_drive if possession_is_home else home_drive
        repeat = offense.get(0, 0.0) * defense.get(0, 0.0)
        decisive = max(1e-12, 1.0 - repeat)
        outcomes: dict[tuple[int, int], float] = {}
        for points, mass in offense.items():
            if points <= 0:
                continue
            score = (home_score + points, away_score) if possession_is_home else (
                home_score, away_score + points)
            outcomes[score] = outcomes.get(score, 0.0) + mass / decisive
        for points, mass in defense.items():
            if points <= 0:
                continue
            probability = offense.get(0, 0.0) * mass / decisive
            score = (home_score, away_score + points) if possession_is_home else (
                home_score + points, away_score)
            outcomes[score] = outcomes.get(score, 0.0) + probability
        return outcomes


class NflLiveModel(_FootballLiveModel):
    """NFL-specific live scoring-event model."""

    scoring_mix = NFL_SCORING_MIX
    model_version = NFL_LIVE_MODEL_VERSION

    def forecast_overtime(
        self,
        expected_home_score: float,
        expected_away_score: float,
        home_score: int,
        away_score: int,
        home_team: str,
        away_team: str,
        state: FootballOvertimeState,
    ) -> FootballLiveForecast | None:
        """Price 2025+ NFL OT using observed possession order.

        Both teams receive an initial possession; once both have possessed,
        the next score wins. A zero clock preserves the observed result rather
        than fabricating another possession.
        """
        home, away = home_team.upper(), away_team.upper()
        if state.possession_team not in {home, away}:
            return None
        if (state.clock_minutes or 0.0) <= 0.0:
            return self._finish(
                {(home_score, away_score): 1.0}, home_score=home_score,
                away_score=away_score, state=state, model_version=self.model_version)
        home_drive = self._drive_distribution(expected_home_score)
        away_drive = self._drive_distribution(expected_away_score)
        completed = list(state.completed_possessions)
        possession_is_home = state.possession_team == home

        # After each side has possessed, NFL overtime is sudden death.
        if home in completed and away in completed:
            outcomes = self._sudden_death_outcomes(
                home_score, away_score, possession_is_home, home_drive, away_drive)
            return self._finish(
                outcomes, home_score=home_score, away_score=away_score,
                state=state, model_version=self.model_version)

        current_drive = home_drive if possession_is_home else away_drive
        opponent_drive = away_drive if possession_is_home else home_drive
        outcomes: dict[tuple[int, int], float] = {}
        for current_points, current_mass in current_drive.items():
            score_home = home_score + (current_points if possession_is_home else 0)
            score_away = away_score + (0 if possession_is_home else current_points)
            after_current = completed + [state.possession_team]
            opponent = away if possession_is_home else home
            # The other team is guaranteed its first possession.  If it has
            # already possessed, resolve the observed score immediately.
            if opponent not in after_current:
                for opponent_points, opponent_mass in opponent_drive.items():
                    final_home = score_home + (opponent_points if not possession_is_home else 0)
                    final_away = score_away + (opponent_points if possession_is_home else 0)
                    mass = current_mass * opponent_mass
                    if final_home == final_away:
                        sudden = self._sudden_death_outcomes(
                            final_home, final_away, possession_is_home,
                            home_drive, away_drive)
                        for score, sudden_mass in sudden.items():
                            outcomes[score] = outcomes.get(score, 0.0) + mass * sudden_mass
                    else:
                        outcomes[(final_home, final_away)] = (
                            outcomes.get((final_home, final_away), 0.0) + mass)
            elif score_home == score_away:
                sudden = self._sudden_death_outcomes(
                    score_home, score_away, not possession_is_home,
                    home_drive, away_drive)
                for score, mass in sudden.items():
                    outcomes[score] = outcomes.get(score, 0.0) + current_mass * mass
            else:
                outcomes[(score_home, score_away)] = outcomes.get((score_home, score_away), 0.0) + current_mass
        return self._finish(
            outcomes, home_score=home_score, away_score=away_score,
            state=state, model_version=self.model_version)


class NcaafLiveModel(_FootballLiveModel):
    """NCAAF-specific live model with its own higher-variance scoring mix."""

    scoring_mix = NCAAF_SCORING_MIX
    model_version = NCAAF_LIVE_MODEL_VERSION

    def _ncaa_drive_distribution(self, expected_score: float, overtime_number: int) -> dict[int, float]:
        # Starting at the opponent 25 makes a score materially more likely
        # than on an ordinary drive. Strength only tilts this bounded prior.
        strength = min(0.10, max(-0.10, (float(expected_score) - 28.0) / 100.0))
        score_probability = 0.68 + strength
        if overtime_number >= 3:
            success = min(0.60, max(0.35, 0.45 + strength))
            return {0: 1.0 - success, 2: success}
        touchdown_share = 0.72
        if overtime_number == 2:
            return _normalize({0: 1.0 - score_probability, 3: score_probability * (1.0 - touchdown_share),
                               8: score_probability * touchdown_share})
        return _normalize({0: 1.0 - score_probability, 3: score_probability * (1.0 - touchdown_share),
                           7: score_probability * touchdown_share * 0.94,
                           8: score_probability * touchdown_share * 0.06})

    @staticmethod
    def _two_point_finish(
        home_score: int,
        away_score: int,
        home_drive: dict[int, float],
        away_drive: dict[int, float],
    ) -> dict[tuple[int, int], float]:
        """Exact NCAA 3OT+ paired-attempt process, including tied rounds."""
        p_home = home_drive.get(2, 0.0)
        p_away = away_drive.get(2, 0.0)
        tie_zero = (1.0 - p_home) * (1.0 - p_away)
        tie_two = p_home * p_away
        home_decisive = p_home * (1.0 - p_away)
        away_decisive = (1.0 - p_home) * p_away
        active = max(1e-12, 1.0 - tie_zero)
        repeat_with_points = tie_two / active
        home_finish = home_decisive / active
        away_finish = away_decisive / active
        outcomes: dict[tuple[int, int], float] = {}
        repeat_mass = 1.0
        tied_points = 0
        for _ in range(128):
            outcomes[(home_score + tied_points + 2, away_score + tied_points)] = (
                outcomes.get((home_score + tied_points + 2, away_score + tied_points), 0.0)
                + repeat_mass * home_finish)
            outcomes[(home_score + tied_points, away_score + tied_points + 2)] = (
                outcomes.get((home_score + tied_points, away_score + tied_points + 2), 0.0)
                + repeat_mass * away_finish)
            repeat_mass *= repeat_with_points
            tied_points += 2
            if repeat_mass < 1e-12:
                break
        return outcomes

    def _future_round_outcomes(
        self,
        home_score: int,
        away_score: int,
        expected_home_score: float,
        expected_away_score: float,
        overtime_number: int,
    ) -> dict[tuple[int, int], float]:
        home_drive = self._ncaa_drive_distribution(expected_home_score, overtime_number)
        away_drive = self._ncaa_drive_distribution(expected_away_score, overtime_number)
        if overtime_number >= 3:
            return self._two_point_finish(home_score, away_score, home_drive, away_drive)
        outcomes: dict[tuple[int, int], float] = {}
        for home_points, home_mass in home_drive.items():
            for away_points, away_mass in away_drive.items():
                final_home, final_away = home_score + home_points, away_score + away_points
                mass = home_mass * away_mass
                if final_home == final_away:
                    future = self._future_round_outcomes(
                        final_home, final_away, expected_home_score,
                        expected_away_score, overtime_number + 1)
                    for score, future_mass in future.items():
                        outcomes[score] = outcomes.get(score, 0.0) + mass * future_mass
                else:
                    outcomes[(final_home, final_away)] = outcomes.get((final_home, final_away), 0.0) + mass
        return outcomes

    def forecast_overtime(
        self,
        expected_home_score: float,
        expected_away_score: float,
        home_score: int,
        away_score: int,
        home_team: str,
        away_team: str,
        state: FootballOvertimeState,
    ) -> FootballLiveForecast | None:
        """Price NCAA alternating-possession OT, including the 3OT 2PT phase."""
        home, away = home_team.upper(), away_team.upper()
        if state.possession_team not in {home, away}:
            return None
        overtime_number = state.period - 4
        home_drive = self._ncaa_drive_distribution(expected_home_score, overtime_number)
        away_drive = self._ncaa_drive_distribution(expected_away_score, overtime_number)
        possession_is_home = state.possession_team == home
        current_drive = home_drive if possession_is_home else away_drive
        opponent_drive = away_drive if possession_is_home else home_drive
        completed = list(state.completed_possessions)
        outcomes: dict[tuple[int, int], float] = {}
        for current_points, current_mass in current_drive.items():
            score_home = home_score + (current_points if possession_is_home else 0)
            score_away = away_score + (0 if possession_is_home else current_points)
            opponent = away if possession_is_home else home
            if opponent not in completed + [state.possession_team]:
                for opponent_points, opponent_mass in opponent_drive.items():
                    final_home = score_home + (opponent_points if not possession_is_home else 0)
                    final_away = score_away + (opponent_points if possession_is_home else 0)
                    mass = current_mass * opponent_mass
                    if final_home == final_away:
                        future = self._future_round_outcomes(
                            final_home, final_away, expected_home_score,
                            expected_away_score, overtime_number + 1)
                        for score, future_mass in future.items():
                            outcomes[score] = outcomes.get(score, 0.0) + mass * future_mass
                    else:
                        outcomes[(final_home, final_away)] = outcomes.get((final_home, final_away), 0.0) + mass
            elif score_home == score_away:
                future = self._future_round_outcomes(
                    score_home, score_away, expected_home_score,
                    expected_away_score, overtime_number + 1)
                for score, mass in future.items():
                    outcomes[score] = outcomes.get(score, 0.0) + current_mass * mass
            else:
                outcomes[(score_home, score_away)] = outcomes.get((score_home, score_away), 0.0) + current_mass
        return self._finish(
            outcomes, home_score=home_score, away_score=away_score,
            state=state, model_version=self.model_version)


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
