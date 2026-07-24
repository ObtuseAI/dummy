"""Generate DUMMY V25 market-class generalization reports."""

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

from predator_mesh.v25 import MILESTONE
from predator_mesh.v25.reports import V25ReportFactory


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


def generate_v25_report_bundle(*, enable_network: bool = False) -> dict[str, dict[str, Any]]:
    return V25ReportFactory(enable_network=enable_network).build()


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
            ]
        ],
    ]


def _required_v25_tests() -> list[str]:
    tests_dir = ROOT / "tests"
    tests: list[str] = []
    for path in sorted(tests_dir.glob("test_*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "tests.v25_test_helpers" in text:
            tests.append(path.name)
    return tests


def _v25_report_names(reports: dict[str, dict[str, Any]] | None = None) -> list[str]:
    names = sorted((reports or generate_v25_report_bundle(enable_network=False)).keys())
    return ["final_report.json", "tests_summary.json", "final_report_v25.json", *names]


def _build_final(reports: dict[str, dict[str, Any]], paths: dict[str, Path] | None = None) -> dict[str, Any]:
    paths = paths or {}
    failures = sorted(name for name, data in reports.items() if data.get("verdict") == "FAIL")
    partials = sorted(name for name, data in reports.items() if data.get("verdict") == "PARTIAL")
    mission = reports["dummy_mission_state_report_v11.json"]
    final_v17 = _load_report("final_report_v17.json", {})
    final_v21 = _load_report("final_report_v21.json", {})
    final_v22 = _load_report("final_report_v22.json", {})
    final_v23 = _load_report("final_report_v23.json", {})
    final_v24 = _load_report("final_report_v24.json", {})
    final_verdict = "FAIL" if failures else "PARTIAL" if partials else "PASS"
    report_paths = {name: str(paths.get(name, ARTIFACTS / name)) for name in reports}
    return {
        "generated_at": now_iso(),
        "workstream": "V25: Market-Class Generalization Forecast Cadence Observer Loop and Source Truth Compounding",
        "milestone": MILESTONE,
        "verdict": final_verdict,
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "read_only_only": True,
        "secret_values_exposed": False,
        "partial_reason": "" if final_verdict == "PASS" else "Live forecasts remain unresolved/not due/source unavailable, live scored count is 0, some market classes remain replay-only or no-trade-only due source/settlement gaps, and replay samples include fixture-labeled cases.",
        "report_verdicts": {name: data.get("verdict") for name, data in reports.items()},
        "report_paths": report_paths,
        "failures": failures,
        "partials": partials,
        "v17_truth_loop_status": final_v17.get("verdict", mission["v17_truth_loop_status"]),
        "v21_source_activation_status": final_v21.get("verdict", mission["v21_source_activation_status"]),
        "v22_forecast_write_status": final_v22.get("forecast_write_breakthrough_status", mission["v22_forecast_write_status"]),
        "v23_observer_calibration_status": final_v23.get("v22_forecast_observer_closure_status", mission["v23_observer_calibration_status"]),
        "v24_open_source_public_data_status": final_v24.get("verdict", mission["v24_open_source_public_data_status"]),
        "live_submit_enabled": False,
        "live_submit_flag_status": "enabled=false",
        "caps_config_status": reports["no_caps_config_modification_report_v25.json"]["verdict"],
        "market_class_ontology_status": mission["market_class_ontology_status"],
        "market_class_registry_status": mission["market_class_registry_status"],
        "evidence_to_market_mapper_status": mission["evidence_to_market_mapper_status"],
        "settlement_mapping_status": mission["settlement_mapping_status"],
        "forecast_cadence_status": mission["forecast_cadence_status"],
        "forecast_cadence_counts": mission["forecast_cadence_counts"],
        "no_trade_quality_status": mission["no_trade_quality_status"],
        "live_observer_loop_status": mission["live_observer_loop_status"],
        "live_forecast_count": mission["live_forecast_count"],
        "live_unresolved_count": mission["live_unresolved_count"],
        "live_scored_count": mission["live_scored_count"],
        "market_class_scoring_status": mission["market_class_scoring_status"],
        "replay_factory_status": mission["replay_factory_status"],
        "replay_count": mission["replay_count"],
        "replay_scored_count": mission["replay_scored_count"],
        "calibration_v5_status": mission["calibration_v5_status"],
        "source_truth_v7_status": mission["source_truth_v7_status"],
        "approved_market_class_discovery_status": mission["approved_market_class_discovery_status"],
        "source_stack_builder_status": mission["source_stack_builder_status"],
        "forecast_ledger_status": mission["forecast_ledger_status"],
        "open_source_adapter_acceleration_status": mission["open_source_adapter_acceleration_status"],
        "compounding_v9_status": mission["compounding_v9_status"],
        "next_bundle_recommendation": mission["next_bundle_recommendation"],
        "market_class_scoreboard_v10_status": mission["market_class_scoreboard_v10_status"],
        "mission_state_verdict": mission["mission_state_verdict"],
        "no_secret_leak_status": reports["no_secret_leak_report_v25.json"]["verdict"],
        "no_source_api_key_leak_status": reports["no_source_api_key_leak_report_v25.json"]["verdict"],
        "no_github_token_leak_status": reports["no_github_token_leak_report_v25.json"]["verdict"],
        "no_kalshi_private_key_leak_status": reports["no_kalshi_private_key_leak_report_v25.json"]["verdict"],
        "no_direct_order_bypass_status": reports["no_direct_order_bypass_report_v25.json"]["verdict"],
        "no_direct_cancel_bypass_status": reports["no_direct_cancel_bypass_report_v25.json"]["verdict"],
        "no_unauthorized_source_status": reports["no_unauthorized_source_report_v25.json"]["verdict"],
        "no_questionable_odds_scraping_status": reports["no_questionable_odds_scraping_report_v25.json"]["verdict"],
        "no_unapproved_source_activation_status": reports["no_unapproved_source_activation_report_v25.json"]["verdict"],
        "no_commercial_source_without_approval_status": reports["no_commercial_source_without_approval_report_v25.json"]["verdict"],
        "no_premium_feed_required_global_blocker_status": reports["no_premium_feed_required_global_blocker_report_v25.json"]["verdict"],
        "no_fixture_claimed_real_status": reports["no_fixture_claimed_real_report_v25.json"]["verdict"],
        "no_replay_claimed_live_status": reports["no_replay_claimed_live_report_v25.json"]["verdict"],
        "no_replay_score_claimed_live_status": reports["no_replay_score_claimed_live_report_v25.json"]["verdict"],
        "no_proxy_claimed_exchange_native_status": reports["no_proxy_claimed_exchange_native_report_v25.json"]["verdict"],
        "no_context_claimed_edge_status": reports["no_context_claimed_edge_report_v25.json"]["verdict"],
        "no_example_market_canonical_center_status": reports["no_example_market_canonical_center_report_v25.json"]["verdict"],
        "no_outcome_fabrication_status": reports["no_outcome_fabrication_report_v25.json"]["verdict"],
        "no_forecast_cadence_to_execution_bridge_status": reports["no_forecast_cadence_to_execution_bridge_report_v25.json"]["verdict"],
        "no_observer_loop_to_execution_bridge_status": reports["no_observer_loop_to_execution_bridge_report_v25.json"]["verdict"],
        "no_market_class_scoring_to_execution_bridge_status": reports["no_market_class_scoring_to_execution_bridge_report_v25.json"]["verdict"],
        "no_calibration_to_execution_bridge_status": reports["no_calibration_to_execution_bridge_report_v25.json"]["verdict"],
        "no_source_truth_to_execution_bridge_status": reports["no_source_truth_to_execution_bridge_report_v25.json"]["verdict"],
        "no_adapter_acceleration_to_execution_bridge_status": reports["no_adapter_acceleration_to_execution_bridge_report_v25.json"]["verdict"],
        "blunder_separation_status": reports["blunder_separation_recheck_v25.json"]["verdict"],
        "dashboard_status": reports["dashboard_v25_report_v1.json"]["verdict"],
        "proof_paths": mission["proof_paths"],
        "remaining_operator_actions": [
            "Implement keyless public adapters for the highest-readiness market classes.",
            "Approve safe sports source usage before moving sports classes beyond fixture/replay lanes.",
            "Expand settlement templates before scoring unresolved live forecasts.",
            "Increase replay sample counts before granting live source accuracy credit.",
        ],
    }


def generate_all_v25_reports_for_tests(*, enable_network: bool = False) -> dict[str, dict[str, Any]]:
    reports = generate_v25_report_bundle(enable_network=enable_network)
    reports["final_report_v25.json"] = _build_final(reports)
    return reports


def _write_final_indexes(final: dict[str, Any], final_path: Path) -> None:
    final_index = dict(final)
    final_index["final_report_v25"] = str(final_path)
    final_index["v25"] = {
        "generated_at": final["generated_at"],
        "milestone": final["milestone"],
        "verdict": final["verdict"],
        "final_report_v25": str(final_path),
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
    enable_network = os.environ.get("DUMMY_V25_ENABLE_NETWORK", "0") == "1"
    reports = generate_v25_report_bundle(enable_network=enable_network)
    paths = {name: _write_report(name, data) for name, data in reports.items()}

    final = _build_final(reports, paths)
    final_path = _write_report("final_report_v25.json", final)
    paths["final_report_v25.json"] = final_path
    _write_final_indexes(final, final_path)

    tests_summary = _load_report("tests_summary.json", {})
    tests_summary["v25_required_commands"] = _required_test_commands()
    tests_summary["v25_required_tests"] = _required_v25_tests()
    tests_summary["v25_required_reports"] = _v25_report_names(reports)
    tests_summary["v25_report_generated_at"] = final["generated_at"]
    tests_summary["v25_final_verdict"] = final["verdict"]
    tests_summary["v25_required_test_count"] = len(tests_summary["v25_required_tests"])
    tests_summary["v25_required_report_count"] = len(tests_summary["v25_required_reports"])
    (ARTIFACTS / "tests_summary.json").write_text(json.dumps(tests_summary, indent=2, default=str), encoding="utf-8")

    print(json.dumps(final, indent=2, default=str))
    return final


if __name__ == "__main__":
    main()
