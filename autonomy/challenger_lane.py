"""Isolated challenger decision lane: makes forward promotion evidence reachable.

The auto-promotion forward-evidence gate (``auto_promotion_runner.
realized_attribution``) only credits a registered candidate when a decision's
``sources_used`` parses to EXACTLY ``{candidate_source: 1.0}``, the underlying
signal carries the registered ``promotion_candidate_fingerprint``, and signal /
receipt / decision / fill / settlement timestamps are strictly ordered after
``registered_at``.  No pre-existing code path could produce such a decision:
challengers are filtered out of fusion before the allocator ever sees them, so
the gate was unreachable for the entire history of the project.

This module closes that gap with a PAPER-ONLY lane that, once per cycle, books
one tiny isolated probe decision per (registered candidate, market):

  * probability comes from the challenger signal ALONE (``sources_used`` is
    ``{source: 1.0}``), never from the fused ensemble;
  * side is the challenger's edge against the honest market implied
    probability; size is fixed at ``LANE_CONTRACTS`` (1 contract);
  * every lane decision id carries the ``chal-`` prefix so every downstream
    consumer can identify (and exclude) lane rows;
  * execution is synthetic and shadow-only in EVERY session mode: the lane
    records an immediate conservative taker fill at the displayed ask (we pay
    the spread and the taker fee), then settles its own rows from recorded
    canonical settlements on later cycles.  It never constructs an order,
    never calls the executor, and carries no broker authority.

Why the executor's real shadow booking is deliberately NOT reused: shadow-book
rows surface in ``ledger.open_decisions("shadow")``, which the SHADOW-mode
brain uses for ``_open_positions`` -- lane rows would then occupy stage
position caps, inflate ``state.open_exposure_cents``, and (worse) be settled
by ``PredatorBrain._close_position``, mutating ``state.daily_pnl_cents`` /
``settled_count_at_stage`` / ``realized_pnl_per_contract_cents``.  The lane's
isolation guarantee ("never mutates risk state, exposure, or bankroll") is
fail-closed and takes priority, so the lane books a synthetic ``FILLED``
witness instead: without any ``SHADOW``-kind outcome the row is invisible to
BOTH scoped books (``is_shadow=0`` and ``is_live=0``), invisible to
``reconcile_shadow_orders`` and ``top_threat``, and skipped by
``reconcile_open_orders`` (``shadow-`` order-id prefix, ``order_active=0``).
The gate itself accepts ``FILLED`` as a fill witness, so forward evidence
accrues identically.

Isolation guarantees (each has a test in ``tests/test_challenger_lane.py``):
  * the lane never receives or touches ``RiskState``;
  * lane rows never appear in either scoped brain book;
  * lane decisions never count toward ``report.orders_placed`` or
    ``MAX_ORDERS_PER_CYCLE`` (the brain callsite does not touch them);
  * at most ``DUMMY_CHALLENGER_LANE_MAX_PER_CYCLE`` (default 10) decisions
    per cycle; the whole lane sits behind ``DUMMY_CHALLENGER_LANE_ENABLED``
    (default on);
  * every per-candidate failure is caught and surfaced as a
    ``challenger_lane_error:<source>:<ExcType>`` report note -- no silent
    passes.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

from autonomy.ontology import (
    Decision,
    DecisionAction,
    Forecast,
    MarketView,
    OutcomeKind,
    TradeOutcome,
)

ENABLED_ENV = "DUMMY_CHALLENGER_LANE_ENABLED"
MAX_PER_CYCLE_ENV = "DUMMY_CHALLENGER_LANE_MAX_PER_CYCLE"
DEFAULT_MAX_PER_CYCLE = 10
DECISION_PREFIX = "chal-"
# One contract: enough for witnessed-fill net-P&L evidence, small enough that
# even a hostile run of lane fills cannot meaningfully move any aggregate.
LANE_CONTRACTS = 1

# Same absolute anchor the ledger's fingerprint stamper uses -- the runner's
# module-level constant is cwd-relative and this lane must not depend on cwd.
REGISTRATIONS_PATH = (
    Path(__file__).resolve().parents[1]
    / "runtime" / "autonomy" / "promotion_forward_registrations.json"
)


def lane_enabled() -> bool:
    raw = str(os.environ.get(ENABLED_ENV, "1")).strip().lower()
    return raw not in {"0", "false", "off", "no"}


def lane_max_per_cycle() -> int:
    """Per-cycle decision cap; malformed operator input fails closed to 0."""
    raw = os.environ.get(MAX_PER_CYCLE_ENV)
    if raw is None:
        return DEFAULT_MAX_PER_CYCLE
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 0
    return max(0, value)


def load_lane_registrations(
    path: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Scope -> registration via the promotion runner's own validated loader.

    Reusing ``load_forward_registrations`` guarantees the lane can never book
    evidence for an entry the gate itself would refuse to read.
    """
    from autonomy.auto_promotion_runner import load_forward_registrations

    return load_forward_registrations(Path(path or REGISTRATIONS_PATH))


def emit_isolated_challenger_decisions(
    ledger: Any,
    scored: Sequence[tuple[MarketView, Any, Sequence[Any]]],
    *,
    mode: str | None = None,
    notes: list[str] | None = None,
    max_per_cycle: int | None = None,
    registrations: Mapping[str, Mapping[str, Any]] | None = None,
    trading_active: bool = True,
) -> dict[str, int]:
    """Run one lane pass: settle matured lane rows, then emit new probes.

    ``scored`` is the brain's post-fusion list of ``(market, forecast,
    signals)`` triples; only the market and the raw per-source signals are
    read.  ``mode`` is provenance only -- the lane behaves identically in
    SHADOW and LIVE sessions because it never executes anything.  When the
    venue reports ``trading_active=False`` no probe is booked (a fill nobody
    could have taken is not evidence) but matured lane rows still settle.
    Returns ``{"emitted": n, "settled": m}``.
    """
    if notes is None:
        notes = []
    if not lane_enabled():
        return {"emitted": 0, "settled": 0}
    if registrations is None:
        try:
            registrations = load_lane_registrations()
        except Exception as exc:  # noqa: BLE001 - fail closed, surfaced
            notes.append(
                f"challenger_lane_error:registrations:{type(exc).__name__}"
            )
            return {"emitted": 0, "settled": 0}
    settled = _settle_lane_positions(ledger, notes)
    cap = (
        lane_max_per_cycle()
        if max_per_cycle is None
        else max(0, int(max_per_cycle))
    )
    emitted = 0
    if registrations and cap > 0 and trading_active:
        registered_sources = {
            scope.split("|", 1)[0] for scope in registrations
        }
        seen: set[tuple[str, str]] = set()
        for market, _forecast, signals in scored:
            if emitted >= cap:
                break
            for signal in signals:
                if emitted >= cap:
                    break
                source = str(getattr(signal, "source", "") or "")
                if source not in registered_sources:
                    continue
                key = (source, str(market.ticker))
                if key in seen:
                    continue
                seen.add(key)
                try:
                    if _emit_one(ledger, market, signal, registrations, mode):
                        emitted += 1
                except Exception as exc:  # noqa: BLE001 - per-candidate wall
                    notes.append(
                        f"challenger_lane_error:{source}:{type(exc).__name__}"
                    )
    if emitted or settled:
        notes.append(f"challenger_lane:emitted={emitted}:settled={settled}")
    return {"emitted": emitted, "settled": settled}


def _emit_one(
    ledger: Any,
    market: MarketView,
    signal: Any,
    registrations: Mapping[str, Mapping[str, Any]],
    mode: str | None,
) -> bool:
    """Book one isolated paper probe; True when a decision was recorded."""
    from autonomy.quote_quality import honest_implied_yes
    from autonomy.taxonomy import grading_scope

    features = dict(getattr(signal, "features", None) or {})
    scope = grading_scope(str(signal.source), str(market.ticker), features)
    if scope not in registrations:
        return False  # registered source, but not the registered exact scope
    # A market with a recorded result is history, not a forecasting target.
    if ledger.settlement_result(market.ticker) is not None:
        return False
    implied = honest_implied_yes(market.yes_bid, market.yes_ask)
    if implied is None:
        return False  # no honest two-sided quote to price an edge against
    probability = float(signal.probability_yes)
    side = "yes" if probability >= implied else "no"
    ask = market.yes_ask if side == "yes" else market.no_ask
    try:
        price_cents = int(ask)
    except (TypeError, ValueError):
        return False
    if not (1 <= price_cents <= 99):
        return False
    win_probability = probability if side == "yes" else 1.0 - probability
    decision_id = DECISION_PREFIX + uuid.uuid4().hex[:12]
    forecast = Forecast(
        market_ticker=market.ticker,
        probability_yes=probability,
        uncertainty=float(signal.uncertainty),
        sources_used={str(signal.source): 1.0},
        market_implied_yes=implied,
        edge_yes=probability - implied,
        rationale=(
            f"challenger_lane[{scope}]: isolated candidate probe, "
            f"p={probability:.3f} vs implied={implied:.3f}"
        ),
    )
    decision = Decision(
        decision_id=decision_id,
        market_ticker=market.ticker,
        action=DecisionAction.BUY_YES if side == "yes" else DecisionAction.BUY_NO,
        side=side,
        price_cents=price_cents,
        count=LANE_CONTRACTS,
        ev_cents_per_contract=round(win_probability * 100.0 - price_cents, 2),
        kelly_fraction=0.0,
        notional_cents=price_cents * LANE_CONTRACTS,
        forecast=forecast,
        risk_snapshot={
            "challenger_lane": True,
            "isolated_candidate_probe": True,
            "registration_scope": scope,
            "session_mode": str(mode or "unknown"),
            "risk_authority": "none_paper_evidence_only",
        },
    )
    ledger.record_decision(decision)
    # Synthetic conservative taker fill at the displayed ask: we cross the
    # book we just observed, pay the spread now and the taker fee at
    # settlement. FILLED (never SHADOW-kind) keeps the row out of both scoped
    # brain books -- see the module docstring for the full isolation argument.
    ledger.record_outcome(TradeOutcome(
        decision_id=decision_id,
        market_ticker=market.ticker,
        kind=OutcomeKind.FILLED,
        order_id=f"shadow-{decision_id}",
        fill_count=LANE_CONTRACTS,
        fill_price_cents=price_cents,
        pnl_cents=None,
        broker_contacted=False,
        detail={
            "reason": "challenger_lane_synthetic_taker_fill",
            "challenger_lane": True,
            "liquidity_role": "taker",
            "fill_price_source": "displayed_ask_at_decision",
            "observed_ask_cents": price_cents,
            "registration_scope": scope,
        },
    ))
    return True


def _settle_lane_positions(ledger: Any, notes: list[str]) -> int:
    """Grade every filled lane row whose market has a canonical settlement.

    The brain's own settlement path never sees lane rows (by design), so the
    lane closes its own book from ``settlement_result`` facts recorded by the
    normal reconciler sweeps. Taker-fee P&L via ``settlement_pnl_cents`` --
    the same arithmetic the brain uses for real shadow positions.
    """
    from autonomy.reconciler import settlement_pnl_cents

    try:
        open_rows = list(ledger.open_decisions())
    except Exception as exc:  # noqa: BLE001 - fail closed, surfaced
        notes.append(
            f"challenger_lane_error:settle_sweep:{type(exc).__name__}"
        )
        return 0
    settled = 0
    for row in open_rows:
        decision_id = str(row.get("decision_id") or "")
        if not decision_id.startswith(DECISION_PREFIX):
            continue
        try:
            ticker = str(row.get("market_ticker") or "")
            result = ledger.settlement_result(ticker)
            if result is None:
                continue
            filled = int(row.get("filled_count") or 0)
            if filled <= 0:
                # Defensive: a lane row is booked with its fill in one pass,
                # but a half-written row must still terminate cleanly.
                ledger.record_outcome(TradeOutcome(
                    decision_id=decision_id,
                    market_ticker=ticker,
                    kind=OutcomeKind.EXPIRED,
                    order_id=str(row.get("order_id") or ""),
                    fill_count=0,
                    fill_price_cents=None,
                    pnl_cents=None,
                    broker_contacted=False,
                    detail={
                        "reason": "challenger_lane_settled_without_fill",
                        "challenger_lane": True,
                    },
                ))
                continue
            fill_price = row.get("fill_price_cents")
            price_cents = int(
                fill_price if fill_price is not None else row["price_cents"]
            )
            pnl = settlement_pnl_cents(
                str(row.get("side") or "").lower(),
                price_cents,
                filled,
                bool(result),
                market_ticker=ticker,
                liquidity_role="taker",
            )
            ledger.record_outcome(TradeOutcome(
                decision_id=decision_id,
                market_ticker=ticker,
                kind=(
                    OutcomeKind.SETTLED_WIN if pnl > 0
                    else OutcomeKind.SETTLED_LOSS
                ),
                order_id=str(row.get("order_id") or ""),
                fill_count=filled,
                fill_price_cents=price_cents,
                pnl_cents=pnl,
                broker_contacted=False,
                detail={
                    "reason": "challenger_lane_settlement",
                    "challenger_lane": True,
                    "result_yes": bool(result),
                    "liquidity_role": "taker",
                },
            ))
            settled += 1
        except Exception as exc:  # noqa: BLE001 - per-row wall
            notes.append(
                f"challenger_lane_error:settle:{type(exc).__name__}"
            )
    return settled
