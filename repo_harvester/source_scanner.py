import re
from typing import Any

DIRECT_ORDER_PATTERNS = [
    r"create_order\s*\(",
    r"submit_order\s*\(",
    r"place_order\s*\(",
    r"\.orders\s*\.create",
    r"portfolio/orders",
    r"clob\.placeOrder",
    r"\.create\s*\(.*order",
]

SECRET_PATTERNS = [
    r"api[_-]?key\s*=\s*[\"'][^\"']+",
    r"api[_-]?secret\s*=\s*[\"'][^\"']+",
    r"private[_-]?key\s*=\s*[\"'][^\"']+",
    r"password\s*=\s*[\"'][^\"']+",
    r"token\s*=\s*[\"'][^\"']+",
]

STRATEGY_PATTERNS = [
    r"def.*strategy",
    r"class.*Strategy",
    r"kelly",
    r"arbitrage",
    r"edge",
    r"expected.*value",
]

FORECAST_PATTERNS = [
    r"forecast",
    r"predict",
    r"probability",
    r"implied_prob",
]

DASHBOARD_PATTERNS = [
    r"streamlit",
    r"dash",
    r"react",
    r"vue",
    r"fastapi",
    r"flask",
]

RISK_PATTERNS = [
    r"risk",
    r"exposure",
    r"stop_loss",
    r"max_position",
]

def scan_text(text: str, patterns: list[str]) -> list[str]:
    hits = []
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            hits.append(pat)
    return hits

async def scan_repo(owner: str, name: str, max_files: int = 50) -> dict[str, Any]:
    from repo_harvester.contents_client import fetch_repo_tree, fetch_file
    tree = await fetch_repo_tree(owner, name)
    files = [t for t in tree.get("tree", []) if t.get("type") == "blob" and t.get("path", "").endswith((".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go"))]
    # Prioritize smaller files and skip tests/vendored dirs
    files = [f for f in files if not any(d in f["path"] for d in ["node_modules", "vendor", "dist", "build", ".git", "__pycache__", "test_", "_test."])]
    files = sorted(files, key=lambda f: f.get("size", 0))[:max_files]

    result = {
        "owner": owner, "name": name,
        "files_scanned": 0,
        "direct_order_hits": [],
        "secret_hits": [],
        "strategy_hits": [],
        "forecast_hits": [],
        "dashboard_hits": [],
        "risk_hits": [],
        "api_signing_hits": [],
        "websocket_hits": [],
    }

    for f in files:
        try:
            text = await fetch_file(owner, name, f["path"])
        except Exception:
            continue
        result["files_scanned"] += 1
        if scan_text(text, DIRECT_ORDER_PATTERNS):
            result["direct_order_hits"].append(f["path"])
        if scan_text(text, SECRET_PATTERNS):
            result["secret_hits"].append(f["path"])
        if scan_text(text, [r"sign", r"signature", r"access-key"]):
            result["api_signing_hits"].append(f["path"])
        if scan_text(text, [r"websocket", r"ws://", r"wss://"]):
            result["websocket_hits"].append(f["path"])
        if scan_text(text, STRATEGY_PATTERNS):
            result["strategy_hits"].append(f["path"])
        if scan_text(text, FORECAST_PATTERNS):
            result["forecast_hits"].append(f["path"])
        if scan_text(text, DASHBOARD_PATTERNS):
            result["dashboard_hits"].append(f["path"])
        if scan_text(text, RISK_PATTERNS):
            result["risk_hits"].append(f["path"])
    return result
