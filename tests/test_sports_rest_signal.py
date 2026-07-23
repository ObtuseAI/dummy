"""Rest mean-shift: model, walk-forward grading, and challenger signal."""
from __future__ import annotations

import math

from autonomy.sports.rest import (
    MAX_REST_LOGIT_SHIFT,
    apply_rest_shift,
    rest_days,
    rest_logit_shift,
    rest_state,
)


class _FakeStore:
    def __init__(self, form: dict[tuple[str, str], list[dict]]):
        self._form = form

    def team_form(self, team, as_of, league=None, n=20):
        return self._form.get((team, league), [])


def test_rest_days_is_point_in_time_and_fails_closed():
    store = _FakeStore({
        ("BOS", "nba"): [{"start_time": "2026-01-08T00:00:00+00:00"}],
    })
    assert rest_days(store, "BOS", "2026-01-10T00:00:00+00:00", "nba") == 2.0
    # No prior game -> None (cold start, no shift).
    assert rest_days(store, "NYK", "2026-01-10T00:00:00+00:00", "nba") is None
    # A "last game" at/after as_of is not point-in-time -> None.
    store2 = _FakeStore({("BOS", "nba"): [{"start_time": "2026-01-11T00:00:00+00:00"}]})
    assert rest_days(store2, "BOS", "2026-01-10T00:00:00+00:00", "nba") is None


def test_logit_shift_favours_rested_side_and_is_bounded():
    # Home rested (3 days) vs away back-to-back (1 day): positive shift.
    assert rest_logit_shift(3.0, 1.0, 0.09) > 0
    # Away more rested: negative.
    assert rest_logit_shift(1.0, 3.0, 0.09) < 0
    # Coefficient 0 or missing rest -> no shift.
    assert rest_logit_shift(3.0, 1.0, 0.0) == 0.0
    assert rest_logit_shift(None, 1.0, 0.09) == 0.0
    # Extreme differential is clamped.
    assert abs(rest_logit_shift(30.0, 0.0, 0.30)) <= MAX_REST_LOGIT_SHIFT + 1e-9


def test_apply_shift_moves_probability_in_logit_space():
    base = 0.50
    up = apply_rest_shift(base, 0.20)
    down = apply_rest_shift(base, -0.20)
    assert up > base > down
    # Symmetric around 0.5 for ±equal shift.
    assert abs((up - 0.5) - (0.5 - down)) < 1e-9
    # Clamped into [0.02, 0.98].
    assert apply_rest_shift(0.99, 5.0) <= 0.98


def test_rest_state_flags_back_to_back():
    store = _FakeStore({
        ("BOS", "nba"): [{"start_time": "2026-01-09T00:00:00+00:00"}],
        ("LAL", "nba"): [{"start_time": "2026-01-06T00:00:00+00:00"}],
    })
    state = rest_state(store, "BOS", "LAL", "2026-01-10T00:00:00+00:00", "nba")
    assert state["home_back_to_back"] is True    # 1 day
    assert state["away_back_to_back"] is False   # 4 days
    assert state["rest_diff_days"] == -3.0


def test_walk_forward_rest_zero_coefficient_matches_unshifted():
    # With coefficient 0 the graded predictions equal the pure scoring model,
    # so a league where rest is noise keeps the σ-only baseline (tuner picks 0).
    from autonomy.sports.rest import apply_rest_shift as _apply

    assert _apply(0.61, rest_logit_shift(2.0, 1.0, 0.0)) == _apply(0.61, 0.0)
    assert math.isclose(_apply(0.61, 0.0), 0.61, abs_tol=1e-9)
