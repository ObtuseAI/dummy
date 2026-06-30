import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock
from repo_harvester.classifier import classify_repo
from repo_harvester.auditor import audit_repo
from repo_harvester.manifest import MANDATORY_REPOS, REPOS_V2, ALL_REPOS_V2
from repo_harvester import runner
from core.ontology import RepoVerdict


def test_classify_rejects_bad_license():
    v, reasons = classify_repo({"license": None, "pushed_at": datetime.now(timezone.utc).isoformat()})
    assert v == RepoVerdict.REJECT_LICENSE


def test_classify_rejects_stale():
    old = (datetime.now(timezone.utc) - timedelta(days=800)).isoformat().replace("+00:00", "Z")
    v, reasons = classify_repo({"license": {"spdx_id": "MIT"}, "pushed_at": old})
    assert v == RepoVerdict.REJECT_STALE


def test_classify_reference_mine():
    recent = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    v, reasons = classify_repo({"license": {"spdx_id": "MIT"}, "pushed_at": recent})
    assert v == RepoVerdict.REFERENCE_MINE


def test_classify_rejects_sports_scraping_description():
    recent = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    meta = {
        "license": {"spdx_id": "MIT"},
        "pushed_at": recent,
        "description": "A tool for scraping bookmaker odds for arbitrage",
    }
    v, reasons = classify_repo(meta, category="sports_prediction_odds")
    assert v == RepoVerdict.REJECT_SCRAPING_RISK
    assert "scraping" in " ".join(reasons).lower() or "bookmaker" in " ".join(reasons).lower()


def test_classify_does_not_reject_nonsports_scraping_description():
    recent = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    meta = {
        "license": {"spdx_id": "MIT"},
        "pushed_at": recent,
        "description": "A tool for scraping bookmaker odds for arbitrage",
    }
    v, reasons = classify_repo(meta, category="prediction_market_native")
    assert v == RepoVerdict.REFERENCE_MINE


@pytest.mark.asyncio
async def test_audit_repo_mock():
    meta = {
        "html_url": "https://github.com/o/r",
        "license": {"spdx_id": "MIT"},
        "pushed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    with patch("repo_harvester.auditor.fetch_repo_metadata", new_callable=AsyncMock, return_value=meta):
        with patch("repo_harvester.auditor.fetch_languages", new_callable=AsyncMock, return_value={"Python": 100}):
            r = await audit_repo("o", "r", category="sports_prediction_odds")
            assert r["verdict"] == "REFERENCE_MINE"
            assert r["category"] == "sports_prediction_odds"


def test_mandatory_manifest_nonempty():
    assert len(MANDATORY_REPOS) >= 30


def test_v2_manifest_has_over_100_repos():
    assert len(ALL_REPOS_V2) > 100
    total_in_groups = sum(len(g["repos"]) for g in REPOS_V2)
    assert total_in_groups >= len(ALL_REPOS_V2)


def test_v2_all_repos_have_category():
    for owner, name, category in ALL_REPOS_V2:
        assert owner and name and category
        assert isinstance(category, str)


@pytest.mark.asyncio
async def test_runner_writes_v2_artifacts(tmp_path):
    """Run the V2 harvester with mocked GitHub clients; do not hit the live API."""
    recent = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    meta = {
        "html_url": "https://github.com/owner/repo",
        "license": {"spdx_id": "MIT"},
        "pushed_at": recent,
        "description": "A useful repo",
    }

    with patch("repo_harvester.runner.OUT", tmp_path):
        with patch("repo_harvester.auditor.fetch_repo_metadata", new_callable=AsyncMock, return_value=meta):
            with patch("repo_harvester.auditor.fetch_languages", new_callable=AsyncMock, return_value={"Python": 100}):
                results = await runner.run_harvester()

    assert len(results) == len(ALL_REPOS_V2)
    expected_files = [
        "repo_manifest_v2.json",
        "repo_classification_v2.json",
        "category_map_v2.json",
        "sports_repo_report.json",
        "weather_repo_report.json",
        "stocks_repo_report.json",
        "commodities_repo_report.json",
        "crypto_repo_report.json",
        "prediction_market_repo_report.json",
        "rejected_repo_report.json",
        "adapter_plan_v2.json",
        "firewall_bypass_scan_report.json",
    ]
    for filename in expected_files:
        assert (tmp_path / filename).exists(), f"missing artifact: {filename}"
