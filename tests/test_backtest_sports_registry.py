"""Backtest sports cohorts stay aligned with the canonical series registry."""

from __future__ import annotations

from autonomy.backtest import _sports_dimensions
from autonomy.sports_markets import SERIES_SPEC


def _row(ticker: str) -> dict[str, object]:
    return {
        "ticker": ticker,
        "market": 0.50,
        "sources_used": {"market_prior": 0.50},
    }


def test_sports_dimensions_classify_every_registered_series() -> None:
    """Every canonical series must retain its registry league and market type."""
    assert SERIES_SPEC
    for series, spec in SERIES_SPEC.items():
        dimensions = _sports_dimensions(_row(f"{series}-26JUL26-EVENT-CONTRACT"))
        assert dimensions is not None, series
        assert dimensions["league"] == spec.league, series
        assert dimensions["market_type"] == spec.market_type, series


def test_sports_dimensions_fail_closed_for_unknown_series() -> None:
    assert _sports_dimensions(_row("KXUNREGISTEREDSPREAD-26JUL26-EVENT-TEAM3")) is None
