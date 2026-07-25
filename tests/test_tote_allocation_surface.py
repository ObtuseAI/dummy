"""The tote app can read and change allocation policy without a restart."""
from __future__ import annotations

import json

import pytest

from autonomy.allocation_config import AllocationConfig
from desktop.dummy_tote.data import RepoData


def _root(tmp_path, payload=None):
    (tmp_path / "configs").mkdir(parents=True, exist_ok=True)
    if payload is not None:
        (tmp_path / "configs" / "allocation.json").write_text(
            json.dumps(payload), encoding="utf-8")
    return tmp_path


class TestConfigRoundTrip:
    def test_written_config_survives_a_reload_unchanged(self, tmp_path):
        path = tmp_path / "allocation.json"
        original = AllocationConfig(policy="proportional", top_k=3, min_weight=0.4,
                                    target_advantage=0.05, throttle=0.75)
        path.write_text(json.dumps(original.to_dict()), encoding="utf-8")
        assert AllocationConfig.load(path) == original


class TestNoDrift:
    """data.py mirrors these constants instead of importing them, because the
    tote app runs from its own venv with no dummy imports. That mirror must not
    drift, or the operator is shown defaults the engine does not use."""

    def test_defaults_match_the_engine(self):
        from desktop.dummy_tote.data import ALLOCATION_DEFAULTS

        engine = AllocationConfig().to_dict()
        assert ALLOCATION_DEFAULTS == engine

    def test_policy_list_matches_the_engine(self):
        from autonomy.candidate_allocation import POLICIES
        from desktop.dummy_tote.data import ALLOCATION_POLICIES

        assert set(ALLOCATION_POLICIES) == set(POLICIES)


class TestSnapshot:
    def test_snapshot_exposes_allocation(self, tmp_path):
        root = _root(tmp_path, {"policy": "top_k", "throttle": 0.5, "top_k": 3,
                                "min_weight": 0.25, "target_advantage": 0.02})
        snap = RepoData(root).snapshot()
        assert snap.allocation["policy"] == "top_k"
        assert snap.allocation["throttle"] == 0.5

    def test_absent_file_yields_documented_defaults(self, tmp_path):
        snap = RepoData(_root(tmp_path)).snapshot()
        assert snap.allocation["policy"] == "kelly_prorata"
        assert snap.allocation["throttle"] == 1.0


class TestSetAllocation:
    def test_writes_a_file_the_engine_can_read_back(self, tmp_path):
        root = _root(tmp_path)
        RepoData(root).set_allocation(policy="proportional", throttle=0.5)
        cfg = AllocationConfig.load(root / "configs" / "allocation.json")
        assert cfg.policy == "proportional"
        assert cfg.throttle == 0.5

    def test_partial_update_preserves_other_keys(self, tmp_path):
        root = _root(tmp_path, {"policy": "top_k", "top_k": 3, "min_weight": 0.4,
                                "target_advantage": 0.05, "throttle": 0.2})
        RepoData(root).set_allocation(throttle=0.9)
        cfg = AllocationConfig.load(root / "configs" / "allocation.json")
        assert cfg.throttle == 0.9
        assert cfg.policy == "top_k" and cfg.top_k == 3

    def test_rejects_an_unknown_policy(self, tmp_path):
        with pytest.raises(ValueError):
            RepoData(_root(tmp_path)).set_allocation(policy="nonsense")

    def test_clamps_throttle_rather_than_writing_an_out_of_range_value(self, tmp_path):
        root = _root(tmp_path)
        RepoData(root).set_allocation(throttle=99.0)
        raw = json.loads((root / "configs" / "allocation.json").read_text(encoding="utf-8"))
        assert raw["throttle"] == 1.0

    def test_throttle_can_only_shrink_never_enlarge_the_pot(self, tmp_path):
        """There is no operator value here that enlarges the pot; enlarging
        requires the sealed-caps ceremony."""
        root = _root(tmp_path)
        for attempt in (5.0, 100.0, float("inf")):
            RepoData(root).set_allocation(throttle=attempt)
            cfg = AllocationConfig.load(root / "configs" / "allocation.json")
            assert cfg.throttle <= 1.0

    def test_negative_throttle_floors_at_zero(self, tmp_path):
        root = _root(tmp_path)
        RepoData(root).set_allocation(throttle=-3.0)
        assert AllocationConfig.load(root / "configs" / "allocation.json").throttle == 0.0

    def test_every_policy_is_settable(self, tmp_path):
        root = _root(tmp_path)
        for policy in ("kelly_prorata", "proportional", "top_k"):
            RepoData(root).set_allocation(policy=policy)
            assert AllocationConfig.load(
                root / "configs" / "allocation.json").policy == policy
