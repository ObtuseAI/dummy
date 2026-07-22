"""Point-in-time crypto challenger evidence across every supported horizon.

This module is deliberately outside Dummy's forecast, allocator, executor,
promotion, and risk paths.  It records what each registered crypto source said
about each listed target, then scores those frozen opinions after settlement.
It has no broker client, credentials, order model, weight writer, gate writer,
or capital authority.

The matrix is intended to answer a narrow research question: which existing
crypto ideas earn out-of-sample probability skill for each
``asset x horizon x contract-family`` scope?  An observational win here is not
permission to trade.  Promotion remains a separate, human-reviewable process.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import sqlite3
import statistics
import time
import uuid
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from autonomy.crypto_paper_twin import cohort_for_market, event_cluster
from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.quote_quality import honest_implied_yes
from autonomy.signals.crypto_indicators import CryptoDataHub
from autonomy.signals.crypto_spot import parse_crypto_ticker


MATRIX_VERSION = "crypto-horizon-evidence-matrix-v1"
SUPPORTED_HORIZONS = ("15m", "1h", "1d", "1w")
EXECUTION_AUTHORITY = False
CAPITAL_AUTHORITY = False
PRODUCTION_WEIGHT_WRITE_AUTHORITY = False
PRODUCTION_GATE_WRITE_AUTHORITY = False
PRODUCTION_RISK_WRITE_AUTHORITY = False

AUTHORITY = {
    "research_only": True,
    "public_read_only_inputs": True,
    "execution_authority": EXECUTION_AUTHORITY,
    "capital_authority": CAPITAL_AUTHORITY,
    "production_weight_write_authority": PRODUCTION_WEIGHT_WRITE_AUTHORITY,
    "production_gate_write_authority": PRODUCTION_GATE_WRITE_AUTHORITY,
    "production_risk_write_authority": PRODUCTION_RISK_WRITE_AUTHORITY,
    "counts_toward_canary": False,
    "counts_toward_scale": False,
    "auto_promotes_sources": False,
}


class PointInTimeViolation(ValueError):
    """Raised when an input was unavailable at the declared decision cutoff."""


def _utc(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise PointInTimeViolation("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _json_ready(value: Any) -> Any:
    """Convert a research payload into a deterministic JSON value."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("provenance payload contains a non-finite float")
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("provenance datetime must include a timezone")
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, Enum):
        return _json_ready(value.value)
    if is_dataclass(value):
        return _json_ready(asdict(value))
    if isinstance(value, Mapping):
        return {
            str(key): _json_ready(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, (set, frozenset)):
        normalized = [_json_ready(item) for item in value]
        return sorted(
            normalized,
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
        )
    if isinstance(value, Path):
        return str(value)
    return str(value)


def canonical_json(value: Any) -> str:
    """Canonical JSON used by the immutable provenance hashes."""
    return json.dumps(
        _json_ready(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def deterministic_provenance_hash(value: Any) -> str:
    """SHA-256 of canonical content; dictionary insertion order is irrelevant."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


_STATE_TIME_FIELDS: tuple[tuple[str, float], ...] = (
    ("coinbase_hourly_at_s", 1.0),
    ("coinbase_minute_at_s", 1.0),
    ("dvol_at_ms", 1_000.0),
)


def _state_timestamps(state: Mapping[str, Any]) -> list[tuple[str, datetime]]:
    timestamps: list[tuple[str, datetime]] = []
    for key, divisor in _STATE_TIME_FIELDS:
        value = state.get(key)
        if value is None:
            continue
        try:
            stamp = datetime.fromtimestamp(float(value) / divisor, timezone.utc)
        except (TypeError, ValueError, OSError, OverflowError) as exc:
            raise PointInTimeViolation(f"invalid source timestamp: {key}") from exc
        timestamps.append((key, stamp))
    for stream in ("minute_ohlcv", "hourly_ohlcv", "daily_ohlcv"):
        for index, row in enumerate(state.get(stream) or []):
            if not isinstance(row, Mapping) or row.get("at_s") is None:
                continue
            try:
                stamp = datetime.fromtimestamp(float(row["at_s"]), timezone.utc)
            except (TypeError, ValueError, OSError, OverflowError) as exc:
                raise PointInTimeViolation(
                    f"invalid source timestamp: {stream}[{index}].at_s"
                ) from exc
            timestamps.append((f"{stream}[{index}].at_s", stamp))
    return timestamps


def validate_point_in_time(
    market: MarketView,
    state: Mapping[str, Any],
    as_of: datetime | str,
) -> None:
    """Fail closed when a market or source observation comes from the future."""
    cutoff = _utc(as_of)
    if market.fetched_at is None:
        raise PointInTimeViolation("market snapshot is missing fetched_at")
    if _utc(market.fetched_at) > cutoff:
        raise PointInTimeViolation("market snapshot was fetched after as_of")
    if _utc(market.close_time) <= cutoff:
        raise PointInTimeViolation("market was already closed at as_of")
    for label, stamp in _state_timestamps(state):
        if stamp > cutoff:
            raise PointInTimeViolation(f"future source observation: {label}")


def state_provenance_manifest(
    asset: str,
    state: Mapping[str, Any],
    as_of: datetime | str,
) -> dict[str, Any]:
    """Compact manifest for a hub state without copying raw payloads to reports."""
    cutoff = _utc(as_of)
    parsed_times = _state_timestamps(state)
    for label, stamp in parsed_times:
        if stamp > cutoff:
            raise PointInTimeViolation(f"future source observation: {label}")
    source_times = {label: stamp.isoformat() for label, stamp in parsed_times}
    missing_timestamps: list[str] = []
    if state.get("book_imbalance") is not None:
        missing_timestamps.append("coinbase_level1_book")
    if state.get("kraken_spot") is not None:
        missing_timestamps.append("kraken_last_spot")
    return {
        "asset": str(asset),
        "as_of": cutoff.isoformat(),
        "received_at": cutoff.isoformat(),
        "state_hash": deterministic_provenance_hash(state),
        "source_observation_times": source_times,
        "source_timestamp_gaps": missing_timestamps,
        "hourly_source": state.get("hourly_source"),
        "row_counts": {
            key: len(state.get(key) or [])
            for key in ("minute_ohlcv", "hourly_ohlcv", "daily_ohlcv")
        },
        "endpoints": (
            "coinbase_exchange_candles",
            "coinbase_exchange_level1_book",
            "kraken_public_ohlc_ticker",
            "deribit_public_dvol",
        ),
    }


SOURCE_ENDPOINTS: dict[str, tuple[str, ...]] = {
    "market_prior": ("kalshi_public_market_snapshot",),
    "cross_venue_polymarket_crypto": (
        "polymarket_public_gamma",
        "polymarket_public_clob",
    ),
    "crypto_macro_regime": ("yahoo_public_chart_macro",),
    "crypto_equities_flow": ("yahoo_public_chart_crypto_equities",),
}


def build_registered_crypto_sources(
    hub: CryptoDataHub | None = None,
    *,
    include_cross_venue: bool = True,
    include_reliability_wrappers: bool = True,
    public_request_timeout_seconds: float | None = None,
) -> list[Any]:
    """Build the crypto source roster without constructing a production brain.

    The roster mirrors the crypto registrations in ``autonomy.session`` but
    supplies no production ledger to cross-venue diagnostics.  Every source is
    observed independently; this function never creates an ensemble.
    """
    from autonomy.reliability import (
        CALIBRATED_SOURCES,
        CalibratedSignal,
        ReliabilityMaps,
    )
    from autonomy.signals.crypto_adaptive import (
        CryptoKamaMomentumSignal,
        CryptoPatienceSignal,
    )
    from autonomy.signals.crypto_chartist import CryptoChartistSignal
    from autonomy.signals.crypto_equities import CryptoEquitiesSignal
    from autonomy.signals.crypto_flows import CryptoBtcLeadlagSignal
    from autonomy.signals.crypto_indicators import (
        CryptoDvolSignal,
        CryptoEmpiricalRegimeSignal,
        CryptoTechnicalCompositeSignal,
    )
    from autonomy.signals.crypto_macro import CryptoMacroRegimeSignal
    from autonomy.signals.crypto_structure import CryptoStructureSignal
    from autonomy.signals.crypto_ta_foundry import CryptoTechnicalFoundrySignal
    from autonomy.signals.crypto_vol import (
        CryptoBlendSigmaSignal,
        CryptoVrpRegimeSignal,
    )
    from autonomy.signals.crypto_spot import (
        CryptoEwmaTailSignal,
        CryptoSpotVolSignal,
    )
    from autonomy.signals.market_debias import MarketDebiasSignal
    from autonomy.signals.market_prior import MarketPriorSignal

    shared = hub or CryptoDataHub()
    macro_fetch = None
    equities_fetch = None
    cross_venue_markets = None
    cross_venue_books = None
    if public_request_timeout_seconds is not None:
        request_timeout = max(0.1, float(public_request_timeout_seconds))
        from autonomy.signals.crypto_equities import default_fetch_equity_state
        from autonomy.signals.crypto_macro import default_fetch_macro_state
        from autonomy.signals.cross_venue import (
            default_fetch_polymarket_markets,
            default_fetch_polymarket_orderbooks,
        )

        macro_fetch = partial(
            default_fetch_macro_state, timeout_seconds=request_timeout
        )
        equities_fetch = partial(
            default_fetch_equity_state, timeout_seconds=request_timeout
        )
        cross_venue_markets = partial(
            default_fetch_polymarket_markets, timeout_seconds=request_timeout
        )
        cross_venue_books = partial(
            default_fetch_polymarket_orderbooks,
            timeout_seconds=request_timeout,
        )
    flat = CryptoSpotVolSignal(fetch_spot_and_vol=shared.flat_spot_and_vol)
    ewma = CryptoEwmaTailSignal(fetch_spot_and_vol=shared.ewma_spot_and_vol)
    sources: list[Any] = [
        MarketPriorSignal(),
        flat,
        ewma,
        CryptoEmpiricalRegimeSignal(fetch_state=shared.state),
        CryptoTechnicalCompositeSignal(fetch_state=shared.state),
        CryptoTechnicalFoundrySignal(fetch_state=shared.state),
        CryptoDvolSignal(fetch_state=shared.state),
        CryptoStructureSignal(fetch_state=shared.state),
        CryptoMacroRegimeSignal(
            fetch_state=shared.state,
            fetch_macro=macro_fetch,
        ),
        CryptoEquitiesSignal(
            fetch_state=shared.state,
            fetch_equities=equities_fetch,
        ),
        CryptoBlendSigmaSignal(fetch_state=shared.state),
        CryptoVrpRegimeSignal(fetch_state=shared.state),
        CryptoBtcLeadlagSignal(fetch_state=shared.state),
        CryptoPatienceSignal(fetch_state=shared.state),
        CryptoKamaMomentumSignal(fetch_state=shared.state),
        CryptoChartistSignal(fetch_state=shared.state),
    ]
    if include_cross_venue:
        from autonomy.signals.cross_venue_macro import CrossVenueCryptoSignal

        # No ledger is supplied: the source may read public comparison data but
        # cannot write the production observation store.
        sources.append(
            CrossVenueCryptoSignal(
                fetch_markets=cross_venue_markets,
                fetch_orderbooks=cross_venue_books,
                ledger=None,
            )
        )
    sources.append(MarketDebiasSignal())
    if include_reliability_wrappers:
        maps = ReliabilityMaps()
        sources.extend(
            CalibratedSignal(parent, maps=maps, sources=CALIBRATED_SOURCES)
            for parent in (flat, ewma)
        )
    return sources


_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS matrix_cycles(
    cycle_id TEXT PRIMARY KEY,
    matrix_version TEXT NOT NULL,
    started_at TEXT NOT NULL,
    as_of_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    markets_seen INTEGER NOT NULL DEFAULT 0,
    attempts_written INTEGER NOT NULL DEFAULT 0,
    errors_json TEXT NOT NULL DEFAULT '[]',
    workload_json TEXT NOT NULL DEFAULT '{}',
    authority_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS crypto_state_snapshots(
    snapshot_id TEXT PRIMARY KEY,
    cycle_id TEXT NOT NULL,
    asset TEXT NOT NULL,
    as_of_at TEXT NOT NULL,
    state_hash TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    FOREIGN KEY(cycle_id) REFERENCES matrix_cycles(cycle_id),
    UNIQUE(cycle_id, asset)
);
CREATE TABLE IF NOT EXISTS horizon_forecast_attempts(
    forecast_id TEXT PRIMARY KEY,
    cycle_id TEXT NOT NULL,
    matrix_version TEXT NOT NULL,
    source TEXT NOT NULL,
    emitted_source TEXT,
    asset TEXT NOT NULL,
    horizon TEXT NOT NULL,
    contract_family TEXT NOT NULL,
    event_cluster TEXT NOT NULL,
    ticker TEXT NOT NULL,
    close_time TEXT NOT NULL,
    status TEXT NOT NULL,
    error_type TEXT,
    probability_yes REAL,
    uncertainty REAL,
    market_probability REAL,
    source_created_at TEXT,
    as_of_at TEXT NOT NULL,
    state_hash TEXT,
    features_json TEXT NOT NULL,
    provenance_json TEXT NOT NULL,
    provenance_hash TEXT NOT NULL,
    result_yes INTEGER,
    settled_at TEXT,
    brier REAL,
    log_loss REAL,
    market_brier REAL,
    market_log_loss REAL,
    FOREIGN KEY(cycle_id) REFERENCES matrix_cycles(cycle_id),
    UNIQUE(cycle_id, source, ticker)
);
CREATE INDEX IF NOT EXISTS horizon_matrix_unsettled
ON horizon_forecast_attempts(status, result_yes, close_time);
CREATE INDEX IF NOT EXISTS horizon_matrix_unsettled_ticker
ON horizon_forecast_attempts(status, result_yes, ticker, close_time);
CREATE INDEX IF NOT EXISTS horizon_matrix_scope
ON horizon_forecast_attempts(source, asset, horizon, contract_family, settled_at);
CREATE TABLE IF NOT EXISTS evidence_work_state(
    work_name TEXT PRIMARY KEY,
    cursor TEXT,
    updated_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
"""


def fair_batch(
    values: Sequence[Any],
    *,
    cursor: str | None,
    limit: int,
    key: Callable[[Any], str] = str,
) -> dict[str, Any]:
    """Return a deterministic cursor-resumable batch without dropping work.

    The cursor is the last *attempted* key, not an offset.  Key cursors survive
    insertions and deletions between public-market scans.  Once the ordered tail
    is exhausted the batch wraps to the beginning, so a permanently unresolved
    ticker cannot starve later work.
    """
    bounded = max(0, int(limit))
    unique: dict[str, Any] = {}
    for value in values:
        unique.setdefault(str(key(value)), value)
    ordered_keys = sorted(unique)
    total = len(ordered_keys)
    if total == 0 or bounded == 0:
        return {
            "items": [],
            "keys": [],
            "total": total,
            "deferred": total,
            "cursor_before": cursor,
            "cursor_after": cursor,
            "wrapped": False,
        }
    start = bisect_right(ordered_keys, str(cursor)) if cursor is not None else 0
    rotated_keys = ordered_keys[start:] + ordered_keys[:start]
    selected_keys = rotated_keys[: min(bounded, total)]
    return {
        "items": [unique[item_key] for item_key in selected_keys],
        "keys": selected_keys,
        "total": total,
        "deferred": max(0, total - len(selected_keys)),
        "cursor_before": cursor,
        "cursor_after": selected_keys[-1] if selected_keys else cursor,
        "wrapped": bool(selected_keys and start + len(selected_keys) > total),
    }


class CryptoHorizonEvidenceStore:
    """Separate research database; never opens Dummy's production ledger."""

    def __init__(
        self,
        path: Path | str = Path("runtime/autonomy/crypto_horizon_evidence.db"),
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        cycle_columns = {
            str(row["name"])
            for row in self.conn.execute("PRAGMA table_info(matrix_cycles)")
        }
        if "workload_json" not in cycle_columns:
            self.conn.execute(
                "ALTER TABLE matrix_cycles ADD COLUMN workload_json "
                "TEXT NOT NULL DEFAULT '{}'"
            )
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def start_cycle(
        self, cycle_id: str, started_at: str, as_of_at: str,
    ) -> None:
        self.conn.execute(
            "INSERT INTO matrix_cycles(cycle_id,matrix_version,started_at,as_of_at,"
            "status,authority_json) VALUES (?,?,?,?,?,?)",
            (
                cycle_id,
                MATRIX_VERSION,
                started_at,
                as_of_at,
                "RUNNING",
                canonical_json(AUTHORITY),
            ),
        )
        self.conn.commit()

    def record_snapshot(
        self, cycle_id: str, asset: str, as_of_at: str, manifest: Mapping[str, Any],
    ) -> bool:
        state_hash = str(manifest["state_hash"])
        snapshot_id = deterministic_provenance_hash(
            {"cycle_id": cycle_id, "asset": asset, "state_hash": state_hash}
        )
        cursor = self.conn.execute(
            "INSERT OR IGNORE INTO crypto_state_snapshots(snapshot_id,cycle_id,asset,"
            "as_of_at,state_hash,manifest_json) VALUES (?,?,?,?,?,?)",
            (
                snapshot_id,
                cycle_id,
                asset,
                as_of_at,
                state_hash,
                canonical_json(manifest),
            ),
        )
        return cursor.rowcount > 0

    def record_attempt(self, row: Mapping[str, Any]) -> bool:
        forecast_id = deterministic_provenance_hash(
            {
                "matrix_version": MATRIX_VERSION,
                "cycle_id": row["cycle_id"],
                "source": row["source"],
                "ticker": row["ticker"],
            }
        )
        cursor = self.conn.execute(
            "INSERT OR IGNORE INTO horizon_forecast_attempts("
            "forecast_id,cycle_id,matrix_version,source,emitted_source,asset,horizon,"
            "contract_family,event_cluster,ticker,close_time,status,error_type,"
            "probability_yes,uncertainty,market_probability,source_created_at,as_of_at,"
            "state_hash,features_json,provenance_json,provenance_hash) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                forecast_id,
                row["cycle_id"],
                MATRIX_VERSION,
                row["source"],
                row.get("emitted_source"),
                row["asset"],
                row["horizon"],
                row["contract_family"],
                row["event_cluster"],
                row["ticker"],
                row["close_time"],
                row["status"],
                row.get("error_type"),
                row.get("probability_yes"),
                row.get("uncertainty"),
                row.get("market_probability"),
                row.get("source_created_at"),
                row["as_of_at"],
                row.get("state_hash"),
                canonical_json(row.get("features") or {}),
                canonical_json(row["provenance"]),
                row["provenance_hash"],
            ),
        )
        return cursor.rowcount > 0

    def finish_cycle(
        self,
        cycle_id: str,
        *,
        completed_at: str,
        status: str,
        markets_seen: int,
        attempts_written: int,
        errors: Sequence[str],
        workload: Mapping[str, Any] | None = None,
    ) -> None:
        self.conn.execute(
            "UPDATE matrix_cycles SET completed_at=?,status=?,markets_seen=?,"
            "attempts_written=?,errors_json=?,workload_json=? WHERE cycle_id=?",
            (
                completed_at,
                status,
                int(markets_seen),
                int(attempts_written),
                canonical_json(list(errors)),
                canonical_json(dict(workload or {})),
                cycle_id,
            ),
        )
        self.conn.commit()

    def work_state(self, work_name: str) -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT work_name,cursor,updated_at,metadata_json "
            "FROM evidence_work_state WHERE work_name=?",
            (str(work_name),),
        ).fetchone()
        if row is None:
            return {
                "work_name": str(work_name),
                "cursor": None,
                "updated_at": None,
                "metadata": {},
            }
        try:
            metadata = json.loads(str(row["metadata_json"] or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            metadata = {"state_error": "INVALID_METADATA_JSON"}
        return {
            "work_name": str(row["work_name"]),
            "cursor": row["cursor"],
            "updated_at": row["updated_at"],
            "metadata": metadata if isinstance(metadata, dict) else {},
        }

    def set_work_cursor(
        self,
        work_name: str,
        cursor: str | None,
        *,
        updated_at: datetime | str,
        metadata: Mapping[str, Any] | None = None,
        commit: bool = True,
    ) -> None:
        stamp = _utc(updated_at).isoformat()
        self.conn.execute(
            "INSERT INTO evidence_work_state(work_name,cursor,updated_at,metadata_json) "
            "VALUES (?,?,?,?) ON CONFLICT(work_name) DO UPDATE SET "
            "cursor=excluded.cursor,updated_at=excluded.updated_at,"
            "metadata_json=excluded.metadata_json",
            (
                str(work_name),
                None if cursor is None else str(cursor),
                stamp,
                canonical_json(dict(metadata or {})),
            ),
        )
        if commit:
            self.conn.commit()

    def fair_work_batch(
        self,
        work_name: str,
        values: Sequence[Any],
        *,
        limit: int,
        key: Callable[[Any], str] = str,
    ) -> dict[str, Any]:
        state = self.work_state(work_name)
        return fair_batch(values, cursor=state.get("cursor"), limit=limit, key=key)

    def unsettled_tickers(self, as_of: datetime | str) -> list[str]:
        cutoff = _utc(as_of).isoformat()
        rows = self.conn.execute(
            "SELECT DISTINCT ticker FROM horizon_forecast_attempts "
            "WHERE status='EMITTED' AND result_yes IS NULL AND close_time<=? "
            "ORDER BY ticker",
            (cutoff,),
        ).fetchall()
        return [str(row[0]) for row in rows]

    def unsettled_ticker_batch(
        self,
        as_of: datetime | str,
        *,
        limit: int,
        work_name: str = "settlement_reconciliation",
    ) -> dict[str, Any]:
        """Select one persistent, fair reconciliation sweep segment.

        The database query is covering and bounded.  Only the selected ticker
        strings cross the SQLite boundary; forecast rows are not loaded merely
        to decide which public results to inspect.
        """
        cutoff = _utc(as_of).isoformat()
        bounded = max(0, int(limit))
        state = self.work_state(work_name)
        cursor = state.get("cursor")
        total = int(
            self.conn.execute(
                "SELECT COUNT(DISTINCT ticker) FROM horizon_forecast_attempts "
                "WHERE status='EMITTED' AND result_yes IS NULL AND close_time<=?",
                (cutoff,),
            ).fetchone()[0]
            or 0
        )
        if total == 0 or bounded == 0:
            return {
                "items": [],
                "keys": [],
                "total": total,
                "deferred": total,
                "cursor_before": cursor,
                "cursor_after": cursor,
                "wrapped": False,
            }

        parameters: list[Any] = [cutoff]
        cursor_clause = ""
        if cursor is not None:
            cursor_clause = " AND ticker>?"
            parameters.append(str(cursor))
        parameters.append(bounded)
        rows = self.conn.execute(
            "SELECT ticker FROM horizon_forecast_attempts "
            "WHERE status='EMITTED' AND result_yes IS NULL AND close_time<=?"
            f"{cursor_clause} GROUP BY ticker ORDER BY ticker LIMIT ?",
            tuple(parameters),
        ).fetchall()
        keys = [str(row[0]) for row in rows]
        wrapped = False
        if len(keys) < min(bounded, total) and cursor is not None:
            remaining = min(bounded, total) - len(keys)
            wrapped_rows = self.conn.execute(
                "SELECT ticker FROM horizon_forecast_attempts "
                "WHERE status='EMITTED' AND result_yes IS NULL AND close_time<=? "
                "AND ticker<=? GROUP BY ticker ORDER BY ticker LIMIT ?",
                (cutoff, str(cursor), remaining),
            ).fetchall()
            keys.extend(str(row[0]) for row in wrapped_rows)
            wrapped = bool(wrapped_rows)
        return {
            "items": keys,
            "keys": keys,
            "total": total,
            "deferred": max(0, total - len(keys)),
            "cursor_before": cursor,
            "cursor_after": keys[-1] if keys else cursor,
            "wrapped": wrapped,
        }

    def unsettled_ticker_count(self, as_of: datetime | str) -> int:
        cutoff = _utc(as_of).isoformat()
        return int(
            self.conn.execute(
                "SELECT COUNT(DISTINCT ticker) FROM horizon_forecast_attempts "
                "WHERE status='EMITTED' AND result_yes IS NULL AND close_time<=?",
                (cutoff,),
            ).fetchone()[0]
            or 0
        )

    def settle_ticker(
        self,
        ticker: str,
        result_yes: bool,
        settled_at: datetime | str,
    ) -> int:
        settled = _utc(settled_at)
        rows = self.conn.execute(
            "SELECT forecast_id,probability_yes,market_probability,as_of_at,close_time "
            "FROM horizon_forecast_attempts WHERE ticker=? AND status='EMITTED' "
            "AND result_yes IS NULL",
            (ticker,),
        ).fetchall()
        updated = 0
        outcome = 1.0 if bool(result_yes) else 0.0
        for row in rows:
            if settled < _utc(str(row["close_time"])):
                raise PointInTimeViolation("settlement predates market close")
            if settled < _utc(str(row["as_of_at"])):
                raise PointInTimeViolation("settlement predates forecast")
            probability = min(1.0 - 1e-12, max(1e-12, float(row["probability_yes"])))
            brier = (probability - outcome) ** 2
            log_loss = -(outcome * math.log(probability) + (1.0 - outcome) * math.log(1.0 - probability))
            market_probability = row["market_probability"]
            market_brier = market_log_loss = None
            if market_probability is not None:
                market = min(1.0 - 1e-12, max(1e-12, float(market_probability)))
                market_brier = (market - outcome) ** 2
                market_log_loss = -(
                    outcome * math.log(market)
                    + (1.0 - outcome) * math.log(1.0 - market)
                )
            cursor = self.conn.execute(
                "UPDATE horizon_forecast_attempts SET result_yes=?,settled_at=?,"
                "brier=?,log_loss=?,market_brier=?,market_log_loss=? "
                "WHERE forecast_id=? AND result_yes IS NULL",
                (
                    int(bool(result_yes)),
                    settled.isoformat(),
                    round(brier, 12),
                    round(log_loss, 12),
                    None if market_brier is None else round(market_brier, 12),
                    None if market_log_loss is None else round(market_log_loss, 12),
                    str(row["forecast_id"]),
                ),
            )
            updated += int(cursor.rowcount > 0)
        self.conn.commit()
        return updated

    def attempts(self, *, cycle_id: str | None = None) -> list[dict[str, Any]]:
        if cycle_id is None:
            rows = self.conn.execute(
                "SELECT * FROM horizon_forecast_attempts ORDER BY as_of_at,source,ticker"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM horizon_forecast_attempts WHERE cycle_id=? "
                "ORDER BY source,ticker",
                (cycle_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def cycle(self, cycle_id: str) -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT * FROM matrix_cycles WHERE cycle_id=?", (cycle_id,)
        ).fetchone()
        return dict(row) if row is not None else {}

    def settled_row_count(self) -> int:
        return int(
            self.conn.execute(
                "SELECT COUNT(*) FROM horizon_forecast_attempts "
                "WHERE status='EMITTED' AND result_yes IS NOT NULL"
            ).fetchone()[0]
            or 0
        )

    def settled_rows(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        if limit is None:
            rows = self.conn.execute(
                "SELECT * FROM horizon_forecast_attempts WHERE status='EMITTED' "
                "AND result_yes IS NOT NULL ORDER BY as_of_at,forecast_id"
            ).fetchall()
        else:
            bounded = max(0, int(limit))
            rows = self.conn.execute(
                "SELECT * FROM (SELECT * FROM horizon_forecast_attempts "
                "WHERE status='EMITTED' AND result_yes IS NOT NULL "
                "ORDER BY settled_at DESC,forecast_id DESC LIMIT ?) "
                "ORDER BY as_of_at,forecast_id",
                (bounded,),
            ).fetchall()
        return [dict(row) for row in rows]


def _percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * min(1.0, max(0.0, fraction))
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _cluster_bootstrap_advantage(
    rows: Sequence[Mapping[str, Any]],
    *,
    resamples: int = 500,
) -> dict[str, Any] | None:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row.get("market_brier") is None or row.get("brier") is None:
            continue
        grouped[str(row["event_cluster"])].append(
            float(row["market_brier"]) - float(row["brier"])
        )
    cluster_values = [statistics.fmean(values) for values in grouped.values()]
    if not cluster_values:
        return None
    observed = statistics.fmean(cluster_values)
    if len(cluster_values) == 1:
        lower = upper = observed
    else:
        seed = int(
            deterministic_provenance_hash(
                {"clusters": sorted(grouped), "values": cluster_values}
            )[:16],
            16,
        )
        rng = random.Random(seed)
        samples = [
            statistics.fmean(rng.choice(cluster_values) for _ in cluster_values)
            for _ in range(max(100, int(resamples)))
        ]
        lower = float(_percentile(samples, 0.025) or 0.0)
        upper = float(_percentile(samples, 0.975) or 0.0)
    return {
        "mean": round(observed, 10),
        "lower": round(lower, 10),
        "upper": round(upper, 10),
        "event_clusters": len(cluster_values),
        "resamples": max(100, int(resamples)),
        "method": "event_cluster_bootstrap_brier_advantage",
    }


def _calibration_error(
    rows: Sequence[Mapping[str, Any]], bins: int = 10,
) -> tuple[float | None, float | None]:
    buckets: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for row in rows:
        if row.get("probability_yes") is None or row.get("result_yes") is None:
            continue
        probability = float(row["probability_yes"])
        index = min(max(0, int(probability * bins)), bins - 1)
        buckets[index].append((probability, float(row["result_yes"])))
    total = sum(len(values) for values in buckets.values())
    if total == 0:
        return None, None
    gaps = [
        (
            len(values),
            abs(
                statistics.fmean(item[0] for item in values)
                - statistics.fmean(item[1] for item in values)
            ),
        )
        for values in buckets.values()
    ]
    ece = sum(count / total * gap for count, gap in gaps)
    mce = max(gap for _count, gap in gaps)
    return round(ece, 10), round(mce, 10)


def _fit_market_blend(rows: Sequence[Mapping[str, Any]]) -> float:
    usable = [
        row for row in rows
        if row.get("probability_yes") is not None
        and row.get("market_probability") is not None
        and row.get("result_yes") is not None
    ]
    if not usable:
        return 0.0
    candidates = [index / 100.0 for index in range(0, 101, 5)]
    return min(
        candidates,
        key=lambda share: statistics.fmean(
            (
                float(row["market_probability"])
                + share * (
                    float(row["probability_yes"])
                    - float(row["market_probability"])
                )
                - float(row["result_yes"])
            ) ** 2
            for row in usable
        ),
    )


def _timestamp_valid_settled_rows(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[tuple[dict[str, Any], datetime, datetime]], Counter[str]]:
    """Return causally timestamped rows and fail-closed exclusion counts.

    A scored forecast is not usable by a temporal calibration merely because
    its outcome is present in the database.  The forecast decision and the
    outcome's settlement both need timezone-aware timestamps, and the outcome
    must become known strictly after the decision.  Callers then apply the
    second, test-specific rule: a training settlement must be strictly earlier
    than the test forecast's decision timestamp.
    """
    valid: list[tuple[dict[str, Any], datetime, datetime]] = []
    exclusions: Counter[str] = Counter()
    for raw in rows:
        row = dict(raw)
        decision_raw = row.get("as_of_at")
        settlement_raw = row.get("settled_at")
        if decision_raw in (None, ""):
            exclusions["missing_decision_timestamp"] += 1
            continue
        if settlement_raw in (None, ""):
            exclusions["missing_settlement_timestamp"] += 1
            continue
        try:
            decision_at = _utc(decision_raw)
        except (PointInTimeViolation, TypeError, ValueError, OverflowError):
            exclusions["invalid_decision_timestamp"] += 1
            continue
        try:
            settled_at = _utc(settlement_raw)
        except (PointInTimeViolation, TypeError, ValueError, OverflowError):
            exclusions["invalid_settlement_timestamp"] += 1
            continue
        if settled_at <= decision_at:
            exclusions["settlement_not_strictly_after_forecast"] += 1
            continue
        valid.append((row, decision_at, settled_at))
    valid.sort(
        key=lambda item: (
            item[1],
            str(item[0].get("forecast_id") or ""),
        )
    )
    return valid, exclusions


def expanding_window_calibration(
    rows: Sequence[Mapping[str, Any]],
    *,
    min_train: int = 20,
    min_forward: int = 20,
) -> dict[str, Any]:
    """Research-only blend using only outcomes known before each decision.

    Forecast order is insufficient when contracts overlap: an earlier forecast
    may settle after several later decisions.  For every test forecast this
    function therefore rebuilds the training window from rows whose own
    decisions *and* settlements are strictly before that test decision.  Rows
    with unknown, malformed, or non-causal timestamps are quarantined from all
    fitting and forward evidence.
    """
    candidates = [
        row for row in rows
        if row.get("probability_yes") is not None
        and row.get("market_probability") is not None
        and row.get("result_yes") is not None
    ]
    settled, timestamp_exclusions = _timestamp_valid_settled_rows(candidates)
    required_train = max(1, int(min_train))
    forward: list[dict[str, Any]] = []
    training_sizes: list[int] = []
    skipped_below_min_train = 0
    withheld_unsettled_at_decision = 0
    for test, test_decision_at, _test_settled_at in settled:
        training = [
            train
            for train, train_decision_at, train_settled_at in settled
            if train_decision_at < test_decision_at
            and train_settled_at < test_decision_at
        ]
        withheld_unsettled_at_decision += sum(
            1
            for _train, train_decision_at, train_settled_at in settled
            if train_decision_at < test_decision_at
            and train_settled_at >= test_decision_at
        )
        if len(training) < required_train:
            skipped_below_min_train += 1
            continue
        training_sizes.append(len(training))
        share = _fit_market_blend(training)
        market = float(test["market_probability"])
        model = float(test["probability_yes"])
        calibrated = min(0.995, max(0.005, market + share * (model - market)))
        outcome = float(test["result_yes"])
        forward.append(
            {
                **test,
                "probability_yes": calibrated,
                "brier": (calibrated - outcome) ** 2,
                "market_brier": (market - outcome) ** 2,
            }
        )
    interval = _cluster_bootstrap_advantage(forward)
    enough = len(forward) >= max(1, int(min_forward))
    lower = None if interval is None else interval.get("lower")
    observational_positive = bool(
        enough and lower is not None and float(lower) > 0.0
    )
    valid_rows = [row for row, _decision_at, _settled_at in settled]
    return {
        "method": "strict_expanding_window_market_model_blend",
        "settled_rows_seen": len(candidates),
        "settled_forecasts": len(valid_rows),
        "forward_forecasts": len(forward),
        "fitted_model_share": round(_fit_market_blend(valid_rows), 6),
        "fitted_model_share_basis": (
            "all_timestamp_valid_settled_rows_current_research_view"
        ),
        "forward_brier_advantage_ci95": interval,
        "point_in_time_training": {
            "decision_timestamp_field": "as_of_at",
            "settlement_timestamp_field": "settled_at",
            "release_rule": "settled_at_strictly_before_test_as_of_at",
            "same_decision_batch_can_train_each_other": False,
            "timestamp_valid_rows": len(valid_rows),
            "timestamp_excluded_rows": sum(timestamp_exclusions.values()),
            "timestamp_exclusion_reasons": dict(sorted(timestamp_exclusions.items())),
            "tests_skipped_below_min_train": skipped_below_min_train,
            "training_rows_min": min(training_sizes) if training_sizes else 0,
            "training_rows_max": max(training_sizes) if training_sizes else 0,
            "earlier_forecast_rows_with_outcomes_unreleased_at_test_decision": (
                withheld_unsettled_at_decision
            ),
        },
        "research_status": (
            "OBSERVATIONAL_POSITIVE"
            if observational_positive
            else "MARKET_ANCHORED_HOLD" if enough
            else "COLLECTING_FORWARD_EVIDENCE"
        ),
        "execution_authority": False,
        "auto_apply": False,
    }


def evidence_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[
            (
                str(row["source"]),
                str(row["asset"]),
                str(row["horizon"]),
                str(row["contract_family"]),
            )
        ].append(row)
    scopes: dict[str, Any] = {}
    for (source, asset, horizon, contract_family), scope_rows in sorted(grouped.items()):
        briers = [float(row["brier"]) for row in scope_rows if row.get("brier") is not None]
        losses = [float(row["log_loss"]) for row in scope_rows if row.get("log_loss") is not None]
        market_briers = [
            float(row["market_brier"])
            for row in scope_rows if row.get("market_brier") is not None
        ]
        ece, mce = _calibration_error(scope_rows)
        key = f"{source}:{asset}:{horizon}:{contract_family}"
        scopes[key] = {
            "source": source,
            "asset": asset,
            "horizon": horizon,
            "contract_family": contract_family,
            "settled_forecasts": len(scope_rows),
            "event_clusters": len({str(row["event_cluster"]) for row in scope_rows}),
            "brier": round(statistics.fmean(briers), 10) if briers else None,
            "log_loss": round(statistics.fmean(losses), 10) if losses else None,
            "market_brier": (
                round(statistics.fmean(market_briers), 10) if market_briers else None
            ),
            "brier_skill_vs_market": (
                round(
                    1.0 - statistics.fmean(briers) / statistics.fmean(market_briers),
                    10,
                )
                if briers and market_briers and statistics.fmean(market_briers) > 0
                else None
            ),
            "ece_10": ece,
            "mce_10": mce,
            "brier_advantage_ci95": _cluster_bootstrap_advantage(scope_rows),
            "expanding_window_calibration": expanding_window_calibration(scope_rows),
            "execution_authority": False,
        }
    return {
        "settled_forecasts": len(rows),
        "scopes": scopes,
        "execution_authority": False,
    }


class CryptoHorizonEvidenceMatrix:
    """Runs source-by-target observation cycles without producing decisions."""

    def __init__(
        self,
        *,
        store: CryptoHorizonEvidenceStore | None = None,
        hub: CryptoDataHub | None = None,
        sources: Sequence[Any] | None = None,
        now_fn: Callable[[], datetime] | None = None,
        monotonic_fn: Callable[[], float] | None = None,
    ) -> None:
        self.store = store or CryptoHorizonEvidenceStore()
        self.hub = hub or CryptoDataHub()
        self.sources = list(sources or build_registered_crypto_sources(self.hub))
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self.monotonic_fn = monotonic_fn or time.monotonic

    def close(self) -> None:
        self.store.close()

    @staticmethod
    def _valid_signal(signal: Signal, market: MarketView) -> None:
        if signal.market_ticker != market.ticker:
            raise ValueError("signal ticker does not match target")
        probability = float(signal.probability_yes)
        uncertainty = float(signal.uncertainty)
        if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
            raise ValueError("invalid signal probability")
        if not math.isfinite(uncertainty) or not 0.0 <= uncertainty <= 0.5:
            raise ValueError("invalid signal uncertainty")

    def run_cycle(
        self,
        markets: Sequence[MarketView],
        *,
        states: Mapping[str, Mapping[str, Any]] | None = None,
        as_of: datetime | str | None = None,
        workload: Mapping[str, Any] | None = None,
        report_max_settled_rows: int | None = None,
    ) -> dict[str, Any]:
        started = self.now_fn().astimezone(timezone.utc)
        selected: list[tuple[MarketView, str, str, str, str]] = []
        for market in markets:
            if market.vertical is not Vertical.CRYPTO:
                continue
            parsed = parse_crypto_ticker(market.ticker)
            cohort = cohort_for_market(market)
            if parsed is None or cohort is None or cohort.timeframe not in SUPPORTED_HORIZONS:
                continue
            asset = str(parsed["asset"])
            contract_family = str(parsed.get("contract_family") or "terminal_price")
            cluster = event_cluster(
                Vertical.CRYPTO, cohort.timeframe, asset, market.close_time
            )
            selected.append(
                (market, asset, cohort.timeframe, contract_family, cluster)
            )

        hook_errors: dict[str, str] = {}
        if selected:
            for source in self.sources:
                hook = getattr(source, "on_cycle_start", None)
                if not callable(hook):
                    continue
                try:
                    hook()
                except Exception as exc:
                    hook_errors[
                        str(getattr(source, "name", type(source).__name__))
                    ] = type(exc).__name__

        state_by_asset: dict[str, Mapping[str, Any]] = {}
        state_errors: dict[str, str] = {}
        supplied = dict(states or {})
        for asset in sorted({item[1] for item in selected}):
            try:
                state_by_asset[asset] = supplied.get(asset) or self.hub.state(asset)
            except Exception as exc:
                state_errors[asset] = type(exc).__name__

        generated: dict[tuple[str, str], tuple[str, Signal | None, str | None]] = {}
        for market, asset, _horizon, _family, _cluster in selected:
            for source in self.sources:
                source_name = str(getattr(source, "name", type(source).__name__))
                key = (market.ticker, source_name)
                if source_name in hook_errors:
                    generated[key] = ("SOURCE_HOOK_ERROR", None, hook_errors[source_name])
                    continue
                if asset in state_errors:
                    generated[key] = ("SOURCE_STATE_ERROR", None, state_errors[asset])
                    continue
                try:
                    if not bool(source.applicable(market)):
                        generated[key] = ("NOT_APPLICABLE", None, None)
                        continue
                    signal = source.generate(market)
                    if signal is None:
                        generated[key] = ("ABSTAINED", None, None)
                        continue
                    self._valid_signal(signal, market)
                    generated[key] = ("EMITTED", signal, None)
                except Exception as exc:
                    generated[key] = ("SOURCE_ERROR", None, type(exc).__name__)

        cutoff = _utc(as_of) if as_of is not None else self.now_fn().astimezone(timezone.utc)
        cycle_id = (
            f"crypto-matrix-{cutoff.strftime('%Y%m%dT%H%M%S')}-"
            f"{uuid.uuid4().hex[:8]}"
        )
        self.store.start_cycle(cycle_id, started.isoformat(), cutoff.isoformat())
        errors: list[str] = []
        state_manifests: dict[str, dict[str, Any]] = {}
        for asset, state in state_by_asset.items():
            try:
                manifest = state_provenance_manifest(asset, state, cutoff)
                state_manifests[asset] = manifest
                self.store.record_snapshot(cycle_id, asset, cutoff.isoformat(), manifest)
            except Exception as exc:
                state_errors[asset] = type(exc).__name__
                errors.append(f"state:{asset}:{type(exc).__name__}:{str(exc)[:120]}")

        attempts_written = 0
        status_counts: Counter[str] = Counter()
        for market, asset, horizon, contract_family, cluster in selected:
            state = state_by_asset.get(asset) or {}
            market_probability = honest_implied_yes(market.yes_bid, market.yes_ask)
            market_snapshot = {
                "ticker": market.ticker,
                "title": market.title,
                "status": market.status,
                "close_time": market.close_time,
                "yes_bid": market.yes_bid,
                "yes_ask": market.yes_ask,
                "no_bid": market.no_bid,
                "no_ask": market.no_ask,
                "volume": market.volume,
                "liquidity": market.liquidity,
                "fetched_at": market.fetched_at,
                "raw": market.raw,
            }
            pit_error: str | None = None
            try:
                if asset in state_errors:
                    raise PointInTimeViolation(
                        f"state unavailable or invalid: {state_errors[asset]}"
                    )
                validate_point_in_time(market, state, cutoff)
            except Exception as exc:
                pit_error = type(exc).__name__
                errors.append(
                    f"pit:{market.ticker}:{type(exc).__name__}:{str(exc)[:120]}"
                )
            for source in self.sources:
                source_name = str(getattr(source, "name", type(source).__name__))
                source_status, signal, source_error = generated[(market.ticker, source_name)]
                if pit_error is not None:
                    source_status, signal, source_error = "PIT_REJECTED", None, pit_error
                if signal is not None:
                    try:
                        if _utc(signal.created_at) > cutoff:
                            raise PointInTimeViolation(
                                "signal was created after the as_of cutoff"
                            )
                    except Exception as exc:
                        source_status, signal, source_error = (
                            "PIT_REJECTED",
                            None,
                            type(exc).__name__,
                        )
                features = dict(signal.features or {}) if signal is not None else {}
                source_created_at = signal.created_at if signal is not None else None
                provenance = {
                    "matrix_version": MATRIX_VERSION,
                    "as_of_at": cutoff.isoformat(),
                    "received_at": cutoff.isoformat(),
                    "asset": asset,
                    "horizon": horizon,
                    "contract_family": contract_family,
                    "event_cluster": cluster,
                    "source": source_name,
                    "source_created_at": source_created_at,
                    "source_features_hash": deterministic_provenance_hash(features),
                    "source_endpoints": SOURCE_ENDPOINTS.get(
                        source_name,
                        (
                            "shared_crypto_data_hub",
                            "derived_local_research_artifacts",
                        ),
                    ),
                    "state_hash": (
                        state_manifests.get(asset, {}).get("state_hash")
                    ),
                    "market_snapshot_hash": deterministic_provenance_hash(
                        market_snapshot
                    ),
                }
                provenance_hash = deterministic_provenance_hash(provenance)
                row = {
                    "cycle_id": cycle_id,
                    "source": source_name,
                    "emitted_source": signal.source if signal is not None else None,
                    "asset": asset,
                    "horizon": horizon,
                    "contract_family": contract_family,
                    "event_cluster": cluster,
                    "ticker": market.ticker,
                    "close_time": market.close_time,
                    "status": source_status,
                    "error_type": source_error,
                    "probability_yes": (
                        float(signal.probability_yes) if signal is not None else None
                    ),
                    "uncertainty": (
                        float(signal.uncertainty) if signal is not None else None
                    ),
                    "market_probability": market_probability,
                    "source_created_at": source_created_at,
                    "as_of_at": cutoff.isoformat(),
                    "state_hash": state_manifests.get(asset, {}).get("state_hash"),
                    "features": features,
                    "provenance": provenance,
                    "provenance_hash": provenance_hash,
                }
                inserted = self.store.record_attempt(row)
                attempts_written += int(inserted)
                if inserted:
                    status_counts[source_status] += 1

        completed = self.now_fn().astimezone(timezone.utc)
        work_report = dict(workload or {})
        settled_total = self.store.settled_row_count()
        report_limit = (
            None
            if report_max_settled_rows is None
            else max(0, int(report_max_settled_rows))
        )
        report_deferred = (
            0 if report_limit is None else max(0, settled_total - report_limit)
        )
        work_report["settled_report"] = {
            "rows_available": settled_total,
            "rows_limit": report_limit,
            "rows_deferred": report_deferred,
            "partial": report_deferred > 0,
            "selection": (
                "all_settled_rows"
                if report_limit is None or report_deferred == 0
                else "most_recent_settled_rows"
            ),
        }
        workload_partial = bool(work_report.get("partial")) or report_deferred > 0
        cycle_status = (
            "CYCLE_OK" if not errors and not workload_partial else "CYCLE_PARTIAL"
        )
        self.store.finish_cycle(
            cycle_id,
            completed_at=completed.isoformat(),
            status=cycle_status,
            markets_seen=len(selected),
            attempts_written=attempts_written,
            errors=errors,
            workload=work_report,
        )
        return self.build_report(
            cycle_id,
            status_counts=dict(sorted(status_counts.items())),
            max_settled_rows=report_limit,
        )

    def reconcile_settlements(
        self,
        fetch_result: Callable[[str], Mapping[str, Any]],
        *,
        as_of: datetime | str | None = None,
        max_tickers: int = 12,
        time_budget_seconds: float = 45.0,
    ) -> dict[str, Any]:
        cutoff = (
            _utc(as_of)
            if as_of is not None
            else self.now_fn().astimezone(timezone.utc)
        )
        bounded_tickers = max(0, int(max_tickers))
        bounded_seconds = max(0.0, float(time_budget_seconds))
        batch = self.store.unsettled_ticker_batch(
            cutoff,
            limit=bounded_tickers,
        )
        started_clock = self.monotonic_fn()
        updates = 0
        settled_tickers = 0
        errors: list[str] = []
        attempted: list[str] = []
        deadline_reached = False
        for ticker in batch["items"]:
            if self.monotonic_fn() - started_clock >= bounded_seconds:
                deadline_reached = True
                break
            try:
                payload = fetch_result(ticker)
                result = str(payload.get("result") or "").lower()
                if result in {"yes", "no"}:
                    changed = self.store.settle_ticker(
                        ticker, result == "yes", cutoff
                    )
                    updates += changed
                    settled_tickers += int(changed > 0)
            except Exception as exc:
                errors.append(f"{ticker}:{type(exc).__name__}")
            finally:
                attempted.append(str(ticker))
                self.store.set_work_cursor(
                    "settlement_reconciliation",
                    str(ticker),
                    updated_at=cutoff,
                    metadata={
                        "attempted_in_current_segment": len(attempted),
                        "eligible_at_segment_start": int(batch["total"]),
                        "authority": dict(AUTHORITY),
                    },
                )
        deferred = max(0, int(batch["total"]) - len(attempted))
        remaining = self.store.unsettled_ticker_count(cutoff)
        cursor_after = (
            attempted[-1] if attempted else batch.get("cursor_before")
        )
        if int(batch["total"]) == 0:
            status = "RECONCILIATION_IDLE"
        elif deadline_reached or deferred or errors:
            status = "RECONCILIATION_PARTIAL"
        else:
            status = "RECONCILIATION_SWEEP_COMPLETE"
        return {
            "status": status,
            "as_of_at": cutoff.isoformat(),
            "settlements_recorded": updates,
            "settled_tickers": settled_tickers,
            "eligible_tickers_at_start": int(batch["total"]),
            "tickers_selected": len(batch["items"]),
            "tickers_attempted": len(attempted),
            "attempted_tickers": attempted,
            "deferred_in_sweep": deferred,
            "unresolved_eligible_tickers": remaining,
            "sweep_complete": deferred == 0,
            "deadline_reached": deadline_reached,
            "work_cap": {
                "max_tickers": bounded_tickers,
                "time_budget_seconds": bounded_seconds,
                "deadline_enforcement": "cooperative_between_public_requests",
            },
            "cursor": {
                "before": batch.get("cursor_before"),
                "after": cursor_after,
                "wrapped": bool(batch.get("wrapped")),
                "persistent": True,
            },
            "errors": errors,
            "authority": dict(AUTHORITY),
        }

    def build_report(
        self,
        cycle_id: str,
        *,
        status_counts: Mapping[str, int] | None = None,
        max_settled_rows: int | None = None,
    ) -> dict[str, Any]:
        cycle = self.store.cycle(cycle_id)
        attempts = self.store.attempts(cycle_id=cycle_id)
        if status_counts is None:
            status_counts = Counter(str(row["status"]) for row in attempts)
        try:
            workload = json.loads(str(cycle.get("workload_json") or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            workload = {"partial": True, "error": "INVALID_WORKLOAD_JSON"}
        if not isinstance(workload, dict):
            workload = {"partial": True, "error": "INVALID_WORKLOAD_SHAPE"}
        settled_total = self.store.settled_row_count()
        settled_rows = self.store.settled_rows(limit=max_settled_rows)
        settled_metrics = evidence_metrics(settled_rows)
        settled_metrics["coverage"] = {
            "rows_available": settled_total,
            "rows_scored": len(settled_rows),
            "rows_deferred": max(0, settled_total - len(settled_rows)),
            "partial": len(settled_rows) < settled_total,
            "selection": (
                "all_settled_rows"
                if len(settled_rows) == settled_total
                else "most_recent_settled_rows"
            ),
        }
        return {
            "report_name": "DUMMY_CRYPTO_HORIZON_EVIDENCE_MATRIX",
            "matrix_version": MATRIX_VERSION,
            "cycle_id": cycle_id,
            "status": cycle.get("status", "UNKNOWN"),
            "started_at": cycle.get("started_at"),
            "as_of_at": cycle.get("as_of_at"),
            "received_at": cycle.get("as_of_at"),
            "completed_at": cycle.get("completed_at"),
            "markets_seen": int(cycle.get("markets_seen") or 0),
            "sources": sorted({str(row["source"]) for row in attempts}),
            "attempts_written": int(cycle.get("attempts_written") or 0),
            "attempt_statuses": dict(sorted(status_counts.items())),
            "horizons": list(SUPPORTED_HORIZONS),
            "settled_evidence": settled_metrics,
            "workload": workload,
            "authority": dict(AUTHORITY),
            "promotion_effect": "none",
            "execution_effect": "none",
            "risk_effect": "none",
        }


def write_evidence_report(report: Mapping[str, Any], out_dir: Path | str) -> Path:
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = str(report.get("completed_at") or datetime.now(timezone.utc).isoformat())
    safe_stamp = stamp.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    path = directory / f"CRYPTO_HORIZON_EVIDENCE_MATRIX_{safe_stamp}.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(_json_ready(report), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)
    latest = directory / "LATEST.json"
    latest_temporary = latest.with_suffix(".tmp")
    latest_temporary.write_text(
        json.dumps(_json_ready(report), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    latest_temporary.replace(latest)
    return path


__all__ = [
    "AUTHORITY",
    "CAPITAL_AUTHORITY",
    "EXECUTION_AUTHORITY",
    "MATRIX_VERSION",
    "PRODUCTION_GATE_WRITE_AUTHORITY",
    "PRODUCTION_RISK_WRITE_AUTHORITY",
    "PRODUCTION_WEIGHT_WRITE_AUTHORITY",
    "SUPPORTED_HORIZONS",
    "CryptoHorizonEvidenceMatrix",
    "CryptoHorizonEvidenceStore",
    "PointInTimeViolation",
    "build_registered_crypto_sources",
    "canonical_json",
    "deterministic_provenance_hash",
    "evidence_metrics",
    "expanding_window_calibration",
    "state_provenance_manifest",
    "validate_point_in_time",
    "write_evidence_report",
]
