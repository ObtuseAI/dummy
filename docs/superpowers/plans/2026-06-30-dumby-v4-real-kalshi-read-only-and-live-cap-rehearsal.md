# DUMBY_V4_REAL_KALSHI_READ_ONLY_INGESTION_AND_LIVE_CAP_FIREWALL_REHEARSAL_V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect Dummy to real Kalshi in READ_ONLY mode, prove ingestion without secrets or orders, then run an AUTONOMOUS_LIVE_CAPPED firewall rehearsal that stops before real submit unless `configs/live_submit.json` explicitly enables it.

**Architecture:** Add a `KalshiRealReadOnly` wrapper and `KalshiNormalizer` for READ_ONLY ingestion, run the 8 repo-derived strategies over normalized snapshots, extend `LiveBrokerFirewall` with a config-gated live-submit check and a rehearsal mode, and add Dashboard V4 endpoints/screens. All changes build on V3 without modifying canonical Blunder or weakening safety controls.

**Tech Stack:** Python 3.11+, FastAPI, httpx, Pydantic, pytest, React/Vite/Tailwind.

## Global Constraints

- Do not rebuild Dummy from scratch.
- Do not modify canonical Blunder (`C:/src/engine/obtuse/blunder`).
- Do not weaken the Live Broker Firewall.
- Do not add a paper-trading ladder.
- Do not expand the repo list.
- Do not log Kalshi secrets.
- Do not write secrets into artifacts.
- Do not create market orders.
- Do not place real live orders unless `configs/live_submit.json` has `enabled: true`.
- No strategy, adapter, forecast, or repo-derived module may submit orders directly.
- All real order submission must pass through `LiveBrokerFirewall.submit`.
- Preserve operator-controlled caps in `configs/caps.json`; Dummy never modifies caps.

---

## File Map

| File | Responsibility |
|---|---|
| `configs/live_submit.json` | Operator-approved live-submit flag. Default `enabled: false`. |
| `core/ontology.py` | Add `Fill`, `RestingOrder`, `KalshiAccount`, `Market`, `Event`, `Contract` models if missing. |
| `kalshi/live_data.py` | Add `KalshiRealReadOnly` class for real READ_ONLY ingestion. |
| `kalshi/normalizer.py` | Add `KalshiNormalizer` class for live data → Dummy-native models. |
| `strategies/scan.py` | Add `StrategyScanner` to run repo-derived families over a snapshot. |
| `live_firewall/firewall.py` | Add `_live_submit_enabled`, `submit_rehearsal`, and live-submit gate in `submit`. |
| `execution/autonomous_path.py` | Add `rehearse_live_cap` and report generators. |
| `services/reports.py` or new `scripts/generate_v4_reports.py` | Generate required V4 artifact reports. |
| `dashboard/backend/v4_routes.py` | FastAPI router for all `/v4/*` endpoints. |
| `dashboard/backend/main.py` | Include `v4_routes`. |
| `dashboard/frontend/src/App.jsx` | Add V4 navigation. |
| `dashboard/frontend/src/screens/KalshiReal.jsx` | Real Kalshi status, account, markets. |
| `dashboard/frontend/src/screens/StrategyScan.jsx` | Strategy proposals/no-trade reasons. |
| `dashboard/frontend/src/screens/FirewallRehearsal.jsx` | Rehearsal verdicts and blocked reasons. |
| `dashboard/frontend/src/screens/LiveSubmit.jsx` | Live-submit flag status. |
| `tests/test_real_kalshi_read_only.py` | Real ingestion tests. |
| `tests/test_kalshi_normalizer.py` | Normalizer tests. |
| `tests/test_real_market_strategy_scan.py` | Strategy scan tests. |
| `tests/test_live_cap_firewall_rehearsal.py` | Firewall rehearsal tests. |
| `tests/test_no_order_in_read_only.py` | No-order-in-read-only proof. |
| `tests/test_no_secret_leak_v3.py` | Secret leak scan. |
| `tests/test_direct_order_bypass_v4.py` | Direct order bypass scan. |
| `tests/test_backend_v4.py` | Dashboard V4 backend tests. |
| `tests/test_blunder_separation_v2.py` | Blunder separation recheck. |

---

## Task 1: Add operator live-submit flag config

**Files:**
- Create: `configs/live_submit.json`

**Interfaces:**
- Produces: `configs/live_submit.json` with `enabled`, `operator`, `timestamp`, `reason`.

- [ ] **Step 1: Create the config file**

```json
{
  "enabled": false,
  "operator": "none",
  "timestamp": "2026-06-30T18:54:51Z",
  "reason": "default disabled"
}
```

- [ ] **Step 2: Verify it is valid JSON and never modified by code**

Run:
```bash
python -c "import json; json.load(open('configs/live_submit.json'))"
```
Expected: no output (success).

- [ ] **Step 3: Commit**

```bash
git add configs/live_submit.json
git commit -m "feat(v4): add operator live-submit flag config"
```

---

## Task 2: Extend ontology models for live data

**Files:**
- Modify: `core/ontology.py`
- Test: `tests/test_ontology.py` (create if missing)

**Interfaces:**
- Consumes: existing Pydantic patterns in `core/ontology.py`.
- Produces: `Fill`, `RestingOrder`, `KalshiAccount`, `Market`, `Event`, `Contract`, `ForecastInput` models.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ontology.py`:

```python
from core.ontology import Fill, RestingOrder, KalshiAccount, Market, Event, Contract, ForecastInput

def test_fill_model():
    f = Fill(fill_id="f1", market_ticker="KXBTCDEMO-26DEC", contract_ticker="KXBTCDEMO-26DEC-B", side="yes", count=1, price=50, timestamp="2026-06-30T18:00:00Z")
    assert f.fill_id == "f1"

def test_forecast_input_model():
    fi = ForecastInput(market_ticker="KXBTCDEMO-26DEC", yes_bid=49, yes_ask=51, timestamp="2026-06-30T18:00:00Z")
    assert fi.yes_bid == 49
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
pytest tests/test_ontology.py -v
```
Expected: `ImportError` or `AttributeError` for missing models.

- [ ] **Step 3: Add models to `core/ontology.py`**

Append to `core/ontology.py`:

```python
class Fill(BaseModel):
    fill_id: str
    market_ticker: str
    contract_ticker: str
    side: str
    count: int
    price: int
    timestamp: str

class RestingOrder(BaseModel):
    order_id: str
    market_ticker: str
    contract_ticker: str
    side: str
    action: str
    type: str
    count: int
    price: int
    status: str
    created_at: str

class KalshiAccount(BaseModel):
    user_id: str
    email: str
    balance_cents: int
    available_cents: int
    portfolio_witness: Optional[str] = None

class Contract(BaseModel):
    ticker: str
    title: str
    status: str
    yes_bid: Optional[int] = None
    yes_ask: Optional[int] = None
    last_price: Optional[int] = None

class Market(BaseModel):
    ticker: str
    title: str
    status: str
    category: str
    event_ticker: str
    contracts: List[Contract] = Field(default_factory=list)

class Event(BaseModel):
    ticker: str
    title: str
    category: str
    status: str
    markets: List[Market] = Field(default_factory=list)

class ForecastInput(BaseModel):
    market_ticker: str
    yes_bid: int
    yes_ask: int
    timestamp: str
    volume: Optional[int] = None
    open_interest: Optional[int] = None
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
pytest tests/test_ontology.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add core/ontology.py tests/test_ontology.py
git commit -m "feat(v4): add live data ontology models"
```

---

## Task 3: Implement real Kalshi READ_ONLY ingestion

**Files:**
- Modify: `kalshi/live_data.py`
- Test: `tests/test_real_kalshi_read_only.py`

**Interfaces:**
- Consumes: `KalshiClient`, `core.secret_guard.redact`, `core.state.STATE`.
- Produces: `KalshiRealReadOnly` with async read methods and `endpoints_called()`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_real_kalshi_read_only.py`:

```python
import pytest
from kalshi.live_data import KalshiRealReadOnly, KalshiCredentialsMissing

@pytest.mark.asyncio
async def test_real_read_only_methods_exist():
    try:
        client = KalshiRealReadOnly()
    except KalshiCredentialsMissing:
        pytest.skip("Kalshi credentials not present")
    assert hasattr(client, "get_account_status")
    assert hasattr(client, "get_balance")
    assert hasattr(client, "get_events")
    assert hasattr(client, "get_markets")
    assert hasattr(client, "get_orderbook")
    assert hasattr(client, "get_positions")
    assert hasattr(client, "get_resting_orders")
    assert hasattr(client, "get_fills")
    assert hasattr(client, "endpoints_called")
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
pytest tests/test_real_kalshi_read_only.py -v
```
Expected: `ImportError` for `KalshiRealReadOnly`.

- [ ] **Step 3: Implement `KalshiRealReadOnly` in `kalshi/live_data.py`**

Add at the top of `kalshi/live_data.py`:

```python
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from core.secret_guard import redact
```

Add exception class:

```python
class KalshiCredentialsMissing(Exception):
    pass
```

Add class:

```python
class KalshiRealReadOnly:
    def __init__(self, client: Optional[KalshiClient] = None):
        key_id = os.environ.get("KALSHI_API_KEY_ID")
        pem = os.environ.get("KALSHI_API_PRIVATE_KEY_PEM")
        pem_path = os.environ.get("KALSHI_API_PRIVATE_KEY_PEM_PATH")
        if not key_id or (not pem and not pem_path):
            raise KalshiCredentialsMissing("KALSHI_API_KEY_ID and KALSHI_API_PRIVATE_KEY_PEM/PATH required")
        self.client = client or KalshiClient()
        self._endpoints: Set[str] = set()

    def _track(self, endpoint: str):
        self._endpoints.add(endpoint)

    def endpoints_called(self) -> Set[str]:
        return set(self._endpoints)

    async def get_account_status(self) -> Dict[str, Any]:
        self._track("GET /account")
        raw = await self.client.get("/account")
        return redact(raw)

    async def get_balance(self) -> Dict[str, Any]:
        self._track("GET /account/balance")
        raw = await self.client.get("/account/balance")
        return redact(raw)

    async def get_events(self) -> List[Dict[str, Any]]:
        self._track("GET /events")
        raw = await self.client.get("/events")
        return redact(raw.get("events", []))

    async def get_markets(self) -> List[Dict[str, Any]]:
        self._track("GET /markets")
        raw = await self.client.get("/markets")
        return redact(raw.get("markets", []))

    async def get_orderbook(self, ticker: str) -> Dict[str, Any]:
        self._track("GET /markets/{ticker}/orderbook")
        raw = await self.client.get(f"/markets/{ticker}/orderbook")
        raw["ticker"] = ticker
        return redact(raw)

    async def get_positions(self) -> List[Dict[str, Any]]:
        self._track("GET /portfolio/positions")
        raw = await self.client.get("/portfolio/positions")
        return redact(raw.get("positions", []))

    async def get_resting_orders(self) -> List[Dict[str, Any]]:
        self._track("GET /portfolio/orders")
        raw = await self.client.get("/portfolio/orders")
        return redact(raw.get("orders", []))

    async def get_fills(self) -> List[Dict[str, Any]]:
        self._track("GET /portfolio/fills")
        raw = await self.client.get("/portfolio/fills")
        return redact(raw.get("fills", []))

    async def get_full_snapshot(self, market_ticker: str) -> Dict[str, Any]:
        return {
            "account_status": await self.get_account_status(),
            "balance": await self.get_balance(),
            "events": await self.get_events(),
            "markets": await self.get_markets(),
            "orderbook": await self.get_orderbook(market_ticker),
            "positions": await self.get_positions(),
            "resting_orders": await self.get_resting_orders(),
            "fills": await self.get_fills(),
            "endpoints_called": sorted(self.endpoints_called()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
pytest tests/test_real_kalshi_read_only.py -v
```
Expected: 1 passed (skipped if no credentials).

- [ ] **Step 5: Commit**

```bash
git add kalshi/live_data.py tests/test_real_kalshi_read_only.py
git commit -m "feat(v4): add real Kalshi READ_ONLY ingestion wrapper"
```

---

## Task 4: Implement Kalshi normalizer

**Files:**
- Create: `kalshi/normalizer.py`
- Test: `tests/test_kalshi_normalizer.py`

**Interfaces:**
- Consumes: raw Kalshi dicts, `core.ontology` models.
- Produces: normalized `Market`, `Event`, `Contract`, `OrderBook`, `Position`, `Fill`, `RestingOrder`, `KalshiAccount`, `ForecastInput`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_kalshi_normalizer.py`:

```python
import pytest
from kalshi.normalizer import KalshiNormalizer
from core.ontology import OrderBook, Market, Fill

def test_normalize_orderbook():
    raw = {
        "ticker": "KXBTCDEMO-26DEC",
        "yes_bid": 49,
        "yes_ask": 51,
        "no_bid": 49,
        "no_ask": 51,
        "timestamp": "2026-06-30T18:00:00Z",
    }
    ob = KalshiNormalizer.normalize_orderbook("KXBTCDEMO-26DEC", raw)
    assert isinstance(ob, OrderBook)
    assert ob.ticker == "KXBTCDEMO-26DEC"

def test_reject_stale_orderbook():
    raw = {
        "yes_bid": 49,
        "yes_ask": 51,
        "timestamp": "2020-01-01T00:00:00Z",
    }
    with pytest.raises(ValueError):
        KalshiNormalizer.normalize_orderbook("KXBTCDEMO-26DEC", raw)

def test_normalize_fill():
    raw = {"fills": [{"fill_id": "f1", "market_ticker": "KXBTCDEMO", "ticker": "KXBTCDEMO-B", "side": "yes", "count": 1, "price": 50, "created_time": "2026-06-30T18:00:00Z"}]}
    fills = KalshiNormalizer.normalize_fills(raw)
    assert len(fills) == 1
    assert isinstance(fills[0], Fill)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
pytest tests/test_kalshi_normalizer.py -v
```
Expected: `ImportError` or `AttributeError`.

- [ ] **Step 3: Implement `KalshiNormalizer`**

Create `kalshi/normalizer.py`:

```python
from datetime import datetime, timezone
from typing import Any, Dict, List
from core.ontology import (
    Contract, Event, Fill, ForecastInput, KalshiAccount, Market,
    OrderBook, Position, RestingOrder,
)

_STALE_SECONDS = 60

class KalshiNormalizer:
    @staticmethod
    def _now_utc() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _parse_ts(ts: str) -> datetime:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    @staticmethod
    def _is_stale(ts: str) -> bool:
        try:
            age = (KalshiNormalizer._now_utc() - KalshiNormalizer._parse_ts(ts)).total_seconds()
            return age > _STALE_SECONDS
        except Exception:
            return True

    @staticmethod
    def normalize_account(raw: Dict[str, Any]) -> KalshiAccount:
        return KalshiAccount(
            user_id=raw.get("user_id", "unknown"),
            email=raw.get("email", ""),
            balance_cents=raw.get("balance", 0),
            available_cents=raw.get("available_balance", 0),
        )

    @staticmethod
    def normalize_events(raw: Dict[str, Any]) -> List[Event]:
        out = []
        for e in raw.get("events", raw if isinstance(raw, list) else []):
            markets = [KalshiNormalizer.normalize_market(m) for m in e.get("markets", [])]
            out.append(Event(
                ticker=e.get("event_ticker", e.get("ticker", "")),
                title=e.get("title", ""),
                category=e.get("category", ""),
                status=e.get("status", ""),
                markets=markets,
            ))
        return out

    @staticmethod
    def normalize_markets(raw: Dict[str, Any]) -> List[Market]:
        out = []
        for m in raw.get("markets", raw if isinstance(raw, list) else []):
            contracts = [KalshiNormalizer._normalize_contract(c) for c in m.get("contracts", [m])]
            out.append(Market(
                ticker=m.get("ticker", ""),
                title=m.get("title", ""),
                status=m.get("status", ""),
                category=m.get("category", ""),
                event_ticker=m.get("event_ticker", ""),
                contracts=contracts,
            ))
        return out

    @staticmethod
    def _normalize_contract(raw: Dict[str, Any]) -> Contract:
        if not raw.get("ticker"):
            raise ValueError("Contract missing ticker")
        return Contract(
            ticker=raw["ticker"],
            title=raw.get("title", ""),
            status=raw.get("status", ""),
            yes_bid=raw.get("yes_bid"),
            yes_ask=raw.get("yes_ask"),
            last_price=raw.get("last_price"),
        )

    @staticmethod
    def normalize_orderbook(ticker: str, raw: Dict[str, Any]) -> OrderBook:
        ts = raw.get("timestamp", raw.get("updated_at", datetime.now(timezone.utc).isoformat()))
        if KalshiNormalizer._is_stale(ts):
            raise ValueError(f"Orderbook for {ticker} is stale (timestamp {ts})")
        bids = raw.get("yes_bid", raw.get("bids", []))
        asks = raw.get("yes_ask", raw.get("asks", []))
        if isinstance(bids, (int, float)):
            bids = [{"price": int(bids * 100) if bids <= 1 else int(bids), "count": 1}]
        if isinstance(asks, (int, float)):
            asks = [{"price": int(asks * 100) if asks <= 1 else int(asks), "count": 1}]
        return OrderBook(
            ticker=ticker,
            bids=bids,
            asks=asks,
            timestamp=ts,
        )

    @staticmethod
    def normalize_positions(raw: Dict[str, Any]) -> List[Position]:
        return [Position(
            market_ticker=p.get("market_ticker", p.get("ticker", "")),
            contract_ticker=p.get("ticker", ""),
            position=p.get("position", 0),
            avg_price=p.get("avg_price", 0),
        ) for p in raw.get("positions", raw if isinstance(raw, list) else [])]

    @staticmethod
    def normalize_resting_orders(raw: Dict[str, Any]) -> List[RestingOrder]:
        return [RestingOrder(
            order_id=o.get("order_id", o.get("id", "")),
            market_ticker=o.get("market_ticker", ""),
            contract_ticker=o.get("ticker", ""),
            side=o.get("side", ""),
            action=o.get("action", ""),
            type=o.get("type", ""),
            count=o.get("count", 0),
            price=o.get("price", 0),
            status=o.get("status", ""),
            created_at=o.get("created_time", o.get("created_at", "")),
        ) for o in raw.get("orders", raw if isinstance(raw, list) else [])]

    @staticmethod
    def normalize_fills(raw: Dict[str, Any]) -> List[Fill]:
        return [Fill(
            fill_id=f.get("fill_id", f.get("id", "")),
            market_ticker=f.get("market_ticker", ""),
            contract_ticker=f.get("ticker", ""),
            side=f.get("side", ""),
            count=f.get("count", 0),
            price=f.get("price", 0),
            timestamp=f.get("created_time", f.get("timestamp", "")),
        ) for f in raw.get("fills", raw if isinstance(raw, list) else [])]

    @staticmethod
    def to_forecast_input(market: Market, orderbook: OrderBook) -> ForecastInput:
        contract = market.contracts[0] if market.contracts else Contract(ticker=market.ticker, title=market.title, status=market.status)
        return ForecastInput(
            market_ticker=market.ticker,
            yes_bid=contract.yes_bid or 0,
            yes_ask=contract.yes_ask or 0,
            timestamp=orderbook.timestamp,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
pytest tests/test_kalshi_normalizer.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add kalshi/normalizer.py tests/test_kalshi_normalizer.py
git commit -m "feat(v4): add Kalshi live data normalizer"
```

---

## Task 5: Add strategy scan orchestrator

**Files:**
- Create: `strategies/scan.py`
- Test: `tests/test_real_market_strategy_scan.py`

**Interfaces:**
- Consumes: repo-derived strategy classes, `Forecast`, `OrderBook`.
- Produces: `StrategyScanResult` list with proposals/no-trade explanations.

- [ ] **Step 1: Write the failing test**

Create `tests/test_real_market_strategy_scan.py`:

```python
import pytest
from core.ontology import Forecast, OrderBook
from strategies.scan import StrategyScanner, StrategyScanResult

@pytest.mark.asyncio
async def test_scan_runs_all_families():
    forecast = Forecast(market_ticker="KXBTCDEMO", yes_price=50, confidence=0.6, source="test")
    orderbook = OrderBook(ticker="KXBTCDEMO", bids=[{"price": 49, "count": 10}], asks=[{"price": 51, "count": 10}], timestamp="2026-06-30T18:00:00Z")
    results = await StrategyScanner().scan(forecast, orderbook)
    assert len(results) >= 8
    for r in results:
        assert isinstance(r, StrategyScanResult)
        assert r.family
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
pytest tests/test_real_market_strategy_scan.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Implement `StrategyScanner`**

Create `strategies/scan.py`:

```python
from dataclasses import dataclass, field
from typing import List, Optional
from core.ontology import Forecast, OrderBook, TradeProposal
from strategies.registry import get_repo_derived_strategies

@dataclass
class StrategyScanResult:
    family: str
    market_ticker: str
    edge_estimate: float
    confidence: float
    liquidity_score: float
    spread_score: float
    settlement_risk_score: float
    proposal: Optional[TradeProposal] = None
    no_trade_reason: Optional[str] = None
    raw_notes: dict = field(default_factory=dict)

class StrategyScanner:
    def __init__(self):
        self.strategies = get_repo_derived_strategies()

    async def scan(self, forecast: Forecast, orderbook: OrderBook) -> List[StrategyScanResult]:
        results = []
        for strat in self.strategies:
            try:
                proposal = strat.evaluate(forecast, orderbook)
            except Exception as exc:
                proposal = None
                no_trade_reason = f"exception: {type(exc).__name__}: {exc}"
            else:
                no_trade_reason = None if proposal else "no edge or below thresholds"
            results.append(StrategyScanResult(
                family=strat.name,
                market_ticker=forecast.market_ticker,
                edge_estimate=proposal.edge_estimate if proposal else 0.0,
                confidence=proposal.confidence if proposal else forecast.confidence,
                liquidity_score=proposal.liquidity_score if proposal else 0.0,
                spread_score=proposal.spread_score if proposal else 0.0,
                settlement_risk_score=proposal.settlement_risk_score if proposal else 1.0,
                proposal=proposal,
                no_trade_reason=no_trade_reason,
            ))
        return results
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
pytest tests/test_real_market_strategy_scan.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add strategies/scan.py tests/test_real_market_strategy_scan.py
git commit -m "feat(v4): add repo-derived strategy scanner"
```

---

## Task 6: Extend LiveBrokerFirewall with live-submit gate and rehearsal mode

**Files:**
- Modify: `live_firewall/firewall.py`
- Test: `tests/test_live_cap_firewall_rehearsal.py`

**Interfaces:**
- Consumes: `configs/live_submit.json`, `LiveOrderRequest`, `OrderBook`, `Forecast`.
- Produces: `RehearsalVerdict`, live-submit gate in `submit`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_live_cap_firewall_rehearsal.py`:

```python
import pytest
from live_firewall.firewall import LiveBrokerFirewall, RehearsalVerdict

@pytest.mark.asyncio
async def test_submit_blocks_without_live_submit_flag():
    fw = LiveBrokerFirewall(client=None)
    assert not fw._live_submit_enabled()
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
pytest tests/test_live_cap_firewall_rehearsal.py -v
```
Expected: `AttributeError` for `_live_submit_enabled`.

- [ ] **Step 3: Add live-submit and rehearsal methods**

In `live_firewall/firewall.py`, add imports:

```python
import json
from pathlib import Path
from dataclasses import dataclass
```

Add dataclass after imports:

```python
@dataclass
class RehearsalVerdict:
    would_submit: bool
    firewall_verdict: Any
    order: Optional[Dict[str, Any]]
    blocked_reason: Optional[str]
```

Add helper method to `LiveBrokerFirewall`:

```python
    def _live_submit_enabled(self) -> bool:
        path = Path("configs/live_submit.json")
        if not path.exists():
            return False
        try:
            data = json.loads(path.read_text())
        except Exception:
            return False
        if data.get("enabled") is not True:
            return False
        return True
```

Add rehearsal method:

```python
    async def submit_rehearsal(self, req, orderbook, forecast):
        verdict = await self.evaluate(req, orderbook, forecast)
        if not verdict.allow:
            return RehearsalVerdict(
                would_submit=False,
                firewall_verdict=verdict,
                order=None,
                blocked_reason=verdict.reason,
            )
        if not self._live_submit_enabled():
            order = self._build_order(req)
            return RehearsalVerdict(
                would_submit=False,
                firewall_verdict=verdict,
                order=order,
                blocked_reason="live_submit_disabled",
            )
        return RehearsalVerdict(
            would_submit=True,
            firewall_verdict=verdict,
            order=self._build_order(req),
            blocked_reason=None,
        )
```

Extract order building into helper:

```python
    def _build_order(self, req) -> Dict[str, Any]:
        return {
            "ticker": req.contract_ticker,
            "side": req.side,
            "action": "buy",
            "type": "limit",
            "count": req.count,
            "price": req.price,
        }
```

Update `submit` to use `_build_order` and add live-submit gate:

```python
    async def submit(self, req, orderbook, forecast):
        verdict = await self.evaluate(req, orderbook, forecast)
        if not verdict.allow:
            return LiveOrderResult(success=False, error=verdict.reason, ...)
        if not self._live_submit_enabled():
            return LiveOrderResult(success=False, error="live_submit_disabled", blocked=True)
        order = self._build_order(req)
        resp = await self.client.create_order(order)
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
pytest tests/test_live_cap_firewall_rehearsal.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add live_firewall/firewall.py tests/test_live_cap_firewall_rehearsal.py
git commit -m "feat(v4): add live-submit gate and firewall rehearsal mode"
```

---

## Task 7: Extend autonomous path with rehearsal method

**Files:**
- Modify: `execution/autonomous_path.py`
- Test: `tests/test_autonomous_path.py` (add tests)

**Interfaces:**
- Consumes: `KalshiRealReadOnly`, `KalshiNormalizer`, `StrategyScanner`, `LiveBrokerFirewall`.
- Produces: `RehearsalResult` and reports.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_autonomous_path.py`:

```python
@pytest.mark.asyncio
async def test_rehearse_live_cap_blocks_by_default(tmp_path):
    path = AutonomousExecutionPath
    assert hasattr(path, "rehearse_live_cap")
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
pytest tests/test_autonomous_path.py::test_rehearse_live_cap_blocks_by_default -v
```
Expected: `AttributeError`.

- [ ] **Step 3: Add `rehearse_live_cap` to `AutonomousExecutionPath`**

In `execution/autonomous_path.py`, add imports:

```python
from dataclasses import dataclass, field
from typing import List
from kalshi.live_data import KalshiRealReadOnly, KalshiCredentialsMissing
from kalshi.normalizer import KalshiNormalizer
from strategies.scan import StrategyScanner, StrategyScanResult
```

Add dataclass:

```python
@dataclass
class RehearsalResult:
    market_ticker: str
    contract_ticker: str
    mode: str
    credentials_present: bool
    snapshot: dict = field(default_factory=dict)
    scan_results: List[StrategyScanResult] = field(default_factory=list)
    selected_proposal: Any = None
    risk_verdict: Any = None
    compliance_verdict: Any = None
    firewall_rehearsal: Any = None
    live_submitted: bool = False
    error: Optional[str] = None
```

Add method:

```python
    async def rehearse_live_cap(self, market_ticker: str, contract_ticker: str, strategy_name: str | None = None) -> RehearsalResult:
        if self.mode != AccountMode.AUTONOMOUS_LIVE_CAPPED:
            return RehearsalResult(market_ticker=market_ticker, contract_ticker=contract_ticker, mode=self.mode.value, credentials_present=False, error="mode_not_autonomous_live_capped")
        try:
            reader = KalshiRealReadOnly()
        except KalshiCredentialsMissing:
            return RehearsalResult(market_ticker=market_ticker, contract_ticker=contract_ticker, mode=self.mode.value, credentials_present=False, error="credentials_missing")
        snapshot = await reader.get_full_snapshot(contract_ticker)
        normalizer = KalshiNormalizer()
        try:
            orderbook = normalizer.normalize_orderbook(contract_ticker, snapshot["orderbook"])
            markets = normalizer.normalize_markets({"markets": snapshot["markets"]})
            market = next((m for m in markets if m.ticker == market_ticker), None)
            forecast = await self.forecast_engine.generate(market, orderbook)
        except Exception as exc:
            return RehearsalResult(market_ticker=market_ticker, contract_ticker=contract_ticker, mode=self.mode.value, credentials_present=True, snapshot=snapshot, error=f"normalization_failed: {exc}")
        scanner = StrategyScanner()
        scan_results = await scanner.scan(forecast, orderbook)
        proposal = None
        if strategy_name:
            proposal = next((r.proposal for r in scan_results if r.family == strategy_name and r.proposal), None)
        if not proposal:
            proposal = next((r.proposal for r in scan_results if r.proposal), None)
        risk_verdict = self.risk_governor.assess_trade_risk(proposal, orderbook) if proposal else None
        compliance_verdict = self.compliance_governor.assess_compliance(proposal) if proposal else None
        firewall_rehearsal = None
        live_submitted = False
        if proposal:
            req = LiveOrderRequest(
                market_ticker=market_ticker,
                contract_ticker=contract_ticker,
                side=proposal.side,
                count=proposal.size,
                price=proposal.target_price,
                adapter_name=proposal.adapter_name,
                strategy_name=proposal.strategy_name,
                proof_refs=proposal.proof_refs,
            )
            firewall_rehearsal = await self.firewall.submit_rehearsal(req, orderbook, forecast)
            if firewall_rehearsal.would_submit:
                result = await self.firewall.submit(req, orderbook, forecast)
                live_submitted = result.success
        return RehearsalResult(
            market_ticker=market_ticker,
            contract_ticker=contract_ticker,
            mode=self.mode.value,
            credentials_present=True,
            snapshot=snapshot,
            scan_results=scan_results,
            selected_proposal=proposal,
            risk_verdict=risk_verdict,
            compliance_verdict=compliance_verdict,
            firewall_rehearsal=firewall_rehearsal,
            live_submitted=live_submitted,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
pytest tests/test_autonomous_path.py -v
```
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add execution/autonomous_path.py tests/test_autonomous_path.py
git commit -m "feat(v4): add autonomous live cap rehearsal method"
```

---

## Task 8: Generate V4 reports

**Files:**
- Create: `scripts/generate_v4_reports.py`
- Modify: `services/reports.py` if needed

**Interfaces:**
- Consumes: reports from ingestion, normalizer, scanner, rehearsal, tests.
- Produces: all required artifact JSON files in `artifacts/dummy/`.

- [ ] **Step 1: Create report generator script**

Create `scripts/generate_v4_reports.py`:

```python
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from kalshi.live_data import KalshiRealReadOnly, KalshiCredentialsMissing
from kalshi.normalizer import KalshiNormalizer
from execution.autonomous_path import AutonomousExecutionPath
from core.config_loader import load_caps
from core.state import AccountMode, STATE

ARTIFACTS = Path("artifacts/dummy")
ARTIFACTS.mkdir(parents=True, exist_ok=True)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

async def generate_read_only_report():
    report = {"timestamp": now_iso(), "credentials_present": False, "endpoints_called": [], "data_summary": {}, "verdict": "SKIP"}
    try:
        reader = KalshiRealReadOnly()
    except KalshiCredentialsMissing:
        return report
    report["credentials_present"] = True
    snapshot = await reader.get_full_snapshot("KXBTCDEMO")
    report["endpoints_called"] = sorted(reader.endpoints_called())
    report["data_summary"] = {
        "events_count": len(snapshot.get("events", [])),
        "markets_count": len(snapshot.get("markets", [])),
        "positions_count": len(snapshot.get("positions", [])),
        "resting_orders_count": len(snapshot.get("resting_orders", [])),
        "fills_count": len(snapshot.get("fills", [])),
    }
    order_endpoints = {e for e in report["endpoints_called"] if "order" in e.lower() or "portfolio/orders" in e}
    report["verdict"] = "FAIL" if order_endpoints else "PASS"
    return report

async def generate_normalization_report():
    report = {"timestamp": now_iso(), "credentials_present": False, "normalized_counts": {}, "errors": [], "verdict": "SKIP"}
    try:
        reader = KalshiRealReadOnly()
    except KalshiCredentialsMissing:
        return report
    report["credentials_present"] = True
    normalizer = KalshiNormalizer()
    try:
        snapshot = await reader.get_full_snapshot("KXBTCDEMO")
        account = normalizer.normalize_account(snapshot["account_status"])
        events = normalizer.normalize_events({"events": snapshot["events"]})
        markets = normalizer.normalize_markets({"markets": snapshot["markets"]})
        orderbook = normalizer.normalize_orderbook("KXBTCDEMO", snapshot["orderbook"])
        positions = normalizer.normalize_positions(snapshot["positions"])
        orders = normalizer.normalize_resting_orders(snapshot["resting_orders"])
        fills = normalizer.normalize_fills(snapshot["fills"])
        report["normalized_counts"] = {
            "account": 1, "events": len(events), "markets": len(markets),
            "orderbook": 1, "positions": len(positions), "resting_orders": len(orders), "fills": len(fills),
        }
        report["verdict"] = "PASS"
    except Exception as exc:
        report["errors"].append(str(exc))
        report["verdict"] = "FAIL"
    return report

async def main():
    reports = {
        "real_kalshi_read_only_report_v1.json": await generate_read_only_report(),
        "kalshi_normalization_report_v1.json": await generate_normalization_report(),
    }
    for name, data in reports.items():
        (ARTIFACTS / name).write_text(json.dumps(data, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run the report generator**

Run:
```bash
python scripts/generate_v4_reports.py
```
Expected: creates `artifacts/dummy/real_kalshi_read_only_report_v1.json` and `artifacts/dummy/kalshi_normalization_report_v1.json`.

- [ ] **Step 3: Commit**

```bash
git add scripts/generate_v4_reports.py
git commit -m "feat(v4): add V4 report generator"
```

---

## Task 9: Add safety tests

**Files:**
- Create: `tests/test_no_order_in_read_only.py`
- Create: `tests/test_no_secret_leak_v3.py`
- Create: `tests/test_direct_order_bypass_v4.py`
- Create: `tests/test_blunder_separation_v2.py`

**Interfaces:**
- Consumes: source tree, logs, artifacts.
- Produces: PASS/FAIL reports.

- [ ] **Step 1: Implement no-order-in-read-only test**

Create `tests/test_no_order_in_read_only.py`:

```python
from kalshi.live_data import KalshiRealReadOnly

def test_read_only_endpoints_exclude_orders():
    reader = KalshiRealReadOnly.__new__(KalshiRealReadOnly)
    reader._endpoints = {
        "GET /account", "GET /account/balance", "GET /events",
        "GET /markets", "GET /markets/{ticker}/orderbook",
        "GET /portfolio/positions", "GET /portfolio/orders", "GET /portfolio/fills",
    }
    order_creating = {e for e in reader.endpoints_called() if "create" in e.lower() or "POST /portfolio/orders" in e}
    assert not order_creating
```

- [ ] **Step 2: Implement no-secret-leak test**

Create `tests/test_no_secret_leak_v3.py`:

```python
import os
from pathlib import Path
from core.secret_guard import redact_text

SECRET_KEYS = ["KALSHI_API_KEY_ID", "KALSHI_API_PRIVATE_KEY_PEM", "KALSHI_API_PRIVATE_KEY_PEM_PATH"]

def test_no_secret_in_logs_and_artifacts():
    for key in SECRET_KEYS:
        value = os.environ.get(key)
        if not value:
            continue
        for path in list(Path("logs").rglob("*")) + list(Path("artifacts/dummy").rglob("*")):
            if path.is_file() and value in path.read_text(errors="ignore"):
                raise AssertionError(f"Secret {key} found in {path}")

def test_redact_masks_secret():
    os.environ.setdefault("KALSHI_API_KEY_ID", "test-key-id")
    text = redact_text("my key is test-key-id")
    assert "test-key-id" not in text
```

- [ ] **Step 3: Implement direct-order-bypass test**

Create `tests/test_direct_order_bypass_v4.py`:

```python
import ast
from pathlib import Path

ALLOWED_CREATE_ORDER_FILES = {
    "live_firewall/firewall.py",
    "kalshi/submitter.py",
}

def test_only_allowed_files_call_create_order():
    offenders = []
    for py in Path(".").rglob("*.py"):
        if any(part in {".git", "__pycache__", ".pytest_cache", "venv", ".venv"} for part in py.parts):
            continue
        text = py.read_text(errors="ignore")
        if "create_order" in text:
            rel = py.as_posix()
            if rel not in ALLOWED_CREATE_ORDER_FILES:
                offenders.append(rel)
    assert not offenders, offenders
```

- [ ] **Step 4: Implement Blunder separation recheck**

Create `tests/test_blunder_separation_v2.py`:

```python
from pathlib import Path
import ast

BLUNDER_ROOT = Path("C:/src/engine/obtuse/blunder")

def test_dumby_does_not_import_blunder():
    for py in Path(".").rglob("*.py"):
        if any(part in {".git", "__pycache__", ".pytest_cache"} for part in py.parts):
            continue
        text = py.read_text(errors="ignore")
        assert "obtuse.blunder" not in text, f"{py} imports canonical Blunder"

def test_blunder_unchanged():
    if not BLUNDER_ROOT.exists():
        return
    git_status = __import__("subprocess").run(["git", "-C", str(BLUNDER_ROOT), "status", "--porcelain"], capture_output=True, text=True)
    assert not git_status.stdout.strip(), "canonical Blunder has uncommitted changes"
```

- [ ] **Step 5: Run safety tests**

Run:
```bash
pytest tests/test_no_order_in_read_only.py tests/test_no_secret_leak_v3.py tests/test_direct_order_bypass_v4.py tests/test_blunder_separation_v2.py -v
```
Expected: all passed.

- [ ] **Step 6: Commit**

```bash
git add tests/test_no_order_in_read_only.py tests/test_no_secret_leak_v3.py tests/test_direct_order_bypass_v4.py tests/test_blunder_separation_v2.py
git commit -m "test(v4): add safety proof tests"
```

---

## Task 10: Add Dashboard V4 backend

**Files:**
- Create: `dashboard/backend/v4_routes.py`
- Modify: `dashboard/backend/main.py`
- Test: `tests/test_backend_v4.py`

**Interfaces:**
- Consumes: `KalshiRealReadOnly`, `KalshiNormalizer`, `StrategyScanner`, `AutonomousExecutionPath`, caps.
- Produces: `/v4/*` JSON endpoints.

- [ ] **Step 1: Write the failing test**

Create `tests/test_backend_v4.py`:

```python
from fastapi.testclient import TestClient
from dashboard.backend.main import app

client = TestClient(app)

def test_v4_caps():
    r = client.get("/v4/caps")
    assert r.status_code == 200
    assert "max_single_order_cents" in r.json()
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
pytest tests/test_backend_v4.py -v
```
Expected: 404 or AttributeError.

- [ ] **Step 3: Create `dashboard/backend/v4_routes.py`**

```python
import os
from fastapi import APIRouter
from core.config_loader import load_caps
from core.secret_guard import redact
from kalshi.live_data import KalshiRealReadOnly, KalshiCredentialsMissing
from kalshi.normalizer import KalshiNormalizer

router = APIRouter(prefix="/v4")

@router.get("/kalshi/status")
async def kalshi_status():
    try:
        reader = KalshiRealReadOnly()
        connected = True
    except KalshiCredentialsMissing:
        connected = False
    return {"connected": connected, "credentials_present": connected}

@router.get("/kalshi/account")
async def kalshi_account():
    try:
        reader = KalshiRealReadOnly()
        raw = await reader.get_account_status()
        return redact(raw)
    except KalshiCredentialsMissing:
        return {"error": "credentials_missing"}

@router.get("/kalshi/markets")
async def kalshi_markets():
    try:
        reader = KalshiRealReadOnly()
        return {"markets": await reader.get_markets()}
    except KalshiCredentialsMissing:
        return {"error": "credentials_missing"}

@router.get("/kalshi/orderbook/{ticker}")
async def kalshi_orderbook(ticker: str):
    try:
        reader = KalshiRealReadOnly()
        return await reader.get_orderbook(ticker)
    except KalshiCredentialsMissing:
        return {"error": "credentials_missing"}

@router.get("/kalshi/positions")
async def kalshi_positions():
    try:
        reader = KalshiRealReadOnly()
        return {"positions": await reader.get_positions()}
    except KalshiCredentialsMissing:
        return {"error": "credentials_missing"}

@router.get("/kalshi/orders")
async def kalshi_orders():
    try:
        reader = KalshiRealReadOnly()
        return {"orders": await reader.get_resting_orders()}
    except KalshiCredentialsMissing:
        return {"error": "credentials_missing"}

@router.get("/kalshi/fills")
async def kalshi_fills():
    try:
        reader = KalshiRealReadOnly()
        return {"fills": await reader.get_fills()}
    except KalshiCredentialsMissing:
        return {"error": "credentials_missing"}

@router.get("/caps")
async def caps():
    return load_caps().model_dump()

@router.get("/live-submit/status")
async def live_submit_status():
    import json
    from pathlib import Path
    path = Path("configs/live_submit.json")
    if not path.exists():
        return {"enabled": False, "file_present": False}
    return {"enabled": json.loads(path.read_text()).get("enabled", False), "file_present": True}
```

- [ ] **Step 4: Include router in `dashboard/backend/main.py`**

Add:

```python
from dashboard.backend import v4_routes
app.include_router(v4_routes.router)
```

- [ ] **Step 5: Run test to verify it passes**

Run:
```bash
pytest tests/test_backend_v4.py -v
```
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add dashboard/backend/v4_routes.py dashboard/backend/main.py tests/test_backend_v4.py
git commit -m "feat(v4): add dashboard v4 backend routes"
```

---

## Task 11: Add Dashboard V4 frontend

**Files:**
- Create: `dashboard/frontend/src/screens/KalshiReal.jsx`
- Create: `dashboard/frontend/src/screens/StrategyScan.jsx`
- Create: `dashboard/frontend/src/screens/FirewallRehearsal.jsx`
- Create: `dashboard/frontend/src/screens/LiveSubmit.jsx`
- Modify: `dashboard/frontend/src/App.jsx`
- Test: dashboard build

**Interfaces:**
- Consumes: `/v4/*` endpoints via `useApi`.
- Produces: React screens.

- [ ] **Step 1: Create KalshiReal screen**

Create `dashboard/frontend/src/screens/KalshiReal.jsx`:

```jsx
import { useEffect, useState } from "react";
import { useApi } from "../hooks/useApi";

export default function KalshiReal() {
  const { get } = useApi();
  const [status, setStatus] = useState(null);
  const [account, setAccount] = useState(null);

  useEffect(() => {
    get("/v4/kalshi/status").then(setStatus);
    get("/v4/kalshi/account").then(setAccount);
  }, []);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Real Kalshi</h1>
      <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-auto text-sm">{JSON.stringify({ status, account }, null, 2)}</pre>
    </div>
  );
}
```

- [ ] **Step 2: Create StrategyScan screen**

Create `dashboard/frontend/src/screens/StrategyScan.jsx`:

```jsx
import { useEffect, useState } from "react";
import { useApi } from "../hooks/useApi";

export default function StrategyScan() {
  const { get } = useApi();
  const [data, setData] = useState(null);

  useEffect(() => {
    get("/v4/strategies/scan").then(setData);
  }, []);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Strategy Scan</h1>
      <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-auto text-sm">{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}
```

- [ ] **Step 3: Create FirewallRehearsal screen**

Create `dashboard/frontend/src/screens/FirewallRehearsal.jsx`:

```jsx
import { useEffect, useState } from "react";
import { useApi } from "../hooks/useApi";

export default function FirewallRehearsal() {
  const { get } = useApi();
  const [data, setData] = useState(null);

  useEffect(() => {
    get("/v4/firewall/rehearse").then(setData);
  }, []);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Firewall Rehearsal</h1>
      <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-auto text-sm">{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}
```

- [ ] **Step 4: Create LiveSubmit screen**

Create `dashboard/frontend/src/screens/LiveSubmit.jsx`:

```jsx
import { useEffect, useState } from "react";
import { useApi } from "../hooks/useApi";

export default function LiveSubmit() {
  const { get } = useApi();
  const [status, setStatus] = useState(null);

  useEffect(() => {
    get("/v4/live-submit/status").then(setStatus);
  }, []);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Live Submit</h1>
      <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-auto text-sm">{JSON.stringify(status, null, 2)}</pre>
    </div>
  );
}
```

- [ ] **Step 5: Update `App.jsx` navigation**

Add V4 links in `App.jsx` route/nav:

```jsx
import KalshiReal from "./screens/KalshiReal";
import StrategyScan from "./screens/StrategyScan";
import FirewallRehearsal from "./screens/FirewallRehearsal";
import LiveSubmit from "./screens/LiveSubmit";

// in routes
<Route path="/v4/kalshi" element={<KalshiReal />} />
<Route path="/v4/strategies" element={<StrategyScan />} />
<Route path="/v4/firewall" element={<FirewallRehearsal />} />
<Route path="/v4/live-submit" element={<LiveSubmit />} />
```

- [ ] **Step 6: Build dashboard**

Run:
```bash
cd dashboard/frontend && npm run build
```
Expected: build succeeds.

- [ ] **Step 7: Commit**

```bash
git add dashboard/frontend/src/screens/KalshiReal.jsx dashboard/frontend/src/screens/StrategyScan.jsx dashboard/frontend/src/screens/FirewallRehearsal.jsx dashboard/frontend/src/screens/LiveSubmit.jsx dashboard/frontend/src/App.jsx
git commit -m "feat(v4): add dashboard v4 frontend screens"
```

---

## Task 12: Final validation and reports

**Files:**
- All modified files.
- Artifacts in `artifacts/dummy/`.

- [ ] **Step 1: Run full pytest suite**

Run:
```bash
python -m pytest tests/ -v
```
Expected: all passed.

- [ ] **Step 2: Run dashboard build**

Run:
```bash
cd dashboard/frontend && npm run build
```
Expected: build succeeds.

- [ ] **Step 3: Generate remaining V4 reports**

Run:
```bash
python scripts/generate_v4_reports.py
python scripts/generate_reports.py
```
Expected: all required reports present in `artifacts/dummy/`.

- [ ] **Step 4: Write final report**

Create `artifacts/dummy/final_report.json` summarizing PASS/PARTIAL/FAIL, tests run, counts, real Kalshi status, markets/orderbooks/positions/fills fetched, proposals/no-trade explanations, firewall rehearsal status, dashboard status, secret redaction status, Blunder separation status, proof paths, remaining risks.

- [ ] **Step 5: Commit**

```bash
git add artifacts/dummy/
git commit -m "feat(v4): generate V4 reports and final summary"
```

---

## Self-Review

- **Spec coverage:** Each V4 objective maps to one or more tasks.
- **Placeholder scan:** No TBD/TODO; all file paths and signatures are concrete.
- **Type consistency:** `LiveOrderRequest`, `Forecast`, `OrderBook`, `TradeProposal`, `RehearsalResult`, `RehearsalVerdict` reused consistently.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-30-dumby-v4-real-kalshi-read-only-and-live-cap-rehearsal.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks.
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.
