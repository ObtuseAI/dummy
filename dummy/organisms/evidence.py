"""Bridges from Phase 2 typed incumbent messages into frozen episode evidence."""

from __future__ import annotations

from dummy.protocols import MessageEnvelope, MessageType

from .models import EpisodeValidationError, PointInTimeEvidence


def freeze_market_quote_message(
    message: MessageEnvelope,
    *,
    source_reference: str,
    observed_at_verified: bool,
) -> PointInTimeEvidence:
    """Freeze a Phase 2 market-view observation without re-fetching it."""

    if message.message_type is not MessageType.OBSERVATION:
        raise EpisodeValidationError("market quote bridge requires OBSERVATION")
    if message.payload.get("observation_kind") != "market_view":
        raise EpisodeValidationError("market quote bridge requires market_view")
    if not message.market_id or message.payload.get("ticker") != message.market_id:
        raise EpisodeValidationError("market quote bridge has mismatched market identity")
    raw = message.payload.get("raw", {})
    if "yes_ask_depth" not in raw or "no_ask_depth" not in raw:
        raise EpisodeValidationError(
            "market quote bridge requires witnessed side-specific ask depth"
        )
    return PointInTimeEvidence(
        evidence_id=message.message_id,
        source_family="kalshi-public-book",
        observed_at=message.effective_time,
        received_at=message.received_at,
        source_reference=source_reference,
        observed_at_verified=observed_at_verified,
        received_at_verified=True,
        payload={
            "kind": "market_quote",
            "market_id": message.market_id,
            "status": str(message.payload["status"]).lower(),
            "yes_bid": message.payload["yes_bid"],
            "yes_ask": message.payload["yes_ask"],
            "no_bid": message.payload["no_bid"],
            "no_ask": message.payload["no_ask"],
            "yes_ask_depth": int(raw["yes_ask_depth"]),
            "no_ask_depth": int(raw["no_ask_depth"]),
        },
        limitations=message.limitations,
    )


def freeze_incumbent_forecast_message(
    message: MessageEnvelope,
    *,
    source_reference: str,
    observed_at_verified: bool,
) -> PointInTimeEvidence:
    """Freeze a Phase 2 incumbent forecast as comparison evidence."""

    if message.message_type is not MessageType.FORECAST:
        raise EpisodeValidationError("incumbent bridge requires FORECAST")
    if not message.market_id:
        raise EpisodeValidationError("incumbent bridge requires market identity")
    required = (
        "probability",
        "uncertainty",
        "source_family",
        "incumbent_source",
        "calibration_identity",
    )
    if any(key not in message.payload for key in required):
        raise EpisodeValidationError("incumbent forecast bridge is incomplete")
    return PointInTimeEvidence(
        evidence_id=message.message_id,
        source_family=str(message.payload["source_family"]),
        observed_at=message.effective_time,
        received_at=message.received_at,
        source_reference=source_reference,
        observed_at_verified=observed_at_verified,
        received_at_verified=True,
        payload={
            "kind": "incumbent_forecast",
            "market_id": message.market_id,
            "probability_yes": message.payload["probability"],
            "uncertainty": message.payload["uncertainty"],
            "source_family": message.payload["source_family"],
            "source": message.payload["incumbent_source"],
            "model_version": message.model_version,
            "calibration_identity": message.payload["calibration_identity"],
            "features": message.payload.get("features", {}),
            "assumptions": ["phase2_incumbent_adapter_output_is_frozen"],
            "failure_conditions": list(message.limitations)
            or ["incumbent_limitations_unspecified"],
        },
        limitations=(*message.limitations, "incumbent_compared_not_substituted"),
    )


def freeze_calibration_message(
    message: MessageEnvelope,
    *,
    source_reference: str,
    observed_at_verified: bool,
    map_verified: bool,
) -> PointInTimeEvidence:
    """Freeze a proposal-only calibration message; unverified maps stay inert."""

    if message.message_type is not MessageType.CALIBRATION_UPDATE:
        raise EpisodeValidationError("calibration bridge requires CALIBRATION_UPDATE")
    requested = float(message.payload.get("calibrated_probability", 0.0)) - float(
        message.payload.get("original_probability", 0.0)
    )
    return PointInTimeEvidence(
        evidence_id=message.message_id,
        source_family="settled-calibration",
        observed_at=message.effective_time,
        received_at=message.received_at,
        source_reference=source_reference,
        observed_at_verified=observed_at_verified,
        received_at_verified=True,
        payload={
            "kind": "calibration_map",
            "verified": map_verified,
            "offset": requested if map_verified else 0.0,
            "map_version": message.model_version,
        },
        limitations=(*message.limitations, "proposal_only"),
    )
