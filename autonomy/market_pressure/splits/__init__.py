"""Scraped betting-splits tier (Wave-32).

Public ticket% vs money%/handle% is the piece the line-only pipeline cannot
see: it turns the inferred public-lean into a MEASURED one and unlocks the
two classic sheep/sharp reads -- money moving opposite the tickets (sharp
side), and a heavy public side the line refuses to confirm (the flat-line
trap). The data is scraped from several public aggregators and fused with
per-source reliability weighting (operator-directed 2026-07-18: "all of them
into an intelligently weighted" read), under a responsible-scraping contract
(cache-first, rate-limited, backoff, fail-open fetch / fail-closed opinion,
archived). Inert unless DUMMY_SPLITS_ENABLED=1.
"""
from __future__ import annotations

from autonomy.market_pressure.splits.model import (
    FusedSplits,
    SplitsRead,
    combine_splits,
)

__all__ = ["SplitsRead", "FusedSplits", "combine_splits"]
