"""Wave-23: the paper twin's self-tightening per-lane entry bars."""
from __future__ import annotations

import sqlite3

from autonomy.crypto_paper_twin import (
    ADAPTIVE_BAR_CAP_CENTS,
    ADAPTIVE_BAR_MIN_SETTLED,
    adaptive_entry_bars,
)

_SCHEMA = """
CREATE TABLE trades(
    trade_id TEXT PRIMARY KEY,
    strategy TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    settled_at TEXT,
    taker_pnl_cents INTEGER
);
"""


def _conn(rows):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.executemany(
        "INSERT INTO trades(trade_id, strategy, timeframe, settled_at, taker_pnl_cents)"
        " VALUES (?,?,?,?,?)",
        rows,
    )
    return conn


def _rows(timeframe, strategy, pnls, start=0):
    return [
        (f"{timeframe}-{strategy}-{start + i}", strategy, timeframe,
         f"2026-07-{(i % 28) + 1:02d}T12:00:00+00:00", pnl)
        for i, pnl in enumerate(pnls)
    ]


def test_bleeding_lane_raises_its_bar_and_healthy_lane_does_not():
    rows = (
        _rows("1h", "exploratory", [-2] * 60)        # bleeding: -2c/trade
        + _rows("15m", "exploratory", [5] * 60)      # healthy: +5c/trade
    )
    bars = adaptive_entry_bars(_conn(rows))
    assert bars == {("1h", "exploratory"): 2.0}


def test_small_samples_and_unsettled_rows_are_exempt():
    rows = (
        _rows("1d", "incumbent", [-10] * (ADAPTIVE_BAR_MIN_SETTLED - 1))
        + [("open-1", "incumbent", "1w", None, None)]
    )
    bars = adaptive_entry_bars(_conn(rows))
    assert bars == {}


def test_bar_is_capped_and_windowed():
    # Catastrophic older losses beyond the window must not dominate: the
    # most recent 100 settle at -1c, the ancient -50c rows fall outside.
    old = _rows("1h", "incumbent", [-50] * 40)
    recent = [
        (f"r{i}", "incumbent", "1h", f"2026-07-29T12:00:{i % 60:02d}+00:00", -1)
        for i in range(100)
    ]
    bars = adaptive_entry_bars(_conn(old + recent))
    assert bars[("1h", "incumbent")] == 1.0

    crash = _rows("15m", "recursive", [-40] * 60)
    bars2 = adaptive_entry_bars(_conn(crash))
    assert bars2[("15m", "recursive")] == ADAPTIVE_BAR_CAP_CENTS


def test_candidate_blocks_on_adjusted_bar():
    from autonomy.crypto_paper_twin import DEFAULT_GENOME, _candidate
    from autonomy.ontology import Forecast, MarketView, Vertical

    market = MarketView(
        ticker="KXBTC15M-26JUL1817-T118000.01", title="BTC?",
        vertical=Vertical.CRYPTO, status="open",
        close_time="2026-07-18T17:15:00+00:00",
        yes_bid=44, yes_ask=46, no_bid=54, no_ask=56,
        volume=10, liquidity=10,
        raw={"floor_strike": 118000.01, "strike_type": "greater"},
    )
    forecast = Forecast(
        market_ticker=market.ticker, probability_yes=0.55, uncertainty=0.10,
        sources_used={"crypto_spot_vol": 1.0}, market_implied_yes=0.46,
        edge_yes=0.09, rationale="test")
    genome = DEFAULT_GENOME

    open_bar = _candidate(
        market, forecast, None, strategy="exploratory", timeframe="15m",
        genome=genome, entry_bar_adjustment=0.0)
    tightened = _candidate(
        market, forecast, None, strategy="exploratory", timeframe="15m",
        genome=genome, entry_bar_adjustment=5.0)
    assert tightened["policy"]["min_ev_cents"] == open_bar["policy"]["min_ev_cents"] + 5.0
    assert tightened["policy"]["entry_bar_adjustment_cents"] == 5.0
    # If the tightened bar now exceeds this candidate's EV, it must block.
    ev = float(open_bar["best"]["ev_cents"]) if "best" in open_bar else None
    if ev is not None and ev < tightened["policy"]["min_ev_cents"]:
        assert not tightened.get("eligible", True) or tightened.get("blockers")
