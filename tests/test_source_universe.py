from __future__ import annotations

from tests.v20_test_helpers import assert_source_candidate


def test_source_universe_contains_required_tiers_domains_and_safe_candidates() -> None:
    from predator_mesh.v20.source_universe import SourceTier, SourceUniverse

    universe = SourceUniverse()
    report = universe.to_report()
    candidates = universe.candidates()

    assert report["verdict"] == "PASS"
    assert {tier.value for tier in SourceTier} <= set(report["tiers"])
    assert {"nasdaq_index_direction", "oil_energy_direction", "sports", "weather", "crypto", "commodities", "finance"} <= set(report["domains"])
    assert len(candidates) >= 80
    assert all(candidate.adapter_plan.live_execution_enabled is False for candidate in candidates)
    assert all(candidate.legality_class for candidate in candidates)
    assert all(candidate.approval_status for candidate in candidates)
    assert_source_candidate(candidates[0].to_dict())
