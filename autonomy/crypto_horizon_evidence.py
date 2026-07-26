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

import copy
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
from autonomy.signals.crypto_indicators import CryptoDataHub, _annualized_vol
from autonomy.signals.crypto_spot import parse_crypto_ticker


MATRIX_VERSION = "crypto-horizon-evidence-matrix-v1"
SUPPORTED_HORIZONS = ("15m", "1h", "1d", "1w")

# Display-honesty gate for headline skill numbers (2026-07-24 external audit
# §8: "headline skills of 0.90-0.99 sit on 2-11 event clusters, SOL-only --
# noise displayed as capability").  A Brier skill measured over a handful of
# independent event clusters is sampling noise, not capability, so the artifact
# refuses to present it as a number.
#
# The threshold reuses the established cluster-robust minimum from
# ``autonomy.backtest._evidence_disposition`` (``min_clusters=10``) -- the same
# "does this scope have enough independent clusters to say anything?" question.
# It is deliberately a local copy, not an import: this module never imports the
# production backtest/ledger stack (see the module docstring).
MIN_DISPLAY_EVENT_CLUSTERS = 10
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


class MalformedCryptoContract(ValueError):
    """Raised when a crypto target has no valid positive settlement boundary."""


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


def _positive_contract_value(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise MalformedCryptoContract(f"{label} must be a positive finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise MalformedCryptoContract(
            f"{label} must be a positive finite number"
        ) from exc
    if not math.isfinite(number) or number <= 0.0:
        raise MalformedCryptoContract(f"{label} must be a positive finite number")
    return number


def validate_crypto_contract(
    market: MarketView,
    parsed: Mapping[str, Any] | None = None,
) -> None:
    """Fail closed when a crypto contract cannot identify valid strike geometry."""
    target = parsed or parse_crypto_ticker(market.ticker)
    if target is None:
        raise MalformedCryptoContract("ticker does not encode a crypto target")
    raw = market.raw if isinstance(market.raw, Mapping) else {}
    strike_type = str(raw.get("strike_type") or "").strip().lower()
    if strike_type in {"greater", "greater_or_equal"}:
        _positive_contract_value(raw.get("floor_strike"), "floor_strike")
        return
    if strike_type == "less":
        _positive_contract_value(raw.get("cap_strike"), "cap_strike")
        return
    if strike_type == "between":
        floor = _positive_contract_value(raw.get("floor_strike"), "floor_strike")
        cap = _positive_contract_value(raw.get("cap_strike"), "cap_strike")
        if floor >= cap:
            raise MalformedCryptoContract(
                "between contract requires floor_strike < cap_strike"
            )
        return
    if strike_type:
        raise MalformedCryptoContract(f"unsupported strike_type: {strike_type}")
    _positive_contract_value(target.get("strike"), "ticker strike")


class _FrozenCycleStateHub:
    """Cycle-scoped state facade used by every matrix-owned crypto source.

    The matrix captures either supplied snapshots or one live hub snapshot per
    asset, validates them, and only then binds this facade. It never delegates
    ``state`` calls to the live hub, so a missing supplied asset cannot trigger
    an accidental network fetch from a source.
    """

    def __init__(self) -> None:
        self._states: dict[str, dict[str, Any]] = {}
        self._bound = False

    def clear(self) -> None:
        self._states = {}
        self._bound = False

    def bind(self, states: Mapping[str, dict[str, Any]]) -> None:
        self._states = {str(asset): state for asset, state in states.items()}
        self._bound = True

    def state(self, asset: str) -> dict[str, Any]:
        if not self._bound:
            raise RuntimeError("cycle state has not been bound")
        try:
            return self._states[str(asset)]
        except KeyError as exc:
            raise KeyError(
                f"{asset} is absent from the frozen cycle state"
            ) from exc

    def flat_spot_and_vol(self, asset: str) -> tuple[float, float]:
        state = self.state(asset)
        volatility = _annualized_vol(
            [float(value) for value in state["hourly_closes"]][-169:],
            24 * 365,
        )
        if volatility is None:
            raise ValueError("insufficient hourly volatility history")
        return float(state["spot"]), volatility

    def ewma_spot_and_vol(self, asset: str) -> tuple[float, float]:
        state = self.state(asset)
        closes = [float(value) for value in state["hourly_closes"]]
        returns = [
            math.log(closes[index] / closes[index - 1])
            for index in range(1, len(closes))
            if closes[index - 1] > 0
        ]
        if not returns:
            raise ValueError("no hourly returns")
        variance = returns[0] ** 2
        for value in returns[1:]:
            variance = 0.94 * variance + 0.06 * value * value
        return float(state["spot"]), math.sqrt(variance) * math.sqrt(24 * 365)


_STATE_TIME_FIELDS: tuple[tuple[str, float], ...] = (
    ("received_at_s", 1.0),
    ("coinbase_hourly_at_s", 1.0),
    ("coinbase_minute_at_s", 1.0),
    ("dvol_at_ms", 1_000.0),
)

_CANDLE_STREAMS = (
    "minute_ohlcv",
    "five_minute_ohlcv",
    "hourly_ohlcv",
    "daily_ohlcv",
)

_CANDLE_TIME_FIELDS: tuple[tuple[str, float], ...] = (
    ("at_s", 1.0),
    ("open_time_s", 1.0),
    ("close_time_s", 1.0),
    ("received_at_s", 1.0),
)

_CANDLE_INTERVALS = {
    "minute_ohlcv": 60,
    "five_minute_ohlcv": 300,
    "hourly_ohlcv": 3_600,
    "daily_ohlcv": 86_400,
}


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
    for stream in _CANDLE_STREAMS:
        for index, row in enumerate(state.get(stream) or []):
            if not isinstance(row, Mapping):
                continue
            for field, divisor in _CANDLE_TIME_FIELDS:
                value = row.get(field)
                if value is None:
                    continue
                label = f"{stream}[{index}].{field}"
                try:
                    stamp = datetime.fromtimestamp(
                        float(value) / divisor,
                        timezone.utc,
                    )
                except (TypeError, ValueError, OSError, OverflowError) as exc:
                    raise PointInTimeViolation(
                        f"invalid source timestamp: {label}"
                    ) from exc
                timestamps.append((label, stamp))
    return timestamps


def _validate_closed_candle_rows(state: Mapping[str, Any]) -> None:
    """Prove every supplied row was closed before its recorded receipt."""
    state_received_raw = state.get("received_at_s")
    state_received = (
        float(state_received_raw) if state_received_raw is not None else None
    )
    for stream, expected_interval in _CANDLE_INTERVALS.items():
        previous_close: float | None = None
        for index, row in enumerate(state.get(stream) or []):
            label = f"{stream}[{index}]"
            if not isinstance(row, Mapping):
                raise PointInTimeViolation(f"{label} is not a candle mapping")
            required = (
                "at_s",
                "open_time_s",
                "close_time_s",
                "received_at_s",
                "interval_s",
                "closed",
            )
            missing = [field for field in required if row.get(field) is None]
            if missing:
                raise PointInTimeViolation(
                    f"{label} missing closed-candle fields: {','.join(missing)}"
                )
            if row.get("closed") is not True:
                raise PointInTimeViolation(f"{label} is not a closed candle")
            try:
                at_s = float(row["at_s"])
                open_s = float(row["open_time_s"])
                close_s = float(row["close_time_s"])
                received_s = float(row["received_at_s"])
                interval_s = float(row["interval_s"])
            except (TypeError, ValueError, OverflowError) as exc:
                raise PointInTimeViolation(
                    f"{label} has invalid closed-candle timestamps"
                ) from exc
            values = (at_s, open_s, close_s, received_s, interval_s)
            if not all(math.isfinite(value) for value in values):
                raise PointInTimeViolation(
                    f"{label} has non-finite closed-candle timestamps"
                )
            if not math.isclose(at_s, open_s, abs_tol=1e-9):
                raise PointInTimeViolation(
                    f"{label}.at_s does not match open_time_s"
                )
            if not math.isclose(interval_s, expected_interval, abs_tol=1e-9):
                raise PointInTimeViolation(
                    f"{label}.interval_s does not match its stream"
                )
            if not math.isclose(
                close_s - open_s,
                expected_interval,
                abs_tol=1e-9,
            ):
                raise PointInTimeViolation(
                    f"{label} close_time_s does not match its interval"
                )
            if received_s < close_s:
                raise PointInTimeViolation(
                    f"{label} was received before candle close"
                )
            if state_received is not None and received_s > state_received:
                raise PointInTimeViolation(
                    f"{label} receipt follows the frozen state receipt"
                )
            if previous_close is not None and open_s < previous_close:
                raise PointInTimeViolation(
                    f"{label} overlaps or is out of chronological order"
                )
            previous_close = close_s


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
    _validate_closed_candle_rows(state)


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
    _validate_closed_candle_rows(state)
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
            for key in _CANDLE_STREAMS
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
    hub: CryptoDataHub | _FrozenCycleStateHub | None = None,
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


# Reconciliation caps for the batch settled-markets phase.  The scheduled
# runner's CLI is frozen by the task definition, so these defaults are the
# live caps: one settled-markets page covers up to ~200 tickers, keeping the
# public request budget flat while up to DEFAULT_MAX_BATCH_SETTLEMENTS
# tickers settle per run (a ~26k backlog drains within a couple of 10-minute
# task fires).  The cooperative wall-clock budget is still checked before
# every public request, so the reserved API budget discipline is unchanged.
DEFAULT_MAX_BATCH_SETTLEMENTS = 20_000
DEFAULT_MAX_PAGES_PER_SERIES = 25

# Sentinel default: build the public settled-markets listing lazily.  The
# scheduled runner only supplies the per-ticker result fetch, so the batch
# phase must default to the public listing to be reachable in production.
# Hermetic tests pass ``fetch_settled_page=None`` (disable) or a callable.
USE_PUBLIC_SETTLED_LISTING: Any = object()


def series_ticker_of(ticker: str) -> str | None:
    """Series prefix of a Kalshi market ticker (``SERIES-EVENT-MARKET``)."""
    head, sep, _rest = str(ticker).partition("-")
    if not sep or not head:
        return None
    return head


def _default_fetch_settled_page(
    series_ticker: str,
    min_close_ts: int,
    cursor: str | None = None,
) -> Mapping[str, Any]:
    """Public settled-markets page; same endpoint as the phantom reconciler."""
    from autonomy.reconciler import default_fetch_settled_page

    return default_fetch_settled_page(series_ticker, min_close_ts, cursor)


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

    def commit(self) -> None:
        self.conn.commit()

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

    def unsettled_ticker_close_map(self, as_of: datetime | str) -> dict[str, str]:
        """Earliest close time per eligible unsettled ticker (covering query)."""
        cutoff = _utc(as_of).isoformat()
        rows = self.conn.execute(
            "SELECT ticker, MIN(close_time) FROM horizon_forecast_attempts "
            "WHERE status='EMITTED' AND result_yes IS NULL AND close_time<=? "
            "GROUP BY ticker",
            (cutoff,),
        ).fetchall()
        return {str(row[0]): str(row[1]) for row in rows}

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
        *,
        commit: bool = True,
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
        if commit:
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


def headline_skill_display(
    skill: float | None,
    event_clusters: int,
    *,
    min_clusters: int = MIN_DISPLAY_EVENT_CLUSTERS,
) -> dict[str, Any]:
    """Decide whether a scope may present a headline Brier-skill number.

    Returns the display block that accompanies every scope in the artifact.
    ``brier_skill_vs_market`` inside the block is the value a dashboard may
    render: ``None`` whenever the evidence is too thin to display.  The
    computed value is never destroyed -- it stays under
    ``computed_brier_skill_vs_market`` for consumers doing their own
    cluster-aware analysis -- but it is not offered as a headline.
    """
    clusters = max(0, int(event_clusters))
    minimum = max(0, int(min_clusters))
    computed = None if skill is None else float(skill)
    if clusters < minimum:
        return {
            "status": "INSUFFICIENT_CLUSTERS",
            "event_clusters": clusters,
            "min_clusters": minimum,
            "brier_skill_vs_market": None,
            "computed_brier_skill_vs_market": computed,
            "suppressed": True,
            "reason": "brier_skill_over_too_few_event_clusters_is_noise",
        }
    if computed is None:
        return {
            "status": "NO_MARKET_BENCHMARK",
            "event_clusters": clusters,
            "min_clusters": minimum,
            "brier_skill_vs_market": None,
            "computed_brier_skill_vs_market": None,
            "suppressed": False,
            "reason": "no_market_benchmarked_settled_rows_in_scope",
        }
    return {
        "status": "DISPLAYED",
        "event_clusters": clusters,
        "min_clusters": minimum,
        "brier_skill_vs_market": computed,
        "computed_brier_skill_vs_market": computed,
        "suppressed": False,
        "reason": "event_clusters_at_or_above_minimum",
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
        clusters = len({str(row["event_cluster"]) for row in scope_rows})
        computed_skill = (
            round(
                1.0 - statistics.fmean(briers) / statistics.fmean(market_briers),
                10,
            )
            if briers and market_briers and statistics.fmean(market_briers) > 0
            else None
        )
        display = headline_skill_display(computed_skill, clusters)
        scopes[key] = {
            "source": source,
            "asset": asset,
            "horizon": horizon,
            "contract_family": contract_family,
            "settled_forecasts": len(scope_rows),
            "event_clusters": clusters,
            "brier": round(statistics.fmean(briers), 10) if briers else None,
            "log_loss": round(statistics.fmean(losses), 10) if losses else None,
            "market_brier": (
                round(statistics.fmean(market_briers), 10) if market_briers else None
            ),
            # Headline field: suppressed (None) below the cluster minimum so a
            # 2-cluster 0.99 can never be rendered as capability.  The computed
            # value survives under ``headline_skill``.
            "brier_skill_vs_market": display["brier_skill_vs_market"],
            "headline_skill": display,
            "ece_10": ece,
            "mce_10": mce,
            "brier_advantage_ci95": _cluster_bootstrap_advantage(scope_rows),
            "expanding_window_calibration": expanding_window_calibration(scope_rows),
            "execution_authority": False,
        }
    suppressed = [
        key for key, scope in scopes.items()
        if scope["headline_skill"]["suppressed"]
    ]
    return {
        "settled_forecasts": len(rows),
        "scopes": scopes,
        "headline_skill_display": {
            "min_clusters": MIN_DISPLAY_EVENT_CLUSTERS,
            "scopes_total": len(scopes),
            "scopes_suppressed": len(suppressed),
            "scopes_displayed": sum(
                1 for scope in scopes.values()
                if scope["headline_skill"]["status"] == "DISPLAYED"
            ),
            "suppressed_scopes": sorted(suppressed),
            "rule": "no_headline_brier_skill_below_min_event_clusters",
        },
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
        self._cycle_state_hub = _FrozenCycleStateHub()
        self._cycle_cutoff: datetime | None = None
        self.sources = list(
            sources
            if sources is not None
            else build_registered_crypto_sources(self._cycle_state_hub)
        )
        seen_sources: set[int] = set()
        for source in self.sources:
            self._bind_source_cycle_inputs(source, seen_sources)
        self._requires_btc_dependency = any(
            self._source_tree_contains(source, "crypto_btc_leadlag", set())
            for source in self.sources
        )
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self.monotonic_fn = monotonic_fn or time.monotonic

    def close(self) -> None:
        self.store.close()

    def _bind_source_cycle_inputs(
        self,
        source: Any,
        seen: set[int],
    ) -> None:
        """Route recognized state and time callbacks through cycle facades."""
        identity = id(source)
        if identity in seen:
            return
        seen.add(identity)
        if hasattr(source, "fetch_state"):
            source.fetch_state = self._cycle_state_hub.state
        if hasattr(source, "_fetch_state"):
            source._fetch_state = self._cycle_state_hub.state
        source_name = str(getattr(source, "name", ""))
        if hasattr(source, "hours_to_close"):
            source.hours_to_close = self._cycle_hours_to_close
        if hasattr(source, "fetch_spot_and_vol"):
            if source_name == "crypto_ewma_t":
                source.fetch_spot_and_vol = self._cycle_state_hub.ewma_spot_and_vol
            elif source_name == "crypto_spot_vol":
                source.fetch_spot_and_vol = self._cycle_state_hub.flat_spot_and_vol
        if source_name in {"crypto_spot_vol", "crypto_ewma_t"}:
            source._hours_to_close = self._cycle_hours_to_close
            source.decision_time_fn = self._cycle_decision_time
        if source_name == "market_debias":
            source._market_context = self._cycle_market_debias_context
        parent = getattr(source, "parent", None)
        if parent is not None:
            self._bind_source_cycle_inputs(parent, seen)

    def _cycle_hours_to_close(self, market: MarketView) -> float:
        """Compute every registered source horizon from the matrix cutoff."""
        decision_time = self._cycle_decision_time()
        close = _utc(market.close_time)
        return max(
            0.05,
            (close - decision_time).total_seconds() / 3_600.0,
        )

    def _cycle_decision_time(self) -> datetime:
        if self._cycle_cutoff is None:
            raise PointInTimeViolation("cycle timing has not been bound")
        return self._cycle_cutoff

    def _cycle_market_debias_context(
        self,
        market: MarketView,
    ) -> tuple[float, str, str] | None:
        """Matrix-clock equivalent of MarketDebiasSignal._market_context."""
        if self._cycle_cutoff is None:
            return None
        from autonomy.signals.market_debias import (
            _exact_curve_scope,
            _horizon_bucket,
            _hours_to_expiry,
            _parse_utc,
        )
        from autonomy.target_policy import is_prediction_quarantined_target

        if is_prediction_quarantined_target(
            market.ticker,
            category=(market.raw or {}).get("category"),
            vertical=market.vertical,
        ):
            return None
        if str(market.status or "").strip().lower() not in {"active", "open"}:
            return None
        if market.fetched_at is not None:
            fetched = _parse_utc(market.fetched_at)
            if fetched is None or fetched > self._cycle_cutoff:
                return None
        hours = _hours_to_expiry(
            market.close_time,
            self._cycle_cutoff.isoformat(),
        )
        if hours is None:
            return None
        horizon = _horizon_bucket(hours)
        exact_scope = _exact_curve_scope(market.ticker, horizon)
        if exact_scope is None:
            return None
        return hours, horizon, exact_scope

    @classmethod
    def _source_tree_contains(
        cls,
        source: Any,
        source_name: str,
        seen: set[int],
    ) -> bool:
        identity = id(source)
        if identity in seen:
            return False
        seen.add(identity)
        if str(getattr(source, "name", "")) == source_name:
            return True
        parent = getattr(source, "parent", None)
        return (
            parent is not None
            and cls._source_tree_contains(parent, source_name, seen)
        )

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
        explicit_cutoff = _utc(as_of) if as_of is not None else None
        selected: list[
            tuple[MarketView, str, str, str, str, str | None]
        ] = []
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
            contract_error: str | None = None
            try:
                validate_crypto_contract(market, parsed)
            except MalformedCryptoContract as exc:
                contract_error = str(exc)
            selected.append(
                (
                    market,
                    asset,
                    cohort.timeframe,
                    contract_family,
                    cluster,
                    contract_error,
                )
            )

        errors: list[str] = []
        required_assets = {
            asset
            for _market, asset, _horizon, _family, _cluster, contract_error
            in selected
            if contract_error is None
        }
        dependency_assets = (
            {"BTC"}
            if self._requires_btc_dependency
            and any(asset in {"ETH", "SOL"} for asset in required_assets)
            else set()
        )
        capture_assets = required_assets | dependency_assets
        supplied_mode = states is not None
        supplied = (
            {str(asset).upper(): state for asset, state in states.items()}
            if states is not None
            else {}
        )

        state_by_asset: dict[str, dict[str, Any]] = {}
        state_errors: dict[str, str] = {}
        state_manifests: dict[str, dict[str, Any]] = {}
        live_reset_error: Exception | None = None
        if capture_assets and not supplied_mode:
            reset = getattr(self.hub, "clear", None)
            if callable(reset):
                try:
                    reset()
                except Exception as exc:
                    live_reset_error = exc
                    errors.append(
                        f"state:hub:{type(exc).__name__}:{str(exc)[:120]}"
                    )
        for asset in sorted(capture_assets):
            if supplied_mode and asset not in supplied:
                if asset in required_assets:
                    state_errors[asset] = "MissingSuppliedState"
                    errors.append(
                        f"state:{asset}:MissingSuppliedState:"
                        "caller did not supply the required asset snapshot"
                    )
                continue
            try:
                if live_reset_error is not None:
                    raise RuntimeError("live hub reset failed")
                raw_state = (
                    supplied[asset] if supplied_mode else self.hub.state(asset)
                )
                if not isinstance(raw_state, Mapping):
                    raise TypeError("state snapshot must be a mapping")
                snapshot = copy.deepcopy(dict(raw_state))
                if not snapshot:
                    raise ValueError("state snapshot is empty")
                embedded_asset = snapshot.get("asset")
                if (
                    embedded_asset is not None
                    and str(embedded_asset).upper() != asset
                ):
                    raise ValueError("state snapshot asset does not match key")
                state_by_asset[asset] = snapshot
            except Exception as exc:
                state_errors[asset] = type(exc).__name__
                errors.append(
                    f"state:{asset}:{type(exc).__name__}:{str(exc)[:120]}"
                )

        # A live cycle's decision cutoff must follow its read-only state
        # capture. An explicit replay cutoff remains fixed and rejects any
        # snapshot that was unavailable then.
        preflight_cutoff = (
            explicit_cutoff
            if explicit_cutoff is not None
            else self.now_fn().astimezone(timezone.utc)
        )
        self._cycle_cutoff = preflight_cutoff
        for asset, snapshot in list(state_by_asset.items()):
            try:
                state_manifests[asset] = state_provenance_manifest(
                    asset,
                    snapshot,
                    preflight_cutoff,
                )
            except Exception as exc:
                state_by_asset.pop(asset, None)
                state_errors[asset] = type(exc).__name__
                errors.append(
                    f"state:{asset}:{type(exc).__name__}:{str(exc)[:120]}"
                )

        market_pit_errors: dict[str, str] = {}
        eligible_selected: list[
            tuple[MarketView, str, str, str, str, str | None]
        ] = []
        for item in selected:
            market, asset, _horizon, _family, _cluster, contract_error = item
            if contract_error is not None:
                errors.append(
                    f"contract:{market.ticker}:MalformedCryptoContract:"
                    f"{contract_error[:120]}"
                )
                continue
            if asset in state_errors:
                market_pit_errors[market.ticker] = state_errors[asset]
                errors.append(
                    f"pit:{market.ticker}:{state_errors[asset]}:"
                    "state unavailable or invalid"
                )
                continue
            try:
                validate_point_in_time(
                    market,
                    state_by_asset[asset],
                    preflight_cutoff,
                )
            except Exception as exc:
                market_pit_errors[market.ticker] = type(exc).__name__
                errors.append(
                    f"pit:{market.ticker}:{type(exc).__name__}:{str(exc)[:120]}"
                )
                continue
            eligible_selected.append(item)

        hook_errors: dict[str, str] = {}
        if eligible_selected:
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

        # Source hooks clear their own caches (and may call ``clear`` on this
        # facade). Bind only after all hooks so every provider sees the exact
        # validated snapshot captured above.
        self._cycle_state_hub.bind(state_by_asset)

        mutated_assets: set[str] = set()
        cycle_state_integrity_error: str | None = None

        def detect_cycle_state_mutation() -> None:
            nonlocal cycle_state_integrity_error
            changed = {
                asset
                for asset, manifest in state_manifests.items()
                if deterministic_provenance_hash(state_by_asset[asset])
                != manifest["state_hash"]
            }
            for asset in sorted(changed - mutated_assets):
                errors.append(
                    f"state:{asset}:CycleStateMutation:"
                    "a source mutated the frozen cycle snapshot"
                )
            if changed:
                mutated_assets.update(changed)
                cycle_state_integrity_error = "CycleStateMutation"

        generated: dict[tuple[str, str], tuple[str, Signal | None, str | None]] = {}
        for source in self.sources:
            source_name = str(getattr(source, "name", type(source).__name__))
            # Check once at each provider boundary. A mutating provider may
            # contaminate its own remaining calls, but all of that provider's
            # outputs are quarantined; no subsequent provider consumes the
            # altered snapshot.
            detect_cycle_state_mutation()
            for (
                market,
                asset,
                _horizon,
                _family,
                _cluster,
                contract_error,
            ) in selected:
                key = (market.ticker, source_name)
                if contract_error is not None:
                    generated[key] = (
                        "CONTRACT_REJECTED",
                        None,
                        "MalformedCryptoContract",
                    )
                    continue
                if market.ticker in market_pit_errors:
                    generated[key] = (
                        "PIT_REJECTED",
                        None,
                        market_pit_errors[market.ticker],
                    )
                    continue
                if cycle_state_integrity_error is not None:
                    generated[key] = (
                        "PIT_REJECTED",
                        None,
                        cycle_state_integrity_error,
                    )
                    continue
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

        detect_cycle_state_mutation()
        if mutated_assets:
            for asset in sorted(mutated_assets):
                state_errors[asset] = "CycleStateMutation"
                state_manifests.pop(asset, None)

        cutoff = (
            explicit_cutoff
            if explicit_cutoff is not None
            else self.now_fn().astimezone(timezone.utc)
        )
        if explicit_cutoff is None:
            for asset, snapshot in list(state_by_asset.items()):
                if asset in mutated_assets:
                    continue
                try:
                    state_manifests[asset] = state_provenance_manifest(
                        asset,
                        snapshot,
                        cutoff,
                    )
                except Exception as exc:
                    state_manifests.pop(asset, None)
                    state_errors[asset] = type(exc).__name__
                    errors.append(
                        f"state:{asset}:{type(exc).__name__}:{str(exc)[:120]}"
                    )
            for (
                market,
                asset,
                _horizon,
                _family,
                _cluster,
                contract_error,
            ) in eligible_selected:
                if contract_error is not None:
                    continue
                if asset in state_errors:
                    market_pit_errors[market.ticker] = state_errors[asset]
                    continue
                try:
                    validate_point_in_time(
                        market,
                        state_by_asset[asset],
                        cutoff,
                    )
                except Exception as exc:
                    market_pit_errors[market.ticker] = type(exc).__name__
                    errors.append(
                        f"pit:{market.ticker}:{type(exc).__name__}:"
                        f"{str(exc)[:120]}"
                    )

        cycle_id = (
            f"crypto-matrix-{cutoff.strftime('%Y%m%dT%H%M%S')}-"
            f"{uuid.uuid4().hex[:8]}"
        )
        self.store.start_cycle(cycle_id, started.isoformat(), cutoff.isoformat())
        for asset, manifest in state_manifests.items():
            self.store.record_snapshot(
                cycle_id,
                asset,
                cutoff.isoformat(),
                manifest,
            )

        attempts_written = 0
        status_counts: Counter[str] = Counter()
        cycle_state_hashes = {
            asset: manifest["state_hash"]
            for asset, manifest in sorted(state_manifests.items())
        }
        for (
            market,
            asset,
            horizon,
            contract_family,
            cluster,
            contract_error,
        ) in selected:
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
            pit_error = market_pit_errors.get(market.ticker)
            if contract_error is None and cycle_state_integrity_error is not None:
                pit_error = cycle_state_integrity_error
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
                    "source_time_cutoff": preflight_cutoff.isoformat(),
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
                    "cycle_state_hashes": cycle_state_hashes,
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
        fetch_settled_page: Any = USE_PUBLIC_SETTLED_LISTING,
        as_of: datetime | str | None = None,
        max_tickers: int = 12,
        time_budget_seconds: float = 45.0,
        max_batch_settlements: int = DEFAULT_MAX_BATCH_SETTLEMENTS,
        max_pages_per_series: int = DEFAULT_MAX_PAGES_PER_SERIES,
    ) -> dict[str, Any]:
        """Two-phase public settlement sweep: batch listings, then fallback.

        Phase 1 lists recently settled markets once per series (cursor-paged,
        the same endpoint shape as the phantom-settlement sweep in
        ``autonomy.reconciler``) and matches every eligible unsettled ticker
        against the listings.  One page covers up to ~200 tickers, so the
        public request budget stays flat while thousands of tickers can
        settle per run.  Phase 2 keeps the original fair, cursor-resumable
        per-ticker GET segment (``max_tickers``) for tickers the listings
        missed (delisted series, venue-lagging results, odd tickers).

        ``fetch_settled_page`` defaults to the public settled-markets listing
        because the scheduled runner only supplies the per-ticker fetch; pass
        ``None`` to disable the batch phase (hermetic tests) or a callable
        ``(series_ticker, min_close_ts, cursor) -> page`` to inject one.  The
        cooperative wall-clock budget is checked before every public request
        in both phases; a fetched page's local settlement writes always
        complete, so a page is never half-applied.  A failing series or
        listing endpoint fails closed to the per-ticker fallback and is
        disclosed in ``errors`` — never silently skipped.
        """
        cutoff = (
            _utc(as_of)
            if as_of is not None
            else self.now_fn().astimezone(timezone.utc)
        )
        bounded_tickers = max(0, int(max_tickers))
        bounded_seconds = max(0.0, float(time_budget_seconds))
        bounded_batch = max(0, int(max_batch_settlements))
        bounded_pages = max(0, int(max_pages_per_series))
        close_map = self.store.unsettled_ticker_close_map(cutoff)
        eligible_at_start = len(close_map)
        started_clock = self.monotonic_fn()
        updates = 0
        settled_tickers = 0
        deadline_reached = False

        batch_enabled = fetch_settled_page is not None
        batch_errors: list[str] = []
        batch_settled = 0
        batch_updates = 0
        batch_pages = 0
        batch_listed = 0
        batch_matched = 0
        batch_cap_reached = False
        series_attempted: list[str] = []
        series_total = 0
        if (
            batch_enabled
            and eligible_at_start > 0
            and bounded_batch > 0
            and bounded_pages > 0
        ):
            page_fetch = (
                _default_fetch_settled_page
                if fetch_settled_page is USE_PUBLIC_SETTLED_LISTING
                else fetch_settled_page
            )
            by_series: dict[str, dict[str, Any]] = {}
            for ticker, close_time in close_map.items():
                series = series_ticker_of(ticker)
                if series is None:
                    continue
                entry = by_series.setdefault(
                    series, {"tickers": set(), "min_close": None}
                )
                entry["tickers"].add(str(ticker))
                try:
                    closed_at = _utc(str(close_time))
                except (PointInTimeViolation, TypeError, ValueError, OverflowError):
                    continue
                if entry["min_close"] is None or closed_at < entry["min_close"]:
                    entry["min_close"] = closed_at
            series_total = len(by_series)
            rotation = self.store.fair_work_batch(
                "settlement_batch_series",
                sorted(by_series),
                limit=series_total,
            )
            for series in rotation["items"]:
                if batch_settled >= bounded_batch:
                    batch_cap_reached = True
                    break
                if deadline_reached:
                    break
                entry = by_series[str(series)]
                if entry["min_close"] is None:
                    # Fail closed: leave the series to the per-ticker fallback.
                    batch_errors.append(f"series:{series}:INVALID_CLOSE_TIMES")
                    continue
                # 60s slack absorbs venue clock skew at the window boundary.
                min_close_ts = int(entry["min_close"].timestamp()) - 60
                cursor_token: str | None = None
                attempted_this_series = False
                for _page in range(bounded_pages):
                    if self.monotonic_fn() - started_clock >= bounded_seconds:
                        deadline_reached = True
                        break
                    if not attempted_this_series:
                        series_attempted.append(str(series))
                        attempted_this_series = True
                    try:
                        payload = page_fetch(
                            str(series), min_close_ts, cursor_token
                        )
                    except Exception as exc:
                        # One dead series never stalls the sweep.
                        batch_errors.append(
                            f"series:{series}:{type(exc).__name__}"
                        )
                        break
                    batch_pages += 1
                    markets = (
                        payload.get("markets")
                        if isinstance(payload, Mapping)
                        else None
                    )
                    for market in markets if isinstance(markets, list) else []:
                        if not isinstance(market, Mapping):
                            continue
                        batch_listed += 1
                        listed_ticker = str(market.get("ticker") or "")
                        if listed_ticker not in entry["tickers"]:
                            continue
                        result = str(market.get("result") or "").lower()
                        if result not in {"yes", "no"}:
                            continue
                        if batch_settled >= bounded_batch:
                            batch_cap_reached = True
                            break
                        batch_matched += 1
                        try:
                            changed = self.store.settle_ticker(
                                listed_ticker,
                                result == "yes",
                                cutoff,
                                commit=False,
                            )
                        except Exception as exc:
                            batch_errors.append(
                                f"{listed_ticker}:{type(exc).__name__}"
                            )
                            continue
                        entry["tickers"].discard(listed_ticker)
                        batch_updates += changed
                        batch_settled += int(changed > 0)
                    self.store.commit()  # page-atomic local writes
                    if batch_cap_reached:
                        break
                    cursor_token = (
                        payload.get("cursor")
                        if isinstance(payload, Mapping)
                        else None
                    ) or None
                    if not cursor_token:
                        break
            if series_attempted:
                self.store.set_work_cursor(
                    "settlement_batch_series",
                    series_attempted[-1],
                    updated_at=cutoff,
                    metadata={
                        "series_attempted": len(series_attempted),
                        "series_total": series_total,
                        "settled_tickers": batch_settled,
                        "authority": dict(AUTHORITY),
                    },
                )
        updates += batch_updates
        settled_tickers += batch_settled

        fallback_batch = self.store.unsettled_ticker_batch(
            cutoff,
            limit=bounded_tickers,
        )
        fallback_errors: list[str] = []
        attempted: list[str] = []
        for ticker in fallback_batch["items"]:
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
                fallback_errors.append(f"{ticker}:{type(exc).__name__}")
            finally:
                attempted.append(str(ticker))
                self.store.set_work_cursor(
                    "settlement_reconciliation",
                    str(ticker),
                    updated_at=cutoff,
                    metadata={
                        "attempted_in_current_segment": len(attempted),
                        "eligible_at_segment_start": int(
                            fallback_batch["total"]
                        ),
                        "authority": dict(AUTHORITY),
                    },
                )
        deferred = max(0, eligible_at_start - batch_settled - len(attempted))
        remaining = self.store.unsettled_ticker_count(cutoff)
        cursor_after = (
            attempted[-1] if attempted else fallback_batch.get("cursor_before")
        )
        errors = batch_errors + fallback_errors
        if eligible_at_start == 0:
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
            "eligible_tickers_at_start": eligible_at_start,
            "tickers_selected": len(fallback_batch["items"]),
            "tickers_attempted": len(attempted),
            "attempted_tickers": attempted,
            "deferred_in_sweep": deferred,
            "unresolved_eligible_tickers": remaining,
            "sweep_complete": deferred == 0,
            "deadline_reached": deadline_reached,
            "batch_sweep": {
                "enabled": batch_enabled,
                "endpoint": "kalshi_public_settled_markets_by_series",
                "series_total": series_total,
                "series_attempted": series_attempted,
                "series_deferred": max(
                    0, series_total - len(series_attempted)
                ),
                "pages_fetched": batch_pages,
                "markets_listed": batch_listed,
                "matched_settlements": batch_matched,
                "settlements_recorded": batch_updates,
                "settled_tickers": batch_settled,
                "cap_reached": batch_cap_reached,
                "errors": batch_errors,
            },
            "work_cap": {
                "max_tickers": bounded_tickers,
                "time_budget_seconds": bounded_seconds,
                "max_batch_settlements": bounded_batch,
                "max_pages_per_series": bounded_pages,
                "deadline_enforcement": "cooperative_between_public_requests",
            },
            "cursor": {
                "before": fallback_batch.get("cursor_before"),
                "after": cursor_after,
                "wrapped": bool(fallback_batch.get("wrapped")),
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
    "DEFAULT_MAX_BATCH_SETTLEMENTS",
    "DEFAULT_MAX_PAGES_PER_SERIES",
    "EXECUTION_AUTHORITY",
    "MATRIX_VERSION",
    "MIN_DISPLAY_EVENT_CLUSTERS",
    "PRODUCTION_GATE_WRITE_AUTHORITY",
    "PRODUCTION_RISK_WRITE_AUTHORITY",
    "PRODUCTION_WEIGHT_WRITE_AUTHORITY",
    "SUPPORTED_HORIZONS",
    "USE_PUBLIC_SETTLED_LISTING",
    "CryptoHorizonEvidenceMatrix",
    "CryptoHorizonEvidenceStore",
    "MalformedCryptoContract",
    "PointInTimeViolation",
    "build_registered_crypto_sources",
    "canonical_json",
    "deterministic_provenance_hash",
    "evidence_metrics",
    "expanding_window_calibration",
    "headline_skill_display",
    "series_ticker_of",
    "state_provenance_manifest",
    "validate_crypto_contract",
    "validate_point_in_time",
    "write_evidence_report",
]
