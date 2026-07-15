"""Deterministic handlers used by a temporary Phase 3 forecast organism."""

from __future__ import annotations

import math
from typing import Iterable

from dummy.agents import (
    AgentContract,
    AgentInvocation,
    AgentRole,
    AgentRuntime,
)
from dummy.protocols import MessageEnvelope, MessageType

from .models import EpisodeValidationError
from .templates import OrganismTemplate


def _messages(
    invocation: AgentInvocation,
    message_type: MessageType,
) -> tuple[MessageEnvelope, ...]:
    return tuple(
        item for item in invocation.input_messages if item.message_type is message_type
    )


def _one(
    invocation: AgentInvocation,
    message_type: MessageType,
) -> MessageEnvelope:
    matches = _messages(invocation, message_type)
    if len(matches) != 1:
        raise EpisodeValidationError(
            f"{invocation.agent_id} requires exactly one {message_type.value}"
        )
    return matches[0]


def _parents(invocation: AgentInvocation) -> tuple[str, ...]:
    return tuple(message.message_id for message in invocation.input_messages)


def _evidence(invocation: AgentInvocation) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                evidence_id
                for message in invocation.input_messages
                for evidence_id in (*message.evidence_ids, message.message_id)
            }
        )
    )


def _effective_time(invocation: AgentInvocation):
    return min(message.effective_time for message in invocation.input_messages)


def _bounded(value: float) -> float:
    return round(min(1.0, max(0.0, float(value))), 12)


def _world_state_version(invocation: AgentInvocation) -> str:
    versions: list[str] = []
    for message in invocation.input_messages:
        key = (
            "state_version"
            if message.message_type is MessageType.MARKET_STATE
            else "world_state_version"
        )
        version = str(message.payload.get(key, ""))
        if not version.strip():
            raise EpisodeValidationError(
                f"{invocation.agent_id} received input without world-state version"
            )
        versions.append(version)
    if len(set(versions)) != 1:
        raise EpisodeValidationError(
            f"{invocation.agent_id} received mixed world-state versions"
        )
    return versions[0]


def _forecast_by_role(
    invocation: AgentInvocation,
    role: str,
) -> MessageEnvelope:
    matches = tuple(
        item
        for item in _messages(invocation, MessageType.FORECAST)
        if item.payload.get("organism_role") == role
    )
    if len(matches) != 1:
        raise EpisodeValidationError(f"missing unique {role} forecast")
    return matches[0]


class FrozenMarketPriorAgent:
    def __init__(self, contract: AgentContract) -> None:
        self.contract = contract

    def __call__(self, invocation: AgentInvocation) -> MessageEnvelope:
        state = _one(invocation, MessageType.MARKET_STATE)
        market = state.payload.get("market", {})
        if market.get("status") not in {"open", "active"}:
            raise EpisodeValidationError("market is not open")
        bid = int(market["yes_bid"])
        ask = int(market["yes_ask"])
        if not 1 <= bid <= ask <= 99:
            raise EpisodeValidationError("market prior requires an uncrossed yes book")
        probability_yes = round((bid + ask) / 200.0, 12)
        return MessageEnvelope.create(
            message_type=MessageType.FORECAST,
            sender=self.contract.agent_id,
            market_id=invocation.market_id,
            issued_at=invocation.invoked_at,
            effective_time=state.effective_time,
            received_at=invocation.invoked_at,
            model_version=self.contract.version,
            policy_version=invocation.policy_version,
            causal_parents=(state.message_id,),
            evidence_ids=state.evidence_ids,
            limitations=("market_price_is_anchor_not_truth", "shadow_only"),
            payload={
                "world_state_version": _world_state_version(invocation),
                "probability": probability_yes,
                "uncertainty": round(max(0.01, (ask - bid) / 200.0), 12),
                "organism_role": AgentRole.MARKET_PRIOR.value,
                "future_label": "market_consensus_continues",
                "assumptions": ["visible_yes_book_is_actionable"],
                "failure_conditions": [
                    "book_stales_before_decision",
                    "visible_liquidity_is_not_fillable",
                ],
                "source_family": self.contract.source_family,
            },
        )


class FrozenIncumbentAgent:
    def __init__(self, contract: AgentContract) -> None:
        self.contract = contract

    def __call__(self, invocation: AgentInvocation) -> MessageEnvelope:
        state = _one(invocation, MessageType.MARKET_STATE)
        incumbent = state.payload.get("incumbent", {})
        probability_yes = float(incumbent["probability_yes"])
        uncertainty = float(incumbent["uncertainty"])
        if not math.isfinite(probability_yes) or not 0.0 <= probability_yes <= 1.0:
            raise EpisodeValidationError("incumbent probability is invalid")
        if not math.isfinite(uncertainty) or not 0.0 <= uncertainty <= 0.5:
            raise EpisodeValidationError("incumbent uncertainty is invalid")
        source_family = str(incumbent.get("source_family", ""))
        if not source_family.strip():
            raise EpisodeValidationError("incumbent source family is missing")
        if source_family != self.contract.source_family:
            raise EpisodeValidationError(
                "incumbent source family differs from registered contract"
            )
        return MessageEnvelope.create(
            message_type=MessageType.FORECAST,
            sender=self.contract.agent_id,
            market_id=invocation.market_id,
            issued_at=invocation.invoked_at,
            effective_time=state.effective_time,
            received_at=invocation.invoked_at,
            model_version=str(incumbent.get("model_version", self.contract.version)),
            policy_version=invocation.policy_version,
            causal_parents=(state.message_id,),
            evidence_ids=state.evidence_ids,
            limitations=("incumbent_output_is_compared_not_substituted", "shadow_only"),
            payload={
                "world_state_version": _world_state_version(invocation),
                "probability": round(probability_yes, 12),
                "uncertainty": round(uncertainty, 12),
                "organism_role": AgentRole.SPECIALIST.value,
                "future_label": "incumbent_specialist_case",
                "assumptions": list(
                    incumbent.get("assumptions", ["incumbent_features_remain_valid"])
                ),
                "failure_conditions": list(
                    incumbent.get(
                        "failure_conditions",
                        ["incumbent_regime_or_inputs_are_misspecified"],
                    )
                ),
                "source_family": source_family,
                "incumbent_source": str(incumbent.get("source", "incumbent")),
            },
        )


class ContrarianAgent:
    def __init__(self, contract: AgentContract) -> None:
        self.contract = contract

    def __call__(self, invocation: AgentInvocation) -> MessageEnvelope:
        prior = _forecast_by_role(invocation, AgentRole.MARKET_PRIOR.value)
        incumbent = _forecast_by_role(invocation, AgentRole.SPECIALIST.value)
        prior_probability = float(prior.payload["probability"])
        incumbent_probability = float(incumbent.payload["probability"])
        counter_probability = _bounded(2.0 * prior_probability - incumbent_probability)
        return MessageEnvelope.create(
            message_type=MessageType.COUNTERFORECAST,
            sender=self.contract.agent_id,
            market_id=invocation.market_id,
            issued_at=invocation.invoked_at,
            effective_time=_effective_time(invocation),
            received_at=invocation.invoked_at,
            model_version=self.contract.version,
            policy_version=invocation.policy_version,
            causal_parents=_parents(invocation),
            evidence_ids=_evidence(invocation),
            limitations=("structured_countercase_not_independent_alpha", "shadow_only"),
            payload={
                "world_state_version": _world_state_version(invocation),
                "probability": counter_probability,
                "uncertainty": max(
                    float(prior.payload.get("uncertainty", 0.0)),
                    float(incumbent.payload.get("uncertainty", 0.0)),
                ),
                "organism_role": AgentRole.CONTRARIAN.value,
                "future_label": "specialist_edge_is_regime_error",
                "assumptions": [
                    "market_anchor_contains_information_missing_from_specialist",
                    "specialist_edge_may_reverse",
                ],
                "failure_conditions": [
                    "incumbent_has_verified_independent_information",
                    "market_anchor_is_stale_or_manipulated",
                ],
                "source_family": self.contract.source_family,
            },
        )


class CalibrationProposalAgent:
    def __init__(self, contract: AgentContract) -> None:
        self.contract = contract

    def __call__(self, invocation: AgentInvocation) -> MessageEnvelope:
        state = _one(invocation, MessageType.MARKET_STATE)
        incumbent = _forecast_by_role(invocation, AgentRole.SPECIALIST.value)
        calibration = state.payload.get("calibration", {})
        verified = calibration.get("verified") is True
        requested_offset = float(calibration.get("offset", 0.0)) if verified else 0.0
        applied_offset = round(min(0.03, max(-0.03, requested_offset)), 12)
        original = float(incumbent.payload["probability"])
        calibrated = _bounded(original + applied_offset)
        limitations = ["proposal_only", "does_not_rewrite_incumbent"]
        if not verified:
            limitations.append("unverified_calibration_map_not_applied")
        return MessageEnvelope.create(
            message_type=MessageType.CALIBRATION_UPDATE,
            sender=self.contract.agent_id,
            market_id=invocation.market_id,
            issued_at=invocation.invoked_at,
            effective_time=_effective_time(invocation),
            received_at=invocation.invoked_at,
            model_version=str(calibration.get("map_version", self.contract.version)),
            policy_version=invocation.policy_version,
            causal_parents=_parents(invocation),
            evidence_ids=_evidence(invocation),
            limitations=tuple(limitations),
            payload={
                "world_state_version": _world_state_version(invocation),
                "base_forecast_id": incumbent.message_id,
                "original_probability": original,
                "calibrated_probability": calibrated,
                "requested_offset": requested_offset,
                "applied_offset": applied_offset,
                "verified_map": verified,
                "proposal_only": True,
                "organism_role": AgentRole.CALIBRATOR.value,
            },
        )


class AdversarialAgent:
    def __init__(self, contract: AgentContract) -> None:
        self.contract = contract

    def __call__(self, invocation: AgentInvocation) -> MessageEnvelope:
        forecasts = _messages(invocation, MessageType.FORECAST)
        counter = _one(invocation, MessageType.COUNTERFORECAST)
        calibration = _one(invocation, MessageType.CALIBRATION_UPDATE)
        probabilities = [float(item.payload["probability"]) for item in forecasts]
        probabilities.append(float(counter.payload["probability"]))
        spread = round(max(probabilities) - min(probabilities), 12)
        base_uncertainty = max(
            float(item.payload.get("uncertainty", 0.0))
            for item in (*forecasts, counter)
        )
        epistemic_uncertainty = round(
            min(0.5, max(base_uncertainty, spread / 2.0)),
            12,
        )
        hard_veto = spread > 0.45 or abs(float(calibration.payload["applied_offset"])) > 0.03
        findings = ["countercase_generated", "forecast_dispersion_measured"]
        if spread >= 0.20:
            findings.append("material_model_disagreement")
        if calibration.payload.get("verified_map") is not True:
            findings.append("calibration_map_unverified")
        message_type = MessageType.VETO if hard_veto else MessageType.UNCERTAINTY
        payload = {
            "world_state_version": _world_state_version(invocation),
            "organism_role": AgentRole.ADVERSARY.value,
            "forecast_spread": spread,
            "epistemic_uncertainty": epistemic_uncertainty,
            "hard_veto": hard_veto,
            "findings": sorted(findings),
            "attacked_message_ids": sorted(item.message_id for item in invocation.input_messages),
            "source_family": self.contract.source_family,
        }
        if message_type is MessageType.VETO:
            payload["reason"] = "adversarial_hard_limit"
        return MessageEnvelope.create(
            message_type=message_type,
            sender=self.contract.agent_id,
            market_id=invocation.market_id,
            issued_at=invocation.invoked_at,
            effective_time=_effective_time(invocation),
            received_at=invocation.invoked_at,
            model_version=self.contract.version,
            policy_version=invocation.policy_version,
            causal_parents=_parents(invocation),
            evidence_ids=_evidence(invocation),
            limitations=("diagnostic_not_forecast_alpha", "shadow_only"),
            payload=payload,
        )


class ShadowControllerAgent:
    """Guard research authority and incumbent separation; never add authority."""

    def __init__(self, contract: AgentContract) -> None:
        self.contract = contract

    def __call__(self, invocation: AgentInvocation) -> MessageEnvelope:
        upstream_vetoes = _messages(invocation, MessageType.VETO)
        blockers = [str(item.payload.get("reason", "upstream_veto")) for item in upstream_vetoes]
        message_type = MessageType.VETO if blockers else MessageType.UNCERTAINTY
        payload = {
            "world_state_version": _world_state_version(invocation),
            "organism_role": AgentRole.SHADOW.value,
            "hard_veto": bool(blockers),
            "blockers": sorted(blockers),
            "execution_lane": "shadow",
            "evidence_class": "simulated",
            "realized": False,
            "execution_authority": False,
            "promotion_authority": "HUMAN_ONLY",
            "incumbent_substitution_allowed": False,
            "authority_can_only_contract": True,
        }
        if blockers:
            payload["reason"] = "shadow_controller_upstream_veto"
        return MessageEnvelope.create(
            message_type=message_type,
            sender=self.contract.agent_id,
            market_id=invocation.market_id,
            issued_at=invocation.invoked_at,
            effective_time=_effective_time(invocation),
            received_at=invocation.invoked_at,
            model_version=self.contract.version,
            policy_version=invocation.policy_version,
            causal_parents=_parents(invocation),
            evidence_ids=_evidence(invocation),
            limitations=("shadow_only", "cannot_expand_authority"),
            payload=payload,
        )


class SynthesizerAgent:
    MARKET_WEIGHT = 0.50
    SPECIALIST_WEIGHT = 0.35
    COUNTER_WEIGHT = 0.15

    def __init__(self, contract: AgentContract, *, shadow_agent_id: str) -> None:
        self.contract = contract
        self.shadow_agent_id = shadow_agent_id

    def __call__(self, invocation: AgentInvocation) -> MessageEnvelope:
        prior = _forecast_by_role(invocation, AgentRole.MARKET_PRIOR.value)
        incumbent = _forecast_by_role(invocation, AgentRole.SPECIALIST.value)
        counter = _one(invocation, MessageType.COUNTERFORECAST)
        calibration = _one(invocation, MessageType.CALIBRATION_UPDATE)
        vetoes = _messages(invocation, MessageType.VETO)
        uncertainties = tuple(
            item
            for item in _messages(invocation, MessageType.UNCERTAINTY)
            if item.sender != self.shadow_agent_id
        )
        prior_probability = float(prior.payload["probability"])
        incumbent_probability = float(incumbent.payload["probability"])
        calibrated_probability = float(calibration.payload["calibrated_probability"])
        counter_probability = float(counter.payload["probability"])
        candidate = round(
            self.MARKET_WEIGHT * prior_probability
            + self.SPECIALIST_WEIGHT * calibrated_probability
            + self.COUNTER_WEIGHT * counter_probability,
            12,
        )
        spread = round(
            max(prior_probability, incumbent_probability, counter_probability)
            - min(prior_probability, incumbent_probability, counter_probability),
            12,
        )
        epistemic = max(
            [float(incumbent.payload.get("uncertainty", 0.5))]
            + [float(item.payload.get("epistemic_uncertainty", 0.0)) for item in uncertainties]
        )
        epistemic = round(min(0.5, epistemic), 12)
        confidence = {
            "evidence_coverage": 1.0,
            "family_independence": round(2.0 / 3.0, 12),
            "calibration_support": 0.75 if calibration.payload["verified_map"] else 0.4,
            "stability": round(max(0.0, 1.0 - 2.0 * epistemic), 12),
        }
        confidence["total"] = round(sum(confidence.values()) / 4.0, 12)
        edge = round(candidate - prior_probability, 12)
        expected_information_gain = round(spread * epistemic, 12)
        additional_analysis_useful = expected_information_gain >= 0.035
        abstain_reasons: list[str] = []
        if vetoes:
            abstain_reasons.append("shadow_or_adversarial_veto")
        if epistemic > 0.22:
            abstain_reasons.append("epistemic_uncertainty_above_limit")
        if confidence["total"] < 0.45:
            abstain_reasons.append("decomposed_confidence_below_floor")
        if abs(edge) < 0.015:
            abstain_reasons.append("edge_inside_no_edge_band")
        decision = (
            "ABSTAIN"
            if abstain_reasons
            else ("FORECAST_YES" if edge > 0.0 else "FORECAST_NO")
        )
        common_payload = {
            "world_state_version": _world_state_version(invocation),
            "candidate_probability": candidate,
            "decision": decision,
            "uncertainty": epistemic,
            "market_prior_probability": prior_probability,
            "incumbent_probability": incumbent_probability,
            "incumbent_comparison_delta": round(candidate - incumbent_probability, 12),
            "market_comparison_delta": edge,
            "family_weights": {
                "market-price": self.MARKET_WEIGHT,
                "incumbent": self.SPECIALIST_WEIGHT,
                "countercase": self.COUNTER_WEIGHT,
            },
            "confidence_decomposition": confidence,
            "knowledge_boundaries": {
                "known_unknowns": [
                    "fillability_after_decision",
                    "unobserved_regime_change",
                    "source_family_dependence",
                ],
                "epistemic_uncertainty": epistemic,
                "forecast_spread": spread,
            },
            "additional_analysis": {
                "useful": additional_analysis_useful,
                "expected_information_gain": expected_information_gain,
                "performed": False,
                "reason": "deterministic_phase3_budget_complete",
            },
            "abstain_reasons": sorted(abstain_reasons),
            "incumbent_substituted": False,
            "organism_role": AgentRole.SYNTHESIZER.value,
            "source_family": self.contract.source_family,
        }
        message_type = MessageType.ABSTENTION if abstain_reasons else MessageType.FORECAST
        if message_type is MessageType.FORECAST:
            common_payload["probability"] = candidate
        return MessageEnvelope.create(
            message_type=message_type,
            sender=self.contract.agent_id,
            market_id=invocation.market_id,
            issued_at=invocation.invoked_at,
            effective_time=_effective_time(invocation),
            received_at=invocation.invoked_at,
            model_version=self.contract.version,
            policy_version=invocation.policy_version,
            causal_parents=_parents(invocation),
            evidence_ids=_evidence(invocation),
            limitations=(
                "experimental_sovereign_forecasting",
                "report_only",
                "shadow_only",
            ),
            payload=common_payload,
        )


def build_organism_runtime(template: OrganismTemplate) -> AgentRuntime:
    """Build a sealed and inactive runtime without external reads or writes."""

    contracts = {contract.role: contract for contract in template.contracts}
    runtime = AgentRuntime()
    runtime.register(
        contracts[AgentRole.MARKET_PRIOR],
        FrozenMarketPriorAgent(contracts[AgentRole.MARKET_PRIOR]),
    )
    runtime.register(
        contracts[AgentRole.SPECIALIST],
        FrozenIncumbentAgent(contracts[AgentRole.SPECIALIST]),
    )
    runtime.register(
        contracts[AgentRole.CONTRARIAN],
        ContrarianAgent(contracts[AgentRole.CONTRARIAN]),
    )
    runtime.register(
        contracts[AgentRole.CALIBRATOR],
        CalibrationProposalAgent(contracts[AgentRole.CALIBRATOR]),
    )
    runtime.register(
        contracts[AgentRole.ADVERSARY],
        AdversarialAgent(contracts[AgentRole.ADVERSARY]),
    )
    runtime.register(
        contracts[AgentRole.SHADOW],
        ShadowControllerAgent(contracts[AgentRole.SHADOW]),
    )
    runtime.register(
        contracts[AgentRole.SYNTHESIZER],
        SynthesizerAgent(
            contracts[AgentRole.SYNTHESIZER],
            shadow_agent_id=contracts[AgentRole.SHADOW].agent_id,
        ),
    )
    runtime.seal()
    return runtime


def activate_organism(runtime: AgentRuntime, *, at) -> tuple[str, ...]:
    for agent_id in runtime.registry.dependency_order:
        runtime.activate(agent_id, at=at)
    return runtime.registry.dependency_order


def collect_outputs(results: Iterable) -> tuple[MessageEnvelope, ...]:
    return tuple(output for result in results for output in result.outputs)
