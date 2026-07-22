"""Regression tests for the audit Task 2 backend-honesty repairs."""

from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from dashboard.backend import main as backend
from dashboard.backend import operator_control_routes as control
from dashboard.backend import operator_routes


@pytest.mark.asyncio
async def test_markets_is_explicitly_configuration_only():
    result = await backend.markets()
    assert result["data_status"] == "configuration_only"
    assert result["live_market_snapshot_available"] is False
    assert result["source"] == "configs/caps.json + configs/allowlists.json"


@pytest.mark.asyncio
async def test_forecasts_reads_store_and_flags_constant_probability(tmp_path, monkeypatch):
    store = tmp_path / "data" / "calibration" / "forecasts.jsonl"
    store.parent.mkdir(parents=True)
    store.write_text(
        '\n'.join([
            json.dumps({
                "contract_ticker": "SPORTS-A",
                "dummy_probability": "0.55",
                "valuation_evidence": {"source": "legacy-private-field"},
            }),
            "not-json",
            "[]",
            json.dumps({"contract_ticker": "SPORTS-B", "dummy_probability": "0.55"}),
            json.dumps({"contract_ticker": "WEATHER-NYC-RAIN-YES", "dummy_probability": "0.90"}),
            json.dumps({"contract_ticker": "KXOIL-ABOVE-100", "dummy_probability": "0.10"}),
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(backend, "ROOT", tmp_path)

    result = await backend.forecasts(limit=10)

    assert result["count"] == 2
    assert result["stored_record_count"] == 4
    assert result["data_only_forecasts_excluded"] == 2
    assert all(
        not row["contract_ticker"].startswith(("WEATHER", "KXOIL"))
        for row in result["forecasts"]
    )
    assert result["skipped_malformed"] == 2
    assert result["data_status"] == "insufficient_probability_variation"
    assert result["freshness_counts"]["timestamp_missing"] == 2
    assert result["forecast_rows_are_actionable"] is False
    assert all("valuation_evidence_status" not in row for row in result["forecasts"])
    assert all("valuation_evidence" not in row for row in result["forecasts"])
    assert result["settlement_backed_performance_claim"] is False

    bounded = await backend.forecasts(limit=0)
    assert len(bounded["forecasts"]) == 1


@pytest.mark.asyncio
async def test_forecasts_missing_store_is_honest_501(tmp_path, monkeypatch):
    monkeypatch.setattr(backend, "ROOT", tmp_path)
    with pytest.raises(HTTPException) as exc:
        await backend.forecasts()
    assert exc.value.status_code == 501


@pytest.mark.asyncio
async def test_forecasts_excludes_unsupported_rows_and_their_private_metadata(
    tmp_path,
    monkeypatch,
):
    store = tmp_path / "data" / "calibration" / "forecasts.jsonl"
    store.parent.mkdir(parents=True)
    store.write_text(
        json.dumps({
            "contract_ticker": "KXTSLA-26JUL22-B350",
            "market_category": "Equities",
            "dummy_probability": "0.72",
            "valuation_evidence": {
                "influence_state": "active_in_fusion",
                "target_mapping_id": "caller-claimed-map",
                "source": "caller-claimed-source",
                "as_of": "2026-07-22T12:00:00+00:00",
                "received_at": "2026-07-22T12:01:00+00:00",
                "method_version": "caller-claimed-v1",
            },
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(backend, "ROOT", tmp_path)

    result = await backend.forecasts(limit=10)

    assert result["count"] == 0
    assert result["forecasts"] == []
    assert result["non_prediction_targets_excluded"] == 1
    assert "equity_index_forecasts_quarantined" not in result
    assert result["target_policy_counts"] == {"unsupported_target": 1}


@pytest.mark.parametrize(
    "caller_claim",
    [
        {"influence_state": "verified_current"},
        {"influence_state": "approved"},
        "verified",
    ],
)
@pytest.mark.asyncio
async def test_forecasts_never_echoes_removed_private_metadata(
    tmp_path,
    monkeypatch,
    caller_claim,
):
    store = tmp_path / "data" / "calibration" / "forecasts.jsonl"
    store.parent.mkdir(parents=True)
    store.write_text(
        json.dumps({
            "contract_ticker": "KXBAA-28JANDELIV-700",
            "market_category": "Companies",
            "dummy_probability": "0.72",
            "valuation_evidence": caller_claim,
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(backend, "ROOT", tmp_path)

    result = await backend.forecasts(limit=10)

    assert result["count"] == 0
    assert result["forecasts"] == []
    assert result["non_prediction_targets_excluded"] == 1


@pytest.mark.asyncio
async def test_strategies_reads_candidate_report(tmp_path, monkeypatch):
    report = tmp_path / "artifacts" / "repo_harvester" / "strategy_extraction_report_v1.json"
    report.parent.mkdir(parents=True)
    report.write_text(
        json.dumps({
            "candidate_count": 5,
            "candidates": [
                {
                    "strategy_name": "ObservedCandidate",
                    "market_types": ["sports"],
                    # Weather repositories may remain contextual data sources
                    # for a sports target.
                    "source_category": "weather_prediction_market",
                },
                {"strategy_name": "KalshiWeatherForecastStrategy", "market_types": ["weather"]},
                {"strategy_name": "CommoditiesEnergyStrategy", "market_types": ["commodities", "energy"]},
                {
                    "strategy_name": "StockMacroMomentumStrategy",
                    "market_types": ["stocks", "indices", "macro"],
                },
                {"strategy_name": "UnknownTargetCandidate"},
            ],
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(backend, "ROOT", tmp_path)

    result = await backend.strategies()

    assert result["candidate_count"] == 1
    assert result["repo_derived_candidates"][0]["strategy_name"] == "ObservedCandidate"
    assert result["reported_candidate_count"] == 5
    assert result["data_only_candidates_excluded"] == 2
    assert result["data_only_strategy_names"] == [
        "CommoditiesEnergyStrategy",
        "KalshiWeatherForecastStrategy",
    ]
    assert result["unknown_target_candidates_excluded"] == 1
    assert "quarantined_candidates_excluded" not in result
    assert "quarantined_strategy_names" not in result
    assert result["catalog_grants_prediction_authority"] is False
    assert result["catalog_grants_execution_authority"] is False
    assert result["data_status"] == (
        "governed_stored_report_filtered_by_target_policy"
    )


@pytest.mark.asyncio
async def test_incomplete_strategy_report_keeps_policy_counts_unknown(tmp_path, monkeypatch):
    report = tmp_path / "artifacts" / "repo_harvester" / "strategy_extraction_report_v1.json"
    report.parent.mkdir(parents=True)
    report.write_text(json.dumps({"candidate_count": 7}), encoding="utf-8")
    monkeypatch.setattr(backend, "ROOT", tmp_path)

    result = await backend.strategies()

    assert result["repo_derived_candidates"] is None
    assert result["candidate_count"] is None
    assert result["data_only_candidates_excluded"] is None
    assert result["data_only_strategy_names"] is None
    assert result["unknown_target_candidates_excluded"] is None
    assert "quarantined_candidates_excluded" not in result
    assert "quarantined_strategy_names" not in result
    assert result["data_status"] == "stored_report_incomplete"


@pytest.mark.asyncio
async def test_proof_and_logs_skip_malformed_files(tmp_path, monkeypatch):
    proof_dir = tmp_path / "proof"
    proof_dir.mkdir()
    payload = {"decision": "no_trade"}
    payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    (proof_dir / "p1.json").write_text(
        json.dumps({
            "ref_id": "p1",
            "timestamp": "2026-07-22T00:00:00+00:00",
            "component": "test",
            "verdict": "no_trade",
            "payload_hash": payload_hash,
            "payload": payload,
        }),
        encoding="utf-8",
    )
    (proof_dir / "bad.json").write_text("{", encoding="utf-8")
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "dummy.jsonl").write_text('{"event":"ok"}\nnot-json\n', encoding="utf-8")
    monkeypatch.setattr(backend, "ROOT", tmp_path)

    proof_result = await backend.proof()
    log_result = await backend.logs()

    assert proof_result["proof_count"] == 1
    assert proof_result["total_files"] == 2
    assert proof_result["invalid_count"] == 1
    assert proof_result["data_status"] == "blocked_partial_integrity_failure"
    assert proof_result["proof_authority_granted"] is False
    assert proof_result["proofs"][0]["ref_id"] == "p1"
    assert log_result["logs"] == [{"event": "ok"}]
    assert log_result["skipped_malformed"] == 1
    assert log_result["data_status"] == "stored_observations"


@pytest.mark.asyncio
async def test_status_exposure_comes_from_recorded_positions(monkeypatch):
    class FakePosition:
        def __init__(self, quantity, avg_price_cents):
            self.quantity = quantity
            self.avg_price_cents = avg_price_cents

        def model_dump(self, mode="json"):
            return {"quantity": self.quantity, "avg_price_cents": self.avg_price_cents}

    class FakeExposure:
        state_healthy = True
        persistence_error = None
        positions = {
            ("A", "yes"): FakePosition(2, 25),
            ("B", "yes"): FakePosition(3, 10),
        }
        open_orders = []

        def total_exposure_cents(self):
            return 80

    monkeypatch.setattr(backend, "get_persistent_exposure_tracker", lambda: FakeExposure())

    result = await backend.status()

    assert result["total_exposure_cents"] == 80
    assert result["open_positions"]


def test_operator_defaults_are_not_hardcoded_or_expired(monkeypatch):
    monkeypatch.delenv("DUMMY_OPERATOR_NAME", raising=False)
    monkeypatch.delenv("DUMMY_OPERATOR_EXPIRES_AT", raising=False)
    monkeypatch.setenv("DUMMY_OPERATOR_AUTHORITY_TTL_DAYS", "invalid")

    expiry = datetime.strptime(operator_routes._default_expires_at(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

    assert operator_routes._operator_name() == "operator"
    assert expiry > datetime.now(timezone.utc)


def test_operator_runner_has_bounded_timeout(monkeypatch):
    def timed_out(*args, **kwargs):
        assert kwargs["timeout"] == operator_routes.DEFAULT_TIMEOUT_SECONDS
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(operator_routes.subprocess, "run", timed_out)

    result = operator_routes._run(["status"])

    assert result["returncode"] == -1
    assert "TIMEOUT" in result["stderr"]


def test_operator_subprocess_results_redact_environment_secrets(monkeypatch):
    secret = "operator-secret-that-must-not-leak"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret)
    monkeypatch.setattr(
        operator_routes.subprocess,
        "run",
        lambda *args, **kwargs: type(
            "Proc",
            (),
            {
                "returncode": 0,
                "stdout": f"provider said {secret}",
                "stderr": f"diagnostic {secret}",
            },
        )(),
    )

    result = operator_routes._run(["status"])
    assert secret not in result["stdout"] + result["stderr"]
    assert "***REDACTED***" in result["stdout"] + result["stderr"]

    wrapped = control._result(
        ["status"],
        label="redaction-check",
        returncode=0,
        stdout=f"provider said {secret}",
        stderr=f"diagnostic {secret}",
    )
    assert secret not in wrapped["stdout"] + wrapped["stderr"]
    assert "***REDACTED***" in wrapped["stdout"] + wrapped["stderr"]


@pytest.mark.asyncio
async def test_missing_active_artifacts_are_unknown_not_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(backend, "ROOT", tmp_path)

    missing_logs = await backend.logs()
    harvester_status = await backend.repo_harvester_status()
    harvester_repos = await backend.repo_harvester_repos()
    harvester_reports = await backend.repo_harvester_reports()

    assert missing_logs["logs"] is None
    assert missing_logs["data_status"] == "unavailable"
    assert harvester_status["status"] is None
    assert harvester_repos["repos"] is None
    assert harvester_reports["reports"] is None
    assert all(
        item["data_status"] == "unavailable"
        for item in (harvester_status, harvester_repos, harvester_reports)
    )


@pytest.mark.asyncio
async def test_operator_control_status_collapses_concurrent_cache_misses(monkeypatch):
    calls = []

    async def fake_run(script, args, **kwargs):
        calls.append((script, tuple(args)))
        await asyncio.sleep(0)
        stdout = "risk utilization 87%\ncompletion: 42%" if args == ["status"] else "ok"
        return {"ok": True, "stdout": stdout, "stderr": "", "returncode": 0}

    monkeypatch.setattr(control, "_run_script_async", fake_run)
    monkeypatch.setattr(control, "_live_submit_state", lambda: {"enabled": False})
    monkeypatch.setattr(control, "_approvals_state", lambda: {"files": [], "count": 0})
    monkeypatch.setattr(control, "_load_real_proof_registry", lambda: None)
    control._status_cache.update(expires_at=0.0, payload=None)

    first, second = await asyncio.gather(control.status(), control.status())

    assert len(calls) == 3
    assert first is second
    assert first["completion_percent"] == 42


@pytest.mark.asyncio
async def test_operator_control_ignores_unlabeled_percentages(monkeypatch):
    async def fake_run(script, args, **kwargs):
        return {"ok": True, "stdout": "risk utilization 87%", "stderr": "", "returncode": 0}

    monkeypatch.setattr(control, "_run_script_async", fake_run)
    monkeypatch.setattr(control, "_live_submit_state", lambda: {"enabled": False})
    monkeypatch.setattr(control, "_approvals_state", lambda: {"files": [], "count": 0})
    monkeypatch.setattr(control, "_load_real_proof_registry", lambda: None)
    control._status_cache.update(expires_at=0.0, payload=None)

    result = await control.status()

    assert result["completion_percent"] is None
