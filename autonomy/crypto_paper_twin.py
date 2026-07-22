"""Always-on, public-read-only crypto paper digital twin.

The twin runs independently of Dummy's SHADOW/LIVE session.  It never loads
credentials, imports a broker adapter, or writes the production autonomy
ledger. Crypto is restricted to BTC/ETH/SOL at native 15-minute, hourly,
daily, and weekly horizons. Commodity prices may enter the separate crypto
macro-regime feature pipeline, but commodity contracts are never targets in
this twin. Every cohort runs an incumbent lane and a frozen
recursive-challenger lane, explicitly ranks every compatible nearest-expiry
price target, records a plain-language explanation, books one
quote-executable *simulated* taker contract per asset/expiry, and tracks a
separate conservative maker-fill diagnostic from public prints.

Paper evidence is useful for model selection but is permanently quarantined:
it cannot satisfy canary/scale readiness and has no execution or capital
authority.
"""
from __future__ import annotations

import json
import math
import random
import sqlite3
import statistics
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from autonomy.evolution_lab import ResearchGenome
from autonomy.fees import kalshi_maker_fee_cents, kalshi_taker_fee_cents
from autonomy.forecaster import EnsembleForecaster
from autonomy.live_book import normalize_orderbook_levels
from autonomy.ontology import Forecast, MarketView, Signal, Vertical
from autonomy.reconciler import (
    default_fetch_market_result,
    default_fetch_trades,
)
from autonomy.scanner import MarketScanner
from autonomy.signals.crypto_indicators import (
    CryptoDataHub,
    CryptoTechnicalCompositeSignal,
)
from autonomy.signals.crypto_spot import (
    CryptoEwmaTailSignal,
    CryptoSpotVolSignal,
)
from autonomy.signals.market_prior import MarketPriorSignal
from autonomy.stats import mean_ci95 as _mean_ci95
from autonomy.target_policy import DATA_ONLY_CONTEXT_POLICY
from kalshi.presubmit import default_fetch_orderbook


TIMEFRAMES = {
    "15m": 15 * 60,
    "1h": 60 * 60,
    "1d": 24 * 60 * 60,
    "1w": 7 * 24 * 60 * 60,
}
BASE_STRATEGIES = ("incumbent", "recursive", "exploratory")
HOURLY_CALIBRATED_STRATEGY = "hourly_calibrated"
STRATEGIES = (*BASE_STRATEGIES, HOURLY_CALIBRATED_STRATEGY)
ASSETS = ("BTC", "ETH", "SOL")
REQUIRED_TRADING_TIMEFRAMES = ("1h", "1d", "1w")
SUPPLEMENTAL_TRADING_TIMEFRAMES = ("15m",)
HOURLY_CALIBRATION_VERSION = "hourly-market-anchor-v1"
HOURLY_CALIBRATION_MIN_SETTLED = 20
HOURLY_CALIBRATION_MIN_CLUSTERS = 10
HOURLY_CALIBRATION_MIN_TRAIN = 10
HOURLY_CALIBRATION_MIN_FORWARD = 10
TARGET_CANDIDATE_VERSION = "earliest-target-candidate-v1"
CRYPTO_COVERAGE_VERSION = "all-listed-nearest-expiry-targets-v1"
CRYPTO_COVERAGE_LANE = "coverage_probe"


@dataclass(frozen=True)
class MarketCohort:
    vertical: Vertical
    asset: str
    timeframe: str
    series: tuple[str, ...]


@dataclass(frozen=True)
class HourlyCalibrationProfile:
    version: str
    status: str
    model_share: float
    fitted_model_share: float
    uncertainty_floor: float
    settled_forecasts: int
    event_clusters: int
    walk_forward_forecasts: int
    walk_forward_clusters: int
    walk_forward_brier_advantage: float | None
    walk_forward_advantage_ci95: dict[str, Any] | None
    fitted_through: str | None
    evidence_source: str = "earliest_forward_hourly_calibration_forecasts"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


COHORTS = (
    MarketCohort(Vertical.CRYPTO, "BTC", "15m", ("KXBTC15M",)),
    MarketCohort(Vertical.CRYPTO, "ETH", "15m", ("KXETH15M",)),
    MarketCohort(Vertical.CRYPTO, "SOL", "15m", ("KXSOL15M",)),
    MarketCohort(Vertical.CRYPTO, "BTC", "1h", ("KXBTCD", "KXBTC")),
    MarketCohort(Vertical.CRYPTO, "ETH", "1h", ("KXETHD", "KXETH")),
    MarketCohort(Vertical.CRYPTO, "SOL", "1h", ("KXSOLD", "KXSOLE")),
    # The same direct-price series carries mixed event cadences. Route each
    # event from its actual open_time-to-close_time duration, not the series-
    # level frequency label. Legacy daily aliases remain accepted when listed.
    MarketCohort(
        Vertical.CRYPTO, "BTC", "1d", ("KXBTCD", "KXBTC", "BTCD", "BTC"),
    ),
    MarketCohort(
        Vertical.CRYPTO, "ETH", "1d", ("KXETHD", "KXETH", "ETHD", "ETH"),
    ),
    MarketCohort(Vertical.CRYPTO, "SOL", "1d", ("KXSOLD", "KXSOLE")),
    MarketCohort(Vertical.CRYPTO, "BTC", "1w", ("KXBTCD", "KXBTC")),
    MarketCohort(Vertical.CRYPTO, "ETH", "1w", ("KXETHD", "KXETH")),
    MarketCohort(Vertical.CRYPTO, "SOL", "1w", ("KXSOLD", "KXSOLE")),
)
WATCHLIST = sorted({series for cohort in COHORTS for series in cohort.series})
MIN_MINUTES_TO_CLOSE = {"15m": 1.0, "1h": 5.0, "1d": 60.0, "1w": 360.0}
MAX_MINUTES_TO_CLOSE = {
    "15m": 20.0,
    "1h": 90.0,
    "1d": 4 * 24 * 60.0,
    "1w": 10 * 24 * 60.0,
}
INCUMBENT_MIN_EV_CENTS = 8.0
INCUMBENT_MAX_UNCERTAINTY = 0.35
INCUMBENT_MAX_ENTRY_CENTS = 75

# Data-justified paper-capital quarantine (Wave-1 C1, 2026-07-16).
# The crypto 1h exploratory and incumbent lanes are net losers on settled paper
# evidence (exploratory: -338c net, Brier skill vs market -0.055; incumbent:
# -558c net, Brier skill -0.481) while the 15m_direction lanes carry the edge.
# Quarantined lanes stop allocating paper bankroll (no trades, no maker
# quotes) but keep emitting observations and target-candidate forecasts, so
# grading evidence continues to accrue and a lane can earn its way back
# through the promotion machinery. Removal of a lane from this set is a
# human, reviewed change citing fresh cohort evidence.
PAPER_LANE_QUARANTINE: frozenset[tuple[str, str, str]] = frozenset({
    ("CRYPTO", "exploratory", "1h"),
    ("CRYPTO", "incumbent", "1h"),
})


def lane_quarantined(vertical: Any, strategy: str, timeframe: str) -> bool:
    """True when a (vertical, strategy, timeframe) lane may not spend paper capital."""
    value = vertical.value if hasattr(vertical, "value") else str(vertical)
    return (str(value), str(strategy), str(timeframe)) in PAPER_LANE_QUARANTINE
PAPER_RESEARCH_MIN_EV_CENTS = 3.0
CONFIDENCE_HAIRCUT_SIGMAS = 0.5
MAKER_TTL_SECONDS = 60
MAX_QUEUE_AHEAD = 50.0
TARGET_LADDER_AUDIT_LIMIT = 12
DEFAULT_GENOME = ResearchGenome(0.75, 8, 0.25, 75)


_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS cycles(
    cycle_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    markets_seen INTEGER NOT NULL DEFAULT 0,
    observations_written INTEGER NOT NULL DEFAULT 0,
    trades_opened INTEGER NOT NULL DEFAULT 0,
    settlements_recorded INTEGER NOT NULL DEFAULT 0,
    maker_updates INTEGER NOT NULL DEFAULT 0,
    errors_json TEXT NOT NULL DEFAULT '[]',
    public_read_only INTEGER NOT NULL DEFAULT 1,
    broker_contacted INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS epochs(
    epoch_id TEXT PRIMARY KEY,
    strategy TEXT NOT NULL,
    genome_id TEXT NOT NULL,
    genome_json TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT NOT NULL,
    reason TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_epoch
ON epochs(strategy) WHERE status='ACTIVE';
CREATE TABLE IF NOT EXISTS observations(
    observation_id TEXT PRIMARY KEY,
    cycle_id TEXT NOT NULL,
    epoch_id TEXT,
    strategy TEXT NOT NULL,
    vertical TEXT NOT NULL DEFAULT 'CRYPTO',
    timeframe TEXT NOT NULL,
    bucket_start TEXT NOT NULL,
    asset TEXT NOT NULL,
    event_cluster TEXT,
    ticker TEXT,
    action TEXT NOT NULL,
    explanation TEXT NOT NULL,
    diagnostics_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    public_read_only INTEGER NOT NULL DEFAULT 1,
    broker_contacted INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(cycle_id) REFERENCES cycles(cycle_id)
);
CREATE INDEX IF NOT EXISTS observation_lane_time
ON observations(strategy,timeframe,asset,created_at);
CREATE TABLE IF NOT EXISTS trades(
    trade_id TEXT PRIMARY KEY,
    observation_id TEXT NOT NULL,
    epoch_id TEXT,
    strategy TEXT NOT NULL,
    vertical TEXT NOT NULL DEFAULT 'CRYPTO',
    timeframe TEXT NOT NULL,
    asset TEXT NOT NULL,
    event_cluster TEXT NOT NULL,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    created_at TEXT NOT NULL,
    close_time TEXT NOT NULL,
    probability_yes REAL NOT NULL,
    market_probability REAL NOT NULL,
    uncertainty REAL NOT NULL,
    edge_cents REAL NOT NULL,
    conservative_ev_cents REAL NOT NULL,
    taker_price_cents INTEGER NOT NULL,
    taker_fee_cents INTEGER NOT NULL,
    taker_fill_basis TEXT NOT NULL,
    status TEXT NOT NULL,
    result_yes INTEGER,
    settled_at TEXT,
    taker_pnl_cents INTEGER,
    brier REAL,
    market_brier REAL,
    explanation TEXT NOT NULL,
    sources_json TEXT NOT NULL,
    features_json TEXT NOT NULL,
    market_snapshot_json TEXT NOT NULL,
    policy_json TEXT NOT NULL,
    maker_price_cents INTEGER,
    maker_fee_cents INTEGER,
    maker_queue_ahead REAL,
    maker_queue_snapshot INTEGER NOT NULL DEFAULT 0,
    maker_status TEXT NOT NULL,
    maker_expires_at TEXT,
    maker_fill_witness_json TEXT,
    maker_pnl_cents INTEGER,
    counts_toward_readiness INTEGER NOT NULL DEFAULT 0,
    broker_contacted INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(observation_id) REFERENCES observations(observation_id),
    UNIQUE(strategy,vertical,timeframe,asset,event_cluster)
);
CREATE INDEX IF NOT EXISTS trade_status ON trades(status,close_time);
CREATE INDEX IF NOT EXISTS maker_status ON trades(maker_status,maker_expires_at);
CREATE TABLE IF NOT EXISTS hourly_calibration_forecasts(
    forecast_id TEXT PRIMARY KEY,
    cycle_id TEXT NOT NULL,
    asset TEXT NOT NULL,
    event_cluster TEXT NOT NULL,
    ticker TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    close_time TEXT NOT NULL,
    raw_probability REAL NOT NULL,
    market_probability REAL NOT NULL,
    calibrated_probability REAL NOT NULL,
    uncertainty REAL NOT NULL,
    model_share REAL NOT NULL,
    calibration_version TEXT NOT NULL,
    profile_json TEXT NOT NULL,
    result_yes INTEGER,
    settled_at TEXT,
    brier REAL,
    market_brier REAL,
    UNIQUE(asset,event_cluster,calibration_version),
    FOREIGN KEY(cycle_id) REFERENCES cycles(cycle_id)
);
CREATE INDEX IF NOT EXISTS hourly_calibration_unsettled
ON hourly_calibration_forecasts(result_yes,ticker);
CREATE TABLE IF NOT EXISTS target_candidate_forecasts(
    candidate_id TEXT PRIMARY KEY,
    cycle_id TEXT NOT NULL,
    candidate_version TEXT NOT NULL,
    strategy TEXT NOT NULL,
    vertical TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    asset TEXT NOT NULL,
    event_cluster TEXT NOT NULL,
    ticker TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    close_time TEXT NOT NULL,
    target_json TEXT NOT NULL,
    side TEXT NOT NULL,
    rank_selected INTEGER NOT NULL,
    eligible INTEGER NOT NULL,
    reason TEXT NOT NULL,
    probability_yes REAL NOT NULL,
    market_probability REAL NOT NULL,
    uncertainty REAL NOT NULL,
    conservative_ev_cents REAL NOT NULL,
    entry_price_cents INTEGER NOT NULL,
    fee_cents INTEGER NOT NULL,
    result_yes INTEGER,
    settled_at TEXT,
    counterfactual_quote_pnl_cents INTEGER,
    brier REAL,
    market_brier REAL,
    UNIQUE(candidate_version,strategy,vertical,timeframe,asset,event_cluster,ticker),
    FOREIGN KEY(cycle_id) REFERENCES cycles(cycle_id)
);
CREATE INDEX IF NOT EXISTS target_candidate_unsettled
ON target_candidate_forecasts(result_yes,close_time,ticker);
CREATE TABLE IF NOT EXISTS crypto_coverage_trades(
    coverage_id TEXT PRIMARY KEY,
    cycle_id TEXT NOT NULL,
    coverage_version TEXT NOT NULL,
    lane TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    asset TEXT NOT NULL,
    event_cluster TEXT NOT NULL,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    created_at TEXT NOT NULL,
    close_time TEXT NOT NULL,
    probability_yes REAL NOT NULL,
    market_probability REAL NOT NULL,
    uncertainty REAL NOT NULL,
    conservative_ev_cents REAL NOT NULL,
    entry_price_cents INTEGER NOT NULL,
    fee_cents INTEGER NOT NULL,
    target_json TEXT NOT NULL,
    normal_policy_eligible INTEGER NOT NULL,
    normal_policy_reason TEXT NOT NULL,
    explanation TEXT NOT NULL,
    status TEXT NOT NULL,
    result_yes INTEGER,
    settled_at TEXT,
    pnl_cents INTEGER,
    brier REAL,
    market_brier REAL,
    counts_toward_promotion INTEGER NOT NULL DEFAULT 0,
    counts_toward_readiness INTEGER NOT NULL DEFAULT 0,
    broker_contacted INTEGER NOT NULL DEFAULT 0,
    UNIQUE(coverage_version,ticker),
    FOREIGN KEY(cycle_id) REFERENCES cycles(cycle_id)
);
CREATE INDEX IF NOT EXISTS crypto_coverage_status
ON crypto_coverage_trades(status,close_time,ticker);
"""


def _utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _vertical_name(value: Vertical | str) -> str:
    return value.value if isinstance(value, Vertical) else str(value)


def _cohorts_for_ticker(ticker: str) -> list[MarketCohort]:
    upper = ticker.upper()
    return [
        cohort for cohort in COHORTS
        if any(upper.startswith(f"{series.upper()}-") for series in cohort.series)
    ]


def cohort_for_ticker(ticker: str) -> MarketCohort | None:
    """Return a cohort only when the ticker's series maps unambiguously."""
    matches = _cohorts_for_ticker(ticker)
    return matches[0] if len(matches) == 1 else None


def market_listing_duration_hours(market: MarketView) -> float | None:
    try:
        opened = _utc(market.raw.get("open_time"))
        closed = _utc(market.close_time)
    except (TypeError, ValueError):
        return None
    duration = (closed - opened).total_seconds() / 3600.0
    return duration if duration > 0 else None


def cohort_for_market(market: MarketView) -> MarketCohort | None:
    matches = _cohorts_for_ticker(market.ticker)
    if len(matches) <= 1:
        return matches[0] if matches else None
    duration = market_listing_duration_hours(market)
    if duration is None:
        return None
    timeframe = "1h" if duration <= 6.0 else "1d" if duration < 120.0 else "1w"
    return next(
        (cohort for cohort in matches if cohort.timeframe == timeframe),
        None,
    )


def strategies_for(vertical: Vertical, timeframe: str) -> tuple[str, ...]:
    if vertical is Vertical.CRYPTO and timeframe == "1h":
        return STRATEGIES
    return BASE_STRATEGIES


def bucket_start(now: datetime, timeframe: str) -> str:
    if timeframe == "1w":
        day = now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        return (day - timedelta(days=day.weekday())).isoformat()
    seconds = TIMEFRAMES[timeframe]
    timestamp = int(now.astimezone(timezone.utc).timestamp())
    return datetime.fromtimestamp(timestamp - timestamp % seconds, timezone.utc).isoformat()


def event_cluster(vertical: Vertical, timeframe: str, asset: str, close_time: str) -> str:
    return (
        f"PAPER:{vertical.value}:{timeframe}:{asset}:{_utc(close_time).isoformat()}"
    )


def hourly_calibration_event_cluster(close_time: str) -> str:
    """Cluster correlated BTC/ETH/SOL forecasts by their shared hourly expiry."""
    return f"PAPER:CRYPTO:1h:{_utc(close_time).isoformat()}"


def _positive_finite(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and parsed > 0 else None


def price_target_metadata(market: MarketView, timeframe: str) -> dict[str, Any]:
    """Normalize a listed price target without guessing missing strike data."""
    strike_type = str(market.raw.get("strike_type") or "").strip().lower()
    floor = _positive_finite(market.raw.get("floor_strike"))
    cap = _positive_finite(market.raw.get("cap_strike"))
    if timeframe == "15m":
        valid = strike_type in {"greater", "greater_or_equal"} and floor is not None
        return {
            "contract_family": "15m_direction",
            "target_type": "opening_reference_direction",
            "strike_type": strike_type or None,
            "floor": floor,
            "cap": None,
            "label": (
                f"settle at/above opening reference {floor:g}"
                if valid else "invalid or missing opening reference"
            ),
            "valid": valid,
            "invalid_reason": None if valid else "missing_valid_15m_opening_reference",
        }
    if strike_type in {"greater", "greater_or_equal"}:
        valid = floor is not None
        target_type = "above"
        label = f"settle at/above {floor:g}" if valid else "invalid above target"
        invalid_reason = None if valid else "missing_valid_floor_strike"
    elif strike_type == "less":
        valid = cap is not None
        target_type = "below"
        label = f"settle below {cap:g}" if valid else "invalid below target"
        invalid_reason = None if valid else "missing_valid_cap_strike"
    elif strike_type == "between":
        valid = floor is not None and cap is not None and floor < cap
        target_type = "bucket"
        label = (
            f"settle between {floor:g} and {cap:g}"
            if valid else "invalid bounded target"
        )
        invalid_reason = None if valid else "missing_or_invalid_bucket_bounds"
    else:
        valid = False
        target_type = "unknown"
        label = "unsupported target type"
        invalid_reason = "unsupported_strike_type"
    return {
        "contract_family": "terminal_price",
        "target_type": target_type,
        "strike_type": strike_type or None,
        "floor": floor,
        "cap": cap,
        "label": label,
        "valid": valid,
        "invalid_reason": invalid_reason,
    }


def _target_rank_ev(candidate: dict[str, Any], strategy: str) -> float:
    value = (
        candidate.get("calibration_rank_ev_cents")
        if strategy == HOURLY_CALIBRATED_STRATEGY
        else (candidate.get("best") or {}).get("ev_cents")
    )
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return -1e12
    return parsed if math.isfinite(parsed) else -1e12


def price_target_inventory(
    markets: Sequence[MarketView], timeframe: str,
) -> dict[str, Any]:
    """Describe every listed nearest-expiry target, including thin books."""
    target_type_counts: dict[str, int] = {}
    invalid_reason_counts: dict[str, int] = {}
    boundaries: list[float] = []
    valid = 0
    complete_quotes = 0
    for market in markets:
        target = price_target_metadata(market, timeframe)
        target_type = str(target.get("target_type") or "unknown")
        target_type_counts[target_type] = target_type_counts.get(target_type, 0) + 1
        if bool(target.get("valid")):
            valid += 1
        elif target.get("invalid_reason"):
            reason = str(target["invalid_reason"])
            invalid_reason_counts[reason] = invalid_reason_counts.get(reason, 0) + 1
        boundaries.extend(
            float(value) for value in (target.get("floor"), target.get("cap"))
            if value is not None
        )
        complete_quotes += int(
            None not in (market.yes_bid, market.yes_ask, market.no_bid, market.no_ask)
        )
    return {
        "all_listed_targets_scanned": True,
        "listed_targets_seen": len(markets),
        "listed_valid_targets": valid,
        "listed_complete_two_sided_quotes": complete_quotes,
        "listed_target_type_counts": target_type_counts,
        "listed_invalid_reason_counts": invalid_reason_counts,
        "listed_boundary_range": {
            "minimum": min(boundaries) if boundaries else None,
            "maximum": max(boundaries) if boundaries else None,
        },
    }


def target_candidate_blockers(reason: str, *, eligible: bool) -> tuple[str, ...]:
    """Canonical multi-label blockers for settled counterfactual diagnostics."""
    if eligible:
        return ("lower_ranked_eligible",)
    text = str(reason or "").lower()
    blockers: list[str] = []
    mappings = (
        ("uncertainty", "uncertainty_gate"),
        ("model edge", "edge_gate"),
        ("entry ", "entry_price_gate"),
        ("conservative ev", "conservative_ev_gate"),
        ("calibration status", "calibration_activation_gate"),
        ("missing_market_probability", "missing_market_probability"),
        ("missing_executable_side_quote", "missing_executable_quote"),
        ("missing_valid", "invalid_target"),
        ("unsupported_strike_type", "invalid_target"),
    )
    for needle, blocker in mappings:
        if needle in text and blocker not in blockers:
            blockers.append(blocker)
    return tuple(blockers or ("other_policy_gate",))


# Throughput classes explain *why* a cohort produced no trade this cycle.
# Only the actionable classes point at a fixable pipeline gap; a market that
# Kalshi simply did not list is correct, expected abstention, not a weakness.
THROUGHPUT_TRADED = "traded"
THROUGHPUT_POLICY_REJECTED = "policy_rejected"
THROUGHPUT_NO_LISTED_MARKET = "no_listed_market"
THROUGHPUT_NO_TWO_SIDED_BOOK = "no_two_sided_book"
THROUGHPUT_FORECAST_INCOMPLETE = "forecast_incomplete"
# Classes where the market was genuinely unavailable to trade — expected, not a
# defect.
EXPECTED_ABSTENTION_CLASSES = frozenset({THROUGHPUT_NO_LISTED_MARKET})
# The only classes that point at a fixable data-pipeline gap. A policy rejection
# means a forecast completed and the engine deliberately declined on edge/EV/
# uncertainty — that is the tunable selectivity lever, not a pipeline weakness.
ACTIONABLE_THROUGHPUT_CLASSES = frozenset({
    THROUGHPUT_NO_TWO_SIDED_BOOK,
    THROUGHPUT_FORECAST_INCOMPLETE,
})


def is_actionable_throughput(throughput_class: str) -> bool:
    """True when the class is a fixable pipeline gap, not selectivity or absence."""
    return throughput_class in ACTIONABLE_THROUGHPUT_CLASSES


_THROUGHPUT_REASONS = {
    THROUGHPUT_NO_LISTED_MARKET: (
        "no nearest-expiry market listed for this cohort (expected when Kalshi "
        "has not opened the horizon)"
    ),
    THROUGHPUT_NO_TWO_SIDED_BOOK: (
        "market listed but never two-sided this cycle; no executable both-way "
        "quote to price against"
    ),
    THROUGHPUT_FORECAST_INCOMPLETE: (
        "two-sided market listed but no forecast completed; missing model, spot, "
        "or volatility input"
    ),
    THROUGHPUT_POLICY_REJECTED: (
        "forecast completed but no target cleared edge/EV/uncertainty policy"
    ),
}


def market_is_two_sided(market: MarketView) -> bool:
    """A market with all four top-of-book quotes present (tradable both ways)."""
    return None not in (
        market.yes_bid, market.yes_ask, market.no_bid, market.no_ask,
    )


def classify_throughput(
    *,
    action: str,
    listed_markets: int,
    two_sided_markets: int,
    forecasted_markets: int,
    candidates: int,
    eligible_candidates: int,
) -> str:
    """Explain a cohort's cycle outcome as one throughput class.

    Distinguishes the three causes that the legacy single reason string
    collapsed together: the market was never listed, it was listed but never
    two-sided, or it was two-sided but no forecast completed. A traded or
    policy-rejected cohort is reported as such so the actionable slice is not
    diluted by expected market absence.
    """
    if str(action).upper().startswith("BUY"):
        return THROUGHPUT_TRADED
    if candidates > 0:
        # A forecast completed for at least one target; the abstain is a
        # deliberate policy decision, not a pipeline gap.
        return THROUGHPUT_POLICY_REJECTED
    if listed_markets <= 0:
        return THROUGHPUT_NO_LISTED_MARKET
    if two_sided_markets <= 0:
        return THROUGHPUT_NO_TWO_SIDED_BOOK
    return THROUGHPUT_FORECAST_INCOMPLETE


def is_expected_abstention(throughput_class: str) -> bool:
    """True when the class reflects genuine market absence, not a fixable gap."""
    return throughput_class in EXPECTED_ABSTENTION_CLASSES


def select_price_target(
    candidates: Sequence[dict[str, Any]], strategy: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Select one target while retaining a bounded audit of the full ladder.

    An eligible target always outranks an ineligible target. This prevents a
    spectacular-looking but policy-blocked strike from forcing an abstention
    when a lower-EV strike actually clears every safety gate.
    """
    if not candidates:
        raise ValueError("target selection requires at least one candidate")

    def ranking_key(row: dict[str, Any]) -> tuple[Any, ...]:
        market = row.get("market")
        target = row.get("target") or {}
        uncertainty = float(row.get("uncertainty") or 1.0)
        volume = int(market.volume) if isinstance(market, MarketView) else 0
        liquidity = int(market.liquidity) if isinstance(market, MarketView) else 0
        ticker = market.ticker if isinstance(market, MarketView) else ""
        return (
            0 if bool(row.get("eligible")) else 1,
            0 if bool(target.get("valid")) else 1,
            -_target_rank_ev(row, strategy),
            uncertainty,
            -volume,
            -liquidity,
            ticker,
        )

    ranked = sorted(candidates, key=ranking_key)
    selected = ranked[0]
    target_type_counts: dict[str, int] = {}
    boundaries: list[float] = []
    compact: list[dict[str, Any]] = []
    for rank, row in enumerate(ranked, start=1):
        market = row.get("market")
        target = row.get("target") or {}
        target_type = str(target.get("target_type") or "unknown")
        target_type_counts[target_type] = target_type_counts.get(target_type, 0) + 1
        boundaries.extend(
            float(value) for value in (target.get("floor"), target.get("cap"))
            if value is not None
        )
        if rank > TARGET_LADDER_AUDIT_LIMIT:
            continue
        best = row.get("best") or {}
        compact.append({
            "rank": rank,
            "selected": row is selected,
            "ticker": market.ticker if isinstance(market, MarketView) else None,
            "target": target,
            "side": best.get("side"),
            "entry_price_cents": best.get("price_cents"),
            "model_probability_yes": (
                round(float(row["probability_yes"]), 10)
                if row.get("probability_yes") is not None else None
            ),
            "market_probability_yes": (
                round(float(row["market_probability"]), 10)
                if row.get("market_probability") is not None else None
            ),
            "uncertainty": (
                round(float(row["uncertainty"]), 10)
                if row.get("uncertainty") is not None else None
            ),
            "conservative_ev_cents": (
                round(float(best["ev_cents"]), 6)
                if best.get("ev_cents") is not None else None
            ),
            "ranking_ev_cents": round(_target_rank_ev(row, strategy), 6),
            "eligible": bool(row.get("eligible")),
            "reason": row.get("reason"),
            "volume": market.volume if isinstance(market, MarketView) else None,
            "liquidity": market.liquidity if isinstance(market, MarketView) else None,
        })
    selected_market = selected.get("market")
    selected_timeframe = str(selected.get("timeframe") or "")
    summary = {
        "selection_version": "nearest-expiry-target-ladder-v1",
        "selection_objective": (
            "highest fee-and-uncertainty-adjusted conservative EV among policy-eligible "
            "targets; diagnostic rank when none are eligible"
        ),
        "targets_evaluated": len(ranked),
        "valid_targets": sum(bool((row.get("target") or {}).get("valid")) for row in ranked),
        "eligible_targets": sum(bool(row.get("eligible")) for row in ranked),
        "target_type_counts": target_type_counts,
        "boundary_range": {
            "minimum": min(boundaries) if boundaries else None,
            "maximum": max(boundaries) if boundaries else None,
        },
        "selected_ticker": (
            selected_market.ticker if isinstance(selected_market, MarketView) else None
        ),
        "selected_target": selected.get("target"),
        "ranked_candidates": compact,
        "ranked_candidates_persisted": len(compact),
        "ranked_candidates_truncated": max(0, len(ranked) - len(compact)),
        "one_position_per_asset_expiry": True,
        "optimizes_raw_win_rate": False,
        "strike_adjustment_enabled": selected_timeframe in {"1h", "1d"},
        "strike_adjustment_authority": "choose_among_contemporaneously_listed_targets_only",
        "counterfactual_replay_requires_frozen_ladder": True,
        "settlement_informed_selection": False,
    }
    selected["target_ladder"] = summary
    return selected, summary


class TrustSnapshot:
    """Read-only source weights copied from the production ledger."""

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self.weights = dict(weights or {})

    @classmethod
    def from_database(cls, path: Path | str) -> TrustSnapshot:
        resolved = Path(path).resolve()
        try:
            connection = sqlite3.connect(
                f"file:{resolved.as_posix()}?mode=ro", uri=True, timeout=10,
            )
            try:
                connection.execute("PRAGMA query_only=ON")
                weights = {
                    str(source): float(weight)
                    for source, weight in connection.execute(
                        "SELECT source,weight FROM source_trust"
                    )
                }
            finally:
                connection.close()
        except (OSError, sqlite3.Error, TypeError, ValueError):
            weights = {}
        return cls(weights)

    def get_weight(self, source: str, default: float = 1.0) -> float:
        return float(self.weights.get(source, default))

    def get_weight_scoped(self, source: str, vertical: str, default: float = 1.0) -> float:
        return float(self.weights.get(f"{source}@{vertical}", self.get_weight(source, default)))


class PaperTwinLedger:
    def __init__(self, path: Path | str = Path("runtime/autonomy/crypto_paper_twin.db")) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, timeout=30)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(_SCHEMA)
        self._ensure_vertical_columns()
        self._quarantine_legacy_15m_ladders()
        self._normalize_hourly_calibration_clusters()
        self.connection.commit()

    def _ensure_vertical_columns(self) -> None:
        for table in ("observations", "trades"):
            columns = {
                str(row[1]) for row in self.connection.execute(f"PRAGMA table_info({table})")
            }
            if "vertical" not in columns:
                self.connection.execute(
                    f"ALTER TABLE {table} ADD COLUMN vertical TEXT NOT NULL DEFAULT 'CRYPTO'"
                )

    def _quarantine_legacy_15m_ladders(self) -> None:
        """Preserve pre-native-15m rows without mixing them into clean cohorts."""
        self.connection.execute(
            "UPDATE observations SET timeframe='legacy_15m_hourly' "
            "WHERE timeframe='15m' AND ticker IS NOT NULL AND ticker NOT LIKE 'KX%15M-%'"
        )
        self.connection.execute(
            "UPDATE trades SET timeframe='legacy_15m_hourly' "
            "WHERE timeframe='15m' AND ticker NOT LIKE 'KX%15M-%'"
        )

    def _normalize_hourly_calibration_clusters(self) -> None:
        rows = self.connection.execute(
            "SELECT forecast_id,close_time FROM hourly_calibration_forecasts"
        ).fetchall()
        for row in rows:
            try:
                cluster = hourly_calibration_event_cluster(str(row["close_time"]))
            except (TypeError, ValueError):
                continue
            self.connection.execute(
                "UPDATE hourly_calibration_forecasts SET event_cluster=? WHERE forecast_id=?",
                (cluster, str(row["forecast_id"])),
            )

    def legacy_quarantine_summary(self) -> dict[str, int]:
        observations = self.connection.execute(
            "SELECT COUNT(*) FROM observations WHERE timeframe='legacy_15m_hourly'"
        ).fetchone()[0]
        trades = self.connection.execute(
            "SELECT COUNT(*) FROM trades WHERE timeframe='legacy_15m_hourly'"
        ).fetchone()[0]
        return {"observations": int(observations), "trades": int(trades)}

    def close(self) -> None:
        self.connection.close()

    def start_cycle(self, at: datetime) -> str:
        cycle_id = f"paper-{at.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
        self.connection.execute(
            "INSERT INTO cycles(cycle_id,started_at,status) VALUES (?,?,?)",
            (cycle_id, at.isoformat(), "RUNNING"),
        )
        self.connection.commit()
        return cycle_id

    def finish_cycle(self, cycle_id: str, report: dict[str, Any]) -> None:
        self.connection.execute(
            "UPDATE cycles SET completed_at=?,status=?,markets_seen=?,observations_written=?,"
            "trades_opened=?,settlements_recorded=?,maker_updates=?,errors_json=? WHERE cycle_id=?",
            (
                str(report["completed_at"]), str(report["status"]),
                int(report.get("markets_seen") or 0),
                int(report.get("observations_written") or 0),
                int(report.get("trades_opened") or 0),
                int(report.get("settlements_recorded") or 0),
                int(report.get("maker_updates") or 0),
                _json(report.get("errors") or []), cycle_id,
            ),
        )
        self.connection.commit()

    def active_epoch(self) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM epochs WHERE strategy='recursive' AND status='ACTIVE'"
        ).fetchone()
        if row is None:
            return None
        return {**dict(row), "genome": json.loads(str(row["genome_json"]))}

    def ensure_epoch(
        self,
        proposed: ResearchGenome,
        *,
        now: datetime,
        proposed_id: str | None = None,
    ) -> dict[str, Any]:
        active = self.active_epoch()
        genome_id = proposed_id or proposed.genome_id
        if active is None:
            epoch_id = f"epoch-{uuid.uuid4().hex[:12]}"
            self.connection.execute(
                "INSERT INTO epochs(epoch_id,strategy,genome_id,genome_json,started_at,status,reason)"
                " VALUES (?,?,?,?,?,'ACTIVE',?)",
                (epoch_id, "recursive", genome_id, _json(asdict(proposed)), now.isoformat(),
                 "initialized_frozen_forward_epoch"),
            )
            self.connection.commit()
            return self.active_epoch() or {}
        if str(active["genome_id"]) == genome_id:
            return active
        performance = self.lane_summary(
            "recursive", None, since=str(active["started_at"]),
        )
        failed = bool(
            int(performance.get("settled_trades") or 0) >= 30
            and int(performance.get("event_clusters") or 0) >= 5
            and int(performance.get("net_pnl_cents") or 0) < 0
            and float((performance.get("mean_pnl_ci95") or {}).get("upper") or 0) < 0
        )
        if not failed:
            return active
        self.connection.execute(
            "UPDATE epochs SET ended_at=?,status='RETIRED',reason=? WHERE epoch_id=?",
            (now.isoformat(), "failed_forward_epoch", str(active["epoch_id"])),
        )
        epoch_id = f"epoch-{uuid.uuid4().hex[:12]}"
        self.connection.execute(
            "INSERT INTO epochs(epoch_id,strategy,genome_id,genome_json,started_at,status,reason)"
            " VALUES (?,?,?,?,?,'ACTIVE',?)",
            (epoch_id, "recursive", genome_id, _json(asdict(proposed)), now.isoformat(),
             "automatic_research_only_rotation_after_failed_epoch"),
        )
        self.connection.commit()
        return self.active_epoch() or {}

    def record_observation(self, row: dict[str, Any]) -> str:
        observation_id = str(row.get("observation_id") or f"obs-{uuid.uuid4().hex[:16]}")
        self.connection.execute(
            "INSERT INTO observations(observation_id,cycle_id,epoch_id,strategy,vertical,timeframe,"
            "bucket_start,asset,event_cluster,ticker,action,explanation,diagnostics_json,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                observation_id, row["cycle_id"], row.get("epoch_id"), row["strategy"],
                _vertical_name(row.get("vertical") or Vertical.CRYPTO), row["timeframe"],
                row["bucket_start"], row["asset"],
                row.get("event_cluster"), row.get("ticker"), row["action"],
                row["explanation"], _json(row.get("diagnostics") or {}), row["created_at"],
            ),
        )
        self.connection.commit()
        return observation_id

    def has_lane_trade(
        self,
        strategy: str,
        timeframe: str,
        asset: str,
        cluster: str,
        vertical: Vertical | str = Vertical.CRYPTO,
    ) -> bool:
        return self.connection.execute(
            "SELECT 1 FROM trades WHERE strategy=? AND vertical=? AND timeframe=? "
            "AND asset=? AND event_cluster=?",
            (strategy, _vertical_name(vertical), timeframe, asset, cluster),
        ).fetchone() is not None

    def record_trade(self, row: dict[str, Any]) -> bool:
        try:
            self.connection.execute(
                "INSERT INTO trades(trade_id,observation_id,epoch_id,strategy,vertical,timeframe,asset,"
                "event_cluster,ticker,side,created_at,close_time,probability_yes,market_probability,"
                "uncertainty,edge_cents,conservative_ev_cents,taker_price_cents,taker_fee_cents,"
                "taker_fill_basis,status,explanation,sources_json,features_json,market_snapshot_json,"
                "policy_json,maker_price_cents,maker_fee_cents,maker_queue_ahead,"
                "maker_queue_snapshot,maker_status,maker_expires_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    row["trade_id"], row["observation_id"], row.get("epoch_id"), row["strategy"],
                    _vertical_name(row.get("vertical") or Vertical.CRYPTO), row["timeframe"],
                    row["asset"], row["event_cluster"], row["ticker"],
                    row["side"], row["created_at"], row["close_time"], row["probability_yes"],
                    row["market_probability"], row["uncertainty"], row["edge_cents"],
                    row["conservative_ev_cents"], row["taker_price_cents"],
                    row["taker_fee_cents"], "live_top_ask_quote_simulated_one_contract",
                    "OPEN", row["explanation"], _json(row.get("sources") or {}),
                    _json(row.get("features") or {}), _json(row.get("market_snapshot") or {}),
                    _json(row.get("policy") or {}), row.get("maker_price_cents"),
                    row.get("maker_fee_cents"), row.get("maker_queue_ahead"),
                    int(bool(row.get("maker_queue_snapshot"))), row["maker_status"],
                    row.get("maker_expires_at"),
                ),
            )
            self.connection.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def record_crypto_coverage_trade(self, row: dict[str, Any]) -> bool:
        """Freeze the earliest forced decision for one real listed ticker."""
        try:
            self.connection.execute(
                "INSERT INTO crypto_coverage_trades(coverage_id,cycle_id,coverage_version,"
                "lane,timeframe,asset,event_cluster,ticker,side,created_at,close_time,"
                "probability_yes,market_probability,uncertainty,conservative_ev_cents,"
                "entry_price_cents,fee_cents,target_json,normal_policy_eligible,"
                "normal_policy_reason,explanation,status,counts_toward_promotion,"
                "counts_toward_readiness,broker_contacted) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'OPEN',?,?,?)",
                (
                    row["coverage_id"], row["cycle_id"], row["coverage_version"],
                    row["lane"], row["timeframe"], row["asset"], row["event_cluster"],
                    row["ticker"], row["side"], row["created_at"], row["close_time"],
                    row["probability_yes"], row["market_probability"], row["uncertainty"],
                    row["conservative_ev_cents"], row["entry_price_cents"],
                    row["fee_cents"], _json(row.get("target") or {}),
                    int(bool(row.get("normal_policy_eligible"))),
                    row["normal_policy_reason"], row["explanation"],
                    int(bool(row.get("counts_toward_promotion"))),
                    int(bool(row.get("counts_toward_readiness"))),
                    int(bool(row.get("broker_contacted"))),
                ),
            )
            self.connection.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def open_tickers(self) -> list[str]:
        return [
            str(row[0]) for row in self.connection.execute(
                "SELECT DISTINCT ticker FROM trades WHERE status='OPEN' ORDER BY ticker"
            )
        ]

    def open_crypto_coverage_tickers(self) -> list[str]:
        return [
            str(row[0]) for row in self.connection.execute(
                "SELECT DISTINCT ticker FROM crypto_coverage_trades "
                "WHERE status='OPEN' ORDER BY ticker"
            )
        ]

    def settle_ticker(self, ticker: str, result_yes: bool, settled_at: datetime) -> int:
        rows = self.connection.execute(
            "SELECT trade_id,side,taker_price_cents,taker_fee_cents,probability_yes,"
            "market_probability,maker_status,maker_price_cents,maker_fee_cents FROM trades"
            " WHERE ticker=? AND status='OPEN'",
            (ticker,),
        ).fetchall()
        updated = 0
        for row in rows:
            won = (str(row["side"]) == "yes" and result_yes) or (
                str(row["side"]) == "no" and not result_yes
            )
            price = int(row["taker_price_cents"])
            taker_pnl = (100 - price if won else -price) - int(row["taker_fee_cents"])
            outcome = 1.0 if result_yes else 0.0
            brier = (float(row["probability_yes"]) - outcome) ** 2
            market_brier = (float(row["market_probability"]) - outcome) ** 2
            maker_pnl = None
            if str(row["maker_status"]) == "FILLED" and row["maker_price_cents"] is not None:
                maker_price = int(row["maker_price_cents"])
                maker_pnl = (100 - maker_price if won else -maker_price) \
                    - int(row["maker_fee_cents"] or 0)
            self.connection.execute(
                "UPDATE trades SET status='SETTLED',result_yes=?,settled_at=?,taker_pnl_cents=?,"
                "brier=?,market_brier=?,maker_pnl_cents=? WHERE trade_id=?",
                (
                    int(result_yes), settled_at.isoformat(), taker_pnl, round(brier, 10),
                    round(market_brier, 10), maker_pnl, str(row["trade_id"]),
                ),
            )
            updated += 1
        self.connection.commit()
        return updated

    def settle_crypto_coverage_ticker(
        self, ticker: str, result_yes: bool, settled_at: datetime,
    ) -> int:
        rows = self.connection.execute(
            "SELECT coverage_id,side,entry_price_cents,fee_cents,probability_yes,"
            "market_probability FROM crypto_coverage_trades "
            "WHERE ticker=? AND status='OPEN'",
            (ticker,),
        ).fetchall()
        for row in rows:
            won = (str(row["side"]) == "yes" and result_yes) or (
                str(row["side"]) == "no" and not result_yes
            )
            price = int(row["entry_price_cents"])
            pnl = (100 - price if won else -price) - int(row["fee_cents"])
            outcome = 1.0 if result_yes else 0.0
            self.connection.execute(
                "UPDATE crypto_coverage_trades SET status='SETTLED',result_yes=?,"
                "settled_at=?,pnl_cents=?,brier=?,market_brier=? WHERE coverage_id=?",
                (
                    int(result_yes), settled_at.isoformat(), pnl,
                    round((float(row["probability_yes"]) - outcome) ** 2, 10),
                    round((float(row["market_probability"]) - outcome) ** 2, 10),
                    str(row["coverage_id"]),
                ),
            )
        self.connection.commit()
        return len(rows)

    def record_hourly_calibration_forecast(self, row: dict[str, Any]) -> bool:
        """Freeze the earliest clean hourly forecast for one asset/expiry.

        These rows are scored whether or not the calibrated lane places a paper
        trade.  The uniqueness constraint prevents later, easier snapshots from
        rewriting the probability that was actually knowable first.
        """
        cursor = self.connection.execute(
            "INSERT OR IGNORE INTO hourly_calibration_forecasts("
            "forecast_id,cycle_id,asset,event_cluster,ticker,observed_at,close_time,"
            "raw_probability,market_probability,calibrated_probability,uncertainty,"
            "model_share,calibration_version,profile_json)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                row["forecast_id"], row["cycle_id"], row["asset"],
                row["event_cluster"], row["ticker"], row["observed_at"],
                row["close_time"], row["raw_probability"],
                row["market_probability"], row["calibrated_probability"],
                row["uncertainty"], row["model_share"],
                row["calibration_version"], _json(row["profile"]),
            ),
        )
        self.connection.commit()
        return bool(cursor.rowcount)

    def unsettled_hourly_calibration_tickers(self) -> list[str]:
        return [
            str(row[0]) for row in self.connection.execute(
                "SELECT DISTINCT ticker FROM hourly_calibration_forecasts "
                "WHERE result_yes IS NULL ORDER BY ticker"
            )
        ]

    def settle_hourly_calibration_ticker(
        self, ticker: str, result_yes: bool, settled_at: datetime,
    ) -> int:
        rows = self.connection.execute(
            "SELECT forecast_id,calibrated_probability,market_probability "
            "FROM hourly_calibration_forecasts WHERE ticker=? AND result_yes IS NULL",
            (ticker,),
        ).fetchall()
        outcome = 1.0 if result_yes else 0.0
        for row in rows:
            brier = (float(row["calibrated_probability"]) - outcome) ** 2
            market_brier = (float(row["market_probability"]) - outcome) ** 2
            self.connection.execute(
                "UPDATE hourly_calibration_forecasts SET result_yes=?,settled_at=?,"
                "brier=?,market_brier=? WHERE forecast_id=?",
                (
                    int(result_yes), settled_at.isoformat(), round(brier, 10),
                    round(market_brier, 10), str(row["forecast_id"]),
                ),
            )
        self.connection.commit()
        return len(rows)

    def hourly_calibration_rows(self, *, settled_only: bool = True) -> list[dict[str, Any]]:
        query = "SELECT * FROM hourly_calibration_forecasts"
        if settled_only:
            query += " WHERE result_yes IS NOT NULL"
        query += " ORDER BY observed_at,forecast_id"
        return [dict(row) for row in self.connection.execute(query)]

    def hourly_calibration_counts(self) -> dict[str, int]:
        row = self.connection.execute(
            "SELECT COUNT(*),SUM(CASE WHEN result_yes IS NOT NULL THEN 1 ELSE 0 END),"
            "COUNT(DISTINCT CASE WHEN result_yes IS NOT NULL THEN event_cluster END) "
            "FROM hourly_calibration_forecasts"
        ).fetchone()
        return {
            "forecasts": int(row[0] or 0),
            "settled_forecasts": int(row[1] or 0),
            "settled_event_clusters": int(row[2] or 0),
        }

    def record_target_candidate_forecasts(
        self, rows: Sequence[dict[str, Any]],
    ) -> int:
        """Freeze the earliest scored snapshot for every listed target candidate."""
        inserted = 0
        for row in rows:
            cursor = self.connection.execute(
                "INSERT OR IGNORE INTO target_candidate_forecasts("
                "candidate_id,cycle_id,candidate_version,strategy,vertical,timeframe,asset,"
                "event_cluster,ticker,observed_at,close_time,target_json,side,rank_selected,"
                "eligible,reason,probability_yes,market_probability,uncertainty,"
                "conservative_ev_cents,entry_price_cents,fee_cents)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    row["candidate_id"], row["cycle_id"], TARGET_CANDIDATE_VERSION,
                    row["strategy"], _vertical_name(row["vertical"]), row["timeframe"],
                    row["asset"], row["event_cluster"], row["ticker"],
                    row["observed_at"], row["close_time"], _json(row["target"]),
                    row["side"], int(bool(row["rank_selected"])),
                    int(bool(row["eligible"])), str(row["reason"]),
                    row["probability_yes"], row["market_probability"],
                    row["uncertainty"], row["conservative_ev_cents"],
                    row["entry_price_cents"], row["fee_cents"],
                ),
            )
            inserted += int(bool(cursor.rowcount))
        self.connection.commit()
        return inserted

    def unsettled_target_candidate_tickers(self, now: datetime) -> list[str]:
        return [
            str(row[0]) for row in self.connection.execute(
                "SELECT DISTINCT ticker FROM target_candidate_forecasts "
                "WHERE result_yes IS NULL AND close_time<=? ORDER BY ticker",
                (now.isoformat(),),
            )
        ]

    def settle_target_candidate_ticker(
        self, ticker: str, result_yes: bool, settled_at: datetime,
    ) -> int:
        rows = self.connection.execute(
            "SELECT candidate_id,side,entry_price_cents,fee_cents,probability_yes,"
            "market_probability FROM target_candidate_forecasts "
            "WHERE ticker=? AND result_yes IS NULL",
            (ticker,),
        ).fetchall()
        outcome = 1.0 if result_yes else 0.0
        for row in rows:
            won = (str(row["side"]) == "yes" and result_yes) or (
                str(row["side"]) == "no" and not result_yes
            )
            price = int(row["entry_price_cents"])
            pnl = (100 - price if won else -price) - int(row["fee_cents"])
            brier = (float(row["probability_yes"]) - outcome) ** 2
            market_brier = (float(row["market_probability"]) - outcome) ** 2
            self.connection.execute(
                "UPDATE target_candidate_forecasts SET result_yes=?,settled_at=?,"
                "counterfactual_quote_pnl_cents=?,brier=?,market_brier=? "
                "WHERE candidate_id=?",
                (
                    int(result_yes), settled_at.isoformat(), pnl, round(brier, 10),
                    round(market_brier, 10), str(row["candidate_id"]),
                ),
            )
        self.connection.commit()
        return len(rows)

    def target_candidate_counts(self) -> dict[str, int]:
        row = self.connection.execute(
            "SELECT COUNT(*),SUM(CASE WHEN result_yes IS NOT NULL THEN 1 ELSE 0 END),"
            "COUNT(DISTINCT CASE WHEN result_yes IS NOT NULL THEN event_cluster END),"
            "SUM(CASE WHEN rank_selected=1 THEN 1 ELSE 0 END),"
            "SUM(CASE WHEN eligible=1 THEN 1 ELSE 0 END) "
            "FROM target_candidate_forecasts"
        ).fetchone()
        return {
            "forecasts": int(row[0] or 0),
            "settled_forecasts": int(row[1] or 0),
            "settled_event_clusters": int(row[2] or 0),
            "rank_selected_forecasts": int(row[3] or 0),
            "eligible_forecasts": int(row[4] or 0),
        }

    def target_candidate_regret_summary(self) -> dict[str, Any]:
        rows = self.connection.execute(
            "SELECT * FROM target_candidate_forecasts WHERE result_yes IS NOT NULL "
            "ORDER BY observed_at,candidate_id"
        ).fetchall()
        blocker_groups: dict[str, dict[str, Any]] = {}
        target_groups: dict[str, dict[str, Any]] = {}

        def add(group: dict[str, Any], row: sqlite3.Row) -> None:
            group.setdefault("forecasts", 0)
            group.setdefault("clusters", set())
            group.setdefault("wins", 0)
            group.setdefault("pnl", [])
            group.setdefault("brier_advantage", [])
            group["forecasts"] += 1
            group["clusters"].add(str(row["event_cluster"]))
            result_yes = bool(row["result_yes"])
            won = (str(row["side"]) == "yes" and result_yes) or (
                str(row["side"]) == "no" and not result_yes
            )
            group["wins"] += int(won)
            group["pnl"].append(float(row["counterfactual_quote_pnl_cents"] or 0))
            group["brier_advantage"].append(
                float(row["market_brier"] or 0) - float(row["brier"] or 0)
            )

        for row in rows:
            try:
                target = json.loads(str(row["target_json"]))
            except (TypeError, ValueError, json.JSONDecodeError):
                target = {}
            target_type = str(target.get("target_type") or "unknown")
            target_key = (
                f"{row['vertical']}:{row['asset']}:{row['timeframe']}:"
                f"{row['strategy']}:{target_type}"
            )
            add(target_groups.setdefault(target_key, {}), row)
            # A rank-selected target is still a rejected candidate when it
            # failed policy and the lane abstained. Excluding it would hide
            # the most important gate counterfactual from regret analysis.
            if not bool(row["rank_selected"]) or not bool(row["eligible"]):
                for blocker in target_candidate_blockers(
                    str(row["reason"]), eligible=bool(row["eligible"]),
                ):
                    blocker_key = (
                        f"{row['vertical']}:{row['asset']}:{row['timeframe']}:"
                        f"{row['strategy']}:{blocker}"
                    )
                    add(blocker_groups.setdefault(blocker_key, {}), row)

        def finish(groups: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
            output: list[dict[str, Any]] = []
            for key, group in groups.items():
                count = int(group["forecasts"])
                pnl = list(group["pnl"])
                advantages = list(group["brier_advantage"])
                output.append({
                    "group": key,
                    "settled_forecasts": count,
                    "event_clusters": len(group["clusters"]),
                    "counterfactual_wins": int(group["wins"]),
                    "counterfactual_win_rate": round(group["wins"] / count, 6),
                    "counterfactual_quote_pnl_cents": round(sum(pnl), 4),
                    "mean_brier_advantage_vs_market": (
                        round(statistics.fmean(advantages), 8) if advantages else None
                    ),
                })
            return sorted(
                output,
                key=lambda item: (-int(item["settled_forecasts"]), str(item["group"])),
            )

        counts = self.target_candidate_counts()
        return {
            "version": TARGET_CANDIDATE_VERSION,
            "counts": counts,
            "blocker_diagnostics": finish(blocker_groups),
            "target_type_diagnostics": finish(target_groups),
            "automatic_gate_tuning": False,
            "selection_use": "diagnostic_until_walk_forward_cluster_evidence",
            "counterfactual_is_fill_evidence": False,
            "counterfactual_basis": "earliest_live_top_ask_quote_one_contract_after_fee",
            "correlation_warning": "adjacent targets share event clusters and are not independent",
            "execution_authority": False,
            "capital_authority": False,
        }

    def selected_hourly_bootstrap_rows(self) -> list[dict[str, Any]]:
        """Legacy selected-trade evidence; diagnostic only, never activation data."""
        return [
            dict(row) for row in self.connection.execute(
                "SELECT * FROM trades WHERE vertical='CRYPTO' AND timeframe='1h' "
                "AND strategy='exploratory' AND status='SETTLED' "
                "ORDER BY created_at,trade_id"
            )
        ]

    def pending_maker_orders(self, now: datetime) -> list[dict[str, Any]]:
        return [
            dict(row) for row in self.connection.execute(
                "SELECT * FROM trades WHERE maker_status='PENDING' AND maker_expires_at<=?",
                (now.isoformat(),),
            )
        ]

    def update_maker(self, trade_id: str, status: str, witness: dict[str, Any]) -> None:
        self.connection.execute(
            "UPDATE trades SET maker_status=?,maker_fill_witness_json=? WHERE trade_id=?",
            (status, _json(witness), trade_id),
        )
        self.connection.commit()

    def recent_explanations(self, limit: int = 16) -> list[dict[str, Any]]:
        return [
            dict(row) for row in self.connection.execute(
                "SELECT created_at,strategy,vertical,timeframe,asset,action,ticker,explanation"
                " FROM observations ORDER BY rowid DESC LIMIT ?",
                (max(1, int(limit)),),
            )
        ]

    def cycle_target_selections(self, cycle_id: str) -> list[dict[str, Any]]:
        selections: list[dict[str, Any]] = []
        rows = self.connection.execute(
            "SELECT strategy,timeframe,asset,action,ticker,diagnostics_json "
            "FROM observations WHERE cycle_id=? AND vertical='CRYPTO' "
            "ORDER BY timeframe,asset,strategy",
            (cycle_id,),
        )
        for row in rows:
            try:
                diagnostics = json.loads(str(row["diagnostics_json"]))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            ladder = diagnostics.get("price_target_selection")
            if not isinstance(ladder, dict):
                continue
            selections.append({
                "strategy": str(row["strategy"]),
                "timeframe": str(row["timeframe"]),
                "asset": str(row["asset"]),
                "action": str(row["action"]),
                "ticker": row["ticker"],
                **ladder,
            })
        return selections

    def settled_target_performance(self) -> dict[str, dict[str, Any]]:
        """Descriptive target evidence only; never an automatic selection weight."""
        groups: dict[str, dict[str, Any]] = {}
        rows = self.connection.execute(
            "SELECT asset,timeframe,strategy,side,result_yes,taker_pnl_cents,brier,market_brier,"
            "market_snapshot_json FROM trades WHERE vertical='CRYPTO' AND status='SETTLED'"
        )
        for row in rows:
            try:
                snapshot = json.loads(str(row["market_snapshot_json"]))
                raw = snapshot.get("raw") or {}
            except (TypeError, ValueError, json.JSONDecodeError):
                raw = {}
            strike_type = str(raw.get("strike_type") or "unknown").lower()
            if str(row["timeframe"]) == "15m":
                target_type = "opening_reference_direction"
            else:
                target_type = {
                    "greater": "above",
                    "greater_or_equal": "above",
                    "less": "below",
                    "between": "bucket",
                }.get(strike_type, "unknown")
            key = f"{row['asset']}:{row['timeframe']}:{row['strategy']}:{target_type}"
            group = groups.setdefault(key, {
                "settled_trades": 0,
                "wins": 0,
                "pnl": [],
                "brier": [],
                "market_brier": [],
            })
            group["settled_trades"] += 1
            result_yes = bool(row["result_yes"])
            won = (str(row["side"]) == "yes" and result_yes) or (
                str(row["side"]) == "no" and not result_yes
            )
            group["wins"] += int(won)
            if row["taker_pnl_cents"] is not None:
                group["pnl"].append(float(row["taker_pnl_cents"]))
            if row["brier"] is not None:
                group["brier"].append(float(row["brier"]))
            if row["market_brier"] is not None:
                group["market_brier"].append(float(row["market_brier"]))
        summaries: dict[str, dict[str, Any]] = {}
        for key, group in sorted(groups.items()):
            count = int(group["settled_trades"])
            wins = int(group["wins"])
            pnl = group["pnl"]
            brier = group["brier"]
            market_brier = group["market_brier"]
            summaries[key] = {
                "settled_trades": count,
                "wins": wins,
                "win_rate": round(wins / count, 6) if count else None,
                "net_pnl_cents": round(sum(pnl), 4),
                "mean_brier": round(statistics.fmean(brier), 8) if brier else None,
                "market_mean_brier": (
                    round(statistics.fmean(market_brier), 8) if market_brier else None
                ),
                "selection_use": "diagnostic_only_until_independent_forward_evidence",
            }
        return summaries

    def lane_summary(
        self,
        strategy: str,
        timeframe: str | None,
        *,
        vertical: Vertical | str | None = None,
        since: str | None = None,
    ) -> dict[str, Any]:
        conditions = ["strategy=?"]
        params: list[Any] = [strategy]
        if vertical is not None:
            conditions.append("vertical=?")
            params.append(_vertical_name(vertical))
        if timeframe is not None:
            conditions.append("timeframe=?")
            params.append(timeframe)
        if since is not None:
            conditions.append("created_at>=?")
            params.append(since)
        where = " AND ".join(conditions)
        rows = self.connection.execute(
            f"SELECT * FROM trades WHERE {where} ORDER BY created_at,trade_id",  # noqa: S608
            params,
        ).fetchall()
        settled = [row for row in rows if str(row["status"]) == "SETTLED"]
        pnl = [int(row["taker_pnl_cents"]) for row in settled]
        mean_ci = _mean_ci95(pnl)
        running = peak = drawdown = 0
        for value in pnl:
            running += value
            peak = max(peak, running)
            drawdown = max(drawdown, peak - running)
        brier = statistics.fmean(float(row["brier"]) for row in settled) if settled else None
        market_brier = statistics.fmean(
            float(row["market_brier"]) for row in settled
        ) if settled else None
        skill = (
            1.0 - brier / market_brier if brier is not None and market_brier and market_brier > 0
            else None
        )
        maker_orders = [row for row in rows if row["maker_price_cents"] is not None]
        maker_filled = [row for row in maker_orders if str(row["maker_status"]) == "FILLED"]
        maker_blocked = [
            row for row in maker_orders if str(row["maker_status"]) == "BLOCKED_QUEUE"
        ]
        maker_pending = [row for row in maker_orders if str(row["maker_status"]) == "PENDING"]
        maker_expired = [
            row for row in maker_orders if str(row["maker_status"]) == "EXPIRED_UNFILLED"
        ]
        maker_settled = [row for row in settled if row["maker_pnl_cents"] is not None]
        return {
            "strategy": strategy,
            "vertical": _vertical_name(vertical) if vertical is not None else "all",
            "timeframe": timeframe or "all",
            "trades": len(rows),
            "settled_trades": len(settled),
            "event_clusters": len({str(row["event_cluster"]) for row in settled}),
            "wins": sum(value > 0 for value in pnl),
            "net_pnl_cents": sum(pnl),
            "mean_pnl_ci95": mean_ci,
            "max_drawdown_cents": drawdown,
            "brier": round(brier, 8) if brier is not None else None,
            "market_brier": round(market_brier, 8) if market_brier is not None else None,
            "brier_skill_vs_market": round(skill, 8) if skill is not None else None,
            "maker_orders": len(maker_orders),
            "maker_queue_snapshots": sum(bool(row["maker_queue_snapshot"]) for row in maker_orders),
            "maker_fills": len(maker_filled),
            "maker_blocked_queue": len(maker_blocked),
            "maker_pending": len(maker_pending),
            "maker_expired_unfilled": len(maker_expired),
            "maker_fill_rate": round(len(maker_filled) / len(maker_orders), 6)
            if maker_orders else None,
            "maker_settled_trades": len(maker_settled),
            "maker_net_pnl_cents": sum(int(row["maker_pnl_cents"]) for row in maker_settled),
        }

    def crypto_coverage_summary(self) -> dict[str, Any]:
        aggregate = self.connection.execute(
            "SELECT COUNT(*) decisions,"
            "SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END) open_decisions,"
            "SUM(CASE WHEN status='SETTLED' THEN 1 ELSE 0 END) settled_decisions,"
            "SUM(CASE WHEN status='SETTLED' AND pnl_cents>0 THEN 1 ELSE 0 END) wins,"
            "COALESCE(SUM(CASE WHEN status='SETTLED' THEN pnl_cents END),0) pnl_cents "
            "FROM crypto_coverage_trades"
        ).fetchone()
        lanes = [
            dict(row) for row in self.connection.execute(
                "SELECT timeframe,asset,COUNT(*) decisions,"
                "SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END) open_decisions,"
                "SUM(CASE WHEN status='SETTLED' THEN 1 ELSE 0 END) settled_decisions,"
                "SUM(CASE WHEN status='SETTLED' AND pnl_cents>0 THEN 1 ELSE 0 END) wins,"
                "COALESCE(SUM(CASE WHEN status='SETTLED' THEN pnl_cents END),0) pnl_cents "
                "FROM crypto_coverage_trades GROUP BY timeframe,asset "
                "ORDER BY timeframe,asset"
            )
        ]
        settled = int(aggregate["settled_decisions"] or 0)
        wins = int(aggregate["wins"] or 0)
        return {
            "decisions": int(aggregate["decisions"] or 0),
            "open_decisions": int(aggregate["open_decisions"] or 0),
            "settled_decisions": settled,
            "wins": wins,
            "win_rate": round(wins / settled, 6) if settled else None,
            "net_pnl_cents": int(aggregate["pnl_cents"] or 0),
            "lanes": lanes,
            "counts_toward_promotion": False,
            "counts_toward_readiness": False,
        }

    def recent_crypto_coverage_trades(
        self, *, status: str | None = None, limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM crypto_coverage_trades"
        params: list[Any] = []
        if status is not None:
            query += " WHERE status=?"
            params.append(status)
        query += " ORDER BY created_at DESC,coverage_id DESC LIMIT ?"
        params.append(max(1, int(limit)))
        values: list[dict[str, Any]] = []
        for row in self.connection.execute(query, params):
            value = dict(row)
            try:
                value["target"] = json.loads(str(value.pop("target_json")))
            except (TypeError, ValueError, json.JSONDecodeError):
                value["target"] = {}
                value.pop("target_json", None)
            values.append(value)
        return values

    def settled_trade_rows(
        self,
        strategy: str,
        timeframe: str,
        vertical: Vertical | str = Vertical.CRYPTO,
    ) -> list[dict[str, Any]]:
        return [
            dict(row) for row in self.connection.execute(
                "SELECT * FROM trades WHERE strategy=? AND vertical=? AND timeframe=? "
                "AND status='SETTLED'"
                " ORDER BY created_at,trade_id",
                (strategy, _vertical_name(vertical), timeframe),
            )
        ]

    def observation_reason_counts(
        self, vertical: Vertical | str | None = None,
    ) -> dict[str, int]:
        counts: dict[str, int] = {}
        query = "SELECT action,diagnostics_json FROM observations"
        params: tuple[Any, ...] = ()
        if vertical is not None:
            query += " WHERE vertical=?"
            params = (_vertical_name(vertical),)
        for row in self.connection.execute(query, params):
            try:
                reason = str((json.loads(str(row["diagnostics_json"])) or {}).get("reason") or row["action"])
            except (TypeError, json.JSONDecodeError):
                reason = str(row["action"])
            counts[reason] = counts.get(reason, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))

    def throughput_class_counts(
        self, vertical: Vertical | str | None = None,
    ) -> dict[str, int]:
        """Count observations by throughput class.

        Rows written before the class was recorded fall back to a derivation
        from their preserved market/candidate counts, so historical evidence
        is classified consistently with fresh cycles.
        """
        counts: dict[str, int] = {}
        query = "SELECT action,diagnostics_json FROM observations"
        params: tuple[Any, ...] = ()
        if vertical is not None:
            query += " WHERE vertical=?"
            params = (_vertical_name(vertical),)
        for row in self.connection.execute(query, params):
            try:
                diag = json.loads(str(row["diagnostics_json"])) or {}
            except (TypeError, json.JSONDecodeError):
                diag = {}
            cls = diag.get("throughput_class")
            if not cls:
                cls = classify_throughput(
                    action=str(row["action"]),
                    listed_markets=int(diag.get("listed_nearest_expiry_markets") or 0),
                    two_sided_markets=int(
                        diag.get("two_sided_markets")
                        if diag.get("two_sided_markets") is not None
                        else diag.get("nearest_expiry_markets") or 0
                    ),
                    forecasted_markets=int(diag.get("nearest_expiry_markets") or 0),
                    candidates=int(diag.get("candidate_markets") or 0),
                    eligible_candidates=int(diag.get("eligible_candidates") or 0),
                )
            counts[cls] = counts.get(cls, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))

    def paired_advantage(
        self,
        timeframe: str,
        strategy: str,
        *,
        vertical: Vertical | str = Vertical.CRYPTO,
        baseline: str = "incumbent",
        simulations: int = 1000,
    ) -> dict[str, Any] | None:
        if strategy == baseline:
            return None
        aggregates: dict[str, dict[str, int]] = {strategy: {}, baseline: {}}
        for lane in (strategy, baseline):
            for row in self.connection.execute(
                "SELECT event_cluster,SUM(taker_pnl_cents) FROM trades"
                " WHERE strategy=? AND vertical=? AND timeframe=? AND status='SETTLED'"
                " GROUP BY event_cluster",
                (lane, _vertical_name(vertical), timeframe),
            ):
                aggregates[lane][str(row[0])] = int(row[1] or 0)
        clusters = sorted(set(aggregates[strategy]) | set(aggregates[baseline]))
        if not clusters:
            return None
        differences = [
            aggregates[strategy].get(cluster, 0) - aggregates[baseline].get(cluster, 0)
            for cluster in clusters
        ]
        rng = random.Random(20260710)
        samples = [
            sum(rng.choice(differences) for _cluster in differences)
            for _ in range(max(200, int(simulations)))
        ]
        return {
            "strategy": strategy,
            "baseline": baseline,
            "vertical": _vertical_name(vertical),
            "observed_pnl_advantage_cents": sum(differences),
            "lower95": round(_percentile(samples, 0.025) or 0.0, 6),
            "upper95": round(_percentile(samples, 0.975) or 0.0, 6),
            "event_clusters": len(clusters),
            "method": "paired_event_cluster_bootstrap_total_pnl_advantage",
        }

    def execution_challengers(
        self, vertical: Vertical | str | None = None,
    ) -> dict[str, Any]:
        query = "SELECT * FROM trades WHERE status='SETTLED'"
        params: tuple[Any, ...] = ()
        if vertical is not None:
            query += " AND vertical=?"
            params = (_vertical_name(vertical),)
        query += " ORDER BY created_at,trade_id"
        rows = [
            dict(row) for row in self.connection.execute(query, params)
        ]
        candidates: list[dict[str, Any]] = []
        evaluated = 0
        for max_uncertainty in (0.15, 0.25, 0.35, 0.40):
            for min_ev in (0.0, 3.0, 5.0, 8.0):
                for max_price in (25, 50, 75, 90):
                    for max_queue in (0.0, 10.0, 25.0, 50.0):
                        evaluated += 1
                        selected = [
                            row for row in rows
                            if float(row["uncertainty"]) <= max_uncertainty
                            and float(row["conservative_ev_cents"]) >= min_ev
                            and int(row["taker_price_cents"]) <= max_price
                            and row["maker_queue_ahead"] is not None
                            and float(row["maker_queue_ahead"]) <= max_queue
                        ]
                        if len(selected) < 10:
                            continue
                        pnl = [int(row["taker_pnl_cents"]) for row in selected]
                        interval = _mean_ci95(pnl)
                        maker_orders = [row for row in selected if row["maker_price_cents"] is not None]
                        maker_fills = [
                            row for row in maker_orders if str(row["maker_status"]) == "FILLED"
                        ]
                        candidates.append({
                            "policy": {
                                "max_uncertainty": max_uncertainty,
                                "min_ev_cents": min_ev,
                                "max_entry_price_cents": max_price,
                                "max_queue_ahead": max_queue,
                            },
                            "settled_trades": len(selected),
                            "event_clusters": len({str(row["event_cluster"]) for row in selected}),
                            "net_pnl_cents": sum(pnl),
                            "mean_pnl_ci95": interval,
                            "maker_orders": len(maker_orders),
                            "maker_fills": len(maker_fills),
                            "maker_fill_rate": (
                                round(len(maker_fills) / len(maker_orders), 6)
                                if maker_orders else None
                            ),
                        })
        candidates.sort(key=lambda row: (
            float((row.get("mean_pnl_ci95") or {}).get("lower") or -1e9),
            int(row.get("net_pnl_cents") or 0),
            int(row.get("maker_fills") or 0),
        ), reverse=True)
        best = candidates[0] if candidates else None
        eligible = bool(
            best
            and int(best["settled_trades"]) >= 30
            and int(best["event_clusters"]) >= 10
            and int(best["net_pnl_cents"]) > 0
            and float((best.get("mean_pnl_ci95") or {}).get("lower") or -1) > 0
            and int(best["maker_fills"]) >= 20
        )
        return {
            "method": "forward_paper_execution_policy_grid",
            "vertical": _vertical_name(vertical) if vertical is not None else "all",
            "policies_evaluated": evaluated,
            "settled_input_trades": len(rows),
            "qualified_candidates": len(candidates),
            "top_candidates": candidates[:10],
            "eligible_for_bounded_main_shadow_review": eligible,
            "auto_apply": False,
            "execution_authority": False,
        }



def load_proposed_genome(
    path: Path | str = Path("runtime/autonomy/simulation_training_latest.json"),
) -> tuple[ResearchGenome, str]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        active = ((payload.get("evolution_lab") or {}).get("active_research_candidate") or {})
        genome = ResearchGenome.from_mapping(active.get("genome"))
        if genome is not None:
            return genome, str(active.get("genome_id") or genome.genome_id)
    except (OSError, TypeError, json.JSONDecodeError):
        pass
    return DEFAULT_GENOME, DEFAULT_GENOME.genome_id


def timeframe_state(state: dict[str, Any], timeframe: str) -> dict[str, Any]:
    frozen = dict(state)
    if timeframe == "15m":
        frozen["minute_closes"] = list(state.get("minute_closes") or [])[-180:]
        frozen["minute_volumes"] = list(state.get("minute_volumes") or [])[-180:]
        frozen["hourly_closes"] = list(state.get("hourly_closes") or [])[-2:]
    elif timeframe in {"1h", "1d", "1w"}:
        frozen["minute_closes"] = []
        frozen["minute_volumes"] = []
        frozen["book_imbalance"] = None
        frozen["microprice_basis_bps"] = None
        if timeframe == "1d":
            frozen["hourly_closes"] = list(state.get("hourly_closes") or [])[-168:]
        elif timeframe == "1w":
            frozen["hourly_closes"] = list(state.get("hourly_closes") or [])[-300:]
    else:
        raise ValueError(f"unsupported timeframe: {timeframe}")
    frozen["paper_timeframe"] = timeframe
    return frozen


def _maker_quote(market: MarketView, side: str) -> int | None:
    bid = market.yes_bid if side == "yes" else market.no_bid
    ask = market.yes_ask if side == "yes" else market.no_ask
    if bid is None or ask is None:
        return None
    price = int(bid) + 1 if int(ask) - int(bid) > 1 else int(bid)
    return price if 1 <= price < int(ask) else None


def maker_queue_snapshot(
    ticker: str,
    side: str,
    price_cents: int | None,
    fetch_orderbook: Callable[[str], dict[str, Any]],
) -> tuple[bool, float | None, str | None]:
    if price_cents is None:
        return False, None, "no_viable_maker_quote"
    try:
        book = fetch_orderbook(ticker)
        recognized = isinstance(book, dict) and any(
            key in book for key in ("yes", "no", "yes_dollars", "no_dollars")
        )
        if not recognized:
            return False, None, "unrecognized_orderbook_schema"
        levels = normalize_orderbook_levels(book, side)
        queue = sum(count for price, count in levels if int(price) == int(price_cents))
        return True, round(float(queue), 4), None
    except Exception as exc:
        return False, None, type(exc).__name__


def maker_fill_witness(
    order: dict[str, Any],
    trades: Iterable[dict[str, Any]],
) -> dict[str, Any] | None:
    side = str(order["side"])
    expected_taker_side = "ask" if side == "yes" else "bid"
    limit = int(order["maker_price_cents"])
    queue = float(order.get("maker_queue_ahead") or 0.0)
    start = _utc(order["created_at"])
    end = _utc(order["maker_expires_at"])
    exact_volume = 0.0
    trade_ids: list[str] = []
    last_at: str | None = None
    for trade in sorted(trades, key=lambda row: str(row.get("created_time") or "")):
        if trade.get("is_block_trade") is True:
            continue
        if str(trade.get("taker_book_side") or "").lower() != expected_taker_side:
            continue
        try:
            raw_price = trade.get("yes_price_dollars") if side == "yes" \
                else trade.get("no_price_dollars")
            price = int(round(float(raw_price) * 100))
            count = float(trade.get("count_fp") or trade.get("count") or 0)
            created = _utc(trade.get("created_time"))
        except (TypeError, ValueError):
            continue
        if not (start <= created <= end) or count <= 0:
            continue
        if price < limit:
            return {
                "reason": "public_trade_through",
                "trade_id": str(trade.get("trade_id") or ""),
                "trade_price_cents": price,
                "fill_witness_at": created.isoformat(),
            }
        if price == limit:
            exact_volume += count
            last_at = created.isoformat()
            if trade.get("trade_id"):
                trade_ids.append(str(trade["trade_id"]))
    if not bool(order.get("maker_queue_snapshot")):
        return None
    if exact_volume + 1e-9 < queue + 1.0:
        return None
    return {
        "reason": "public_trade_queue_consumed",
        "queue_ahead_contracts": queue,
        "matching_trade_volume": round(exact_volume, 4),
        "matching_trade_ids": trade_ids[:20],
        "fill_witness_at": last_at,
    }


ADAPTIVE_BAR_MIN_SETTLED = 30
ADAPTIVE_BAR_WINDOW = 100
ADAPTIVE_BAR_CAP_CENTS = 5.0


def adaptive_entry_bars(conn: sqlite3.Connection) -> dict[tuple[str, str], float]:
    """Per-(timeframe, strategy) self-tightening EV bar (Wave-23).

    Forensics: the 1h lanes bled (-849c across 353 settled) while 15m
    exploratory profited -- the same static entry policy cannot fit both.
    Each lane's bar now rises by its OWN realized mean per-trade loss over
    its most recent settled window (capped, >= a minimum sample), and simply
    stays at the policy default while the lane is healthy. It never loosens
    below baseline, forecasts/observations continue regardless (evidence
    accrual is untouched -- only paper ORDER flow tightens), and a lane that
    recovers on paper-worthy quotes re-earns its default bar as the window
    turns. Forced-coverage diagnostics are exempt at the call site.
    """
    rows = conn.execute(
        """
        SELECT timeframe, strategy, taker_pnl_cents FROM (
            SELECT timeframe, strategy, taker_pnl_cents,
                   ROW_NUMBER() OVER (
                       PARTITION BY timeframe, strategy
                       ORDER BY settled_at DESC
                   ) AS recency
            FROM trades
            WHERE taker_pnl_cents IS NOT NULL AND settled_at IS NOT NULL
        ) WHERE recency <= ?
        """,
        (ADAPTIVE_BAR_WINDOW,),
    ).fetchall()
    pnl: dict[tuple[str, str], list[float]] = {}
    for row in rows:
        pnl.setdefault(
            (str(row["timeframe"]), str(row["strategy"])), []
        ).append(float(row["taker_pnl_cents"]))
    bars: dict[tuple[str, str], float] = {}
    for key, values in pnl.items():
        if len(values) < ADAPTIVE_BAR_MIN_SETTLED:
            continue
        mean = sum(values) / len(values)
        if mean < 0.0:
            bars[key] = round(min(ADAPTIVE_BAR_CAP_CENTS, -mean), 2)
    return bars


def _candidate(
    market: MarketView,
    forecast: Forecast,
    technical: Signal | None,
    *,
    strategy: str,
    timeframe: str,
    genome: ResearchGenome,
    hourly_calibration: HourlyCalibrationProfile | None = None,
    entry_bar_adjustment: float = 0.0,
) -> dict[str, Any]:
    target = price_target_metadata(market, timeframe)
    if market.vertical is Vertical.CRYPTO and not bool(target["valid"]):
        return {
            "eligible": False,
            "reason": str(target["invalid_reason"]),
            "market": market,
            "target": target,
            "strategy": strategy,
            "timeframe": timeframe,
        }
    if forecast.market_implied_yes is None:
        return {
            "eligible": False,
            "reason": "missing_market_probability",
            "market": market,
            "target": target,
            "strategy": strategy,
            "timeframe": timeframe,
        }
    market_probability = float(forecast.market_implied_yes)
    if strategy == "incumbent":
        probability = float(forecast.probability_yes)
        uncertainty = float(forecast.uncertainty)
        edge_threshold = 0
        max_uncertainty = INCUMBENT_MAX_UNCERTAINTY
        max_price = INCUMBENT_MAX_ENTRY_CENTS
        min_ev = INCUMBENT_MIN_EV_CENTS
        blend = {"incumbent": 1.0, "timeframe_technical": 0.0}
    elif strategy == "exploratory":
        technical_probability = (
            float(technical.probability_yes) if technical is not None
            else float(forecast.probability_yes)
        )
        probability = min(0.995, max(
            0.005,
            0.70 * float(forecast.probability_yes) + 0.30 * technical_probability,
        ))
        technical_uncertainty = float(technical.uncertainty) if technical is not None else 0.35
        disagreement = abs(float(forecast.probability_yes) - technical_probability)
        uncertainty = min(0.50, max(
            0.08,
            math.sqrt((0.7 * forecast.uncertainty) ** 2 + (0.3 * technical_uncertainty) ** 2),
            disagreement,
        ))
        edge_threshold = 0
        max_uncertainty = 0.40
        max_price = 90
        min_ev = 0.0
        blend = {"incumbent": 0.70, "timeframe_technical": 0.30}
    elif strategy == HOURLY_CALIBRATED_STRATEGY:
        technical_probability = (
            float(technical.probability_yes) if technical is not None
            else float(forecast.probability_yes)
        )
        raw_probability = min(0.995, max(
            0.005,
            0.70 * float(forecast.probability_yes) + 0.30 * technical_probability,
        ))
        profile = hourly_calibration or fit_hourly_calibration_profile([])
        probability = min(0.995, max(
            0.005,
            market_probability + profile.model_share * (
                raw_probability - market_probability
            ),
        ))
        technical_uncertainty = float(technical.uncertainty) if technical is not None else 0.35
        disagreement = abs(float(forecast.probability_yes) - technical_probability)
        uncertainty = min(0.50, max(
            profile.uncertainty_floor,
            math.sqrt((0.7 * forecast.uncertainty) ** 2 + (0.3 * technical_uncertainty) ** 2),
            disagreement,
        ))
        edge_threshold = 3
        max_uncertainty = 0.35
        max_price = INCUMBENT_MAX_ENTRY_CENTS
        min_ev = PAPER_RESEARCH_MIN_EV_CENTS
        blend = {
            "market_anchor": round(1.0 - profile.model_share, 8),
            "hourly_raw_model": profile.model_share,
        }
    else:
        technical_probability = (
            float(technical.probability_yes) if technical is not None
            else float(forecast.probability_yes)
        )
        raw = 0.80 * float(forecast.probability_yes) + 0.20 * technical_probability
        probability = market_probability + genome.shrinkage * (raw - market_probability)
        probability = min(0.995, max(0.005, probability))
        technical_uncertainty = float(technical.uncertainty) if technical is not None else 0.35
        disagreement = abs(float(forecast.probability_yes) - technical_probability)
        uncertainty = min(0.50, max(
            0.08,
            math.sqrt((0.8 * forecast.uncertainty) ** 2 + (0.2 * technical_uncertainty) ** 2),
            disagreement,
        ))
        edge_threshold = genome.edge_threshold_cents
        max_uncertainty = genome.max_uncertainty
        max_price = min(INCUMBENT_MAX_ENTRY_CENTS, genome.max_entry_price_cents)
        min_ev = PAPER_RESEARCH_MIN_EV_CENTS
        blend = {"incumbent": 0.80, "timeframe_technical": 0.20}
        raw_probability = raw
    if strategy != HOURLY_CALIBRATED_STRATEGY:
        raw_probability = probability
    # Wave-23: the lane's self-learned bar (0.0 while healthy) tightens the
    # EV requirement by the lane's own realized bleed.
    min_ev += max(0.0, float(entry_bar_adjustment))
    raw_edge = abs(probability - market_probability) * 100.0
    options: list[dict[str, Any]] = []
    for side, win_probability, ask in (
        ("yes", probability, market.yes_ask),
        ("no", 1.0 - probability, market.no_ask),
    ):
        if ask is None:
            continue
        price = int(ask)
        fee = kalshi_taker_fee_cents(price, 1, market.ticker)
        conservative = max(0.005, win_probability - CONFIDENCE_HAIRCUT_SIGMAS * uncertainty)
        ev = conservative * 100.0 - price - fee
        options.append({
            "side": side,
            "price_cents": price,
            "fee_cents": fee,
            "win_probability": win_probability,
            "conservative_probability": conservative,
            "ev_cents": ev,
        })
    if not options:
        return {
            "eligible": False,
            "reason": "missing_executable_side_quote",
            "market": market,
            "target": target,
            "strategy": strategy,
            "timeframe": timeframe,
        }
    best = max(options, key=lambda row: float(row["ev_cents"]))
    blockers: list[str] = []
    if uncertainty > max_uncertainty:
        blockers.append(f"uncertainty {uncertainty:.3f}>{max_uncertainty:.3f}")
    if raw_edge < edge_threshold:
        blockers.append(f"model edge {raw_edge:.2f}c<{edge_threshold}c")
    if int(best["price_cents"]) > max_price:
        blockers.append(f"entry {best['price_cents']}c>{max_price}c")
    if float(best["ev_cents"]) < min_ev:
        blockers.append(f"conservative EV {best['ev_cents']:.2f}c<{min_ev:.2f}c")
    if (
        strategy == HOURLY_CALIBRATED_STRATEGY
        and (hourly_calibration is None or hourly_calibration.status != "ACTIVE_FORWARD_CALIBRATION")
    ):
        status = (
            hourly_calibration.status if hourly_calibration is not None
            else "MISSING_CALIBRATION_PROFILE"
        )
        blockers.append(f"hourly calibration status {status}")
    ranking_options: list[float] = []
    if strategy == HOURLY_CALIBRATED_STRATEGY:
        for side, win_probability, ask in (
            ("yes", raw_probability, market.yes_ask),
            ("no", 1.0 - raw_probability, market.no_ask),
        ):
            if ask is None:
                continue
            del side
            price = int(ask)
            fee = kalshi_taker_fee_cents(price, 1, market.ticker)
            conservative = max(0.005, win_probability - CONFIDENCE_HAIRCUT_SIGMAS * uncertainty)
            ranking_options.append(conservative * 100.0 - price - fee)
    return {
        "eligible": not blockers,
        "reason": "eligible" if not blockers else "; ".join(blockers),
        "market": market,
        "target": target,
        "forecast": forecast,
        "technical": technical,
        "strategy": strategy,
        "timeframe": timeframe,
        "probability_yes": probability,
        "raw_probability_yes": raw_probability,
        "market_probability": market_probability,
        "uncertainty": uncertainty,
        "raw_edge_cents": raw_edge,
        "best": best,
        "calibration_rank_ev_cents": (
            max(ranking_options) if ranking_options else float(best["ev_cents"])
        ),
        "policy": {
            "min_ev_cents": min_ev,
            "entry_bar_adjustment_cents": round(max(0.0, float(entry_bar_adjustment)), 2),
            "max_uncertainty": max_uncertainty,
            "max_entry_price_cents": max_price,
            "edge_threshold_cents": edge_threshold,
            "technical_blend": blend,
            "strike_selection": {
                "hourly_and_daily_adjustment_enabled": timeframe in {"1h", "1d"},
                "mode": "rank_all_contemporaneously_listed_nearest_expiry_targets",
                "objective": "fee_uncertainty_adjusted_conservative_ev",
                "listed_targets_only": True,
                "counterfactual_replay_requires_frozen_ladder": True,
                "settlement_informed_selection": False,
            },
            "genome": asdict(genome) if strategy == "recursive" else None,
            "exploratory_paper_only": strategy == "exploratory",
            "hourly_calibrated_paper_only": strategy == HOURLY_CALIBRATED_STRATEGY,
            "hourly_calibration": (
                hourly_calibration.to_dict()
                if strategy == HOURLY_CALIBRATED_STRATEGY and hourly_calibration is not None
                else None
            ),
        },
    }


def decision_explanation(candidate: dict[str, Any], asset: str) -> str:
    market = candidate.get("market")
    ticker = market.ticker if isinstance(market, MarketView) else "no-market"
    vertical = str(candidate.get("vertical") or "CRYPTO")
    prefix = (
        f"{vertical} {asset} {candidate.get('timeframe')} {candidate.get('strategy')}"
    )
    if candidate.get("best") is None:
        ladder = candidate.get("target_ladder") or {}
        inventory_text = (
            f" Reviewed {int(ladder.get('listed_targets_seen') or 0)} listed target(s); "
            f"{int(ladder.get('targets_evaluated') or 0)} had a complete scoring path."
        )
        return (
            f"{prefix} ABSTAIN. {candidate.get('reason', 'no candidate')}."
            f"{inventory_text} "
            "No paper order and no broker contact."
        )
    best = candidate["best"]
    action = f"BUY {str(best['side']).upper()}" if candidate.get("eligible") else "ABSTAIN"
    technical = candidate.get("technical")
    technical_text = (
        f" timeframe model={technical.probability_yes:.1%}"
        if technical is not None else " timeframe model unavailable"
    )
    target = candidate.get("target") or {}
    ladder = candidate.get("target_ladder") or {}
    target_text = str(target.get("label") or "unclassified target")
    ladder_text = (
        f" Selected from {int(ladder.get('targets_evaluated') or 0)} listed "
        f"nearest-expiry target(s), {int(ladder.get('eligible_targets') or 0)} eligible,"
        " using fee- and uncertainty-adjusted conservative EV;"
    )
    return (
        f"{prefix} {action} on {ticker} ({target_text}).{ladder_text} "
        f"Model YES={candidate['probability_yes']:.1%}, "
        f"market={candidate['market_probability']:.1%}, uncertainty={candidate['uncertainty']:.1%}, "
        f"absolute edge={candidate['raw_edge_cents']:.2f}c;{technical_text}. "
        f"Best side={best['side'].upper()} at the live top ask {best['price_cents']}c, "
        f"taker fee={best['fee_cents']}c, conservative probability="
        f"{best['conservative_probability']:.1%}, conservative EV={best['ev_cents']:.2f}c. "
        f"Decision rule: {candidate['reason']}. Paper-only; quote-executable simulation, "
        "not a witnessed market fill and never readiness evidence."
    )


def forced_crypto_coverage_decision(
    candidate: dict[str, Any], asset: str,
) -> dict[str, Any]:
    """Freeze one diagnostic paper side without relaxing the normal policy."""
    market = candidate.get("market")
    best = candidate.get("best")
    target = candidate.get("target") or {}
    if (
        not isinstance(market, MarketView)
        or not isinstance(best, dict)
        or not bool(target.get("valid"))
    ):
        raise ValueError("coverage decision requires a real valid quoted target")
    normal_reason = str(candidate.get("reason") or "unknown")
    side = str(best["side"])
    explanation = (
        f"CRYPTO {asset} {candidate.get('timeframe')} {CRYPTO_COVERAGE_LANE} "
        f"FORCED PAPER BUY {side.upper()} on {market.ticker} "
        f"({target.get('label') or 'listed target'}). "
        f"Model YES={float(candidate['probability_yes']):.1%}, "
        f"market={float(candidate['market_probability']):.1%}, "
        f"uncertainty={float(candidate['uncertainty']):.1%}; "
        f"entry={int(best['price_cents'])}c + {int(best['fee_cents'])}c fee, "
        f"conservative EV={float(best['ev_cents']):.2f}c. "
        f"Normal exploratory policy status: {normal_reason}. Forced solely to measure "
        "listed-target coverage, calibration, and failure modes; excluded from model "
        "promotion, readiness, execution, and capital evidence."
    )
    return {
        "coverage_version": CRYPTO_COVERAGE_VERSION,
        "lane": CRYPTO_COVERAGE_LANE,
        "timeframe": str(candidate["timeframe"]),
        "asset": str(asset),
        "event_cluster": str(candidate["event_cluster"]),
        "ticker": market.ticker,
        "side": side,
        "close_time": market.close_time,
        "probability_yes": round(float(candidate["probability_yes"]), 10),
        "market_probability": round(float(candidate["market_probability"]), 10),
        "uncertainty": round(float(candidate["uncertainty"]), 10),
        "conservative_ev_cents": round(float(best["ev_cents"]), 6),
        "entry_price_cents": int(best["price_cents"]),
        "fee_cents": int(best["fee_cents"]),
        "target": target,
        "normal_policy_eligible": bool(candidate.get("eligible")),
        "normal_policy_reason": normal_reason,
        "explanation": explanation,
        "counts_toward_promotion": False,
        "counts_toward_readiness": False,
        "broker_contacted": False,
    }


def _percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    index = (len(ordered) - 1) * max(0.0, min(1.0, fraction))
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    weight = index - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _fit_hourly_model_share(rows: Sequence[dict[str, Any]]) -> float:
    """Least-squares incremental model weight over the market, bounded safely."""
    numerator = 0.0
    denominator = 0.0
    for row in rows:
        raw = float(row["raw_probability"])
        market = float(row["market_probability"])
        outcome = float(row["result_yes"])
        residual = raw - market
        numerator += residual * (outcome - market)
        denominator += residual * residual
    if denominator <= 1e-12:
        return 0.0
    # Even a successful challenger must retain at least a 50% market anchor.
    return min(0.50, max(0.0, numerator / denominator))


def _cluster_bootstrap_mean_ci95(
    values: dict[str, list[float]], *, seed: int = 20260710,
) -> dict[str, Any] | None:
    clusters = [statistics.fmean(group) for group in values.values() if group]
    if not clusters:
        return None
    observed = statistics.fmean(clusters)
    if len(clusters) < 2:
        return {
            "lower": None,
            "mean": round(observed, 8),
            "upper": None,
            "event_clusters": len(clusters),
            "resamples": 0,
            "method": "event_cluster_bootstrap_mean_brier_advantage",
        }
    rng = random.Random(seed)
    samples = [
        statistics.fmean(rng.choice(clusters) for _ in clusters)
        for _ in range(1000)
    ]
    return {
        "lower": round(float(_percentile(samples, 0.025) or 0.0), 8),
        "mean": round(observed, 8),
        "upper": round(float(_percentile(samples, 0.975) or 0.0), 8),
        "event_clusters": len(clusters),
        "resamples": 1000,
        "method": "event_cluster_bootstrap_mean_brier_advantage",
    }


def fit_hourly_calibration_profile(
    rows: Sequence[dict[str, Any]],
) -> HourlyCalibrationProfile:
    """Fit only from previously settled, earliest-forward hourly forecasts.

    Activation is governed by an expanding-window walk-forward test.  The
    final weight may be fitted on all prior rows, but it remains zero until the
    strictly later validation predictions beat the market with a positive
    event-cluster lower bound.
    """
    settled = sorted(
        (dict(row) for row in rows if row.get("result_yes") is not None),
        key=lambda row: (str(row.get("observed_at") or ""), str(row.get("forecast_id") or "")),
    )
    clusters = {str(row["event_cluster"]) for row in settled}
    fitted_share = _fit_hourly_model_share(settled)
    forward_advantages: dict[str, list[float]] = {}
    forward_predictions: list[tuple[float, float]] = []
    for index in range(HOURLY_CALIBRATION_MIN_TRAIN, len(settled)):
        training = settled[:index]
        test = settled[index]
        share = _fit_hourly_model_share(training)
        raw = float(test["raw_probability"])
        market = float(test["market_probability"])
        outcome = float(test["result_yes"])
        calibrated = min(0.995, max(0.005, market + share * (raw - market)))
        advantage = (market - outcome) ** 2 - (calibrated - outcome) ** 2
        cluster = str(test["event_cluster"])
        forward_advantages.setdefault(cluster, []).append(advantage)
        forward_predictions.append((calibrated, outcome))
    interval = _cluster_bootstrap_mean_ci95(forward_advantages)
    forward_n = len(forward_predictions)
    forward_clusters = len(forward_advantages)
    lower = None if interval is None else interval.get("lower")
    enough = (
        len(settled) >= HOURLY_CALIBRATION_MIN_SETTLED
        and len(clusters) >= HOURLY_CALIBRATION_MIN_CLUSTERS
        and forward_n >= HOURLY_CALIBRATION_MIN_FORWARD
        and forward_clusters >= HOURLY_CALIBRATION_MIN_CLUSTERS
    )
    active = bool(
        enough and fitted_share > 0 and lower is not None and float(lower) > 0
    )
    if active:
        status = "ACTIVE_FORWARD_CALIBRATION"
    elif enough:
        status = "MARKET_ANCHORED_HOLD"
    else:
        status = "COLLECTING_FORWARD_EVIDENCE"
    if forward_predictions:
        rmse = math.sqrt(statistics.fmean(
            (probability - outcome) ** 2 for probability, outcome in forward_predictions
        ))
        uncertainty_floor = min(0.35, max(0.10, 0.50 * rmse))
    else:
        uncertainty_floor = 0.20
    return HourlyCalibrationProfile(
        version=HOURLY_CALIBRATION_VERSION,
        status=status,
        model_share=round(fitted_share if active else 0.0, 8),
        fitted_model_share=round(fitted_share, 8),
        uncertainty_floor=round(uncertainty_floor, 8),
        settled_forecasts=len(settled),
        event_clusters=len(clusters),
        walk_forward_forecasts=forward_n,
        walk_forward_clusters=forward_clusters,
        walk_forward_brier_advantage=(
            round(statistics.fmean(
                value for group in forward_advantages.values() for value in group
            ), 8)
            if forward_advantages else None
        ),
        walk_forward_advantage_ci95=interval,
        fitted_through=(str(settled[-1].get("settled_at")) if settled else None),
    )


def hourly_selected_bootstrap_diagnostic(
    rows: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Expose why the new lane starts held; never count selected rows as proof."""
    normalized = [
        {
            "raw_probability": float(row["probability_yes"]),
            "market_probability": float(row["market_probability"]),
            "result_yes": int(row["result_yes"]),
        }
        for row in rows if row.get("result_yes") is not None
    ]
    share = _fit_hourly_model_share(normalized)
    model_brier = (
        statistics.fmean(
            (row["raw_probability"] - row["result_yes"]) ** 2 for row in normalized
        ) if normalized else None
    )
    market_brier = (
        statistics.fmean(
            (row["market_probability"] - row["result_yes"]) ** 2 for row in normalized
        ) if normalized else None
    )
    return {
        "selection_biased": True,
        "counts_toward_activation": False,
        "source": "previously_selected_exploratory_hourly_trades",
        "settled_trades": len(normalized),
        "brier_optimal_model_share": round(share, 8),
        "model_brier": round(model_brier, 8) if model_brier is not None else None,
        "market_brier": round(market_brier, 8) if market_brier is not None else None,
    }


def compounding_proposal(
    rows: Sequence[dict[str, Any]],
    *,
    simulations: int = 1000,
    starting_bankroll_cents: int = 10_000,
    seed: int = 20260710,
) -> dict[str, Any]:
    if not rows:
        return {
            "available": False,
            "reason": "no settled paper trades",
            "capital_authority": False,
            "live_application": False,
        }
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["event_cluster"]), []).append(row)
    clusters = sorted(grouped)
    rng = random.Random(seed)
    results: list[dict[str, Any]] = []
    safe: list[float] = []
    for fraction in (0.0025, 0.005, 0.01, 0.02):
        for adverse_slippage in (0, 2, 5, 10):
            terminal: list[float] = []
            drawdowns: list[float] = []
            for _ in range(max(200, int(simulations))):
                sampled = [rng.choice(clusters) for _ in clusters]
                bankroll = float(starting_bankroll_cents)
                peak = bankroll
                max_drawdown = 0.0
                for cluster in sampled:
                    for row in grouped[cluster]:
                        cost = max(1.0, float(row["taker_price_cents"]) + float(row["taker_fee_cents"]))
                        stressed_pnl = float(row["taker_pnl_cents"]) - adverse_slippage
                        bankroll += bankroll * fraction * (stressed_pnl / cost)
                        bankroll = max(0.0, bankroll)
                        peak = max(peak, bankroll)
                        max_drawdown = max(max_drawdown, peak - bankroll)
                terminal.append(bankroll)
                drawdowns.append(max_drawdown)
            result = {
                "risk_fraction": fraction,
                "adverse_slippage_cents": adverse_slippage,
                "terminal_bankroll_cents": {
                    "p05": round(_percentile(terminal, 0.05) or 0, 2),
                    "median": round(_percentile(terminal, 0.50) or 0, 2),
                },
                "max_drawdown_cents_p95": round(_percentile(drawdowns, 0.95) or 0, 2),
                "probability_of_loss": round(
                    sum(value < starting_bankroll_cents for value in terminal) / len(terminal), 6,
                ),
            }
            results.append(result)
            if (
                adverse_slippage == 10
                and len(rows) >= 30
                and len(clusters) >= 10
                and result["terminal_bankroll_cents"]["p05"] >= starting_bankroll_cents
                and result["max_drawdown_cents_p95"] <= starting_bankroll_cents * 0.10
                and result["probability_of_loss"] <= 0.25
            ):
                safe.append(fraction)
    return {
        "available": True,
        "method": "event_cluster_bootstrap_fractional_bankroll",
        "settled_trades": len(rows),
        "event_clusters": len(clusters),
        "results": results,
        "highest_stress_safe_fraction": max(safe) if safe else None,
        "demotion_rule": "any negative drift or >10% drawdown proposes zero live fraction",
        "recommended_live_fraction": None,
        "capital_authority": False,
        "live_application": False,
    }


def _paper_gate(summary: dict[str, Any], compounding: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    if int(summary.get("settled_trades") or 0) < 30:
        blockers.append(f"settled paper trades {summary.get('settled_trades', 0)}/30")
    if int(summary.get("event_clusters") or 0) < 10:
        blockers.append(f"paper event clusters {summary.get('event_clusters', 0)}/10")
    if int(summary.get("net_pnl_cents") or 0) <= 0:
        blockers.append("paper net P&L is not positive")
    lower = (summary.get("mean_pnl_ci95") or {}).get("lower")
    if lower is None or float(lower) <= 0:
        blockers.append("paper mean P&L lower95 is not positive")
    skill = summary.get("brier_skill_vs_market")
    if skill is None or float(skill) <= 0:
        blockers.append("paper fill-conditioned Brier skill is not positive")
    if compounding.get("highest_stress_safe_fraction") is None:
        blockers.append("no paper fraction passes severe compounding stress")
    return {
        "paper_research_ready": not blockers,
        "blockers": blockers,
        "live_canary_ready": False,
        "live_canary_blocker": (
            "paper/simulated fills never authorize live trading; a later main-shadow experiment "
            "must earn witnessed fills and the production canary gate must independently pass"
        ),
        "execution_authority": False,
    }


def _forward_selection_gate(
    summary: dict[str, Any],
    compounding: dict[str, Any],
    advantage: dict[str, Any] | None,
    *,
    promotion_allowed: bool,
) -> dict[str, Any]:
    blockers: list[str] = []
    if int(summary.get("settled_trades") or 0) < 100:
        blockers.append(f"forward settled trades {summary.get('settled_trades', 0)}/100")
    if int(summary.get("event_clusters") or 0) < 10:
        blockers.append(f"forward event clusters {summary.get('event_clusters', 0)}/10")
    lower = (summary.get("mean_pnl_ci95") or {}).get("lower")
    if lower is None or float(lower) <= 0:
        blockers.append("forward mean P&L lower95 is not positive")
    skill = summary.get("brier_skill_vs_market")
    if skill is None or float(skill) <= 0:
        blockers.append("forward Brier skill versus market is not positive")
    if advantage is None or float(advantage.get("lower95") or 0) <= 0:
        blockers.append("paired cluster-bootstrap advantage versus incumbent is not positive")
    if compounding.get("highest_stress_safe_fraction") is None:
        blockers.append("severe compounding stress has no safe fraction")
    if not promotion_allowed:
        blockers.append("exploratory lane is diagnostic-only and cannot be promoted")
    return {
        "ready_for_explicit_main_shadow_review": not blockers,
        "blockers": blockers,
        "paired_advantage": advantage,
        "auto_apply": False,
        "execution_authority": False,
    }


class CryptoPaperTwin:
    def __init__(
        self,
        *,
        ledger: PaperTwinLedger | None = None,
        scanner: MarketScanner | None = None,
        hub: CryptoDataHub | None = None,
        trust: TrustSnapshot | None = None,
        fetch_result: Callable[[str], dict[str, Any]] | None = None,
        fetch_orderbook: Callable[[str], dict[str, Any]] | None = None,
        fetch_trades: Callable[[str, int, int], list[dict[str, Any]]] | None = None,
        now_fn: Callable[[], datetime] | None = None,
        proposed_genome_path: Path | str = Path(
            "runtime/autonomy/simulation_training_latest.json"
        ),
    ) -> None:
        self.ledger = ledger or PaperTwinLedger()
        self.scanner = scanner or MarketScanner(
            watchlist=list(WATCHLIST),
            verticals={Vertical.CRYPTO},
        )
        self.hub = hub or CryptoDataHub()
        self.trust = trust or TrustSnapshot.from_database("runtime/autonomy/ledger.db")
        self.fetch_result = fetch_result or default_fetch_market_result
        self.fetch_orderbook = fetch_orderbook or default_fetch_orderbook
        self.fetch_trades = fetch_trades or default_fetch_trades
        self.now_fn = now_fn or _now
        self.proposed_genome_path = Path(proposed_genome_path)

    def close(self) -> None:
        self.ledger.close()

    def _base_forecasts(
        self, markets: Sequence[MarketView], states: dict[str, dict[str, Any]],
    ) -> tuple[dict[str, Forecast], dict[str, dict[str, Any]]]:
        flat = CryptoSpotVolSignal(
            fetch_spot_and_vol=lambda asset: (
                float(states[asset]["spot"]),
                self.hub.flat_spot_and_vol(asset)[1],
            )
        )
        ewma = CryptoEwmaTailSignal(
            fetch_spot_and_vol=lambda asset: (
                float(states[asset]["spot"]),
                self.hub.ewma_spot_and_vol(asset)[1],
            )
        )
        prior = MarketPriorSignal()
        forecaster = EnsembleForecaster(self.trust)  # type: ignore[arg-type]
        forecasts: dict[str, Forecast] = {}
        source_features: dict[str, dict[str, Any]] = {}
        for market in markets:
            if market.vertical is not Vertical.CRYPTO:
                continue
            signals: list[Signal] = []
            for source in (prior, flat, ewma):
                try:
                    if source.applicable(market):
                        signal = source.generate(market)
                        if signal is not None:
                            signals.append(signal)
                except Exception:
                    continue
            forecast = forecaster.fuse(market, signals)
            if forecast is not None:
                forecasts[market.ticker] = forecast
                source_features[market.ticker] = {
                    signal.source: signal.features for signal in signals
                }
        return forecasts, source_features

    def _technical(
        self,
        market: MarketView,
        timeframe: str,
        states: dict[str, dict[str, Any]],
    ) -> Signal | None:
        if market.vertical is not Vertical.CRYPTO:
            return None
        source = CryptoTechnicalCompositeSignal(
            fetch_state=lambda asset: timeframe_state(states[asset], timeframe),
        )
        try:
            return source.generate(market)
        except Exception:
            return None

    def _markets_for_asset(
        self,
        markets: Sequence[MarketView],
        asset: str,
        timeframe: str,
        now: datetime,
        vertical: Vertical = Vertical.CRYPTO,
    ) -> list[MarketView]:
        candidates: list[tuple[datetime, MarketView]] = []
        for market in markets:
            cohort = cohort_for_market(market)
            if cohort is None:
                continue
            if (
                cohort.vertical is not vertical
                or cohort.asset != asset
                or cohort.timeframe != timeframe
            ):
                continue
            try:
                close = _utc(market.close_time)
            except (TypeError, ValueError):
                continue
            minutes = (close - now).total_seconds() / 60.0
            if not (
                MIN_MINUTES_TO_CLOSE[timeframe]
                <= minutes
                <= MAX_MINUTES_TO_CLOSE[timeframe]
            ):
                continue
            candidates.append((close, market))
        if not candidates:
            return []
        nearest = min(close for close, _market in candidates)
        return [market for close, market in candidates if close == nearest]

    def _reconcile_settlements(
        self, now: datetime, errors: list[str],
    ) -> tuple[int, int, int, int]:
        trade_updates = 0
        coverage_updates = 0
        calibration_updates = 0
        target_candidate_updates = 0
        tickers = sorted(
            set(self.ledger.open_tickers())
            | set(self.ledger.open_crypto_coverage_tickers())
            | set(self.ledger.unsettled_hourly_calibration_tickers())
            | set(self.ledger.unsettled_target_candidate_tickers(now))
        )
        for ticker in tickers:
            try:
                market = self.fetch_result(ticker)
                result = str(market.get("result") or "").lower()
                if result in {"yes", "no"}:
                    resolved_yes = result == "yes"
                    trade_updates += self.ledger.settle_ticker(ticker, resolved_yes, now)
                    coverage_updates += self.ledger.settle_crypto_coverage_ticker(
                        ticker, resolved_yes, now,
                    )
                    calibration_updates += self.ledger.settle_hourly_calibration_ticker(
                        ticker, resolved_yes, now,
                    )
                    target_candidate_updates += (
                        self.ledger.settle_target_candidate_ticker(
                            ticker, resolved_yes, now,
                        )
                    )
            except Exception as exc:
                errors.append(f"settlement:{ticker}:{type(exc).__name__}")
        return (
            trade_updates, coverage_updates, calibration_updates,
            target_candidate_updates,
        )

    def _reconcile_makers(self, now: datetime, errors: list[str]) -> int:
        updated = 0
        for order in self.ledger.pending_maker_orders(now):
            try:
                trades = self.fetch_trades(
                    str(order["ticker"]),
                    int(_utc(order["created_at"]).timestamp()),
                    int(_utc(order["maker_expires_at"]).timestamp()),
                )
                witness = maker_fill_witness(order, trades)
                if witness is not None:
                    self.ledger.update_maker(str(order["trade_id"]), "FILLED", witness)
                else:
                    self.ledger.update_maker(
                        str(order["trade_id"]), "EXPIRED_UNFILLED",
                        {"reason": "no_public_trade_fill_witness"},
                    )
                updated += 1
            except Exception as exc:
                errors.append(f"maker:{order['ticker']}:{type(exc).__name__}")
        return updated

    def run_cycle(self) -> dict[str, Any]:
        now = self.now_fn().astimezone(timezone.utc)
        cycle_id = self.ledger.start_cycle(now)
        errors: list[str] = []
        observations_written = trades_opened = calibration_forecasts_recorded = 0
        lane_trades_quarantined = 0
        target_candidate_forecasts_recorded = 0
        coverage_trades_recorded = 0
        coverage_scope_targets: dict[str, int] = {
            f"{asset}:{timeframe}": 0
            for asset in ASSETS for timeframe in TIMEFRAMES
        }
        coverage_scope_recorded: dict[str, int] = dict.fromkeys(
            coverage_scope_targets, 0,
        )
        try:
            self.hub.clear()
            maker_updates = self._reconcile_makers(now, errors)
            (
                settlements,
                coverage_settlements,
                hourly_calibration_settlements,
                target_candidate_settlements,
            ) = self._reconcile_settlements(now, errors)
            hourly_calibration = fit_hourly_calibration_profile(
                self.ledger.hourly_calibration_rows()
            )
            markets = self.scanner.scan()
            states: dict[str, dict[str, Any]] = {}
            for asset in ASSETS:
                try:
                    states[asset] = self.hub.state(asset)
                except Exception as exc:
                    errors.append(f"state:{asset}:{type(exc).__name__}")
            proposed, proposed_id = load_proposed_genome(self.proposed_genome_path)
            epoch = self.ledger.ensure_epoch(
                proposed, now=now, proposed_id=proposed_id,
            )
            active_genome = ResearchGenome.from_mapping(epoch.get("genome")) or proposed
            # Wave-23: each (timeframe, strategy) lane learns its own entry
            # bar from its own recent settled record -- a bleeding lane
            # raises its EV requirement by its realized per-trade loss
            # (capped), a healthy lane keeps the policy default. Failure
            # converts to selectivity instead of repeating itself.
            try:
                entry_bars = adaptive_entry_bars(self.ledger.connection)
            except Exception:
                entry_bars = {}
            self._entry_bars = entry_bars
            listed_compatible_markets = [
                market for market in markets
                if cohort_for_market(market) is not None
            ]
            eligible_markets = [
                market for market in listed_compatible_markets
                if None not in (
                    market.yes_bid, market.yes_ask, market.no_bid, market.no_ask,
                )
            ]
            forecasts, source_features = self._base_forecasts(eligible_markets, states)
            for cohort in COHORTS:
                vertical = cohort.vertical
                timeframe = cohort.timeframe
                asset = cohort.asset
                listed_lane_markets = self._markets_for_asset(
                    listed_compatible_markets, asset, timeframe, now, vertical,
                )
                lane_markets = [
                    market for market in listed_lane_markets
                    if market.ticker in forecasts
                ]
                target_inventory = price_target_inventory(
                    listed_lane_markets, timeframe,
                )
                cluster = event_cluster(
                    vertical, timeframe, asset, listed_lane_markets[0].close_time,
                ) if listed_lane_markets else None
                if vertical is Vertical.CRYPTO and cluster is not None:
                    scope_key = f"{asset}:{timeframe}"
                    for market in lane_markets:
                        forecast = forecasts.get(market.ticker)
                        if forecast is None:
                            continue
                        coverage_candidate = _candidate(
                            market,
                            forecast,
                            self._technical(market, timeframe, states),
                            strategy="exploratory",
                            timeframe=timeframe,
                            genome=active_genome,
                        )
                        coverage_candidate["vertical"] = vertical.value
                        coverage_candidate["event_cluster"] = cluster
                        if (
                            not isinstance(coverage_candidate.get("best"), dict)
                            or not bool((coverage_candidate.get("target") or {}).get("valid"))
                        ):
                            continue
                        coverage_scope_targets[scope_key] += 1
                        forced = forced_crypto_coverage_decision(
                            coverage_candidate, asset,
                        )
                        recorded = int(
                            self.ledger.record_crypto_coverage_trade({
                                **forced,
                                "coverage_id": f"crypto-coverage-{uuid.uuid4().hex[:16]}",
                                "cycle_id": cycle_id,
                                "created_at": now.isoformat(),
                            })
                        )
                        coverage_trades_recorded += recorded
                        coverage_scope_recorded[scope_key] += recorded
                for strategy in strategies_for(vertical, timeframe):
                        strategy_cluster = (
                            hourly_calibration_event_cluster(
                                listed_lane_markets[0].close_time,
                            )
                            if (
                                strategy == HOURLY_CALIBRATED_STRATEGY
                                and listed_lane_markets
                            )
                            else cluster
                        )
                        candidates: list[dict[str, Any]] = []
                        for market in lane_markets:
                            forecast = forecasts.get(market.ticker)
                            if forecast is None:
                                continue
                            technical = self._technical(market, timeframe, states)
                            candidates.append(_candidate(
                                market, forecast, technical, strategy=strategy,
                                timeframe=timeframe, genome=active_genome,
                                hourly_calibration=(
                                    hourly_calibration
                                    if strategy == HOURLY_CALIBRATED_STRATEGY else None
                                ),
                                entry_bar_adjustment=entry_bars.get(
                                    (timeframe, strategy), 0.0),
                            ))
                            candidates[-1]["vertical"] = vertical.value
                        if candidates:
                            best_candidate, target_ladder = select_price_target(
                                candidates, strategy,
                            )
                        else:
                            reason = (
                                "no directly model-compatible listed market for requested cohort"
                                if not cohort.series
                                else "no open two-sided nearest-expiry market with a complete forecast"
                            )
                            best_candidate = {
                                "eligible": False,
                                "reason": reason,
                                "strategy": strategy,
                                "timeframe": timeframe,
                                "vertical": vertical.value,
                            }
                            target_ladder = {
                                "selection_version": "nearest-expiry-target-ladder-v1",
                                "selection_objective": (
                                    "highest fee-and-uncertainty-adjusted conservative EV "
                                    "among policy-eligible targets"
                                ),
                                "targets_evaluated": 0,
                                "valid_targets": 0,
                                "eligible_targets": 0,
                                "target_type_counts": {},
                                "boundary_range": {"minimum": None, "maximum": None},
                                "selected_ticker": None,
                                "selected_target": None,
                                "ranked_candidates": [],
                                "ranked_candidates_persisted": 0,
                                "ranked_candidates_truncated": 0,
                                "one_position_per_asset_expiry": True,
                                "optimizes_raw_win_rate": False,
                                "strike_adjustment_enabled": timeframe in {"1h", "1d"},
                                "strike_adjustment_authority": (
                                    "choose_among_contemporaneously_listed_targets_only"
                                ),
                                "counterfactual_replay_requires_frozen_ladder": True,
                                "settlement_informed_selection": False,
                            }
                        target_ladder.update(target_inventory)
                        target_ladder["listed_targets_excluded_from_scoring"] = max(
                            0,
                            int(target_inventory["listed_targets_seen"])
                            - int(target_ladder["targets_evaluated"]),
                        )
                        target_ladder["scoring_exclusion_rule"] = (
                            "missing complete two-sided probability anchor, complete forecast, "
                            "or valid strike; never invent a tradable quote"
                        )
                        best_candidate["target_ladder"] = target_ladder
                        if strategy_cluster is not None:
                            candidate_forecasts: list[dict[str, Any]] = []
                            for candidate in candidates:
                                candidate_market = candidate.get("market")
                                candidate_best = candidate.get("best")
                                if (
                                    not isinstance(candidate_market, MarketView)
                                    or not isinstance(candidate_best, dict)
                                    or candidate.get("probability_yes") is None
                                    or candidate.get("market_probability") is None
                                    or candidate.get("uncertainty") is None
                                ):
                                    continue
                                candidate_forecasts.append({
                                    "candidate_id": f"tcand-{uuid.uuid4().hex[:16]}",
                                    "cycle_id": cycle_id,
                                    "strategy": strategy,
                                    "vertical": vertical,
                                    "timeframe": timeframe,
                                    "asset": asset,
                                    "event_cluster": strategy_cluster,
                                    "ticker": candidate_market.ticker,
                                    "observed_at": now.isoformat(),
                                    "close_time": candidate_market.close_time,
                                    "target": candidate.get("target") or {},
                                    "side": str(candidate_best["side"]),
                                    "rank_selected": candidate is best_candidate,
                                    "eligible": bool(candidate.get("eligible")),
                                    "reason": str(candidate.get("reason") or "unknown"),
                                    "probability_yes": round(
                                        float(candidate["probability_yes"]), 10,
                                    ),
                                    "market_probability": round(
                                        float(candidate["market_probability"]), 10,
                                    ),
                                    "uncertainty": round(
                                        float(candidate["uncertainty"]), 10,
                                    ),
                                    "conservative_ev_cents": round(
                                        float(candidate_best["ev_cents"]), 6,
                                    ),
                                    "entry_price_cents": int(
                                        candidate_best["price_cents"]
                                    ),
                                    "fee_cents": int(candidate_best["fee_cents"]),
                                })
                            target_candidate_forecasts_recorded += (
                                self.ledger.record_target_candidate_forecasts(
                                    candidate_forecasts,
                                )
                            )
                        explanation = decision_explanation(best_candidate, asset)
                        action = (
                            f"BUY_{str(best_candidate['best']['side']).upper()}"
                            if best_candidate.get("eligible") else "ABSTAIN"
                        )
                        market = best_candidate.get("market")
                        listing_duration_hours = (
                            market_listing_duration_hours(market)
                            if isinstance(market, MarketView) else None
                        )
                        observation_id = self.ledger.record_observation({
                            "cycle_id": cycle_id,
                            "epoch_id": epoch.get("epoch_id") if strategy == "recursive" else None,
                            "strategy": strategy,
                            "vertical": vertical,
                            "timeframe": timeframe,
                            "bucket_start": bucket_start(now, timeframe),
                            "asset": asset,
                            "event_cluster": strategy_cluster,
                            "ticker": market.ticker if isinstance(market, MarketView) else None,
                            "action": action,
                            "explanation": explanation,
                            "diagnostics": {
                                "reason": best_candidate.get("reason"),
                                "candidate_markets": len(candidates),
                                "nearest_expiry_markets": len(lane_markets),
                                "listed_nearest_expiry_markets": len(listed_lane_markets),
                                "two_sided_markets": sum(
                                    market_is_two_sided(m) for m in listed_lane_markets
                                ),
                                "throughput_class": classify_throughput(
                                    action=action,
                                    listed_markets=len(listed_lane_markets),
                                    two_sided_markets=sum(
                                        market_is_two_sided(m) for m in listed_lane_markets
                                    ),
                                    forecasted_markets=len(lane_markets),
                                    candidates=len(candidates),
                                    eligible_candidates=sum(
                                        bool(row.get("eligible")) for row in candidates
                                    ),
                                ),
                                "eligible_candidates": sum(bool(row.get("eligible")) for row in candidates),
                                "contract_family": (
                                    "15m_direction" if timeframe == "15m"
                                    else "terminal_price"
                                ),
                                "listed_series": list(cohort.series),
                                "listing_duration_hours": listing_duration_hours,
                                "price_target_selection": target_ladder,
                                "paper_only": True,
                                "lane_quarantined": lane_quarantined(
                                    vertical, strategy, timeframe,
                                ),
                            },
                            "created_at": now.isoformat(),
                        })
                        observations_written += 1
                        if (
                            strategy == HOURLY_CALIBRATED_STRATEGY
                            and isinstance(market, MarketView)
                            and strategy_cluster is not None
                            and best_candidate.get("raw_probability_yes") is not None
                        ):
                            calibration_forecasts_recorded += int(
                                self.ledger.record_hourly_calibration_forecast({
                                    "forecast_id": f"hcal-{uuid.uuid4().hex[:16]}",
                                    "cycle_id": cycle_id,
                                    "asset": asset,
                                    "event_cluster": strategy_cluster,
                                    "ticker": market.ticker,
                                    "observed_at": now.isoformat(),
                                    "close_time": market.close_time,
                                    "raw_probability": round(
                                        float(best_candidate["raw_probability_yes"]), 10,
                                    ),
                                    "market_probability": round(
                                        float(best_candidate["market_probability"]), 10,
                                    ),
                                    "calibrated_probability": round(
                                        float(best_candidate["probability_yes"]), 10,
                                    ),
                                    "uncertainty": round(
                                        float(best_candidate["uncertainty"]), 10,
                                    ),
                                    "model_share": hourly_calibration.model_share,
                                    "calibration_version": hourly_calibration.version,
                                    "profile": hourly_calibration.to_dict(),
                                })
                            )
                        if not best_candidate.get("eligible") or not isinstance(market, MarketView):
                            continue
                        if lane_quarantined(vertical, strategy, timeframe):
                            # Quarantined lane: the observation above is the
                            # grading emission; no paper capital is spent.
                            lane_trades_quarantined += 1
                            continue
                        assert strategy_cluster is not None
                        if self.ledger.has_lane_trade(
                            strategy, timeframe, asset, strategy_cluster, vertical,
                        ):
                            continue
                        best = best_candidate["best"]
                        side = str(best["side"])
                        maker_price = _maker_quote(market, side)
                        queue_available, queue_ahead, queue_error = maker_queue_snapshot(
                            market.ticker, side, maker_price, self.fetch_orderbook,
                        )
                        if maker_price is None:
                            maker_status = "NO_VIABLE_QUOTE"
                        elif queue_available and float(queue_ahead or 0) > MAX_QUEUE_AHEAD:
                            maker_status = "BLOCKED_QUEUE"
                        else:
                            maker_status = "PENDING"
                        technical = best_candidate.get("technical")
                        features = {
                            "vertical": vertical.value,
                            "timeframe": timeframe,
                            "contract_family": (
                                "15m_direction" if timeframe == "15m"
                                else "terminal_price"
                            ),
                            "technical": technical.features if technical is not None else None,
                            "source_features": source_features.get(market.ticker, {}),
                            "listing_duration_hours": listing_duration_hours,
                            "price_target": best_candidate.get("target"),
                            "target_selection": {
                                key: target_ladder.get(key)
                                for key in (
                                    "selection_version", "selection_objective",
                                    "targets_evaluated", "valid_targets",
                                    "eligible_targets", "target_type_counts",
                                    "selected_ticker", "selected_target",
                                    "one_position_per_asset_expiry",
                                    "optimizes_raw_win_rate",
                                    "strike_adjustment_enabled",
                                    "strike_adjustment_authority",
                                    "counterfactual_replay_requires_frozen_ladder",
                                    "settlement_informed_selection",
                                )
                            },
                            "queue_snapshot_error": queue_error,
                            "spot_state": {
                                key: states.get(asset, {}).get(key)
                                for key in (
                                    "spot", "coinbase_spot", "kraken_spot", "dvol",
                                    "venue_divergence_bps", "book_imbalance",
                                    "microprice_basis_bps", "coinbase_minute_age_s",
                                    "coinbase_hourly_age_s",
                                )
                            },
                        }
                        recorded = self.ledger.record_trade({
                            "trade_id": f"trade-{uuid.uuid4().hex[:16]}",
                            "observation_id": observation_id,
                            "epoch_id": epoch.get("epoch_id") if strategy == "recursive" else None,
                            "strategy": strategy,
                            "vertical": vertical,
                            "timeframe": timeframe,
                            "asset": asset,
                            "event_cluster": strategy_cluster,
                            "ticker": market.ticker,
                            "side": side,
                            "created_at": now.isoformat(),
                            "close_time": market.close_time,
                            "probability_yes": round(float(best_candidate["probability_yes"]), 10),
                            "market_probability": round(float(best_candidate["market_probability"]), 10),
                            "uncertainty": round(float(best_candidate["uncertainty"]), 10),
                            "edge_cents": round(float(best_candidate["raw_edge_cents"]), 6),
                            "conservative_ev_cents": round(float(best["ev_cents"]), 6),
                            "taker_price_cents": int(best["price_cents"]),
                            "taker_fee_cents": int(best["fee_cents"]),
                            "explanation": explanation,
                            "sources": best_candidate["forecast"].sources_used,
                            "features": features,
                            "market_snapshot": {
                                "ticker": market.ticker,
                                "title": market.title,
                                "vertical": vertical.value,
                                "close_time": market.close_time,
                                "yes_bid": market.yes_bid,
                                "yes_ask": market.yes_ask,
                                "no_bid": market.no_bid,
                                "no_ask": market.no_ask,
                                "volume": market.volume,
                                "price_target": best_candidate.get("target"),
                                "raw": market.raw,
                            },
                            "policy": best_candidate["policy"],
                            "maker_price_cents": maker_price,
                            "maker_fee_cents": kalshi_maker_fee_cents(
                                int(maker_price), 1, market.ticker,
                            ) if maker_price is not None else None,
                            "maker_queue_ahead": queue_ahead,
                            "maker_queue_snapshot": queue_available,
                            "maker_status": maker_status,
                            "maker_expires_at": (
                                now + timedelta(seconds=MAKER_TTL_SECONDS)
                            ).isoformat() if maker_status == "PENDING" else None,
                        })
                        trades_opened += int(recorded)
            report = self.build_report(
                now=now,
                cycle_id=cycle_id,
                markets_seen=len(markets),
                observations_written=observations_written,
                trades_opened=trades_opened,
                settlements_recorded=settlements,
                coverage_settlements_recorded=coverage_settlements,
                coverage_trades_recorded=coverage_trades_recorded,
                coverage_scope_targets=coverage_scope_targets,
                coverage_scope_recorded=coverage_scope_recorded,
                maker_updates=maker_updates,
                hourly_calibration_settlements=hourly_calibration_settlements,
                calibration_forecasts_recorded=calibration_forecasts_recorded,
                target_candidate_settlements=target_candidate_settlements,
                target_candidate_forecasts_recorded=(
                    target_candidate_forecasts_recorded
                ),
                errors=errors,
                lane_trades_quarantined=lane_trades_quarantined,
            )
        except Exception as exc:
            errors.append(f"cycle:{type(exc).__name__}:{str(exc)[:160]}")
            report = self.build_report(
                now=now,
                cycle_id=cycle_id,
                markets_seen=0,
                observations_written=observations_written,
                trades_opened=trades_opened,
                settlements_recorded=0,
                coverage_settlements_recorded=0,
                coverage_trades_recorded=coverage_trades_recorded,
                coverage_scope_targets=coverage_scope_targets,
                coverage_scope_recorded=coverage_scope_recorded,
                maker_updates=0,
                hourly_calibration_settlements=0,
                calibration_forecasts_recorded=calibration_forecasts_recorded,
                target_candidate_settlements=0,
                target_candidate_forecasts_recorded=(
                    target_candidate_forecasts_recorded
                ),
                errors=errors,
                failed=True,
                lane_trades_quarantined=lane_trades_quarantined,
            )
        self.ledger.finish_cycle(cycle_id, report)
        return report

    def build_report(
        self,
        *,
        now: datetime,
        cycle_id: str,
        markets_seen: int,
        observations_written: int,
        trades_opened: int,
        settlements_recorded: int,
        coverage_settlements_recorded: int,
        coverage_trades_recorded: int,
        coverage_scope_targets: dict[str, int],
        coverage_scope_recorded: dict[str, int],
        maker_updates: int,
        hourly_calibration_settlements: int,
        calibration_forecasts_recorded: int,
        target_candidate_settlements: int,
        target_candidate_forecasts_recorded: int,
        errors: list[str],
        failed: bool = False,
        lane_trades_quarantined: int = 0,
    ) -> dict[str, Any]:
        vertical_timeframes = {
            Vertical.CRYPTO: ("15m", "1h", "1d", "1w"),
        }
        hourly_profile = fit_hourly_calibration_profile(
            self.ledger.hourly_calibration_rows()
        )
        hourly_bootstrap = hourly_selected_bootstrap_diagnostic(
            self.ledger.selected_hourly_bootstrap_rows()
        )
        hourly_counts = self.ledger.hourly_calibration_counts()
        cohort_lanes: dict[str, dict[str, dict[str, Any]]] = {}
        cohort_compounding: dict[str, dict[str, dict[str, Any]]] = {}
        cohort_gates: dict[str, dict[str, dict[str, Any]]] = {}
        cohort_forward: dict[str, dict[str, dict[str, Any]]] = {}
        comparisons: dict[str, dict[str, Any]] = {}
        for vertical, timeframes in vertical_timeframes.items():
            vertical_name = vertical.value
            cohort_lanes[vertical_name] = {}
            cohort_compounding[vertical_name] = {}
            cohort_gates[vertical_name] = {}
            cohort_forward[vertical_name] = {}
            for timeframe in timeframes:
                cohort_lanes[vertical_name][timeframe] = {}
                cohort_compounding[vertical_name][timeframe] = {}
                cohort_gates[vertical_name][timeframe] = {}
                cohort_forward[vertical_name][timeframe] = {}
                for strategy in strategies_for(vertical, timeframe):
                    summary = self.ledger.lane_summary(
                        strategy, timeframe, vertical=vertical,
                    )
                    rows = self.ledger.settled_trade_rows(
                        strategy, timeframe, vertical,
                    )
                    stress = compounding_proposal(rows)
                    cohort_lanes[vertical_name][timeframe][strategy] = summary
                    cohort_compounding[vertical_name][timeframe][strategy] = stress
                    cohort_gates[vertical_name][timeframe][strategy] = _paper_gate(
                        summary, stress,
                    )
                    if strategy != "incumbent":
                        advantage = self.ledger.paired_advantage(
                            timeframe, strategy, vertical=vertical,
                        )
                        cohort_forward[vertical_name][timeframe][strategy] = (
                            _forward_selection_gate(
                                summary,
                                stress,
                                advantage,
                                promotion_allowed=strategy in {
                                    "recursive", HOURLY_CALIBRATED_STRATEGY,
                                },
                            )
                        )
            comparisons[vertical_name] = {}
            for strategy in STRATEGIES:
                applicable_timeframes = [
                    timeframe for timeframe in timeframes
                    if strategy in cohort_lanes[vertical_name][timeframe]
                ]
                if not applicable_timeframes:
                    continue
                summaries = {
                    timeframe: cohort_lanes[vertical_name][timeframe][strategy]
                    for timeframe in applicable_timeframes
                }
                enough = all(
                    int(summary["settled_trades"]) >= 30
                    and int(summary["event_clusters"]) >= 10
                    for summary in summaries.values()
                )
                winner = None
                if enough:
                    winner = max(
                        summaries,
                        key=lambda timeframe: (
                            float((summaries[timeframe].get("mean_pnl_ci95") or {}).get("lower") or -1e9),
                            float(summaries[timeframe].get("brier_skill_vs_market") or -1e9),
                        ),
                    )
                comparisons[vertical_name][strategy] = {
                    "enough_independent_evidence": enough,
                    "provisional_winner": winner,
                    "minimum_per_timeframe": {
                        "settled_trades": 30,
                        "event_clusters": 10,
                    },
                    "applicable_timeframes": applicable_timeframes,
                    **summaries,
                }
        weaknesses: list[dict[str, Any]] = []
        # Report the actual throughput constraint, not the legacy collapsed
        # reason string. Only actionable classes are weaknesses; a market Kalshi
        # never listed is expected, correct abstention and is reported apart.
        throughput_counts = self.ledger.throughput_class_counts()
        throughput_actionable = {
            cls: count for cls, count in throughput_counts.items()
            if is_actionable_throughput(cls)
        }
        throughput_expected = {
            cls: count for cls, count in throughput_counts.items()
            if is_expected_abstention(cls)
        }
        for cls, count in sorted(
            throughput_actionable.items(), key=lambda item: (-item[1], item[0]),
        )[:10]:
            weaknesses.append({
                "component": "throughput",
                "throughput_class": cls,
                "reason": _THROUGHPUT_REASONS.get(cls, cls),
                "observations": count,
                "actionable": True,
            })
        reasons = self.ledger.observation_reason_counts()
        for vertical_name, timeframes in cohort_lanes.items():
            for timeframe, strategies in timeframes.items():
                for strategy, summary in strategies.items():
                    lane_name = f"{vertical_name}:{timeframe}:{strategy}"
                    if (
                        int(summary["settled_trades"])
                        and int(summary["net_pnl_cents"]) <= 0
                    ):
                        weaknesses.append({
                            "component": "paper_performance",
                            "lane": lane_name,
                            "reason": "settled paper P&L is not positive",
                            "net_pnl_cents": summary["net_pnl_cents"],
                        })
                    if (
                        summary["maker_orders"]
                        and summary["maker_queue_snapshots"] < summary["maker_orders"]
                    ):
                        weaknesses.append({
                            "component": "execution_trace",
                            "lane": lane_name,
                            "reason": "maker queue snapshot incomplete",
                            "snapshots": summary["maker_queue_snapshots"],
                            "orders": summary["maker_orders"],
                        })
                    if int(summary.get("maker_blocked_queue") or 0) > 0:
                        weaknesses.append({
                            "component": "execution_queue",
                            "lane": lane_name,
                            "reason": "maker quote blocked by more than 50 contracts ahead",
                            "blocked_orders": summary["maker_blocked_queue"],
                        })
        if hourly_profile.status != "ACTIVE_FORWARD_CALIBRATION":
            weaknesses.append({
                "component": "hourly_calibration",
                "lane": f"CRYPTO:1h:{HOURLY_CALIBRATED_STRATEGY}",
                "reason": hourly_profile.status,
                "settled_forward_forecasts": hourly_profile.settled_forecasts,
                "walk_forward_brier_advantage_lower95": (
                    (hourly_profile.walk_forward_advantage_ci95 or {}).get("lower")
                ),
                "active_model_share": hourly_profile.model_share,
            })
        coverage_summary = self.ledger.crypto_coverage_summary()
        coverage_lanes = {
            f"{row['asset']}:{row['timeframe']}": row
            for row in coverage_summary["lanes"]
        }
        coverage_matrix: list[dict[str, Any]] = []
        for timeframe in vertical_timeframes[Vertical.CRYPTO]:
            for asset in ASSETS:
                scope = f"{asset}:{timeframe}"
                observed = int(coverage_scope_targets.get(scope) or 0)
                tracked = coverage_lanes.get(scope) or {}
                if observed:
                    status = "TRACKING_FORCED_PAPER"
                    explanation = (
                        f"{observed} real listed signal-compatible nearest-expiry "
                        "target(s) were forced into the diagnostic paper ledger."
                    )
                else:
                    status = "NO_LISTED_SIGNAL_COMPATIBLE_MARKET"
                    explanation = (
                        "No real listed target had both a complete forecast and executable "
                        "two-sided quote this cycle; no synthetic trade was fabricated."
                    )
                coverage_matrix.append({
                    "scope": scope,
                    "asset": asset,
                    "timeframe": timeframe,
                    "status": status,
                    "is_coverage_gap": not bool(observed),
                    "targets_observed_this_cycle": observed,
                    "forced_trades_recorded_this_cycle": int(
                        coverage_scope_recorded.get(scope) or 0
                    ),
                    "tracked_decisions": int(tracked.get("decisions") or 0),
                    "open_decisions": int(tracked.get("open_decisions") or 0),
                    "settled_decisions": int(tracked.get("settled_decisions") or 0),
                    "net_pnl_cents": int(tracked.get("pnl_cents") or 0),
                    "explanation": explanation,
                    "counts_toward_promotion": False,
                    "counts_toward_readiness": False,
                })
        active = self.ledger.active_epoch()
        completed_at = self.now_fn().astimezone(timezone.utc)
        crypto_name = Vertical.CRYPTO.value
        return {
            "report_name": "DUMMY_MARKET_HORIZON_PAPER_TWIN",
            "cycle_id": cycle_id,
            "started_at": now.isoformat(),
            "completed_at": completed_at.isoformat(),
            "status": "CYCLE_FAILED" if failed else "CYCLE_OK",
            "markets_seen": markets_seen,
            "observations_written": observations_written,
            "trades_opened": trades_opened,
            "settlements_recorded": settlements_recorded,
            "forced_crypto_trades_recorded": coverage_trades_recorded,
            "forced_crypto_settlements_recorded": coverage_settlements_recorded,
            "hourly_calibration_settlements_recorded": hourly_calibration_settlements,
            "hourly_calibration_forecasts_recorded": calibration_forecasts_recorded,
            "target_candidate_settlements_recorded": target_candidate_settlements,
            "target_candidate_forecasts_recorded": target_candidate_forecasts_recorded,
            "maker_updates": maker_updates,
            "errors": errors,
            "lane_trades_quarantined": lane_trades_quarantined,
            "paper_lane_quarantine": sorted(
                ":".join(lane) for lane in PAPER_LANE_QUARANTINE
            ),
            "timeframes": list(vertical_timeframes[Vertical.CRYPTO]),
            "assets": list(ASSETS),
            "vertical_timeframes": {
                vertical.value: list(timeframes)
                for vertical, timeframes in vertical_timeframes.items()
            },
            "assets_by_vertical": {
                crypto_name: list(ASSETS),
            },
            "universe_policy": {
                "crypto_assets": list(ASSETS),
                "crypto_timeframes": list(vertical_timeframes[Vertical.CRYPTO]),
                "required_crypto_trading_timeframes": list(
                    REQUIRED_TRADING_TIMEFRAMES
                ),
                "other_crypto_allowed": False,
                "weather_contracts_allowed": False,
                "commodity_contracts_allowed": False,
                "weather_and_commodities_role": "contextual_data_only",
                "unlisted_market_action": "ABSTAIN",
                "synthetic_contract_substitution": False,
            },
            "horizon_execution_contract": {
                "assets": list(ASSETS),
                "required_timeframes": list(REQUIRED_TRADING_TIMEFRAMES),
                "supplemental_timeframes": list(SUPPLEMENTAL_TRADING_TIMEFRAMES),
                "required_scopes": [
                    f"{asset}:{timeframe}"
                    for asset in ASSETS
                    for timeframe in REQUIRED_TRADING_TIMEFRAMES
                ],
                "listed_market_behavior": (
                    "evaluate every compatible nearest-expiry target and freeze "
                    "one non-pyramiding diagnostic paper decision per asset/expiry"
                ),
                "normal_trade_policy": (
                    "fee_uncertainty_liquidity_and_evidence_gated"
                ),
                "unlisted_market_behavior": "abstain_without_synthetic_substitution",
                "live_execution_authority": False,
                "capital_authority": False,
            },
            "data_only_context_policy": DATA_ONLY_CONTEXT_POLICY,
            "strategies": list(STRATEGIES),
            "active_recursive_epoch": active,
            # Compatibility: lanes remains the crypto view. New consumers
            # should use cohorts for vertical-separated evidence.
            "lanes": cohort_lanes[crypto_name],
            "cohorts": cohort_lanes,
            # Wave-23: lanes' self-learned entry bars (empty while healthy).
            "entry_bar_adjustments": {
                f"{timeframe}:{strategy}": value
                for (timeframe, strategy), value in sorted(
                    getattr(self, "_entry_bars", {}).items())
            },
            "phase_2_forward_selection": {
                "frozen_epoch": active,
                "candidate_gates": cohort_forward[crypto_name],
                "candidate_gates_by_vertical": cohort_forward,
                "automatic_rotation": "research-only after 30 settled trades, 5 clusters, and statistically negative P&L",
            },
            "hourly_calibration": {
                "profile": hourly_profile.to_dict(),
                "forward_ledger": hourly_counts,
                "selected_trade_bootstrap_diagnostic": hourly_bootstrap,
                "activation_rule": {
                    "minimum_settled_forecasts": HOURLY_CALIBRATION_MIN_SETTLED,
                    "minimum_event_clusters": HOURLY_CALIBRATION_MIN_CLUSTERS,
                    "minimum_walk_forward_forecasts": HOURLY_CALIBRATION_MIN_FORWARD,
                    "positive_cluster_brier_advantage_lower95": True,
                    "maximum_model_share": 0.50,
                },
                "production_effect": "none",
                "execution_authority": False,
                "capital_authority": False,
            },
            "price_target_selection": {
                "version": "nearest-expiry-target-ladder-v1",
                "assets": list(ASSETS),
                "terminal_price_horizons": ["1h", "1d", "1w"],
                "native_direction_horizons": ["15m"],
                "objective": (
                    "maximize fee-and-uncertainty-adjusted conservative EV across every "
                    "valid nearest-expiry listed target, preferring policy-eligible targets"
                ),
                "raw_win_rate_is_not_the_objective": True,
                "invalid_or_missing_strikes": "fail_closed",
                "one_position_per_asset_expiry": True,
                "current_cycle": self.ledger.cycle_target_selections(cycle_id),
                "settled_target_type_diagnostics": (
                    self.ledger.settled_target_performance()
                ),
                "historical_diagnostics_influence_selection": False,
                "activation_requirement": (
                    "independent forward evidence before any target-type preference"
                ),
                "rejection_regret": self.ledger.target_candidate_regret_summary(),
                "execution_authority": False,
                "capital_authority": False,
            },
            "forced_crypto_coverage": {
                "version": CRYPTO_COVERAGE_VERSION,
                "lane": CRYPTO_COVERAGE_LANE,
                "designated_scopes": len(ASSETS) * len(
                    vertical_timeframes[Vertical.CRYPTO]
                ),
                "scopes_observed_this_cycle": sum(
                    int(row["targets_observed_this_cycle"] > 0)
                    for row in coverage_matrix
                ),
                "coverage_gap_count": sum(
                    int(row["is_coverage_gap"]) for row in coverage_matrix
                ),
                "coverage_gaps": [
                    row["scope"] for row in coverage_matrix
                    if row["is_coverage_gap"]
                ],
                "targets_observed_this_cycle": sum(coverage_scope_targets.values()),
                "forced_trades_recorded_this_cycle": coverage_trades_recorded,
                "forced_settlements_recorded_this_cycle": (
                    coverage_settlements_recorded
                ),
                "matrix": coverage_matrix,
                "summary": coverage_summary,
                "active_trades": self.ledger.recent_crypto_coverage_trades(
                    status="OPEN", limit=100,
                ),
                "recent_settlements": self.ledger.recent_crypto_coverage_trades(
                    status="SETTLED", limit=50,
                ),
                "real_listed_markets_only": True,
                "all_valid_nearest_expiry_targets": True,
                "fabricated_trades": False,
                "counts_toward_promotion": False,
                "counts_toward_readiness": False,
                "execution_authority": False,
                "capital_authority": False,
            },
            "timeframe_comparison": comparisons[crypto_name],
            "timeframe_comparison_by_vertical": comparisons,
            "phase_3_execution": {
                "maker_method": "one-minute public-print queue-consumption witness",
                "taker_method": "live top-ask quote simulated for one contract",
                "reason_counts": reasons,
                "reason_counts_by_vertical": {
                    vertical.value: self.ledger.observation_reason_counts(vertical)
                    for vertical in vertical_timeframes
                },
                "throughput_classes": throughput_counts,
                "throughput_actionable": throughput_actionable,
                "throughput_expected": throughput_expected,
                "throughput_legend": _THROUGHPUT_REASONS,
                "policy_challengers": self.ledger.execution_challengers(
                    Vertical.CRYPTO,
                ),
                "policy_challengers_by_vertical": {
                    vertical.value: self.ledger.execution_challengers(vertical)
                    for vertical in vertical_timeframes
                },
            },
            "phase_4_canary_decision": {
                "gates": cohort_gates[crypto_name],
                "gates_by_vertical": cohort_gates,
                "live_canary_ready": False,
                "authority_required": "separate explicit operator authorization after production canary gate",
            },
            "phase_5_compounding": cohort_compounding[crypto_name],
            "phase_5_compounding_by_vertical": cohort_compounding,
            "weaknesses": weaknesses,
            "recent_explanations": self.ledger.recent_explanations(64),
            "evidence_quarantine": {
                "counts_toward_canary": False,
                "counts_toward_scale": False,
                "simulated_taker_quote_is_witnessed_fill": False,
                "maker_public_print_is_research_execution_evidence_only": True,
                "exploratory_lane_is_promotion_evidence": False,
                "hourly_calibrated_lane_requires_forward_activation": True,
                "selected_hourly_bootstrap_counts_toward_activation": False,
                "target_candidate_counterfactual_counts_as_fill_evidence": False,
                "target_candidate_counterfactual_auto_tunes_gates": False,
                "forced_crypto_coverage_counts_toward_promotion": False,
                "forced_crypto_coverage_counts_toward_readiness": False,
                "legacy_15m_hourly_rows": self.ledger.legacy_quarantine_summary(),
            },
            "authority": {
                "independent_of_shadow_or_live_session": True,
                "continues_during_authorized_live_operation": True,
                "public_get_only": True,
                "credentials_loaded": False,
                "broker_contacted": False,
                "execution_authority": False,
                "capital_authority": False,
                "production_weight_write_authority": False,
                "production_risk_write_authority": False,
                "forced_crypto_coverage_counts_toward_promotion": False,
            },
        }


def write_paper_twin_report(
    report: dict[str, Any],
    out_dir: Path | str = Path("artifacts/dummy/crypto_paper_twin"),
) -> Path:
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = _utc(report["completed_at"]).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"MARKET_HORIZON_PAPER_TWIN_{stamp}.json"
    payload = json.dumps(report, indent=2, sort_keys=True, default=str)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)
    latest = directory / "LATEST.json"
    latest_tmp = latest.with_suffix(".tmp")
    latest_tmp.write_text(payload, encoding="utf-8")
    latest_tmp.replace(latest)
    return path
