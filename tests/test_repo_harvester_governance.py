from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest

from core.ontology import RepoVerdict
from repo_harvester import runner, v2_digestion
from repo_harvester.adapter_planner import generate_adapter_plan_v3
from repo_harvester.adapter_test_generator import write_adapter_test_report
from repo_harvester.incorporation_engine import get_allowed_adapter_names
from repo_harvester.incorporation_registry import load_registry, save_registry
from repo_harvester.promotion_engine import (
    build_promotion_records,
    update_incorporation_registry,
)
from repo_harvester.retry_policy import (
    HarvestRetryExhausted,
    PENDING_RETRY,
    run_with_bounded_retry,
)
from repo_harvester.strategy_catalog import (
    relabel_legacy_report,
    sanitize_strategy_extraction_report,
)


async def _no_sleep(_: float) -> None:
    return None


def _complete_scan(**overrides):
    scan = {
        "files_scanned": 2,
        "files_considered": 2,
        "tree_size": 2,
        "scan_complete": True,
        "harvest_status": "COMPLETE",
        "direct_order_hits": [],
        "kalshi_order_hits": [],
        "polymarket_order_hits": [],
        "private_key_hits": [],
        "api_secret_hits": [],
        "secret_hits": [],
        "strategy_hits": ["strategy.py"],
        "forecast_hits": ["forecast.py"],
        "risk_hits": [],
        "arbitrage_hits": [],
        "websocket_hits": [],
        "settlement_hits": [],
        "dashboard_hits": [],
        "sports_hits": [],
        "weather_hits": [],
        "stocks_hits": [],
        "commodities_hits": [],
        "crypto_hits": [],
    }
    scan.update(overrides)
    return scan


@pytest.mark.asyncio
async def test_bounded_retry_recovers_from_transient_failures() -> None:
    calls = 0

    async def operation():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise httpx.ReadTimeout("temporary upstream timeout")
        return {"ok": True}

    result = await run_with_bounded_retry(operation, sleep=_no_sleep)
    assert result == {"ok": True}
    assert calls == 3


@pytest.mark.asyncio
async def test_runner_exhausted_transient_failure_remains_pending(monkeypatch) -> None:
    calls = 0

    async def always_timeout(*args, **kwargs):
        del args, kwargs
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("temporary upstream timeout")

    async def fast_retry(operation):
        return await run_with_bounded_retry(operation, sleep=_no_sleep)

    monkeypatch.setattr(runner, "audit_repo", always_timeout)
    monkeypatch.setattr(runner, "run_with_bounded_retry", fast_retry)

    result = await runner._audit_one("owner", "repo", "sports_prediction_odds")

    assert calls == 3
    assert result["verdict"] == PENDING_RETRY
    assert result["retryable"] is True
    assert result["retry_attempts"] == 3
    assert not result["verdict"].startswith("REJECT")


@pytest.mark.asyncio
async def test_runner_permanent_failure_is_not_retried(monkeypatch) -> None:
    calls = 0

    async def broken(*args, **kwargs):
        del args, kwargs
        nonlocal calls
        calls += 1
        raise ValueError("malformed repository metadata")

    monkeypatch.setattr(runner, "audit_repo", broken)
    result = await runner._audit_one("owner", "repo", "sports_prediction_odds")

    assert calls == 1
    assert result["verdict"] == RepoVerdict.REJECT_BROKEN.value
    assert result["retryable"] is False


@pytest.mark.asyncio
async def test_github_get_retries_503_then_succeeds(monkeypatch) -> None:
    calls = 0

    class Client:
        async def get(self, url, **kwargs):
            del kwargs
            nonlocal calls
            calls += 1
            request = httpx.Request("GET", url)
            if calls < 3:
                return httpx.Response(503, request=request, json={"message": "busy"})
            return httpx.Response(200, request=request, json={"name": "repo"})

    async def fast_retry(operation):
        return await run_with_bounded_retry(operation, sleep=_no_sleep)

    monkeypatch.setattr(v2_digestion, "run_with_bounded_retry", fast_retry)
    result = await v2_digestion._github_get(Client(), "https://api.github.test/repos/x/y")

    assert result == {"name": "repo"}
    assert calls == 3


@pytest.mark.asyncio
async def test_transient_scan_failure_is_not_cached_as_repository_truth(tmp_path, monkeypatch) -> None:
    async def unavailable(*args, **kwargs):
        del args, kwargs
        cause = httpx.ReadTimeout("temporary upstream timeout")
        raise HarvestRetryExhausted(cause, 3)

    monkeypatch.setattr(v2_digestion, "CACHE", tmp_path)
    monkeypatch.setattr(v2_digestion, "fetch_repo_metadata", unavailable)

    result = await v2_digestion._scan_one_repo(
        object(), "owner", "repo", "sports_prediction_odds"
    )

    assert result["harvest_status"] == PENDING_RETRY
    assert result["scan_complete"] is False
    assert result["retryable"] is True
    assert not list(tmp_path.glob("*.json"))


def test_incomplete_source_scan_never_generates_adapter_plan() -> None:
    plan = generate_adapter_plan_v3(
        {
            "owner": "x",
            "name": "y",
            "license": "MIT",
            "pushed_at": datetime.now(timezone.utc).isoformat(),
            "description": "",
        },
        _complete_scan(
            scan_complete=False,
            harvest_status=PENDING_RETRY,
            error="temporary timeout",
        ),
        category="sports_prediction_odds",
    )

    assert plan["verdict"] == PENDING_RETRY
    assert plan["plans"] == []


def test_model_zoo_is_dependency_candidate_not_fake_adapter() -> None:
    plan = generate_adapter_plan_v3(
        {
            "owner": "models",
            "name": "zoo",
            "license": "MIT",
            "pushed_at": datetime.now(timezone.utc).isoformat(),
            "description": "general forecasting library",
        },
        _complete_scan(),
        category="universal_ml_forecasting_optimization",
    )

    assert plan["verdict"] == RepoVerdict.DIRECT_DEPENDENCY_CANDIDATE.value
    assert plan["plans"][0]["production_capability"] is False
    assert plan["plans"][0]["emits_native_types"] is False


def test_sync_demotes_legacy_boolean_claim_to_pending() -> None:
    save_registry({
        "incorporated": [{
            "repo": "models/zoo",
            "adapter_name": "zoo_adapter",
            "tests_passed": True,
        }],
        "rejected": [],
        "pending_tests": [],
    })
    records = {
        "adapter_targets": [{
            "repo": "models/zoo",
            "adapter_name": "zoo_adapter",
            "category": "universal_ml_forecasting_optimization",
            "data_only": False,
            "passthrough_model_zoo": True,
        }],
        "direct_dependency_candidates": [],
        "reference_only_strategy_mines": [],
    }

    update_incorporation_registry(records)
    registry = load_registry()

    assert registry["incorporated"] == []
    assert registry["verified_integration_count"] == 0
    assert registry["pending_tests"][0]["adapter_name"] == "zoo_adapter"
    assert registry["pending_tests"][0]["production_capability"] is False
    assert registry["pending_tests"][0]["passthrough_model_zoo"] is True
    assert "zoo_adapter" not in get_allowed_adapter_names()


def test_current_generated_records_declare_zero_authority() -> None:
    records = build_promotion_records()["adapter_targets"]
    assert records
    assert all(record["tests_passed"] is False for record in records)
    assert all(record["production_capability"] is False for record in records)
    assert all(record["prediction_authority"] is False for record in records)
    assert all(record["execution_authority"] is False for record in records)


def test_structural_test_report_cannot_claim_production_capability(tmp_path) -> None:
    path = write_adapter_test_report(350, 0, 0, path=tmp_path / "report.json")
    report = json.loads(path.read_text())

    assert report["result"]["overall"] == "STRUCTURAL_PASS_CAPABILITY_UNVERIFIED"
    assert report["adapter_specific_upstream_tests_passed"] is False
    assert report["production_capability"] is False
    assert report["prediction_authority"] is False
    assert report["execution_authority"] is False
    assert report["incorporation_authority"] is False


def test_weather_and_commodities_create_data_inputs_not_strategies() -> None:
    plans = [
        {
            "repo": "weather/source",
            "category": "weather_prediction_market",
            "verdict": RepoVerdict.ADAPTER_TARGET.value,
            "scan_summary": _complete_scan(weather_hits=["weather.py"]),
        },
        {
            "repo": "commodity/source",
            "category": "commodities_energy_agriculture",
            "verdict": RepoVerdict.ADAPTER_TARGET.value,
            "scan_summary": _complete_scan(commodities_hits=["commodity.py"]),
        },
    ]

    report = v2_digestion.build_strategy_extraction_report(plans)

    assert report["candidate_count"] == 0
    assert report["data_only_input_count"] == 2
    assert all(item["prediction_authority"] is False for item in report["data_only_inputs"])
    assert all(item["trade_proposal_authority"] is False for item in report["data_only_inputs"])


def test_stock_candidates_are_excluded_as_unsupported_targets() -> None:
    plans = [{
        "repo": "equity/source",
        "category": "finance_and_trading",
        "verdict": RepoVerdict.ADAPTER_TARGET.value,
        "scan_summary": _complete_scan(
            stocks_hits=["stocks.py"],
            strategy_hits=[],
            forecast_hits=[],
        ),
    }]

    report = v2_digestion.build_strategy_extraction_report(plans)

    assert report["candidate_count"] == 0
    assert report["quarantined_candidate_count"] == 1
    candidate = report["quarantined_candidates"][0]
    assert candidate["strategy_name"] == "StockMacroMomentumStrategy"
    assert candidate["output"] == "ABSTAIN"
    assert candidate["prediction_authority"] is False
    assert candidate["trade_proposal_authority"] is False
    assert candidate["quarantine_reason"] == "outside_supported_prediction_targets"


def test_stale_strategy_report_is_sanitized_without_granting_authority() -> None:
    report = sanitize_strategy_extraction_report({
        "candidate_count": 3,
        "candidates": [
            {
                "strategy_name": "SportsCandidate",
                "market_types": ["sports"],
                "prediction_authority": True,
                "execution_authority": True,
            },
            {
                "strategy_name": "StockMacroMomentumStrategy",
                "market_types": ["stocks", "indices"],
                "valuation_evidence": {"influence_state": "active_in_fusion"},
            },
            {"strategy_name": "UnknownTarget"},
        ],
    })

    assert report["schema_version"] == 3
    # Unlabelled legacy rows are keyword-template fan-out, never extractions.
    assert report["candidate_count"] == 0
    assert report["candidates"] == []
    assert report["repo_derived_candidate_count"] == 0
    assert report["keyword_template_inventory_count"] == 1
    template = report["keyword_template_inventory"][0]
    assert template["strategy_name"] == "SportsCandidate"
    assert template["derivation"] == "keyword_template_not_repo_derived"
    assert template["repo_derived_logic"] is False
    assert template["output"] == "ABSTAIN"
    assert template["prediction_authority"] is False
    assert template["execution_authority"] is False
    assert report["quarantined_candidate_count"] == 1
    assert report["quarantined_candidates"][0]["output"] == "ABSTAIN"
    assert report["unknown_target_excluded_count"] == 1
    assert report["catalog_grants_prediction_authority"] is False
    assert report["catalog_grants_execution_authority"] is False


# --- Wave-84: keyword-template fan-out must not be counted as extraction ----


def _template_plans() -> list[dict]:
    return [
        {
            "repo": "sports/source",
            "category": "sports_prediction_odds",
            "verdict": RepoVerdict.ADAPTER_TARGET.value,
            "scan_summary": _complete_scan(sports_hits=["odds.py"]),
        },
        {
            "repo": "crypto/source",
            "category": "crypto_event_markets",
            "verdict": RepoVerdict.ADAPTER_TARGET.value,
            "scan_summary": _complete_scan(
                crypto_hits=["btc.py"],
                arbitrage_hits=["arb.py"],
                websocket_hits=["ws.py"],
            ),
        },
    ]


def test_keyword_templates_are_not_counted_as_extracted_candidates() -> None:
    report = v2_digestion.build_strategy_extraction_report(_template_plans())

    # The headline count is repo-derived extractions only, and there is no
    # extraction path, so it is 0 while the inventory is non-empty.
    assert report["candidate_count"] == 0
    assert report["candidates"] == []
    assert report["repo_derived_candidate_count"] == 0
    assert report["keyword_template_inventory_count"] > 0
    assert report["inventory_only"] is True
    assert report["repo_derived_extraction_implemented"] is False
    assert report["extraction_method"] == "manifest_keyword_counter_fan_out"
    assert report["schema_version"] == 2


def test_every_inventory_row_declares_template_provenance() -> None:
    report = v2_digestion.build_strategy_extraction_report(_template_plans())
    rows = report["keyword_template_inventory"]

    assert rows
    for row in rows:
        assert row["derivation"] == "keyword_template_not_repo_derived"
        assert row["repo_derived_logic"] is False
        assert row["description_is_canned_template"] is True
        assert row["keyword_trigger"]
        assert row["output"] == "ABSTAIN"
        assert row["prediction_authority"] is False
        assert row["trade_proposal_authority"] is False
        assert row["execution_authority"] is False
        assert row["calls_live_order_endpoints"] is False
    # The row still records which repo tripped which counter: inventory kept.
    assert {row["repo"] for row in rows} == {"sports/source", "crypto/source"}
    triggers = {row["keyword_trigger"] for row in rows}
    assert "sports_hits" in triggers


def test_fresh_report_survives_the_sanitizer_without_regaining_a_count() -> None:
    report = v2_digestion.build_strategy_extraction_report(_template_plans())
    governed = sanitize_strategy_extraction_report(report)

    assert governed["candidate_count"] == 0
    assert governed["candidates"] == []
    assert governed["keyword_template_inventory_count"] == report[
        "keyword_template_inventory_count"
    ]
    assert all(
        row["prediction_authority"] is False
        for row in governed["keyword_template_inventory"]
    )


def test_labelled_repo_derived_row_is_the_only_thing_that_counts() -> None:
    governed = sanitize_strategy_extraction_report({
        "candidate_count": 2,
        "candidates": [
            {
                "strategy_name": "RealExtraction",
                "market_types": ["sports"],
                "repo_derived_logic": True,
            },
            {"strategy_name": "TemplateRow", "market_types": ["sports"]},
        ],
    })

    assert governed["candidate_count"] == 1
    assert governed["candidates"][0]["strategy_name"] == "RealExtraction"
    assert governed["candidates"][0]["prediction_authority"] is False
    assert governed["keyword_template_inventory_count"] == 1


def test_legacy_report_relabel_deflates_the_headline_without_dropping_rows() -> None:
    legacy = {
        "generated_at": "2026-06-30T19:02:07.981039+00:00",
        "candidate_count": 3,
        "candidates": [
            {"strategy_name": "SportsMomentumStrategy", "market_types": ["sports"]},
            {"strategy_name": "CryptoEventMarketStrategy", "market_types": ["crypto"]},
            {
                "strategy_name": "StockMacroMomentumStrategy",
                "market_types": ["stocks"],
            },
        ],
    }

    relabelled = relabel_legacy_report(legacy)

    assert relabelled["candidate_count"] == 0
    assert relabelled["reported_candidate_count_before_relabel"] == 3
    assert relabelled["keyword_template_inventory_count"] == 2
    assert relabelled["quarantined_candidate_count"] == 1
    assert relabelled["relabelled_without_rescan"] is True
    assert relabelled["generated_at"] == legacy["generated_at"]
    # No row is lost by the relabel.
    total = (
        relabelled["keyword_template_inventory_count"]
        + relabelled["quarantined_candidate_count"]
        + relabelled["data_only_input_count"]
        + relabelled["unknown_target_excluded_count"]
    )
    assert total == len(legacy["candidates"])


def test_registry_states_incorporation_status_in_plain_words() -> None:
    save_registry({
        "incorporated": [],
        "rejected": [],
        "pending_tests": [
            {"adapter_name": "a_adapter"},
            {"adapter_name": "b_adapter"},
        ],
    })

    registry = load_registry()

    assert registry["verified_integration_count"] == 0
    assert registry["pending_adapter_count"] == 2
    assert registry["incorporation_summary"].startswith(
        "0 of 2 planned adapters are incorporated"
    )
    assert "pending adapter-specific upstream verification" in (
        registry["incorporation_summary"]
    )
