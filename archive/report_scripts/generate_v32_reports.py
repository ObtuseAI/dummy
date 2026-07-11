"""Generate DUMMY V32 source recovery and live observation expansion reports."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS = ROOT / "artifacts" / "dummy"
ARTIFACTS.mkdir(parents=True, exist_ok=True)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh.v32 import MILESTONE
from predator_mesh.v32.reports import DEFAULT_REQUIRED_REPORT_NAMES, REPORT_NAMES, V32ReportFactory


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _write_report(name: str, data: dict[str, Any]) -> Path:
    path = ARTIFACTS / name
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


def generate_v32_report_bundle(*, enable_network: bool = False) -> dict[str, dict[str, Any]]:
    return V32ReportFactory(enable_network=enable_network, env={}).build()


def _required_test_commands() -> list[str]:
    return [
        "python -m pytest tests/ -q --tb=short --timeout=60 --durations=25",
        "python -m pytest tests/test_v32_source_recovery_controller_v1.py tests/test_operator_gated_probe_run_v2.py tests/test_minimal_public_probe_pass_v1.py tests/test_live_public_evidence_expansion_v2.py tests/test_settlement_compatible_evidence_expansion_v2.py tests/test_due_forecast_closure_expansion_v5.py tests/test_live_score_expansion_seed_v3.py tests/test_v32_required_report_manifest.py tests/test_probe_cache_replay_separation_v2.py tests/test_source_truth_recovery_closure_v13.py tests/test_no_source_recovery_to_execution_bridge_v32.py tests/test_no_disabled_probe_scored_live_v32.py tests/test_dashboard_v32.py -q --tb=short",
        "cd dashboard/frontend && npm run build",
        "python scripts/generate_v32_reports.py",
    ]


def _required_v32_tests() -> list[str]:
    tests: list[str] = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "tests.v32_test_helpers" in text or "predator_mesh.v32" in text:
            tests.append(path.name)
    return tests


def _v32_report_names(reports: dict[str, dict[str, Any]] | None = None) -> list[str]:
    names = sorted((reports or generate_v32_report_bundle(enable_network=False)).keys())
    return ["final_report.json", "tests_summary.json", "final_report_v32.json", *names]


def _build_final(reports: dict[str, dict[str, Any]], paths: dict[str, Path] | None = None) -> dict[str, Any]:
    paths = paths or {}
    failures = sorted(name for name, data in reports.items() if data.get("verdict") == "FAIL")
    partials = sorted(name for name, data in reports.items() if data.get("verdict") == "PARTIAL")
    mission = reports["dummy_mission_state_report_v18.json"]
    final_verdict = "FAIL" if failures else "PARTIAL" if partials else "PASS"
    all_required = sorted(set(REPORT_NAMES))
    missing = [name for name in all_required if name not in reports]
    final = {
        "generated_at": now_iso(),
        "workstream": "V32: Source Recovery Live Observation Expansion",
        "milestone": MILESTONE,
        "verdict": final_verdict,
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "read_only_only": True,
        "secret_values_exposed": False,
        "execution_bridge_present": False,
        "partial_reason": "" if final_verdict == "PASS" else "; ".join(mission["partial_reasons"]),
        "report_verdicts": {name: data.get("verdict") for name, data in reports.items()},
        "report_paths": {name: str(paths.get(name, ARTIFACTS / name)) for name in reports},
        "required_report_count": len(all_required),
        "all_required_reports_generated": not missing,
        "missing_required_reports": missing,
        "failures": failures,
        "partials": partials,
        "remaining_operator_actions": [
            "Set DUMMY_PUBLIC_PROBE_MODE=1 and DUMMY_PUBLIC_PROBE_ACK=READ_ONLY_PUBLIC_PROBES_ONLY before running the bounded public probe pass.",
            "Review Kalshi READ_ONLY access and sports source approval before expanding those source families.",
            "Leave live-submit and caps unchanged.",
        ],
    }
    passthrough_keys = [
        "v17_truth_loop_status",
        "v21_source_activation_status",
        "v22_forecast_write_status",
        "v23_observer_calibration_status",
        "v24_open_source_public_data_status",
        "v25_market_class_generalization_status",
        "v26_keyless_settlement_expansion_status",
        "v27_integration_settlement_live_scoring_status",
        "v28_oss_observation_closure_status",
        "v29_oss_adapter_spec_factory_status",
        "v30_in_house_adapter_implementation_status",
        "v31_public_probe_execution_status",
        "live_submit_flag_status",
        "caps_config_status",
        "source_recovery_controller_status",
        "operator_gated_probe_run_status",
        "gate_state",
        "ack_validation_status",
        "minimal_public_probe_pass_status",
        "probe_run_count",
        "probe_source_family_count",
        "weather_recovery_status",
        "crypto_recovery_status",
        "public_event_recovery_status",
        "kalshi_readonly_recovery_status",
        "live_public_evidence_expansion_status",
        "live_public_evidence_packet_count",
        "settlement_compatible_evidence_expansion_status",
        "settlement_compatible_evidence_count",
        "due_forecast_closure_expansion_status",
        "due_forecast_count",
        "observed_forecast_count",
        "live_score_expansion_status",
        "live_scored_count",
        "live_unresolved_count",
        "live_calibration_expansion_status",
        "probe_cache_replay_separation_status",
        "sports_fixture_guard_status",
        "sports_source_mode",
        "source_truth_recovery_closure_v13_status",
        "partial_reduction_status",
        "partial_causes_before",
        "partial_causes_after",
        "source_recovery_sprint_queue_v9_status",
        "compounding_v16_status",
        "next_bundle_recommendation",
        "market_class_scoreboard_v17_status",
        "mission_state_verdict",
        "no_secret_leak_status",
        "no_source_api_key_leak_status",
        "no_github_token_leak_status",
        "no_kalshi_private_key_leak_status",
        "no_direct_order_bypass_status",
        "no_direct_cancel_bypass_status",
        "no_unauthorized_source_status",
        "no_questionable_odds_scraping_status",
        "no_unapproved_source_activation_status",
        "no_commercial_source_without_approval_status",
        "no_premium_feed_required_global_blocker_status",
        "no_browser_automation_status",
        "no_pageagent_status",
        "no_dom_extraction_status",
        "no_browser_research_lane_status",
        "no_mined_repo_clone_status",
        "no_mined_repo_import_status",
        "no_mined_repo_execution_status",
        "no_blind_mined_code_copy_status",
        "no_fixture_claimed_real_status",
        "no_replay_claimed_live_status",
        "no_replay_score_claimed_live_status",
        "no_proxy_claimed_exchange_native_status",
        "no_cached_sample_claimed_live_status",
        "no_stale_cached_evidence_scored_live_status",
        "no_public_sample_evidence_scored_live_status",
        "no_context_claimed_edge_status",
        "no_example_market_canonical_center_status",
        "no_unresolved_forecast_scored_status",
        "no_ambiguous_settlement_scored_status",
        "no_source_unavailable_forecast_scored_status",
        "no_not_due_forecast_scored_status",
        "no_adapter_fixture_scored_live_status",
        "no_adapter_dry_run_scored_live_status",
        "no_public_probe_failure_scored_live_status",
        "no_disabled_probe_scored_live_status",
        "no_outcome_fabrication_status",
        "no_source_recovery_to_execution_bridge_status",
        "no_operator_gated_probe_run_to_execution_bridge_status",
        "no_minimal_public_probe_pass_to_execution_bridge_status",
        "no_live_public_evidence_expansion_to_execution_bridge_status",
        "no_settlement_compatible_evidence_to_execution_bridge_status",
        "no_due_closure_expansion_to_execution_bridge_status",
        "no_live_score_expansion_to_execution_bridge_status",
        "no_live_calibration_expansion_to_execution_bridge_status",
        "no_probe_cache_to_execution_bridge_status",
        "no_source_truth_to_execution_bridge_status",
        "no_source_recovery_sprint_to_execution_bridge_status",
        "blunder_separation_status",
        "dashboard_status",
        "proof_paths",
    ]
    final.update({key: mission[key] for key in passthrough_keys})
    return final


def generate_all_v32_reports_for_tests(*, enable_network: bool = False) -> dict[str, dict[str, Any]]:
    reports = generate_v32_report_bundle(enable_network=enable_network)
    reports["final_report_v32.json"] = _build_final(reports)
    return reports


def _write_final_indexes(final: dict[str, Any], final_path: Path) -> None:
    final_index = {
        "generated_at": final["generated_at"],
        "workstream": final["workstream"],
        "milestone": final["milestone"],
        "verdict": final["verdict"],
        "partial_reason": final["partial_reason"],
        "required_report_count": final["required_report_count"],
        "all_required_reports_generated": final["all_required_reports_generated"],
        "gate_state": final["gate_state"],
        "probe_run_count": final["probe_run_count"],
        "live_public_evidence_packet_count": final["live_public_evidence_packet_count"],
        "observed_forecast_count": final["observed_forecast_count"],
        "live_scored_count": final["live_scored_count"],
        "live_submit_flag_status": final["live_submit_flag_status"],
        "caps_config_status": final["caps_config_status"],
        "mission_state_verdict": final["mission_state_verdict"],
        "final_report_v32": str(final_path),
        "proof_paths": final["proof_paths"],
    }
    final_index["v32"] = {
        "generated_at": final["generated_at"],
        "milestone": final["milestone"],
        "verdict": final["verdict"],
        "final_report_v32": str(final_path),
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
    _write_report("final_report.json", final_index)


def _write_required_report_names_manifest() -> None:
    (ARTIFACTS / "v32_required_report_names_from_attachment.txt").write_text(
        "\n".join(DEFAULT_REQUIRED_REPORT_NAMES) + "\n",
        encoding="utf-8",
    )


def main() -> dict[str, Any]:
    _write_required_report_names_manifest()
    reports = generate_v32_report_bundle(enable_network=False)
    paths = {name: _write_report(name, data) for name, data in reports.items()}
    final = _build_final(reports, paths)
    final_path = _write_report("final_report_v32.json", final)
    _write_final_indexes(final, final_path)

    tests_summary = _load_report("tests_summary.json", {})
    tests_summary["v32_required_commands"] = _required_test_commands()
    tests_summary["v32_required_tests"] = _required_v32_tests()
    tests_summary["v32_required_reports"] = _v32_report_names(reports)
    tests_summary["v32_report_generated_at"] = final["generated_at"]
    tests_summary["v32_final_verdict"] = final["verdict"]
    tests_summary["v32_required_test_count"] = len(tests_summary["v32_required_tests"])
    tests_summary["v32_required_report_count"] = len(tests_summary["v32_required_reports"])
    _write_report("tests_summary.json", tests_summary)
    return final


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
