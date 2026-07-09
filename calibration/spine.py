from __future__ import annotations
from decimal import Decimal
from math import log
from statistics import mean, pstdev
from typing import Any
from calibration.schema import (
    CalibrationMetrics,
    CalibrationMetricsV2,
    ForecastRecord,
    ForecastRecordV2,
    SettlementRecord,
)


class CalibrationSpine:
    """Scoring backbone for V1 and V2 calibration records.

    V2 supports multi-model probabilities, market-implied deltas, model
    disagreement, confidence-bucket accuracy, and abstention/no-trade tracking.
    It does not claim profitability or SOTA performance.
    """

    def score(self, forecasts: list[ForecastRecord], settlement: SettlementRecord) -> CalibrationMetrics:
        """V1 single-model scoring (preserved)."""
        if not forecasts:
            return CalibrationMetrics(market_ticker=settlement.market_ticker, contract_ticker=settlement.contract_ticker, sample_count=0)
        p = float(forecasts[-1].dummy_probability)
        y = settlement.outcome
        brier = (p - y) ** 2
        logloss = -(y * log(max(p, 1e-9)) + (1 - y) * log(max(1 - p, 1e-9)))
        low, high = forecasts[-1].uncertainty_band
        coverage = 1 if Decimal(str(low)) <= Decimal(str(y)) <= Decimal(str(high)) else 0
        return CalibrationMetrics(
            market_ticker=settlement.market_ticker,
            contract_ticker=settlement.contract_ticker,
            brier_score=round(brier, 6),
            log_loss=round(logloss, 6),
            calibration_error=round(abs(p - y), 6),
            coverage=float(coverage),
            sample_count=len(forecasts),
        )

    @staticmethod
    def _safe_log_loss(p: float, y: int) -> float:
        p = max(min(p, 1 - 1e-9), 1e-9)
        return -(y * log(p) + (1 - y) * log(1 - p))

    @staticmethod
    def _brier(p: float, y: int) -> float:
        return (p - y) ** 2

    @staticmethod
    def _bucket(p: float) -> str:
        if p >= 0.7:
            return "high"
        if p >= 0.4:
            return "medium"
        return "low"

    def _expected_calibration_error(
        self,
        records: list[ForecastRecordV2],
        outcome: int,
    ) -> float | None:
        """Simple 10-bin ECE using final_probability as the calibration axis."""
        if not records:
            return None
        bins: dict[int, list[tuple[float, int]]] = {i: [] for i in range(10)}
        for rec in records:
            p = float(rec.final_probability)
            idx = min(int(p * 10), 9)
            bins[idx].append((p, outcome))
        errors = []
        for entries in bins.values():
            if not entries:
                continue
            avg_p = mean(p for p, _ in entries)
            avg_y = mean(y for _, y in entries)
            errors.append(abs(avg_p - avg_y) * len(entries))
        total = sum(len(v) for v in bins.values())
        if total == 0:
            return None
        return round(sum(errors) / total, 6)

    def _confidence_bucket_accuracy(
        self,
        records: list[ForecastRecordV2],
        outcome: int,
    ) -> dict[str, float]:
        """Directional accuracy per confidence bucket.

        A forecast is counted as correct when its direction (>= 0.5 or < 0.5)
        matches the realized outcome.
        """
        buckets: dict[str, list[int]] = {"high": [], "medium": [], "low": []}
        for rec in records:
            bucket = self._bucket(float(rec.final_probability))
            p = float(rec.final_probability)
            correct = 1 if ((p >= 0.5 and outcome == 1) or (p < 0.5 and outcome == 0)) else 0
            buckets[bucket].append(correct)
        return {bucket: round(mean(vals), 6) if vals else 0.0 for bucket, vals in buckets.items()}

    def score_v2(
        self,
        forecasts: list[ForecastRecordV2],
        settlement: SettlementRecord,
    ) -> CalibrationMetricsV2:
        """V2 multi-model scoring for a settled contract.

        All metrics are descriptive and averaged over the supplied forecast
        sequence. No profitability or SOTA claim is made.
        """
        if not forecasts:
            return CalibrationMetricsV2(
                market_ticker=settlement.market_ticker,
                contract_ticker=settlement.contract_ticker,
                sample_count=0,
                settled_count=0,
            )

        y = settlement.outcome
        briers: list[float] = []
        log_losses: list[float] = []
        market_deltas: list[float] = []
        disagreement_scores: list[float] = []
        abstention_count = 0
        no_trade_reasons: dict[str, int] = {}

        for rec in forecasts:
            p = float(rec.final_probability)
            briers.append(self._brier(p, y))
            log_losses.append(self._safe_log_loss(p, y))
            market_deltas.append(abs(p - float(rec.market_implied_probability)))

            model_probs = [float(x) for x in rec.model_probabilities()]
            if len(model_probs) >= 2:
                disagreement_scores.append(round(pstdev(model_probs), 6))
            else:
                disagreement_scores.append(0.0)

            if rec.no_trade_reason is not None:
                abstention_count += 1
                reason = rec.no_trade_reason or "unspecified"
                no_trade_reasons[reason] = no_trade_reasons.get(reason, 0) + 1

        sample_count = len(forecasts)
        return CalibrationMetricsV2(
            market_ticker=settlement.market_ticker,
            contract_ticker=settlement.contract_ticker,
            brier_score=round(mean(briers), 6) if briers else None,
            log_loss=round(mean(log_losses), 6) if log_losses else None,
            expected_calibration_error=self._expected_calibration_error(forecasts, y),
            market_implied_delta=round(mean(market_deltas), 6) if market_deltas else None,
            model_disagreement_score=round(mean(disagreement_scores), 6) if disagreement_scores else None,
            confidence_bucket_accuracy=self._confidence_bucket_accuracy(forecasts, y),
            abstention_count=abstention_count,
            abstention_rate=round(abstention_count / sample_count, 6) if sample_count else 0.0,
            no_trade_reasons=no_trade_reasons,
            sample_count=sample_count,
            settled_count=sum(1 for rec in forecasts if rec.settlement_status == "settled"),
        )
