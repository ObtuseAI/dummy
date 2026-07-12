"""Settlement-trained sports intelligence challengers (MLB + team leagues)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.sports.baseball import BaseballRunModel, remaining_innings
from autonomy.sports.espn import EspnClient, canonical_team
from autonomy.sports.injuries import InjuryBook
from autonomy.sports.team_scores import LEAGUE_SCORE_CONFIGS, TeamScoreModel

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
    ) -> None:
        from autonomy.specialists.seasons import SeasonMonitor

        self.espn = espn or EspnClient()
        self.model_path = model_path or MODEL_DIR / "mlb_runs_model.json"
        self.model = model or BaseballRunModel.load(self.model_path)
        self.injuries = injuries or InjuryBook()
        self.seasons = seasons or SeasonMonitor(espn=self.espn)

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

    def applicable(self, market: MarketView) -> bool:
        parsed = parse_sports_contract(market)
        return market.vertical is Vertical.SPORTS and parsed is not None and parsed.sport == "mlb"

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
                probability = self.model.live_total_probability(
                    prediction, home_score + away_score, parsed.threshold, rem)
                uncertainty = min(0.45, prediction.total_uncertainty + 0.05)
                source = "mlb_live_total"
                market_detail = (
                    f"live over {parsed.threshold:g} ({home_score + away_score} so far, "
                    f"inning {game.current_period})"
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
        uncertainty = min(0.45, uncertainty + 0.05 * injury_burden)
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
        if game is None or game.status != "pre":
            return None
        prediction = self.models[parsed.sport].predict(game)
        if parsed.market_type == "winner" and parsed.subject:
            subject = parsed.subject.upper()
            if subject == game.home.upper():
                probability = prediction.home_win_probability
            elif subject == game.away.upper():
                probability = 1.0 - prediction.home_win_probability
            else:
                return None
            uncertainty = prediction.winner_uncertainty
            source = f"{parsed.sport}_structural_winner"
            detail = f"{subject} win"
        elif parsed.market_type == "total" and parsed.threshold is not None:
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
                f"{prediction.expected_away_score:.2f}+{prediction.expected_home_score:.2f}="
                f"{prediction.expected_total:.2f}; paired sample={prediction.sample_games}"
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
                "expected_home_score": prediction.expected_home_score,
                "expected_away_score": prediction.expected_away_score,
                "expected_total": prediction.expected_total,
                "threshold": parsed.threshold,
                "sample_games": prediction.sample_games,
            },
        )
