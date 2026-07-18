"""Market-pressure pipeline (Wave-29+): turn the multi-book line-movement
record into sharp/public intelligence -- steam, dispersion, reverse line
movement, traps, and underdog value.

The foundation (Wave-29) is pure analysis over the Wave-12 odds archive: no
new data, no scraping, no probability influence yet. Later waves add the
public-lean model + reverse-line-movement (Wave-30), scraped betting splits
(Wave-31), and the operator-facing sharp-read report (Wave-32).

See docs/superpowers/specs/2026-07-18-market-pressure-pipeline-design.md.
"""
from __future__ import annotations

from autonomy.market_pressure.dispersion import DispersionRead, detect_dispersion
from autonomy.market_pressure.line_movement import (
    Quote,
    SideSeries,
    movement_series,
    read_archive_window,
)
from autonomy.market_pressure.steam import SteamRead, detect_steam

__all__ = [
    "Quote",
    "SideSeries",
    "movement_series",
    "read_archive_window",
    "SteamRead",
    "detect_steam",
    "DispersionRead",
    "detect_dispersion",
]
