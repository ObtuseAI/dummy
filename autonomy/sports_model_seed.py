"""Bounded producer for fresh MLB/WNBA winner-model seed evidence.

The broad mispricing monitor is a research sweep over the entire public
universe.  Sports display grades must not wait for that sweep to finish.  This
module therefore performs one deliberately narrow operation:

* fetch the public ``KXMLBGAME`` and ``KXWNBAGAME`` books concurrently;
* refresh only the incumbent governed winner sources for those leagues;
* read the production trust weights through a SQLite ``mode=ro`` /
  ``query_only`` snapshot;
* fuse with the same :class:`autonomy.forecaster.EnsembleForecaster`; and
* atomically publish ``sports_model_seed_authoritative.json`` for the
  display-only quote refresher.

It has no session, execution, promotion, capital, or outcome-recording
authority.  A newly active promoted MLB/WNBA challenger is a hard stop until
this producer explicitly supports that source/category; silently omitting an
earned contributor would make the cached ensemble differ from the governed
ensemble.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from zoneinfo import ZoneInfo

from autonomy.forecaster import EnsembleForecaster
from autonomy.market_labels import humanize_market
from autonomy.ontology import Forecast, MarketView, Signal
from autonomy.promotion import PromotionRegistry
from autonomy.scanner import default_fetch_series_markets, to_market_view
from autonomy.signals.market_prior import MarketPriorSignal
from autonomy.signals.cross_venue import (
    CrossVenueSignal,
    default_fetch_polymarket_markets,
    default_fetch_polymarket_orderbook,
)
from autonomy.signals.sports_elo import SportsEloSignal
from autonomy.signals.sportsbook import SportsbookConsensusSignal
from autonomy.sports.espn import EspnClient
from autonomy.sports_board_refresh import (
    AUTHORITATIVE_MODEL_SEED_ARTIFACT_SOURCE,
    AUTHORITATIVE_MODEL_SEED_PATH,
    AUTHORITATIVE_MODEL_SEED_STATUS_PATH,
    DISPLAY_MODEL_FUTURE_SKEW_SECONDS,
    DISPLAY_MODEL_MAX_AGE_SECONDS,
    DISPLAY_TIMEZONE,
    _atomic_write_json,
    _event_start_time,
    _flatten_groups,
    _replace_with_retry,
    _refresh_lock,
    publish_fresh_sports_display_board,
    validate_authoritative_model_seed_binding,
)
from autonomy.sports_markets import SPORTS_LEAGUES, series_of
from autonomy.target_policy import is_prediction_quarantined_target
from autonomy.taxonomy import scope_weight_key


TASK_NAME = "DummySportsModelSeed"
TARGET_SERIES = ("KXMLBGAME", "KXWNBAGAME")
TARGET_LEAGUES = ("mlb", "wnba")
SPORTS_SUBJECTS = frozenset(league.lower() for league in SPORTS_LEAGUES)
SUPPORTED_GOVERNED_SOURCES = frozenset({
    "cross_venue_polymarket",
    "market_prior",
    "sports_elo",
    "sportsbook_consensus",
})

LEDGER_PATH = Path("runtime/autonomy/ledger.db")
STATUS_PATH = AUTHORITATIVE_MODEL_SEED_STATUS_PATH
LOCK_PATH = Path("runtime/autonomy/sports_model_seed_authoritative.lock")

DEFAULT_SERIES_TIMEOUT_SECONDS = 6.0
DEFAULT_OVERALL_FETCH_TIMEOUT_SECONDS = 15.0
READ_ONLY_TRUST_RETRY_DELAYS_SECONDS = (0.05, 0.15)


class SportsModelSeedUnavailable(RuntimeError):
    """Raised when an exact, governed model seed cannot be published."""


class ReadOnlyTrustSnapshotBusy(SportsModelSeedUnavailable):
    """Raised after bounded retries cannot acquire a read-only trust snapshot."""


class UnsupportedGovernedSportsPromotion(SportsModelSeedUnavailable):
    """Raised when the narrow producer would omit an active sports scope."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


@dataclass(frozen=True)
class ReadOnlyTrustWeights:
    """In-memory trust snapshot with the ``AutonomyLedger`` read contract."""

    weights: Mapping[str, float]
    source_path: str

    @classmethod
    def from_ledger(cls, path: Path | str) -> "ReadOnlyTrustWeights":
        source = Path(path).resolve()
        if not source.is_file():
            raise SportsModelSeedUnavailable(
                f"read-only trust ledger is missing: {source}"
            )
        rows: list[tuple[Any, Any]] | None = None
        for attempt in range(len(READ_ONLY_TRUST_RETRY_DELAYS_SECONDS) + 1):
            connection: sqlite3.Connection | None = None
            try:
                connection = sqlite3.connect(
                    f"file:{source.as_posix()}?mode=ro",
                    uri=True,
                    timeout=5.0,
                )
                connection.execute("PRAGMA query_only=ON")
                query_only = connection.execute("PRAGMA query_only").fetchone()
                if not query_only or int(query_only[0]) != 1:
                    raise SportsModelSeedUnavailable(
                        "SQLite query_only could not be verified for trust snapshot"
                    )
                rows = connection.execute(
                    "SELECT source, weight FROM source_trust"
                ).fetchall()
                break
            except sqlite3.OperationalError as exc:
                if attempt >= len(READ_ONLY_TRUST_RETRY_DELAYS_SECONDS):
                    raise ReadOnlyTrustSnapshotBusy(
                        "read-only trust snapshot failed: OperationalError"
                    ) from exc
                time.sleep(READ_ONLY_TRUST_RETRY_DELAYS_SECONDS[attempt])
            except sqlite3.Error as exc:
                raise SportsModelSeedUnavailable(
                    f"read-only trust snapshot failed: {type(exc).__name__}"
                ) from exc
            finally:
                if connection is not None:
                    connection.close()

        if rows is None:  # defensive: the bounded loop either returns rows or raises
            raise SportsModelSeedUnavailable("read-only trust snapshot failed")

        weights: dict[str, float] = {}
        for raw_source, raw_weight in rows:
            try:
                weight = float(raw_weight)
            except (TypeError, ValueError):
                continue
            if math.isfinite(weight):
                weights[str(raw_source)] = weight
        return cls(weights=weights, source_path=str(source))

    def get_weight(self, source: str, default: float = 1.0) -> float:
        return float(self.weights.get(str(source), default))

    def get_weight_scoped(self, source: str, vertical: str) -> float:
        key = f"{source}@{vertical}"
        if key in self.weights:
            return float(self.weights[key])
        return self.get_weight(source)

    def get_weight_for_signal(
        self,
        source: str,
        vertical: str,
        ticker: str,
        features: dict[str, Any] | None = None,
    ) -> float:
        exact = scope_weight_key(source, ticker, features or {})
        if exact in self.weights:
            return float(self.weights[exact])
        return self.get_weight_scoped(source, vertical)

    def digest(self) -> str:
        packet = json.dumps(
            dict(sorted(self.weights.items())),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(packet.encode("utf-8")).hexdigest()


def unsupported_target_promotions(registry: PromotionRegistry) -> list[str]:
    """Return active sports scopes this narrow producer cannot reproduce.

    A promotion for another league or market category is a hard stop.  The
    authoritative seed must never look complete while silently omitting an
    active governed sports contributor.
    """
    snapshot = registry.snapshot()
    blocked: list[str] = []
    for raw_scope in snapshot.get("active") or []:
        scope = str(raw_scope)
        parts = scope.split("|", 3)
        if len(parts) != 4:
            continue
        source, subject, market_type, _axis = parts
        if subject not in SPORTS_SUBJECTS:
            continue
        if subject not in TARGET_LEAGUES or (
            source not in SUPPORTED_GOVERNED_SOURCES
            or market_type not in {"na", "winner"}
        ):
            blocked.append(scope)
    return sorted(set(blocked))


def _default_fetch_series(series: str, timeout_seconds: float) -> dict[str, Any]:
    return default_fetch_series_markets(
        series,
        timeout_seconds=timeout_seconds,
    )


def _fetch_winner_pages(
    *,
    fetch_series: Callable[[str], dict[str, Any]],
    clock: Callable[[], datetime],
    overall_timeout_seconds: float,
) -> tuple[dict[str, tuple[dict[str, Any], datetime]], dict[str, str]]:
    """Fetch both winner series concurrently under one small wall-clock cap."""
    executor = ThreadPoolExecutor(
        max_workers=len(TARGET_SERIES),
        thread_name_prefix="sports-model-seed-public",
    )
    futures = {
        executor.submit(fetch_series, series): series for series in TARGET_SERIES
    }
    pages: dict[str, tuple[dict[str, Any], datetime]] = {}
    failures: dict[str, str] = {}
    try:
        try:
            completed = as_completed(
                futures,
                timeout=max(0.1, float(overall_timeout_seconds)),
            )
            for future in completed:
                series = futures[future]
                try:
                    page = future.result()
                    received_at = clock().astimezone(timezone.utc)
                    if not isinstance(page, dict) or not isinstance(
                        page.get("markets", []), list
                    ):
                        raise TypeError("public series response has invalid schema")
                    pages[series] = (page, received_at)
                except Exception as exc:  # isolated and reported below
                    failures[series] = type(exc).__name__
        except TimeoutError:
            pass
        for future, series in futures.items():
            if series in pages or series in failures:
                continue
            if future.done():
                try:
                    page = future.result()
                    received_at = clock().astimezone(timezone.utc)
                    if not isinstance(page, dict) or not isinstance(
                        page.get("markets", []), list
                    ):
                        raise TypeError("public series response has invalid schema")
                    pages[series] = (page, received_at)
                except Exception as exc:
                    failures[series] = type(exc).__name__
            else:
                future.cancel()
                failures[series] = "overall_timeout"
    finally:
        # Every production HTTP call has its own shorter timeout.  Do not hold
        # the scheduler wrapper open after the bounded result is decided.
        executor.shutdown(wait=False, cancel_futures=True)
    return pages, failures


def _current_pregame_markets(
    pages: Mapping[str, tuple[dict[str, Any], datetime]],
    *,
    now: datetime,
    timezone_name: str = DISPLAY_TIMEZONE,
) -> list[MarketView]:
    current = now.astimezone(timezone.utc)
    coverage_date = current.astimezone(ZoneInfo(timezone_name)).date().isoformat()
    by_ticker: dict[str, MarketView] = {}
    for expected_series, (page, received_at) in pages.items():
        stamp = received_at.astimezone(timezone.utc).isoformat()
        for raw in page.get("markets", []):
            if not isinstance(raw, dict):
                continue
            market = to_market_view(raw, fetched_at=stamp)
            if series_of(market.ticker) != expected_series:
                continue
            if str(market.status).lower() not in {"active", "open", "trading"}:
                continue
            if is_prediction_quarantined_target(
                market.ticker,
                category=(market.raw or {}).get("category"),
                vertical=market.vertical,
            ):
                continue
            label = humanize_market(market.ticker, market.title)
            if label.get("event_date") != coverage_date:
                continue
            close_at = _utc(market.close_time)
            event_start = _event_start_time(market)
            if (
                close_at is None
                or close_at <= current
                or event_start is None
                or event_start <= current
            ):
                continue
            held = by_ticker.get(market.ticker)
            held_at = _utc(getattr(held, "fetched_at", None)) if held else None
            if held is None or held_at is None or received_at > held_at:
                by_ticker[market.ticker] = market
    return [by_ticker[ticker] for ticker in sorted(by_ticker)]


def _default_sources() -> tuple[Any, ...]:
    espn = EspnClient()
    return (
        MarketPriorSignal(),
        SportsEloSignal(espn=espn),
        SportsbookConsensusSignal(espn=espn),
        CrossVenueSignal(
            fetch_markets=lambda: default_fetch_polymarket_markets(
                timeout_seconds=DEFAULT_SERIES_TIMEOUT_SECONDS,
            ),
            fetch_orderbook=lambda token_id: default_fetch_polymarket_orderbook(
                token_id,
                timeout_seconds=DEFAULT_SERIES_TIMEOUT_SECONDS,
            ),
        ),
    )


def _warm_sources_without_persistence(
    sources: Iterable[Any],
    *,
    now: datetime,
) -> list[str]:
    """Refresh target source caches without writing research/ledger evidence."""
    warnings: list[str] = []
    today = now.astimezone(timezone.utc).date()
    recent = f"{(today - timedelta(days=2)).strftime('%Y%m%d')}-{today.strftime('%Y%m%d')}"
    for source in sources:
        try:
            if isinstance(source, SportsEloSignal):
                source.espn.clear_cache()
                with ThreadPoolExecutor(
                    max_workers=len(TARGET_LEAGUES),
                    thread_name_prefix="sports-model-seed-espn",
                ) as executor:
                    futures = {
                        executor.submit(
                            source.warmup,
                            league,
                            [recent],
                            persist=False,
                        ): league
                        for league in TARGET_LEAGUES
                    }
                    for future in as_completed(futures):
                        league = futures[future]
                        try:
                            future.result()
                        except Exception as exc:
                            warnings.append(
                                f"{source.name}:{league}:{type(exc).__name__}"
                            )
                continue
            if isinstance(source, SportsbookConsensusSignal):
                # The Elo source already cleared their shared ESPN client.
                # This hook only clears that cache, so repeating it would throw
                # away the just-fetched bounded snapshot.
                continue
            hook = getattr(source, "on_cycle_start", None)
            if callable(hook):
                hook()
        except Exception as exc:
            warnings.append(
                f"{getattr(source, 'name', type(source).__name__)}:{type(exc).__name__}"
            )
    return warnings


def _governed_forecasts(
    markets: Iterable[MarketView],
    *,
    sources: Iterable[Any],
    weights: ReadOnlyTrustWeights,
    promotion: PromotionRegistry,
    clock: Callable[[], datetime],
) -> tuple[dict[str, tuple[Forecast, str]], dict[str, int]]:
    # The fast display seed reads the human source registry, but it does not
    # consume retired paper/shadow outcome gates (including no-edge maps).
    forecaster = EnsembleForecaster(
        weights,
        promotion=promotion,
        negative_scopes=frozenset(),
    )
    forecasts: dict[str, tuple[Forecast, str]] = {}
    failures: dict[str, int] = {}
    source_list = tuple(sources)
    market_list = list(markets)
    for source in source_list:
        if isinstance(source, CrossVenueSignal):
            prefetch_failures = source.prefetch_orderbooks_for(market_list)
            if prefetch_failures:
                failures[f"{source.name}:orderbook_prefetch"] = len(
                    prefetch_failures
                )
    for market in market_list:
        signals: list[Signal] = []
        for source in source_list:
            name = str(getattr(source, "name", type(source).__name__))
            try:
                if not source.applicable(market):
                    continue
                signal = source.generate(market)
                if signal is not None:
                    signals.append(signal)
            except Exception:
                failures[name] = failures.get(name, 0) + 1
        forecast = forecaster.fuse(market, signals)
        if forecast is not None:
            generated_at = clock().astimezone(timezone.utc).isoformat()
            forecasts[market.ticker] = (forecast, generated_at)
    return forecasts, failures


def _seed_contract(payload: dict[str, Any], *, now: datetime) -> None:
    if payload.get("source") != AUTHORITATIVE_MODEL_SEED_ARTIFACT_SOURCE:
        raise SportsModelSeedUnavailable("published seed has the wrong source")
    if any(
        payload.get(field) is not False
        for field in ("execution_authority", "promotion_authority", "trust_authority")
    ):
        raise SportsModelSeedUnavailable("published seed claims forbidden authority")
    if payload.get("producer") != TASK_NAME or not payload.get("producer_run_id"):
        raise SportsModelSeedUnavailable("published seed lacks producer identity")
    if payload.get("requested_series") != list(TARGET_SERIES):
        raise SportsModelSeedUnavailable("published seed requested the wrong series")
    if payload.get("covered_series") != list(TARGET_SERIES):
        raise SportsModelSeedUnavailable("published seed lacks complete series coverage")
    if payload.get("coverage_complete") is not True:
        raise SportsModelSeedUnavailable("published seed does not prove complete coverage")
    current = now.astimezone(timezone.utc)
    for row in _flatten_groups(payload):
        if row.get("model_status") != "FRESH":
            continue
        generated = _utc(row.get("forecast_generated_at"))
        age = math.inf if generated is None else (current - generated).total_seconds()
        if (
            generated is None
            or age < -DISPLAY_MODEL_FUTURE_SKEW_SECONDS
            or age > DISPLAY_MODEL_MAX_AGE_SECONDS
        ):
            raise SportsModelSeedUnavailable(
                f"published seed contains a stale model row: {row.get('ticker')}"
            )


def _base_status(
    *,
    status: str,
    stage: str,
    at: datetime,
    run_id: str,
    started_at: datetime,
    last_success_at: Any,
    last_success_run_id: Any = None,
    last_success_seed_sha256: Any = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "stage": stage,
        "at": at.astimezone(timezone.utc).isoformat(),
        "run_id": run_id,
        "started_at": started_at.astimezone(timezone.utc).isoformat(),
        "last_success_at": last_success_at,
        "last_success_run_id": last_success_run_id,
        "last_success_seed_sha256": last_success_seed_sha256,
        "task_name": TASK_NAME,
        "producer": "DummySportsModelSeed.fast_winner_seed",
        "artifact_source": AUTHORITATIVE_MODEL_SEED_ARTIFACT_SOURCE,
        "target_series": list(TARGET_SERIES),
        "forecast_freshness_limit_seconds": DISPLAY_MODEL_MAX_AGE_SECONDS,
        "lock_kind": "os_held_auto_release",
        "public_get_only": True,
        "ledger_access": "read_only_mode_ro_query_only_snapshot",
        "no_ledger_writes": True,
        "no_paper_or_book_tape_writes": True,
        "retired_paper_or_shadow_pnl_consulted": False,
        "paper_result_promotion_gate_consulted": False,
        "canary_result_consulted": False,
        "negative_scope_performance_gate_consulted": False,
        "bankroll_or_trade_performance_gate_consulted": False,
        "human_model_source_registry_read_only": True,
        "no_broker_or_order_calls": True,
        "execution_authority": False,
        "promotion_authority": False,
        "trust_authority": False,
        "capital_authority": False,
    }


def _write_status(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_json(path, payload)


def _stage_status(
    prior: dict[str, Any],
    *,
    stage: str,
    at: datetime,
    **extra: Any,
) -> dict[str, Any]:
    """Advance a status while retaining an ordered audit timestamp map."""
    stamp = at.astimezone(timezone.utc).isoformat()
    timestamps = dict(prior.get("stage_timestamps") or {})
    timestamps[stage] = stamp
    return {
        **prior,
        "status": "STAGE",
        "stage": stage,
        "at": stamp,
        "stage_timestamps": timestamps,
        **extra,
    }


def run_scheduled_seed(
    *,
    output_path: Path = AUTHORITATIVE_MODEL_SEED_PATH,
    status_path: Path = STATUS_PATH,
    lock_path: Path = LOCK_PATH,
    ledger_path: Path = LEDGER_PATH,
    fetch_series: Callable[[str], dict[str, Any]] | None = None,
    promotion: PromotionRegistry | None = None,
    sources: Iterable[Any] | None = None,
    source_warmer: Callable[[Iterable[Any], datetime], list[str]] | None = None,
    clock: Callable[[], datetime] = _utcnow,
    monotonic: Callable[[], float] = time.monotonic,
    series_timeout_seconds: float = DEFAULT_SERIES_TIMEOUT_SECONDS,
    overall_fetch_timeout_seconds: float = DEFAULT_OVERALL_FETCH_TIMEOUT_SECONDS,
) -> tuple[int, dict[str, Any]]:
    """Run one locked, atomic sports-model-seed refresh.

    Return codes mirror the display refresher: 0 success, 75 expected overlap,
    and 1 for every fail-closed production error.
    """
    started_at = clock().astimezone(timezone.utc)
    began = monotonic()
    run_id = uuid.uuid4().hex
    prior = _load_json(status_path)
    last_success_at = prior.get("last_success_at")
    last_success_run_id = prior.get("last_success_run_id")
    last_success_seed_sha256 = prior.get("last_success_seed_sha256")

    with _refresh_lock(lock_path) as acquired:
        if not acquired:
            status = _base_status(
                status="SKIPPED_LOCK_HELD",
                stage="lock",
                at=clock(),
                run_id=run_id,
                started_at=started_at,
                last_success_at=last_success_at,
                last_success_run_id=last_success_run_id,
                last_success_seed_sha256=last_success_seed_sha256,
            )
            # The active lock owner alone owns the durable attempt status.
            # A skipped overlap must not overwrite its STARTED/STAGE record.
            return 75, status

        stage = "promotion_guard"
        status = _base_status(
            status="STARTED",
            stage=stage,
            at=started_at,
            run_id=run_id,
            started_at=started_at,
            last_success_at=last_success_at,
            last_success_run_id=last_success_run_id,
            last_success_seed_sha256=last_success_seed_sha256,
        )
        status["stage_timestamps"] = {stage: started_at.isoformat()}
        _write_status(status_path, status)

        try:
            registry = promotion or PromotionRegistry()
            promotion_snapshot = registry.snapshot()
            promotion_snapshot_sha256 = hashlib.sha256(
                json.dumps(
                    promotion_snapshot,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            unsupported = unsupported_target_promotions(registry)
            if unsupported:
                raise UnsupportedGovernedSportsPromotion(
                    "active sports promotion is outside the fast seed contract: "
                    + ", ".join(unsupported[:8])
                )

            stage = "public_winner_fetch"
            status = _stage_status(
                status,
                stage=stage,
                at=clock(),
                unsupported_active_promotions=[],
                promotion_snapshot_sha256=promotion_snapshot_sha256,
            )
            _write_status(status_path, status)
            public_fetch = fetch_series or (
                lambda series: _default_fetch_series(series, series_timeout_seconds)
            )
            pages, failures = _fetch_winner_pages(
                fetch_series=public_fetch,
                clock=clock,
                overall_timeout_seconds=overall_fetch_timeout_seconds,
            )
            missing = sorted(set(TARGET_SERIES).difference(pages))
            if missing:
                detail = {series: failures.get(series, "missing") for series in missing}
                raise SportsModelSeedUnavailable(
                    "winner-series coverage incomplete: "
                    + json.dumps(detail, sort_keys=True)
                )

            assessment_clock = clock().astimezone(timezone.utc)
            markets = _current_pregame_markets(
                pages,
                now=assessment_clock,
            )

            stage = "read_only_trust_snapshot"
            status = _stage_status(
                status,
                stage=stage,
                at=clock(),
                covered_series=sorted(pages),
                series_received_at={
                    series: received_at.isoformat()
                    for series, (_page, received_at) in sorted(pages.items())
                },
                current_pregame_market_count=len(markets),
            )
            _write_status(status_path, status)
            weights = ReadOnlyTrustWeights.from_ledger(ledger_path)

            stage = "governed_source_refresh"
            status = _stage_status(
                status,
                stage=stage,
                at=clock(),
                trust_weight_count=len(weights.weights),
                trust_weights_sha256=weights.digest(),
            )
            _write_status(status_path, status)
            source_roster = tuple(sources) if sources is not None else _default_sources()
            if source_warmer is None:
                warm_warnings = _warm_sources_without_persistence(
                    source_roster,
                    now=assessment_clock,
                )
            else:
                warm_warnings = list(source_warmer(source_roster, assessment_clock))

            stage = "governed_forecast"
            status = _stage_status(
                status,
                stage=stage,
                at=clock(),
                governed_source_roster=[
                    str(getattr(source, "name", type(source).__name__))
                    for source in source_roster
                ],
                source_refresh_warnings=warm_warnings,
            )
            _write_status(status_path, status)
            forecasts, source_failures = _governed_forecasts(
                markets,
                sources=source_roster,
                weights=weights,
                promotion=registry,
                clock=clock,
            )

            stage = "atomic_seed_publish"
            # Re-read the human governance inputs immediately before publish.
            # An operator edit during the run invalidates the assembled roster.
            if isinstance(registry, PromotionRegistry):
                current_registry = PromotionRegistry(
                    promotions_path=registry.promotions_path,
                    demotions_path=registry.demotions_path,
                )
                current_promotion_snapshot = current_registry.snapshot()
            else:
                current_promotion_snapshot = registry.snapshot()
            if current_promotion_snapshot != promotion_snapshot:
                raise SportsModelSeedUnavailable(
                    "sports promotion registry changed during seed generation"
                )

            status = _stage_status(
                status,
                stage=stage,
                at=clock(),
                forecast_count=len(forecasts),
                source_generate_failures=source_failures,
            )
            _write_status(status_path, status)
            completed = clock().astimezone(timezone.utc)
            output_path = Path(output_path)
            staging_seed = output_path.with_name(
                f".{output_path.name}.{run_id}.candidate"
            )
            try:
                board = publish_fresh_sports_display_board(
                    markets,
                    forecasts,
                    base_path=output_path,
                    output_path=staging_seed,
                    now=completed,
                    artifact_source=AUTHORITATIVE_MODEL_SEED_ARTIFACT_SOURCE,
                    producer=TASK_NAME,
                    producer_run_id=run_id,
                    requested_series=TARGET_SERIES,
                    covered_series=TARGET_SERIES,
                    series_received_at={
                        series: received_at.isoformat()
                        for series, (_page, received_at) in sorted(pages.items())
                    },
                    coverage_complete=True,
                )
                _seed_contract(board, now=completed)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                _replace_with_retry(staging_seed, output_path)
            finally:
                staging_seed.unlink(missing_ok=True)

            seed_bytes = Path(output_path).read_bytes()
            seed_sha256 = hashlib.sha256(seed_bytes).hexdigest()

            success_at = str(board.get("generated_at") or completed.isoformat())
            final = _base_status(
                status="REFRESH_OK",
                stage="complete",
                at=completed,
                run_id=run_id,
                started_at=started_at,
                last_success_at=success_at,
                last_success_run_id=run_id,
                last_success_seed_sha256=seed_sha256,
            )
            final.update({
                "completed_at": completed.isoformat(),
                "duration_seconds": round(monotonic() - began, 3),
                "covered_series": sorted(pages),
                "series_received_at": {
                    series: received_at.isoformat()
                    for series, (_page, received_at) in sorted(pages.items())
                },
                "coverage_complete": True,
                "current_pregame_market_count": len(markets),
                "forecast_count": len(forecasts),
                "current_market_count": board.get("current_market_count"),
                "refreshed_tier_count": board.get("refreshed_tier_count"),
                "unattributed_current_market_count": board.get(
                    "unattributed_current_market_count"
                ),
                "seed_generated_at": board.get("generated_at"),
                "seed_path": str(output_path),
                "seed_sha256": seed_sha256,
                "trust_weight_count": len(weights.weights),
                "trust_weights_sha256": weights.digest(),
                "governed_source_roster": [
                    str(getattr(source, "name", type(source).__name__))
                    for source in source_roster
                ],
                "source_refresh_warnings": warm_warnings,
                "source_generate_failures": source_failures,
                "unsupported_active_promotions": [],
                "promotion_snapshot_sha256": promotion_snapshot_sha256,
                "stage_timestamps": {
                    **dict(status.get("stage_timestamps") or {}),
                    "complete": completed.isoformat(),
                },
            })
            _write_status(status_path, final)
            return 0, final
        except Exception as exc:
            failed_at = clock().astimezone(timezone.utc)
            prior_binding_error: str | None = None
            if isinstance(exc, ReadOnlyTrustSnapshotBusy):
                try:
                    binding = validate_authoritative_model_seed_binding(
                        seed_path=output_path,
                        status_path=status_path,
                        now=failed_at,
                    )
                except Exception as binding_exc:
                    # Keep the original, sanitized SQLite failure as the public
                    # error.  This field records only the local validator class,
                    # never SQLite details or external payloads.
                    prior_binding_error = type(binding_exc).__name__
                else:
                    generated_at = _utc(binding.get("generated_at"))
                    if generated_at is not None:  # guaranteed by the validator
                        final = _base_status(
                            status="SKIPPED_TRUST_SNAPSHOT_BUSY",
                            stage=stage,
                            at=failed_at,
                            run_id=run_id,
                            started_at=started_at,
                            last_success_at=last_success_at,
                            last_success_run_id=last_success_run_id,
                            last_success_seed_sha256=last_success_seed_sha256,
                        )
                        final.update({
                            "completed_at": failed_at.isoformat(),
                            "duration_seconds": round(monotonic() - began, 3),
                            "reason": str(exc)[:500],
                            "retryable": True,
                            "using_last_success": True,
                            "last_success_age_seconds": round(
                                (failed_at - generated_at).total_seconds(), 3
                            ),
                            "seed_path": str(output_path),
                            "seed_sha256": binding["seed_sha256"],
                            "prior_seed_binding_status": binding.get("status"),
                            "stage_timestamps": {
                                **dict(status.get("stage_timestamps") or {}),
                                "skipped": failed_at.isoformat(),
                            },
                        })
                        _write_status(status_path, final)
                        return 75, final

            final = _base_status(
                status=f"REFRESH_FAILED:{type(exc).__name__}",
                stage=stage,
                at=failed_at,
                run_id=run_id,
                started_at=started_at,
                last_success_at=last_success_at,
                last_success_run_id=last_success_run_id,
                last_success_seed_sha256=last_success_seed_sha256,
            )
            final.update({
                "completed_at": failed_at.isoformat(),
                "duration_seconds": round(monotonic() - began, 3),
                "error": str(exc)[:500],
                "stage_timestamps": {
                    **dict(status.get("stage_timestamps") or {}),
                    "failed": failed_at.isoformat(),
                },
            })
            if isinstance(exc, ReadOnlyTrustSnapshotBusy):
                final.update({
                    "retryable": True,
                    "using_last_success": False,
                    "prior_seed_binding_error": prior_binding_error,
                })
            if isinstance(exc, UnsupportedGovernedSportsPromotion):
                final["unsupported_active_promotions"] = (
                    unsupported_target_promotions(registry)
                )
            _write_status(status_path, final)
            return 1, final


__all__ = [
    "LOCK_PATH",
    "ReadOnlyTrustSnapshotBusy",
    "ReadOnlyTrustWeights",
    "STATUS_PATH",
    "SUPPORTED_GOVERNED_SOURCES",
    "SportsModelSeedUnavailable",
    "TASK_NAME",
    "TARGET_SERIES",
    "UnsupportedGovernedSportsPromotion",
    "run_scheduled_seed",
    "unsupported_target_promotions",
]
