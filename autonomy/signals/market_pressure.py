"""Market-pressure challenger signal (Wave-30).

Reads the multi-book line-movement archive, and for each pre-game sports
market infers the sharp/public picture -- cross-book steam, reverse line
movement against the public lean, soft-line dispersion -- and emits a capped,
challenger-only nudge toward the sharp side of the de-vig consensus. It only
speaks when there is an actionable read: no movement, too few books, or no
public/sharp divergence -> abstain.

Data comes from the Wave-12 odds archive (``DUMMY_ODDS_ARCHIVE_DIR``), not a
live fetch: line MOVEMENT needs history, and the archive already accumulates
every paid multi-book snapshot. The whole archive is read and featurized ONCE
per cycle (``on_cycle_start``); ``generate`` is then a lookup. Fully inert if
the archive is empty or missing. Never fights a settlement or a started game.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from autonomy.market_pressure import (
    detect_dispersion,
    detect_steam,
    movement_series,
    read_archive_window,
)
from autonomy.market_pressure.pressure import synthesize_pressure
from autonomy.market_pressure.public_lean import estimate_public_lean
from autonomy.market_pressure.splits.service import SplitsService
from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.signals.licensed_consensus import LEAGUE_TO_ODDS_SPORT
from autonomy.signals.sports_elo import parse_game_ticker
from autonomy.sports.espn import EspnClient

ARCHIVE_LOOKBACK_HOURS = 48.0
STEAM_WINDOW_HOURS = 12.0
MIN_BOOKS = 3


def _clamp(value: float, low: float = 0.02, high: float = 0.98) -> float:
    return max(low, min(high, value))


class MarketPressureSignal:
    name = "market_pressure"

    def __init__(
        self,
        espn: EspnClient | None = None,
        archive_dir: str | None = None,
        splits: SplitsService | None = None,
    ):
        self.espn = espn or EspnClient()
        self.archive_dir = archive_dir
        # Scraped splits (Wave-32). Inert unless DUMMY_SPLITS_ENABLED=1; when
        # absent the synthesis falls back to the estimated public lean.
        self.splits = splits if splits is not None else SplitsService()
        self._series: dict[tuple[str, str, str, str], Any] = {}
        self._latest_by_sport: dict[str, list[dict[str, Any]]] = {}
        self._now: float = 0.0

    def on_cycle_start(self) -> None:
        self.espn.clear_cache()
        self._now = datetime.now(timezone.utc).timestamp()
        try:
            self.splits.refresh(list(LEAGUE_TO_ODDS_SPORT.keys()))
        except Exception:
            pass   # fail-open: a scrape hiccup never breaks the cycle
        snapshots = read_archive_window(
            self.archive_dir,
            sport_keys=set(LEAGUE_TO_ODDS_SPORT.values()),
            now=self._now,
            lookback_hours=ARCHIVE_LOOKBACK_HOURS,
        )
        self._series = movement_series(snapshots)
        # Latest event dict per (sport, event_id) for team-name matching.
        latest: dict[str, dict[str, tuple[float, dict[str, Any]]]] = {}
        for ts, event in snapshots:
            sport = str(event.get("sport_key"))
            eid = str(event.get("id"))
            held = latest.setdefault(sport, {}).get(eid)
            if held is None or ts > held[0]:
                latest.setdefault(sport, {})[eid] = (ts, event)
        self._latest_by_sport = {
            sport: [pair[1] for pair in events.values()]
            for sport, events in latest.items()
        }

    def applicable(self, market: MarketView) -> bool:
        if market.vertical is not Vertical.SPORTS:
            return False
        parsed = parse_game_ticker(market.ticker)
        return parsed is not None and parsed["league"] in LEAGUE_TO_ODDS_SPORT

    def _subject_series(self, event_id: str, side_name: str) -> list[Any]:
        return [
            s for (eid, _book, mkt, side), s in self._series.items()
            if eid == event_id and mkt == "h2h" and side == side_name
        ]

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_game_ticker(market.ticker)
        if parsed is None or parsed["league"] not in LEAGUE_TO_ODDS_SPORT:
            return None
        sport_key = LEAGUE_TO_ODDS_SPORT[parsed["league"]]
        events = self._latest_by_sport.get(sport_key)
        if not events:
            return None

        game = self.espn.find_matchup(
            parsed["league"], parsed["subject"], parsed["opponent"],
            dates=parsed["date_yyyymmdd"])
        if game is None or game.status != "pre":
            return None
        home_name = game.home_name or game.home
        away_name = game.away_name or game.away
        if not home_name or not away_name:
            return None

        from autonomy.odds_providers import _match_event

        event = _match_event(events, home_name, away_name)
        if not event:
            return None
        event_id = str(event.get("id"))
        # Read side names from the ARCHIVE event so they match the outcome keys.
        odds_home = str(event.get("home_team") or "")
        odds_away = str(event.get("away_team") or "")
        subject_home = game.home.upper() == parsed["subject"]
        subject_name = odds_home if subject_home else odds_away
        opponent_name = odds_away if subject_home else odds_home
        if not subject_name:
            return None

        subject_series = self._subject_series(event_id, subject_name)
        if len(subject_series) < MIN_BOOKS:
            return None

        dispersion = detect_dispersion(subject_series, min_books=MIN_BOOKS)
        if not dispersion.has_read or dispersion.consensus is None:
            return None
        baseline = _clamp(dispersion.consensus)

        steam = detect_steam(
            subject_series, now=self._now,
            window_hours=STEAM_WINDOW_HOURS, min_books=MIN_BOOKS)
        subject_lean = estimate_public_lean(
            league=parsed["league"], devig_prob=baseline,
            is_home=subject_home, team_name=subject_name)
        opponent_lean = estimate_public_lean(
            league=parsed["league"], devig_prob=1.0 - baseline,
            is_home=not subject_home, team_name=opponent_name)
        # Scraped splits (oriented to the game's home side); empty & harmless
        # when the tier is unarmed, in which case the estimated lean stands.
        splits = self.splits.splits_for(home_name, away_name)

        read = synthesize_pressure(
            subject_side=subject_name, opponent_side=opponent_name,
            subject_devig=baseline, subject_lean=subject_lean,
            opponent_lean=opponent_lean, steam=steam, dispersion=dispersion,
            splits=splits, subject_is_home=subject_home)

        # Only speak when there is an actionable nudge -- otherwise this just
        # restates the consensus another source already carries.
        if not read.has_read or read.prob_adjustment == 0.0:
            return None

        probability = _clamp(baseline + read.prob_adjustment)
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=probability,
            uncertainty=max(0.06, 0.13 - 0.05 * read.confidence),
            rationale=(
                f"{parsed['subject']} pressure: {read.rationale} "
                f"(consensus {baseline:.3f} -> {probability:.3f})"
            ),
            features={
                "challenger_only": True,
                "baseline_consensus": baseline,
                "subject_home": subject_home,
                "public_lean_subject": round(subject_lean.lean, 4),
                "public_lean_opponent": round(opponent_lean.lean, 4),
                **read.as_dict(),
                "steam": steam.as_dict(),
                "dispersion": dispersion.as_dict(),
            },
        )
