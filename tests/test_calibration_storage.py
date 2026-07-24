import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from calibration.schema import ForecastRecordV2, SettlementRecord
from calibration.storage import CalibrationStorage


def _v1_opinion(**kwargs):
    class Opinion:
        pass

    op = Opinion()
    op.market_ticker = kwargs.get("market_ticker", "MKT")
    op.contract_ticker = kwargs.get("contract_ticker", "MKT-YES")
    op.dummy_probability = Decimal(kwargs.get("dummy_probability", "0.55"))
    op.confidence_score = Decimal(kwargs.get("confidence_score", "0.7"))
    op.uncertainty_band = (
        Decimal(kwargs.get("low", "0.45")),
        Decimal(kwargs.get("high", "0.65")),
    )
    op.timestamp = kwargs.get("timestamp", datetime.now(timezone.utc))
    op.proof_reference = kwargs.get("proof_reference", "p1")
    return op


def _v2_record(**kwargs):
    return ForecastRecordV2(
        forecast_id=kwargs.get("forecast_id", "fc_1"),
        market_ticker=kwargs.get("market_ticker", "MKT"),
        contract_ticker=kwargs.get("contract_ticker", "MKT-YES"),
        model_route=kwargs.get("model_route", "MOCK_ONLY"),
        market_implied_probability=Decimal(
            kwargs.get("market_implied_probability", "0.5")
        ),
        dummy_probability=Decimal(kwargs.get("dummy_probability", "0.55")),
        deepseekv4flash_probability=(
            Decimal(kwargs["deepseekv4flash_probability"])
            if "deepseekv4flash_probability" in kwargs
            else None
        ),
        minimaxm3_probability=(
            Decimal(kwargs["minimaxm3_probability"])
            if "minimaxm3_probability" in kwargs
            else None
        ),
        final_probability=Decimal(kwargs.get("final_probability", "0.55")),
        confidence_bucket=kwargs.get("confidence_bucket", "medium"),
        timestamp=kwargs.get("timestamp", datetime.now(timezone.utc)),
        settlement_status=kwargs.get("settlement_status", "open"),
        realized_outcome=kwargs.get("realized_outcome"),
        no_trade_reason=kwargs.get("no_trade_reason"),
    )


def test_storage_appends_and_loads_v1_forecasts(tmp_path):
    storage = CalibrationStorage(data_dir=tmp_path)
    opinion = _v1_opinion()
    storage.append_forecast(opinion)
    loaded = storage.load_forecasts("MKT-YES")
    assert len(loaded) == 1
    assert loaded[0].dummy_probability == Decimal("0.55")
    assert loaded[0].proof_reference == "p1"


def test_storage_appends_and_loads_v2_forecasts(tmp_path):
    storage = CalibrationStorage(data_dir=tmp_path)
    record = _v2_record(
        forecast_id="fc_v2_1",
        dummy_probability="0.60",
        deepseekv4flash_probability="0.62",
        minimaxm3_probability="0.58",
        final_probability="0.60",
        confidence_bucket="medium",
    )
    storage.append_forecast_v2(record)
    loaded = storage.load_forecasts_v2("MKT-YES")
    assert len(loaded) == 1
    assert loaded[0].forecast_id == "fc_v2_1"
    assert loaded[0].deepseekv4flash_probability == Decimal("0.62")


def test_storage_v2_accepts_dict(tmp_path):
    storage = CalibrationStorage(data_dir=tmp_path)
    record = {
        "forecast_id": "fc_dict_1",
        "market_ticker": "MKT",
        "contract_ticker": "MKT-YES",
        "model_route": "MOCK_ONLY",
        "market_implied_probability": "0.5",
        "dummy_probability": "0.55",
        "final_probability": "0.55",
        "confidence_bucket": "medium",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    storage.append_forecast_v2(record)
    loaded = storage.load_forecasts_v2("MKT-YES")
    assert len(loaded) == 1
    assert loaded[0].forecast_id == "fc_dict_1"


def test_storage_appends_settlement(tmp_path):
    storage = CalibrationStorage(data_dir=tmp_path)
    settlement = SettlementRecord(
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        outcome=1,
        settled_at=datetime.now(timezone.utc),
        source="test",
    )
    storage.append_settlement(settlement)
    path = tmp_path / "settlements.jsonl"
    assert path.exists()
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["outcome"] == 1


def test_settlement_retry_is_idempotent_across_storage_instances(tmp_path):
    first = CalibrationStorage(data_dir=tmp_path)
    second = CalibrationStorage(data_dir=tmp_path)
    settlement = SettlementRecord(
        market_ticker="mkt",
        contract_ticker="mkt-yes",
        outcome=1,
        settled_at=datetime.now(timezone.utc),
        source="read-only-truth",
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda storage: storage.append_settlement(settlement),
                (first, second),
            )
        )

    assert sorted(results) == [False, True]
    assert len((tmp_path / "settlements.jsonl").read_text().splitlines()) == 1
    assert len(first.load_settlements()) == 1


def test_conflicting_settlement_retry_fails_closed_without_append(tmp_path):
    storage = CalibrationStorage(data_dir=tmp_path)
    base = {
        "market_ticker": "MKT",
        "contract_ticker": "MKT-YES",
        "settled_at": datetime.now(timezone.utc),
        "source": "read-only-truth",
    }
    assert storage.append_settlement({**base, "outcome": 1}) is True

    with pytest.raises(ValueError, match="conflicting settlement outcome"):
        storage.append_settlement({**base, "outcome": 0})

    assert len((tmp_path / "settlements.jsonl").read_text().splitlines()) == 1
    assert storage.load_settlements()[0].outcome == 1


def test_malformed_settlement_ledger_blocks_retry_instead_of_healing(tmp_path):
    (tmp_path / "settlements.jsonl").write_text("not-json\n", encoding="utf-8")
    storage = CalibrationStorage(data_dir=tmp_path)

    with pytest.raises(ValueError, match="invalid settlements ledger row 1"):
        storage.append_settlement(
            {
                "market_ticker": "MKT",
                "contract_ticker": "MKT-YES",
                "outcome": 1,
                "settled_at": datetime.now(timezone.utc),
                "source": "read-only-truth",
            }
        )

    assert (tmp_path / "settlements.jsonl").read_text(encoding="utf-8") == (
        "not-json\n"
    )


def test_storage_v1_and_v2_files_are_separate(tmp_path):
    storage = CalibrationStorage(data_dir=tmp_path)
    storage.append_forecast(_v1_opinion())
    storage.append_forecast_v2(_v2_record())
    assert len(storage.load_forecasts("MKT-YES")) == 1
    assert len(storage.load_forecasts_v2("MKT-YES")) == 1


def test_storage_generates_report(tmp_path):
    storage = CalibrationStorage(data_dir=tmp_path)
    storage.append_forecast(_v1_opinion(proof_reference="p_v1"))
    storage.append_forecast_v2(_v2_record(forecast_id="fc_report_1"))
    storage.append_settlement(
        SettlementRecord(
            market_ticker="MKT",
            contract_ticker="MKT-YES",
            outcome=1,
            settled_at=datetime.now(timezone.utc),
            source="test",
        )
    )

    # Was Path("artifacts/dummy"): a relative path resolved against the repo
    # root, so this test wrote into the REAL governance evidence tree.
    artifact_dir = tmp_path / "artifacts" / "dummy"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    report_path = artifact_dir / "calibration_storage_report_v1.json"
    report = {
        "report_type": "calibration_storage_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_dir": str(tmp_path),
        "v1_forecasts_loaded": len(storage.load_forecasts("MKT-YES")),
        "v2_forecasts_loaded": len(storage.load_forecasts_v2("MKT-YES")),
        "v2_sample": storage.load_forecasts_v2("MKT-YES")[0].model_dump(mode="json"),
        "supports_v1": True,
        "supports_v2": True,
    }
    report_path.write_text(json.dumps(report, indent=2))
    assert report_path.exists()
