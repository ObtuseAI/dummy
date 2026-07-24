"""Generate DUMMY V30 in-house adapter implementation and fixture contract reports."""

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

from predator_mesh.v30 import MILESTONE
from predator_mesh.v30.reports import DEFAULT_REQUIRED_REPORT_NAMES, REPORT_NAMES, V30ReportFactory


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


def generate_v30_report_bundle(*, enable_network: bool = False) -> dict[str, dict[str, Any]]:
    return V30ReportFactory(enable_network=enable_network).build()


def _required_test_commands() -> list[str]:
    return [
        "python -m pytest tests/ -q --tb=short --timeout=60 --durations=25",
        "python -m pytest tests/test_v30_adapter_implementation_selection_v1.py tests/test_in_house_adapter_base_interface_v1.py tests/test_weather_public_observation_adapter_v1.py tests/test_crypto_public_price_adapter_v1.py tests/test_public_event_reference_adapter_v1.py tests/test_kalshi_readonly_rule_adapter_v1.py tests/test_adapter_fixture_contract_implementation_v1.py tests/test_adapter_normalization_pipeline_v1.py tests/test_adapter_to_settlement_compatibility_v1.py tests/test_adapter_observation_closure_dry_run_v1.py tests/test_public_probe_implementation_readiness_v3.py tests/test_sports_fixture_only_adapter_guard_v1.py tests/test_adapter_source_truth_v11.py tests/test_adapter_implementation_partial_reduction_v1.py tests/test_v30_required_report_manifest.py tests/test_no_adapter_implementation_to_execution_bridge_v30.py tests/test_no_adapter_fixture_scored_live_v30.py tests/test_dashboard_v30.py -q --tb=short",
        "cd dashboard/frontend && npm run build",
        "python scripts/generate_v30_reports.py",
    ]


def _required_v30_tests() -> list[str]:
    tests: list[str] = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "tests.v30_test_helpers" in text or "predator_mesh.v30" in text:
            tests.append(path.name)
    return tests


def _v30_report_names(reports: dict[str, dict[str, Any]] | None = None) -> list[str]:
    names = sorted((reports or generate_v30_report_bundle(enable_network=False)).keys())
    return ["final_report.json", "tests_summary.json", "final_report_v30.json", *names]


def _build_final(reports: dict[str, dict[str, Any]], paths: dict[str, Path] | None = None) -> dict[str, Any]:
    paths = paths or {}
    failures = sorted(name for name, data in reports.items() if data.get("verdict") == "FAIL")
    partials = sorted(name for name, data in reports.items() if data.get("verdict") == "PARTIAL")
    mission = reports["dummy_mission_state_report_v16.json"]
    final_verdict = "FAIL" if failures else "PARTIAL" if partials else "PASS"
    all_required = sorted(set(REPORT_NAMES))
    missing = [name for name in all_required if name not in reports]
    final = {
        "generated_at": now_iso(),
        "workstream": "V30: Operator Approved In-House Adapter Implementation Fixture Contracts",
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
            "Use explicit read-only public probe env gate before any real public probe run.",
            "Keep fixture/sample adapter output non-scoring until live public probe evidence exists.",
            "Keep sports fixture/replay-only until a terms-safe public sports source is approved.",
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
        "live_submit_flag_status",
        "caps_config_status",
        "adapter_implementation_selection_status",
        "selected_adapter_count",
        "implemented_adapter_count",
        "deferred_adapter_spec_count",
        "in_house_adapter_base_interface_status",
        "weather_adapter_status",
        "crypto_adapter_status",
        "public_event_reference_adapter_status",
        "kalshi_readonly_rule_adapter_status",
        "fixture_contract_status",
        "fixture_contract_count",
        "adapter_normalization_status",
        "normalized_evidence_packet_count",
        "adapter_to_settlement_compatibility_status",
        "settlement_compatible_packet_count",
        "observation_closure_dry_run_status",
        "dry_run_observed_count",
        "dry_run_score_eligible_count",
        "live_scored_count",
        "live_unresolved_count",
        "observed_forecast_count",
        "public_probe_readiness_status",
        "public_probe_ready_count",
        "integration_mode_status",
        "sports_fixture_only_guard_status",
        "sports_source_mode",
        "adapter_source_truth_v11_status",
        "adapter_implementation_partial_reduction_status",
        "partial_causes_before",
        "partial_causes_after",
        "adapter_sprint_v7_status",
        "compounding_v14_status",
        "next_bundle_recommendation",
        "market_class_scoreboard_v15_status",
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
        "no_context_claimed_edge_status",
        "no_example_market_canonical_center_status",
        "no_unresolved_forecast_scored_status",
        "no_ambiguous_settlement_scored_status",
        "no_source_unavailable_forecast_scored_status",
        "no_not_due_forecast_scored_status",
        "no_adapter_fixture_scored_live_status",
        "no_adapter_dry_run_scored_live_status",
        "no_outcome_fabrication_status",
        "no_adapter_implementation_to_execution_bridge_status",
        "no_adapter_normalization_to_execution_bridge_status",
        "no_settlement_compatibility_to_execution_bridge_status",
        "no_observation_dry_run_to_execution_bridge_status",
        "no_public_probe_readiness_to_execution_bridge_status",
        "no_source_truth_to_execution_bridge_status",
        "no_adapter_sprint_to_execution_bridge_status",
        "blunder_separation_status",
        "dashboard_status",
        "proof_paths",
    ]
    final.update({key: mission[key] for key in passthrough_keys})
    return final


def generate_all_v30_reports_for_tests(*, enable_network: bool = False) -> dict[str, dict[str, Any]]:
    reports = generate_v30_report_bundle(enable_network=enable_network)
    reports["final_report_v30.json"] = _build_final(reports)
    return reports


def _write_final_indexes(final: dict[str, Any], final_path: Path) -> None:
    final_index = dict(final)
    final_index["final_report_v30"] = str(final_path)
    final_index["v30"] = {
        "generated_at": final["generated_at"],
        "milestone": final["milestone"],
        "verdict": final["verdict"],
        "final_report_v30": str(final_path),
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
    (ARTIFACTS / "v30_required_report_names_from_attachment.txt").write_text(
        "\n".join(DEFAULT_REQUIRED_REPORT_NAMES) + "\n",
        encoding="utf-8",
    )


def main() -> dict[str, Any]:
    _write_required_report_names_manifest()
    enable_network = os.environ.get("DUMMY_PUBLIC_INTEGRATION_MODE") == "1"
    reports = generate_v30_report_bundle(enable_network=enable_network)
    paths = {name: _write_report(name, data) for name, data in reports.items()}
    final = _build_final(reports, paths)
    final_path = _write_report("final_report_v30.json", final)
    _write_final_indexes(final, final_path)

    tests_summary = _load_report("tests_summary.json", {})
    tests_summary["v30_required_commands"] = _required_test_commands()
    tests_summary["v30_required_tests"] = _required_v30_tests()
    tests_summary["v30_required_reports"] = _v30_report_names(reports)
    tests_summary["v30_report_generated_at"] = final["generated_at"]
    tests_summary["v30_final_verdict"] = final["verdict"]
    tests_summary["v30_required_test_count"] = len(tests_summary["v30_required_tests"])
    tests_summary["v30_required_report_count"] = len(tests_summary["v30_required_reports"])
    _write_report("tests_summary.json", tests_summary)
    return final


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
