from repo_harvester.source_scanner import scan_text, DIRECT_ORDER_PATTERNS, SECRET_PATTERNS
from repo_harvester.adapter_planner import generate_adapter_plan
from core.ontology import RepoVerdict

def test_scan_detects_direct_order():
    text = "def submit():\n    client.create_order(ticker, side, price)\n"
    assert scan_text(text, DIRECT_ORDER_PATTERNS)

def test_scan_detects_secret():
    text = "API_KEY = 'abc123'\n"
    assert scan_text(text, SECRET_PATTERNS)

def test_adapter_plan_rejects_direct_order():
    plan = generate_adapter_plan(
        {"owner": "x", "name": "y", "license": "MIT"},
        {"direct_order_hits": ["a.py"], "secret_hits": [], "strategy_hits": [], "forecast_hits": [], "risk_hits": [], "dashboard_hits": [], "api_signing_hits": [], "websocket_hits": [], "files_scanned": 1}
    )
    assert plan["verdict"] == RepoVerdict.REJECT_DIRECT_ORDER_BYPASS.value
    assert plan["plans"] == []

def test_adapter_plan_creates_adapter_target():
    plan = generate_adapter_plan(
        {"owner": "x", "name": "y", "license": "MIT"},
        {"direct_order_hits": [], "secret_hits": [], "strategy_hits": ["a.py"], "forecast_hits": ["b.py"], "risk_hits": [], "dashboard_hits": [], "api_signing_hits": [], "websocket_hits": [], "files_scanned": 1}
    )
    assert plan["verdict"] == RepoVerdict.ADAPTER_TARGET.value
    assert len(plan["plans"]) == 1
