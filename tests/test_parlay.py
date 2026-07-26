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


def test_legacy_same_game_opposing_descriptions_are_not_guessed():
    # Backward-compatible legacy legs have no explicit settlement semantics.
    # The engine may model negative correlation but must not parse free text
    # and pretend it proved mutual exclusivity.
    legs = [ParlayLeg("NYY win", 0.6, 0.72, "g"), ParlayLeg("LAD win", 0.4, -0.72, "g")]
    pricing = price_parlay(legs)
    assert pricing.fair_prob > 0.0
    assert pricing.fair_prob < pricing.naive_prob
    assert pricing.correlation_premium < -0.05
    assert pricing.features["semantic_status"] == "LEGACY_UNCHECKED"


def test_explicit_opposing_winners_are_mutually_exclusive():
    legs = [
        ParlayLeg(
            "NYY win",
            0.6,
            0.72,
            "g",
            identity="g:winner:nyy",
            outcome="nyy",
            exclusivity_group="full_game_winner",
        ),
        ParlayLeg(
            "LAD win",
            0.4,
            -0.72,
            "g",
            identity="g:winner:lad",
            outcome="lad",
            exclusivity_group="full_game_winner",
        ),
    ]
    pricing = price_parlay(legs, combo_price=0.20)
    assert joint_probability(legs) == 0.0
    assert naive_independent(legs) == 0.0
    assert pricing.fair_prob == 0.0
    assert pricing.edge == -0.20
    assert pricing.features["semantic_status"] == "MUTUALLY_EXCLUSIVE"
    assert pricing.features["pricing_status"] == "IMPOSSIBLE_MUTUALLY_EXCLUSIVE"
    assert pricing.features["contradiction_reasons"] == [
        "exclusivity_group:g:full_game_winner"
    ]


def test_explicit_over_and_under_on_same_line_are_mutually_exclusive():
    legs = [
        ParlayLeg(
            "over 8.5",
            0.52,
            0.15,
            "g",
            identity="g:total:8.5:over",
            outcome="over",
            exclusivity_group="full_game_total:8.5",
        ),
        ParlayLeg(
            "under 8.5",
            0.48,
            -0.15,
            "g",
            identity="g:total:8.5:under",
            outcome="under",
            exclusivity_group="full_game_total:8.5",
        ),
    ]
    assert joint_probability(legs) == 0.0
    assert price_parlay(legs).fair_prob == 0.0


def test_opposite_outcomes_on_one_contract_identity_are_impossible():
    legs = [
        ParlayLeg(
            "contract yes",
            0.62,
            game_id="g",
            ticker="KX-CONTRACT",
            outcome="yes",
        ),
        ParlayLeg(
            "contract no",
            0.38,
            game_id="g",
            ticker="KX-CONTRACT",
            outcome="no",
        ),
    ]
    pricing = price_parlay(legs)
    assert pricing.fair_prob == 0.0
    assert pricing.features["contradiction_reasons"] == [
        "identity:g:kx-contract"
    ]


def test_exclusivity_group_is_scoped_by_game():
    legs = [
        ParlayLeg(
            "game one home",
            0.55,
            0.72,
            "g1",
            identity="g1:winner:home",
            outcome="home",
            exclusivity_group="full_game_winner",
        ),
        ParlayLeg(
            "game two away",
            0.45,
            -0.72,
            "g2",
            identity="g2:winner:away",
            outcome="away",
            exclusivity_group="full_game_winner",
        ),
    ]
    assert abs(joint_probability(legs) - 0.55 * 0.45) < 1e-3


def test_exact_duplicate_leg_is_collapsed_not_multiplied():
    leg = ParlayLeg(
        "NYY win",
        0.55,
        0.72,
        "g",
        ticker="KXMLBGAME-G-NYY",
        identity="g:winner:nyy",
        outcome="nyy",
        exclusivity_group="full_game_winner",
    )
    pricing = price_parlay([leg, leg], combo_price=0.55)
    assert joint_probability([leg, leg]) == 0.55
    assert naive_independent([leg, leg]) == 0.55
    assert pricing.fair_prob == 0.55
    assert pricing.naive_prob == 0.55
    assert pricing.edge == 0.0
    assert pricing.n_legs == 1
    assert pricing.features["input_legs"] == 2
    assert pricing.features["effective_legs"] == 1
    assert pricing.features["duplicate_legs_collapsed"] == 1
    assert pricing.features["duplicate_conflicts"] == 0


def test_conflicting_duplicate_estimates_collapse_conservatively():
    common = {
        "game_id": "g",
        "identity": "g:winner:nyy",
        "outcome": "nyy",
        "exclusivity_group": "full_game_winner",
    }
    legs = [
        ParlayLeg("NYY win v1", 0.60, 0.72, **common),
        ParlayLeg("NYY win v2", 0.54, 0.60, **common),
    ]
    pricing = price_parlay(legs)
    assert pricing.fair_prob == 0.54
    assert pricing.n_legs == 1
    assert pricing.features["duplicate_legs_collapsed"] == 1
    assert pricing.features["duplicate_conflicts"] == 1
    assert pricing.features["calibration_status"] == "UNCALIBRATED"
    assert pricing.features["execution_authority"] is False
    assert pricing.features["promotion_authority"] is False


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
    assert pricing.features["calibration_status"] == "UNCALIBRATED"
    assert pricing.features["execution_authority"] is False
