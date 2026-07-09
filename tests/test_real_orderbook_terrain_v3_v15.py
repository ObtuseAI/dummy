from __future__ import annotations

from predator_mesh.v13.market_discovery import MarketDiscoveryMode, MarketDiscoveryProof
from predator_mesh.v13.orderbook_snapshot_v2 import RealOrderbookSnapshotClosure
from predator_mesh.v14.terrain_closure import RealOrderbookTerrainClosureV2
from predator_mesh.v15.auth_probe_v2 import KalshiAuthProbeDecision, KalshiAuthProbeV2
from predator_mesh.v15.credential_shape_repair import KalshiCredentialShapeRepairEngine
from predator_mesh.v15.credential_source_conflict_resolver import KalshiCredentialSourceConflictResolver
from predator_mesh.v15.retry_gate_v2 import RealTerrainRetryGateV2
from predator_mesh.v15.terrain_closure_v3 import RealOrderbookTerrainClosureV3
from tests.v13_test_helpers import real_snapshot_result
from tests.v15_test_helpers import MALFORMED_BACKSLASH_ENV, VALID_ENV, bridge_with_env, forensics_with_env


def _real_closure() -> RealOrderbookSnapshotClosure:
    return RealOrderbookSnapshotClosure(
        real_snapshot_result(),
        MarketDiscoveryProof(mode=MarketDiscoveryMode.REAL_READ_ONLY_DISCOVERY, eligible_candidates=[], real_read_only_used=True),
        "REAL_READ_ONLY",
        {"ready": True, "redacted": True},
    )


def test_malformed_credentials_never_claim_real_terrain() -> None:
    forensics = forensics_with_env(MALFORMED_BACKSLASH_ENV)
    repair = KalshiCredentialShapeRepairEngine(forensics=forensics)
    resolver = KalshiCredentialSourceConflictResolver(bridge=bridge_with_env(MALFORMED_BACKSLASH_ENV))
    gate = RealTerrainRetryGateV2(repair_engine=repair, conflict_resolver=resolver)
    closure = RealOrderbookTerrainClosureV3(forensics_report=forensics.to_report(), retry_gate=gate)
    mode = closure.terrain_mode()
    assert mode != "PASS_REAL_TERRAIN"
    assert mode.startswith("PARTIAL_")


def test_valid_auth_pass_with_provable_real_mode_yields_pass_real_terrain() -> None:
    forensics = forensics_with_env(VALID_ENV)
    repair = KalshiCredentialShapeRepairEngine(forensics=forensics)
    resolver = KalshiCredentialSourceConflictResolver(bridge=bridge_with_env(VALID_ENV))
    auth_probe = KalshiAuthProbeV2(repair_engine=repair, conflict_resolver=resolver, probe_fn=lambda: KalshiAuthProbeDecision.AUTH_PASS.value)
    gate = RealTerrainRetryGateV2(repair_engine=repair, conflict_resolver=resolver, auth_probe=auth_probe)
    inner = RealOrderbookTerrainClosureV2(closure=_real_closure())
    closure = RealOrderbookTerrainClosureV3(forensics_report=forensics.to_report(), retry_gate=gate, inner=inner)
    assert closure.terrain_mode() == "PASS_REAL_TERRAIN"
    report = closure.to_report()
    assert report["real_terrain_provably_used"] is True
    assert report["sample_fallback_used"] is False


def test_retry_now_decision_but_sample_data_never_claims_pass_real_terrain() -> None:
    """CRITICAL invariant: label alone must never upgrade to PASS_REAL_TERRAIN."""
    from predator_mesh.v12.orderbook_snapshot import OrderbookSnapshotMode
    from predator_mesh.v12.orderbook_v2 import OrderbookLiquidityModelV2

    fallback = OrderbookLiquidityModelV2().fallback_result()
    assert fallback.mode is not OrderbookSnapshotMode.REAL_READ_ONLY
    sample_closure = RealOrderbookSnapshotClosure(
        fallback,
        MarketDiscoveryProof(mode=MarketDiscoveryMode.SAMPLE_STATIC_FALLBACK, eligible_candidates=[]),
        "",
        {"ready": True, "redacted": True},
    )

    forensics = forensics_with_env(VALID_ENV)
    repair = KalshiCredentialShapeRepairEngine(forensics=forensics)
    resolver = KalshiCredentialSourceConflictResolver(bridge=bridge_with_env(VALID_ENV))
    auth_probe = KalshiAuthProbeV2(repair_engine=repair, conflict_resolver=resolver, probe_fn=lambda: KalshiAuthProbeDecision.AUTH_PASS.value)
    gate = RealTerrainRetryGateV2(repair_engine=repair, conflict_resolver=resolver, auth_probe=auth_probe)
    inner = RealOrderbookTerrainClosureV2(closure=sample_closure)
    closure = RealOrderbookTerrainClosureV3(forensics_report=forensics.to_report(), retry_gate=gate, inner=inner)

    assert closure.terrain_mode() == "FAIL_MALFORMED_PIPELINE"
