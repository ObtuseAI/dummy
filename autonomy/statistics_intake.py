"""Public, read-only intake for raw economic, volatility, and weather facts.

Raw observations are provenance-bearing research inputs, not probabilities.
No adapter in this module can place an order or alter a forecasting weight.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from autonomy.ledger import AutonomyLedger

BLS_SERIES = {
    "CUUR0000SA0": {"name": "CPI-U all items", "unit": "index_1982_84_100"},
    "LNS14000000": {"name": "Civilian unemployment rate", "unit": "percent"},
    "CES0000000001": {"name": "Total nonfarm payroll employment", "unit": "thousands"},
}

NWS_STATIONS = {
    "NY": "KNYC", "CHI": "KORD", "MIA": "KMIA", "AUS": "KAUS",
    "DEN": "KDEN", "PHIL": "KPHL", "LAX": "KLAX", "TSEA": "KSEA",
}


@dataclass(frozen=True)
class ExternalObservation:
    source: str
    series_id: str
    observed_at: str
    value: float
    unit: str
    published_at: str | None = None
    features: dict[str, Any] = field(default_factory=dict)


def default_fetch_bls(series_ids: list[str], start_year: int, end_year: int) -> dict[str, Any]:
    import httpx

    response = httpx.post(
        "https://api.bls.gov/publicAPI/v2/timeseries/data/",
        json={"seriesid": series_ids, "startyear": str(start_year), "endyear": str(end_year)},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def parse_bls(payload: dict[str, Any]) -> list[ExternalObservation]:
    observations: list[ExternalObservation] = []
    series_rows = ((payload.get("Results") or {}).get("series") or [])
    for series in series_rows:
        series_id = str(series.get("seriesID") or "")
        metadata = BLS_SERIES.get(series_id, {"name": series_id, "unit": "reported_value"})
        for row in series.get("data") or []:
            year = str(row.get("year") or "")
            period = str(row.get("period") or "")
            if len(year) != 4 or not period.startswith("M") or period == "M13":
                continue
            try:
                month = int(period[1:])
                value = float(str(row.get("value", "")).replace(",", ""))
                observed = datetime(int(year), month, 1, tzinfo=timezone.utc).isoformat()
            except (TypeError, ValueError):
                continue
            observations.append(ExternalObservation(
                source="bls",
                series_id=series_id,
                observed_at=observed,
                value=value,
                unit=str(metadata["unit"]),
                features={
                    "name": metadata["name"],
                    "period_name": row.get("periodName"),
                    "footnotes": row.get("footnotes") or [],
                },
            ))
    return observations


def default_fetch_deribit_dvol(
    currency: str, start_timestamp: int, end_timestamp: int,
) -> dict[str, Any]:
    import httpx

    response = httpx.get(
        "https://www.deribit.com/api/v2/public/get_volatility_index_data",
        params={
            "currency": currency,
            "start_timestamp": start_timestamp,
            "end_timestamp": end_timestamp,
            "resolution": "3600",
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def parse_deribit_dvol(payload: dict[str, Any], currency: str) -> list[ExternalObservation]:
    observations: list[ExternalObservation] = []
    for row in ((payload.get("result") or {}).get("data") or []):
        if not isinstance(row, list) or len(row) < 5:
            continue
        try:
            observed_at = datetime.fromtimestamp(float(row[0]) / 1000, timezone.utc).isoformat()
            open_value, high, low, close = map(float, row[1:5])
        except (TypeError, ValueError, OSError):
            continue
        observations.append(ExternalObservation(
            source="deribit_dvol",
            series_id=f"{currency.upper()}_DVOL_1H",
            observed_at=observed_at,
            value=close,
            unit="volatility_index_points",
            features={"open": open_value, "high": high, "low": low, "close": close},
        ))
    return observations


def default_fetch_nws_latest(station_id: str) -> dict[str, Any]:
    import httpx

    response = httpx.get(
        f"https://api.weather.gov/stations/{station_id}/observations/latest",
        headers={"User-Agent": "DummyPredictionResearch/0.1 (local-read-only)"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def parse_nws_latest(
    payload: dict[str, Any], station_id: str, city_code: str,
) -> list[ExternalObservation]:
    properties = payload.get("properties") or {}
    timestamp = properties.get("timestamp")
    temperature = (properties.get("temperature") or {}).get("value")
    if timestamp is None or temperature is None:
        return []
    try:
        celsius = float(temperature)
    except (TypeError, ValueError):
        return []
    return [ExternalObservation(
        source="nws_station",
        series_id=f"{station_id}_TEMPERATURE",
        observed_at=str(timestamp),
        published_at=str(timestamp),
        value=(celsius * 9.0 / 5.0) + 32.0,
        unit="degrees_fahrenheit",
        features={
            "city_code": city_code,
            "station_id": station_id,
            "raw_celsius": celsius,
            "text_description": properties.get("textDescription"),
        },
    )]


def _store(ledger: AutonomyLedger, observations: list[ExternalObservation]) -> dict[str, int]:
    inserted = 0
    duplicates = 0
    for observation in observations:
        created = ledger.record_external_observation(
            source=observation.source,
            series_id=observation.series_id,
            observed_at=observation.observed_at,
            published_at=observation.published_at,
            value=observation.value,
            unit=observation.unit,
            features=observation.features,
        )
        inserted += int(created)
        duplicates += int(not created)
    return {"received": len(observations), "inserted": inserted, "duplicates": duplicates}


def collect_public_statistics(
    ledger: AutonomyLedger,
    *,
    fetch_bls: Callable[[list[str], int, int], dict[str, Any]] = default_fetch_bls,
    fetch_deribit: Callable[[str, int, int], dict[str, Any]] = default_fetch_deribit_dvol,
    fetch_nws: Callable[[str], dict[str, Any]] = default_fetch_nws_latest,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Collect every independent public source, isolating source failures."""
    current = now or datetime.now(timezone.utc)
    report: dict[str, Any] = {
        "report_name": "PUBLIC_STATISTICS_INTAKE",
        "execution_authority": False,
        "created_at": current.isoformat(),
        "sources": {},
    }
    try:
        payload = fetch_bls(list(BLS_SERIES), current.year - 2, current.year)
        report["sources"]["bls"] = {"status": "OK", **_store(ledger, parse_bls(payload))}
    except Exception as exc:
        report["sources"]["bls"] = {"status": "ERROR", "error": type(exc).__name__}

    start_ms = int((current - timedelta(days=7)).timestamp() * 1000)
    end_ms = int(current.timestamp() * 1000)
    for currency in ("BTC", "ETH"):
        key = f"deribit_dvol_{currency.lower()}"
        try:
            payload = fetch_deribit(currency, start_ms, end_ms)
            report["sources"][key] = {
                "status": "OK", **_store(ledger, parse_deribit_dvol(payload, currency)),
            }
        except Exception as exc:
            report["sources"][key] = {"status": "ERROR", "error": type(exc).__name__}

    nws_observations: list[ExternalObservation] = []
    nws_errors: dict[str, str] = {}
    for city_code, station_id in NWS_STATIONS.items():
        try:
            nws_observations.extend(parse_nws_latest(
                fetch_nws(station_id), station_id, city_code,
            ))
        except Exception as exc:
            nws_errors[station_id] = type(exc).__name__
    report["sources"]["nws_station"] = {
        "status": "OK" if nws_observations else "ERROR",
        **_store(ledger, nws_observations),
        "station_errors": nws_errors,
    }
    report["ledger_summary"] = ledger.external_observation_summary()
    return report
