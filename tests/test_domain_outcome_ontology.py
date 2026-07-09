from __future__ import annotations


def test_domain_outcome_ontology_covers_original_domains_and_ambiguity_pressure() -> None:
    from predator_mesh.v17.outcomes import DomainOutcomeOntology

    report = DomainOutcomeOntology().to_report()

    assert set(report["domains"]) == {"sports", "weather", "crypto", "commodities", "finance"}
    assert "game_winner" in report["event_types"]["sports"]
    assert report["ambiguous_settlement_generates_no_trade_pressure"] is True
