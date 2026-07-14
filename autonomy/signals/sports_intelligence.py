"""Settlement-trained sports intelligence challengers (MLB + team leagues)."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from autonomy.live_odds import EspnSummaryBook
from autonomy.ontology import MarketView, Signal, Vertical
from core.logger import logger
from autonomy.sports import boxscores as boxscores_module
from autonomy.sports.baseball import (
    BaseballRunModel,
    remaining_innings,
    rest_travel_uncertainty_bump,
)
from autonomy.sports.boxscores import BoxscoreStore, parse_team_boxscores
from autonomy.sports.college import (
    BASE_ABS_MARGIN_PMF_COLLEGE,
    NCAAF_MODEL_VERSION,
    NCAAMB_PARAMS,
    ncaaf_college,
    parse_neutral_site,
)
from autonomy.sports.elo import EloModel
from autonomy.sports.espn import EspnClient, Game, canonical_team, default_fetch_scoreboard
from autonomy.sports.football_weather import default_fetch_football_weather, football_weather_adjustment
from autonomy.sports.injuries import InjuryBook
from autonomy.sports.nba_model import (
    MARGIN_SIGMA_BASE as NBA_MARGIN_SIGMA_BASE,
    MODEL_VERSION as NBA_MODEL_VERSION,
    NbaModel,
    is_warm as nba_is_warm,
    minutes_remaining_in_game as nba_minutes_remaining,
    spread_cover_probability as nba_spread_cover_probability,
    win_probability_from_margin as nba_win_probability_from_margin,
)
from autonomy.sports.nfl_margin import (
    margin_distribution as power_ratings_margin_distribution,
    spread_cover_probability as power_ratings_nfl_spread_cover_probability,
    win_probability as power_ratings_nfl_win_probability,
)
from autonomy.sports.nhl_model import (
    MODEL_VERSION as NHL_MODEL_VERSION,
    NhlModel,
    is_warm as nhl_is_warm,
    minutes_remaining_in_game as nhl_minutes_remaining,
    parse_goalie_boxscores,
    parse_probable_goalies,
)
from autonomy.sports.power_ratings import (
    ConsensusMargin,
    EloSource,
    EspnBpiSource,
    EspnFpiSource,
    consensus_margin,
)
from autonomy.sports.ratings_solvers import ColleyRatingSource, MasseyRatingSource
from autonomy.sports.players import (
    LEAGUE_POINT_SCALE,
    LeagueInjuryBook,
    RookieBook,
    TeamAvailability,
    apply_margin_shift_to_scores,
    availability_effect,
    bounded_mismatch_score,
    mismatch_margin_shift,
    shift_probability_by_margin,
)
from autonomy.sports.situations import (
    GameDateTracker,
    PlayoffBook,
    PlayoffState,
    RestEffect,
    RosterDriftBook,
    nfl_rest_effect,
    nhl_rest_effect,
    playoff_soft_effect,
    roster_soft_effect,
)
from autonomy.sports.team_scores import LEAGUE_SCORE_CONFIGS, TeamScoreModel

# WS-1's fetch-budget guidance ("~16/day/league"), applied here since WS-2's
# NBA engine is BoxscoreStore's first consumer (see boxscores.py's WS-1
# report: "the fetch-budget/try-except-continue loop ... belongs to
# whichever later workstream wires BoxscoreStore into a daemon/warmup
# script -- WS-2 is the first consumer"). WS-3's NHL engine reuses the same
# budget for its own boxscore+goalie fetch.
NBA_BOXSCORE_FETCH_BUDGET = 16
NHL_BOXSCORE_FETCH_BUDGET = 16
NCAAMB_BOXSCORE_FETCH_BUDGET = 16

MODEL_DIR = Path("runtime/autonomy")
# WS-4: shared with autonomy/signals/sports_elo.py's own ELO_DIR -- this
# signal reads the ncaaf Elo ratings that signal already trains every cycle
# (registered together in the same session, see autonomy/session.py) rather
# than retraining a second copy here.
ELO_DIR = Path("runtime/autonomy")
_MONTHS = {month: index for index, month in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"),
    start=1,
)}
_MLB_TEAMS = {
    "AZ", "ATL", "BAL", "BOS", "CHC", "CIN", "CLE", "COL", "CWS", "DET",
    "HOU", "KC", "LAA", "LAD", "MIA", "MIL", "MIN", "NYM", "NYY", "OAK",
    "ATH", "PHI", "PIT", "SD", "SEA", "SF", "STL", "TB", "TEX", "TOR", "WSH",
}
_TEAM_WINNER_SERIES = {
    "KXNBAGAME": "nba",
    "KXNFLGAME": "nfl",
    "KXNCAAFGAME": "ncaaf",
    "KXNHLGAME": "nhl",
    "KXNCAAMBGAME": "ncaamb",
}
_TEAM_TOTAL_SERIES = {
    "KXNBATOTAL": "nba",
    "KXNFLTOTAL": "nfl",
    "KXNCAAFTOTAL": "ncaaf",
    "KXNHLTOTAL": "nhl",
    "KXNCAAMBTOTAL": "ncaamb",
}
_TEAM_SPREAD_SERIES = {
    "KXNBASPREAD": "nba",
    "KXNFLSPREAD": "nfl",
    "KXNCAAFSPREAD": "ncaaf",
    "KXNHLSPREAD": "nhl",
    "KXNCAAMBSPREAD": "ncaamb",
}


@dataclass(frozen=True)
class SportsContract:
    sport: str
    market_type: str
    date_yyyymmdd: str
    competitors: tuple[str, str] | None = None
    subject: str | None = None
    threshold: float | None = None
    fight_code: str | None = None


def _date_and_remainder(token: str) -> tuple[str, str] | None:
    match = re.match(r"^(\d{2})([A-Z]{3})(\d{2})(.*)$", token.upper())
    if not match:
        return None
    year, month_name, day, remainder = match.groups()
    month = _MONTHS.get(month_name)
    if month is None:
        return None
    return f"20{year}{month:02d}{int(day):02d}", remainder


def _strip_start_time(remainder: str) -> str:
    return remainder[4:] if len(remainder) >= 8 and remainder[:4].isdigit() else remainder


def _split_mlb_teams(token: str) -> tuple[str, str] | None:
    for first in sorted(_MLB_TEAMS, key=len, reverse=True):
        if not token.startswith(first):
            continue
        second = token[len(first):]
        if second in _MLB_TEAMS:
            return canonical_team("mlb", first), canonical_team("mlb", second)
    return None


def parse_sports_contract(market: MarketView) -> SportsContract | None:
    parts = market.ticker.upper().split("-")
    if len(parts) < 2:
        return None
    series = parts[0]
    dated = _date_and_remainder(parts[1])
    if dated is None:
        return None
    date_yyyymmdd, remainder = dated

    if series in _TEAM_WINNER_SERIES:
        from autonomy.signals.sports_elo import parse_game_ticker

        parsed = parse_game_ticker(market.ticker)
        if parsed is None:
            return None
        return SportsContract(
            parsed["league"], "winner", parsed["date_yyyymmdd"],
            (parsed["subject"], parsed["opponent"]), subject=parsed["subject"],
        )

    if series in _TEAM_TOTAL_SERIES:
        threshold = market.raw.get("floor_strike")
        try:
            parsed_threshold = float(threshold)
        except (TypeError, ValueError):
            return None
        title = re.sub(r"\s+(?:Total (?:Points|Goals)|Goal Total|Total)\??$", "", market.title, flags=re.IGNORECASE)
        names = re.split(r"\s+vs\.?\s+", title, maxsplit=1, flags=re.IGNORECASE)
        if len(names) != 2:
            return None
        return SportsContract(
            _TEAM_TOTAL_SERIES[series], "total", date_yyyymmdd,
            (names[0].strip(), names[1].strip()), threshold=parsed_threshold,
        )

    if series in _TEAM_SPREAD_SERIES:
        # e.g. KXNFLSPREAD-26SEP13KCBUF-KC3: subject abbreviation + strike
        # index in the suffix; the real margin line is floor_strike, and the
        # full team names ride the title ("Chiefs vs Bills Spread...").
        if len(parts) < 3:
            return None
        subject_match = re.match(r"^([A-Z]+?)\d+$", parts[2])
        if subject_match is None:
            return None
        threshold = market.raw.get("floor_strike")
        try:
            parsed_threshold = float(threshold)
        except (TypeError, ValueError):
            return None
        title = re.sub(r"\s+Spread.*$", "", market.title, flags=re.IGNORECASE)
        names = re.split(r"\s+vs\.?\s+", title, maxsplit=1, flags=re.IGNORECASE)
        if len(names) != 2:
            return None
        return SportsContract(
            _TEAM_SPREAD_SERIES[series], "spread", date_yyyymmdd,
            (names[0].strip(), names[1].strip()),
            subject=subject_match.group(1), threshold=parsed_threshold,
        )

    if series in {"KXMLBGAME", "KXMLBTOTAL", "KXMLBRFI", "KXMLBSPREAD"}:
        teams = _split_mlb_teams(_strip_start_time(remainder))
        if teams is None:
            return None
        if series == "KXMLBGAME":
            if len(parts) < 3:
                return None
            return SportsContract(
                "mlb", "winner", date_yyyymmdd, teams,
                subject=canonical_team("mlb", parts[2]),
            )
        if series == "KXMLBTOTAL":
            threshold = market.raw.get("floor_strike")
            try:
                parsed_threshold = float(threshold)
            except (TypeError, ValueError):
                return None
            return SportsContract(
                "mlb", "total_runs", date_yyyymmdd, teams, threshold=parsed_threshold,
            )
        if series == "KXMLBSPREAD":
            # e.g. KXMLBSPREAD-26JUL112110AZLAD-AZ8 -> subject "AZ", floor 7.5
            # ("wins by over 7.5 runs"). The ticker suffix is TEAM + strike index;
            # the real margin line is the market's floor_strike.
            if len(parts) < 3:
                return None
            subject_match = re.match(r"^([A-Z]+?)\d+$", parts[2])
            if subject_match is None:
                return None
            threshold = market.raw.get("floor_strike")
            try:
                parsed_threshold = float(threshold)
            except (TypeError, ValueError):
                return None
            return SportsContract(
                "mlb", "spread", date_yyyymmdd, teams,
                subject=canonical_team("mlb", subject_match.group(1)),
                threshold=parsed_threshold,
            )
        return SportsContract("mlb", "yrfi", date_yyyymmdd, teams)

    return None


def _date_range(days_back: int = 2) -> str:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=days_back)
    return f"{start.strftime('%Y%m%d')}-{today.strftime('%Y%m%d')}"


# How far back MasseyRatingSource/ColleyRatingSource look to build their
# settled-game graph, and how the window is chunked (mirrors
# scripts/run_dummy_sports_warmup.py's own chunking for the same reason:
# keep each individual ESPN scoreboard fetch to a bounded date span rather
# than one huge multi-month request). Both are solved ONCE per
# PowerRatingsSignal instance (construction time), not re-solved every
# cycle -- "Keep per-cycle warm cost sane" per the WS-A1b brief -- so this
# cost is paid once per process, same as FPI/BPI's per-instance fetch cache.
MASSEY_COLLEY_WARMUP_DAYS_BACK = 120
MASSEY_COLLEY_WARMUP_CHUNK_DAYS = 15


def _massey_colley_date_ranges(
    days_back: int = MASSEY_COLLEY_WARMUP_DAYS_BACK,
    chunk_days: int = MASSEY_COLLEY_WARMUP_CHUNK_DAYS,
) -> list[str]:
    today = datetime.now(timezone.utc).date()
    ranges: list[str] = []
    start = today - timedelta(days=days_back)
    while start < today:
        end = min(today, start + timedelta(days=chunk_days - 1))
        ranges.append(f"{start.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}")
        start = end + timedelta(days=1)
    return ranges


class BaseballIntelligenceSignal:
    """Challenger forecasts for MLB winner, total runs, and YRFI/NRFI."""

    name = "mlb_intelligence"

    def __init__(
        self,
        espn: EspnClient | None = None,
        model: BaseballRunModel | None = None,
        model_path: Path | None = None,
        injuries: "InjuryBook | None" = None,
        seasons: Any = None,
        live_book: EspnSummaryBook | None = None,
    ) -> None:
        from autonomy.specialists.seasons import SeasonMonitor

        self.espn = espn or EspnClient()
        self.model_path = model_path or MODEL_DIR / "mlb_runs_model.json"
        self.model = model or BaseballRunModel.load(self.model_path)
        self.injuries = injuries or InjuryBook()
        self.seasons = seasons or SeasonMonitor(espn=self.espn)
        # WS-11: live base-out state (plays[-1].onFirst/onSecond/onThird +
        # outs), read from the same ESPN-summary endpoint the sharp-book live
        # de-vig already uses. A fetch failure or missing plays -> None,
        # which is a fail-closed no-op on live_total_probability.
        self.live_book = live_book or EspnSummaryBook(league="mlb")

    def warmup(self, date_ranges: list[str]) -> int:
        updated = 0
        games: list[Any] = []
        for dates in date_ranges:
            games.extend(self.espn.games("mlb", dates))
        for game in sorted(games, key=lambda item: item.date):
            updated += int(self.model.update(game))
        if updated:
            self.model.save(self.model_path)
        return updated

    def on_cycle_start(self) -> None:
        # Season gate: MLB sleeps Nov-Feb. No wake backfill needed -- a
        # genuine wake follows an offseason with no games behind it, and a
        # false-dormant blip (bounded by the gate's TTL) is covered by this
        # recent-days warmup window on the next active cycle.
        if not self.seasons.active("mlb"):
            return
        self.espn.clear_cache()
        self.warmup([_date_range()])
        self.espn.clear_cache()
        self.injuries.refresh()  # refresh availability once per cycle
        self.live_book.clear()  # re-read in-play base-out state each cycle

    def applicable(self, market: MarketView) -> bool:
        parsed = parse_sports_contract(market)
        return market.vertical is Vertical.SPORTS and parsed is not None and parsed.sport == "mlb"

    def _previous_start(self, team: str, before_date_yyyymmdd: str, exclude_game_id: str) -> str | None:
        """Most recent OTHER game's start time for `team` strictly before the
        given date, from the signal's own recent-days ESPN cache ("our
        stores") -- no dedicated network fetch. Fail-closed to None on any
        lookup problem.
        """
        try:
            games = self.espn.games("mlb", _date_range())
        except Exception:
            return None
        candidates = [
            g for g in games
            if g.game_id != exclude_game_id
            and g.date
            and g.date[:10].replace("-", "") < before_date_yyyymmdd
            and (canonical_team("mlb", g.home) == team or canonical_team("mlb", g.away) == team)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda g: g.date).date

    def _rest_travel_uncertainty(self, game: Any) -> float:
        today = game.date[:10].replace("-", "") if game.date else ""
        if not today:
            return 0.0
        for team in (canonical_team("mlb", game.home), canonical_team("mlb", game.away)):
            previous = self._previous_start(team, today, game.game_id)
            bump = rest_travel_uncertainty_bump(game.date, previous)
            if bump > 0.0:
                return bump
        return 0.0

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_sports_contract(market)
        if parsed is None or parsed.sport != "mlb" or parsed.competitors is None:
            return None
        game = self.espn.find_matchup(
            "mlb", parsed.competitors[0], parsed.competitors[1], parsed.date_yyyymmdd,
        )
        if game is None or game.status not in ("pre", "in"):
            return None
        prediction = self.model.predict(game)
        live = game.status == "in"
        base_out_feature: dict[str, Any] | None = None
        # One fail-closed gate for every live market: a valid score + inning are
        # required, and YRFI (a first-inning market) is meaningless once underway.
        live_state: tuple[int, int, float] | None = None
        if live:
            if (game.home_score is None or game.away_score is None
                    or game.current_period is None or game.current_period < 1
                    or parsed.market_type == "yrfi"):
                return None
            live_state = (
                game.home_score, game.away_score, remaining_innings(game.current_period),
            )
        if parsed.market_type == "winner":
            subject = canonical_team("mlb", parsed.subject or "")
            home = canonical_team("mlb", game.home)
            if subject not in {home, canonical_team("mlb", game.away)}:
                return None
            if live_state is not None:
                home_score, away_score, rem = live_state
                home_win = self.model.live_win_probability(
                    prediction, home_score, away_score, rem)
                # A per-inning live approximation is coarser than the pre-game line.
                uncertainty = min(0.45, prediction.winner_uncertainty + 0.05)
                source = "mlb_live_winner"
                market_detail = (
                    f"{subject} live win ({away_score}-{home_score}, "
                    f"inning {game.current_period})"
                )
            else:
                home_win = prediction.home_win_probability
                uncertainty = prediction.winner_uncertainty
                source = "mlb_structural_winner"
                market_detail = f"{subject} win"
            probability = home_win if subject == home else 1.0 - home_win
        elif parsed.market_type == "total_runs" and parsed.threshold is not None:
            if live_state is not None:
                home_score, away_score, rem = live_state
                base_state = outs = None
                try:
                    base_out = self.live_book.base_out_state(game.game_id)
                except Exception:
                    base_out = None
                if base_out is not None:
                    base_state, outs = base_out
                    base_out_feature = {"base_state": base_state, "outs": outs}
                probability = self.model.live_total_probability(
                    prediction, home_score + away_score, parsed.threshold, rem,
                    base_state=base_state, outs=outs, current_period=game.current_period,
                )
                uncertainty = min(0.45, prediction.total_uncertainty + 0.05)
                source = "mlb_live_total"
                market_detail = (
                    f"live over {parsed.threshold:g} ({home_score + away_score} so far, "
                    f"inning {game.current_period}"
                    + (f", {base_state} {outs}out" if base_state else "")
                    + ")"
                )
            else:
                probability = self.model.total_probability(prediction, parsed.threshold)
                uncertainty = prediction.total_uncertainty
                source = "mlb_total_runs"
                market_detail = f"over {parsed.threshold:g} runs"
        elif parsed.market_type == "spread" and parsed.threshold is not None and parsed.subject:
            subject = canonical_team("mlb", parsed.subject)
            home = canonical_team("mlb", game.home)
            away = canonical_team("mlb", game.away)
            if subject not in {home, away}:
                return None
            subject_is_home = subject == home
            if live_state is not None:
                home_score, away_score, rem = live_state
                probability = self.model.live_spread_probability(
                    prediction, subject_is_home, parsed.threshold,
                    home_score, away_score, rem)
                uncertainty = min(0.45, prediction.winner_uncertainty + 0.07)
                source = "mlb_live_spread"
                market_detail = (
                    f"{subject} live by >{parsed.threshold:g} (inning {game.current_period})"
                )
            else:
                probability = self.model.spread_probability(
                    prediction, subject_is_home=subject_is_home, margin=parsed.threshold)
                # Run-margin tails are higher-variance than the moneyline; widen a touch.
                uncertainty = min(0.45, prediction.winner_uncertainty + 0.06)
                source = "mlb_run_spread"
                market_detail = f"{subject} by >{parsed.threshold:g}"
        elif parsed.market_type == "yrfi":
            probability = prediction.yrfi_probability
            uncertainty = prediction.first_inning_uncertainty
            source = "mlb_first_inning_run"
            market_detail = "YRFI (NO is NRFI)"
        else:
            return None
        # Availability: a banged-up roster is harder to forecast, so widen the
        # uncertainty (never shift the mean -- which player and how much is
        # unknown). No injury feed -> zero burden -> byte-identical output.
        injury_burden = (
            self.injuries.burden_for(game.home_name)
            + self.injuries.burden_for(game.away_name)
        )
        # Rest/travel: SOFT signal (day game after a previous night game) --
        # widens uncertainty only, never shifts the mean. No prior-game match
        # -> 0.0 -> byte-identical.
        rest_bump = self._rest_travel_uncertainty(game)
        uncertainty = min(0.45, uncertainty + 0.05 * injury_burden + rest_bump)
        return Signal(
            source=source,
            market_ticker=market.ticker,
            probability_yes=min(0.995, max(0.005, probability)),
            uncertainty=uncertainty,
            rationale=(
                f"MLB {market_detail}: {game.away}@{game.home}; expected runs "
                f"{prediction.expected_away_runs:.2f}+{prediction.expected_home_runs:.2f}="
                f"{prediction.expected_total_runs:.2f}; YRFI={prediction.yrfi_probability:.3f}; "
                f"team sample={prediction.sample_games}; pitchers={prediction.pitchers_available}"
            ),
            features={
                "challenger_only": True,
                "promotion_eligible": False,
                "point_in_time": True,
                "public_read_only": True,
                "sport": "mlb",
                "market_type": parsed.market_type,
                "live": live,
                "injury_burden": round(injury_burden, 3),
                "current_period": game.current_period,
                "home_score": game.home_score,
                "away_score": game.away_score,
                "model_version": prediction.model_version,
                "event_start": game.date,
                "home": game.home,
                "away": game.away,
                "home_pitcher": game.home_pitcher,
                "away_pitcher": game.away_pitcher,
                "home_pitcher_era": game.home_pitcher_era,
                "away_pitcher_era": game.away_pitcher_era,
                "expected_home_runs": prediction.expected_home_runs,
                "expected_away_runs": prediction.expected_away_runs,
                "expected_total_runs": prediction.expected_total_runs,
                "yrfi_probability": prediction.yrfi_probability,
                "threshold": parsed.threshold,
                "sample_games": prediction.sample_games,
                "park_factor": prediction.park_factor,
                "base_out_state": base_out_feature,
                "rest_travel_uncertainty_bump": rest_bump,
            },
        )


class TeamSportsIntelligenceSignal:
    """League-isolated score challengers for pro and college team sports."""

    name = "team_sports_intelligence"

    def __init__(
        self,
        espn: EspnClient | None = None,
        models: dict[str, TeamScoreModel] | None = None,
        model_dir: Path | None = None,
        seasons: Any = None,
        nba_boxscores: BoxscoreStore | None = None,
        nba_model: NbaModel | None = None,
        nba_model_path: Path | None = None,
        fetch_nba_summary: Any = None,
        nhl_boxscores: BoxscoreStore | None = None,
        nhl_model: NhlModel | None = None,
        nhl_model_path: Path | None = None,
        fetch_nhl_summary: Any = None,
        fetch_nhl_scoreboard: Any = None,
        ncaamb_boxscores: BoxscoreStore | None = None,
        ncaamb_model: NbaModel | None = None,
        ncaamb_model_path: Path | None = None,
        fetch_ncaamb_summary: Any = None,
        ncaaf_elo: EloModel | None = None,
        ncaaf_elo_path: Path | None = None,
        fetch_college_scoreboard: Any = None,
        injury_books: dict[str, LeagueInjuryBook] | None = None,
        rookie_book: RookieBook | None = None,
        nfl_rest_tracker: GameDateTracker | None = None,
        nhl_rest_tracker: GameDateTracker | None = None,
        playoff_books: dict[str, PlayoffBook] | None = None,
        roster_drift_books: dict[str, RosterDriftBook] | None = None,
        fetch_football_weather: Any = None,
    ) -> None:
        from autonomy.specialists.seasons import SeasonMonitor

        self.espn = espn or EspnClient()
        self.model_dir = model_dir or MODEL_DIR
        # Season gate shares this signal's ESPN client (and its cache), so
        # an activity check costs at most one scoreboard read per league
        # per TTL window.
        self.seasons = seasons or SeasonMonitor(espn=self.espn)
        self.models = models or {
            league: TeamScoreModel.load(
                league, self.model_dir / f"team_scores_{league}.json",
            )
            for league in LEAGUE_SCORE_CONFIGS
        }
        # WS-2: NBA's own pace x efficiency engine + the WS-1 boxscore store
        # it learns from. Both default to on-disk state under this signal's
        # model_dir, exactly like `self.models` above; a fresh/empty store
        # (e.g. in tests using tmp_path) means every NBA matchup starts cold
        # and falls back to the generic `self.models["nba"]` wholesale.
        self.nba_boxscores = nba_boxscores or BoxscoreStore(
            "nba", path=self.model_dir / "boxscores_nba.json")
        self.nba_model_path = nba_model_path or self.model_dir / "nba_pace_model.json"
        self.nba_model = nba_model or NbaModel.load(self.nba_model_path)
        # Injectable for tests; defaults to the real keyless ESPN summary
        # fetch (autonomy/sports/boxscores.py::fetch_summary). Only ever
        # called from `_warmup_nba`, never from `generate`.
        self._fetch_nba_summary = fetch_nba_summary or boxscores_module.fetch_summary
        # WS-3: NHL's bivariate-Poisson + OT/SO engine, same on-disk/cold-
        # fallback discipline as NBA above.
        self.nhl_boxscores = nhl_boxscores or BoxscoreStore(
            "nhl", path=self.model_dir / "boxscores_nhl.json")
        self.nhl_model_path = nhl_model_path or self.model_dir / "nhl_bipoisson_model.json"
        self.nhl_model = nhl_model or NhlModel.load(self.nhl_model_path)
        self._fetch_nhl_summary = fetch_nhl_summary or boxscores_module.fetch_summary
        # Raw-scoreboard fetch for probable-goalie identity (see
        # nhl_model.py::parse_probable_goalies -- this is deliberately NOT
        # routed through `self.espn`, which discards the raw payload after
        # parsing into `Game`). Injectable for tests; defaults to the real
        # keyless ESPN scoreboard fetch. Cached per date string within a
        # cycle so N markets on the same game/day cost one extra fetch, not N.
        self._fetch_nhl_scoreboard = fetch_nhl_scoreboard or default_fetch_scoreboard
        self._nhl_probables_cache: dict[str, dict[str, tuple[str | None, str | None]]] = {}
        # WS-4: NCAAMB's own pace x efficiency engine, same class as NBA's
        # (autonomy/sports/nba_model.py::NbaModel) but parameterized with
        # NCAAMB_PARAMS (see autonomy/sports/college.py) and its own on-disk
        # boxscore store/model path -- never shares state with the NBA
        # instances above. Same cold-fallback discipline: below
        # MIN_GAMES_FOR_ENGINE for either team, every NCAAMB branch below
        # falls through to the generic `self.models["ncaamb"]` wholesale.
        self.ncaamb_boxscores = ncaamb_boxscores or BoxscoreStore(
            "ncaamb", path=self.model_dir / "boxscores_ncaamb.json")
        self.ncaamb_model_path = ncaamb_model_path or self.model_dir / "ncaamb_pace_model.json"
        self.ncaamb_model = ncaamb_model or NbaModel.load(self.ncaamb_model_path, params=NCAAMB_PARAMS)
        self._fetch_ncaamb_summary = fetch_ncaamb_summary or boxscores_module.fetch_summary
        # WS-4: NCAAF's talent-gap blend reads (never retrains) the ncaaf Elo
        # ratings autonomy/signals/sports_elo.py::SportsEloSignal already
        # keeps warm every cycle (registered alongside this signal in
        # autonomy/session.py) -- reloaded fresh each `on_cycle_start` below
        # so this signal never runs on stale ratings from its own long-lived
        # in-memory copy.
        self.ncaaf_elo_path = ncaaf_elo_path or ELO_DIR / "elo_ncaaf.json"
        self.ncaaf_elo = ncaaf_elo or EloModel.load("ncaaf", self.ncaaf_elo_path)
        # Raw-scoreboard fetch for the neutralSite flag (see
        # college.py::parse_neutral_site -- Game itself doesn't carry it,
        # same reasoning as the NHL probable-goalie raw read above). Shared
        # across ncaaf/ncaamb since `default_fetch_scoreboard` is league-
        # generic; cached per (league, date) within a cycle.
        self._fetch_college_scoreboard = fetch_college_scoreboard or default_fetch_scoreboard
        self._neutral_site_cache: dict[tuple[str, str], dict[str, bool]] = {}
        # WS-6: per-league HARD/SOFT availability books (independent of
        # injuries.py's MLB-only InjuryBook -- see players.py's module
        # docstring). One book per league in LEAGUE_SCORE_CONFIGS, refreshed
        # once per cycle exactly like MLB's own injuries.refresh() pattern.
        self.injury_books = injury_books or {
            league: LeagueInjuryBook(league) for league in LEAGUE_SCORE_CONFIGS
        }
        # WS-6: NFL QB rookie-start probe only (NHL's starting-goalie rookie
        # flag is already shipped by WS-3's is_rookie_goalie -- see
        # players.py's module docstring for why this isn't duplicated here).
        self.rookie_book = rookie_book or RookieBook("nfl")
        # WS-7: shared per-team game-date trackers for the two NEW rest
        # states (NFL bye/Thursday-short-week, NHL back-to-back) -- NBA's
        # own in-model rest engine is deliberately untouched, see
        # situations.py's module docstring. Persisted on disk like every
        # other per-league model above; an empty/fresh tracker (e.g. tests
        # using tmp_path) means every matchup starts with no rest history,
        # i.e. a genuine 0.0/no-op -- fail-closed.
        self.nfl_rest_tracker = nfl_rest_tracker or GameDateTracker.load(
            self.model_dir / "situations_rest_nfl.json", league="nfl")
        self.nhl_rest_tracker = nhl_rest_tracker or GameDateTracker.load(
            self.model_dir / "situations_rest_nhl.json", league="nhl")
        # WS-7: playoff-context (clinched/eliminated/must_win) books, one per
        # team-sport league, refreshed once per cycle exactly like
        # `injury_books` above -- a league whose standings feed is absent/
        # offseason (LATE_SEASON gate, see situations.py) or simply never
        # refreshed (this signal's own `seasons.active` gate in
        # `on_cycle_start`) resolves every team to PlayoffState()'s all-False
        # default, fail-closed.
        self.playoff_books = playoff_books or {
            league: PlayoffBook(league) for league in LEAGUE_SCORE_CONFIGS
        }
        # WS-7: roster-hash-drift proxy books (trades/coaching soft signal),
        # one per league, persisted on disk (the prior cycle's roster
        # snapshot must survive a process restart for drift detection to
        # mean anything -- see situations.py::RosterDriftBook).
        self.roster_drift_books = roster_drift_books or {
            league: RosterDriftBook.load(
                self.model_dir / f"situations_roster_{league}.json", league=league,
            )
            for league in LEAGUE_SCORE_CONFIGS
        }
        # WS-10: NFL/NCAAF outdoor-weather TOTALS-only adjustment (see
        # autonomy/sports/football_weather.py). Injectable for tests;
        # defaults to the real keyless Open-Meteo fetch. Only ever called
        # from the "total" market branch below -- winner/spread pricing
        # never touches it, so it's never invoked for those market types.
        self._fetch_football_weather = fetch_football_weather or default_fetch_football_weather

    def _warmup_nba(self, date_ranges: list[str]) -> int:
        """Ingest WS-1 boxscores + update the NBA pace model for newly-final
        games (fetch-budget-capped, try/except-continue per game -- one bad
        fetch never blocks the rest, mirroring WS-1's documented contract).
        """
        games: list[Game] = []
        for dates in date_ranges:
            games.extend(self.espn.games("nba", dates))
        finals = sorted(
            (
                g for g in games
                if g.status == "post" and g.game_id not in self.nba_model.processed_game_ids
            ),
            key=lambda g: g.date,
        )
        updated = 0
        fetched = 0
        for game in finals:
            if fetched >= NBA_BOXSCORE_FETCH_BUDGET:
                break
            fetched += 1
            try:
                summary = self._fetch_nba_summary("nba", game.game_id)
            except Exception:
                continue
            boxes = parse_team_boxscores("nba", summary)
            if len(boxes) != 2:
                continue
            self.nba_boxscores.ingest(boxes)
            by_team = {b.team: b for b in boxes}
            home_box = by_team.get(canonical_team("nba", game.home))
            away_box = by_team.get(canonical_team("nba", game.away))
            if self.nba_model.update(game, home_box, away_box):
                updated += 1
        if updated:
            self.nba_model.save(self.nba_model_path)
        return updated

    def _warmup_nhl(self, date_ranges: list[str]) -> int:
        """Ingest WS-1 boxscores + goalie rows and update the NHL engine for
        newly-final games (same fetch-budget-capped, try/except-continue
        shape as `_warmup_nba` -- ONE summary fetch per game feeds both the
        team-level boxscore store and the goalie layer, see
        nhl_model.py::parse_goalie_boxscores).
        """
        games: list[Game] = []
        for dates in date_ranges:
            games.extend(self.espn.games("nhl", dates))
        finals = sorted(
            (
                g for g in games
                if g.status == "post" and g.game_id not in self.nhl_model.processed_game_ids
            ),
            key=lambda g: g.date,
        )
        updated = 0
        fetched = 0
        for game in finals:
            if fetched >= NHL_BOXSCORE_FETCH_BUDGET:
                break
            fetched += 1
            try:
                summary = self._fetch_nhl_summary("nhl", game.game_id)
            except Exception:
                continue
            boxes = parse_team_boxscores("nhl", summary)
            if len(boxes) != 2:
                continue
            self.nhl_boxscores.ingest(boxes)
            by_team = {b.team: b for b in boxes}
            home_box = by_team.get(canonical_team("nhl", game.home))
            away_box = by_team.get(canonical_team("nhl", game.away))
            goalie_rows = parse_goalie_boxscores(summary)
            home_goalies = [r for r in goalie_rows if r.team == canonical_team("nhl", game.home)]
            away_goalies = [r for r in goalie_rows if r.team == canonical_team("nhl", game.away)]
            if self.nhl_model.update(game, home_box, away_box, home_goalies, away_goalies):
                updated += 1
        if updated:
            self.nhl_model.save(self.nhl_model_path)
        return updated

    def _nhl_probables_for(self, dates: str) -> dict[str, tuple[str | None, str | None]]:
        """game_id -> (home_goalie, away_goalie) for one YYYYMMDD date,
        cached for the rest of this cycle (see `on_cycle_start`'s cache
        clear) so every market on the same game costs one extra raw
        scoreboard fetch, not one per market."""
        if dates in self._nhl_probables_cache:
            return self._nhl_probables_cache[dates]
        try:
            payload = self._fetch_nhl_scoreboard("nhl", dates)
        except Exception:
            payload = {}
        parsed = parse_probable_goalies(payload)
        self._nhl_probables_cache[dates] = parsed
        return parsed

    def _warmup_ncaamb(self, date_ranges: list[str]) -> int:
        """Ingest boxscores + update the NCAAMB pace model for newly-final
        games -- identical shape to `_warmup_nba`, just pointed at the
        ncaamb-specific store/model/fetch (see college.py's PROBE 3 for why
        the boxscore schema is safe to reuse verbatim)."""
        games: list[Game] = []
        for dates in date_ranges:
            games.extend(self.espn.games("ncaamb", dates))
        finals = sorted(
            (
                g for g in games
                if g.status == "post" and g.game_id not in self.ncaamb_model.processed_game_ids
            ),
            key=lambda g: g.date,
        )
        updated = 0
        fetched = 0
        for game in finals:
            if fetched >= NCAAMB_BOXSCORE_FETCH_BUDGET:
                break
            fetched += 1
            try:
                summary = self._fetch_ncaamb_summary("ncaamb", game.game_id)
            except Exception:
                continue
            boxes = parse_team_boxscores("ncaamb", summary)
            if len(boxes) != 2:
                continue
            self.ncaamb_boxscores.ingest(boxes)
            by_team = {b.team: b for b in boxes}
            home_box = by_team.get(canonical_team("ncaamb", game.home))
            away_box = by_team.get(canonical_team("ncaamb", game.away))
            if self.ncaamb_model.update(game, home_box, away_box):
                updated += 1
        if updated:
            self.ncaamb_model.save(self.ncaamb_model_path)
        return updated

    def _neutral_site_for(self, league: str, dates: str) -> dict[str, bool]:
        """game_id -> neutralSite for one (league, YYYYMMDD) pair, cached for
        the rest of this cycle (see `on_cycle_start`'s cache clear) -- same
        one-fetch-per-game-day-not-per-market discipline as
        `_nhl_probables_for`."""
        key = (league, dates)
        if key in self._neutral_site_cache:
            return self._neutral_site_cache[key]
        try:
            payload = self._fetch_college_scoreboard(league, dates)
        except Exception:
            payload = {}
        parsed = parse_neutral_site(payload)
        self._neutral_site_cache[key] = parsed
        return parsed

    def warmup(self, league: str, date_ranges: list[str]) -> int:
        model = self.models[league]
        updated = 0
        games: list[Any] = []
        for dates in date_ranges:
            games.extend(self.espn.games(league, dates))
        for game in sorted(games, key=lambda item: item.date):
            updated += int(model.update(game))
        if updated:
            model.save(self.model_dir / f"team_scores_{league}.json")
        return updated

    def on_cycle_start(self) -> None:
        self.espn.clear_cache()
        self._nhl_probables_cache = {}  # probables/lineups can change day to day
        self._neutral_site_cache = {}  # same -- a schedule's neutral-site flag can change
        # Reload (never retrain) the ncaaf Elo ratings SportsEloSignal keeps
        # warm every cycle -- see this signal's __init__ docstring note.
        try:
            self.ncaaf_elo = EloModel.load("ncaaf", self.ncaaf_elo_path)
        except Exception:
            pass  # keep the last-loaded ratings rather than go cold on a blip
        recent = _date_range()
        for league in LEAGUE_SCORE_CONFIGS:
            try:
                # Season gate: a dormant league (no games in the detection
                # window) skips its warmup fetch entirely. No wake backfill:
                # a genuine wake has an empty offseason behind it, and a
                # false-dormant blip is covered by this recent-days window.
                if not self.seasons.active(league):
                    continue
                self.warmup(league, [recent])
                # WS-6: HARD/SOFT availability, once per cycle (mirrors
                # BaseballIntelligenceSignal.on_cycle_start's own
                # self.injuries.refresh()). Internally fail-closed already
                # (see LeagueInjuryBook.refresh), so a dead feed just leaves
                # this league's book empty rather than aborting the loop.
                self.injury_books[league].refresh()
                # WS-7: playoff-context, once per cycle, same fail-closed
                # discipline as injury_books above (an unreachable/offseason
                # standings feed just leaves this league's book empty).
                self.playoff_books[league].refresh()
                # WS-7: roster-hash-drift proxy, budget-capped, for today's
                # slate only -- `self.espn.games` is a cache hit here (the
                # warmup() call above already fetched it), same pattern as
                # the NFL rookie probe below.
                league_games = self.espn.games(league, recent)
                league_teams = sorted({g.home for g in league_games} | {g.away for g in league_games})
                self.roster_drift_books[league].refresh(league_teams)
                self.roster_drift_books[league].save(
                    self.model_dir / f"situations_roster_{league}.json")
                if league == "nba":
                    self._warmup_nba([recent])
                elif league == "nhl":
                    self._warmup_nhl([recent])
                    # WS-7: shared rest tracker, settlement-only (see
                    # GameDateTracker.update's own point-in-time gate) --
                    # completed games from this cycle's recent-days window.
                    nhl_updated = False
                    for game in league_games:
                        nhl_updated = self.nhl_rest_tracker.update(game) or nhl_updated
                    if nhl_updated:
                        self.nhl_rest_tracker.save(self.model_dir / "situations_rest_nhl.json")
                elif league == "ncaamb":
                    self._warmup_ncaamb([recent])
                elif league == "nfl":
                    # WS-6: NFL QB rookie-start probe, budget-capped, for
                    # today's slate only -- reuses `league_games`/`league_teams`
                    # computed above (same cache hit, no extra fetch).
                    self.rookie_book.refresh(league_teams)
                    # WS-7: shared rest tracker, same settlement-only gate as NHL.
                    nfl_updated = False
                    for game in league_games:
                        nfl_updated = self.nfl_rest_tracker.update(game) or nfl_updated
                    if nfl_updated:
                        self.nfl_rest_tracker.save(self.model_dir / "situations_rest_nfl.json")
            except Exception:
                continue
        self.espn.clear_cache()

    def applicable(self, market: MarketView) -> bool:
        parsed = parse_sports_contract(market)
        return (
            market.vertical is Vertical.SPORTS
            and parsed is not None
            and parsed.sport in LEAGUE_SCORE_CONFIGS
        )

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_sports_contract(market)
        if (
            parsed is None
            or parsed.sport not in LEAGUE_SCORE_CONFIGS
            or parsed.competitors is None
        ):
            return None
        if parsed.market_type == "winner":
            game = self.espn.find_matchup(
                parsed.sport, parsed.competitors[0], parsed.competitors[1],
                parsed.date_yyyymmdd,
            )
        else:
            game = self.espn.find_matchup_names(
                parsed.sport, parsed.competitors[0], parsed.competitors[1],
                parsed.date_yyyymmdd,
            )
        if game is None:
            return None
        # WS-6: player availability (HARD margin-shift + SOFT/rookie
        # uncertainty widen) computed once per game, before market-type
        # branching, so NFL/NCAAF can bake the HARD delta straight into
        # their margin kernel's inputs below (an EXACT shift, not the
        # logit-space approximation NBA/NHL/NCAAMB use further down).
        # Fail-closed throughout: an unrefreshed/dead injury_books entry has
        # an empty book (LeagueInjuryBook.refresh's own contract), so
        # `home_availability`/`away_availability` are the zero-value
        # TeamAvailability() default and every effect below is 0.0/None --
        # byte-identical to this whole layer being disabled.
        injury_book = self.injury_books.get(parsed.sport)
        home_availability = injury_book.for_team(game.home_name) if injury_book else TeamAvailability()
        away_availability = injury_book.for_team(game.away_name) if injury_book else TeamAvailability()
        rookie_home = self.rookie_book.rookie_start(game.home) if parsed.sport == "nfl" else None
        rookie_away = self.rookie_book.rookie_start(game.away) if parsed.sport == "nfl" else None
        player_effect = availability_effect(
            parsed.sport, home_availability, away_availability, rookie_home, rookie_away)
        hard_margin_delta = player_effect.hard_margin_delta
        # WS-7: HARD rest states (NFL bye/Thursday-short-week, NHL back-to-
        # back), computed unconditionally so the miner always sees the state
        # even when a later gate (NHL's live branch, see nba_live/nhl_live
        # below) skips APPLYING it to price. Every other league has no
        # tracker wired at all (situations.py deliberately leaves NBA's own
        # in-model rest engine untouched -- see its module docstring), so
        # this is a genuine 0.0/no-op there, fail-closed.
        situational_rest = RestEffect()
        if parsed.sport == "nfl":
            situational_rest = nfl_rest_effect(
                self.nfl_rest_tracker.recent_dates(game.home),
                self.nfl_rest_tracker.recent_dates(game.away),
                game.date,
            )
        elif parsed.sport == "nhl":
            situational_rest = nhl_rest_effect(
                self.nhl_rest_tracker.recent_dates(game.home),
                self.nhl_rest_tracker.recent_dates(game.away),
                game.date,
            )
        situational_margin_delta = situational_rest.margin_delta
        # WS-7: SOFT playoff-context (clinched/eliminated -- widen only) and
        # roster/coaching-drift proxy (widen only), both league-generic: a
        # missing/unrefreshed book resolves to its own all-False/zero
        # default (PlayoffBook/RosterDriftBook's own fail-closed contract),
        # so an offseason or feed-down league is byte-identical to this
        # whole layer being disabled.
        playoff_book = self.playoff_books.get(parsed.sport)
        home_playoff = playoff_book.for_team(game.home) if playoff_book else PlayoffState()
        away_playoff = playoff_book.for_team(game.away) if playoff_book else PlayoffState()
        playoff_effect = playoff_soft_effect(home_playoff, away_playoff)
        roster_book = self.roster_drift_books.get(parsed.sport)
        home_roster_event = roster_book.event_for(game.home) if roster_book else {}
        away_roster_event = roster_book.event_for(game.away) if roster_book else {}
        roster_effect = roster_soft_effect(home_roster_event, away_roster_event)
        # Mismatch finder: bounded [-1,1], sourced from already-shipped
        # per-team split metrics (NBA/NCAAMB rest gap, NHL special-teams
        # gap -- populated in their own blocks below once warm). NFL/NCAAF
        # have no per-team split metric wired into this signal at all (no
        # BoxscoreStore instance exists for either league here -- see
        # players.py's module docstring probe #3), so their score stays
        # unavailable/None -- fail-closed, not fabricated.
        mismatch_score: float | None = None
        mismatch_delta = 0.0
        # Flipped to False only once a warm per-league engine below actually
        # computes a real mismatch_score; NFL/NCAAF never flip it (no
        # source metric wired), and a COLD nba/nhl/ncaamb game (no warm
        # engine yet) correctly stays "unavailable" too.
        mismatch_unavailable = True
        # NBA and NHL alone carry an in-play branch (WS-2/WS-3); every other
        # league in this signal stays pre-game only, unchanged from before WS-2.
        nba_live = parsed.sport == "nba" and game.status == "in"
        nhl_live = parsed.sport == "nhl" and game.status == "in"
        if parsed.sport in ("nba", "nhl"):
            if game.status not in ("pre", "in"):
                return None
        elif game.status != "pre":
            return None
        prediction = self.models[parsed.sport].predict(game)
        # NFL winner/spread price from the key-number margin kernel (mass at
        # 3/7/10 priced where it lives) instead of a smooth normal; the
        # winner cell and every spread rung share ONE tilted distribution,
        # so the 3x3 lattice's margin column is coherent by construction.
        nfl_kernel = None
        margin_model_version = None
        if parsed.sport == "nfl" and parsed.market_type in ("winner", "spread"):
            from autonomy.sports.nfl_margin import NflMarginModel

            # WS-6/WS-7: HARD availability + HARD rest state (bye/Thursday
            # short week) both bake into the kernel's own input scores --
            # symmetric split so the margin shifts by EXACTLY the combined
            # delta while the total stays untouched (the brief's own key
            # test: QB-Out shifts NFL expected margin by exactly -4.5).
            # delta_margin == 0.0 is a literal no-op (both scores
            # unchanged), so a healthy/rested roster is byte-identical to
            # before WS-6/WS-7.
            adj_home_score, adj_away_score = apply_margin_shift_to_scores(
                prediction.expected_home_score, prediction.expected_away_score,
                hard_margin_delta + situational_margin_delta)
            nfl_kernel = NflMarginModel(adj_home_score, adj_away_score)
            margin_model_version = "nfl_key_number_kernel_v1"

        # NCAAF winner/spread price from the college key-number kernel
        # (WS-4) -- reuses nfl_margin.py's tilted-PMF machinery wholesale
        # (autonomy/sports/college.py::NcaafCollegeModel) with a shallower
        # college base table and an expected margin blended with a talent-
        # gap Elo prior early in the season. Unlike NBA/NHL/NCAAMB below,
        # this never wholesale-falls-back to the generic prediction -- the
        # blend is DESIGNED to degrade gracefully to pure Elo at games=0
        # rather than needing a cold gate (see college.py::talent_gap_margin).
        ncaaf_kernel = None
        ncaaf_prediction = None
        if parsed.sport == "ncaaf":
            dates = (game.date or "")[:10].replace("-", "")
            neutral_lookup = self._neutral_site_for("ncaaf", dates) if dates else {}
            neutral_site = neutral_lookup.get(game.game_id, False)
            home_elo = self.ncaaf_elo.rating(canonical_team("ncaaf", game.home))
            away_elo = self.ncaaf_elo.rating(canonical_team("ncaaf", game.away))
            ncaaf_kernel, ncaaf_prediction = ncaaf_college(
                prediction, home_elo, away_elo, prediction.sample_games, neutral_site)
            margin_model_version = NCAAF_MODEL_VERSION
            # WS-6: same HARD-availability margin shift as NFL above, but
            # NcaafCollegeModel takes an already-blended expected_margin
            # directly (not raw home/away scores) -- rebuild the kernel with
            # margin + hard_margin_delta; expected_total is untouched, so
            # this is an exact shift of the margin only, same as NFL's.
            # `ncaaf_prediction` (used for reporting/uncertainty) is left
            # pointing at the pre-shift kernel's numbers on purpose -- the
            # shift itself is separately logged via hard_margin_delta.
            if hard_margin_delta != 0.0:
                from autonomy.sports.college import NcaafCollegeModel

                ncaaf_kernel = NcaafCollegeModel(
                    ncaaf_kernel.expected_margin + hard_margin_delta,
                    ncaaf_kernel.expected_total, ncaaf_kernel.total_sigma,
                )

        # NBA winner/spread/total price from the pace x efficiency engine
        # (WS-2) once WS-1's BoxscoreStore has >= MIN_GAMES_FOR_ENGINE games
        # for BOTH teams; below that, every branch below falls straight
        # through to the generic `prediction` (TeamScoreModel) computed
        # above -- WHOLESALE, never half-blended (nba_model_fallback logs
        # which path fired). A live NBA market with no warm engine has no
        # fallback pricing path at all (TeamScoreModel is pre-game only), so
        # it abstains rather than guess.
        nba_engine = None
        nba_prediction = None
        nba_live_state: tuple[int, int, float] | None = None
        if parsed.sport == "nba":
            if nba_live and (
                game.home_score is None or game.away_score is None
                or game.current_period is None or game.current_period < 1
            ):
                return None
            home_abbr, away_abbr = game.home.upper(), game.away.upper()
            warm = nba_is_warm(self.nba_boxscores, home_abbr, away_abbr)
            if nba_live and not warm:
                return None
            if warm:
                nba_engine = self.nba_model
                nba_prediction = nba_engine.predict(game)
                margin_model_version = NBA_MODEL_VERSION
                # WS-6 mismatch: rest gap (points) between the two teams'
                # own rest adjustments -- already-shipped WS-2 per-team
                # fields, bounded/symmetric via bounded_mismatch_score.
                # (Pace gap is NOT included: WS-1's BoxscoreStore has no
                # per-team-vs-league-average pace split wired into this
                # signal -- see players.py's module docstring probe #3.)
                mismatch_score = bounded_mismatch_score(
                    nba_prediction.rest_adjustment_home, nba_prediction.rest_adjustment_away,
                    LEAGUE_POINT_SCALE["nba"],
                )
                mismatch_delta = mismatch_margin_shift(mismatch_score, LEAGUE_POINT_SCALE["nba"])
                mismatch_unavailable = False
                if nba_live:
                    minutes_remaining = nba_minutes_remaining(game.current_period, game.current_clock)
                    if minutes_remaining is None:
                        return None
                    nba_live_state = (game.home_score, game.away_score, minutes_remaining)

        # NHL winner/spread/total price from the bivariate-Poisson + OT/SO
        # engine (WS-3) once warm, same wholesale-fallback discipline as NBA
        # above. Goalie identity is looked up from the raw scoreboard
        # payload for this game's own date (see `_nhl_probables_for`) --
        # absent probables degrade to the unknown-goalie branch inside
        # `NhlModel.predict` rather than block pricing.
        nhl_engine = None
        nhl_prediction = None
        nhl_live_state: tuple[int, int, float] | None = None
        if parsed.sport == "nhl":
            if nhl_live and (
                game.home_score is None or game.away_score is None
                or game.current_period is None or game.current_period < 1
            ):
                return None
            home_abbr, away_abbr = game.home.upper(), game.away.upper()
            warm = nhl_is_warm(self.nhl_boxscores, home_abbr, away_abbr)
            if nhl_live and not warm:
                return None
            if warm:
                nhl_engine = self.nhl_model
                dates = (game.date or "")[:10].replace("-", "")
                probables = self._nhl_probables_for(dates) if dates else {}
                home_goalie, away_goalie = probables.get(game.game_id, (None, None))
                nhl_prediction = nhl_engine.predict(game, home_goalie, away_goalie)
                margin_model_version = NHL_MODEL_VERSION
                # WS-6 mismatch: NHL special-teams gap (WS-3's own per-team
                # special_teams_shift_home/away, already in expected-goal
                # units) -- bounded/symmetric via bounded_mismatch_score.
                mismatch_score = bounded_mismatch_score(
                    nhl_prediction.special_teams_shift_home, nhl_prediction.special_teams_shift_away,
                    LEAGUE_POINT_SCALE["nhl"],
                )
                mismatch_delta = mismatch_margin_shift(mismatch_score, LEAGUE_POINT_SCALE["nhl"])
                mismatch_unavailable = False
                if nhl_live:
                    minutes_remaining = nhl_minutes_remaining(game.current_period, game.current_clock)
                    if minutes_remaining is None:
                        return None
                    nhl_live_state = (game.home_score, game.away_score, minutes_remaining)

        # NCAAMB winner/spread/total price from its own pace x efficiency
        # engine (WS-4: NbaModel parameterized with NCAAMB_PARAMS -- same
        # class, same arithmetic, different cold-start/sigma constants; see
        # autonomy/sports/nba_model.py::PaceParams) once warm, same
        # wholesale-fallback discipline as NBA/NHL above -- never a half-
        # blend. Neutral site (tournament/showcase games) drops the home
        # edge via the same neutralSite flag lookup as NCAAF above.
        ncaamb_engine = None
        ncaamb_prediction = None
        ncaamb_neutral_site = None
        if parsed.sport == "ncaamb":
            home_abbr, away_abbr = game.home.upper(), game.away.upper()
            warm = nba_is_warm(self.ncaamb_boxscores, home_abbr, away_abbr)
            if warm:
                ncaamb_engine = self.ncaamb_model
                dates = (game.date or "")[:10].replace("-", "")
                neutral_lookup = self._neutral_site_for("ncaamb", dates) if dates else {}
                ncaamb_neutral_site = neutral_lookup.get(game.game_id, False)
                ncaamb_prediction = ncaamb_engine.predict(game, neutral=ncaamb_neutral_site)
                margin_model_version = NCAAMB_PARAMS.version
                # WS-6 mismatch: same rest-gap treatment as NBA above (same
                # NbaPrediction dataclass, NCAAMB_PARAMS-parameterized).
                mismatch_score = bounded_mismatch_score(
                    ncaamb_prediction.rest_adjustment_home, ncaamb_prediction.rest_adjustment_away,
                    LEAGUE_POINT_SCALE["ncaamb"],
                )
                mismatch_delta = mismatch_margin_shift(mismatch_score, LEAGUE_POINT_SCALE["ncaamb"])
                mismatch_unavailable = False

        # Report numbers from whichever model actually priced this signal
        # (NbaModel/NhlModel/NCAAMB's NbaModel when warm, the college NCAAF
        # kernel prediction for ncaaf, the generic TeamScoreModel otherwise/
        # always for every other league) -- keeps the rationale/features
        # numbers consistent with `probability` instead of silently mixing
        # models.
        if nba_prediction is not None:
            report = nba_prediction
        elif nhl_prediction is not None:
            report = nhl_prediction
        elif ncaamb_prediction is not None:
            report = ncaamb_prediction
        elif ncaaf_prediction is not None:
            report = ncaaf_prediction
        else:
            report = prediction

        # WS-10: NFL/NCAAF outdoor-weather TOTALS-only mean shift. Populated
        # ONLY inside the "total" branch below for parsed.sport in
        # ("nfl", "ncaaf") -- winner/spread never set this, so they stay
        # byte-identical to a world without this feature (no fetch is even
        # attempted for those market types, let alone applied).
        weather_features: dict[str, Any] = {}

        if parsed.market_type == "winner" and parsed.subject:
            subject = parsed.subject.upper()
            if subject == game.home.upper():
                subject_is_home = True
            elif subject == game.away.upper():
                subject_is_home = False
            else:
                return None
            if nba_engine is not None and nba_live_state is not None:
                home_score, away_score, minutes_remaining = nba_live_state
                home_win = nba_engine.live_win_probability_for(
                    nba_prediction, home_score, away_score, minutes_remaining)
                source = "nba_live_winner"
                detail = f"{subject} live win ({away_score}-{home_score}, period {game.current_period})"
                uncertainty = min(0.45, prediction.winner_uncertainty + 0.05)
            elif nhl_engine is not None and nhl_live_state is not None:
                home_score, away_score, minutes_remaining = nhl_live_state
                home_win = nhl_engine.live_win_probability_for(
                    nhl_prediction, home_score, away_score, minutes_remaining)
                source = "nhl_live_winner"
                detail = f"{subject} live win ({away_score}-{home_score}, period {game.current_period})"
                uncertainty = min(0.45, nhl_prediction.winner_uncertainty + 0.05)
            else:
                if nba_engine is not None:
                    home_win = nba_prediction.home_win_probability
                elif nhl_engine is not None:
                    home_win = nhl_prediction.home_win_probability
                elif ncaamb_engine is not None:
                    home_win = ncaamb_prediction.home_win_probability
                elif ncaaf_kernel is not None:
                    home_win = ncaaf_kernel.home_win_probability()
                elif nfl_kernel is not None:
                    home_win = nfl_kernel.home_win_probability()
                else:
                    home_win = prediction.home_win_probability
                source = f"{parsed.sport}_structural_winner"
                detail = f"{subject} win"
                # Own-prediction uncertainty on every WARM college/NHL path
                # (the WS-3 lesson: never fall back to the generic
                # `prediction.winner_uncertainty` once a more specific engine
                # actually priced this signal); ncaaf's kernel is never
                # "cold" the way NBA/NHL/NCAAMB can be (see the talent-gap
                # blend above), so it always reports its own uncertainty.
                if nhl_engine is not None:
                    uncertainty = nhl_prediction.winner_uncertainty
                elif ncaamb_engine is not None:
                    uncertainty = ncaamb_prediction.winner_uncertainty
                elif ncaaf_kernel is not None:
                    uncertainty = ncaaf_prediction.winner_uncertainty
                else:
                    uncertainty = prediction.winner_uncertainty
            probability = home_win if subject_is_home else 1.0 - home_win
            # WS-6: NFL/NCAAF already baked their HARD-availability shift
            # into their kernel's input margin above (an EXACT shift); NBA/
            # NHL/NCAAMB have no raw-margin-input kernel to inject into, so
            # nudge the already-computed probability via a bounded logit-
            # space shift instead (see players.shift_probability_by_margin
            # -- an exact no-op when the combined delta is 0.0).
            # Pre-game only: once nba_live/nhl_live's `live_win_probability_for`
            # is pricing off the actual live score, the injured player's
            # absence is already baked into that score -- re-applying the
            # pre-game availability/mismatch delta here would double-count
            # it. NCAAMB has no live path (nba_live/nhl_live are always False
            # for it), so it keeps the shift unconditionally, same as before.
            if parsed.sport in ("nba", "nhl", "ncaamb") and not (nba_live or nhl_live):
                probability = shift_probability_by_margin(
                    probability, hard_margin_delta + mismatch_delta + situational_margin_delta,
                    LEAGUE_POINT_SCALE[parsed.sport], subject_is_home,
                )
        elif parsed.market_type == "spread" and parsed.subject and parsed.threshold is not None:
            subject = parsed.subject.upper()
            if subject == game.home.upper():
                subject_is_home = True
            elif subject == game.away.upper():
                subject_is_home = False
            else:
                return None
            if nba_engine is not None and nba_live_state is not None:
                home_score, away_score, minutes_remaining = nba_live_state
                probability = nba_engine.live_spread_probability_for(
                    nba_prediction, subject_is_home, parsed.threshold,
                    home_score, away_score, minutes_remaining)
                source = "nba_live_spread"
                detail = f"{subject} live by >{parsed.threshold:g} (period {game.current_period})"
                uncertainty = min(0.45, prediction.winner_uncertainty + 0.07)
            elif nhl_engine is not None and nhl_live_state is not None:
                home_score, away_score, minutes_remaining = nhl_live_state
                probability = nhl_engine.live_spread_probability_for(
                    nhl_prediction, subject_is_home, parsed.threshold,
                    home_score, away_score, minutes_remaining)
                source = "nhl_live_spread"
                detail = f"{subject} live by >{parsed.threshold:g} (period {game.current_period})"
                uncertainty = min(0.45, nhl_prediction.winner_uncertainty + 0.07)
            else:
                if nba_engine is not None:
                    probability = nba_engine.cover_probability(
                        nba_prediction, subject_is_home, parsed.threshold)
                elif nhl_engine is not None:
                    probability = nhl_engine.cover_probability(
                        nhl_prediction, subject_is_home, parsed.threshold)
                elif ncaamb_engine is not None:
                    probability = ncaamb_engine.cover_probability(
                        ncaamb_prediction, subject_is_home, parsed.threshold)
                elif ncaaf_kernel is not None:
                    probability = (
                        ncaaf_kernel.home_cover_probability(parsed.threshold)
                        if subject_is_home
                        else ncaaf_kernel.away_cover_probability(parsed.threshold)
                    )
                elif nfl_kernel is not None:
                    probability = (
                        nfl_kernel.home_cover_probability(parsed.threshold)
                        if subject_is_home
                        else nfl_kernel.away_cover_probability(parsed.threshold)
                    )
                else:
                    # Generic leagues: normal margin over the model's own
                    # sigma (NBA below MIN_GAMES_FOR_ENGINE lands here too).
                    subject_margin = (
                        prediction.expected_home_score - prediction.expected_away_score
                        if subject_is_home
                        else prediction.expected_away_score - prediction.expected_home_score
                    )
                    sigma = LEAGUE_SCORE_CONFIGS[parsed.sport].margin_sigma
                    z = (parsed.threshold - subject_margin) / max(0.25, sigma)
                    probability = min(0.995, max(0.005, 1.0 - 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))))
                if nhl_engine is not None:
                    uncertainty = min(0.44, nhl_prediction.winner_uncertainty + 0.02)
                elif ncaamb_engine is not None:
                    uncertainty = min(0.44, ncaamb_prediction.winner_uncertainty + 0.02)
                elif ncaaf_kernel is not None:
                    uncertainty = min(0.44, ncaaf_prediction.winner_uncertainty + 0.02)
                else:
                    uncertainty = min(0.44, prediction.winner_uncertainty + 0.02)
                source = f"{parsed.sport}_spread"
                detail = f"{subject} covers {parsed.threshold:g}"
            # WS-6: same post-hoc logit shift as the winner branch above --
            # NFL/NCAAF are exact via their kernel (nfl_kernel/ncaaf_kernel
            # already reflect hard_margin_delta), NBA/NHL/NCAAMB get the
            # bounded approximation. Same live-double-count gate as the
            # winner branch: skip on the nba_live/nhl_live in-play path,
            # since live_spread_probability_for already prices off the
            # actual (injury-affected) live score.
            if parsed.sport in ("nba", "nhl", "ncaamb") and not (nba_live or nhl_live):
                probability = shift_probability_by_margin(
                    probability, hard_margin_delta + mismatch_delta + situational_margin_delta,
                    LEAGUE_POINT_SCALE[parsed.sport], subject_is_home,
                )
        elif parsed.market_type == "total" and parsed.threshold is not None:
            if nba_engine is not None and nba_live_state is not None:
                home_score, away_score, minutes_remaining = nba_live_state
                probability = nba_engine.live_total_probability_for(
                    nba_prediction, home_score + away_score, parsed.threshold, minutes_remaining)
                source = "nba_live_total"
                detail = (
                    f"live over {parsed.threshold:g} ({home_score + away_score} so far, "
                    f"period {game.current_period})"
                )
                uncertainty = min(0.45, prediction.total_uncertainty + 0.05)
            elif nhl_engine is not None and nhl_live_state is not None:
                home_score, away_score, minutes_remaining = nhl_live_state
                probability = nhl_engine.live_total_probability_for(
                    nhl_prediction, home_score + away_score, parsed.threshold,
                    home_score, away_score, minutes_remaining)
                source = "nhl_live_total"
                detail = (
                    f"live over {parsed.threshold:g} ({home_score + away_score} so far, "
                    f"period {game.current_period})"
                )
                uncertainty = min(0.45, nhl_prediction.total_uncertainty + 0.05)
            elif nba_engine is not None:
                probability = nba_engine.total_probability(nba_prediction, parsed.threshold)
                uncertainty = prediction.total_uncertainty
                source = "nba_game_total"
                detail = f"over {parsed.threshold:g}"
            elif nhl_engine is not None:
                probability = nhl_engine.total_probability(nhl_prediction, parsed.threshold)
                uncertainty = nhl_prediction.total_uncertainty
                source = "nhl_game_total"
                detail = f"over {parsed.threshold:g}"
            elif ncaamb_engine is not None:
                probability = ncaamb_engine.total_probability(ncaamb_prediction, parsed.threshold)
                uncertainty = ncaamb_prediction.total_uncertainty
                source = "ncaamb_game_total"
                detail = f"over {parsed.threshold:g}"
            elif ncaaf_kernel is not None:
                # WS-10: weather hits the TOTAL mean only -- ncaaf_kernel
                # itself (shared with the winner/spread branches above) is
                # never mutated; a fresh kernel is built here just for total
                # pricing so winner/spread stay byte-identical regardless of
                # weather. NcaafCollegeModel's margin distribution (which is
                # all winner/spread reads) depends only on expected_margin,
                # never expected_total, so this is doubly safe.
                weather_delta, weather_features = football_weather_adjustment(
                    "ncaaf", game.home, game.date, fetch_fn=self._fetch_football_weather)
                total_kernel = ncaaf_kernel
                if weather_delta:
                    from autonomy.sports.college import NcaafCollegeModel

                    total_kernel = NcaafCollegeModel(
                        ncaaf_kernel.expected_margin,
                        ncaaf_kernel.expected_total + weather_delta,
                        ncaaf_kernel.total_sigma,
                    )
                probability = total_kernel.total_over_probability(parsed.threshold)
                uncertainty = ncaaf_prediction.total_uncertainty
                source = "ncaaf_game_total"
                detail = f"over {parsed.threshold:g}"
            else:
                # WS-10: NFL totals price off the generic TeamScoreModel
                # path (NFL's own key-number kernel is winner/spread only --
                # see nfl_kernel's construction above), so the weather delta
                # shifts a locally-`replace`d copy of `prediction` used ONLY
                # for this probability call; `prediction` itself (read by
                # the winner/spread branches and by `report` above) is
                # untouched. Every other league landing in this generic
                # branch (cold NBA/NHL/NCAAMB) never computes a weather
                # delta at all, so it's an exact 0.0 no-op for them.
                weather_delta = 0.0
                if parsed.sport == "nfl":
                    weather_delta, weather_features = football_weather_adjustment(
                        "nfl", game.home, game.date, fetch_fn=self._fetch_football_weather)
                total_prediction = prediction
                if weather_delta:
                    total_prediction = replace(
                        prediction, expected_total=prediction.expected_total + weather_delta)
                probability = self.models[parsed.sport].total_probability(
                    total_prediction, parsed.threshold,
                )
                uncertainty = prediction.total_uncertainty
                source = f"{parsed.sport}_game_total"
                detail = f"over {parsed.threshold:g}"
        else:
            return None
        # WS-6/WS-7: SOFT (Questionable/DTD/Probable) + rookie + playoff-
        # context (clinched/eliminated) + roster-drift effects widen
        # uncertainty ONLY, uniformly across every market type (mirrors
        # BaseballIntelligenceSignal's own injury_burden/rest_bump pattern
        # -- a single additive bump right before Signal construction, never
        # touching the mean). A healthy/rookie-free/mid-season/feed-absent
        # game adds exactly 0.0, so the clip is a no-op and `uncertainty` is
        # byte-identical to before WS-6/WS-7.
        uncertainty = min(
            0.45,
            uncertainty + player_effect.soft_uncertainty_add + player_effect.rookie_uncertainty_add
            + playoff_effect.uncertainty_add + roster_effect.uncertainty_add,
        )
        return Signal(
            source=source,
            market_ticker=market.ticker,
            probability_yes=probability,
            uncertainty=uncertainty,
            rationale=(
                f"{parsed.sport.upper()} {detail}: {game.away}@{game.home}; expected "
                f"{report.expected_away_score:.2f}+{report.expected_home_score:.2f}="
                f"{report.expected_total:.2f}; paired sample={report.sample_games}"
            ),
            features={
                "challenger_only": True,
                "promotion_eligible": False,
                "point_in_time": True,
                "public_read_only": True,
                "sport": parsed.sport,
                "market_type": parsed.market_type,
                "model_version": prediction.model_version,
                "event_start": game.date,
                "home": game.home,
                "away": game.away,
                "expected_home_score": report.expected_home_score,
                "expected_away_score": report.expected_away_score,
                "expected_total": report.expected_total,
                "threshold": parsed.threshold,
                # WS-6: player availability / rookie / mismatch layer.
                **player_effect.features,
                # WS-7: rest (NFL bye/short-week, NHL b2b) / playoff-context
                # (clinched/eliminated/must_win) / roster-drift layer.
                **situational_rest.features,
                **playoff_effect.features,
                **roster_effect.features,
                # WS-10: NFL/NCAAF outdoor-weather TOTALS-only layer -- empty
                # for every non-total market and for any total signal where
                # the reading was unavailable (fail-closed), never mutating
                # any of the mean-shift keys above.
                **weather_features,
                "mismatch_score": round(mismatch_score, 4) if mismatch_score is not None else None,
                "mismatch_margin_delta": round(mismatch_delta, 4),
                **({f"{parsed.sport}_mismatch_unavailable": True} if mismatch_unavailable else {}),
                **({"nba_minutes_scaling_unavailable": True} if parsed.sport == "nba" else {}),
                "sample_games": report.sample_games,
                **(
                    {"margin_model_version": margin_model_version}
                    if margin_model_version else {}
                ),
                **(
                    {
                        "nba_model_fallback": nba_engine is None,
                        "live": nba_live,
                        "expected_pace": nba_prediction.expected_pace if nba_prediction else None,
                        "rest_days_home": nba_prediction.rest_days_home if nba_prediction else None,
                        "rest_days_away": nba_prediction.rest_days_away if nba_prediction else None,
                        "rest_adjustment": (
                            (nba_prediction.rest_adjustment_home - nba_prediction.rest_adjustment_away)
                            if nba_prediction else None
                        ),
                        "current_period": game.current_period if nba_live else None,
                        "home_score": game.home_score if nba_live else None,
                        "away_score": game.away_score if nba_live else None,
                    }
                    if parsed.sport == "nba" else {}
                ),
                **(
                    {
                        "nhl_model_fallback": nhl_engine is None,
                        "live": nhl_live,
                        "goalie_known_home": nhl_prediction.goalie_known_home if nhl_prediction else None,
                        "goalie_known_away": nhl_prediction.goalie_known_away if nhl_prediction else None,
                        "rookie_goalie_home": nhl_prediction.rookie_goalie_home if nhl_prediction else None,
                        "rookie_goalie_away": nhl_prediction.rookie_goalie_away if nhl_prediction else None,
                        "goalie_delta_home": nhl_prediction.goalie_delta_home if nhl_prediction else None,
                        "goalie_delta_away": nhl_prediction.goalie_delta_away if nhl_prediction else None,
                        "special_teams_shift_home": (
                            nhl_prediction.special_teams_shift_home if nhl_prediction else None
                        ),
                        "special_teams_shift_away": (
                            nhl_prediction.special_teams_shift_away if nhl_prediction else None
                        ),
                        "current_period": game.current_period if nhl_live else None,
                        "home_score": game.home_score if nhl_live else None,
                        "away_score": game.away_score if nhl_live else None,
                    }
                    if parsed.sport == "nhl" else {}
                ),
                **(
                    {
                        "neutral_site": ncaaf_prediction.neutral_site if ncaaf_prediction else None,
                        "talent_gap_weight": (
                            ncaaf_prediction.talent_gap_weight if ncaaf_prediction else None
                        ),
                        "expected_margin": (
                            ncaaf_prediction.expected_margin if ncaaf_prediction else None
                        ),
                    }
                    if parsed.sport == "ncaaf" else {}
                ),
                **(
                    {
                        "ncaamb_model_fallback": ncaamb_engine is None,
                        "neutral_site": ncaamb_neutral_site,
                        "expected_pace": ncaamb_prediction.expected_pace if ncaamb_prediction else None,
                        "rest_days_home": ncaamb_prediction.rest_days_home if ncaamb_prediction else None,
                        "rest_days_away": ncaamb_prediction.rest_days_away if ncaamb_prediction else None,
                    }
                    if parsed.sport == "ncaamb" else {}
                ),
            },
        )


# =========================================================================
# Phenon Harness WS-A2: power-ratings challenger ladder + divergence flag.
# =========================================================================
#
# Consumes WS-A1's `consensus_margin` (autonomy/sports/power_ratings.py --
# ESPN FPI/BPI blended with a read-only Elo read) and turns the resulting
# ensemble margin into TWO emissions, both challenger-only / fail-closed:
#
#   Emission 1 (standalone challenger): winner + the FULL spread ladder
#   priced from ONE distribution -- `margin_distribution` (football) or the
#   WS-2 normal-margin helper (`win_probability_from_margin` /
#   `spread_cover_probability` in nba_model.py, basketball) -- so winner and
#   spread stay lattice-coherent by construction, exactly like every other
#   engine hook in this module.
#
#   Emission 2 (opportunistic divergence): a bounded `power_divergence`
#   feature on the SAME Signal, fired only when the consensus disagrees with
#   "our own" engine (the generic TeamScoreModel every league already falls
#   back to) by more than a per-league threshold AND the power-ratings
#   sources themselves agree (dispersion below a per-league ceiling) --
#   high dispersion suppresses the flag rather than trusting a noisy read.
#
# Pre-game only (first pass, per the WS-A2 brief): this sidesteps the
# nba_live/nhl_live double-count question WS-6/7 had to solve -- a later
# pass can extend live coverage the same way if this is ever promoted.

FOOTBALL_POWER_LEAGUES = ("nfl", "ncaaf")
BASKETBALL_POWER_LEAGUES = ("nba", "ncaamb")
# The 4 leagues this signal supports (retired POINTS_PER_RATING_UNIT's role
# as the leagues gate now that per-league scaling moved into each
# RatingSource -- see autonomy/sports/power_ratings.py).
POWER_RATINGS_SUPPORTED_LEAGUES = FOOTBALL_POWER_LEAGUES + BASKETBALL_POWER_LEAGUES

POWER_RATINGS_MODEL_VERSION = "power_ratings_consensus_v1"

# Per-league divergence gate (points, home-signed): |ensemble_margin -
# our_engine_margin| must exceed this before the opportunist/mispricing
# path is told about a divergence. One flat threshold would over-fire on
# high-scoring sports (NFL/NCAAF) and under-fire on lower-scoring ones
# (NBA/NCAAMB use tighter per-possession scoring), so this is per-league.
# Propose-then-promote TUNER CANDIDATES, not placeholders.
DIVERGENCE_THRESHOLD: dict[str, float] = {
    "nfl": 4.0,
    "ncaaf": 5.0,
    "nba": 5.0,
    "ncaamb": 6.0,
}

# Per-league dispersion ceiling (points, max-min implied margin across
# sources): the power-ratings sources must roughly AGREE before a gap vs
# our own engine is trusted as real signal rather than consensus noise.
# High dispersion suppresses Emission 2 outright, independent of gap size.
# Propose-then-promote TUNER CANDIDATES, not placeholders.
DISPERSION_CEILING: dict[str, float] = {
    "nfl": 6.0,
    "ncaaf": 7.0,
    "nba": 6.0,
    "ncaamb": 7.0,
}

# Emission 1: dispersion (source disagreement) widens uncertainty ONLY --
# never the mean, never a silent suppress of the challenger itself. Bounded
# additive widen, capped so a wildly dispersed read can't blow past the
# ontology's useful uncertainty range. Propose-then-promote TUNER
# CANDIDATES.
POWER_RATINGS_BASE_UNCERTAINTY = 0.30
DISPERSION_UNCERTAINTY_SCALE = 0.01   # +uncertainty per point of dispersion
DISPERSION_UNCERTAINTY_CAP = 0.15     # max additive widen from dispersion alone

# Basketball challenger sigma (nba/ncaamb): reuses nba_model's shared base
# margin sigma (the WS-2 normal-margin helper) rather than hand-rolling a
# normal. The power-ratings consensus carries no per-matchup pace signal to
# heteroskedastically scale by (unlike NbaModel's own sigma), so this is a
# fixed challenger-only simplification -- a tuner candidate, never the same
# object as NbaModel's per-game sigma.
POWER_RATINGS_BASKETBALL_SIGMA = NBA_MARGIN_SIGMA_BASE

# Massey/Colley solve once at construction and cache; unlike Elo/TeamScoreModel
# (reloaded from disk every cycle) they would otherwise freeze at construction
# while the rest of the ensemble tracks fresh settlements. New games settle at
# most a few times a day, so re-solving every 10-minute cycle is wasteful; this
# TTL re-warms the OWNED sources at most once per window in on_cycle_start.
# Propose-then-promote TUNER CANDIDATE.
MASSEY_COLLEY_REWARM_TTL_HOURS = 12.0


class PowerRatingsSignal:
    """Standalone power-ratings challenger: winner+spread ladder + divergence.

    See the module comment block above for the two emissions. Every emitted
    Signal is challenger_only/not promotion_eligible; a down/thin/all-
    sources-none consensus (`consensus_margin` returns None) emits NO
    signal at all, byte-identical to this whole feature being disabled.
    """

    name = "power_ratings"

    def __init__(
        self,
        espn: EspnClient | None = None,
        elo_dir: Path | None = None,
        model_dir: Path | None = None,
        fpi_source: Any = None,
        bpi_source: Any = None,
        massey_source: Any = None,
        colley_source: Any = None,
        seasons: Any = None,
        consensus_fn: Any = None,
        models: dict[str, TeamScoreModel] | None = None,
        elo_models: dict[str, EloModel] | None = None,
    ) -> None:
        from autonomy.specialists.seasons import SeasonMonitor

        self.espn = espn or EspnClient()
        self.elo_dir = elo_dir or ELO_DIR
        self.model_dir = model_dir or MODEL_DIR
        self.seasons = seasons or SeasonMonitor(espn=self.espn)
        # Injectable seam for tests: bypasses source selection/fetch/Elo
        # entirely and lets a fixed ConsensusMargin drive the emission math.
        # Defaults to the real WS-A1 blend.
        self._consensus_fn = consensus_fn or consensus_margin
        # Shared keyless FPI/BPI fetch sources -- one instance per league
        # family (mirrors WS-A1's own per-cycle-warmed-instance pattern),
        # never mutated by anything in this class.
        self.fpi_source = fpi_source or EspnFpiSource()
        self.bpi_source = bpi_source or EspnBpiSource()
        # WS-A1b: in-house Massey (ridge least-squares over margins) +
        # Colley (win-loss matrix) sources, mathematically independent of
        # ESPN FPI/BPI/Elo -- see autonomy/sports/ratings_solvers.py. Solved
        # ONCE here at construction time (not re-solved every cycle) and
        # cached on the source; a caller-injected source is trusted as
        # already warm and is NEVER auto-warmed here, mirroring how an
        # injected fpi_source/bpi_source is never re-fetched by this
        # __init__ either.
        self.massey_source = massey_source or MasseyRatingSource(espn=self.espn)
        self.colley_source = colley_source or ColleyRatingSource(espn=self.espn)
        # Only sources this instance CONSTRUCTED are auto-warmed (and later
        # re-warmed): a caller-injected source is trusted as already warm and
        # is never touched, mirroring the injected fpi/bpi contract above.
        self._owns_massey = massey_source is None
        self._owns_colley = colley_source is None
        # Wall-clock of the last (re-)warm, so on_cycle_start re-solves only
        # once per MASSEY_COLLEY_REWARM_TTL_HOURS instead of every cycle. None
        # until the first warm lands.
        self._last_massey_colley_warm: datetime | None = None
        if self._owns_massey or self._owns_colley:
            self._warm_massey_colley(
                warm_massey=self._owns_massey, warm_colley=self._owns_colley)
            self._last_massey_colley_warm = datetime.now(timezone.utc)
        # "Our own" per-league engine for the divergence gap (Emission 2):
        # the generic TeamScoreModel every league already falls back to
        # (see TeamSportsIntelligenceSignal) -- reloaded (never retrained)
        # from the SAME on-disk file that signal trains every cycle, so
        # this stays a pure read of the system's actual baseline rather
        # than a duplicated second copy.
        self.models = models or {
            league: TeamScoreModel.load(
                league, self.model_dir / f"team_scores_{league}.json")
            for league in POWER_RATINGS_SUPPORTED_LEAGUES
        }
        # Read-only Elo reads, same discipline as EloSource's own contract:
        # reloaded (never retrained) from the SAME per-league file
        # SportsEloSignal already trains every cycle.
        self.elo_models = elo_models or {
            league: EloModel.load(league, self.elo_dir / f"elo_{league}.json")
            for league in POWER_RATINGS_SUPPORTED_LEAGUES
        }

    def _warm_massey_colley(self, warm_massey: bool = True, warm_colley: bool = True) -> None:
        """Solve Massey/Colley once per league over the trailing settled-game
        window (see `_massey_colley_date_ranges`). Same fail-closed shape as
        every other per-league warm in this module: a dormant league (season
        gate) or an exception mid-fetch is skipped/swallowed rather than
        raised, leaving that league's ratings empty (byte-identical to the
        source being absent) instead of crashing signal construction.
        """
        if not (warm_massey or warm_colley):
            return
        date_ranges = _massey_colley_date_ranges()
        for league in POWER_RATINGS_SUPPORTED_LEAGUES:
            try:
                if not self.seasons.active(league):
                    continue
            except Exception:
                continue
            if warm_massey:
                try:
                    self.massey_source.warmup(league, date_ranges)
                except Exception:
                    pass
                else:
                    if not getattr(self.massey_source, "_ratings", {}).get(league):
                        logger.warning(
                            "Massey warmup produced no ratings (dropped from ensemble)",
                            extra={"component": "sports_intelligence", "league": league, "source": "massey"},
                        )
            if warm_colley:
                try:
                    self.colley_source.warmup(league, date_ranges)
                except Exception:
                    pass
                else:
                    if not getattr(self.colley_source, "_ratings", {}).get(league):
                        logger.warning(
                            "Colley warmup produced no ratings (dropped from ensemble)",
                            extra={"component": "sports_intelligence", "league": league, "source": "colley"},
                        )

    def _sources(self, league: str) -> list[Any]:
        rating_source = (
            self.fpi_source if league in FOOTBALL_POWER_LEAGUES else self.bpi_source
        )
        return [
            rating_source,
            EloSource(self.elo_models[league]),
            self.massey_source,
            self.colley_source,
        ]

    def on_cycle_start(self) -> None:
        self.espn.clear_cache()
        try:
            self.elo_models = {
                league: EloModel.load(league, self.elo_dir / f"elo_{league}.json")
                for league in POWER_RATINGS_SUPPORTED_LEAGUES
            }
            self.models = {
                league: TeamScoreModel.load(
                    league, self.model_dir / f"team_scores_{league}.json")
                for league in POWER_RATINGS_SUPPORTED_LEAGUES
            }
        except Exception:
            pass  # keep last-loaded state rather than go cold on a blip
        self._rewarm_massey_colley_if_stale()

    def _rewarm_massey_colley_if_stale(self) -> None:
        """Re-solve owned Massey/Colley sources at most once per TTL.

        Keeps the in-house ratings tracking fresh settlements instead of
        freezing at construction, without paying the college-scale solve every
        cycle. Injected sources (tests) are never touched. Fail-closed: a warm
        that raises leaves the last-good ratings in place (``_warm_massey_colley``
        already swallows per-league errors); the timestamp advances regardless
        so a persistently failing feed is retried on the TTL, not every cycle.
        """
        if not (self._owns_massey or self._owns_colley):
            return
        now = datetime.now(timezone.utc)
        last = self._last_massey_colley_warm
        if last is not None and (now - last) < timedelta(
            hours=MASSEY_COLLEY_REWARM_TTL_HOURS
        ):
            return
        try:
            self._warm_massey_colley(
                warm_massey=self._owns_massey, warm_colley=self._owns_colley)
        except Exception:
            pass  # keep last-good ratings; never wedge the cycle on a warm blip
        # Advance the timestamp regardless of outcome so a persistently failing
        # feed is retried on the TTL, not hammered every cycle.
        self._last_massey_colley_warm = now

    def applicable(self, market: MarketView) -> bool:
        parsed = parse_sports_contract(market)
        return (
            market.vertical is Vertical.SPORTS
            and parsed is not None
            and parsed.sport in POWER_RATINGS_SUPPORTED_LEAGUES
            and parsed.market_type in ("winner", "spread")
        )

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_sports_contract(market)
        if (
            parsed is None
            or parsed.sport not in POWER_RATINGS_SUPPORTED_LEAGUES
            or parsed.market_type not in ("winner", "spread")
            or parsed.competitors is None
            or not parsed.subject
        ):
            return None
        if parsed.market_type == "winner":
            game = self.espn.find_matchup(
                parsed.sport, parsed.competitors[0], parsed.competitors[1],
                parsed.date_yyyymmdd,
            )
        else:
            game = self.espn.find_matchup_names(
                parsed.sport, parsed.competitors[0], parsed.competitors[1],
                parsed.date_yyyymmdd,
            )
        # Pre-game only (see class docstring): never fight a live or settled
        # market -- no live double-count question to solve on this pass.
        if game is None or game.status != "pre":
            return None
        home = canonical_team(parsed.sport, game.home)
        away = canonical_team(parsed.sport, game.away)
        subject = parsed.subject.upper()
        if subject == home:
            subject_is_home = True
        elif subject == away:
            subject_is_home = False
        else:
            return None

        consensus = self._consensus_fn(home, away, parsed.sport, self._sources(parsed.sport))
        if consensus is None:
            return None  # fail-closed: every source down/thin -- no signal at all

        is_football = parsed.sport in FOOTBALL_POWER_LEAGUES
        if is_football:
            # WS-C routing doctrine: college engines price off the shallower
            # college key-number table (BASE_ABS_MARGIN_PMF_COLLEGE), not
            # NFL's -- college margins spike less hard on 3/7 and run a
            # longer tail (see autonomy/sports/college.py). NFL keeps the
            # module default (base_pmf=None -> BASE_ABS_MARGIN_PMF).
            football_base_pmf = (
                BASE_ABS_MARGIN_PMF_COLLEGE if parsed.sport == "ncaaf" else None
            )
            distribution = power_ratings_margin_distribution(
                consensus.ensemble_margin, base_pmf=football_base_pmf)
            home_win = power_ratings_nfl_win_probability(distribution)
            if parsed.market_type == "spread":
                if parsed.threshold is None:
                    return None
                subject_distribution = (
                    distribution if subject_is_home
                    else {-m: p for m, p in distribution.items()}
                )
                probability = power_ratings_nfl_spread_cover_probability(
                    subject_distribution, parsed.threshold)
            else:
                probability = home_win if subject_is_home else 1.0 - home_win
        else:
            sigma = POWER_RATINGS_BASKETBALL_SIGMA
            home_win = nba_win_probability_from_margin(consensus.ensemble_margin, sigma)
            if parsed.market_type == "spread":
                if parsed.threshold is None:
                    return None
                subject_margin = (
                    consensus.ensemble_margin if subject_is_home
                    else -consensus.ensemble_margin
                )
                probability = nba_spread_cover_probability(subject_margin, sigma, parsed.threshold)
            else:
                probability = home_win if subject_is_home else 1.0 - home_win
        probability = min(0.995, max(0.005, probability))

        # Emission 1: dispersion widens uncertainty ONLY -- bounded, capped
        # -- never the mean and never a silent suppress of the challenger.
        uncertainty = min(
            0.45,
            POWER_RATINGS_BASE_UNCERTAINTY
            + min(DISPERSION_UNCERTAINTY_CAP, DISPERSION_UNCERTAINTY_SCALE * consensus.dispersion),
        )

        # Emission 2: opportunistic divergence flag. Bounded evidence only
        # (never a capital action): fires ONLY when the gap between the
        # consensus and our own engine is large AND the power-ratings
        # sources themselves agree (low dispersion) -- high dispersion
        # suppresses the flag even when the raw gap looks large, since a
        # noisy consensus could simply be wrong rather than informative.
        power_divergence: dict[str, Any] | None = None
        our_prediction = self.models[parsed.sport].predict(game)
        our_engine_margin = our_prediction.expected_home_score - our_prediction.expected_away_score
        gap = consensus.ensemble_margin - our_engine_margin
        if (
            abs(gap) > DIVERGENCE_THRESHOLD[parsed.sport]
            and consensus.dispersion < DISPERSION_CEILING[parsed.sport]
        ):
            kalshi_mid = None
            if market.yes_bid is not None and market.yes_ask is not None:
                kalshi_mid = (market.yes_bid + market.yes_ask) / 2.0 / 100.0
            power_divergence = {
                "sport": parsed.sport,
                "gap": round(gap, 3),
                "ensemble_margin": round(consensus.ensemble_margin, 3),
                "our_engine_margin": round(our_engine_margin, 3),
                "dispersion": round(consensus.dispersion, 3),
                "kalshi_mid": kalshi_mid,
            }

        return Signal(
            source=f"power_ratings_{parsed.sport}",
            market_ticker=market.ticker,
            probability_yes=probability,
            uncertainty=uncertainty,
            rationale=(
                f"{parsed.sport.upper()} power-ratings consensus {home}/{away}: "
                f"ensemble_margin={consensus.ensemble_margin:.2f} "
                f"(n_sources={consensus.n_sources}, dispersion={consensus.dispersion:.2f})"
            ),
            features={
                "challenger_only": True,
                "promotion_eligible": False,
                "point_in_time": True,
                "public_read_only": True,
                "sport": parsed.sport,
                "market_type": parsed.market_type,
                "margin_model_version": POWER_RATINGS_MODEL_VERSION,
                "ensemble_margin": consensus.ensemble_margin,
                "dispersion": consensus.dispersion,
                "n_sources": consensus.n_sources,
                "per_source": dict(consensus.per_source),
                "threshold": parsed.threshold,
                "power_divergence": power_divergence,
            },
        )
