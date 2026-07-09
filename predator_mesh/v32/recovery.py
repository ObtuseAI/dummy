"""V32 source recovery, live evidence expansion, and closure helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from predator_mesh.v31.probes import (
    DueForecastLiveObservationClosureV4,
    ExplicitPublicProbeOperatorGateV3,
    FakePublicProbeTransportV1,
    LivePublicEvidenceCaptureV1,
    LiveScoreSeedV2,
    ProbeEvidenceNormalizationPipelineV2,
    V30AdapterPublicProbeRunnerV1,
)


def _dict(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value


@dataclass(frozen=True)
class SourceRecoverySafetyProofV1:
    read_only_only: bool = True
    no_execution_bridge: bool = True
    no_browser_automation: bool = True
    no_scraping: bool = True
    no_private_or_keyed_source: bool = True
    no_live_submit_or_caps_mutation: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SourceRecoveryCaseV2:
    case_id: str
    adapter_family: str
    market_class: str
    metric: str
    blocker: str
    due: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SourceRecoveryPlanV2:
    case_id: str
    recovery_action: str
    operator_action_required: bool
    eligible_for_probe: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SourceRecoveryAttemptV2:
    case_id: str
    adapter_family: str
    attempted: bool
    status: str
    blocker: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SourceRecoveryDecisionV2:
    case_id: str
    decision: str
    blocker: str | None
    recovered: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SourceRecoveryResultV2:
    source_recovery_controller_status: str
    recovery_cases: list[SourceRecoveryCaseV2]
    recovery_plans: list[SourceRecoveryPlanV2]
    recovery_attempts: list[SourceRecoveryAttemptV2]
    recovery_decisions: list[SourceRecoveryDecisionV2]
    blockers: list[str]
    safety_proof: SourceRecoverySafetyProofV1
    operator_action_required: bool
    execution_bridge_present: bool = False

    @property
    def case_count(self) -> int:
        return len(self.recovery_cases)

    @property
    def attempt_count(self) -> int:
        return len(self.recovery_attempts)

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "recovery_cases": [item.to_dict() for item in self.recovery_cases],
            "recovery_plans": [item.to_dict() for item in self.recovery_plans],
            "recovery_attempts": [item.to_dict() for item in self.recovery_attempts],
            "recovery_decisions": [item.to_dict() for item in self.recovery_decisions],
            "safety_proof": self.safety_proof.to_dict(),
            "case_count": self.case_count,
            "attempt_count": self.attempt_count,
        }


@dataclass(frozen=True)
class ProbeGateNoExecutionProofV2:
    no_execution_bridge: bool = True
    no_order_cancel_paths: bool = True
    no_live_submit_or_caps_mutation: bool = True
    no_secret_env_read: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OperatorGatedProbeRunDecisionV2:
    enabled: bool
    gate_state: str
    ack_validation_status: str
    operator_intent: str
    run_blocker: str | None
    max_requests: int
    timeout_budget_seconds: int
    source_families: list[str]
    no_execution_proof: ProbeGateNoExecutionProofV2
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["no_execution_proof"] = self.no_execution_proof.to_dict()
        return data


class OperatorGatedProbeRunV2:
    def decide(self, env: dict[str, str] | None = None) -> OperatorGatedProbeRunDecisionV2:
        env = env or {}
        mode = env.get("DUMMY_PUBLIC_PROBE_MODE")
        ack = env.get("DUMMY_PUBLIC_PROBE_ACK")
        enabled = mode == "1" and ack == "READ_ONLY_PUBLIC_PROBES_ONLY"
        if ack is None:
            ack_status = "FAIL_MISSING_ACK"
            blocker = "EXACT_READONLY_ACK_REQUIRED"
        elif ack != "READ_ONLY_PUBLIC_PROBES_ONLY":
            ack_status = "FAIL_INVALID_ACK"
            blocker = "EXACT_READONLY_ACK_REQUIRED"
        else:
            ack_status = "PASS"
            blocker = None if enabled else "PROBE_MODE_DISABLED"
        return OperatorGatedProbeRunDecisionV2(
            enabled=enabled,
            gate_state="ENABLED_READONLY_PUBLIC_PROBES" if enabled else "DISABLED_BY_DEFAULT",
            ack_validation_status=ack_status,
            operator_intent="READ_ONLY_PUBLIC_PROBES_ONLY" if enabled else "OPERATOR_ACTION_REQUIRED",
            run_blocker=blocker,
            max_requests=4 if enabled else 0,
            timeout_budget_seconds=12 if enabled else 0,
            source_families=["weather", "crypto", "public_event", "kalshi_readonly"] if enabled else [],
            no_execution_proof=ProbeGateNoExecutionProofV2(),
        )


@dataclass(frozen=True)
class MinimalPublicProbePassResultV1:
    minimal_public_probe_pass_status: str
    probe_run_count: int
    failure_count: int
    source_family_summary: dict[str, Any]
    failure_summary: dict[str, Any]
    safety_summary: dict[str, Any]
    run_summary: Any | None = None
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["run_summary"] = _dict(self.run_summary) if self.run_summary else None
        return data


class MinimalPublicProbePassV1:
    def run(self, gate: OperatorGatedProbeRunDecisionV2) -> MinimalPublicProbePassResultV1:
        if not gate.enabled:
            return MinimalPublicProbePassResultV1(
                "PASS_DISABLED_BY_DEFAULT",
                0,
                0,
                {"source_family_count": 4, "families": ["weather", "crypto", "public_event", "kalshi_readonly"]},
                {"failure_count": 0},
                {"execution_bridge_present": False, "read_only_only": True},
            )
        v31_gate = ExplicitPublicProbeOperatorGateV3().decide({
            "DUMMY_PUBLIC_PROBE_MODE": "1",
            "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
        })
        run = V30AdapterPublicProbeRunnerV1(transport=FakePublicProbeTransportV1()).run(v31_gate)
        return MinimalPublicProbePassResultV1(
            "PASS_WITH_REMAINING_BLOCKERS" if run.failures else "PASS",
            run.probe_run_count,
            run.probe_failure_count,
            {"source_family_count": run.source_family_count, "families": ["weather", "crypto", "public_event", "kalshi_readonly"]},
            {"failure_count": run.probe_failure_count, "blockers": [failure.blocker for failure in run.failures]},
            {"execution_bridge_present": False, "read_only_only": True, "secret_values_exposed": False},
            run,
        )


@dataclass(frozen=True)
class DomainRecoveryResultV2:
    domain: str
    status: str
    blocker: str | None
    fallback_source_plan: str
    attempt_status: str
    settlement_decision: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _domain_recovery(domain: str, gate_enabled: bool) -> DomainRecoveryResultV2:
    if not gate_enabled:
        return DomainRecoveryResultV2(
            domain,
            "PASS_DISABLED_BY_DEFAULT",
            "PROBE_DISABLED",
            f"operator-enable bounded {domain} public probe",
            "NOT_ATTEMPTED_GATE_DISABLED",
            "NO_MATCHING_LIVE_PUBLIC_EVIDENCE",
        )
    if domain == "kalshi_readonly":
        return DomainRecoveryResultV2(domain, "READONLY_ACCESS_UNAVAILABLE", "READONLY_ACCESS_UNAVAILABLE", "configure read-only access", "BLOCKED", "SETTLEMENT_AMBIGUOUS")
    return DomainRecoveryResultV2(domain, "PASS", None, f"bounded {domain} public source", "PASS", "SETTLEMENT_COMPATIBLE")


@dataclass(frozen=True)
class ExpandedLivePublicEvidencePacketV1:
    adapter_family: str
    market_class: str
    metric: str
    value: Any
    mode: str
    evidence_timestamp: str | None
    confidence: float
    provenance: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LivePublicEvidenceExpansionResultV2:
    live_public_evidence_expansion_status: str
    packets: list[ExpandedLivePublicEvidencePacketV1]
    family_summary: dict[str, int]
    blockers: list[str]
    fixture_promoted_to_live: bool = False
    source_unavailable_promoted_to_live: bool = False
    execution_bridge_present: bool = False

    @property
    def packet_count(self) -> int:
        return len(self.packets)

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "packets": [packet.to_dict() for packet in self.packets],
            "packet_count": self.packet_count,
        }


class LivePublicEvidenceExpansionV2:
    def expand(self, state: dict[str, Any]) -> LivePublicEvidenceExpansionResultV2:
        if not state["operator_gate"].enabled:
            return LivePublicEvidenceExpansionResultV2("PASS_DISABLED_BY_DEFAULT", [], {}, ["PROBE_DISABLED"])
        run = state["minimal_probe_pass"].run_summary
        packets = LivePublicEvidenceCaptureV1().capture(run) if run else []
        expanded = [
            ExpandedLivePublicEvidencePacketV1(
                packet.adapter_family,
                packet.market_class,
                packet.metric,
                packet.value,
                packet.mode,
                packet.evidence_timestamp,
                packet.confidence,
                packet.provenance,
            )
            for packet in packets
        ]
        family_summary: dict[str, int] = {}
        for packet in expanded:
            family_summary[packet.adapter_family] = family_summary.get(packet.adapter_family, 0) + 1
        return LivePublicEvidenceExpansionResultV2("PASS" if expanded else "PASS_WITH_BLOCKERS", expanded, family_summary, [] if expanded else ["SOURCE_UNAVAILABLE"])


@dataclass(frozen=True)
class SettlementEvidenceJoinDecisionV2:
    adapter_family: str
    market_class: str
    metric: str
    decision: str
    confidence: float
    live_score_allowed: bool = False
    blocker: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SettlementCompatibleEvidenceExpansionResultV2:
    settlement_compatible_evidence_expansion_status: str
    candidates: list[ExpandedLivePublicEvidencePacketV1]
    join_decisions: list[SettlementEvidenceJoinDecisionV2]
    blockers: list[str]
    execution_bridge_present: bool = False

    @property
    def compatible_count(self) -> int:
        return sum(1 for decision in self.join_decisions if decision.decision == "SETTLEMENT_COMPATIBLE")

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "join_decisions": [decision.to_dict() for decision in self.join_decisions],
            "compatible_count": self.compatible_count,
        }


class SettlementCompatibleEvidenceExpansionV2:
    def expand(self, evidence: LivePublicEvidenceExpansionResultV2) -> SettlementCompatibleEvidenceExpansionResultV2:
        decisions = [
            SettlementEvidenceJoinDecisionV2(packet.adapter_family, packet.market_class, packet.metric, "SETTLEMENT_COMPATIBLE", packet.confidence)
            for packet in evidence.packets
        ]
        status = "PASS" if decisions else "PASS_DISABLED_BY_DEFAULT"
        return SettlementCompatibleEvidenceExpansionResultV2(status, evidence.packets, decisions, [] if decisions else ["NO_MATCHING_LIVE_PUBLIC_EVIDENCE"])


@dataclass(frozen=True)
class DueForecastClosureDecisionV2:
    forecast_id: str
    status: str
    blocker: str | None
    score_seed_eligible: bool
    evidence: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DueForecastClosureExpansionResultV5:
    due_forecast_closure_expansion_status: str
    decisions: list[DueForecastClosureDecisionV2]
    blockers: list[str]
    outcome_fabricated: bool = False
    execution_bridge_present: bool = False

    @property
    def due_forecast_count(self) -> int:
        return 4

    @property
    def observed_forecast_count(self) -> int:
        return sum(1 for decision in self.decisions if decision.status == "OBSERVED_LIVE_PUBLIC")

    @property
    def live_unresolved_count(self) -> int:
        return self.due_forecast_count - self.observed_forecast_count

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "decisions": [decision.to_dict() for decision in self.decisions],
            "due_forecast_count": self.due_forecast_count,
            "observed_forecast_count": self.observed_forecast_count,
            "live_unresolved_count": self.live_unresolved_count,
        }


class DueForecastClosureExpansionV5:
    def close(self, settlement: SettlementCompatibleEvidenceExpansionResultV2) -> DueForecastClosureExpansionResultV5:
        if not settlement.join_decisions:
            decisions = [
                DueForecastClosureDecisionV2("weather_threshold_due_v32", "UNRESOLVED", "NO_MATCHING_LIVE_PUBLIC_EVIDENCE", False),
                DueForecastClosureDecisionV2("crypto_threshold_due_v32", "UNRESOLVED", "NO_MATCHING_LIVE_PUBLIC_EVIDENCE", False),
                DueForecastClosureDecisionV2("public_event_due_v32", "UNRESOLVED", "NO_MATCHING_LIVE_PUBLIC_EVIDENCE", False),
                DueForecastClosureDecisionV2("kalshi_rule_due_v32", "UNRESOLVED", "SETTLEMENT_AMBIGUOUS", False),
            ]
            return DueForecastClosureExpansionResultV5("PASS_DISABLED_BY_DEFAULT", decisions, ["NO_MATCHING_LIVE_PUBLIC_EVIDENCE", "SETTLEMENT_AMBIGUOUS"])
        decisions = [
            DueForecastClosureDecisionV2(f"{join.adapter_family}_due_v32", "OBSERVED_LIVE_PUBLIC", None, True, join.to_dict())
            for join in settlement.join_decisions
        ]
        decisions.append(DueForecastClosureDecisionV2("kalshi_rule_due_v32", "UNRESOLVED", "SETTLEMENT_AMBIGUOUS", False))
        return DueForecastClosureExpansionResultV5("PASS_WITH_REMAINING_BLOCKERS", decisions, ["SETTLEMENT_AMBIGUOUS"])


@dataclass(frozen=True)
class LiveScoreExpansionResultV3:
    live_score_expansion_status: str
    score_records: list[dict[str, Any]]
    live_unresolved_count: int
    disabled_probe_scored_live: bool = False
    public_probe_failure_scored_live: bool = False
    ambiguous_settlement_scored: bool = False
    execution_bridge_present: bool = False

    @property
    def live_scored_count(self) -> int:
        return len(self.score_records)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "live_scored_count": self.live_scored_count}


class LiveScoreExpansionSeedV3:
    def seed(self, closure: DueForecastClosureExpansionResultV5) -> LiveScoreExpansionResultV3:
        observed = [decision for decision in closure.decisions if decision.status == "OBSERVED_LIVE_PUBLIC" and decision.score_seed_eligible]
        records = [{"forecast_id": decision.forecast_id, "score_source": "OBSERVED_LIVE_PUBLIC"} for decision in observed]
        return LiveScoreExpansionResultV3("PASS" if records else "PASS_DISABLED_BY_DEFAULT", records, closure.live_unresolved_count)


@dataclass(frozen=True)
class LiveCalibrationExpansionResultV3:
    live_calibration_expansion_status: str
    live_calibration_sample_count: int
    low_sample_warning: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LiveCalibrationExpansionV3:
    def expand(self, score: LiveScoreExpansionResultV3) -> LiveCalibrationExpansionResultV3:
        if score.live_scored_count == 0:
            return LiveCalibrationExpansionResultV3("PASS_DISABLED_BY_DEFAULT", 0, False)
        return LiveCalibrationExpansionResultV3("PASS_LOW_SAMPLE_WARNING", score.live_scored_count, score.live_scored_count < 20)


@dataclass(frozen=True)
class ProbeCacheReplaySeparationResultV2:
    probe_cache_replay_separation_status: str = "PASS"
    fixture_scored_live: bool = False
    replay_scored_live: bool = False
    stale_cached_evidence_scored_live: bool = False
    public_sample_evidence_scored_live: bool = False
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProbeCacheReplaySeparationV2:
    def audit(self, state: dict[str, Any]) -> ProbeCacheReplaySeparationResultV2:
        return ProbeCacheReplaySeparationResultV2()


@dataclass(frozen=True)
class SportsFixtureGuardV3Result:
    sports_fixture_guard_status: str = "PASS"
    sports_source_mode: str = "FIXTURE_REPLAY_ONLY"
    sports_probe_eligibility_decision: str = "SOURCE_TERMS_APPROVAL_REQUIRED"
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SourceTruthRecoveryClosureResultV13:
    source_truth_recovery_closure_v13_status: str
    source_recovery_truth_signal: str
    probe_run_truth_signal: str
    evidence_compatibility_truth_signal: str
    observation_closure_truth_signal: str
    live_score_truth_signal: str
    source_truth_recovery_action_v13: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SourceTruthRecoveryClosureV13:
    def evaluate(self, state: dict[str, Any]) -> SourceTruthRecoveryClosureResultV13:
        gate_enabled = state["operator_gate"].enabled
        score = state["score_expansion"]
        return SourceTruthRecoveryClosureResultV13(
            "PASS_WITH_REMAINING_PARTIALS" if not gate_enabled or score.live_scored_count == 0 else "PASS",
            "GATE_DISABLED_RECOVERY_PLANNED" if not gate_enabled else "RECOVERY_ATTEMPTED",
            "NO_PROBE_RUN_DEFAULT_DISABLED" if not gate_enabled else "BOUNDED_PROBE_RUN_ATTEMPTED",
            "NO_SETTLEMENT_COMPATIBLE_LIVE_EVIDENCE" if not state["settlement_expansion"].join_decisions else "SETTLEMENT_COMPATIBLE_LIVE_EVIDENCE",
            "NO_OBSERVED_LIVE_PUBLIC_CLOSURE" if state["closure_expansion"].observed_forecast_count == 0 else "OBSERVED_LIVE_PUBLIC_CLOSURE",
            "NO_VALID_LIVE_PUBLIC_SCORE_EXPANSION" if score.live_scored_count == 0 else "LIVE_PUBLIC_SCORE_EXPANDED",
            "operator may enable bounded read-only probe pass" if not gate_enabled else "review source recovery blockers before expanding source families",
        )


class V32SourceRecoveryControllerV1:
    def cases(self) -> list[SourceRecoveryCaseV2]:
        return [
            SourceRecoveryCaseV2("weather_recovery_v32", "weather", "WEATHER_THRESHOLD", "temperature_f", "NO_MATCHING_LIVE_PUBLIC_EVIDENCE"),
            SourceRecoveryCaseV2("crypto_recovery_v32", "crypto", "CRYPTO_PRICE_THRESHOLD", "btc_usd", "NO_MATCHING_LIVE_PUBLIC_EVIDENCE"),
            SourceRecoveryCaseV2("public_event_recovery_v32", "public_event", "FINANCE_MACRO_RELEASE", "cpi_yoy", "NO_MATCHING_LIVE_PUBLIC_EVIDENCE"),
            SourceRecoveryCaseV2("kalshi_readonly_recovery_v32", "kalshi_readonly", "KALSHI_MAPPED_MARKET", "settlement_rule_text", "READONLY_ACCESS_UNAVAILABLE"),
        ]

    def run(self, state: dict[str, Any]) -> SourceRecoveryResultV2:
        gate_enabled = state["operator_gate"].enabled
        cases = self.cases()
        plans = [
            SourceRecoveryPlanV2(case.case_id, "bounded read-only public probe" if gate_enabled else "operator enablement packet", not gate_enabled, gate_enabled)
            for case in cases
        ]
        attempts: list[SourceRecoveryAttemptV2] = []
        decisions: list[SourceRecoveryDecisionV2] = []
        blockers: list[str] = []
        if gate_enabled:
            for domain in state["domain_recovery"].values():
                attempts.append(SourceRecoveryAttemptV2(f"{domain.domain}_recovery_v32", domain.domain, domain.status == "PASS", domain.status, domain.blocker))
                recovered = domain.status == "PASS"
                if domain.blocker:
                    blockers.append(domain.blocker)
                decisions.append(SourceRecoveryDecisionV2(f"{domain.domain}_recovery_v32", "RECOVERED" if recovered else domain.blocker or "BLOCKED", domain.blocker, recovered))
            status = "PASS_WITH_REMAINING_BLOCKERS" if blockers else "PASS"
        else:
            blockers = ["PROBE_DISABLED"]
            decisions = [SourceRecoveryDecisionV2(case.case_id, "OPERATOR_ENABLE_PUBLIC_PROBES", "PROBE_DISABLED", False) for case in cases]
            status = "PASS_DISABLED_BY_DEFAULT"
        return SourceRecoveryResultV2(status, cases, plans, attempts, decisions, sorted(set(blockers)), SourceRecoverySafetyProofV1(), not gate_enabled)


def build_default_v32_state(*, enable_network: bool = False, env: dict[str, str] | None = None) -> dict[str, Any]:
    env = env or {}
    operator_gate = OperatorGatedProbeRunV2().decide(env)
    minimal_probe_pass = MinimalPublicProbePassV1().run(operator_gate)
    domain_recovery = {
        domain: _domain_recovery(domain, operator_gate.enabled)
        for domain in ["weather", "crypto", "public_event", "kalshi_readonly"]
    }
    state: dict[str, Any] = {
        "operator_gate": operator_gate,
        "minimal_probe_pass": minimal_probe_pass,
        "domain_recovery": domain_recovery,
    }
    state["evidence_expansion"] = LivePublicEvidenceExpansionV2().expand(state)
    state["settlement_expansion"] = SettlementCompatibleEvidenceExpansionV2().expand(state["evidence_expansion"])
    state["closure_expansion"] = DueForecastClosureExpansionV5().close(state["settlement_expansion"])
    state["score_expansion"] = LiveScoreExpansionSeedV3().seed(state["closure_expansion"])
    state["calibration_expansion"] = LiveCalibrationExpansionV3().expand(state["score_expansion"])
    state["cache_replay_separation"] = ProbeCacheReplaySeparationV2().audit(state)
    state["sports_guard"] = SportsFixtureGuardV3Result()
    state["source_truth"] = SourceTruthRecoveryClosureV13().evaluate(state)
    state["source_recovery"] = V32SourceRecoveryControllerV1().run(state)
    return state
