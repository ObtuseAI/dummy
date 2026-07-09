from __future__ import annotations

DOMAINS = {"sports", "weather", "crypto", "commodities", "finance"}
ALLOWED_MODES = {
    "REAL_READ_ONLY_ACTIVE",
    "REAL_READ_ONLY_DEGRADED",
    "PUBLIC_STATIC_FIXTURE",
    "STATIC_FIXTURE_ONLY",
    "MOCK_ONLY_EXPLICIT",
    "BLOCKED_LEGALITY",
    "BLOCKED_MISSING_DEPENDENCY",
    "BLOCKED_TIMEOUT",
    "BLOCKED_SOURCE_UNAVAILABLE",
}


def assert_pass_or_partial(report: dict) -> None:
    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report.get("secret_values_exposed") is False


def assert_domain_activation_report(domain: str) -> None:
    from predator_mesh.v19.domain_sources import domain_source_profile

    report = domain_source_profile(domain).activation_report()
    assert_pass_or_partial(report)
    assert report["domain"] == domain
    assert report["source_legality_class"]
    assert report["source_activation_mode"] in ALLOWED_MODES
    assert report["live_execution_enabled"] is False


def assert_domain_evidence_packet(domain: str) -> None:
    from predator_mesh.v19.domain_sources import domain_source_profile

    report = domain_source_profile(domain).evidence_packet_report()
    assert_pass_or_partial(report)
    assert report["domain"] == domain
    assert report["fixture_evidence_claimed_real"] is False
    assert report["source_legality_class"]
    assert report["freshness_timestamp"] is not None


def assert_domain_blocker_report(domain: str) -> None:
    from predator_mesh.v19.domain_sources import domain_source_profile

    report = domain_source_profile(domain).blocker_report()
    assert_pass_or_partial(report)
    assert report["domain"] == domain
    assert isinstance(report["blockers"], list)
    assert report["proof_refs"]
