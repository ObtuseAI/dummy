"""Generate DUMMY V29 OSS triage, adapter-spec, fixture, and probe-readiness reports."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.evidence_dir import EvidencePath

ARTIFACTS = EvidencePath(ROOT / "artifacts" / "dummy")

from predator_mesh.v29 import MILESTONE
from predator_mesh.v29.reports import DEFAULT_REQUIRED_REPORT_NAMES, REPORT_NAMES, V29ReportFactory


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _write_report(name: str, data: dict[str, Any]) -> Path:
    path = ARTIFACTS / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return path


def _load_report(name: str, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    path = ARTIFACTS / name
    if not path.exists():
        return fallback or {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback or {}


def generate_v29_report_bundle(*, enable_network: bool = False) -> dict[str, dict[str, Any]]:
    return V29ReportFactory(enable_network=enable_network).build()


def _required_test_commands() -> list[str]:
    return [
        "python -m pytest tests/ -q --tb=short --timeout=60 --durations=25",
        "python -m pytest tests/test_oss_candidate_universe_normalizer_v1.py tests/test_oss_license_terms_triage_v1.py tests/test_adapter_spec_factory_v1.py tests/test_fixture_schema_generator_v1.py tests/test_adapter_contract_test_planner_v1.py tests/test_public_probe_readiness_planner_v2.py tests/test_settlement_gap_adapter_mapper_v1.py tests/test_sports_source_legality_resolver_v3.py tests/test_oss_candidate_promotion_gate_v1.py tests/test_domain_market_class_scoreboard_v14.py tests/test_dummy_mission_state_v29.py tests/test_v29_required_report_manifest.py tests/test_no_browser_automation_v29.py tests/test_no_mined_repo_execution_v29.py tests/test_no_adapter_spec_to_execution_bridge_v29.py tests/test_no_public_probe_readiness_to_execution_bridge_v29.py tests/test_dashboard_v29.py -q --tb=short",
        "cd dashboard/frontend && npm run build",
        "python scripts/generate_v29_reports.py",
    ]


def _required_v29_tests() -> list[str]:
    tests_dir = ROOT / "tests"
    tests: list[str] = []
    for path in sorted(tests_dir.glob("test_*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "tests.v29_test_helpers" in text:
            tests.append(path.name)
    return tests


def _v29_report_names(reports: dict[str, dict[str, Any]] | None = None) -> list[str]:
    names = sorted((reports or generate_v29_report_bundle(enable_network=False)).keys())
    return ["final_report.json", "tests_summary.json", "final_report_v29.json", *names]


def _build_final(reports: dict[str, dict[str, Any]], paths: dict[str, Path] | None = None) -> dict[str, Any]:
    paths = paths or {}
    failures = sorted(name for name, data in reports.items() if data.get("verdict") == "FAIL")
    partials = sorted(name for name, data in reports.items() if data.get("verdict") == "PARTIAL")
    mission = reports["dummy_mission_state_report_v15.json"]
    final_verdict = "FAIL" if failures else "PARTIAL" if partials else "PASS"
    report_paths = {name: str(paths.get(name, ARTIFACTS / name)) for name in reports}
    all_required = sorted(set(REPORT_NAMES))
    missing = [name for name in all_required if name not in reports]
    return {
        "generated_at": now_iso(),
        "workstream": "V29: OSS Candidate Triage Adapter Spec Factory And Public Data Probe Readiness",
        "milestone": MILESTONE,
        "verdict": final_verdict,
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "read_only_only": True,
        "secret_values_exposed": False,
        "execution_bridge_present": False,
        "trading_endpoints_used": False,
        "cancel_endpoints_used": False,
        "private_endpoints_used": False,
        "order_endpoints_used": False,
        "github_mining_mode": "metadata_only_no_clone_no_import_no_execute",
        "mined_repo_cloned": False,
        "mined_repo_imported": False,
        "mined_repo_executed": False,
        "blind_mined_code_copied": False,
        "partial_reason": "" if final_verdict == "PASS" else "; ".join(mission["partial_reasons"]),
        "report_verdicts": {name: data.get("verdict") for name, data in reports.items()},
        "report_paths": report_paths,
        "required_report_count": len(all_required),
        "all_required_reports_generated": not missing,
        "missing_required_reports": missing,
        "failures": failures,
        "partials": partials,
        "v17_truth_loop_status": mission["v17_truth_loop_status"],
        "v21_source_activation_status": mission["v21_source_activation_status"],
        "v22_forecast_write_status": mission["v22_forecast_write_status"],
        "v23_observer_calibration_status": mission["v23_observer_calibration_status"],
        "v24_open_source_public_data_status": mission["v24_open_source_public_data_status"],
        "v25_market_class_generalization_status": mission["v25_market_class_generalization_status"],
        "v26_keyless_settlement_expansion_status": mission["v26_keyless_settlement_expansion_status"],
        "v27_integration_settlement_live_scoring_status": mission["v27_integration_settlement_live_scoring_status"],
        "v28_oss_observation_closure_status": mission["v28_oss_observation_closure_status"],
        "live_submit_enabled": mission["live_submit_enabled"],
        "live_submit_flag_status": mission["live_submit_flag_status"],
        "caps_config_status": mission["caps_config_status"],
        "oss_candidate_universe_status": mission["oss_candidate_universe_status"],
        "total_candidate_count": mission["total_candidate_count"],
        "category_counts": mission["category_counts"],
        "keyword_provenance_status": mission["keyword_provenance_status"],
        "license_terms_triage_status": mission["license_terms_triage_status"],
        "license_triage_verdict_counts": mission["license_triage_verdict_counts"],
        "maintenance_quality_status": mission["maintenance_quality_status"],
        "market_class_oss_fit_status": mission["market_class_oss_fit_status"],
        "adapter_spec_factory_status": mission["adapter_spec_factory_status"],
        "adapter_spec_ready_count": mission["adapter_spec_ready_count"],
        "fixture_schema_generator_status": mission["fixture_schema_generator_status"],
        "fixture_contract_ready_count": mission["fixture_contract_ready_count"],
        "adapter_contract_test_planner_status": mission["adapter_contract_test_planner_status"],
        "public_probe_readiness_status": mission["public_probe_readiness_status"],
        "public_probe_ready_count": mission["public_probe_ready_count"],
        "settlement_gap_adapter_mapper_status": mission["settlement_gap_adapter_mapper_status"],
        "settlement_gap_closure_candidate_count": mission["settlement_gap_closure_candidate_count"],
        "sports_legality_resolver_status": mission["sports_legality_resolver_status"],
        "sports_source_mode": mission["sports_source_mode"],
        "weather_adapter_spec_pack_status": mission["weather_adapter_spec_pack_status"],
        "crypto_adapter_spec_pack_status": mission["crypto_adapter_spec_pack_status"],
        "event_market_adapter_spec_pack_status": mission["event_market_adapter_spec_pack_status"],
        "trading_backtesting_reference_status": mission["trading_backtesting_reference_status"],
        "bloomberg_alternative_reference_status": mission["bloomberg_alternative_reference_status"],
        "oss_candidate_promotion_gate_status": mission["oss_candidate_promotion_gate_status"],
        "promotion_level_counts": mission["promotion_level_counts"],
        "adapter_sprint_v6_status": mission["adapter_sprint_v6_status"],
        "compounding_v13_status": mission["compounding_v13_status"],
        "next_bundle_recommendation": mission["next_bundle_recommendation"],
        "market_class_scoreboard_v14_status": mission["market_class_scoreboard_v14_status"],
        "mission_state_verdict": mission["mission_state_verdict"],
        "live_scored_count": mission["live_scored_count"],
        "live_unresolved_count": mission["live_unresolved_count"],
        "observed_forecast_count": mission["observed_forecast_count"],
        "integration_mode_status": mission["integration_mode_status"],
        "no_secret_leak_status": mission["no_secret_leak_status"],
        "no_source_api_key_leak_status": mission["no_source_api_key_leak_status"],
        "no_github_token_leak_status": mission["no_github_token_leak_status"],
        "no_kalshi_private_key_leak_status": mission["no_kalshi_private_key_leak_status"],
        "no_direct_order_bypass_status": mission["no_direct_order_bypass_status"],
        "no_direct_cancel_bypass_status": mission["no_direct_cancel_bypass_status"],
        "no_unauthorized_source_status": mission["no_unauthorized_source_status"],
        "no_questionable_odds_scraping_status": mission["no_questionable_odds_scraping_status"],
        "no_unapproved_source_activation_status": mission["no_unapproved_source_activation_status"],
        "no_commercial_source_without_approval_status": mission["no_commercial_source_without_approval_status"],
        "no_premium_feed_required_global_blocker_status": mission["no_premium_feed_required_global_blocker_status"],
        "no_browser_automation_status": mission["no_browser_automation_status"],
        "no_pageagent_status": mission["no_pageagent_status"],
        "no_dom_extraction_status": mission["no_dom_extraction_status"],
        "no_browser_research_lane_status": mission["no_browser_research_lane_status"],
        "no_mined_repo_clone_status": mission["no_mined_repo_clone_status"],
        "no_mined_repo_import_status": mission["no_mined_repo_import_status"],
        "no_mined_repo_execution_status": mission["no_mined_repo_execution_status"],
        "no_blind_mined_code_copy_status": mission["no_blind_mined_code_copy_status"],
        "no_fixture_claimed_real_status": mission["no_fixture_claimed_real_status"],
        "no_replay_claimed_live_status": mission["no_replay_claimed_live_status"],
        "no_replay_score_claimed_live_status": mission["no_replay_score_claimed_live_status"],
        "no_proxy_claimed_exchange_native_status": mission["no_proxy_claimed_exchange_native_status"],
        "no_cached_sample_claimed_live_status": mission["no_cached_sample_claimed_live_status"],
        "no_stale_cached_evidence_scored_live_status": mission["no_stale_cached_evidence_scored_live_status"],
        "no_context_claimed_edge_status": mission["no_context_claimed_edge_status"],
        "no_example_market_canonical_center_status": mission["no_example_market_canonical_center_status"],
        "no_unresolved_forecast_scored_status": mission["no_unresolved_forecast_scored_status"],
        "no_ambiguous_settlement_scored_status": mission["no_ambiguous_settlement_scored_status"],
        "no_source_unavailable_forecast_scored_status": mission["no_source_unavailable_forecast_scored_status"],
        "no_not_due_forecast_scored_status": mission["no_not_due_forecast_scored_status"],
        "no_outcome_fabrication_status": mission["no_outcome_fabrication_status"],
        "no_oss_triage_to_execution_bridge_status": mission["no_oss_triage_to_execution_bridge_status"],
        "no_adapter_spec_to_execution_bridge_status": mission["no_adapter_spec_to_execution_bridge_status"],
        "no_public_probe_readiness_to_execution_bridge_status": mission["no_public_probe_readiness_to_execution_bridge_status"],
        "no_source_truth_to_execution_bridge_status": mission["no_source_truth_to_execution_bridge_status"],
        "no_adapter_sprint_to_execution_bridge_status": mission["no_adapter_sprint_to_execution_bridge_status"],
        "blunder_separation_status": mission["blunder_separation_status"],
        "dashboard_status": mission["dashboard_status"],
        "proof_paths": mission["proof_paths"],
        "remaining_operator_actions": [
            "Approve a specific in-house adapter implementation sprint before importing any normal package through repo-owned dependency controls.",
            "Keep sports, betting, wagering, sportsbook, gambling, fantasy, daily fantasy, and sports drafting sources fixture/reference-only until terms-safe sources are approved.",
            "Enable read-only public probe integration only with explicit DUMMY_PUBLIC_INTEGRATION_MODE=1 and DUMMY_PUBLIC_INTEGRATION_CONFIRM=READ_ONLY_PUBLIC_PROBES.",
            "Do not treat Bloomberg or other keyed commercial feeds as required global blockers.",
        ],
    }


def generate_all_v29_reports_for_tests(*, enable_network: bool = False) -> dict[str, dict[str, Any]]:
    reports = generate_v29_report_bundle(enable_network=enable_network)
    reports["final_report_v29.json"] = _build_final(reports)
    return reports


def _write_final_indexes(final: dict[str, Any], final_path: Path) -> None:
    final_index = dict(final)
    final_index["final_report_v29"] = str(final_path)
    final_index["v29"] = {
        "generated_at": final["generated_at"],
        "milestone": final["milestone"],
        "verdict": final["verdict"],
        "final_report_v29": str(final_path),
        "partial_reason": final["partial_reason"],
    }
    existing = _load_report("final_report.json", {})
    if existing:
        final_index["previous_final_report_snapshot"] = {
            key: existing[key]
            for key in ("generated_at", "milestone", "verdict", "partial_reason")
            if key in existing
        }
        for key, value in existing.items():
            if re.fullmatch(r"v\d+(?:_\d+)?", key) and key not in final_index:
                final_index[key] = value
    (ARTIFACTS / "final_report.json").write_text(json.dumps(final_index, indent=2, default=str), encoding="utf-8")


def _write_required_report_names_manifest() -> None:
    (ARTIFACTS / "v29_required_report_names_from_attachment.txt").write_text(
        "\n".join(DEFAULT_REQUIRED_REPORT_NAMES) + "\n",
        encoding="utf-8",
    )


def main() -> dict[str, Any]:
    _write_required_report_names_manifest()
    enable_network = os.environ.get("DUMMY_PUBLIC_INTEGRATION_MODE") == "1"
    reports = generate_v29_report_bundle(enable_network=enable_network)
    paths = {name: _write_report(name, data) for name, data in reports.items()}

    final = _build_final(reports, paths)
    final_path = _write_report("final_report_v29.json", final)
    paths["final_report_v29.json"] = final_path
    _write_final_indexes(final, final_path)

    tests_summary = _load_report("tests_summary.json", {})
    tests_summary["v29_required_commands"] = _required_test_commands()
    tests_summary["v29_required_tests"] = _required_v29_tests()
    tests_summary["v29_required_reports"] = _v29_report_names(reports)
    tests_summary["v29_report_generated_at"] = final["generated_at"]
    tests_summary["v29_final_verdict"] = final["verdict"]
    tests_summary["v29_required_test_count"] = len(tests_summary["v29_required_tests"])
    tests_summary["v29_required_report_count"] = len(tests_summary["v29_required_reports"])
    _write_report("tests_summary.json", tests_summary)

    return final


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
