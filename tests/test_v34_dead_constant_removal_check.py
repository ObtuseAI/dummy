from __future__ import annotations

from tests.v35_test_helpers import assert_current_test_report


def test_dead_constants_removed() -> None:
    report = assert_current_test_report(__file__)
    assert report["dead_constants_removed"] is True
    assert report["operator_action_not_referenced"] is True
    assert report["trading_language_not_referenced"] is True
    assert report["gate_logic_delegates_to_v33"] is True
    assert report["execution_bridge_present"] is False


def test_no_dead_constant_references_in_v34_run() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    run_text = (root / "predator_mesh" / "v34" / "run.py").read_text(encoding="utf-8")
    assert "OPERATOR_ACTION" not in run_text
    assert "TRADING_LANGUAGE" not in run_text
