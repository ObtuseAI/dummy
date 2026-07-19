"""Wave-44: splitting diagnostics out of the recal must not change the weights.

The 6-hourly recal runs run_backtest(bootstrap_weights=True,
include_diagnostics=False) for a fast weight refresh; the DummyBacktestReport
task runs it with diagnostics for the dashboard/summary. These pin that the
diagnostics flag leaves the source scoring and derived weights byte-identical
(diagnostics are observability, not weight inputs) and only gates the expensive
sub-reports.
"""
from __future__ import annotations

from autonomy.backtest import run_backtest
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Signal

_DIAGNOSTIC_KEYS = (
    "signal_data_quality", "realized_trade_statistics", "execution_tournament",
    "crypto_challenger_gates", "decision_policy", "execution_adverse_selection",
)


def _sig(source, ticker, p):
    return Signal(source=source, market_ticker=ticker, probability_yes=p,
                  uncertainty=0.1, rationale="")


def _seed(led):
    for ticker, result in [("A", True), ("B", True), ("C", False)]:
        led.record_signal(_sig("market_prior", ticker, 0.5))
        led.record_signal(_sig("sharp", ticker, 0.9 if result else 0.1))
        led.record_settlement(ticker, result)


def test_diagnostics_flag_preserves_weights(tmp_path):
    a = AutonomyLedger(db_path=tmp_path / "a.db")
    _seed(a)
    full = run_backtest(a, include_diagnostics=True)
    a.close()

    b = AutonomyLedger(db_path=tmp_path / "b.db")
    _seed(b)
    light = run_backtest(b, include_diagnostics=False)
    b.close()

    # Core (weights + scoring) byte-identical
    assert full["sources"] == light["sources"]
    assert full["derived_weights"] == light["derived_weights"]
    assert full["sources_by_scope"] == light["sources_by_scope"]
    assert full["settled_markets"] == light["settled_markets"]

    # Diagnostics present in full, absent in light
    assert full.get("diagnostics_included") is True
    assert light.get("diagnostics_included") is False
    for key in _DIAGNOSTIC_KEYS:
        assert key in full
        assert key not in light


def test_light_recal_still_bootstraps_weights(tmp_path):
    led = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        _seed(led)
        run_backtest(led, bootstrap_weights=True, include_diagnostics=False)
        # weights persisted despite skipping diagnostics
        assert led.get_weight("sharp") > 0
    finally:
        led.close()
