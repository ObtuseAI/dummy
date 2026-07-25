"""Operator control over allocation: file, env override, and fail-safe defaults."""
from __future__ import annotations

import json

from autonomy.allocation_config import AllocationConfig


def _write(tmp_path, payload):
    path = tmp_path / "allocation.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class TestDefaults:
    def test_missing_file_yields_stock_defaults(self, tmp_path):
        cfg = AllocationConfig.load(tmp_path / "absent.json")
        assert cfg.policy == "kelly_prorata"
        assert cfg.top_k == 5
        assert cfg.min_weight == 0.25
        assert cfg.target_advantage == 0.02
        assert cfg.throttle == 1.0

    def test_malformed_file_fails_safe_to_defaults_not_to_full_deployment(self, tmp_path):
        path = tmp_path / "allocation.json"
        path.write_text("{not json", encoding="utf-8")
        cfg = AllocationConfig.load(path)
        assert cfg.policy == "kelly_prorata"
        assert cfg.throttle == 1.0

    def test_unknown_policy_falls_back(self, tmp_path):
        cfg = AllocationConfig.load(_write(tmp_path, {"policy": "nonsense"}))
        assert cfg.policy == "kelly_prorata"


class TestFileValues:
    def test_reads_every_key(self, tmp_path):
        cfg = AllocationConfig.load(_write(tmp_path, {
            "policy": "top_k", "top_k": 3, "min_weight": 0.4,
            "target_advantage": 0.05, "throttle": 0.5,
        }))
        assert (cfg.policy, cfg.top_k, cfg.min_weight) == ("top_k", 3, 0.4)
        assert (cfg.target_advantage, cfg.throttle) == (0.05, 0.5)


class TestClamps:
    def test_throttle_clamped_to_unit_interval(self, tmp_path):
        assert AllocationConfig.load(_write(tmp_path, {"throttle": 5.0})).throttle == 1.0
        assert AllocationConfig.load(_write(tmp_path, {"throttle": -1.0})).throttle == 0.0

    def test_min_weight_never_zero(self, tmp_path):
        cfg = AllocationConfig.load(_write(tmp_path, {"min_weight": 0.0}))
        assert cfg.min_weight > 0.0

    def test_min_weight_capped_at_one(self, tmp_path):
        assert AllocationConfig.load(_write(tmp_path, {"min_weight": 9.0})).min_weight == 1.0

    def test_top_k_never_negative(self, tmp_path):
        assert AllocationConfig.load(_write(tmp_path, {"top_k": -3})).top_k == 0

    def test_garbage_types_fall_back_per_key(self, tmp_path):
        cfg = AllocationConfig.load(_write(tmp_path, {
            "top_k": "lots", "throttle": None, "min_weight": [],
        }))
        assert cfg.top_k == 5 and cfg.throttle == 1.0 and cfg.min_weight == 0.25


class TestEnvOverride:
    def test_env_beats_file(self, tmp_path, monkeypatch):
        path = _write(tmp_path, {"policy": "top_k", "throttle": 0.2})
        monkeypatch.setenv("DUMMY_ALLOC_POLICY", "proportional")
        monkeypatch.setenv("DUMMY_ALLOC_THROTTLE", "0.75")
        cfg = AllocationConfig.load(path)
        assert cfg.policy == "proportional" and cfg.throttle == 0.75

    def test_garbage_env_is_ignored_in_favour_of_the_file(self, tmp_path, monkeypatch):
        path = _write(tmp_path, {"throttle": 0.3})
        monkeypatch.setenv("DUMMY_ALLOC_THROTTLE", "banana")
        assert AllocationConfig.load(path).throttle == 0.3

    def test_env_throttle_is_clamped_too(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DUMMY_ALLOC_THROTTLE", "99")
        assert AllocationConfig.load(tmp_path / "absent.json").throttle == 1.0


class TestShippedConfig:
    def test_repo_config_parses_to_documented_defaults(self):
        from autonomy.allocation_config import CONFIG_PATH
        cfg = AllocationConfig.load(CONFIG_PATH)
        assert cfg.policy == "kelly_prorata"
        assert cfg.throttle == 1.0
