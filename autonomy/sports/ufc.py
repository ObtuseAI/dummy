"""UFC opponent-strength and fight-duration challenger.

Public scoreboard finals update fighter Elo, weight-class Elo, and distance
tendencies.  Pregame records provide a bounded cold-start prior.  Duration
markets use a survival curve constrained to the model's go-the-distance
probability instead of treating round thresholds as unrelated binaries.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

MODEL_VERSION = "ufc-elo-survival-v1"
BASE_RATING = 1500.0
ELO_SCALE = 400.0
ELO_K = 28.0
WEIGHT_CLASS_K = 18.0
EWMA_ALPHA = 0.10


def normalize_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value))
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()


def _record(competitor: dict[str, Any]) -> tuple[int, int, int] | None:
    for record in competitor.get("records") or []:
        if record.get("type") != "total" and record.get("name") != "overall":
            continue
        match = re.match(r"^(\d+)-(\d+)-(\d+)", str(record.get("summary") or ""))
        if match:
            return tuple(int(value) for value in match.groups())
    return None


@dataclass(frozen=True)
class UfcFight:
    fight_id: str
    fighter_a: str
    fighter_b: str
    status: str
    winner: str | None
    date: str
    weight_class: str
    scheduled_rounds: int
    fighter_a_record: tuple[int, int, int] | None = None
    fighter_b_record: tuple[int, int, int] | None = None
    finish_round: int | None = None
    finish_seconds: float | None = None
    went_distance: bool | None = None

    @property
    def elapsed_minutes(self) -> float | None:
        if self.finish_round is None or self.finish_seconds is None:
            return None
        return (self.finish_round - 1) * 5.0 + self.finish_seconds / 60.0


def parse_ufc_scoreboard(payload: dict[str, Any]) -> list[UfcFight]:
    fights: list[UfcFight] = []
    for event in payload.get("events") or []:
        for competition in event.get("competitions") or []:
            competitors = competition.get("competitors") or []
            if len(competitors) != 2:
                continue
            names = [
                str((competitor.get("athlete") or {}).get("displayName") or "").strip()
                for competitor in competitors
            ]
            if not all(names):
                continue
            status = competition.get("status") or {}
            state = str((status.get("type") or {}).get("state") or "pre")
            winner = None
            if state == "post":
                for competitor, name in zip(competitors, names):
                    if competitor.get("winner") is True:
                        winner = name
                        break
            try:
                scheduled_rounds = int(
                    ((competition.get("format") or {}).get("regulation") or {}).get("periods") or 3
                )
            except (TypeError, ValueError):
                scheduled_rounds = 3
            detail_text = " ".join(
                str((detail.get("type") or {}).get("text") or "")
                for detail in competition.get("details") or []
            ).lower()
            went_distance = None
            if state == "post":
                went_distance = "decision" in detail_text
            try:
                finish_round = int(status.get("period")) if state == "post" else None
                finish_seconds = float(status.get("clock")) if state == "post" else None
            except (TypeError, ValueError):
                finish_round = None
                finish_seconds = None
            fights.append(UfcFight(
                fight_id=str(competition.get("id") or ""),
                fighter_a=names[0],
                fighter_b=names[1],
                status=state,
                winner=winner,
                date=str(competition.get("date") or competition.get("startDate") or ""),
                weight_class=str((competition.get("type") or {}).get("abbreviation") or "Unknown"),
                scheduled_rounds=max(1, min(5, scheduled_rounds)),
                fighter_a_record=_record(competitors[0]),
                fighter_b_record=_record(competitors[1]),
                finish_round=finish_round,
                finish_seconds=finish_seconds,
                went_distance=went_distance,
            ))
    return fights


def default_fetch_ufc_scoreboard(dates: str | None) -> dict[str, Any]:
    import httpx

    params = {"dates": dates} if dates else {}
    response = httpx.get(
        "https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard",
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _fighter_codes(name: str) -> set[str]:
    tokens = normalize_name(name).split()
    surname_tokens = tokens[1:] if len(tokens) > 1 else tokens
    return {token[:3].upper() for token in surname_tokens if len(token) >= 3}


class UfcEspnClient:
    def __init__(
        self, fetch_scoreboard: Callable[[str | None], dict[str, Any]] | None = None,
    ) -> None:
        self.fetch_scoreboard = fetch_scoreboard or default_fetch_ufc_scoreboard
        self._cache: dict[str | None, list[UfcFight]] = {}

    def clear_cache(self) -> None:
        self._cache.clear()

    def fights(self, dates: str | None = None) -> list[UfcFight]:
        if dates not in self._cache:
            try:
                self._cache[dates] = parse_ufc_scoreboard(self.fetch_scoreboard(dates))
            except Exception:
                self._cache[dates] = []
        return self._cache[dates]

    def find_fight(
        self,
        fighter: str | None,
        fight_code: str | None,
        dates: str | None,
    ) -> UfcFight | None:
        subject = normalize_name(fighter or "")
        code = str(fight_code or "").upper()
        code_a, code_b = (code[:3], code[3:6]) if len(code) >= 6 else ("", "")
        candidates: list[UfcFight] = []
        for fight in self.fights(dates):
            names = (normalize_name(fight.fighter_a), normalize_name(fight.fighter_b))
            if subject and not any(subject == name for name in names):
                continue
            if code_a and code_b:
                first_codes = _fighter_codes(fight.fighter_a)
                second_codes = _fighter_codes(fight.fighter_b)
                if not (
                    (code_a in first_codes and code_b in second_codes)
                    or (code_b in first_codes and code_a in second_codes)
                ):
                    continue
            candidates.append(fight)
        pre = [fight for fight in candidates if fight.status == "pre"]
        return (pre or candidates or [None])[0]


@dataclass
class FighterState:
    rating: float = BASE_RATING
    fights: int = 0
    wins: int = 0
    distance_ewma: float = 0.45
    elapsed_fraction_ewma: float = 0.72
    weight_ratings: dict[str, float] = field(default_factory=dict)
    weight_fights: dict[str, int] = field(default_factory=dict)


@dataclass
class WeightClassState:
    fights: int = 0
    distance_ewma: float = 0.45


@dataclass(frozen=True)
class UfcPrediction:
    fighter_a_win_probability: float
    distance_probability: float
    winner_uncertainty: float
    duration_uncertainty: float
    sample_fights: int
    scheduled_rounds: int
    weight_class: str
    model_version: str = MODEL_VERSION

    def before_round_probability(self, round_number: int) -> float:
        total_minutes = self.scheduled_rounds * 5.0
        cutoff = max(0.0, min(total_minutes, (round_number - 1) * 5.0))
        if cutoff <= 0:
            return 0.005
        survival_to_end = min(0.98, max(0.02, self.distance_probability))
        hazard = -math.log(survival_to_end) / total_minutes
        return min(0.995, max(0.005, 1.0 - math.exp(-hazard * cutoff)))


def _elo_probability(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + math.pow(10.0, (rating_b - rating_a) / ELO_SCALE))


def _record_probability(record: tuple[int, int, int] | None) -> tuple[float, int]:
    if record is None:
        return 0.5, 0
    wins, losses, _draws = record
    bouts = wins + losses
    return (wins + 1.0) / (bouts + 2.0), bouts


@dataclass
class UfcModel:
    fighters: dict[str, FighterState] = field(default_factory=dict)
    weight_classes: dict[str, WeightClassState] = field(default_factory=dict)
    processed_fight_ids: set[str] = field(default_factory=set)
    fights_seen: int = 0

    def _fighter(self, name: str) -> FighterState:
        return self.fighters.setdefault(normalize_name(name), FighterState())

    def update(self, fight: UfcFight) -> bool:
        if (
            fight.fight_id in self.processed_fight_ids
            or fight.status != "post"
            or not fight.winner
            or fight.went_distance is None
        ):
            return False
        first = self._fighter(fight.fighter_a)
        second = self._fighter(fight.fighter_b)
        first_won = normalize_name(fight.winner) == normalize_name(fight.fighter_a)
        expected = _elo_probability(first.rating, second.rating)
        delta = ELO_K * ((1.0 if first_won else 0.0) - expected)
        first.rating += delta
        second.rating -= delta
        first.fights += 1
        second.fights += 1
        first.wins += int(first_won)
        second.wins += int(not first_won)
        weight = fight.weight_class
        first_weight = first.weight_ratings.get(weight, BASE_RATING)
        second_weight = second.weight_ratings.get(weight, BASE_RATING)
        expected_weight = _elo_probability(first_weight, second_weight)
        weight_delta = WEIGHT_CLASS_K * ((1.0 if first_won else 0.0) - expected_weight)
        first.weight_ratings[weight] = first_weight + weight_delta
        second.weight_ratings[weight] = second_weight - weight_delta
        first.weight_fights[weight] = first.weight_fights.get(weight, 0) + 1
        second.weight_fights[weight] = second.weight_fights.get(weight, 0) + 1
        distance_value = float(fight.went_distance)
        first.distance_ewma = EWMA_ALPHA * distance_value + (1.0 - EWMA_ALPHA) * first.distance_ewma
        second.distance_ewma = EWMA_ALPHA * distance_value + (1.0 - EWMA_ALPHA) * second.distance_ewma
        elapsed = fight.elapsed_minutes
        if elapsed is not None:
            elapsed_fraction = min(1.0, elapsed / (fight.scheduled_rounds * 5.0))
            first.elapsed_fraction_ewma = EWMA_ALPHA * elapsed_fraction + (1.0 - EWMA_ALPHA) * first.elapsed_fraction_ewma
            second.elapsed_fraction_ewma = EWMA_ALPHA * elapsed_fraction + (1.0 - EWMA_ALPHA) * second.elapsed_fraction_ewma
        weight_state = self.weight_classes.setdefault(weight, WeightClassState())
        weight_state.distance_ewma = (
            EWMA_ALPHA * distance_value + (1.0 - EWMA_ALPHA) * weight_state.distance_ewma
        )
        weight_state.fights += 1
        self.processed_fight_ids.add(fight.fight_id)
        self.fights_seen += 1
        return True

    def predict(self, fight: UfcFight) -> UfcPrediction:
        first = self._fighter(fight.fighter_a)
        second = self._fighter(fight.fighter_b)
        elo = _elo_probability(first.rating, second.rating)
        surface_sample = min(
            first.weight_fights.get(fight.weight_class, 0),
            second.weight_fights.get(fight.weight_class, 0),
        )
        if surface_sample:
            weight_probability = _elo_probability(
                first.weight_ratings.get(fight.weight_class, BASE_RATING),
                second.weight_ratings.get(fight.weight_class, BASE_RATING),
            )
            weight_share = min(0.35, surface_sample / 20.0)
            elo = (1.0 - weight_share) * elo + weight_share * weight_probability
        first_record, first_bouts = _record_probability(fight.fighter_a_record)
        second_record, second_bouts = _record_probability(fight.fighter_b_record)
        record_probability = first_record / max(1e-6, first_record + second_record)
        record_share = min(0.30, min(first_bouts, second_bouts) / 100.0)
        win_probability = (1.0 - record_share) * elo + record_share * record_probability

        sample = min(first.fights, second.fights)
        fighter_distance = 0.5 * (first.distance_ewma + second.distance_ewma)
        weight_state = self.weight_classes.get(fight.weight_class)
        if weight_state is not None and weight_state.fights:
            weight_share = min(0.35, weight_state.fights / 60.0)
            fighter_distance = (
                (1.0 - weight_share) * fighter_distance
                + weight_share * weight_state.distance_ewma
            )
        # Five-round fights go the distance less often than a naive 3-round
        # carry-over because they expose fighters to ten extra minutes.
        if fight.scheduled_rounds == 5:
            fighter_distance *= 0.72
        distance_probability = min(0.90, max(0.08, fighter_distance))
        cold = 1.0 / math.sqrt(1.0 + sample / 4.0)
        return UfcPrediction(
            fighter_a_win_probability=min(0.98, max(0.02, win_probability)),
            distance_probability=distance_probability,
            winner_uncertainty=min(0.44, 0.10 + 0.24 * cold),
            duration_uncertainty=min(0.45, 0.13 + 0.24 * cold),
            sample_fights=sample,
            scheduled_rounds=fight.scheduled_rounds,
            weight_class=fight.weight_class,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_version": MODEL_VERSION,
            "fighters": {key: asdict(value) for key, value in self.fighters.items()},
            "weight_classes": {key: asdict(value) for key, value in self.weight_classes.items()},
            "processed_fight_ids": sorted(self.processed_fight_ids),
            "fights_seen": self.fights_seen,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UfcModel":
        return cls(
            fighters={key: FighterState(**value) for key, value in data.get("fighters", {}).items()},
            weight_classes={
                key: WeightClassState(**value) for key, value in data.get("weight_classes", {}).items()
            },
            processed_fight_ids=set(data.get("processed_fight_ids", [])),
            fights_seen=int(data.get("fights_seen", 0)),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(path)

    @classmethod
    def load(cls, path: Path) -> "UfcModel":
        if path.exists():
            try:
                return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                pass
        return cls()
