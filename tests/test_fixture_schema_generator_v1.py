from tests.v29_test_helpers import assert_v29_report_named


def test_fixture_schema_generator_v1_keeps_fixture_sample_and_cached_modes_separate_from_live() -> None:
    report = assert_v29_report_named(
        "fixture_schema_generator_v1_report.json",
        "fixture_schema_generator_status",
        "fixture_contract_ready_count",
        "fixture_modes",
    )

    assert report["fixture_schema_generator_status"] == "PASS"
    assert report["fixture_contract_ready_count"] >= 5
    assert {
        "REPLAY_FIXTURE",
        "PUBLIC_SAMPLE_RESPONSE",
        "CACHED_PUBLIC_RESPONSE",
        "LIVE_PUBLIC_PROBE_RESULT",
        "INVALID_STALE_CACHE",
        "INVALID_UNTRUSTED_SAMPLE",
    } <= set(report["fixture_modes"])
    assert report["fixture_evidence_claimed_real"] is False
    assert report["sample_response_claimed_live"] is False
    assert report["stale_cached_evidence_scored_live"] is False
    assert report["source_api_keys_in_fixtures"] is False
    assert report["execution_bridge_present"] is False
