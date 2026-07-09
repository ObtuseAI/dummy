from __future__ import annotations

from tests.v13_test_helpers import FakeRealKalshiReadOnlyClient
from tests.v16_test_helpers import real_snapshot


def test_config_bound_snapshot_fetches_real_sanitized_nonempty_orderbook() -> None:
    client = FakeRealKalshiReadOnlyClient()
    result = real_snapshot(client)

    assert result.mode.value == "REAL_READ_ONLY"
    assert result.nonempty_proof.nonempty is True
    assert result.endpoint_proof.read_only_endpoints_only is True
    assert result.proof.order_endpoints_called == []
    assert result.proof.cancel_endpoints_called == []
