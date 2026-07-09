"""Tests for correlation grouping + per-cluster risk caps."""

from __future__ import annotations

from autonomy.correlation import group_key
from autonomy.ontology import Stage
from autonomy.risk_brain import RiskBrain


def test_group_key_crypto_buckets_same_expiry_cluster():
    a = group_key("KXBTC-26JUL0820-B63550")
    b = group_key("KXBTC-26JUL0820-B63150")
    c = group_key("KXBTC-26JUL0820-T71000")
    assert a == b == c  # all same-expiry BTC = one cluster
    assert group_key("KXBTC-26JUL0920-B63550") != a  # different expiry


def test_group_key_commodity():
    assert group_key("KXWTI-26JUL1014-T80.99") == group_key("KXWTI-26JUL1014-T85")
    assert group_key("KXWTI-26JUL1014-T80") != group_key("KXWTI-26JUL1114-T80")


def test_group_key_weather_city_day():
    a = group_key("KXHIGHNY-26JUL09-T90")
    b = group_key("KXHIGHNY-26JUL09-B89.5")
    assert a == b
    assert group_key("KXHIGHCHI-26JUL09-T90") != a  # different city
    assert group_key("KXHIGHNY-26JUL10-T90") != a  # different day


def test_group_key_game_both_sides_same():
    a = group_key("KXMLBGAME-26JUL111810PHIDET-PHI")
    b = group_key("KXMLBGAME-26JUL111810PHIDET-DET")
    assert a == b  # both sides of one game = one cluster


def test_group_key_fallback_event_stem():
    assert group_key("KXWEIRD-ABC-XYZ").startswith("EVENT:")


def _brain_state(tmp_path, **overrides):
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    state = brain.load_state(1_000_000)  # $10k so fractional caps don't bind first
    for k, v in overrides.items():
        setattr(state, k, v)
    return brain, state


def test_group_count_cap_blocks_stacking(tmp_path):
    brain, state = _brain_state(tmp_path)  # CANARY: max_per_group = 1
    # First position in the cluster is allowed.
    first = brain.order_budget(state, "KXBTC-26JUL0820-B63550", 0, kelly=1.0,
                               group_exposure_cents=0, group_open_count=0)
    assert first.allowed
    # A second correlated position (group already has 1) is blocked.
    second = brain.order_budget(state, "KXBTC-26JUL0820-B63150", 0, kelly=1.0,
                                group_exposure_cents=first.max_notional_cents, group_open_count=1)
    assert not second.allowed
    assert "correlated" in second.reason


def test_group_notional_cap_binds(tmp_path):
    brain, state = _brain_state(tmp_path)
    state.stage = Stage.RAMP  # max_per_group = 2, group_frac = 0.03
    # Group budget = 1_000_000 * 0.03 = 30_000c; already 29_950 used.
    budget = brain.order_budget(state, "KXBTC-26JUL0820-B63150", 0, kelly=1.0,
                                group_exposure_cents=29_950, group_open_count=1)
    assert budget.max_notional_cents <= 50  # squeezed by remaining group budget


def test_higher_stage_allows_more_per_group(tmp_path):
    brain, state = _brain_state(tmp_path)
    state.stage = Stage.CRUISE  # max_per_group = 3
    third = brain.order_budget(state, "KXBTC-26JUL0820-B1", 0, kelly=1.0,
                               group_exposure_cents=100, group_open_count=2)
    assert third.allowed
