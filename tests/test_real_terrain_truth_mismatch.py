from __future__ import annotations


def test_truth_mismatch_fails_when_downstream_says_fallback_despite_real_evidence() -> None:
    from predator_mesh.v16.terrain_truth import RealTerrainTruthInput, RealTerrainTruthResolver

    verdict = RealTerrainTruthResolver(
        RealTerrainTruthInput(
            credential_shape_state="SHAPE_VALID",
            auth_probe_state="AUTH_PASS",
            config_binding_state="PASS",
            market_discovery_state="REAL_READ_ONLY_DISCOVERY",
            eligible_market_candidate_count=1,
            orderbook_snapshot_state="REAL_READ_ONLY",
            nonempty_book_proof=True,
            read_only_endpoint_audit=True,
            replay_state="REAL_SNAPSHOT_REPLAY",
            fallback_state="DOWNSTREAM_SAMPLE_STATIC_FALLBACK",
            artifact_freshness="FRESH",
        )
    ).resolve()

    assert verdict.verdict == "FAIL_TRUTH_MISMATCH"
    assert verdict.mismatch is not None
