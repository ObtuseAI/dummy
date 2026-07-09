from __future__ import annotations

from v19_test_helpers import assert_domain_evidence_packet


def test_weather_real_evidence_packet_tracks_station_and_freshness_shape() -> None:
    assert_domain_evidence_packet("weather")
