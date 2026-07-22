"""Auto-promotion runner: rails gathering, evidence I/O, apply, end-to-end."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from autonomy.auto_promotion import EngineResult, RailsVerdict, ScopeDecision
from autonomy.auto_promotion_runner import (
    apply_result,
    clv_by_exact_scope,
    eligible_scopes_from_rows,
    fused_probs_by_source,
    gather_rails_inputs,
    load_mined_family_sizes,
    realized_attribution,
    run_auto_promotion,
)
from autonomy.forecaster import EnsembleForecaster
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.promotion import PromotionRegistry
from autonomy.promotion_ledger import PromotionLedger
from autonomy.strategy_miner import MinedRow

# Fixed and safely in the PAST: the ledger intake quarantines future-dated
# signals against the wall clock, so the fixture era must predate any run.
NOW = datetime(2026, 7, 10, 0, 0, tzinfo=timezone.utc)
NOW_TS, NOW_ISO = NOW.timestamp(), NOW.isoformat()
SCOPE = "crypto_ta_foundry|btc|15m_direction|15m"


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _fresh_runtime(tmp_path: Path) -> Path:
    rd = tmp_path / "runtime"
    rd.mkdir(parents=True, exist_ok=True)
    _write(rd / "heartbeat.json", {
        "alive": True, "last_status": "OK",
        "last_cycle_at": (NOW - timedelta(hours=1)).isoformat(),
    })
    return rd


# -- rails gathering -------------------------------------------------------------

def test_rails_all_clear_on_a_healthy_runtime(tmp_path):
    rd = _fresh_runtime(tmp_path)
    inputs = gather_rails_inputs(rd, NOW_TS, exchange_anomaly_check=lambda: False)
    from autonomy.auto_promotion import evaluate_rails

    assert evaluate_rails(inputs).abort is False


def test_rails_kill_file_and_heartbeat_states(tmp_path):
    rd = _fresh_runtime(tmp_path)
    (rd / "KILL").write_text("stop", encoding="utf-8")
    inputs = gather_rails_inputs(rd, NOW_TS, exchange_anomaly_check=lambda: False)
    assert inputs.kill_file_present is True

    rd2 = _fresh_runtime(tmp_path / "b")
    _write(rd2 / "heartbeat.json", {
        "alive": True, "last_status": "CYCLE_ERROR:ValueError",
        "last_cycle_at": (NOW - timedelta(hours=1)).isoformat(),
    })
    inputs2 = gather_rails_inputs(rd2, NOW_TS, exchange_anomaly_check=lambda: False)
    assert str(inputs2.heartbeat_status).startswith("CYCLE_ERROR")


def test_rails_missing_heartbeat_is_infinitely_stale(tmp_path):
    rd = tmp_path / "runtime"
    rd.mkdir(exist_ok=True)
    inputs = gather_rails_inputs(rd, NOW_TS, exchange_anomaly_check=lambda: False)
    assert inputs.artifact_age_hours == float("inf")
    assert inputs.heartbeat_alive is False


def test_rails_stale_heartbeat_but_optional_stale_clv_is_not_a_global_rail(tmp_path):
    rd = tmp_path / "runtime"
    rd.mkdir(exist_ok=True)
    _write(rd / "heartbeat.json", {
        "alive": True, "last_status": "OK",
        "last_cycle_at": (NOW - timedelta(hours=30)).isoformat(),
    })
    inputs = gather_rails_inputs(rd, NOW_TS, exchange_anomaly_check=lambda: False)
    assert inputs.artifact_age_hours is not None and inputs.artifact_age_hours > 24

    rd2 = _fresh_runtime(tmp_path / "b")
    _write(rd2 / "clv_report.json", {
        "generated_at": (NOW - timedelta(hours=48)).isoformat(), "scopes": {},
    })
    inputs2 = gather_rails_inputs(rd2, NOW_TS, exchange_anomaly_check=lambda: False)
    assert inputs2.artifact_age_hours == 1.0


def test_stale_clv_is_excluded_and_uses_stricter_no_clv_threshold(tmp_path):
    db = _seed_promotable_db(tmp_path)
    rd = _fresh_runtime(tmp_path)
    _write(rd / "clv_report.json", {
        "generated_at": (NOW - timedelta(hours=48)).isoformat(),
        "scopes": {"crypto|15m_direction": {
            "clv_bps_mean": 40.0,
            "clv_bps_ci95_lower": 12.0,
            "clv_bps_ci95_upper": 68.0,
            "n_event_clusters": 55,
        }},
    })

    state = run_auto_promotion(
        db,
        runtime_dir=rd,
        now_ts=NOW_TS,
        now_iso=NOW_ISO,
        exchange_anomaly_check=lambda: False,
        alert_fn=lambda *a, **k: None,
    )

    assert state["status"] == "OK"
    assert state["optional_evidence"]["clv"]["status"] == "STALE_EXCLUDED"
    assert state["optional_evidence"]["clv"]["used"] is False
    review = json.loads(
        (rd / "promotion_human_review_candidates.json").read_text("utf-8")
    )
    dossier = review["candidates"][0]["dossier"]
    assert dossier["clusters"]["threshold"] == 450
    assert dossier["clusters"]["note"] == "no CLV instrumentation -> higher cluster bar"
    assert dossier["clv_ci95_lower"]["measured"] is None


def test_rails_quarantined_source_and_saturated_weight(tmp_path):
    rd = _fresh_runtime(tmp_path)
    _write(rd / "source_health.json", {"crypto_spot_vol": {"fails": 0, "quarantine": 2}})
    inputs = gather_rails_inputs(rd, NOW_TS, exchange_anomaly_check=lambda: False)
    assert inputs.health_error is True

    rd2 = _fresh_runtime(tmp_path / "b")
    inputs2 = gather_rails_inputs(
        rd2, NOW_TS, weights={"x": 8.0}, exchange_anomaly_check=lambda: False)
    assert inputs2.weight_saturation_flagged is True
    inputs3 = gather_rails_inputs(
        rd2, NOW_TS, weights={"x": 7.5}, exchange_anomaly_check=lambda: False)
    assert inputs3.weight_saturation_flagged is False


def test_rails_exchange_check_is_consumed(tmp_path):
    rd = _fresh_runtime(tmp_path)
    assert gather_rails_inputs(
        rd, NOW_TS, exchange_anomaly_check=lambda: True).exchange_anomaly is True


def test_default_exchange_anomaly_fails_closed(monkeypatch):
    from autonomy import exchange_status
    from autonomy.auto_promotion_runner import _default_exchange_anomaly

    # Healthy venue -> no anomaly.
    monkeypatch.setattr(exchange_status, "fetch_exchange_status",
                        lambda: {"exchange_active": True, "trading_active": True})
    assert _default_exchange_anomaly() is False
    # Trading paused -> anomaly.
    monkeypatch.setattr(exchange_status, "fetch_exchange_status",
                        lambda: {"exchange_active": True, "trading_active": False})
    assert _default_exchange_anomaly() is True

    # Unreachable status -> anomaly (unknown defers adding risk; this is the
    # OPPOSITE of the daemon's fail-open per-cycle check, deliberately).
    def _boom():
        raise RuntimeError("network down")

    monkeypatch.setattr(exchange_status, "fetch_exchange_status", _boom)
    assert _default_exchange_anomaly() is True


# -- evidence gathering ------------------------------------------------------------

def _mined(scope: str, source: str, ticker: str, *, challenger=True, eligible=True):
    return MinedRow(
        source=source, ticker=ticker,
        event_cluster=ticker.rsplit("-", 1)[0],
        created_at="2026-07-01T00:00:00+00:00",
        probability_yes=0.7, market_probability=0.55, result_yes=True,
        features={"challenger_only": challenger, "promotion_eligible": eligible},
        scope=scope,
    )


def test_eligible_scopes_require_gating_and_opt_in_majority():
    rows = (
        [_mined("a|x|t|15m", "a", f"KXA-{i}-T") for i in range(4)]
        + [_mined("b|x|t|15m", "b", f"KXB-{i}-T", eligible=False) for i in range(4)]
        + [_mined("c|x|t|15m", "c", f"KXC-{i}-T", challenger=False) for i in range(4)]
    )
    assert eligible_scopes_from_rows(rows) == {"a|x|t|15m"}


def test_clv_maps_specialist_grain_onto_exact_scopes():
    report = {"scopes": {
        "crypto|15m_direction": {
            "clv_bps_mean": 40.0, "clv_bps_ci95_lower": 12.0,
            "clv_bps_ci95_upper": 68.0, "n_event_clusters": 55,
        },
        "mlb|winner": {"clv_bps_mean": 5.0, "clv_bps_ci95_lower": None},
    }}
    scopes = {SCOPE, "mlb_structural_winner|mlb|winner|pre", "sports_elo|nfl|winner|pre"}
    mapped = clv_by_exact_scope(report, scopes)
    assert set(mapped) == {SCOPE}
    assert mapped[SCOPE]["lower"] == 12.0
    assert mapped[SCOPE]["grain"] == "specialist|market_type"


def test_fused_probs_cover_champions_and_promoted_sources():
    rows = (
        [_mined("champ|x|t|15m", "champ", f"KXA-{i}-T", challenger=False)
         for i in range(4)]
        + [_mined("chal|x|t|15m", "chal", f"KXB-{i}-T") for i in range(4)]
        + [_mined("promoted|x|t|15m", "promoted", f"KXC-{i}-T") for i in range(4)]
    )
    tape = fused_probs_by_source(rows, promoted_sources={"promoted"})
    assert set(tape) == {"champ", "promoted"}  # never the plain challenger
    assert tape["champ"]["KXA-0-T"] == 0.7


def test_mined_family_sizes_clamped_and_fail_closed(tmp_path):
    path = tmp_path / "fams.json"
    assert load_mined_family_sizes(path) == {}
    _write(path, {"a|x|t|15m": 120, "b|x|t|15m": 0, "c|x|t|15m": "junk"})
    fams = load_mined_family_sizes(path)
    assert fams == {"a|x|t|15m": 120, "b|x|t|15m": 1}


def test_realized_attribution_share_weights_settled_trades(tmp_path):
    from autonomy.ontology import (
        Decision, DecisionAction, Forecast, OutcomeKind, TradeOutcome,
    )

    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        ticker = "KXBTC15M-26JUL16-T60000"
        ledger.record_signal(Signal(
            source="crypto_ta_foundry", market_ticker=ticker,
            probability_yes=0.7, uncertainty=0.1, rationale="",
            features={"challenger_only": True, "market_type": "15m_direction",
                      "hours_to_close": 0.2},
            created_at="2026-07-16T00:00:00+00:00"), mode="live")
        ledger._conn.execute(  # noqa: SLF001
            "UPDATE signals SET ingested_at=? WHERE source=? AND market_ticker=?",
            ("2026-07-16T00:01:00+00:00", "crypto_ta_foundry", ticker),
        )
        ledger._conn.commit()  # noqa: SLF001
        forecast = Forecast(
            market_ticker=ticker, probability_yes=0.7, uncertainty=0.1,
            sources_used={"crypto_ta_foundry": 0.6, "market_prior": 0.4},
            market_implied_yes=0.55, edge_yes=0.15, rationale="")
        ledger.record_decision(Decision(
            decision_id="d1", market_ticker=ticker,
            action=DecisionAction.BUY_YES, side="yes", price_cents=55,
            count=1, ev_cents_per_contract=10.0, kelly_fraction=0.01,
            notional_cents=55, forecast=forecast, risk_snapshot={},
            created_at="2026-07-16T00:05:00+00:00"))
        ledger.record_outcome(TradeOutcome(
            decision_id="d1", market_ticker=ticker, kind=OutcomeKind.FILLED,
            order_id="o1", fill_count=1, fill_price_cents=55, pnl_cents=None,
            broker_contacted=False,
            created_at="2026-07-16T00:06:00+00:00"))
        ledger.record_settlement(ticker, True)
        ledger._conn.execute(  # noqa: SLF001
            "UPDATE settlements SET settled_at=? WHERE market_ticker=?",
            ("2026-07-16T00:59:00+00:00", ticker),
        )
        ledger._conn.commit()  # noqa: SLF001
        ledger.record_outcome(TradeOutcome(
            decision_id="d1", market_ticker=ticker,
            kind=OutcomeKind.SETTLED_WIN, order_id="o1", fill_count=1,
            fill_price_cents=55, pnl_cents=45, broker_contacted=False,
            created_at="2026-07-16T01:00:00+00:00"))

        conn = sqlite3.connect(tmp_path / "l.db")
        try:
            attribution = realized_attribution(conn)
        finally:
            conn.close()
    finally:
        ledger.close()

    assert SCOPE in attribution
    entry = attribution[SCOPE]
    assert entry["n_trades"] == 1
    from autonomy.correlation import group_key

    cluster = group_key(ticker)
    assert entry["pnl_by_cluster"][cluster] == [0.45 * 0.6]  # share-weighted


# -- apply --------------------------------------------------------------------------

def _decision(action: str, scope: str = SCOPE, stage: int = 1,
              weight: float = 0.25) -> ScopeDecision:
    return ScopeDecision(scope=scope, action=action, stage=stage,
                         weight_fraction=weight, dossier={"k": "v"}, reason="r")


def test_apply_result_writes_registry_chain_and_alerts(tmp_path):
    alerts = []

    def alert_fn(kind, message, detail=None, now_iso=None):
        alerts.append((kind, message))

    promotions_path = tmp_path / "promotions.json"
    ledger_path = tmp_path / "chain.jsonl"
    result = EngineResult(
        aborted=False, rails=RailsVerdict(abort=False),
        promotions=[_decision("PROMOTE")], generated_at=NOW_ISO)
    applied = apply_result(result, promotions_path=promotions_path,
                           ledger_path=ledger_path, now_iso=NOW_ISO,
                           alert_fn=alert_fn)
    assert applied["promoted"] == [SCOPE]

    doc = json.loads(promotions_path.read_text(encoding="utf-8"))
    assert doc["version"] == 2
    entry = doc["promotions"][0]
    assert entry["source"] == "crypto_ta_foundry" and entry["subject"] == "btc"
    assert entry["stage"] == 1 and entry["weight_fraction"] == 0.25
    assert entry["promoted_by"] == "auto_promotion_engine"

    chain = PromotionLedger(ledger_path).read_verified()
    assert [e.action for e in chain] == ["PROMOTE"]
    assert chain[0].payload["dossier"] == {"k": "v"}
    assert entry["evidence_ref"] == chain[0].entry_hash
    assert [kind for kind, _ in alerts] == ["AUTO_PROMOTION"]

    # The registry immediately honors the stage-1 probation weight.
    registry = PromotionRegistry(promotions_path, tmp_path / "demotions.json")
    assert registry.is_promoted(SCOPE) is True
    assert registry.stage_for(SCOPE) == 1
    assert registry.weight_multiplier(SCOPE) == 0.25


def test_apply_result_escalation_updates_entry_to_full_weight(tmp_path):
    alerts = []

    def alert_fn(kind, message, detail=None, now_iso=None):
        alerts.append(kind)

    promotions_path = tmp_path / "promotions.json"
    ledger_path = tmp_path / "chain.jsonl"
    apply_result(EngineResult(aborted=False, rails=RailsVerdict(abort=False),
                              promotions=[_decision("PROMOTE")]),
                 promotions_path=promotions_path, ledger_path=ledger_path,
                 now_iso=NOW_ISO, alert_fn=alert_fn)
    apply_result(EngineResult(aborted=False, rails=RailsVerdict(abort=False),
                              escalations=[_decision("ESCALATE", stage=2, weight=1.0)]),
                 promotions_path=promotions_path, ledger_path=ledger_path,
                 now_iso=NOW_ISO, alert_fn=alert_fn)
    registry = PromotionRegistry(promotions_path, tmp_path / "demotions.json")
    assert registry.stage_for(SCOPE) == 2
    assert registry.weight_multiplier(SCOPE) == 1.0
    chain = PromotionLedger(ledger_path).read_verified()
    assert [e.action for e in chain] == ["PROMOTE", "ESCALATE"]
    assert alerts == ["AUTO_PROMOTION", "AUTO_ESCALATION"]


def test_apply_result_demotion_chains_and_alerts_without_touching_file(tmp_path):
    alerts = []
    promotions_path = tmp_path / "promotions.json"
    result = EngineResult(aborted=False, rails=RailsVerdict(abort=False),
                          demotions=[_decision("DEMOTE", weight=0.0)])
    apply_result(result, promotions_path=promotions_path,
                 ledger_path=tmp_path / "chain.jsonl", now_iso=NOW_ISO,
                 alert_fn=lambda kind, *a, **k: alerts.append(kind))
    assert alerts == ["AUTO_DEMOTION"]
    assert not promotions_path.exists()  # demotion alone never rewrites promotions
    chain = PromotionLedger(tmp_path / "chain.jsonl").read_verified()
    assert [e.action for e in chain] == ["DEMOTE"]


# -- end-to-end run_auto_promotion -----------------------------------------------------

def _seed_promotable_db(tmp_path: Path, *, n: int = 320) -> Path:
    """A ledger where one crypto scope has genuinely earned stage 1."""
    db = tmp_path / "ledger.db"
    ledger = AutonomyLedger(db_path=db)
    try:
        start = NOW - timedelta(days=14)
        signals = []
        for i in range(n):
            at = (start + timedelta(minutes=63 * i)).isoformat()
            ticker = f"KXBTC15M-N{i:04d}-T60000"
            signals.append(Signal(
                source="market_prior", market_ticker=ticker,
                probability_yes=0.55, uncertainty=0.1, rationale="",
                features={}, created_at=at))
            signals.append(Signal(
                source="crypto_ta_foundry", market_ticker=ticker,
                probability_yes=0.75, uncertainty=0.1, rationale="",
                features={"challenger_only": True, "promotion_eligible": True,
                          "market_type": "15m_direction", "hours_to_close": 0.2},
                created_at=at))
        # Promotion authority is earned only from forward/live-observed rows;
        # retro replay remains a separate research-only lane.
        accepted = ledger.record_signals(signals, mode="live")
        assert all(accepted)
        # 75% win rate: comfortably clear of the Brier-edge CI boundary (a
        # 70% rate lands the bootstrap lower bound at ~exactly zero here).
        for i in range(n):
            ledger.record_settlement(f"KXBTC15M-N{i:04d}-T60000", (i % 4) < 3)
    finally:
        ledger.close()
    return db


def test_run_aborts_on_kill_file_with_chain_record_and_alert(tmp_path):
    rd = _fresh_runtime(tmp_path)
    (rd / "KILL").write_text("stop", encoding="utf-8")
    alerts = []
    state = run_auto_promotion(
        tmp_path / "missing.db", runtime_dir=rd, now_ts=NOW_TS, now_iso=NOW_ISO,
        exchange_anomaly_check=lambda: False,
        alert_fn=lambda kind, *a, **k: alerts.append(kind))
    assert state["status"] == "ABORTED"
    assert state["reasons"] == ["kill_file_present"]
    assert alerts == ["PROMOTION_RUN_ABORTED"]
    chain = PromotionLedger(rd / "promotion_ledger.jsonl").read_verified()
    assert [e.action for e in chain] == ["ABORT"]
    # The dashboard artifact records the abort too.
    persisted = json.loads((rd / "auto_promotion_state.json").read_text("utf-8"))
    assert persisted["status"] == "ABORTED"
    assert persisted["live_trading_authority"] == "OPERATOR_ONLY_UNAFFECTED"


def test_run_aborts_when_the_hash_chain_is_broken(tmp_path):
    rd = _fresh_runtime(tmp_path)
    (rd / "promotion_ledger.jsonl").write_text("tampered\n", encoding="utf-8")
    alerts = []
    state = run_auto_promotion(
        tmp_path / "missing.db", runtime_dir=rd, now_ts=NOW_TS, now_iso=NOW_ISO,
        exchange_anomaly_check=lambda: False,
        alert_fn=lambda kind, *a, **k: alerts.append(kind))
    assert state["status"] == "ABORTED"
    assert state["reasons"] == ["promotion_ledger_broken"]
    assert alerts == ["PROMOTION_RUN_ABORTED"]


def test_run_no_db_reports_and_promotes_nothing(tmp_path):
    rd = _fresh_runtime(tmp_path)
    state = run_auto_promotion(
        tmp_path / "missing.db", runtime_dir=rd, now_ts=NOW_TS, now_iso=NOW_ISO,
        exchange_anomaly_check=lambda: False, alert_fn=lambda *a, **k: None)
    assert state["status"] == "NO_DB"
    assert not (rd / "promotions.json").exists()


def test_run_with_positive_fill_free_diagnostics_stays_human_review_only(tmp_path):
    db = _seed_promotable_db(tmp_path)
    rd = _fresh_runtime(tmp_path)
    _write(rd / "clv_report.json", {
        "generated_at": (NOW - timedelta(hours=2)).isoformat(),
        "scopes": {"crypto|15m_direction": {
            "clv_bps_mean": 40.0, "clv_bps_ci95_lower": 12.0,
            "clv_bps_ci95_upper": 68.0, "n_event_clusters": 55}},
    })
    alerts = []
    state = run_auto_promotion(
        db, runtime_dir=rd, now_ts=NOW_TS, now_iso=NOW_ISO,
        exchange_anomaly_check=lambda: False,
        alert_fn=lambda kind, *a, **k: alerts.append(kind))
    assert state["status"] == "OK"
    assert state["promoted"] == []
    assert [row["scope"] for row in state["human_review_candidates"]] == [SCOPE]
    assert "AUTO_PROMOTION" not in alerts

    registry = PromotionRegistry(rd / "promotions.json", rd / "auto_demotions.json")
    assert registry.is_promoted(SCOPE) is False
    chain = PromotionLedger(rd / "promotion_ledger.jsonl").read_verified()
    assert chain == ()
    candidates = json.loads(
        (rd / "promotion_human_review_candidates.json").read_text("utf-8")
    )
    dossier = candidates["candidates"][0]["dossier"]
    assert dossier["counterfactual_pnl_ci95_lower"]["pass"] is True
    assert dossier["forward_witnessed_fill_evidence"]["pass"] is False

    # Second run remains a non-authoritative review candidate; the daily
    # add-risk budget was never consumed.
    state2 = run_auto_promotion(
        db, runtime_dir=rd, now_ts=NOW_TS, now_iso=NOW_ISO,
        exchange_anomaly_check=lambda: False, alert_fn=lambda *a, **k: None)
    assert state2["status"] == "OK"
    assert state2["promoted"] == [] and state2["escalated"] == []
    assert state2["promotions_used_today_before_run"] == 0


def test_run_without_clv_never_promotes_from_counterfactual_roi(tmp_path):
    # Positive in-sample ROI remains visible for research, but cannot substitute
    # for registered, isolated forward witnessed-fill evidence.
    db = _seed_promotable_db(tmp_path)
    rd = _fresh_runtime(tmp_path)
    state = run_auto_promotion(
        db, runtime_dir=rd, now_ts=NOW_TS, now_iso=NOW_ISO,
        exchange_anomaly_check=lambda: False, alert_fn=lambda *a, **k: None)
    assert state["status"] == "OK"
    assert state["promoted"] == []
    assert [row["scope"] for row in state["human_review_candidates"]] == [SCOPE]


def test_run_demotes_a_promoted_scope_and_sticks_it(tmp_path):
    db = tmp_path / "ledger.db"
    ledger = AutonomyLedger(db_path=db)
    try:
        start = NOW - timedelta(days=14)
        signals = []
        for i in range(320):
            at = (start + timedelta(minutes=63 * i)).isoformat()
            ticker = f"KXBTC15M-N{i:04d}-T60000"
            signals.append(Signal(
                source="market_prior", market_ticker=ticker,
                probability_yes=0.55, uncertainty=0.1, rationale="",
                features={}, created_at=at))
            signals.append(Signal(
                source="crypto_ta_foundry", market_ticker=ticker,
                probability_yes=0.75, uncertainty=0.1, rationale="",
                features={"challenger_only": True, "promotion_eligible": True,
                          "market_type": "15m_direction", "hours_to_close": 0.2},
                created_at=at))
        ledger.record_signals(signals, mode="live")
        for i in range(320):
            ledger.record_settlement(f"KXBTC15M-N{i:04d}-T60000", (i % 10) < 3)
    finally:
        ledger.close()

    rd = _fresh_runtime(tmp_path)
    _write(rd / "promotions.json", {"version": 2, "promotions": [{
        "source": "crypto_ta_foundry", "subject": "btc",
        "market_type": "15m_direction", "horizon": "15m",
        "stage": 1, "weight_fraction": 0.25,
        "promoted_at": "2026-07-01T00:00:00+00:00",
        "promoted_by": "auto_promotion_engine", "evidence_ref": "x"}]})
    alerts = []
    state = run_auto_promotion(
        db, runtime_dir=rd, now_ts=NOW_TS, now_iso=NOW_ISO,
        exchange_anomaly_check=lambda: False,
        alert_fn=lambda kind, *a, **k: alerts.append(kind))
    assert state["demoted"] == [SCOPE]
    assert "AUTO_DEMOTION" in alerts
    demotions = json.loads((rd / "auto_demotions.json").read_text("utf-8"))
    assert demotions["demotions"][0]["scope"] == SCOPE
    registry = PromotionRegistry(rd / "promotions.json", rd / "auto_demotions.json")
    assert registry.is_promoted(SCOPE) is False  # sticky demotion wins


# -- stage-aware fusion (registry + forecaster integration) ---------------------------

def _crypto_market() -> MarketView:
    return MarketView(
        ticker="KXBTC15M-26JUL16-T60000", title="BTC 15m",
        vertical=Vertical.CRYPTO, status="open",
        close_time="2026-07-16T12:15:00+00:00",
        yes_bid=54, yes_ask=56, no_bid=44, no_ask=46,
        volume=1000, liquidity=1000, raw={})


def _signals(market: MarketView) -> list[Signal]:
    prior = Signal(source="market_prior", market_ticker=market.ticker,
                   probability_yes=0.5, uncertainty=0.1, rationale="")
    challenger = Signal(
        source="crypto_ta_foundry", market_ticker=market.ticker,
        probability_yes=0.9, uncertainty=0.1, rationale="",
        features={"challenger_only": True, "promotion_eligible": True,
                  "market_type": "15m_direction", "hours_to_close": 0.2})
    return [prior, challenger]


def _entry(stage: int | None, weight_fraction: float | None) -> dict:
    entry = {"source": "crypto_ta_foundry", "subject": "btc",
             "market_type": "15m_direction", "horizon": "15m"}
    if stage is not None:
        entry["stage"] = stage
    if weight_fraction is not None:
        entry["weight_fraction"] = weight_fraction
    return entry


def test_probation_weight_caps_stage1_fusion_influence(tmp_path):
    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        market = _crypto_market()
        probation = tmp_path / "p1.json"
        _write(probation, {"version": 2, "promotions": [_entry(1, 0.25)]})
        full = tmp_path / "p2.json"
        _write(full, {"version": 2, "promotions": [_entry(2, 1.0)]})

        fused_probation = EnsembleForecaster(
            ledger, promotion=PromotionRegistry(probation, tmp_path / "d.json"),
        ).fuse(market, _signals(market))
        fused_full = EnsembleForecaster(
            ledger, promotion=PromotionRegistry(full, tmp_path / "d.json"),
        ).fuse(market, _signals(market))
        assert fused_probation is not None and fused_full is not None
        # Both include the challenger (probability pulled above the prior)...
        assert fused_probation.probability_yes > 0.5
        # ...but probation gives it strictly less influence than full weight.
        assert fused_probation.probability_yes < fused_full.probability_yes
        assert (fused_probation.sources_used["crypto_ta_foundry"]
                < fused_full.sources_used["crypto_ta_foundry"])
    finally:
        ledger.close()


def test_legacy_promotion_entries_default_to_full_weight(tmp_path):
    path = tmp_path / "p.json"
    _write(path, {"promotions": [_entry(None, None)]})  # pre-ladder human entry
    registry = PromotionRegistry(path, tmp_path / "d.json")
    assert registry.is_promoted(SCOPE) is True
    assert registry.stage_for(SCOPE) == 2
    assert registry.weight_multiplier(SCOPE) == 1.0
    snapshot = registry.snapshot()
    assert snapshot["stages"][SCOPE] == 2
    assert snapshot["weight_fractions"][SCOPE] == 1.0


def test_registry_corrupt_stage_values_fail_safe(tmp_path):
    path = tmp_path / "p.json"
    _write(path, {"promotions": [{**_entry(None, None),
                                  "stage": "junk", "weight_fraction": "junk"}]})
    registry = PromotionRegistry(path, tmp_path / "d.json")
    assert registry.stage_for(SCOPE) == 2
    assert registry.weight_multiplier(SCOPE) == 1.0


def test_non_promoted_scope_multiplier_is_neutral(tmp_path):
    registry = PromotionRegistry(tmp_path / "p.json", tmp_path / "d.json")
    assert registry.weight_multiplier(SCOPE) == 1.0
    assert registry.stage_for(SCOPE) is None
