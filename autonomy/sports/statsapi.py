"""Official MLB StatsAPI adapter (statsapi.mlb.com; no key). Read-only.

Produces a point-in-time MlbGameContext with confirmed lineups, platoon
splits, bullpen fatigue, park factors, pitcher rate stats, and wind/temp.
Every field is nullable and its presence is tracked, so downstream model
heads degrade gracefully and the validation harness can attribute misses to
missing inputs. Nothing here forecasts, trades, or touches credentials.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any, Literal

SnapshotKind = Literal["projected", "confirmed"]


@dataclass(frozen=True)
class LineupSlot:
    batting_order: int
    player_id: int
    name: str | None = None
    bats: str | None = None  # "L" | "R" | "S"


@dataclass(frozen=True)
class PitcherRates:
    player_id: int
    name: str | None = None
    throws: str | None = None  # "L" | "R"
    era: float | None = None
    k_pct: float | None = None
    bb_pct: float | None = None
    hr9: float | None = None


@dataclass(frozen=True)
class MlbGameContext:
    game_pk: int
    snapshot: SnapshotKind
    captured_at: str  # ISO-8601 UTC receipt time (provenance)
    home: str
    away: str
    venue: str | None = None
    home_probable_pitcher_id: int | None = None
    away_probable_pitcher_id: int | None = None
    home_pitcher: PitcherRates | None = None
    away_pitcher: PitcherRates | None = None
    home_lineup: tuple[LineupSlot, ...] = ()
    away_lineup: tuple[LineupSlot, ...] = ()
    home_bullpen_fatigue: dict[int, float] = field(default_factory=dict)
    away_bullpen_fatigue: dict[int, float] = field(default_factory=dict)
    park_run_factor: float | None = None
    park_hr_factor: float | None = None
    wind_speed_mph: float | None = None
    wind_direction: str | None = None
    temperature_f: float | None = None

    def field_provenance(self) -> dict[str, bool]:
        """Presence map: True when a field carries real data, False when absent."""
        present: dict[str, bool] = {}
        for f in fields(self):
            if f.name in {"game_pk", "snapshot", "captured_at", "home", "away"}:
                continue
            value = getattr(self, f.name)
            present[f.name] = bool(value) if value is not None else False
        return present
