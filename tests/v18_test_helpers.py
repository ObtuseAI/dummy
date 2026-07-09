from __future__ import annotations

DOMAINS = {"sports", "weather", "crypto", "commodities", "finance"}


def assert_pass_report(report: dict) -> None:
    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report.get("secret_values_exposed") is False


def assert_domain_research_foundation(domain: str) -> None:
    from predator_mesh.v18.research_domains import domain_foundation

    report = domain_foundation(domain).research_report()
    assert_pass_report(report)
    assert report["domain"] == domain
    assert report["fixture_evidence_claimed_real"] is False
    assert report["source_legality_required"] is True
    assert report["feature_categories"]


def assert_domain_baseline_forecast(domain: str) -> None:
    from predator_mesh.v18.research_domains import domain_foundation

    report = domain_foundation(domain).baseline_report()
    assert_pass_report(report)
    assert report["domain"] == domain
    assert report["heavy_ml_used"] is False
    assert report["fake_edge_claimed"] is False
    assert report["baseline_types"]


def assert_domain_settlement_map(domain: str) -> None:
    from predator_mesh.v18.research_domains import domain_foundation

    report = domain_foundation(domain).settlement_report()
    assert_pass_report(report)
    assert report["domain"] == domain
    assert report["settlement_source_required"] is True
    assert report["fabricates_truth"] is False


def assert_domain_no_trade_gate(domain: str) -> None:
    from predator_mesh.v18.research_domains import domain_foundation

    report = domain_foundation(domain).no_trade_report()
    assert_pass_report(report)
    assert report["domain"] == domain
    assert report["no_trade_triggers"]
    assert report["settlement_ambiguity_generates_no_trade"] is True
