from __future__ import annotations


def test_artifact_dependency_graph_contains_v16_final_dependencies() -> None:
    from predator_mesh.v16.proof_freshness import ArtifactDependencyGraph

    graph = ArtifactDependencyGraph.for_v16().to_report()

    assert "final_report_v16.json" in graph["nodes"]
    assert "real_terrain_truth_resolver_report_v1.json" in graph["dependencies"]["final_report_v16.json"]
