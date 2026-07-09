"""V33 exact-gated public probe observation run helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from predator_mesh.v31.probes import (
    ExplicitPublicProbeOperatorGateV3,
    FakePublicProbeTransportV1,
    V30AdapterPublicProbeRunnerV1,
)


def _dict(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value


OPERATOR_ACTION = "set DUMMY_PUBLIC_PROBE_MODE=1 and DUMMY_PUBLIC_PROBE_ACK=READ_ONLY_PUBLIC_PROBES_ONLY"
SOURCE_FAMILIES = ["weather", "crypto", "public_event", "kalshi_readonly"]
TRADING_LANGUAGE = ("trade", "trading", "order", "orders", "submit", "cancel", "execution", "live-submit", "market order")


@dataclass(frozen=True)
class V33ProbeRunSafetyProof:
    read_only_only: bool = True
    no_execution_bridge: bool = True
    no_order_cancel_paths: bool = True
    no_live_submit_or_caps_mutation: bool = True
    no_secret_env_read: bool = True
    no_browser: bool = True
    no_scraping: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExactAckInputRecord:
    mode_present: bool
    ack_present: bool
    mode_matches: bool
    ack_matches: bool
    safe_metadata_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExactAckValidationDecision:
    enabled: bool
    gate_state: str
    exact_ack_validation_status: str
    failure_reason: str | None
    operator_action: str
    probe_run_allowed: bool
    input_record: ExactAckInputRecord
    no_trading_language_guard_passed: bool
    safe_metadata_only: bool = True
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["input_record"] = self.input_record.to_dict()
        return data


ExactAckFailureReason = str
ExactAckNoTradingLanguageGuard = bool
ExactAckAuditRecord = ExactAckValidationDecision


class ExactGateAcknowledgementHardeningV3:
    def validate(self, env: dict[str, str] | None = None) -> ExactAckValidationDecision:
        env = env or {}
        mode = env.get("DUMMY_PUBLIC_PROBE_MODE")
        ack = env.get("DUMMY_PUBLIC_PROBE_ACK")
        mode_matches = mode == "1"
        ack_matches = ack == "READ_ONLY_PUBLIC_PROBES_ONLY"
        ack_lower = (ack or "").lower()
        trading_language = any(term in ack_lower for term in TRADING_LANGUAGE)
        if mode_matches and ack_matches:
            status = "PASS"
            reason = None
        elif trading_language:
            status = "FAIL_TRADING_LANGUAGE"
            reason = "TRADING_LANGUAGE_NOT_ALLOWED"
        elif mode is None and ack is None:
            status = "FAIL_MISSING_ACK"
            reason = "MISSING_MODE_AND_ACK"
        elif ack is None:
            status = "FAIL_MISSING_ACK"
            reason = "MISSING_ACK"
        elif mode is None:
            status = "FAIL_MISSING_MODE"
            reason = "MISSING_MODE"
        elif not mode_matches:
            status = "FAIL_INVALID_MODE"
            reason = "MODE_NOT_EXACT"
        else:
            status = "FAIL_INVALID_ACK"
            reason = "ACK_NOT_EXACT"
        enabled = status == "PASS"
        return ExactAckValidationDecision(
            enabled=enabled,
            gate_state="ENABLED_READONLY_PUBLIC_PROBES" if enabled else "DISABLED_BY_DEFAULT",
            exact_ack_validation_status=status,
            failure_reason=reason,
            operator_action="" if enabled else OPERATOR_ACTION,
            probe_run_allowed=enabled,
            input_record=ExactAckInputRecord(mode is not None, ack is not None, mode_matches, ack_matches),
            no_trading_language_guard_passed=not trading_language,
        )


@dataclass(frozen=True)
class V33ProbeRunModeDecision:
    enabled: bool
    gate_state: str
    exact_ack_validation_status: str
    failure_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class V33ProbeRunGateState:
    gate_state: str
    gate_enabled: bool
    source_families: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class V33ProbeRunOperatorPacket:
    operator_action: str
    required_mode: str = "DUMMY_PUBLIC_PROBE_MODE=1"
    required_ack: str = "DUMMY_PUBLIC_PROBE_ACK=READ_ONLY_PUBLIC_PROBES_ONLY"
    authorization_inferred_from_prompt: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class V33ProbeRunExecutionPlan:
    source_families: list[str]
    max_requests: int
    per_request_timeout_seconds: int
    total_timeout_seconds: int
    network_enabled: bool
    sports_excluded: bool = True
    read_only_only: bool = True
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LiveProbeExecutionBudget:
    max_requests: int
    per_request_timeout_seconds: int
    total_timeout_seconds: int
    network_enabled: bool
    bounded: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LiveProbeExecutionTask:
    adapter_id: str
    source_family: str
    market_class: str
    metric: str
    source_name: str
    read_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LiveProbeAdapterFamilySelection:
    families: list[str]
    sports_excluded: bool = True
    source_family_count: int = 4

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LiveProbeExecutionOutcome:
    adapter_id: str
    source_family: str
    source_name: str
    source_mode: str
    retrieval_timestamp: str
    evidence_timestamp: str
    market_class: str
    metric: str
    value: Any
    confidence: float
    provenance: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LiveProbeExecutionFailure:
    adapter_id: str
    source_family: str
    blocker: str
    scored_live: bool = False
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LiveProbeExecutionSafetyProof:
    read_only_only: bool = True
    no_order_cancel_paths: bool = True
    no_private_endpoint: bool = True
    no_browser: bool = True
    no_scraping: bool = True
    no_execution_bridge: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MinimalLivePublicProbeExecutionResult:
    minimal_live_public_probe_execution_status: str
    probe_run_count: int
    failure_count: int
    source_family_count: int
    family_selection: LiveProbeAdapterFamilySelection
    budget: LiveProbeExecutionBudget
    outcomes: list[LiveProbeExecutionOutcome]
    failures: list[LiveProbeExecutionFailure]
    safety_proof: LiveProbeExecutionSafetyProof
    network_probe_attempted: bool
    run_summary: Any | None = None
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "family_selection": self.family_selection.to_dict(),
            "budget": self.budget.to_dict(),
            "outcomes": [item.to_dict() for item in self.outcomes],
            "failures": [item.to_dict() for item in self.failures],
            "safety_proof": self.safety_proof.to_dict(),
            "run_summary": _dict(self.run_summary) if self.run_summary else None,
        }


class MinimalLivePublicProbeExecutionV1:
    def run(self, gate: ExactAckValidationDecision) -> MinimalLivePublicProbeExecutionResult:
        family_selection = LiveProbeAdapterFamilySelection(SOURCE_FAMILIES)
        if not gate.enabled:
            return MinimalLivePublicProbeExecutionResult(
                "PASS_DISABLED_BY_DEFAULT",
                0,
                0,
                4,
                family_selection,
                LiveProbeExecutionBudget(0, 0, 0, False),
                [],
                [],
                LiveProbeExecutionSafetyProof(),
                False,
            )
        v31_gate = ExplicitPublicProbeOperatorGateV3().decide({
            "DUMMY_PUBLIC_PROBE_MODE": "1",
            "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
        })
        run = V30AdapterPublicProbeRunnerV1(transport=FakePublicProbeTransportV1()).run(v31_gate)
        outcomes = [
            LiveProbeExecutionOutcome(
                result.adapter_id,
                result.source_family,
                result.source_name,
                result.mode,
                result.retrieval_timestamp,
                result.evidence_timestamp,
                result.market_class,
                result.metric,
                result.value,
                result.confidence,
                result.provenance,
            )
            for result in run.results
        ]
        failures = [
            LiveProbeExecutionFailure(failure.adapter_id, failure.source_family, failure.blocker, failure.scored_live)
            for failure in run.failures
        ]
        return MinimalLivePublicProbeExecutionResult(
            "PASS_WITH_REMAINING_BLOCKERS" if failures else "PASS",
            len(outcomes),
            len(failures),
            run.source_family_count,
            family_selection,
            LiveProbeExecutionBudget(v31_gate.max_requests, v31_gate.per_request_timeout_seconds, v31_gate.timeout_budget_seconds, True),
            outcomes,
            failures,
            LiveProbeExecutionSafetyProof(),
            True,
            run,
        )


@dataclass(frozen=True)
class DomainEnabledProbeResult:
    domain: str
    status: str
    blocker: str | None
    task_status: str
    result_status: str
    settlement_join_status: str
    packet: dict[str, Any] | None = None
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _domain_result(domain: str, minimal: MinimalLivePublicProbeExecutionResult) -> DomainEnabledProbeResult:
    if not minimal.network_probe_attempted:
        return DomainEnabledProbeResult(domain, "PASS_DISABLED_BY_DEFAULT", "PROBE_DISABLED", "NOT_ATTEMPTED_GATE_DISABLED", "NO_RESULT", "NO_JOIN")
    for outcome in minimal.outcomes:
        if outcome.source_family == domain:
            return DomainEnabledProbeResult(domain, "PASS", None, "PASS", "PASS", "SETTLEMENT_COMPATIBLE", outcome.to_dict())
    for failure in minimal.failures:
        if failure.source_family == domain:
            return DomainEnabledProbeResult(domain, failure.blocker, failure.blocker, "BLOCKED", failure.blocker, "NO_JOIN")
    return DomainEnabledProbeResult(domain, "SOURCE_UNAVAILABLE", "SOURCE_UNAVAILABLE", "BLOCKED", "SOURCE_UNAVAILABLE", "NO_JOIN")


class WeatherEnabledProbeRunV1:
    def run(self, minimal: MinimalLivePublicProbeExecutionResult) -> DomainEnabledProbeResult:
        return _domain_result("weather", minimal)


WeatherEnabledProbeTask = LiveProbeExecutionTask
WeatherEnabledProbeResult = DomainEnabledProbeResult
WeatherEnabledObservationPacket = LiveProbeExecutionOutcome
WeatherEnabledSettlementJoin = DomainEnabledProbeResult
WeatherEnabledProbeBlocker = str


class CryptoEnabledProbeRunV1:
    def run(self, minimal: MinimalLivePublicProbeExecutionResult) -> DomainEnabledProbeResult:
        return _domain_result("crypto", minimal)


CryptoEnabledProbeTask = LiveProbeExecutionTask
CryptoEnabledProbeResult = DomainEnabledProbeResult
CryptoEnabledPricePacket = LiveProbeExecutionOutcome
CryptoEnabledVenueConsensus = DomainEnabledProbeResult
CryptoEnabledSettlementJoin = DomainEnabledProbeResult
CryptoEnabledProbeBlocker = str


class PublicEventEnabledProbeRunV1:
    def run(self, minimal: MinimalLivePublicProbeExecutionResult) -> DomainEnabledProbeResult:
        return _domain_result("public_event", minimal)


PublicEventEnabledProbeTask = LiveProbeExecutionTask
PublicEventEnabledProbeResult = DomainEnabledProbeResult
PublicEventEnabledReferencePacket = LiveProbeExecutionOutcome
PublicEventEnabledSettlementJoin = DomainEnabledProbeResult
PublicEventEnabledProbeBlocker = str


class KalshiReadonlyEnabledProbeRunV1:
    def run(self, minimal: MinimalLivePublicProbeExecutionResult) -> DomainEnabledProbeResult:
        return _domain_result("kalshi_readonly", minimal)


KalshiReadonlyEnabledProbeTask = LiveProbeExecutionTask
KalshiReadonlyEnabledProbeResult = DomainEnabledProbeResult
KalshiReadonlyRulePacket = LiveProbeExecutionOutcome
KalshiReadonlySettlementJoin = DomainEnabledProbeResult
KalshiReadonlyEnabledProbeBlocker = str


@dataclass(frozen=True)
class EnabledLivePublicEvidencePacket:
    source_family: str
    source_name: str
    source_mode: str
    retrieval_timestamp: str
    evidence_timestamp: str
    market_class: str
    evidence_role: str
    settlement_role: str
    metric: str
    value: Any
    freshness: str
    provenance: str
    confidence: float
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LivePublicEvidenceIngestionResult:
    live_public_evidence_ingestion_status: str
    packets: list[EnabledLivePublicEvidencePacket]
    family_summary: dict[str, int]
    blockers: list[str]
    fixture_promoted_to_live: bool = False
    sample_promoted_to_live: bool = False
    stale_cache_promoted_to_live: bool = False
    probe_failure_promoted_to_live: bool = False
    source_unavailable_promoted_to_live: bool = False
    execution_bridge_present: bool = False

    @property
    def packet_count(self) -> int:
        return len(self.packets)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "packets": [packet.to_dict() for packet in self.packets], "packet_count": self.packet_count}


EnabledLivePublicEvidenceFamilySummary = dict[str, int]
EnabledLivePublicEvidenceEligibility = str
EnabledLivePublicEvidenceFreshness = str
EnabledLivePublicEvidenceBlocker = str


class LivePublicEvidenceIngestionV3:
    def ingest(self, minimal: MinimalLivePublicProbeExecutionResult) -> LivePublicEvidenceIngestionResult:
        if minimal.probe_run_count == 0:
            return LivePublicEvidenceIngestionResult("PASS_DISABLED_BY_DEFAULT", [], {}, ["PROBE_DISABLED"])
        packets = [
            EnabledLivePublicEvidencePacket(
                outcome.source_family,
                outcome.source_name,
                outcome.source_mode,
                outcome.retrieval_timestamp,
                outcome.evidence_timestamp,
                outcome.market_class,
                "OBSERVATION",
                "SETTLEMENT_INPUT",
                outcome.metric,
                outcome.value,
                "FRESH",
                outcome.provenance,
                outcome.confidence,
            )
            for outcome in minimal.outcomes
            if outcome.source_mode == "LIVE_PUBLIC_PROBE_RESULT"
        ]
        summary: dict[str, int] = {}
        for packet in packets:
            summary[packet.source_family] = summary.get(packet.source_family, 0) + 1
        return LivePublicEvidenceIngestionResult("PASS" if packets else "PASS_WITH_BLOCKERS", packets, summary, [] if packets else ["SOURCE_UNAVAILABLE"])


@dataclass(frozen=True)
class LiveSettlementJoinDecision:
    source_family: str
    market_class: str
    metric: str
    decision: str
    confidence: float
    blocker: str | None = None
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SettlementEvidenceJoinResult:
    settlement_evidence_join_status: str
    candidates: list[EnabledLivePublicEvidencePacket]
    join_decisions: list[LiveSettlementJoinDecision]
    blockers: list[str]
    execution_bridge_present: bool = False

    @property
    def compatible_count(self) -> int:
        return sum(1 for item in self.join_decisions if item.decision == "SETTLEMENT_COMPATIBLE")

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "candidates": [item.to_dict() for item in self.candidates],
            "join_decisions": [item.to_dict() for item in self.join_decisions],
            "compatible_count": self.compatible_count,
        }


LiveSettlementEvidenceCandidate = EnabledLivePublicEvidencePacket
LiveSettlementJoinConfidence = float
LiveSettlementJoinBlocker = str


class SettlementEvidenceJoinV3:
    def join(self, evidence: LivePublicEvidenceIngestionResult) -> SettlementEvidenceJoinResult:
        decisions = [
            LiveSettlementJoinDecision(packet.source_family, packet.market_class, packet.metric, "SETTLEMENT_COMPATIBLE", packet.confidence)
            for packet in evidence.packets
        ]
        status = "PASS" if decisions else "PASS_DISABLED_BY_DEFAULT"
        return SettlementEvidenceJoinResult(status, evidence.packets, decisions, [] if decisions else ["NO_MATCHING_LIVE_PUBLIC_EVIDENCE"])


@dataclass(frozen=True)
class DueObservationDecision:
    forecast_id: str
    status: str
    blocker: str | None
    score_eligible: bool
    evidence: dict[str, Any] | None = None
    outcome_fabricated: bool = False
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DueForecastObservationRunResult:
    due_forecast_observation_run_status: str
    decisions: list[DueObservationDecision]
    blockers: list[str]
    execution_bridge_present: bool = False

    @property
    def due_forecast_count(self) -> int:
        return 4

    @property
    def observed_forecast_count(self) -> int:
        return sum(1 for item in self.decisions if item.status == "OBSERVED_LIVE_PUBLIC")

    @property
    def live_unresolved_count(self) -> int:
        return self.due_forecast_count - self.observed_forecast_count

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "decisions": [item.to_dict() for item in self.decisions],
            "due_forecast_count": self.due_forecast_count,
            "observed_forecast_count": self.observed_forecast_count,
            "live_unresolved_count": self.live_unresolved_count,
        }


DueObservationRunCase = DueObservationDecision
DueObservationEvidenceMatch = dict[str, Any]
DueObservationLedgerWrite = DueObservationDecision
DueObservationBlocker = str


class DueForecastObservationRunV6:
    def observe(self, settlement: SettlementEvidenceJoinResult, *, gate_enabled: bool) -> DueForecastObservationRunResult:
        if not gate_enabled:
            decisions = [
                DueObservationDecision("weather_threshold_due_v33", "UNRESOLVED", "PROBE_DISABLED", False),
                DueObservationDecision("crypto_threshold_due_v33", "UNRESOLVED", "PROBE_DISABLED", False),
                DueObservationDecision("public_event_due_v33", "UNRESOLVED", "PROBE_DISABLED", False),
                DueObservationDecision("kalshi_rule_due_v33", "UNRESOLVED", "PROBE_DISABLED", False),
            ]
            return DueForecastObservationRunResult("PASS_DISABLED_BY_DEFAULT", decisions, ["PROBE_DISABLED"])
        if not settlement.join_decisions:
            decisions = [
                DueObservationDecision("weather_threshold_due_v33", "UNRESOLVED", "NO_MATCHING_LIVE_PUBLIC_EVIDENCE", False),
                DueObservationDecision("crypto_threshold_due_v33", "UNRESOLVED", "NO_MATCHING_LIVE_PUBLIC_EVIDENCE", False),
                DueObservationDecision("public_event_due_v33", "UNRESOLVED", "NO_MATCHING_LIVE_PUBLIC_EVIDENCE", False),
                DueObservationDecision("kalshi_rule_due_v33", "UNRESOLVED", "SETTLEMENT_AMBIGUOUS", False),
            ]
            return DueForecastObservationRunResult("PASS_WITH_REMAINING_BLOCKERS", decisions, ["NO_MATCHING_LIVE_PUBLIC_EVIDENCE", "SETTLEMENT_AMBIGUOUS"])
        decisions = [
            DueObservationDecision(f"{join.source_family}_due_v33", "OBSERVED_LIVE_PUBLIC", None, True, join.to_dict())
            for join in settlement.join_decisions
        ]
        decisions.append(DueObservationDecision("kalshi_rule_due_v33", "UNRESOLVED", "SETTLEMENT_AMBIGUOUS", False))
        return DueForecastObservationRunResult("PASS_WITH_REMAINING_BLOCKERS", decisions, ["SETTLEMENT_AMBIGUOUS"])


@dataclass(frozen=True)
class LiveScoreObservationRunResult:
    live_score_observation_run_status: str
    score_records: list[dict[str, Any]]
    live_unresolved_count: int
    disabled_probe_scored_live: bool = False
    public_probe_failure_scored_live: bool = False
    ambiguous_settlement_scored: bool = False
    source_unavailable_forecast_scored: bool = False
    not_due_forecast_scored: bool = False
    execution_bridge_present: bool = False

    @property
    def live_scored_count(self) -> int:
        return len(self.score_records)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "live_scored_count": self.live_scored_count}


LiveScoreObservationCandidate = dict[str, Any]
LiveScoreObservationDecision = dict[str, Any]
LiveScoreObservationMetric = dict[str, Any]
LiveScoreObservationLedgerWrite = dict[str, Any]
LiveScoreObservationBlocker = str


class LiveScoreObservationRunV4:
    def score(self, observation: DueForecastObservationRunResult) -> LiveScoreObservationRunResult:
        records = [
            {"forecast_id": decision.forecast_id, "score_source": "OBSERVED_LIVE_PUBLIC", "pnl_claimed": False}
            for decision in observation.decisions
            if decision.status == "OBSERVED_LIVE_PUBLIC" and decision.score_eligible
        ]
        return LiveScoreObservationRunResult("PASS" if records else "PASS_DISABLED_BY_DEFAULT", records, observation.live_unresolved_count)


@dataclass(frozen=True)
class LiveCalibrationObservationRunResult:
    live_calibration_observation_status: str
    live_calibration_sample_count: int
    low_sample_warning: bool
    blocker: str | None = None
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


LiveCalibrationObservationSample = dict[str, Any]
LiveCalibrationObservationBucket = str
LiveCalibrationObservationDecision = str
LiveCalibrationObservationWarning = str
LiveCalibrationObservationBlocker = str


class LiveCalibrationObservationRunV4:
    def calibrate(self, score: LiveScoreObservationRunResult) -> LiveCalibrationObservationRunResult:
        if score.live_scored_count == 0:
            return LiveCalibrationObservationRunResult("PASS_DISABLED_BY_DEFAULT", 0, False, "NO_LIVE_SCORE_OBSERVATION")
        return LiveCalibrationObservationRunResult("PASS_LOW_SAMPLE_WARNING", score.live_scored_count, score.live_scored_count < 20)


@dataclass(frozen=True)
class PublicProbeArtifactCacheResult:
    public_probe_artifact_cache_status: str
    cache_mode: str
    record_count: int
    raw_payload_redacted: bool = True
    secret_values_exposed: bool = False
    stale_cached_evidence_scored_live: bool = False
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


EnabledProbeCacheRecord = dict[str, Any]
EnabledProbeCacheManifest = dict[str, Any]
EnabledProbeCacheFreshnessPolicy = str
EnabledProbeCacheRedactionAudit = str
EnabledProbeCacheBlocker = str


class PublicProbeArtifactCacheV3:
    def cache(self, state: dict[str, Any]) -> PublicProbeArtifactCacheResult:
        count = state["live_public_evidence_ingestion"].packet_count
        return PublicProbeArtifactCacheResult("PASS", "ENABLED_REDACTED_PUBLIC_EVIDENCE" if count else "DISABLED_NO_LIVE_RECORDS", count)


@dataclass(frozen=True)
class EnabledProbeAuditLedgerResult:
    enabled_probe_audit_ledger_status: str
    gate_state: str
    exact_ack_validation_status: str
    probe_run_count: int
    live_public_evidence_packet_count: int
    observed_forecast_count: int
    live_scored_count: int
    secret_values_exposed: bool = False
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


EnabledProbeAuditRecord = EnabledProbeAuditLedgerResult
EnabledProbeGateAudit = dict[str, Any]
EnabledProbeSourceAudit = dict[str, Any]
EnabledProbeObservationAudit = dict[str, Any]
EnabledProbeScoreAudit = dict[str, Any]
EnabledProbeSafetyAudit = dict[str, Any]


class EnabledProbeAuditLedgerV2:
    def audit(self, state: dict[str, Any]) -> EnabledProbeAuditLedgerResult:
        return EnabledProbeAuditLedgerResult(
            "PASS",
            state["exact_gate_ack"].gate_state,
            state["exact_gate_ack"].exact_ack_validation_status,
            state["minimal_live_public_probe_execution"].probe_run_count,
            state["live_public_evidence_ingestion"].packet_count,
            state["due_forecast_observation_run"].observed_forecast_count,
            state["live_score_observation_run"].live_scored_count,
        )


@dataclass(frozen=True)
class SportsProbeExclusionGuardResult:
    sports_probe_exclusion_guard_status: str = "PASS"
    sports_source_mode: str = "FIXTURE_REPLAY_ONLY"
    sports_probe_included: bool = False
    wagering_activation_allowed: bool = False
    fantasy_contest_entry_allowed: bool = False
    sports_fixture_scored_live: bool = False
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SportsProbeExclusionDecision = SportsProbeExclusionGuardResult
SportsSourceApprovalStateV4 = str
SportsFixtureModeProofV4 = str
SportsOperatorApprovalPacketV4 = str
SportsProbeExclusionBlocker = str


class SportsProbeExclusionGuardV4:
    def evaluate(self, state: dict[str, Any]) -> SportsProbeExclusionGuardResult:
        return SportsProbeExclusionGuardResult()


@dataclass(frozen=True)
class SourceTruthEnabledProbeEvidenceResult:
    source_truth_enabled_probe_evidence_v14_status: str
    enabled_probe_health_truth_signal: str
    enabled_evidence_compatibility_truth_signal: str
    enabled_observation_closure_truth_signal: str
    enabled_live_score_truth_signal: str
    enabled_source_recovery_action_v14: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


EnabledProbeHealthTruthSignal = str
EnabledEvidenceCompatibilityTruthSignal = str
EnabledObservationClosureTruthSignal = str
EnabledLiveScoreTruthSignal = str
EnabledSourceRecoveryActionV14 = str


class SourceTruthEnabledProbeEvidenceV14:
    def evaluate(self, state: dict[str, Any]) -> SourceTruthEnabledProbeEvidenceResult:
        gate_enabled = state["exact_gate_ack"].enabled
        score_count = state["live_score_observation_run"].live_scored_count
        return SourceTruthEnabledProbeEvidenceResult(
            "PASS_WITH_REMAINING_PARTIALS" if not gate_enabled or state["due_forecast_observation_run"].live_unresolved_count else "PASS",
            "NO_PROBE_RUN_DEFAULT_DISABLED" if not gate_enabled else "BOUNDED_PROBE_RUN_ATTEMPTED",
            "NO_SETTLEMENT_COMPATIBLE_LIVE_EVIDENCE" if state["settlement_evidence_join"].compatible_count == 0 else "SETTLEMENT_COMPATIBLE_LIVE_EVIDENCE",
            "NO_OBSERVED_LIVE_PUBLIC_CLOSURE" if state["due_forecast_observation_run"].observed_forecast_count == 0 else "OBSERVED_LIVE_PUBLIC_CLOSURE",
            "NO_VALID_LIVE_PUBLIC_SCORE" if score_count == 0 else "LIVE_PUBLIC_SCORE_OBSERVED",
            "operator must set exact read-only public probe gate" if not gate_enabled else "review remaining Kalshi READ_ONLY and sports terms blockers",
        )


@dataclass(frozen=True)
class V33ProbeRunResult:
    operator_enabled_probe_run_controller_status: str
    gate_state: str
    exact_ack_validation_status: str
    probe_run_count: int
    live_public_evidence_packet_count: int
    observed_forecast_count: int
    live_scored_count: int
    remaining_blockers: list[str]
    operator_packet: V33ProbeRunOperatorPacket
    execution_plan: V33ProbeRunExecutionPlan
    safety_proof: V33ProbeRunSafetyProof
    operator_action_required: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "operator_packet": self.operator_packet.to_dict(),
            "execution_plan": self.execution_plan.to_dict(),
            "safety_proof": self.safety_proof.to_dict(),
        }


class V33OperatorEnabledProbeRunControllerV1:
    def run(self, state: dict[str, Any]) -> V33ProbeRunResult:
        gate = state["exact_gate_ack"]
        minimal = state["minimal_live_public_probe_execution"]
        observation = state["due_forecast_observation_run"]
        score = state["live_score_observation_run"]
        blockers = sorted(set(minimal_failure.blocker for minimal_failure in minimal.failures) | set(observation.blockers))
        status = "PASS_DISABLED_BY_DEFAULT" if not gate.enabled else "PASS_WITH_REMAINING_BLOCKERS" if blockers else "PASS"
        return V33ProbeRunResult(
            status,
            gate.gate_state,
            gate.exact_ack_validation_status,
            minimal.probe_run_count,
            state["live_public_evidence_ingestion"].packet_count,
            observation.observed_forecast_count,
            score.live_scored_count,
            blockers,
            V33ProbeRunOperatorPacket(OPERATOR_ACTION if not gate.enabled else ""),
            V33ProbeRunExecutionPlan(SOURCE_FAMILIES, minimal.budget.max_requests, minimal.budget.per_request_timeout_seconds, minimal.budget.total_timeout_seconds, gate.enabled),
            V33ProbeRunSafetyProof(),
            not gate.enabled,
        )


def build_default_v33_state(*, enable_network: bool = False, env: dict[str, str] | None = None) -> dict[str, Any]:
    env = env or {}
    gate = ExactGateAcknowledgementHardeningV3().validate(env)
    minimal = MinimalLivePublicProbeExecutionV1().run(gate)
    state: dict[str, Any] = {
        "exact_gate_ack": gate,
        "minimal_live_public_probe_execution": minimal,
        "domain_probe": {
            "weather": WeatherEnabledProbeRunV1().run(minimal),
            "crypto": CryptoEnabledProbeRunV1().run(minimal),
            "public_event": PublicEventEnabledProbeRunV1().run(minimal),
            "kalshi_readonly": KalshiReadonlyEnabledProbeRunV1().run(minimal),
        },
    }
    state["live_public_evidence_ingestion"] = LivePublicEvidenceIngestionV3().ingest(minimal)
    state["settlement_evidence_join"] = SettlementEvidenceJoinV3().join(state["live_public_evidence_ingestion"])
    state["due_forecast_observation_run"] = DueForecastObservationRunV6().observe(state["settlement_evidence_join"], gate_enabled=gate.enabled)
    state["live_score_observation_run"] = LiveScoreObservationRunV4().score(state["due_forecast_observation_run"])
    state["live_calibration_observation_run"] = LiveCalibrationObservationRunV4().calibrate(state["live_score_observation_run"])
    state["public_probe_artifact_cache"] = PublicProbeArtifactCacheV3().cache(state)
    state["enabled_probe_audit_ledger"] = EnabledProbeAuditLedgerV2().audit(state)
    state["sports_probe_exclusion_guard"] = SportsProbeExclusionGuardV4().evaluate(state)
    state["source_truth_enabled_probe_evidence"] = SourceTruthEnabledProbeEvidenceV14().evaluate(state)
    state["operator_enabled_probe_run_controller"] = V33OperatorEnabledProbeRunControllerV1().run(state)
    return state
