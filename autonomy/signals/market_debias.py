"""Market-debias signal: exploit the exchange's own measured miscalibration.

Prediction markets carry documented systematic biases (the longshot bias
being the classic: cheap contracts resolve YES less often than their price
implies). Instead of assuming the folklore, we measure it from canonical live
market-prior receipts that predate decisions, close, and settlement. Retro or
late observations are quarantined from the curve.

The signal then answers one question per market: at this price level, what
fraction of markets ACTUALLY resolved YES? Where that differs from the price,
the market itself is the mispriced instrument.

Fail-closed everywhere: no verified exact-scope curve -> no opinion. Every
emission is challenger/report-only and cannot auto-promote; an explicit
exact-scope registry promotion is required after forward calibration.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from autonomy.ontology import MarketView, Signal

CURVE_PATH = Path("runtime/autonomy/market_calibration.json")
N_BUCKETS = 20  # 5-cent buckets
MIN_BUCKET_N = 100  # no opinion from thin history
# Aggregate curves are retained for diagnostics, but operational emissions use
# only exact subject/market-type/horizon curves. This prevents a pooled crypto
# or sports relationship from acquiring authority through an unrelated exact
# scope's promotion.
N_VERTICAL_BUCKETS = 10
MIN_VERTICAL_BUCKET_N = 80
# Forward-registered promotion-candidate scopes (2026-07-22 elite audit;
# runtime/autonomy/promotion_forward_registrations.json). promotion_eligible
# flips True for EXACTLY these grading scopes' emissions and stays False for
# every other scope.
#
# Since 8c43272 emissions stamp market_type as "<type>@<horizon>", so the
# derived grading scope carries the horizon: no live emission can produce the
# original registered shape "market_debias|mlb|na|pre" (which required the
# taxonomy market_type to fall through to the bare "na"), and forward evidence
# for the mlb candidate could never accrue. The scopes below are the mlb exact
# curve scopes that actually carry a dense verified bucket -- i.e. the only
# scopes the signal emits under at all (measured against both the live curve
# artifact and the live ledger's last ~54k market_debias rows, 2026-07-24).
# A scope that densifies later stays opted out until it is deliberately
# registered: eligibility is an explicit act, never a side effect of history
# growing. Registrations are append-only, so the dead "na" entry remains in the
# file immutably; nothing can ever match it again.
#
# scripts/register_forward_candidates.py imports this set, so the registration
# file and this gate cannot drift apart again. The registration FINGERPRINT is
# never stamped here: the ledger stamps it at record time from the immutable
# registrations file (AutonomyLedger._stamp_forward_fingerprint).
PROMOTION_ELIGIBLE_SCOPES: frozenset[str] = frozenset({
    "market_debias|mlb|prop@long|pre",
    "market_debias|mlb|prop@short|pre",
    "market_debias|mlb|spread@long|pre",
})
HORIZON_BUCKETS = ("near_terminal", "short", "long")
LIVE_EVIDENCE_MODE = "live_only_receipt_bounded_decision_or_first_seen_v2"
CURVE_SCHEMA_VERSION = 6
_TERMINAL_STATUSES = frozenset({"closed", "finalized", "resolved", "settled"})
_OPEN_STATUSES = frozenset({"active", "open"})
_DECISION_SELECTION = "latest_receipt_at_or_before_earliest_decision"
_UNDECIDED_SELECTION = "earliest_live_receipt_for_undecided_contract"


def _parse_utc(value: Any) -> datetime | None:
    """Parse an explicitly zoned timestamp, returning UTC or ``None``.

    Naive timestamps are not point-in-time evidence: interpreting them in the
    host timezone would silently move the information boundary.
    """
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _horizon_bucket(hours_to_expiry: float) -> str:
    if hours_to_expiry <= 6:
        return "near_terminal"
    if hours_to_expiry <= 72:
        return "short"
    return "long"


def _hours_to_expiry(close_time: Any, observed_at: Any) -> float | None:
    close = _parse_utc(close_time)
    observed = _parse_utc(observed_at)
    if close is None or observed is None:
        return None
    hours = (close - observed).total_seconds() / 3600.0
    # A quote at or after close can encode the outcome. It is never a
    # forecasting observation, even if settlement is recorded later.
    return hours if hours > 0.0 else None


def _market_type(ticker: str) -> str:
    sports_scope = _scope_of(ticker)
    if sports_scope and ":" in sports_scope:
        return sports_scope.split(":", 1)[1]
    try:
        from autonomy.taxonomy import market_type_for

        return market_type_for("market_debias", ticker, {})
    except Exception:  # noqa: BLE001 - unknown tickers remain isolated
        return "na"


def _exact_curve_scope(ticker: str, horizon: str) -> str | None:
    if horizon not in HORIZON_BUCKETS:
        return None
    try:
        from autonomy.scanner import classify_vertical
        from autonomy.taxonomy import prediction_subject

        vertical = classify_vertical(ticker).value
        subject = prediction_subject(ticker)
    except Exception:  # noqa: BLE001 - fail closed on unclassifiable scope
        return None
    market_type = _market_type(ticker)
    if not vertical or not subject or not market_type:
        return None
    return f"{vertical}|{subject}|{market_type}|{horizon}"


@dataclass(frozen=True)
class DebiasSample:
    """One canonical, receipt-bounded live market observation and its truth."""

    probability_yes: float
    result_yes: int
    ticker: str
    horizon: str
    exact_scope: str
    observed_at: str
    received_at: str
    close_time: str
    settled_at: str
    decision_at: str | None
    signal_id: int
    selection_policy: str


def ledger_samples(ledger: Any) -> list[DebiasSample]:
    """Return one canonical point-in-time live prior per settled contract.

    Eligibility is deliberately stricter than a settlement join:

    * only ``mode='live'`` rows count;
    * both source and receipt timestamps must be valid and receipt cannot
      precede observation;
    * both timestamps must be no later than the earliest decision, if any;
    * both timestamps must be strictly before close and settlement, excluding
      terminal/outcome leakage;
    * decided contracts use the latest eligible row at/before the earliest
      decision; contracts never acted on use their first eligible live receipt,
      not a hindsight-selected near-settlement quote;
    * a later invalid row cannot hide an earlier honest observation.
    """
    import sqlite3

    from autonomy.retention import install_signal_history

    conn: sqlite3.Connection = ledger._conn  # noqa: SLF001 - trusted ledger consumer
    install_signal_history(conn)

    has_decisions = (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='decisions'"
        ).fetchone()
        is not None
    )
    decision_times: dict[str, datetime | None] = {}
    if has_decisions:
        for ticker, created_at in conn.execute(
            "SELECT market_ticker, created_at FROM decisions"
        ):
            key = str(ticker).strip().upper()
            stamp = _parse_utc(created_at)
            if stamp is None:
                # One malformed decision makes the market's decision boundary
                # unknowable; never fall back to the later settlement.
                decision_times[key] = None
            elif key not in decision_times:
                decision_times[key] = stamp
            elif decision_times[key] is not None:
                decision_times[key] = min(decision_times[key], stamp)

    rows = conn.execute(
        """
        SELECT s.id, s.probability_yes, st.result_yes, st.market_ticker,
               s.features, s.created_at, s.ingested_at, s.mode, st.settled_at
        FROM signal_history s
        JOIN settlements st ON st.market_ticker = s.market_ticker
        WHERE s.source = 'market_prior' AND LOWER(s.mode) = 'live'
        """
    ).fetchall()
    canonical: dict[
        tuple[str, str], tuple[tuple[datetime, datetime, int], DebiasSample]
    ] = {}
    for (
        row_id,
        probability,
        result,
        ticker_raw,
        features_raw,
        observed_raw,
        received_raw,
        mode,
        settled_raw,
    ) in rows:
        ticker = str(ticker_raw)
        ticker_key = ticker.strip().upper()
        if str(mode).strip().lower() != "live":
            continue
        observed = _parse_utc(observed_raw)
        received = _parse_utc(received_raw)
        settled = _parse_utc(settled_raw)
        if (
            observed is None
            or received is None
            or settled is None
            or received < observed
        ):
            continue
        try:
            features = json.loads(features_raw or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(features, dict):
            continue
        status = str(
            features.get("market_status") or features.get("status") or ""
        ).lower()
        if status in _TERMINAL_STATUSES or status not in _OPEN_STATUSES:
            continue
        close = _parse_utc(features.get("close_time"))
        if close is None:
            continue
        # Close and settlement are strict: equality may already reveal truth.
        if (
            observed >= close
            or received >= close
            or observed >= settled
            or received >= settled
        ):
            continue
        decision = decision_times.get(ticker_key, "missing")
        if decision is None:
            continue
        if decision != "missing" and (observed > decision or received > decision):
            continue
        try:
            parsed_probability = float(probability)
            parsed_result = int(result)
        except (TypeError, ValueError):
            continue
        if (
            not math.isfinite(parsed_probability)
            or not 0.0 <= parsed_probability <= 1.0
            or parsed_result not in (0, 1)
        ):
            continue
        hours = _hours_to_expiry(close.isoformat(), observed.isoformat())
        if hours is None:
            continue
        horizon = _horizon_bucket(hours)
        exact_scope = _exact_curve_scope(ticker, horizon)
        if exact_scope is None:
            continue
        selection_policy = (
            _UNDECIDED_SELECTION if decision == "missing" else _DECISION_SELECTION
        )
        sample = DebiasSample(
            probability_yes=parsed_probability,
            result_yes=parsed_result,
            ticker=ticker,
            horizon=horizon,
            exact_scope=exact_scope,
            observed_at=observed.isoformat(),
            received_at=received.isoformat(),
            close_time=close.isoformat(),
            settled_at=settled.isoformat(),
            decision_at=None if decision == "missing" else decision.isoformat(),
            signal_id=int(row_id),
            selection_policy=selection_policy,
        )
        rank = (observed, received, int(row_id))
        key = (ticker_key, exact_scope)
        held = canonical.get(key)
        choose = held is None
        if held is not None:
            choose = rank < held[0] if decision == "missing" else rank > held[0]
        if choose:
            canonical[key] = (rank, sample)
    return [canonical[key][1] for key in sorted(canonical)]


def _bin_samples(
    samples: list[tuple[float, int]],
    n_buckets: int,
) -> list[dict[str, Any]]:
    buckets = [
        {
            "lo": i / n_buckets,
            "hi": (i + 1) / n_buckets,
            "n": 0,
            "sum_price": 0.0,
            "sum_yes": 0,
        }
        for i in range(n_buckets)
    ]
    for mid_prob, result in samples:
        idx = min(n_buckets - 1, max(0, int(mid_prob * n_buckets)))
        buckets[idx]["n"] += 1
        buckets[idx]["sum_price"] += mid_prob
        buckets[idx]["sum_yes"] += int(result)
    out = []
    for bucket in buckets:
        n = bucket["n"]
        out.append(
            {
                "lo": bucket["lo"],
                "hi": bucket["hi"],
                "n": n,
                "avg_price": round(bucket["sum_price"] / n, 4) if n else None,
                "yes_rate": round(bucket["sum_yes"] / n, 4) if n else None,
            }
        )
    return out


def _scope_of(ticker: str) -> str | None:
    """``"<vertical>:<market_type>"`` for a sports market, else None.

    The price->outcome relationship is market-TYPE specific: a 0.60-priced
    moneyline favorite resolves YES ~80%, but a 0.60-priced first-inning-run
    (YRFI) resolves ~47% -- pooling them into one sports curve made YRFI inherit
    the favorites' yes-rate (a measured +0.15 bias). Scoping by market type lets
    each type read its OWN curve, or abstain when its own history is too thin.
    """
    try:
        from autonomy.scanner import classify_vertical
        from autonomy.sports_markets import spec_for

        spec = spec_for(ticker)
        if spec is None:
            return None
        return f"{classify_vertical(ticker).value}:{spec.market_type}"
    except Exception:  # noqa: BLE001
        return None


def fit_curve(samples: list[Any]) -> dict[str, Any]:
    """Fit diagnostic and exact-scope curves from verified live samples only.

    Legacy tuples are counted as unverified research inputs but never enter an
    operative bucket. That keeps retro candles and ad-hoc tuples useful for
    audit accounting without letting them acquire probability authority by
    being passed to this function.
    """
    unverified_research_n = 0
    invalid_verified_n = 0
    canonical: dict[
        tuple[str, str], tuple[tuple[datetime, datetime, int], DebiasSample]
    ] = {}
    for raw in samples:
        if not isinstance(raw, DebiasSample):
            unverified_research_n += 1
            continue
        observed = _parse_utc(raw.observed_at)
        received = _parse_utc(raw.received_at)
        close = _parse_utc(raw.close_time)
        settled = _parse_utc(raw.settled_at)
        decision = _parse_utc(raw.decision_at) if raw.decision_at is not None else None
        try:
            probability = float(raw.probability_yes)
            result = int(raw.result_yes)
            signal_id = int(raw.signal_id)
        except (TypeError, ValueError):
            invalid_verified_n += 1
            continue
        expected_selection = (
            _UNDECIDED_SELECTION if decision is None else _DECISION_SELECTION
        )
        if (
            observed is None
            or received is None
            or close is None
            or settled is None
            or received < observed
            or observed >= close
            or received >= close
            or observed >= settled
            or received >= settled
            or (raw.decision_at is not None and decision is None)
            or (decision is not None and (observed > decision or received > decision))
            or not math.isfinite(probability)
            or not 0.0 <= probability <= 1.0
            or result not in (0, 1)
            or raw.selection_policy != expected_selection
        ):
            invalid_verified_n += 1
            continue
        hours = _hours_to_expiry(close.isoformat(), observed.isoformat())
        horizon = _horizon_bucket(hours) if hours is not None else ""
        exact_scope = _exact_curve_scope(raw.ticker, horizon)
        # Recompute scope and horizon instead of trusting caller-supplied
        # labels; a spoofed label must not pool unrelated contracts.
        if (
            exact_scope is None
            or raw.horizon != horizon
            or raw.exact_scope != exact_scope
        ):
            invalid_verified_n += 1
            continue
        normalized = DebiasSample(
            probability_yes=probability,
            result_yes=result,
            ticker=str(raw.ticker),
            horizon=horizon,
            exact_scope=exact_scope,
            observed_at=observed.isoformat(),
            received_at=received.isoformat(),
            close_time=close.isoformat(),
            settled_at=settled.isoformat(),
            decision_at=decision.isoformat() if decision is not None else None,
            signal_id=signal_id,
            selection_policy=expected_selection,
        )
        rank = (observed, received, signal_id)
        key = (normalized.ticker, exact_scope)
        held = canonical.get(key)
        if held is None or rank > held[0]:
            canonical[key] = (rank, normalized)
    verified = [canonical[key][1] for key in sorted(canonical)]

    flat: list[tuple[float, int]] = []
    by_vertical: dict[str, list[tuple[float, int]]] = {}
    by_scope: dict[str, list[tuple[float, int]]] = {}
    by_horizon: dict[str, list[tuple[float, int]]] = {}
    by_vertical_horizon: dict[str, list[tuple[float, int]]] = {}
    by_scope_horizon: dict[str, list[tuple[float, int]]] = {}
    by_exact_scope: dict[str, list[tuple[float, int]]] = {}
    for sample in verified:
        mid_prob, result = sample.probability_yes, sample.result_yes
        flat.append((mid_prob, result))
        horizon = sample.horizon
        by_horizon.setdefault(horizon, []).append((mid_prob, result))
        by_exact_scope.setdefault(sample.exact_scope, []).append((mid_prob, result))
        vertical = sample.exact_scope.split("|", 1)[0]
        by_vertical.setdefault(vertical, []).append((mid_prob, result))
        by_vertical_horizon.setdefault(f"{vertical}@{horizon}", []).append(
            (mid_prob, result)
        )
        scope = _scope_of(sample.ticker)
        if scope:
            by_scope.setdefault(scope, []).append((mid_prob, result))
            by_scope_horizon.setdefault(f"{scope}@{horizon}", []).append(
                (mid_prob, result)
            )
    verticals = {
        vertical: {
            "n_total": len(rows),
            "n_buckets": N_VERTICAL_BUCKETS,
            "min_bucket_n": MIN_VERTICAL_BUCKET_N,
            "buckets": _bin_samples(rows, N_VERTICAL_BUCKETS),
        }
        for vertical, rows in sorted(by_vertical.items())
    }
    scopes = {
        scope: {
            "n_total": len(rows),
            "n_buckets": N_VERTICAL_BUCKETS,
            "min_bucket_n": MIN_VERTICAL_BUCKET_N,
            "buckets": _bin_samples(rows, N_VERTICAL_BUCKETS),
        }
        for scope, rows in sorted(by_scope.items())
    }

    def scoped_curves(
        groups: dict[str, list[tuple[float, int]]],
    ) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "n_total": len(rows),
                "n_buckets": N_VERTICAL_BUCKETS,
                "min_bucket_n": MIN_VERTICAL_BUCKET_N,
                "buckets": _bin_samples(rows, N_VERTICAL_BUCKETS),
            }
            for name, rows in sorted(groups.items())
        }

    digest = hashlib.sha256()
    for sample in verified:
        digest.update(
            json.dumps(
                {
                    "probability_yes": sample.probability_yes,
                    "result_yes": sample.result_yes,
                    "ticker": sample.ticker,
                    "horizon": sample.horizon,
                    "exact_scope": sample.exact_scope,
                    "observed_at": sample.observed_at,
                    "received_at": sample.received_at,
                    "close_time": sample.close_time,
                    "settled_at": sample.settled_at,
                    "decision_at": sample.decision_at,
                    "signal_id": sample.signal_id,
                    "selection_policy": sample.selection_policy,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        digest.update(b"\n")

    return {
        "report_name": "MARKET_DEBIAS_CURVE",
        "schema_version": CURVE_SCHEMA_VERSION,
        "evidence_mode": LIVE_EVIDENCE_MODE,
        "point_in_time_rules": {
            "live_mode_only": True,
            "receipt_bounded": True,
            "decided_contracts_earliest_decision_bounded": True,
            "undecided_contracts_first_seen_only": True,
            "strictly_pre_close": True,
            "strictly_pre_settlement": True,
            "canonical_row_per_contract_exact_scope": True,
            "legacy_or_retro_inputs_operational": False,
        },
        "raw_input_n": len(samples),
        "n_total": len(flat),
        "verified_live_n": len(flat),
        "unverified_research_n": unverified_research_n,
        "invalid_verified_n": invalid_verified_n,
        "training_digest_sha256": digest.hexdigest(),
        "training_observed_min": min(
            (row.observed_at for row in verified), default=None
        ),
        "training_observed_max": max(
            (row.observed_at for row in verified), default=None
        ),
        "training_received_max": max(
            (row.received_at for row in verified), default=None
        ),
        "min_bucket_n": MIN_BUCKET_N,
        "buckets": _bin_samples(flat, N_BUCKETS),
        "verticals": verticals,
        "scopes": scopes,
        "exact_scopes": scoped_curves(by_exact_scope),
        "horizons": scoped_curves(by_horizon),
        "vertical_horizons": scoped_curves(by_vertical_horizon),
        "scope_horizons": scoped_curves(by_scope_horizon),
        "prediction_authority": False,
        "execution_authority": False,
        "automatic_promotion": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def write_curve(curve: dict[str, Any], path: Path | None = None) -> Path:
    path = path or CURVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(curve, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def load_curve(path: Path | None = None) -> dict[str, Any] | None:
    path = path or CURVE_PATH
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data.get("buckets"), list) else None


class MarketDebiasSignal:
    name = "market_debias"

    def __init__(
        self,
        curve: dict[str, Any] | None = None,
        curve_path: Path | None = None,
        promotion: Any = None,
    ):
        self._curve = curve if curve is not None else load_curve(curve_path)
        if promotion is None:
            from autonomy.promotion import PromotionRegistry

            promotion = PromotionRegistry()
        self._promotion = promotion

    @staticmethod
    def _dense_bucket(
        curve: dict[str, Any], mid_prob: float, default_buckets: int, default_min: int
    ) -> dict[str, Any] | None:
        n_buckets = int(curve.get("n_buckets") or default_buckets)
        min_n = int(curve.get("min_bucket_n") or default_min)
        buckets = curve.get("buckets") or []
        idx = min(n_buckets - 1, max(0, int(mid_prob * n_buckets)))
        if idx >= len(buckets):
            return None
        bucket = buckets[idx]
        if int(bucket.get("n") or 0) >= min_n and bucket.get("yes_rate") is not None:
            return bucket
        return None

    def _bucket_for(
        self, mid_prob: float, exact_scope: str
    ) -> tuple[dict[str, Any], str] | None:
        """Return a dense verified curve for the target's *exact* scope.

        Global, vertical, and cross-horizon curves remain in the artifact as
        report diagnostics only. A target never borrows them: otherwise an
        exact-scope promotion could grant authority to a probability learned
        from a different league, asset, market type, or horizon.
        """
        if (
            self._curve is None
            or int(self._curve.get("schema_version") or 0) < CURVE_SCHEMA_VERSION
            or self._curve.get("evidence_mode") != LIVE_EVIDENCE_MODE
        ):
            return None
        curve = (self._curve.get("exact_scopes") or {}).get(exact_scope)
        if not isinstance(curve, dict):
            return None
        bucket = self._dense_bucket(
            curve, mid_prob, N_VERTICAL_BUCKETS, MIN_VERTICAL_BUCKET_N
        )
        return (bucket, exact_scope) if bucket is not None else None

    @staticmethod
    def _market_context(market: MarketView) -> tuple[float, str, str] | None:
        from autonomy.target_policy import is_prediction_quarantined_target

        if is_prediction_quarantined_target(
            market.ticker,
            category=(market.raw or {}).get("category"),
            vertical=market.vertical,
        ):
            return None
        if str(market.status or "").strip().lower() not in {"active", "open"}:
            return None
        now = datetime.now(timezone.utc)
        if market.fetched_at is not None:
            fetched = _parse_utc(market.fetched_at)
            if fetched is None or fetched > now:
                return None
        observed = now
        hours = _hours_to_expiry(market.close_time, observed.isoformat())
        if hours is None:
            return None
        horizon = _horizon_bucket(hours)
        exact_scope = _exact_curve_scope(market.ticker, horizon)
        if exact_scope is None:
            return None
        return hours, horizon, exact_scope

    def _is_explicitly_promoted(
        self, market: MarketView, features: dict[str, Any]
    ) -> bool:
        check = getattr(self._promotion, "is_promoted_signal", None)
        if not callable(check):
            return False
        try:
            return bool(check(self.name, market.ticker, features))
        except Exception:  # noqa: BLE001 - corrupt authority state fails closed
            return False

    def applicable(self, market: MarketView) -> bool:
        from autonomy.quote_quality import honest_implied_yes

        implied = honest_implied_yes(market.yes_bid, market.yes_ask)
        context = self._market_context(market)
        if implied is None or context is None:
            return False
        _hours, _horizon, exact_scope = context
        mid_prob = min(0.995, max(0.005, implied))
        return self._bucket_for(mid_prob, exact_scope) is not None

    def generate(self, market: MarketView) -> Signal | None:
        # Honest-quote gate (Wave-5 discipline): a phantom mid on a dead book
        # is not a price level; opining on it would re-import the fabrication
        # the measurement layer just evicted.
        from autonomy.quote_quality import honest_implied_yes

        implied = honest_implied_yes(market.yes_bid, market.yes_ask)
        context = self._market_context(market)
        if implied is None or context is None:
            return None
        mid_prob = min(0.995, max(0.005, implied))
        hours, horizon, exact_scope = context
        found = self._bucket_for(mid_prob, exact_scope)
        if found is None:
            return None
        bucket, curve_scope = found
        rate = float(bucket["yes_rate"])
        n = int(bucket["n"])
        # Binomial standard error widens the opinion where history is thinner.
        se = math.sqrt(max(1e-9, rate * (1.0 - rate)) / n)
        p_yes = min(0.995, max(0.005, rate))
        features: dict[str, Any] = {
            "mid_prob": mid_prob,
            "bucket_n": n,
            "bucket_yes_rate": rate,
            "curve_scope": curve_scope,
            "horizon_bucket": horizon,
            "hours_to_close": hours,
            "vertical": market.vertical.value,
            "market_type": f"{_market_type(market.ticker)}@{horizon}",
            "curve_schema_version": self._curve.get("schema_version"),
            "curve_evidence_mode": self._curve.get("evidence_mode"),
            "curve_training_digest": self._curve.get("training_digest_sha256"),
            "curve_created_at": self._curve.get("created_at"),
            "challenger_only": True,
            # The autonomous ladder cannot opt this source in from in-sample
            # fit: only the forward-registered exact scopes (stamped below)
            # are promotion-eligible; every other scope stays opted out.
            "promotion_eligible": False,
            "forward_calibration_required": True,
            "execution_authority": False,
        }
        try:
            from autonomy.taxonomy import grading_scope

            features["promotion_eligible"] = (
                grading_scope(self.name, market.ticker, features)
                in PROMOTION_ELIGIBLE_SCOPES
            )
        except Exception:  # noqa: BLE001 - fail closed: stays opted out
            features["promotion_eligible"] = False
        promoted = self._is_explicitly_promoted(market, features)
        features["report_only"] = not promoted
        features["prediction_authority"] = promoted
        features["promoted_exact_scope"] = promoted
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=p_yes,
            uncertainty=min(0.5, max(0.06, 0.08 + 2.0 * se)),
            rationale=(
                f"empirical debias[{curve_scope}]: mid {mid_prob:.2f} bucket "
                f"[{bucket['lo']:.2f},{bucket['hi']:.2f}) resolved YES {rate:.1%} over n={n}"
            ),
            features=features,
        )
