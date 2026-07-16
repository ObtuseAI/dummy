from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_source_credential_requirement_reports_env_names_without_values() -> None:
    report = assert_v20_report("source_credential_requirement_report_v1.json", "requirements")
    assert report["credential_value_storage_allowed"] is False
    assert report["source_api_key_values_exposed"] is False
