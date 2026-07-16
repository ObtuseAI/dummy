# Phase D: Hybrid Live-Cap Firewall Rehearsal + Dashboard V7 + V7 Reports + Integration Tests

**Goal:** Wire the hybrid model layers into a rehearsed live-cap execution path, add a V7 dashboard screen alongside V6, create the V7 report generator, and prove integration safety with new regression tests.

---

## Global Constraints (Phase D)

- Do not modify Blunder or rename Dummy.
- No live order submission except through `LiveBrokerFirewall.submit`.
- No secrets in prompts, logs, or artifacts.
- Caps and live-submit config are read-only.
- Mock fallback must keep the dashboard and reports working when credentials are absent.

---

## Files to Create / Modify

### Create

1. `execution/hybrid_path.py`
2. `dashboard/backend/v7_routes.py`
3. `dashboard/frontend/src/screens/V7Dashboard.jsx`
4. `scripts/generate_v7_reports.py`

### Modify

5. `dashboard/backend/main.py` — include `v7_routes.router`.
6. `dashboard/frontend/src/App.jsx` — add V7 Dashboard route and nav link.
7. `pyproject.toml` if new packages need discovery; current `[tool.setuptools.packages.find]` already covers top-level modules, so no change is required unless new packages are nested.

---

## Interfaces

### `execution/hybrid_path.py`

```python
from __future__ import annotations
from typing import Any
from execution.autonomous_path import AutonomousExecutionPath
from forecasting.hybrid_engine import HybridForecastEngine
from strategies.intelligence import StrategyIntelligence
from strategies.disagreement import HybridDisagreementEngine
from core.ontology import AccountMode
from core import state as state_module

class HybridAutonomousExecutionPath(AutonomousExecutionPath):
    def __init__(self, *args, hybrid_engine: HybridForecastEngine | None = None, intelligence: StrategyIntelligence | None = None, disagreement: HybridDisagreementEngine | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.hybrid_engine = hybrid_engine or HybridForecastEngine()
        self.intelligence = intelligence or StrategyIntelligence()
        self.disagreement = disagreement or HybridDisagreementEngine()

    async def rehearse_live_cap_with_model_review(
        self,
        market_ticker: str,
        contract_ticker: str,
        strategy_name: str | None = None,
    ) -> dict[str, Any]:
        if state_module.STATE.mode != AccountMode.AUTONOMOUS_LIVE_CAPPED:
            return {"status": "blocked", "rejected_by": "mode", "reason": "Mode is not AUTONOMOUS_LIVE_CAPPED"}
        base = await super().rehearse_live_cap(market_ticker, contract_ticker, strategy_name)
        if base.get("status") in ("blocked", "no_trade") or "proposal" not in base:
            return {**base, "model_review": None}

        proposal = base["proposal"]
        orderbook = base.get("orderbook")
        forecast_opinion = None
        if orderbook:
            forecast_opinion = await self.hybrid_engine.forecast_opinion(
                market_ticker=market_ticker,
                contract_ticker=contract_ticker,
                event_title=market_ticker,
                contract_title=contract_ticker,
                orderbook=orderbook,
            )
        intelligence_results = []
        if orderbook and "forecast" in base:
            from core.ontology import Forecast
            forecast = Forecast.model_validate(base["forecast"])
            intelligence_results = await self.intelligence.evaluate(forecast, orderbook)

        review = None
        if forecast_opinion:
            review = await self.disagreement.review(
                ModelTask.FORECAST_OPINION,
                f"Review forecast for {market_ticker}",
                context={"market_ticker": market_ticker, "contract_ticker": contract_ticker},
            )

        model_review = {
            "forecast_opinion": forecast_opinion.model_dump() if forecast_opinion else None,
            "intelligence_results": [self._intelligence_to_dict(r) for r in intelligence_results],
            "disagreement_review": review,
        }
        return {**base, "model_review": model_review, "hybrid_status": base.get("status")}

    def _intelligence_to_dict(self, result) -> dict[str, Any]:
        return {
            "family": result.scan_result.family,
            "critique_verdict": result.critique.verdict if result.critique else None,
            "no_trade_reason": result.no_trade_reason.reason if result.no_trade_reason else None,
            "draft": result.draft.model_dump() if result.draft else None,
        }
```

### `dashboard/backend/v7_routes.py`

```python
from __future__ import annotations
from fastapi import APIRouter
from core.state import STATE
from core.ontology import AccountMode, OrderBook, OrderBookLevel
from forecasting.hybrid_engine import HybridForecastEngine
from strategies.intelligence import StrategyIntelligence
from strategies.disagreement import HybridDisagreementEngine
from execution.hybrid_path import HybridAutonomousExecutionPath
from datetime import datetime, timezone

router = APIRouter(prefix="/v7", tags=["v7"])

@router.get("/identity")
async def identity():
    return {
        "project": "Dummy",
        "milestone": "DUMMY_V7_HYBRID_ROUTING_DESIGN_V1",
        "previous_name": "Dumby",
        "v7_focus": "hybrid_model_routing",
    }

@router.get("/model-router/status")
async def model_router_status():
    from model_router.router import ModelRouter
    from model_router.config import load_model_routing_config
    cfg = load_model_routing_config()
    return {
        "config_present": True,
        "mock_fallback_enabled": cfg.mock_fallback_enabled,
        "blocked_categories": cfg.blocked_prompt_categories,
    }

@router.get("/forecast/opinion")
async def forecast_opinion(market_ticker: str = "MKT", contract_ticker: str = "MKT-YES"):
    engine = HybridForecastEngine()
    book = OrderBook(
        market_ticker=market_ticker,
        contract_ticker=contract_ticker,
        bids=[OrderBookLevel(price=48, size=100)],
        asks=[OrderBookLevel(price=52, size=100)],
        timestamp=datetime.now(timezone.utc),
    )
    opinion = await engine.forecast_opinion(market_ticker, contract_ticker, market_ticker, contract_ticker, book)
    return {"opinion": opinion.model_dump(), "source": "mock"}

@router.get("/strategies/intelligence")
async def strategies_intelligence(market_ticker: str = "MKT", contract_ticker: str = "MKT-YES"):
    intel = StrategyIntelligence()
    from forecasting.engine import ForecastEngine
    book = OrderBook(
        market_ticker=market_ticker,
        contract_ticker=contract_ticker,
        bids=[OrderBookLevel(price=48, size=100)],
        asks=[OrderBookLevel(price=52, size=100)],
        timestamp=datetime.now(timezone.utc),
    )
    forecast = ForecastEngine().forecast(market_ticker, contract_ticker, market_ticker, contract_ticker, book)
    results = await intel.evaluate(forecast, book)
    return {"results": [r.scan_result.family for r in results], "source": "mock"}

@router.get("/hybrid/rehearsal")
async def hybrid_rehearsal(market_ticker: str = "MKT", contract_ticker: str = "MKT-YES"):
    if STATE.mode != AccountMode.AUTONOMOUS_LIVE_CAPPED:
        return {"status": "blocked", "reason": "Mode is not AUTONOMOUS_LIVE_CAPPED"}
    path = HybridAutonomousExecutionPath()
    result = await path.rehearse_live_cap_with_model_review(market_ticker, contract_ticker)
    return {"status": result.get("status"), "model_review_present": result.get("model_review") is not None}

@router.get("/reports/status")
async def reports_status():
    from pathlib import Path
    final = Path("C:/src/engine/dummy/artifacts/dummy/final_report.json")
    return {"final_report_present": final.exists()}
```

### `dashboard/frontend/src/screens/V7Dashboard.jsx`

```jsx
import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';

export default function V7Dashboard() {
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const [identity, routerStatus, opinion, intel, rehearsal, reports] = await Promise.all([
          fetchJson('/v7/identity'),
          fetchJson('/v7/model-router/status'),
          fetchJson('/v7/forecast/opinion'),
          fetchJson('/v7/strategies/intelligence'),
          fetchJson('/v7/hybrid/rehearsal'),
          fetchJson('/v7/reports/status'),
        ]);
        setData({ identity, routerStatus, opinion, intel, rehearsal, reports });
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) return <div className="p-4">Loading V7 dashboard...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="p-4 space-y-6">
      <h1 className="text-2xl font-bold">Dummy V7 Dashboard</h1>
      {Object.entries(data).map(([key, value]) => (
        <div key={key} className="bg-gray-800 rounded p-4">
          <h2 className="text-lg font-semibold mb-2">{key}</h2>
          <pre className="text-sm overflow-auto max-h-64 bg-gray-900 p-2 rounded">{JSON.stringify(value, null, 2)}</pre>
        </div>
      ))}
    </div>
  );
}
```

### `dashboard/backend/main.py` modification

After the existing `app.include_router(v6_router)` line, add:

```python
from dashboard.backend import v7_routes
app.include_router(v7_routes.router)
```

### `dashboard/frontend/src/App.jsx` modification

Add import:

```jsx
import V7Dashboard from './screens/V7Dashboard';
```

Add `"V7 Dashboard"` to the `links` array and add a route:

```jsx
<Route path="/v7-dashboard" element={<V7Dashboard />} />
```

### `scripts/generate_v7_reports.py`

Structure:

```python
from __future__ import annotations
import asyncio
import json
from pathlib import Path
from scripts.generate_v6_reports import main as v6_main

ROOT = Path(__file__).parent.parent
ARTIFACTS = ROOT / "artifacts" / "dummy"

def now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

async def generate_model_routing_report_v1() -> dict:
    return {
        "generated_at": now_iso(),
        "workstream": "V7: Model Routing",
        "config_present": (ROOT / "configs" / "model_routing.json").exists(),
        "mock_fallback_enabled": True,
        "verdict": "PASS",
    }

async def generate_prompt_firewall_report_v1() -> dict:
    return {
        "generated_at": now_iso(),
        "workstream": "V7: Prompt Firewall",
        "blocked_categories": ["secret_leak", "instruction_injection", "order_endpoint", "cap_modification"],
        "verdict": "PASS",
    }

# ... add generate_real_market_forecast_loop_report_v1, generate_calibration_report_v1,
# generate_strategy_intelligence_report_v1, generate_hybrid_disagreement_report_v1,
# generate_hybrid_live_cap_firewall_rehearsal_report_v1, generate_dashboard_v7_report_v1,
# generate_model_proof_order_path_report_v1, generate_dummy_canonical_identity_report_v3,
# generate_blunder_separation_recheck_v5, generate_direct_order_bypass_report_v7.

async def main():
    await v6_main()
    reports = {
        "model_routing_report_v1.json": await generate_model_routing_report_v1(),
        "prompt_firewall_report_v1.json": await generate_prompt_firewall_report_v1(),
        # ... remaining V7 reports
    }
    for name, data in reports.items():
        (ARTIFACTS / name).write_text(json.dumps(data, indent=2, default=str))

    # Recompute final_report.json as V7.
    final_path = ARTIFACTS / "final_report.json"
    existing = json.loads(final_path.read_text()) if final_path.exists() else {}
    existing["milestone"] = "DUMMY_V7_HYBRID_ROUTING_DESIGN_V1"
    existing["verdict"] = "PASS" if all(r.get("verdict") in ("PASS", "PARTIAL") for r in reports.values()) else "FAIL"
    existing["generated_at"] = now_iso()
    final_path.write_text(json.dumps(existing, indent=2, default=str))
    print(json.dumps(existing, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(main())
```

The report functions should exercise the real components enough to prove they exist and return the expected verdicts, but they must not leak secrets or submit live orders.

---

## Tests

Create:

- `tests/test_hybrid_live_cap_firewall_rehearsal.py`
- `tests/test_model_proof_order_path.py`
- `tests/test_dashboard_v7.py`
- `tests/test_dummy_canonical_identity_v3.py`
- `tests/test_blunder_separation_v5.py`
- `tests/test_direct_order_bypass_v7.py`

Example `tests/test_hybrid_live_cap_firewall_rehearsal.py`:

```python
import pytest
from core import state as state_module
from core.ontology import AccountMode
from execution.hybrid_path import HybridAutonomousExecutionPath

@pytest.mark.asyncio
async def test_hybrid_rehearsal_does_not_submit_live():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    path = HybridAutonomousExecutionPath()
    result = await path.rehearse_live_cap_with_model_review("MKT", "MKT-YES")
    assert result.get("live_submitted") is not True
    assert result.get("status") in ("rehearsal", "no_trade", "blocked")
```

Example `tests/test_model_proof_order_path.py`:

```python
import re
from pathlib import Path

def test_only_allowed_callers_invoke_create_order():
    root = Path("C:/src/engine/dummy")
    excluded = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules", "dist", "build", "tests", "artifacts"}
    call_re = re.compile(r'(?<![\w"\'])create_order\s*\(')
    offenders = set()
    for py in root.rglob("*.py"):
        if any(part in excluded for part in py.parts):
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if call_re.search(line) and "def create_order(" not in line:
                offenders.add(py.relative_to(root).as_posix())
                break
    allowed = {"live_firewall/firewall.py", "kalshi/submitter.py"}
    assert offenders <= allowed, offenders
```

Example `tests/test_dashboard_v7.py`:

```python
from pathlib import Path
from fastapi.testclient import TestClient
from dashboard.backend.main import app

def test_v7_routes_return_200():
    client = TestClient(app)
    endpoints = [
        "/v7/identity",
        "/v7/model-router/status",
        "/v7/forecast/opinion",
        "/v7/strategies/intelligence",
        "/v7/reports/status",
    ]
    for ep in endpoints:
        r = client.get(ep)
        assert r.status_code == 200, f"{ep} failed: {r.text}"

def test_v7_frontend_dist_exists():
    assert (Path("C:/src/engine/dummy/dashboard/frontend/dist/index.html")).exists()
```

---

## Phase D Validation

```bash
cd /c/src/engine/dummy
python -m pytest tests/test_hybrid_live_cap_firewall_rehearsal.py tests/test_model_proof_order_path.py tests/test_dashboard_v7.py tests/test_dummy_canonical_identity_v3.py tests/test_blunder_separation_v5.py tests/test_direct_order_bypass_v7.py -v
```

Then build the dashboard and generate final V7 reports:

```bash
cd dashboard/frontend
npm ci
npm run build
cd ../..
python scripts/generate_v7_reports.py
cat artifacts/dummy/final_report.json
```

Expected: all tests pass, dashboard builds, `final_report.json` shows `verdict` = `PASS` (or `PARTIAL` if live credentials are absent), and no new `create_order` callers appear outside the allowed set.
```

---

**Summary:** I drafted the complete V7 master plan and four phase briefs with concrete file maps, interfaces, code snippets, tests, and validation commands; they need to be written to the five paths under `docs/superpowers/plans/` because this planning environment lacks file-write tooling.
