from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from calibration.storage import CalibrationStorage
from core.ontology import Contract, Market, OrderBook, OrderBookLevel
from forecasting.model_probability_authority import model_probability_scope
from forecasting.real_market_loop import (
    MODEL_MODE_LIVE_HYBRID,
    MODEL_MODE_MOCK_ONLY,
    RealMarketForecastLoopV2,
)


def _scope(*, ticker: str, hours: float, live_phase: bool = False) -> str:
    decision_at = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
    return model_probability_scope(
        ticker=ticker,
        title="Will Bitcoin finish above the strike?",
        category="Crypto",
        decision_at=decision_at,
        expiration=decision_at + timedelta(hours=hours),
        live_phase=live_phase,
    )


def test_crypto_model_authority_uses_four_non_pooled_horizons():
    ticker = "KXBTCD-26JUL2317-T100000"

    hourly = _scope(ticker=ticker, hours=4)
    daily = _scope(ticker=ticker, hours=24)
    weekly = _scope(ticker=ticker, hours=168)
    fifteen_minute = _scope(ticker="KXBTC15M-26JUL221215-15", hours=8)

    assert hourly.endswith("|1h")
    assert daily.endswith("|1d")
    assert weekly.endswith("|1w")
    assert fifteen_minute.endswith("|15m")
    assert len({hourly, daily, weekly, fifteen_minute}) == 4


def test_crypto_daily_scope_cannot_equal_weekly_scope_for_same_contract_family():
    ticker = "KXBTCD-26JUL2317-T100000"

    daily = _scope(ticker=ticker, hours=119.99)
    weekly = _scope(ticker=ticker, hours=120)

    assert daily.rsplit("|", 1)[0] == weekly.rsplit("|", 1)[0]
    assert daily.endswith("|1d")
    assert weekly.endswith("|1w")
    assert daily != weekly


def test_sports_model_authority_scope_splits_pre_live_and_unknown():
    decision_at = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
    kwargs = {
        "ticker": "KXMLBGAME-26JUL22NYYBOS-NYY-YES",
        "title": "Will the Yankees beat the Red Sox? Yes",
        "category": "Sports",
        "decision_at": decision_at,
        "expiration": decision_at + timedelta(hours=4),
    }

    pre = model_probability_scope(**kwargs, live_phase=False)
    live = model_probability_scope(**kwargs, live_phase=True)
    unknown = model_probability_scope(**kwargs, live_phase=None)

    assert pre.endswith("|pre")
    assert live.endswith("|live")
    assert unknown.endswith("|unknown")
    assert pre.rsplit("|", 1)[0] == live.rsplit("|", 1)[0]
    assert pre.rsplit("|", 1)[0] == unknown.rsplit("|", 1)[0]
    assert len({pre, live, unknown}) == 3


def test_live_loop_passes_explicit_sports_phase_into_authority_scope(tmp_path):
    now = datetime.now(timezone.utc)
    contract = Contract(
        ticker="KXMLBGAME-26JUL22NYYBOS-NYY-YES",
        title="Yes",
        status="in_play",
        expiration=now + timedelta(hours=2),
    )
    market = Market(
        ticker="KXMLBGAME-26JUL22NYYBOS-NYY",
        title="Will the Yankees beat the Red Sox?",
        status="in_play",
        category="Sports",
        event_ticker="KXMLBGAME-26JUL22NYYBOS",
        contracts=[contract],
    )
    orderbook = OrderBook(
        market_ticker=market.ticker,
        contract_ticker=contract.ticker,
        bids=[OrderBookLevel(price=49, size=100)],
        asks=[OrderBookLevel(price=51, size=100)],
        timestamp=now,
    )
    loop = RealMarketForecastLoopV2(
        hybrid_engine=SimpleNamespace(),
        storage=CalibrationStorage(data_dir=tmp_path / "calibration"),
        artifact_dir=tmp_path / "artifacts",
        model_authority_path=tmp_path / "missing-authority.json",
        model_authority_approved_roots=[tmp_path],
    )
    loop.model_mode = MODEL_MODE_MOCK_ONLY

    scores = loop._score_market(market, contract, orderbook)
    assert scores is not None
    assert scores["live_phase"] is True
    base = loop._build_base_forecast(market, contract, orderbook, scores)
    decision = loop._model_probability_authority_for(base, scores)

    assert decision.scope.endswith("|live")
    assert decision.weight == 0
    assert decision.blockers == ("model_mode_not_live_hybrid",)


def test_raw_live_flag_requires_explicit_boolean(tmp_path):
    market = Market(
        ticker="KXMLBGAME-26JUL22NYYBOS-NYY",
        title="Will the Yankees beat the Red Sox?",
        status="active",
        category="Sports",
        event_ticker="KXMLBGAME-26JUL22NYYBOS",
    )
    loop = RealMarketForecastLoopV2(
        hybrid_engine=SimpleNamespace(),
        storage=CalibrationStorage(data_dir=tmp_path / "calibration"),
        artifact_dir=tmp_path / "artifacts",
    )

    assert loop._is_live_phase(market, {"is_live": True}) is True
    assert loop._is_live_phase(market, {"is_live": False}) is False
    assert loop._is_live_phase(market, {"phase": "pregame"}) is False
    assert loop._is_live_phase(market, {"is_live": "true"}) is None
    assert loop._is_live_phase(market, {"phase": "delayed"}) is None
    assert (
        loop._is_live_phase(
            market,
            {"is_live": True, "phase": "pregame"},
        )
        is None
    )


def test_ambiguous_sports_phase_has_no_model_probability_authority(tmp_path):
    now = datetime.now(timezone.utc)
    contract = Contract(
        ticker="KXMLBGAME-26JUL22NYYBOS-NYY-YES",
        title="Yes",
        status="active",
        expiration=now + timedelta(hours=2),
    )
    market = Market(
        ticker="KXMLBGAME-26JUL22NYYBOS-NYY",
        title="Will the Yankees beat the Red Sox?",
        status="active",
        category="Sports",
        event_ticker="KXMLBGAME-26JUL22NYYBOS",
        contracts=[contract],
    )
    orderbook = OrderBook(
        market_ticker=market.ticker,
        contract_ticker=contract.ticker,
        bids=[OrderBookLevel(price=49, size=100)],
        asks=[OrderBookLevel(price=51, size=100)],
        timestamp=now,
    )
    loop = RealMarketForecastLoopV2(
        hybrid_engine=SimpleNamespace(),
        storage=CalibrationStorage(data_dir=tmp_path / "calibration"),
        artifact_dir=tmp_path / "artifacts",
    )
    loop.model_mode = MODEL_MODE_LIVE_HYBRID

    scores = loop._score_market(market, contract, orderbook)
    assert scores is not None
    assert scores["live_phase"] is None
    assert scores["market_phase"] == "unknown"
    base = loop._build_base_forecast(market, contract, orderbook, scores)
    decision = loop._model_probability_authority_for(base, scores)

    assert decision.scope.endswith("|unknown")
    assert decision.authorized is False
    assert decision.weight == 0
    assert decision.blockers == ("sports_phase_unknown_or_ambiguous",)


def test_contract_only_live_phase_is_recognized_and_conflicts_fail_closed(tmp_path):
    market = Market(
        ticker="KXMLBGAME-26JUL22NYYBOS-NYY",
        title="Will the Yankees beat the Red Sox?",
        status="active",
        category="Sports",
        event_ticker="KXMLBGAME-26JUL22NYYBOS",
    )
    live_contract = Contract(
        ticker="KXMLBGAME-26JUL22NYYBOS-NYY-YES",
        title="Yes",
        status="in_play",
    )
    loop = RealMarketForecastLoopV2(
        hybrid_engine=SimpleNamespace(),
        storage=CalibrationStorage(data_dir=tmp_path / "calibration"),
        artifact_dir=tmp_path / "artifacts",
    )

    assert loop._is_live_phase(market, contract=live_contract) is True
    assert (
        loop._is_live_phase(
            market,
            {"phase": "pregame"},
            live_contract,
        )
        is None
    )
