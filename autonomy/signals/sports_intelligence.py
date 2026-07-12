"""Settlement-trained MLB runs and UFC fight intelligence challengers."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.sports.baseball import BaseballRunModel
from autonomy.sports.espn import EspnClient, canonical_team
from autonomy.sports.formula_one import F1EspnClient, F1Model, normalize_text
from autonomy.sports.team_scores import LEAGUE_SCORE_CONFIGS, TeamScoreModel
from autonomy.sports.ufc import UfcEspnClient, UfcModel, normalize_name

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
    if series == "KXF1RACE":
        subject = str(market.raw.get("yes_sub_title") or "").strip()
        return SportsContract(
            "f1", "winner", "", subject=subject or None, fight_code=parts[1],
        )
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

    if series in {"KXUFCFIGHT", "KXUFCROUNDS", "KXUFCDISTANCE"}:
        fight_code = remainder[:6] if len(remainder) >= 6 else remainder
        if series == "KXUFCFIGHT":
            subject = str(market.raw.get("yes_sub_title") or "").strip()
            return SportsContract(
                "ufc", "winner", date_yyyymmdd,
                subject=subject or None, fight_code=fight_code,
            )
        if series == "KXUFCROUNDS":
            threshold = None
            if len(parts) >= 3:
                try:
                    threshold = float(parts[2])
                except ValueError:
                    threshold = None
            if threshold is None:
                match = re.search(r"before round\s+(\d+)", market.title, flags=re.IGNORECASE)
                threshold = float(match.group(1)) if match else None
            if threshold is None:
                return None
            return SportsContract(
                "ufc", "before_round", date_yyyymmdd,
                threshold=threshold, fight_code=fight_code,
            )
        return SportsContract("ufc", "distance", date_yyyymmdd, fight_code=fight_code)
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
    ) -> None:
        self.espn = espn or EspnClient()
        self.model_path = model_path or MODEL_DIR / "mlb_runs_model.json"
        self.model = model or BaseballRunModel.load(self.model_path)

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
        self.espn.clear_cache()
        self.warmup([_date_range()])
        self.espn.clear_cache()

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
        if game is None or game.status != "pre":
            return None
        prediction = self.model.predict(game)
        if parsed.market_type == "winner":
            subject = canonical_team("mlb", parsed.subject or "")
            home = canonical_team("mlb", game.home)
            if subject not in {home, canonical_team("mlb", game.away)}:
                return None
            probability = (
                prediction.home_win_probability
                if subject == home else 1.0 - prediction.home_win_probability
            )
            uncertainty = prediction.winner_uncertainty
            source = "mlb_structural_winner"
            market_detail = f"{subject} win"
        elif parsed.market_type == "total_runs" and parsed.threshold is not None:
            probability = self.model.total_probability(prediction, parsed.threshold)
            uncertainty = prediction.total_uncertainty
            source = "mlb_total_runs"
            market_detail = f"over {parsed.threshold:g} runs"
        elif parsed.market_type == "spread" and parsed.threshold is not None and parsed.subject:
            subject = canonical_team("mlb", parsed.subject)
            home = canonical_team("mlb", game.home)
            away = canonical_team("mlb", game.away)
            if subject == home:
                probability = self.model.spread_probability(
                    prediction, subject_is_home=True, margin=parsed.threshold)
            elif subject == away:
                probability = self.model.spread_probability(
                    prediction, subject_is_home=False, margin=parsed.threshold)
            else:
                return None
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
    ) -> None:
        self.espn = espn or EspnClient()
        self.model_dir = model_dir or MODEL_DIR
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


class UfcIntelligenceSignal:
    """Challenger forecasts for UFC winners, round totals, and distance."""

    name = "ufc_intelligence"

    def __init__(
        self,
        espn: UfcEspnClient | None = None,
        model: UfcModel | None = None,
        model_path: Path | None = None,
    ) -> None:
        self.espn = espn or UfcEspnClient()
        self.model_path = model_path or MODEL_DIR / "ufc_model.json"
        self.model = model or UfcModel.load(self.model_path)

    def warmup(self, dates: list[str]) -> int:
        updated = 0
        fights: list[Any] = []
        for date_range in dates:
            fights.extend(self.espn.fights(date_range))
        for fight in sorted(fights, key=lambda item: item.date):
            updated += int(self.model.update(fight))
        if updated:
            self.model.save(self.model_path)
        return updated

    def on_cycle_start(self) -> None:
        self.espn.clear_cache()
        self.warmup([_date_range(14)])
        self.espn.clear_cache()

    def applicable(self, market: MarketView) -> bool:
        parsed = parse_sports_contract(market)
        return market.vertical is Vertical.SPORTS and parsed is not None and parsed.sport == "ufc"

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_sports_contract(market)
        if parsed is None or parsed.sport != "ufc":
            return None
        fight = self.espn.find_fight(parsed.subject, parsed.fight_code, parsed.date_yyyymmdd)
        if fight is None or fight.status != "pre":
            return None
        prediction = self.model.predict(fight)
        if parsed.market_type == "winner" and parsed.subject:
            subject = normalize_name(parsed.subject)
            if subject == normalize_name(fight.fighter_a):
                probability = prediction.fighter_a_win_probability
            elif subject == normalize_name(fight.fighter_b):
                probability = 1.0 - prediction.fighter_a_win_probability
            else:
                return None
            uncertainty = prediction.winner_uncertainty
            source = "ufc_fight_winner"
            market_detail = f"{parsed.subject} win"
        elif parsed.market_type == "before_round" and parsed.threshold is not None:
            probability = prediction.before_round_probability(int(parsed.threshold))
            uncertainty = prediction.duration_uncertainty
            source = "ufc_round_total"
            market_detail = f"finish before round {int(parsed.threshold)}"
        elif parsed.market_type == "distance":
            probability = prediction.distance_probability
            uncertainty = prediction.duration_uncertainty
            source = "ufc_fight_distance"
            market_detail = "go the distance"
        else:
            return None
        return Signal(
            source=source,
            market_ticker=market.ticker,
            probability_yes=min(0.995, max(0.005, probability)),
            uncertainty=uncertainty,
            rationale=(
                f"UFC {market_detail}: {fight.fighter_a} vs {fight.fighter_b}; "
                f"distance={prediction.distance_probability:.3f}; "
                f"weight={prediction.weight_class}; scheduled={prediction.scheduled_rounds}; "
                f"paired sample={prediction.sample_fights}"
            ),
            features={
                "challenger_only": True,
                "promotion_eligible": False,
                "point_in_time": True,
                "public_read_only": True,
                "market_type": parsed.market_type,
                "model_version": prediction.model_version,
                "event_start": fight.date,
                "fighter_a": fight.fighter_a,
                "fighter_b": fight.fighter_b,
                "weight_class": prediction.weight_class,
                "scheduled_rounds": prediction.scheduled_rounds,
                "distance_probability": prediction.distance_probability,
                "threshold": parsed.threshold,
                "sample_fights": prediction.sample_fights,
            },
        )


class FormulaOneIntelligenceSignal:
    """Field-normalized Formula One race-winner challenger."""

    name = "f1_intelligence"

    def __init__(
        self,
        espn: F1EspnClient | None = None,
        model: F1Model | None = None,
        model_path: Path | None = None,
    ) -> None:
        self.espn = espn or F1EspnClient()
        self.model_path = model_path or MODEL_DIR / "f1_model.json"
        self.model = model or F1Model.load(self.model_path)

    def warmup(self, year: int) -> int:
        updated = 0
        for race in sorted(self.espn.races(year), key=lambda item: item.date):
            updated += int(self.model.update(race))
        if updated:
            self.model.save(self.model_path)
        return updated

    def on_cycle_start(self) -> None:
        self.espn.clear_cache()
        self.warmup(datetime.now(timezone.utc).year)

    def applicable(self, market: MarketView) -> bool:
        parsed = parse_sports_contract(market)
        return market.vertical is Vertical.SPORTS and parsed is not None and parsed.sport == "f1"

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_sports_contract(market)
        if parsed is None or parsed.sport != "f1" or not parsed.subject:
            return None
        year = datetime.now(timezone.utc).year
        race = self.espn.find_race(year, market.title)
        if race is None or race.status != "pre":
            return None
        prediction = self.model.predict(race)
        probability = prediction.probabilities.get(normalize_text(parsed.subject))
        if probability is None:
            return None
        return Signal(
            source="f1_race_winner",
            market_ticker=market.ticker,
            probability_yes=min(0.995, max(0.005, probability)),
            uncertainty=prediction.uncertainty,
            rationale=(
                f"F1 {parsed.subject} to win {race.name}: field-normalized probability "
                f"{probability:.3f}; field={prediction.field_size}; "
                f"minimum driver history={prediction.minimum_driver_races} races"
            ),
            features={
                "challenger_only": True,
                "promotion_eligible": False,
                "point_in_time": True,
                "public_read_only": True,
                "sport": "f1",
                "market_type": "winner",
                "model_version": prediction.model_version,
                "event_start": race.date,
                "race": race.name,
                "driver": parsed.subject,
                "field_size": prediction.field_size,
                "sample_races": prediction.minimum_driver_races,
            },
        )
