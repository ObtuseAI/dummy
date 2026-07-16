"""Recalibration sanity guard: pathological trust vectors are rejected fail-closed.

Regression anchor: on 2026-07-16T04:02Z a single shadow cycle applied 679
phantom settlements and pushed EVERY crypto source weight to the 8.0 ceiling
uniformly — a saturated vector that ranks nothing — with no alarm. The guard
must catch exactly that event, keep the prior weights, and alert.
"""
from __future__ import annotations

from pathlib import Path

from autonomy.ledger import AutonomyLedger
from autonomy.learner import (
    Learner,
    MAX_RECAL_JUMP_RATIO,
    WEIGHT_CEILING,
    screen_weight_vector,
)

# The literal weight_updates vector from the observed 2026-07-16T04:02Z cycle
# (runtime/autonomy/cycles.jsonl): 13 crypto sources pinned at the ceiling,
# market sources unsaturated — so whole-vector uniformity alone cannot see it.
OBSERVED_ALL_8_EVENT = {
    "crypto_blend_sigma": 8.0,
    "crypto_btc_leadlag": 8.0,
    "crypto_dvol_implied": 8.0,
    "crypto_empirical_regime": 8.0,
    "crypto_equities_flow": 8.0,
    "crypto_ewma_t": 8.0,
    "crypto_ewma_t::cal": 8.0,
    "crypto_macro_regime": 8.0,
    "crypto_spot_vol": 8.0,
    "crypto_spot_vol::cal": 8.0,
    "crypto_structure_swing": 8.0,
    "crypto_technical_composite": 8.0,
    "crypto_technical_foundry": 8.0,
    "market_debias": 1.163736244857062,
    "market_prior": 2.563,
}
# The healthy vector one cycle earlier (03:42Z) — the state the guard reverts to.
PRIOR_HEALTHY = {
    "crypto_blend_sigma": 3.0929496660695266,
    "crypto_btc_leadlag": 3.2643696247368816,
    "crypto_dvol_implied": 3.060916833911,
    "crypto_empirical_regime": 3.1489066343904737,
    "crypto_equities_flow": 3.0448496891933017,
    "crypto_ewma_t": 3.1286684682354036,
    "crypto_ewma_t::cal": 3.1329929365398703,
    "crypto_macro_regime": 3.058913518062097,
    "crypto_spot_vol": 3.086892247802104,
    "crypto_spot_vol::cal": 3.134659177211495,
    "crypto_technical_composite": 3.0802123761905276,
    "crypto_technical_foundry": 3.2486733275852737,
    "market_debias": 1.386121797426779,
    "market_prior": 2.563,
}


class _Report:
    def __init__(self, weight_updates):
        self.weight_updates = dict(weight_updates)
        self.notes: list[str] = []


def test_all_equal_at_ceiling_rejected():
    reasons = screen_weight_vector({f"s{i}_x": WEIGHT_CEILING for i in range(5)})
    assert any(r.startswith("all_at_ceiling") for r in reasons)


def test_two_sources_at_ceiling_rejected():
    # all-at-ceiling alarms even below the uniformity group-size threshold.
    reasons = screen_weight_vector({"a_x": 8.0, "b_y": 8.0})
    assert any(r.startswith("all_at_ceiling") for r in reasons)


def test_all_equal_anywhere_rejected():
    reasons = screen_weight_vector({"a_x": 2.5, "b_y": 2.5, "c_z": 2.5})
    assert any(r.startswith("all_equal") for r in reasons)


def test_neutral_uniformity_is_the_cold_start_prior_not_a_pathology():
    assert screen_weight_vector({"a_x": 1.0, "b_y": 1.0, "c_z": 1.0}) == []


def test_supermajority_at_cap_rejected():
    vec = {f"s{i}_x": 8.0 for i in range(19)}
    vec["outlier_y"] = 3.1
    reasons = screen_weight_vector(vec)
    assert any(r.startswith("supermajority_at_cap") for r in reasons)


def test_excess_single_cycle_jump_rejected():
    previous = {"a_x": 1.0, "b_y": 2.0, "c_z": 3.0}
    candidate = {"a_x": 1.0 * (MAX_RECAL_JUMP_RATIO + 1), "b_y": 2.1, "c_z": 2.9}
    reasons = screen_weight_vector(candidate, previous)
    assert any(r.startswith("excess_jump[a_x") for r in reasons)


def test_healthy_discriminating_vector_passes():
    previous = {"a_x": 1.0, "b_y": 2.0, "c_z": 0.5}
    candidate = {"a_x": 1.1, "b_y": 1.9, "c_z": 0.55}
    assert screen_weight_vector(candidate, previous) == []


def test_regression_observed_all_8_crypto_event_rejected():
    """The literal 2026-07-16T04:02Z event must be caught.

    Whole-vector uniformity misses it (market sources were unsaturated); the
    per-vertical-group screen must flag the saturated crypto cluster.
    """
    reasons = screen_weight_vector(OBSERVED_ALL_8_EVENT, PRIOR_HEALTHY)
    assert reasons, "the observed all-8.0 crypto event must be rejected"
    assert any("crypto" in r for r in reasons)
    assert any(
        r.startswith("all_at_ceiling[crypto") or
        r.startswith("supermajority_at_cap[crypto")
        for r in reasons
    )


def test_guard_cycle_weights_reverts_and_alerts(tmp_path: Path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    fired: list[tuple[str, str, dict]] = []
    try:
        for source, weight in PRIOR_HEALTHY.items():
            ledger.update_weight(source, weight)
        previous = ledger.all_weights()
        # Simulate the runaway cycle writing the saturated vector.
        for source, weight in OBSERVED_ALL_8_EVENT.items():
            ledger.update_weight(source, weight)

        learner = Learner(ledger, alert=lambda k, m, d: fired.append((k, m, d)))
        report = _Report(OBSERVED_ALL_8_EVENT)
        verdict = learner.guard_cycle_weights(report, previous)

        assert verdict["accepted"] is False
        assert verdict["reasons"]
        # Previous weights restored — fail-closed, nothing degenerate stands.
        for source, weight in PRIOR_HEALTHY.items():
            assert abs(ledger.get_weight(source) - weight) < 1e-9
        # The rejected vector is logged in the alert for the post-mortem.
        assert fired and fired[0][0] == "RECAL_REJECTED"
        assert fired[0][2]["rejected_weights"]["crypto_blend_sigma"] == 8.0
        # The report presents the prior surface downstream and is annotated.
        assert report.weight_updates["crypto_blend_sigma"] != 8.0
        assert any(note.startswith("recal_rejected:") for note in report.notes)
    finally:
        ledger.close()


def test_guard_cycle_weights_accepts_healthy_updates(tmp_path: Path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    fired: list[tuple[str, str, dict]] = []
    try:
        previous = {"a_x": 1.0, "b_y": 2.0}
        for source, weight in previous.items():
            ledger.update_weight(source, weight)
        updates = {"a_x": 1.2, "b_y": 1.8}
        for source, weight in updates.items():
            ledger.update_weight(source, weight)
        learner = Learner(ledger, alert=lambda k, m, d: fired.append((k, m, d)))
        report = _Report(updates)
        verdict = learner.guard_cycle_weights(report, previous)
        assert verdict["accepted"] is True
        assert fired == []
        assert abs(ledger.get_weight("a_x") - 1.2) < 1e-9
        assert report.weight_updates == updates
    finally:
        ledger.close()


def test_guard_reverts_scoped_keys_touched_in_the_same_cycle(tmp_path: Path):
    """The learner writes global + scoped + exact keys with one multiplier; a
    rejection must roll back the scoped rows too, not just the globals."""
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        previous = dict(PRIOR_HEALTHY)
        previous["crypto_blend_sigma@CRYPTO"] = 3.05
        for source, weight in previous.items():
            ledger.update_weight(source, weight)
        snapshot = ledger.all_weights()
        for source, weight in OBSERVED_ALL_8_EVENT.items():
            ledger.update_weight(source, weight)
        ledger.update_weight("crypto_blend_sigma@CRYPTO", 8.0)

        learner = Learner(ledger, alert=lambda *a: None)
        learner.guard_cycle_weights(_Report(OBSERVED_ALL_8_EVENT), snapshot)
        assert abs(ledger.get_weight("crypto_blend_sigma@CRYPTO") - 3.05) < 1e-9
    finally:
        ledger.close()
