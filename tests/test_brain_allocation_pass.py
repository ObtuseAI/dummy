"""The brain divides one pot across the cycle instead of first-come-first-served."""
from __future__ import annotations

import inspect

from autonomy.candidate_allocation import Ask, allocate


def test_two_candidates_cannot_both_take_the_whole_pot():
    """Regression for the greedy path.

    ``autonomy/allocator.py`` used to hand the first-ranked candidate the whole
    remaining budget, so a near-equal rival could be left with nothing.
    """
    asks = [Ask("first", "scope_a", 1000, 10), Ask("second", "scope_b", 1000, 10)]
    grants = allocate(asks, 1000, {"scope_a": 1.0, "scope_b": 1.0}, "kelly_prorata")
    assert sum(g.granted_cents for g in grants) <= 1000
    assert all(g.granted_cents > 0 for g in grants), "both must be funded"


class TestBrainWiring:
    def test_brain_runs_the_allocation_pass(self):
        import autonomy.brain as brain

        source = inspect.getsource(brain)
        assert "candidate_allocation" in source
        assert "allocation_cap_cents" in source

    def test_asks_are_built_from_the_evaluated_slice_not_all_scored(self):
        """The pot must be divided among candidates that will actually be
        evaluated. Building asks from ``scored`` would spread the pot across
        markets past MAX_CANDIDATES_EVALUATED that never reach decide()."""
        import autonomy.brain as brain

        source = inspect.getsource(brain)
        assert "alloc_pool = decision_slice" in source

    def test_pot_is_divided_only_across_holdable_slots(self):
        """MAX_CANDIDATES_EVALUATED is 100 but a stage may permit 5 open
        markets. Splitting the pot 100 ways would drive every grant below the
        price of one contract and silently halt trading."""
        import autonomy.brain as brain

        source = inspect.getsource(brain)
        assert "alloc_slots" in source
        assert "max_open_markets" in source

    def test_candidates_outside_the_pool_are_granted_zero_not_unlimited(self):
        """alloc_grants.get(ticker) returning None would leave a candidate
        UNCAPPED, which is the greedy bug this whole change removes."""
        import autonomy.brain as brain

        source = inspect.getsource(brain)
        assert "alloc_grants.get(market.ticker, 0)" in source

    def test_scope_helper_never_raises_on_a_bad_market(self):
        from autonomy.brain import PredatorBrain

        class _Bad:
            @property
            def ticker(self):
                raise RuntimeError("boom")

        # Unbound call: the helper must not depend on brain state.
        result = PredatorBrain._allocation_scope(None, _Bad(), None)
        assert isinstance(result, str)

    def test_scope_advantages_returns_empty_when_snapshot_absent(self, monkeypatch, tmp_path):
        from autonomy.brain import PredatorBrain

        monkeypatch.chdir(tmp_path)
        assert PredatorBrain._scope_advantages(None) == {}
