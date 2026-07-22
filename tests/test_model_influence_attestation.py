from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from core.ontology import (
    Forecast,
    LiveOrderRequest,
    ModelInfluenceAttestation,
)
from forecasting.model_influence_attestation import (
    MODEL_INFLUENCE_ATTESTATION_MAX_FUTURE_SKEW,
    MODEL_INFLUENCE_ATTESTATION_TTL,
    build_model_influence_attestation,
    verify_model_influence_attestation,
)
from forecasting.model_probability_authority import (
    ModelProbabilityAuthorityDecision,
    model_probability_scope,
)
from live_firewall.exposure_tracker import ExposureTracker
from live_firewall.firewall import LiveBrokerFirewall


def _forecast() -> Forecast:
    now = datetime.now(timezone.utc)
    return Forecast(
        market_ticker="KXMLBGAME-26JUL22-NYYBOS",
        contract_ticker="KXMLBGAME-26JUL22-NYYBOS-NYY",
        event_title="Yankees at Red Sox",
        contract_title="Yankees win",
        market_implied_probability=Decimal("0.50"),
        dummy_probability=Decimal("0.57"),
        probability_delta=Decimal("0.07"),
        confidence_score=Decimal("0.70"),
        uncertainty_band=(Decimal("0.52"), Decimal("0.62")),
        expected_edge=Decimal("0.07"),
        edge_after_fees=Decimal("0.065"),
        freshness_score=Decimal("1"),
        liquidity_score=Decimal("0.8"),
        spread_score=Decimal("0.8"),
        orderbook_depth_score=Decimal("0.8"),
        settlement_risk_score=Decimal("0.1"),
        source_summary="point_in_time_quant",
        model_summary="deterministic baseline",
        calibration_notes="unit-test",
        timestamp=now,
        expiration=now + timedelta(hours=8),
        strategy_references=["test_strategy"],
        proof_reference="forecast-proof-1",
    )


def _request_fields(forecast: Forecast) -> dict[str, object]:
    return {
        "proposal_id": "proposal-1",
        "market_ticker": forecast.market_ticker,
        "contract_ticker": forecast.contract_ticker,
        "side": "yes",
        "price_cents": 51,
        "size": 1,
        "strategy_proof_reference": "strategy-proof-1",
        "forecast_proof_reference": forecast.proof_reference,
        "adapter_name": "kalshi_live_firewall_adapter",
    }


def _request(
    forecast: Forecast,
    *,
    authority_decision: ModelProbabilityAuthorityDecision | None = None,
    issued_at: datetime | None = None,
    request_updates: dict[str, object] | None = None,
) -> LiveOrderRequest:
    fields = _request_fields(forecast)
    fields.update(request_updates or {})
    attestation = build_model_influence_attestation(
        forecast,
        fields,
        authority_decision=authority_decision,
        market_category="Sports",
        live_phase=False,
        supporting_model_output_reference=(
            "model-opinion-proof-1" if authority_decision is not None else None
        ),
        issued_at=issued_at,
    )
    return LiveOrderRequest(
        **fields,
        model_influence_attestation=attestation,
    )


class _Registry:
    def __init__(self, decision: ModelProbabilityAuthorityDecision) -> None:
        self.decision = decision
        self.calls = 0

    def evaluate(self, scope: str, *, now=None) -> ModelProbabilityAuthorityDecision:
        self.calls += 1
        assert scope == self.decision.scope
        return self.decision


def _authority(forecast: Forecast, *, authorized: bool) -> ModelProbabilityAuthorityDecision:
    scope = model_probability_scope(
        ticker=forecast.contract_ticker,
        title=f"{forecast.event_title} {forecast.contract_title}",
        category="Sports",
        decision_at=forecast.timestamp,
        expiration=forecast.expiration,
        live_phase=False,
    )
    return ModelProbabilityAuthorityDecision(
        scope=scope,
        weight=Decimal("0.20") if authorized else Decimal("0"),
        authorized=authorized,
        blockers=() if authorized else ("exact_scope_promotion_missing",),
        evidence_ref="artifacts/dummy/model-authority.json" if authorized else None,
    )


def test_quant_only_attestation_is_explicit_and_does_not_consult_registry() -> None:
    forecast = _forecast()
    request = _request(forecast)
    denying = _Registry(_authority(forecast, authorized=False))

    result = verify_model_influence_attestation(
        request,
        forecast,
        authority_registry=denying,  # type: ignore[arg-type]
    )

    assert result.valid is True
    assert result.reason == "quant_only_probability_attested"
    assert request.model_influence_attestation is not None
    assert request.model_influence_attestation.model_probability_authority == 0
    assert denying.calls == 0


def test_stale_quant_only_attestation_is_rejected_before_registry() -> None:
    now = datetime.now(timezone.utc)
    issued_at = now - MODEL_INFLUENCE_ATTESTATION_TTL - timedelta(microseconds=1)
    forecast = _forecast().model_copy(update={"timestamp": issued_at})
    request = _request(
        forecast,
        issued_at=issued_at,
    )
    denying = _Registry(_authority(forecast, authorized=False))

    result = verify_model_influence_attestation(
        request,
        forecast,
        authority_registry=denying,  # type: ignore[arg-type]
        now=now,
    )

    assert result.valid is False
    assert result.reason == "model_influence_attestation_stale"
    assert denying.calls == 0


def test_stale_model_weighted_attestation_does_not_refresh_registry() -> None:
    now = datetime.now(timezone.utc)
    issued_at = now - MODEL_INFLUENCE_ATTESTATION_TTL - timedelta(microseconds=1)
    forecast = _forecast().model_copy(update={"timestamp": issued_at})
    authority = _authority(forecast, authorized=True)
    request = _request(
        forecast,
        authority_decision=authority,
        issued_at=issued_at,
    )
    registry = _Registry(authority)

    result = verify_model_influence_attestation(
        request,
        forecast,
        authority_registry=registry,  # type: ignore[arg-type]
        now=now,
    )

    assert result.valid is False
    assert result.reason == "model_influence_attestation_stale"
    assert registry.calls == 0


def test_quant_only_attestation_is_valid_immediately_before_ttl() -> None:
    now = datetime.now(timezone.utc)
    issued_at = now - MODEL_INFLUENCE_ATTESTATION_TTL + timedelta(microseconds=1)
    forecast = _forecast().model_copy(update={"timestamp": issued_at})
    request = _request(
        forecast,
        issued_at=issued_at,
    )

    result = verify_model_influence_attestation(request, forecast, now=now)

    assert result.valid is True
    assert result.reason == "quant_only_probability_attested"


def test_attestation_is_stale_at_exact_ttl_boundary() -> None:
    now = datetime.now(timezone.utc)
    issued_at = now - MODEL_INFLUENCE_ATTESTATION_TTL
    forecast = _forecast().model_copy(update={"timestamp": issued_at})
    request = _request(forecast, issued_at=issued_at)

    result = verify_model_influence_attestation(request, forecast, now=now)

    assert result.valid is False
    assert result.reason == "model_influence_attestation_stale"


def test_attestation_builder_rejects_naive_issued_at() -> None:
    forecast = _forecast()

    with pytest.raises(ValueError, match="timezone-aware"):
        _request(
            forecast,
            issued_at=datetime.now().replace(tzinfo=None),
        )


def test_attestation_issued_beyond_clock_skew_is_rejected() -> None:
    now = datetime.now(timezone.utc)
    forecast = _forecast()
    request = _request(
        forecast,
        issued_at=(
            now
            + MODEL_INFLUENCE_ATTESTATION_MAX_FUTURE_SKEW
            + timedelta(microseconds=1)
        ),
    )

    result = verify_model_influence_attestation(request, forecast, now=now)

    assert result.valid is False
    assert result.reason == "model_influence_attestation_issued_in_future"


def test_attestation_at_clock_skew_boundary_is_accepted() -> None:
    now = datetime.now(timezone.utc)
    forecast = _forecast()
    request = _request(
        forecast,
        issued_at=now + MODEL_INFLUENCE_ATTESTATION_MAX_FUTURE_SKEW,
    )

    result = verify_model_influence_attestation(request, forecast, now=now)

    assert result.valid is True
    assert result.reason == "quant_only_probability_attested"


def test_new_attestation_cannot_refresh_a_stale_forecast() -> None:
    now = datetime.now(timezone.utc)
    forecast = _forecast().model_copy(
        update={
            "timestamp": (
                now
                - MODEL_INFLUENCE_ATTESTATION_TTL
                - timedelta(microseconds=1)
            )
        }
    )
    request = _request(forecast, issued_at=now)

    result = verify_model_influence_attestation(request, forecast, now=now)

    assert result.valid is False
    assert result.reason == "model_influence_attestation_stale"


def test_attestation_never_outlives_bound_proposal_expiration() -> None:
    now = datetime.now(timezone.utc)
    issued_at = now - timedelta(seconds=10)
    forecast = _forecast().model_copy(update={"timestamp": issued_at})
    request = _request(
        forecast,
        issued_at=issued_at,
        request_updates={
            "expiration_ts": int((now - timedelta(seconds=1)).timestamp())
        },
    )

    result = verify_model_influence_attestation(request, forecast, now=now)

    assert result.valid is False
    assert result.reason == "model_influence_attestation_expired"


def test_firewall_maps_stale_attestation_to_model_authority_rejection() -> None:
    now = datetime.now(timezone.utc)
    issued_at = now - MODEL_INFLUENCE_ATTESTATION_TTL - timedelta(seconds=1)
    forecast = _forecast().model_copy(update={"timestamp": issued_at})
    request = _request(forecast, issued_at=issued_at)
    firewall = LiveBrokerFirewall(None, ExposureTracker())

    verdict = firewall._model_influence_verdict(request, forecast)

    assert verdict.allow is False
    assert verdict.rejected_by == "model_influence_authority"
    assert verdict.reason == "model_influence_attestation_stale"


def test_firewall_rejects_omitted_attestation_fail_closed() -> None:
    forecast = _forecast()
    request = LiveOrderRequest(**_request_fields(forecast))
    firewall = LiveBrokerFirewall(None, ExposureTracker())

    verdict = firewall._model_influence_verdict(request, forecast)

    assert verdict.allow is False
    assert verdict.rejected_by == "model_influence_authority"
    assert verdict.reason == "model_influence_attestation_missing"


@pytest.mark.parametrize(
    ("field", "value", "expected_reason"),
    [
        ("proposal_id", "proposal-tampered", "model_influence_proposal_binding_mismatch"),
        ("price_cents", 73, "model_influence_proposal_binding_mismatch"),
    ],
)
def test_proposal_tamper_breaks_attestation(
    field: str,
    value: object,
    expected_reason: str,
) -> None:
    forecast = _forecast()
    request = _request(forecast).model_copy(update={field: value})

    result = verify_model_influence_attestation(request, forecast)

    assert result.valid is False
    assert result.reason == expected_reason


def test_operational_probability_tamper_breaks_forecast_binding() -> None:
    forecast = _forecast()
    request = _request(forecast)
    changed = forecast.model_copy(update={"dummy_probability": Decimal("0.91")})

    result = verify_model_influence_attestation(request, changed)

    assert result.valid is False
    assert result.reason == "model_influence_forecast_binding_mismatch"


def test_attestation_body_tamper_breaks_digest() -> None:
    forecast = _forecast()
    request = _request(forecast)
    assert request.model_influence_attestation is not None
    changed_attestation = request.model_influence_attestation.model_copy(
        update={"supporting_model_output_reference": "forged-model-proof"}
    )
    changed_request = request.model_copy(
        update={"model_influence_attestation": changed_attestation}
    )

    result = verify_model_influence_attestation(changed_request, forecast)

    assert result.valid is False
    assert result.reason == "model_influence_attestation_digest_mismatch"


def test_claimed_model_weight_is_rejected_when_fresh_authority_is_zero() -> None:
    forecast = _forecast()
    claimed = _authority(forecast, authorized=True)
    request = _request(forecast, authority_decision=claimed)
    fresh_zero = _Registry(_authority(forecast, authorized=False))
    firewall = LiveBrokerFirewall(
        None,
        ExposureTracker(),
        model_authority_registry=fresh_zero,  # type: ignore[arg-type]
    )

    verdict = firewall._model_influence_verdict(request, forecast)

    assert verdict.allow is False
    assert verdict.reason == "model_probability_authority_not_current"
    assert fresh_zero.calls == 1


def test_model_weight_requires_matching_fresh_scope_weight_and_evidence() -> None:
    forecast = _forecast()
    authority = _authority(forecast, authorized=True)
    request = _request(forecast, authority_decision=authority)
    registry = _Registry(authority)
    firewall = LiveBrokerFirewall(
        None,
        ExposureTracker(),
        model_authority_registry=registry,  # type: ignore[arg-type]
    )

    verdict = firewall._model_influence_verdict(request, forecast)

    assert verdict.allow is True
    assert verdict.reason == "fresh_model_probability_authority_verified"
    assert registry.calls == 1


def test_production_request_constructors_emit_explicit_attestation() -> None:
    root = Path(__file__).resolve().parent.parent
    constructors = {
        "execution/autonomous_path.py": 2,
        "execution/hybrid_path.py": 1,
        "autonomy/executor.py": 1,
        "predator_mesh/lanes/firewall_rehearsal.py": 1,
    }
    for relative, expected_calls in constructors.items():
        source = (root / relative).read_text(encoding="utf-8")
        assert source.count("LiveOrderRequest(") == expected_calls
        assert source.count("model_influence_attestation=") >= expected_calls
    generator = (root / "repo_harvester/adapter_test_generator.py").read_text(
        encoding="utf-8"
    )
    assert "model_influence_attestation=build_model_influence_attestation(" in generator


def test_attestation_type_forbids_unknown_fields() -> None:
    forecast = _forecast()
    request = _request(forecast)
    assert request.model_influence_attestation is not None
    payload = request.model_influence_attestation.model_dump()
    payload["untrusted_extension"] = True

    with pytest.raises(Exception, match="Extra inputs are not permitted"):
        ModelInfluenceAttestation.model_validate(payload)
