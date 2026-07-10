from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from autonomy.allocator import Allocator
from autonomy.forecaster import EnsembleForecaster
from autonomy.ontology import (
    Decision,
    DecisionAction,
    Forecast,
    MarketView,
    OutcomeKind,
    Signal,
    TradeOutcome,
    Vertical,
)
from autonomy.risk_brain import RiskBrain
from autonomy.signals.crypto_indicators import (
    CryptoDataHub,
    CryptoDvolSignal,
    CryptoEmpiricalRegimeSignal,
    CryptoTechnicalCompositeSignal,
)
from autonomy.signals.crypto_spot import CryptoSpotVolSignal


def _market(**overrides) -> MarketView:
    data = {
        "ticker": "KXBTCD-26JUL1017-T64000",
        "title": "BTC above 64000",
        "vertical": Vertical.CRYPTO,
        "status": "active",
        "close_time": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "yes_bid": 39,
        "yes_ask": 41,
        "no_bid": 59,
        "no_ask": 61,
        "volume": 10_000,
        "liquidity": 10_000,
        "raw": {"strike_type": "greater", "floor_strike": 64_000.0},
    }
    data.update(overrides)
    return MarketView(**data)


def _indicator_state() -> dict:
    hourly = [60_000.0 * (1.0005**index) for index in range(200)]
    minute = [hourly[-1] * (1.00002**index) for index in range(200)]
    return {
        "asset": "BTC",
        "spot": minute[-1],
        "coinbase_spot": minute[-1],
        "kraken_spot": minute[-1] * 1.0001,
        "venue_divergence_bps": 1.0,
        "hourly_closes": hourly,
        "minute_closes": minute,
        "minute_volumes": [100.0] * 185 + [250.0] * 15,
        "book_imbalance": 0.2,
        "microprice_basis_bps": 0.5,
        "dvol": 55.0,
        "dvol_at_ms": 1_700_000_000_000,
    }


class _Ledger:
    def get_weight_scoped(self, source, _vertical, default=1.0):
        return {"market_prior": 3.0}.get(source, 8.0)

    def get_weight(self, source, default=1.0):
        return self.get_weight_scoped(source, "CRYPTO", default)


def test_crypto_signal_uncertainty_is_probability_scale_not_return_sigma():
    signal = CryptoSpotVolSignal(
        fetch_spot_and_vol=lambda _asset: (64_000.0, 0.50),
    ).generate(_market())
    assert signal is not None
    assert signal.uncertainty >= 0.08
    assert signal.features["horizon_log_return_sigma"] < signal.uncertainty


def test_crypto_forecaster_pools_correlated_models_and_anchors_market():
    market = _market()
    prior = Signal("market_prior", market.ticker, 0.80, 0.50, "")
    one_model = Signal("crypto_spot_vol", market.ticker, 0.20, 0.08, "")
    second_model = Signal("crypto_ewma_t", market.ticker, 0.20, 0.08, "")
    forecaster = EnsembleForecaster(_Ledger())
    single = forecaster.fuse(market, [prior, one_model])
    pooled = forecaster.fuse(market, [prior, one_model, second_model])
    assert pooled is not None and single is not None
    assert pooled.sources_used["market_prior"] == 0.25
    assert pooled.sources_used["crypto_spot_vol"] + pooled.sources_used["crypto_ewma_t"] == 0.75
    assert pooled.probability_yes == pytest.approx(single.probability_yes)
    assert pooled.uncertainty == pytest.approx(single.uncertainty)


def test_challenger_only_signal_is_logged_but_excluded_from_fusion():
    market = _market()
    forecast = EnsembleForecaster(_Ledger()).fuse(market, [
        Signal("market_prior", market.ticker, 0.4, 0.02, ""),
        Signal("crypto_spot_vol", market.ticker, 0.6, 0.10, ""),
        Signal("crypto_empirical_regime", market.ticker, 0.99, 0.01, "",
               features={"challenger_only": True}),
    ])
    assert forecast is not None
    assert "crypto_empirical_regime" not in forecast.sources_used
    assert forecast.probability_yes < 0.7


def test_empirical_regime_logs_indicators_and_is_quarantined():
    calls = []

    def fetch(asset):
        calls.append(asset)
        return _indicator_state()

    source = CryptoEmpiricalRegimeSignal(fetch_state=fetch)
    first = source.generate(_market())
    second = source.generate(_market(ticker="KXBTCD-26JUL1017-T64500",
                                     raw={"strike_type": "greater", "floor_strike": 64_500.0}))
    assert first is not None and second is not None
    assert calls == ["BTC"]
    assert first.features["challenger_only"] is True
    assert first.features["return_samples"] >= 12
    assert first.features["rsi_14m"] is not None
    assert first.features["macd_12_26_bps"] is not None
    assert first.uncertainty >= 0.08


def test_dvol_challenger_maps_implied_vol_but_cannot_enter_ensemble():
    signal = CryptoDvolSignal(fetch_state=lambda _asset: _indicator_state()).generate(_market())
    assert signal is not None
    assert signal.features["annual_implied_vol"] == 0.55
    assert signal.features["challenger_only"] is True
    assert signal.uncertainty >= 0.12


def test_technical_composite_turns_indicators_into_bounded_challenger():
    signal = CryptoTechnicalCompositeSignal(
        fetch_state=lambda _asset: _indicator_state(),
    ).generate(_market())
    assert signal is not None
    assert signal.features["challenger_only"] is True
    assert signal.features["technical_model_version"] == 1
    assert signal.features["technical_score"] > 0
    assert signal.features["technical_coverage"] == pytest.approx(1.0)
    assert abs(signal.features["shift_in_horizon_sigma"]) <= 0.45
    assert signal.features["technical_components"]["minute_resolution"] == 1.0
    assert signal.uncertainty >= 0.14


def test_crypto_data_hub_drops_stale_intraday_data_and_sorts_dvol():
    now = 2_000_000_000
    hourly = [
        [now - (200 - index) * 3600, 0, 0, 0, 60_000 + index, 10]
        for index in range(200)
    ]
    stale_minute = [[now - 3600, 0, 0, 0, 60_200, 10]]

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class Client:
        def get(self, url, params=None):
            if url.endswith("/candles"):
                return Response(hourly if params["granularity"] == 3600 else stale_minute)
            if url.endswith("/book"):
                return Response({"bids": [["60198", "2"]], "asks": [["60202", "1"]]})
            if "kraken" in url:
                return Response({"error": [], "result": {"XXBTZUSD": {"c": ["60201"]}}})
            if "deribit" in url:
                return Response({"result": {"data": [
                    [(now - 3600) * 1000, 0, 0, 0, 42.0],
                    [(now - 12 * 3600) * 1000, 0, 0, 0, 99.0],
                ]}})
            raise AssertionError(url)

        def close(self):
            return None

    state = CryptoDataHub(
        client_factory=Client, now_s=lambda: now,
    ).state("BTC")
    assert state["minute_closes"] == []
    assert state["coinbase_minute_at_s"] is None
    assert state["coinbase_hourly_age_s"] == 3600
    assert state["dvol"] == 42.0


def test_risk_brain_refuses_pyramiding_existing_market(tmp_path):
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    state = brain.load_state(10_000)
    budget = brain.order_budget(
        state, "KXBTC-TEST", market_exposure_cents=10, kelly=0.5,
        group_exposure_cents=10, group_open_count=1,
    )
    assert budget.allowed is False
    assert budget.reason == "existing open position in market"


def test_crypto_allocator_requires_higher_ev(tmp_path):
    market = _market()
    forecast = Forecast(
        market_ticker=market.ticker, probability_yes=0.48, uncertainty=0.02,
        sources_used={"market_prior": 0.25, "crypto_spot_vol": 0.75},
        market_implied_yes=0.40, edge_yes=0.08, rationale="fixture",
    )
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    decision = Allocator(brain).decide(market, forecast, brain.load_state(10_000))
    assert decision.action is DecisionAction.ABSTAIN
    assert "threshold 8.0c" in decision.abstain_reason


def test_backtest_surfaces_crypto_fill_selection_gap(tmp_path):
    from autonomy.backtest import run_backtest
    from autonomy.ledger import AutonomyLedger

    ledger = AutonomyLedger(tmp_path / "ledger.db")
    ticker = "KXBTCD-26JUL1017-T64000"
    try:
        for source, probability in (
            ("market_prior", 0.60),
            ("crypto_spot_vol", 0.80),
            ("crypto_ewma_t", 0.78),
        ):
            ledger.record_signal(Signal(
                source, ticker, probability, 0.1, "fixture",
            ))
        forecast = Forecast(
            market_ticker=ticker, probability_yes=0.80, uncertainty=0.08,
            sources_used={"market_prior": 0.25, "crypto_spot_vol": 0.375,
                          "crypto_ewma_t": 0.375},
            market_implied_yes=0.60, edge_yes=0.20, rationale="fixture",
        )
        ledger.record_decision(Decision(
            decision_id="crypto-loss", market_ticker=ticker,
            action=DecisionAction.BUY_YES, side="yes", price_cents=40,
            count=1, ev_cents_per_contract=10, kelly_fraction=0.1,
            notional_cents=40, forecast=forecast, risk_snapshot={},
        ))
        ledger.record_outcome(TradeOutcome(
            decision_id="crypto-loss", market_ticker=ticker,
            kind=OutcomeKind.SHADOW, order_id="shadow", fill_count=0,
            fill_price_cents=None, pnl_cents=None, broker_contacted=False,
        ))
        ledger.record_outcome(TradeOutcome(
            decision_id="crypto-loss", market_ticker=ticker,
            kind=OutcomeKind.FILLED, order_id="shadow", fill_count=1,
            fill_price_cents=40, pnl_cents=None, broker_contacted=False,
        ))
        ledger.record_settlement(ticker, False)
        ledger.record_outcome(TradeOutcome(
            decision_id="crypto-loss", market_ticker=ticker,
            kind=OutcomeKind.SETTLED_LOSS, order_id="shadow", fill_count=1,
            fill_price_cents=40, pnl_cents=-40, broker_contacted=False,
        ))
        diagnostics = run_backtest(ledger)["crypto_diagnostics"]
        assert diagnostics["filled_settled_decisions"] == 1
        assert diagnostics["market_brier"] < diagnostics["ensemble_brier"]
        assert diagnostics["net_pnl_cents"] == -40
        assert diagnostics["guard_counterfactual"]["settled_fills_retained"] == 1
        gates = run_backtest(ledger)["crypto_challenger_gates"]
        assert gates["crypto_empirical_regime"]["auto_promote"] is False
        assert gates["crypto_empirical_regime"]["ready_for_explicit_fusion_review"] is False
        assert gates["crypto_technical_composite"]["auto_promote"] is False
    finally:
        ledger.close()
