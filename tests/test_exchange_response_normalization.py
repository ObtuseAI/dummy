from __future__ import annotations

from predator_mesh.v11.reconcile import ExchangeResponseNormalizer


def test_exchange_response_normalizer_handles_simulated_states() -> None:
    normalizer = ExchangeResponseNormalizer()

    assert normalizer.normalize({"order": {"status": "partially_filled", "filled_count": 1}})["normalized_state"] == "PARTIAL_FILL_SIMULATED"
    assert normalizer.normalize({"order": {"status": "filled", "filled_count": 2}})["normalized_state"] == "FILLED_SIMULATED"
    assert normalizer.normalize({"bad": object()})["normalized_state"] == "ERROR_QUARANTINED"
    assert normalizer.to_report()["verdict"] == "PASS"
