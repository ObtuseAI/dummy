"""Formula One multi-competitor rating and race-winner challenger."""
from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

MODEL_VERSION = "f1-field-rating-v1"
BASE_RATING = 1500.0
UPDATE_K = 26.0


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value))
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()


@dataclass(frozen=True)
class F1Entry:
    driver: str
    position: int
    winner: bool


@dataclass(frozen=True)
class F1Race:
    race_id: str
    name: str
    date: str
    status: str
    entries: tuple[F1Entry, ...]


def parse_f1_scoreboard(payload: dict[str, Any]) -> list[F1Race]:
    races: list[F1Race] = []
    for event in payload.get("events") or []:
        race = next((
            competition for competition in event.get("competitions") or []
            if str((competition.get("type") or {}).get("abbreviation") or "").lower() == "race"
        ), None)
        if race is None:
            continue
        state = str(((race.get("status") or {}).get("type") or {}).get("state") or "pre")
        entries: list[F1Entry] = []
        for index, competitor in enumerate(race.get("competitors") or [], start=1):
            driver = str((competitor.get("athlete") or {}).get("displayName") or "").strip()
            if not driver:
                continue
            try:
                position = int(competitor.get("order") or index)
            except (TypeError, ValueError):
                position = index
            entries.append(F1Entry(driver, position, competitor.get("winner") is True))
        if not entries and state == "post":
            continue
        races.append(F1Race(
            race_id=str(race.get("id") or event.get("id") or ""),
            name=str(event.get("name") or ""),
            date=str(race.get("date") or event.get("date") or ""),
            status=state,
            entries=tuple(entries),
        ))
    return races


def default_fetch_f1_scoreboard(year: int) -> dict[str, Any]:
    import httpx

    response = httpx.get(
        "https://site.api.espn.com/apis/site/v2/sports/racing/f1/scoreboard",
        params={"dates": str(year)},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


class F1EspnClient:
    def __init__(
        self, fetch_scoreboard: Callable[[int], dict[str, Any]] | None = None,
    ) -> None:
        self.fetch_scoreboard = fetch_scoreboard or default_fetch_f1_scoreboard
        self._cache: dict[int, list[F1Race]] = {}

    def clear_cache(self) -> None:
        self._cache.clear()

    def races(self, year: int) -> list[F1Race]:
        if year not in self._cache:
            try:
                self._cache[year] = parse_f1_scoreboard(self.fetch_scoreboard(year))
            except Exception:
                self._cache[year] = []
        return self._cache[year]

    def find_race(self, year: int, market_title: str) -> F1Race | None:
        title_tokens = set(normalize_text(market_title).split()) - {
            "will", "finish", "first", "in", "the", "main", "race", "at", "grand", "prix",
            str(year),
        }
        candidates: list[tuple[int, F1Race]] = []
        for race in self.races(year):
            race_tokens = set(normalize_text(race.name).split()) - {
                "grand", "prix", str(year), "airways", "formula", "1",
            }
            overlap = len(title_tokens & race_tokens)
            if overlap:
                candidates.append((overlap, race))
        pre = [item for item in candidates if item[1].status == "pre"]
        ranked = sorted(pre or candidates, key=lambda item: item[0], reverse=True)
        return ranked[0][1] if ranked else None


@dataclass
class DriverState:
    rating: float = BASE_RATING
    races: int = 0
    wins: int = 0
    finish_percentile_ewma: float = 0.5


@dataclass(frozen=True)
class F1Prediction:
    probabilities: dict[str, float]
    uncertainty: float
    field_size: int
    minimum_driver_races: int
    model_version: str = MODEL_VERSION


@dataclass
class F1Model:
    drivers: dict[str, DriverState] = field(default_factory=dict)
    processed_race_ids: set[str] = field(default_factory=set)
    races_seen: int = 0

    def _driver(self, name: str) -> DriverState:
        return self.drivers.setdefault(normalize_text(name), DriverState())

    def update(self, race: F1Race) -> bool:
        if race.race_id in self.processed_race_ids or race.status != "post":
            return False
        field = sorted(race.entries, key=lambda entry: entry.position)
        if len(field) < 5:
            return False
        expected_scores = {
            entry.driver: math.exp((self._driver(entry.driver).rating - BASE_RATING) / 180.0)
            for entry in field
        }
        expected_total = sum(expected_scores.values())
        actual_scores = {
            entry.driver: math.exp(-0.22 * (entry.position - 1)) for entry in field
        }
        actual_total = sum(actual_scores.values())
        size = len(field)
        for entry in field:
            state = self._driver(entry.driver)
            expected = expected_scores[entry.driver] / expected_total
            actual = actual_scores[entry.driver] / actual_total
            state.rating += UPDATE_K * size * (actual - expected)
            percentile = (entry.position - 1) / max(1, size - 1)
            state.finish_percentile_ewma = (
                0.20 * percentile + 0.80 * state.finish_percentile_ewma
            )
            state.races += 1
            state.wins += int(entry.winner or entry.position == 1)
        self.processed_race_ids.add(race.race_id)
        self.races_seen += 1
        return True

    def predict(self, race: F1Race) -> F1Prediction:
        scores: dict[str, float] = {}
        samples: list[int] = []
        field = [entry.driver for entry in race.entries] or [
            name for name, state in self.drivers.items() if state.races > 0
        ]
        for driver in field:
            state = self._driver(driver)
            samples.append(state.races)
            form = 0.5 - state.finish_percentile_ewma
            scores[driver] = math.exp(
                (state.rating - BASE_RATING) / 165.0 + 0.65 * form
            )
        total = sum(scores.values())
        probabilities = {
            normalize_text(driver): value / total for driver, value in scores.items()
        }
        sample = min(samples) if samples else 0
        uncertainty = min(0.46, 0.12 + 0.24 / math.sqrt(1.0 + sample / 3.0))
        return F1Prediction(probabilities, uncertainty, len(scores), sample)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_version": MODEL_VERSION,
            "drivers": {key: asdict(value) for key, value in self.drivers.items()},
            "processed_race_ids": sorted(self.processed_race_ids),
            "races_seen": self.races_seen,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "F1Model":
        return cls(
            drivers={key: DriverState(**value) for key, value in data.get("drivers", {}).items()},
            processed_race_ids=set(data.get("processed_race_ids", [])),
            races_seen=int(data.get("races_seen", 0)),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(path)

    @classmethod
    def load(cls, path: Path) -> "F1Model":
        if path.exists():
            try:
                return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                pass
        return cls()
