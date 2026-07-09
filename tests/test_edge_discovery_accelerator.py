from __future__ import annotations

from predator_mesh.v10.edge_accelerator import EdgeDiscoveryAccelerator, EdgeTriageDecision


def test_edge_discovery_accelerator_ranks_hypotheses() -> None:
    accelerator = EdgeDiscoveryAccelerator()
    batch = accelerator.generate_batch()
    ranked = accelerator.rank(batch)

    assert batch.hypotheses
    assert ranked.hypotheses[0].score.total >= ranked.hypotheses[-1].score.total
    assert all(isinstance(h.triage, EdgeTriageDecision) for h in ranked.hypotheses)
