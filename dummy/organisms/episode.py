"""End-to-end deterministic Phase 3 forecast episode orchestration."""

from __future__ import annotations

import math
from typing import Protocol

from autonomy.fees import kalshi_taker_fee_cents

from dummy import VNEXT_MATURITY
from dummy.agents import AgentInvocation, AgentRole, AgentState, InvocationStatus
from dummy.protocols import MessageEnvelope, MessageType
from dummy.world_model import (
    WorldModelValidationError,
    hydrate_issue_world_state,
)

from .agents import activate_organism, build_organism_runtime
from .models import (
    CompetingFuture,
    CAPABILITY_STEP_NAMES,
    DecisionKind,
    EpisodeArtifact,
    EpisodeRequest,
    EpisodeStatus,
    EpisodeStep,
    EpisodeValidationError,
    HeldOutCase,
    IssuedEpisodeArtifact,
    IssueRequest,
    VerifiedSettlement,
    canonical_json,
    digest_json,
    iso,
    thaw_json,
)
from .templates import OrganismTemplate, select_template


class EpisodeSink(Protocol):
    def append(self, artifact: EpisodeArtifact) -> str: ...


CAPABILITY_NAMES = CAPABILITY_STEP_NAMES


def _evidence_by_kind(request: IssueRequest, kind: str):
    matches = tuple(
        item for item in request.evidence if item.payload.get("kind") == kind
    )
    if len(matches) != 1:
        raise EpisodeValidationError(
            f"episode requires exactly one {kind} evidence item"
        )
    return matches[0]


def _optional_evidence_by_kind(request: IssueRequest, kind: str):
    matches = tuple(
        item for item in request.evidence if item.payload.get("kind") == kind
    )
    if len(matches) > 1:
        raise EpisodeValidationError(
            f"episode accepts at most one {kind} evidence item"
        )
    return matches[0] if matches else None


def _freeze_state(
    request: IssueRequest,
    template: OrganismTemplate,
) -> MessageEnvelope:
    quote_evidence = _evidence_by_kind(request, "market_quote")
    incumbent_evidence = _evidence_by_kind(request, "incumbent_forecast")
    calibration_evidence = _optional_evidence_by_kind(request, "calibration_map")
    market = thaw_json(quote_evidence.payload)
    incumbent = thaw_json(incumbent_evidence.payload)
    if market.pop("kind", None) != "market_quote":
        raise EpisodeValidationError("market quote kind is malformed")
    if incumbent.pop("kind", None) != "incumbent_forecast":
        raise EpisodeValidationError("incumbent forecast kind is malformed")
    if str(market.get("market_id", request.market_id)) != request.market_id:
        raise EpisodeValidationError("market quote references a different market")
    if str(incumbent.get("market_id", request.market_id)) != request.market_id:
        raise EpisodeValidationError("incumbent forecast references a different market")
    if str(market.get("status", "")).lower() not in {"open", "active"}:
        raise EpisodeValidationError("market quote is not open")
    try:
        yes_bid = int(market["yes_bid"])
        yes_ask = int(market["yes_ask"])
        no_bid = int(market["no_bid"])
        no_ask = int(market["no_ask"])
        yes_ask_depth = int(market["yes_ask_depth"])
        no_ask_depth = int(market["no_ask_depth"])
    except (KeyError, TypeError, ValueError) as exc:
        raise EpisodeValidationError("market quote is incomplete or malformed") from exc
    if not (
        1 <= yes_bid <= yes_ask <= 99
        and 1 <= no_bid <= no_ask <= 99
        and yes_ask + no_bid == 100
        and yes_bid + no_ask == 100
        and yes_ask_depth >= 0
        and no_ask_depth >= 0
    ):
        raise EpisodeValidationError("market quote is crossed or incoherent")
    try:
        incumbent_probability = float(incumbent["probability_yes"])
        incumbent_uncertainty = float(incumbent["uncertainty"])
    except (KeyError, TypeError, ValueError) as exc:
        raise EpisodeValidationError("incumbent forecast is incomplete") from exc
    if (
        not math.isfinite(incumbent_probability)
        or not 0.0 <= incumbent_probability <= 1.0
        or not math.isfinite(incumbent_uncertainty)
        or not 0.0 <= incumbent_uncertainty <= 0.5
    ):
        raise EpisodeValidationError("incumbent forecast is outside typed bounds")
    if calibration_evidence is None:
        calibration = {
            "verified": False,
            "offset": 0.0,
            "map_version": "unavailable",
        }
    else:
        calibration = thaw_json(calibration_evidence.payload)
        if calibration.pop("kind", None) != "calibration_map":
            raise EpisodeValidationError("calibration map kind is malformed")

    try:
        world_state = hydrate_issue_world_state(request)
    except WorldModelValidationError as exc:
        raise EpisodeValidationError(
            f"Phase 4 world-state hydration failed closed: {exc}"
        ) from exc

    evidence_manifest = [item.to_dict() for item in request.evidence]
    state_payload = {
        "observation_kind": "phase4_frozen_episode_state",
        "state_scope": world_state.schema.scope,
        "template_id": template.template_id,
        "template_digest": template.digest(),
        "market": market,
        "incumbent": incumbent,
        "calibration": calibration,
        "world_state": world_state.to_dict(),
        "evidence_manifest": evidence_manifest,
        "state_version": world_state.snapshot_id,
    }
    effective_time = max(item.observed_at for item in request.evidence)
    return MessageEnvelope.create(
        message_type=MessageType.MARKET_STATE,
        sender="phase4-world-state-freezer-v1",
        market_id=request.market_id,
        issued_at=request.decision_at,
        effective_time=effective_time,
        received_at=request.decision_at,
        model_version=world_state.schema.schema_version,
        policy_version=request.policy_version,
        evidence_ids=tuple(item.evidence_id for item in request.evidence),
        limitations=(
            "phase4_versioned_world_state",
            "missing_optional_state_is_explicit_not_imputed",
            "research_shadow_only",
        ),
        payload=state_payload,
    )


def _invoke(
    *,
    runtime,
    template: OrganismTemplate,
    role: AgentRole,
    request: IssueRequest,
    inputs: tuple[MessageEnvelope, ...],
) -> MessageEnvelope:
    contract = template.contract_for(role)
    invocation = AgentInvocation.create(
        agent_id=contract.agent_id,
        market_id=request.market_id,
        market_type=request.market_type,
        clock_domain=request.clock_domain,
        policy_version=request.policy_version,
        invoked_at=request.decision_at,
        evidence_keys=("frozen_point_in_time_state",),
        input_messages=inputs,
    )
    result = runtime.invoke(invocation)
    if result.status is not InvocationStatus.COMPLETED or len(result.outputs) != 1:
        reasons = ",".join(result.reasons) or "no_output"
        raise EpisodeValidationError(
            f"{role.value} failed closed with {result.status.value}:{reasons}"
        )
    return result.outputs[0]


def _run_agents(
    request: IssueRequest,
    template: OrganismTemplate,
    state: MessageEnvelope,
):
    runtime = build_organism_runtime(template)
    activation_order = activate_organism(runtime, at=request.decision_at)
    prior = _invoke(
        runtime=runtime,
        template=template,
        role=AgentRole.MARKET_PRIOR,
        request=request,
        inputs=(state,),
    )
    incumbent = _invoke(
        runtime=runtime,
        template=template,
        role=AgentRole.SPECIALIST,
        request=request,
        inputs=(state,),
    )
    contrarian = _invoke(
        runtime=runtime,
        template=template,
        role=AgentRole.CONTRARIAN,
        request=request,
        inputs=(prior, incumbent),
    )
    calibration = _invoke(
        runtime=runtime,
        template=template,
        role=AgentRole.CALIBRATOR,
        request=request,
        inputs=(state, incumbent),
    )
    adversary = _invoke(
        runtime=runtime,
        template=template,
        role=AgentRole.ADVERSARY,
        request=request,
        inputs=(prior, incumbent, contrarian, calibration),
    )
    shadow = _invoke(
        runtime=runtime,
        template=template,
        role=AgentRole.SHADOW,
        request=request,
        inputs=(state, prior, incumbent, contrarian, calibration, adversary),
    )
    synthesis = _invoke(
        runtime=runtime,
        template=template,
        role=AgentRole.SYNTHESIZER,
        request=request,
        inputs=(
            state,
            prior,
            incumbent,
            contrarian,
            calibration,
            adversary,
            shadow,
        ),
    )
    for agent_id in reversed(activation_order):
        runtime.lifecycle(agent_id).transition(
            AgentState.RETIRED,
            at=request.decision_at,
            reason="temporary_organism_dissolved_after_issuance",
            evidence_ids=(synthesis.message_id,),
        )
    lifecycle = {
        agent_id: [item.to_dict() for item in runtime.lifecycle(agent_id).history]
        for agent_id in sorted(activation_order)
    }
    return (
        (prior, incumbent, contrarian, calibration, adversary, shadow, synthesis),
        activation_order,
        lifecycle,
    )


def _future(message: MessageEnvelope) -> CompetingFuture:
    return CompetingFuture(
        future_id=message.message_id,
        agent_id=message.sender,
        label=str(message.payload["future_label"]),
        probability_yes=float(message.payload["probability"]),
        source_family=str(message.payload["source_family"]),
        assumptions=tuple(message.payload["assumptions"]),
        failure_conditions=tuple(message.payload["failure_conditions"]),
        evidence_ids=message.evidence_ids,
    )


def _simulate_execution(
    request: IssueRequest,
    state: MessageEnvelope,
    synthesis: MessageEnvelope,
) -> dict[str, object]:
    decision = str(synthesis.payload["decision"])
    candidate = float(synthesis.payload["candidate_probability"])
    market = state.payload["market"]
    if decision == DecisionKind.ABSTAIN.value:
        return {
            "status": "NO_ORDER_ABSTAINED",
            "lane": "shadow",
            "evidence_class": "simulated",
            "realized": False,
            "broker_contacted": False,
            "order_submitted": False,
            "fill_count": 0,
        }
    is_yes = decision == DecisionKind.FORECAST_YES.value
    side = "yes" if is_yes else "no"
    price_key = "yes_ask" if is_yes else "no_ask"
    price = int(market[price_key])
    if not 1 <= price <= 99:
        raise EpisodeValidationError("shadow execution requires a valid witnessed ask")
    depth_key = "yes_ask_depth" if is_yes else "no_ask_depth"
    depth = int(market.get(depth_key, 0))
    fill_count = min(request.max_shadow_contracts, max(0, depth))
    side_probability = candidate if is_yes else 1.0 - candidate
    fee_cents = kalshi_taker_fee_cents(price, fill_count, request.market_id)
    expected_value_cents = round(
        side_probability * 100.0 * fill_count
        - price * fill_count
        - fee_cents,
        6,
    )
    if fill_count == 0 or expected_value_cents <= 0.0:
        fill_count = 0
        fee_cents = 0
        status = "NO_FILL_INSUFFICIENT_DEPTH_OR_NET_EDGE"
    else:
        status = "SIMULATED_WITNESSED_QUOTE_FILL"
    return {
        "status": status,
        "side": side,
        "price_cents": price,
        "available_depth": depth,
        "requested_count": request.max_shadow_contracts,
        "fill_count": fill_count,
        "fee_cents": fee_cents,
        "expected_value_cents": expected_value_cents,
        "lane": "shadow",
        "evidence_class": "simulated",
        "witness_type": "frozen_point_in_time_quote",
        "realized": False,
        "broker_contacted": False,
        "order_submitted": False,
        "order_id": None,
    }


def _settle_shadow_execution(
    execution: dict[str, object],
    *,
    result_yes: bool,
) -> dict[str, object]:
    fill_count = int(execution.get("fill_count", 0))
    if fill_count <= 0:
        return {
            "status": "NO_SHADOW_FILL_TO_GRADE",
            "counterfactual_pnl_cents": None,
            "realized": False,
            "evidence_class": "simulated",
        }
    side = str(execution["side"])
    price = int(execution["price_cents"])
    fee_cents = int(execution["fee_cents"])
    won = result_yes if side == "yes" else not result_yes
    gross_pnl = (100 - price) * fill_count if won else -price * fill_count
    return {
        "status": "SHADOW_FILL_COUNTERFACTUALLY_SETTLED",
        "won": won,
        "gross_pnl_cents": gross_pnl,
        "fee_cents": fee_cents,
        "counterfactual_pnl_cents": gross_pnl - fee_cents,
        "realized": False,
        "evidence_class": "simulated",
    }


def _brier(probability_yes: float, result_yes: bool) -> float:
    return round((probability_yes - float(result_yes)) ** 2, 12)


def _log_loss(probability_yes: float, result_yes: bool) -> float:
    clipped = min(1.0 - 1e-12, max(1e-12, probability_yes))
    value = -(
        float(result_yes) * math.log(clipped)
        + (1.0 - float(result_yes)) * math.log(1.0 - clipped)
    )
    return round(value, 12)


def _grade_agents(
    template: OrganismTemplate,
    messages: tuple[MessageEnvelope, ...],
    result_yes: bool,
) -> list[dict[str, object]]:
    by_sender = {message.sender: message for message in messages}
    prior_agent = template.contract_for(AgentRole.MARKET_PRIOR).agent_id
    prior_probability = float(by_sender[prior_agent].payload["probability"])
    grades: list[dict[str, object]] = []
    for contract in sorted(template.contracts, key=lambda item: item.agent_id):
        message = by_sender[contract.agent_id]
        candidate = message.payload.get("probability")
        if candidate is None and contract.role is AgentRole.CALIBRATOR:
            candidate = message.payload["calibrated_probability"]
        if candidate is None and contract.role is AgentRole.SYNTHESIZER:
            candidate = message.payload["candidate_probability"]
        if candidate is not None:
            parsed = float(candidate)
            brier = _brier(parsed, result_yes)
            grade = {
                "agent_id": contract.agent_id,
                "role": contract.role.value,
                "score_kind": "probabilistic",
                "probability_yes": parsed,
                "brier": brier,
                "log_loss": _log_loss(parsed, result_yes),
                "brier_excess_vs_market": round(
                    brier - _brier(prior_probability, result_yes),
                    12,
                ),
            }
        elif contract.role is AgentRole.ADVERSARY:
            grade = {
                "agent_id": contract.agent_id,
                "role": contract.role.value,
                "score_kind": "diagnostic_coverage",
                "score": 1.0 if message.payload.get("findings") else 0.0,
                "hard_veto": bool(message.payload.get("hard_veto")),
            }
        elif contract.role is AgentRole.SHADOW:
            safe = (
                message.payload.get("execution_authority") is False
                and message.payload.get("incumbent_substitution_allowed") is False
            )
            grade = {
                "agent_id": contract.agent_id,
                "role": contract.role.value,
                "score_kind": "governance_integrity",
                "score": 1.0 if safe else 0.0,
            }
        else:
            raise EpisodeValidationError(
                f"participating agent lacks a grading rule: {contract.agent_id}"
            )
        grades.append(grade)
    if len(grades) != len(template.contracts):
        raise EpisodeValidationError("every participating agent must be graded")
    return grades


def _trust_proposals(grades: list[dict[str, object]]) -> list[dict[str, object]]:
    market_grades = [item for item in grades if item["role"] == AgentRole.MARKET_PRIOR.value]
    if len(market_grades) != 1:
        raise EpisodeValidationError("trust grading requires one market prior")
    market_brier = float(market_grades[0]["brier"])
    proposals: list[dict[str, object]] = []
    for grade in grades:
        if grade["score_kind"] == "probabilistic":
            delta = 0.01 if float(grade["brier"]) < market_brier else -0.01
        else:
            delta = 0.0
        proposals.append(
            {
                "agent_id": grade["agent_id"],
                "proposed_trust_delta": delta,
                "applied": False,
                "authority": "RECOMMEND_ONLY",
                "limitations": ["single_episode_evidence", "human_review_required"],
            }
        )
    return proposals


def _improvement_and_replay(
    request: EpisodeRequest,
    grades: list[dict[str, object]],
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    role_grade = {str(item["role"]): item for item in grades}
    incumbent_brier = float(role_grade[AgentRole.SPECIALIST.value]["brier"])
    market_brier = float(role_grade[AgentRole.MARKET_PRIOR.value]["brier"])
    specialist_delta = 0.05 if incumbent_brier < market_brier else -0.05
    proposal = {
        "proposal_id": digest_json(
            {
                "episode": request.episode_id(),
                "specialist_weight_delta": specialist_delta,
            }
        ),
        "scope": "phase3_template_family_weights",
        "specialist_weight_delta": specialist_delta,
        "bounded": True,
        "protected_paths_touched": [],
        "execution_authority": False,
        "applied": False,
        "human_review_required": True,
    }
    baseline_scores: list[float] = []
    proposed_scores: list[float] = []
    cases: list[dict[str, object]] = []
    proposed_specialist = 0.35 + specialist_delta
    proposed_market = 0.65 - proposed_specialist
    for case in request.held_out_cases:
        counter = min(
            1.0,
            max(
                0.0,
                2.0 * case.market_prior_probability - case.incumbent_probability,
            ),
        )
        baseline = (
            0.50 * case.market_prior_probability
            + 0.35 * case.incumbent_probability
            + 0.15 * counter
        )
        proposed = (
            proposed_market * case.market_prior_probability
            + proposed_specialist * case.incumbent_probability
            + 0.15 * counter
        )
        baseline_brier = _brier(baseline, case.result_yes)
        proposed_brier = _brier(proposed, case.result_yes)
        baseline_scores.append(baseline_brier)
        proposed_scores.append(proposed_brier)
        cases.append(
            {
                **case.to_dict(),
                "baseline_probability": round(baseline, 12),
                "proposed_probability": round(proposed, 12),
                "baseline_brier": baseline_brier,
                "proposed_brier": proposed_brier,
            }
        )
    if cases:
        baseline_mean = round(sum(baseline_scores) / len(baseline_scores), 12)
        proposed_mean = round(sum(proposed_scores) / len(proposed_scores), 12)
        improvement = round(baseline_mean - proposed_mean, 12)
        replay_status = "HELD_OUT_REPLAY_COMPLETE"
    else:
        baseline_mean = None
        proposed_mean = None
        improvement = None
        replay_status = "NO_HELD_OUT_EVIDENCE"
    replay = {
        "replay_id": digest_json(
            {
                "proposal_id": proposal["proposal_id"],
                "cases": cases,
            }
        ),
        "status": replay_status,
        "event_cluster_purged": True,
        "held_out_case_count": len(cases),
        "baseline_mean_brier": baseline_mean,
        "proposed_mean_brier": proposed_mean,
        "brier_improvement": improvement,
        "cases": cases,
        "applied": False,
    }
    positive_direction = (
        len(cases) >= 5 and improvement is not None and improvement > 0.0
    )
    promotion = {
        "candidate_id": digest_json(
            {
                "proposal_id": proposal["proposal_id"],
                "replay_id": replay["replay_id"],
                "positive_direction": positive_direction,
            }
        ),
        "status": "PHASE3_RESEARCH_CANDIDATE_NOT_PROMOTABLE",
        "evidence_direction_positive": positive_direction,
        "eligible_for_human_review": positive_direction,
        "eligible_for_promotion": False,
        "automatic_promotion": False,
        "promotion_authority": "HUMAN_ONLY",
        "incumbent_weights_modified": False,
        "orders_modified": False,
        "capital_modified": False,
        "applied": False,
        "blockers": [
            "phase5_empirical_evidence_gates_unmet",
            "phases_6_through_8_incomplete",
            "no_cluster_corrected_confidence_interval",
            "no_forward_paper_evidence_for_candidate",
            "human_promotion_review_not_requested",
        ],
    }
    return proposal, replay, promotion


def _steps(evidence: tuple[tuple[str, ...], ...]) -> list[dict[str, object]]:
    if not 1 <= len(evidence) <= 20:
        raise EpisodeValidationError("capability evidence step count is invalid")
    return [
        EpisodeStep(
            number=index,
            name=CAPABILITY_NAMES[index - 1],
            status="COMPLETE",
            evidence_ids=step_evidence,
        ).to_dict()
        for index, step_evidence in enumerate(evidence, start=1)
    ]


def issue_episode(request: IssueRequest) -> IssuedEpisodeArtifact:
    """Issue and freeze a decision using pre-close evidence only."""

    template = select_template(
        market_id=request.market_id,
        market_type=request.market_type,
        vertical=request.vertical,
        clock_domain=request.clock_domain,
    )
    state = _freeze_state(request, template)
    messages, activation_order, lifecycle = _run_agents(request, template, state)
    prior, incumbent, contrarian, calibration, adversary, shadow, synthesis = messages
    futures = [_future(prior), _future(incumbent), _future(contrarian)]
    execution = _simulate_execution(request, state, synthesis)
    decision = {
        "message": synthesis.to_dict(),
        "decision_id": synthesis.message_id,
        "decision_kind": synthesis.payload["decision"],
        "candidate_probability": synthesis.payload["candidate_probability"],
        "market_prior_probability": synthesis.payload["market_prior_probability"],
        "incumbent_probability": synthesis.payload["incumbent_probability"],
        "incumbent_substituted": False,
        "frozen": True,
    }
    decision_digest = digest_json(decision)
    execution_id = digest_json(execution)
    episode_id = request.episode_id()
    capability_steps = _steps(
        (
            (state.message_id,),
            (prior.message_id,),
            (state.message_id,),
            (template.digest(),),
            tuple(item.evidence_id for item in request.evidence),
            tuple(item.future_id for item in futures),
            (adversary.message_id,),
            (synthesis.message_id,),
            (synthesis.message_id,),
            (synthesis.message_id,),
            (synthesis.message_id,),
            (decision_digest,),
            (execution_id,),
        )
    )
    return IssuedEpisodeArtifact(
        {
            "schema_version": 1,
            "maturity": VNEXT_MATURITY,
            "episode_id": episode_id,
            "status": EpisodeStatus.ISSUED.value,
            "issue_request": request.semantic_dict(),
            "objective": request.objective,
            "market_id": request.market_id,
            "market_type": request.market_type,
            "vertical": request.vertical.value,
            "clock_domain": request.clock_domain.value,
            "event_cluster_id": request.event_cluster_id,
            "policy_version": request.policy_version,
            "decision_at": iso(request.decision_at),
            "market_close_at": iso(request.market_close_at),
            "template": template.to_dict(),
            "morphology": {
                "activation_order": list(activation_order),
                "temporary": True,
                "dissolved_after_issuance": True,
                "one_specialist_per_market": True,
                "lifecycle": lifecycle,
            },
            "frozen_world_state": state.to_dict(),
            "competing_futures": [item.to_dict() for item in futures],
            "agent_messages": [item.to_dict() for item in messages],
            "decision": decision,
            "decision_digest": decision_digest,
            "shadow_execution": execution,
            "capability_steps": capability_steps,
            "governance": {
                "execution_authority": False,
                "promotion_authority": "HUMAN_ONLY",
                "incumbent_substitution_allowed": False,
                "incumbent_weights_modified": False,
                "orders_modified": False,
                "capital_modified": False,
                "broker_contacted": False,
                "research_ceiling": "SIMULATE",
            },
        }
    )


def complete_issued_episode(
    issued: IssuedEpisodeArtifact,
    *,
    settlement: VerifiedSettlement,
    held_out_cases: tuple[HeldOutCase, ...],
    ledger: EpisodeSink,
) -> EpisodeArtifact:
    """Attach later truth to an immutable issuance without rerunning agents."""

    issued_payload = issued.to_dict()
    issue_request = IssueRequest.from_dict(issued_payload["issue_request"])
    request = EpisodeRequest(
        issue=issue_request,
        settlement=settlement,
        held_out_cases=held_out_cases,
    )
    if request.episode_id() != issued.episode_id:
        raise EpisodeValidationError("settlement request differs from issued episode")
    template = select_template(
        market_id=issue_request.market_id,
        market_type=issue_request.market_type,
        vertical=issue_request.vertical,
        clock_domain=issue_request.clock_domain,
    )
    if issued_payload["template"] != template.to_dict():
        raise EpisodeValidationError("issued template differs from executable template")
    messages = tuple(
        MessageEnvelope.from_dict(item) for item in issued_payload["agent_messages"]
    )
    if len(messages) != len(template.contracts):
        raise EpisodeValidationError("issued episode has an incomplete agent transcript")
    if {message.sender for message in messages} != {
        contract.agent_id for contract in template.contracts
    }:
        raise EpisodeValidationError("issued transcript differs from template contracts")
    execution = issued_payload["shadow_execution"]
    shadow_settlement = _settle_shadow_execution(
        execution,
        result_yes=settlement.result_yes,
    )
    grades = _grade_agents(template, messages, settlement.result_yes)
    trust_proposals = _trust_proposals(grades)
    improvement, replay, promotion = _improvement_and_replay(request, grades)
    grade_id = digest_json({"grades": grades})
    trust_id = digest_json({"trust_proposals": trust_proposals})
    episode_id = issued.episode_id
    first_steps = tuple(
        tuple(step["evidence_ids"])
        for step in issued_payload["capability_steps"]
    )
    later_steps = (
        (settlement.source_reference, digest_json(shadow_settlement)),
        (grade_id,),
        (trust_id,),
        (episode_id,),
        (str(improvement["proposal_id"]),),
        (str(replay["replay_id"]),),
        (str(promotion["candidate_id"]),),
    )
    capability_steps = _steps((*first_steps, *later_steps))
    artifact = EpisodeArtifact(
        {
            **issued_payload,
            "status": EpisodeStatus.DISSOLVED.value,
            "issuance_digest": issued.digest(),
            "settlement": {
                **settlement.to_dict(),
                "lane": "shadow",
                "realized_capital_pnl": False,
                "shadow_fill_grade": shadow_settlement,
            },
            "agent_grades": grades,
            "calibration_and_trust_proposals": trust_proposals,
            "bounded_improvement_proposal": improvement,
            "held_out_replay": replay,
            "promotion_candidate": promotion,
            "capability_steps": capability_steps,
            "ledger_record_id": episode_id,
        }
    )
    record_id = ledger.append(artifact)
    if record_id != episode_id:
        raise EpisodeValidationError("ledger returned a mismatched episode record ID")
    return artifact


def run_complete_episode(
    request: EpisodeRequest,
    *,
    ledger: EpisodeSink,
) -> EpisodeArtifact:
    """Convenience replay: structurally issue first, then attach later truth."""

    issued = issue_episode(request.issue)
    return complete_issued_episode(
        issued,
        settlement=request.settlement,
        held_out_cases=request.held_out_cases,
        ledger=ledger,
    )


def replay_episode(
    request: EpisodeRequest,
    *,
    ledger: EpisodeSink,
) -> EpisodeArtifact:
    """Re-execute the semantic input; callers compare canonical artifact bytes."""

    return run_complete_episode(request, ledger=ledger)


def episode_input_digest(request: EpisodeRequest) -> str:
    return digest_json(request.semantic_dict())


def artifact_bytes(artifact: EpisodeArtifact | IssuedEpisodeArtifact) -> bytes:
    return canonical_json(artifact.to_dict()).encode("utf-8")
