"""Forward-only performance accounting for versioned betting-guide tiers.

Forecast skill and realized trade economics are intentionally separate:

* forecast performance grades one receipt-bounded fused emission per settled
  market and the value side stored at issue time;
* realized performance includes only decisions bound to an immutable canonical
  settlement and a prior shadow- or broker-witnessed positive fill, and uses
  witnessed cost/fee details when available.

Legacy forecasts are never retroactively relabelled under the current policy.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from collections import defaultdict
from typing import Any, Iterable

from autonomy.correlation import group_key
from autonomy.fees import kalshi_maker_fee_cents, kalshi_taker_fee_cents
from autonomy.retention import install_signal_history
from autonomy.tier_policy import (
    MAX_QUOTE_AGE_SECONDS,
    MAX_QUOTE_FUTURE_SKEW_SECONDS,
    TIER_POLICY_SHA256,
    TIER_POLICY_SPEC,
    TIER_POLICY_VERSION,
    tier_snapshot_is_valid,
)

POLICY_EFFECTIVE_AT = "2026-07-22T00:00:00+00:00"
_TIER_ORDER = ("A", "B", "C", "WATCH")
_DISTRIBUTION_ORDER = (*_TIER_ORDER, "UNATTRIBUTED")
MIN_FORWARD_N = 30
MIN_FORWARD_EVENT_CLUSTERS = 10
CLUSTER_BOOTSTRAP_SAMPLES = 1000


def _parse_ts(value: Any) -> float | None:
    from autonomy.strategy_miner import _parse_ts as parse

    return parse(value)


def _wilson(successes: int, total: int) -> dict[str, float] | None:
    if total <= 0:
        return None
    z = 1.959963984540054
    p = successes / total
    denominator = 1.0 + z * z / total
    center = (p + z * z / (2.0 * total)) / denominator
    margin = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * total)) / total) / denominator
    return {"low": round(max(0.0, center - margin), 4), "high": round(min(1.0, center + margin), 4)}


def _tier_name(value: Any) -> str:
    return str(value) if value in {"A", "B", "C"} else "WATCH"


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _canonical_tier_score(value: Any) -> float | None:
    """Normalize scores to the precision frozen by the tier snapshot."""
    parsed = _safe_float(value)
    return None if parsed is None else round(parsed, 6)


def _evidence_status(n: int, clusters: int) -> str:
    return (
        "FORWARD_SAMPLE_AVAILABLE"
        if n >= MIN_FORWARD_N and clusters >= MIN_FORWARD_EVENT_CLUSTERS
        else "INSUFFICIENT_SAMPLE"
    )


def _valid_tier_receipt_times(
    features: dict[str, Any], *, no_later_than: float,
) -> tuple[float, float] | None:
    """Validate that frozen quote evidence really preceded the issued record."""
    quote_ts = _parse_ts(features.get("tier_quote_fetched_at"))
    assessed_ts = _parse_ts(features.get("tier_assessed_at"))
    claimed_age = _safe_float(features.get("tier_quote_age_seconds"))
    if quote_ts is None or assessed_ts is None or claimed_age is None:
        return None
    observed_age = assessed_ts - quote_ts
    if (
        observed_age < -MAX_QUOTE_FUTURE_SKEW_SECONDS
        or observed_age > MAX_QUOTE_AGE_SECONDS
        or abs(observed_age - claimed_age) > 0.01
        or assessed_ts > no_later_than
    ):
        return None
    return quote_ts, assessed_ts


def _cluster_mean_ci(
    rows: list[dict[str, Any]],
    value: Any,
    *,
    seed: str,
) -> dict[str, float] | None:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        parsed = _safe_float(value(row))
        if parsed is not None:
            grouped[str(row["event_key"])].append(parsed)
    cluster_aggregates = [
        (sum(values), len(values)) for values in grouped.values() if values
    ]
    if len(cluster_aggregates) < 2:
        return None
    rng = random.Random(int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16], 16))
    draws: list[float] = []
    for _ in range(CLUSTER_BOOTSTRAP_SAMPLES):
        sampled_total = 0.0
        sampled_n = 0
        for _cluster in cluster_aggregates:
            cluster_total, cluster_n = rng.choice(cluster_aggregates)
            sampled_total += cluster_total
            sampled_n += cluster_n
        draws.append(sampled_total / sampled_n)
    draws.sort()
    return {
        "low": round(draws[int(0.025 * (len(draws) - 1))], 4),
        "high": round(draws[int(0.975 * (len(draws) - 1))], 4),
        "event_clusters": len(cluster_aggregates),
    }


def _cluster_roi_ci(rows: list[dict[str, Any]], *, seed: str) -> dict[str, float] | None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["event_key"])].append(row)
    cluster_totals = [
        (
            sum(int(row["pnl_cents"]) for row in bucket),
            sum(max(0, int(row["cost_cents"])) for row in bucket),
        )
        for bucket in grouped.values()
    ]
    if len(cluster_totals) < 2:
        return None
    rng = random.Random(int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16], 16))
    draws: list[float] = []
    for _ in range(CLUSTER_BOOTSTRAP_SAMPLES):
        sample = [rng.choice(cluster_totals) for _cluster in cluster_totals]
        pnl = sum(row[0] for row in sample)
        cost = sum(row[1] for row in sample)
        if cost > 0:
            draws.append(pnl / cost)
    if not draws:
        return None
    draws.sort()
    return {
        "low": round(draws[int(0.025 * (len(draws) - 1))], 4),
        "high": round(draws[int(0.975 * (len(draws) - 1))], 4),
        "event_clusters": len(cluster_totals),
    }


def _forecast_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0, "evidence_status": "COLLECTING_FORWARD_EVIDENCE"}
    briers: list[float] = []
    losses: list[float] = []
    side_rows: list[dict[str, Any]] = []
    market_briers: list[float] = []
    edges: list[float] = []
    calibration: list[tuple[float, int]] = []
    for row in rows:
        p = min(1.0, max(0.0, float(row["probability_yes"])))
        y = int(row["result_yes"])
        briers.append((p - y) ** 2)
        clipped = min(1.0 - 1e-12, max(1e-12, p))
        losses.append(-(y * math.log(clipped) + (1 - y) * math.log(1.0 - clipped)))
        calibration.append((p, y))
        side = row.get("value_side")
        if side in {"yes", "no"}:
            side_rows.append({
                **row,
                "value_side_hit": (side == "yes") == bool(y),
            })
        market = _safe_float(row.get("market_probability"))
        if market is not None and 0.0 <= market <= 1.0:
            market_briers.append((market - y) ** 2)
        edge = _safe_float(row.get("after_fee_edge"))
        if edge is not None:
            edges.append(edge)

    bins: list[dict[str, Any]] = []
    weighted_gap = 0.0
    max_gap = 0.0
    for index in range(10):
        low, high = index / 10.0, (index + 1) / 10.0
        members = [
            (p, y) for p, y in calibration
            if low <= p < high or (index == 9 and p == 1.0)
        ]
        if not members:
            continue
        predicted = sum(p for p, _ in members) / len(members)
        observed = sum(y for _, y in members) / len(members)
        gap = abs(predicted - observed)
        weighted_gap += len(members) * gap
        max_gap = max(max_gap, gap)
        bins.append({
            "range": f"{low:.1f}-{high:.1f}",
            "n": len(members),
            "predicted_mean": round(predicted, 4),
            "observed_rate": round(observed, 4),
        })
    mean_brier = sum(briers) / len(briers)
    side_wins = sum(bool(row["value_side_hit"]) for row in side_rows)
    clusters = len({str(row["event_key"]) for row in rows})
    output: dict[str, Any] = {
        "n": len(rows),
        "event_clusters": clusters,
        "value_side_n": len(side_rows),
        "value_side_wins": side_wins,
        "value_side_hit_rate": (
            round(side_wins / len(side_rows), 4) if side_rows else None
        ),
        "value_side_hit_rate_descriptive_wilson_ci95": _wilson(
            side_wins, len(side_rows)
        ),
        "value_side_hit_rate_cluster_ci95": _cluster_mean_ci(
            side_rows,
            lambda row: 1.0 if row["value_side_hit"] else 0.0,
            seed="tier-forecast-hit",
        ),
        "mean_brier": round(mean_brier, 6),
        "mean_log_loss": round(sum(losses) / len(losses), 6),
        "expected_calibration_error": round(weighted_gap / len(rows), 6),
        "maximum_calibration_error": round(max_gap, 6),
        "calibration_bins": bins,
        "mean_assigned_after_fee_edge": (
            round(sum(edges) / len(edges), 6) if edges else None
        ),
        "evidence_status": _evidence_status(len(rows), clusters),
    }
    if market_briers:
        mean_market = sum(market_briers) / len(market_briers)
        # Positive means the model's Brier was lower (better).
        paired = []
        for row in rows:
            market = _safe_float(row.get("market_probability"))
            if market is not None and 0.0 <= market <= 1.0:
                paired.append(row)
        paired_model = sum(
            (float(row["probability_yes"]) - int(row["result_yes"])) ** 2
            for row in paired
        ) / len(paired)
        output.update({
            "market_comparison_n": len(market_briers),
            "market_comparison_baseline": (
                "selected_side_executable_ask_bound_to_tier_snapshot"
            ),
            "mean_market_brier": round(mean_market, 6),
            "brier_advantage_vs_market": round(mean_market - paired_model, 6),
        })
    return output


def _latest_forward_forecasts(conn: Any) -> list[dict[str, Any]]:
    install_signal_history(conn)
    epoch_row = conn.execute(
        "SELECT first_signal_id FROM tier_policy_epochs WHERE policy_version=?",
        (TIER_POLICY_VERSION,),
    ).fetchone()
    first_signal_id = int(epoch_row[0]) if epoch_row is not None else 0
    decision_times: dict[str, float | None] = {}
    for ticker, created_at in conn.execute(
        "SELECT market_ticker,created_at FROM decisions"
    ):
        key = str(ticker)
        stamp = _parse_ts(created_at)
        if stamp is None:
            decision_times[key] = None
        elif key not in decision_times:
            decision_times[key] = stamp
        elif decision_times[key] is not None:
            decision_times[key] = min(float(decision_times[key]), stamp)

    rows = conn.execute(
        """
        SELECT sig.id,sig.market_ticker,sig.probability_yes,sig.uncertainty,
               sig.created_at,sig.ingested_at,sig.mode,sig.features,
               st.result_yes,st.settled_at
        FROM signal_history sig
        JOIN settlements st ON st.market_ticker=sig.market_ticker
        WHERE sig.source='fused_forecast'
          AND LOWER(sig.mode)='live'
          AND sig.id>=?
          AND datetime(sig.created_at)>=datetime(?)
          AND sig.features LIKE ?
        """,
        (
            first_signal_id,
            POLICY_EFFECTIVE_AT,
            f'%"tier_policy_version":"{TIER_POLICY_VERSION}"%',
        ),
    ).fetchall()
    latest: dict[str, tuple[tuple[float, float, int], dict[str, Any]]] = {}
    for (
        row_id, ticker, probability, uncertainty, created_at, ingested_at,
        mode, features_raw, result, settled_at,
    ) in rows:
        ticker = str(ticker)
        created = _parse_ts(created_at)
        ingested = _parse_ts(ingested_at)
        settled = _parse_ts(settled_at)
        if created is None or ingested is None or settled is None or ingested < created:
            continue
        try:
            features = json.loads(features_raw or "{}")
        except (TypeError, ValueError):
            continue
        if not tier_snapshot_is_valid(features, ticker=ticker):
            continue
        close = _parse_ts(features.get("tier_close_time"))
        if close is None:
            continue
        cutoff = min(settled, close)
        if ticker in decision_times:
            decision = decision_times[ticker]
            if decision is None:
                continue
            cutoff = min(cutoff, float(decision))
        if created > cutoff or ingested > cutoff:
            continue
        receipt_times = _valid_tier_receipt_times(
            features, no_later_than=created
        )
        if receipt_times is None:
            continue
        p = _safe_float(probability)
        u = _safe_float(uncertainty)
        if p is None or u is None or not 0.0 <= p <= 1.0 or not 0.0 <= u <= 0.5:
            continue
        snapshot_uncertainty = _safe_float(features.get("tier_uncertainty"))
        ask = _safe_float(features.get("tier_entry_price_cents"))
        gross = _safe_float(features.get("tier_gross_executable_edge"))
        side = features.get("tier_side")
        if (
            snapshot_uncertainty is None
            or abs(snapshot_uncertainty - u) > 1e-6
            or ask is None
            or gross is None
            or side not in {"yes", "no"}
        ):
            continue
        win_probability = p if side == "yes" else 1.0 - p
        if abs(gross - (win_probability - ask / 100.0)) > 1e-6:
            continue
        try:
            y = 1 if int(result) else 0
        except (TypeError, ValueError):
            continue
        rank = (created, ingested, int(row_id))
        # ``market_implied_yes`` is not part of the immutable tier digest and
        # therefore cannot support a comparative-skill claim. Derive the
        # baseline from the selected-side executable ask that *is* bound into
        # and semantically checked by the tier snapshot.
        quote_implied_yes = (
            float(ask) / 100.0 if side == "yes" else 1.0 - float(ask) / 100.0
        )
        record = {
            "ticker": ticker,
            "probability_yes": p,
            "uncertainty": u,
            "result_yes": y,
            "tier": _tier_name(features.get("tier")),
            "value_side": features.get("tier_side"),
            "market_probability": quote_implied_yes,
            "after_fee_edge": features.get("tier_after_fee_edge"),
            "scope": str(features.get("tier_scope") or "OTHER"),
            "market_type": str(features.get("tier_market_type") or "market"),
            "horizon_phase": str(features.get("tier_horizon_phase") or "unknown"),
            "event_key": str(features.get("tier_event_key") or group_key(ticker)),
            "created_at": str(created_at),
            "settled_at": str(settled_at),
        }
        held = latest.get(ticker)
        if held is None or rank > held[0]:
            latest[ticker] = (rank, record)
    return [record for _rank, record in latest.values()]


def _trade_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0, "evidence_status": "COLLECTING_FORWARD_EVIDENCE"}
    ordered = sorted(rows, key=lambda row: (str(row["settled_at"]), str(row["decision_id"])))
    pnl = [int(row["pnl_cents"]) for row in ordered]
    cost = [max(0, int(row["cost_cents"])) for row in ordered]
    wins = sum(value > 0 for value in pnl)
    gross_wins = sum(max(0, value) for value in pnl)
    gross_losses = abs(sum(min(0, value) for value in pnl))
    equity = 0
    peak = 0
    drawdown = 0
    for value in pnl:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    total_cost = sum(cost)
    clusters = len({str(row["event_key"]) for row in rows})
    return {
        "n": len(rows),
        "event_clusters": clusters,
        "wins": wins,
        "losses": len(rows) - wins,
        "win_rate": round(wins / len(rows), 4),
        "win_rate_descriptive_wilson_ci95": _wilson(wins, len(rows)),
        "win_rate_cluster_ci95": _cluster_mean_ci(
            rows,
            lambda row: 1.0 if int(row["pnl_cents"]) > 0 else 0.0,
            seed="tier-realized-win",
        ),
        "net_pnl_cents": sum(pnl),
        "entry_cost_plus_fees_cents": total_cost,
        "roi": round(sum(pnl) / total_cost, 6) if total_cost > 0 else None,
        "roi_cluster_ci95": _cluster_roi_ci(rows, seed="tier-realized-roi"),
        "profit_factor": (
            round(gross_wins / gross_losses, 6) if gross_losses > 0 else None
        ),
        "max_drawdown_cents": drawdown,
        "exact_witnessed_cost_n": sum(bool(row["exact_cost"]) for row in rows),
        "evidence_status": _evidence_status(len(rows), clusters),
    }


def _forward_realized_trades(conn: Any) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT settle.id,settle.decision_id,settle.market_ticker,settle.kind,
               settle.pnl_cents,settle.created_at,
               d.market_ticker,d.action,d.side,d.probability_yes,
               d.forecast_uncertainty,d.created_at,d.count,
               a.tier_label,a.tier_score,a.tier_reason,a.snapshot_json,
               a.snapshot_sha256,a.assigned_at,a.recorded_at,
               fill.market_ticker,fill.kind,fill.order_id,fill.fill_count,
               fill.fill_price_cents,fill.broker_contacted,
               fill.detail,fill.created_at,
               canonical.result_yes,canonical.settled_at,
               CASE
                   WHEN fill.broker_contacted=0 AND EXISTS(
                       SELECT 1 FROM outcomes shadow_witness
                       WHERE shadow_witness.decision_id=settle.decision_id
                         AND shadow_witness.kind='SHADOW'
                         AND shadow_witness.id<=fill.id
                   ) THEN 'shadow'
                   WHEN fill.broker_contacted=1
                    AND fill.kind IN ('FILLED','PARTIALLY_FILLED')
                    AND fill.order_id IS NOT NULL
                    AND TRIM(fill.order_id)!=''
                    AND EXISTS(
                       SELECT 1 FROM outcomes accepted_witness
                       WHERE accepted_witness.decision_id=settle.decision_id
                         AND accepted_witness.kind='ACCEPTED'
                         AND accepted_witness.broker_contacted=1
                         AND accepted_witness.order_id=fill.order_id
                         AND accepted_witness.id<fill.id
                    ) THEN 'live'
                   ELSE 'unverified'
               END AS book
        FROM outcomes settle
        JOIN decisions d ON d.decision_id=settle.decision_id
        JOIN decision_tier_attribution a ON a.decision_id=settle.decision_id
        JOIN settlements canonical
          ON canonical.market_ticker=settle.market_ticker
        JOIN outcomes fill ON fill.id=(
            SELECT MAX(f.id) FROM outcomes f
            WHERE f.decision_id=settle.decision_id
              AND f.id<settle.id AND f.fill_count>0
              AND f.kind IN ('FILLED','PARTIALLY_FILLED','SHADOW')
        )
        WHERE settle.kind IN ('SETTLED_WIN','SETTLED_LOSS')
          AND settle.pnl_cents IS NOT NULL
          AND a.policy_version=?
          AND d.market_ticker=settle.market_ticker
          AND fill.market_ticker=settle.market_ticker
        ORDER BY settle.id
        """,
        (TIER_POLICY_VERSION,),
    ).fetchall()
    # A reconciler retry may append a second settlement outcome. Keep the
    # latest valid outcome per decision without manufacturing zero-P&L rows;
    # the joined settlement-table row remains the one canonical result.
    latest: dict[str, dict[str, Any]] = {}
    for (
        settlement_id, decision_id, ticker, settlement_kind, pnl, settled_at,
        decision_ticker, decision_action, decision_side, decision_probability,
        decision_uncertainty, decision_created_at, decision_count,
        tier_label, tier_score, tier_reason, snapshot_raw,
        snapshot_digest, assigned_at, recorded_at,
        fill_ticker, fill_kind, fill_order_id, fill_count, fill_price,
        fill_broker_contacted, fill_detail_raw, fill_at,
        canonical_result_yes, canonical_settled_at, book,
    ) in rows:
        try:
            snapshot = json.loads(snapshot_raw or "{}")
        except (TypeError, ValueError):
            snapshot = {}
        if (
            hashlib.sha256(str(snapshot_raw).encode("utf-8")).hexdigest()
            != str(snapshot_digest)
            or str(decision_ticker) != str(ticker)
            or str(fill_ticker) != str(ticker)
            or not tier_snapshot_is_valid(snapshot, ticker=str(ticker))
            or _tier_name(snapshot.get("tier")) != _tier_name(tier_label)
            or _canonical_tier_score(snapshot.get("tier_score"))
            != _canonical_tier_score(tier_score)
            or str(snapshot.get("tier_reason") or "") != str(tier_reason or "")
        ):
            continue
        expected_action = "BUY_YES" if decision_side == "yes" else "BUY_NO"
        if (
            decision_side not in {"yes", "no"}
            or decision_action != expected_action
            or snapshot.get("tier_side") != decision_side
        ):
            continue
        probability = _safe_float(decision_probability)
        uncertainty = _safe_float(decision_uncertainty)
        snapshot_uncertainty = _safe_float(snapshot.get("tier_uncertainty"))
        ask = _safe_float(snapshot.get("tier_entry_price_cents"))
        gross = _safe_float(snapshot.get("tier_gross_executable_edge"))
        if None in {probability, uncertainty, snapshot_uncertainty, ask, gross}:
            continue
        win_probability = (
            float(probability)
            if decision_side == "yes"
            else 1.0 - float(probability)
        )
        if (
            abs(float(snapshot_uncertainty) - float(uncertainty)) > 1e-6
            or abs(float(gross) - (win_probability - float(ask) / 100.0)) > 1e-6
        ):
            continue
        assigned_ts = _parse_ts(assigned_at)
        decision_created_ts = _parse_ts(decision_created_at)
        recorded_ts = _parse_ts(recorded_at)
        fill_ts = _parse_ts(fill_at)
        outcome_settled_ts = _parse_ts(settled_at)
        canonical_settled_ts = _parse_ts(canonical_settled_at)
        close_ts = _parse_ts(snapshot.get("tier_close_time"))
        receipt_times = (
            _valid_tier_receipt_times(snapshot, no_later_than=assigned_ts)
            if assigned_ts is not None else None
        )
        quote_ts, assessed_ts = receipt_times or (None, None)
        if (
            None in {
                assigned_ts, decision_created_ts, recorded_ts, fill_ts,
                outcome_settled_ts, canonical_settled_ts, close_ts,
                assessed_ts, quote_ts,
            }
            or not (
                float(quote_ts)
                <= float(assessed_ts) + MAX_QUOTE_FUTURE_SKEW_SECONDS
                and float(assessed_ts) <= float(assigned_ts)
                and abs(float(assigned_ts) - float(decision_created_ts)) <= 0.001
                and float(assigned_ts) <= float(recorded_ts)
                <= float(fill_ts) <= float(close_ts)
                and float(fill_ts) < float(canonical_settled_ts)
                <= float(outcome_settled_ts)
            )
        ):
            continue
        try:
            canonical_result = int(canonical_result_yes)
        except (TypeError, ValueError):
            continue
        if canonical_result not in {0, 1}:
            continue
        canonical_win = (
            (decision_side == "yes" and canonical_result == 1)
            or (decision_side == "no" and canonical_result == 0)
        )
        expected_settlement_kind = (
            "SETTLED_WIN" if canonical_win else "SETTLED_LOSS"
        )
        if settlement_kind != expected_settlement_kind or book == "unverified":
            continue
        try:
            detail = json.loads(fill_detail_raw or "{}")
        except (TypeError, ValueError):
            detail = {}
        try:
            count = int(fill_count)
            requested_count = int(decision_count)
            witnessed_fill_cost = detail.get("fill_cost_cents") is not None
            witnessed_fee = detail.get("execution_fee_cents") is not None
            exact_cost = witnessed_fill_cost and witnessed_fee
            if requested_count <= 0 or count <= 0 or count > requested_count:
                continue
            if fill_kind == "FILLED" and count != requested_count:
                continue
            if fill_kind == "PARTIALLY_FILLED" and count >= requested_count:
                continue
            price = int(fill_price) if fill_price is not None else None
            if price is not None and not 1 <= price <= 99:
                continue
            if witnessed_fill_cost:
                fill_cost = int(detail["fill_cost_cents"])
                if not 1 <= fill_cost <= 99 * count:
                    continue
                if (
                    price is not None
                    and abs(fill_cost - price * count) > max(1, count)
                ):
                    continue
            else:
                # Submitted limits are intentions, not fill-cost evidence.
                # A witnessed fill price is the minimum acceptable fallback.
                if fill_price is None:
                    continue
                if price is None:
                    continue
                fill_cost = price * count
            if witnessed_fee:
                fee = int(detail["execution_fee_cents"])
                if not 0 <= fee <= 2 * count:
                    continue
            else:
                modeled_price = (
                    int(fill_price)
                    if fill_price is not None
                    else round(fill_cost / count)
                )
                if not 1 <= modeled_price <= 99:
                    continue
                fee_fn = (
                    kalshi_maker_fee_cents
                    if str(detail.get("liquidity_role") or "").lower() == "maker"
                    else kalshi_taker_fee_cents
                )
                fee = fee_fn(modeled_price, count, str(ticker))
            expected_pnl = (
                100 * count - fill_cost - fee
                if settlement_kind == "SETTLED_WIN"
                else -fill_cost - fee
            )
            if int(pnl) != expected_pnl:
                continue
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        record = {
            "settlement_id": int(settlement_id),
            "decision_id": str(decision_id),
            "ticker": str(ticker),
            "tier": _tier_name(tier_label),
            "pnl_cents": int(pnl),
            "cost_cents": fill_cost + fee,
            "exact_cost": exact_cost,
            "book": str(book),
            "event_key": str(snapshot.get("tier_event_key") or group_key(str(ticker))),
            "scope": str(snapshot.get("tier_scope") or "OTHER"),
            "market_type": str(snapshot.get("tier_market_type") or "market"),
            "horizon_phase": str(
                snapshot.get("tier_horizon_phase") or "unknown"
            ),
            "settled_at": str(canonical_settled_at),
        }
        held = latest.get(str(decision_id))
        if held is None or record["settlement_id"] > held["settlement_id"]:
            latest[str(decision_id)] = record
    return list(latest.values())


def _group_metrics(
    rows: Iterable[dict[str, Any]],
    metric: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    by_tier_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_scope_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        tier = _tier_name(row.get("tier"))
        by_tier_rows[tier].append(row)
        by_scope_rows[f"{tier}|{row.get('scope') or 'OTHER'}"].append(row)
    by_tier = {tier: metric(by_tier_rows.get(tier, [])) for tier in _TIER_ORDER}
    by_scope = {
        key: metric(bucket) for key, bucket in sorted(by_scope_rows.items())
    }
    return by_tier, by_scope


def _fine_grained_metrics(
    rows: Iterable[dict[str, Any]], metric: Any,
) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = "|".join((
            _tier_name(row.get("tier")),
            str(row.get("scope") or "OTHER"),
            str(row.get("market_type") or "market"),
            str(row.get("horizon_phase") or "unknown"),
        ))
        buckets[key].append(row)
    return {key: metric(bucket) for key, bucket in sorted(buckets.items())}


def _scope_horizon_metrics(
    rows: Iterable[dict[str, Any]], metric: Any, *, include_tier: bool = False,
) -> dict[str, Any]:
    """Aggregate crypto/sports horizons without hiding them behind market type."""
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        parts = [
            str(row.get("scope") or "OTHER"),
            str(row.get("horizon_phase") or "unknown"),
        ]
        if include_tier:
            parts.insert(0, _tier_name(row.get("tier")))
        buckets["|".join(parts)].append(row)
    return {key: metric(bucket) for key, bucket in sorted(buckets.items())}


def current_tier_distribution(board: dict[str, Any] | None) -> dict[str, Any]:
    """Cheap current-board counts; safe for snapshot-backed dashboard routes."""
    if not isinstance(board, dict):
        return {"n": 0, "counts": {tier: 0 for tier in _DISTRIBUTION_ORDER}}
    flat: list[dict[str, Any]] = []
    for league in (board.get("groups") or {}).values():
        for rows in (league or {}).values():
            flat.extend(row for row in (rows or []) if isinstance(row, dict))
    if not flat and isinstance(board.get("top"), list) and int(board.get("rows") or 0) <= len(board["top"]):
        flat = [row for row in board["top"] if isinstance(row, dict)]
    counts = {tier: 0 for tier in _DISTRIBUTION_ORDER}
    scopes: dict[str, dict[str, int]] = defaultdict(
        lambda: {tier: 0 for tier in _DISTRIBUTION_ORDER}
    )
    for row in flat:
        is_current = (
            row.get("tier_policy_version") == TIER_POLICY_VERSION
            and row.get("tier_policy_sha256") == TIER_POLICY_SHA256
            and isinstance(row.get("tier_snapshot_sha256"), str)
            and len(str(row.get("tier_snapshot_sha256"))) == 64
        )
        tier = _tier_name(row.get("tier")) if is_current else "UNATTRIBUTED"
        counts[tier] += 1
        scopes[str(row.get("league") or "OTHER")][tier] += 1
    total = len(flat)
    return {
        "n": total,
        "counts": counts,
        "percentages": {
            tier: round(count / total, 4) if total else 0.0
            for tier, count in counts.items()
        },
        "by_scope": dict(scopes),
        "policy_versions": sorted({
            str(row.get("tier_policy_version")) for row in flat
            if row.get("tier_policy_version")
        }),
    }


def tier_performance_report(conn: Any) -> dict[str, Any]:
    """Build the version-separated, forward-only tier evidence report."""
    forecasts = _latest_forward_forecasts(conn)
    trades = _forward_realized_trades(conn)
    forecast_by_tier, forecast_by_scope = _group_metrics(forecasts, _forecast_metrics)
    realized_by_tier, realized_by_scope = _group_metrics(trades, _trade_metrics)
    forecast_overall = _forecast_metrics(forecasts)
    realized_overall = _trade_metrics(trades)
    realized_by_book: dict[str, Any] = {}
    for book in ("shadow", "live"):
        selected = [row for row in trades if row["book"] == book]
        tiers, _scopes = _group_metrics(selected, _trade_metrics)
        realized_by_book[book] = {"overall": _trade_metrics(selected), "by_tier": tiers}

    sufficient = any(
        block.get("evidence_status") == "FORWARD_SAMPLE_AVAILABLE"
        for block in (forecast_overall, realized_overall)
    )
    return {
        "schema_version": 1,
        "policy_version": TIER_POLICY_VERSION,
        "policy_sha256": TIER_POLICY_SHA256,
        "policy_spec": TIER_POLICY_SPEC,
        "legacy_backfill": False,
        "status": (
            "FORWARD_SAMPLE_AVAILABLE"
            if sufficient
            else "INSUFFICIENT_SAMPLE"
            if forecasts or trades
            else "COLLECTING_FORWARD_EVIDENCE"
        ),
        "forecast": {
            "population": "one latest receipt-bounded current-policy fused forecast per settled market",
            "overall": forecast_overall,
            "by_tier": forecast_by_tier,
            "by_tier_scope": forecast_by_scope,
            "by_scope_horizon": _scope_horizon_metrics(
                forecasts, _forecast_metrics
            ),
            "by_tier_scope_horizon": _scope_horizon_metrics(
                forecasts, _forecast_metrics, include_tier=True
            ),
            "by_tier_scope_market_horizon": _fine_grained_metrics(
                forecasts, _forecast_metrics
            ),
        },
        "realized": {
            "population": (
                "current-policy decisions bound to an immutable canonical "
                "settlement and a prior shadow- or broker-witnessed positive fill"
            ),
            "overall": realized_overall,
            "by_tier": realized_by_tier,
            "by_tier_scope": realized_by_scope,
            "by_scope_horizon": _scope_horizon_metrics(trades, _trade_metrics),
            "by_tier_scope_horizon": _scope_horizon_metrics(
                trades, _trade_metrics, include_tier=True
            ),
            "by_tier_scope_market_horizon": _fine_grained_metrics(
                trades, _trade_metrics
            ),
            "by_book": realized_by_book,
        },
        "caveat": (
            "Tier labels describe issued quote value under one policy version. "
            "Market-relative Brier uses only the digest-bound selected-side "
            "executable ask. Small samples are explicitly insufficient; tiers "
            "never grant execution authority."
        ),
    }
