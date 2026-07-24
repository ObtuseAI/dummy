"""Wave-86 ratchet: cheap to earn once, dearer to earn again.

Owner directive: minimal positive ROI earns a place; a negative ROI demotes
and RAISES the bar for the next attempt, autonomously. The ratchet is what
makes a low first bar defensible -- failure is remembered and repriced instead
of forgotten.
"""
from __future__ import annotations

import json

from autonomy.promotion_ratchet import (
    CLUSTER_RATCHET_FACTOR,
    MAX_ATTEMPTS,
    ROI_RATCHET_STEP,
    clears_ratchet,
    load_ratchet,
    record_demotion,
    requirements_for,
    save_ratchet,
)

SCOPE = "crypto_technical_foundry|sol|15m_direction|15m"
BASE_CLUSTERS = 3


def _reqs(state, **kw):
    return requirements_for(state, SCOPE, base_clusters=BASE_CLUSTERS, **kw)


def test_first_attempt_is_the_minimal_bar():
    need = _reqs(load_ratchet("does-not-exist.json"))
    assert need["attempt"] == 1
    assert need["prior_demotions"] == 0
    assert need["required_forward_clusters"] == BASE_CLUSTERS
    assert need["required_roi_ci95_lower"] == 0.0
    assert need["eligible_for_retry"] is True


def test_each_demotion_raises_both_bars():
    state = load_ratchet("does-not-exist.json")
    seen_clusters, seen_roi = [], []
    for attempt in range(4):
        need = _reqs(state)
        seen_clusters.append(need["required_forward_clusters"])
        seen_roi.append(need["required_roi_ci95_lower"])
        record_demotion(state, SCOPE, reason="roi_negative", roi=-0.02)
    # Strictly increasing on both axes -- the ratchet only ever tightens.
    assert seen_clusters == sorted(set(seen_clusters))
    assert seen_roi == sorted(set(seen_roi))
    assert seen_clusters[1] == int(BASE_CLUSTERS * CLUSTER_RATCHET_FACTOR)
    assert seen_roi[1] == ROI_RATCHET_STEP


def test_scope_retires_after_max_attempts():
    state = load_ratchet("does-not-exist.json")
    for _ in range(MAX_ATTEMPTS):
        record_demotion(state, SCOPE, reason="roi_negative")
    need = _reqs(state)
    assert need["eligible_for_retry"] is False
    assert need["reason"] == "retired_after_max_demotions"
    verdict = clears_ratchet(
        state, SCOPE, forward_clusters=10_000, roi_ci95_lower=9.9,
        base_clusters=BASE_CLUSTERS,
    )
    assert verdict["pass"] is False          # no amount of evidence revives it
    assert "eligible_for_retry" in verdict["failures"]


def test_minimal_positive_roi_clears_the_first_attempt():
    state = load_ratchet("does-not-exist.json")
    verdict = clears_ratchet(
        state, SCOPE, forward_clusters=BASE_CLUSTERS, roi_ci95_lower=0.0001,
        base_clusters=BASE_CLUSTERS,
    )
    assert verdict["pass"] is True


def test_zero_roi_lower_bound_is_not_an_edge():
    """A CI lower bound sitting on zero is a coin flip, not evidence."""
    state = load_ratchet("does-not-exist.json")
    verdict = clears_ratchet(
        state, SCOPE, forward_clusters=BASE_CLUSTERS, roi_ci95_lower=0.0,
        base_clusters=BASE_CLUSTERS,
    )
    assert verdict["pass"] is False
    assert "roi_ci95_lower" in verdict["failures"]

    for bad in (None, -0.01):
        assert clears_ratchet(
            state, SCOPE, forward_clusters=BASE_CLUSTERS, roi_ci95_lower=bad,
            base_clusters=BASE_CLUSTERS,
        )["pass"] is False


def test_what_cleared_attempt_one_does_not_clear_attempt_two():
    """The point of the ratchet, stated as a test."""
    state = load_ratchet("does-not-exist.json")
    ok_first = dict(forward_clusters=BASE_CLUSTERS, roi_ci95_lower=0.0001)
    assert clears_ratchet(state, SCOPE, base_clusters=BASE_CLUSTERS, **ok_first)["pass"]

    record_demotion(state, SCOPE, reason="roi_negative", roi=-0.03)
    assert clears_ratchet(
        state, SCOPE, base_clusters=BASE_CLUSTERS, **ok_first
    )["pass"] is False

    # It can still come back -- with materially more evidence.
    assert clears_ratchet(
        state, SCOPE, base_clusters=BASE_CLUSTERS,
        forward_clusters=BASE_CLUSTERS * 2, roi_ci95_lower=ROI_RATCHET_STEP + 0.001,
    )["pass"] is True


def test_ratchet_survives_a_round_trip_and_never_resets(tmp_path):
    path = tmp_path / "promotion_ratchet.json"
    state = load_ratchet(path)
    record_demotion(state, SCOPE, reason="roi_negative", roi=-0.05)
    record_demotion(state, SCOPE, reason="roi_negative", roi=-0.01)
    save_ratchet(state, path)

    reloaded = load_ratchet(path)
    assert requirements_for(
        reloaded, SCOPE, base_clusters=BASE_CLUSTERS,
    )["prior_demotions"] == 2
    # History is bounded but the authoritative count is not lost.
    assert json.loads(path.read_text(encoding="utf-8"))["scopes"][SCOPE]["demotions"] == 2


def test_unknown_scope_and_corrupt_state_fail_safe(tmp_path):
    path = tmp_path / "corrupt.json"
    path.write_text("{not json", encoding="utf-8")
    state = load_ratchet(path)
    assert state == {}
    assert requirements_for(
        state, "never|seen|before|x", base_clusters=BASE_CLUSTERS,
    )["attempt"] == 1
