from __future__ import annotations

import json
import socket
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from archive.routes import v8_routes
from dashboard.backend.operator_auth import require_operator
from model_router.config import ProviderConfig
from model_router.providers import BaseModelProvider
from model_router.smoke import LiveModelSmoke, LiveModelSmokeV2, LiveModelSmokeV3
from model_router.tasks import ModelTask


class _ExternalProviderDouble(BaseModelProvider):
    name = "external_provider_double"

    def __init__(self) -> None:
        super().__init__(
            ProviderConfig(api_base="https://example.invalid", api_key_env="X", model_name="x")
        )
        self.call_count = 0

    async def _call_api(self, prompt, task, max_tokens, temperature):
        self.call_count += 1
        raise AssertionError("external provider call was not authorized")


@pytest.mark.asyncio
@pytest.mark.parametrize("runner_type", [LiveModelSmoke, LiveModelSmokeV2, LiveModelSmokeV3])
async def test_legacy_smoke_defaults_to_zero_network_with_credentials_present(
    runner_type,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "present-but-must-not-be-used")
    monkeypatch.setenv("MINIMAX_API_KEY", "present-but-must-not-be-used")
    runner = runner_type(artifacts_dir=tmp_path)

    monkeypatch.setattr(
        runner,
        "_build_provider",
        Mock(side_effect=AssertionError("provider construction was not authorized")),
    )
    if hasattr(runner, "_build_resolved_provider"):
        monkeypatch.setattr(
            runner,
            "_build_resolved_provider",
            Mock(side_effect=AssertionError("resolved provider construction was not authorized")),
        )
    if hasattr(runner, "resolver"):
        monkeypatch.setattr(
            runner.resolver,
            "resolve",
            AsyncMock(side_effect=AssertionError("model resolution network was not authorized")),
        )

    report = await runner.run()

    assert report["live_model_status"] == "MOCK_ONLY"
    assert report["live_contact_authorized"] is False
    assert report["contact_mode"] == "PREFLIGHT_ONLY"


@pytest.mark.asyncio
async def test_low_level_legacy_execute_call_is_also_gated_without_opt_in(tmp_path):
    runner = LiveModelSmoke(artifacts_dir=tmp_path)
    external = _ExternalProviderDouble()

    result = await runner._execute_call(
        external,
        runner.deepseek_prompt,
        ModelTask.MARKET_THESIS,
        prompt_summary="zero-network gate test",
    )

    assert external.call_count == 0
    assert result.provider == "mock"
    assert result.response_schema_ok is True


def test_every_v8_archive_get_is_read_only_and_zero_network(monkeypatch, tmp_path):
    artifacts = tmp_path / "artifacts"
    configs = tmp_path / "configs"
    artifacts.mkdir()
    configs.mkdir()
    (artifacts / "real_market_forecast_loop_report_v2.json").write_text(
        json.dumps({"markets": [{"market_ticker": "MKT"}], "opinions": [{"id": "one"}]}),
        encoding="utf-8",
    )
    (artifacts / "strategy_governor_report_v1.json").write_text(
        json.dumps({"decision_count": 1, "decisions": [{"decision": "NO_TRADE"}]}),
        encoding="utf-8",
    )
    (artifacts / "strategy_governor_decision_manifest_v1.json").write_text(
        json.dumps({"decision_count": 1}),
        encoding="utf-8",
    )
    before = {path: path.read_bytes() for path in artifacts.iterdir()}

    monkeypatch.setattr(v8_routes, "ARTIFACTS", artifacts)
    monkeypatch.setattr(v8_routes, "CONFIGS", configs)

    network_attempts: list[object] = []
    write_attempts: list[Path] = []
    original_socket_connect = socket.socket.connect

    def _block_socket_connect(sock, address):
        # Starlette/AnyIO uses a loopback socket pair to run the in-process
        # TestClient on Windows.  That is test plumbing, not provider contact.
        if isinstance(address, tuple) and address and address[0] in {"127.0.0.1", "::1"}:
            return original_socket_connect(sock, address)
        network_attempts.append(address)
        raise AssertionError(f"archive GET attempted network contact: {address!r}")

    def _block_write_text(path, *args, **kwargs):
        write_attempts.append(path)
        raise AssertionError(f"archive GET attempted a file write: {path}")

    monkeypatch.setattr(socket.socket, "connect", _block_socket_connect)
    monkeypatch.setattr(Path, "write_text", _block_write_text)

    app = FastAPI()
    app.include_router(v8_routes.router)

    async def _archive_test_operator():
        return {"operator": "archive-test"}

    app.dependency_overrides[require_operator] = _archive_test_operator
    client = TestClient(app)
    paths = (
        "/v8/status",
        "/v8/model-providers",
        "/v8/live-smoke",
        "/v8/prompt-firewall",
        "/v8/output-firewall",
        "/v8/forecast-opinions",
        "/v8/calibration",
        "/v8/strategy-governor",
        "/v8/disagreement",
        "/v8/firewall-rehearsal",
        "/v8/proof-reports",
    )

    responses = {path: client.get(path) for path in paths}

    assert all(response.status_code == 200 for response in responses.values())
    assert responses["/v8/live-smoke"].json()["contact_mode"] == "PREFLIGHT_ONLY"
    assert responses["/v8/live-smoke"].json()["legacy_smoke_status"] == "RETIRED_LEGACY_SMOKE"
    assert responses["/v8/live-smoke"].json()["network_contacted"] is False
    assert responses["/v8/forecast-opinions"].json()["mode"] == "STORED_ARTIFACT_ONLY"
    assert responses["/v8/disagreement"].json()["review_executed"] is False
    assert responses["/v8/firewall-rehearsal"].json()["rehearsal_executed"] is False
    assert network_attempts == []
    assert write_attempts == []
    assert {path: path.read_bytes() for path in artifacts.iterdir()} == before


def test_v8_archive_route_module_has_no_provider_or_execution_engines():
    source = Path(v8_routes.__file__).read_text(encoding="utf-8")
    forbidden = (
        "RealMarketForecastLoopV2",
        "HybridDisagreementEngineV2",
        "HybridLiveCapRehearsalV2",
        "LiveModelSmoke",
        "create_order",
        "generate_strategy_governor_reports",
    )

    assert all(name not in source for name in forbidden)
