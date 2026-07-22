from __future__ import annotations
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
from threading import Lock, RLock
import tempfile
import time
from typing import Any
from calibration.schema import ForecastRecord, ForecastRecordV2, SettlementRecord

DATA_DIR = Path("data/calibration")
ARTIFACT_DIR = Path("artifacts/dummy/calibration")
_SETTLEMENT_LOCKS_GUARD = Lock()
_SETTLEMENT_LOCKS: dict[Path, RLock] = {}
_FILE_LOCK_TIMEOUT_SECONDS = 10.0


def _settlement_lock(path: Path) -> RLock:
    """Return a process-wide lock shared by storage instances for one ledger."""
    resolved = path.resolve()
    with _SETTLEMENT_LOCKS_GUARD:
        return _SETTLEMENT_LOCKS.setdefault(resolved, RLock())


@contextmanager
def _settlement_file_lock(path: Path):
    """Serialize settlement reads/appends across independent processes.

    The in-process ``RLock`` is insufficient when the dashboard, mesh, and
    reconciler run separately. A one-byte advisory lock keeps the legacy JSONL
    ledger idempotent without replacing it or fabricating a recovery row.
    """
    lock_digest = hashlib.sha256(
        str(path.resolve()).casefold().encode("utf-8")
    ).hexdigest()
    lock_path = Path(tempfile.gettempdir()) / (
        f"dummy-calibration-settlements-{lock_digest}.lock"
    )
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    acquired = False
    deadline = time.monotonic() + _FILE_LOCK_TIMEOUT_SECONDS
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        while not acquired:
            handle.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"timed out locking settlement ledger {path}"
                    ) from exc
                time.sleep(0.01)
        yield
    finally:
        if acquired:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


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

    def append_settlement(
        self,
        settlement: SettlementRecord | dict[str, Any],
    ) -> bool:
        """Append one unique settlement truth row.

        Reconciliation retries with the same market/contract/outcome are a
        no-op. A different outcome for an already-settled contract is a hard
        conflict and is never appended.
        """
        if isinstance(settlement, dict):
            settlement = SettlementRecord.model_validate(settlement)
        path = self._path("settlements")
        with _settlement_lock(path):
            with _settlement_file_lock(path):
                existing = self._deduplicate_settlements(
                    self._load_valid_records(
                        "settlements",
                        SettlementRecord,
                        strict=True,
                    )
                )
                key = self._settlement_key(settlement)
                if not all(key):
                    raise ValueError(
                        "settlement market_ticker and contract_ticker are required"
                    )
                for prior in existing:
                    if self._settlement_key(prior) != key:
                        continue
                    if prior.outcome == settlement.outcome:
                        return False
                    raise ValueError(
                        "conflicting settlement outcome for "
                        f"{settlement.market_ticker}/{settlement.contract_ticker}: "
                        f"existing={prior.outcome}, incoming={settlement.outcome}"
                    )
                with path.open("a", encoding="utf-8") as f:
                    f.write(settlement.model_dump_json() + "\n")
                    f.flush()
                    os.fsync(f.fileno())
        return True

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
        return [
            record
            for record in self.load_all_forecasts_v2()
            if record.contract_ticker == contract_ticker
        ]

    def load_all_forecasts_v2(self) -> list[ForecastRecordV2]:
        """Load every valid V2 forecast without inventing replacement rows."""
        return self._load_valid_records("forecasts_v2", ForecastRecordV2)

    def load_settlements(self) -> list[SettlementRecord]:
        """Load unique settlement truths; reject a corrupt/conflicting ledger."""
        path = self._path("settlements")
        with _settlement_lock(path):
            with _settlement_file_lock(path):
                return self._deduplicate_settlements(
                    self._load_valid_records(
                        "settlements",
                        SettlementRecord,
                        strict=True,
                    )
                )

    @staticmethod
    def _settlement_key(record: SettlementRecord) -> tuple[str, str]:
        return (
            record.market_ticker.strip().upper(),
            record.contract_ticker.strip().upper(),
        )

    @classmethod
    def _deduplicate_settlements(
        cls,
        records: list[SettlementRecord],
    ) -> list[SettlementRecord]:
        unique: dict[tuple[str, str], SettlementRecord] = {}
        for record in records:
            key = cls._settlement_key(record)
            if not all(key):
                raise ValueError(
                    "settlement ledger contains an empty market or contract ticker"
                )
            prior = unique.get(key)
            if prior is None:
                unique[key] = record
                continue
            if prior.outcome != record.outcome:
                raise ValueError(
                    "conflicting settlement outcomes in ledger for "
                    f"{record.market_ticker}/{record.contract_ticker}: "
                    f"{prior.outcome} != {record.outcome}"
                )
        return list(unique.values())

    def _load_valid_records(
        self,
        name: str,
        model: Any,
        *,
        strict: bool = False,
    ) -> list[Any]:
        path = self._path(name)
        if not path.exists():
            return []
        records: list[Any] = []
        with path.open(encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(model.model_validate(json.loads(line)))
                except (json.JSONDecodeError, ValueError) as exc:
                    if strict:
                        raise ValueError(
                            f"invalid {name} ledger row {line_number}: {exc}"
                        ) from exc
                    # A malformed historical row is not evidence and must not
                    # be replaced with a fabricated record.
                    continue
        return records
