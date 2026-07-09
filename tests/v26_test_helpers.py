from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


_EXPLICIT_REPORTS = {
    "dummy_mission_state_v26": "dummy_mission_state_report_v12.json",
    "dashboard_v26": "dashboard_v26_report_v1.json",
    "timeout_guards_still_intact_v26": "v26_runtime_budget_report_v1.json",
    "v17_truth_loop_still_passes_v26": "final_report_v26.json",
    "v21_source_activation_still_passes_v26": "final_report_v26.json",
    "v22_forecast_write_breakthrough_still_passes_v26": "final_report_v26.json",
    "v23_observer_calibration_still_passes_or_partial_expected_v26": "final_report_v26.json",
    "v24_open_source_public_data_still_passes_v26": "final_report_v26.json",
    "v25_market_class_generalization_still_passes_or_partial_expected_v26": "final_report_v26.json",
}


def _candidate_report_names(stem: str) -> list[str]:
    if stem in _EXPLICIT_REPORTS:
        return [_EXPLICIT_REPORTS[stem]]
    if stem.endswith("_v26") and (
        stem.startswith("no_")
        or stem.startswith("readonly_only_")
        or stem in {"blunder_separation_v26", "dummy_canonical_identity_v26"}
    ):
        base = stem.removesuffix("_v26")
        if base == "blunder_separation":
            return ["blunder_separation_recheck_v26.json"]
        if base == "dummy_canonical_identity":
            return ["dummy_canonical_identity_report_v26.json"]
        return [f"{base}_report_v26.json"]
    return [
        f"{stem}_report.json",
        f"{stem}_report_v1.json",
        f"{stem}_v1_report.json",
        f"{stem}_v2_report.json",
        f"{stem}_v3_report.json",
        f"{stem}_proof_v1.json",
        f"{stem}_scoreboard_v1.json",
    ]


def report_name_for_test(test_file: str | Path) -> str:
    stem = Path(test_file).stem.removeprefix("test_")
    reports = v26_reports()
    for candidate in _candidate_report_names(stem):
        if candidate in reports:
            return candidate
    raise AssertionError(f"No V26 report mapped for {stem}")


def assert_no_execution_or_secrets(report: dict) -> None:
    text = json.dumps(report, default=str)
    banned_fragments = [
        "BEGIN PRIVATE KEY",
        "END PRIVATE KEY",
        "github_pat_",
        "ghp_",
        "raw_prompt",
        "api_key_value",
        "source_api_key_value",
        "private_key_pem",
        "LiveBrokerFirewall.submit(",
    ]
    for fragment in banned_fragments:
        assert fragment not in text, fragment
    assert report.get("secret_values_exposed") is False
    assert report.get("live_submit_disabled") is True
    assert report.get("caps_unchanged") is True


def assert_pass_or_partial(report: dict) -> None:
    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report["read_only_only"] is True
    assert_no_execution_or_secrets(report)


@lru_cache(maxsize=1)
def v26_reports() -> dict[str, dict]:
    from scripts.generate_v26_reports import generate_all_v26_reports_for_tests

    return generate_all_v26_reports_for_tests(enable_network=False)


def assert_v26_report_named(report_name: str, *required_keys: str) -> dict:
    reports = v26_reports()
    assert report_name in reports, report_name
    report = reports[report_name]
    assert_pass_or_partial(report)
    for key in required_keys:
        assert key in report
    return report


def assert_current_test_report(test_file: str | Path) -> dict:
    return assert_v26_report_named(report_name_for_test(test_file), "workstream")
