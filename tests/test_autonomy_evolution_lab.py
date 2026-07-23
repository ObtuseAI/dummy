from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autonomy.evolution_lab import (
    INCUMBENT_GENOME,
    ResearchGenome,
    candidate_population,
    run_evolution_lab,
    trace_replay_audit,
)


def _rows(
    count: int = 180,
    *,
    start: datetime = datetime(2025, 1, 1, tzinfo=timezone.utc),
    offset: int = 0,
) -> list[dict]:
    rows = []
    for local_index in range(count):
        index = offset + local_index
        created_at = start + timedelta(hours=local_index * 2)
        result = index % 5 != 0
        rows.append({
            "ticker": f"EVOLVE-{index:05d}",
            "cluster": f"epoch-{index:05d}",
            "forecast": 0.76 if result else 0.24,
            "market": 0.50,
            "uncertainty": 0.10,
            "result": int(result),
            "created_at": created_at,
            "settled_at": created_at + timedelta(hours=1),
        })
    return rows


def test_candidate_population_is_bounded_deterministic_and_parented():
    parent = ResearchGenome(0.75, 8, 0.18, 65)
    first = candidate_population(parent, generation=4, limit=48)
    second = candidate_population(parent, generation=4, limit=48)
    assert first == second
    assert len(first) == 48
    assert parent in first
    assert INCUMBENT_GENOME in first
    assert all(genome.is_bounded() for genome in first)


def test_archive_elites_seed_local_research_probes_before_population_truncation():
    active = ResearchGenome(0.75, 8, 0.18, 65)
    archive = ResearchGenome(0.50, 12, 0.18, 65)
    population = candidate_population(
        active,
        generation=5,
        limit=16,
        archive_parents=(archive,),
        mutation_scale=1.0,
    )
    assert archive in population
    assert ResearchGenome(0.58, 14, 0.21, 70) in population


def test_evolution_lab_is_causal_stressed_and_has_no_production_authority():
    report = run_evolution_lab(
        _rows(),
        as_of=datetime(2025, 3, 1, tzinfo=timezone.utc),
        population_size=32,
        bootstrap_simulations=200,
    )
    assert report["generation"] == 1
    assert report["population"]["bounded"] is True
    assert report["population"]["folds_completed"] >= 3
    for fold in report["folds"]:
        assert fold["training_latest_settlement"] < fold["test_start"]
    stress = report["retrospective_out_of_sample"]["stress_scenarios"]
    assert set(stress) == {"baseline", "wide_spread", "edge_decay", "severe_liquidity"}
    assert report["active_research_candidate"]["genome_id"].startswith("rg-")
    assert report["authority"] == {
        "automatic_research_candidate_rotation": True,
        "code_mutation_authority": False,
        "deployment_authority": False,
        "weight_write_authority": False,
        "risk_write_authority": False,
        "execution_authority": False,
        "capital_authority": False,
    }
    assert report["evidence_quarantine"]["counts_toward_canary"] is False


def test_forward_ratchet_accumulates_only_later_decisions_and_generation_is_stable():
    first_rows = _rows(
        180,
        start=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    first = run_evolution_lab(
        first_rows,
        as_of=datetime(2025, 2, 1, tzinfo=timezone.utc),
        population_size=32,
        bootstrap_simulations=200,
    )
    assert first["forward_ratchet"]["candidate"]["trades"] == 0

    later_rows = _rows(
        60,
        start=datetime(2025, 2, 2, tzinfo=timezone.utc),
        offset=180,
    )
    second = run_evolution_lab(
        first_rows + later_rows,
        previous_report={"evolution_lab": first},
        as_of=datetime(2025, 3, 1, tzinfo=timezone.utc),
        population_size=32,
        bootstrap_simulations=200,
    )
    assert second["generation"] == 2
    assert second["evidence"]["advanced"] is True
    assert second["evidence"]["new_settled_markets"] == 60
    assert second["forward_ratchet"]["candidate"]["trades"] > 0

    unchanged = run_evolution_lab(
        first_rows + later_rows,
        previous_report={"evolution_lab": second},
        as_of=datetime(2025, 3, 1, 1, tzinfo=timezone.utc),
        population_size=32,
        bootstrap_simulations=200,
    )
    assert unchanged["generation"] == 2
    assert unchanged["evidence"]["advanced"] is False
    assert unchanged["evidence"]["new_settled_markets"] == 0


def test_quality_diversity_archive_compounds_only_oos_research_evidence():
    first = run_evolution_lab(
        _rows(),
        as_of=datetime(2025, 3, 1, tzinfo=timezone.utc),
        population_size=32,
        bootstrap_simulations=200,
    )
    archive = first["quality_diversity_archive"]
    assert archive["cell_count"] > 0
    assert archive["current_generation_candidates_evaluated"] > 0
    assert archive["archive_seeds_next_research_population"] is True
    assert archive["automatic_production_selection"] is False
    assert all(
        cell["evidence_source"] == "causal_preselected_purged_out_of_sample_folds"
        and cell["execution_authority"] is False
        for cell in archive["cells"]
    )
    pressure = first["adaptive_mutation_pressure"]
    assert 0.25 <= pressure["applied_scale"] <= 2.0
    assert 0.25 <= pressure["next_scale"] <= 2.0
    assert pressure["code_mutation_authority"] is False
    assert first["candidate_lineage"]["record_count"] == first["population"][
        "candidates_generated"
    ]

    unchanged = run_evolution_lab(
        _rows(),
        previous_report={"evolution_lab": first},
        as_of=datetime(2025, 3, 1, 1, tzinfo=timezone.utc),
        population_size=32,
        bootstrap_simulations=200,
    )
    assert unchanged["evidence"]["advanced"] is False
    assert unchanged["population"]["archive_parents_seeded"] > 0
    assert unchanged["adaptive_mutation_pressure"]["action"] == (
        "hold_no_new_settled_evidence"
    )
    assert unchanged["adaptive_mutation_pressure"]["updates_without_new_settlements"] is True


def test_trace_replay_fingerprints_truth_and_fails_closed_on_gaps():
    rows = [{
        "decision_id": "d-1",
        "ticker": "TRACE-1",
        "price_cents": 40,
        "ev_cents": 10.0,
        "uncertainty": 0.1,
        "submitted_at": "2025-01-01T00:00:00+00:00",
        "queue_ahead": None,
        "filled": True,
        "known": True,
        "settled_pnl_cents": -40,
    }]
    first = trace_replay_audit(rows)
    second = trace_replay_audit(rows)
    assert first == second
    assert first["settled_losses"] == 1
    assert first["orders_missing_queue_snapshot"] == 1
    assert first["complete_for_execution_optimization"] is False
    assert first["execution_authority"] is False


def test_crossover_recombines_building_blocks_from_both_parents():
    from autonomy.evolution_lab import crossover_genomes

    a = ResearchGenome(0.30, 5, 0.12, 50)   # tight, cheap-entry lineage
    b = ResearchGenome(1.20, 16, 0.38, 88)  # loose, permissive lineage
    children = crossover_genomes(a, b)
    assert all(child.is_bounded() for child in children)
    # The two complementary uniform-crossover children each mix one parent's
    # shrinkage with the OTHER parent's entry price -- a combination neither a
    # nor b holds and grid mutation around one parent cannot land on.
    combos = {(c.shrinkage, c.max_entry_price_cents) for c in children}
    assert (0.30, 88) in combos or (1.20, 50) in combos
    # Midpoint blend is the recombinant centroid.
    assert any(
        abs(c.shrinkage - 0.75) < 1e-6 and c.max_entry_price_cents == 69
        for c in children
    )
    # Deterministic.
    assert crossover_genomes(a, b) == children


def test_population_contains_cross_lineage_recombinants():
    from autonomy.evolution_lab import crossover_genomes

    active = ResearchGenome(0.30, 5, 0.12, 50)
    elite = ResearchGenome(1.20, 16, 0.38, 88)
    population = candidate_population(
        active, generation=7, limit=64, archive_parents=(elite,),
    )
    expected = crossover_genomes(active, elite)
    assert any(child in population for child in expected)
    assert all(genome.is_bounded() for genome in population)
