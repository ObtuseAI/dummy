"""NHL bivariate-Poisson goal engine with an explicit OT/shootout branch and
goalie identity (WS-3 / spec Sec.5.3).

Point-in-time challenger, same discipline as autonomy/sports/nba_model.py
(WS-2): two per-team EWMA goal rates (for/against), cold priors + reliability
weighting, `save/load/to_dict/from_dict`, live gating on `status == "in"`,
and the signal-hook wholesale-fallback pattern. The one genuinely new piece
of math is the OT/SO branch: Kalshi NHL winner markets settle on the FINAL
score including overtime and a shootout (see the build-time probe below), so
a regulation-only Poisson model would misprice every game that goes past 60
minutes. Every winner/puck-line/totals number in this module is priced off
ONE regulation-goal matrix (`goal_split`, independent Poissons -- correlation
term deferred, see below) so the three markets stay coherent by construction,
mirroring nfl_margin.py/nba_model.py's single-distribution discipline.

INDEPENDENCE ASSUMPTION (deferred): home and away goals are modeled as
INDEPENDENT Poissons. A true bivariate Poisson would carry a small positive
correlation term (score effects, game state affecting both teams' shot rates
similarly). The brief calls this out explicitly as deferred; MIN_GAMES_FOR_ENGINE
and the wide uncertainty bands are not a substitute for that term, just a
documented gap for a future workstream.

PROBE 1 (build-time, 2026-07-12, network confirmed reachable) -- Kalshi
NHL settlement rules, fetched live from
``https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXNHLGAME``
(a settled market, since NHL was offseason -- no open KXNHLGAME markets):
ticker ``KXNHLGAME-26JUN14CARVGK-VGK``, rules_primary: "If VGK Golden Knights
wins the Game 6: Carolina at Vegas professional hockey game scheduled for Jun
14, 2026, then the market resolves to Yes." -- terse, no explicit OT/SO
carve-out (rules_secondary was empty for every KXNHLGAME/KXNHLSPREAD market
sampled). This CONFIRMS the winner market resolves on "who wins the game" with
no regulation-only qualifier (the standard sports-settlement convention: full
game including OT/SO), but does not spell out OT/SO in so many words -- the
brief's assumption (winner incl. OT/SO, SO = 1-goal margin) is adopted as
documented here rather than fabricated certainty.

The KXNHLTOTAL series' rules_secondary, however, DOES spell it out exactly
(ticker ``KXNHLTOTAL-26JUN14CARVGK-9``): "Goals scored during regulation and
overtime count as normal. If the game is decided by a shootout, the shootout
result will be recorded as one goal awarded to the winning team." This
confirms: (a) a real OT goal counts toward the total exactly like a
regulation goal (+1, no special handling needed -- already true of the raw
regulation-tie total before any OT/SO adjustment), and (b) a shootout also
adds exactly +1 to the total (credited to the winner), matching the brief's
"SO = 1-goal margin" assumption for the SPREAD side.

DISCREPANCY vs the brief's totals formula: the brief specifies
``reg_total + Bernoulli(OT_GOAL_PRE_SHOOTOUT)·1`` on tie mass (i.e. only a
~70% chance of the +1 bump, modeling "OT ends it before a shootout is
needed"). The probed settlement text above shows the REAL rule always adds
+1 on a regulation tie (whether decided in OT or via the shootout-credited
goal) -- i.e. the true probability of the totals bump is 100%, not 70%.
OT_GOAL_PRE_SHOOTOUT=0.70 is implemented here EXACTLY as the brief specifies
(this task's instructions call these "exact values" to ship verbatim, and
frame the constant as "auditable" -- a propose-then-promote tuning candidate,
not an independently-fit settlement fact), with this discrepancy on record
for whoever tunes it next: the honest prior, given the settlement text, is
that OT_GOAL_PRE_SHOOTOUT should converge toward 1.0, not 0.70.

PROBE 2 (build-time, 2026-07-12) -- probable starting goalies. Fetched
``.../hockey/nhl/scoreboard?dates=20260112`` (in-season date; NHL is
offseason in July). Every competitor on every event carried a `probables`
list keyed by ``name: "probableStartingGoalie"``, e.g. event 401803067 (FLA @
BUF): home (BUF) probable ``athlete.displayName == "Colten Ellis"``, away
(FLA) probable ``athlete.displayName == "Sergei Bobrovsky"``. `statistics` on
the probable entry itself was EMPTY (no season save% riding along), so the
goalie's quality has to come from our OWN boxscore history, exactly as the
brief specifies -- there is no keyless season-save% shortcut.

IMPORTANT: `autonomy/sports/espn.py`'s `Game.home_pitcher`/`away_pitcher`
fields (populated by `_probable_era` for EVERY league, not gated to
baseball) look like a ready-made hook for goalie identity, but are NOT used
here -- `_probable_era` reads ``probables[0].get("displayName")`` FIRST,
which for a hockey (or baseball) probables entry is the generic label
("Probable Starting Goalie" / "Probable Starting Pitcher"), not the athlete's
name; the athlete-name fallback is unreachable because that field is always
present and truthy. Confirmed by parsing the trimmed fixture below through
the real `parse_scoreboard`: `game.home_pitcher == "Probable Starting
Goalie"`, not "Colten Ellis". `espn.py`'s own docstring marks these fields
"(baseball only; None when absent)", so this is a pre-existing, out-of-scope
quirk (harmless for baseball today -- `home_pitcher` there is display-only,
never used in BaseballRunModel's math) rather than something WS-3 should
paper over by reusing it. This module parses `competitions[].competitors[].
probables[].athlete.displayName` itself, directly off the raw scoreboard
payload (`parse_probable_goalies`), independent of `Game`/`espn.py`.

PROBE 3 (build-time, 2026-07-12) -- goalie boxscore rows. Fetched
``.../hockey/nhl/summary?event=401803067`` (same FLA @ BUF game as WS-1's own
NHL boxscore probe). `boxscore["players"]` (a section `boxscores.py::
parse_team_boxscores` never touches -- that function only reads
`boxscore["teams"]`) has one entry per team, each with a `statistics` list of
per-position-group blocks; the block named ``"goalies"`` carries
``keys == ["goalsAgainst", "shotsAgainst", "shootoutSaves",
"shootoutShotsAgainst", "saves", "savePct", "evenStrengthSaves",
"powerPlaySaves", "shortHandedSaves", "timeOnIce", "ytdGoals",
"penaltyMinutes"]`` and one `athletes[]` entry per goalie who played
(`athlete.id`, `athlete.displayName`, `stats` aligned by index to `keys`).
Observed: FLA's Bobrovsky (id 5571, matching the scoreboard probable's
`playerId`) saves=20/shotsAgainst=23 (.870); BUF's Ellis (id 4736758, also
matching) saves=28/shotsAgainst=31 (.903). Trimmed fixtures committed at
tests/fixtures/boxscore_nhl_401803067_players.json (goalie rows) and
tests/fixtures/scoreboard_nhl_20260112_401803067.json (probables). This
module keys its own goalie store by (team, athlete display name) -- the ids
line up across both feeds but the extra plumbing to carry an id through
`Game`/the hook isn't needed when the display name is already the stable,
directly-observed join key in both payloads.

Live: time-scaled Poisson over minutes remaining (mirrors MLB's
`remaining_innings` -> "innings left / 9" ratio, here "minutes left / 60"),
plus a pulled-goalie empty-net inflation in the final
PULLED_GOALIE_FINAL_MINUTES.  Winner, spread, and total all consume the same
inflated remaining-goal lambdas so the live lattice cannot disagree with
itself during the exact empty-net window where scoring hazard changes most.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

from autonomy.sports.boxscores import BoxscoreStore, TeamBoxscore
from autonomy.sports.espn import Game

# v1: bivariate (independent-Poisson) goals + explicit OT/SO branch, goalie
# identity, special teams, pulled-goalie live inflation.
MODEL_VERSION = "nhl_bipoisson_ot_v1"

# -- team goal-rate EWMA + matchup ------------------------------------------
PRIOR_GOAL_RATE = 3.05          # brief's exact league-average GF/GA prior
EWMA_ALPHA = 0.10               # brief's exact value
HOME_EDGE = 0.18                # brief's exact value, goals; split +/- half
GOAL_MATRIX_TRUNCATION = 12     # brief's exact truncation

# -- cold-start reliability weighting (mirrors nba_model.py's `_metric`) ----
COLD_FULL_WEIGHT_GAMES = 25.0
COLD_WEIGHT_CAP = 0.85

# -- OT / shootout branch ----------------------------------------------------
OT_STRENGTH_TILT = 0.30         # brief's exact constant

# -- totals OT bump (see module docstring's DISCREPANCY note) ---------------
OT_GOAL_PRE_SHOOTOUT = 0.70     # brief's exact constant, shipped verbatim

# -- goalie layer -------------------------------------------------------------
GOALIE_PRIOR_SAVE_PCT = 0.905          # league-average NHL save %
GOALIE_EWMA_ALPHA = 0.10
GOALIE_DELTA_MAX = 0.25                # brief's exact bound, goals
# Calibration target for the propose-then-promote tuner (not independently
# fit here -- mirrors nba_model.py's own framing of its own constants):
# converts a goalie's save%-above-prior into a goal-rate shift on the
# opponent. At GOALIE_DELTA_SCALE=8.0, a goalie ~0.03 above/below the league
# prior (roughly the gap between an average starter and a truly elite/replacement
# one) reaches the +/-0.25 cap.
GOALIE_DELTA_SCALE = 8.0
GOALIE_UNKNOWN_UNCERTAINTY_BUMP = 0.03  # brief's exact bound
GOALIE_COLD_FULL_WEIGHT_STARTS = 20.0   # reliability weight on save% EWMA
ROOKIE_GOALIE_START_THRESHOLD = 10      # brief's self-derived proxy, exact

# -- special teams ------------------------------------------------------------
PRIOR_PP_PCT = 0.20
PRIOR_PK_PCT = 0.80
# Derived, not a magic zero: if both teams sit exactly at the league-average
# PP%/PK%, a team's power-play scoring rate should equal the league-average
# rate of goals allowed while shorthanded (same underlying population, two
# sides of the same coin), so the mismatch is 0 at the priors by construction.
LEAGUE_MEAN_SPECIAL_TEAMS_MISMATCH = PRIOR_PP_PCT - (1.0 - PRIOR_PK_PCT)
SPECIAL_TEAMS_SCALE = 0.5               # calibration target, not independently fit
SPECIAL_TEAMS_MAX_SHIFT = 0.15          # brief's exact bound

# -- warm gate (mirrors nba_model.py's MIN_GAMES_FOR_ENGINE) -----------------
MIN_GAMES_FOR_ENGINE = 5

# -- live ----------------------------------------------------------------------
REGULATION_MINUTES = 60.0
MINUTES_PER_PERIOD = 20.0
PULLED_GOALIE_FINAL_MINUTES = 3.0       # brief's exact bound
PULLED_GOALIE_MAX_DEFICIT = 2           # brief's exact bound
PULLED_GOALIE_TRAILING_MULT = 1.8       # brief's exact constant
PULLED_GOALIE_LEADING_MULT = 2.5        # brief's exact constant


# =============================================================== poisson math


def poisson_pmf(k: int, mean: float) -> float:
    """P(X == k) for a Poisson variable. No standalone version exists in
    autonomy/sports/baseball.py (only a CDF); a local one is used here rather
    than reverse-engineering it from `poisson_cdf`'s running-sum internals.
    """
    if k < 0:
        return 0.0
    mean = max(0.0, float(mean))
    return math.exp(-mean) * mean ** k / math.factorial(k)


def _pmf_array(mean: float, truncation: int = GOAL_MATRIX_TRUNCATION) -> list[float]:
    return [poisson_pmf(k, mean) for k in range(truncation + 1)]


@dataclass(frozen=True)
class RegulationSplit:
    """The full regulation-goal picture for one matchup (or one LIVE
    remaining-time slice, with `lead` folded in -- see `goal_split`).

    `margin_pmf`: home-margin (h - a, or lead + remaining h - a live) ->
    probability, EXCLUDING the tied cells (margin == 0 never appears; ties
    are broken out separately below since Kalshi settlement always resolves
    them via OT/SO, never as a push).
    `total_pmf`: index = combined goal total -> probability (regulation/
    remaining goals only, ties included at their own raw total) -- length
    2*truncation+2 so the OT/SO +1 bump always has room without truncation
    loss.
    `tie_total_pmf`: total -> probability, the SUBSET of `total_pmf`'s mass
    that came from a tied cell (this is exactly the mass `final_total_pmf`
    reallocates by OT_GOAL_PRE_SHOOTOUT).
    """
    reg_win: float
    reg_tie: float
    reg_loss: float
    margin_pmf: dict[int, float]
    total_pmf: list[float]
    tie_total_pmf: dict[int, float]


def goal_split(
    lead: int, home_mean: float, away_mean: float, truncation: int = GOAL_MATRIX_TRUNCATION,
) -> RegulationSplit:
    """The joint (home, away) goal matrix -- independent Poissons, truncated
    at `truncation` -- reduced to win/tie/loss mass, a home-margin PMF, and a
    total PMF, all measured against `lead` (pass lead=0 for a pre-game
    prediction; a live caller passes the CURRENT score lead and `home_mean`/
    `away_mean` scaled to the goals remaining -- see `NhlModel.predict`/
    `live_*_for` below). One function serves both pre-game and live pricing,
    exactly like nba_model.py's single Brownian-bridge formula serves both.
    """
    home_pmf = _pmf_array(home_mean, truncation)
    away_pmf = _pmf_array(away_mean, truncation)
    reg_win = reg_tie = reg_loss = 0.0
    margin_pmf: dict[int, float] = {}
    total_pmf = [0.0] * (2 * truncation + 2)
    tie_total_pmf: dict[int, float] = {}
    for h in range(truncation + 1):
        home_p = home_pmf[h]
        if home_p <= 0.0:
            continue
        for a in range(truncation + 1):
            p = home_p * away_pmf[a]
            if p <= 0.0:
                continue
            total_index = h + a
            total_pmf[total_index] += p
            final_margin = lead + h - a
            if final_margin > 0:
                reg_win += p
                margin_pmf[final_margin] = margin_pmf.get(final_margin, 0.0) + p
            elif final_margin < 0:
                reg_loss += p
                margin_pmf[final_margin] = margin_pmf.get(final_margin, 0.0) + p
            else:
                reg_tie += p
                tie_total_pmf[total_index] = tie_total_pmf.get(total_index, 0.0) + p
    return RegulationSplit(reg_win, reg_tie, reg_loss, margin_pmf, total_pmf, tie_total_pmf)


# ==================================================================== OT / SO


def win_prob_reg_normalized(reg_win: float, reg_loss: float) -> float:
    """The two-way regulation win share, excluding tie mass -- ambiguity
    resolution: reg_win / (reg_win + reg_loss)."""
    denom = reg_win + reg_loss
    if denom <= 0.0:
        return 0.5
    return reg_win / denom


def ot_win_probability(reg_win: float, reg_loss: float) -> float:
    """p_ot = 0.5 + 0.5*(win_prob_reg_normalized - 0.5)*OT_STRENGTH_TILT --
    brief's exact formula: near-coin, tilted slightly toward the side that
    was stronger in regulation."""
    normalized = win_prob_reg_normalized(reg_win, reg_loss)
    return 0.5 + 0.5 * (normalized - 0.5) * OT_STRENGTH_TILT


def home_win_probability(split: RegulationSplit) -> float:
    """P(home wins) = P(reg win) + P(reg tie)*p_ot -- brief's exact formula."""
    p_ot = ot_win_probability(split.reg_win, split.reg_loss)
    probability = split.reg_win + split.reg_tie * p_ot
    return min(0.995, max(0.005, probability))


def final_margin_pmf(split: RegulationSplit) -> dict[int, float]:
    """Home-margin PMF after OT/SO resolves every tied cell into a 1-goal
    decision (Kalshi: OT win AND shootout both settle as a 1-goal margin --
    see the module docstring's rules probe). No mass remains at margin 0.
    """
    p_ot = ot_win_probability(split.reg_win, split.reg_loss)
    pmf = dict(split.margin_pmf)
    pmf[1] = pmf.get(1, 0.0) + split.reg_tie * p_ot
    pmf[-1] = pmf.get(-1, 0.0) + split.reg_tie * (1.0 - p_ot)
    return pmf


# =================================================================== puck line


def home_cover_probability(split: RegulationSplit, threshold: float) -> float:
    """P(home final margin > threshold). At threshold=1.5 this is exactly
    P(reg margin >= 2) -- an OT/SO win (margin 1) never covers, since the
    OT/SO mass all lands at margin +/-1 (see `final_margin_pmf`)."""
    pmf = final_margin_pmf(split)
    probability = sum(p for m, p in pmf.items() if m > threshold)
    return min(0.995, max(0.005, probability))


def away_cover_probability(split: RegulationSplit, threshold: float) -> float:
    """P(away final margin > threshold), from the SAME split/distribution as
    `home_cover_probability` -- coherent by construction."""
    pmf = final_margin_pmf(split)
    probability = sum(p for m, p in pmf.items() if -m > threshold)
    return min(0.995, max(0.005, probability))


# ====================================================================== totals


def final_total_pmf(split: RegulationSplit) -> list[float]:
    """Regulation total PMF with the OT/shootout bump applied to TIE mass
    only: OT_GOAL_PRE_SHOOTOUT of each tied cell's probability moves from its
    raw total to total+1 (an OT/SO-decided game always scores exactly one
    more goal against the settlement total -- see the module docstring); the
    remaining (1-OT_GOAL_PRE_SHOOTOUT) share stays at the raw regulation
    total (brief's literal Bernoulli(0.7) formula, shipped verbatim -- see
    the DISCREPANCY note above about the real settlement rule).
    """
    pmf = list(split.total_pmf)
    last_index = len(pmf) - 1
    for total, mass in split.tie_total_pmf.items():
        move = mass * OT_GOAL_PRE_SHOOTOUT
        pmf[total] -= move
        target = min(total + 1, last_index)
        pmf[target] += move
    return pmf


def total_over_probability(pmf: list[float], threshold: float) -> float:
    probability = sum(p for k, p in enumerate(pmf) if k > threshold)
    return min(0.995, max(0.005, probability))


# ==================================================================== goalie


@dataclass
class NhlGoalieState:
    starts: int = 0
    save_pct_ewma: float = GOALIE_PRIOR_SAVE_PCT


@dataclass(frozen=True)
class GoalieBoxscore:
    game_id: str
    team: str
    name: str
    saves: float
    shots_against: float
    time_on_ice_minutes: float = 0.0


def _parse_time_on_ice(value: Any) -> float:
    """"MM:SS" -> minutes (float). Anything unparseable -> 0.0 (never blocks
    starter selection; see `NhlModel._update_goalie`)."""
    match = re.match(r"^(\d+):(\d{2})$", str(value or "").strip())
    if not match:
        return 0.0
    minutes, seconds = int(match.group(1)), int(match.group(2))
    return minutes + seconds / 60.0


def parse_goalie_boxscores(summary: dict[str, Any] | None) -> list[GoalieBoxscore]:
    """Extract each team's goalie row(s) from `boxscore["players"]` (a
    section autonomy/sports/boxscores.py::parse_team_boxscores never reads --
    that function only covers `boxscore["teams"]`). See the module docstring
    PROBE 3 for the exact observed shape. Fail-closed: no game id or no
    players section -> [].
    """
    payload = summary or {}
    game_id = str((payload.get("header") or {}).get("id") or "")
    if not game_id:
        return []
    players = (payload.get("boxscore") or {}).get("players") or []
    rows: list[GoalieBoxscore] = []
    for team_entry in players:
        abbreviation = (team_entry.get("team") or {}).get("abbreviation")
        if not abbreviation:
            continue
        for stat_group in team_entry.get("statistics") or []:
            if stat_group.get("name") != "goalies":
                continue
            keys = stat_group.get("keys") or []
            for athlete_row in stat_group.get("athletes") or []:
                athlete = athlete_row.get("athlete") or {}
                name = athlete.get("displayName")
                stats = athlete_row.get("stats") or []
                if not name or len(stats) != len(keys):
                    continue
                values = dict(zip(keys, stats))
                try:
                    saves = float(values["saves"])
                    shots_against = float(values["shotsAgainst"])
                except (KeyError, TypeError, ValueError):
                    continue
                rows.append(GoalieBoxscore(
                    game_id=game_id, team=str(abbreviation).upper(), name=name,
                    saves=saves, shots_against=shots_against,
                    time_on_ice_minutes=_parse_time_on_ice(values.get("timeOnIce")),
                ))
    return rows


def parse_probable_goalies(payload: dict[str, Any] | None) -> dict[str, tuple[str | None, str | None]]:
    """game_id -> (home_goalie_name, away_goalie_name) from a raw ESPN NHL
    scoreboard payload's `competitions[].competitors[].probables`. Both
    entries are None when a competitor has no `probables` block (fail-closed:
    the caller degrades to the unknown-goalie branch rather than fabricate an
    identity -- see the module docstring PROBE 2).
    """
    result: dict[str, tuple[str | None, str | None]] = {}
    for event in (payload or {}).get("events") or []:
        game_id = str(event.get("id") or "")
        comps = event.get("competitions") or []
        if not game_id or not comps:
            continue
        home_name = away_name = None
        for competitor in comps[0].get("competitors") or []:
            name = _probable_goalie_name(competitor)
            if competitor.get("homeAway") == "home":
                home_name = name
            elif competitor.get("homeAway") == "away":
                away_name = name
        result[game_id] = (home_name, away_name)
    return result


def _probable_goalie_name(competitor: dict[str, Any]) -> str | None:
    probables = competitor.get("probables") or []
    if not probables:
        return None
    athlete = (probables[0] or {}).get("athlete") or {}
    return athlete.get("displayName") or athlete.get("fullName")


def goalie_metric_weight(starts: int) -> float:
    return min(COLD_WEIGHT_CAP, starts / GOALIE_COLD_FULL_WEIGHT_STARTS)


def goalie_save_pct(state: NhlGoalieState | None) -> tuple[float, int]:
    """(reliability-weighted save%, starts) -- a cold/never-seen goalie
    blends fully to the league prior, same cold-start shape as
    nba_model.py's `_metric`."""
    if state is None:
        return GOALIE_PRIOR_SAVE_PCT, 0
    weight = goalie_metric_weight(state.starts)
    blended = (1.0 - weight) * GOALIE_PRIOR_SAVE_PCT + weight * state.save_pct_ewma
    return blended, state.starts


def goalie_delta(save_pct: float) -> float:
    """Positive => better-than-average goalie => shifts the OPPONENT's
    (shooting team's) lambda DOWN. Bounded to +/-GOALIE_DELTA_MAX (brief's
    exact bound)."""
    raw = (save_pct - GOALIE_PRIOR_SAVE_PCT) * GOALIE_DELTA_SCALE
    return max(-GOALIE_DELTA_MAX, min(GOALIE_DELTA_MAX, raw))


def is_rookie_goalie(state: NhlGoalieState | None) -> bool:
    """Self-derived rookie proxy (brief's chosen fallback over a keyless
    roster-experience probe): fewer than ROOKIE_GOALIE_START_THRESHOLD starts
    in OUR OWN store. A goalie we've never seen counts as a rookie."""
    starts = state.starts if state is not None else 0
    return starts < ROOKIE_GOALIE_START_THRESHOLD


# ============================================================== special teams


def special_teams_shift(pp_subject: float, pk_opponent: float) -> float:
    """Bounded lambda shift for `subject` from the mismatch between its own
    power-play EWMA and the opponent's penalty-kill EWMA, relative to the
    league-average mismatch (0 at the priors -- see
    LEAGUE_MEAN_SPECIAL_TEAMS_MISMATCH)."""
    mismatch = (pp_subject - (1.0 - pk_opponent)) - LEAGUE_MEAN_SPECIAL_TEAMS_MISMATCH
    raw = mismatch * SPECIAL_TEAMS_SCALE
    return max(-SPECIAL_TEAMS_MAX_SHIFT, min(SPECIAL_TEAMS_MAX_SHIFT, raw))


# ================================================================== live math


def _parse_clock_minutes(display_clock: str | None) -> float | None:
    """ESPN "status.displayClock" ("M:SS"/"MM:SS") -> minutes remaining IN
    THE CURRENT PERIOD. Fail-closed on anything else (mirrors
    nba_model.py::parse_clock_minutes; kept local/self-contained per this
    package's per-sport-module convention rather than cross-imported)."""
    if not display_clock:
        return None
    match = re.match(r"^(\d+):(\d{2})$", display_clock.strip())
    if not match:
        return None
    minutes, seconds = int(match.group(1)), int(match.group(2))
    return minutes + seconds / 60.0


def minutes_remaining_in_game(period: int | None, display_clock: str | None) -> float | None:
    """Total regulation-basis minutes left, given the current period (1-3)
    and that period's display clock. None on any missing/unparseable input.
    OT (period >= 4): only the current extra period's own clock counts, same
    regulation-basis approximation as nba_model.py's OT handling."""
    if period is None or period < 1:
        return None
    clock_minutes = _parse_clock_minutes(display_clock)
    if clock_minutes is None:
        return None
    if period <= 3:
        remaining_full_periods = 3 - period
        return remaining_full_periods * MINUTES_PER_PERIOD + clock_minutes
    return clock_minutes


def pulled_goalie_lambdas(
    lambda_home: float, lambda_away: float, home_score: int, away_score: int,
    minutes_remaining: float,
) -> tuple[float, float]:
    """(adjusted_home, adjusted_away) remaining-goal means with empty-net
    inflation applied ONLY inside the final PULLED_GOALIE_FINAL_MINUTES with
    a nonzero deficit of at most PULLED_GOALIE_MAX_DEFICIT (brief's exact
    bounds). The TRAILING team pulls its own goalie for an extra attacker
    (a modest boost to ITS OWN scoring rate); the LEADING team suddenly faces
    an empty net (a much larger boost to ITS scoring rate on any clean look).
    Winner, spread, and total live paths all consume this same adjusted pair
    so their probabilities remain coherent in the pulled-goalie window.
    """
    if minutes_remaining > PULLED_GOALIE_FINAL_MINUTES:
        return lambda_home, lambda_away
    deficit = home_score - away_score
    if deficit == 0 or abs(deficit) > PULLED_GOALIE_MAX_DEFICIT:
        return lambda_home, lambda_away
    if deficit < 0:  # home trailing
        return lambda_home * PULLED_GOALIE_TRAILING_MULT, lambda_away * PULLED_GOALIE_LEADING_MULT
    return lambda_home * PULLED_GOALIE_LEADING_MULT, lambda_away * PULLED_GOALIE_TRAILING_MULT


# ======================================================================= state


def _ewma(previous: float, value: float, alpha: float = EWMA_ALPHA) -> float:
    return alpha * value + (1.0 - alpha) * previous


def _rate(numerator: Any, denominator: Any) -> float | None:
    try:
        n = float(numerator)
        d = float(denominator)
    except (TypeError, ValueError):
        return None
    if d <= 0:
        return None
    return n / d


@dataclass
class NhlTeamState:
    games: int = 0
    gf_ewma: float = PRIOR_GOAL_RATE
    ga_ewma: float = PRIOR_GOAL_RATE
    pp_pct_ewma: float = PRIOR_PP_PCT
    pk_pct_ewma: float = PRIOR_PK_PCT


@dataclass(frozen=True)
class NhlPrediction:
    home_win_probability: float
    expected_home_goals: float
    expected_away_goals: float
    expected_total: float
    lambda_home: float
    lambda_away: float
    winner_uncertainty: float
    total_uncertainty: float
    goalie_known_home: bool
    goalie_known_away: bool
    rookie_goalie_home: bool
    rookie_goalie_away: bool
    goalie_delta_home: float
    goalie_delta_away: float
    special_teams_shift_home: float
    special_teams_shift_away: float
    sample_games: int
    split: RegulationSplit
    model_version: str = MODEL_VERSION

    @property
    def expected_home_score(self) -> float:  # sports_intelligence.py's generic report fields
        return self.expected_home_goals

    @property
    def expected_away_score(self) -> float:
        return self.expected_away_goals


# =============================================================== the model


@dataclass
class NhlModel:
    teams: dict[str, NhlTeamState] = field(default_factory=dict)
    goalies: dict[str, NhlGoalieState] = field(default_factory=dict)
    processed_game_ids: set[str] = field(default_factory=set)
    games_seen: int = 0

    def _team(self, abbreviation: str) -> NhlTeamState:
        return self.teams.setdefault(abbreviation.upper(), NhlTeamState())

    @staticmethod
    def _goalie_key(team: str, name: str) -> str:
        return f"{team.upper()}|{name}"

    def _goalie(self, team: str, name: str | None) -> NhlGoalieState | None:
        if not name:
            return None
        return self.goalies.get(self._goalie_key(team, name))

    def _metric(self, state: NhlTeamState, field_name: str, prior: float) -> float:
        weight = min(COLD_WEIGHT_CAP, state.games / COLD_FULL_WEIGHT_GAMES)
        return (1.0 - weight) * prior + weight * float(getattr(state, field_name))

    # -- learning (settlement-only; see `update`'s gate) ---------------------

    def _update_goalie(self, team: str, rows: list[GoalieBoxscore]) -> None:
        if not rows:
            return
        starter = max(rows, key=lambda row: row.time_on_ice_minutes)
        if starter.shots_against <= 0:
            return
        key = self._goalie_key(team, starter.name)
        state = self.goalies.setdefault(key, NhlGoalieState())
        save_pct = starter.saves / starter.shots_against
        state.save_pct_ewma = _ewma(state.save_pct_ewma, save_pct, GOALIE_EWMA_ALPHA)
        state.starts += 1

    def update(
        self, game: Game, home_box: TeamBoxscore | None, away_box: TeamBoxscore | None,
        home_goalies: Sequence[GoalieBoxscore] = (), away_goalies: Sequence[GoalieBoxscore] = (),
    ) -> bool:
        """Settlement-only learning (point-in-time honesty): refuses anything
        but a completed final with both teams' WS-1 boxscores. Idempotent by
        game_id. Live state never enters here."""
        if (
            game.game_id in self.processed_game_ids
            or game.status != "post"
            or game.home_score is None
            or game.away_score is None
            or home_box is None
            or away_box is None
        ):
            return False
        home = self._team(game.home)
        away = self._team(game.away)
        home.gf_ewma = _ewma(home.gf_ewma, float(game.home_score))
        home.ga_ewma = _ewma(home.ga_ewma, float(game.away_score))
        away.gf_ewma = _ewma(away.gf_ewma, float(game.away_score))
        away.ga_ewma = _ewma(away.ga_ewma, float(game.home_score))

        home_pp = _rate(home_box.stats.get("powerPlayGoals"), home_box.stats.get("powerPlayOpportunities"))
        away_pp = _rate(away_box.stats.get("powerPlayGoals"), away_box.stats.get("powerPlayOpportunities"))
        if home_pp is not None:
            home.pp_pct_ewma = _ewma(home.pp_pct_ewma, home_pp)
            away.pk_pct_ewma = _ewma(away.pk_pct_ewma, 1.0 - home_pp)
        if away_pp is not None:
            away.pp_pct_ewma = _ewma(away.pp_pct_ewma, away_pp)
            home.pk_pct_ewma = _ewma(home.pk_pct_ewma, 1.0 - away_pp)

        self._update_goalie(game.home, list(home_goalies))
        self._update_goalie(game.away, list(away_goalies))

        home.games += 1
        away.games += 1
        self.games_seen += 1
        self.processed_game_ids.add(game.game_id)
        return True

    # -- pre-game --------------------------------------------------------

    def predict(
        self, game: Game, home_goalie_name: str | None = None, away_goalie_name: str | None = None,
    ) -> NhlPrediction:
        home = self._team(game.home)
        away = self._team(game.away)
        gf_home = self._metric(home, "gf_ewma", PRIOR_GOAL_RATE)
        ga_home = self._metric(home, "ga_ewma", PRIOR_GOAL_RATE)
        gf_away = self._metric(away, "gf_ewma", PRIOR_GOAL_RATE)
        ga_away = self._metric(away, "ga_ewma", PRIOR_GOAL_RATE)
        lambda_home = (gf_home + ga_away) / 2.0 + HOME_EDGE / 2.0
        lambda_away = (gf_away + ga_home) / 2.0 - HOME_EDGE / 2.0

        # -- goalie layer: known -> mean shift (bounded); unknown -> widen
        # uncertainty only, never touch the mean (see module docstring).
        goalie_known_home = home_goalie_name is not None
        goalie_known_away = away_goalie_name is not None
        home_goalie_state = self._goalie(game.home, home_goalie_name)
        away_goalie_state = self._goalie(game.away, away_goalie_name)
        delta_home = delta_away = 0.0
        rookie_home = rookie_away = False
        if goalie_known_home:
            save_pct_home, _ = goalie_save_pct(home_goalie_state)
            delta_home = goalie_delta(save_pct_home)
            lambda_away -= delta_home
            rookie_home = is_rookie_goalie(home_goalie_state)
        if goalie_known_away:
            save_pct_away, _ = goalie_save_pct(away_goalie_state)
            delta_away = goalie_delta(save_pct_away)
            lambda_home -= delta_away
            rookie_away = is_rookie_goalie(away_goalie_state)

        # -- special teams: bounded lambda shift, always applied (a cold
        # team's PP/PK EWMAs blend to the league prior via `_metric`, so this
        # is a genuine no-op -- not a mean shift -- until we have data).
        pp_home = self._metric(home, "pp_pct_ewma", PRIOR_PP_PCT)
        pk_home = self._metric(home, "pk_pct_ewma", PRIOR_PK_PCT)
        pp_away = self._metric(away, "pp_pct_ewma", PRIOR_PP_PCT)
        pk_away = self._metric(away, "pk_pct_ewma", PRIOR_PK_PCT)
        st_shift_home = special_teams_shift(pp_home, pk_away)
        st_shift_away = special_teams_shift(pp_away, pk_home)
        lambda_home = max(0.1, lambda_home + st_shift_home)
        lambda_away = max(0.1, lambda_away + st_shift_away)

        split = goal_split(0, lambda_home, lambda_away)

        sample = min(home.games, away.games)
        cold = 1.0 / math.sqrt(1.0 + sample / 8.0)
        winner_uncertainty = min(0.42, 0.10 + 0.20 * cold)
        total_uncertainty = min(0.44, 0.12 + 0.20 * cold)
        if not goalie_known_home:
            winner_uncertainty = min(0.45, winner_uncertainty + GOALIE_UNKNOWN_UNCERTAINTY_BUMP)
            total_uncertainty = min(0.45, total_uncertainty + GOALIE_UNKNOWN_UNCERTAINTY_BUMP)
        if not goalie_known_away:
            winner_uncertainty = min(0.45, winner_uncertainty + GOALIE_UNKNOWN_UNCERTAINTY_BUMP)
            total_uncertainty = min(0.45, total_uncertainty + GOALIE_UNKNOWN_UNCERTAINTY_BUMP)

        return NhlPrediction(
            home_win_probability=home_win_probability(split),
            expected_home_goals=lambda_home,
            expected_away_goals=lambda_away,
            expected_total=lambda_home + lambda_away,
            lambda_home=lambda_home,
            lambda_away=lambda_away,
            winner_uncertainty=winner_uncertainty,
            total_uncertainty=total_uncertainty,
            goalie_known_home=goalie_known_home,
            goalie_known_away=goalie_known_away,
            rookie_goalie_home=rookie_home,
            rookie_goalie_away=rookie_away,
            goalie_delta_home=delta_home,
            goalie_delta_away=delta_away,
            special_teams_shift_home=st_shift_home,
            special_teams_shift_away=st_shift_away,
            sample_games=sample,
            split=split,
        )

    def cover_probability(self, prediction: NhlPrediction, subject_is_home: bool, threshold: float) -> float:
        fn = home_cover_probability if subject_is_home else away_cover_probability
        return fn(prediction.split, threshold)

    def total_probability(self, prediction: NhlPrediction, threshold: float) -> float:
        return total_over_probability(final_total_pmf(prediction.split), threshold)

    # -- live -------------------------------------------------------------

    def live_win_probability_for(
        self, prediction: NhlPrediction, home_score: int, away_score: int, minutes_remaining: float,
    ) -> float:
        """Time-scaled remaining goals with the shared pulled-goalie state."""
        fraction = max(0.0, float(minutes_remaining)) / REGULATION_MINUTES
        remaining_home = prediction.lambda_home * fraction
        remaining_away = prediction.lambda_away * fraction
        adjusted_home, adjusted_away = pulled_goalie_lambdas(
            remaining_home, remaining_away, home_score, away_score, minutes_remaining)
        lead = int(home_score) - int(away_score)
        split = goal_split(lead, adjusted_home, adjusted_away)
        return home_win_probability(split)

    def live_spread_probability_for(
        self, prediction: NhlPrediction, subject_is_home: bool, threshold: float,
        home_score: int, away_score: int, minutes_remaining: float,
    ) -> float:
        fraction = max(0.0, float(minutes_remaining)) / REGULATION_MINUTES
        remaining_home = prediction.lambda_home * fraction
        remaining_away = prediction.lambda_away * fraction
        adjusted_home, adjusted_away = pulled_goalie_lambdas(
            remaining_home, remaining_away, home_score, away_score, minutes_remaining)
        lead = int(home_score) - int(away_score)
        split = goal_split(lead, adjusted_home, adjusted_away)
        fn = home_cover_probability if subject_is_home else away_cover_probability
        return fn(split, threshold)

    def live_total_probability_for(
        self, prediction: NhlPrediction, current_total: float, threshold: float,
        home_score: int, away_score: int, minutes_remaining: float,
    ) -> float:
        fraction = max(0.0, float(minutes_remaining)) / REGULATION_MINUTES
        remaining_home = prediction.lambda_home * fraction
        remaining_away = prediction.lambda_away * fraction
        adjusted_home, adjusted_away = pulled_goalie_lambdas(
            remaining_home, remaining_away, home_score, away_score, minutes_remaining)
        lead = int(home_score) - int(away_score)
        split = goal_split(lead, adjusted_home, adjusted_away)
        pmf = final_total_pmf(split)
        return total_over_probability(pmf, threshold - float(current_total))

    # -- persistence --------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_version": MODEL_VERSION,
            "teams": {key: asdict(value) for key, value in self.teams.items()},
            "goalies": {key: asdict(value) for key, value in self.goalies.items()},
            "processed_game_ids": sorted(self.processed_game_ids),
            "games_seen": self.games_seen,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NhlModel":
        return cls(
            teams={key: NhlTeamState(**value) for key, value in data.get("teams", {}).items()},
            goalies={key: NhlGoalieState(**value) for key, value in data.get("goalies", {}).items()},
            processed_game_ids=set(data.get("processed_game_ids", [])),
            games_seen=int(data.get("games_seen", 0)),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(path)

    @classmethod
    def load(cls, path: Path) -> "NhlModel":
        if path.exists():
            try:
                return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                pass
        return cls()


# ================================================================ warm gate


def boxscore_games_available(store: BoxscoreStore, team: str, floor: int = MIN_GAMES_FOR_ENGINE) -> int:
    return len(store.recent(team, n=floor))


def is_warm(store: BoxscoreStore, home: str, away: str) -> bool:
    """True iff WS-1's BoxscoreStore has >= MIN_GAMES_FOR_ENGINE games for
    BOTH teams -- the fallback gate (never a half-blend), mirrors
    nba_model.py::is_warm exactly."""
    return (
        boxscore_games_available(store, home) >= MIN_GAMES_FOR_ENGINE
        and boxscore_games_available(store, away) >= MIN_GAMES_FOR_ENGINE
    )
