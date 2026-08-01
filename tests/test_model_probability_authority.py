import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from forecasting.model_probability_authority import (
    EXPECTED_PROVIDER_MODELS,
    MODEL_AUTHORITY_SCHEMA,
    MODEL_EVIDENCE_MODE,
    MODEL_EVIDENCE_SCHEMA,
    ModelProbabilityAuthorityRegistry,
    model_probability_scope,
)


NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
SCOPE = model_probability_scope(
    ticker="KXMLBGAME-26JUL22NYYBOS-NYY-YES",
    title="Will the Yankees beat the Red Sox? Yes",
    category="Sports",
    decision_at=NOW,
    expiration=NOW + timedelta(hours=4),
    live_phase=False,
)


def test_unknown_sports_phase_scope_is_never_promotable(tmp_path) -> None:
    unknown_scope = model_probability_scope(
        ticker="KXMLBGAME-26JUL22NYYBOS-NYY-YES",
        title="Will the Yankees beat the Red Sox? Yes",
        category="Sports",
        decision_at=NOW,
        expiration=NOW + timedelta(hours=4),
        live_phase=None,
    )
    registry = ModelProbabilityAuthorityRegistry(tmp_path / "missing.json")

    decision = registry.evaluate(unknown_scope, now=NOW)

    assert unknown_scope.endswith("|unknown")
    assert decision.authorized is False
    assert decision.weight == 0
    assert decision.blockers == ("authority_scope_axis_unknown",)


def _bundle(
    tmp_path,
    *,
    scope: str = SCOPE,
    evidence_updates: dict | None = None,
    promotion_updates: dict | None = None,
    demotions: list | None = None,
):
    evidence_root = tmp_path / "artifacts" / "dummy"
    evidence_root.mkdir(parents=True)
    computed_at = NOW - timedelta(hours=1)
    evidence = {
        "evidence_mode": MODEL_EVIDENCE_MODE,
        "forward_calibrated": True,
        "receipt_bounded": True,
        "point_in_time": True,
        "retro_rows_included": 0,
        "independent_event_clusters": 300,
        "brier_edge_ci95": {"lower": 0.002, "upper": 0.01},
        "earned_weight": 0.12,
        "computed_at": computed_at.isoformat(),
        "received_through": (computed_at - timedelta(minutes=1)).isoformat(),
    }
    if evidence_updates:
        evidence.update(evidence_updates)
    row = json.loads(json.dumps(evidence))
    cluster_count = evidence.get("independent_event_clusters")
    row["independent_event_cluster_ids"] = [
        f"event-{index}" for index in range(cluster_count)
    ] if isinstance(cluster_count, int) and not isinstance(cluster_count, bool) else []
    artifact = {
        "schema_version": MODEL_EVIDENCE_SCHEMA,
        "artifact_type": MODEL_EVIDENCE_SCHEMA,
        "generated_at": evidence["computed_at"],
        "evidence_mode": MODEL_EVIDENCE_MODE,
        # Deliberately reversed: provider identity is a set, not an order.
        "provider_models": list(reversed(sorted(EXPECTED_PROVIDER_MODELS))),
        "promotion_authority": False,
        "scopes": {scope: row},
    }
    artifact_path = evidence_root / "model_evidence.json"
    artifact_bytes = json.dumps(artifact, sort_keys=True, indent=2).encode("utf-8")
    artifact_path.write_bytes(artifact_bytes)
    evidence["evidence_ref"] = str(artifact_path)
    evidence["evidence_sha256"] = hashlib.sha256(artifact_bytes).hexdigest()

    promotion = {
        "scope": scope,
        "status": "PROMOTED",
        "provider_models": list(reversed(sorted(EXPECTED_PROVIDER_MODELS))),
        "promoted_at": (computed_at + timedelta(minutes=1)).isoformat(),
        "evidence": evidence,
    }
    if promotion_updates:
        promotion.update(promotion_updates)
    registry_path = tmp_path / "model_authority.json"
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": MODEL_AUTHORITY_SCHEMA,
                "promotions": [promotion],
                "demotions": demotions or [],
            }
        ),
        encoding="utf-8",
    )
    registry = ModelProbabilityAuthorityRegistry(
        registry_path,
        approved_evidence_roots=[evidence_root],
    )
    return registry, registry_path, artifact_path


def test_fresh_canonical_exact_scope_promotion_earns_only_recorded_weight(tmp_path):
    registry, _registry_path, _artifact_path = _bundle(tmp_path)

    decision = registry.evaluate(SCOPE, now=NOW)

    assert decision.authorized is True
    assert float(decision.weight) == pytest.approx(0.12)
    assert decision.independent_event_clusters == 300
    assert decision.blockers == ()


@pytest.mark.parametrize(
    ("evidence_updates", "expected_blocker"),
    [
        ({"independent_event_clusters": 299}, "independent_event_clusters_below_300"),
        ({"brier_edge_ci95": {"lower": 0, "upper": 0.01}}, "brier_edge_ci95_lower_not_positive"),
        ({"earned_weight": 0}, "earned_weight_invalid_or_out_of_bounds"),
        ({"earned_weight": 0.36}, "earned_weight_invalid_or_out_of_bounds"),
        ({"receipt_bounded": False}, "receipt_bounded_not_proven"),
        ({"forward_calibrated": False}, "forward_calibration_not_proven"),
        ({"point_in_time": False}, "point_in_time_not_proven"),
        ({"retro_rows_included": 1}, "retro_rows_not_zero"),
        (
            {"computed_at": (NOW - timedelta(days=8)).isoformat()},
            "model_evidence_stale",
        ),
    ],
)
def test_every_evidence_predicate_fails_closed(
    tmp_path,
    evidence_updates,
    expected_blocker,
):
    registry, _registry_path, _artifact_path = _bundle(
        tmp_path,
        evidence_updates=evidence_updates,
    )

    decision = registry.evaluate(SCOPE, now=NOW)

    assert decision.authorized is False
    assert decision.weight == 0
    assert expected_blocker in decision.blockers


def test_wrong_scope_never_inherits_promotion(tmp_path):
    registry, _registry_path, _artifact_path = _bundle(tmp_path)
    other_scope = SCOPE.replace("|mlb|", "|nfl|")

    decision = registry.evaluate(other_scope, now=NOW)

    assert decision.weight == 0
    assert decision.blockers == ("exact_scope_promotion_missing",)


def test_explicit_demotion_wins_over_valid_evidence(tmp_path):
    registry, _registry_path, _artifact_path = _bundle(
        tmp_path,
        demotions=[{"scope": SCOPE, "reason": "negative drift"}],
    )

    decision = registry.evaluate(SCOPE, now=NOW)

    assert decision.weight == 0
    assert decision.blockers == ("scope_explicitly_demoted",)


def test_tampered_canonical_artifact_cannot_retain_authority(tmp_path):
    registry, _registry_path, artifact_path = _bundle(tmp_path)
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    artifact["scopes"][SCOPE]["earned_weight"] = 0.35
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

    decision = registry.evaluate(SCOPE, now=NOW)

    assert decision.weight == 0
    assert "canonical_evidence_sha256_mismatch" in decision.blockers
    assert "canonical_scope_earned_weight_mismatch" in decision.blockers


def test_duplicate_event_clusters_cannot_satisfy_300_cluster_gate(tmp_path):
    registry, registry_path, artifact_path = _bundle(tmp_path)
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    ids = artifact["scopes"][SCOPE]["independent_event_cluster_ids"]
    ids[-1] = ids[0]
    artifact_bytes = json.dumps(artifact, sort_keys=True).encode("utf-8")
    artifact_path.write_bytes(artifact_bytes)
    registry_data = json.loads(registry_path.read_text(encoding="utf-8"))
    registry_data["promotions"][0]["evidence"]["evidence_sha256"] = hashlib.sha256(
        artifact_bytes
    ).hexdigest()
    registry_path.write_text(json.dumps(registry_data), encoding="utf-8")

    decision = registry.evaluate(SCOPE, now=NOW)

    assert decision.weight == 0
    assert "canonical_independent_cluster_ids_not_unique" in decision.blockers


def test_self_attested_dossier_without_canonical_artifact_is_rejected(tmp_path):
    registry, registry_path, artifact_path = _bundle(tmp_path)
    artifact_path.unlink()

    decision = registry.evaluate(SCOPE, now=NOW)

    assert decision.weight == 0
    assert "canonical_evidence_artifact_missing" in decision.blockers
    assert registry_path.exists()


def test_superseded_two_model_lineage_cannot_transfer_authority(tmp_path):
    registry, registry_path, artifact_path = _bundle(tmp_path)
    legacy_models = [
        "google/terra-3.5-flash",
        "openai/gpt-5.6-terra",
    ]
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    artifact["provider_models"] = legacy_models
    artifact_bytes = json.dumps(artifact, sort_keys=True).encode("utf-8")
    artifact_path.write_bytes(artifact_bytes)
    registry_data = json.loads(registry_path.read_text(encoding="utf-8"))
    promotion = registry_data["promotions"][0]
    promotion["provider_models"] = legacy_models
    promotion["evidence"]["evidence_sha256"] = hashlib.sha256(
        artifact_bytes
    ).hexdigest()
    registry_path.write_text(json.dumps(registry_data), encoding="utf-8")

    decision = registry.evaluate(SCOPE, now=NOW)

    assert decision.weight == 0
    assert "promotion_provider_model_set_mismatch" in decision.blockers
    assert "canonical_evidence_provider_set_mismatch" in decision.blockers


def test_corrupt_or_duplicate_registry_is_zero_authority(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("not-json", encoding="utf-8")
    corrupt = ModelProbabilityAuthorityRegistry(path, approved_evidence_roots=[tmp_path])
    assert corrupt.evaluate(SCOPE, now=NOW).weight == 0

    registry, registry_path, _artifact_path = _bundle(tmp_path / "duplicate")
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    data["promotions"].append(data["promotions"][0])
    registry_path.write_text(json.dumps(data), encoding="utf-8")
    decision = registry.evaluate(SCOPE, now=NOW)
    assert decision.weight == 0
    assert decision.blockers == ("duplicate_exact_scope_promotions",)
