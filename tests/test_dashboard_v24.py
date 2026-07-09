from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.backend.main import app
from tests.v24_test_helpers import assert_current_test_report


def test_dashboard_v24_endpoints_return_open_source_state_without_secrets() -> None:
    assert_current_test_report(__file__)
    client = TestClient(app)
    endpoints = [
        "/api/v24/open-source-doctrine",
        "/api/v24/source-universe-reclassification",
        "/api/v24/keyless-public-expansion",
        "/api/v24/public-proxy-terrain",
        "/api/v24/nasdaq-open-proxy",
        "/api/v24/oil-open-proxy",
        "/api/v24/open-data-replay",
        "/api/v24/replay-calibration-v2",
        "/api/v24/open-source-baseline-lab",
        "/api/v24/keyless-live-forecast-expansion",
        "/api/v24/open-source-adapter-work-queue",
        "/api/v24/optional-premium-demotion",
        "/api/v24/source-truth-v6",
        "/api/v24/forecast-lifecycle-v3",
        "/api/v24/open-source-compounding-v8",
        "/api/v24/domain-scoreboard-v9",
        "/api/v24/mission-state",
    ]
    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200, response.text
        assert "BEGIN PRIVATE KEY" not in response.text
        assert "raw_prompt" not in response.text.lower()
        payload = response.json()
        assert payload["live_submit_disabled"] is True
        assert payload["caps_unchanged"] is True
