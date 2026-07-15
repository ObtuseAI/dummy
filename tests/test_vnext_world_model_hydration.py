from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from dummy.agents import AgentVertical
from dummy.chronos import ClockDomain
from dummy.organisms import IssueRequest, PointInTimeEvidence
from dummy.world_model import (
    StateLayer,
    ValueStatus,
    WorldHydrationError,
    WorldModelValidationError,
    WorldObservation,
    WorldStateSnapshot,
    build_world_snapshot,
    hydrate_issue_world_state,
    observations_from_issue,
    schema_for,
    supported_schema_manifest,
)


NOW = datetime(2026, 7, 14, 22, 0, tzinfo=timezone.utc)


def _issue(
    *,
    decision_at: datetime = NOW,
    received_at: datetime = NOW,
    features: dict[str, object] | None = None,
    include_calibration_identity: bool = True,
) -> IssueRequest:
    incumbent_payload: dict[str, object] = {
        "kind": "incumbent_forecast",
        "market_id": "KXBTC15M-26JUL142215-15",
        "probability_yes": 0.64,
        "uncertainty": 0.09,
        "source_family": "crypto-coinbase-distribution",
        "source": "crypto_distribution",
        "model_version": "crypto-model-v1",
        "features": features or {},
        "assumptions": ["frozen_inputs"],
        "failure_conditions": ["regime_change"],
    }
    if include_calibration_identity:
        incumbent_payload["calibration_identity"] = "crypto-calibration-v1"
    evidence = (
        PointInTimeEvidence(
            evidence_id="quote-1",
            source_family="kalshi-public-book",
            observed_at=received_at - timedelta(seconds=1),
            received_at=received_at,
            source_reference="fixture://quote",
            observed_at_verified=True,
            received_at_verified=True,
            payload={
                "kind": "market_quote",
                "market_id": "KXBTC15M-26JUL142215-15",
                "status": "open",
                "yes_bid": 49,
                "yes_ask": 51,
                "no_bid": 49,
                "no_ask": 51,
                "yes_ask_depth": 4,
                "no_ask_depth": 5,
            },
        ),
        PointInTimeEvidence(
            evidence_id="incumbent-1",
            source_family="crypto-coinbase-distribution",
            observed_at=received_at - timedelta(seconds=2),
            received_at=received_at,
            source_reference="fixture://incumbent",
            observed_at_verified=True,
            received_at_verified=True,
            payload=incumbent_payload,
        ),
    )
    return IssueRequest(
        market_id="KXBTC15M-26JUL142215-15",
        market_type="15m_direction",
        vertical=AgentVertical.CRYPTO,
        clock_domain=ClockDomain.FIFTEEN_MINUTE,
        objective="Point-in-time BTC forecast",
        policy_version="phase4-policy-v1",
        decision_at=decision_at,
        market_close_at=decision_at + timedelta(minutes=15),
        event_cluster_id="btc-window-1",
        evidence=evidence,
    )


def test_manifest_has_horizon_crypto_and_each_league_clock_schema() -> None:
    manifest = supported_schema_manifest()
    schemas = manifest["schemas"]
    assert len(schemas) == 52
    ids = {item["schema_id"] for item in schemas}
    assert "dummy-crypto-fifteen_minute-world-state-v1" in ids
    for league in ("mlb", "nba", "nfl", "ncaaf", "nhl", "ncaamb"):
        assert f"dummy-{league}-pregame-world-state-v1" in ids
    assert "dummy-mlb-inning-world-state-v1" in ids
    assert "dummy-mlb-possession-world-state-v1" not in ids
    assert "dummy-nfl-inning-world-state-v1" not in ids
    assert "dummy-nhl-halftime-world-state-v1" not in ids
    assert "dummy-nba-period-world-state-v1" in ids
    assert "dummy-nfl-possession-world-state-v1" in ids
    with pytest.raises(WorldModelValidationError, match="unsupported sports"):
        schema_for(AgentVertical.MLB, ClockDomain.POSSESSION)


def test_hydration_is_deterministic_provenanced_and_explicitly_missing() -> None:
    request = _issue(
        features={
            "annual_vol": 0.55,
            "horizon_log_return_sigma": 0.012,
        }
    )
    first = hydrate_issue_world_state(request)
    second = hydrate_issue_world_state(request)
    assert first.to_json() == second.to_json()
    assert first.snapshot_id == second.snapshot_id
    assert first.schema.scope == "crypto_horizon:fifteen_minute"
    assert first.value("crypto.realized_volatility").value == 0.55
    assert first.value("crypto.realized_volatility").provenance[0].evidence_id == "incumbent-1"
    missing = first.value("crypto.funding")
    assert missing.status is ValueStatus.MISSING
    assert missing.layer is StateLayer.MISSING
    assert missing.uncertainty == 1.0
    assert missing.value is None
    assert missing.provenance == ()
    assert all(0.0 <= item.uncertainty <= 1.0 for item in first.values)
    assert all(item["provenance_status"] for item in first.to_dict()["values"])
    manifest = first.value("incumbent.feature_manifest").value
    with pytest.raises(TypeError):
        manifest["annual_vol"] = 0.99


def test_snapshot_identity_rejects_content_independent_id() -> None:
    snapshot = hydrate_issue_world_state(_issue())
    with pytest.raises(WorldModelValidationError, match="snapshot_id"):
        WorldStateSnapshot(
            snapshot_id="tampered",
            schema=snapshot.schema,
            market_id=snapshot.market_id,
            as_of=snapshot.as_of,
            policy_version=snapshot.policy_version,
            values=snapshot.values,
            contradictions=snapshot.contradictions,
            source_observation_digest=snapshot.source_observation_digest,
        )


def test_critical_lease_expiry_fails_closed_without_carry_forward() -> None:
    request = _issue(
        decision_at=NOW + timedelta(minutes=3),
        received_at=NOW,
    )
    with pytest.raises(WorldHydrationError, match="critical world state is missing"):
        hydrate_issue_world_state(request)


def test_future_received_observation_cannot_enter_snapshot() -> None:
    request = _issue()
    observations = observations_from_issue(request)
    future = replace(
        observations[0],
        received_at=NOW + timedelta(seconds=1),
        observed_at=NOW,
        revision_id="future-revision",
    )
    with pytest.raises(WorldHydrationError, match="future-received"):
        build_world_snapshot(
            schema=schema_for(request.vertical, request.clock_domain),
            market_id=request.market_id,
            as_of=NOW,
            policy_version=request.policy_version,
            observations=(*observations[1:], future),
        )


def test_unlinked_optional_disagreement_is_preserved_as_contradiction() -> None:
    request = _issue(features={"annual_vol": 0.55})
    observations = observations_from_issue(request)
    original = next(
        item for item in observations if item.field_key == "crypto.realized_volatility"
    )
    conflicting = replace(
        original,
        value=0.80,
        evidence_id="independent-vol-2",
        revision_id="independent-vol-revision-2",
        source="independent-vol-source",
        source_reference="fixture://independent-vol",
    )
    snapshot = build_world_snapshot(
        schema=schema_for(request.vertical, request.clock_domain),
        market_id=request.market_id,
        as_of=request.decision_at,
        policy_version=request.policy_version,
        observations=(*observations, conflicting),
    )
    state = snapshot.value("crypto.realized_volatility")
    assert state.status is ValueStatus.CONTRADICTED
    assert state.value is None
    assert snapshot.contradictions[0].reason == "unlinked_observations_disagree"


def test_hypothesis_requires_calibration_and_mapping_evidence() -> None:
    with pytest.raises(WorldModelValidationError, match="calibration identity"):
        WorldObservation(
            field_key="incumbent.probability_yes",
            layer=StateLayer.HYPOTHESIS,
            value=0.5,
            unit="probability",
            uncertainty=0.1,
            observed_at=NOW,
            received_at=NOW,
            timestamp_verified=True,
            source="fixture",
            source_family="fixture",
            source_reference="fixture://forecast",
            evidence_id="forecast-1",
            revision_id="forecast-revision-1",
            causal_evidence_ids=("forecast-1",),
            probability=0.5,
        )


def test_issue_without_incumbent_calibration_identity_fails_closed() -> None:
    with pytest.raises(WorldHydrationError, match="calibration identity"):
        hydrate_issue_world_state(_issue(include_calibration_identity=False))
