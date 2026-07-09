from __future__ import annotations

from tests.v16_test_helpers import pass_truth_verdict


def test_truth_resolver_passes_real_readonly_discovery_and_nonempty_book() -> None:
    verdict = pass_truth_verdict()

    assert verdict.verdict == "PASS_REAL_TERRAIN"
    assert verdict.evidence.real_evidence_present is True


def test_truth_resolver_empty_book_is_partial_not_malformed() -> None:
    from predator_mesh.v16.terrain_truth import RealTerrainTruthInput, RealTerrainTruthResolver

    verdict = RealTerrainTruthResolver(
        RealTerrainTruthInput(
            credential_shape_state="SHAPE_VALID",
            auth_probe_state="AUTH_PASS",
            config_binding_state="PASS",
            market_discovery_state="REAL_READ_ONLY_DISCOVERY",
            eligible_market_candidate_count=1,
            orderbook_snapshot_state="REAL_READ_ONLY_DEGRADED",
            nonempty_book_proof=False,
            read_only_endpoint_audit=True,
            replay_state="EMPTY_REAL_ORDERBOOK",
            fallback_state="NOT_USED",
            artifact_freshness="FRESH",
        )
    ).resolve()

    assert verdict.verdict == "PARTIAL_EMPTY_ORDERBOOK"


def test_truth_resolver_nonempty_degraded_real_book_passes_with_warnings() -> None:
    from predator_mesh.v16.terrain_truth import RealTerrainTruthInput, RealTerrainTruthResolver

    verdict = RealTerrainTruthResolver(
        RealTerrainTruthInput(
            credential_shape_state="SHAPE_VALID",
            auth_probe_state="AUTH_PASS",
            config_binding_state="PASS",
            market_discovery_state="REAL_READ_ONLY_DISCOVERY",
            eligible_market_candidate_count=1,
            orderbook_snapshot_state="REAL_READ_ONLY_DEGRADED",
            nonempty_book_proof=True,
            read_only_endpoint_audit=True,
            replay_state="REAL_SNAPSHOT_REPLAY_WITH_WARNINGS",
            fallback_state="NOT_USED",
            artifact_freshness="FRESH",
        )
    ).resolve()

    assert verdict.verdict == "PASS_REAL_TERRAIN_WITH_WARNINGS"
    assert "REAL_ORDERBOOK_DEGRADED_NONEMPTY" in (verdict.warnings or [])
