from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from calibration.schema import ForecastRecord, ForecastRecordV2, SettlementRecord

DATA_DIR = Path("data/calibration")
ARTIFACT_DIR = Path("artifacts/dummy/calibration")


class CalibrationStorage:
    """Persist V1 and V2 calibration records to line-delimited JSON files."""

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        return self.data_dir / f"{name}.jsonl"

    def append_forecast(self, opinion: Any):
        """V1 forecast append (preserved)."""
        record = ForecastRecord(
            market_ticker=opinion.market_ticker,
            contract_ticker=opinion.contract_ticker,
            dummy_probability=opinion.dummy_probability,
            confidence_score=opinion.confidence_score,
            uncertainty_band=opinion.uncertainty_band,
            timestamp=opinion.timestamp,
            proof_reference=opinion.proof_reference,
        )
        with self._path("forecasts").open("a") as f:
            f.write(record.model_dump_json() + "\n")

    def append_forecast_v2(self, record: ForecastRecordV2 | dict[str, Any]):
        """V2 forecast append with multi-model probabilities."""
        if isinstance(record, dict):
            record = ForecastRecordV2.model_validate(record)
        with self._path("forecasts_v2").open("a") as f:
            f.write(record.model_dump_json() + "\n")

    def append_settlement(self, settlement: SettlementRecord):
        with self._path("settlements").open("a") as f:
            f.write(settlement.model_dump_json() + "\n")

    def load_forecasts(self, contract_ticker: str) -> list[ForecastRecord]:
        path = self._path("forecasts")
        if not path.exists():
            return []
        records = []
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                if data.get("contract_ticker") == contract_ticker:
                    records.append(ForecastRecord.model_validate(data))
        return records

    def load_forecasts_v2(self, contract_ticker: str) -> list[ForecastRecordV2]:
        path = self._path("forecasts_v2")
        if not path.exists():
            return []
        records = []
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                if data.get("contract_ticker") == contract_ticker:
                    records.append(ForecastRecordV2.model_validate(data))
        return records
