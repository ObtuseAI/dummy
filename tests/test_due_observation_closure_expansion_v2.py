from __future__ import annotations

from tests.v41_test_helpers import assert_current_test_report, v41_enabled_reports


def test_due_observation_closure_expansion_v2_closes_only_matching_live_public() -> None:
    report = assert_current_test_report(__file__)
    assert report["forecast_mutation_performed"] is False
    assert report["probe_disabled_blocker"] == "PROBE_DISABLED"
    enabled = v41_enabled_reports()["due_observation_closure_expansion_v2_report.json"]
    assert enabled["v41_new_observed_count"] >= 6
    assert enabled["valid_matching_real_live_public_evidence_only"] is True
