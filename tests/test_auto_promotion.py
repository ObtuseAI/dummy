"""AutoPromotionEngine: ladder criteria, rails, cap, hysteresis, determinism."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from autonomy.auto_promotion import (
    AutoPromotionEngine,
    PromotionConfig,
    RailsInputs,
    RailsVerdict,
    build_scope_evidence,
    cluster_bootstrap_ci,
    correlation_guard,
    counterfactual_pnl,
    demotion_breach,
    evaluate_rails,
)
from autonomy.strategy_miner import MinedRow

BASE = datetime(2026, 6, 1, tzinfo=timezone.utc)
SCOPE = "crypto_ta_foundry|btc|15m_direction|15m"
CLV_OK = {"lower": 25.0, "mean": 60.0, "upper": 95.0}


def _rows(
    scope: str = SCOPE,
    *,
    n: int = 360,
    prob: float = 0.75,
    market: float = 0.55,
    win_pattern=lambda i: (i % 10) < 7,
    hours_step: float = 1.0,
    source: str | None = None,
    ticker_prefix: str = "KXBTC15M",
) -> list[MinedRow]:
    source = source or scope.split("|", 1)[0]
    rows = []
    for i in range(n):
        rows.append(MinedRow(
            source=source,
            ticker=f"{ticker_prefix}-{i:04d}-T60000",
            event_cluster=f"{ticker_prefix}-{i:04d}",
            created_at=(BASE + timedelta(hours=i * hours_step)).isoformat(),
            probability_yes=prob,
            market_probability=market,
            result_yes=win_pattern(i),
            features={},
            scope=scope,
        ))
    return rows


def _now_ts(n: int = 360, hours_step: float = 1.0) -> float:
    return (BASE + timedelta(hours=n * hours_step + 1)).timestamp()


def _forward_realized(scope: str) -> dict:
    fingerprint = hashlib.sha256(scope.encode("utf-8")).hexdigest()
    pnl = {f"forward-{i}": [1.0] for i in range(60)}
    timestamps = [
        (BASE + timedelta(hours=4 * i)).isoformat() for i in range(60)
    ]
    return {
        "n_trades": 60,
        "pnl_by_cluster": pnl,
        "evidence_origin": "ledger_verified",
        "receipt_bounded": True,
        "witnessed_fill_net_pnl": True,
        "forward_evidence": {
            "evidence_version": "promotion_forward_fill_v1",
            "evidence_origin": "ledger_verified",
            "receipt_bounded": True,
            "witnessed_fill_net_pnl": True,
            "out_of_sample_after_registration": True,
            "isolated_candidate_decisions": True,
            "registered_at": (BASE - timedelta(days=1)).isoformat(),
            "candidate_fingerprint": fingerprint,
            "n_trades": 60,
            "pnl_by_cluster": pnl,
            "trade_timestamps": timestamps,
        },
    }


def _forward_map(scopes) -> dict:
    return {scope: _forward_realized(scope) for scope in scopes}


# -- counterfactual P&L math ----------------------------------------------------

def test_counterfactual_pnl_yes_side_by_hand():
    # Model above market -> YES at the market price. Unlisted crypto series:
    # general maker multiplier is 0 -> no fee.
    win = MinedRow("s", "KXBTC15M-1-T", "KXBTC15M-1", "2026-06-01T00:00:00+00:00",
                   0.75, 0.55, True, {}, SCOPE)
    loss = MinedRow("s", "KXBTC15M-2-T", "KXBTC15M-2", "2026-06-01T00:00:00+00:00",
                    0.75, 0.55, False, {}, SCOPE)
    assert abs(counterfactual_pnl(win) - 0.45) < 1e-9   # 1 - 0.55
    assert abs(counterfactual_pnl(loss) - (-0.55)) < 1e-9


def test_counterfactual_pnl_no_side_and_maker_fee():
    # Model below market -> NO side. KXMLBGAME is a maker-fee (M=1) series:
    # fee at 45c/55c symmetric = ceil(1.75 * 0.55 * 0.45) = 1 cent.
    no_win = MinedRow("s", "KXMLBGAME-26JUL15AB-AB", "KXMLBGAME-26JUL15AB",
                      "2026-06-01T00:00:00+00:00", 0.35, 0.55, False, {}, "x|mlb|winner|pre")
    no_loss = MinedRow("s", "KXMLBGAME-26JUL15AB-AB", "KXMLBGAME-26JUL15AB",
                       "2026-06-01T00:00:00+00:00", 0.35, 0.55, True, {}, "x|mlb|winner|pre")
    # NO entry cost = 1 - 0.55 = 0.45; payoff = 1 when NO wins; fee = 1c.
    assert abs(counterfactual_pnl(no_win) - (1.0 - 0.45 - 0.01)) < 1e-9
    assert abs(counterfactual_pnl(no_loss) - (0.0 - 0.45 - 0.01)) < 1e-9


# -- deterministic cluster bootstrap + Bonferroni --------------------------------

def test_bootstrap_is_deterministic_and_cluster_level():
    values = {f"c{i}": [0.02, 0.02] for i in range(50)}
    values["c0"] = [-0.5]  # one bad cluster
    a = cluster_bootstrap_ci(values, seed="x")
    b = cluster_bootstrap_ci(values, seed="x")
    assert a == b  # same seed, same inputs -> byte-identical interval
    assert a is not None and a["clusters"] == 50
    # The unit is the cluster: the lone bad cluster caps the mean well below
    # the per-emission average of the 99 good values.
    assert a["mean"] < 0.02


def test_bootstrap_bonferroni_widens_interval():
    import random

    rng = random.Random(7)
    values = {f"c{i}": [rng.gauss(0.01, 0.05)] for i in range(120)}
    plain = cluster_bootstrap_ci(values, seed="s", family_size=1)
    adjusted = cluster_bootstrap_ci(values, seed="s", family_size=50)
    assert plain is not None and adjusted is not None
    assert adjusted["lower"] <= plain["lower"]
    assert adjusted["upper"] >= plain["upper"]
    assert adjusted["family_size"] == 50


def test_bootstrap_empty_and_single_cluster():
    assert cluster_bootstrap_ci({}, seed="s") is None
    single = cluster_bootstrap_ci({"c": [0.1, 0.3]}, seed="s")
    assert single is not None
    assert single["lower"] == single["upper"] == single["mean"] == 0.2


# -- correlation guard -----------------------------------------------------------

def test_correlation_guard_flags_near_duplicates_only_with_overlap():
    candidate = {f"T{i}": 0.4 + i * 0.01 for i in range(10)}
    clone = dict(candidate)
    guard = correlation_guard(candidate, {"incumbent": clone})
    assert guard["ok"] is False and guard["with_source"] == "incumbent"
    assert guard["max_correlation"] == 1.0
    # Below the overlap floor the pair is skipped, not treated as correlated.
    tiny = {k: candidate[k] for k in list(candidate)[:3]}
    guard2 = correlation_guard(candidate, {"incumbent": tiny})
    assert guard2["ok"] is True and guard2["with_source"] is None


def test_correlation_guard_constant_series_has_no_correlation():
    candidate = {f"T{i}": 0.5 for i in range(10)}
    other = {f"T{i}": 0.3 + i * 0.02 for i in range(10)}
    guard = correlation_guard(candidate, {"other": other})
    assert guard["ok"] is True  # zero variance -> no linear correlation


def test_anticorrelation_also_trips_the_guard():
    candidate = {f"T{i}": 0.4 + i * 0.01 for i in range(10)}
    inverse = {f"T{i}": 0.6 - i * 0.01 for i in range(10)}
    guard = correlation_guard(candidate, {"inv": inverse})
    assert guard["ok"] is False and guard["max_correlation"] == -1.0


# -- stage-1 criteria, one by one --------------------------------------------------

def test_strong_scope_passes_every_stage1_gate():
    rows = _rows()
    ev = build_scope_evidence(SCOPE, rows, _now_ts(), clv=CLV_OK)
    assert ev.evidence_pass(), ev.failing_criteria()
    d = ev.dossier()
    assert d["clusters"]["threshold"] == 300           # CLV present
    assert d["evidence_span_days"]["threshold"] == 7.0  # owner-set span
    assert d["contested_beat_rate"]["measured"] == 0.7


def test_criterion_a_clusters_and_span():
    short = build_scope_evidence(SCOPE, _rows(n=250), _now_ts(250), clv=CLV_OK)
    assert not short.evidence_pass()
    assert "clusters" in short.failing_criteria()
    # 360 clusters compressed into < 7 days trips the span floor.
    fast = build_scope_evidence(
        SCOPE, _rows(hours_step=0.25), _now_ts(hours_step=0.25), clv=CLV_OK)
    assert "evidence_span_days" in fast.failing_criteria()


def test_criterion_b_edge_ci_blocks_coin_flips():
    coin = build_scope_evidence(
        SCOPE, _rows(win_pattern=lambda i: i % 2 == 0), _now_ts(), clv=CLV_OK)
    assert not coin.evidence_pass()
    assert "contested_brier_edge_ci95_lower" in coin.failing_criteria()


def test_criterion_b_beat_rate_blocks_lucky_few_hits():
    # 40% of contested emissions are huge wins, 60% are small losses: the
    # cluster-mean edge CI clears zero, but the beat rate is only 0.40.
    rows = []
    for i in range(400):
        big_win = (i % 5) < 2
        rows.append(MinedRow(
            source="crypto_ta_foundry",
            ticker=f"KXBTC15M-{i:04d}-T", event_cluster=f"KXBTC15M-{i:04d}",
            created_at=(BASE + timedelta(hours=i)).isoformat(),
            probability_yes=0.95 if big_win else 0.61,
            market_probability=0.55,
            result_yes=big_win,  # winners win, contesters-of-0.60 lose
            features={}, scope=SCOPE,
        ))
    ev = build_scope_evidence(SCOPE, rows, _now_ts(400), clv=CLV_OK)
    d = ev.dossier()
    assert d["contested_brier_edge_ci95_lower"]["pass"] is True
    assert d["contested_beat_rate"]["measured"] == 0.4
    assert "contested_beat_rate" in ev.failing_criteria()


def test_criterion_c_counterfactual_diagnostic_gate_blocks_alone():
    # The P&L gate is its own criterion: everything else green, pnl CI red.
    import dataclasses

    strong = build_scope_evidence(SCOPE, _rows(), _now_ts(), clv=CLV_OK)
    losing = dataclasses.replace(
        strong, pnl_ci={"mean": -0.01, "lower": -0.03,
                        "upper": 0.01, "clusters": 360},
    )
    assert strong.evidence_pass()
    assert not losing.evidence_pass()
    assert losing.failing_criteria() == ["counterfactual_pnl_ci95_lower"]


def test_criterion_c_pnl_is_fee_adjusted_in_the_dossier():
    ev = build_scope_evidence(SCOPE, _rows(), _now_ts(), clv=CLV_OK)
    d = ev.dossier()["counterfactual_pnl_ci95_lower"]
    assert d["unit"] == "dollars_per_contract"
    # 70% win at 55c entry, zero-fee series: mean ~ 0.7*0.45 - 0.3*0.55 = 0.15
    assert abs((ev.pnl_ci or {}).get("mean", 0) - 0.15) < 0.02


def test_criterion_d_degradation_blocks():
    # Healthy history, then 100 trailing clusters of confident losses.
    good = _rows(n=300)
    bad = []
    for i in range(100):
        bad.append(MinedRow(
            source="crypto_ta_foundry",
            ticker=f"KXBTC15M-9{i:03d}-T", event_cluster=f"KXBTC15M-9{i:03d}",
            created_at=(BASE + timedelta(hours=300 + i)).isoformat(),
            probability_yes=0.75, market_probability=0.55,
            result_yes=False, features={}, scope=SCOPE,
        ))
    ev = build_scope_evidence(SCOPE, good + bad, _now_ts(400), clv=CLV_OK)
    assert ev.degrading is True
    assert "not_degrading" in ev.failing_criteria()


def test_criterion_e_clv_gate_and_no_clv_higher_bar():
    rows_400 = _rows(n=400)
    # CLV instrumented and positive: 400 clusters clear the 300 bar.
    with_clv = build_scope_evidence(SCOPE, rows_400, _now_ts(400), clv=CLV_OK)
    assert with_clv.evidence_pass()
    # CLV instrumented but not confidently positive: hard fail.
    bad_clv = build_scope_evidence(
        SCOPE, rows_400, _now_ts(400), clv={"lower": -5.0, "mean": 10.0})
    assert "clv_ci95_lower" in bad_clv.failing_criteria()
    # No CLV instrumentation: allowed, but 400 < 450 clusters now fails (a).
    no_clv = build_scope_evidence(SCOPE, rows_400, _now_ts(400), clv=None)
    assert no_clv.required_clusters == 450
    assert "clusters" in no_clv.failing_criteria()
    # ... and 460 clusters passes without CLV.
    rows_460 = _rows(n=460)
    no_clv_big = build_scope_evidence(SCOPE, rows_460, _now_ts(460), clv=None)
    assert no_clv_big.evidence_pass(), no_clv_big.failing_criteria()


def test_criterion_f_correlation_routes_to_replacement_not_promotion():
    import dataclasses

    # Vary the candidate's emitted probabilities so a linear correlation is
    # measurable, then mirror them exactly in an incumbent's tape. A 75% win
    # rate keeps the Brier CI comfortably clear despite the added variance.
    rows = [dataclasses.replace(row, probability_yes=0.70 + (i % 10) * 0.01)
            for i, row in enumerate(_rows(win_pattern=lambda i: (i % 4) < 3))]
    incumbent_tape = {row.ticker: row.probability_yes for row in rows}
    ev = build_scope_evidence(
        SCOPE, rows, _now_ts(), clv=CLV_OK,
        fused_probs_by_source={"crypto_spot_vol": incumbent_tape})
    # Correlation guard failed but everything else passed.
    assert ev.evidence_pass()
    assert ev.correlation["ok"] is False

    engine = AutoPromotionEngine()
    result = engine.decide(
        scope_rows={SCOPE: rows}, promoted={}, now_ts=_now_ts(),
        now_iso="2026-07-16T09:00:00+00:00", rails=RailsVerdict(abort=False),
        clv_by_scope={SCOPE: CLV_OK},
        realized_by_scope=_forward_map([SCOPE]),
        fused_probs_by_source={"crypto_spot_vol": incumbent_tape})
    assert result.promotions == []
    assert [d.scope for d in result.replacement_candidates] == [SCOPE]
    assert "crypto_spot_vol" in result.replacement_candidates[0].reason


def test_candidates_own_source_never_correlates_with_itself():
    import dataclasses

    rows = [dataclasses.replace(row, probability_yes=0.70 + (i % 10) * 0.01)
            for i, row in enumerate(_rows())]
    own_tape = {row.ticker: row.probability_yes for row in rows}
    ev = build_scope_evidence(
        SCOPE, rows, _now_ts(), clv=CLV_OK,
        fused_probs_by_source={"crypto_ta_foundry": own_tape})
    assert ev.correlation["ok"] is True


def test_mined_family_bonferroni_can_block_marginal_scope():
    # A marginal winner: edge CI lower barely above zero at family size 1.
    rows = _rows(win_pattern=lambda i: (i % 100) < 62)
    plain = build_scope_evidence(SCOPE, rows, _now_ts(), clv=CLV_OK, family_size=1)
    mined = build_scope_evidence(SCOPE, rows, _now_ts(), clv=CLV_OK, family_size=200)
    assert (mined.brier_ci or {})["lower"] <= (plain.brier_ci or {})["lower"]
    d = mined.dossier()["contested_brier_edge_ci95_lower"]
    assert d["bonferroni_applied"] is True and d["family_size"] == 200


# -- demotion hysteresis ------------------------------------------------------------

def test_demotion_needs_confidently_negative_trailing_record():
    # Confidently negative trailing window -> breach.
    losing = _rows(win_pattern=lambda i: (i % 10) < 3)
    breach = demotion_breach(SCOPE, losing)
    assert breach["breach"] is True
    # Mildly negative mean whose CI straddles zero -> NO breach (hysteresis:
    # the same record would also fail promotion, so the scope just holds).
    mixed = _rows(win_pattern=lambda i: (i % 100) < 62)
    hold = demotion_breach(SCOPE, mixed)
    assert hold["breach"] is False
    ev = build_scope_evidence(SCOPE, mixed, _now_ts(), clv=CLV_OK)
    assert not ev.evidence_pass()  # not promotable either -> no churn band


def test_engine_demotes_at_both_stages_and_instantly():
    losing = _rows(win_pattern=lambda i: (i % 10) < 3)
    engine = AutoPromotionEngine()
    for stage in (1, 2):
        result = engine.decide(
            scope_rows={SCOPE: losing}, promoted={SCOPE: {"stage": stage}},
            now_ts=_now_ts(), now_iso="2026-07-16T09:00:00+00:00",
            rails=RailsVerdict(abort=False))
        assert [d.scope for d in result.demotions] == [SCOPE]
        assert result.demotions[0].stage == stage
        assert result.demotions[0].weight_fraction == 0.0


def test_demoted_scope_cannot_escalate_in_the_same_run():
    losing = _rows(win_pattern=lambda i: (i % 10) < 3)
    realized = {SCOPE: {"n_trades": 80,
                        "pnl_by_cluster": {f"c{i}": [1.0] for i in range(60)}}}
    result = AutoPromotionEngine().decide(
        scope_rows={SCOPE: losing}, promoted={SCOPE: {"stage": 1}},
        now_ts=_now_ts(), now_iso="x", rails=RailsVerdict(abort=False),
        realized_by_scope=realized)
    assert [d.scope for d in result.demotions] == [SCOPE]
    assert result.escalations == []


# -- stage 2 escalation ---------------------------------------------------------------

def test_escalation_requires_50_trades_and_positive_realized_ci():
    engine = AutoPromotionEngine()
    good = {"n_trades": 50, "pnl_by_cluster": {f"c{i}": [0.5, 1.5] for i in range(30)}}
    few = {"n_trades": 49, "pnl_by_cluster": {f"c{i}": [0.5, 1.5] for i in range(30)}}
    losing = {"n_trades": 80, "pnl_by_cluster": {f"c{i}": [(-1.0) ** i * 5.0]
                                                 for i in range(60)}}
    rows = _rows()

    def run(realized):
        return engine.decide(
            scope_rows={SCOPE: rows}, promoted={SCOPE: {"stage": 1}},
            now_ts=_now_ts(), now_iso="x", rails=RailsVerdict(abort=False),
            realized_by_scope={SCOPE: realized} if realized else {})

    assert [d.scope for d in run(good).escalations] == [SCOPE]
    assert run(good).escalations[0].weight_fraction == 1.0
    assert run(few).escalations == []
    assert run(losing).escalations == []
    assert run(None).escalations == []


def test_stage2_scope_never_re_escalates():
    result = AutoPromotionEngine().decide(
        scope_rows={SCOPE: _rows()}, promoted={SCOPE: {"stage": 2}},
        now_ts=_now_ts(), now_iso="x", rails=RailsVerdict(abort=False),
        realized_by_scope={SCOPE: {"n_trades": 500,
                                   "pnl_by_cluster": {f"c{i}": [1.0] for i in range(60)}}})
    assert result.escalations == [] and result.promotions == []


# -- rails ------------------------------------------------------------------------------

def test_every_rail_aborts_alone():
    cases = {
        "kill_file_present": RailsInputs(kill_file_present=True),
        "heartbeat_cycle_error": RailsInputs(heartbeat_status="CYCLE_ERROR:ValueError"),
        "heartbeat_not_alive": RailsInputs(heartbeat_alive=False),
        "health_error": RailsInputs(health_error=True),
        "weight_saturation_anomaly": RailsInputs(weight_saturation_flagged=True),
        "exchange_anomaly": RailsInputs(exchange_anomaly=True),
        "evidence_artifacts_stale": RailsInputs(artifact_age_hours=25.0),
    }
    for reason, inputs in cases.items():
        verdict = evaluate_rails(inputs)
        assert verdict.abort is True and verdict.reasons == [reason]
    clean = evaluate_rails(RailsInputs(artifact_age_hours=1.0))
    assert clean.abort is False and clean.reasons == []


def test_tripped_rails_abort_the_entire_run_before_any_decision():
    result = AutoPromotionEngine().decide(
        scope_rows={SCOPE: _rows()}, promoted={}, now_ts=_now_ts(),
        now_iso="x", rails=RailsVerdict(abort=True, reasons=["kill_file_present"]),
        clv_by_scope={SCOPE: CLV_OK})
    assert result.aborted is True
    assert result.promotions == [] and result.demotions == []


# -- daily cap + determinism ---------------------------------------------------------

def _three_strong_scopes():
    scope_rows, clv = {}, {}
    for k in range(3):
        scope = f"src{k}|btc|fam|15m"
        scope_rows[scope] = _rows(
            scope, source=f"src{k}", ticker_prefix=f"KXBTCF{k}",
            win_pattern=lambda i, k=k: (i % 100) < 66 + k * 4)
        clv[scope] = CLV_OK
    return scope_rows, clv


def test_daily_cap_defers_beyond_two_and_counts_prior_actions():
    scope_rows, clv = _three_strong_scopes()
    engine = AutoPromotionEngine()

    full = engine.decide(scope_rows=scope_rows, promoted={}, now_ts=_now_ts(),
                         now_iso="x", rails=RailsVerdict(abort=False),
                         clv_by_scope=clv,
                         realized_by_scope=_forward_map(scope_rows))
    assert len(full.promotions) == 2 and len(full.deferred) == 1
    assert all("daily promotion cap" in d.reason for d in full.deferred)

    one_used = engine.decide(scope_rows=scope_rows, promoted={}, now_ts=_now_ts(),
                             now_iso="x", rails=RailsVerdict(abort=False),
                             promotions_used_today=1, clv_by_scope=clv,
                             realized_by_scope=_forward_map(scope_rows))
    assert len(one_used.promotions) == 1 and len(one_used.deferred) == 2

    spent = engine.decide(scope_rows=scope_rows, promoted={}, now_ts=_now_ts(),
                          now_iso="x", rails=RailsVerdict(abort=False),
                          promotions_used_today=2, clv_by_scope=clv,
                          realized_by_scope=_forward_map(scope_rows))
    assert spent.promotions == [] and len(spent.deferred) == 3


def test_cap_is_shared_between_promotions_and_escalations():
    scope_rows, clv = _three_strong_scopes()
    promoted_scope = "already|btc|fam|15m"
    scope_rows[promoted_scope] = _rows(promoted_scope, source="already",
                                       ticker_prefix="KXBTCALREADY")
    realized = _forward_map(scope_rows)
    realized[promoted_scope] = {
        "n_trades": 90,
        "pnl_by_cluster": {f"c{i}": [2.0] for i in range(60)}}
    result = AutoPromotionEngine().decide(
        scope_rows=scope_rows, promoted={promoted_scope: {"stage": 1}},
        now_ts=_now_ts(), now_iso="x", rails=RailsVerdict(abort=False),
        clv_by_scope=clv, realized_by_scope=realized)
    total_added = len(result.promotions) + len(result.escalations)
    assert total_added == 2
    assert len(result.deferred) == 2  # 4 candidates - 2 budget


def test_decisions_are_deterministic_and_capped_weight_is_stamped():
    scope_rows, clv = _three_strong_scopes()
    engine = AutoPromotionEngine()
    kwargs = dict(scope_rows=scope_rows, promoted={}, now_ts=_now_ts(),
                  now_iso="x", rails=RailsVerdict(abort=False), clv_by_scope=clv,
                  realized_by_scope=_forward_map(scope_rows))
    a = engine.decide(**kwargs)
    b = engine.decide(**kwargs)
    assert [d.to_dict() for d in a.promotions] == [d.to_dict() for d in b.promotions]
    assert [d.to_dict() for d in a.deferred] == [d.to_dict() for d in b.deferred]
    for decision in a.promotions:
        assert decision.stage == 1 and decision.weight_fraction == 0.25
        # The chained dossier carries thresholds beside measurements.
        assert decision.dossier["clusters"]["threshold"] == 300
        assert decision.dossier["evidence_span_days"]["threshold"] == 7.0


def test_eligibility_gate_blocks_unstamped_scopes():
    rows = _rows()
    result = AutoPromotionEngine().decide(
        scope_rows={SCOPE: rows}, promoted={}, now_ts=_now_ts(), now_iso="x",
        rails=RailsVerdict(abort=False), clv_by_scope={SCOPE: CLV_OK},
        eligible_scopes=set())  # nothing opted in
    assert result.promotions == [] and result.deferred == []


def test_config_thresholds_flow_into_the_dossier():
    config = PromotionConfig(min_span_days=3.0, min_beat_rate=0.5,
                             min_clusters=100, min_clusters_no_clv=150)
    rows = _rows(n=120, hours_step=1.0, win_pattern=lambda i: (i % 10) < 8)
    ev = build_scope_evidence(SCOPE, rows, _now_ts(120), clv=CLV_OK, config=config)
    d = ev.dossier()
    assert d["clusters"]["threshold"] == 100
    assert d["evidence_span_days"]["threshold"] == 3.0
    assert d["contested_beat_rate"]["threshold"] == 0.5
    assert ev.evidence_pass(), ev.failing_criteria()
