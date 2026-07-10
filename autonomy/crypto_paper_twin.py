"""Always-on, public-read-only crypto and commodities paper digital twin.

The twin runs independently of Dummy's SHADOW/LIVE session.  It never loads
credentials, imports a broker adapter, or writes the production autonomy
ledger. Crypto is restricted to BTC/ETH/SOL at native 15-minute, hourly,
daily, and weekly horizons. Commodities use equivalent daily and weekly WTI,
natural-gas, and gold cohorts. Every cohort runs an incumbent lane and a frozen
recursive-challenger lane, records a plain-language explanation, books one
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
from autonomy.signals.commodities_spot import CommoditiesSpotVolSignal
from autonomy.signals.crypto_indicators import (
    CryptoDataHub,
    CryptoTechnicalCompositeSignal,
)
from autonomy.signals.crypto_spot import (
    CryptoEwmaTailSignal,
    CryptoSpotVolSignal,
)
from autonomy.signals.market_prior import MarketPriorSignal
from kalshi.presubmit import default_fetch_orderbook


TIMEFRAMES = {
    "15m": 15 * 60,
    "1h": 60 * 60,
    "1d": 24 * 60 * 60,
    "1w": 7 * 24 * 60 * 60,
}
STRATEGIES = ("incumbent", "recursive", "exploratory")
ASSETS = ("BTC", "ETH", "SOL")
COMMODITY_ASSETS = ("WTI", "NATGAS", "GOLD")


@dataclass(frozen=True)
class MarketCohort:
    vertical: Vertical
    asset: str
    timeframe: str
    series: tuple[str, ...]


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
    MarketCohort(Vertical.COMMODITIES, "WTI", "1d", ("KXWTI",)),
    MarketCohort(Vertical.COMMODITIES, "NATGAS", "1d", ("KXNATGASD",)),
    MarketCohort(Vertical.COMMODITIES, "GOLD", "1d", ("KXGOLDD",)),
    MarketCohort(Vertical.COMMODITIES, "WTI", "1w", ("KXWTIW",)),
    MarketCohort(Vertical.COMMODITIES, "NATGAS", "1w", ("KXNATGASW",)),
    MarketCohort(Vertical.COMMODITIES, "GOLD", "1w", ("KXGOLDW",)),
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
PAPER_RESEARCH_MIN_EV_CENTS = 3.0
CONFIDENCE_HAIRCUT_SIGMAS = 0.5
MAKER_TTL_SECONDS = 60
MAX_QUEUE_AHEAD = 50.0
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

    def open_tickers(self) -> list[str]:
        return [
            str(row[0]) for row in self.connection.execute(
                "SELECT DISTINCT ticker FROM trades WHERE status='OPEN' ORDER BY ticker"
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


def _mean_ci95(values: Sequence[float]) -> dict[str, Any] | None:
    if not values:
        return None
    numbers = [float(value) for value in values]
    mean = statistics.fmean(numbers)
    if len(numbers) < 2:
        return {"mean": round(mean, 6), "lower": None, "upper": None, "n": len(numbers)}
    half = 1.96 * statistics.stdev(numbers) / math.sqrt(len(numbers))
    return {
        "mean": round(mean, 6),
        "lower": round(mean - half, 6),
        "upper": round(mean + half, 6),
        "n": len(numbers),
        "method": "normal_mean_95",
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


def _candidate(
    market: MarketView,
    forecast: Forecast,
    technical: Signal | None,
    *,
    strategy: str,
    timeframe: str,
    genome: ResearchGenome,
) -> dict[str, Any]:
    if forecast.market_implied_yes is None:
        return {"eligible": False, "reason": "missing_market_probability", "market": market}
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
        return {"eligible": False, "reason": "missing_two_sided_quote", "market": market}
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
    return {
        "eligible": not blockers,
        "reason": "eligible" if not blockers else "; ".join(blockers),
        "market": market,
        "forecast": forecast,
        "technical": technical,
        "strategy": strategy,
        "timeframe": timeframe,
        "probability_yes": probability,
        "market_probability": market_probability,
        "uncertainty": uncertainty,
        "raw_edge_cents": raw_edge,
        "best": best,
        "policy": {
            "min_ev_cents": min_ev,
            "max_uncertainty": max_uncertainty,
            "max_entry_price_cents": max_price,
            "edge_threshold_cents": edge_threshold,
            "technical_blend": blend,
            "genome": asdict(genome) if strategy == "recursive" else None,
            "exploratory_paper_only": strategy == "exploratory",
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
        return (
            f"{prefix} ABSTAIN. {candidate.get('reason', 'no candidate')}. "
            "No paper order and no broker contact."
        )
    best = candidate["best"]
    action = f"BUY {str(best['side']).upper()}" if candidate.get("eligible") else "ABSTAIN"
    technical = candidate.get("technical")
    technical_text = (
        f" timeframe model={technical.probability_yes:.1%}"
        if technical is not None else " timeframe model unavailable"
    )
    return (
        f"{prefix} {action} on {ticker}. Model YES={candidate['probability_yes']:.1%}, "
        f"market={candidate['market_probability']:.1%}, uncertainty={candidate['uncertainty']:.1%}, "
        f"absolute edge={candidate['raw_edge_cents']:.2f}c;{technical_text}. "
        f"Best side={best['side'].upper()} at the live top ask {best['price_cents']}c, "
        f"taker fee={best['fee_cents']}c, conservative probability="
        f"{best['conservative_probability']:.1%}, conservative EV={best['ev_cents']:.2f}c. "
        f"Decision rule: {candidate['reason']}. Paper-only; quote-executable simulation, "
        "not a witnessed market fill and never readiness evidence."
    )


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
        commodity_signal: CommoditiesSpotVolSignal | None = None,
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
            verticals={Vertical.CRYPTO, Vertical.COMMODITIES},
        )
        self.hub = hub or CryptoDataHub()
        self.commodity_signal = commodity_signal or CommoditiesSpotVolSignal()
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
            signals: list[Signal] = []
            sources = (
                (prior, flat, ewma)
                if market.vertical is Vertical.CRYPTO
                else (prior, self.commodity_signal)
            )
            for source in sources:
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

    def _reconcile_settlements(self, now: datetime, errors: list[str]) -> int:
        updated = 0
        for ticker in self.ledger.open_tickers():
            try:
                market = self.fetch_result(ticker)
                result = str(market.get("result") or "").lower()
                if result in {"yes", "no"}:
                    updated += self.ledger.settle_ticker(ticker, result == "yes", now)
            except Exception as exc:
                errors.append(f"settlement:{ticker}:{type(exc).__name__}")
        return updated

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
        observations_written = trades_opened = 0
        try:
            self.hub.clear()
            maker_updates = self._reconcile_makers(now, errors)
            settlements = self._reconcile_settlements(now, errors)
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
            eligible_markets = [
                market for market in markets
                if cohort_for_market(market) is not None
                and None not in (market.yes_bid, market.yes_ask, market.no_bid, market.no_ask)
            ]
            forecasts, source_features = self._base_forecasts(eligible_markets, states)
            for cohort in COHORTS:
                vertical = cohort.vertical
                timeframe = cohort.timeframe
                asset = cohort.asset
                lane_markets = self._markets_for_asset(
                    eligible_markets, asset, timeframe, now, vertical,
                )
                cluster = event_cluster(
                    vertical, timeframe, asset, lane_markets[0].close_time,
                ) if lane_markets else None
                for strategy in STRATEGIES:
                        candidates: list[dict[str, Any]] = []
                        for market in lane_markets:
                            forecast = forecasts.get(market.ticker)
                            if forecast is None:
                                continue
                            technical = self._technical(market, timeframe, states)
                            candidates.append(_candidate(
                                market, forecast, technical, strategy=strategy,
                                timeframe=timeframe, genome=active_genome,
                            ))
                            candidates[-1]["vertical"] = vertical.value
                        if candidates:
                            best_candidate = max(
                                candidates,
                                key=lambda row: float((row.get("best") or {}).get("ev_cents") or -1e9),
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
                            "event_cluster": cluster,
                            "ticker": market.ticker if isinstance(market, MarketView) else None,
                            "action": action,
                            "explanation": explanation,
                            "diagnostics": {
                                "reason": best_candidate.get("reason"),
                                "candidate_markets": len(candidates),
                                "nearest_expiry_markets": len(lane_markets),
                                "eligible_candidates": sum(bool(row.get("eligible")) for row in candidates),
                                "contract_family": (
                                    "15m_direction" if timeframe == "15m"
                                    else "terminal_price"
                                ),
                                "listed_series": list(cohort.series),
                                "listing_duration_hours": listing_duration_hours,
                                "paper_only": True,
                            },
                            "created_at": now.isoformat(),
                        })
                        observations_written += 1
                        if not best_candidate.get("eligible") or not isinstance(market, MarketView):
                            continue
                        assert cluster is not None
                        if self.ledger.has_lane_trade(
                            strategy, timeframe, asset, cluster, vertical,
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
                            "event_cluster": cluster,
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
                maker_updates=maker_updates,
                errors=errors,
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
                maker_updates=0,
                errors=errors,
                failed=True,
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
        maker_updates: int,
        errors: list[str],
        failed: bool = False,
    ) -> dict[str, Any]:
        vertical_timeframes = {
            Vertical.CRYPTO: ("15m", "1h", "1d", "1w"),
            Vertical.COMMODITIES: ("1d", "1w"),
        }
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
                for strategy in STRATEGIES:
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
                                promotion_allowed=strategy == "recursive",
                            )
                        )
            comparisons[vertical_name] = {}
            for strategy in STRATEGIES:
                summaries = {
                    timeframe: cohort_lanes[vertical_name][timeframe][strategy]
                    for timeframe in timeframes
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
                    **summaries,
                }
        weaknesses: list[dict[str, Any]] = []
        reasons = self.ledger.observation_reason_counts()
        for reason, count in list(reasons.items())[:10]:
            if reason != "eligible":
                weaknesses.append({
                    "component": "decision_selectivity",
                    "reason": reason,
                    "observations": count,
                })
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
        active = self.ledger.active_epoch()
        completed_at = self.now_fn().astimezone(timezone.utc)
        crypto_name = Vertical.CRYPTO.value
        commodity_name = Vertical.COMMODITIES.value
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
            "maker_updates": maker_updates,
            "errors": errors,
            "timeframes": list(vertical_timeframes[Vertical.CRYPTO]),
            "assets": list(ASSETS),
            "vertical_timeframes": {
                vertical.value: list(timeframes)
                for vertical, timeframes in vertical_timeframes.items()
            },
            "assets_by_vertical": {
                crypto_name: list(ASSETS),
                commodity_name: list(COMMODITY_ASSETS),
            },
            "universe_policy": {
                "crypto_assets": list(ASSETS),
                "crypto_timeframes": list(vertical_timeframes[Vertical.CRYPTO]),
                "other_crypto_allowed": False,
                "commodity_assets": list(COMMODITY_ASSETS),
                "commodity_timeframes": list(
                    vertical_timeframes[Vertical.COMMODITIES]
                ),
                "unlisted_market_action": "ABSTAIN",
                "synthetic_contract_substitution": False,
            },
            "strategies": list(STRATEGIES),
            "active_recursive_epoch": active,
            # Compatibility: lanes remains the crypto view. New consumers
            # should use cohorts for vertical-separated evidence.
            "lanes": cohort_lanes[crypto_name],
            "cohorts": cohort_lanes,
            "phase_2_forward_selection": {
                "frozen_epoch": active,
                "candidate_gates": cohort_forward[crypto_name],
                "candidate_gates_by_vertical": cohort_forward,
                "automatic_rotation": "research-only after 30 settled trades, 5 clusters, and statistically negative P&L",
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
