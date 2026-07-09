from __future__ import annotations

from predator_mesh.v13.credential_bridge import KalshiCredentialSource, KalshiReadOnlyCredentialBridge
from tests.v13_test_helpers import write_dummy_env


def test_kalshi_credential_source_resolution_prefers_process_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KALSHI_API_KEY_ID", "process_key_should_not_leak")
    monkeypatch.setenv("KALSHI_API_PRIVATE_KEY_PEM", "process_pem_should_not_leak")
    dummy_env = write_dummy_env(tmp_path / "dummy.env")

    bridge = KalshiReadOnlyCredentialBridge(
        env=None,
        dummy_env_path=dummy_env,
        project_env_path=tmp_path / "missing.env",
    )

    report = bridge.source_resolution_report()
    assert report["source"] == KalshiCredentialSource.PROCESS_ENV.value
    assert report["ready"] is True
    assert report["searched_sources"] == [
        "process_env",
        "dummy_env_file",
        "local_secret_file_reference",
        "missing",
    ]
