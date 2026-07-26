from pathlib import Path

import pytest

from adapters.base import DummyAdapter

ROOT = Path(__file__).resolve().parents[1]


def test_adapter_base_abstract():
    with pytest.raises(TypeError):
        DummyAdapter()


def test_fabricated_reference_wrappers_are_retired():
    """Named-library wrappers that only called Dummy's baseline must stay gone."""

    retired = {
        "autogluon_adapter.py",
        "catboost_adapter.py",
        "darts_adapter.py",
        "lightgbm_adapter.py",
        "qlib_adapter.py",
        "statsmodels_adapter.py",
        "xgboost_adapter.py",
        "yfinance_reference_adapter.py",
        "kalshi_official_reference_adapter.py",
        "kalshi_python_sdk_adapter.py",
        "kalshi_live_firewall_adapter.py",
        "pykalshi_reference_adapter.py",
    }
    adapters = ROOT / "adapters"
    assert all(not (adapters / name).exists() for name in retired)


def test_adapter_package_contains_only_current_contracts():
    adapters = ROOT / "adapters"
    assert {path.name for path in adapters.iterdir() if not path.name.startswith("__pycache__")} == {
        "__init__.py",
        "base.py",
        "promoted",
    }
