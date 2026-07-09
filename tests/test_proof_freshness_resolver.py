from __future__ import annotations


def test_proof_freshness_resolver_rejects_stale_sample_override() -> None:
    from predator_mesh.v16.proof_freshness import ProofFreshnessResolver

    report = ProofFreshnessResolver(
        required_artifacts={
            "real_terrain_truth_resolver_report_v1.json": {"generated_at": "2026-07-03T00:00:00+00:00", "terrain_truth_verdict": "PASS_REAL_TERRAIN"},
            "orderbook_liquidity_model_report_v6.json": {"generated_at": "2026-07-03T00:00:01+00:00", "terrain_truth_verdict": "PASS_REAL_TERRAIN"},
        },
        historical_artifacts={"orderbook_liquidity_model_report_v4.json": {"terrain_mode": "SAMPLE_STATIC_FALLBACK"}},
    ).to_report()

    assert report["freshness_state"] == "FRESH"
    assert report["stale_artifact_warnings"] == []
