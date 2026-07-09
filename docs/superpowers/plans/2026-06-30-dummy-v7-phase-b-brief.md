# Phase B: Real-Market Forecast Loop + Calibration Spine

**Goal:** Use the Phase A router to generate typed `ForecastOpinion` and `MarketThesis` objects from real Kalshi market snapshots, and build a calibration spine that scores forecasts against eventual settlements.

---

## Global Constraints (Phase B)

- Do not modify Blunder or rename Dummy.
- No live order submission.
- No secrets in prompts, logs, or artifacts.
- Caps and live-submit config are read-only.
- Missing model keys fall back to mock; missing Kalshi credentials fall back to mock snapshots.

---

## Files to Create / Modify

### Create

1. `forecasting/hybrid_engine.py`
2. `forecasting/real_market_loop.py`
3. `calibration/__init__.py`
4. `calibration/schema.py`
5. `calibration/spine.py`
6. `calibration/storage.py`

### Modify

7. `core/ontology.py` — add `ForecastOpinion`, `CalibrationNote`, `MarketThesis`.
8. `data/calibration/` directory (for working calibration JSON).
9. `artifacts/dummy/calibration/` directory (for generated calibration reports).

---

## Interfaces

### `core/ontology.py` additions

```python
class ForecastOpinion(BaseModel):
    market_ticker: str
    contract_ticker: str
    forecast_reference: str
    market_implied_probability: Decimal
    dummy_probability: Decimal
    probability_delta: Decimal
    confidence_score: Decimal
    uncertainty_band: tuple[Decimal, Decimal]
    model_summary: str
    reasoning: str
    no_trade_reason: str | None = None
    calibration_notes: list[str] = Field(default_factory=list)
    timestamp: datetime
    expiration: datetime
    proof_reference: str

class CalibrationNote(BaseModel):
    market_ticker: str
    contract_ticker: str
    note: str
    source: str
    timestamp: datetime

class MarketThesis(BaseModel):
    market_ticker: str
    contract_ticker: str
    thesis: str
    bullish_signals: list[str] = Field(default_factory=list)
    bearish_signals: list[str] = Field(default_factory=list)
    source: str
    timestamp: datetime
```

### `forecasting/hybrid_engine.py`

```python
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from core.ontology import ForecastOpinion, MarketThesis, OrderBook, Forecast
from forecasting.engine import ForecastEngine
from model_router.router import ModelRouter
from model_router.tasks import ModelTask

class HybridForecastEngine:
    def __init__(self, base_engine: ForecastEngine | None = None, router: ModelRouter | None = None):
        self.base_engine = base_engine or ForecastEngine()
        self.router = router or ModelRouter()

    async def forecast_opinion(
        self,
        market_ticker: str,
        contract_ticker: str,
        event_title: str,
        contract_title: str,
        orderbook: OrderBook,
    ) -> ForecastOpinion:
        base = self.base_engine.forecast(market_ticker, contract_ticker, event_title, contract_title, orderbook)
        prompt = self._build_forecast_prompt(base, orderbook)
        envelope = await self.router.call(
            ModelTask.FORECAST_OPINION,
            prompt,
            context={"market_ticker": market_ticker, "contract_ticker": contract_ticker},
        )
        return self._parse_opinion(envelope.content, base)

    def _build_forecast_prompt(self, base: Forecast, orderbook: OrderBook) -> str:
        return (
            f"Market: {base.market_ticker}\n"
            f"Contract: {base.contract_ticker}\n"
            f"Market-implied probability: {base.market_implied_probability}\n"
            f"Dummy base probability: {base.dummy_probability}\n"
            f"Edge after fees: {base.edge_after_fees}\n"
            f"Orderbook best bid/ask: {orderbook.bids[-1].price if orderbook.bids else None} / {orderbook.asks[0].price if orderbook.asks else None}\n"
            "Return a JSON object with keys: dummy_probability, confidence_score, uncertainty_band [low, high], reasoning, no_trade_reason (optional), calibration_notes (list)."
        )

    def _parse_opinion(self, content: str, base: Forecast) -> ForecastOpinion:
        try:
            data = json.loads(content)
        except Exception:
            data = {}
        dummy_prob = Decimal(str(data.get("dummy_probability", base.dummy_probability)))
        confidence = Decimal(str(data.get("confidence_score", base.confidence_score)))
        band = data.get("uncertainty_band") or [float(max(Decimal("0"), dummy_prob - Decimal("0.05"))), float(min(Decimal("1"), dummy_prob + Decimal("0.05")))]
        return ForecastOpinion(
            market_ticker=base.market_ticker,
            contract_ticker=base.contract_ticker,
            forecast_reference=base.proof_reference,
            market_implied_probability=base.market_implied_probability,
            dummy_probability=dummy_prob,
            probability_delta=(dummy_prob - base.market_implied_probability).quantize(Decimal("0.0001")),
            confidence_score=confidence,
            uncertainty_band=(Decimal(str(band[0])), Decimal(str(band[1]))),
            model_summary="hybrid_router",
            reasoning=str(data.get("reasoning", "no model reasoning")),
            no_trade_reason=data.get("no_trade_reason"),
            calibration_notes=data.get("calibration_notes", []),
            timestamp=datetime.now(timezone.utc),
            expiration=datetime.now(timezone.utc) + timedelta(hours=1),
            proof_reference=f"hybrid_forecast_{base.market_ticker}_{datetime.now(timezone.utc).isoformat()}",
        )

    async def market_thesis(self, market_ticker: str, contract_ticker: str, context: dict[str, Any]) -> MarketThesis:
        prompt = f"Write a concise market thesis for {market_ticker}/{contract_ticker}. Context: {context}"
        envelope = await self.router.call(ModelTask.MARKET_THESIS, prompt, context=context)
        try:
            data = json.loads(envelope.content)
        except Exception:
            data = {}
        return MarketThesis(
            market_ticker=market_ticker,
            contract_ticker=contract_ticker,
            thesis=data.get("thesis", "no thesis"),
            bullish_signals=data.get("bullish_signals", []),
            bearish_signals=data.get("bearish_signals", []),
            source=envelope.decision.provider_name,
            timestamp=datetime.now(timezone.utc),
        )
```

### `forecasting/real_market_loop.py`

```python
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from core.ontology import ForecastOpinion
from forecasting.hybrid_engine import HybridForecastEngine
from kalshi.live_data import KalshiRealReadOnly, KalshiCredentialsMissing
from kalshi.normalizer import KalshiNormalizer
from calibration.storage import CalibrationStorage

class RealMarketForecastLoop:
    def __init__(
        self,
        hybrid_engine: HybridForecastEngine | None = None,
        storage: CalibrationStorage | None = None,
    ):
        self.hybrid_engine = hybrid_engine or HybridForecastEngine()
        self.storage = storage or CalibrationStorage()
        self.credentials_present = False

    async def run(self, contract_tickers: list[str] | None = None) -> dict[str, Any]:
        try:
            reader = KalshiRealReadOnly()
            self.credentials_present = True
        except KalshiCredentialsMissing:
            return {"source": "mock", "opinions": [], "reason": "kalshi_credentials_missing"}
        normalizer = KalshiNormalizer()
        tickers = contract_tickers or ["KXELONMARS-99"]
        opinions: list[ForecastOpinion] = []
        try:
            for ticker in tickers:
                snapshot = await reader.get_full_snapshot(ticker)
                normalized = normalizer.normalize_full_snapshot(snapshot, ticker)
                market = normalized["markets"][0] if normalized["markets"] else None
                orderbook = normalized["orderbook"]
                opinion = await self.hybrid_engine.forecast_opinion(
                    market_ticker=orderbook.market_ticker,
                    contract_ticker=ticker,
                    event_title=market.title if market else ticker,
                    contract_title=ticker,
                    orderbook=orderbook,
                )
                opinions.append(opinion)
                self.storage.append_forecast(opinion)
        finally:
            await reader.close()
        return {"source": "live", "opinions": [o.model_dump() for o in opinions], "count": len(opinions)}
```

### `calibration/schema.py`

```python
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, Field

class ForecastRecord(BaseModel):
    market_ticker: str
    contract_ticker: str
    dummy_probability: Decimal
    confidence_score: Decimal
    uncertainty_band: tuple[Decimal, Decimal]
    timestamp: datetime
    proof_reference: str

class SettlementRecord(BaseModel):
    market_ticker: str
    contract_ticker: str
    outcome: int  # 0 or 1
    settled_at: datetime
    source: str

class CalibrationMetrics(BaseModel):
    market_ticker: str
    contract_ticker: str
    brier_score: float | None = None
    log_loss: float | None = None
    calibration_error: float | None = None
    coverage: float | None = None
    sample_count: int = 0
    generated_at: datetime = Field(default_factory=lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc))
```

### `calibration/spine.py`

```python
from __future__ import annotations
from decimal import Decimal
from math import log
from typing import Any
from calibration.schema import ForecastRecord, SettlementRecord, CalibrationMetrics

class CalibrationSpine:
    def score(self, forecasts: list[ForecastRecord], settlement: SettlementRecord) -> CalibrationMetrics:
        if not forecasts:
            return CalibrationMetrics(market_ticker=settlement.market_ticker, contract_ticker=settlement.contract_ticker, sample_count=0)
        p = float(forecasts[-1].dummy_probability)
        y = settlement.outcome
        brier = (p - y) ** 2
        logloss = -(y * log(max(p, 1e-9)) + (1 - y) * log(max(1 - p, 1e-9)))
        low, high = forecasts[-1].uncertainty_band
        coverage = 1 if Decimal(str(low)) <= Decimal(str(y)) <= Decimal(str(high)) else 0
        return CalibrationMetrics(
            market_ticker=settlement.market_ticker,
            contract_ticker=settlement.contract_ticker,
            brier_score=round(brier, 6),
            log_loss=round(logloss, 6),
            calibration_error=round(abs(p - y), 6),
            coverage=float(coverage),
            sample_count=len(forecasts),
        )
```

### `calibration/storage.py`

```python
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from calibration.schema import ForecastRecord, SettlementRecord

DATA_DIR = Path("data/calibration")
ARTIFACT_DIR = Path("artifacts/dummy/calibration")

class CalibrationStorage:
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        return self.data_dir / f"{name}.jsonl"

    def append_forecast(self, opinion: Any):
        record = ForecastRecord(
            market_ticker=opinion.market_ticker,
            contract_ticker=opinion.contract_ticker,
            dummy_probability=opinion.dummy_probability,
            confidence_score=opinion.confidence_score,
            uncertainty_band=opinion.uncertainty_band,
            timestamp=opinion.timestamp,
            proof_reference=opinion.proof_reference,
        )
        with self._path("forecasts").open("a") as f:
            f.write(record.model_dump_json() + "\n")

    def append_settlement(self, settlement: SettlementRecord):
        with self._path("settlements").open("a") as f:
            f.write(settlement.model_dump_json() + "\n")

    def load_forecasts(self, contract_ticker: str) -> list[ForecastRecord]:
        path = self._path("forecasts")
        if not path.exists():
            return []
        records = []
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                if data.get("contract_ticker") == contract_ticker:
                    records.append(ForecastRecord.model_validate(data))
        return records
```

---

## Tests

Create:

- `tests/test_real_market_forecast_loop.py`
- `tests/test_forecast_opinion_schema.py`
- `tests/test_calibration_spine.py`

Example `tests/test_real_market_forecast_loop.py`:

```python
import pytest
from forecasting.real_market_loop import RealMarketForecastLoop

@pytest.mark.asyncio
async def test_loop_mock_fallback_without_kalshi_creds():
    loop = RealMarketForecastLoop()
    result = await loop.run(["MOCK-YES"])
    assert result["source"] == "mock"
    assert result["opinions"] == []
```

Example `tests/test_calibration_spine.py`:

```python
from datetime import datetime, timezone
from decimal import Decimal
from calibration.schema import ForecastRecord, SettlementRecord
from calibration.spine import CalibrationSpine

def test_perfect_forecast_brier_zero():
    spine = CalibrationSpine()
    fc = ForecastRecord(
        market_ticker="MKT", contract_ticker="MKT-YES",
        dummy_probability=Decimal("1.0"), confidence_score=Decimal("0.9"),
        uncertainty_band=(Decimal("0.9"), Decimal("1.0")),
        timestamp=datetime.now(timezone.utc), proof_reference="p1",
    )
    settlement = SettlementRecord(market_ticker="MKT", contract_ticker="MKT-YES", outcome=1, settled_at=datetime.now(timezone.utc), source="test")
    metrics = spine.score([fc], settlement)
    assert metrics.brier_score == 0.0
    assert metrics.coverage == 1.0
```

---

## Phase B Validation

```bash
cd /c/src/engine/dummy
python -m pytest tests/test_real_market_forecast_loop.py tests/test_forecast_opinion_schema.py tests/test_calibration_spine.py -v
```

Expected: all pass, mock fallback works when Kalshi or model credentials are absent.
```

---