from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


_EXPLICIT_REPORTS = {
    "dashboard_v21": "dashboard_v21_report_v1.json",
    "source_approval_operator_packet": "source_approval_operator_packet_v1.json",
    "source_allowlist_delta_recommendation": "source_allowlist_delta_recommendation_v1.json",
    "official_public_evidence_packet_manifest": "official_public_evidence_packet_manifest_v1.json",
    "eia_energy_real_adapter_v1": "eia_energy_real_adapter_v1_report.json",
    "nws_weather_real_adapter_v1": "nws_weather_real_adapter_v1_report.json",
    "finance_macro_official_activation_v1": "finance_macro_official_activation_v1_report.json",
    "nasdaq_direction_bootstrap_v1": "nasdaq_direction_bootstrap_v1_report.json",
    "oil_direction_bootstrap_v1": "oil_direction_bootstrap_v1_report.json",
    "vendor_capability_matrix": "vendor_capability_matrix_v1.json",
    "operator_acquisition_checklist": "operator_acquisition_checklist_v1.json",
    "source_activation_breakout_scoreboard": "source_activation_breakout_scoreboard_v1.json",
    "evidence_router_v3": "evidence_router_v3_report.json",
    "evidence_sufficiency_v2": "evidence_sufficiency_v2_report.json",
    "forecast_pipeline_v3": "forecast_pipeline_v3_report.json",
    "compounding_control_plane_v4": "compounding_control_plane_v4_report.json",
    "domain_scoreboard_v5": "domain_scoreboard_v5_report.json",
    "dummy_mission_state_v21": "dummy_mission_state_report_v7.json",
    "v21_runtime_budget": "v21_runtime_budget_report_v1.json",
    "dashboard_cache_policy_v3": "dashboard_cache_policy_v3_report.json",
    "report_chain_runtime_profiler_v4": "report_chain_runtime_profiler_v4_report.json",
    "blunder_separation_v21": "blunder_separation_recheck_v21.json",
    "dummy_canonical_identity_v21": "dummy_canonical_identity_report_v21.json",
    "timeout_guards_still_intact_v21": "v21_runtime_budget_report_v1.json",
    "v17_truth_loop_still_passes_v21": "final_report_v21.json",
    "v18_domain_foundation_still_passes_or_partial_expected_v21": "final_report_v21.json",
    "v19_activation_architecture_still_passes_or_partial_expected_v21": "final_report_v21.json",
    "v20_source_universe_still_passes_or_partial_expected_v21": "final_report_v21.json",
}


def report_name_for_test(test_file: str | Path) -> str:
    stem = Path(test_file).stem.removeprefix("test_")
    if stem in _EXPLICIT_REPORTS:
        return _EXPLICIT_REPORTS[stem]
    if stem.endswith("_v21"):
        return f"{stem.removesuffix('_v21')}_report_v21.json"
    return f"{stem}_report_v1.json"


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
    ]
    for fragment in banned_fragments:
        assert fragment not in text, fragment
    assert report.get("secret_values_exposed") is False


def assert_pass_or_partial(report: dict) -> None:
    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert_no_execution_or_secrets(report)


@lru_cache(maxsize=1)
def v21_reports() -> dict[str, dict]:
    from archive.report_scripts.generate_v21_reports import generate_all_v21_reports_for_tests

    return generate_all_v21_reports_for_tests(enable_network=False)


def assert_v21_report_named(report_name: str, *required_keys: str) -> dict:
    reports = v21_reports()
    assert report_name in reports, report_name
    report = reports[report_name]
    assert_pass_or_partial(report)
    for key in required_keys:
        assert key in report
    return report


def assert_current_test_report(test_file: str | Path) -> dict:
    return assert_v21_report_named(report_name_for_test(test_file), "workstream")
