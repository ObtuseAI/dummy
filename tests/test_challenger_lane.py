"""Isolated challenger lane: the forward-evidence gate is finally reachable.

The decisive test here runs the auto-promotion runner's OWN evidence builder
(``realized_attribution``) over a ledger populated exclusively through the
lane's public flow and asserts a ``forward_evidence`` block appears for the
registered scope -- the predicate that was unreachable for the entire history
of the project.
"""
from __future__ import annotations

import inspect
import json
from datetime import datetime, timedelta, timezone

from autonomy.challenger_lane import (
    DECISION_PREFIX,
    ENABLED_ENV,
    MAX_PER_CYCLE_ENV,
    emit_isolated_challenger_decisions,
)
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import MarketView, Signal, Vertical

SOURCE = "crypto_equities_flow"
SCOPE = "crypto_equities_flow|sol|15m_direction|15m"
FINGERPRINT = "ab" * 32  # 64 lowercase hex chars, matches the loader's shape


def _write_registrations(path, *, registered_at=None, scope=SCOPE,
                         fingerprint=FINGERPRINT):
    registered_at = registered_at or (
        datetime.now(timezone.utc) - timedelta(hours=1)
    ).isoformat()
    path.write_text(json.dumps({"registrations": [{
        "scope": scope,
        "candidate_fingerprint": fingerprint,
        "registered_at": registered_at,
        "definition_module": "autonomy/signals/crypto_equities.py",
        "authority": "none_registration_is_a_precondition_not_a_promotion",
    }]}), encoding="utf-8")
    return path


def _lane_env(monkeypatch):
    monkeypatch.delenv(ENABLED_ENV, raising=False)
    monkeypatch.delenv(MAX_PER_CYCLE_ENV, raising=False)


def _ledger(tmp_path, monkeypatch, regs_path):
    monkeypatch.setattr(
        AutonomyLedger, "_FORWARD_REGISTRATIONS_PATH", regs_path,
    )
    return AutonomyLedger(tmp_path / "lane-ledger.db")


def _sol_market(ticker="KXSOL15M-26JUL241200-00"):
    return MarketView(
        ticker=ticker, title="SOL 15m direction", vertical=Vertical.CRYPTO,
        status="active",
        close_time=(
            datetime.now(timezone.utc) + timedelta(minutes=12)
        ).isoformat(),
        yes_bid=44, yes_ask=48, no_bid=52, no_ask=56,
        volume=100, liquidity=1_000,
    )


def _candidate_signal(ticker, source=SOURCE, probability=0.62):
    return Signal(
        source=source, market_ticker=ticker, probability_yes=probability,
        uncertainty=0.2, rationale="lane fixture",
        features={"challenger_only": True, "hours_to_close": 0.2},
    )


def _registrations(regs_path):
    from autonomy.auto_promotion_runner import load_forward_registrations

    return load_forward_registrations(regs_path)


def _lane_pass(ledger, market_signal_pairs, regs_path, notes=None, **kwargs):
    return emit_isolated_challenger_decisions(
        ledger,
        [(market, None, signals) for market, signals in market_signal_pairs],
        notes=notes if notes is not None else [],
        registrations=_registrations(regs_path),
        **kwargs,
    )


# -- THE structural proof ------------------------------------------------------

def test_forward_evidence_gate_is_reachable(tmp_path, monkeypatch):
    """Lane decision + fill + settlement satisfies the runner's forward gate."""
    from autonomy.auto_promotion_runner import realized_attribution

    _lane_env(monkeypatch)
    regs_path = _write_registrations(tmp_path / "regs.json")
    ledger = _ledger(tmp_path, monkeypatch, regs_path)
    try:
        market = _sol_market()
        signal = _candidate_signal(market.ticker)
        assert ledger.record_signal(signal)
        # The ledger stamped the REGISTERED fingerprint at record time.
        assert signal.features["promotion_candidate_fingerprint"] == FINGERPRINT

        notes: list[str] = []
        first = _lane_pass(ledger, [(market, [signal])], regs_path, notes)
        assert first == {"emitted": 1, "settled": 0}

        decision_id, sources_used = ledger._conn.execute(
            "SELECT decision_id, sources_used FROM decisions",
        ).fetchone()
        assert decision_id.startswith(DECISION_PREFIX)
        assert json.loads(sources_used) == {SOURCE: 1.0}
        # p=0.62 > implied 0.46 -> BUY_YES, synthetic taker fill at the ask.
        fill = ledger._conn.execute(
            "SELECT kind, fill_count, fill_price_cents FROM outcomes",
        ).fetchone()
        assert fill == ("FILLED", 1, 48)

        # Market settles YES; the next lane pass grades the row itself.
        ledger.record_settlement(market.ticker, True)
        second = _lane_pass(ledger, [], regs_path, notes)
        assert second == {"emitted": 0, "settled": 1}
        terminal = ledger._conn.execute(
            "SELECT kind, pnl_cents FROM outcomes WHERE kind LIKE 'SETTLED%'",
        ).fetchone()
        assert terminal[0] == "SETTLED_WIN" and terminal[1] > 0

        realized = realized_attribution(
            ledger._conn, forward_registrations=_registrations(regs_path),
        )
        forward = realized[SCOPE]["forward_evidence"]
        assert forward["n_trades"] == 1
        assert forward["candidate_fingerprint"] == FINGERPRINT
        assert forward["isolated_candidate_decisions"] is True
        assert forward["out_of_sample_after_registration"] is True
        assert any(forward["pnl_by_cluster"].values())
    finally:
        ledger.close()


# -- isolation guarantees ------------------------------------------------------

def test_lane_rows_are_invisible_to_both_brain_books(tmp_path, monkeypatch):
    _lane_env(monkeypatch)
    regs_path = _write_registrations(tmp_path / "regs.json")
    ledger = _ledger(tmp_path, monkeypatch, regs_path)
    try:
        market = _sol_market()
        signal = _candidate_signal(market.ticker)
        assert ledger.record_signal(signal)
        result = _lane_pass(ledger, [(market, [signal])], regs_path)
        assert result["emitted"] == 1
        # The brain's book scopes (risk exposure, stage caps, shadow
        # reconciler, settlement close-out) never see the lane row ...
        assert ledger.open_decisions("shadow") == []
        assert ledger.open_decisions("live") == []
        # ... while the lane's own unscoped sweep still finds it, inactive.
        unscoped = ledger.open_decisions()
        assert [r["decision_id"].startswith(DECISION_PREFIX) for r in unscoped] == [True]
        assert unscoped[0]["order_active"] == 0
        assert unscoped[0]["order_id"].startswith("shadow-")
    finally:
        ledger.close()


def test_lane_signature_cannot_touch_risk_state():
    parameters = inspect.signature(emit_isolated_challenger_decisions).parameters
    assert "state" not in parameters
    assert "executor" not in parameters


def test_per_cycle_cap_and_env_override(tmp_path, monkeypatch):
    _lane_env(monkeypatch)
    regs_path = _write_registrations(tmp_path / "regs.json")
    ledger = _ledger(tmp_path, monkeypatch, regs_path)
    try:
        pairs = []
        for day in range(1, 13):  # 12 candidates > default cap of 10
            market = _sol_market(f"KXSOL15M-26JUL{day:02d}1200-00")
            signal = _candidate_signal(market.ticker)
            assert ledger.record_signal(signal)
            pairs.append((market, [signal]))
        result = _lane_pass(ledger, pairs, regs_path)
        assert result["emitted"] == 10
        assert ledger._conn.execute(
            "SELECT COUNT(*) FROM decisions",
        ).fetchone()[0] == 10

        monkeypatch.setenv(MAX_PER_CYCLE_ENV, "1")
        fresh = [(m, s) for m, s in pairs[10:]]
        assert _lane_pass(ledger, fresh, regs_path)["emitted"] == 1

        monkeypatch.setenv(MAX_PER_CYCLE_ENV, "not-a-number")
        assert _lane_pass(ledger, fresh, regs_path)["emitted"] == 0
    finally:
        ledger.close()


def test_env_kill_switch_disables_everything(tmp_path, monkeypatch):
    _lane_env(monkeypatch)
    monkeypatch.setenv(ENABLED_ENV, "0")
    regs_path = _write_registrations(tmp_path / "regs.json")
    ledger = _ledger(tmp_path, monkeypatch, regs_path)
    try:
        market = _sol_market()
        signal = _candidate_signal(market.ticker)
        assert ledger.record_signal(signal)
        notes: list[str] = []
        result = _lane_pass(ledger, [(market, [signal])], regs_path, notes)
        assert result == {"emitted": 0, "settled": 0}
        assert notes == []
        assert ledger._conn.execute(
            "SELECT COUNT(*) FROM decisions",
        ).fetchone()[0] == 0
    finally:
        ledger.close()


def test_unregistered_source_and_wrong_scope_are_ignored(tmp_path, monkeypatch):
    _lane_env(monkeypatch)
    regs_path = _write_registrations(tmp_path / "regs.json")
    ledger = _ledger(tmp_path, monkeypatch, regs_path)
    try:
        # Registered source, WRONG subject scope (btc, not sol).
        btc_market = _sol_market("KXBTC15M-26JUL241200-00")
        btc_signal = _candidate_signal(btc_market.ticker)
        assert ledger.record_signal(btc_signal)
        # The ledger fingerprint stamp is scope-exact too.
        assert "promotion_candidate_fingerprint" not in btc_signal.features
        # Unregistered source on the registered market.
        sol_market = _sol_market()
        other = _candidate_signal(sol_market.ticker, source="crypto_spot_vol")
        assert ledger.record_signal(other)
        notes: list[str] = []
        result = _lane_pass(
            ledger,
            [(btc_market, [btc_signal]), (sol_market, [other])],
            regs_path,
            notes,
        )
        assert result == {"emitted": 0, "settled": 0}
        assert notes == []
    finally:
        ledger.close()


def test_candidate_failure_is_noted_never_raised(tmp_path, monkeypatch):
    _lane_env(monkeypatch)
    regs_path = _write_registrations(tmp_path / "regs.json")
    ledger = _ledger(tmp_path, monkeypatch, regs_path)
    try:
        market = _sol_market()
        signal = _candidate_signal(market.ticker)
        assert ledger.record_signal(signal)

        def _boom(_decision):
            raise RuntimeError("ledger detonated")

        monkeypatch.setattr(ledger, "record_decision", _boom)
        notes: list[str] = []
        result = _lane_pass(ledger, [(market, [signal])], regs_path, notes)
        assert result["emitted"] == 0
        assert f"challenger_lane_error:{SOURCE}:RuntimeError" in notes
    finally:
        ledger.close()


def test_already_settled_market_is_never_probed(tmp_path, monkeypatch):
    _lane_env(monkeypatch)
    regs_path = _write_registrations(tmp_path / "regs.json")
    ledger = _ledger(tmp_path, monkeypatch, regs_path)
    try:
        market = _sol_market()
        signal = _candidate_signal(market.ticker)
        assert ledger.record_signal(signal)
        ledger.record_settlement(market.ticker, False)
        result = _lane_pass(ledger, [(market, [signal])], regs_path)
        assert result == {"emitted": 0, "settled": 0}
    finally:
        ledger.close()


def test_trading_halt_blocks_probes_but_still_settles(tmp_path, monkeypatch):
    _lane_env(monkeypatch)
    regs_path = _write_registrations(tmp_path / "regs.json")
    ledger = _ledger(tmp_path, monkeypatch, regs_path)
    try:
        market = _sol_market()
        signal = _candidate_signal(market.ticker)
        assert ledger.record_signal(signal)
        assert _lane_pass(ledger, [(market, [signal])], regs_path)["emitted"] == 1
        ledger.record_settlement(market.ticker, True)

        halted_market = _sol_market("KXSOL15M-26JUL021200-00")
        halted_signal = _candidate_signal(halted_market.ticker)
        assert ledger.record_signal(halted_signal)
        result = _lane_pass(
            ledger, [(halted_market, [halted_signal])], regs_path,
            trading_active=False,
        )
        assert result == {"emitted": 0, "settled": 1}
    finally:
        ledger.close()


# -- eligibility stamps --------------------------------------------------------

def test_market_debias_eligibility_is_exact_registered_scopes_only():
    from autonomy.signals.market_debias import PROMOTION_ELIGIBLE_SCOPES
    from autonomy.taxonomy import grading_scope

    ticker = "KXMLBTB-26JUL241910CLETB-CLEJRAMREZ11-2"
    # Current emission shape: market_type is stamped "<type>@<horizon>", so the
    # horizon rides in the grading scope. These are the registered scopes.
    assert grading_scope(
        "market_debias", ticker,
        {"vertical": "SPORTS", "market_type": "prop@long"},
    ) == "market_debias|mlb|prop@long|pre"
    assert PROMOTION_ELIGIBLE_SCOPES == {
        "market_debias|mlb|prop@long|pre",
        "market_debias|mlb|prop@short|pre",
        "market_debias|mlb|spread@long|pre",
    }
    # The pre-8c43272 unstamped shape ("...|na|pre") is no longer producible by
    # any emission and is NOT eligible; an unregistered market type / horizon
    # stays opted out too (fail-closed exactness).
    for features in (
        {"vertical": "SPORTS"},
        {"vertical": "SPORTS", "market_type": "winner@short"},
        {"vertical": "SPORTS", "market_type": "prop@near_terminal"},
    ):
        assert (
            grading_scope("market_debias", ticker, features)
            not in PROMOTION_ELIGIBLE_SCOPES
        )
