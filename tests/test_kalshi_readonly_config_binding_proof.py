from __future__ import annotations

from tests.v16_test_helpers import missing_runtime_config, valid_runtime_config


def test_config_binding_proof_passes_for_valid_runtime_config() -> None:
    from predator_mesh.v16.runtime_config import KalshiReadOnlyConfigBindingProof

    report = KalshiReadOnlyConfigBindingProof(valid_runtime_config()).to_report()

    assert report["binding_state"] == "PASS"
    assert report["same_config_for_auth_discovery_snapshot"] is True
    assert report["secret_values_exposed"] is False


def test_config_binding_proof_blocks_invalid_selected_source() -> None:
    from predator_mesh.v16.runtime_config import KalshiReadOnlyConfigBindingProof

    report = KalshiReadOnlyConfigBindingProof(missing_runtime_config()).to_report()

    assert report["binding_state"] == "PARTIAL_CONFIG_BINDING_ERROR"
    assert report["terrain_retry_allowed"] is False
