from __future__ import annotations

from predator_mesh.v10.validation import ValidationProfile, ValidationShardRunner


def test_validation_profiles_are_bounded() -> None:
    runner = ValidationShardRunner()
    shards = runner.shards_for_profile(ValidationProfile.MESH_ONLY)
    assert shards
    assert all(shard.timeout_s <= 60 for shard in shards)
    assert all("pytest tests/" in shard.command or "npm run build" in shard.command for shard in shards)


def test_validation_sharding_report() -> None:
    report = ValidationShardRunner().to_report()
    assert report["verdict"] == "PASS"
    assert "full_regression" in report["profiles"]
    assert report["recursive_pytest_allowed"] is False
