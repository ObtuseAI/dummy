from __future__ import annotations

from tests.v36_test_helpers import assert_current_test_report


def test_no_secret_leak_v36() -> None:
    report = assert_current_test_report(__file__)
    assert report["secret_values_exposed"] is False
    assert report["source_api_keys_exposed"] is False
    assert report["github_tokens_exposed"] is False
    assert report["kalshi_private_keys_exposed"] is False
    assert report["llm_secrets_exposed"] is False
    assert report["execution_bridge_present"] is False
