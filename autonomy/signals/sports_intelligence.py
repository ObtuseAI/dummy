"""Settlement-trained sports intelligence challengers (MLB + team leagues)."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from autonomy.live_odds import EspnSummaryBook
from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.sports import boxscores as boxscores_module
from autonomy.sports.baseball import (
    BaseballRunModel,
    remaining_innings,
    rest_travel_uncertainty_bump,
)
from autonomy.sports.boxscores import BoxscoreStore, parse_team_boxscores
from autonomy.sports.espn import EspnClient, Game, canonical_team, default_fetch_scoreboard
from autonomy.sports.injuries import InjuryBook
from autonomy.sports.nba_model import (
    MODEL_VERSION as NBA_MODEL_VERSION,
    NbaModel,
    is_warm as nba_is_warm,
    minutes_remaining_in_game as nba_minutes_remaining,
)
from autonomy.sports.nhl_model import (
    MODEL_VERSION as NHL_MODEL_VERSION,
    NhlModel,
    is_warm as nhl_is_warm,
    minutes_remaining_in_game as nhl_minutes_remaining,
    parse_goalie_boxscores,
    parse_probable_goalies,
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

MODEL_DIR = Path("runtime/autonomy")
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
                if league == "nba":
                    self._warmup_nba([recent])
                elif league == "nhl":
                    self._warmup_nhl([recent])
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

            nfl_kernel = NflMarginModel(
                prediction.expected_home_score, prediction.expected_away_score)
            margin_model_version = "nfl_key_number_kernel_v1"

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
                if nhl_live:
                    minutes_remaining = nhl_minutes_remaining(game.current_period, game.current_clock)
                    if minutes_remaining is None:
                        return None
                    nhl_live_state = (game.home_score, game.away_score, minutes_remaining)

        # Report numbers from whichever model actually priced this signal
        # (NbaModel/NhlModel when warm, the generic TeamScoreModel otherwise/
        # always for every other league) -- keeps the rationale/features
        # numbers consistent with `probability` instead of silently mixing
        # models.
        if nba_prediction is not None:
            report = nba_prediction
        elif nhl_prediction is not None:
            report = nhl_prediction
        else:
            report = prediction

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
                elif nfl_kernel is not None:
                    home_win = nfl_kernel.home_win_probability()
                else:
                    home_win = prediction.home_win_probability
                source = f"{parsed.sport}_structural_winner"
                detail = f"{subject} win"
                uncertainty = (
                    nhl_prediction.winner_uncertainty
                    if nhl_engine is not None
                    else prediction.winner_uncertainty
                )
            probability = home_win if subject_is_home else 1.0 - home_win
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
                uncertainty = (
                    min(0.44, nhl_prediction.winner_uncertainty + 0.02)
                    if nhl_engine is not None
                    else min(0.44, prediction.winner_uncertainty + 0.02)
                )
                source = f"{parsed.sport}_spread"
                detail = f"{subject} covers {parsed.threshold:g}"
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
            else:
                probability = self.models[parsed.sport].total_probability(
                    prediction, parsed.threshold,
                )
                uncertainty = prediction.total_uncertainty
                source = f"{parsed.sport}_game_total"
                detail = f"over {parsed.threshold:g}"
        else:
            return None
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
            },
        )
