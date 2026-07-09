from __future__ import annotations

from predator_mesh.v33.run import PublicProbeArtifactCacheV3, build_default_v33_state
from tests.v33_test_helpers import assert_current_test_report


def test_public_probe_artifact_cache_keeps_modes_and_redaction_explicit() -> None:
    cache = PublicProbeArtifactCacheV3().cache(build_default_v33_state(enable_network=False))

    assert cache.public_probe_artifact_cache_status == "PASS"
    assert cache.cache_mode == "DISABLED_NO_LIVE_RECORDS"
    assert cache.raw_payload_redacted is True
    assert cache.secret_values_exposed is False
    assert cache.execution_bridge_present is False


def test_public_probe_artifact_cache_report_contract() -> None:
    report = assert_current_test_report(__file__)

    assert report["public_probe_artifact_cache_status"] == "PASS"
    assert report["raw_payload_redacted"] is True
