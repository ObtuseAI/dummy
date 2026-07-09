from __future__ import annotations

from predator_mesh.v13.credential_bridge import KalshiReadOnlyCredentialBridge
from predator_mesh.v15.credential_source_conflict_resolver import (
    KalshiCredentialSourceConflictResolver,
    KalshiCredentialSourcePriority,
)


def test_single_source_no_conflict(tmp_path) -> None:
    bridge = KalshiReadOnlyCredentialBridge(
        env={"KALSHI_API_KEY_ID": "abc", "KALSHI_API_PRIVATE_KEY_PEM": "x"},
        dummy_env_path=tmp_path / "no_dummy.env",
        project_env_path=tmp_path / "no_project.env",
    )
    resolution = KalshiCredentialSourceConflictResolver(bridge=bridge).resolve()
    assert resolution.has_conflict is False
    assert resolution.to_report()["verdict"] == "PASS"


def test_conflicting_sources_detected(tmp_path) -> None:
    dummy_env = tmp_path / "dummy.env"
    dummy_env.write_text("KALSHI_API_KEY_ID=dummyval\nKALSHI_API_PRIVATE_KEY_PEM_PATH=/tmp/x.pem\n", encoding="utf-8")
    bridge = KalshiReadOnlyCredentialBridge(
        env={"KALSHI_API_KEY_ID": "abc", "KALSHI_API_PRIVATE_KEY_PEM": "x"},
        dummy_env_path=dummy_env,
        project_env_path=tmp_path / "no_project.env",
    )
    resolution = KalshiCredentialSourceConflictResolver(bridge=bridge).resolve()
    assert resolution.has_conflict is True
    assert resolution.to_report()["verdict"] == "PARTIAL"


def test_priority_order_matches_bridge_precedence() -> None:
    order = [p.value for p in KalshiCredentialSourcePriority.ordered()]
    assert order == ["process_env", "dummy_env_file", "local_secret_file_reference", "missing"]


def test_no_secret_values_leak_in_report(tmp_path) -> None:
    bridge = KalshiReadOnlyCredentialBridge(
        env={"KALSHI_API_KEY_ID": "super-secret-key", "KALSHI_API_PRIVATE_KEY_PEM": "BEGIN PRIVATE KEY secret"},
        dummy_env_path=tmp_path / "no_dummy.env",
        project_env_path=tmp_path / "no_project.env",
    )
    report = KalshiCredentialSourceConflictResolver(bridge=bridge).to_report()
    text = str(report)
    assert "super-secret-key" not in text
    assert "BEGIN PRIVATE KEY secret" not in text
