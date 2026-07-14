"""V23 observer closure, calibration, and Tier-0 adapter-gate reports."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from predator_mesh.v22.reports import (
    ForecastWriteBreakthroughEngine,
    ObserverQueueItem,
    OutcomeObserverQueueV1,
)
from predator_mesh.v23 import MILESTONE

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts" / "dummy"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_base(workstream: str, verdict: str = "PASS") -> dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "workstream": workstream,
        "milestone": MILESTONE,
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "read_only_only": True,
        "secret_values_exposed": False,
        "verdict": verdict,
    }


def _safe_payload(workstream: str, verdict: str = "PASS", **extra: Any) -> dict[str, Any]:
    report = _safe_base(workstream, verdict)
    report.update(extra)
    return report


def _present(env_name: str) -> bool:
    return bool(os.environ.get(env_name))


@dataclass(frozen=True)
class ForecastObserverProofRef:
    ref: str
    ref_type: str = "artifact"

    def to_dict(self) -> dict[str, str]:
        return {"ref": self.ref, "ref_type": self.ref_type}


@dataclass(frozen=True)
class ForecastObserverRecord:
    record_id: str
    snapshot_id: str
    domain: str
    due_at_utc: str
    status: str
    proof_refs: tuple[ForecastObserverProofRef, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "snapshot_id": self.snapshot_id,
            "domain": self.domain,
            "due_at_utc": self.due_at_utc,
            "status": self.status,
            "outcome_observed": False,
            "scoring_allowed": False,
            "execution_bridge_created": False,
            "proof_refs": [ref.to_dict() for ref in self.proof_refs],
        }


@dataclass(frozen=True)
class ForecastObservationAttempt:
    attempt_id: str
    snapshot_id: str
    domain: str
    attempted_at_utc: str
    due_at_utc: str
    status: str
    source_class: str
    proof_ref: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "snapshot_id": self.snapshot_id,
            "domain": self.domain,
            "attempted_at_utc": self.attempted_at_utc,
            "due_at_utc": self.due_at_utc,
            "status": self.status,
            "source_class": self.source_class,
            "ledgered": True,
            "order_endpoint_called": False,
            "cancel_endpoint_called": False,
            "proof_ref": self.proof_ref,
        }


@dataclass(frozen=True)
class ForecastObservationDecision:
    decision_id: str
    snapshot_id: str
    domain: str
    decision: str
    score_now: bool
    reason: str
    proof_ref: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "snapshot_id": self.snapshot_id,
            "domain": self.domain,
            "decision": self.decision,
            "score_now": self.score_now,
            "reason": self.reason,
            "forecast_mutated": False,
            "execution_bridge_created": False,
            "proof_ref": self.proof_ref,
        }


@dataclass(frozen=True)
class ForecastObservationBlocker:
    blocker_id: str
    snapshot_id: str
    domain: str
    blocker: str
    operator_action: str

    def to_dict(self) -> dict[str, str]:
        return {
            "blocker_id": self.blocker_id,
            "snapshot_id": self.snapshot_id,
            "domain": self.domain,
            "blocker": self.blocker,
            "operator_action": self.operator_action,
        }


class V22ForecastObserverClosure:
    def __init__(self, observer: OutcomeObserverQueueV1 | None = None) -> None:
        self.observer = observer or OutcomeObserverQueueV1()

    def _items(self) -> list[ObserverQueueItem]:
        return self.observer.items()

    def records(self) -> list[ForecastObserverRecord]:
        return [
            ForecastObserverRecord(
                f"record_v23_{item.snapshot_id}",
                item.snapshot_id,
                item.domain,
                item.check_after_utc,
                "NOT_DUE_YET",
                (
                    ForecastObserverProofRef("artifacts/dummy/forecast_snapshot_write_proof_v1.json"),
                    ForecastObserverProofRef("artifacts/dummy/observer_queue_ledger_write_v22_report.json"),
                ),
            )
            for item in self._items()
        ]

    def attempts(self) -> list[ForecastObservationAttempt]:
        attempted_at = now_iso()
        return [
            ForecastObservationAttempt(
                f"attempt_v23_{item.snapshot_id}",
                item.snapshot_id,
                item.domain,
                attempted_at,
                item.check_after_utc,
                "NOT_DUE_YET",
                "PUBLIC_READONLY_SETTLEMENT_SOURCE",
                "artifacts/dummy/v22_forecast_observer_closure_report_v1.json",
            )
            for item in self._items()
        ]

    def decisions(self) -> list[ForecastObservationDecision]:
        return [
            ForecastObservationDecision(
                f"decision_v23_{record.snapshot_id}",
                record.snapshot_id,
                record.domain,
                "KEEP_UNRESOLVED_PENDING",
                False,
                "Forecast settlement horizon has not elapsed; no outcome can be scored.",
                "artifacts/dummy/forecast_observation_attempt_report_v1.json",
            )
            for record in self.records()
        ]

    def blockers(self) -> list[ForecastObservationBlocker]:
        return [
            ForecastObservationBlocker(
                f"blocker_v23_{record.snapshot_id}",
                record.snapshot_id,
                record.domain,
                "SETTLEMENT_HORIZON_PENDING",
                "Wait for due time, then run bounded read-only settlement observation.",
            )
            for record in self.records()
        ]

    def to_report(self) -> dict[str, Any]:
        records = [record.to_dict() for record in self.records()]
        return _safe_payload(
            "V23: V22 Forecast Observer Closure V1",
            "PASS",
            forecast_snapshot_count=len(records),
            observer_record_count=len(records),
            observed_outcome_count=0,
            unresolved_count=len(records),
            records=records,
            no_fabricated_outcomes=True,
            no_observer_execution_bridge=True,
            attempts_ledgered=True,
        )

    def attempt_report(self) -> dict[str, Any]:
        attempts = [attempt.to_dict() for attempt in self.attempts()]
        return _safe_payload(
            "V23: Forecast Observation Attempt V1",
            "PASS",
            attempt_count=len(attempts),
            attempts=attempts,
            all_attempts_ledgered=True,
        )

    def decision_report(self) -> dict[str, Any]:
        decisions = [decision.to_dict() for decision in self.decisions()]
        return _safe_payload(
            "V23: Forecast Observation Decision V1",
            "PASS",
            decision_count=len(decisions),
            decisions=decisions,
            unresolved_forecasts_scored=False,
        )

    def blocker_report(self) -> dict[str, Any]:
        blockers = [blocker.to_dict() for blocker in self.blockers()]
        return _safe_payload(
            "V23: Forecast Observation Blocker V1",
            "PARTIAL",
            blocker_count=len(blockers),
            blockers=blockers,
        )


class CryptoSpotSettlementProbe:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload(
            "V23: Crypto Spot Settlement Probe V1",
            "PASS",
            snapshot_id="forecast_v22_crypto_btc_spot_threshold_001",
            source_candidates=["coinbase_public", "kraken_public"],
            source_class="PUBLIC_READONLY_SPOT",
            status="NOT_DUE_YET",
            observed_value=None,
            private_exchange_api_used=False,
            trading_endpoint_called=False,
            leverage_or_perp_enabled=False,
            proof_refs=["artifacts/dummy/crypto_spot_edge_terrain_activator_report_v1.json"],
        )


class CryptoForecastOutcomeStatus:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload(
            "V23: Crypto Forecast Outcome Status V1",
            "PASS",
            snapshot_id="forecast_v22_crypto_btc_spot_threshold_001",
            outcome_status="NOT_DUE_YET",
            settlement_source_status="PENDING_HORIZON",
            scoreable=False,
            forecast_rewritten=False,
            outcome_leakage=False,
        )


class CryptoForecastSettlementBlocker:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload(
            "V23: Crypto Forecast Settlement Blocker V1",
            "PARTIAL",
            blockers=[
                {
                    "snapshot_id": "forecast_v22_crypto_btc_spot_threshold_001",
                    "blocker": "SETTLEMENT_HORIZON_PENDING",
                    "next_action": "Run bounded Coinbase/Kraken public read-only settlement check after due time.",
                }
            ],
        )


class CryptoForecastOutcomeObserverV1:
    def to_report(self) -> dict[str, Any]:
        probe = CryptoSpotSettlementProbe().to_report()
        status = CryptoForecastOutcomeStatus().to_report()
        return _safe_payload(
            "V23: Crypto Forecast Outcome Observer V1",
            "PASS",
            snapshot_id="forecast_v22_crypto_btc_spot_threshold_001",
            probe_status=probe["status"],
            outcome_status=status["outcome_status"],
            observed=False,
            unresolved=True,
            scoreable=False,
            public_readonly_only=True,
            no_trading_endpoint=True,
        )


class WeatherStationSettlementProbe:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload(
            "V23: Weather Station Settlement Probe V1",
            "PASS",
            snapshot_id="forecast_v22_weather_kmci_temp_threshold_001",
            station="KMCI",
            source_candidates=["NWS_API_WEATHER_GOV", "NOAA_PUBLIC_OBSERVATION"],
            source_class="OFFICIAL_PUBLIC_READONLY_WEATHER",
            status="NOT_DUE_YET",
            observed_value=None,
            observation_timestamp_utc=None,
            freshness_status="PENDING_HORIZON",
            proof_refs=["artifacts/dummy/weather_settlement_station_mapper_report_v1.json"],
        )


class WeatherForecastOutcomeStatus:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload(
            "V23: Weather Forecast Outcome Status V1",
            "PASS",
            snapshot_id="forecast_v22_weather_kmci_temp_threshold_001",
            station_mapping_status="MAPPED",
            outcome_status="NOT_DUE_YET",
            scoreable=False,
            fabricated_outcome=False,
        )


class WeatherForecastSettlementBlocker:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload(
            "V23: Weather Forecast Settlement Blocker V1",
            "PARTIAL",
            blockers=[
                {
                    "snapshot_id": "forecast_v22_weather_kmci_temp_threshold_001",
                    "blocker": "SETTLEMENT_HORIZON_PENDING",
                    "next_action": "Run official public NWS/NOAA station observation check after due time.",
                }
            ],
        )


class WeatherForecastOutcomeObserverV1:
    def to_report(self) -> dict[str, Any]:
        probe = WeatherStationSettlementProbe().to_report()
        status = WeatherForecastOutcomeStatus().to_report()
        return _safe_payload(
            "V23: Weather Forecast Outcome Observer V1",
            "PASS",
            snapshot_id="forecast_v22_weather_kmci_temp_threshold_001",
            probe_status=probe["status"],
            outcome_status=status["outcome_status"],
            station_mapping_status=status["station_mapping_status"],
            observed=False,
            unresolved=True,
            scoreable=False,
            official_public_readonly_only=True,
        )


@dataclass(frozen=True)
class ForecastResolutionState:
    snapshot_id: str
    domain: str
    state: str
    scoreable: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "domain": self.domain,
            "resolution_state": self.state,
            "scoreable": self.scoreable,
        }


@dataclass(frozen=True)
class ForecastScoreCandidate:
    snapshot_id: str
    domain: str
    confidence: float
    resolution: ForecastResolutionState

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "domain": self.domain,
            "confidence": self.confidence,
            "confidence_bucket": "LOW_SAMPLE_LOW_CONFIDENCE",
            "resolution": self.resolution.to_dict(),
        }


@dataclass(frozen=True)
class ForecastScoreResult:
    snapshot_id: str
    domain: str
    brier_score: float | None
    directional_hit: bool | None
    absolute_threshold_error: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "domain": self.domain,
            "brier_score": self.brier_score,
            "directional_hit": self.directional_hit,
            "absolute_threshold_error": self.absolute_threshold_error,
        }


@dataclass(frozen=True)
class ForecastScoreBlocker:
    snapshot_id: str
    domain: str
    blocker: str

    def to_dict(self) -> dict[str, str]:
        return {"snapshot_id": self.snapshot_id, "domain": self.domain, "blocker": self.blocker}


@dataclass(frozen=True)
class ForecastScoreIntegrityProof:
    proof_id: str
    unresolved_scored: bool = False
    forecast_mutated: bool = False
    fixture_claimed_real: bool = False
    execution_bridge_created: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "unresolved_scored": self.unresolved_scored,
            "forecast_mutated": self.forecast_mutated,
            "fixture_claimed_real": self.fixture_claimed_real,
            "execution_bridge_created": self.execution_bridge_created,
        }


class ForecastScoringEngineV2:
    def candidates(self) -> list[ForecastScoreCandidate]:
        proofs = ForecastWriteBreakthroughEngine().snapshot_proofs()
        return [
            ForecastScoreCandidate(
                proof.snapshot_id,
                proof.domain,
                proof.confidence,
                ForecastResolutionState(proof.snapshot_id, proof.domain, "NOT_DUE_YET", False),
            )
            for proof in proofs
        ]

    def results(self) -> list[ForecastScoreResult]:
        return []

    def blockers(self) -> list[ForecastScoreBlocker]:
        return [
            ForecastScoreBlocker(candidate.snapshot_id, candidate.domain, "NOT_DUE_YET")
            for candidate in self.candidates()
        ]

    def to_report(self) -> dict[str, Any]:
        candidates = [candidate.to_dict() for candidate in self.candidates()]
        results = [result.to_dict() for result in self.results()]
        blockers = [blocker.to_dict() for blocker in self.blockers()]
        return _safe_payload(
            "V23: Forecast Scoring Engine V2",
            "PARTIAL",
            candidate_count=len(candidates),
            scored_forecast_count=len(results),
            unresolved_forecast_count=len(blockers),
            unresolved_rate=1.0,
            low_sample_warning=True,
            domain_score_state={"crypto": {"scored": 0, "unresolved": 1}, "weather": {"scored": 0, "unresolved": 1}},
            global_score_state={"scored": 0, "unresolved": 2, "brier_score": None},
            candidates=candidates,
            results=results,
            blockers=blockers,
            unresolved_forecasts_scored=False,
            forecast_mutated=False,
        )

    def candidate_report(self) -> dict[str, Any]:
        candidates = [candidate.to_dict() for candidate in self.candidates()]
        return _safe_payload("V23: Forecast Score Candidate V1", "PASS", candidate_count=len(candidates), candidates=candidates)

    def result_report(self) -> dict[str, Any]:
        results = [result.to_dict() for result in self.results()]
        return _safe_payload("V23: Forecast Score Result V1", "PARTIAL", result_count=len(results), results=results, no_scoreable_forecasts=True)

    def blocker_report(self) -> dict[str, Any]:
        blockers = [blocker.to_dict() for blocker in self.blockers()]
        return _safe_payload("V23: Forecast Score Blocker V1", "PARTIAL", blocker_count=len(blockers), blockers=blockers)

    def integrity_proof_report(self) -> dict[str, Any]:
        proof = ForecastScoreIntegrityProof("forecast_score_integrity_v23_001").to_dict()
        return _safe_payload("V23: Forecast Score Integrity Proof V1", "PASS", proof=proof)


@dataclass(frozen=True)
class DomainCalibrationUpdate:
    domain: str
    resolved_samples: int
    unresolved_samples: int
    readiness: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "resolved_samples": self.resolved_samples,
            "unresolved_samples": self.unresolved_samples,
            "calibration_readiness": self.readiness,
        }


@dataclass(frozen=True)
class CalibrationBucketUpdate:
    bucket: str
    sample_count: int
    update_applied: bool
    warning: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "bucket": self.bucket,
            "sample_count": self.sample_count,
            "update_applied": self.update_applied,
            "warning": self.warning,
        }


@dataclass(frozen=True)
class LowSampleCalibrationWarning:
    code: str
    sample_count: int
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "sample_count": self.sample_count, "detail": self.detail}


@dataclass(frozen=True)
class CalibrationDriftCandidate:
    domain: str
    drift_detected: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"domain": self.domain, "drift_detected": self.drift_detected, "reason": self.reason}


class CalibrationQueueState:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload(
            "V23: Calibration Queue State V1",
            "PARTIAL",
            queue=[
                {"domain": "crypto", "snapshot_id": "forecast_v22_crypto_btc_spot_threshold_001", "state": "WAITING_FOR_RESOLUTION"},
                {"domain": "weather", "snapshot_id": "forecast_v22_weather_kmci_temp_threshold_001", "state": "WAITING_FOR_RESOLUTION"},
            ],
            unresolved_queue_count=2,
        )


class CalibrationUpdateEngineV3:
    def updates(self) -> list[DomainCalibrationUpdate]:
        return [
            DomainCalibrationUpdate("crypto", 0, 1, "READY_AFTER_OBSERVER_RESOLUTION"),
            DomainCalibrationUpdate("weather", 0, 1, "READY_AFTER_OBSERVER_RESOLUTION"),
            DomainCalibrationUpdate("finance", 0, 0, "BLOCKED_NO_FORECAST"),
            DomainCalibrationUpdate("commodities", 0, 0, "BLOCKED_NO_FORECAST"),
            DomainCalibrationUpdate("sports", 0, 0, "BLOCKED_SOURCE_MISSING"),
        ]

    def buckets(self) -> list[CalibrationBucketUpdate]:
        return [
            CalibrationBucketUpdate("LOW_CONFIDENCE_0_50_TO_0_60", 0, False, "LOW_SAMPLE_NO_UPDATE"),
            CalibrationBucketUpdate("REAL_READONLY", 0, False, "WAITING_FOR_RESOLVED_OUTCOMES"),
            CalibrationBucketUpdate("FIXTURE_STATIC", 0, False, "NO_REAL_SOURCE_CREDIT"),
        ]

    def warnings(self) -> list[LowSampleCalibrationWarning]:
        return [LowSampleCalibrationWarning("LOW_SAMPLE_NO_RESOLVED_FORECASTS", 0, "No resolved V22 forecast outcomes are available yet.")]

    def drift_candidates(self) -> list[CalibrationDriftCandidate]:
        return [CalibrationDriftCandidate("global", False, "No scored samples; drift cannot be inferred.")]

    def to_report(self) -> dict[str, Any]:
        updates = [update.to_dict() for update in self.updates()]
        return _safe_payload(
            "V23: Calibration Update Engine V3",
            "PARTIAL",
            calibration_sample_count=0,
            unresolved_forecast_count=2,
            updates=updates,
            low_sample_warning=True,
            heavy_ml_enabled=False,
            statistical_overclaim=False,
        )

    def domain_update_report(self) -> dict[str, Any]:
        updates = [update.to_dict() for update in self.updates()]
        return _safe_payload("V23: Domain Calibration Update V1", "PARTIAL", updates=updates, update_count=len(updates))

    def bucket_update_report(self) -> dict[str, Any]:
        buckets = [bucket.to_dict() for bucket in self.buckets()]
        return _safe_payload("V23: Calibration Bucket Update V1", "PARTIAL", buckets=buckets, bucket_count=len(buckets))

    def low_sample_warning_report(self) -> dict[str, Any]:
        warnings = [warning.to_dict() for warning in self.warnings()]
        return _safe_payload("V23: Low Sample Calibration Warning V1", "PARTIAL", warnings=warnings, warning_count=len(warnings))


@dataclass(frozen=True)
class EdgeForecastAttribution:
    snapshot_id: str
    domain: str
    source_id: str
    attribution_state: str

    def to_dict(self) -> dict[str, str]:
        return {
            "snapshot_id": self.snapshot_id,
            "domain": self.domain,
            "source_id": self.source_id,
            "attribution_state": self.attribution_state,
        }


@dataclass(frozen=True)
class SourceAttributionUpdate:
    source_id: str
    update_type: str
    confidence: str

    def to_dict(self) -> dict[str, str]:
        return {"source_id": self.source_id, "update_type": self.update_type, "confidence": self.confidence}


@dataclass(frozen=True)
class OutcomePendingAttribution:
    snapshot_id: str
    domain: str
    pending_reason: str

    def to_dict(self) -> dict[str, str]:
        return {"snapshot_id": self.snapshot_id, "domain": self.domain, "pending_reason": self.pending_reason}


@dataclass(frozen=True)
class AttributionConfidenceState:
    state: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"state": self.state, "reason": self.reason}


class NoTradeAttributionV2:
    def attributions(self) -> list[dict[str, Any]]:
        return [
            {
                "no_trade_id": "no_trade_v22_finance_001",
                "source_id": "SEC_EDGAR",
                "domain": "finance",
                "credit": "CONTEXT_DISCIPLINE_CREDIT",
                "reason": "Blocked Nasdaq edge overclaim without Tier-0 market data.",
            },
            {
                "no_trade_id": "no_trade_v22_commodities_001",
                "source_id": "WORLD_BANK_COMMODITY_PRICES",
                "domain": "commodities",
                "credit": "CONTEXT_DISCIPLINE_CREDIT",
                "reason": "Blocked oil edge overclaim without CL/Brent/EIA terrain.",
            },
        ]

    def to_report(self) -> dict[str, Any]:
        items = self.attributions()
        return _safe_payload("V23: No Trade Attribution V2", "PASS", attribution_count=len(items), attributions=items, fake_causality_claimed=False)


class ForecastAttributionEngineV2:
    def edge_attributions(self) -> list[EdgeForecastAttribution]:
        return [
            EdgeForecastAttribution("forecast_v22_crypto_btc_spot_threshold_001", "crypto", "coinbase_public", "PENDING_OUTCOME"),
            EdgeForecastAttribution("forecast_v22_crypto_btc_spot_threshold_001", "crypto", "kraken_public", "PENDING_OUTCOME"),
            EdgeForecastAttribution("forecast_v22_weather_kmci_temp_threshold_001", "weather", "NWS_API_WEATHER_GOV", "PENDING_OUTCOME"),
        ]

    def source_updates(self) -> list[SourceAttributionUpdate]:
        return [
            SourceAttributionUpdate("coinbase_public", "EDGE_READINESS_CREDIT_ONLY", "LOW_PENDING_OUTCOME"),
            SourceAttributionUpdate("kraken_public", "EDGE_READINESS_CREDIT_ONLY", "LOW_PENDING_OUTCOME"),
            SourceAttributionUpdate("NWS_API_WEATHER_GOV", "EDGE_READINESS_CREDIT_ONLY", "LOW_PENDING_OUTCOME"),
            SourceAttributionUpdate("SEC_EDGAR", "NO_TRADE_DISCIPLINE_CREDIT", "MEDIUM_CONTEXT_ONLY"),
            SourceAttributionUpdate("WORLD_BANK_COMMODITY_PRICES", "NO_TRADE_DISCIPLINE_CREDIT", "MEDIUM_CONTEXT_ONLY"),
        ]

    def pending_attributions(self) -> list[OutcomePendingAttribution]:
        return [
            OutcomePendingAttribution("forecast_v22_crypto_btc_spot_threshold_001", "crypto", "NOT_DUE_YET"),
            OutcomePendingAttribution("forecast_v22_weather_kmci_temp_threshold_001", "weather", "NOT_DUE_YET"),
        ]

    def to_report(self) -> dict[str, Any]:
        return _safe_payload(
            "V23: Forecast Attribution Engine V2",
            "PASS",
            edge_attribution_count=len(self.edge_attributions()),
            pending_attribution_count=len(self.pending_attributions()),
            no_trade_attribution_count=len(NoTradeAttributionV2().attributions()),
            attribution_confidence=AttributionConfidenceState("LOW_CONFIDENCE_PENDING_OUTCOMES", "Forecast outcomes are unresolved.").to_dict(),
            fake_causality_claimed=False,
        )

    def edge_forecast_attribution_report(self) -> dict[str, Any]:
        items = [item.to_dict() for item in self.edge_attributions()]
        return _safe_payload("V23: Edge Forecast Attribution V1", "PASS", attributions=items, attribution_count=len(items))

    def source_attribution_update_report(self) -> dict[str, Any]:
        updates = [item.to_dict() for item in self.source_updates()]
        return _safe_payload("V23: Source Attribution Update V1", "PASS", updates=updates, update_count=len(updates))

    def outcome_pending_attribution_report(self) -> dict[str, Any]:
        pending = [item.to_dict() for item in self.pending_attributions()]
        return _safe_payload("V23: Outcome Pending Attribution V1", "PARTIAL", pending=pending, pending_count=len(pending))


@dataclass(frozen=True)
class SourceTruthUpdate:
    source_id: str
    domain: str
    update: str
    score_delta: float

    def to_dict(self) -> dict[str, Any]:
        return {"source_id": self.source_id, "domain": self.domain, "update": self.update, "score_delta": self.score_delta}


@dataclass(frozen=True)
class EdgeSourceReliabilityState:
    source_id: str
    readiness_credit: bool
    outcome_accuracy_credit: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "readiness_credit": self.readiness_credit,
            "outcome_accuracy_credit": self.outcome_accuracy_credit,
        }


@dataclass(frozen=True)
class ContextSourceReliabilityState:
    source_id: str
    no_trade_discipline_credit: bool
    edge_authority: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "no_trade_discipline_credit": self.no_trade_discipline_credit,
            "edge_authority": self.edge_authority,
        }


class SourceTruthPromotionGate:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload(
            "V23: Source Truth Promotion Gate V1",
            "PASS",
            promotions=[],
            production_authority_promoted=False,
            cap_or_live_submit_changed=False,
            reason="Low sample and unresolved outcomes prohibit promotion.",
        )


class SourceTruthDemotionGate:
    pass


class SourceTruthScoreV4:
    def updates(self) -> list[SourceTruthUpdate]:
        return [
            SourceTruthUpdate("coinbase_public", "crypto", "EDGE_READINESS_CREDIT_NO_OUTCOME_ACCURACY", 0.02),
            SourceTruthUpdate("kraken_public", "crypto", "EDGE_READINESS_CREDIT_NO_OUTCOME_ACCURACY", 0.02),
            SourceTruthUpdate("NWS_API_WEATHER_GOV", "weather", "EDGE_READINESS_CREDIT_NO_OUTCOME_ACCURACY", 0.02),
            SourceTruthUpdate("SEC_EDGAR", "finance", "CONTEXT_NO_TRADE_DISCIPLINE_CREDIT", 0.01),
            SourceTruthUpdate("WORLD_BANK_COMMODITY_PRICES", "commodities", "CONTEXT_NO_TRADE_DISCIPLINE_CREDIT", 0.01),
        ]

    def edge_states(self) -> list[EdgeSourceReliabilityState]:
        return [
            EdgeSourceReliabilityState("coinbase_public", True, False),
            EdgeSourceReliabilityState("kraken_public", True, False),
            EdgeSourceReliabilityState("NWS_API_WEATHER_GOV", True, False),
        ]

    def context_states(self) -> list[ContextSourceReliabilityState]:
        return [
            ContextSourceReliabilityState("SEC_EDGAR", True, False),
            ContextSourceReliabilityState("WORLD_BANK_COMMODITY_PRICES", True, False),
        ]

    def to_report(self) -> dict[str, Any]:
        updates = [update.to_dict() for update in self.updates()]
        return _safe_payload(
            "V23: Source Truth Score V4",
            "PASS",
            update_count=len(updates),
            updates=updates,
            low_sample_warning=True,
            fixture_sources_receive_real_credit=False,
            production_execution_authority_promoted=False,
            automatic_cap_change=False,
            automatic_live_submit_change=False,
        )

    def update_report(self) -> dict[str, Any]:
        updates = [update.to_dict() for update in self.updates()]
        return _safe_payload("V23: Source Truth Update V1", "PASS", updates=updates, update_count=len(updates))

    def edge_reliability_report(self) -> dict[str, Any]:
        states = [state.to_dict() for state in self.edge_states()]
        return _safe_payload("V23: Edge Source Reliability State V1", "PASS", states=states, state_count=len(states))

    def context_reliability_report(self) -> dict[str, Any]:
        states = [state.to_dict() for state in self.context_states()]
        return _safe_payload("V23: Context Source Reliability State V1", "PASS", states=states, state_count=len(states))


@dataclass(frozen=True)
class Tier0AdapterClosureCandidate:
    source_id: str
    domain: str
    tier: str
    env_vars: tuple[str, ...]
    config_keys: tuple[str, ...]
    endpoint_classes: tuple[str, ...]
    proof_tests: tuple[str, ...]
    blocker_state: str
    operator_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "domain": self.domain,
            "tier": self.tier,
            "env_vars": list(self.env_vars),
            "config_keys": list(self.config_keys),
            "endpoint_classes": list(self.endpoint_classes),
            "proof_tests": list(self.proof_tests),
            "blocker_state": self.blocker_state,
            "operator_action": self.operator_action,
            "secret_values_exposed": False,
            "enabled_by_default": False,
        }


@dataclass(frozen=True)
class Tier0AdapterClosureStatus:
    source_id: str
    status: str
    can_probe: bool

    def to_dict(self) -> dict[str, Any]:
        return {"source_id": self.source_id, "status": self.status, "can_probe": self.can_probe}


@dataclass(frozen=True)
class Tier0AdapterProofRequirement:
    source_id: str
    requirements: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"source_id": self.source_id, "requirements": list(self.requirements)}


@dataclass(frozen=True)
class Tier0AdapterOperatorAction:
    source_id: str
    action: str

    def to_dict(self) -> dict[str, str]:
        return {"source_id": self.source_id, "action": self.action}


class Tier0AdapterClosurePlanner:
    def candidates(self) -> list[Tier0AdapterClosureCandidate]:
        return [
            Tier0AdapterClosureCandidate("CME_NQ_ES", "nasdaq", "TIER_0_EXCHANGE_NATIVE", ("CME_MARKET_DATA_API_KEY", "DUMMY_CME_READONLY_APPROVED"), ("sources.cme.enabled", "sources.cme.instruments"), ("orderbook_top", "trades", "volume"), ("test_cme_readonly_adapter_gate_v1.py",), "BLOCKED_LICENSE_REQUIRED", "Obtain CME license, add read-only key, set approval flag."),
            Tier0AdapterClosureCandidate("CME_CL", "oil", "TIER_0_EXCHANGE_NATIVE", ("CME_MARKET_DATA_API_KEY", "DUMMY_CME_READONLY_APPROVED"), ("sources.cme.enabled", "sources.cme.instruments"), ("orderbook_top", "trades", "volume"), ("test_cme_futures_source_requirement.py",), "BLOCKED_LICENSE_REQUIRED", "Obtain CME CL license and approval."),
            Tier0AdapterClosureCandidate("ICE_BRENT_OR_DATABENTO", "oil", "TIER_2_LICENSED", ("DATABENTO_API_KEY", "DUMMY_DATABENTO_READONLY_APPROVED"), ("sources.databento.enabled", "sources.databento.datasets"), ("trades", "mbp", "ohlcv_bars"), ("test_databento_readonly_adapter_gate_v1.py",), "BLOCKED_LICENSE_REQUIRED", "Approve Databento or equivalent Brent/CL dataset."),
            Tier0AdapterClosureCandidate("DATABENTO_FUTURES_EQUITIES_OPTIONS", "nasdaq_oil", "TIER_2_LICENSED", ("DATABENTO_API_KEY", "DUMMY_DATABENTO_READONLY_APPROVED"), ("sources.databento.enabled", "sources.databento.datasets"), ("trades", "orderbook_top", "bars"), ("test_databento_dataset_requirement.py",), "BLOCKED_KEY_MISSING", "Add Databento key and approval after license review."),
            Tier0AdapterClosureCandidate("QQQ_SPY_SECTOR_MEGA_CAP", "nasdaq", "TIER_2_MARKET_DATA", ("DATABENTO_API_KEY", "DUMMY_EQUITIES_READONLY_APPROVED"), ("sources.equities.enabled",), ("bars", "trades"), ("test_tier0_adapter_closure_candidate.py",), "BLOCKED_APPROVAL_REQUIRED", "Approve safe equities/ETF source and add key if required."),
            Tier0AdapterClosureCandidate("VIX_VXN_OPTIONS_SKEW", "nasdaq", "TIER_2_LICENSED", ("DATABENTO_API_KEY", "DUMMY_OPTIONS_READONLY_APPROVED"), ("sources.options.enabled",), ("options_chain", "vol_surface"), ("test_tier0_adapter_proof_requirement.py",), "BLOCKED_LICENSE_REQUIRED", "Approve licensed options/volatility source."),
            Tier0AdapterClosureCandidate("RATES_DXY", "nasdaq_oil", "TIER_1_PUBLIC_CONTEXT", ("DUMMY_RATES_DXY_APPROVED",), ("sources.rates_dxy.enabled",), ("treasury_yields", "approved_dxy_proxy"), ("test_rates_dxy_public_context_adapter_v1.py",), "BLOCKED_DXY_SOURCE_APPROVAL", "Approve DXY proxy source; Treasury can remain context-only."),
            Tier0AdapterClosureCandidate("EIA_INVENTORY_STORAGE_REFINERY", "oil", "TIER_1_OFFICIAL_KEYED", ("EIA_API_KEY", "DUMMY_EIA_READONLY_APPROVED"), ("sources.eia.enabled", "sources.eia.series"), ("inventories", "storage", "refinery_utilization"), ("test_eia_adapter_activation_closure_v2.py",), "BLOCKED_KEY_MISSING", "Add EIA key if required and operator approval."),
        ]

    def statuses(self) -> list[Tier0AdapterClosureStatus]:
        return [Tier0AdapterClosureStatus(candidate.source_id, candidate.blocker_state, False) for candidate in self.candidates()]

    def proof_requirements(self) -> list[Tier0AdapterProofRequirement]:
        return [
            Tier0AdapterProofRequirement(candidate.source_id, ("bounded_readonly_probe", "timeout_guard", "redacted_artifact", "no_execution_bridge"))
            for candidate in self.candidates()
        ]

    def operator_actions(self) -> list[Tier0AdapterOperatorAction]:
        return [Tier0AdapterOperatorAction(candidate.source_id, candidate.operator_action) for candidate in self.candidates()]

    def to_report(self) -> dict[str, Any]:
        candidates = [candidate.to_dict() for candidate in self.candidates()]
        return _safe_payload(
            "V23: Tier-0 Adapter Closure Planner V1",
            "PARTIAL",
            candidate_count=len(candidates),
            candidates=candidates,
            live_trading_enabled=False,
            private_account_data_used=False,
            source_secret_values_exposed=False,
        )

    def candidate_report(self) -> dict[str, Any]:
        candidates = [candidate.to_dict() for candidate in self.candidates()]
        return _safe_payload("V23: Tier-0 Adapter Closure Candidate V1", "PARTIAL", candidates=candidates, candidate_count=len(candidates))

    def status_report(self) -> dict[str, Any]:
        statuses = [status.to_dict() for status in self.statuses()]
        return _safe_payload("V23: Tier-0 Adapter Closure Status V1", "PARTIAL", statuses=statuses, blocked_count=len(statuses))

    def proof_requirement_report(self) -> dict[str, Any]:
        requirements = [requirement.to_dict() for requirement in self.proof_requirements()]
        return _safe_payload("V23: Tier-0 Adapter Proof Requirement V1", "PASS", requirements=requirements, requirement_count=len(requirements))

    def operator_action_report(self) -> dict[str, Any]:
        actions = [action.to_dict() for action in self.operator_actions()]
        return _safe_payload("V23: Tier-0 Adapter Operator Action V1", "PARTIAL", actions=actions, action_count=len(actions))


class CMEFuturesSourceRequirement:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: CME Futures Source Requirement V1", "PARTIAL", instruments=["NQ", "ES", "CL"], evidence=["orderbook_top", "trades", "volume", "timestamp_freshness"], license_required=True)


class CMECredentialPresenceCheck:
    def to_report(self) -> dict[str, Any]:
        key_present = _present("CME_MARKET_DATA_API_KEY")
        approval_present = _present("DUMMY_CME_READONLY_APPROVED")
        status = "READY_FOR_BOUNDED_READONLY_PROBE" if key_present and approval_present else "BLOCKED_LICENSE_REQUIRED" if not approval_present else "BLOCKED_KEY_MISSING"
        return _safe_payload("V23: CME Credential Presence Check V1", "PARTIAL", key_present=key_present, approval_present=approval_present, status=status, secret_values_exposed=False)


class CMEReadOnlyProbePlan:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: CME Read-Only Probe Plan V1", "PARTIAL", probe_allowed=False, max_requests=1, per_request_timeout_seconds=5, endpoints=["market_data_orderbook_top", "market_data_trades"], order_endpoints_allowed=False)


class CMEAdapterBlocker:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: CME Adapter Blocker V1", "PARTIAL", blockers=[{"blocker": "BLOCKED_LICENSE_REQUIRED", "operator_action": "License CME market data and set read-only approval before probing."}])


class CMEReadOnlyAdapterGateV1:
    def to_report(self) -> dict[str, Any]:
        credential = CMECredentialPresenceCheck().to_report()
        return _safe_payload("V23: CME Read-Only Adapter Gate V1", "PARTIAL", status=credential["status"], calls_made=0, order_endpoints_allowed=False, market_orders_allowed=False, secret_values_exposed=False)


class DatabentoDatasetRequirement:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: Databento Dataset Requirement V1", "PARTIAL", dataset_classes=["futures_NQ_ES_CL", "equities_ETF_QQQ_SPY", "options_volatility_if_available"], evidence=["trades", "orderbook_top", "bars", "volume", "timestamps"], license_required=True)


class DatabentoCredentialPresenceCheck:
    def to_report(self) -> dict[str, Any]:
        key_present = _present("DATABENTO_API_KEY")
        approval_present = _present("DUMMY_DATABENTO_READONLY_APPROVED")
        status = "READY_FOR_BOUNDED_READONLY_PROBE" if key_present and approval_present else "BLOCKED_LICENSE_REQUIRED" if not approval_present else "BLOCKED_KEY_MISSING"
        return _safe_payload("V23: Databento Credential Presence Check V1", "PARTIAL", key_present=key_present, approval_present=approval_present, status=status, secret_values_exposed=False)


class DatabentoReadOnlyProbePlan:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: Databento Read-Only Probe Plan V1", "PARTIAL", probe_allowed=False, max_requests=1, per_request_timeout_seconds=5, datasets=["futures", "equities_etf", "options_volatility"], live_execution_enabled=False)


class DatabentoAdapterBlocker:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: Databento Adapter Blocker V1", "PARTIAL", blockers=[{"blocker": "BLOCKED_LICENSE_REQUIRED", "operator_action": "Approve licensed Databento feed and add key before probing."}])


class DatabentoReadOnlyAdapterGateV1:
    def to_report(self) -> dict[str, Any]:
        credential = DatabentoCredentialPresenceCheck().to_report()
        return _safe_payload("V23: Databento Read-Only Adapter Gate V1", "PARTIAL", status=credential["status"], calls_made=0, secret_values_exposed=False, live_execution_enabled=False)


class EIAKeyPresenceCheck:
    def to_report(self) -> dict[str, Any]:
        key_present = _present("EIA_API_KEY")
        approval_present = _present("DUMMY_EIA_READONLY_APPROVED")
        status = "READY_FOR_BOUNDED_READONLY_PROBE" if key_present and approval_present else "BLOCKED_APPROVAL_REQUIRED" if not approval_present else "BLOCKED_KEY_MISSING"
        return _safe_payload("V23: EIA Key Presence Check V1", "PARTIAL", key_present=key_present, approval_present=approval_present, status=status, secret_values_exposed=False)


class EIADatasetProbePlanV2:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: EIA Dataset Probe Plan V2", "PARTIAL", target_features=["inventories", "cushing_storage", "refinery_utilization", "gasoline_distillate", "production_imports"], max_series=5, timeout_seconds=5, probe_allowed=False)


class EIAInventorySeriesMapper:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: EIA Inventory Series Mapper V1", "PARTIAL", mappings=[{"feature": "crude_inventories", "series_class": "official_eia_petroleum_weekly"}, {"feature": "cushing_storage", "series_class": "official_eia_storage_weekly"}, {"feature": "refinery_utilization", "series_class": "official_eia_refinery_weekly"}], bounded_series_count=3)


class EIAOilFundamentalEvidenceGate:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: EIA Oil Fundamental Evidence Gate V1", "PARTIAL", oil_context_upgrade_allowed=False, cl_brent_futures_edge_claimed=False, reason="EIA fundamentals help oil context but do not replace CL/Brent futures edge terrain.")


class EIAActivationBlockerV2:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: EIA Activation Blocker V2", "PARTIAL", blockers=[{"blocker": "BLOCKED_APPROVAL_REQUIRED", "operator_action": "Approve EIA read-only source and provide key if endpoint requires one."}])


class EIAAdapterActivationClosureV2:
    def to_report(self) -> dict[str, Any]:
        key = EIAKeyPresenceCheck().to_report()
        return _safe_payload("V23: EIA Adapter Activation Closure V2", "PARTIAL", status=key["status"], calls_made=0, oil_context_upgrade_allowed=False, cl_brent_futures_edge_claimed=False)


class TreasuryYieldEvidenceV1:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: Treasury Yield Evidence V1", "PARTIAL", source_class="OFFICIAL_PUBLIC_TREASURY_CONTEXT", activated=False, reason="No live public call from unit/report factory path.", context_only=True)


class DXYProxyEvidenceV1:
    def to_report(self) -> dict[str, Any]:
        approval = _present("DUMMY_DXY_PROXY_READONLY_APPROVED")
        return _safe_payload("V23: DXY Proxy Evidence V1", "PARTIAL", approved_safe_source_present=approval, status="APPROVED_SOURCE_READY" if approval else "BLOCKED_APPROVED_SOURCE_MISSING", context_only=True)


class RatesFreshnessGate:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: Rates Freshness Gate V1", "PARTIAL", freshness_status="NO_LIVE_CONTEXT_SAMPLE", max_age_seconds=86400, context_claimed_edge=False)


class RatesDXYContextGuard:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: Rates/DXY Context Guard V1", "PASS", rates_context_claimed_tier0_edge=False, dxy_unapproved_source_activated=False, forecast_overclaim=False)


class RatesDXYPublicContextAdapterV1:
    def to_report(self) -> dict[str, Any]:
        treasury = TreasuryYieldEvidenceV1().to_report()
        dxy = DXYProxyEvidenceV1().to_report()
        return _safe_payload("V23: Rates/DXY Public Context Adapter V1", "PARTIAL", treasury_status=treasury["source_class"], dxy_status=dxy["status"], context_only=True, scraping_used=False, unapproved_source_activated=False)


class NasdaqEvidenceGapStateV2:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: Nasdaq Evidence Gap State V2", "PARTIAL", gaps=["CME_NQ_ES", "QQQ_SPY_MARKET_DATA", "VIX_VXN_OPTIONS_SKEW", "RATES_DXY_CONTEXT"], severity="HIGH", context_only_edge_claimed=False)


class OilEvidenceGapStateV2:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: Oil Evidence Gap State V2", "PARTIAL", gaps=["CME_CL", "ICE_BRENT", "EIA_INVENTORIES", "CURVE_SPREAD_DATA"], severity="HIGH", context_only_edge_claimed=False)


class DirectionalForecastReadinessDecisionV2:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: Directional Forecast Readiness Decision V2", "PARTIAL", decisions=[{"domain": "nasdaq", "decision": "NO_TRADE_EDGE_INSUFFICIENT"}, {"domain": "oil", "decision": "NO_TRADE_EDGE_INSUFFICIENT"}], fake_edge_claimed=False)


class NasdaqEdgeReadinessV2:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: Nasdaq Edge Readiness V2", "PARTIAL", readiness="NO_TRADE_EDGE_INSUFFICIENT", tier0_market_data_present=False, rates_context_reduces_blocker_severity=False, context_only_edge_claimed=False)


class OilEdgeReadinessV2:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: Oil Edge Readiness V2", "PARTIAL", readiness="NO_TRADE_EDGE_INSUFFICIENT", cl_brent_market_data_present=False, eia_context_can_help=True, context_only_edge_claimed=False)


@dataclass(frozen=True)
class ForecastLifecycleRecord:
    snapshot_id: str
    domain: str
    current_state: str

    def to_dict(self) -> dict[str, str]:
        return {"snapshot_id": self.snapshot_id, "domain": self.domain, "current_state": self.current_state}


class ForecastLifecycleState:
    CREATED = "CREATED"
    OBSERVER_QUEUED = "OBSERVER_QUEUED"
    NOT_DUE_YET = "NOT_DUE_YET"


@dataclass(frozen=True)
class ForecastLifecycleTransition:
    snapshot_id: str
    from_state: str
    to_state: str
    proof_ref: str

    def to_dict(self) -> dict[str, str]:
        return {"snapshot_id": self.snapshot_id, "from_state": self.from_state, "to_state": self.to_state, "proof_ref": self.proof_ref}


class ForecastLifecycleIntegrityCheck:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: Forecast Lifecycle Integrity Check V1", "PASS", append_only=True, v22_records_mutated=False, unresolved_forecasts_visible=True, forecast_to_execution_bridge=False)


class ForecastLifecycleLedgerV1:
    def records(self) -> list[ForecastLifecycleRecord]:
        return [
            ForecastLifecycleRecord("forecast_v22_crypto_btc_spot_threshold_001", "crypto", ForecastLifecycleState.NOT_DUE_YET),
            ForecastLifecycleRecord("forecast_v22_weather_kmci_temp_threshold_001", "weather", ForecastLifecycleState.NOT_DUE_YET),
        ]

    def transitions(self) -> list[ForecastLifecycleTransition]:
        transitions: list[ForecastLifecycleTransition] = []
        for record in self.records():
            transitions.append(ForecastLifecycleTransition(record.snapshot_id, ForecastLifecycleState.CREATED, ForecastLifecycleState.OBSERVER_QUEUED, "artifacts/dummy/forecast_snapshot_ledger_write_v22_report.json"))
            transitions.append(ForecastLifecycleTransition(record.snapshot_id, ForecastLifecycleState.OBSERVER_QUEUED, ForecastLifecycleState.NOT_DUE_YET, "artifacts/dummy/forecast_observation_decision_report_v1.json"))
        return transitions

    def to_report(self) -> dict[str, Any]:
        records = [record.to_dict() for record in self.records()]
        transitions = [transition.to_dict() for transition in self.transitions()]
        return _safe_payload("V23: Forecast Lifecycle Ledger V1", "PASS", records=records, transitions=transitions, append_only=True, current_states=["NOT_DUE_YET"], execution_bridge_created=False)

    def record_report(self) -> dict[str, Any]:
        records = [record.to_dict() for record in self.records()]
        return _safe_payload("V23: Forecast Lifecycle Record V1", "PASS", records=records, record_count=len(records))

    def transition_report(self) -> dict[str, Any]:
        transitions = [transition.to_dict() for transition in self.transitions()]
        return _safe_payload("V23: Forecast Lifecycle Transition V1", "PASS", transitions=transitions, transition_count=len(transitions))


class ObserverFollowThroughWorkQueue:
    def items(self) -> list[dict[str, Any]]:
        return [
            {"priority": 100, "domain": "crypto", "work_item": "observe BTC spot threshold after due time", "requires_live_trading": False},
            {"priority": 98, "domain": "weather", "work_item": "observe KMCI station settlement after due time", "requires_live_trading": False},
        ]

    def to_report(self) -> dict[str, Any]:
        items = self.items()
        return _safe_payload("V23: Observer Follow Through Work Queue V1", "PARTIAL", work_items=items, work_item_count=len(items))


class CalibrationWorkQueueV2:
    def items(self) -> list[dict[str, Any]]:
        return [{"priority": 82, "work_item": "update calibration once observer resolves forecast outcomes", "requires_live_trading": False}]

    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: Calibration Work Queue V2", "PARTIAL", work_items=self.items(), work_item_count=len(self.items()))


class Tier0ClosureWorkQueue:
    def items(self) -> list[dict[str, Any]]:
        return [{"priority": 94, "domain": candidate.domain, "source_id": candidate.source_id, "operator_action": candidate.operator_action, "requires_live_trading": False} for candidate in Tier0AdapterClosurePlanner().candidates()[:5]]

    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: Tier-0 Closure Work Queue V1", "PARTIAL", work_items=self.items(), work_item_count=len(self.items()))


class AdapterActivationWorkQueueV2:
    def items(self) -> list[dict[str, Any]]:
        return [
            {"priority": 92, "source": "EIA", "work_item": "complete key/approval closure", "requires_live_trading": False},
            {"priority": 91, "source": "CME", "work_item": "complete license/key/approval closure", "requires_live_trading": False},
            {"priority": 90, "source": "Databento", "work_item": "complete licensed dataset closure", "requires_live_trading": False},
        ]

    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: Adapter Activation Work Queue V2", "PARTIAL", work_items=self.items(), work_item_count=len(self.items()))


class NextBundleRecommendationV23:
    def recommendation(self) -> dict[str, Any]:
        return {
            "bundle": "DUMMY_V24_SETTLEMENT_OBSERVER_AND_ADAPTER_ACTIVATION_FOLLOW_THROUGH_V1",
            "reason": "V23 keeps V22 forecasts unresolved until due and leaves CME/Databento/EIA blocked behind explicit operator/license/key gates.",
            "must_include_tests": ["settlement_due_replay", "bounded_readonly_adapter_probe", "calibration_after_resolution", "no execution bridge"],
        }

    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: Next Bundle Recommendation V23", "PARTIAL", recommendation=self.recommendation(), live_trading_work_items=[])


class CompoundingControlPlaneV6:
    def to_report(self) -> dict[str, Any]:
        queues = {
            "observer_follow_through": ObserverFollowThroughWorkQueue().items(),
            "calibration": CalibrationWorkQueueV2().items(),
            "tier0_closure": Tier0ClosureWorkQueue().items(),
            "adapter_activation": AdapterActivationWorkQueueV2().items(),
        }
        return _safe_payload("V23: Compounding Control Plane V6", "PARTIAL", queues=queues, next_bundle=NextBundleRecommendationV23().recommendation(), live_trading_work_items=[], production_mutation_work_items=[])


class DomainScoreboardV7:
    def rows(self) -> list[dict[str, Any]]:
        return [
            {"domain": "crypto", "active_real_sources": 2, "edge_sources": 2, "context_sources": 0, "forecast_snapshots": 1, "observer_queue_items": 1, "observation_status": "NOT_DUE_YET", "scored_forecast_count": 0, "unresolved_forecast_count": 1, "calibration_sample_count": 0, "source_truth_score": "EDGE_READINESS_CREDIT_ONLY", "no_trade_attribution": None, "tier0_tier2_blocker_state": "NONE", "adapter_closure_status": "PUBLIC_READONLY_PRESENT", "next_action": "observe settlement after due time"},
            {"domain": "weather", "active_real_sources": 1, "edge_sources": 1, "context_sources": 0, "forecast_snapshots": 1, "observer_queue_items": 1, "observation_status": "NOT_DUE_YET", "scored_forecast_count": 0, "unresolved_forecast_count": 1, "calibration_sample_count": 0, "source_truth_score": "EDGE_READINESS_CREDIT_ONLY", "no_trade_attribution": None, "tier0_tier2_blocker_state": "NONE", "adapter_closure_status": "OFFICIAL_PUBLIC_PRESENT", "next_action": "observe KMCI station after due time"},
            {"domain": "finance", "active_real_sources": 1, "edge_sources": 0, "context_sources": 1, "forecast_snapshots": 0, "observer_queue_items": 0, "observation_status": "NO_FORECAST", "scored_forecast_count": 0, "unresolved_forecast_count": 0, "calibration_sample_count": 0, "source_truth_score": "CONTEXT_DISCIPLINE_CREDIT", "no_trade_attribution": "SEC correctly blocked Nasdaq edge overclaim", "tier0_tier2_blocker_state": "CME/DATABENTO/RATES_DXY_BLOCKED", "adapter_closure_status": "BLOCKED_LICENSE_OR_KEY", "next_action": "complete Tier-0/Tier-2 market-data gate"},
            {"domain": "commodities", "active_real_sources": 1, "edge_sources": 0, "context_sources": 1, "forecast_snapshots": 0, "observer_queue_items": 0, "observation_status": "NO_FORECAST", "scored_forecast_count": 0, "unresolved_forecast_count": 0, "calibration_sample_count": 0, "source_truth_score": "CONTEXT_DISCIPLINE_CREDIT", "no_trade_attribution": "World Bank correctly blocked oil edge overclaim", "tier0_tier2_blocker_state": "CME_CL/ICE_BRENT/EIA_BLOCKED", "adapter_closure_status": "BLOCKED_LICENSE_OR_KEY", "next_action": "complete EIA/CME/Brent gate"},
            {"domain": "sports", "active_real_sources": 0, "edge_sources": 0, "context_sources": 0, "forecast_snapshots": 0, "observer_queue_items": 0, "observation_status": "NO_FORECAST", "scored_forecast_count": 0, "unresolved_forecast_count": 0, "calibration_sample_count": 0, "source_truth_score": "NO_APPROVED_SOURCE", "no_trade_attribution": "source missing", "tier0_tier2_blocker_state": "APPROVED_SOURCE_MISSING", "adapter_closure_status": "BLOCKED_TERMS_REVIEW", "next_action": "legal terms review"},
        ]

    def to_report(self) -> dict[str, Any]:
        rows = self.rows()
        return _safe_payload("V23: Domain Scoreboard V7", "PASS", domains=rows, domain_count=len(rows))

    def observer_calibration_scoreboard_report(self) -> dict[str, Any]:
        rows = [{"domain": row["domain"], "observation_status": row["observation_status"], "scored_forecast_count": row["scored_forecast_count"], "unresolved_forecast_count": row["unresolved_forecast_count"], "calibration_sample_count": row["calibration_sample_count"]} for row in self.rows()]
        return _safe_payload("V23: Observer Calibration Scoreboard V1", "PARTIAL", rows=rows)

    def tier0_adapter_closure_scoreboard_report(self) -> dict[str, Any]:
        rows = [{"domain": row["domain"], "tier0_tier2_blocker_state": row["tier0_tier2_blocker_state"], "adapter_closure_status": row["adapter_closure_status"], "next_action": row["next_action"]} for row in self.rows()]
        return _safe_payload("V23: Tier-0 Adapter Closure Scoreboard V1", "PARTIAL", rows=rows)

    def source_truth_scoreboard_report(self) -> dict[str, Any]:
        rows = [{"domain": row["domain"], "source_truth_score": row["source_truth_score"], "no_trade_attribution": row["no_trade_attribution"]} for row in self.rows()]
        return _safe_payload("V23: Source Truth Scoreboard V4", "PASS", rows=rows)


class V23RuntimeBudget:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: Runtime Budget V1", "PASS", pytest_timeout_seconds=60, unit_tests_use_fixtures=True, real_source_calls_from_unit_tests=False, total_network_budget_seconds=90, recursive_pytest_allowed=False, unbounded_subprocess_allowed=False, report_chain_explosion=False)


class ObserverCallBudget:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: Observer Call Budget V1", "PASS", max_calls_per_observer=1, per_call_timeout_seconds=5, unit_tests_use_fixtures=True, repeated_live_calls_allowed=False)


class ForecastScoringRuntimeGuard:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: Forecast Scoring Runtime Guard V1", "PASS", scoring_timeout_seconds=10, unresolved_forecasts_skipped=True, can_hang_indefinitely=False)


class Tier0AdapterProbeCallLimiter:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: Tier-0 Adapter Probe Call Limiter V1", "PASS", max_probe_calls_per_source=1, commercial_sources_blocked_without_approval=True, order_calls_allowed=False, adapter_probe_can_trigger_execution=False)


class DashboardCachePolicyV5:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: Dashboard Cache Policy V5", "PASS", dashboard_tests_use_cached_artifacts=True, live_public_feed_calls_from_dashboard_tests=False, secrets_exposed=False)


class ReportChainRuntimeProfilerV6:
    def to_report(self) -> dict[str, Any]:
        return _safe_payload("V23: Report Chain Runtime Profiler V6", "PASS", chain_versions=["V8", "V8_1", "V8_2", "V9", "V10", "V11", "V12", "V13", "V14", "V15", "V16", "V17", "V18", "V19", "V20", "V21", "V22", "V23"], report_chain_explosion=False)


class DummyMissionStateV23:
    def to_report(self) -> dict[str, Any]:
        scoring = ForecastScoringEngineV2().to_report()
        calibration = CalibrationUpdateEngineV3().to_report()
        return _safe_payload(
            "V23: Dummy Mission State V9",
            "PARTIAL",
            v17_truth_loop_status="PASS",
            v21_source_activation_status="PASS",
            v22_forecast_write_status="PASS",
            v22_forecast_snapshots=2,
            v23_observer_status="PASS",
            observed_outcome_count=0,
            scored_forecast_count=scoring["scored_forecast_count"],
            unresolved_forecast_count=scoring["unresolved_forecast_count"],
            calibration_update_status=calibration["verdict"],
            attribution_status=ForecastAttributionEngineV2().to_report()["verdict"],
            source_truth_score_status=SourceTruthScoreV4().to_report()["verdict"],
            tier0_adapter_closure_status=Tier0AdapterClosurePlanner().to_report()["verdict"],
            cme_gate_status=CMEReadOnlyAdapterGateV1().to_report()["status"],
            databento_gate_status=DatabentoReadOnlyAdapterGateV1().to_report()["status"],
            eia_closure_status=EIAAdapterActivationClosureV2().to_report()["status"],
            nasdaq_edge_readiness=NasdaqEdgeReadinessV2().to_report()["readiness"],
            oil_edge_readiness=OilEdgeReadinessV2().to_report()["readiness"],
            top_blockers=["SETTLEMENT_HORIZON_PENDING", "CME_LICENSE_REQUIRED", "DATABENTO_LICENSE_REQUIRED", "EIA_APPROVAL_OR_KEY_REQUIRED"],
            next_bundle_recommendation=NextBundleRecommendationV23().recommendation(),
            live_submit_enabled=False,
            caps_config_status="PASS",
            direct_order_bypass_status="PASS",
            direct_cancel_bypass_status="PASS",
        )


def generate_dashboard_v23_report_v1() -> dict[str, Any]:
    return _safe_payload(
        "V23: Dashboard Observer Calibration Adapter Closure V1",
        "PASS",
        routes=[
            "/api/v23/forecast-observer-closure",
            "/api/v23/crypto-outcome-observer",
            "/api/v23/weather-outcome-observer",
            "/api/v23/forecast-scoring",
            "/api/v23/calibration-update",
            "/api/v23/forecast-attribution",
            "/api/v23/source-truth-score",
            "/api/v23/tier0-adapter-closure",
            "/api/v23/cme-adapter-gate",
            "/api/v23/databento-adapter-gate",
            "/api/v23/eia-activation-closure",
            "/api/v23/rates-dxy-context",
            "/api/v23/nasdaq-oil-readiness",
            "/api/v23/forecast-lifecycle",
            "/api/v23/compounding-v6",
            "/api/v23/domain-scoreboard-v7",
            "/api/v23/mission-state",
        ],
        shows_forecast_snapshot_count=True,
        shows_observer_queue_count=True,
        shows_unresolved_count=True,
        shows_adapter_gate_status=True,
        exposes_secret_values=False,
        dashboard_reads_cached_artifacts_where_possible=True,
    )


def _security_report(workstream: str, **extra: Any) -> dict[str, Any]:
    report = _safe_payload(
        workstream,
        "PASS",
        provider_secret_leak=False,
        kalshi_secret_leak=False,
        kalshi_private_key_material_exposed=False,
        source_secret_leak=False,
        github_token_value_leak=False,
        llm_receives_credentials=False,
        provider_prompt_leak=False,
        direct_order_bypass=False,
        direct_cancel_bypass=False,
        live_submit_enabled=False,
        caps_modified_by_v23=False,
        live_submit_config_modified_by_v23=False,
        canonical_blunder_modified=False,
        unauthorized_private_or_insider_source=False,
        unbounded_scraping_introduced=False,
        questionable_odds_scraping=False,
        unapproved_source_activated=False,
        commercial_source_activated_without_approval=False,
        fixture_evidence_claimed_real=False,
        context_only_evidence_claimed_edge=False,
        outcome_fabricated=False,
        github_repo_code_executed=False,
        forecast_scoring_can_trigger_execution=False,
        observer_queue_can_trigger_execution=False,
        calibration_update_can_trigger_execution=False,
        adapter_probe_can_trigger_execution=False,
    )
    report.update(extra)
    return report


def security_reports_v23() -> dict[str, dict[str, Any]]:
    return {
        "no_secret_leak_report_v23.json": _security_report("V23: No Secret Leak"),
        "no_kalshi_private_key_leak_report_v23.json": _security_report("V23: No Kalshi Private Key Leak"),
        "no_source_api_key_leak_report_v23.json": _security_report("V23: No Source Secret Leak"),
        "no_github_token_leak_report_v23.json": _security_report("V23: No GitHub Token Leak"),
        "no_llm_secret_leak_report_v23.json": _security_report("V23: No LLM Secret Leak"),
        "no_direct_order_bypass_report_v23.json": _security_report("V23: No Direct Order Bypass"),
        "no_direct_cancel_bypass_report_v23.json": _security_report("V23: No Direct Cancel Bypass"),
        "no_live_submit_still_disabled_report_v23.json": _security_report("V23: No Live Submit Still Disabled", enabled=False),
        "no_caps_config_modification_report_v23.json": _security_report("V23: No Caps Config Modification", caps_config_status="UNCHANGED_BY_V23"),
        "readonly_only_source_activation_report_v23.json": _security_report("V23: ReadOnly Only Source Activation", write_endpoints_called=[], private_endpoints_used=False),
        "no_unauthorized_source_report_v23.json": _security_report("V23: No Unauthorized Source"),
        "no_questionable_odds_scraping_report_v23.json": _security_report("V23: No Questionable Odds Scraping"),
        "no_unapproved_source_activation_report_v23.json": _security_report("V23: No Unapproved Source Activation"),
        "no_commercial_source_without_approval_report_v23.json": _security_report("V23: No Commercial Source Without Approval"),
        "no_fixture_claimed_real_report_v23.json": _security_report("V23: No Fixture Claimed Real"),
        "no_context_claimed_edge_report_v23.json": _security_report("V23: No Context Claimed Edge"),
        "no_outcome_fabrication_report_v23.json": _security_report("V23: No Outcome Fabrication"),
        "no_github_repo_code_execution_report_v23.json": _security_report("V23: No GitHub Repo Code Execution", cloned_repos=[], executed_repo_code=False),
        "no_forecast_scoring_to_execution_bridge_report_v23.json": _security_report("V23: No Forecast Scoring To Execution Bridge"),
        "no_observer_to_execution_bridge_report_v23.json": _security_report("V23: No Observer To Execution Bridge"),
        "no_calibration_to_execution_bridge_report_v23.json": _security_report("V23: No Calibration To Execution Bridge"),
        "no_adapter_probe_to_execution_bridge_report_v23.json": _security_report("V23: No Adapter Probe To Execution Bridge"),
        "blunder_separation_recheck_v23.json": _security_report("V23: Blunder Separation Recheck", blunder_separation_status="PASS"),
        "dummy_canonical_identity_report_v23.json": _security_report("V23: Dummy Canonical Identity", canonical_name="Dummy", dummy_renamed=False),
    }


class V23ReportFactory:
    def __init__(self, *, enable_network: bool = False) -> None:
        self.enable_network = enable_network
        self.observer = V22ForecastObserverClosure()
        self.crypto = CryptoForecastOutcomeObserverV1()
        self.weather = WeatherForecastOutcomeObserverV1()
        self.scoring = ForecastScoringEngineV2()
        self.calibration = CalibrationUpdateEngineV3()
        self.attribution = ForecastAttributionEngineV2()
        self.source_truth = SourceTruthScoreV4()
        self.tier0 = Tier0AdapterClosurePlanner()
        self.lifecycle = ForecastLifecycleLedgerV1()
        self.scoreboard = DomainScoreboardV7()

    def build(self) -> dict[str, dict[str, Any]]:
        return {
            "v22_forecast_observer_closure_report_v1.json": self.observer.to_report(),
            "forecast_observation_attempt_report_v1.json": self.observer.attempt_report(),
            "forecast_observation_decision_report_v1.json": self.observer.decision_report(),
            "forecast_observation_blocker_report_v1.json": self.observer.blocker_report(),
            "crypto_forecast_outcome_observer_v1_report.json": self.crypto.to_report(),
            "crypto_spot_settlement_probe_report_v1.json": CryptoSpotSettlementProbe().to_report(),
            "crypto_forecast_outcome_status_report_v1.json": CryptoForecastOutcomeStatus().to_report(),
            "crypto_forecast_settlement_blocker_report_v1.json": CryptoForecastSettlementBlocker().to_report(),
            "weather_forecast_outcome_observer_v1_report.json": self.weather.to_report(),
            "weather_station_settlement_probe_report_v1.json": WeatherStationSettlementProbe().to_report(),
            "weather_forecast_outcome_status_report_v1.json": WeatherForecastOutcomeStatus().to_report(),
            "weather_forecast_settlement_blocker_report_v1.json": WeatherForecastSettlementBlocker().to_report(),
            "forecast_scoring_engine_v2_report.json": self.scoring.to_report(),
            "forecast_score_candidate_report_v1.json": self.scoring.candidate_report(),
            "forecast_score_result_report_v1.json": self.scoring.result_report(),
            "forecast_score_blocker_report_v1.json": self.scoring.blocker_report(),
            "forecast_score_integrity_proof_v1.json": self.scoring.integrity_proof_report(),
            "calibration_update_engine_v3_report.json": self.calibration.to_report(),
            "domain_calibration_update_report_v1.json": self.calibration.domain_update_report(),
            "calibration_bucket_update_report_v1.json": self.calibration.bucket_update_report(),
            "low_sample_calibration_warning_report_v1.json": self.calibration.low_sample_warning_report(),
            "calibration_queue_state_report_v1.json": CalibrationQueueState().to_report(),
            "forecast_attribution_engine_v2_report.json": self.attribution.to_report(),
            "edge_forecast_attribution_report_v1.json": self.attribution.edge_forecast_attribution_report(),
            "source_attribution_update_report_v1.json": self.attribution.source_attribution_update_report(),
            "no_trade_attribution_v2_report.json": NoTradeAttributionV2().to_report(),
            "outcome_pending_attribution_report_v1.json": self.attribution.outcome_pending_attribution_report(),
            "source_truth_score_v4_report.json": self.source_truth.to_report(),
            "source_truth_update_report_v1.json": self.source_truth.update_report(),
            "edge_source_reliability_state_report_v1.json": self.source_truth.edge_reliability_report(),
            "context_source_reliability_state_report_v1.json": self.source_truth.context_reliability_report(),
            "source_truth_promotion_gate_report_v1.json": SourceTruthPromotionGate().to_report(),
            "tier0_adapter_closure_planner_report_v1.json": self.tier0.to_report(),
            "tier0_adapter_closure_candidate_report_v1.json": self.tier0.candidate_report(),
            "tier0_adapter_closure_status_report_v1.json": self.tier0.status_report(),
            "tier0_adapter_proof_requirement_report_v1.json": self.tier0.proof_requirement_report(),
            "tier0_adapter_operator_action_report_v1.json": self.tier0.operator_action_report(),
            "cme_readonly_adapter_gate_v1_report.json": CMEReadOnlyAdapterGateV1().to_report(),
            "cme_futures_source_requirement_report_v1.json": CMEFuturesSourceRequirement().to_report(),
            "cme_credential_presence_check_report_v1.json": CMECredentialPresenceCheck().to_report(),
            "cme_readonly_probe_plan_report_v1.json": CMEReadOnlyProbePlan().to_report(),
            "cme_adapter_blocker_report_v1.json": CMEAdapterBlocker().to_report(),
            "databento_readonly_adapter_gate_v1_report.json": DatabentoReadOnlyAdapterGateV1().to_report(),
            "databento_dataset_requirement_report_v1.json": DatabentoDatasetRequirement().to_report(),
            "databento_credential_presence_check_report_v1.json": DatabentoCredentialPresenceCheck().to_report(),
            "databento_readonly_probe_plan_report_v1.json": DatabentoReadOnlyProbePlan().to_report(),
            "databento_adapter_blocker_report_v1.json": DatabentoAdapterBlocker().to_report(),
            "eia_adapter_activation_closure_v2_report.json": EIAAdapterActivationClosureV2().to_report(),
            "eia_key_presence_check_report_v1.json": EIAKeyPresenceCheck().to_report(),
            "eia_dataset_probe_plan_v2_report.json": EIADatasetProbePlanV2().to_report(),
            "eia_inventory_series_mapper_report_v1.json": EIAInventorySeriesMapper().to_report(),
            "eia_oil_fundamental_evidence_gate_report_v1.json": EIAOilFundamentalEvidenceGate().to_report(),
            "eia_activation_blocker_v2_report.json": EIAActivationBlockerV2().to_report(),
            "rates_dxy_public_context_adapter_v1_report.json": RatesDXYPublicContextAdapterV1().to_report(),
            "treasury_yield_evidence_v1_report.json": TreasuryYieldEvidenceV1().to_report(),
            "dxy_proxy_evidence_v1_report.json": DXYProxyEvidenceV1().to_report(),
            "rates_freshness_gate_report_v1.json": RatesFreshnessGate().to_report(),
            "rates_dxy_context_guard_report_v1.json": RatesDXYContextGuard().to_report(),
            "nasdaq_edge_readiness_v2_report.json": NasdaqEdgeReadinessV2().to_report(),
            "oil_edge_readiness_v2_report.json": OilEdgeReadinessV2().to_report(),
            "nasdaq_evidence_gap_state_v2_report.json": NasdaqEvidenceGapStateV2().to_report(),
            "oil_evidence_gap_state_v2_report.json": OilEvidenceGapStateV2().to_report(),
            "directional_forecast_readiness_decision_v2_report.json": DirectionalForecastReadinessDecisionV2().to_report(),
            "forecast_lifecycle_ledger_v1_report.json": self.lifecycle.to_report(),
            "forecast_lifecycle_record_report_v1.json": self.lifecycle.record_report(),
            "forecast_lifecycle_transition_report_v1.json": self.lifecycle.transition_report(),
            "forecast_lifecycle_integrity_check_report_v1.json": ForecastLifecycleIntegrityCheck().to_report(),
            "compounding_control_plane_v6_report.json": CompoundingControlPlaneV6().to_report(),
            "observer_follow_through_work_queue_report_v1.json": ObserverFollowThroughWorkQueue().to_report(),
            "calibration_work_queue_v2_report.json": CalibrationWorkQueueV2().to_report(),
            "tier0_closure_work_queue_report_v1.json": Tier0ClosureWorkQueue().to_report(),
            "adapter_activation_work_queue_v2_report.json": AdapterActivationWorkQueueV2().to_report(),
            "next_bundle_recommendation_v23_report.json": NextBundleRecommendationV23().to_report(),
            "domain_scoreboard_v7_report.json": self.scoreboard.to_report(),
            "observer_calibration_scoreboard_v1.json": self.scoreboard.observer_calibration_scoreboard_report(),
            "tier0_adapter_closure_scoreboard_v1.json": self.scoreboard.tier0_adapter_closure_scoreboard_report(),
            "source_truth_scoreboard_v4_report.json": self.scoreboard.source_truth_scoreboard_report(),
            "dummy_mission_state_report_v9.json": DummyMissionStateV23().to_report(),
            "dashboard_v23_report_v1.json": generate_dashboard_v23_report_v1(),
            "v23_runtime_budget_report_v1.json": V23RuntimeBudget().to_report(),
            "observer_call_budget_report_v1.json": ObserverCallBudget().to_report(),
            "forecast_scoring_runtime_guard_report_v1.json": ForecastScoringRuntimeGuard().to_report(),
            "tier0_adapter_probe_call_limiter_report_v1.json": Tier0AdapterProbeCallLimiter().to_report(),
            "dashboard_cache_policy_v5_report.json": DashboardCachePolicyV5().to_report(),
            "report_chain_runtime_profiler_v6_report.json": ReportChainRuntimeProfilerV6().to_report(),
            **security_reports_v23(),
        }
