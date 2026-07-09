from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_crypto_evidence_packet_v3_does_not_claim_fixture_real() -> None:
    report = assert_v20_report("crypto_evidence_packet_v3_report.json", "source_blockers")
    assert report["fixture_evidence_claimed_real"] is False

