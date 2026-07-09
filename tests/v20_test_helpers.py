from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


def assert_pass_or_partial(report: dict) -> None:
    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report.get("secret_values_exposed") is False


def assert_report_shape(report: dict, *required_keys: str) -> None:
    assert_pass_or_partial(report)
    for key in required_keys:
        assert key in report


def assert_no_execution_or_secrets(report: dict) -> None:
    text = json.dumps(report, default=str)
    assert "BEGIN PRIVATE KEY" not in text
    assert "raw_prompt" not in text.lower()
    assert "github_pat_" not in text
    assert "ghp_" not in text
    assert report.get("secret_values_exposed") is False


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_source_candidate(candidate: dict) -> None:
    required = {
        "source_id",
        "name",
        "tier",
        "domains",
        "source_class",
        "legality_class",
        "approval_status",
        "license_status",
        "cost_class",
        "latency_class",
        "freshness_class",
        "expected_edge_class",
        "adapter_plan",
        "fallback_mode",
        "activation_risk",
        "proof_refs",
    }
    assert required <= set(candidate)
    assert candidate["adapter_plan"]["activation_authority"] == "READ_ONLY_ONLY"
    assert candidate["adapter_plan"]["live_execution_enabled"] is False


def assert_required_report_exists(artifact_dir: Path, name: str) -> dict:
    path = artifact_dir / name
    assert path.exists(), name
    return load_json(path)


@lru_cache(maxsize=1)
def v20_bundle() -> dict[str, dict]:
    from scripts.generate_v20_reports import generate_v20_report_bundle

    return generate_v20_report_bundle()


def assert_v20_report(report_name: str, *required_keys: str) -> dict:
    report = v20_bundle()[report_name]
    assert_report_shape(report, *required_keys)
    assert_no_execution_or_secrets(report)
    return report


def assert_security_report(factory_name: str) -> dict:
    import scripts.generate_v20_reports as generator

    report = getattr(generator, factory_name)()
    assert report["verdict"] == "PASS"
    assert_no_execution_or_secrets(report)
    return report
