"""Generate DUMMY V26 keyless public adapter and settlement expansion reports."""

from __future__ import annotations

import json
import os
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

from predator_mesh.v26 import MILESTONE
from predator_mesh.v26.reports import REPORT_NAMES, V26ReportFactory


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


def generate_v26_report_bundle(*, enable_network: bool = False) -> dict[str, dict[str, Any]]:
    return V26ReportFactory(enable_network=enable_network).build()


def _required_test_commands() -> list[str]:
    return [
        "python -m pytest tests/ -vv -s --tb=short --maxfail=1 --durations=25 --timeout=60",
        "python -m pytest tests/ -q --tb=short --timeout=60",
        "cd dashboard/frontend && npm run build",
        *[
            f"python scripts/generate_v{suffix}_reports.py"
            for suffix in [
                "8",
                "8_1",
                "8_2",
                "9",
                "10",
                "11",
                "12",
                "13",
                "14",
                "15",
                "16",
                "17",
                "18",
                "19",
                "20",
                "21",
                "22",
                "23",
                "24",
                "25",
                "26",
            ]
        ],
    ]


def _required_v26_tests() -> list[str]:
    tests_dir = ROOT / "tests"
    tests: list[str] = []
    for path in sorted(tests_dir.glob("test_*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "tests.v26_test_helpers" in text:
            tests.append(path.name)
    return tests


def _v26_report_names(reports: dict[str, dict[str, Any]] | None = None) -> list[str]:
    names = sorted((reports or generate_v26_report_bundle(enable_network=False)).keys())
    return ["final_report.json", "tests_summary.json", "final_report_v26.json", *names]


def _build_final(reports: dict[str, dict[str, Any]], paths: dict[str, Path] | None = None) -> dict[str, Any]:
    paths = paths or {}
    failures = sorted(name for name, data in reports.items() if data.get("verdict") == "FAIL")
    partials = sorted(name for name, data in reports.items() if data.get("verdict") == "PARTIAL")
    mission = reports["dummy_mission_state_report_v12.json"]
    final_v17 = _load_report("final_report_v17.json", {})
    final_v21 = _load_report("final_report_v21.json", {})
    final_v22 = _load_report("final_report_v22.json", {})
    final_v23 = _load_report("final_report_v23.json", {})
    final_v24 = _load_report("final_report_v24.json", {})
    final_v25 = _load_report("final_report_v25.json", {})
    final_verdict = "FAIL" if failures else "PARTIAL" if partials else "PASS"
    report_paths = {name: str(paths.get(name, ARTIFACTS / name)) for name in reports}
    return {
        "generated_at": now_iso(),
        "workstream": "V26: Keyless Public Market-Class Adapters And Settlement Expansion",
        "milestone": MILESTONE,
        "verdict": final_verdict,
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "read_only_only": True,
        "secret_values_exposed": False,
        "partial_reason": "" if final_verdict == "PASS" else "; ".join(mission["partial_reasons"]),
        "report_verdicts": {name: data.get("verdict") for name, data in reports.items()},
        "report_paths": report_paths,
        "failures": failures,
        "partials": partials,
        "v17_truth_loop_status": final_v17.get("verdict", mission["v17_truth_loop_status"]),
        "v21_source_activation_status": final_v21.get("verdict", mission["v21_source_activation_status"]),
        "v22_forecast_write_status": final_v22.get("forecast_write_breakthrough_status", mission["v22_forecast_write_status"]),
        "v23_observer_calibration_status": final_v23.get("v22_forecast_observer_closure_status", mission["v23_observer_calibration_status"]),
        "v24_open_source_public_data_status": final_v24.get("verdict", mission["v24_open_source_public_data_status"]),
        "v25_market_class_generalization_status": final_v25.get("verdict", mission["v25_market_class_generalization_status"]),
        "live_submit_enabled": False,
        "live_submit_flag_status": mission["live_submit_flag_status"],
        "caps_config_status": mission["caps_config_status"],
        "keyless_public_adapter_registry_status": mission["keyless_public_adapter_registry_status"],
        "keyless_adapter_active_count": mission["keyless_adapter_active_count"],
        "keyless_probe_status": mission["keyless_probe_status"],
        "weather_settlement_expansion_status": mission["weather_settlement_expansion_status"],
        "crypto_settlement_expansion_status": mission["crypto_settlement_expansion_status"],
        "commodity_public_reference_adapter_status": mission["commodity_public_reference_adapter_status"],
        "finance_macro_public_event_adapter_status": mission["finance_macro_public_event_adapter_status"],
        "sports_public_schedule_status_adapter_status": mission["sports_public_schedule_status_adapter_status"],
        "public_event_generic_adapter_status": mission["public_event_generic_adapter_status"],
        "kalshi_readonly_market_class_join_status": mission["kalshi_readonly_market_class_join_status"],
        "settlement_closure_status": mission["settlement_closure_status"],
        "forecast_resolution_accelerator_status": mission["forecast_resolution_accelerator_status"],
        "market_class_forecast_cadence_v2_status": mission["market_class_forecast_cadence_v2_status"],
        "forecast_write_count": mission["forecast_write_count"],
        "no_trade_write_count": mission["no_trade_write_count"],
        "observer_queue_count": mission["observer_queue_count"],
        "due_forecast_count": mission["due_forecast_count"],
        "observed_forecast_count": mission["observed_forecast_count"],
        "live_scored_count": mission["live_scored_count"],
        "live_unresolved_count": mission["live_unresolved_count"],
        "replay_scored_count": mission["replay_scored_count"],
        "replay_to_live_selector_status": mission["replay_to_live_selector_status"],
        "source_truth_v8_status": mission["source_truth_v8_status"],
        "adapter_sprint_queue_status": mission["adapter_sprint_queue_status"],
        "compounding_v10_status": mission["compounding_v10_status"],
        "next_bundle_recommendation": mission["next_bundle_recommendation"],
        "market_class_scoreboard_v11_status": mission["market_class_scoreboard_v11_status"],
        "mission_state_verdict": mission["mission_state_verdict"],
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
        "no_fixture_claimed_real_status": mission["no_fixture_claimed_real_status"],
        "no_replay_claimed_live_status": mission["no_replay_claimed_live_status"],
        "no_replay_score_claimed_live_status": mission["no_replay_score_claimed_live_status"],
        "no_proxy_claimed_exchange_native_status": mission["no_proxy_claimed_exchange_native_status"],
        "no_context_claimed_edge_status": mission["no_context_claimed_edge_status"],
        "no_example_market_canonical_center_status": mission["no_example_market_canonical_center_status"],
        "no_unresolved_forecast_scored_status": mission["no_unresolved_forecast_scored_status"],
        "no_outcome_fabrication_status": mission["no_outcome_fabrication_status"],
        "no_keyless_probe_to_execution_bridge_status": mission["no_keyless_probe_to_execution_bridge_status"],
        "no_settlement_probe_to_execution_bridge_status": mission["no_settlement_probe_to_execution_bridge_status"],
        "no_forecast_resolution_to_execution_bridge_status": mission["no_forecast_resolution_to_execution_bridge_status"],
        "no_live_scoring_to_execution_bridge_status": mission["no_live_scoring_to_execution_bridge_status"],
        "no_replay_to_live_selector_to_execution_bridge_status": mission["no_replay_to_live_selector_to_execution_bridge_status"],
        "no_source_truth_to_execution_bridge_status": mission["no_source_truth_to_execution_bridge_status"],
        "no_adapter_sprint_to_execution_bridge_status": mission["no_adapter_sprint_to_execution_bridge_status"],
        "blunder_separation_status": mission["blunder_separation_status"],
        "dashboard_status": mission["dashboard_status"],
        "proof_paths": mission["proof_paths"],
        "remaining_operator_actions": [
            "Run explicit integration-mode keyless probes when operator permits live public calls.",
            "Approve a public sports schedule/status source before sports leaves replay/no-trade mode.",
            "Map settlement rules for unresolved Kalshi read-only market candidates.",
            "Keep premium/keyed sources optional upgrades, never global blockers.",
        ],
    }


def generate_all_v26_reports_for_tests(*, enable_network: bool = False) -> dict[str, dict[str, Any]]:
    reports = generate_v26_report_bundle(enable_network=enable_network)
    reports["final_report_v26.json"] = _build_final(reports)
    return reports


def _write_final_indexes(final: dict[str, Any], final_path: Path) -> None:
    final_index = dict(final)
    final_index["final_report_v26"] = str(final_path)
    final_index["v26"] = {
        "generated_at": final["generated_at"],
        "milestone": final["milestone"],
        "verdict": final["verdict"],
        "final_report_v26": str(final_path),
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


def main() -> dict[str, Any]:
    enable_network = os.environ.get("DUMMY_V26_ENABLE_NETWORK", "0") == "1"
    reports = generate_v26_report_bundle(enable_network=enable_network)
    paths = {name: _write_report(name, data) for name, data in reports.items()}

    final = _build_final(reports, paths)
    final_path = _write_report("final_report_v26.json", final)
    paths["final_report_v26.json"] = final_path
    _write_final_indexes(final, final_path)

    tests_summary = _load_report("tests_summary.json", {})
    tests_summary["v26_required_commands"] = _required_test_commands()
    tests_summary["v26_required_tests"] = _required_v26_tests()
    tests_summary["v26_required_reports"] = _v26_report_names(reports)
    tests_summary["v26_report_generated_at"] = final["generated_at"]
    tests_summary["v26_final_verdict"] = final["verdict"]
    tests_summary["v26_required_test_count"] = len(tests_summary["v26_required_tests"])
    tests_summary["v26_required_report_count"] = len(tests_summary["v26_required_reports"])
    _write_report("tests_summary.json", tests_summary)

    return final


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
