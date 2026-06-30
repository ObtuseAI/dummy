import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock
from repo_harvester.classifier import classify_repo
from repo_harvester.auditor import audit_repo
from repo_harvester.manifest import MANDATORY_REPOS
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

@pytest.mark.asyncio
async def test_audit_repo_mock():
    meta = {"html_url": "https://github.com/o/r", "license": {"spdx_id": "MIT"}, "pushed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
    with patch("repo_harvester.auditor.fetch_repo_metadata", new_callable=AsyncMock, return_value=meta):
        with patch("repo_harvester.auditor.fetch_languages", new_callable=AsyncMock, return_value={"Python": 100}):
            r = await audit_repo("o", "r")
            assert r["verdict"] == "REFERENCE_MINE"

def test_mandatory_manifest_nonempty():
    assert len(MANDATORY_REPOS) >= 30
