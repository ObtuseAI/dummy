from __future__ import annotations

import re
from typing import Any

import pytest

from predator_mesh import report_contract_registry
from predator_mesh import report_runtime


def _without_volatile(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_volatile(item)
            for key, item in value.items()
            if key not in {"generated_at", "artifact_path", "artifact_paths"}
        }
    if isinstance(value, list):
        return [_without_volatile(item) for item in value]
    return value


@pytest.mark.parametrize(
    "version,kwargs,final_name",
    [
        (106, {}, "final_report_v106.json"),
        (209, {}, "final_report_v209.json"),
        (266, {}, "final_report_v266.json"),
        (
            266,
            {
                "import_approval": {
                    "exact_phrase": (
                        "I approve Dummy to run one controlled production "
                        "pilot through LiveBrokerFirewall only, with no market "
                        "orders, strict caps, live-submit already "
                        "operator-enabled, per-order fail-closed checks, and "
                        "immediate pilot auto-lock"
                    ),
                    "operator": "operator:test",
                    "timestamp": "2026-07-25T00:00:00Z",
                    "reason": "one controlled pilot only",
                    "scope": "one_controlled_production_pilot_via_firewall_only",
                    "expiration": "2026-07-26T00:00:00Z",
                    "no_market_order_acknowledgment": "no market order",
                    "strict_caps_acknowledgment": "strict caps",
                    "live_submit_operator_enabled_acknowledgment": (
                        "live-submit already operator-enabled"
                    ),
                    "per_order_fail_closed_acknowledgment": (
                        "per-order fail-closed"
                    ),
                    "pilot_auto_lock_acknowledgment": "pilot auto-lock",
                },
                "live_submit_descriptor": True,
                "caps_descriptor": True,
                "firewall_descriptor": True,
            },
            "final_report_v266.json",
        ),
        (267, {}, "final_report_v267.json"),
        (268, {}, "final_report_v268.json"),
        (269, {}, "final_report_v269.json"),
        (271, {}, "final_report_v271.json"),
        (296, {}, "final_report_v296.json"),
        (299, {}, "final_report_v299.json"),
        (304, {}, "final_report_v304.json"),
    ],
)
def test_stable_build_preserves_versioned_artifact_contract(
    version: int, kwargs: dict[str, Any], final_name: str
) -> None:
    reports = report_runtime.generate_all_reports_for_tests(
        version, **kwargs
    )
    stage = report_runtime._stage(version)

    assert final_name == stage.FINAL_NAME
    assert set(stage.DEFAULT_REQUIRED_REPORT_NAMES).issubset(reports)
    assert reports[final_name]["milestone"] == stage._stable_runtime_milestone
    assert reports[final_name]["verification_commands"] == (
        stage.VERIFICATION_COMMANDS
    )
    for report in reports.values():
        assert report.get("approval_files_written", 0) == 0
        assert report.get("runtime_approvals_created_by_dummy", False) is False
        assert report.get("real_broker_contacted", False) is False


def test_runtime_rejects_removed_legacy_versions() -> None:
    with pytest.raises(report_runtime.ReportContractError):
        report_runtime.generate_report_bundle(105)


def test_registry_has_complete_integrity_checked_contract_coverage() -> None:
    assert report_contract_registry.PAYLOAD_SHA256 == (
        "cc34e30e64a26bfb36a855cbfd8b8f6c589a415da8ae8742ba62ba4024e7bc2b"
    )
    for version in range(106, 305):
        stage = report_contract_registry.load_contract(version)
        factory = report_contract_registry.factory_type(version)
        assert stage.MILESTONE
        assert callable(factory)


def test_registry_sources_cannot_import_version_packages() -> None:
    forbidden = {}
    for version, source in report_contract_registry._contract_sources().items():
        if re.search(
            r"(?:from|import)\s+predator_mesh\.v\d+(?:\.|\s|$)",
            source,
        ):
            forbidden[version] = True
    assert forbidden == {}


@pytest.mark.parametrize("version", range(106, 305))
def test_retained_default_contract_is_exact_and_fail_closed(
    version: int,
) -> None:
    stage = report_contract_registry.load_contract(version)
    reports = report_runtime.generate_report_bundle(version)

    assert set(reports) == set(stage.DEFAULT_REQUIRED_REPORT_NAMES)
    for report in reports.values():
        assert report.get("approval_files_written", 0) == 0
        assert report.get("runtime_approvals_created_by_dummy", False) is False
        assert report.get("real_broker_contacted", False) is False
        assert report.get("real_live_orders_submitted_count", 0) == 0
        assert report.get("scale_applied", False) is False
        assert report.get("autonomous_trading_enabled", False) is False
