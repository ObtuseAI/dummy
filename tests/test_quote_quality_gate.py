"""Wave-5 P0: honest-quote gate, honest-benchmark grading, trust-key hygiene."""
from __future__ import annotations

import sqlite3

import pytest

from autonomy.auto_promotion_runner import _valid_trust_key
from autonomy.backtest import SourceScoreTracker, _brier
from autonomy.learner import Learner
from autonomy.ontology import MarketView, Vertical
from autonomy.quote_quality import (
    CONTESTED_DISAGREEMENT,
    honest_implied_yes,
    suspect_crypto_contested_pair,
)
from autonomy.signals.market_prior import MarketPriorSignal


def _market(bid, ask, ticker="KXBTC-26JUL17-B64000", vertical=Vertical.CRYPTO, volume=500):
    return MarketView(
        ticker=ticker, title="t", vertical=vertical, status="open",
        close_time="2026-07-18T00:00:00+00:00", yes_bid=bid, yes_ask=ask,
        no_bid=(100 - ask) if ask is not None else None,
        no_ask=(100 - bid) if bid is not None else None,
        volume=volume, liquidity=1000, raw={},
    )


# ---- honest_implied_yes -------------------------------------------------------

def test_honest_implied_real_quotes():
    assert honest_implied_yes(45, 55) == pytest.approx(0.50)
    assert honest_implied_yes(2, 10) == pytest.approx(0.06)
    assert honest_implied_yes(90, 99) == pytest.approx(0.945)


def test_honest_implied_rejects_fabrication():
    assert honest_implied_yes(None, 55) is None
    assert honest_implied_yes(45, None) is None
    assert honest_implied_yes(0, 99) is None          # no YES commitment
    assert honest_implied_yes(1, 100) is None         # no NO commitment
    assert honest_implied_yes(1, 99) is None          # 98c-wide phantom "50"
    assert honest_implied_yes(30, 55) is None         # spread 25 > 20
    assert honest_implied_yes(60, 40) is None         # crossed
    assert honest_implied_yes(40, 60) == pytest.approx(0.50)  # exactly at bound


# ---- MarketPriorSignal abstains on junk books --------------------------------

def test_market_prior_emits_on_real_book():
    signal = MarketPriorSignal().generate(_market(45, 55))
    assert signal is not None and signal.probability_yes == pytest.approx(0.50)


def test_market_prior_abstains_on_dead_book():
    dead = _market(1, 99)
    assert MarketPriorSignal().applicable(dead) is False
    assert MarketPriorSignal().generate(dead) is None


# ---- forecaster: no fabricated implied / edge --------------------------------

def test_forecaster_implied_gated():
    from autonomy.forecaster import EnsembleForecaster
    from autonomy.ontology import Signal

    class _Ledger:
        def get_weight(self, source, default=1.0):
            return 1.0

    forecaster = EnsembleForecaster(_Ledger())
    sig = Signal(source="crypto_spot_vol", market_ticker="KXBTC-X", probability_yes=0.95,
                 uncertainty=0.1, rationale="", features={})
    dead = _market(1, 99)
    out = forecaster.fuse(dead, [sig])
    assert out is not None
    assert out.market_implied_yes is None      # no phantom 50c mid
    assert out.edge_yes == 0.0                 # no claimed edge vs nothing
    live = _market(44, 48)
    out2 = forecaster.fuse(live, [sig])
    assert out2.market_implied_yes == pytest.approx(0.46)


# ---- learner: honest benchmark + contested-only ------------------------------

class _FakeLedger:
    def __init__(self, signals):
        self._signals = signals
        self.weights: dict[str, float] = {}

    def calibration_signals_for_market(self, ticker):
        return self._signals

    def signals_for_market(self, ticker):
        return self._signals

    def get_weight(self, source, default=1.0):
        return self.weights.get(source, default)

    def update_weight(self, source, weight, brier=None):
        self.weights[source] = weight


def test_learner_no_market_prior_no_trust_movement():
    ledger = _FakeLedger([
        {"source": "crypto_spot_vol", "probability_yes": 0.99, "features": {}},
    ])
    updated = Learner(ledger).apply_settlement("KXBTC-26JUL17-B64000", True)
    assert updated == {} and ledger.weights == {}


def test_learner_uncontested_rows_do_not_move_weights():
    ledger = _FakeLedger([
        {"source": "market_prior", "probability_yes": 0.50, "features": {}},
        {"source": "crypto_spot_vol", "probability_yes": 0.52, "features": {}},  # gap < 0.05
    ])
    updated = Learner(ledger).apply_settlement("KXBTC-26JUL17-B64000", True)
    assert updated == {}


def test_learner_contested_win_moves_weights_up():
    ledger = _FakeLedger([
        {"source": "market_prior", "probability_yes": 0.40, "features": {}},
        {"source": "crypto_spot_vol", "probability_yes": 0.90, "features": {}},
    ])
    updated = Learner(ledger).apply_settlement("KXBTC-26JUL17-B64000", True)
    assert updated["crypto_spot_vol"] > 1.0
    assert "market_prior" not in updated  # self-comparison never moves


# ---- historical quarantine ----------------------------------------------------

def test_suspect_pair_matches_fabrication_signature():
    assert suspect_crypto_contested_pair(0.99, 0.42, "KXBTC-26JUL17-B64000") is True
    assert suspect_crypto_contested_pair(0.01, 0.50, "KXSOL15M-26JUL162130-30") is True
    # honest patterns survive
    assert suspect_crypto_contested_pair(0.60, 0.42, "KXBTC-26JUL17-B64000") is False   # gap < 0.30
    assert suspect_crypto_contested_pair(0.99, 0.20, "KXBTC-26JUL17-B64000") is False   # prior outside band
    # sports never quarantined (books are real)
    assert suspect_crypto_contested_pair(0.99, 0.45, "KXMLBGAME-26JUL17NYYBOS-NYY") is False


def test_tracker_quarantines_suspect_contested_rows():
    tracker = SourceScoreTracker("crypto_spot_vol")
    market_p = 0.45
    tracker.observe(0.99, 1, _brier(market_p, 1), market_p=market_p,
                    cluster_key="c1", ticker="KXBTC-26JUL17-B64000")
    assert tracker.n == 1                 # accuracy still counted
    assert tracker.contested_n == 0       # phantom edge NOT minted
    tracker.observe(0.99, 1, _brier(market_p, 1), market_p=market_p,
                    cluster_key="c2", ticker="KXMLBGAME-26JUL17NYYBOS-NYY")
    assert tracker.contested_n == 1       # real sports book still graded


# ---- trust-key hygiene --------------------------------------------------------

def test_valid_trust_key_shapes():
    assert _valid_trust_key("crypto_spot_vol") is True
    assert _valid_trust_key("crypto_spot_vol@CRYPTO") is True
    assert _valid_trust_key("scope:crypto_spot_vol|btc|ladder|hourly") is True
    assert _valid_trust_key("scope:crypto_spot_vol|ladder|hourly") is False   # legacy 3-part
    assert _valid_trust_key("scope:crypto_structure_swing|ladder|unknown") is False


def test_saturation_rail_ignores_orphaned_legacy_keys():
    from autonomy.auto_promotion_runner import WEIGHT_SATURATION_EPS, _valid_trust_key
    from autonomy.learner import WEIGHT_CEILING

    weights = {"scope:crypto_spot_vol|ladder|hourly": 8.0, "crypto_spot_vol": 3.2}
    saturated = any(
        float(w) >= WEIGHT_CEILING - WEIGHT_SATURATION_EPS
        for k, w in weights.items() if _valid_trust_key(k)
    )
    assert saturated is False
    weights["crypto_spot_vol"] = 8.0
    saturated = any(
        float(w) >= WEIGHT_CEILING - WEIGHT_SATURATION_EPS
        for k, w in weights.items() if _valid_trust_key(k)
    )
    assert saturated is True


def test_migration_script_removes_only_legacy_rows(tmp_path):
    from scripts.migrate_trust_keys import find_legacy_rows

    db = tmp_path / "ledger.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE source_trust (source TEXT PRIMARY KEY, weight REAL,"
        " brier_sum REAL, brier_count INTEGER, updated_at TEXT)"
    )
    conn.executemany(
        "INSERT INTO source_trust VALUES (?,?,?,?,?)",
        [
            ("crypto_spot_vol", 3.2, 1.0, 10, "t"),
            ("crypto_spot_vol@CRYPTO", 3.1, 1.0, 10, "t"),
            ("scope:crypto_spot_vol|btc|ladder|hourly", 2.0, 1.0, 10, "t"),
            ("scope:crypto_spot_vol|ladder|hourly", 8.0, 1.0, 2028, "t"),
        ],
    )
    conn.commit()
    legacy = find_legacy_rows(conn)
    assert [row["source"] for row in legacy] == ["scope:crypto_spot_vol|ladder|hourly"]


def test_contested_threshold_shared():
    from autonomy.backtest import CONTESTED_DISAGREEMENT as backtest_threshold

    assert CONTESTED_DISAGREEMENT == backtest_threshold == 0.05
