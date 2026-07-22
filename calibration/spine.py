from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from math import log, sqrt
from statistics import mean, pstdev, stdev
from typing import Any, Iterable
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

    def score(
        self, forecasts: list[ForecastRecord], settlement: SettlementRecord
    ) -> CalibrationMetrics:
        """V1 single-model scoring (preserved)."""
        if not forecasts:
            return CalibrationMetrics(
                market_ticker=settlement.market_ticker,
                contract_ticker=settlement.contract_ticker,
                sample_count=0,
            )
        p = float(forecasts[-1].dummy_probability)
        y = settlement.outcome
        brier = (p - y) ** 2
        logloss = -(y * log(max(p, 1e-9)) + (1 - y) * log(max(1 - p, 1e-9)))
        return CalibrationMetrics(
            market_ticker=settlement.market_ticker,
            contract_ticker=settlement.contract_ticker,
            brier_score=round(brier, 6),
            log_loss=round(logloss, 6),
            calibration_error=round(abs(p - y), 6),
            # Interval coverage is not identifiable from one binary outcome;
            # reporting 0/1 here confused accuracy with coverage.
            coverage=None,
            sample_count=1,
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
        if len({record.contract_ticker for record in records}) < 2:
            return None
        bins: dict[int, list[tuple[float, int]]] = {i: [] for i in range(10)}
        for rec in records:
            p = float(rec.final_probability)
            idx = min(int(p * 10), 9)
            realized = (
                rec.realized_outcome if rec.realized_outcome is not None else outcome
            )
            bins[idx].append((p, realized))
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
            correct = (
                1 if ((p >= 0.5 and outcome == 1) or (p < 0.5 and outcome == 0)) else 0
            )
            buckets[bucket].append(correct)
        return {
            bucket: round(mean(vals), 6) if vals else 0.0
            for bucket, vals in buckets.items()
        }

    @staticmethod
    def _contract_key(
        market_ticker: str,
        contract_ticker: str,
    ) -> tuple[str, str]:
        return market_ticker.strip().upper(), contract_ticker.strip().upper()

    @staticmethod
    def _utc_or_none(value: datetime) -> datetime | None:
        """Normalize an aware timestamp; naive times are not point-in-time evidence."""
        try:
            if value.tzinfo is None or value.utcoffset() is None:
                return None
            return value.astimezone(timezone.utc)
        except (OverflowError, ValueError):
            return None

    @staticmethod
    def _slice_name(value: str | None, fallback: str = "unknown") -> str:
        if value is None or not value.strip():
            return fallback
        normalized = "_".join(value.strip().lower().replace("-", " ").split())
        return normalized or fallback

    @classmethod
    def _calibration_horizon(
        cls,
        forecast: ForecastRecordV2,
        forecast_at: datetime,
        settled_at: datetime,
    ) -> str:
        explicit = cls._slice_name(forecast.horizon, fallback="")
        aliases = {
            "15_min": "15m",
            "15_mins": "15m",
            "15_minutes": "15m",
            "1h": "hourly",
            "1_hour": "hourly",
            "hour": "hourly",
            "1d": "daily",
            "1_day": "daily",
            "day": "daily",
            "1w": "weekly",
            "1_week": "weekly",
            "week": "weekly",
        }
        if explicit:
            return aliases.get(explicit, explicit)

        tokens = {
            token
            for token in (
                f"{forecast.market_ticker}_{forecast.contract_ticker}".upper()
                .replace("-", "_")
                .split("_")
            )
            if token
        }
        if tokens & {"15M", "15MIN", "15MINS"}:
            return "15m"
        if tokens & {"1H", "HOURLY"}:
            return "hourly"
        if tokens & {"1D", "DAILY"}:
            return "daily"
        if tokens & {"1W", "WEEKLY"}:
            return "weekly"

        lead_seconds = max(0.0, (settled_at - forecast_at).total_seconds())
        if lead_seconds <= 30 * 60:
            return "15m"
        if lead_seconds <= 3 * 60 * 60:
            return "hourly"
        if lead_seconds <= 36 * 60 * 60:
            return "daily"
        if lead_seconds <= 8 * 24 * 60 * 60:
            return "weekly"
        return "long_term"

    @staticmethod
    def _mean_ci_95(
        values: list[float],
        *,
        lower_bound: float | None = None,
        upper_bound: float | None = None,
    ) -> list[float] | None:
        if len(values) < 2:
            return None
        center = mean(values)
        margin = 1.96 * stdev(values) / sqrt(len(values))
        low = center - margin
        high = center + margin
        if lower_bound is not None:
            low = max(lower_bound, low)
        if upper_bound is not None:
            high = min(upper_bound, high)
        return [round(low, 6), round(high, 6)]

    def _summarize_calibration_points(
        self,
        points: list[dict[str, Any]],
    ) -> dict[str, Any]:
        sample_count = len(points)
        if sample_count < 2:
            sample_quality = "INSUFFICIENT_DATA"
            reason = "fewer_than_two_unique_settled_contracts"
        elif sample_count < 30:
            sample_quality = "LOW_SAMPLE"
            reason = "fewer_than_thirty_unique_settled_contracts"
        else:
            sample_quality = "OK"
            reason = None

        briers = [float(point["brier_score"]) for point in points]
        log_losses = [float(point["log_loss"]) for point in points]
        probabilities = [float(point["probability"]) for point in points]
        outcomes = [int(point["outcome"]) for point in points]
        market_briers = [
            float(point["market_brier_score"])
            for point in points
            if point["market_brier_score"] is not None
        ]
        market_log_losses = [
            float(point["market_log_loss"])
            for point in points
            if point["market_log_loss"] is not None
        ]
        paired_forecast_briers = [
            float(point["brier_score"])
            for point in points
            if point["market_brier_score"] is not None
        ]

        raw_bins: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for point in points:
            index = min(9, max(0, int(float(point["probability"]) * 10)))
            raw_bins[index].append(point)

        buckets: list[dict[str, Any]] = []
        weighted_gap = 0.0
        occupied_gaps: list[float] = []
        for index in range(10):
            entries = raw_bins.get(index, [])
            avg_probability = (
                mean(float(entry["probability"]) for entry in entries)
                if entries
                else None
            )
            empirical_rate = (
                mean(int(entry["outcome"]) for entry in entries) if entries else None
            )
            gap = (
                abs(avg_probability - empirical_rate)
                if sample_count >= 2
                and avg_probability is not None
                and empirical_rate is not None
                else None
            )
            if gap is not None:
                weighted_gap += gap * len(entries)
                occupied_gaps.append(gap)
            buckets.append(
                {
                    "bucket": index,
                    "range": [round(index / 10, 1), round((index + 1) / 10, 1)],
                    "count": len(entries),
                    "mean_probability": (
                        round(avg_probability, 6)
                        if avg_probability is not None
                        else None
                    ),
                    "empirical_rate": (
                        round(empirical_rate, 6) if empirical_rate is not None else None
                    ),
                    "accuracy": (
                        round(empirical_rate, 6) if empirical_rate is not None else None
                    ),
                    "absolute_gap": round(gap, 6) if gap is not None else None,
                }
            )

        brier_score = round(mean(briers), 6) if briers else None
        market_brier_score = round(mean(market_briers), 6) if market_briers else None
        paired_forecast_brier_score = (
            round(mean(paired_forecast_briers), 6) if paired_forecast_briers else None
        )
        return {
            "status": sample_quality,
            "sample_quality": sample_quality,
            "reason": reason,
            "sample_size": sample_count,
            "sample_count": sample_count,
            "contract_count": sample_count,
            "brier_score": brier_score,
            "brier_score_ci_95": self._mean_ci_95(
                briers,
                lower_bound=0.0,
                upper_bound=1.0,
            ),
            "log_loss": round(mean(log_losses), 6) if log_losses else None,
            "log_loss_ci_95": self._mean_ci_95(
                log_losses,
                lower_bound=0.0,
            ),
            "expected_calibration_error": (
                round(weighted_gap / sample_count, 6) if sample_count >= 2 else None
            ),
            "maximum_calibration_error": (
                round(max(occupied_gaps), 6) if occupied_gaps else None
            ),
            "mean_probability": (
                round(mean(probabilities), 6) if probabilities else None
            ),
            "empirical_rate": round(mean(outcomes), 6) if outcomes else None,
            "market_sample_count": len(market_briers),
            "market_brier_score": market_brier_score,
            "paired_forecast_brier_score": paired_forecast_brier_score,
            "market_log_loss": (
                round(mean(market_log_losses), 6) if market_log_losses else None
            ),
            "brier_skill_vs_market": (
                round(market_brier_score - paired_forecast_brier_score, 6)
                if market_brier_score is not None
                and paired_forecast_brier_score is not None
                else None
            ),
            "abstention_count": sum(
                1 for point in points if point["no_trade_reason"] is not None
            ),
            "abstention_rate": (
                round(
                    sum(1 for point in points if point["no_trade_reason"] is not None)
                    / sample_count,
                    6,
                )
                if sample_count
                else 0.0
            ),
            "buckets": buckets,
            "binning": {
                "scheme": "ten_fixed_probability_bins",
                "ece_weighting": "unique_contract_count",
                "mce_definition": "maximum_occupied_bin_absolute_gap",
                "minimum_contracts_for_ece_mce": 2,
            },
            "uncertainty_interval_method": (
                "descriptive_normal_approximation_95pct"
                if sample_count >= 2
                else "not_computed_below_two_contracts"
            ),
        }

    def score_dataset_v2(
        self,
        forecasts: Iterable[ForecastRecordV2],
        settlements: Iterable[SettlementRecord],
    ) -> dict[str, Any]:
        """Score a dataset using one point per unique settled contract.

        The latest valid forecast strictly before settlement is selected.
        At-settlement/future snapshots, duplicate settlement rows, outcome
        conflicts, and naive timestamps cannot inflate calibration evidence.
        """
        forecast_rows = list(forecasts)
        settlement_rows = list(settlements)
        settlements_by_key: dict[tuple[str, str], SettlementRecord] = {}
        conflict_keys: set[tuple[str, str]] = set()
        duplicate_settlement_count = 0
        invalid_settlement_count = 0

        for settlement in settlement_rows:
            key = self._contract_key(
                settlement.market_ticker,
                settlement.contract_ticker,
            )
            settled_at = self._utc_or_none(settlement.settled_at)
            if (
                not all(key)
                or settled_at is None
                or settlement.outcome not in {0, 1}
                or not settlement.source.strip()
            ):
                invalid_settlement_count += 1
                continue
            if key in conflict_keys:
                continue
            prior = settlements_by_key.get(key)
            if prior is None:
                settlements_by_key[key] = settlement
                continue
            if prior.outcome != settlement.outcome:
                conflict_keys.add(key)
                settlements_by_key.pop(key, None)
                continue
            duplicate_settlement_count += 1
            prior_at = self._utc_or_none(prior.settled_at)
            if prior_at is not None and settled_at < prior_at:
                settlements_by_key[key] = settlement

        forecasts_by_key: dict[tuple[str, str], list[ForecastRecordV2]] = defaultdict(
            list
        )
        invalid_forecast_identity_count = 0
        for forecast in forecast_rows:
            key = self._contract_key(
                forecast.market_ticker,
                forecast.contract_ticker,
            )
            if not all(key) or not forecast.forecast_id.strip():
                invalid_forecast_identity_count += 1
                continue
            forecasts_by_key[key].append(forecast)

        points: list[dict[str, Any]] = []
        unmatched_settlement_count = 0
        invalid_forecast_timestamp_count = 0
        invalid_probability_count = 0
        invalid_market_probability_count = 0
        post_settlement_forecast_count = 0
        at_settlement_forecast_count = 0
        superseded_forecast_count = 0
        forecast_outcome_conflict_count = 0

        for key, settlement in sorted(settlements_by_key.items()):
            settled_at = self._utc_or_none(settlement.settled_at)
            if settled_at is None:
                invalid_settlement_count += 1
                continue
            eligible: list[tuple[datetime, str, ForecastRecordV2]] = []
            for forecast in forecasts_by_key.get(key, []):
                forecast_at = self._utc_or_none(forecast.timestamp)
                if forecast_at is None:
                    invalid_forecast_timestamp_count += 1
                    continue
                probability = float(forecast.final_probability)
                if not 0.0 <= probability <= 1.0:
                    invalid_probability_count += 1
                    continue
                if forecast_at >= settled_at:
                    if forecast_at == settled_at:
                        at_settlement_forecast_count += 1
                    else:
                        post_settlement_forecast_count += 1
                    continue
                eligible.append((forecast_at, forecast.forecast_id, forecast))
            if not eligible:
                unmatched_settlement_count += 1
                continue

            eligible.sort(key=lambda item: (item[0], item[1]))
            forecast_at, _, selected = eligible[-1]
            superseded_forecast_count += len(eligible) - 1
            if (
                selected.realized_outcome is not None
                and selected.realized_outcome != settlement.outcome
            ):
                forecast_outcome_conflict_count += 1
                continue

            probability = float(selected.final_probability)
            market_probability = float(selected.market_implied_probability)
            if not 0.0 <= market_probability <= 1.0:
                market_probability = None
                invalid_market_probability_count += 1
            outcome = settlement.outcome
            domain = self._slice_name(selected.category)
            horizon = self._calibration_horizon(
                selected,
                forecast_at,
                settled_at,
            )
            points.append(
                {
                    "market_ticker": selected.market_ticker,
                    "contract_ticker": selected.contract_ticker,
                    "forecast_id": selected.forecast_id,
                    "selected_forecast_at": forecast_at.isoformat(),
                    "settled_at": settled_at.isoformat(),
                    "probability": round(probability, 6),
                    "market_probability": (
                        round(market_probability, 6)
                        if market_probability is not None
                        else None
                    ),
                    "outcome": outcome,
                    "brier_score": round(self._brier(probability, outcome), 6),
                    "log_loss": round(self._safe_log_loss(probability, outcome), 6),
                    "market_brier_score": (
                        round(self._brier(market_probability, outcome), 6)
                        if market_probability is not None
                        else None
                    ),
                    "market_log_loss": (
                        round(self._safe_log_loss(market_probability, outcome), 6)
                        if market_probability is not None
                        else None
                    ),
                    "domain": domain,
                    "horizon": horizon,
                    "temporal_slice": settled_at.strftime("%Y-%m"),
                    "forecast_temporal_slice": forecast_at.strftime("%Y-%m"),
                    "no_trade_reason": selected.no_trade_reason,
                }
            )

        def summaries(field: str) -> dict[str, dict[str, Any]]:
            grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for point in points:
                grouped[str(point[field])].append(point)
            return {
                label: self._summarize_calibration_points(grouped[label])
                for label in sorted(grouped)
            }

        overall = self._summarize_calibration_points(points)
        return {
            "status": overall["status"],
            "calibration_unit": "unique_market_contract",
            "selection_policy": "latest_valid_forecast_strictly_before_settlement",
            "forecast_population": (
                "all_logged_forecasts_including_no_trade_abstentions"
            ),
            "settlement_truth_authority": "settlement_ledger",
            "overall": overall,
            "temporal_slices": summaries("temporal_slice"),
            "forecast_temporal_slices": summaries("forecast_temporal_slice"),
            "domain_slices": summaries("domain"),
            "horizon_slices": summaries("horizon"),
            "domain_horizon_slices": {
                domain: {
                    horizon: self._summarize_calibration_points(
                        [
                            point
                            for point in points
                            if point["domain"] == domain and point["horizon"] == horizon
                        ]
                    )
                    for horizon in sorted(
                        {
                            str(point["horizon"])
                            for point in points
                            if point["domain"] == domain
                        }
                    )
                }
                for domain in sorted({str(point["domain"]) for point in points})
            },
            "contract_metrics": points,
            "diagnostics": {
                "input_forecast_count": len(forecast_rows),
                "input_settlement_count": len(settlement_rows),
                "unique_settlement_contract_count": len(settlements_by_key),
                "scored_contract_count": len(points),
                "duplicate_settlement_count": duplicate_settlement_count,
                "conflicting_settlement_contract_count": len(conflict_keys),
                "invalid_settlement_count": invalid_settlement_count,
                "unmatched_settlement_count": unmatched_settlement_count,
                "invalid_forecast_identity_count": invalid_forecast_identity_count,
                "invalid_forecast_timestamp_count": invalid_forecast_timestamp_count,
                "invalid_probability_count": invalid_probability_count,
                "invalid_market_probability_count": invalid_market_probability_count,
                "post_settlement_forecast_count": post_settlement_forecast_count,
                "at_settlement_forecast_count": at_settlement_forecast_count,
                "superseded_pre_settlement_forecast_count": superseded_forecast_count,
                "forecast_outcome_conflict_count": forecast_outcome_conflict_count,
            },
        }

    def score_v2(
        self,
        forecasts: list[ForecastRecordV2],
        settlement: SettlementRecord,
    ) -> CalibrationMetricsV2:
        """V2 multi-model scoring for a settled contract.

        All metrics are descriptive and averaged over the supplied forecast
        sequence. ECE/MCE are intentionally absent here because they require
        multiple unique contracts; use :meth:`score_dataset_v2` for those
        metrics. No profitability or SOTA claim is made.
        """
        if not forecasts:
            return CalibrationMetricsV2(
                market_ticker=settlement.market_ticker,
                contract_ticker=settlement.contract_ticker,
                sample_count=0,
                settled_count=0,
            )

        y = settlement.outcome
        settlement_key = self._contract_key(
            settlement.market_ticker,
            settlement.contract_ticker,
        )
        briers: list[float] = []
        log_losses: list[float] = []
        market_deltas: list[float] = []
        disagreement_scores: list[float] = []
        abstention_count = 0
        no_trade_reasons: dict[str, int] = {}

        for rec in forecasts:
            if (
                self._contract_key(rec.market_ticker, rec.contract_ticker)
                != settlement_key
            ):
                raise ValueError(
                    "score_v2 accepts forecasts for exactly one settled contract"
                )
            p = float(rec.final_probability)
            market_probability = float(rec.market_implied_probability)
            if not 0.0 <= p <= 1.0 or not 0.0 <= market_probability <= 1.0:
                raise ValueError("forecast probabilities must be between zero and one")
            briers.append(self._brier(p, y))
            log_losses.append(self._safe_log_loss(p, y))
            market_deltas.append(abs(p - market_probability))

            model_probs = [float(x) for x in rec.model_probabilities()]
            if any(not 0.0 <= value <= 1.0 for value in model_probs):
                raise ValueError("model probabilities must be between zero and one")
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
            expected_calibration_error=None,
            maximum_calibration_error=None,
            market_implied_delta=round(mean(market_deltas), 6)
            if market_deltas
            else None,
            model_disagreement_score=round(mean(disagreement_scores), 6)
            if disagreement_scores
            else None,
            confidence_bucket_accuracy=self._confidence_bucket_accuracy(forecasts, y),
            abstention_count=abstention_count,
            abstention_rate=round(abstention_count / sample_count, 6)
            if sample_count
            else 0.0,
            no_trade_reasons=no_trade_reasons,
            sample_count=sample_count,
            settled_count=1,
        )
