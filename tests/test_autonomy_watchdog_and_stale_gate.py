"""Wave-1 D2+D3: stale-data submit gate, ops watchdog, dashboard status endpoint."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from autonomy.allocator import Allocator
from autonomy.executor import Executor
from autonomy.forecaster import EnsembleForecaster
from autonomy.ontology import MarketView, OutcomeKind, SessionMode, Signal
from autonomy.risk_brain import RiskBrain
from autonomy.scanner import classify_vertical, to_market_view
from autonomy.staleness import (
    DEFAULT_STALENESS_POLICY,
    StalenessPolicy,
    evaluate_snapshot_freshness,
    to_epoch_seconds,
)
from autonomy.watchdog import (
    DEFAULT_TASKS,
    TaskSpec,
    evaluate_watchdog,
    fire_watchdog_alerts,
    run_watchdog,
)

NOW = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
NOW_EPOCH = NOW.timestamp()


def _iso(seconds_ago: float) -> str:
    return (NOW - timedelta(seconds=seconds_ago)).isoformat()


# ---------------------------------------------------------------- staleness policy


def test_policy_horizon_defaults():
    pol = DEFAULT_STALENESS_POLICY
    assert pol.max_age_seconds("KXBTC15M-26JUL161200-30") == 60.0
    assert pol.max_age_seconds("KXBTCD-26JUL1617-T64999.99") == 180.0
    assert pol.max_age_seconds("KXMLBGAME-26JUL16-NYY", is_live_market=True) == 120.0
    assert pol.max_age_seconds("KXMLBGAME-26JUL16-NYY") == 300.0
    assert pol.max_age_seconds("KXWHATEVER-1") == 300.0


def test_to_epoch_parses_iso_and_numbers_and_fails_closed():
    assert to_epoch_seconds("2026-07-16T12:00:00+00:00") == NOW_EPOCH
    assert to_epoch_seconds("2026-07-16T12:00:00Z") == NOW_EPOCH
    assert to_epoch_seconds(NOW_EPOCH) == NOW_EPOCH
    assert to_epoch_seconds(None) is None
    assert to_epoch_seconds("") is None
    assert to_epoch_seconds("not a timestamp") is None


def test_freshness_verdicts():
    fresh = evaluate_snapshot_freshness("KXBTC15M-X", _iso(30), NOW_EPOCH)
    assert fresh["fresh"] is True and fresh["reason"] == "fresh"

    stale = evaluate_snapshot_freshness("KXBTC15M-X", _iso(90), NOW_EPOCH)
    assert stale["fresh"] is False
    assert stale["reason"] == "stale_market_snapshot"
    assert stale["age_seconds"] > stale["max_age_seconds"]

    # Fail-closed: unknown freshness is stale, never fresh.
    missing = evaluate_snapshot_freshness("KXBTC15M-X", None, NOW_EPOCH)
    assert missing["fresh"] is False and missing["reason"] == "missing_snapshot_timestamp"

    future = evaluate_snapshot_freshness("KXBTC15M-X", _iso(-120), NOW_EPOCH)
    assert future["fresh"] is False and future["reason"] == "snapshot_timestamp_in_future"


def test_sports_live_vs_pregame_thresholds():
    live = evaluate_snapshot_freshness("KXNBAGAME-X", _iso(200), NOW_EPOCH, is_live_market=True)
    pregame = evaluate_snapshot_freshness("KXNBAGAME-X", _iso(200), NOW_EPOCH)
    assert live["fresh"] is False  # 200s > 120s live budget
    assert pregame["fresh"] is True  # 200s <= 300s pregame budget


# ---------------------------------------------------------------- executor gate


def _market(ticker="KXBTCD-26JUL16-T100000.00", yes_bid=30, yes_ask=40, **overrides) -> MarketView:
    defaults = dict(
        ticker=ticker,
        title="test market",
        vertical=classify_vertical(ticker),
        status="active",
        close_time=(datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        yes_bid=yes_bid,
        yes_ask=yes_ask,
        no_bid=100 - yes_ask,
        no_ask=100 - yes_bid,
        volume=500,
        liquidity=1000,
    )
    defaults.update(overrides)
    return MarketView(**defaults)


def _forecast(market, probability, uncertainty=0.08):
    class _FakeLedger:
        def get_weight(self, source, default=1.0):
            return 1.0

    return EnsembleForecaster(_FakeLedger()).fuse(market, [
        Signal(source="s", market_ticker=market.ticker,
               probability_yes=probability, uncertainty=uncertainty, rationale=""),
    ])


def _decision(tmp_path, market=None):
    market = market or _market()
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    return Allocator(brain).decide(market, _forecast(market, 0.85), brain.load_state(100_000))


def test_executor_blocks_stale_snapshot_and_counts(tmp_path):
    decision = _decision(tmp_path)
    executor = Executor(
        SessionMode.SHADOW,
        session_path=tmp_path / "s.json", kill_path=tmp_path / "KILL",
        staleness_policy=StalenessPolicy(),
        now_fn=lambda: NOW_EPOCH,
    )
    outcome = asyncio.run(executor.execute(decision, snapshot_ts=_iso(500)))
    assert outcome.kind is OutcomeKind.BLOCKED_LOCAL
    assert outcome.broker_contacted is False
    assert outcome.detail["reason"] == "stale_market_snapshot"
    assert outcome.detail["snapshot_age_seconds"] == 500.0
    assert outcome.detail["max_age_seconds"] == 180.0  # slow crypto budget
    assert executor.stale_block_count == 1
    # Refusals accumulate — never a silent skip.
    asyncio.run(executor.execute(decision, snapshot_ts=None))
    assert executor.stale_block_count == 2


def test_executor_fresh_snapshot_passes_gate(tmp_path):
    decision = _decision(tmp_path)
    executor = Executor(
        SessionMode.SHADOW,
        session_path=tmp_path / "s.json", kill_path=tmp_path / "KILL",
        staleness_policy=StalenessPolicy(),
        now_fn=lambda: NOW_EPOCH,
    )
    outcome = asyncio.run(executor.execute(decision, snapshot_ts=_iso(60)))
    assert outcome.kind is OutcomeKind.SHADOW
    assert executor.stale_block_count == 0


def test_executor_gate_fail_closed_on_missing_timestamp(tmp_path):
    decision = _decision(tmp_path)
    executor = Executor(
        SessionMode.SHADOW,
        session_path=tmp_path / "s.json", kill_path=tmp_path / "KILL",
        staleness_policy=StalenessPolicy(),
        now_fn=lambda: NOW_EPOCH,
    )
    outcome = asyncio.run(executor.execute(decision))  # no snapshot_ts at all
    assert outcome.kind is OutcomeKind.BLOCKED_LOCAL
    assert outcome.detail["reason"] == "missing_snapshot_timestamp"


def test_executor_without_policy_keeps_legacy_behavior(tmp_path):
    decision = _decision(tmp_path)
    executor = Executor(
        SessionMode.SHADOW, session_path=tmp_path / "s.json", kill_path=tmp_path / "KILL",
    )
    outcome = asyncio.run(executor.execute(decision))  # gate inactive: no policy
    assert outcome.kind is OutcomeKind.SHADOW


def _write_live_session(path):
    from autonomy.executor import AUTONOMY_ACK, SESSION_ACCOUNTING_VERSION

    path.write_text(json.dumps({
        "mode": "LIVE",
        "ack": AUTONOMY_ACK,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "accounting_version": SESSION_ACCOUNTING_VERSION,
    }), encoding="utf-8")


def test_live_submit_rechecks_exchange_halt_state(tmp_path):
    session = tmp_path / "s.json"
    _write_live_session(session)
    decision = _decision(tmp_path)

    halted = Executor(
        SessionMode.LIVE, session_path=session, kill_path=tmp_path / "KILL",
        exchange_status_fn=lambda: {"exchange_active": True, "trading_active": False},
    )
    outcome = asyncio.run(halted.execute(decision))
    assert outcome.kind is OutcomeKind.BLOCKED_LOCAL
    assert outcome.detail["reason"] == "trading_halted_at_submit"
    assert outcome.broker_contacted is False

    maintenance = Executor(
        SessionMode.LIVE, session_path=session, kill_path=tmp_path / "KILL",
        exchange_status_fn=lambda: {"exchange_active": False},
    )
    outcome2 = asyncio.run(maintenance.execute(decision))
    assert outcome2.detail["reason"] == "exchange_maintenance_at_submit"


def test_live_submit_exchange_probe_failure_fails_open(tmp_path):
    """Unknown venue state is NOT down: the check must never be a stall point."""
    session = tmp_path / "s.json"
    _write_live_session(session)
    decision = _decision(tmp_path)

    def boom():
        raise RuntimeError("probe down")

    class FakeAdapter:
        async def submit_limit_order(self, request):
            from predator_mesh.brokers.livebrokerfirewall_adapter import SubmitResult

            return SubmitResult(submitted=True, order_id="ord-1", state="OPEN", raw={}, errors=[])

        async def close(self):
            pass

    executor = Executor(
        SessionMode.LIVE, session_path=session, kill_path=tmp_path / "KILL",
        exchange_status_fn=boom, adapter_factory=lambda d: FakeAdapter(),
    )
    outcome = asyncio.run(executor.execute(decision))
    assert outcome.kind is OutcomeKind.ACCEPTED


def test_scanner_stamps_fetched_at():
    from autonomy.scanner import MarketScanner

    page = {"markets": [{
        "ticker": "KXBTCD-26JUL16-T100000.00", "status": "active",
        "yes_bid": 30, "yes_ask": 40, "no_bid": 60, "no_ask": 70,
    }]}
    views = MarketScanner(fetch_series=lambda s: page, watchlist=["KXBTCD"]).scan()
    assert len(views) == 1
    stamped = to_epoch_seconds(views[0].fetched_at)
    assert stamped is not None
    assert abs(stamped - datetime.now(timezone.utc).timestamp()) < 60


def test_to_market_view_default_has_unknown_freshness():
    view = to_market_view({"ticker": "KXBTC-26JUL16-T1", "status": "active"})
    assert view.fetched_at is None


def test_brain_passes_snapshot_ts_to_executor(tmp_path, monkeypatch):
    """The cycle wires MarketView.fetched_at into the executor's stale gate."""
    # Isolate from any cwd-relative runtime/no_edge_map.json: the fusion floor is
    # tested on its own; here a strong signal must reach the executor regardless
    # of whatever scopes live evidence has floored.
    monkeypatch.setattr("autonomy.no_edge_map.load_negative_scopes", lambda *a, **k: frozenset())
    from autonomy.brain import PredatorBrain
    from autonomy.learner import Learner
    from autonomy.ledger import AutonomyLedger
    from autonomy.reconciler import Reconciler
    from autonomy.scanner import MarketScanner
    from autonomy.signals.base import SourceRegistry
    from autonomy.signals.crypto_spot import CryptoSpotVolSignal
    from autonomy.signals.market_prior import MarketPriorSignal

    ledger = AutonomyLedger(db_path=tmp_path / "ledger.db")
    registry = SourceRegistry()
    registry.register(MarketPriorSignal())
    registry.register(CryptoSpotVolSignal(fetch_spot_and_vol=lambda asset: (100_000.0, 0.5)))

    def fetch_series(series):
        if series != "KXBTCD":
            return {"markets": []}
        return {"markets": [{
            "ticker": "KXBTCD-26JUL16-T100000.00",
            "title": "BTC above $100k", "status": "active",
            "close_time": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            "yes_bid": 30, "yes_ask": 40, "no_bid": 60, "no_ask": 70,
            "volume": 500, "liquidity": 1000,
            "strike_type": "greater", "floor_strike": 100000.0,
        }]}

    seen: list = []

    class SpyExecutor(Executor):
        async def execute(self, decision, *, snapshot_ts=None, is_live_market=False):
            seen.append(snapshot_ts)
            return await super().execute(
                decision, snapshot_ts=snapshot_ts, is_live_market=is_live_market,
            )

    brain = PredatorBrain(
        mode=SessionMode.SHADOW,
        ledger=ledger,
        registry=registry,
        scanner=MarketScanner(fetch_series=fetch_series, watchlist=["KXBTCD"]),
        risk_brain=RiskBrain(state_path=tmp_path / "risk.json"),
        executor=SpyExecutor(
            SessionMode.SHADOW, session_path=tmp_path / "s.json",
            kill_path=tmp_path / "KILL", staleness_policy=StalenessPolicy(),
        ),
        reconciler=Reconciler(ledger, fetch_market_result=lambda t: {"result": ""}),
        learner=Learner(ledger),
    )
    try:
        report = asyncio.run(brain.run_cycle())
        assert report.status == "CYCLE_OK"
        assert report.orders_placed == 1  # fresh scan stamp passes the gate
        assert seen and to_epoch_seconds(seen[0]) is not None
    finally:
        ledger.close()


# ---------------------------------------------------------------- watchdog


def _real_iso(seconds_ago: float) -> str:
    """Real-clock stamp: the dashboard/status snapshot uses the actual now."""
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat()


def _real_now_epoch() -> float:
    return datetime.now(timezone.utc).timestamp()


def _runtime(tmp_path: Path, *, heartbeat_age=60.0, mispricing_age=30.0) -> Path:
    rd = tmp_path / "runtime"
    rd.mkdir(parents=True, exist_ok=True)
    (rd / "heartbeat.json").write_text(json.dumps({
        "alive": True, "last_cycle_at": _real_iso(heartbeat_age), "last_status": "CYCLE_OK",
    }), encoding="utf-8")
    (rd / "mispricing_monitor_latest.json").write_text(json.dumps({
        "generated_at": _real_iso(mispricing_age),
    }), encoding="utf-8")
    return rd


def test_watchdog_fresh_artifacts_are_healthy_for_their_tasks(tmp_path):
    rd = _runtime(tmp_path)
    status = evaluate_watchdog(rd, now_epoch=_real_now_epoch())
    rows = {r["task_name"]: r for r in status["tasks"]}
    assert rows["DummyShadowPredator"]["stale"] is False
    assert 59.0 <= rows["DummyShadowPredator"]["age_seconds"] <= 120.0
    assert rows["DummyShadowPredator"]["threshold_seconds"] == 1200.0  # 2x 10min
    assert rows["DummyMispricingMonitor"]["stale"] is False
    # Absent artifacts are fail-closed stale.
    assert rows["DummyCryptoPaperTwin"]["stale"] is True
    assert rows["DummyCryptoPaperTwin"]["timestamp_source"] == "missing"
    assert "DummyCryptoPaperTwin" in status["stale_tasks"]
    assert status["healthy"] is False


def test_watchdog_flags_stale_task_beyond_two_cadences(tmp_path):
    rd = _runtime(tmp_path, mispricing_age=300.0)  # 2min cadence -> stale at 240s
    status = evaluate_watchdog(rd, now_epoch=_real_now_epoch())
    rows = {r["task_name"]: r for r in status["tasks"]}
    assert rows["DummyMispricingMonitor"]["stale"] is True
    assert "DummyMispricingMonitor" in status["stale_tasks"]


def test_watchdog_covers_every_default_task(tmp_path):
    names = {spec.name for spec in DEFAULT_TASKS}
    assert names == {
        "DummyShadowPredator", "DummyMispricingMonitor", "DummyCryptoPaperTwin",
        "DummySportsSimulation", "DummySimulationTrainer", "DummyStrategyMiner",
        "DummyReadinessReport",
    }
    status = evaluate_watchdog(tmp_path, now_epoch=NOW_EPOCH)
    assert {r["task_name"] for r in status["tasks"]} == names


def test_watchdog_cycle_error_streak_and_kill_file(tmp_path):
    rd = _runtime(tmp_path)
    lines = [json.dumps({"status": "CYCLE_OK", "at": "t0"})]
    lines += [json.dumps({"status": "CYCLE_ERROR:OperationalError", "at": f"t{i}"}) for i in range(4)]
    (rd / "cycles.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (rd / "KILL").write_text("x", encoding="utf-8")
    status = evaluate_watchdog(rd, now_epoch=_real_now_epoch())
    assert status["cycle_error_streak"] == 4
    assert status["latest_cycle_status"] == "CYCLE_ERROR:OperationalError"
    assert status["kill_file_present"] is True
    assert status["healthy"] is False


def test_watchdog_ledger_and_disk_thresholds(tmp_path):
    rd = _runtime(tmp_path)
    (rd / "ledger.db").write_bytes(b"x" * 2_000_000)  # 0.002 GB
    over = evaluate_watchdog(rd, now_epoch=_real_now_epoch(), ledger_max_gb=0.001)
    assert over["ledger_over_threshold"] is True
    under = evaluate_watchdog(rd, now_epoch=_real_now_epoch(), ledger_max_gb=1.0)
    assert under["ledger_over_threshold"] is False
    assert under["ledger_size_gb"] == 0.002
    # An absurd floor trips disk_below_floor deterministically.
    floored = evaluate_watchdog(rd, now_epoch=_real_now_epoch(), disk_floor_gb=10_000_000.0)
    assert floored["disk_below_floor"] is True


def test_watchdog_alerts_fire_on_rising_edge_only(tmp_path, monkeypatch):
    import autonomy.alerts as alerts

    alert_dir = tmp_path / "alerts"
    monkeypatch.setattr(alerts, "RUNTIME_DIR", alert_dir)
    monkeypatch.setattr(alerts, "ALERTS_LOG", alert_dir / "alerts.jsonl")
    monkeypatch.setattr(alerts, "ALERTS_LATEST", alert_dir / "alerts_latest.json")
    monkeypatch.setattr(alerts, "ALERT_STATE", alert_dir / "alert_state.json")

    rd = _runtime(tmp_path, mispricing_age=999.0)
    (rd / "KILL").write_text("x", encoding="utf-8")
    tasks = [DEFAULT_TASKS[0], DEFAULT_TASKS[1]]  # shadow (fresh) + mispricing (stale)
    status = evaluate_watchdog(rd, now_epoch=_real_now_epoch(), tasks=tasks)

    state_path = rd / "watchdog_state.json"
    first = fire_watchdog_alerts(status, now_iso="t1", state_path=state_path)
    kinds = sorted(a["kind"] for a in first)
    assert kinds == ["WATCHDOG_KILL_FILE", "WATCHDOG_TASK_STALE"]
    assert {a["severity"] for a in first} == {"critical"}

    # Standing condition does not re-fire.
    second = fire_watchdog_alerts(status, now_iso="t2", state_path=state_path)
    assert second == []

    # Recovery clears the latch; the next episode fires again.
    (rd / "KILL").unlink()
    recovered = evaluate_watchdog(
        _runtime(tmp_path, mispricing_age=10.0), now_epoch=_real_now_epoch(), tasks=tasks,
    )
    fire_watchdog_alerts(recovered, now_iso="t3", state_path=state_path)
    relapse = evaluate_watchdog(
        _runtime(tmp_path, mispricing_age=999.0), now_epoch=_real_now_epoch(), tasks=tasks,
    )
    third = fire_watchdog_alerts(relapse, now_iso="t4", state_path=state_path)
    assert [a["kind"] for a in third] == ["WATCHDOG_TASK_STALE"]


def test_run_watchdog_writes_status_file(tmp_path, monkeypatch):
    monkeypatch.setenv("DUMMY_WATCHDOG_ALERTS", "0")
    rd = _runtime(tmp_path)
    status = run_watchdog(rd, now_epoch=_real_now_epoch())
    written = json.loads((rd / "watchdog_status.json").read_text(encoding="utf-8"))
    assert written["generated_at"] == status["generated_at"]
    assert written["stale_tasks"] == status["stale_tasks"]
    assert "tasks" in written


def test_custom_task_spec_threshold():
    spec = TaskSpec("X", "x.json", ("generated_at",), 600)
    assert spec.threshold_seconds == 1200.0


# ---------------------------------------------------------------- dashboard


def test_status_snapshot_never_touches_ledger(tmp_path, monkeypatch):
    from autonomy import dashboard

    called = {"ledger": False}

    class BoomLedger:
        def __init__(self, *a, **k):
            called["ledger"] = True
            raise AssertionError("status snapshot must never open ledger.db")

    import autonomy.ledger as ledger_mod

    monkeypatch.setattr(ledger_mod, "AutonomyLedger", BoomLedger)
    rd = _runtime(tmp_path)
    snapshot = dashboard.assemble_status_snapshot(runtime_dir=rd)
    assert called["ledger"] is False
    assert snapshot["ledger_touched"] is False
    assert snapshot["heartbeat"]["alive"] is True
    assert snapshot["source"] == "status_snapshot"


def test_status_snapshot_data_ages_flag_stale_and_fresh(tmp_path):
    from autonomy.dashboard import assemble_status_snapshot

    rd = _runtime(tmp_path, heartbeat_age=60.0, mispricing_age=999.0)
    snapshot = assemble_status_snapshot(runtime_dir=rd)
    ages = snapshot["data_ages"]
    assert ages["heartbeat"]["stale"] is False
    assert ages["heartbeat"]["age_seconds"] is not None
    assert ages["mispricing_monitor"]["stale"] is True  # 999s > 240s threshold
    # Absent artifacts read as stale (fail-closed), never as fresh.
    assert ages["crypto_paper_twin"]["stale"] is True
    assert ages["crypto_paper_twin"]["age_seconds"] is None


def test_status_snapshot_includes_watchdog_status(tmp_path):
    from autonomy.dashboard import assemble_status_snapshot

    rd = _runtime(tmp_path)
    (rd / "watchdog_status.json").write_text(json.dumps({
        "healthy": False, "stale_tasks": ["DummyCryptoPaperTwin"],
    }), encoding="utf-8")
    snapshot = assemble_status_snapshot(runtime_dir=rd)
    assert snapshot["watchdog"]["healthy"] is False
    assert snapshot["watchdog"]["stale_tasks"] == ["DummyCryptoPaperTwin"]


def test_full_dashboard_state_carries_data_ages(tmp_path):
    from autonomy.dashboard import assemble_dashboard_state

    rd = _runtime(tmp_path)
    state = assemble_dashboard_state(runtime_dir=rd)
    assert "data_ages" in state and "watchdog" in state
    assert state["data_ages"]["heartbeat"]["stale"] is False


def test_api_status_endpoint_fast_and_marked(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setattr("autonomy.dashboard.RUNTIME_DIR", tmp_path)
    from autonomy.dashboard import build_app

    client = TestClient(build_app())
    r = client.get("/api/status")
    assert r.status_code == 200
    payload = r.json()
    assert payload["source"] == "status_snapshot"
    assert payload["ledger_touched"] is False
    assert "data_ages" in payload


def test_api_autonomy_still_serves_and_caches(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setattr("autonomy.dashboard.RUNTIME_DIR", tmp_path)
    from autonomy.dashboard import build_app

    client = TestClient(build_app())
    r = client.get("/api/autonomy")
    assert r.status_code == 200
    assert "heartbeat" in r.json()
    # Second poll inside the cache window is served from cache.
    assert client.get("/api/autonomy").status_code == 200


def test_api_autonomy_deadline_falls_back_to_503_with_pointer(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setattr("autonomy.dashboard.RUNTIME_DIR", tmp_path)
    monkeypatch.setenv("DUMMY_DASHBOARD_STATE_DEADLINE_SECONDS", "0.05")
    import autonomy.dashboard as dash

    def slow_assemble(runtime_dir=None):
        import time as _time

        _time.sleep(0.5)
        return {"heartbeat": {"alive": True}}

    monkeypatch.setattr(dash, "assemble_dashboard_state", slow_assemble)
    client = TestClient(dash.build_app())
    r = client.get("/api/autonomy")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "COMPUTING"
    assert body["hint"] == "/api/status"
    # The fast snapshot stays responsive while the heavy report computes.
    assert client.get("/api/status").status_code == 200


def test_api_autonomy_serves_stale_cache_when_recompute_is_slow(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setattr("autonomy.dashboard.RUNTIME_DIR", tmp_path)
    monkeypatch.setenv("DUMMY_DASHBOARD_STATE_DEADLINE_SECONDS", "0.05")
    import autonomy.dashboard as dash

    calls = {"n": 0}

    def assemble(runtime_dir=None):
        calls["n"] += 1
        if calls["n"] > 1:
            import time as _time

            _time.sleep(0.5)
        return {"heartbeat": {"alive": True}, "call": calls["n"]}

    monkeypatch.setattr(dash, "assemble_dashboard_state", assemble)
    monkeypatch.setattr(dash, "_monotonic", lambda: 0.0)
    client = TestClient(dash.build_app())
    assert client.get("/api/autonomy").json()["call"] == 1
    # Expire the cache, make the recompute slow: the stale value is served
    # (marked) instead of blocking or 503ing.
    monkeypatch.setattr(dash, "_monotonic", lambda: 1e9)
    r = client.get("/api/autonomy")
    assert r.status_code == 200
    assert r.json().get("stale_cache") is True
