import pytest
from decimal import Decimal


def test_normalizer_rejects_stale_orderbook():
    from kalshi.normalizer import KalshiNormalizer, DataNormalizationError
    from datetime import datetime, timezone, timedelta

    norm = KalshiNormalizer()
    stale_ts = datetime.now(timezone.utc) - timedelta(days=1)
    raw = {
        "ticker": "MKT-YES",
        "bids": [{"price": 45, "size": 10}],
        "asks": [{"price": 55, "size": 10}],
        "timestamp": int(stale_ts.timestamp() * 1000),
    }
    with pytest.raises(DataNormalizationError):
        norm.normalize_orderbook("MKT-YES", raw)


def test_normalizer_report_exists():
    from scripts.generate_v5_reports import generate_normalization_report_v2
    import asyncio
    report = asyncio.run(generate_normalization_report_v2())
    assert report["verdict"] in ("PASS", "SKIP")
