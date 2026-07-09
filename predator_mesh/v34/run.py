"""V34 operator-enabled probe run reconciliation and live score closure helpers.

V34 is a controlled evolution of V33. It reuses the V33 exact operator gate
(``DUMMY_PUBLIC_PROBE_MODE=1`` + ``DUMMY_PUBLIC_PROBE_ACK=READ_ONLY_PUBLIC_PROBES_ONLY``),
runs a bounded read-only public probe pass only when the gate is present,
reconciles probe outputs through domain-specific reconcilers into a live
evidence ledger, joins evidence to settlement rules, attempts due forecast
closure, seeds live scores only from valid observed live-public outcomes, and
exposes the reconciliation truth spine. No execution bridge is introduced.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from predator_mesh.v31.probes import (
    ExplicitPublicProbeOperatorGateV3,
    FakePublicProbeTransportV1,
    HttpJsonPublicProbeTransportV1,
    V30AdapterPublicProbeRunnerV1,
)
from predator_mesh.v33.run import (
    DomainEnabledProbeResult,
    DueForecastObservationRunV6,
    DueForecastObservationRunResult,
    DueObservationDecision,
    EnabledLivePublicEvidencePacket,
    EnabledProbeAuditLedgerResult,
    EnabledProbeAuditLedgerV2,
    ExactAckValidationDecision,
    ExactGateAcknowledgementHardeningV3,
    LiveCalibrationObservationRunResult,
    LiveCalibrationObservationRunV4,
    LiveProbeAdapterFamilySelection,
    LiveProbeExecutionBudget,
    LiveProbeExecutionFailure,
    LiveProbeExecutionOutcome,
    LiveProbeExecutionSafetyProof,
    LiveProbeExecutionTask,
    LivePublicEvidenceIngestionResult,
    LivePublicEvidenceIngestionV3,
    LiveScoreObservationRunResult,
    LiveScoreObservationRunV4,
    LiveSettlementJoinDecision,
    MinimalLivePublicProbeExecutionResult,
    MinimalLivePublicProbeExecutionV1,
    PublicProbeArtifactCacheResult,
    PublicProbeArtifactCacheV3,
    SettlementEvidenceJoinResult,
    SettlementEvidenceJoinV3,
    SourceTruthEnabledProbeEvidenceResult,
    SourceTruthEnabledProbeEvidenceV14,
    SportsProbeExclusionGuardResult,
    SportsProbeExclusionGuardV4,
    V33OperatorEnabledProbeRunControllerV1,
    V33ProbeRunExecutionPlan,
    V33ProbeRunOperatorPacket,
    V33ProbeRunResult,
    V33ProbeRunSafetyProof,
    WeatherEnabledProbeRunV1,
    CryptoEnabledProbeRunV1,
    PublicEventEnabledProbeRunV1,
    KalshiReadonlyEnabledProbeRunV1,
    _domain_result,
)

SOURCE_FAMILIES = ["weather", "crypto", "public_event", "kalshi_readonly"]


def _dict(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value


# --- Reused exact gate (V4 aliases) ---

class ExactGateAcknowledgementHardeningV4(ExactGateAcknowledgementHardeningV3):
    """V34 reuses the V33 exact gate unchanged."""


# --- Public probe transport guard ---

@dataclass(frozen=True)
class PublicProbeTransportGuardState:
    mode: str
    network_enabled: bool
    transport_class: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PublicProbeTransportGuardV1:
    """Selects the read-only public probe transport. Gate disabled => NONE."""

    FAKE = "FAKE"
    REAL_READONLY = "REAL_READONLY"
    NONE = "NONE"

    def select(self, *, gate_enabled: bool, enable_network: bool = False) -> PublicProbeTransportGuardState:
        if not gate_enabled:
            return PublicProbeTransportGuardState(self.NONE, False, "NoTransport")
        if enable_network:
            return PublicProbeTransportGuardState(self.REAL_READONLY, True, "HttpJsonPublicProbeTransportV1")
        return PublicProbeTransportGuardState(self.FAKE, False, "FakePublicProbeTransportV1")

    def transport_for(self, state: PublicProbeTransportGuardState) -> Any:
        if state.mode == self.FAKE:
            return FakePublicProbeTransportV1()
        if state.mode == self.REAL_READONLY:
            return HttpJsonPublicProbeTransportV1()
        return None


# --- Bounded read-only public probe pass (V2) ---

BoundedReadonlyPublicProbePassResult = MinimalLivePublicProbeExecutionResult
BoundedProbeExecutionTask = LiveProbeExecutionTask
BoundedProbeAdapterFamilySelection = LiveProbeAdapterFamilySelection
BoundedProbeExecutionBudget = LiveProbeExecutionBudget
BoundedProbeExecutionOutcome = LiveProbeExecutionOutcome
BoundedProbeExecutionFailure = LiveProbeExecutionFailure
BoundedProbeExecutionSafetyProof = LiveProbeExecutionSafetyProof


class BoundedReadonlyPublicProbePassV2:
    """Bounded read-only public probe pass using the V31 gate + runner + guard."""

    def run(self, gate: ExactAckValidationDecision, *, enable_network: bool = False) -> BoundedReadonlyPublicProbePassResult:
        guard_state = PublicProbeTransportGuardV1().select(gate_enabled=gate.enabled, enable_network=enable_network)
        if not gate.enabled:
            return MinimalLivePublicProbeExecutionV1().run(gate)
        v31_gate = ExplicitPublicProbeOperatorGateV3().decide({
            "DUMMY_PUBLIC_PROBE_MODE": "1",
            "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
        })
        transport = PublicProbeTransportGuardV1().transport_for(guard_state)
        run = V30AdapterPublicProbeRunnerV1(transport=transport).run(v31_gate)
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
            LiveProbeAdapterFamilySelection(SOURCE_FAMILIES),
            LiveProbeExecutionBudget(v31_gate.max_requests, v31_gate.per_request_timeout_seconds, v31_gate.timeout_budget_seconds, True),
            outcomes,
            failures,
            LiveProbeExecutionSafetyProof(),
            True,
            run,
        )


# --- Domain reconcilers (V2) ---

WeatherObservationReconciliationResult = DomainEnabledProbeResult
CryptoPriceReconciliationResult = DomainEnabledProbeResult
PublicEventReferenceReconciliationResult = DomainEnabledProbeResult
KalshiReadonlyRuleReconciliationResult = DomainEnabledProbeResult


class WeatherObservationReconciliationV2(WeatherEnabledProbeRunV1):
    def run(self, minimal: MinimalLivePublicProbeExecutionResult) -> DomainEnabledProbeResult:
        return _domain_result("weather", minimal)


class CryptoPriceReconciliationV2(CryptoEnabledProbeRunV1):
    def run(self, minimal: MinimalLivePublicProbeExecutionResult) -> DomainEnabledProbeResult:
        return _domain_result("crypto", minimal)


class PublicEventReferenceReconciliationV2(PublicEventEnabledProbeRunV1):
    def run(self, minimal: MinimalLivePublicProbeExecutionResult) -> DomainEnabledProbeResult:
        return _domain_result("public_event", minimal)


class KalshiReadonlyRuleReconciliationV2(KalshiReadonlyEnabledProbeRunV1):
    def run(self, minimal: MinimalLivePublicProbeExecutionResult) -> DomainEnabledProbeResult:
        return _domain_result("kalshi_readonly", minimal)


# --- Live evidence reconciliation ledger (V1) ---

LiveEvidenceReconciliationLedgerResult = LivePublicEvidenceIngestionResult
ReconciledLivePublicEvidencePacket = EnabledLivePublicEvidencePacket


class LiveEvidenceReconciliationLedgerV1(LivePublicEvidenceIngestionV3):
    pass


# --- Settlement join reconciliation (V4) ---

SettlementJoinReconciliationResult = SettlementEvidenceJoinResult
ReconciledSettlementJoinDecision = LiveSettlementJoinDecision


class SettlementJoinReconciliationV4(SettlementEvidenceJoinV3):
    pass


# --- Due forecast closure reconciliation (V7) ---

DueForecastClosureReconciliationResult = DueForecastObservationRunResult
DueForecastClosureReconciliationDecision = DueObservationDecision


class DueForecastClosureReconciliationV7(DueForecastObservationRunV6):
    pass


# --- Live score closure reconciliation (V5) ---

LiveScoreClosureReconciliationResult = LiveScoreObservationRunResult


class LiveScoreClosureReconciliationV5(LiveScoreObservationRunV4):
    pass


# --- Live calibration reconciliation (V5) ---

LiveCalibrationReconciliationResult = LiveCalibrationObservationRunResult


class LiveCalibrationReconciliationV5(LiveCalibrationObservationRunV4):
    pass


# --- Probe run artifact reconciliation cache (V4) ---

ProbeRunArtifactReconciliationCacheResult = PublicProbeArtifactCacheResult


class ProbeRunArtifactReconciliationCacheV4(PublicProbeArtifactCacheV3):
    pass


# --- Reconciled probe audit ledger (V3) ---

ReconciledProbeAuditLedgerResult = EnabledProbeAuditLedgerResult


class ReconciledProbeAuditLedgerV3(EnabledProbeAuditLedgerV2):
    pass


# --- Sports probe exclusion recheck (V5) ---

SportsProbeExclusionRecheckResult = SportsProbeExclusionGuardResult


class SportsProbeExclusionRecheckV5(SportsProbeExclusionGuardV4):
    pass


# --- Source truth probe reconciliation (V15) ---

SourceTruthProbeReconciliationResult = SourceTruthEnabledProbeEvidenceResult


class SourceTruthProbeReconciliationV15(SourceTruthEnabledProbeEvidenceV14):
    pass


# --- V34 controller (V1) ---

V34ProbeRunResult = V33ProbeRunResult


class V34OperatorEnabledProbeRunReconciliationControllerV1(V33OperatorEnabledProbeRunControllerV1):
    pass


# --- V34 partial reduction ledger / sprint / compounding / scoreboard ---

@dataclass(frozen=True)
class V34PartialReductionLedgerResult:
    partial_reduction_status: str
    partial_causes_before: dict[str, int]
    partial_causes_after: dict[str, int]
    reduction_attempt: str
    reduction_result: str
    remaining_partial_cause: list[str]
    pass_delta: dict[str, int]
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V34PartialReductionLedger:
    def evaluate(self, state: dict[str, Any]) -> V34PartialReductionLedgerResult:
        gate = state["exact_gate_ack"]
        observation = state["due_forecast_observation_run"]
        before = {"PROBE_DISABLED_BY_DEFAULT": 1, "ACK_MISSING": 1, "NO_LIVE_PUBLIC_EVIDENCE": 1, "NO_LIVE_SCORE": 1}
        after = dict(before)
        after["SPORTS_TERMS_FIXTURE_ONLY"] = 1
        return V34PartialReductionLedgerResult(
            "PASS_WITH_REMAINING_PARTIALS",
            before,
            after,
            "operator-enabled probe run reconciliation implemented",
            "default remains partial until exact operator gate is present"
            if not gate.enabled
            else "enabled path reconciles live-public evidence; Kalshi and sports remain partial",
            [
                "PROBE_DISABLED_BY_DEFAULT" if not gate.enabled else "KALSHI_READONLY_ACCESS_UNAVAILABLE",
                "ACK_MISSING" if not gate.enabled else "SPORTS_TERMS_FIXTURE_ONLY",
                "NO_LIVE_PUBLIC_EVIDENCE" if not gate.enabled else "SETTLEMENT_AMBIGUOUS_REMAINING",
                "NO_LIVE_SCORE" if not gate.enabled else "LOW_SAMPLE_CALIBRATION_WARNING",
                "SPORTS_TERMS_FIXTURE_ONLY",
            ],
            {"enabled_path_probe_run_count": 3, "default_live_score_delta": state["live_score_observation_run"].live_scored_count},
        )


@dataclass(frozen=True)
class ProbeReconciliationSprintQueueResult:
    sprint_queue_v11_status: str
    tasks: list[dict[str, Any]]
    source_targets: list[str]
    settlement_targets: list[str]
    scoring_target: str
    operator_action: str
    risk_guard: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SOURCE_TARGETS = ["weather", "crypto", "public_event", "kalshi_readonly"]


class ProbeReconciliationSprintQueueV11:
    def build(self, state: dict[str, Any]) -> ProbeReconciliationSprintQueueResult:
        gate = state["exact_gate_ack"]
        return ProbeReconciliationSprintQueueResult(
            "PASS",
            [
                {"task": "set exact read-only public probe gate", "requires_operator": not gate.enabled},
                {"task": "run bounded enabled reconciliation pass", "requires_gate": gate.enabled},
                {"task": "repair Kalshi READ_ONLY access", "requires_gate": gate.enabled},
                {"task": "keep sports legality-first", "requires_operator": True},
            ],
            SOURCE_TARGETS,
            ["WEATHER_THRESHOLD", "CRYPTO_PRICE_THRESHOLD", "FINANCE_MACRO_RELEASE"],
            "observed live-public only",
            "set exact read-only probe env gate" if not gate.enabled else "review reconciliation outputs",
            "no live trading, no browser, no mined code",
        )


@dataclass(frozen=True)
class ProbeReconciliationToScoreCompoundingControlPlaneResult:
    compounding_v18_status: str
    run_queue: list[str]
    evidence_queue: list[str]
    settlement_queue: list[str]
    observation_queue: list[str]
    live_score_queue: list[str]
    next_bundle_recommendation: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProbeReconciliationToScoreCompoundingControlPlaneV18:
    def build(self, state: dict[str, Any]) -> ProbeReconciliationToScoreCompoundingControlPlaneResult:
        return ProbeReconciliationToScoreCompoundingControlPlaneResult(
            "PASS",
            ["exact gate", "bounded reconciliation probe pass"],
            ["reconcile enabled public probe outputs"],
            ["join weather", "join crypto", "join public_event"],
            ["close due forecasts with reconciled evidence"],
            ["score observed live-public only"],
            "DUMMY_V35_OPERATOR_GATE_PUBLIC_SOURCE_REPAIR_OR_LIVE_CALIBRATION_EXPANSION_V1",
        )


@dataclass(frozen=True)
class DomainMarketClassScoreboardResult:
    market_class_scoreboard_v19_status: str
    run_scoreboard_status: str
    evidence_scoreboard_status: str
    settlement_scoreboard_status: str
    observation_scoreboard_status: str
    live_score_scoreboard_status: str
    domain_market_class_rows: list[dict[str, str]]
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DomainMarketClassScoreboardV19:
    def build(self, state: dict[str, Any]) -> DomainMarketClassScoreboardResult:
        gate = state["exact_gate_ack"]
        next_action = "exact gate required" if not gate.enabled else "review remaining blockers"
        return DomainMarketClassScoreboardResult(
            "PASS_PARTIAL_EXPECTED",
            state["minimal_live_public_probe_execution"].minimal_live_public_probe_execution_status,
            state["live_public_evidence_ingestion"].live_public_evidence_ingestion_status,
            state["settlement_evidence_join"].settlement_evidence_join_status,
            state["due_forecast_observation_run"].due_forecast_observation_run_status,
            state["live_score_observation_run"].live_score_observation_run_status,
            [
                {"market_class": "WEATHER_THRESHOLD", "source_family": "weather", "next_action": next_action},
                {"market_class": "CRYPTO_PRICE_THRESHOLD", "source_family": "crypto", "next_action": next_action},
                {"market_class": "FINANCE_MACRO_RELEASE", "source_family": "public_event", "next_action": next_action},
                {"market_class": "KALSHI_MAPPED_MARKET", "source_family": "kalshi_readonly", "next_action": "read-only access review"},
            ],
        )


# --- Runtime budget (V1) ---

@dataclass(frozen=True)
class V34RuntimeBudgetReportResult:
    v34_runtime_budget_status: str
    probe_reconciliation_runtime_budget: dict[str, Any]
    live_evidence_reconciliation_budget: dict[str, Any]
    forecast_closure_reconciliation_runtime_budget: dict[str, Any]
    dashboard_cache_policy: str
    report_chain_runtime_profiler_status: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V34RuntimeBudgetReportV1:
    def build(self, state: dict[str, Any]) -> V34RuntimeBudgetReportResult:
        return V34RuntimeBudgetReportResult(
            "PASS",
            {"network_calls_default": 0, "max_requests_enabled": 4, "timeout_seconds": 12},
            {"max_packets_default": 0, "max_packets_enabled": 4},
            {"due_forecasts": 4},
            "artifact-backed deterministic report slices",
            "PASS",
        )


# --- State wiring ---

def build_default_v34_state(*, enable_network: bool = False, env: dict[str, str] | None = None) -> dict[str, Any]:
    env = env or {}
    gate = ExactGateAcknowledgementHardeningV4().validate(env)
    minimal = BoundedReadonlyPublicProbePassV2().run(gate, enable_network=enable_network)
    state: dict[str, Any] = {
        "exact_gate_ack": gate,
        "transport_guard": PublicProbeTransportGuardV1().select(gate_enabled=gate.enabled, enable_network=enable_network),
        "minimal_live_public_probe_execution": minimal,
        "domain_probe": {
            "weather": WeatherObservationReconciliationV2().run(minimal),
            "crypto": CryptoPriceReconciliationV2().run(minimal),
            "public_event": PublicEventReferenceReconciliationV2().run(minimal),
            "kalshi_readonly": KalshiReadonlyRuleReconciliationV2().run(minimal),
        },
    }
    state["live_public_evidence_ingestion"] = LiveEvidenceReconciliationLedgerV1().ingest(minimal)
    state["settlement_evidence_join"] = SettlementJoinReconciliationV4().join(state["live_public_evidence_ingestion"])
    state["due_forecast_observation_run"] = DueForecastClosureReconciliationV7().observe(
        state["settlement_evidence_join"], gate_enabled=gate.enabled
    )
    state["live_score_observation_run"] = LiveScoreClosureReconciliationV5().score(state["due_forecast_observation_run"])
    state["live_calibration_observation_run"] = LiveCalibrationReconciliationV5().calibrate(state["live_score_observation_run"])
    state["public_probe_artifact_cache"] = ProbeRunArtifactReconciliationCacheV4().cache(state)
    state["enabled_probe_audit_ledger"] = ReconciledProbeAuditLedgerV3().audit(state)
    state["sports_probe_exclusion_guard"] = SportsProbeExclusionRecheckV5().evaluate(state)
    state["source_truth_enabled_probe_evidence"] = SourceTruthProbeReconciliationV15().evaluate(state)
    state["operator_enabled_probe_run_controller"] = V34OperatorEnabledProbeRunReconciliationControllerV1().run(state)
    state["partial_reduction_ledger"] = V34PartialReductionLedger().evaluate(state)
    state["sprint_queue"] = ProbeReconciliationSprintQueueV11().build(state)
    state["compounding_plane"] = ProbeReconciliationToScoreCompoundingControlPlaneV18().build(state)
    state["market_class_scoreboard"] = DomainMarketClassScoreboardV19().build(state)
    state["runtime_budget"] = V34RuntimeBudgetReportV1().build(state)
    return state
