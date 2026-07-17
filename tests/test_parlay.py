"""Wave-10: correlation-aware parlay / combo fair-value engine."""
from __future__ import annotations

from autonomy.parlay import (
    ParlayLeg,
    alignment_loading,
    joint_probability,
    naive_independent,
    normal_cdf,
    normal_ppf,
    price_parlay,
)


def test_ppf_cdf_round_trip():
    for p in (0.02, 0.1, 0.3, 0.5, 0.73, 0.95, 0.99):
        assert abs(normal_cdf(normal_ppf(p)) - p) < 1e-6


def test_different_games_are_independent():
    legs = [ParlayLeg("A", 0.6, 0.72, "g1"), ParlayLeg("B", 0.5, 0.72, "g2")]
    assert abs(joint_probability(legs) - 0.30) < 1e-3          # 0.6 * 0.5
    assert abs(joint_probability(legs) - naive_independent(legs)) < 1e-3


def test_legs_without_game_id_are_independent():
    legs = [ParlayLeg("A", 0.6), ParlayLeg("B", 0.5)]
    assert abs(joint_probability(legs) - 0.30) < 1e-3


def test_single_leg_returns_its_probability():
    assert abs(joint_probability([ParlayLeg("x", 0.42)]) - 0.42) < 1e-9


def test_same_game_aligned_legs_beat_the_product():
    """Positively correlated same-game legs -> true joint ABOVE the independence
    product. An independence-priced combo is therefore underpriced (edge > 0)."""
    legs = [ParlayLeg("NYY win", 0.6, 0.72, "g"), ParlayLeg("NYY team total over", 0.55, 0.72, "g")]
    pricing = price_parlay(legs, combo_price=naive_independent(legs))
    assert pricing.fair_prob > pricing.naive_prob
    assert pricing.correlation_premium > 0.05
    assert pricing.edge > 0.05                                 # priced at product => positive edge
    assert pricing.features["same_game"] is True


def test_same_game_opposing_legs_fall_below_the_product():
    legs = [ParlayLeg("NYY win", 0.6, 0.72, "g"), ParlayLeg("LAD win", 0.4, -0.72, "g")]
    pricing = price_parlay(legs)
    assert pricing.fair_prob < pricing.naive_prob
    assert pricing.correlation_premium < -0.05


def test_three_leg_same_game_stack_premium():
    stack = [
        ParlayLeg("win", 0.60, 0.72, "g"),
        ParlayLeg("team total over", 0.55, 0.72, "g"),
        ParlayLeg("first-five win", 0.57, 0.60, "g"),
    ]
    pricing = price_parlay(stack, combo_price=0.18)
    assert pricing.n_legs == 3
    assert pricing.fair_prob > 0.28                            # ~0.31, vs 0.19 product
    assert pricing.correlation_premium > 0.10
    assert pricing.edge > 0.10


def test_mixed_correlated_and_independent_games():
    """A same-game correlated pair combined with an unrelated third game: the
    correlated pair lifts above its own product, then the third multiplies in."""
    legs = [
        ParlayLeg("NYY win", 0.6, 0.72, "gA"),
        ParlayLeg("NYY team total over", 0.55, 0.72, "gA"),
        ParlayLeg("BOS win", 0.5, 0.72, "gB"),
    ]
    pair_only = joint_probability(legs[:2])
    assert abs(joint_probability(legs) - pair_only * 0.5) < 1e-3


def test_alignment_loadings_have_correct_signs():
    assert alignment_loading("winner", "full", True) > 0
    assert alignment_loading("winner", "full", False) < 0
    # First-five is noisier -> a smaller magnitude than the full-game leg.
    assert abs(alignment_loading("winner", "f5", True)) < alignment_loading("winner", "full", True)
    # Combined totals are only weakly tied to who wins.
    assert 0 < alignment_loading("total", "full", None) < 0.3
    assert alignment_loading("spread", "full", True) > 0
    assert alignment_loading("team_total", "full", False) < 0


def test_no_edge_reported_without_a_combo_price():
    pricing = price_parlay([ParlayLeg("a", 0.6, 0.72, "g"), ParlayLeg("b", 0.5, 0.72, "g")])
    assert pricing.edge is None and pricing.combo_price is None
    assert pricing.fair_prob > 0
