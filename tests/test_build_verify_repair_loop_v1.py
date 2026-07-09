from __future__ import annotations

from tests.v37_test_helpers import assert_current_test_report


def test_build_verify_repair_loop_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["build_verify_repair_loop_status"] == "PASS"
    assert report["max_repair_attempts"] == 2
    assert report["bounded_loop"] is True
    assert "python -m py_compile predator_mesh/v37/reports.py scripts/generate_v37_reports.py dashboard/backend/v37_routes.py" in report["verification_commands"]
    assert report["real_probe_requires_exact_gate"] is True
