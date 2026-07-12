"""Sports signal: Elo win-probability vs Kalshi single-game moneyline markets.

Parses Kalshi game tickers (KX{LEAGUE}GAME-<date><time?><AWAYHOME>-<SUBJECT>),
locates the matchup on ESPN to resolve home/away and confirm it hasn't started,
and emits P(subject wins) from the persistent per-league Elo model. Elo is
warmed up from the season's completed games and keeps learning from every
settled result the reconciler feeds back.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.sports.elo import EloModel
from autonomy.sports.espn import LEAGUE_TO_ESPN, EspnClient

_LEAGUE_RE = re.compile(r"^KX([A-Z]+)GAME$")
_MIDDLE_RE = re.compile(r"^(\d{2})([A-Z]{3})(\d{2})(\d{4})?([A-Z]{4,10})$")
_MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], start=1)}

ELO_DIR = Path("runtime/autonomy")


def parse_game_ticker(ticker: str) -> dict[str, Any] | None:
    parts = ticker.split("-")
    if len(parts) < 3:
        return None
    league_match = _LEAGUE_RE.match(parts[0])
    if not league_match:
        return None
    league = league_match.group(1).lower()
    if league not in LEAGUE_TO_ESPN:
        return None
    middle_match = _MIDDLE_RE.match(parts[1])
    if not middle_match:
        return None
    yy, mon, dd, _time, teams = middle_match.groups()
    month = _MONTHS.get(mon)
    if not month:
        return None
    subject = parts[2].upper()
    teams = teams.upper()
    if teams.startswith(subject):
        opponent = teams[len(subject):]
    elif teams.endswith(subject):
        opponent = teams[: -len(subject)]
    else:
        return None
    if not opponent:
        return None
    return {
        "league": league,
        "date_yyyymmdd": f"20{yy}{month:02d}{int(dd):02d}",
        "subject": subject,
        "opponent": opponent,
    }


class SportsEloSignal:
    name = "sports_elo"

    def __init__(self, espn: EspnClient | None = None, elo_dir: Path | None = None,
                 seasons=None):
        from autonomy.specialists.seasons import SeasonMonitor

        self.espn = espn or EspnClient()
        self.elo_dir = elo_dir or ELO_DIR
        self._models: dict[str, EloModel] = {}
        # Season gate shares this signal's ESPN client and skips dormant
        # leagues' per-cycle retrain fetches (they have no finished games).
        self.seasons = seasons or SeasonMonitor(espn=self.espn)

    def _model(self, league: str) -> EloModel:
        if league not in self._models:
            self._models[league] = EloModel.load(league, self.elo_dir / f"elo_{league}.json")
        return self._models[league]

    def warmup(self, league: str, date_ranges: list[str]) -> EloModel:
        """Replay completed games (chronological) to train ratings."""
        model = self._model(league)
        games: list[Any] = []
        for dates in date_ranges:
            games.extend(self.espn.games(league, dates))
        for game in sorted(games, key=lambda g: g.date):
            if game.status == "post" and game.home_won is not None:
                model.update(game.home, game.away, game.home_won, game_id=game.game_id)
        model.save(self.elo_dir / f"elo_{league}.json")
        return model

    def on_cycle_start(self, recent_range: str | None = None) -> None:
        """Absorb just-completed games into Elo and reset the per-cycle cache.

        This is how the sports model keeps learning while live: every finished
        game since the last cycle updates ratings (idempotent via game_id).
        """
        self.espn.clear_cache()
        from datetime import datetime, timedelta, timezone

        if recent_range is None:
            today = datetime.now(timezone.utc).date()
            start = today - timedelta(days=2)
            recent_range = f"{start.strftime('%Y%m%d')}-{today.strftime('%Y%m%d')}"
        for league in LEAGUE_TO_ESPN:
            try:
                if not self.seasons.active(league):
                    continue  # dormant league: no finished games to absorb
                self.warmup(league, [recent_range])
            except Exception:
                continue
        self.espn.clear_cache()

    def applicable(self, market: MarketView) -> bool:
        return market.vertical is Vertical.SPORTS and parse_game_ticker(market.ticker) is not None

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_game_ticker(market.ticker)
        if parsed is None:
            return None
        league = parsed["league"]
        model = self._model(league)

        game = self.espn.find_matchup(league, parsed["subject"], parsed["opponent"],
                                      dates=parsed["date_yyyymmdd"])
        # Never fight a settlement: skip games already started or finished.
        if game is not None and game.status != "pre":
            return None
        subject_home = None if game is None else (game.home.upper() == parsed["subject"])

        # Starting-pitcher ERAs (baseball). Map the game's home/away probables
        # to the subject and opponent based on who is home.
        subject_era = opponent_era = None
        subject_pitcher = opponent_pitcher = None
        if game is not None and subject_home is not None:
            if subject_home:
                subject_era, opponent_era = game.home_pitcher_era, game.away_pitcher_era
                subject_pitcher, opponent_pitcher = game.home_pitcher, game.away_pitcher
            else:
                subject_era, opponent_era = game.away_pitcher_era, game.home_pitcher_era
                subject_pitcher, opponent_pitcher = game.away_pitcher, game.home_pitcher

        p_yes = model.predict_team(parsed["subject"], parsed["opponent"], subject_home,
                                   subject_pitcher_era=subject_era, opponent_pitcher_era=opponent_era)
        p_yes = min(0.98, max(0.02, p_yes))

        has_pitchers = subject_era is not None and opponent_era is not None
        coldness = 0.20 if model.games_seen < 50 else 0.05
        site_penalty = 0.06 if subject_home is None else 0.0  # unknown venue = weaker
        pitcher_bonus = -0.03 if has_pitchers else 0.0  # extra info tightens uncertainty
        uncertainty = min(0.5, max(0.05, 0.22 - 0.30 * abs(p_yes - 0.5) + coldness + site_penalty + pitcher_bonus))
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=p_yes,
            uncertainty=uncertainty,
            rationale=(
                f"{league.upper()} Elo {parsed['subject']}({model.rating(parsed['subject']):.0f}) "
                f"vs {parsed['opponent']}({model.rating(parsed['opponent']):.0f}) "
                f"home={subject_home} games_seen={model.games_seen}"
                + (f" | SP {subject_pitcher}({subject_era}) vs {opponent_pitcher}({opponent_era})"
                   if has_pitchers else "")
            ),
            features={
                "subject_rating": model.rating(parsed["subject"]),
                "opponent_rating": model.rating(parsed["opponent"]),
                "subject_home": subject_home,
                "games_seen": model.games_seen,
                "subject_pitcher_era": subject_era,
                "opponent_pitcher_era": opponent_era,
            },
        )
