"""Typed, fail-closed binding for operational model probability influence.

This module does not grant authority.  It records which exact forecast and
proposal consumed a probability and lets the central live firewall re-check a
fresh :class:`ModelProbabilityAuthorityRegistry` decision at the final sink.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
import hashlib
import json
from typing import Any

from core.ontology import (
    Forecast,
    LiveOrderRequest,
    ModelInfluenceAttestation,
    ProbabilityInfluenceKind,
)
from forecasting.model_probability_authority import (
    ModelProbabilityAuthorityDecision,
    ModelProbabilityAuthorityRegistry,
    is_sports_model_market,
    model_probability_scope,
)


MODEL_INFLUENCE_ATTESTATION_TTL = timedelta(seconds=30)
MODEL_INFLUENCE_ATTESTATION_MAX_FUTURE_SKEW = timedelta(seconds=5)


def _decimal_text(value: Decimal | int | str) -> str:
    parsed = Decimal(str(value))
    if not parsed.is_finite():
        raise ValueError("non-finite decimal cannot be attested")
    if parsed == 0:
        return "0"
    return format(parsed.normalize(), "f")


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("attested datetime must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _utc_datetime(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("attestation clock must be timezone-aware")
    return value.astimezone(timezone.utc)


def _context_expiration(
    request: LiveOrderRequest,
    forecast: Forecast,
) -> datetime:
    """Return the earliest digest-bound forecast or proposal expiration."""
    expirations = [_utc_datetime(forecast.expiration)]
    if request.expiration_ts is not None:
        try:
            expirations.append(
                datetime.fromtimestamp(request.expiration_ts, tz=timezone.utc)
            )
        except (OSError, OverflowError, ValueError) as exc:
            raise ValueError("proposal expiration is invalid") from exc
    return min(expirations)


def _canonical_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return _decimal_text(value)
    if isinstance(value, datetime):
        return _utc_text(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, float):
        return _decimal_text(str(value))
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"unsupported attestation value: {type(value).__name__}")


def _sha256(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        _canonical_value(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest().upper()


def forecast_binding_sha256(forecast: Forecast) -> str:
    """Bind all operational probability, edge, identity, and proof fields."""
    return _sha256(
        {
            "schema_version": "operational_forecast_binding_v1",
            "market_ticker": forecast.market_ticker,
            "contract_ticker": forecast.contract_ticker,
            "event_title": forecast.event_title,
            "contract_title": forecast.contract_title,
            "market_implied_probability": forecast.market_implied_probability,
            "dummy_probability": forecast.dummy_probability,
            "probability_delta": forecast.probability_delta,
            "confidence_score": forecast.confidence_score,
            "uncertainty_band": forecast.uncertainty_band,
            "expected_edge": forecast.expected_edge,
            "edge_after_fees": forecast.edge_after_fees,
            "source_summary": forecast.source_summary,
            "model_summary": forecast.model_summary,
            "calibration_notes": forecast.calibration_notes,
            "timestamp": forecast.timestamp,
            "expiration": forecast.expiration,
            "proof_reference": forecast.proof_reference,
        }
    )


def _proposal_binding_payload(values: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "operational_proposal_binding_v1",
        "proposal_id": values.get("proposal_id"),
        "market_ticker": values.get("market_ticker"),
        "contract_ticker": values.get("contract_ticker"),
        "side": values.get("side"),
        "price_cents": values.get("price_cents"),
        "size": values.get("size"),
        "strategy_proof_reference": values.get("strategy_proof_reference"),
        "forecast_proof_reference": values.get("forecast_proof_reference"),
        "adapter_name": values.get("adapter_name"),
        "liquidity_role": values.get("liquidity_role", "maker"),
        "risk_state_sha256": values.get("risk_state_sha256"),
        "risk_snapshot": values.get("risk_snapshot") or {},
        "expiration_ts": values.get("expiration_ts"),
    }


def proposal_binding_sha256(values: Mapping[str, Any] | LiveOrderRequest) -> str:
    if isinstance(values, LiveOrderRequest):
        raw: Mapping[str, Any] = values.model_dump(
            exclude={"model_influence_attestation"}
        )
    else:
        raw = values
    return _sha256(_proposal_binding_payload(raw))


def _attestation_body(
    *,
    influence_kind: ProbabilityInfluenceKind,
    model_probability_authority: Decimal,
    authority_scope: str | None,
    authority_evidence_ref: str | None,
    market_category: str | None,
    live_phase: bool | None,
    supporting_model_output_reference: str | None,
    issued_at: datetime,
    forecast_digest: str,
    proposal_digest: str,
) -> dict[str, Any]:
    return {
        "schema_version": "operational_model_influence_v1",
        "influence_kind": influence_kind,
        "model_probability_authority": model_probability_authority,
        "authority_scope": authority_scope,
        "authority_evidence_ref": authority_evidence_ref,
        "market_category": market_category,
        "live_phase": live_phase,
        "supporting_model_output_reference": supporting_model_output_reference,
        "issued_at": issued_at,
        "forecast_binding_sha256": forecast_digest,
        "proposal_binding_sha256": proposal_digest,
    }


def build_model_influence_attestation(
    forecast: Forecast,
    request_fields: Mapping[str, Any],
    *,
    authority_decision: ModelProbabilityAuthorityDecision | None = None,
    market_category: str | None = None,
    live_phase: bool | None = None,
    supporting_model_output_reference: str | None = None,
    issued_at: datetime | None = None,
) -> ModelInfluenceAttestation:
    """Create an explicit quant-only or model-weighted request attestation.

    Only a typed, already-authorized registry decision can produce a
    ``MODEL_WEIGHTED`` claim.  The firewall still re-evaluates the registry;
    this builder is evidence plumbing, not an authority source.
    """
    if request_fields.get("market_ticker") != forecast.market_ticker:
        raise ValueError("request market does not match attested forecast")
    if request_fields.get("contract_ticker") != forecast.contract_ticker:
        raise ValueError("request contract does not match attested forecast")
    if request_fields.get("forecast_proof_reference") != forecast.proof_reference:
        raise ValueError("request forecast proof does not match attested forecast")

    decision = authority_decision
    weighted = bool(
        decision is not None
        and decision.authorized
        and decision.weight > 0
    )
    kind = (
        ProbabilityInfluenceKind.MODEL_WEIGHTED
        if weighted
        else ProbabilityInfluenceKind.QUANT_ONLY
    )
    weight = decision.weight if weighted and decision is not None else Decimal("0")
    scope = decision.scope if decision is not None else None
    evidence_ref = decision.evidence_ref if weighted and decision is not None else None
    if weighted:
        if (
            is_sports_model_market(
                ticker=forecast.contract_ticker,
                category=market_category or "",
            )
            and live_phase is not True
            and live_phase is not False
        ):
            raise ValueError(
                "model-weighted sports attestation requires explicit market phase"
            )
        expected_scope = model_probability_scope(
            ticker=forecast.contract_ticker,
            title=f"{forecast.event_title} {forecast.contract_title}",
            category=market_category or "",
            decision_at=forecast.timestamp,
            expiration=forecast.expiration,
            live_phase=live_phase,
        )
        if scope != expected_scope:
            raise ValueError("authority decision scope does not match forecast context")
    now = issued_at or datetime.now(timezone.utc)
    forecast_digest = forecast_binding_sha256(forecast)
    proposal_digest = proposal_binding_sha256(request_fields)
    body = _attestation_body(
        influence_kind=kind,
        model_probability_authority=weight,
        authority_scope=scope,
        authority_evidence_ref=evidence_ref,
        market_category=market_category,
        live_phase=live_phase,
        supporting_model_output_reference=supporting_model_output_reference,
        issued_at=now,
        forecast_digest=forecast_digest,
        proposal_digest=proposal_digest,
    )
    return ModelInfluenceAttestation(
        **body,
        attestation_sha256=_sha256(body),
    )


@dataclass(frozen=True)
class ModelInfluenceVerification:
    valid: bool
    reason: str


def verify_model_influence_attestation(
    request: LiveOrderRequest,
    forecast: Forecast,
    *,
    authority_registry: ModelProbabilityAuthorityRegistry | None = None,
    now: datetime | None = None,
) -> ModelInfluenceVerification:
    """Verify exact bindings, bounded freshness, and model authority.

    Every attestation, including ``QUANT_ONLY``, expires thirty seconds after
    it is issued and never outlives the bound forecast or proposal.  A newly
    issued attestation also cannot refresh an old forecast.  The derived expiry
    uses only fields already covered by the attestation digests.
    """
    attestation = request.model_influence_attestation
    if attestation is None:
        return ModelInfluenceVerification(False, "model_influence_attestation_missing")
    try:
        expected_forecast = forecast_binding_sha256(forecast)
        expected_proposal = proposal_binding_sha256(request)
        body = _attestation_body(
            influence_kind=attestation.influence_kind,
            model_probability_authority=attestation.model_probability_authority,
            authority_scope=attestation.authority_scope,
            authority_evidence_ref=attestation.authority_evidence_ref,
            market_category=attestation.market_category,
            live_phase=attestation.live_phase,
            supporting_model_output_reference=attestation.supporting_model_output_reference,
            issued_at=attestation.issued_at,
            forecast_digest=attestation.forecast_binding_sha256,
            proposal_digest=attestation.proposal_binding_sha256,
        )
        expected_attestation = _sha256(body)
        now_utc = _utc_datetime(now or datetime.now(timezone.utc))
        issued_at = _utc_datetime(attestation.issued_at)
        forecast_at = _utc_datetime(forecast.timestamp)
        context_expiration = _context_expiration(request, forecast)
    except (InvalidOperation, TypeError, ValueError):
        return ModelInfluenceVerification(False, "model_influence_attestation_invalid")

    if attestation.forecast_binding_sha256 != expected_forecast:
        return ModelInfluenceVerification(False, "model_influence_forecast_binding_mismatch")
    if attestation.proposal_binding_sha256 != expected_proposal:
        return ModelInfluenceVerification(False, "model_influence_proposal_binding_mismatch")
    if attestation.attestation_sha256 != expected_attestation:
        return ModelInfluenceVerification(False, "model_influence_attestation_digest_mismatch")
    if issued_at - now_utc > MODEL_INFLUENCE_ATTESTATION_MAX_FUTURE_SKEW:
        return ModelInfluenceVerification(
            False,
            "model_influence_attestation_issued_in_future",
        )
    if forecast_at - now_utc > MODEL_INFLUENCE_ATTESTATION_MAX_FUTURE_SKEW:
        return ModelInfluenceVerification(
            False,
            "model_influence_attestation_time_invalid",
        )
    if forecast_at - issued_at > MODEL_INFLUENCE_ATTESTATION_MAX_FUTURE_SKEW:
        return ModelInfluenceVerification(
            False,
            "model_influence_attestation_time_invalid",
        )
    if context_expiration <= max(issued_at, forecast_at):
        return ModelInfluenceVerification(
            False,
            "model_influence_attestation_expiry_invalid",
        )
    freshness_expiration = min(
        issued_at + MODEL_INFLUENCE_ATTESTATION_TTL,
        forecast_at + MODEL_INFLUENCE_ATTESTATION_TTL,
    )
    if now_utc >= freshness_expiration:
        return ModelInfluenceVerification(False, "model_influence_attestation_stale")
    if now_utc >= context_expiration:
        return ModelInfluenceVerification(False, "model_influence_attestation_expired")
    if (
        is_sports_model_market(
            ticker=request.market_ticker,
            category=attestation.market_category or "",
        )
        and attestation.live_phase is not True
        and attestation.live_phase is not False
    ):
        return ModelInfluenceVerification(
            False,
            "sports_phase_unknown_or_ambiguous",
        )
    if attestation.influence_kind is ProbabilityInfluenceKind.QUANT_ONLY:
        return ModelInfluenceVerification(True, "quant_only_probability_attested")

    try:
        expected_scope = model_probability_scope(
            ticker=forecast.contract_ticker,
            title=f"{forecast.event_title} {forecast.contract_title}",
            category=attestation.market_category or "",
            decision_at=forecast.timestamp,
            expiration=forecast.expiration,
            live_phase=attestation.live_phase,
        )
    except Exception:
        return ModelInfluenceVerification(False, "model_influence_scope_unverifiable")
    if attestation.authority_scope != expected_scope:
        return ModelInfluenceVerification(False, "model_influence_scope_mismatch")

    registry = authority_registry or ModelProbabilityAuthorityRegistry()
    decision = registry.evaluate(expected_scope, now=now_utc)
    if not decision.authorized or decision.weight <= 0:
        return ModelInfluenceVerification(False, "model_probability_authority_not_current")
    if decision.weight != attestation.model_probability_authority:
        return ModelInfluenceVerification(False, "model_probability_authority_weight_mismatch")
    if decision.evidence_ref != attestation.authority_evidence_ref:
        return ModelInfluenceVerification(False, "model_probability_authority_evidence_mismatch")
    return ModelInfluenceVerification(True, "fresh_model_probability_authority_verified")


__all__ = [
    "MODEL_INFLUENCE_ATTESTATION_MAX_FUTURE_SKEW",
    "MODEL_INFLUENCE_ATTESTATION_TTL",
    "ModelInfluenceVerification",
    "build_model_influence_attestation",
    "forecast_binding_sha256",
    "proposal_binding_sha256",
    "verify_model_influence_attestation",
]
