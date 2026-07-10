from __future__ import annotations

from datetime import datetime, timezone

from autonomy.ledger import AutonomyLedger
from autonomy.statistics_intake import (
    collect_public_statistics,
    parse_bls,
    parse_deribit_dvol,
    parse_nws_latest,
)


def test_parsers_preserve_units_and_source_provenance():
    bls = parse_bls({"Results": {"series": [{
        "seriesID": "CUUR0000SA0",
        "data": [{"year": "2026", "period": "M06", "periodName": "June",
                  "value": "321.5", "footnotes": []}],
    }]}})
    assert bls[0].source == "bls"
    assert bls[0].unit == "index_1982_84_100"
    dvol = parse_deribit_dvol({"result": {"data": [[1_700_000_000_000, 50, 55, 49, 53]]}}, "BTC")
    assert dvol[0].series_id == "BTC_DVOL_1H"
    assert dvol[0].value == 53
    nws = parse_nws_latest({"properties": {
        "timestamp": "2026-07-09T12:00:00+00:00",
        "temperature": {"value": 20.0}, "textDescription": "Clear",
    }}, "KNYC", "NY")
    assert nws[0].value == 68.0


def test_collection_is_deduplicated_and_isolates_source_failure(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    bls_payload = {"Results": {"series": [{
        "seriesID": "CUUR0000SA0",
        "data": [{"year": "2026", "period": "M06", "value": "321.5"}],
    }]}}
    dvol_payload = {"result": {"data": [[1_700_000_000_000, 50, 55, 49, 53]]}}
    nws_payload = {"properties": {
        "timestamp": "2026-07-09T12:00:00+00:00",
        "temperature": {"value": 20.0},
    }}
    try:
        kwargs = {
            "fetch_bls": lambda *_args: bls_payload,
            "fetch_deribit": lambda currency, *_args: (
                (_ for _ in ()).throw(RuntimeError("ETH unavailable"))
                if currency == "ETH" else dvol_payload
            ),
            "fetch_nws": lambda _station: nws_payload,
            "now": datetime(2026, 7, 9, tzinfo=timezone.utc),
        }
        first = collect_public_statistics(ledger, **kwargs)
        second = collect_public_statistics(ledger, **kwargs)
        assert first["execution_authority"] is False
        assert first["sources"]["deribit_dvol_eth"]["status"] == "ERROR"
        assert first["ledger_summary"]["total_observations"] == 10
        assert second["ledger_summary"]["total_observations"] == 10
        assert second["sources"]["bls"]["duplicates"] == 1
        assert ledger.record_external_observation(
            source="bls", series_id="CUUR0000SA0",
            observed_at="2026-06-01T00:00:00+00:00", value=322.0,
            unit="index_1982_84_100", features={"revision": True},
        ) is True
        assert ledger.external_observation_summary()["total_observations"] == 11
    finally:
        ledger.close()
