from __future__ import annotations

from tests.v16_test_helpers import real_discovery


def test_real_market_discovery_proof_v2_marks_real_readonly_discovery() -> None:
    report = real_discovery().proof.to_report()

    assert report["mode"] == "REAL_READ_ONLY_DISCOVERY"
    assert report["read_only_endpoints_only"] is True
    assert report["verdict"] == "PASS"
