from __future__ import annotations

from fastapi.testclient import TestClient

from autonomy.dashboard import build_app
from repo_harvester.incorporation_registry import (
    dashboard_registry_payload,
    load_registry,
)
from repo_harvester.promotion_engine import (
    ARTIFACTS,
    DUMMY_ARTIFACTS,
    REPO_ROOT,
    build_promotion_records,
    update_incorporation_registry,
)
from strategies.registry import strategy_catalog_payload


def test_strategy_catalog_states_research_and_authority_truth():
    payload = strategy_catalog_payload()

    assert payload["strategy_count"] == 9
    assert payload["research_only_count"] == 6
    assert payload["dormant_count"] == 3
    assert payload["execution_authority_count"] == 0
    assert all(
        row["lifecycle_status"] in {"RESEARCH_ONLY", "DORMANT"}
        for row in payload["strategies"]
    )
    assert all(row["execution_authority"] is False for row in payload["strategies"])


def test_harvester_paths_are_checkout_relative():
    assert ARTIFACTS == REPO_ROOT / "artifacts" / "repo_harvester"
    assert DUMMY_ARTIFACTS == REPO_ROOT / "artifacts" / "dummy"
    assert "C:/src/engine/dummy" not in str(ARTIFACTS).replace("\\", "/")


def test_every_current_adapter_target_is_dormant_and_dashboard_visible():
    records = build_promotion_records()
    adapter_targets = records["adapter_targets"]
    assert adapter_targets
    assert all(row["lifecycle_status"] == "DORMANT" for row in adapter_targets)
    assert all(row["integration_status"] == "DORMANT" for row in adapter_targets)
    assert all(row["challenger_graded"] is False for row in adapter_targets)
    assert all(row["prediction_authority"] is False for row in adapter_targets)
    assert all(row["execution_authority"] is False for row in adapter_targets)

    update_incorporation_registry(records)
    registry = load_registry()
    assert registry["registry_status"] == "DORMANT_UNVERIFIED"
    assert registry["dormant_adapter_count"] == len(adapter_targets)
    assert registry["verified_integration_count"] == 0

    payload = dashboard_registry_payload()
    assert payload["inventory_count"] == len(adapter_targets)
    assert payload["dormant_adapter_count"] == len(adapter_targets)
    assert payload["verified_challenger_count"] == 0
    assert payload["all_unverified_adapters_dormant"] is True
    assert payload["authority"] == {"prediction": False, "execution": False}

    with TestClient(build_app(), client=("127.0.0.1", 50000)) as client:
        response = client.get(
            "/api/repo-harvester",
            headers={"Host": "127.0.0.1:8787"},
        )
        strategy_response = client.get(
            "/api/strategy-catalog",
            headers={"Host": "127.0.0.1:8787"},
        )

    assert response.status_code == 200
    assert response.json()["dormant_adapter_count"] == len(adapter_targets)
    assert strategy_response.status_code == 200
    assert strategy_response.json()["execution_authority_count"] == 0
