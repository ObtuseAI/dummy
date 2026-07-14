"""WS-15 taxonomy: horizon buckets, scope keys, registry completeness tripwire."""
from __future__ import annotations

import pytest

from autonomy.backtest import run_backtest
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Signal
from autonomy.taxonomy import (
    CRYPTO_HOURLY_MAX_HOURS,
    grading_scope,
    horizon_bucket,
    market_type_for,
    specialist_for,
)


# -- horizon buckets -----------------------------------------------------------

def test_horizon_bucket_boundaries():
    # Native 15-minute series is recognized from the ticker, before hours.
    assert horizon_bucket("KXBTC15M-26JUL091700-15", None) == "15m"
    assert horizon_bucket("KXETH15M-26JUL091700-00", 40.0) == "15m"
    # The hourly/daily split sits exactly at CRYPTO_HOURLY_MAX_HOURS.
    assert CRYPTO_HOURLY_MAX_HOURS == 3.0
    assert horizon_bucket("KXBTCD-26JUL0917-T71000", 2.9) == "hourly"
    assert horizon_bucket("KXBTCD-26JUL0917-T71000", 3.0) == "hourly"
    assert horizon_bucket("KXBTCD-26JUL0917-T71000", 3.1) == "daily+"
    assert horizon_bucket("KXBTCD-26JUL0917-T71000", 26.0) == "daily+"
    # No horizon evidence -> a single 'unknown' bucket, never a wrong one.
    assert horizon_bucket("KXBTCD-26JUL0917-T71000", None) == "unknown"
    assert horizon_bucket("KXBTCD-26JUL0917-T71000", "garbage") == "unknown"


# -- specialist resolution -----------------------------------------------------

def test_specialist_for_resolves_exact_and_prefixed_sources():
    exact = {
        "market_prior": "market", "market_debias": "market",
        "sports_elo": "sports_elo", "sportsbook_consensus": "sportsbook",
        "cross_venue_polymarket": "cross_venue",
        "commodities_spot_vol": "commodities", "weather_openmeteo": "weather",
    }
    for source, label in exact.items():
        assert specialist_for(source) == label
    # Emitted sub-source strings (differ from registry names) resolve by prefix.
    prefixed = {
        "crypto_spot_vol": "crypto", "crypto_structure_swing": "crypto",
        "mlb_live_winner": "mlb", "mlb_structural_winner": "mlb",
        "nfl_structural_winner": "nfl", "nfl_spread": "nfl",
        "nba_spread": "nba", "nhl_live_total": "nhl",
        "ncaaf_game_total": "ncaaf", "ncaamb_game_total": "ncaamb",
        "ufc_fight_winner": "retired", "f1_race_winner": "retired",
    }
    for source, label in prefixed.items():
        assert specialist_for(source) == label
    assert specialist_for("some_new_unmapped_source") == "other"
    assert specialist_for("") == "other"


def test_registry_completeness_tripwire():
    """Every REGISTERED source must resolve to a real specialist.

    This is the alarm: a new signal shipped without a taxonomy home resolves
    to 'other' and fails here.
    """
    from autonomy.ontology import SessionMode
    from autonomy.session import build_brain

    brain = build_brain(SessionMode.SHADOW)
    names = sorted(getattr(s, "name", "") for s in brain.registry.sources())
    # WS-A2: PowerRatingsSignal must actually be wired into build_brain --
    # not just importable/tested in isolation -- or this challenger stays
    # permanently inert in the live pipeline.
    assert "power_ratings" in names
    unmapped = sorted(name for name in names if specialist_for(name) == "other")
    assert unmapped == [], f"sources with no taxonomy home: {unmapped}"


# -- market type + scope -------------------------------------------------------

def test_market_type_prefers_stamped_then_derives_crypto_family():
    # Sports stamp market_type in features; that wins.
    assert market_type_for(
        "nfl_spread", "KXNFLSPREAD-26SEP13KCBUF-KC3", {"market_type": "spread"}) == "spread"
    # Crypto derives its contract family from the ticker.
    assert market_type_for("crypto_spot_vol", "KXBTCD-26JUL0917-T71000", {}) == "ladder"
    assert market_type_for(
        "crypto_spot_vol", "KXBTC15M-26JUL091700-15", {}) == "15m_direction"
    # Unparseable / non-crypto with no stamp -> 'na'.
    assert market_type_for("mystery", "NOTATICKER", {}) == "na"


def test_grading_scope_uses_horizon_for_crypto_and_phase_for_sports():
    crypto = grading_scope(
        "crypto_spot_vol", "KXBTCD-26JUL0917-T71000", {"hours_to_close": 2.0})
    assert crypto == "crypto_spot_vol|ladder|hourly"
    crypto_daily = grading_scope(
        "crypto_spot_vol", "KXETHD-26JUL0917-T3500", {"hours_to_close": 26.0})
    assert crypto_daily == "crypto_spot_vol|ladder|daily+"
    # Sports scope on phase (pre vs live), read from the source name/features.
    pre = grading_scope("mlb_structural_winner", "KXMLBGAME-26JUL10-HOU",
                        {"market_type": "winner"})
    assert pre == "mlb_structural_winner|winner|pre"
    live = grading_scope("mlb_live_winner", "KXMLBGAME-26JUL10-HOU",
                         {"market_type": "winner"})
    assert live == "mlb_live_winner|winner|live"
    pa_live = grading_scope("mlb_pa_live_winner", "KXMLBGAME-26JUL10-HOU",
                            {"market_type": "winner"})
    assert pa_live == "mlb_pa_live_winner|winner|live"
    live_feature = grading_scope("nba_structural_winner", "KXNBAGAME-26OCT20-LAL",
                                 {"market_type": "winner", "live": True})
    assert live_feature.endswith("|live")


# -- end-to-end per-scope trackers in the backtest -----------------------------

def _crypto_signal(source, ticker, p, hours):
    return Signal(
        source=source, market_ticker=ticker, probability_yes=p,
        uncertainty=0.1, rationale="", features={"hours_to_close": hours},
    )


def test_backtest_separates_scopes_and_keeps_bare_source_aggregate(tmp_path):
    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        # Same source + same market_type (ladder), two different horizons.
        cases = [
            ("KXBTCD-26JUL0917-T71000", True, 2.0),    # hourly
            ("KXBTCD-26JUL0918-T71000", False, 2.0),   # hourly
            ("KXETHD-26JUL0917-T3500", True, 26.0),    # daily+
            ("KXETHD-26JUL0918-T3500", False, 26.0),   # daily+
        ]
        for ticker, result, hours in cases:
            ledger.record_signal(_crypto_signal("market_prior", ticker, 0.5, hours))
            ledger.record_signal(
                _crypto_signal("crypto_spot_vol", ticker, 0.8 if result else 0.2, hours))
            ledger.record_settlement(ticker, result)

        report = run_backtest(ledger, bootstrap_weights=True)
        scopes = report["sources_by_scope"]
        assert "crypto_spot_vol|ladder|hourly" in scopes
        assert "crypto_spot_vol|ladder|daily+" in scopes
        assert scopes["crypto_spot_vol|ladder|hourly"]["n"] == 2
        assert scopes["crypto_spot_vol|ladder|daily+"]["n"] == 2
        # The bare-source aggregate is untouched (all four still counted once).
        assert report["sources"]["crypto_spot_vol"]["n"] == 4
        # Scope keys are EVIDENCE ONLY -- never written to the weights table
        # (the live forecaster looks up bare source names).
        assert ledger.get_weight("crypto_spot_vol|ladder|hourly", default=1.0) == 1.0
        assert ledger.get_weight("crypto_spot_vol") != 1.0  # bare source did persist
    finally:
        ledger.close()


# -- WS-8: (specialist, market_type, phase) trust-surface roll-up --------------

def test_trust_surface_rolls_sources_up_to_specialist_grain(tmp_path):
    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        # Two DIFFERENT crypto sources price the same ladder/hourly scope; the
        # roll-up must collapse them into ONE crypto|ladder|hourly bucket.
        cases = [
            ("KXBTCD-26JUL0917-T71000", True, 2.0),
            ("KXBTCD-26JUL0918-T71000", False, 2.0),
        ]
        for ticker, result, hours in cases:
            ledger.record_signal(_crypto_signal("market_prior", ticker, 0.5, hours))
            ledger.record_signal(
                _crypto_signal("crypto_spot_vol", ticker, 0.8 if result else 0.2, hours))
            ledger.record_signal(
                _crypto_signal("crypto_structure_swing", ticker, 0.7 if result else 0.3, hours))
            ledger.record_settlement(ticker, result)

        report = run_backtest(ledger, bootstrap_weights=False)
        # Source grain is unchanged (two distinct source scopes still present).
        scopes = report["sources_by_scope"]
        assert "crypto_spot_vol|ladder|hourly" in scopes
        assert "crypto_structure_swing|ladder|hourly" in scopes

        surface = report["trust_surface_by_specialist"]
        assert "crypto|ladder|hourly" in surface
        rolled = surface["crypto|ladder|hourly"]
        assert rolled["specialist"] == "crypto"
        assert rolled["market_type"] == "ladder"
        assert rolled["phase"] == "hourly"
        # Both crypto sources (2 markets each) rolled up -> n = 4.
        assert rolled["n"] == 4
        assert rolled["source_family_size"] == 2
        assert set(rolled["source_family"]) == {"crypto_spot_vol", "crypto_structure_swing"}
        # market_prior rolls up to its OWN specialist ("market"), never into
        # crypto. (Its axis is phase "pre", not a horizon -- grading_scope only
        # uses horizon buckets for crypto-specialist sources; market_prior is
        # not one. The roll-up faithfully reflects that WS-15 keying.)
        assert any(k.startswith("market|") for k in surface)
        assert "market|ladder|pre" in surface
        # Honest by construction: NO fabricated CI at this coarser grain --
        # the per-source cluster CIs stay in sources_by_scope (the gate reads
        # those). This view is evidence, not a promotion input.
        assert "contested_mean_brier_edge_ci95" not in rolled
    finally:
        ledger.close()


def test_calibration_signals_carry_parsed_features(tmp_path):
    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        ledger.record_signal(_crypto_signal(
            "crypto_spot_vol", "KXBTCD-26JUL0917-T71000", 0.7, 3.5))
        rows = ledger.calibration_signals_for_market("KXBTCD-26JUL0917-T71000")
        row = next(r for r in rows if r["source"] == "crypto_spot_vol")
        assert row["features"]["hours_to_close"] == 3.5
    finally:
        ledger.close()
