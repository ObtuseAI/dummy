from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_weather_evidence_packet_v3_labels_model_data_gate() -> None:
    report = assert_v20_report("weather_evidence_packet_v3_report.json", "source_blockers")
    assert "HRRR/GFS/ECMWF model-data plan/gate" in report["source_blockers"]
