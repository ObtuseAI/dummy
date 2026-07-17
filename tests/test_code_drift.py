"""Deployed-code drift detection (pure core)."""
from __future__ import annotations

from autonomy.code_drift import code_drift_status


def test_current_checkout_is_not_drifted():
    s = code_drift_status(local_head="abc", remote_head="abc", commits_behind=0)
    assert s["drifted"] is False
    assert s["severity"] == "info"


def test_slightly_behind_is_warning():
    s = code_drift_status(local_head="abc", remote_head="def", commits_behind=3)
    assert s["drifted"] is True
    assert s["severity"] == "warning"
    assert "3 commit" in s["message"]


def test_far_behind_is_critical():
    s = code_drift_status(local_head="abc", remote_head="def", commits_behind=58)
    assert s["drifted"] is True
    assert s["severity"] == "critical"
    assert "58 commits behind" in s["message"]


def test_head_mismatch_without_count_still_drifts():
    # Detached/rewritten HEAD equal count but different sha -> still drift.
    s = code_drift_status(local_head="abc", remote_head="zzz", commits_behind=0)
    assert s["drifted"] is True


def test_unknown_heads_do_not_false_positive():
    # Fetch failed and both heads unknown, 0 behind -> not drifted (no guessing).
    s = code_drift_status(local_head=None, remote_head=None, commits_behind=0)
    assert s["drifted"] is False


def test_dirty_flag_passthrough():
    s = code_drift_status(local_head="a", remote_head="a", commits_behind=0, dirty=True)
    assert s["dirty"] is True
