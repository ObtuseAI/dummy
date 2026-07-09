from __future__ import annotations

from tests.v13_test_helpers import FakeRealKalshiReadOnlyClient
from tests.v16_test_helpers import SECRET_KEY, valid_runtime_config


def test_client_factory_uses_runtime_config_and_reports_redacted_source() -> None:
    from predator_mesh.v16.runtime_config import KalshiReadOnlyClientFactory

    client = FakeRealKalshiReadOnlyClient()
    factory = KalshiReadOnlyClientFactory(valid_runtime_config(), client_factory=lambda _config: client)

    assert factory.build() is client
    report = factory.to_report()
    assert report["runtime_config_ready"] is True
    assert report["selected_source"] == "process_env"
    assert SECRET_KEY not in str(report)
