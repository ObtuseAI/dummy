"""Crypto 1h lane paper-capital quarantine (Wave-1 C1).

Settled paper evidence: the crypto 1h exploratory lane is a net loser
(-338c, Brier skill vs market -0.055) and the 1h incumbent worse
(-558c, Brier skill -0.481), while 15m_direction carries the edge. The two
losing lanes stop allocating paper bankroll but keep emitting observations so
grading evidence continues to accrue and they can earn their way back.
"""
from __future__ import annotations

from autonomy.crypto_paper_twin import (
    PAPER_LANE_QUARANTINE,
    lane_quarantined,
)
from autonomy.ontology import Vertical


def test_crypto_1h_exploratory_and_incumbent_are_quarantined():
    assert lane_quarantined(Vertical.CRYPTO, "exploratory", "1h") is True
    assert lane_quarantined(Vertical.CRYPTO, "incumbent", "1h") is True


def test_other_crypto_1h_lanes_still_trade():
    # The recursive challenger and the hourly-calibrated lane were not the
    # documented losers; they keep their paper allocation.
    assert lane_quarantined(Vertical.CRYPTO, "recursive", "1h") is False
    assert lane_quarantined(Vertical.CRYPTO, "hourly_calibrated", "1h") is False


def test_untouched_timeframes_still_trade():
    for timeframe in ("15m", "1d", "1w"):
        for strategy in ("exploratory", "incumbent", "recursive"):
            assert lane_quarantined(Vertical.CRYPTO, strategy, timeframe) is False


def test_commodities_lanes_unaffected():
    for timeframe in ("1d", "1w"):
        for strategy in ("exploratory", "incumbent", "recursive"):
            assert lane_quarantined(Vertical.COMMODITIES, strategy, timeframe) is False


def test_quarantine_set_is_exactly_the_two_documented_losers():
    assert PAPER_LANE_QUARANTINE == {
        ("CRYPTO", "exploratory", "1h"),
        ("CRYPTO", "incumbent", "1h"),
    }


def test_string_vertical_matches_enum_vertical():
    assert lane_quarantined("CRYPTO", "incumbent", "1h") is True
    assert lane_quarantined("CRYPTO", "incumbent", "1d") is False


def test_cycle_quarantined_lanes_observe_but_never_spend_paper_capital(tmp_path):
    """Integration: a full twin cycle keeps grading the 1h losers (observations
    continue) while writing zero trades for them; other lanes still trade."""
    import json

    from tests.test_autonomy_crypto_paper_twin import _twin

    twin = _twin(tmp_path)
    try:
        report = twin.run_cycle()
        assert report["status"] == "CYCLE_OK"
        conn = twin.ledger.connection

        # No paper capital: zero trades in the quarantined lanes.
        assert conn.execute(
            "SELECT COUNT(*) FROM trades WHERE vertical='CRYPTO' AND "
            "timeframe='1h' AND strategy IN ('exploratory','incumbent')"
        ).fetchone()[0] == 0
        # The quarantine actually intercepted eligible candidates this cycle.
        assert report["lane_trades_quarantined"] > 0
        assert report["paper_lane_quarantine"] == [
            "CRYPTO:exploratory:1h",
            "CRYPTO:incumbent:1h",
        ]

        # Grading continues: the quarantined lanes still emit observations,
        # flagged so research can see the abstention was policy, not absence.
        rows = conn.execute(
            "SELECT diagnostics_json FROM observations WHERE vertical='CRYPTO' "
            "AND timeframe='1h' AND strategy IN ('exploratory','incumbent')"
        ).fetchall()
        assert len(rows) > 0
        assert all(
            json.loads(row[0]).get("lane_quarantined") is True for row in rows
        )

        # Untouched lanes still allocate paper capital.
        assert conn.execute(
            "SELECT COUNT(*) FROM trades WHERE NOT (vertical='CRYPTO' AND "
            "timeframe='1h' AND strategy IN ('exploratory','incumbent'))"
        ).fetchone()[0] > 0
        # And their observations are not flagged.
        other = conn.execute(
            "SELECT diagnostics_json FROM observations WHERE timeframe='15m' LIMIT 5"
        ).fetchall()
        assert other
        assert all(
            json.loads(row[0]).get("lane_quarantined") is False for row in other
        )
    finally:
        twin.close()
