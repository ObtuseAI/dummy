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
