# Phase C: Strategy Intelligence + Hybrid Disagreement Engine

**Goal:** Add LLM critique to strategy scan results, enrich no-trade reasoning, and build a dual-model disagreement engine that downgrades confidence when DeepSeek and Minimax diverge.

---

## Global Constraints (Phase C)

- Do not modify Blunder or rename Dummy.
- No live order submission.
- No secrets in prompts, logs, or artifacts.
- Caps and live-submit config are read-only.
- LLM outputs remain within the approved value-object boundary.

---

## Files to Create / Modify

### Create

1. `strategies/critique.py`
2. `strategies/intelligence.py`
3. `strategies/disagreement.py`

### Modify

4. `core/ontology.py` — add `StrategyCritique`, `NoTradeReason`, `TradeProposalDraft`, `HybridReviewResult`.
5. `strategies/scan.py` — add optional `critique` and `no_trade_reason` fields to `StrategyScanResult`.

---

## Interfaces

### `core/ontology.py` additions

```python
class StrategyCritique(BaseModel):
    strategy_family: str
    market_ticker: str
    contract_ticker: str
    verdict: str  # "proceed", "warn", "block"
    edge_assessment: str
    risk_assessment: str
    confidence_adjustment: Decimal = Decimal("0")
    reasoning: str
    timestamp: datetime
    proof_reference: str

class NoTradeReason(BaseModel):
    market_ticker: str
    contract_ticker: str
    reason: str
    contributing_factors: list[str] = Field(default_factory=list)
    model_summary: str
    timestamp: datetime
    proof_reference: str

class TradeProposalDraft(BaseModel):
    market_ticker: str
    contract_ticker: str
    side: str
    price_cents: int
    size: int
    reasoning: str
    timestamp: datetime

class HybridReviewResult(BaseModel):
    task: str
    primary: dict
    secondary: dict
    agreement_score: Decimal
    confidence_adjustment: Decimal
    verdict: str
    reasoning: str
    timestamp: datetime
    proof_reference: str
```

### `strategies/critique.py`

```python
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
import json
from core.ontology import StrategyCritique
from model_router.router import ModelRouter
from model_router.tasks import ModelTask
from strategies.scan import StrategyScanResult

class StrategyCritiqueEngine:
    def __init__(self, router: ModelRouter | None = None):
        self.router = router or ModelRouter()

    async def critique(self, result: StrategyScanResult) -> StrategyCritique:
        prompt = (
            f"Strategy: {result.family}\n"
            f"Market: {result.market_ticker}/{result.contract_ticker}\n"
            f"Edge estimate: {result.edge_estimate}\n"
            f"Confidence: {result.confidence}\n"
            f"Liquidity: {result.liquidity_score}, Spread: {result.spread_score}, Settlement risk: {result.settlement_risk_score}\n"
            "Return JSON with verdict (proceed/warn/block), edge_assessment, risk_assessment, confidence_adjustment, reasoning."
        )
        envelope = await self.router.call(ModelTask.STRATEGY_CRITIQUE, prompt)
        data = json.loads(envelope.content) if envelope.content else {}
        return StrategyCritique(
            strategy_family=result.family,
            market_ticker=result.market_ticker,
            contract_ticker=result.contract_ticker,
            verdict=data.get("verdict", "warn"),
            edge_assessment=data.get("edge_assessment", ""),
            risk_assessment=data.get("risk_assessment", ""),
            confidence_adjustment=Decimal(str(data.get("confidence_adjustment", 0))),
            reasoning=data.get("reasoning", ""),
            timestamp=datetime.now(timezone.utc),
            proof_reference=envelope.proof_id,
        )
```

### `strategies/intelligence.py`

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from core.ontology import StrategyCritique, NoTradeReason, TradeProposalDraft
from model_router.router import ModelRouter
from model_router.tasks import ModelTask
from strategies.critique import StrategyCritiqueEngine
from strategies.scan import StrategyScanner, StrategyScanResult
import json
from datetime import datetime, timezone
from decimal import Decimal

@dataclass
class IntelligenceResult:
    scan_result: StrategyScanResult
    critique: StrategyCritique | None = None
    no_trade_reason: NoTradeReason | None = None
    draft: TradeProposalDraft | None = None

class StrategyIntelligence:
    def __init__(self, scanner: StrategyScanner | None = None, critique_engine: StrategyCritiqueEngine | None = None, router: ModelRouter | None = None):
        self.scanner = scanner or StrategyScanner()
        self.critique_engine = critique_engine or StrategyCritiqueEngine(router)

    async def evaluate(self, forecast, orderbook) -> list[IntelligenceResult]:
        scans = self.scanner.scan(forecast, orderbook)
        results: list[IntelligenceResult] = []
        for scan in scans:
            critique = await self.critique_engine.critique(scan)
            no_trade = None
            draft = None
            if scan.proposal is None:
                no_trade = await self._explain_no_trade(scan, forecast, critique)
            else:
                draft = TradeProposalDraft(
                    market_ticker=scan.proposal.market_ticker,
                    contract_ticker=scan.proposal.contract_ticker,
                    side=scan.proposal.side,
                    price_cents=scan.proposal.price_cents,
                    size=scan.proposal.size,
                    reasoning=critique.reasoning,
                    timestamp=datetime.now(timezone.utc),
                )
            results.append(IntelligenceResult(scan, critique, no_trade, draft))
        return results

    async def _explain_no_trade(self, scan: StrategyScanResult, forecast, critique: StrategyCritique) -> NoTradeReason:
        prompt = (
            f"Strategy {scan.family} returned no trade for {scan.market_ticker}. "
            f"Existing reason: {scan.no_trade_reason}. Critique: {critique.reasoning}. "
            "Return JSON with reason and contributing_factors."
        )
        envelope = await self.router.call(ModelTask.NO_TRADE_REASON, prompt)
        data = json.loads(envelope.content) if envelope.content else {}
        return NoTradeReason(
            market_ticker=scan.market_ticker,
            contract_ticker=scan.contract_ticker,
            reason=data.get("reason", scan.no_trade_reason or "unknown"),
            contributing_factors=data.get("contributing_factors", []),
            model_summary="hybrid_no_trade",
            timestamp=datetime.now(timezone.utc),
            proof_reference=envelope.proof_id,
        )
```

### `strategies/disagreement.py`

```python
from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from difflib import SequenceMatcher
from model_router.router import ModelRouter
from model_router.tasks import ModelTask

class HybridDisagreementEngine:
    def __init__(self, router: ModelRouter | None = None):
        self.router = router or ModelRouter()

    async def review(self, task: ModelTask, prompt: str, context: dict | None = None) -> dict:
        primary = await self.router.call(task, prompt, context)
        secondary = await self.router.call(task, prompt, context)
        score = self._agreement(primary.content, secondary.content)
        adjustment = Decimal("0") if score > Decimal("0.8") else Decimal("-0.15") if score > Decimal("0.5") else Decimal("-0.3")
        verdict = "agree" if score > Decimal("0.8") else "disagree"
        return {
            "task": task.value,
            "primary": {"provider": primary.decision.provider_name, "content": primary.content},
            "secondary": {"provider": secondary.decision.provider_name, "content": secondary.content},
            "agreement_score": score,
            "confidence_adjustment": adjustment,
            "verdict": verdict,
            "reasoning": f"agreement_score={score}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "proof_reference": str(uuid.uuid4()),
        }

    def _agreement(self, a: str, b: str) -> Decimal:
        return Decimal(str(round(SequenceMatcher(None, a, b).ratio(), 4)))
```

### `strategies/scan.py` modification

Add fields to `StrategyScanResult`:

```python
@dataclass
class StrategyScanResult:
    family: str
    market_ticker: str
    contract_ticker: str
    edge_estimate: float
    confidence: float
    liquidity_score: float
    spread_score: float
    settlement_risk_score: float
    proposal: Optional[TradeProposal] = None
    no_trade_reason: Optional[str] = None
    critique: Optional[Any] = None
    raw_notes: dict[str, Any] = field(default_factory=dict)
```

---

## Tests

Create:

- `tests/test_strategy_intelligence.py`
- `tests/test_strategy_critique.py`
- `tests/test_hybrid_disagreement_engine.py`

Example `tests/test_strategy_critique.py`:

```python
import pytest
from strategies.critique import StrategyCritiqueEngine
from strategies.scan import StrategyScanResult

@pytest.mark.asyncio
async def test_critique_returns_structured_result():
    engine = StrategyCritiqueEngine()
    scan = StrategyScanResult(
        family="probability_disagreement",
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        edge_estimate=0.01,
        confidence=0.6,
        liquidity_score=0.7,
        spread_score=0.8,
        settlement_risk_score=0.2,
    )
    critique = await engine.critique(scan)
    assert critique.strategy_family == "probability_disagreement"
    assert critique.verdict in {"proceed", "warn", "block"}
    assert critique.proof_reference
```

Example `tests/test_hybrid_disagreement_engine.py`:

```python
import pytest
from model_router.tasks import ModelTask
from strategies.disagreement import HybridDisagreementEngine

@pytest.mark.asyncio
async def test_mock_disagreement_review():
    engine = HybridDisagreementEngine()
    result = await engine.review(ModelTask.FORECAST_OPINION, "What is the probability?")
    assert "agreement_score" in result
    assert "confidence_adjustment" in result
```

---

## Phase C Validation

```bash
cd /c/src/engine/dummy
python -m pytest tests/test_strategy_intelligence.py tests/test_strategy_critique.py tests/test_hybrid_disagreement_engine.py -v
```

Expected: all pass using mock fallback.
```

---