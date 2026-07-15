"""Twelve-part conservative confidence decomposition."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone

from dummy.protocols import MessageEnvelope, MessageType

from .state import ConfidenceDecomposition, MetaCalibrationEvidence


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def decompose_confidence(
    *,
    world_state: Mapping[str, object],
    messages: tuple[MessageEnvelope, ...],
    decision_at: datetime,
    incumbent_calibration_verified: bool,
    meta_calibration: MetaCalibrationEvidence,
) -> ConfidenceDecomposition:
    forecasts = tuple(
        message
        for message in messages
        if message.message_type in {MessageType.FORECAST, MessageType.COUNTERFORECAST}
    )
    probabilities = tuple(float(message.payload["probability"]) for message in forecasts)
    uncertainties = tuple(float(message.payload.get("uncertainty", 0.5)) for message in forecasts)
    spread = max(probabilities) - min(probabilities) if probabilities else 1.0
    market_priors = tuple(
        float(message.payload["probability"])
        for message in forecasts
        if message.payload.get("organism_role") == "market_prior"
    )
    non_market = tuple(
        float(message.payload["probability"])
        for message in forecasts
        if message.payload.get("organism_role") != "market_prior"
    )
    if len(market_priors) == 1 and non_market:
        mean_prior_gap = sum(abs(value - market_priors[0]) for value in non_market) / len(
            non_market
        )
        market_agreement = max(0.0, 1.0 - 2.0 * mean_prior_gap)
    else:
        market_agreement = 0.0
    values = tuple(
        value
        for value in world_state.get("values", ())
        if isinstance(value, Mapping)
    )
    present = tuple(value for value in values if value.get("status") == "present")
    fresh = 0
    reliable = 0
    for value in present:
        valid_until = value.get("valid_until")
        if isinstance(valid_until, str) and _parse(valid_until) >= decision_at:
            fresh += 1
        if value.get("provenance_status") == "verified_observation_chain":
            reliable += 1
    regimes = tuple(
        value for value in values if "regime" in str(value.get("field_key", ""))
    )
    regimes_present = sum(value.get("status") == "present" for value in regimes)
    families = {
        str(message.payload.get("source_family", "")) for message in forecasts
    }
    causal = sum(bool(message.evidence_ids or message.causal_parents) for message in messages)
    sample_support = min(1.0, meta_calibration.sample_size / 200.0)
    calibration_reliability = 0.0
    if meta_calibration.verified:
        calibration_reliability = max(
            0.0,
            1.0 - float(meta_calibration.ece or 1.0),
        )
    elif incumbent_calibration_verified:
        calibration_reliability = 0.4
    return ConfidenceDecomposition(
        model=round(max(0.0, 1.0 - 2.0 * max(uncertainties, default=0.5)), 12),
        evidence_completeness=float(world_state.get("completeness", 0.0)),
        evidence_freshness=round(fresh / max(1, len(present)), 12),
        data_reliability=round(reliable / max(1, len(present)), 12),
        regime_familiarity=round(regimes_present / max(1, len(regimes)), 12),
        historical_analogue_strength=0.0,
        calibration_reliability=round(calibration_reliability, 12),
        market_prior_agreement=round(market_agreement, 12),
        source_independence=round(len(families) / max(1, len(forecasts)), 12),
        causal_confidence=round(causal / max(1, len(messages)), 12),
        forecast_stability=round(max(0.0, 1.0 - spread), 12),
        settlement_sample_support=sample_support,
    )
