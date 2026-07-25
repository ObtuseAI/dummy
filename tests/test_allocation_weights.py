"""Turning contested-Brier advantage into an allocation weight."""
from __future__ import annotations

from autonomy.allocation_config import AllocationConfig
from autonomy.allocation_weights import weight_for_advantage, weights_for_scopes

CFG = AllocationConfig(min_weight=0.25, target_advantage=0.02)


class TestWeightForAdvantage:
    def test_unknown_advantage_gets_the_floor_not_zero(self):
        assert weight_for_advantage(None, min_weight=0.25, target_advantage=0.02) == 0.25

    def test_negative_advantage_gets_the_floor(self):
        assert weight_for_advantage(-0.05, min_weight=0.25, target_advantage=0.02) == 0.25

    def test_zero_advantage_gets_the_floor(self):
        assert weight_for_advantage(0.0, min_weight=0.25, target_advantage=0.02) == 0.25

    def test_advantage_at_target_earns_full_weight(self):
        assert weight_for_advantage(0.02, min_weight=0.25, target_advantage=0.02) == 1.0

    def test_advantage_above_target_is_capped_at_one(self):
        assert weight_for_advantage(0.50, min_weight=0.25, target_advantage=0.02) == 1.0

    def test_partial_advantage_interpolates_above_the_floor(self):
        w = weight_for_advantage(0.01, min_weight=0.25, target_advantage=0.02)
        assert 0.25 < w < 1.0

    def test_monotone_in_advantage(self):
        weights = [weight_for_advantage(a, min_weight=0.25, target_advantage=0.02)
                   for a in (0.0, 0.005, 0.01, 0.015, 0.02, 0.03)]
        assert weights == sorted(weights)

    def test_bool_is_not_a_number(self):
        assert weight_for_advantage(True, min_weight=0.25, target_advantage=0.02) == 0.25


class TestWeightsForScopes:
    def test_every_requested_scope_is_present(self):
        out = weights_for_scopes(["a", "b"], {"a": 0.02}, config=CFG)
        assert set(out) == {"a", "b"}

    def test_missing_scope_falls_to_the_floor(self):
        out = weights_for_scopes(["a", "b"], {"a": 0.02}, config=CFG)
        assert out["a"] == 1.0 and out["b"] == 0.25

    def test_no_weight_is_ever_zero(self):
        out = weights_for_scopes(["a", "b", "c"], {}, config=CFG)
        assert all(w > 0.0 for w in out.values())

    def test_non_numeric_advantage_is_treated_as_unknown(self):
        out = weights_for_scopes(["a"], {"a": "banana"}, config=CFG)
        assert out["a"] == 0.25

    def test_empty_scopes_returns_empty(self):
        assert weights_for_scopes([], {"a": 0.02}, config=CFG) == {}
