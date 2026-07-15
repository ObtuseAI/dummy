"""Adapters from frozen organism evidence into typed world observations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dummy.organisms.models import IssueRequest, PointInTimeEvidence

from .builder import build_world_snapshot
from .models import (
    StateLayer,
    WorldHydrationError,
    WorldObservation,
    WorldStateSnapshot,
    digest_json,
    thaw_json,
)
from .schemas import schema_for


_QUOTE_FIELDS = {
    "status": ("market.status", "enum"),
    "yes_bid": ("market.yes_bid_cents", "cents"),
    "yes_ask": ("market.yes_ask_cents", "cents"),
    "no_bid": ("market.no_bid_cents", "cents"),
    "no_ask": ("market.no_ask_cents", "cents"),
    "yes_ask_depth": ("market.yes_ask_depth", "contracts"),
    "no_ask_depth": ("market.no_ask_depth", "contracts"),
}
_CRYPTO_FEATURE_FIELDS = {
    "annual_vol": ("crypto.realized_volatility", "annualized_volatility"),
    "implied_vol": ("crypto.implied_volatility", "annualized_volatility"),
    "horizon_log_return_sigma": ("crypto.horizon_uncertainty", "log_return_sigma"),
    "macro_score": ("crypto.macro_risk", "score"),
}


def _revision(evidence: PointInTimeEvidence, field_key: str) -> str:
    return digest_json(
        {
            "evidence_id": evidence.evidence_id,
            "field_key": field_key,
            "received_at": evidence.to_dict()["received_at"],
        }
    )


def _base(
    evidence: PointInTimeEvidence,
    *,
    field_key: str,
    additional_limitations: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "field_key": field_key,
        "observed_at": evidence.observed_at,
        "received_at": evidence.received_at,
        "timestamp_verified": (
            evidence.observed_at_verified and evidence.received_at_verified
        ),
        "source_family": evidence.source_family,
        "source_reference": evidence.source_reference,
        "evidence_id": evidence.evidence_id,
        "revision_id": _revision(evidence, field_key),
        "limitations": tuple(
            sorted({*evidence.limitations, *additional_limitations})
        ),
    }


def _evidence_by_kind(
    request: IssueRequest,
    kind: str,
) -> PointInTimeEvidence:
    matches = tuple(
        item for item in request.evidence if item.payload.get("kind") == kind
    )
    if len(matches) != 1:
        raise WorldHydrationError(
            f"world hydration requires exactly one {kind} evidence item"
        )
    return matches[0]


def observations_from_issue(request: IssueRequest) -> tuple[WorldObservation, ...]:
    """Convert already-frozen evidence without network access or imputation."""

    quote = _evidence_by_kind(request, "market_quote")
    incumbent = _evidence_by_kind(request, "incumbent_forecast")
    quote_payload = thaw_json(quote.payload)
    incumbent_payload = thaw_json(incumbent.payload)
    observations: list[WorldObservation] = []
    for source_key, (field_key, unit) in _QUOTE_FIELDS.items():
        if source_key not in quote_payload:
            raise WorldHydrationError(
                f"critical quote field is absent: {source_key}"
            )
        observations.append(
            WorldObservation(
                **_base(quote, field_key=field_key),
                layer=StateLayer.FACT,
                value=quote_payload[source_key],
                unit=unit,
                uncertainty=0.0,
                source="kalshi-public-book",
            )
        )

    try:
        probability = float(incumbent_payload["probability_yes"])
        uncertainty = float(incumbent_payload["uncertainty"])
        source = str(incumbent_payload["source"])
        model_version = str(incumbent_payload["model_version"])
        calibration_identity = str(incumbent_payload["calibration_identity"])
    except (KeyError, TypeError, ValueError) as exc:
        raise WorldHydrationError(
            "incumbent forecast lacks probability, uncertainty, model, or calibration identity"
        ) from exc
    if not source.strip() or not model_version.strip() or not calibration_identity.strip():
        raise WorldHydrationError("incumbent model identity cannot be blank")
    probability_key = "incumbent.probability_yes"
    observations.append(
        WorldObservation(
            **_base(incumbent, field_key=probability_key),
            layer=StateLayer.HYPOTHESIS,
            value=probability,
            unit="probability",
            uncertainty=uncertainty,
            source=source,
            transform_version=model_version,
            causal_evidence_ids=(incumbent.evidence_id,),
            probability=probability,
            calibration_identity=calibration_identity,
            mapping_evidence_ids=(incumbent.evidence_id,),
        )
    )
    uncertainty_key = "incumbent.uncertainty"
    observations.append(
        WorldObservation(
            **_base(incumbent, field_key=uncertainty_key),
            layer=StateLayer.DERIVED,
            value=uncertainty,
            unit="probability",
            uncertainty=0.0,
            source=source,
            transform_version=model_version,
            causal_evidence_ids=(incumbent.evidence_id,),
        )
    )

    features = incumbent_payload.get("features")
    if features is not None:
        if not isinstance(features, Mapping):
            raise WorldHydrationError("incumbent feature manifest must be a mapping")
        feature_payload = dict(features)
        feature_key = "incumbent.feature_manifest"
        observations.append(
            WorldObservation(
                **_base(
                    incumbent,
                    field_key=feature_key,
                    additional_limitations=(
                        "component_uncertainty_inherited_from_incumbent",
                    ),
                ),
                layer=StateLayer.DERIVED,
                value=feature_payload,
                unit="json",
                uncertainty=uncertainty,
                source=source,
                transform_version=model_version,
                causal_evidence_ids=(incumbent.evidence_id,),
            )
        )
        if request.vertical.value == "crypto":
            for source_key, (field_key, unit) in _CRYPTO_FEATURE_FIELDS.items():
                if source_key not in feature_payload:
                    continue
                observations.append(
                    WorldObservation(
                        **_base(
                            incumbent,
                            field_key=field_key,
                            additional_limitations=(
                                "feature_extracted_from_frozen_incumbent_payload",
                                "component_uncertainty_inherited_from_incumbent",
                            ),
                        ),
                        layer=StateLayer.DERIVED,
                        value=feature_payload[source_key],
                        unit=unit,
                        uncertainty=uncertainty,
                        source=source,
                        transform_version=model_version,
                        causal_evidence_ids=(incumbent.evidence_id,),
                    )
                )
    return tuple(observations)


def hydrate_issue_world_state(request: IssueRequest) -> WorldStateSnapshot:
    schema = schema_for(request.vertical, request.clock_domain)
    return build_world_snapshot(
        schema=schema,
        market_id=request.market_id,
        as_of=request.decision_at,
        policy_version=request.policy_version,
        observations=observations_from_issue(request),
    )
