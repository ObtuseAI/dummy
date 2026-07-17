"""Wave-7 Ascendancy deltas: negative controls, preregistration, sealed
holdout, no-edge map, conservative-advantage haircuts."""
from __future__ import annotations

import hashlib

import pytest

from autonomy.conservative_advantage import (
    conservative_advantage,
    scope_conservative_advantage,
    selection_z_inflation,
)
from autonomy.negative_controls import run_battery_for_source
from autonomy.no_edge_map import build_no_edge_map, classify_scope
from dummy.autoresearch.preregistration import (
    PreregistrationError,
    PreregistrationRegistry,
    enforce_preregistered,
)
from dummy.autoresearch.sealed_holdout import HoldoutBudgetExceeded, SealedHoldout


# ---- negative controls --------------------------------------------------------

def _det(i: int, salt: str) -> float:
    return (int(hashlib.sha256(f"{salt}|{i}".encode()).hexdigest()[:8], 16) % 1000) / 1000.0


def _skilled_rows(n=400):
    """Genuine skill against an HONEST, informative market: the prior leans
    with the outcome (markets are calibrated), the model leans harder."""
    rows = []
    for i in range(n):
        outcome = _det(i, "world") < 0.5
        rows.append({
            "probability_yes": 0.85 if outcome else 0.15,
            "market_probability": 0.62 if outcome else 0.38,   # informative prior
            "result_yes": int(outcome),
            "event_cluster": f"C{i}",
            "created_at": f"2026-07-{(i % 28) + 1:02d}T12:00:00+00:00",
        })
    return rows


def test_skilled_source_passes_battery():
    result = run_battery_for_source("skilled", _skilled_rows())
    assert result["status"] == "clean"
    assert result["real_edge"]["lower"] > 0            # genuinely positive
    shuffled = result["controls"]["shuffled_labels"]
    assert shuffled["lower"] <= 0                       # edge dies in a scrambled world
    # Honest benchmark: average contested price tracks realized prevalence.
    assert result["controls"]["benchmark_calibration"]["gap"] < 0.15


def test_fabricated_prior_source_is_flagged():
    """The 2026-07-17 bug signature: the 'edge' lives in a fabricated prior.

    Model trivially says NO on deep-OTM strikes; the recorded prior is a
    phantom ~coin mid while true outcomes are ~3% YES. The benchmark's
    average price (0.48) is 0.45 away from realized prevalence (0.03) — an
    honest market can never be that miscalibrated at scale -> flag."""
    rows = []
    for i in range(400):
        rows.append({
            "probability_yes": 0.02,          # model trivially says NO
            "market_probability": 0.48,       # fabricated ~coin mid
            "result_yes": int(_det(i, "otm") < 0.03),  # OTM: ~3% YES
            "event_cluster": f"C{i}",
            "created_at": f"2026-07-{(i % 28) + 1:02d}T12:00:00+00:00",
        })
    result = run_battery_for_source("phantom", rows)
    assert result["real_edge"]["lower"] > 0            # looks like huge edge...
    assert "benchmark_miscalibrated_vs_prevalence" in result["flags"]
    assert result["status"] == "flagged"


def test_underpowered_source_reports_insufficient():
    result = run_battery_for_source("thin", _skilled_rows(20))
    assert result["status"] == "insufficient_rows"


# ---- preregistration ----------------------------------------------------------

def test_preregistration_roundtrip_and_idempotency(tmp_path):
    reg = PreregistrationRegistry(tmp_path / "prereg.jsonl")
    record = reg.register(
        "cand-1", lane="crypto",
        hypothesis="SOL 15m equities-flow beats the book when SP futures move first",
        mechanism="cross-asset lead-lag: equities repricing propagates to SOL within minutes",
        falsification_condition="contested Brier edge CI95 lower <= 0 over 300 clusters",
    )
    assert reg.is_registered("cand-1")
    again = reg.register(
        "cand-1", lane="crypto",
        hypothesis="SOL 15m equities-flow beats the book when SP futures move first",
        mechanism="cross-asset lead-lag: equities repricing propagates to SOL within minutes",
        falsification_condition="contested Brier edge CI95 lower <= 0 over 300 clusters",
    )
    assert again.prereg_id == record.prereg_id          # identical claim = idempotent
    assert len(reg.for_candidate("cand-1")) == 1


def test_preregistration_rejects_vague_claims(tmp_path):
    reg = PreregistrationRegistry(tmp_path / "prereg.jsonl")
    with pytest.raises(PreregistrationError):
        reg.register("cand-2", lane="crypto", hypothesis="it works",
                     mechanism="magic", falsification_condition="loses")


def test_enforce_preregistered_lists_missing(tmp_path):
    reg = PreregistrationRegistry(tmp_path / "prereg.jsonl")
    reg.register("a", lane="x",
                 hypothesis="a substantive hypothesis about market behavior",
                 mechanism="a substantive mechanism grounded in structure",
                 falsification_condition="edge CI lower <= 0 over 100 clusters")
    assert enforce_preregistered(["a", "b"], reg) == ["b"]


# ---- sealed holdout -----------------------------------------------------------

def test_sealed_holdout_one_shot_budget(tmp_path):
    holdout = SealedHoldout([1, 2, 3], usage_path=tmp_path / "usage.jsonl")
    result = holdout.submit("cand-1", lambda rows: {"n": len(rows)})
    assert result == {"n": 3}
    with pytest.raises(HoldoutBudgetExceeded):
        holdout.submit("cand-1", lambda rows: {"n": len(rows)})
    # A different candidate still has its own budget.
    assert holdout.submit("cand-2", lambda rows: {"n": len(rows)}) == {"n": 3}


def test_sealed_holdout_crash_consumes_budget(tmp_path):
    holdout = SealedHoldout([1], usage_path=tmp_path / "usage.jsonl")

    def _boom(rows):
        raise RuntimeError("evaluation crashed")

    with pytest.raises(RuntimeError):
        holdout.submit("cand-x", _boom)
    with pytest.raises(HoldoutBudgetExceeded):          # no peek-by-crashing
        holdout.submit("cand-x", lambda rows: {})


# ---- no-edge map --------------------------------------------------------------

def _scope(clusters, lower, upper, mean=None):
    return {"contested_event_clusters": clusters,
            "contested_mean_brier_edge_ci95": {
                "lower": lower, "upper": upper,
                "mean": mean if mean is not None else (lower + upper) / 2}}


def test_classify_scope_states():
    assert classify_scope(_scope(100, 0.01, 0.03)) == "edge"
    assert classify_scope(_scope(100, -0.01, 0.01)) == "no_demonstrated_edge"
    assert classify_scope(_scope(100, -0.02, -0.005)) == "significantly_negative"
    assert classify_scope(_scope(10, 0.01, 0.03)) == "insufficient_evidence"
    assert classify_scope({"contested_event_clusters": 100}) == "insufficient_evidence"


def test_build_no_edge_map_shapes():
    report = {"sources_by_scope": {
        "good|x|y|z": _scope(100, 0.01, 0.03),
        "dead|x|y|z": _scope(100, -0.02, -0.01),
        "flat|x|y|z": _scope(100, -0.004, 0.004),
        "thin|x|y|z": _scope(5, 0.1, 0.3),
    }}
    out = build_no_edge_map(report)
    assert out["counts"] == {"edge": 1, "no_demonstrated_edge": 1,
                             "significantly_negative": 1, "insufficient_evidence": 1}
    assert out["significantly_negative"][0]["scope"] == "dead|x|y|z"
    assert out["insufficient_evidence_scopes"] == ["thin|x|y|z"]


# ---- conservative advantage ---------------------------------------------------

def test_selection_inflation_monotone():
    assert selection_z_inflation(1) == 1.0
    assert selection_z_inflation(10) > selection_z_inflation(2) > 1.0


def test_conservative_advantage_haircuts_stack():
    base = conservative_advantage(0.02, ci_halfwidth=0.005)
    assert base.conservative == pytest.approx(0.015)
    # A family of 20 candidates widens the effective interval.
    mined = conservative_advantage(0.02, ci_halfwidth=0.005, family_size=20)
    assert mined.conservative < base.conservative
    # Four correlated opportunities shrink it further (sqrt(4) = 2x width).
    correlated = conservative_advantage(0.02, ci_halfwidth=0.005,
                                        family_size=20, correlation_group_n=4)
    assert correlated.conservative < mined.conservative
    # Costs subtract in the same units.
    costed = conservative_advantage(0.02, ci_halfwidth=0.005, cost=0.02)
    assert costed.conservative < 0 and costed.to_dict()["positive"] is False


def test_scope_conservative_advantage_from_backtest_stats():
    stats = _scope(889, 0.012517, 0.027904, mean=0.019991)   # market_debias, real numbers
    out = scope_conservative_advantage(stats, family_size=1)
    assert out is not None
    assert out["positive"] is True                            # survives its own CI haircut
    assert scope_conservative_advantage({"contested_mean_brier_edge_ci95": {}}) is None
