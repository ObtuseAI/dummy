import pytest
from adapters.qlib_adapter import QlibAdapter
from adapters.base import DumbyAdapter


def test_adapter_base_abstract():
    with pytest.raises(TypeError):
        DumbyAdapter()


def test_qlib_adapter_emits_native_forecast():
    a = QlibAdapter()
    from core.ontology import OrderBook, OrderBookLevel
    from datetime import datetime, timezone
    book = OrderBook(market_ticker="M", contract_ticker="M-YES", bids=[OrderBookLevel(price=48, size=10)], asks=[OrderBookLevel(price=52, size=10)], timestamp=datetime.now(timezone.utc))
    f = a.to_native_forecast({"market": "M", "contract": "M-YES", "event": "E", "title": "Yes", "book": book})
    assert f.market_ticker == "M"


def test_all_adapter_files_exist():
    from pathlib import Path
    expected = [
        "kalshi_official_reference_adapter.py", "kalshi_python_sdk_adapter.py",
        "pykalshi_reference_adapter.py", "kalshi_live_firewall_adapter.py",
        "polymarket_reference_adapter.py", "cross_market_reference_adapter.py",
        "prediction_market_analysis_adapter.py", "predictos_reference_adapter.py",
        "homerun_reference_adapter.py", "qlib_adapter.py", "rd_agent_reference_adapter.py",
        "finrl_reference_adapter.py", "finrl_meta_reference_adapter.py",
        "finrl_trading_reference_adapter.py", "lean_reference_adapter.py",
        "nautilus_reference_adapter.py", "vectorbt_reference_adapter.py",
        "backtrader_reference_adapter.py", "backtesting_py_reference_adapter.py",
        "freqtrade_reference_adapter.py", "hummingbot_reference_adapter.py",
        "openbb_adapter.py", "darts_adapter.py", "autogluon_adapter.py",
        "optuna_adapter.py", "statsmodels_adapter.py", "xgboost_adapter.py",
        "lightgbm_adapter.py", "catboost_adapter.py", "nixtla_statsforecast_adapter.py",
        "yfinance_reference_adapter.py",
    ]
    root = Path("C:/src/engine/dumby/adapters")
    for name in expected:
        assert (root / name).exists(), f"Missing adapter: {name}"
