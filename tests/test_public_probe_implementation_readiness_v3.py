from predator_mesh.v30.adapters import PublicProbeImplementationReadinessV3, build_default_v30_context
from tests.v30_test_helpers import assert_v30_report_named


def test_public_probe_implementation_readiness_v3_marks_ready_but_disabled_without_running_probes() -> None:
    readiness = PublicProbeImplementationReadinessV3().plan(build_default_v30_context())

    ready = [item for item in readiness["candidates"] if item["readiness_verdict"] == "READY_DISABLED_BY_DEFAULT"]
    assert len(ready) >= 3
    assert readiness["integration_mode_status"] == "DISABLED_BY_DEFAULT"
    assert readiness["public_probe_run_count"] == 0
    assert all(item["requires_secret"] is False for item in ready)
    assert all(item["method"] == "GET" for item in ready)
    assert all(item["live_execution_enabled"] is False for item in ready)


def test_public_probe_implementation_readiness_v3_report_contract() -> None:
    report = assert_v30_report_named(
        "public_probe_implementation_readiness_v3_report.json",
        "public_probe_readiness_status",
    )
    assert report["public_probe_readiness_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert report["public_probe_ready_count"] >= 3
    assert report["public_probe_run_count"] == 0
