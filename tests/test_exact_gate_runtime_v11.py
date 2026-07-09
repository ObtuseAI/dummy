from __future__ import annotations

from tests.v43_test_helpers import assert_current_test_report


def test_exact_gate_runtime_v11_report() -> None:
    assert_current_test_report(__file__)
