# MLB Monster S2 — Validation Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the three-head validation harness that grades any MLB engine's settled paper decisions — beat-the-close (contested-Brier, cluster-robust), full-surface calibration, and paper P&L — so every model head (S3+) is measured against a single honest bar from birth.

**Architecture:** A new pure module `autonomy/sports/mlb_validation.py` consumes settled `SportsObservation` rows (from the existing `SportsEvidenceLedger.rows()`) plus their realized `pnl_cents`, and reuses the contested-Brier + event-cluster-bootstrap machinery already in `autonomy/backtest.py`. It produces an `MlbEngineScorecard` per source with three head verdicts. No new data source, no live calls, no forecaster/model changes — this is measurement only, and it is offline (not gated on the StatsAPI terms-review that blocks S3).

**Tech Stack:** Python 3.11+, stdlib (`math`, `statistics`, `random`), `pytest`. Reuses `autonomy/backtest.py` (`_brier`, `CONTESTED_DISAGREEMENT`, `_cluster_bootstrap_mean_ci`) and `autonomy/stats.py` (`mean_ci95`).

## Global Constraints

- Python `>=3.11`; `from __future__ import annotations` at the top of every new module.
- Pure and offline: the harness reads settled decisions and computes scores. No network, no live StatsAPI, no ledger writes, no forecaster/model mutation.
- Reuse, do not duplicate: contested threshold is `autonomy.backtest.CONTESTED_DISAGREEMENT` (0.05); Brier is `autonomy.backtest._brier`; the event-cluster bootstrap is `autonomy.backtest._cluster_bootstrap_mean_ci`; mean CI is `autonomy.stats.mean_ci95`. Do not re-implement any of these.
- The primary head ("beat the close") is judged on the CONTESTED population only: decisions where `abs(model_probability - market_probability) >= CONTESTED_DISAGREEMENT`. A head is positive only when the cluster-bootstrap lower 95% bound of the model-minus-market Brier edge is `> 0` AND contested_n `>= MIN_CONTESTED_N` (import `autonomy.backtest.MIN_CONTESTED_N`, currently 20).
- Brier edge sign convention: `market_brier - model_brier` (positive = model beat the market). Match `autonomy/backtest.py`'s existing convention exactly.
- New code in `autonomy/sports/mlb_validation.py`; tests in `tests/test_autonomy_mlb_validation.py`. Do not modify `backtest.py`, `stats.py`, `simulation.py`, or any engine.
- Run the full suite with `python -m pytest -q` before the final commit; it must stay green (baseline after S1 merge: 4,669 passed, 0 skipped).
- Commit after every task with a `feat:`/`test:` message ending in `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: `HeadVerdict` and `MlbEngineScorecard` result types

**Files:**
- Create: `autonomy/sports/mlb_validation.py`
- Test: `tests/test_autonomy_mlb_validation.py`

**Interfaces:**
- Produces: `HeadVerdict` frozen dataclass (`name: str`, `passed: bool`, `metric: float | None`, `n: int`, `detail: dict[str, Any]`); `MlbEngineScorecard` frozen dataclass (`source: str`, `settled: int`, `beat_close: HeadVerdict`, `calibration: HeadVerdict`, `paper_pnl: HeadVerdict`, `is_champion_ready: bool`) where `is_champion_ready` is `beat_close.passed` (primary head governs promotion; the other two are sanity heads surfaced but not gating).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_mlb_validation.py
from __future__ import annotations

from autonomy.sports.mlb_validation import HeadVerdict, MlbEngineScorecard


def test_scorecard_champion_ready_tracks_primary_head_only():
    beat = HeadVerdict(name="beat_close", passed=True, metric=0.02, n=40, detail={})
    calib = HeadVerdict(name="calibration", passed=False, metric=-0.01, n=100, detail={})
    pnl = HeadVerdict(name="paper_pnl", passed=True, metric=150.0, n=100, detail={})
    card = MlbEngineScorecard(
        source="mlb_pa_sim", settled=100,
        beat_close=beat, calibration=calib, paper_pnl=pnl,
    )
    # Primary head (beat the close) alone gates champion readiness.
    assert card.is_champion_ready is True
    # A failed primary head blocks it regardless of the sanity heads.
    blocked = MlbEngineScorecard(
        source="x", settled=100,
        beat_close=HeadVerdict("beat_close", False, -0.01, 40, {}),
        calibration=calib, paper_pnl=pnl,
    )
    assert blocked.is_champion_ready is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_mlb_validation.py::test_scorecard_champion_ready_tracks_primary_head_only -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autonomy.sports.mlb_validation'`.

- [ ] **Step 3: Write minimal implementation**

```python
# autonomy/sports/mlb_validation.py
"""Three-head validation harness for MLB engines.

Grades a source's settled paper decisions on three independent heads:
  1. beat_close   - contested-Brier skill vs the market close (primary; the
                    money bar). Cluster-robust lower bound must clear zero.
  2. calibration  - full-surface Brier skill vs the market on all settled
                    decisions (a broad-calibration sanity guard).
  3. paper_pnl    - realized paper P&L (operational outcome).

Only the primary head gates champion readiness; the other two are surfaced so
a lucky contested streak or a mis-calibrated tail is visible. Pure and offline:
reads settled decisions, computes scores, writes nothing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class HeadVerdict:
    name: str
    passed: bool
    metric: float | None
    n: int
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MlbEngineScorecard:
    source: str
    settled: int
    beat_close: HeadVerdict
    calibration: HeadVerdict
    paper_pnl: HeadVerdict

    @property
    def is_champion_ready(self) -> bool:
        """Only the primary head (beat the close) gates promotion."""
        return self.beat_close.passed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autonomy_mlb_validation.py::test_scorecard_champion_ready_tracks_primary_head_only -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add autonomy/sports/mlb_validation.py tests/test_autonomy_mlb_validation.py
git commit -m "feat(mlb): validation scorecard result types"
```

---

### Task 2: A settled-decision input record and a per-source filter

**Files:**
- Modify: `autonomy/sports/mlb_validation.py`
- Test: `tests/test_autonomy_mlb_validation.py`

**Interfaces:**
- Produces: `SettledDecision` frozen dataclass (`source: str`, `market_type: str`, `event_cluster: str`, `model_probability: float`, `market_probability: float`, `result_yes: bool`, `pnl_cents: int | None`); `settled_decisions_for(rows, pnl_by_id, source) -> list[SettledDecision]` — filters an iterable of objects with the `SportsObservation` attribute shape to one source, keeping only rows whose `result_yes is not None`, attaching `pnl_cents` from a `{observation_id: pnl_cents}` map (None when absent).

Notes: `SportsObservation` (from `autonomy/sports/simulation.py`) exposes `observation_id`, `source`, `market_type`, `event_cluster`, `model_probability`, `market_probability`, `result_yes`. The harness takes any object with those attributes (duck-typed) so tests can use a lightweight stand-in and production can pass real rows.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_mlb_validation.py (append)
from dataclasses import dataclass as _dc

from autonomy.sports.mlb_validation import SettledDecision, settled_decisions_for


@_dc
class _Row:
    observation_id: str
    source: str
    market_type: str
    event_cluster: str
    model_probability: float
    market_probability: float
    result_yes: object  # bool | None


def test_settled_decisions_filters_source_and_unsettled():
    rows = [
        _Row("a", "mlb_pa_sim", "winner", "g1", 0.60, 0.52, True),
        _Row("b", "mlb_pa_sim", "winner", "g2", 0.40, 0.55, False),
        _Row("c", "mlb_gbm", "winner", "g1", 0.70, 0.52, True),   # other source
        _Row("d", "mlb_pa_sim", "total", "g3", 0.50, 0.50, None),  # unsettled
    ]
    out = settled_decisions_for(rows, {"a": 30, "b": -20}, "mlb_pa_sim")
    assert [d.event_cluster for d in out] == ["g1", "g2"]
    assert out[0].pnl_cents == 30 and out[1].pnl_cents == -20
    assert all(d.source == "mlb_pa_sim" for d in out)
    assert all(isinstance(d.result_yes, bool) for d in out)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_mlb_validation.py -k settled_decisions -v`
Expected: FAIL with `ImportError: cannot import name 'SettledDecision'`.

- [ ] **Step 3: Write minimal implementation**

```python
# autonomy/sports/mlb_validation.py (append)


@dataclass(frozen=True)
class SettledDecision:
    source: str
    market_type: str
    event_cluster: str
    model_probability: float
    market_probability: float
    result_yes: bool
    pnl_cents: int | None = None


def settled_decisions_for(
    rows: Any, pnl_by_id: dict[str, int], source: str,
) -> list[SettledDecision]:
    """Settled decisions for one source, with realized P&L attached."""
    out: list[SettledDecision] = []
    for row in rows:
        if row.source != source or row.result_yes is None:
            continue
        pnl = pnl_by_id.get(row.observation_id)
        out.append(SettledDecision(
            source=row.source,
            market_type=row.market_type,
            event_cluster=row.event_cluster,
            model_probability=float(row.model_probability),
            market_probability=float(row.market_probability),
            result_yes=bool(row.result_yes),
            pnl_cents=None if pnl is None else int(pnl),
        ))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autonomy_mlb_validation.py -k settled_decisions -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add autonomy/sports/mlb_validation.py tests/test_autonomy_mlb_validation.py
git commit -m "feat(mlb): settled-decision record + per-source filter"
```

---

### Task 3: The beat-the-close head (contested-Brier, cluster-robust)

**Files:**
- Modify: `autonomy/sports/mlb_validation.py`
- Test: `tests/test_autonomy_mlb_validation.py`

**Interfaces:**
- Consumes: `SettledDecision` (Task 2); `autonomy.backtest._brier`, `autonomy.backtest.CONTESTED_DISAGREEMENT`, `autonomy.backtest.MIN_CONTESTED_N`, `autonomy.backtest._cluster_bootstrap_mean_ci`.
- Produces: `beat_close_head(decisions) -> HeadVerdict`.

Notes: contested = `abs(model - market) >= CONTESTED_DISAGREEMENT`. For each contested decision compute the Brier edge `market_brier - model_brier` (positive = model better) and bucket it by `event_cluster`. The verdict passes iff `contested_n >= MIN_CONTESTED_N` AND the cluster-bootstrap lower 95% bound of the mean edge is `> 0`. `_cluster_bootstrap_mean_ci(edges_by_cluster)` returns a dict with a `"lower"` key (match `backtest.py`'s call site — inspect it and pass the same structure).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_mlb_validation.py (append)
from autonomy.sports.mlb_validation import beat_close_head


def _dec(cluster, model, market, result, pnl=0):
    return SettledDecision("mlb_pa_sim", "winner", cluster, model, market, result, pnl)


def test_beat_close_head_needs_min_contested_n():
    # Two contested decisions the model nails, but below MIN_CONTESTED_N -> fail.
    decisions = [
        _dec("g1", 0.80, 0.55, True),
        _dec("g2", 0.20, 0.45, False),
    ]
    verdict = beat_close_head(decisions)
    assert verdict.name == "beat_close"
    assert verdict.passed is False  # contested_n below the minimum
    assert verdict.n == 2


def test_beat_close_head_passes_when_model_beats_market_on_contested():
    # 40 contested decisions across 20 clusters; the model is confidently right
    # and the market is closer to 0.5, so the model's Brier edge is positive
    # with a lower bound above zero.
    decisions = []
    for i in range(20):
        decisions.append(_dec(f"win{i}", 0.85, 0.55, True))
        decisions.append(_dec(f"loss{i}", 0.15, 0.45, False))
    verdict = beat_close_head(decisions)
    assert verdict.n == 40
    assert verdict.metric is not None and verdict.metric > 0
    assert verdict.passed is True
    assert verdict.detail["contested_n"] == 40


def test_beat_close_head_ignores_uncontested():
    # Model agrees with the market (<5c apart) -> not contested -> excluded.
    decisions = [_dec(f"g{i}", 0.52, 0.51, True) for i in range(30)]
    verdict = beat_close_head(decisions)
    assert verdict.detail["contested_n"] == 0
    assert verdict.passed is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_mlb_validation.py -k beat_close -v`
Expected: FAIL with `ImportError: cannot import name 'beat_close_head'`.

- [ ] **Step 3: Write minimal implementation**

First read `autonomy/backtest.py` around the `_cluster_bootstrap_mean_ci` definition and its call site to confirm the exact argument shape (a `dict[str, list[float]]` of edges keyed by cluster) and the returned dict's `"lower"` key. Then:

```python
# autonomy/sports/mlb_validation.py (append)
from autonomy.backtest import (
    CONTESTED_DISAGREEMENT,
    MIN_CONTESTED_N,
    _brier,
    _cluster_bootstrap_mean_ci,
)


def beat_close_head(decisions: list[SettledDecision]) -> HeadVerdict:
    """Primary head: contested-Brier skill vs the close, cluster-robust."""
    edges: list[float] = []
    edges_by_cluster: dict[str, list[float]] = {}
    for d in decisions:
        if abs(d.model_probability - d.market_probability) < CONTESTED_DISAGREEMENT:
            continue
        outcome = 1 if d.result_yes else 0
        edge = _brier(d.market_probability, outcome) - _brier(d.model_probability, outcome)
        edges.append(edge)
        edges_by_cluster.setdefault(d.event_cluster, []).append(edge)
    contested_n = len(edges)
    # _cluster_bootstrap_mean_ci requires a fixed string seed for deterministic
    # resampling (the codebase forbids unseeded randomness).
    ci = (
        _cluster_bootstrap_mean_ci(edges_by_cluster, seed="mlb-beat-close-v1")
        if edges else None
    )
    mean_edge = (sum(edges) / contested_n) if contested_n else None
    lower = (ci or {}).get("lower")
    passed = (
        contested_n >= MIN_CONTESTED_N
        and lower is not None
        and lower > 0.0
    )
    return HeadVerdict(
        name="beat_close",
        passed=passed,
        metric=mean_edge,
        n=len(decisions),
        detail={
            "contested_n": contested_n,
            "contested_disagreement": CONTESTED_DISAGREEMENT,
            "min_contested_n": MIN_CONTESTED_N,
            "cluster_bootstrap_ci95": ci,
            "event_clusters": len(edges_by_cluster),
        },
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autonomy_mlb_validation.py -k beat_close -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add autonomy/sports/mlb_validation.py tests/test_autonomy_mlb_validation.py
git commit -m "feat(mlb): beat-the-close head (contested-Brier, cluster-robust)"
```

---

### Task 4: Calibration and paper-P&L sanity heads

**Files:**
- Modify: `autonomy/sports/mlb_validation.py`
- Test: `tests/test_autonomy_mlb_validation.py`

**Interfaces:**
- Consumes: `SettledDecision`, `_brier`, `autonomy.stats.mean_ci95`.
- Produces: `calibration_head(decisions) -> HeadVerdict` (full-surface mean Brier edge vs market over ALL settled decisions; passes when the mean-edge CI lower bound `> 0` and `n >= 1`); `paper_pnl_head(decisions) -> HeadVerdict` (sum of `pnl_cents` over decisions that carry one; passes when net `> 0` and at least one settled P&L exists).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_mlb_validation.py (append)
from autonomy.sports.mlb_validation import calibration_head, paper_pnl_head


def test_calibration_head_full_surface_edge():
    # Model consistently closer to the outcome than the market across 30 games.
    decisions = [_dec(f"g{i}", 0.90, 0.60, True) for i in range(30)]
    verdict = calibration_head(decisions)
    assert verdict.name == "calibration"
    assert verdict.n == 30
    assert verdict.metric is not None and verdict.metric > 0
    assert verdict.passed is True


def test_calibration_head_empty_is_unproven():
    verdict = calibration_head([])
    assert verdict.passed is False and verdict.n == 0


def test_paper_pnl_head_sums_realized():
    decisions = [
        _dec("g1", 0.6, 0.5, True, pnl=40),
        _dec("g2", 0.4, 0.5, False, pnl=-15),
        _dec("g3", 0.6, 0.5, True, pnl=None),  # no realized P&L -> excluded
    ]
    verdict = paper_pnl_head(decisions)
    assert verdict.name == "paper_pnl"
    assert verdict.metric == 25.0  # 40 - 15
    assert verdict.n == 2
    assert verdict.passed is True


def test_paper_pnl_head_negative_fails():
    decisions = [_dec("g1", 0.6, 0.5, False, pnl=-52)]
    verdict = paper_pnl_head(decisions)
    assert verdict.passed is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_mlb_validation.py -k "calibration or paper_pnl" -v`
Expected: FAIL with `ImportError: cannot import name 'calibration_head'`.

- [ ] **Step 3: Write minimal implementation**

```python
# autonomy/sports/mlb_validation.py (append)
from autonomy.stats import mean_ci95


def calibration_head(decisions: list[SettledDecision]) -> HeadVerdict:
    """Sanity head: full-surface mean Brier edge vs the market (all settled)."""
    edges: list[float] = []
    for d in decisions:
        outcome = 1 if d.result_yes else 0
        edges.append(
            _brier(d.market_probability, outcome) - _brier(d.model_probability, outcome)
        )
    ci = mean_ci95(edges) if edges else None
    lower = (ci or {}).get("lower")
    mean_edge = (ci or {}).get("mean")
    passed = bool(edges) and lower is not None and lower > 0.0
    return HeadVerdict(
        name="calibration",
        passed=passed,
        metric=mean_edge,
        n=len(edges),
        detail={"mean_edge_ci95": ci},
    )


def paper_pnl_head(decisions: list[SettledDecision]) -> HeadVerdict:
    """Operational head: net realized paper P&L over decisions that have one."""
    realized = [d.pnl_cents for d in decisions if d.pnl_cents is not None]
    net = sum(realized)
    passed = bool(realized) and net > 0
    return HeadVerdict(
        name="paper_pnl",
        passed=passed,
        metric=float(net) if realized else None,
        n=len(realized),
        detail={"net_pnl_cents": net, "priced_decisions": len(realized)},
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autonomy_mlb_validation.py -k "calibration or paper_pnl" -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add autonomy/sports/mlb_validation.py tests/test_autonomy_mlb_validation.py
git commit -m "feat(mlb): calibration + paper-P&L sanity heads"
```

---

### Task 5: `score_engine` — assemble the three heads into a scorecard

**Files:**
- Modify: `autonomy/sports/mlb_validation.py`
- Test: `tests/test_autonomy_mlb_validation.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `score_engine(rows, pnl_by_id, source) -> MlbEngineScorecard` — the single public entry point: filter to the source's settled decisions, run all three heads, assemble the scorecard.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_mlb_validation.py (append)
from autonomy.sports.mlb_validation import score_engine


def test_score_engine_assembles_all_three_heads():
    rows = []
    pnl = {}
    for i in range(20):
        rows.append(_Row(f"w{i}", "mlb_pa_sim", "winner", f"win{i}", 0.85, 0.55, True))
        rows.append(_Row(f"l{i}", "mlb_pa_sim", "winner", f"loss{i}", 0.15, 0.45, False))
        pnl[f"w{i}"] = 30
        pnl[f"l{i}"] = 20
    # Noise from another source must be ignored.
    rows.append(_Row("x", "mlb_gbm", "winner", "g1", 0.5, 0.5, True))
    card = score_engine(rows, pnl, "mlb_pa_sim")
    assert card.source == "mlb_pa_sim"
    assert card.settled == 40
    assert card.beat_close.name == "beat_close"
    assert card.calibration.name == "calibration"
    assert card.paper_pnl.name == "paper_pnl"
    assert card.beat_close.passed is True
    assert card.is_champion_ready is True


def test_score_engine_no_decisions_is_unproven():
    card = score_engine([], {}, "mlb_pa_sim")
    assert card.settled == 0
    assert card.is_champion_ready is False
    assert card.beat_close.n == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_mlb_validation.py -k score_engine -v`
Expected: FAIL with `ImportError: cannot import name 'score_engine'`.

- [ ] **Step 3: Write minimal implementation**

```python
# autonomy/sports/mlb_validation.py (append)


def score_engine(
    rows: Any, pnl_by_id: dict[str, int], source: str,
) -> MlbEngineScorecard:
    """Grade one engine's settled MLB decisions on all three heads."""
    decisions = settled_decisions_for(rows, pnl_by_id, source)
    return MlbEngineScorecard(
        source=source,
        settled=len(decisions),
        beat_close=beat_close_head(decisions),
        calibration=calibration_head(decisions),
        paper_pnl=paper_pnl_head(decisions),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autonomy_mlb_validation.py -k score_engine -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the full module and full suite, then commit**

Run: `python -m pytest tests/test_autonomy_mlb_validation.py -v` (all PASS), then `python -m pytest -q` (full suite green, >= 4,669 passed, 0 skipped plus the new module).

```bash
git add autonomy/sports/mlb_validation.py tests/test_autonomy_mlb_validation.py
git commit -m "feat(mlb): score_engine assembles the three-head scorecard"
```

---

### Task 6: Baseline the current model + wire a read-only report

**Files:**
- Create: `scripts/mlb_validation_report.py`
- Modify: `autonomy/sports/mlb_validation.py` (add a `scorecard_to_dict` serializer only)
- Test: `tests/test_autonomy_mlb_validation.py`

**Interfaces:**
- Produces: `scorecard_to_dict(card) -> dict[str, Any]` (JSON-safe); `scripts/mlb_validation_report.py` reads the live `SportsEvidenceLedger`, builds the `{observation_id: pnl_cents}` map from settled paper decisions, and prints a scorecard for each MLB source found — establishing the current `baseball.py` model's baseline (expected: `beat_close` NOT passed, since it is at market parity — the harness proving the honest baseline).

Notes: this task reproduces the S1 pattern of a live-verification script that is NOT a pytest test. The unit test covers only `scorecard_to_dict`; the script is exercised by hand.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_mlb_validation.py (append)
from autonomy.sports.mlb_validation import scorecard_to_dict


def test_scorecard_to_dict_is_json_safe():
    import json
    card = score_engine(
        [_Row("a", "s", "winner", "g1", 0.6, 0.52, True)], {"a": 10}, "s",
    )
    payload = scorecard_to_dict(card)
    # Round-trips through JSON without error and preserves the primary verdict.
    text = json.dumps(payload)
    back = json.loads(text)
    assert back["source"] == "s"
    assert back["is_champion_ready"] == card.is_champion_ready
    assert back["heads"]["beat_close"]["name"] == "beat_close"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autonomy_mlb_validation.py -k json_safe -v`
Expected: FAIL with `ImportError: cannot import name 'scorecard_to_dict'`.

- [ ] **Step 3: Write minimal implementation**

```python
# autonomy/sports/mlb_validation.py (append)
from dataclasses import asdict


def scorecard_to_dict(card: MlbEngineScorecard) -> dict[str, Any]:
    """JSON-safe scorecard for reports and the dashboard."""
    return {
        "source": card.source,
        "settled": card.settled,
        "is_champion_ready": card.is_champion_ready,
        "heads": {
            head.name: asdict(head)
            for head in (card.beat_close, card.calibration, card.paper_pnl)
        },
    }
```

Then the report script:

```python
# scripts/mlb_validation_report.py
"""Print the three-head validation scorecard for each MLB engine in the ledger.

Read-only. Establishes the current model's baseline: expect beat_close to be
unproven (the current baseball.py model is at market parity), which is the
harness telling the truth. Not a pytest test.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.sports.mlb_validation import score_engine, scorecard_to_dict  # noqa: E402
from autonomy.sports.simulation import SportsEvidenceLedger  # noqa: E402

RUNTIME = Path("runtime/autonomy/sports_simulation.db")


def main() -> int:
    if not RUNTIME.exists():
        print(f"No sports ledger at {RUNTIME}")
        return 0
    ledger = SportsEvidenceLedger(RUNTIME)
    try:
        rows = [r for r in ledger.rows(earliest_per_ticker_source=False)
                if r.sport == "mlb"]
        pnl_by_id: dict[str, int] = {}
        for d in ledger.recent_paper_decisions(status="SETTLED", limit=100000):
            if d.get("sport") == "mlb" and d.get("observation_id") and d.get("pnl_cents") is not None:
                pnl_by_id[str(d["observation_id"])] = int(d["pnl_cents"])
        sources = sorted({r.source for r in rows})
    finally:
        ledger.close()
    if not sources:
        print("No MLB engine decisions in the ledger yet.")
        return 0
    for source in sources:
        card = score_engine(rows, pnl_by_id, source)
        print(json.dumps(scorecard_to_dict(card), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes, then run the script**

Run: `python -m pytest tests/test_autonomy_mlb_validation.py -k json_safe -v`
Expected: PASS.

Run: `python scripts/mlb_validation_report.py`
Expected: prints a scorecard per MLB source. The current model's `beat_close.passed` should be `false` (parity baseline) — that is the harness working, not a failure. Confirm it does not raise and the P&L map attaches.

- [ ] **Step 5: Run the full suite and commit**

Run: `python -m pytest -q`
Expected: full suite green (>= 4,669 passed, 0 skipped, plus the new module).

```bash
git add autonomy/sports/mlb_validation.py scripts/mlb_validation_report.py tests/test_autonomy_mlb_validation.py
git commit -m "feat(mlb): scorecard serializer + live baseline validation report"
```

---

## Self-Review

**Spec coverage (S2 = spec Layer C):**
- Contested-Brier skill vs close, cluster-robust, event-purged population — Task 3 (reuses `backtest.py`'s bootstrap) ✓
- Public-benchmark sanity — Task 4 `calibration_head` implements the full-surface Brier-vs-market guard. NOTE: the spec named an external benchmark (ESPN/538 Elo); with no per-decision external prediction stored, S2 uses full-surface market-relative calibration as the buildable sanity guard and defers a stored external benchmark to a later enrichment. Flag for spec-review adjudication.
- Paper P&L — Task 4 `paper_pnl_head` ✓
- Champion gating on primary head only — Task 1 `is_champion_ready` ✓
- Grades any engine by source; reused by S3+ from birth — Task 5 `score_engine` ✓
- Offline, pure, no live calls (not gated on StatsAPI terms review) — Global Constraints ✓
- Baseline the current model — Task 6 report ✓

**Placeholder scan:** none — every step carries runnable test and implementation code.

**Type consistency:** `HeadVerdict`, `MlbEngineScorecard`, `SettledDecision`, `settled_decisions_for`, `beat_close_head`, `calibration_head`, `paper_pnl_head`, `score_engine`, `scorecard_to_dict` are used with consistent names/signatures across tasks. `_Row` stand-in in tests carries the exact duck-typed attribute shape `settled_decisions_for` reads.

**Reuse check:** `_brier`, `CONTESTED_DISAGREEMENT`, `MIN_CONTESTED_N`, `_cluster_bootstrap_mean_ci` imported from `autonomy.backtest`; `mean_ci95` from `autonomy.stats`. Task 3 Step 3 instructs reading `backtest.py` first to confirm the `_cluster_bootstrap_mean_ci` argument shape and `"lower"` key before implementing — the one integration risk, called out explicitly.

**Out of S2 scope (correctly deferred):** the model heads themselves (S3-S4), StatsAPI live wiring (S3, governance-gated), recursive loops (S5), dashboard surfacing of the scorecard (a small follow-up once a real engine exists).
