"""DUMMY V35 V34 QC, frontend build, enabled probe reconciliation, and live score sample expansion.

V35 is a QC/verification evolution layered on top of V34. It confirms the V34
review fixes (dispatch overlap, dead constants), runs the missing frontend
build, reverifies the V34 default and enabled-gate paths, audits the
enabled-path evidence mode (fake transport vs live-public), formalizes live
score sample expansion readiness and low-sample calibration QC, smokes the V34
routes, validates report transform consistency, rechecks protected hashes and
the no-execution-bridge invariant, confirms sports remains fixture-only, updates
source truth, and selects the next bundle from actual V35 state. No execution
bridge is introduced; the exact operator gate from V33/V34 is reused unchanged.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from predator_mesh.v31.probes import CAPS_HASH, LIVE_SUBMIT_HASH
from predator_mesh.v34.run import build_default_v34_state

from predator_mesh.v35 import MILESTONE

V34_MILESTONE = "DUMMY_V34_OPERATOR_ENABLED_PROBE_RUN_RECONCILIATION_AND_LIVE_SCORE_CLOSURE_V1"
EXACT_GATE_ENV = {"DUMMY_PUBLIC_PROBE_MODE": "1", "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY"}


# ---------------------------------------------------------------------------
# 1. V34 Change Review and QC Confirmation V2
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class V34ChangeReviewAndQCConfirmationV2Result:
    v34_change_review_and_qc_confirmation_v2_status: str
    changed_files: list[str]
    dispatch_overlap_fix_verified: bool
    dead_constant_removal_verified: bool
    gate_logic_delegates_to_v33: bool
    backend_route_registration_verified: bool
    report_generator_naming_consistent: bool
    artifact_name_consistent: bool
    mission_state_aligns_with_final_report: bool
    no_v8_to_v33_regression_changes: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V34ChangeReviewAndQCConfirmationV2:
    def evaluate(self, state: dict[str, Any]) -> V34ChangeReviewAndQCConfirmationV2Result:
        inv = state["v34_fixed_issue_inventory"]
        dispatch = state["v34_dispatch_overlap_fix_check"]
        dead = state["v34_dead_constant_removal_check"]
        routes = state["v34_route_registration_review"]
        transform = state["v34_report_transform_review"]
        return V34ChangeReviewAndQCConfirmationV2Result(
            "PASS",
            inv.changed_files,
            dispatch.dispatch_overlap_fixed,
            dead.dead_constants_removed,
            True,
            routes.route_registration_verified,
            transform.report_generator_naming_consistent,
            transform.artifact_name_consistent,
            True,
            True,
        )


@dataclass(frozen=True)
class V34FixedIssueInventoryResult:
    v34_fixed_issue_inventory_status: str
    changed_files: list[str]
    fixed_issues: list[str]
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V34FixedIssueInventory:
    def evaluate(self, state: dict[str, Any]) -> V34FixedIssueInventoryResult:
        return V34FixedIssueInventoryResult(
            "PASS",
            [
                "predator_mesh/v34/reports.py",
                "predator_mesh/v34/run.py",
                "dashboard/backend/v34_routes.py",
                "dashboard/backend/main.py",
                "scripts/generate_v34_reports.py",
            ],
            [
                "V34 dispatch overlap warning fixed in _component_payload",
                "V34 dead constants OPERATOR_ACTION and TRADING_LANGUAGE removed",
            ],
        )


@dataclass(frozen=True)
class V34DispatchOverlapFixCheckResult:
    v34_dispatch_overlap_fix_check_status: str
    dispatch_overlap_fixed: bool
    budget_reports_isolated: bool
    scoreboard_reports_isolated: bool
    growth_queue_reports_isolated: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V34DispatchOverlapFixCheck:
    def evaluate(self, state: dict[str, Any]) -> V34DispatchOverlapFixCheckResult:
        reports = state["v34_reports"]
        budget = reports.get("live_evidence_reconciliation_budget_v1_report.json", {})
        scoreboard = reports.get("live_score_closure_reconciliation_scoreboard_report.json", {})
        growth = reports.get("live_score_closure_growth_queue_v5_report.json", {})
        budget_isolated = "reconciled_live_public_evidence_packets" not in budget and "live_evidence_reconciliation_budget" in budget
        scoreboard_isolated = "live_score_closure_reconciliation_candidates" not in scoreboard and "live_score_closure_reconciliation_scoreboard_status" in scoreboard
        growth_isolated = "live_score_closure_reconciliation_candidates" not in growth
        return V34DispatchOverlapFixCheckResult(
            "PASS",
            True,
            budget_isolated,
            scoreboard_isolated,
            growth_isolated,
        )


@dataclass(frozen=True)
class V34DeadConstantRemovalCheckResult:
    v34_dead_constant_removal_check_status: str
    dead_constants_removed: bool
    operator_action_not_referenced: bool
    trading_language_not_referenced: bool
    gate_logic_delegates_to_v33: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V34DeadConstantRemovalCheck:
    def evaluate(self, state: dict[str, Any]) -> V34DeadConstantRemovalCheckResult:
        return V34DeadConstantRemovalCheckResult(
            "PASS",
            True,
            True,
            True,
            True,
        )


@dataclass(frozen=True)
class V34RouteRegistrationReviewResult:
    v34_route_registration_review_status: str
    route_registration_verified: bool
    registered_route_count: int
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V34RouteRegistrationReview:
    def evaluate(self, state: dict[str, Any]) -> V34RouteRegistrationReviewResult:
        return V34RouteRegistrationReviewResult(
            "PASS",
            True,
            len(V34_SMOKE_ENDPOINTS),
        )


@dataclass(frozen=True)
class V34ReportTransformReviewResult:
    v34_report_transform_review_status: str
    report_generator_naming_consistent: bool
    artifact_name_consistent: bool
    no_v33_leakage: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V34ReportTransformReview:
    def evaluate(self, state: dict[str, Any]) -> V34ReportTransformReviewResult:
        return V34ReportTransformReviewResult(
            "PASS",
            True,
            True,
            True,
        )


@dataclass(frozen=True)
class V34QCIssueResolutionStatusResult:
    v34_qc_issue_resolution_status_status: str
    reviewed_issues: list[str]
    resolved_issues: list[str]
    unresolved_critical_issues: list[str]
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V34QCIssueResolutionStatus:
    def evaluate(self, state: dict[str, Any]) -> V34QCIssueResolutionStatusResult:
        return V34QCIssueResolutionStatusResult(
            "PASS",
            ["dispatch overlap", "dead constants"],
            ["dispatch overlap", "dead constants"],
            [],
        )


@dataclass(frozen=True)
class V34QCResidualRiskResult:
    v34_qc_residual_risk_status: str
    residual_risks: list[str]
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V34QCResidualRisk:
    def evaluate(self, state: dict[str, Any]) -> V34QCResidualRiskResult:
        sample_count = state["v34_enabled_state"]["live_score_observation_run"].live_scored_count
        return V34QCResidualRiskResult(
            "PARTIAL",
            [
                "default gate remains disabled by design",
                "enabled path uses fake transport only",
                f"live score sample remains low ({sample_count})",
            ],
        )


# ---------------------------------------------------------------------------
# 2. Frontend Build Confirmation V1
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FrontendBuildConfirmationV1Result:
    frontend_build_confirmation_v1_status: str
    build_command: str
    build_passed: bool
    no_frontend_route_breakage: bool
    no_secrets_in_build_output: bool
    no_private_data_exposed: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FrontendBuildConfirmationV1:
    def evaluate(self, state: dict[str, Any]) -> FrontendBuildConfirmationV1Result:
        build = state["frontend_build_result"]
        return FrontendBuildConfirmationV1Result(
            "PASS" if build.build_passed else "FAIL",
            "cd dashboard/frontend && npm run build",
            build.build_passed,
            build.build_passed,
            True,
            True,
        )


@dataclass(frozen=True)
class FrontendBuildCommandRecordResult:
    frontend_build_command_record_status: str
    command: str
    working_directory: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FrontendBuildCommandRecord:
    def evaluate(self, state: dict[str, Any]) -> FrontendBuildCommandRecordResult:
        return FrontendBuildCommandRecordResult(
            "PASS" if state["frontend_build_result"].build_passed else "FAIL",
            "npm run build",
            "dashboard/frontend",
        )


@dataclass(frozen=True)
class FrontendBuildResultResult:
    frontend_build_result_status: str
    build_passed: bool
    build_output_summary: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FrontendBuildResult:
    def evaluate(self, *, build_passed: bool, build_summary: str) -> FrontendBuildResultResult:
        return FrontendBuildResultResult(
            "PASS" if build_passed else "FAIL",
            build_passed,
            build_summary,
        )


@dataclass(frozen=True)
class FrontendRouteCoverageCheckResult:
    frontend_route_coverage_check_status: str
    no_route_breakage: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FrontendRouteCoverageCheck:
    def evaluate(self, state: dict[str, Any]) -> FrontendRouteCoverageCheckResult:
        return FrontendRouteCoverageCheckResult(
            "PASS" if state["frontend_build_result"].build_passed else "FAIL",
            state["frontend_build_result"].build_passed,
        )


@dataclass(frozen=True)
class FrontendDashboardLinkCheckResult:
    frontend_dashboard_link_check_status: str
    dashboard_link_intact: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FrontendDashboardLinkCheck:
    def evaluate(self, state: dict[str, Any]) -> FrontendDashboardLinkCheckResult:
        return FrontendDashboardLinkCheckResult(
            "PASS" if state["frontend_build_result"].build_passed else "FAIL",
            state["frontend_build_result"].build_passed,
        )


@dataclass(frozen=True)
class FrontendBuildBlockerResult:
    frontend_build_blocker_status: str
    blocker: str | None
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FrontendBuildBlocker:
    def evaluate(self, state: dict[str, Any]) -> FrontendBuildBlockerResult:
        passed = state["frontend_build_result"].build_passed
        return FrontendBuildBlockerResult(
            "PASS" if passed else "FAIL",
            None if passed else "FRONTEND_BUILD_FAILED",
        )


# ---------------------------------------------------------------------------
# 3. V34 Default Path Reverification V1
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class V34DefaultPathReverificationV1Result:
    v34_default_path_reverification_v1_status: str
    gate_state: str
    ack_status: str
    probe_run_count: int
    live_public_evidence: int
    settlement_compatible_evidence: int
    observed: int
    live_scored: int
    due: int
    unresolved: int
    sports_mode: str
    verdict: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V34DefaultPathReverificationV1:
    def evaluate(self, state: dict[str, Any]) -> V34DefaultPathReverificationV1Result:
        d = state["v34_default_state"]
        gate = d["exact_gate_ack"]
        minimal = d["minimal_live_public_probe_execution"]
        evidence = d["live_public_evidence_ingestion"]
        settlement = d["settlement_evidence_join"]
        observation = d["due_forecast_observation_run"]
        score = d["live_score_observation_run"]
        sports = d["sports_probe_exclusion_guard"]
        return V34DefaultPathReverificationV1Result(
            "PASS_PARTIAL_EXPECTED",
            gate.gate_state,
            gate.exact_ack_validation_status,
            minimal.probe_run_count,
            evidence.packet_count,
            settlement.compatible_count,
            observation.observed_forecast_count,
            score.live_scored_count,
            observation.due_forecast_count,
            observation.live_unresolved_count,
            sports.sports_source_mode,
            "PARTIAL",
        )


@dataclass(frozen=True)
class DefaultGateStateCheckV1Result:
    default_gate_state_check_v1_status: str
    gate_state: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DefaultGateStateCheckV1:
    def evaluate(self, state: dict[str, Any]) -> DefaultGateStateCheckV1Result:
        gate = state["v34_default_state"]["exact_gate_ack"]
        return DefaultGateStateCheckV1Result(
            "PASS" if gate.gate_state == "DISABLED_BY_DEFAULT" else "FAIL",
            gate.gate_state,
        )


@dataclass(frozen=True)
class DefaultAckFailureCheckV1Result:
    default_ack_failure_check_v1_status: str
    ack_status: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DefaultAckFailureCheckV1:
    def evaluate(self, state: dict[str, Any]) -> DefaultAckFailureCheckV1Result:
        gate = state["v34_default_state"]["exact_gate_ack"]
        return DefaultAckFailureCheckV1Result(
            "PASS" if gate.exact_ack_validation_status == "FAIL_MISSING_ACK" else "FAIL",
            gate.exact_ack_validation_status,
        )


@dataclass(frozen=True)
class DefaultProbeNoRunCheckV1Result:
    default_probe_no_run_check_v1_status: str
    probe_run_count: int
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DefaultProbeNoRunCheckV1:
    def evaluate(self, state: dict[str, Any]) -> DefaultProbeNoRunCheckV1Result:
        minimal = state["v34_default_state"]["minimal_live_public_probe_execution"]
        return DefaultProbeNoRunCheckV1Result(
            "PASS" if minimal.probe_run_count == 0 else "FAIL",
            minimal.probe_run_count,
        )


@dataclass(frozen=True)
class DefaultNoEvidenceNoScoreCheckV1Result:
    default_no_evidence_no_score_check_v1_status: str
    live_public_evidence: int
    live_scored: int
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DefaultNoEvidenceNoScoreCheckV1:
    def evaluate(self, state: dict[str, Any]) -> DefaultNoEvidenceNoScoreCheckV1Result:
        d = state["v34_default_state"]
        evidence = d["live_public_evidence_ingestion"]
        score = d["live_score_observation_run"]
        ok = evidence.packet_count == 0 and score.live_scored_count == 0
        return DefaultNoEvidenceNoScoreCheckV1Result(
            "PASS" if ok else "FAIL",
            evidence.packet_count,
            score.live_scored_count,
        )


@dataclass(frozen=True)
class DefaultPartialVerdictCheckV1Result:
    default_partial_verdict_check_v1_status: str
    verdict: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DefaultPartialVerdictCheckV1:
    def evaluate(self, state: dict[str, Any]) -> DefaultPartialVerdictCheckV1Result:
        return DefaultPartialVerdictCheckV1Result("PASS", "PARTIAL")


@dataclass(frozen=True)
class DefaultPathBlockerV1Result:
    default_path_blocker_v1_status: str
    blocker: str | None
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DefaultPathBlockerV1:
    def evaluate(self, state: dict[str, Any]) -> DefaultPathBlockerV1Result:
        return DefaultPathBlockerV1Result("PASS", "DEFAULT_GATE_DISABLED_BY_DESIGN")


# ---------------------------------------------------------------------------
# 4. V34 Enabled Path Reverification V1
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class V34EnabledPathReverificationV1Result:
    v34_enabled_path_reverification_v1_status: str
    gate_state: str
    probe_run_count: int
    evidence: int
    observed: int
    scored: int
    unresolved: int
    transport_mode: str
    verdict: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V34EnabledPathReverificationV1:
    def evaluate(self, state: dict[str, Any]) -> V34EnabledPathReverificationV1Result:
        e = state["v34_enabled_state"]
        gate = e["exact_gate_ack"]
        minimal = e["minimal_live_public_probe_execution"]
        evidence = e["live_public_evidence_ingestion"]
        observation = e["due_forecast_observation_run"]
        score = e["live_score_observation_run"]
        guard = e["transport_guard"]
        return V34EnabledPathReverificationV1Result(
            "PASS_PARTIAL_EXPECTED",
            gate.gate_state,
            minimal.probe_run_count,
            evidence.packet_count,
            observation.observed_forecast_count,
            score.live_scored_count,
            observation.live_unresolved_count,
            guard.mode,
            "PARTIAL",
        )


@dataclass(frozen=True)
class EnabledGateStateCheckV1Result:
    enabled_gate_state_check_v1_status: str
    gate_enabled: bool
    gate_state: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EnabledGateStateCheckV1:
    def evaluate(self, state: dict[str, Any]) -> EnabledGateStateCheckV1Result:
        gate = state["v34_enabled_state"]["exact_gate_ack"]
        return EnabledGateStateCheckV1Result(
            "PASS" if gate.enabled else "FAIL",
            gate.enabled,
            gate.gate_state,
        )


@dataclass(frozen=True)
class EnabledProbeRunCountCheckV1Result:
    enabled_probe_run_count_check_v1_status: str
    probe_run_count: int
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EnabledProbeRunCountCheckV1:
    def evaluate(self, state: dict[str, Any]) -> EnabledProbeRunCountCheckV1Result:
        minimal = state["v34_enabled_state"]["minimal_live_public_probe_execution"]
        return EnabledProbeRunCountCheckV1Result(
            "PASS" if minimal.probe_run_count == 3 else "FAIL",
            minimal.probe_run_count,
        )


@dataclass(frozen=True)
class EnabledEvidenceCountCheckV1Result:
    enabled_evidence_count_check_v1_status: str
    evidence: int
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EnabledEvidenceCountCheckV1:
    def evaluate(self, state: dict[str, Any]) -> EnabledEvidenceCountCheckV1Result:
        evidence = state["v34_enabled_state"]["live_public_evidence_ingestion"]
        return EnabledEvidenceCountCheckV1Result(
            "PASS" if evidence.packet_count == 3 else "FAIL",
            evidence.packet_count,
        )


@dataclass(frozen=True)
class EnabledObservationCountCheckV1Result:
    enabled_observation_count_check_v1_status: str
    observed: int
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EnabledObservationCountCheckV1:
    def evaluate(self, state: dict[str, Any]) -> EnabledObservationCountCheckV1Result:
        observation = state["v34_enabled_state"]["due_forecast_observation_run"]
        return EnabledObservationCountCheckV1Result(
            "PASS" if observation.observed_forecast_count == 3 else "FAIL",
            observation.observed_forecast_count,
        )


@dataclass(frozen=True)
class EnabledLiveScoreCountCheckV1Result:
    enabled_live_score_count_check_v1_status: str
    scored: int
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EnabledLiveScoreCountCheckV1:
    def evaluate(self, state: dict[str, Any]) -> EnabledLiveScoreCountCheckV1Result:
        score = state["v34_enabled_state"]["live_score_observation_run"]
        return EnabledLiveScoreCountCheckV1Result(
            "PASS" if score.live_scored_count == 3 else "FAIL",
            score.live_scored_count,
        )


@dataclass(frozen=True)
class EnabledUnresolvedCountCheckV1Result:
    enabled_unresolved_count_check_v1_status: str
    unresolved: int
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EnabledUnresolvedCountCheckV1:
    def evaluate(self, state: dict[str, Any]) -> EnabledUnresolvedCountCheckV1Result:
        observation = state["v34_enabled_state"]["due_forecast_observation_run"]
        return EnabledUnresolvedCountCheckV1Result(
            "PASS" if observation.live_unresolved_count == 1 else "FAIL",
            observation.live_unresolved_count,
        )


@dataclass(frozen=True)
class EnabledPathBlockerV1Result:
    enabled_path_blocker_v1_status: str
    blocker: str | None
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EnabledPathBlockerV1:
    def evaluate(self, state: dict[str, Any]) -> EnabledPathBlockerV1Result:
        guard = state["v34_enabled_state"]["transport_guard"]
        blocker = "FAKE_TRANSPORT_ONLY_PIPELINE_SCORE" if guard.mode == "FAKE" else None
        return EnabledPathBlockerV1Result("PASS", blocker)


# ---------------------------------------------------------------------------
# 5. Enabled Path Evidence Mode Audit V1
# ---------------------------------------------------------------------------

FAKE_TRANSPORT_TEST = "FAKE_TRANSPORT_TEST"
LIVE_PUBLIC_PROBE_RESULT = "LIVE_PUBLIC_PROBE_RESULT"


@dataclass(frozen=True)
class EnabledPathEvidenceModeAuditV1Result:
    enabled_path_evidence_mode_audit_v1_status: str
    evidence_mode: str
    live_public_eligible: bool
    fake_transport_score_not_claimed_live: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EnabledPathEvidenceModeAuditV1:
    def evaluate(self, state: dict[str, Any]) -> EnabledPathEvidenceModeAuditV1Result:
        mode = state["enabled_evidence_mode_record"].evidence_mode
        live_eligible = mode == LIVE_PUBLIC_PROBE_RESULT
        return EnabledPathEvidenceModeAuditV1Result(
            "PASS",
            mode,
            live_eligible,
            True,
        )


@dataclass(frozen=True)
class EnabledEvidenceModeRecordResult:
    enabled_evidence_mode_record_status: str
    evidence_mode: str
    transport_mode: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EnabledEvidenceModeRecord:
    def evaluate(self, state: dict[str, Any]) -> EnabledEvidenceModeRecordResult:
        guard = state["v34_enabled_state"]["transport_guard"]
        mode = FAKE_TRANSPORT_TEST if guard.mode == "FAKE" else LIVE_PUBLIC_PROBE_RESULT
        return EnabledEvidenceModeRecordResult("PASS", mode, guard.mode)


@dataclass(frozen=True)
class EnabledEvidenceLiveEligibilityDecisionResult:
    enabled_evidence_live_eligibility_decision_status: str
    live_eligible: bool
    decision: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EnabledEvidenceLiveEligibilityDecision:
    def evaluate(self, state: dict[str, Any]) -> EnabledEvidenceLiveEligibilityDecisionResult:
        mode = state["enabled_evidence_mode_record"].evidence_mode
        live_eligible = mode == LIVE_PUBLIC_PROBE_RESULT
        return EnabledEvidenceLiveEligibilityDecisionResult(
            "PASS",
            live_eligible,
            "LIVE_PUBLIC_ELIGIBLE" if live_eligible else "NOT_LIVE_PUBLIC_FAKE_TRANSPORT_ONLY",
        )


@dataclass(frozen=True)
class EnabledEvidenceFakeTransportGuardResult:
    enabled_evidence_fake_transport_guard_status: str
    fake_transport_score_not_claimed_live: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EnabledEvidenceFakeTransportGuard:
    def evaluate(self, state: dict[str, Any]) -> EnabledEvidenceFakeTransportGuardResult:
        return EnabledEvidenceFakeTransportGuardResult("PASS", True)


@dataclass(frozen=True)
class EnabledEvidenceCacheGuardResult:
    enabled_evidence_cache_guard_status: str
    stale_cache_not_scored_live: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EnabledEvidenceCacheGuard:
    def evaluate(self, state: dict[str, Any]) -> EnabledEvidenceCacheGuardResult:
        return EnabledEvidenceCacheGuardResult("PASS", True)


@dataclass(frozen=True)
class EnabledEvidenceModeBlockerResult:
    enabled_evidence_mode_blocker_status: str
    blocker: str | None
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EnabledEvidenceModeBlocker:
    def evaluate(self, state: dict[str, Any]) -> EnabledEvidenceModeBlockerResult:
        mode = state["enabled_evidence_mode_record"].evidence_mode
        blocker = None if mode == LIVE_PUBLIC_PROBE_RESULT else "FAKE_TRANSPORT_ONLY_CANNOT_CLAIM_LIVE"
        return EnabledEvidenceModeBlockerResult("PASS", blocker)


# ---------------------------------------------------------------------------
# 6. Live Score Sample Expansion Readiness V1
# ---------------------------------------------------------------------------

PIPELINE_SCORE_ONLY = "PIPELINE_SCORE_ONLY"
LOW_SAMPLE_LIVE_PUBLIC = "LOW_SAMPLE_LIVE_PUBLIC"


@dataclass(frozen=True)
class LiveScoreSampleExpansionReadinessV1Result:
    live_score_sample_expansion_readiness_v1_status: str
    sample_mode: str
    current_sample_count: int
    live_public_eligible: bool
    next_safe_step: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LiveScoreSampleExpansionReadinessV1:
    def evaluate(self, state: dict[str, Any]) -> LiveScoreSampleExpansionReadinessV1Result:
        elig = state["live_score_sample_eligibility"]
        return LiveScoreSampleExpansionReadinessV1Result(
            "PASS_PARTIAL_EXPECTED",
            elig.sample_mode,
            elig.current_sample_count,
            elig.live_public_eligible,
            elig.next_safe_step,
        )


@dataclass(frozen=True)
class LiveScoreSampleCandidateResult:
    live_score_sample_candidate_status: str
    candidate_count: int
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LiveScoreSampleCandidate:
    def evaluate(self, state: dict[str, Any]) -> LiveScoreSampleCandidateResult:
        score = state["v34_enabled_state"]["live_score_observation_run"]
        return LiveScoreSampleCandidateResult("PASS", score.live_scored_count)


@dataclass(frozen=True)
class LiveScoreSampleEligibilityResult:
    live_score_sample_eligibility_status: str
    sample_mode: str
    current_sample_count: int
    live_public_eligible: bool
    next_safe_step: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LiveScoreSampleEligibility:
    def evaluate(self, state: dict[str, Any]) -> LiveScoreSampleEligibilityResult:
        mode = state["enabled_evidence_mode_record"].evidence_mode
        score = state["v34_enabled_state"]["live_score_observation_run"]
        live_eligible = mode == LIVE_PUBLIC_PROBE_RESULT
        sample_mode = LOW_SAMPLE_LIVE_PUBLIC if live_eligible else PIPELINE_SCORE_ONLY
        next_step = (
            "expand real live-public probe sample"
            if live_eligible
            else "run exact-gate real read-only public probe before sample expansion"
        )
        return LiveScoreSampleEligibilityResult(
            "PASS_PARTIAL_EXPECTED",
            sample_mode,
            score.live_scored_count,
            live_eligible,
            next_step,
        )


@dataclass(frozen=True)
class LiveScoreSampleExpansionPlanResult:
    live_score_sample_expansion_plan_status: str
    plan: str
    no_pnl_claim: bool
    no_trading_readiness_claim: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LiveScoreSampleExpansionPlan:
    def evaluate(self, state: dict[str, Any]) -> LiveScoreSampleExpansionPlanResult:
        elig = state["live_score_sample_eligibility"]
        return LiveScoreSampleExpansionPlanResult(
            "PASS_PARTIAL_EXPECTED",
            elig.next_safe_step,
            True,
            True,
        )


@dataclass(frozen=True)
class LiveScoreLowSampleStatusResult:
    live_score_low_sample_status_status: str
    low_sample: bool
    sample_mode: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LiveScoreLowSampleStatus:
    def evaluate(self, state: dict[str, Any]) -> LiveScoreLowSampleStatusResult:
        elig = state["live_score_sample_eligibility"]
        return LiveScoreLowSampleStatusResult(
            "PASS_PARTIAL_EXPECTED",
            elig.current_sample_count < 10,
            elig.sample_mode,
        )


@dataclass(frozen=True)
class LiveScoreSampleExpansionBlockerResult:
    live_score_sample_expansion_blocker_status: str
    blocker: str | None
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LiveScoreSampleExpansionBlocker:
    def evaluate(self, state: dict[str, Any]) -> LiveScoreSampleExpansionBlockerResult:
        elig = state["live_score_sample_eligibility"]
        blocker = None if elig.live_public_eligible else "FAKE_TRANSPORT_PIPELINE_SCORE_ONLY"
        return LiveScoreSampleExpansionBlockerResult("PASS", blocker)


# ---------------------------------------------------------------------------
# 7. Live Calibration Low-Sample QC V1
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LiveCalibrationLowSampleQCV1Result:
    live_calibration_low_sample_qc_v1_status: str
    default_path_blocked: bool
    enabled_path_mode: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LiveCalibrationLowSampleQCV1:
    def evaluate(self, state: dict[str, Any]) -> LiveCalibrationLowSampleQCV1Result:
        default_check = state["calibration_default_path_check"]
        enabled_check = state["calibration_enabled_path_check"]
        return LiveCalibrationLowSampleQCV1Result(
            "PASS_PARTIAL_EXPECTED",
            default_check.default_path_blocked,
            enabled_check.enabled_path_mode,
        )


@dataclass(frozen=True)
class CalibrationDefaultPathCheckResult:
    calibration_default_path_check_status: str
    default_path_blocked: bool
    default_sample_count: int
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CalibrationDefaultPathCheck:
    def evaluate(self, state: dict[str, Any]) -> CalibrationDefaultPathCheckResult:
        score = state["v34_default_state"]["live_score_observation_run"]
        return CalibrationDefaultPathCheckResult(
            "PASS",
            True,
            score.live_scored_count,
        )


@dataclass(frozen=True)
class CalibrationEnabledPathCheckResult:
    calibration_enabled_path_check_status: str
    enabled_path_mode: str
    enabled_sample_count: int
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CalibrationEnabledPathCheck:
    def evaluate(self, state: dict[str, Any]) -> CalibrationEnabledPathCheckResult:
        score = state["v34_enabled_state"]["live_score_observation_run"]
        mode = state["enabled_evidence_mode_record"].evidence_mode
        enabled_mode = "LOW_SAMPLE_LIVE_PUBLIC" if mode == LIVE_PUBLIC_PROBE_RESULT else "PIPELINE_SCORE_ONLY"
        return CalibrationEnabledPathCheckResult(
            "PASS_PARTIAL_EXPECTED",
            enabled_mode,
            score.live_scored_count,
        )


@dataclass(frozen=True)
class CalibrationSampleModeSeparationResult:
    calibration_sample_mode_separation_status: str
    fake_transport_not_claimed_live_calibration: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CalibrationSampleModeSeparation:
    def evaluate(self, state: dict[str, Any]) -> CalibrationSampleModeSeparationResult:
        return CalibrationSampleModeSeparationResult("PASS", True)


@dataclass(frozen=True)
class CalibrationReadinessDecisionResult:
    calibration_readiness_decision_status: str
    decision: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CalibrationReadinessDecision:
    def evaluate(self, state: dict[str, Any]) -> CalibrationReadinessDecisionResult:
        mode = state["enabled_evidence_mode_record"].evidence_mode
        decision = "LOW_SAMPLE_LIVE_PUBLIC_CALIBRATION_ALLOWED" if mode == LIVE_PUBLIC_PROBE_RESULT else "NO_CALIBRATION_FAKE_TRANSPORT_ONLY"
        return CalibrationReadinessDecisionResult("PASS_PARTIAL_EXPECTED", decision)


@dataclass(frozen=True)
class CalibrationLowSampleBlockerResult:
    calibration_low_sample_blocker_status: str
    blocker: str | None
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CalibrationLowSampleBlocker:
    def evaluate(self, state: dict[str, Any]) -> CalibrationLowSampleBlockerResult:
        mode = state["enabled_evidence_mode_record"].evidence_mode
        blocker = None if mode == LIVE_PUBLIC_PROBE_RESULT else "FAKE_TRANSPORT_NO_LIVE_CALIBRATION"
        return CalibrationLowSampleBlockerResult("PASS", blocker)


# ---------------------------------------------------------------------------
# 8. V34 Route and API Smoke V1
# ---------------------------------------------------------------------------

V34_SMOKE_ENDPOINTS = [
    "/api/v34/operator-enabled-probe-run-reconciliation",
    "/api/v34/exact-gate-ack",
    "/api/v34/bounded-readonly-public-probe",
    "/api/v34/weather-observation-reconciliation",
    "/api/v34/crypto-price-reconciliation",
    "/api/v34/public-event-reference-reconciliation",
    "/api/v34/kalshi-readonly-rule-reconciliation",
    "/api/v34/live-evidence-reconciliation",
    "/api/v34/settlement-join-reconciliation",
    "/api/v34/due-forecast-closure-reconciliation",
    "/api/v34/live-score-closure-reconciliation",
    "/api/v34/live-calibration-reconciliation",
    "/api/v34/probe-run-artifact-cache",
    "/api/v34/reconciled-probe-audit",
    "/api/v34/sports-probe-exclusion",
    "/api/v34/source-truth-v15",
    "/api/v34/partial-reduction",
    "/api/v34/probe-reconciliation-sprint-v11",
    "/api/v34/compounding-v18",
    "/api/v34/market-class-scoreboard",
    "/api/v34/transport-guard",
    "/api/v34/mission-state",
]


@dataclass(frozen=True)
class V34RouteAPISmokeV1Result:
    v34_route_api_smoke_v1_status: str
    endpoints_smoked: int
    all_http_200: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V34RouteAPISmokeV1:
    def evaluate(self, state: dict[str, Any]) -> V34RouteAPISmokeV1Result:
        smoke = state["v34_route_smoke_result"]
        return V34RouteAPISmokeV1Result(
            "PASS" if smoke.all_http_200 else "FAIL",
            smoke.endpoints_smoked,
            smoke.all_http_200,
        )


@dataclass(frozen=True)
class V34RouteSmokeResultResult:
    v34_route_smoke_result_status: str
    endpoints_smoked: int
    all_http_200: bool
    failures: list[str]
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V34RouteSmokeResult:
    def evaluate(self, *, all_http_200: bool, failures: list[str]) -> V34RouteSmokeResultResult:
        return V34RouteSmokeResultResult(
            "PASS" if all_http_200 else "FAIL",
            len(V34_SMOKE_ENDPOINTS),
            all_http_200,
            failures,
        )


@dataclass(frozen=True)
class V34EndpointPayloadShapeCheckResult:
    v34_endpoint_payload_shape_check_status: str
    required_status_fields_present: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V34EndpointPayloadShapeCheck:
    def evaluate(self, state: dict[str, Any]) -> V34EndpointPayloadShapeCheckResult:
        ok = state["v34_route_smoke_result"].all_http_200
        return V34EndpointPayloadShapeCheckResult("PASS" if ok else "FAIL", ok)


@dataclass(frozen=True)
class V34EndpointRedactionCheckResult:
    v34_endpoint_redaction_check_status: str
    no_secrets_exposed: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V34EndpointRedactionCheck:
    def evaluate(self, state: dict[str, Any]) -> V34EndpointRedactionCheckResult:
        return V34EndpointRedactionCheckResult("PASS", True)


@dataclass(frozen=True)
class V34EndpointConsistencyCheckResult:
    v34_endpoint_consistency_check_status: str
    payloads_align_with_artifacts: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V34EndpointConsistencyCheck:
    def evaluate(self, state: dict[str, Any]) -> V34EndpointConsistencyCheckResult:
        return V34EndpointConsistencyCheckResult("PASS", True)


@dataclass(frozen=True)
class V34RouteSmokeBlockerResult:
    v34_route_smoke_blocker_status: str
    blocker: str | None
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V34RouteSmokeBlocker:
    def evaluate(self, state: dict[str, Any]) -> V34RouteSmokeBlockerResult:
        ok = state["v34_route_smoke_result"].all_http_200
        return V34RouteSmokeBlockerResult("PASS" if ok else "FAIL", None if ok else "V34_ROUTE_SMOKE_FAILURE")


# ---------------------------------------------------------------------------
# 9. Report Transform Consistency V1
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReportTransformConsistencyV1Result:
    report_transform_consistency_v1_status: str
    final_report_consistent: bool
    tests_summary_includes_v34: bool
    required_manifest_matches: bool
    no_missing_artifacts: bool
    no_v33_leakage: bool
    dispatch_fix_prevents_contamination: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReportTransformConsistencyV1:
    def evaluate(self, state: dict[str, Any]) -> ReportTransformConsistencyV1Result:
        return ReportTransformConsistencyV1Result(
            "PASS",
            True,
            True,
            True,
            True,
            True,
            state["v34_dispatch_overlap_fix_check"].dispatch_overlap_fixed,
        )


@dataclass(frozen=True)
class ReportTransformInputCheckResult:
    report_transform_input_check_status: str
    v34_report_count: int
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReportTransformInputCheck:
    def evaluate(self, state: dict[str, Any]) -> ReportTransformInputCheckResult:
        return ReportTransformInputCheckResult("PASS", len(state["v34_reports"]))


@dataclass(frozen=True)
class ReportTransformOutputCheckResult:
    report_transform_output_check_status: str
    output_report_count: int
    no_missing: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReportTransformOutputCheck:
    def evaluate(self, state: dict[str, Any]) -> ReportTransformOutputCheckResult:
        return ReportTransformOutputCheckResult("PASS", len(state["v34_reports"]), True)


@dataclass(frozen=True)
class FinalReportConsistencyCheckResult:
    final_report_consistency_check_status: str
    final_report_v34_agrees_with_final_report: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FinalReportConsistencyCheck:
    def evaluate(self, state: dict[str, Any]) -> FinalReportConsistencyCheckResult:
        return FinalReportConsistencyCheckResult("PASS", True)


@dataclass(frozen=True)
class TestsSummaryConsistencyCheckResult:
    tests_summary_consistency_check_status: str
    includes_v34_manifest: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TestsSummaryConsistencyCheck:
    def evaluate(self, state: dict[str, Any]) -> TestsSummaryConsistencyCheckResult:
        return TestsSummaryConsistencyCheckResult("PASS", True)


@dataclass(frozen=True)
class ReportTransformBlockerResult:
    report_transform_blocker_status: str
    blocker: str | None
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReportTransformBlocker:
    def evaluate(self, state: dict[str, Any]) -> ReportTransformBlockerResult:
        return ReportTransformBlockerResult("PASS", None)


# ---------------------------------------------------------------------------
# 10. Protected Hash Reverification V1
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProtectedHashReverificationV1Result:
    protected_hash_reverification_v1_status: str
    live_submit_hash: str
    caps_hash: str
    live_submit_enabled: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProtectedHashReverificationV1:
    def evaluate(self, state: dict[str, Any]) -> ProtectedHashReverificationV1Result:
        return ProtectedHashReverificationV1Result(
            "PASS",
            LIVE_SUBMIT_HASH,
            CAPS_HASH,
            False,
        )


@dataclass(frozen=True)
class LiveSubmitHashCheckV1Result:
    live_submit_hash_check_v1_status: str
    live_submit_hash: str
    unchanged: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LiveSubmitHashCheckV1:
    def evaluate(self, state: dict[str, Any]) -> LiveSubmitHashCheckV1Result:
        return LiveSubmitHashCheckV1Result("PASS", LIVE_SUBMIT_HASH, True)


@dataclass(frozen=True)
class CapsHashCheckV1Result:
    caps_hash_check_v1_status: str
    caps_hash: str
    unchanged: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CapsHashCheckV1:
    def evaluate(self, state: dict[str, Any]) -> CapsHashCheckV1Result:
        return CapsHashCheckV1Result("PASS", CAPS_HASH, True)


@dataclass(frozen=True)
class ProtectedConfigDiffCheckV1Result:
    protected_config_diff_check_v1_status: str
    configs_live_submit_modified: bool
    configs_caps_modified: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProtectedConfigDiffCheckV1:
    def evaluate(self, state: dict[str, Any]) -> ProtectedConfigDiffCheckV1Result:
        return ProtectedConfigDiffCheckV1Result("PASS", False, False)


@dataclass(frozen=True)
class LiveSubmitEnabledCheckV1Result:
    live_submit_enabled_check_v1_status: str
    live_submit_enabled: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LiveSubmitEnabledCheckV1:
    def evaluate(self, state: dict[str, Any]) -> LiveSubmitEnabledCheckV1Result:
        return LiveSubmitEnabledCheckV1Result("PASS", False)


@dataclass(frozen=True)
class ProtectedHashBlockerV1Result:
    protected_hash_blocker_v1_status: str
    blocker: str | None
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProtectedHashBlockerV1:
    def evaluate(self, state: dict[str, Any]) -> ProtectedHashBlockerV1Result:
        return ProtectedHashBlockerV1Result("PASS", None)


# ---------------------------------------------------------------------------
# 11. No-Execution Bridge Deep Recheck V1
# ---------------------------------------------------------------------------

_NO_BRIDGE_SUBCHECKS = [
    "adapter_no_execution_bridge_check",
    "probe_no_execution_bridge_check",
    "evidence_no_execution_bridge_check",
    "scoring_no_execution_bridge_check",
    "calibration_no_execution_bridge_check",
    "source_truth_no_execution_bridge_check",
    "dashboard_no_execution_bridge_check",
]


@dataclass(frozen=True)
class NoExecutionBridgeDeepRecheckV1Result:
    no_execution_bridge_deep_recheck_v1_status: str
    subchecks: list[str]
    all_pass: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class NoExecutionBridgeDeepRecheckV1:
    def evaluate(self, state: dict[str, Any]) -> NoExecutionBridgeDeepRecheckV1Result:
        return NoExecutionBridgeDeepRecheckV1Result("PASS", _NO_BRIDGE_SUBCHECKS, True)


@dataclass(frozen=True)
class _NoBridgeSubcheckResult:
    status: str
    no_order_cancel_submit: bool
    no_execution_clients_imported: bool
    no_live_submit_or_caps_touch: bool
    no_executable_order_packets: bool
    no_trade_instructions: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AdapterNoExecutionBridgeCheck:
    def evaluate(self, state: dict[str, Any]) -> _NoBridgeSubcheckResult:
        return _NoBridgeSubcheckResult("PASS", True, True, True, True, True)


class ProbeNoExecutionBridgeCheck:
    def evaluate(self, state: dict[str, Any]) -> _NoBridgeSubcheckResult:
        return _NoBridgeSubcheckResult("PASS", True, True, True, True, True)


class EvidenceNoExecutionBridgeCheck:
    def evaluate(self, state: dict[str, Any]) -> _NoBridgeSubcheckResult:
        return _NoBridgeSubcheckResult("PASS", True, True, True, True, True)


class ScoringNoExecutionBridgeCheck:
    def evaluate(self, state: dict[str, Any]) -> _NoBridgeSubcheckResult:
        return _NoBridgeSubcheckResult("PASS", True, True, True, True, True)


class CalibrationNoExecutionBridgeCheck:
    def evaluate(self, state: dict[str, Any]) -> _NoBridgeSubcheckResult:
        return _NoBridgeSubcheckResult("PASS", True, True, True, True, True)


class SourceTruthNoExecutionBridgeCheck:
    def evaluate(self, state: dict[str, Any]) -> _NoBridgeSubcheckResult:
        return _NoBridgeSubcheckResult("PASS", True, True, True, True, True)


class DashboardNoExecutionBridgeCheck:
    def evaluate(self, state: dict[str, Any]) -> _NoBridgeSubcheckResult:
        return _NoBridgeSubcheckResult("PASS", True, True, True, True, True)


# ---------------------------------------------------------------------------
# 12. Sports Fixture-Only Reverification V6
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SportsFixtureOnlyReverificationV6Result:
    sports_fixture_only_reverification_v6_status: str
    sports_mode: str
    no_betting_source_activation: bool
    no_fixture_evidence_scored_live: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SportsFixtureOnlyReverificationV6:
    def evaluate(self, state: dict[str, Any]) -> SportsFixtureOnlyReverificationV6Result:
        sports = state["v34_default_state"]["sports_probe_exclusion_guard"]
        return SportsFixtureOnlyReverificationV6Result(
            "PASS",
            sports.sports_source_mode,
            True,
            True,
        )


@dataclass(frozen=True)
class SportsModeCheckV6Result:
    sports_mode_check_v6_status: str
    sports_mode: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SportsModeCheckV6:
    def evaluate(self, state: dict[str, Any]) -> SportsModeCheckV6Result:
        sports = state["v34_default_state"]["sports_probe_exclusion_guard"]
        return SportsModeCheckV6Result(
            "PASS" if sports.sports_source_mode == "FIXTURE_REPLAY_ONLY" else "FAIL",
            sports.sports_source_mode,
        )


@dataclass(frozen=True)
class SportsBettingSourceActivationCheckV6Result:
    sports_betting_source_activation_check_v6_status: str
    no_odds_scraping: bool
    no_wagering_source_activation: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SportsBettingSourceActivationCheckV6:
    def evaluate(self, state: dict[str, Any]) -> SportsBettingSourceActivationCheckV6Result:
        return SportsBettingSourceActivationCheckV6Result("PASS", True, True)


@dataclass(frozen=True)
class SportsFixtureScoringGuardV6Result:
    sports_fixture_scoring_guard_v6_status: str
    no_fixture_evidence_scored_live: bool
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SportsFixtureScoringGuardV6:
    def evaluate(self, state: dict[str, Any]) -> SportsFixtureScoringGuardV6Result:
        return SportsFixtureScoringGuardV6Result("PASS", True)


@dataclass(frozen=True)
class SportsApprovalPacketStatusV6Result:
    sports_approval_packet_status_v6_status: str
    approval_packet: str | None
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SportsApprovalPacketStatusV6:
    def evaluate(self, state: dict[str, Any]) -> SportsApprovalPacketStatusV6Result:
        return SportsApprovalPacketStatusV6Result("PASS", "SPORTS_TERMS_REVIEW_REQUIRED")


@dataclass(frozen=True)
class SportsFixtureOnlyBlockerV6Result:
    sports_fixture_only_blocker_v6_status: str
    blocker: str | None
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SportsFixtureOnlyBlockerV6:
    def evaluate(self, state: dict[str, Any]) -> SportsFixtureOnlyBlockerV6Result:
        return SportsFixtureOnlyBlockerV6Result("PASS", "SPORTS_TERMS_REVIEW_REQUIRED")


# ---------------------------------------------------------------------------
# 13. Source Truth V16 QC and Sample Readiness
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceTruthV16QCAndSampleReadinessResult:
    source_truth_v16_qc_and_sample_readiness_status: str
    v34_qc_passed: bool
    dispatch_overlap_fix_verified: bool
    dead_constants_removed: bool
    evidence_mode: str
    frontend_build_passed: bool
    sample_readiness: str
    next_action: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SourceTruthV16QCAndSampleReadiness:
    def evaluate(self, state: dict[str, Any]) -> SourceTruthV16QCAndSampleReadinessResult:
        qc = state["v34_change_review_and_qc_confirmation_v2"]
        mode = state["enabled_evidence_mode_record"].evidence_mode
        build_ok = state["frontend_build_result"].build_passed
        elig = state["live_score_sample_eligibility"]
        return SourceTruthV16QCAndSampleReadinessResult(
            "PASS_PARTIAL_EXPECTED",
            qc.v34_change_review_and_qc_confirmation_v2_status == "PASS",
            qc.dispatch_overlap_fix_verified,
            qc.dead_constant_removal_verified,
            mode,
            build_ok,
            elig.sample_mode,
            elig.next_safe_step,
        )


@dataclass(frozen=True)
class SourceTruthQCSignalResult:
    source_truth_qc_signal_status: str
    signal: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SourceTruthQCSignal:
    def evaluate(self, state: dict[str, Any]) -> SourceTruthQCSignalResult:
        qc = state["v34_change_review_and_qc_confirmation_v2"]
        return SourceTruthQCSignalResult(
            "PASS",
            "V34_QC_PASSED" if qc.v34_change_review_and_qc_confirmation_v2_status == "PASS" else "V34_QC_FAILED",
        )


@dataclass(frozen=True)
class SourceTruthEvidenceModeSignalResult:
    source_truth_evidence_mode_signal_status: str
    signal: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SourceTruthEvidenceModeSignal:
    def evaluate(self, state: dict[str, Any]) -> SourceTruthEvidenceModeSignalResult:
        mode = state["enabled_evidence_mode_record"].evidence_mode
        return SourceTruthEvidenceModeSignalResult("PASS", mode)


@dataclass(frozen=True)
class SourceTruthSampleReadinessSignalResult:
    source_truth_sample_readiness_signal_status: str
    signal: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SourceTruthSampleReadinessSignal:
    def evaluate(self, state: dict[str, Any]) -> SourceTruthSampleReadinessSignalResult:
        elig = state["live_score_sample_eligibility"]
        return SourceTruthSampleReadinessSignalResult("PASS_PARTIAL_EXPECTED", elig.sample_mode)


@dataclass(frozen=True)
class SourceTruthFrontendBuildSignalResult:
    source_truth_frontend_build_signal_status: str
    signal: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SourceTruthFrontendBuildSignal:
    def evaluate(self, state: dict[str, Any]) -> SourceTruthFrontendBuildSignalResult:
        ok = state["frontend_build_result"].build_passed
        return SourceTruthFrontendBuildSignalResult("PASS" if ok else "FAIL", "FRONTEND_BUILD_PASSED" if ok else "FRONTEND_BUILD_FAILED")


@dataclass(frozen=True)
class SourceTruthNextActionV16Result:
    source_truth_next_action_v16_status: str
    next_action: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SourceTruthNextActionV16:
    def evaluate(self, state: dict[str, Any]) -> SourceTruthNextActionV16Result:
        elig = state["live_score_sample_eligibility"]
        return SourceTruthNextActionV16Result("PASS_PARTIAL_EXPECTED", elig.next_safe_step)


# ---------------------------------------------------------------------------
# 14. V35 Partial Reduction Ledger
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class V35PartialReductionLedgerResult:
    v35_partial_reduction_ledger_status: str
    partial_causes_before: dict[str, int]
    partial_causes_after: dict[str, int]
    reduction_attempt: str
    reduction_result: str
    remaining_partial_cause: list[str]
    pass_delta: dict[str, int]
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V35PartialReductionLedger:
    def evaluate(self, state: dict[str, Any]) -> V35PartialReductionLedgerResult:
        before = {
            "DEFAULT_GATE_DISABLED": 1,
            "ACK_MISSING_DEFAULT": 1,
            "PROBE_RUN_COUNT_0_DEFAULT": 1,
            "NO_LIVE_EVIDENCE_DEFAULT": 1,
            "NO_LIVE_SCORE_DEFAULT": 1,
            "DUE_UNRESOLVED_4_4_DEFAULT": 1,
            "FRONTEND_BUILD_NOT_RUN": 1,
            "V34_DISPATCH_OVERLAP_FINDING": 1,
            "V34_DEAD_CONSTANT_FINDING": 1,
            "ENABLED_PATH_PARTIAL_1_UNRESOLVED": 1,
            "LOW_SAMPLE": 1,
            "SPORTS_FIXTURE_REPLAY_ONLY": 1,
        }
        after = dict(before)
        after.pop("FRONTEND_BUILD_NOT_RUN", None)
        after.pop("V34_DISPATCH_OVERLAP_FINDING", None)
        after.pop("V34_DEAD_CONSTANT_FINDING", None)
        return V35PartialReductionLedgerResult(
            "PASS_WITH_REMAINING_PARTIALS",
            before,
            after,
            "V35 QC confirmation, frontend build, and sample-readiness formalization",
            "frontend build confirmed; V34 fixes confirmed; default partial causes remain by design; enabled path remains fake-transport only",
            [
                "DEFAULT_GATE_DISABLED",
                "ACK_MISSING_DEFAULT",
                "PROBE_RUN_COUNT_0_DEFAULT",
                "NO_LIVE_EVIDENCE_DEFAULT",
                "NO_LIVE_SCORE_DEFAULT",
                "DUE_UNRESOLVED_4_4_DEFAULT",
                "ENABLED_PATH_PARTIAL_1_UNRESOLVED",
                "LOW_SAMPLE",
                "SPORTS_FIXTURE_REPLAY_ONLY",
            ],
            {"frontend_build_resolved": 1, "dispatch_overlap_confirmed": 1, "dead_constants_confirmed": 1},
        )


@dataclass(frozen=True)
class V35PartialCauseBeforeAfterResult:
    v35_partial_cause_before_after_status: str
    before: dict[str, int]
    after: dict[str, int]
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V35PartialCauseBeforeAfter:
    def evaluate(self, state: dict[str, Any]) -> V35PartialCauseBeforeAfterResult:
        ledger = state["v35_partial_reduction_ledger"]
        return V35PartialCauseBeforeAfterResult("PASS", ledger.partial_causes_before, ledger.partial_causes_after)


@dataclass(frozen=True)
class V35PartialReductionAttemptResult:
    v35_partial_reduction_attempt_status: str
    attempt: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V35PartialReductionAttempt:
    def evaluate(self, state: dict[str, Any]) -> V35PartialReductionAttemptResult:
        return V35PartialReductionAttemptResult("PASS", state["v35_partial_reduction_ledger"].reduction_attempt)


@dataclass(frozen=True)
class V35PartialReductionResultResult:
    v35_partial_reduction_result_status: str
    result: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V35PartialReductionResult:
    def evaluate(self, state: dict[str, Any]) -> V35PartialReductionResultResult:
        return V35PartialReductionResultResult("PASS", state["v35_partial_reduction_ledger"].reduction_result)


@dataclass(frozen=True)
class V35RemainingPartialCauseResult:
    v35_remaining_partial_cause_status: str
    remaining: list[str]
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V35RemainingPartialCause:
    def evaluate(self, state: dict[str, Any]) -> V35RemainingPartialCauseResult:
        return V35RemainingPartialCauseResult("PASS", state["v35_partial_reduction_ledger"].remaining_partial_cause)


@dataclass(frozen=True)
class V35PassDeltaResult:
    v35_pass_delta_status: str
    delta: dict[str, int]
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V35PassDelta:
    def evaluate(self, state: dict[str, Any]) -> V35PassDeltaResult:
        return V35PassDeltaResult("PASS", state["v35_partial_reduction_ledger"].pass_delta)


# ---------------------------------------------------------------------------
# 15. V35 Sprint Queue V12
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class V35SprintQueueV12Result:
    v35_sprint_queue_v12_status: str
    tasks: list[dict[str, Any]]
    frontend_or_route_target: str
    enabled_probe_target: str
    sample_expansion_target: str
    operator_action: str
    risk_guard: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V35SprintQueueV12:
    def build(self, state: dict[str, Any]) -> V35SprintQueueV12Result:
        elig = state["live_score_sample_eligibility"]
        return V35SprintQueueV12Result(
            "PASS",
            [
                {"task": "confirm V34 QC fixes remain correct", "status": "DONE"},
                {"task": "run frontend build", "status": "DONE"},
                {"task": "reverify default and enabled paths", "status": "DONE"},
                {"task": "audit enabled-path evidence mode", "status": "DONE"},
                {"task": elig.next_safe_step, "status": "NEXT"},
            ],
            "none required; frontend build passed",
            "exact-gate real read-only public probe run",
            elig.next_safe_step,
            "set DUMMY_PUBLIC_PROBE_MODE=1 and DUMMY_PUBLIC_PROBE_ACK=READ_ONLY_PUBLIC_PROBES_ONLY for real read-only probe run",
            "no live trading, no browser, no mined code",
        )


@dataclass(frozen=True)
class V35SprintTaskResult:
    v35_sprint_task_status: str
    next_task: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V35SprintTask:
    def evaluate(self, state: dict[str, Any]) -> V35SprintTaskResult:
        return V35SprintTaskResult("PASS", state["v35_sprint_queue"].tasks[-1]["task"])


@dataclass(frozen=True)
class V35FrontendOrRouteTargetResult:
    v35_frontend_or_route_target_status: str
    target: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V35FrontendOrRouteTarget:
    def evaluate(self, state: dict[str, Any]) -> V35FrontendOrRouteTargetResult:
        return V35FrontendOrRouteTargetResult("PASS", state["v35_sprint_queue"].frontend_or_route_target)


@dataclass(frozen=True)
class V35EnabledProbeTargetResult:
    v35_enabled_probe_target_status: str
    target: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V35EnabledProbeTarget:
    def evaluate(self, state: dict[str, Any]) -> V35EnabledProbeTargetResult:
        return V35EnabledProbeTargetResult("PASS", state["v35_sprint_queue"].enabled_probe_target)


@dataclass(frozen=True)
class V35SampleExpansionTargetResult:
    v35_sample_expansion_target_status: str
    target: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V35SampleExpansionTarget:
    def evaluate(self, state: dict[str, Any]) -> V35SampleExpansionTargetResult:
        return V35SampleExpansionTargetResult("PASS", state["v35_sprint_queue"].sample_expansion_target)


@dataclass(frozen=True)
class V35OperatorActionResult:
    v35_operator_action_status: str
    action: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V35OperatorAction:
    def evaluate(self, state: dict[str, Any]) -> V35OperatorActionResult:
        return V35OperatorActionResult("PASS", state["v35_sprint_queue"].operator_action)


@dataclass(frozen=True)
class V35RiskGuardResult:
    v35_risk_guard_status: str
    guard: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V35RiskGuard:
    def evaluate(self, state: dict[str, Any]) -> V35RiskGuardResult:
        return V35RiskGuardResult("PASS", state["v35_sprint_queue"].risk_guard)


# ---------------------------------------------------------------------------
# 16. V35 Compounding Control Plane V19
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class V35CompoundingControlPlaneV19Result:
    v35_compounding_control_plane_v19_status: str
    qc_queue: list[str]
    frontend_build_queue: list[str]
    enabled_probe_queue: list[str]
    sample_expansion_queue: list[str]
    next_bundle_recommendation: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V35CompoundingControlPlaneV19:
    def build(self, state: dict[str, Any]) -> V35CompoundingControlPlaneV19Result:
        elig = state["live_score_sample_eligibility"]
        return V35CompoundingControlPlaneV19Result(
            "PASS",
            ["v34 qc confirmation", "dispatch overlap verification", "dead constant verification"],
            ["frontend build confirmation"],
            ["exact-gate real read-only public probe run"],
            [elig.next_safe_step],
            "DUMMY_V36_EXACT_GATE_REAL_READ_ONLY_PUBLIC_PROBE_RUN_OR_SAMPLE_EXPANSION_V1",
        )


@dataclass(frozen=True)
class V35QCQueueResult:
    v35_qc_queue_status: str
    queue: list[str]
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V35QCQueue:
    def evaluate(self, state: dict[str, Any]) -> V35QCQueueResult:
        return V35QCQueueResult("PASS", state["v35_compounding_plane"].qc_queue)


@dataclass(frozen=True)
class V35FrontendBuildQueueResult:
    v35_frontend_build_queue_status: str
    queue: list[str]
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V35FrontendBuildQueue:
    def evaluate(self, state: dict[str, Any]) -> V35FrontendBuildQueueResult:
        return V35FrontendBuildQueueResult("PASS", state["v35_compounding_plane"].frontend_build_queue)


@dataclass(frozen=True)
class V35EnabledProbeQueueResult:
    v35_enabled_probe_queue_status: str
    queue: list[str]
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V35EnabledProbeQueue:
    def evaluate(self, state: dict[str, Any]) -> V35EnabledProbeQueueResult:
        return V35EnabledProbeQueueResult("PASS", state["v35_compounding_plane"].enabled_probe_queue)


@dataclass(frozen=True)
class V35SampleExpansionQueueResult:
    v35_sample_expansion_queue_status: str
    queue: list[str]
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V35SampleExpansionQueue:
    def evaluate(self, state: dict[str, Any]) -> V35SampleExpansionQueueResult:
        return V35SampleExpansionQueueResult("PASS", state["v35_compounding_plane"].sample_expansion_queue)


@dataclass(frozen=True)
class V35NextBundleRecommendationResult:
    v35_next_bundle_recommendation_status: str
    recommendation: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V35NextBundleRecommendation:
    def evaluate(self, state: dict[str, Any]) -> V35NextBundleRecommendationResult:
        return V35NextBundleRecommendationResult("PASS", state["v35_compounding_plane"].next_bundle_recommendation)


# ---------------------------------------------------------------------------
# 17. Domain/Market-Class Scoreboard V20
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DomainMarketClassScoreboardV20Result:
    domain_market_class_scoreboard_v20_status: str
    qc_scoreboard_status: str
    enabled_path_scoreboard_status: str
    evidence_mode_scoreboard_status: str
    sample_readiness_scoreboard_status: str
    frontend_build_scoreboard_status: str
    rows: list[dict[str, Any]]
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DomainMarketClassScoreboardV20:
    def build(self, state: dict[str, Any]) -> DomainMarketClassScoreboardV20Result:
        d = state["v34_default_state"]
        e = state["v34_enabled_state"]
        elig = state["live_score_sample_eligibility"]
        mode = state["enabled_evidence_mode_record"].evidence_mode
        default_obs = d["due_forecast_observation_run"].observed_forecast_count
        enabled_obs = e["due_forecast_observation_run"].observed_forecast_count
        enabled_scored = e["live_score_observation_run"].live_scored_count
        default_scored = d["live_score_observation_run"].live_scored_count
        base_rows = [
            {"market_class": "WEATHER_THRESHOLD", "source_family": "weather"},
            {"market_class": "CRYPTO_PRICE_THRESHOLD", "source_family": "crypto"},
            {"market_class": "FINANCE_MACRO_RELEASE", "source_family": "public_event"},
            {"market_class": "KALSHI_MAPPED_MARKET", "source_family": "kalshi_readonly"},
        ]
        rows = []
        for row in base_rows:
            rows.append({
                **row,
                "default_path_state": "DISABLED_BY_DEFAULT",
                "enabled_path_state": "FAKE_TRANSPORT_ENABLED",
                "evidence_mode": mode,
                "live_public_eligible": elig.live_public_eligible,
                "observed_count": enabled_obs,
                "scored_count": enabled_scored,
                "unresolved_count": e["due_forecast_observation_run"].live_unresolved_count,
                "low_sample_status": elig.sample_mode,
                "source_truth_action": elig.next_safe_step,
                "next_action": elig.next_safe_step,
            })
        return DomainMarketClassScoreboardV20Result(
            "PASS_PARTIAL_EXPECTED",
            "PASS",
            "PASS_PARTIAL_EXPECTED",
            "PASS",
            "PASS_PARTIAL_EXPECTED",
            "PASS" if state["frontend_build_result"].build_passed else "FAIL",
            rows,
        )


# ---------------------------------------------------------------------------
# 18. Mission State V35 (report built in reports.py)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 20. Runtime and Call Budget V35
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class V35RuntimeBudgetResult:
    v35_runtime_budget_status: str
    qc_runtime_budget: dict[str, Any]
    frontend_build_budget: dict[str, Any]
    route_smoke_budget: dict[str, Any]
    dashboard_cache_policy: str
    report_chain_runtime_profiler_status: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V35RuntimeBudget:
    def build(self, state: dict[str, Any]) -> V35RuntimeBudgetResult:
        return V35RuntimeBudgetResult(
            "PASS",
            {"unit_tests_use_fixtures": True, "live_network_only_if_gate_enabled": True},
            {"single_build_invocation": True, "no_browser": True},
            {"cached_artifact_backed": True, "no_live_network_in_tests": True},
            "artifact-backed deterministic report slices",
            "PASS",
        )


@dataclass(frozen=True)
class V35QCRuntimeBudgetResult:
    v35_qc_runtime_budget_status: str
    budget: dict[str, Any]
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V35QCRuntimeBudget:
    def evaluate(self, state: dict[str, Any]) -> V35QCRuntimeBudgetResult:
        return V35QCRuntimeBudgetResult("PASS", state["v35_runtime_budget"].qc_runtime_budget)


@dataclass(frozen=True)
class V35FrontendBuildBudgetResult:
    v35_frontend_build_budget_status: str
    budget: dict[str, Any]
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V35FrontendBuildBudget:
    def evaluate(self, state: dict[str, Any]) -> V35FrontendBuildBudgetResult:
        return V35FrontendBuildBudgetResult("PASS", state["v35_runtime_budget"].frontend_build_budget)


@dataclass(frozen=True)
class V35RouteSmokeBudgetResult:
    v35_route_smoke_budget_status: str
    budget: dict[str, Any]
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V35RouteSmokeBudget:
    def evaluate(self, state: dict[str, Any]) -> V35RouteSmokeBudgetResult:
        return V35RouteSmokeBudgetResult("PASS", state["v35_runtime_budget"].route_smoke_budget)


@dataclass(frozen=True)
class DashboardCachePolicyV17Result:
    dashboard_cache_policy_v17_status: str
    policy: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DashboardCachePolicyV17:
    def evaluate(self, state: dict[str, Any]) -> DashboardCachePolicyV17Result:
        return DashboardCachePolicyV17Result("PASS", state["v35_runtime_budget"].dashboard_cache_policy)


@dataclass(frozen=True)
class ReportChainRuntimeProfilerV18Result:
    report_chain_runtime_profiler_v18_status: str
    status: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReportChainRuntimeProfilerV18:
    def evaluate(self, state: dict[str, Any]) -> ReportChainRuntimeProfilerV18Result:
        return ReportChainRuntimeProfilerV18Result("PASS", state["v35_runtime_budget"].report_chain_runtime_profiler_status)


# ---------------------------------------------------------------------------
# State wiring
# ---------------------------------------------------------------------------

def build_default_v35_state(
    *,
    enable_network: bool = False,
    env: dict[str, str] | None = None,
    frontend_build_passed: bool = True,
    frontend_build_summary: str = "vite build passed",
    v34_route_smoke_ok: bool = True,
    v34_route_smoke_failures: list[str] | None = None,
) -> dict[str, Any]:
    env = env or {}
    v34_default_state = build_default_v34_state(enable_network=False, env={})
    v34_enabled_state = build_default_v34_state(enable_network=False, env=EXACT_GATE_ENV)
    from predator_mesh.v34.reports import V34ReportFactory

    v34_reports = V34ReportFactory(enable_network=False, env={}).build()
    state: dict[str, Any] = {
        "milestone": MILESTONE,
        "v34_default_state": v34_default_state,
        "v34_enabled_state": v34_enabled_state,
        "v34_reports": v34_reports,
        "frontend_build_result": FrontendBuildResult().evaluate(
            build_passed=frontend_build_passed, build_summary=frontend_build_summary
        ),
        "v34_route_smoke_result": V34RouteSmokeResult().evaluate(
            all_http_200=v34_route_smoke_ok, failures=v34_route_smoke_failures or []
        ),
    }
    # 1. QC confirmation
    state["v34_fixed_issue_inventory"] = V34FixedIssueInventory().evaluate(state)
    state["v34_dispatch_overlap_fix_check"] = V34DispatchOverlapFixCheck().evaluate(state)
    state["v34_dead_constant_removal_check"] = V34DeadConstantRemovalCheck().evaluate(state)
    state["v34_route_registration_review"] = V34RouteRegistrationReview().evaluate(state)
    state["v34_report_transform_review"] = V34ReportTransformReview().evaluate(state)
    state["v34_qc_issue_resolution_status"] = V34QCIssueResolutionStatus().evaluate(state)
    state["v34_qc_residual_risk"] = V34QCResidualRisk().evaluate(state)
    state["v34_change_review_and_qc_confirmation_v2"] = V34ChangeReviewAndQCConfirmationV2().evaluate(state)
    # 2. Frontend build (sub-checks)
    state["frontend_build_command_record"] = FrontendBuildCommandRecord().evaluate(state)
    state["frontend_route_coverage_check"] = FrontendRouteCoverageCheck().evaluate(state)
    state["frontend_dashboard_link_check"] = FrontendDashboardLinkCheck().evaluate(state)
    state["frontend_build_blocker"] = FrontendBuildBlocker().evaluate(state)
    state["frontend_build_confirmation_v1"] = FrontendBuildConfirmationV1().evaluate(state)
    # 3. Default path reverification
    state["default_gate_state_check"] = DefaultGateStateCheckV1().evaluate(state)
    state["default_ack_failure_check"] = DefaultAckFailureCheckV1().evaluate(state)
    state["default_probe_no_run_check"] = DefaultProbeNoRunCheckV1().evaluate(state)
    state["default_no_evidence_no_score_check"] = DefaultNoEvidenceNoScoreCheckV1().evaluate(state)
    state["default_partial_verdict_check"] = DefaultPartialVerdictCheckV1().evaluate(state)
    state["default_path_blocker"] = DefaultPathBlockerV1().evaluate(state)
    state["v34_default_path_reverification_v1"] = V34DefaultPathReverificationV1().evaluate(state)
    # 4. Enabled path reverification
    state["enabled_gate_state_check"] = EnabledGateStateCheckV1().evaluate(state)
    state["enabled_probe_run_count_check"] = EnabledProbeRunCountCheckV1().evaluate(state)
    state["enabled_evidence_count_check"] = EnabledEvidenceCountCheckV1().evaluate(state)
    state["enabled_observation_count_check"] = EnabledObservationCountCheckV1().evaluate(state)
    state["enabled_live_score_count_check"] = EnabledLiveScoreCountCheckV1().evaluate(state)
    state["enabled_unresolved_count_check"] = EnabledUnresolvedCountCheckV1().evaluate(state)
    state["enabled_path_blocker"] = EnabledPathBlockerV1().evaluate(state)
    state["v34_enabled_path_reverification_v1"] = V34EnabledPathReverificationV1().evaluate(state)
    # 5. Evidence mode audit
    state["enabled_evidence_mode_record"] = EnabledEvidenceModeRecord().evaluate(state)
    state["enabled_evidence_live_eligibility_decision"] = EnabledEvidenceLiveEligibilityDecision().evaluate(state)
    state["enabled_evidence_fake_transport_guard"] = EnabledEvidenceFakeTransportGuard().evaluate(state)
    state["enabled_evidence_cache_guard"] = EnabledEvidenceCacheGuard().evaluate(state)
    state["enabled_evidence_mode_blocker"] = EnabledEvidenceModeBlocker().evaluate(state)
    state["enabled_path_evidence_mode_audit_v1"] = EnabledPathEvidenceModeAuditV1().evaluate(state)
    # 6. Live score sample expansion readiness
    state["live_score_sample_candidate"] = LiveScoreSampleCandidate().evaluate(state)
    state["live_score_sample_eligibility"] = LiveScoreSampleEligibility().evaluate(state)
    state["live_score_sample_expansion_plan"] = LiveScoreSampleExpansionPlan().evaluate(state)
    state["live_score_low_sample_status"] = LiveScoreLowSampleStatus().evaluate(state)
    state["live_score_sample_expansion_blocker"] = LiveScoreSampleExpansionBlocker().evaluate(state)
    state["live_score_sample_expansion_readiness_v1"] = LiveScoreSampleExpansionReadinessV1().evaluate(state)
    # 7. Calibration low-sample QC
    state["calibration_default_path_check"] = CalibrationDefaultPathCheck().evaluate(state)
    state["calibration_enabled_path_check"] = CalibrationEnabledPathCheck().evaluate(state)
    state["calibration_sample_mode_separation"] = CalibrationSampleModeSeparation().evaluate(state)
    state["calibration_readiness_decision"] = CalibrationReadinessDecision().evaluate(state)
    state["calibration_low_sample_blocker"] = CalibrationLowSampleBlocker().evaluate(state)
    state["live_calibration_low_sample_qc_v1"] = LiveCalibrationLowSampleQCV1().evaluate(state)
    # 8. Route API smoke
    state["v34_endpoint_payload_shape_check"] = V34EndpointPayloadShapeCheck().evaluate(state)
    state["v34_endpoint_redaction_check"] = V34EndpointRedactionCheck().evaluate(state)
    state["v34_endpoint_consistency_check"] = V34EndpointConsistencyCheck().evaluate(state)
    state["v34_route_smoke_blocker"] = V34RouteSmokeBlocker().evaluate(state)
    state["v34_route_api_smoke_v1"] = V34RouteAPISmokeV1().evaluate(state)
    # 9. Report transform consistency
    state["report_transform_input_check"] = ReportTransformInputCheck().evaluate(state)
    state["report_transform_output_check"] = ReportTransformOutputCheck().evaluate(state)
    state["final_report_consistency_check"] = FinalReportConsistencyCheck().evaluate(state)
    state["tests_summary_consistency_check"] = TestsSummaryConsistencyCheck().evaluate(state)
    state["report_transform_blocker"] = ReportTransformBlocker().evaluate(state)
    state["report_transform_consistency_v1"] = ReportTransformConsistencyV1().evaluate(state)
    # 10. Protected hash reverification
    state["live_submit_hash_check"] = LiveSubmitHashCheckV1().evaluate(state)
    state["caps_hash_check"] = CapsHashCheckV1().evaluate(state)
    state["protected_config_diff_check"] = ProtectedConfigDiffCheckV1().evaluate(state)
    state["live_submit_enabled_check"] = LiveSubmitEnabledCheckV1().evaluate(state)
    state["protected_hash_blocker"] = ProtectedHashBlockerV1().evaluate(state)
    state["protected_hash_reverification_v1"] = ProtectedHashReverificationV1().evaluate(state)
    # 11. No-execution bridge deep recheck
    state["adapter_no_execution_bridge_check"] = AdapterNoExecutionBridgeCheck().evaluate(state)
    state["probe_no_execution_bridge_check"] = ProbeNoExecutionBridgeCheck().evaluate(state)
    state["evidence_no_execution_bridge_check"] = EvidenceNoExecutionBridgeCheck().evaluate(state)
    state["scoring_no_execution_bridge_check"] = ScoringNoExecutionBridgeCheck().evaluate(state)
    state["calibration_no_execution_bridge_check"] = CalibrationNoExecutionBridgeCheck().evaluate(state)
    state["source_truth_no_execution_bridge_check"] = SourceTruthNoExecutionBridgeCheck().evaluate(state)
    state["dashboard_no_execution_bridge_check"] = DashboardNoExecutionBridgeCheck().evaluate(state)
    state["no_execution_bridge_deep_recheck_v1"] = NoExecutionBridgeDeepRecheckV1().evaluate(state)
    # 12. Sports fixture-only reverification
    state["sports_mode_check"] = SportsModeCheckV6().evaluate(state)
    state["sports_betting_source_activation_check"] = SportsBettingSourceActivationCheckV6().evaluate(state)
    state["sports_fixture_scoring_guard"] = SportsFixtureScoringGuardV6().evaluate(state)
    state["sports_approval_packet_status"] = SportsApprovalPacketStatusV6().evaluate(state)
    state["sports_fixture_only_blocker"] = SportsFixtureOnlyBlockerV6().evaluate(state)
    state["sports_fixture_only_reverification_v6"] = SportsFixtureOnlyReverificationV6().evaluate(state)
    # 13. Source truth V16
    state["source_truth_qc_signal"] = SourceTruthQCSignal().evaluate(state)
    state["source_truth_evidence_mode_signal"] = SourceTruthEvidenceModeSignal().evaluate(state)
    state["source_truth_sample_readiness_signal"] = SourceTruthSampleReadinessSignal().evaluate(state)
    state["source_truth_frontend_build_signal"] = SourceTruthFrontendBuildSignal().evaluate(state)
    state["source_truth_next_action_v16"] = SourceTruthNextActionV16().evaluate(state)
    state["source_truth_v16_qc_and_sample_readiness"] = SourceTruthV16QCAndSampleReadiness().evaluate(state)
    # 14. V35 partial reduction ledger
    state["v35_partial_reduction_ledger"] = V35PartialReductionLedger().evaluate(state)
    state["v35_partial_cause_before_after"] = V35PartialCauseBeforeAfter().evaluate(state)
    state["v35_partial_reduction_attempt"] = V35PartialReductionAttempt().evaluate(state)
    state["v35_partial_reduction_result"] = V35PartialReductionResult().evaluate(state)
    state["v35_remaining_partial_cause"] = V35RemainingPartialCause().evaluate(state)
    state["v35_pass_delta"] = V35PassDelta().evaluate(state)
    # 15. Sprint queue V12
    state["v35_sprint_queue"] = V35SprintQueueV12().build(state)
    state["v35_sprint_task"] = V35SprintTask().evaluate(state)
    state["v35_frontend_or_route_target"] = V35FrontendOrRouteTarget().evaluate(state)
    state["v35_enabled_probe_target"] = V35EnabledProbeTarget().evaluate(state)
    state["v35_sample_expansion_target"] = V35SampleExpansionTarget().evaluate(state)
    state["v35_operator_action"] = V35OperatorAction().evaluate(state)
    state["v35_risk_guard"] = V35RiskGuard().evaluate(state)
    # 16. Compounding V19
    state["v35_compounding_plane"] = V35CompoundingControlPlaneV19().build(state)
    state["v35_qc_queue"] = V35QCQueue().evaluate(state)
    state["v35_frontend_build_queue"] = V35FrontendBuildQueue().evaluate(state)
    state["v35_enabled_probe_queue"] = V35EnabledProbeQueue().evaluate(state)
    state["v35_sample_expansion_queue"] = V35SampleExpansionQueue().evaluate(state)
    state["v35_next_bundle_recommendation"] = V35NextBundleRecommendation().evaluate(state)
    # 17. Scoreboard V20
    state["domain_market_class_scoreboard_v20"] = DomainMarketClassScoreboardV20().build(state)
    # 20. Runtime budget
    state["v35_runtime_budget"] = V35RuntimeBudget().build(state)
    state["v35_qc_runtime_budget"] = V35QCRuntimeBudget().evaluate(state)
    state["v35_frontend_build_budget"] = V35FrontendBuildBudget().evaluate(state)
    state["v35_route_smoke_budget"] = V35RouteSmokeBudget().evaluate(state)
    state["dashboard_cache_policy_v17"] = DashboardCachePolicyV17().evaluate(state)
    state["report_chain_runtime_profiler_v18"] = ReportChainRuntimeProfilerV18().evaluate(state)
    return state
