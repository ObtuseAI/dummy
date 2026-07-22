from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from autonomy.target_policy import is_prediction_quarantined_target
from calibration.schema import ForecastRecordV2, SettlementRecord


def _aware_timestamp(value: datetime) -> float | None:
    """UTC-comparable timestamp, or None when provenance is ambiguous."""
    try:
        if value.tzinfo is None or value.utcoffset() is None:
            return None
        return value.timestamp()
    except (OSError, OverflowError, ValueError):
        return None


class ProbabilityRecalibrator:
    """Persisted additive bias correction learned only from settled forecasts."""

    def __init__(self, path: Path, min_samples: int = 20):
        self.path = path
        self.min_samples = min_samples
        self.corrections: dict[str, Decimal] = {}
        self.sample_counts: dict[str, int] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self.corrections = {
                str(key): Decimal(str(value))
                for key, value in (payload.get("corrections") or {}).items()
            }
            self.sample_counts = {
                str(key): int(value)
                for key, value in (payload.get("sample_counts") or {}).items()
            }
        except Exception:
            self.corrections = {}
            self.sample_counts = {}

    def fit(
        self,
        forecasts: Iterable[ForecastRecordV2],
        settlements: Iterable[SettlementRecord],
    ) -> bool:
        # Resolve one trustworthy settlement per contract. Consistent repeats
        # use the earliest settlement timestamp; malformed or conflicting
        # repeats quarantine the contract instead of allowing order-dependent
        # labels.
        settled: dict[str, tuple[str, int, float]] = {}
        quarantined_settlements: set[str] = set()
        for record in settlements:
            contract = str(record.contract_ticker).strip()
            if not contract or contract in quarantined_settlements:
                continue
            stamp = _aware_timestamp(record.settled_at)
            try:
                outcome = int(record.outcome)
            except (TypeError, ValueError):
                outcome = -1
            market = str(record.market_ticker).strip()
            if stamp is None or outcome not in (0, 1) or not market:
                quarantined_settlements.add(contract)
                settled.pop(contract, None)
                continue
            held = settled.get(contract)
            if held is not None and (held[0] != market or held[1] != outcome):
                quarantined_settlements.add(contract)
                settled.pop(contract, None)
                continue
            if held is None or stamp < held[2]:
                settled[contract] = (market, outcome, stamp)

        # Repeated cycle emissions cannot manufacture sample size. Keep only
        # the latest valid pre-settlement final forecast for each contract.
        canonical: dict[
            str,
            tuple[tuple[float, str], tuple[str, str, str, str], ForecastRecordV2, int],
        ] = {}
        quarantined_forecasts: set[str] = set()
        for forecast in forecasts:
            contract = str(forecast.contract_ticker).strip()
            if is_prediction_quarantined_target(
                contract,
                category=forecast.category,
            ) or is_prediction_quarantined_target(
                str(forecast.market_ticker),
                category=forecast.category,
            ):
                # Historical equity/data-only rows remain auditable in storage
                # but cannot alter category or global corrections used by
                # sports/crypto forecasts.
                continue
            settlement = settled.get(contract)
            if (
                not contract
                or settlement is None
                or contract in quarantined_forecasts
                or str(forecast.market_ticker).strip() != settlement[0]
            ):
                continue
            stamp = _aware_timestamp(forecast.timestamp)
            probability = forecast.final_probability
            if (
                stamp is None
                or stamp > settlement[2]
                or not probability.is_finite()
                or not Decimal("0") <= probability <= Decimal("1")
            ):
                continue
            category = str(forecast.category or "").strip().lower()
            rank = (stamp, str(forecast.forecast_id))
            signature = (
                str(forecast.market_ticker).strip(),
                str(probability),
                category,
                str(forecast.model_route),
            )
            held = canonical.get(contract)
            if held is not None and stamp == held[0][0] and signature != held[1]:
                quarantined_forecasts.add(contract)
                canonical.pop(contract, None)
                continue
            if held is None or rank > held[0]:
                canonical[contract] = (rank, signature, forecast, settlement[1])

        errors: dict[str, list[Decimal]] = defaultdict(list)
        for _rank, _signature, forecast, outcome in canonical.values():
            error = Decimal(outcome) - forecast.final_probability
            errors["global"].append(error)
            category = str(forecast.category or "").strip().lower()
            if category:
                errors[f"category:{category}"].append(error)

        corrections: dict[str, Decimal] = {}
        sample_counts: dict[str, int] = {}
        for key, values in errors.items():
            sample_counts[key] = len(values)
            if len(values) < self.min_samples:
                continue
            correction = sum(values, Decimal("0")) / Decimal(len(values))
            corrections[key] = max(Decimal("-0.15"), min(Decimal("0.15"), correction)).quantize(
                Decimal("0.0001")
            )

        self.corrections = corrections
        self.sample_counts = sample_counts
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "method": "additive_settled_bias",
            "sample_unit": "unique_contract",
            "forecast_policy": "latest_valid_pre_settlement",
            "min_samples": self.min_samples,
            "corrections": {key: str(value) for key, value in corrections.items()},
            "sample_counts": sample_counts,
            "quarantined_settlements": len(quarantined_settlements),
            "quarantined_forecasts": len(quarantined_forecasts),
            "status": "fitted" if corrections else "insufficient_data",
        }
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return bool(corrections)

    def apply(self, probability: Decimal, category: str | None = None) -> Decimal:
        normalized = str(category or "").strip().lower()
        category_key = f"category:{normalized}" if normalized else None
        correction = self.corrections.get(
            category_key or "", self.corrections.get("global", Decimal("0"))
        )
        return max(Decimal("0"), min(Decimal("1"), probability + correction)).quantize(
            Decimal("0.0001")
        )
