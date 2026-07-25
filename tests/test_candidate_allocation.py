"""Cross-candidate allocation: dividing one pot among competing asks."""
from __future__ import annotations

from autonomy.candidate_allocation import Ask, allocate


def _asks(*specs):
    return [Ask(candidate_id=cid, scope=scope, ask_cents=cents, price_cents=10)
            for cid, scope, cents in specs]


def _total(grants):
    return sum(g.granted_cents for g in grants)


class TestInvariants:
    def test_never_exceeds_the_pot(self):
        asks = _asks(("a", "s1", 800), ("b", "s2", 800), ("c", "s3", 800))
        for policy in ("kelly_prorata", "proportional", "top_k"):
            grants = allocate(asks, 1000, {"s1": 1.0, "s2": 1.0, "s3": 1.0}, policy)
            assert _total(grants) <= 1000, policy

    def test_never_raises_a_size_above_its_ask(self):
        asks = _asks(("a", "s1", 50), ("b", "s2", 50))
        for policy in ("kelly_prorata", "proportional", "top_k"):
            grants = allocate(asks, 10_000, {"s1": 1.0, "s2": 1.0}, policy)
            by_id = {g.candidate_id: g.granted_cents for g in grants}
            assert by_id["a"] <= 50 and by_id["b"] <= 50, policy

    def test_adding_a_candidate_never_increases_an_existing_grant(self):
        weights = {"s1": 1.0, "s2": 1.0, "s3": 1.0}
        for policy in ("kelly_prorata", "proportional", "top_k"):
            before = allocate(_asks(("a", "s1", 900), ("b", "s2", 900)),
                              1000, weights, policy, top_k=2)
            after = allocate(_asks(("a", "s1", 900), ("b", "s2", 900), ("c", "s3", 900)),
                             1000, weights, policy, top_k=2)
            b_before = {g.candidate_id: g.granted_cents for g in before}
            b_after = {g.candidate_id: g.granted_cents for g in after}
            for cid in ("a", "b"):
                assert b_after[cid] <= b_before[cid], f"{policy}/{cid}"

    def test_higher_weight_never_lowers_its_own_grant(self):
        asks = _asks(("a", "s1", 900), ("b", "s2", 900))
        low = allocate(asks, 1000, {"s1": 0.25, "s2": 1.0}, "kelly_prorata")
        high = allocate(asks, 1000, {"s1": 1.0, "s2": 1.0}, "kelly_prorata")
        a_low = next(g.granted_cents for g in low if g.candidate_id == "a")
        a_high = next(g.granted_cents for g in high if g.candidate_id == "a")
        assert a_high >= a_low

    def test_deterministic_across_calls(self):
        asks = _asks(("a", "s1", 500), ("b", "s1", 500), ("c", "s1", 500))
        first = allocate(asks, 700, {"s1": 1.0}, "kelly_prorata")
        second = allocate(asks, 700, {"s1": 1.0}, "kelly_prorata")
        assert [g.granted_cents for g in first] == [g.granted_cents for g in second]


class TestKellyProrata:
    def test_undersubscribed_deploys_less_than_the_pot(self):
        grants = allocate(_asks(("a", "s1", 100), ("b", "s2", 100)),
                          10_000, {"s1": 1.0, "s2": 1.0}, "kelly_prorata")
        assert _total(grants) == 200

    def test_oversubscribed_scales_everyone_down_proportionally(self):
        grants = allocate(_asks(("a", "s1", 1000), ("b", "s2", 1000)),
                          1000, {"s1": 1.0, "s2": 1.0}, "kelly_prorata")
        by_id = {g.candidate_id: g.granted_cents for g in grants}
        assert by_id["a"] == 500 and by_id["b"] == 500

    def test_weight_shifts_the_split(self):
        grants = allocate(_asks(("a", "s1", 1000), ("b", "s2", 1000)),
                          1000, {"s1": 1.0, "s2": 0.25}, "kelly_prorata")
        by_id = {g.candidate_id: g.granted_cents for g in grants}
        assert by_id["a"] > by_id["b"]


class TestProportional:
    def test_splits_the_pot_by_weight_share(self):
        grants = allocate(_asks(("a", "s1", 10_000), ("b", "s2", 10_000)),
                          1000, {"s1": 3.0, "s2": 1.0}, "proportional")
        by_id = {g.candidate_id: g.granted_cents for g in grants}
        assert by_id["a"] == 750 and by_id["b"] == 250

    def test_clamps_to_the_ask_without_redistributing(self):
        grants = allocate(_asks(("a", "s1", 100), ("b", "s2", 10_000)),
                          1000, {"s1": 1.0, "s2": 1.0}, "proportional")
        by_id = {g.candidate_id: g.granted_cents for g in grants}
        assert by_id["a"] == 100
        assert by_id["b"] == 500  # NOT 900 -- no redistribution


class TestTopK:
    def test_funds_only_the_top_k_by_weight(self):
        grants = allocate(
            _asks(("a", "s1", 300), ("b", "s2", 300), ("c", "s3", 300)),
            10_000, {"s1": 1.0, "s2": 0.5, "s3": 0.25}, "top_k", top_k=2)
        by_id = {g.candidate_id: g.granted_cents for g in grants}
        assert by_id["a"] == 300 and by_id["b"] == 300 and by_id["c"] == 0


class TestDegenerate:
    def test_zero_pot_grants_nothing(self):
        grants = allocate(_asks(("a", "s1", 100)), 0, {"s1": 1.0}, "kelly_prorata")
        assert _total(grants) == 0

    def test_negative_pot_grants_nothing(self):
        grants = allocate(_asks(("a", "s1", 100)), -5, {"s1": 1.0}, "kelly_prorata")
        assert _total(grants) == 0

    def test_no_asks_returns_empty(self):
        assert allocate([], 1000, {}, "kelly_prorata") == []

    def test_nonpositive_ask_is_excluded(self):
        grants = allocate(_asks(("a", "s1", 0), ("b", "s2", 100)),
                          1000, {"s1": 1.0, "s2": 1.0}, "kelly_prorata")
        by_id = {g.candidate_id: g.granted_cents for g in grants}
        assert by_id["a"] == 0 and by_id["b"] == 100

    def test_missing_weight_is_treated_as_zero_contribution_not_a_crash(self):
        grants = allocate(_asks(("a", "unknown_scope", 100)),
                          1000, {}, "kelly_prorata")
        assert _total(grants) == 0

    def test_unknown_policy_falls_back_to_kelly_prorata(self):
        grants = allocate(_asks(("a", "s1", 1000), ("b", "s2", 1000)),
                          1000, {"s1": 1.0, "s2": 1.0}, "nonsense")
        by_id = {g.candidate_id: g.granted_cents for g in grants}
        assert by_id["a"] == 500 and by_id["b"] == 500
        assert all(g.policy == "kelly_prorata" for g in grants)
