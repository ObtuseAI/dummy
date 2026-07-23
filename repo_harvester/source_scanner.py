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

# V2 source-scan taxonomy ------------------------------------------------------

SCAN_CATEGORIES: dict[str, list[str]] = {
    "direct_order": [
        r"create_order\s*\(",
        r"submit_order\s*\(",
        r"place_order\s*\(",
        r"placeOrder\s*\(",
        r"send_order\s*\(",
        r"post_order\s*\(",
        r"\.orders\s*\.create",
        r"portfolio/orders",
        r"exchange/trade",
        r"createOrder\s*\(",
        r"\.create\s*\(.*order",
    ],
    "kalshi_order": [
        r"kalshi",
        r"/orders",
        r"/exchange/trade",
        r"create_order_sell",
        r"create_order_buy",
        r"kalshi.*order",
    ],
    "polymarket_order": [
        r"clob",
        r"placeOrder",
        r"createOrder",
        r"negRisk",
        r"polymarket.*order",
        r"\.orders\.",
    ],
    "private_key": [
        r"private[_-]?key",
        r"privateKey",
        r"priv_key",
        r"wallet\.privateKey",
        r"signing[_-]?key",
        r"secret[_-]?key",
        r"mnemonic",
        r"seed[_-]?phrase",
    ],
    "api_secret": [
        r"api[_-]?key",
        r"api[_-]?secret",
        r"access[_-]?key",
        r"appsecret",
        r"consumer[_-]?secret",
        r"auth[_-]?token",
        r"bearer\s+[a-zA-Z0-9_-]+",
    ],
    "dashboard": [
        r"streamlit",
        r"dash\s",
        r"react",
        r"vue",
        r"fastapi",
        r"flask",
        r"gradio",
        r"panel\.",
        r"tornado",
    ],
    "forecast": [
        r"forecast",
        r"predict",
        r"regression",
        r"classifier",
        r"probability",
        r"implied[_-]?prob",
        r"machine[_-]?learning",
        r"ml[_-]?model",
    ],
    "strategy": [
        r"strategy",
        r"trading[_-]?strategy",
        r"bot",
        r"arbitrage",
        r"kelly",
        r"edge",
        r"expected[_-]?value",
        r"alpha",
        r"signal",
    ],
    "risk": [
        r"risk",
        r"exposure",
        r"stop[_-]?loss",
        r"max[_-]?position",
        r"drawdown",
        r"var\s*\(",
        r"volatility",
        r"sharpe",
    ],
    "arbitrage": [
        r"arbitrage",
        r"arb\b",
        r"spread",
        r"mispricing",
        r"cross[_-]?market",
        r"cross[_-]?exchange",
    ],
    "websocket": [
        r"websocket",
        r"ws://",
        r"wss://",
        r"socket\.io",
        r"subscribe\s*\(",
        r"on_message",
        r"on_open",
        r"ws_client",
    ],
    "settlement": [
        r"settlement",
        r"resolve",
        r"outcome",
        r"expire",
        r"redeem",
        r"claim",
        r"mature",
        r"payoff",
    ],
    "sports": [
        r"sports",
        r"nba\b",
        r"football",
        r"soccer",
        r"baseball",
        r"nfl\b",
        r"mlb\b",
        r"odds",
        r"betting",
        r"game",
        r"match",
        r"bookmaker",
    ],
    "weather": [
        r"weather",
        r"noaa",
        r"open[_-]?meteo",
        r"temperature",
        r"rainfall",
        r"precipitation",
        r"forecast",
    ],
    "stocks": [
        r"stock",
        r"equity",
        r"option",
        r"sp500",
        r"nasdaq",
        r"nyse",
        r"yfinance",
        r"alpaca",
        r"portfolio",
        r"quant",
    ],
    "commodities": [
        r"commodity",
        r"gold",
        r"oil",
        r"energy",
        r"cot\b",
        r"eia\b",
        r"agriculture",
        r"wti",
        r"brent",
        r"natural[_-]?gas",
    ],
    "crypto": [
        r"crypto",
        r"bitcoin",
        r"\bbtc\b",
        r"ethereum",
        r"\beth\b",
        r"ccxt",
        r"freqtrade",
        r"exchange",
        r"wallet",
        r"blockchain",
    ],
}


SCAN_EXTENSIONS = (".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go", ".sol", ".java")
SKIP_PATH_FRAGMENTS = [
    "node_modules", "vendor", "dist", "build", ".git", "__pycache__",
    "test_", "_test.", ".test.", "tests/", "docs/", "examples/",
]


def scan_text(text: str, patterns: list[str]) -> list[str]:
    hits = []
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            hits.append(pat)
    return hits


def categorize_text(text: str) -> dict[str, list[str]]:
    """Return matched pattern strings for each V2 scan category."""
    return {
        category: scan_text(text, patterns)
        for category, patterns in SCAN_CATEGORIES.items()
    }


def _should_skip_path(path: str) -> bool:
    lowered = path.lower()
    return any(fragment in lowered for fragment in SKIP_PATH_FRAGMENTS)


def _score_file(path: str) -> int:
    """Prefer implementation files near the root; deprioritize tests/docs."""
    path_lower = path.lower()
    score = 0
    if any(path.endswith(ext) for ext in (".py", ".rs", ".go")):
        score += 20
    if any(path.endswith(ext) for ext in (".ts", ".js")):
        score += 10
    if "/src/" in path_lower or path.count("/") <= 1:
        score += 15
    if "main" in path_lower or "app" in path_lower or "cli" in path_lower:
        score += 10
    if "test" in path_lower or "doc" in path_lower or "example" in path_lower:
        score -= 20
    return score


async def scan_repo(owner: str, name: str, max_files: int = 50) -> dict[str, Any]:
    from repo_harvester.contents_client import fetch_repo_tree, fetch_file
    tree = await fetch_repo_tree(owner, name)
    files = [t for t in tree.get("tree", []) if t.get("type") == "blob" and t.get("path", "").endswith(SCAN_EXTENSIONS)]
    files = [f for f in files if not _should_skip_path(f["path"])]
    files = sorted(files, key=lambda f: (f.get("size", 0), -_score_file(f["path"])))[:max_files]

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

    texts: dict[str, str] = {}
    for f in files:
        try:
            text = await fetch_file(owner, name, f["path"])
        except Exception:
            continue
        texts[f["path"]] = text
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
    # Security-inspection gate: credential-harvesting / RCE red flags. A BLOCK
    # verdict must keep the repo out of the adoption pipeline (checked at
    # incorporation), never adopted silently.
    from repo_harvester.security_gate import assess_repo_security

    result["security"] = assess_repo_security(texts)
    return result


async def scan_repo_enhanced(owner: str, name: str, client=None, max_files: int = 35) -> dict[str, Any]:
    """Source-level scan using the V2 taxonomy.

    If ``client`` is provided it must be an httpx.AsyncClient; otherwise a new
    client is created per call (slower but simple for small runs).
    """
    from repo_harvester.contents_client import fetch_repo_tree, fetch_file
    tree = await fetch_repo_tree(owner, name)
    files = [t for t in tree.get("tree", []) if t.get("type") == "blob" and t.get("path", "").endswith(SCAN_EXTENSIONS)]
    files = [f for f in files if not _should_skip_path(f["path"])]
    # Sort by size ascending, with a path-quality tie-breaker.
    files = sorted(files, key=lambda f: (f.get("size", 0), -_score_file(f["path"])))[:max_files]

    result = {
        "owner": owner,
        "name": name,
        "files_scanned": 0,
        "files_considered": len(files),
        "tree_size": len(tree.get("tree", [])),
    }
    for category in SCAN_CATEGORIES:
        result[f"{category}_hits"] = []

    for f in files:
        try:
            text = await fetch_file(owner, name, f["path"])
        except Exception:
            continue
        result["files_scanned"] += 1
        categories = categorize_text(text)
        for category, hits in categories.items():
            if hits:
                result[f"{category}_hits"].append(f["path"])

    return result
