from __future__ import annotations

import json

from tests.v13_test_helpers import SECRET_KEY, SECRET_PEM, ready_bridge


def test_kalshi_readonly_credential_bridge_reads_dummy_env_without_exposing_values(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("KALSHI_API_KEY_ID", raising=False)
    monkeypatch.delenv("KALSHI_API_PRIVATE_KEY_PEM", raising=False)
    bridge = ready_bridge(tmp_path)

    readiness = bridge.resolve()
    payload = json.dumps(readiness.to_dict())

    assert readiness.ready is True
    assert readiness.source.value == "dummy_env_file"
    assert SECRET_KEY not in payload
    assert SECRET_PEM not in payload
    assert readiness.redacted is True
