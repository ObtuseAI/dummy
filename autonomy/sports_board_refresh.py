"""Bounded, display-only refresh for the current MLB/WNBA betting guide.

The full autonomy cycle scans and researches thousands of markets.  That work
must not be on the critical path for keeping a human-facing sports guide
current.  This module therefore performs a much smaller operation:

* fetch the public, unauthenticated Kalshi books for the registered MLB/WNBA
  series;
* reuse only a recent forecast from the cycle artifact (never a prior tier);
* reassess that forecast against the newly fetched executable quotes with the
  unchanged :mod:`autonomy.tier_policy` implementation; and
* write a separate display artifact which no execution, promotion, trust, or
  settlement path reads.

Missing or old models remain visible as ``UNATTRIBUTED``.  The refresher never
turns a stale row into a letter grade and never opens ``ledger.db``.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from zoneinfo import ZoneInfo

import httpx

from autonomy.bet_board import (
    BOARD_PATH,
    DISPLAY_BOARD_PATH,
    _finish_board,
    write_board_artifact,
)
from autonomy.market_labels import humanize_market
from autonomy.ontology import Forecast
from autonomy.quote_quality import honest_implied_yes
from autonomy.scanner import default_fetch_series_markets, to_market_view
from autonomy.sports_markets import (
    SERIES_SPEC,
    series_of,
    spec_for,
)
from autonomy.tier_policy import assign_cycle_tiers, normalized_quote_sizes

DISPLAY_REFRESH_KIND = "sports_public_quote_refresh_v1"
DISPLAY_ARTIFACT_SOURCE = "sports_display_refresh_v1"
MODEL_SEED_ARTIFACT_SOURCE = "sports_model_seed_v1"
AUTHORITATIVE_MODEL_SEED_ARTIFACT_SOURCE = (
    "sports_model_seed_authoritative_v1"
)
DISPLAY_MODEL_PROVENANCE_VERSION = 2

# A fresh quote must never make an old forecast look current.  Reuse is limited
# to the same 15-minute window as executable quotes; after that the old issue
# may be shown only as explicitly expired context and the public bucket is
# UNATTRIBUTED.
DISPLAY_MODEL_MAX_AGE_SECONDS = 15 * 60.0
DISPLAY_MODEL_FUTURE_SKEW_SECONDS = 5.0

TARGET_LEAGUES = ("mlb", "wnba")
DISPLAY_TIMEZONE = "America/Chicago"
# Keep scheduled public reads deliberately conservative.  Kalshi's public
# market endpoint has returned transient 429s under the previous eight-worker
# fan-out; two workers preserves bounded parallelism without creating an
# avoidable burst at each scheduled refresh.
DEFAULT_MAX_WORKERS = 2
DEFAULT_SERIES_TIMEOUT_SECONDS = 6.0
DEFAULT_OVERALL_TIMEOUT_SECONDS = 45.0
PUBLIC_FETCH_RETRY_DELAYS_SECONDS = (0.05, 0.15)

STATUS_PATH = Path("runtime/autonomy/sports_board_refresh_status.json")
LOCK_PATH = Path("runtime/autonomy/sports_board_refresh.lock")
# Legacy broad-monitor seed. It remains readable only when a caller passes the
# path explicitly; the scheduled display refresher never falls back to it.
MODEL_SEED_PATH = Path("runtime/autonomy/sports_model_seed.json")
AUTHORITATIVE_MODEL_SEED_PATH = Path(
    "runtime/autonomy/sports_model_seed_authoritative.json"
)
AUTHORITATIVE_MODEL_SEED_STATUS_PATH = Path(
    "runtime/autonomy/sports_model_seed_authoritative_status.json"
)


class SportsBoardRefreshUnavailable(RuntimeError):
    """Raised when no public series response is safe enough to publish."""


class _PublicSeriesFetchFailure(RuntimeError):
    """Sanitized public-read failure safe to persist in display artifacts."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


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


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _canonical_model_provenance(row: dict[str, Any]) -> dict[str, Any]:
    """Fields that bind a refreshed tier to its cached forecast provenance."""
    return {
        "display_refresh_kind": row.get("display_refresh_kind"),
        "display_model_provenance_version": row.get(
            "display_model_provenance_version"
        ),
        "ticker": row.get("ticker"),
        "probability": row.get("probability"),
        "uncertainty": row.get("uncertainty"),
        "model_source": row.get("model_source"),
        "forecast_generated_at": row.get("forecast_generated_at"),
        "forecast_age_seconds_at_assessment": row.get(
            "forecast_age_seconds_at_assessment"
        ),
        "forecast_freshness_limit_seconds": row.get(
            "forecast_freshness_limit_seconds"
        ),
        "forecast_source_artifact_sha256": row.get(
            "forecast_source_artifact_sha256"
        ),
        "forecast_sources_used": row.get("forecast_sources_used"),
        "forecast_sources_provenance_status": row.get(
            "forecast_sources_provenance_status"
        ),
        "event_start_time": row.get("event_start_time"),
        "event_phase_at_assessment": row.get("event_phase_at_assessment"),
        "execution_authority": row.get("execution_authority"),
        "promotion_authority": row.get("promotion_authority"),
        "trust_authority": row.get("trust_authority"),
    }


def _model_provenance_digest(row: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            _canonical_model_provenance(row),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _governed_sources(value: Any) -> dict[str, float]:
    """Return finite positive governed weights, excluding malformed entries."""
    if not isinstance(value, dict):
        return {}
    result: dict[str, float] = {}
    for raw_name, raw_weight in value.items():
        name = str(raw_name or "").strip()
        weight = _finite(raw_weight)
        if name and weight is not None and weight > 0.0:
            result[name] = weight
    return result


def _has_non_market_predictive_source(value: Any) -> bool:
    # EnsembleForecaster emits only governed/promoted sources. market_prior is
    # the exchange price benchmark, not independent predictive evidence.
    return any(
        name != "market_prior" for name in _governed_sources(value)
    )


def validate_display_model_provenance(
    row: dict[str, Any],
    *,
    current: datetime,
) -> tuple[bool, str]:
    """Verify that a display tier still has a fresh, bound cached model.

    This is an additional display constraint.  The immutable tier-policy hash,
    quote binding, fee math, and scarcity checks remain independently enforced
    by :func:`autonomy.bet_board.read_board_artifact`.
    """
    if row.get("display_refresh_kind") != DISPLAY_REFRESH_KIND:
        return False, "missing_display_model_provenance"
    if row.get("display_model_provenance_version") != (
        DISPLAY_MODEL_PROVENANCE_VERSION
    ):
        return False, "invalid_display_model_provenance_version"
    if any(
        row.get(key) is not False
        for key in (
            "execution_authority",
            "promotion_authority",
            "trust_authority",
        )
    ):
        return False, "display_refresh_claims_forbidden_authority"
    claimed = row.get("display_model_provenance_sha256")
    if not isinstance(claimed, str) or claimed != _model_provenance_digest(row):
        return False, "invalid_display_model_provenance_hash"

    model_at = _utc(row.get("forecast_generated_at"))
    assessed_at = _utc(row.get("tier_assessed_at"))
    limit = _finite(row.get("forecast_freshness_limit_seconds"))
    recorded_age = _finite(row.get("forecast_age_seconds_at_assessment"))
    source_hash = row.get("forecast_source_artifact_sha256")
    sources_used = _governed_sources(row.get("forecast_sources_used"))
    event_start = _utc(row.get("event_start_time"))
    if (
        model_at is None
        or assessed_at is None
        or limit is None
        or not 0.0 < limit <= DISPLAY_MODEL_MAX_AGE_SECONDS
        or recorded_age is None
        or not isinstance(source_hash, str)
        or len(source_hash) != 64
        or row.get("model_source") not in {
            "cycle_artifact_cached_forecast",
            "cached_display_forecast",
            "fresh_governed_ensemble",
            "sports_model_seed_forecast",
        }
        or row.get("forecast_sources_provenance_status")
        != "GOVERNED_NON_MARKET_SOURCE_PRESENT"
        or not _has_non_market_predictive_source(sources_used)
        or event_start is None
        or row.get("event_phase_at_assessment") != "PRE_GAME"
    ):
        return False, "invalid_display_model_provenance_fields"

    age_at_assessment = (assessed_at - model_at).total_seconds()
    if age_at_assessment < -DISPLAY_MODEL_FUTURE_SKEW_SECONDS:
        return False, "display_model_after_assessment"
    if abs(age_at_assessment - recorded_age) > 0.01:
        return False, "display_model_age_mismatch"
    if age_at_assessment > limit:
        return False, "display_model_stale_at_assessment"
    age_at_read = (current.astimezone(timezone.utc) - model_at).total_seconds()
    if age_at_read < -DISPLAY_MODEL_FUTURE_SKEW_SECONDS:
        return False, "display_model_after_read_time"
    if age_at_read > limit:
        return False, "display_model_stale_at_read_time"
    if assessed_at >= event_start:
        return False, "display_model_assessed_in_play"
    if current.astimezone(timezone.utc) >= event_start:
        return False, "display_model_now_in_play"
    return True, "validated_display_model_provenance"


def _registered_series(leagues: Iterable[str]) -> tuple[str, ...]:
    wanted = {str(league).lower() for league in leagues}
    return tuple(sorted(
        series
        for series, spec in SERIES_SPEC.items()
        if str(spec.league).lower() in wanted
    ))


def _flatten_groups(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    groups = payload.get("groups")
    if not isinstance(groups, dict):
        return rows
    for markets in groups.values():
        if not isinstance(markets, dict):
            continue
        for group_rows in markets.values():
            if isinstance(group_rows, list):
                rows.extend(
                    deepcopy(row) for row in group_rows if isinstance(row, dict)
                )
    return rows


def select_sports_model_source_path(
    *,
    board_path: Path = BOARD_PATH,
    display_path: Path = DISPLAY_BOARD_PATH,
    seed_path: Path = AUTHORITATIVE_MODEL_SEED_PATH,
    now: datetime | None = None,
    timezone_name: str = DISPLAY_TIMEZONE,
) -> Path:
    """Choose the artifact with the most usable current-day sports models.

    Existence alone is not evidence: a stale/invalid display overlay must not
    starve a newer cycle artifact and republish a board with zero grades.
    Display candidates additionally have to pass their provenance binding.
    """
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    current = current.astimezone(timezone.utc)
    coverage_date = current.astimezone(ZoneInfo(timezone_name)).date().isoformat()

    def _score(path: Path) -> tuple[int, int, float]:
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError):
            return (0, 0, float("-inf"))
        if not isinstance(payload, dict):
            return (0, 0, float("-inf"))
        source = str(payload.get("source") or "")
        if source not in {
            "cycle_artifact",
            DISPLAY_ARTIFACT_SOURCE,
            MODEL_SEED_ARTIFACT_SOURCE,
            AUTHORITATIVE_MODEL_SEED_ARTIFACT_SOURCE,
        }:
            return (0, 0, float("-inf"))
        valid = 0
        governed_rejection = 0
        newest = float("-inf")
        for row in _flatten_groups(payload):
            ticker = str(row.get("ticker") or "")
            spec = spec_for(ticker)
            if spec is None or str(spec.league).lower() not in TARGET_LEAGUES:
                continue
            event_date = str(row.get("event_date") or "")
            if not event_date:
                event_date = str(
                    humanize_market(ticker, row.get("title")).get("event_date")
                    or ""
                )
            if event_date != coverage_date:
                continue
            probability = _finite(row.get("probability"))
            uncertainty = _finite(row.get("uncertainty"))
            # An artifact completion stamp can be minutes younger than a row
            # produced early in a broad sweep.  Only exact row provenance is
            # safe for the 15-minute reuse clock.
            forecast_at = _utc(row.get("forecast_generated_at"))
            age = (
                (current - forecast_at).total_seconds()
                if forecast_at is not None else math.inf
            )
            if (
                row.get("model_status") == "MARKET_PRIOR_ONLY"
                and forecast_at is not None
                and -DISPLAY_MODEL_FUTURE_SKEW_SECONDS <= age
                <= DISPLAY_MODEL_MAX_AGE_SECONDS
                and _governed_sources(row.get("forecast_sources_used"))
                and not _has_non_market_predictive_source(
                    row.get("forecast_sources_used")
                )
            ):
                governed_rejection += 1
                newest = max(newest, forecast_at.timestamp())
                continue
            if (
                probability is None
                or uncertainty is None
                or forecast_at is None
                or not 0.0 <= probability <= 1.0
                or not 0.0 <= uncertainty <= 0.5
                or not _has_non_market_predictive_source(
                    row.get("forecast_sources_used")
                )
            ):
                continue
            age = (current - forecast_at).total_seconds()
            if age < -DISPLAY_MODEL_FUTURE_SKEW_SECONDS or age > DISPLAY_MODEL_MAX_AGE_SECONDS:
                continue
            if source in {
                DISPLAY_ARTIFACT_SOURCE,
                MODEL_SEED_ARTIFACT_SOURCE,
                AUTHORITATIVE_MODEL_SEED_ARTIFACT_SOURCE,
            }:
                provenance_ok, _reason = validate_display_model_provenance(
                    row,
                    current=current,
                )
                if not provenance_ok:
                    continue
            valid += 1
            newest = max(newest, forecast_at.timestamp())
        return (valid, governed_rejection, newest)

    candidates = [Path(board_path), Path(display_path), Path(seed_path)]
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        raise SportsBoardRefreshUnavailable("no model source artifact exists")
    # Coverage is the primary objective; newest model breaks equal-coverage
    # ties.  The final path name tie-break keeps behavior deterministic.
    scored = [(_score(path), path) for path in existing]
    best_score, best_path = max(
        scored,
        key=lambda item: (*item[0], str(item[1])),
    )
    if best_score[0] <= 0 and best_score[1] <= 0:
        raise SportsBoardRefreshUnavailable(
            "no current-day sports forecast is fresh enough to refresh"
        )
    return best_path


def _http_failure_reason(exc: httpx.HTTPStatusError) -> str:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status == 429:
        return "http_429"
    if isinstance(status, int) and 500 <= status <= 599:
        return "http_5xx"
    if isinstance(status, int) and 400 <= status <= 499:
        return "http_4xx"
    return "transport"


def _sanitized_public_failure(exc: BaseException) -> str:
    """Classify a failed public read without retaining request details."""
    if isinstance(exc, _PublicSeriesFetchFailure):
        return exc.reason
    if isinstance(exc, httpx.HTTPStatusError):
        return _http_failure_reason(exc)
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        return "timeout"
    if isinstance(exc, httpx.TransportError):
        return "transport"
    # Invalid JSON/schema and unexpected adapter errors stay fail-closed.  The
    # artifact records only a fixed public-safe class, never exception text.
    return "transport"


def _fetch_public_series_with_retry(
    series: str,
    *,
    timeout_seconds: float,
    fetch_markets: Callable[..., dict[str, Any]] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """Retry only transient failures from the production public GET adapter.

    The initial request may be followed by at most two retries on a fixed,
    jitter-free schedule.  Callers that inject ``fetch_series`` into the board
    refresher bypass this wrapper, keeping hermetic test/replay behavior exact.
    """
    fetch = fetch_markets or default_fetch_series_markets
    sleeper = sleep or time.sleep
    retry_delays = PUBLIC_FETCH_RETRY_DELAYS_SECONDS
    for attempt in range(len(retry_delays) + 1):
        try:
            return fetch(series, timeout_seconds=timeout_seconds)
        except httpx.HTTPStatusError as exc:
            reason = _http_failure_reason(exc)
            retryable = reason in {"http_429", "http_5xx"}
        except (TimeoutError, httpx.TimeoutException):
            reason = "timeout"
            retryable = True
        except httpx.TransportError:
            reason = "transport"
            retryable = True
        if not retryable or attempt >= len(retry_delays):
            raise _PublicSeriesFetchFailure(reason) from None
        sleeper(retry_delays[attempt])
    raise AssertionError("bounded public-series retry loop exhausted")


def _public_fetcher(timeout_seconds: float) -> Callable[[str], dict[str, Any]]:
    return lambda series: _fetch_public_series_with_retry(
        series,
        timeout_seconds=timeout_seconds,
    )


def _fetch_series_bounded(
    series: tuple[str, ...],
    *,
    fetch_series: Callable[[str], dict[str, Any]],
    max_workers: int,
    overall_timeout_seconds: float,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Fetch a fixed series roster concurrently with a wall-clock ceiling."""
    if not series:
        return {}, {}
    executor = ThreadPoolExecutor(
        max_workers=max(1, min(int(max_workers), len(series))),
        thread_name_prefix="sports-board-public",
    )
    futures = {
        executor.submit(fetch_series, series_ticker): series_ticker
        for series_ticker in series
    }
    pages: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    try:
        try:
            completed = as_completed(
                futures,
                timeout=max(0.1, float(overall_timeout_seconds)),
            )
            for future in completed:
                series_ticker = futures[future]
                try:
                    page = future.result()
                    if not isinstance(page, dict) or not isinstance(
                        page.get("markets", []), list
                    ):
                        raise TypeError("public series response has invalid schema")
                    pages[series_ticker] = page
                except Exception as exc:  # isolated public-series failure
                    errors[series_ticker] = _sanitized_public_failure(exc)
        except TimeoutError:
            pass
        for future, series_ticker in futures.items():
            if series_ticker in pages or series_ticker in errors:
                continue
            if future.done():
                try:
                    page = future.result()
                    if not isinstance(page, dict) or not isinstance(
                        page.get("markets", []), list
                    ):
                        raise TypeError("public series response has invalid schema")
                    pages[series_ticker] = page
                except Exception as exc:
                    errors[series_ticker] = _sanitized_public_failure(exc)
            else:
                future.cancel()
                errors[series_ticker] = "timeout"
    finally:
        # Individual HTTP calls have their own short timeout.  Do not let the
        # scheduler wait for a straggler after the bounded result is decided.
        executor.shutdown(wait=False, cancel_futures=True)
    return pages, errors


def _model_cache(
    base_rows: list[dict[str, Any]],
    *,
    model_generated_at: datetime | None,
    assessed_at: datetime,
    max_age_seconds: float,
) -> tuple[dict[str, tuple[float, float]], str, float | None]:
    if model_generated_at is None:
        return {}, "MISSING", None
    age = (assessed_at - model_generated_at).total_seconds()
    if age < -DISPLAY_MODEL_FUTURE_SKEW_SECONDS:
        return {}, "FUTURE", age
    if age > max_age_seconds:
        return {}, "STALE", age
    cached: dict[str, tuple[float, float]] = {}
    for row in base_rows:
        ticker = str(row.get("ticker") or "")
        probability = _finite(row.get("probability"))
        uncertainty = _finite(row.get("uncertainty"))
        if (
            not ticker
            or probability is None
            or uncertainty is None
            or not 0.0 <= probability <= 1.0
            or not 0.0 <= uncertainty <= 0.5
        ):
            continue
        cached[ticker] = (probability, uncertainty)
    return cached, "FRESH", age


def _unattributed_market_row(
    market: Any,
    *,
    model_status: str,
    model_generated_at: str | None,
    forecast_sources_used: dict[str, float] | None = None,
    forecast_sources_provenance_status: str = "UNAVAILABLE_IN_SOURCE_ARTIFACT",
    prior_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Visible listing for a current market that lacks a recent model."""
    from autonomy.bet_board import _group_of

    league, bet_type = _group_of(market.ticker)
    label = humanize_market(market.ticker, getattr(market, "title", None))
    implied = honest_implied_yes(market.yes_bid, market.yes_ask)
    raw = market.raw if isinstance(getattr(market, "raw", None), dict) else {}
    quote_sizes = normalized_quote_sizes(market)
    vertical = getattr(market, "vertical", None)
    vertical = getattr(vertical, "value", vertical)
    row = {
        "ticker": market.ticker,
        "category": raw.get("category") or getattr(market, "category", None),
        "series_tags": raw.get("series_tags") or raw.get("tags"),
        "vertical": vertical,
        "title": getattr(market, "title", None) or label["label"],
        "matchup": label["matchup"],
        "market": label["market"],
        "subject": label["subject"],
        "subject_team": label["subject_team"],
        "label": label["label"],
        "game_date": label["date"],
        "event_date": label["event_date"],
        "event_id": label["event_id"],
        "league": league,
        "bet_type": bet_type,
        "probability": None,
        "market_probability": round(float(implied), 4) if implied is not None else None,
        "edge": None,
        "pick": None,
        "value_side": None,
        "forecast_lean": None,
        "tier": None,
        "tier_policy_version": "unattributed",
        "tier_reason": f"cached_model_{model_status.lower()}",
        "tier_display_bucket": "UNATTRIBUTED",
        "uncertainty": None,
        "yes_bid": market.yes_bid,
        "yes_ask": market.yes_ask,
        "no_bid": market.no_bid,
        "no_ask": market.no_ask,
        "liquidity": market.liquidity,
        **quote_sizes,
        "close_time": market.close_time,
        "quote_fetched_at": market.fetched_at,
        "display_refresh_kind": DISPLAY_REFRESH_KIND,
        "display_only": True,
        "execution_authority": False,
        "promotion_authority": False,
        "trust_authority": False,
        "model_status": model_status,
        "forecast_generated_at": model_generated_at,
        "forecast_sources_used": dict(forecast_sources_used or {}),
        "forecast_sources_provenance_status": (
            forecast_sources_provenance_status
        ),
    }
    if isinstance(prior_row, dict):
        row.update({
            "last_issued_tier": prior_row.get("tier"),
            "last_issued_tier_assessed_at": prior_row.get("tier_assessed_at"),
            "last_issued_tier_reason": prior_row.get("tier_reason"),
            "last_issued_tier_status": "EXPIRED_RESEARCH_CONTEXT_ONLY",
        })
    return row


def _event_start_time(market: Any) -> datetime | None:
    """Official scheduled occurrence time; unknown means no reusable grade."""
    raw = market.raw if isinstance(getattr(market, "raw", None), dict) else {}
    for key in (
        "occurrence_datetime",
        "event_start_time",
        "scheduled_start_time",
        "start_time",
    ):
        parsed = _utc(raw.get(key))
        if parsed is not None:
            return parsed
    return None


def _unattributed_context_row(
    source: dict[str, Any],
    *,
    reason: str,
) -> dict[str, Any]:
    """Copy a failed-series listing without carrying any current tier claim."""
    row = deepcopy(source)
    previous_tier = (
        row.get("tier")
        if row.get("tier") is not None
        else row.get("last_issued_tier")
    )
    previous_assessed = (
        row.get("tier_assessed_at")
        or row.get("last_issued_tier_assessed_at")
    )
    previous_reason = (
        row.get("tier_reason")
        if row.get("tier") is not None
        else row.get("last_issued_tier_reason")
    )
    for key in tuple(row):
        if key == "tier" or key.startswith("tier_"):
            row.pop(key, None)
    row.update({
        "tier": None,
        "tier_policy_version": "unattributed",
        "tier_reason": reason,
        "tier_display_bucket": "UNATTRIBUTED",
        "tier_display_reason": reason,
        "pick": None,
        "value_side": None,
        "entry_price_cents": None,
        "modeled_fee_cents": None,
        "gross_executable_edge": None,
        "after_fee_edge": None,
        "display_refresh_kind": DISPLAY_REFRESH_KIND,
        "display_only": True,
        "execution_authority": False,
        "promotion_authority": False,
        "trust_authority": False,
        "model_status": "SERIES_REFRESH_FAILED",
        "last_issued_tier": previous_tier,
        "last_issued_tier_assessed_at": previous_assessed,
        "last_issued_tier_reason": previous_reason,
        "last_issued_tier_status": "EXPIRED_RESEARCH_CONTEXT_ONLY",
    })
    return row


def _replace_with_retry(
    source: Path,
    destination: Path,
    *,
    attempts: int = 8,
    base_delay_seconds: float = 0.05,
) -> None:
    """Atomically replace a file despite brief Windows reader/AV locks.

    Windows can deny ``os.replace`` while another process has the destination
    open without delete sharing. Retrying only ``PermissionError`` preserves
    atomic publication and still fails boundedly for a persistent lock.
    """
    limit = max(1, int(attempts))
    for attempt in range(limit):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt + 1 >= limit:
                raise
            time.sleep(max(0.0, float(base_delay_seconds)) * (attempt + 1))


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, sort_keys=True),
            encoding="utf-8",
        )
        _replace_with_retry(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _forecast_packet_sha256(
    ticker: str,
    forecast: Any,
    forecast_generated_at: str,
) -> str:
    packet = {
        "ticker": ticker,
        "probability_yes": round(float(forecast.probability_yes), 12),
        "uncertainty": round(float(forecast.uncertainty), 12),
        "sources_used": dict(getattr(forecast, "sources_used", {}) or {}),
        "rationale_sha256": hashlib.sha256(
            str(getattr(forecast, "rationale", "")).encode("utf-8")
        ).hexdigest(),
        "forecast_generated_at": forecast_generated_at,
    }
    return hashlib.sha256(
        json.dumps(packet, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def publish_fresh_sports_display_board(
    markets: Iterable[Any],
    forecasts: dict[str, Any],
    *,
    base_path: Path = BOARD_PATH,
    output_path: Path = DISPLAY_BOARD_PATH,
    now: datetime | None = None,
    timezone_name: str = DISPLAY_TIMEZONE,
    leagues: Iterable[str] = TARGET_LEAGUES,
    artifact_source: str = DISPLAY_ARTIFACT_SOURCE,
    producer: str = "DummyMispricingMonitor",
    producer_run_id: str | None = None,
    requested_series: Iterable[str] | None = None,
    covered_series: Iterable[str] | None = None,
    series_received_at: Mapping[str, str] | None = None,
    coverage_complete: bool | None = None,
) -> dict[str, Any]:
    """Publish fresh governed ensemble results from an existing monitor pass.

    ``forecasts`` values are ``(Forecast, generated_at_iso)``.  The producer is
    the already-scheduled mispricing monitor, which has just scanned the public
    books and run the same promoted-only :class:`EnsembleForecaster` as the
    autonomy cycle.  Live-specialist scalar forecasts are intentionally never
    supplied here.
    """
    completed = now or datetime.now(timezone.utc)
    if completed.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    completed = completed.astimezone(timezone.utc)
    wanted = {str(league).lower() for league in leagues}
    coverage_date = completed.astimezone(ZoneInfo(timezone_name)).date().isoformat()

    current_markets: dict[str, Any] = {}
    for market in markets:
        ticker = str(getattr(market, "ticker", "") or "")
        spec = spec_for(ticker)
        if spec is None or str(spec.league).lower() not in wanted:
            continue
        label = humanize_market(ticker, getattr(market, "title", None))
        if label.get("event_date") != coverage_date:
            continue
        if str(getattr(market, "status", "")).lower() not in {
            "active", "open", "trading",
        }:
            continue
        close_at = _utc(getattr(market, "close_time", None))
        if close_at is None or close_at <= completed:
            continue
        current_markets[ticker] = market

    scored: list[tuple[Any, Any]] = []
    generated_by_ticker: dict[str, datetime] = {}
    status_by_ticker: dict[str, str] = {}
    sources_by_ticker: dict[str, dict[str, float]] = {}
    for ticker, market in current_markets.items():
        event_start = _event_start_time(market)
        if event_start is None:
            status_by_ticker[ticker] = "UNKNOWN_EVENT_START"
            continue
        if completed >= event_start:
            status_by_ticker[ticker] = "IN_PLAY"
            continue
        record = forecasts.get(ticker)
        if not isinstance(record, tuple) or len(record) != 2:
            status_by_ticker[ticker] = "MISSING"
            continue
        forecast, generated_raw = record
        if str(getattr(forecast, "market_ticker", "") or "") != ticker:
            status_by_ticker[ticker] = "IDENTITY_MISMATCH"
            continue
        generated = _utc(generated_raw)
        if generated is None:
            status_by_ticker[ticker] = "MISSING_TIMESTAMP"
            continue
        age = (completed - generated).total_seconds()
        if age < -DISPLAY_MODEL_FUTURE_SKEW_SECONDS:
            status_by_ticker[ticker] = "FUTURE"
            continue
        if age > DISPLAY_MODEL_MAX_AGE_SECONDS:
            status_by_ticker[ticker] = "STALE"
            continue
        sources = _governed_sources(getattr(forecast, "sources_used", None))
        sources_by_ticker[ticker] = sources
        generated_by_ticker[ticker] = generated
        if not _has_non_market_predictive_source(sources):
            status_by_ticker[ticker] = "MARKET_PRIOR_ONLY"
            continue
        probability = _finite(getattr(forecast, "probability_yes", None))
        uncertainty = _finite(getattr(forecast, "uncertainty", None))
        if (
            probability is None
            or uncertainty is None
            or not 0.0 <= probability <= 1.0
            or not 0.0 <= uncertainty <= 0.5
        ):
            status_by_ticker[ticker] = "INVALID"
            continue
        scored.append((market, forecast))

    assignments = assign_cycle_tiers(scored, now=completed)
    output_path = Path(output_path)
    staging_path = output_path.with_name(
        f".{output_path.name}.{os.getpid()}.{uuid.uuid4().hex}.graded"
    )
    try:
        graded = write_board_artifact(
            scored,
            path=staging_path,
            now_iso=completed.isoformat(),
            tier_assignments=assignments,
        )
        refreshed_rows = _flatten_groups(graded)
    finally:
        try:
            staging_path.unlink(missing_ok=True)
            staging_path.with_suffix(".tmp").unlink(missing_ok=True)
        except OSError:
            pass

    refreshed_by_ticker = {
        str(row.get("ticker") or ""): row for row in refreshed_rows
    }
    for ticker, row in refreshed_by_ticker.items():
        forecast, _generated_raw = forecasts[ticker]
        generated = generated_by_ticker[ticker]
        age = (completed - generated).total_seconds()
        event_start = _event_start_time(current_markets[ticker])
        row.update({
            "display_refresh_kind": DISPLAY_REFRESH_KIND,
            "display_model_provenance_version": (
                DISPLAY_MODEL_PROVENANCE_VERSION
            ),
            "display_only": True,
            "execution_authority": False,
            "promotion_authority": False,
            "trust_authority": False,
            "model_source": "fresh_governed_ensemble",
            "model_status": "FRESH",
            "forecast_generated_at": generated.isoformat(),
            "forecast_age_seconds_at_assessment": round(age, 6),
            "forecast_freshness_limit_seconds": (
                DISPLAY_MODEL_MAX_AGE_SECONDS
            ),
            "forecast_source_artifact_sha256": _forecast_packet_sha256(
                ticker,
                forecast,
                generated.isoformat(),
            ),
            "forecast_sources_used": dict(
                getattr(forecast, "sources_used", {}) or {}
            ),
            "forecast_sources_provenance_status": (
                "GOVERNED_NON_MARKET_SOURCE_PRESENT"
            ),
            "event_start_time": event_start.isoformat(),
            "event_phase_at_assessment": "PRE_GAME",
            "quote_source": "kalshi_public_get_markets",
        })
        row["display_model_provenance_sha256"] = _model_provenance_digest(row)

    for ticker, market in current_markets.items():
        if ticker in refreshed_by_ticker:
            continue
        refreshed_by_ticker[ticker] = _unattributed_market_row(
            market,
            model_status=status_by_ticker.get(ticker, "MISSING"),
            model_generated_at=(
                generated_by_ticker[ticker].isoformat()
                if ticker in generated_by_ticker else None
            ),
            forecast_sources_used=sources_by_ticker.get(ticker),
            forecast_sources_provenance_status=(
                "MARKET_PRIOR_ONLY"
                if status_by_ticker.get(ticker) == "MARKET_PRIOR_ONLY"
                else "UNAVAILABLE_IN_SOURCE_ARTIFACT"
            ),
        )

    observed_series = sorted({series_of(ticker) for ticker in current_markets})
    requested = (
        list(dict.fromkeys(str(item) for item in requested_series))
        if requested_series is not None
        else list(_registered_series(leagues))
    )
    covered = (
        sorted(set(str(item) for item in covered_series))
        if covered_series is not None
        else observed_series
    )
    failed_series = {
        item: (
            "series_fetch_failed_or_unavailable"
            if covered_series is not None
            else "not_observed_in_monitor_scan"
        )
        for item in requested
        if item not in set(covered)
    }
    series_refreshed_at: dict[str, str] = {
        str(item): str(stamp)
        for item, stamp in (series_received_at or {}).items()
    }
    for ticker, market in current_markets.items():
        fetched = _utc(getattr(market, "fetched_at", None))
        if fetched is None:
            continue
        item = series_of(ticker)
        held = _utc(series_refreshed_at.get(item))
        if held is None or fetched > held:
            series_refreshed_at[item] = fetched.isoformat()
    payload = _finish_board(
        list(refreshed_by_ticker.values()),
        generated_at=completed.isoformat(),
        source=artifact_source,
        producer=str(producer),
        producer_run_id=producer_run_id,
        display_only=True,
        overlay_contract_version=1,
        overlay_only=True,
        execution_authority=False,
        promotion_authority=False,
        trust_authority=False,
        cycle_artifact_path=str(base_path),
        overlay_scope="current_day_mlb_wnba_only",
        coverage_date=coverage_date,
        coverage_timezone=timezone_name,
        requested_series=requested,
        covered_series=covered,
        observed_series=observed_series,
        series_refreshed_at=series_refreshed_at,
        failed_series=failed_series,
        coverage_complete=(
            bool(coverage_complete)
            if coverage_complete is not None
            else False
        ),
        coverage_note=(
            "All requested public series reads completed successfully; an empty "
            "series page is valid complete coverage."
            if coverage_complete is True
            else (
                "Observed current-day listings from the monitor's successful "
                "public series reads; per-series failures are fail-soft and "
                "cannot claim complete coverage."
            )
        ),
        current_market_count=len(current_markets),
        refreshed_tier_count=len(refreshed_rows),
        unattributed_current_market_count=(
            len(current_markets) - len(refreshed_rows)
        ),
        forecast_freshness_limit_seconds=(DISPLAY_MODEL_MAX_AGE_SECONDS),
        no_request_time_ledger_or_network=True,
        no_broker_or_order_calls=True,
    )
    _atomic_write_json(output_path, payload)
    return payload


def refresh_sports_display_board(
    *,
    base_path: Path = BOARD_PATH,
    output_path: Path = DISPLAY_BOARD_PATH,
    fetch_series: Callable[[str], dict[str, Any]] | None = None,
    series: Iterable[str] | None = None,
    leagues: Iterable[str] = TARGET_LEAGUES,
    now: datetime | None = None,
    timezone_name: str = DISPLAY_TIMEZONE,
    model_max_age_seconds: float = DISPLAY_MODEL_MAX_AGE_SECONDS,
    max_workers: int = DEFAULT_MAX_WORKERS,
    series_timeout_seconds: float = DEFAULT_SERIES_TIMEOUT_SECONDS,
    overall_timeout_seconds: float = DEFAULT_OVERALL_TIMEOUT_SECONDS,
    expected_base_sha256: str | None = None,
) -> dict[str, Any]:
    """Refresh and atomically publish the display-only sports board.

    No ledger, broker, account, order, promotion, or trust API is touched.
    ``fetch_series`` is injectable so coverage/failure behavior is hermetic in
    tests; the production default calls only Kalshi's public ``GET /markets``.
    """
    started = now or datetime.now(timezone.utc)
    if started.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    started = started.astimezone(timezone.utc)
    if isinstance(model_max_age_seconds, bool):
        raise ValueError("model_max_age_seconds must be a real number")
    model_max_age_seconds = float(model_max_age_seconds)
    if not 0.0 < model_max_age_seconds <= DISPLAY_MODEL_MAX_AGE_SECONDS:
        raise ValueError(
            "model_max_age_seconds must be positive and no greater than 900"
        )
    requested = tuple(series) if series is not None else _registered_series(leagues)
    requested = tuple(dict.fromkeys(str(item).upper() for item in requested))
    allowed_leagues = {str(league).lower() for league in leagues}
    for series_ticker in requested:
        spec = SERIES_SPEC.get(series_ticker)
        if spec is None or str(spec.league).lower() not in allowed_leagues:
            raise ValueError(f"series outside display sports scope: {series_ticker}")

    base_bytes = Path(base_path).read_bytes()
    base_sha256 = hashlib.sha256(base_bytes).hexdigest()
    if (
        expected_base_sha256 is not None
        and base_sha256 != str(expected_base_sha256)
    ):
        raise SportsBoardRefreshUnavailable(
            "authoritative model seed changed after binding validation"
        )
    base = json.loads(base_bytes.decode("utf-8"))
    if not isinstance(base, dict):
        raise SportsBoardRefreshUnavailable("base cycle board is not an object")
    base_rows = _flatten_groups(base)
    model_source = str(base.get("source") or "")

    public_fetch = fetch_series or _public_fetcher(series_timeout_seconds)
    pages, failures = _fetch_series_bounded(
        requested,
        fetch_series=public_fetch,
        max_workers=max_workers,
        overall_timeout_seconds=overall_timeout_seconds,
    )
    if not pages:
        raise SportsBoardRefreshUnavailable(
            "no public MLB/WNBA series completed successfully"
        )

    # Use the actual completion time in production.  Injected ``now`` keeps
    # tests/replays deterministic and never creates a younger-than-real quote.
    completed = started if now is not None else datetime.now(timezone.utc)
    quote_fetched_at = started.isoformat()
    coverage_date = completed.astimezone(ZoneInfo(timezone_name)).date().isoformat()
    coverage_compact = coverage_date.replace("-", "")
    current_markets: dict[str, Any] = {}
    malformed_rows = 0
    for requested_series, page in pages.items():
        for raw in page.get("markets", []):
            if not isinstance(raw, dict):
                malformed_rows += 1
                continue
            view = to_market_view(raw, fetched_at=quote_fetched_at)
            if series_of(view.ticker) != requested_series:
                malformed_rows += 1
                continue
            spec = spec_for(view.ticker)
            if (
                spec is None
                or str(spec.league).lower() not in allowed_leagues
                or str(view.status).lower() not in {"active", "open", "trading"}
            ):
                continue
            label = humanize_market(view.ticker, view.title)
            if label.get("event_date", "").replace("-", "") != coverage_compact:
                continue
            close_at = _utc(view.close_time)
            if close_at is None or close_at <= completed:
                continue
            current_markets[view.ticker] = view

    base_by_ticker = {
        str(row.get("ticker") or ""): row for row in base_rows
        if row.get("ticker")
    }
    cache: dict[str, tuple[float, float, datetime, dict[str, float]]] = {}
    cache_status: dict[str, str] = {}
    for ticker, row in base_by_ticker.items():
        probability = _finite(row.get("probability"))
        uncertainty = _finite(row.get("uncertainty"))
        forecast_at = _utc(row.get("forecast_generated_at"))
        sources_used = _governed_sources(row.get("forecast_sources_used"))
        # Wave-78: the independent model view carried on the prior cycle row.
        model_probability = _finite(row.get("model_probability"))
        model_uncertainty = _finite(row.get("model_uncertainty"))
        model_sources = row.get("model_sources")
        model_sources = model_sources if isinstance(model_sources, dict) else None
        if (
            row.get("model_status") == "MARKET_PRIOR_ONLY"
            and forecast_at is not None
            and sources_used
            and not _has_non_market_predictive_source(sources_used)
        ):
            cache_status[ticker] = "MARKET_PRIOR_ONLY"
            continue
        if (
            probability is None
            or uncertainty is None
            or forecast_at is None
            or not 0.0 <= probability <= 1.0
            or not 0.0 <= uncertainty <= 0.5
        ):
            cache_status[ticker] = "MISSING_EXACT_FORECAST_TIMESTAMP"
            continue
        if not _has_non_market_predictive_source(sources_used):
            cache_status[ticker] = (
                "MARKET_PRIOR_ONLY" if sources_used else "MISSING_LINEAGE"
            )
            continue
        age = (completed - forecast_at).total_seconds()
        if age < -DISPLAY_MODEL_FUTURE_SKEW_SECONDS:
            cache_status[ticker] = "FUTURE"
            continue
        if age > model_max_age_seconds:
            cache_status[ticker] = "STALE"
            continue
        if model_source in {
            DISPLAY_ARTIFACT_SOURCE,
            MODEL_SEED_ARTIFACT_SOURCE,
            AUTHORITATIVE_MODEL_SEED_ARTIFACT_SOURCE,
        }:
            valid, _reason = validate_display_model_provenance(
                row,
                current=completed,
            )
            if not valid:
                cache_status[ticker] = "INVALID_PROVENANCE"
                continue
        elif model_source != "cycle_artifact":
            cache_status[ticker] = "UNTRUSTED_SOURCE"
            continue
        cache[ticker] = (
            probability, uncertainty, forecast_at, sources_used,
            model_probability, model_uncertainty, model_sources,
        )
        cache_status[ticker] = "FRESH"

    scored: list[tuple[Any, Forecast]] = []
    model_status_by_ticker: dict[str, str] = {}
    forecast_at_by_ticker: dict[str, datetime] = {}
    sources_at_by_ticker: dict[str, dict[str, float]] = {}
    for ticker, market in current_markets.items():
        event_start = _event_start_time(market)
        if event_start is None:
            model_status_by_ticker[ticker] = "UNKNOWN_EVENT_START"
            continue
        if completed >= event_start:
            model_status_by_ticker[ticker] = "IN_PLAY"
            continue
        cached = cache.get(ticker)
        if cached is None:
            model_status_by_ticker[ticker] = cache_status.get(ticker, "MISSING")
            continue
        (probability, uncertainty, forecast_at, sources_used,
         model_probability, model_uncertainty, model_sources) = cached
        forecast_at_by_ticker[ticker] = forecast_at
        sources_at_by_ticker[ticker] = sources_used
        implied = honest_implied_yes(market.yes_bid, market.yes_ask)
        scored.append((
            market,
            Forecast(
                market_ticker=ticker,
                probability_yes=probability,
                uncertainty=uncertainty,
                sources_used=sources_used,
                market_implied_yes=implied,
                edge_yes=(probability - implied) if implied is not None else 0.0,
                rationale="display-only reassessment of cached cycle forecast",
                # Model view is stable model output; the tier re-grade against a
                # moved quote re-derives model_edge/side from the fresh implied.
                model_probability_yes=model_probability,
                model_uncertainty=model_uncertainty,
                model_sources=model_sources,
            ),
        ))

    assignments = assign_cycle_tiers(scored, now=completed)
    output_path = Path(output_path)
    staging_path = output_path.with_name(
        f".{output_path.name}.{os.getpid()}.{uuid.uuid4().hex}.graded"
    )
    refreshed_rows: list[dict[str, Any]] = []
    try:
        graded = write_board_artifact(
            scored,
            path=staging_path,
            now_iso=completed.isoformat(),
            tier_assignments=assignments,
        )
        refreshed_rows = _flatten_groups(graded)
    finally:
        try:
            staging_path.unlink(missing_ok=True)
            staging_path.with_suffix(".tmp").unlink(missing_ok=True)
        except OSError:
            pass

    by_ticker = {str(row.get("ticker") or ""): row for row in refreshed_rows}
    for ticker, row in by_ticker.items():
        forecast_at = forecast_at_by_ticker[ticker]
        forecast_age = (completed - forecast_at).total_seconds()
        row.update({
            "display_refresh_kind": DISPLAY_REFRESH_KIND,
            "display_model_provenance_version": (
                DISPLAY_MODEL_PROVENANCE_VERSION
            ),
            "display_only": True,
            "execution_authority": False,
            "promotion_authority": False,
            "trust_authority": False,
            "model_source": (
                "cached_display_forecast"
                if model_source == DISPLAY_ARTIFACT_SOURCE
                else "sports_model_seed_forecast"
                if model_source in {
                    MODEL_SEED_ARTIFACT_SOURCE,
                    AUTHORITATIVE_MODEL_SEED_ARTIFACT_SOURCE,
                }
                else "cycle_artifact_cached_forecast"
            ),
            "model_status": "FRESH",
            "forecast_generated_at": forecast_at.isoformat(),
            "forecast_age_seconds_at_assessment": round(
                forecast_age, 6
            ),
            "forecast_freshness_limit_seconds": float(model_max_age_seconds),
            "forecast_source_artifact_sha256": base_sha256,
            "forecast_sources_used": dict(sources_at_by_ticker[ticker]),
            "forecast_sources_provenance_status": (
                "GOVERNED_NON_MARKET_SOURCE_PRESENT"
            ),
            "event_start_time": _event_start_time(current_markets[ticker]).isoformat(),
            "event_phase_at_assessment": "PRE_GAME",
            "quote_source": "kalshi_public_get_markets",
        })
        row["display_model_provenance_sha256"] = _model_provenance_digest(row)

    for ticker, market in current_markets.items():
        if ticker in by_ticker:
            continue
        by_ticker[ticker] = _unattributed_market_row(
            market,
            model_status=model_status_by_ticker.get(
                ticker,
                "MISSING",
            ),
            model_generated_at=(
                forecast_at_by_ticker[ticker].isoformat()
                if ticker in forecast_at_by_ticker else None
            ),
            prior_row=base_by_ticker.get(ticker),
            forecast_sources_used=_governed_sources(
                (base_by_ticker.get(ticker) or {}).get("forecast_sources_used")
            ),
            forecast_sources_provenance_status=(
                "MARKET_PRIOR_ONLY"
                if model_status_by_ticker.get(ticker) == "MARKET_PRIOR_ONLY"
                else "UNAVAILABLE_IN_SOURCE_ARTIFACT"
            ),
        )

    covered = set(pages)
    overlay_by_ticker = dict(by_ticker)
    for row in base_rows:
        ticker = str(row.get("ticker") or "")
        if (
            series_of(ticker) in set(requested).difference(covered)
            and str(row.get("event_date") or "") == coverage_date
            and ticker not in overlay_by_ticker
        ):
            overlay_by_ticker[ticker] = _unattributed_context_row(
                row,
                reason="series_refresh_failed_or_unknown",
            )

    category_coverage = sorted({
        f"{SERIES_SPEC[item].league}:{SERIES_SPEC[item].segment}:"
        f"{SERIES_SPEC[item].market_type}:"
        f"{SERIES_SPEC[item].stat or '-'}"
        for item in requested
    })
    payload = _finish_board(
        list(overlay_by_ticker.values()),
        generated_at=completed.isoformat(),
        source=DISPLAY_ARTIFACT_SOURCE,
        display_only=True,
        overlay_contract_version=1,
        overlay_only=True,
        execution_authority=False,
        promotion_authority=False,
        trust_authority=False,
        model_source_path=str(base_path),
        model_source_artifact_sha256=base_sha256,
        model_source_generated_at=base.get("generated_at"),
        forecast_freshness_limit_seconds=float(model_max_age_seconds),
        coverage_date=coverage_date,
        coverage_timezone=timezone_name,
        requested_series=list(requested),
        covered_series=sorted(covered),
        observed_series=sorted(covered),
        series_refreshed_at={
            item: quote_fetched_at for item in sorted(covered)
        },
        failed_series=failures,
        coverage_complete=(len(covered) == len(requested)),
        category_coverage=category_coverage,
        current_market_count=len(current_markets),
        refreshed_tier_count=len(refreshed_rows),
        unattributed_current_market_count=(
            len(current_markets) - len(refreshed_rows)
        ),
        malformed_public_rows=malformed_rows,
        quote_batch_started_at=started.isoformat(),
        quote_batch_completed_at=completed.isoformat(),
        no_ledger_reads=True,
        no_broker_or_order_calls=True,
    )
    _atomic_write_json(output_path, payload)
    return payload


def validate_authoritative_model_seed_binding(
    *,
    seed_path: Path = AUTHORITATIVE_MODEL_SEED_PATH,
    status_path: Path = AUTHORITATIVE_MODEL_SEED_STATUS_PATH,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Bind the authoritative seed bytes to the producer's last success.

    ``STARTED`` and ``FAILED`` attempts may update the status artifact, but they
    preserve the last-success run/hash fields.  Attempt time therefore cannot
    make an old or half-published seed consumable.
    """
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    current = current.astimezone(timezone.utc)
    try:
        seed_bytes = Path(seed_path).read_bytes()
        seed = json.loads(seed_bytes.decode("utf-8"))
        status = json.loads(Path(status_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SportsBoardRefreshUnavailable(
            "authoritative sports model seed or status is unreadable"
        ) from exc
    if not isinstance(seed, dict) or not isinstance(status, dict):
        raise SportsBoardRefreshUnavailable(
            "authoritative sports model seed binding has invalid schema"
        )
    digest = hashlib.sha256(seed_bytes).hexdigest()
    generated_at = _utc(seed.get("generated_at"))
    run_id = str(seed.get("producer_run_id") or "")
    if (
        seed.get("source") != AUTHORITATIVE_MODEL_SEED_ARTIFACT_SOURCE
        or seed.get("producer") != "DummySportsModelSeed"
        or not run_id
        or generated_at is None
        or status.get("last_success_at") != seed.get("generated_at")
        or status.get("last_success_run_id") != run_id
        or status.get("last_success_seed_sha256") != digest
        or status.get("artifact_source")
        != AUTHORITATIVE_MODEL_SEED_ARTIFACT_SOURCE
        or status.get("execution_authority") is not False
        or seed.get("execution_authority") is not False
    ):
        raise SportsBoardRefreshUnavailable(
            "authoritative sports model seed is not bound to producer success"
        )
    age = (current - generated_at).total_seconds()
    if (
        age < -DISPLAY_MODEL_FUTURE_SKEW_SECONDS
        or age > DISPLAY_MODEL_MAX_AGE_SECONDS
    ):
        raise SportsBoardRefreshUnavailable(
            "authoritative sports model seed success is stale"
        )
    return {
        "seed_sha256": digest,
        "producer_run_id": run_id,
        "generated_at": seed.get("generated_at"),
        "status": status.get("status"),
    }


@contextmanager
def _refresh_lock(path: Path):
    """Non-blocking OS-held lock, automatically released after a crash."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    if handle.seek(0, os.SEEK_END) == 0:
        handle.write(b"\0")
        handle.flush()
    handle.seek(0)
    acquired = False
    try:
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                acquired = True
            except OSError:
                acquired = False
        else:
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError:
                acquired = False
        yield acquired
    finally:
        if acquired:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        handle.close()


def run_scheduled_refresh(
    *,
    base_path: Path | None = None,
    output_path: Path = DISPLAY_BOARD_PATH,
    status_path: Path = STATUS_PATH,
    lock_path: Path = LOCK_PATH,
) -> tuple[int, dict[str, Any]]:
    """Locking/scheduler wrapper with a small, atomic liveness artifact."""
    began = time.time()
    with _refresh_lock(lock_path) as acquired:
        if not acquired:
            status = {
                "status": "SKIPPED_LOCK_HELD",
                "at": datetime.now(timezone.utc).isoformat(),
                "execution_authority": False,
                "lock_kind": "os_held_auto_release",
            }
            _atomic_write_json(status_path, status)
            return 75, status
        try:
            # The scheduled display board has one authoritative model owner.
            # Legacy broad-monitor/display/cycle artifacts can be supplied only
            # by an explicit diagnostic caller; production never falls back to
            # them and therefore cannot silently resurrect an old grade.
            expected_sha256 = None
            if base_path is None:
                source_path = AUTHORITATIVE_MODEL_SEED_PATH
                binding = validate_authoritative_model_seed_binding(
                    seed_path=source_path,
                    status_path=AUTHORITATIVE_MODEL_SEED_STATUS_PATH,
                )
                expected_sha256 = str(binding["seed_sha256"])
            else:
                source_path = base_path
            board = refresh_sports_display_board(
                base_path=source_path,
                output_path=output_path,
                expected_base_sha256=expected_sha256,
            )
            status = {
                "status": "REFRESH_OK",
                "at": board.get("generated_at"),
                "duration_seconds": round(time.time() - began, 3),
                "coverage_complete": board.get("coverage_complete"),
                "covered_series": len(board.get("covered_series") or []),
                "requested_series": len(board.get("requested_series") or []),
                "current_market_count": board.get("current_market_count"),
                "refreshed_tier_count": board.get("refreshed_tier_count"),
                "execution_authority": False,
                "no_ledger_reads": True,
                "no_broker_or_order_calls": True,
                "model_source_path": str(source_path),
                "lock_kind": "os_held_auto_release",
            }
            _atomic_write_json(status_path, status)
            return 0, status
        except Exception as exc:
            status = {
                "status": f"REFRESH_FAILED:{type(exc).__name__}",
                "error": str(exc)[:300],
                "at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": round(time.time() - began, 3),
                "execution_authority": False,
                "lock_kind": "os_held_auto_release",
            }
            _atomic_write_json(status_path, status)
            return 1, status


__all__ = [
    "AUTHORITATIVE_MODEL_SEED_ARTIFACT_SOURCE",
    "AUTHORITATIVE_MODEL_SEED_PATH",
    "AUTHORITATIVE_MODEL_SEED_STATUS_PATH",
    "DISPLAY_ARTIFACT_SOURCE",
    "DISPLAY_MODEL_MAX_AGE_SECONDS",
    "DISPLAY_REFRESH_KIND",
    "MODEL_SEED_ARTIFACT_SOURCE",
    "MODEL_SEED_PATH",
    "SportsBoardRefreshUnavailable",
    "publish_fresh_sports_display_board",
    "refresh_sports_display_board",
    "run_scheduled_refresh",
    "select_sports_model_source_path",
    "validate_authoritative_model_seed_binding",
    "validate_display_model_provenance",
]
