"""Reconciler: order status, stale-order cancellation, settlement detection.

Reads broker state (authenticated GETs) and market results (public GETs),
turns them into ledger facts. Cancels resting orders that have gone stale —
a maker quote left behind by a moved market is adverse selection waiting to
happen.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Callable

from autonomy.fees import kalshi_maker_fee_cents, kalshi_taker_fee_cents
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import MarketView, OutcomeKind, TradeOutcome
from kalshi.strict_json import load_strict_json_response

STALE_ORDER_MINUTES = 45

# Schema stamp for the phantom-grading coverage receipt (2026-07-24 audit §8:
# "phantom grading coverage % is not emitted anywhere"). Bump only on a
# breaking shape change; dashboards read this block off the cycle report.
PHANTOM_COVERAGE_VERSION = "phantom-coverage-v1"
_KALSHI_PUBLIC_BASE = "https://external-api.kalshi.com/trade-api/v2"


def _series_of(ticker: str) -> str:
    """Series prefix of a Kalshi market ticker (``SERIES-EVENT-MARKET``)."""
    return str(ticker).split("-", 1)[0]


def _ratio(numerator: int, denominator: int) -> float | None:
    """Coverage ratio, or None when the denominator is empty (never 0/0=1)."""
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _dollar_amount(
    payload: dict[str, Any], dollars_key: str, cents_key: str,
) -> Decimal | None:
    """Read one cumulative monetary field, preferring subpenny dollars."""
    dollars = _decimal_or_none(payload.get(dollars_key))
    if dollars is not None:
        return dollars
    cents = _decimal_or_none(payload.get(cents_key))
    return None if cents is None else cents / Decimal(100)


def _whole_cents(amount_dollars: Decimal | None) -> int | None:
    if amount_dollars is None:
        return None
    return int((amount_dollars * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _public_base() -> str:
    """Return the reviewed production endpoint, never an ambient override."""
    return _KALSHI_PUBLIC_BASE


def _public_get(
    path: str,
    *,
    params: dict[str, Any] | None = None,
    timeout_seconds: float,
) -> Any:
    """GET broker truth without inheriting proxy or netrc configuration."""
    import httpx

    with httpx.Client(
        base_url=_KALSHI_PUBLIC_BASE,
        timeout=max(0.1, float(timeout_seconds)),
        trust_env=False,
    ) as client:
        return client.get(path, params=params)


def default_fetch_market_result(
    ticker: str,
    *,
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    response = _public_get(
        f"/markets/{ticker}",
        timeout_seconds=timeout_seconds,
    )
    response.raise_for_status()
    market = load_strict_json_response(response).get("market", {})
    return market if isinstance(market, dict) else {}


def default_fetch_settled_page(series_ticker: str, min_close_ts: int,
                               cursor: str | None = None) -> dict[str, Any]:
    """One page of recently settled markets for a series (public GET)."""
    params: dict[str, Any] = {
        "series_ticker": series_ticker, "status": "settled",
        "min_close_ts": min_close_ts, "limit": 200,
    }
    if cursor:
        params["cursor"] = cursor
    response = _public_get(
        "/markets",
        params=params,
        timeout_seconds=20,
    )
    response.raise_for_status()
    data = load_strict_json_response(response)
    return data if isinstance(data, dict) else {}


def default_fetch_trades(ticker: str, min_ts: int, max_ts: int) -> list[dict[str, Any]]:
    """Fetch standard-book public prints for an exact market/time window."""
    collected: list[dict[str, Any]] = []
    cursor: str | None = None
    for _page in range(5):
        params: dict[str, Any] = {
            "ticker": ticker, "min_ts": min_ts, "max_ts": max_ts,
            "is_block_trade": "false", "limit": 1000,
        }
        if cursor:
            params["cursor"] = cursor
        response = _public_get(
            "/markets/trades",
            params=params,
            timeout_seconds=20,
        )
        response.raise_for_status()
        payload = load_strict_json_response(response)
        rows = payload.get("trades") or []
        if isinstance(rows, list):
            collected.extend(row for row in rows if isinstance(row, dict))
        cursor = payload.get("cursor") or None
        if not cursor:
            break
    return collected


class Reconciler:
    def __init__(
        self,
        ledger: AutonomyLedger,
        fetch_market_result: Callable[[str], dict[str, Any]] | None = None,
        order_status_fn: Callable[[str], dict[str, Any]] | None = None,
        cancel_fn: Callable[[str], dict[str, Any]] | None = None,
        fetch_settled_page: Callable[..., dict[str, Any]] | None = None,
        fetch_shadow_candles: Callable[..., list[dict[str, Any]]] | None = None,
        fetch_shadow_trades: Callable[[str, int, int], list[dict[str, Any]]] | None = None,
    ) -> None:
        self.ledger = ledger
        self.fetch_market_result = fetch_market_result or default_fetch_market_result
        self.order_status_fn = order_status_fn
        self.cancel_fn = cancel_fn
        # Opt-in (None = disabled) so hermetic tests never hit the network.
        self.fetch_settled_page = fetch_settled_page
        self.fetch_shadow_candles = fetch_shadow_candles
        self.fetch_shadow_trades = fetch_shadow_trades
        # Coverage receipt for the most recent phantom-grading pass. Rewritten
        # on every call (never appended to) so a stale receipt can't be reported
        # as this cycle's coverage. See _forecast_coverage_receipt.
        self.last_forecast_coverage: dict[str, Any] = {
            "status": "NOT_RUN",
            "phantom_coverage_version": PHANTOM_COVERAGE_VERSION,
        }

    def _claim_settlement(self, ticker: str, result_yes: bool) -> bool:
        """Persist one settlement and return whether this worker owns grading.

        ``AutonomyLedger.record_settlement_if_new`` makes the claim atomic
        across processes.  Tiny ledger test doubles retain the legacy
        ``record_settlement`` protocol and are treated as the sole writer.
        """
        claim = getattr(self.ledger, "record_settlement_if_new", None)
        if callable(claim):
            return bool(claim(ticker, result_yes))
        self.ledger.record_settlement(ticker, result_yes)
        return True

    # ------------------------------------------------------------------
    # Settlements (public data; drives the whole learning loop)
    # ------------------------------------------------------------------

    def reconcile_settlements(self) -> list[tuple[str, bool]]:
        settled: list[tuple[str, bool]] = []
        for ticker in self.ledger.unsettled_traded_markets():
            try:
                market = self.fetch_market_result(ticker)
            except Exception:
                continue
            result = str(market.get("result", "")).lower()
            if result in ("yes", "no"):
                result_yes = result == "yes"
                if self._claim_settlement(ticker, result_yes):
                    settled.append((ticker, result_yes))
        return settled

    def reconcile_forecast_settlements(
        self,
        series_list: list[str],
        lookback_hours: float = 48.0,
        max_pages_per_series: int = 3,
    ) -> list[tuple[str, bool]]:
        """Phantom grading: settle every FORECASTED market, not just traded ones.

        The machine opines on ~1000 markets a cycle; every one that settles is
        free calibration evidence. Batch sweep: one settled-markets listing per
        watchlist series (cursor-paged), matched against tickers we recently
        signaled on. No per-ticker calls, no positions touched — settlements
        recorded here feed the learner only.

        Every pass writes a coverage receipt to ``self.last_forecast_coverage``
        (2026-07-24 audit: the "grades every priced market" claim was
        unverifiable because no coverage number was emitted anywhere). A series
        whose listing still has a cursor after ``max_pages_per_series`` pages —
        the 50+ strike ladder overflow — is disclosed as an explicit
        ``pagination_truncated`` flag instead of silent partial coverage.
        """
        requested = [str(series) for series in series_list]
        if self.fetch_settled_page is None or not requested:
            self.last_forecast_coverage = self._forecast_coverage_receipt(
                status=(
                    "NOT_ATTEMPTED_NO_LISTING_ENDPOINT"
                    if self.fetch_settled_page is None
                    else "NOT_ATTEMPTED_NO_SERIES"
                ),
                eligible=None,
                eligible_in_requested_series=0,
                attempted_eligible=0,
                graded=0,
                series_requested=len(requested),
                series_attempted=0,
                series_failed=[],
                series_truncated=[],
                max_pages_per_series=max_pages_per_series,
            )
            return []
        unsettled = set(self.ledger.unsettled_forecast_markets())
        # Snapshot the denominator BEFORE the sweep mutates ``unsettled``.
        eligible_total = len(unsettled)
        eligible_by_series: dict[str, int] = {}
        for ticker in unsettled:
            key = _series_of(ticker)
            eligible_by_series[key] = eligible_by_series.get(key, 0) + 1
        if not unsettled:
            self.last_forecast_coverage = self._forecast_coverage_receipt(
                status="NOTHING_ELIGIBLE",
                eligible=0,
                eligible_in_requested_series=0,
                attempted_eligible=0,
                graded=0,
                series_requested=len(requested),
                series_attempted=0,
                series_failed=[],
                series_truncated=[],
                max_pages_per_series=max_pages_per_series,
            )
            return []
        min_close_ts = int(datetime.now(timezone.utc).timestamp() - lookback_hours * 3600)
        settled: list[tuple[str, bool]] = []
        attempted_series: list[str] = []
        failed_series: list[str] = []
        truncated_series: list[str] = []
        for series in requested:
            cursor: str | None = None
            attempted = False
            failed = False
            for _page in range(max_pages_per_series):
                try:
                    data = self.fetch_settled_page(series, min_close_ts, cursor)
                except Exception:
                    failed = True
                    break  # one dead series never stalls the sweep
                attempted = True
                for market in data.get("markets", []):
                    ticker = str(market.get("ticker", ""))
                    if ticker not in unsettled:
                        continue
                    result = str(market.get("result", "")).lower()
                    if result in ("yes", "no"):
                        result_yes = result == "yes"
                        if self._claim_settlement(ticker, result_yes):
                            settled.append((ticker, result_yes))
                        unsettled.discard(ticker)
                cursor = data.get("cursor") or None
                if not cursor:
                    break
            if attempted:
                attempted_series.append(series)
            if failed:
                failed_series.append(series)
            elif cursor:
                # Page cap hit with the listing still unexhausted: the tail of
                # this series was never looked at this pass.
                truncated_series.append(series)
        incomplete = set(failed_series) | set(truncated_series)
        attempted_eligible = sum(
            eligible_by_series.get(series, 0)
            for series in set(attempted_series) - incomplete
        )
        self.last_forecast_coverage = self._forecast_coverage_receipt(
            status="SWEPT",
            eligible=eligible_total,
            eligible_in_requested_series=sum(
                eligible_by_series.get(series, 0) for series in set(requested)
            ),
            attempted_eligible=attempted_eligible,
            graded=len(settled),
            series_requested=len(requested),
            series_attempted=len(attempted_series),
            series_failed=failed_series,
            series_truncated=truncated_series,
            max_pages_per_series=max_pages_per_series,
        )
        return settled

    @staticmethod
    def _forecast_coverage_receipt(
        *,
        status: str,
        eligible: int | None,
        eligible_in_requested_series: int,
        attempted_eligible: int,
        graded: int,
        series_requested: int,
        series_attempted: int,
        series_failed: list[str],
        series_truncated: list[str],
        max_pages_per_series: int,
    ) -> dict[str, Any]:
        """Build one phantom-grading coverage receipt.

        Denominator (``eligible_unsettled_forecasts``): every market we priced
        inside the ledger's forecast window that still carries no settlement —
        exactly the set the phantom path was asked to cover
        (``AutonomyLedger.unsettled_forecast_markets``). ``None`` means the
        sweep never ran, so no denominator was ever established.

        ``attempt_coverage_ratio`` = ``attempted_eligible_forecasts`` /
        ``eligible_unsettled_forecasts``. An eligible ticker counts as
        ATTEMPTED only when its series listing was fetched to exhaustion this
        pass: the cursor ran out, the endpoint did not fail, and the page cap
        was not hit. Tickers whose series was never requested, whose listing
        errored, or whose pagination was truncated are excluded on purpose —
        the ratio exists to make unattempted work visible.

        ``graded_coverage_ratio`` = ``graded_this_pass`` /
        ``eligible_unsettled_forecasts``: the share of the ungraded backlog
        this pass actually resolved. It is expected to be small (most eligible
        markets have not closed yet); it is an honesty measure, not a target.
        """
        pages = max(0, int(max_pages_per_series))
        return {
            "phantom_coverage_version": PHANTOM_COVERAGE_VERSION,
            "status": status,
            "eligible_unsettled_forecasts": eligible,
            "eligible_in_requested_series": int(eligible_in_requested_series),
            "eligible_outside_requested_series": (
                None if eligible is None
                else max(0, int(eligible) - int(eligible_in_requested_series))
            ),
            "attempted_eligible_forecasts": int(attempted_eligible),
            "graded_this_pass": int(graded),
            "attempt_coverage_ratio": _ratio(
                int(attempted_eligible), int(eligible or 0)
            ),
            "graded_coverage_ratio": _ratio(int(graded), int(eligible or 0)),
            "series_requested": int(series_requested),
            "series_attempted": int(series_attempted),
            "series_failed": sorted(series_failed),
            "series_truncated": sorted(series_truncated),
            "max_pages_per_series": pages,
            "pagination_truncated": bool(series_truncated),
            "listing_errors": bool(series_failed),
            "complete": bool(
                status == "SWEPT"
                and not series_failed
                and not series_truncated
                and eligible is not None
                and int(attempted_eligible) >= int(eligible)
            ),
        }

    # ------------------------------------------------------------------
    # Open orders (authenticated; only in live mode)
    # ------------------------------------------------------------------

    def reconcile_open_orders(self) -> list[TradeOutcome]:
        if self.order_status_fn is None:
            return []
        outcomes: list[TradeOutcome] = []
        for open_decision in self.ledger.open_decisions():
            if not open_decision.get("order_active"):
                continue
            order_id = open_decision.get("order_id") or ""
            if not order_id or order_id.startswith("shadow-"):
                continue
            try:
                status_payload = self.order_status_fn(order_id)
            except Exception:
                continue
            if not isinstance(status_payload, dict):
                continue
            wrapped = status_payload.get("order")
            status = wrapped if isinstance(wrapped, dict) else status_payload
            state = str(status.get("status", "")).lower()
            raw_filled = status.get("fill_count_fp")
            if raw_filled is None or raw_filled == "":
                raw_filled = status.get("fill_count")
            if raw_filled is None or raw_filled == "":
                raw_filled = status.get("filled_count", 0)
            filled_decimal = _decimal_or_none(raw_filled)
            # Dummy's position, ledger, and capital units are currently whole
            # contracts. Never truncate a broker fixed-point fill: 0.50 is
            # real exposure, not zero. Until every downstream unit supports
            # fixed point, retain the open order/capital reservation and emit
            # no terminal fact for any fractional, negative, or malformed
            # count.
            if (
                filled_decimal is None
                or filled_decimal < 0
                or filled_decimal != filled_decimal.to_integral_value()
            ):
                continue
            filled = int(filled_decimal)
            prior_filled = int(open_decision.get("filled_count") or 0)
            created = str(status.get("created_time", ""))
            fill_price, fill_detail = self._broker_fill_evidence(
                open_decision, status, filled
            )
            if state in ("executed", "filled") or filled >= int(open_decision["count"]):
                outcomes.append(self._outcome(
                    open_decision, OutcomeKind.FILLED, order_id, filled,
                    {"state": state or "filled", **fill_detail}, fill_price,
                ))
            elif state in ("canceled", "cancelled"):
                outcomes.append(self._outcome(
                    open_decision, OutcomeKind.CANCELED, order_id, filled,
                    {"state": state, **fill_detail}, fill_price,
                ))
            elif state == "expired":
                outcomes.append(self._outcome(
                    open_decision, OutcomeKind.EXPIRED, order_id, filled,
                    {"state": state, **fill_detail}, fill_price,
                ))
            elif state == "rejected":
                outcomes.append(self._outcome(
                    open_decision, OutcomeKind.REJECTED, order_id, filled,
                    {"state": state, **fill_detail}, fill_price,
                ))
            elif filled > prior_filled:
                outcomes.append(self._outcome(
                    open_decision, OutcomeKind.PARTIALLY_FILLED, order_id, filled,
                    {
                        "state": state or "resting",
                        "new_cumulative_fill_count": filled,
                        **fill_detail,
                    },
                    fill_price,
                ))
            elif state == "resting" and self._is_stale(created) and self.cancel_fn is not None:
                try:
                    cancel_payload = self.cancel_fn(order_id)
                    wrapped_cancel = (
                        cancel_payload.get("order")
                        if isinstance(cancel_payload, dict)
                        else None
                    )
                    cancel_status = (
                        wrapped_cancel
                        if isinstance(wrapped_cancel, dict)
                        else cancel_payload
                    )
                    confirmed_state = (
                        str(cancel_status.get("status") or "").lower()
                        if isinstance(cancel_status, dict)
                        else ""
                    )
                    # A cancel request/204 is not a terminal order witness.
                    # Retain the order until this response or a later status
                    # read explicitly reports canceled/cancelled.
                    if confirmed_state not in {"canceled", "cancelled"}:
                        continue
                    role = str(open_decision.get("liquidity_role") or "maker")
                    reason = (
                        "stale_taker_remainder_auto_cancel"
                        if role == "taker" else "stale_maker_quote_auto_cancel"
                    )
                    outcomes.append(self._outcome(
                        open_decision, OutcomeKind.CANCELED, order_id, filled,
                        {
                            "state": confirmed_state,
                            "reason": reason,
                            **fill_detail,
                        },
                        fill_price,
                    ))
                except Exception:
                    pass
        for outcome in outcomes:
            self.ledger.record_outcome(outcome)
        return outcomes

    def reconcile_shadow_orders(
        self,
        markets: list[MarketView],
        *,
        now: datetime | None = None,
    ) -> list[TradeOutcome]:
        """Conservatively witness shadow maker and taker fills.

        Maker fills require a later cross/print/queue witness. Taker fills
        require a later executable ask witness. Both book the submitted limit
        rather than optimistic price improvement, and both expire without P&L
        when no witness arrives.
        """
        from autonomy.executor import MAX_QUEUE_AHEAD_CONTRACTS, order_ttl_seconds

        now = now or datetime.now(timezone.utc)
        by_ticker = {market.ticker: market for market in markets}
        outcomes: list[TradeOutcome] = []
        for pending in self.ledger.open_decisions("shadow"):
            if not pending.get("order_active") or int(pending.get("filled_count") or 0) > 0:
                continue
            try:
                created = datetime.fromisoformat(str(pending["created_at"]).replace("Z", "+00:00"))
            except Exception:
                created = now
            age_seconds = (now - created).total_seconds()
            ttl_seconds = order_ttl_seconds(str(pending["market_ticker"]))
            expires = created.timestamp() + ttl_seconds
            submission = pending.get("submission_detail") or {}
            liquidity_role = str(pending.get("liquidity_role") or "maker").lower()
            taker_depth_evidence: dict[str, Any] | None = None
            if liquidity_role == "taker":
                reprice = submission.get("execution_reprice")
                if not isinstance(reprice, dict):
                    reprice = {}
                candidate = submission.get("executable_liquidity") or reprice.get(
                    "executable_liquidity"
                )
                evidence_error: str | None = None
                if not isinstance(candidate, dict):
                    evidence_error = "missing_executable_depth_evidence"
                else:
                    from autonomy.executable_liquidity import LIQUIDITY_EVIDENCE_VERSION

                    if candidate.get("liquidity_evidence_version") != LIQUIDITY_EVIDENCE_VERSION:
                        evidence_error = "invalid_executable_depth_version"
                    elif candidate.get("fill_status") != "unfilled_plan_only":
                        evidence_error = "invalid_executable_depth_fill_status"
                    elif not candidate.get("quote_received_at"):
                        evidence_error = "missing_executable_depth_receipt"
                    else:
                        try:
                            evidence_count = int(candidate.get("executable_count"))
                            evidence_limit = int(candidate.get("submitted_limit_price_cents"))
                        except (TypeError, ValueError):
                            evidence_error = "invalid_executable_depth_values"
                        else:
                            if evidence_count != int(pending["count"]):
                                evidence_error = "executable_depth_count_mismatch"
                            elif evidence_limit != int(pending["price_cents"]):
                                evidence_error = "executable_depth_limit_mismatch"
                if evidence_error is not None:
                    if age_seconds >= ttl_seconds:
                        outcomes.append(TradeOutcome(
                            decision_id=str(pending["decision_id"]),
                            market_ticker=str(pending["market_ticker"]),
                            kind=OutcomeKind.EXPIRED,
                            order_id=str(pending.get("order_id") or ""),
                            fill_count=0,
                            fill_price_cents=None,
                            pnl_cents=None,
                            broker_contacted=False,
                            detail={
                                "reason": f"shadow_taker_{evidence_error}",
                                "liquidity_role": "taker",
                            },
                        ))
                    continue
                taker_depth_evidence = candidate
            if (
                liquidity_role == "maker"
                and submission.get("queue_snapshot_available")
                and float(submission.get("queue_ahead_contracts") or 0)
                    > MAX_QUEUE_AHEAD_CONTRACTS
            ):
                outcomes.append(TradeOutcome(
                    decision_id=str(pending["decision_id"]),
                    market_ticker=str(pending["market_ticker"]),
                    kind=OutcomeKind.EXPIRED,
                    order_id=str(pending.get("order_id") or ""),
                    fill_count=0,
                    fill_price_cents=None,
                    pnl_cents=None,
                    broker_contacted=False,
                    detail={
                        "reason": "shadow_queue_policy_invalidated",
                        "queue_ahead_contracts": submission["queue_ahead_contracts"],
                        "maximum_queue_ahead_contracts": MAX_QUEUE_AHEAD_CONTRACTS,
                    },
                ))
                continue
            detail: dict[str, Any] | None = None
            if now.timestamp() < expires:
                market = by_ticker.get(str(pending["market_ticker"]))
                ask = None
                if market is not None:
                    ask = market.yes_ask if pending["side"] == "yes" else market.no_ask
                if liquidity_role == "maker":
                    detail = self._shadow_trade_fill(
                        pending, int(created.timestamp()), int(min(now.timestamp(), expires)),
                    )
                if detail is None and ask is not None and int(ask) <= int(pending["price_cents"]):
                    detail = {
                        "reason": (
                            "shadow_taker_observed_executable_ask"
                            if liquidity_role == "taker"
                            else "shadow_maker_observed_cross"
                        ),
                        "observed_ask_cents": int(ask),
                        "fill_witness_at": now.isoformat(),
                        "conservative_fill_price_cents": int(pending["price_cents"]),
                    }
                    if liquidity_role == "taker":
                        # Depth truth at the witness, not just at submit: the
                        # displayed ask size when the executable ask appears
                        # caps how many contracts this witness can honestly
                        # simulate. Absent sizes keep the submit-time evidence
                        # cap but are disclosed as unverified-at-witness.
                        depth = self._taker_witness_depth(
                            market, str(pending["side"]), int(pending["count"]),
                        )
                        if depth.get("witness_depth_insufficient"):
                            detail = None
                        else:
                            detail.update(depth)
            if detail is None:
                detail = self._shadow_candle_cross(
                    pending, int(created.timestamp()), int(min(now.timestamp(), expires))
                )
                if detail is not None and liquidity_role == "taker":
                    detail["reason"] = "shadow_taker_intracycle_executable_ask"
            if detail is not None:
                kind = OutcomeKind.FILLED
                detail["liquidity_role"] = liquidity_role
                detail["fill_price_source"] = "submitted_limit_conservative"
                if taker_depth_evidence is not None:
                    detail["executable_liquidity"] = taker_depth_evidence
                    detail["simulated_fill_authority"] = "depth_haircut_plus_later_ask"
            elif age_seconds >= ttl_seconds:
                kind = OutcomeKind.EXPIRED
                detail = {
                    "reason": f"shadow_{liquidity_role}_ttl_expired_unfilled",
                    "liquidity_role": liquidity_role,
                }
            else:
                continue
            fill_count = int(pending["count"]) if kind is OutcomeKind.FILLED else 0
            if kind is OutcomeKind.FILLED:
                witnessed = detail.get("witnessed_fill_count")
                if isinstance(witnessed, int) and 0 < witnessed < fill_count:
                    # Shadow partial-fill truth: only the witnessed size fills;
                    # the remainder is conservatively canceled (never carried as
                    # a live-style resting remainder) so evidence undercounts
                    # rather than overcounts. FILLED stays the terminal kind --
                    # PARTIALLY_FILLED is the live remainder-rests state and
                    # would leave a shadow order active forever.
                    fill_count = witnessed
                    detail["partial_fill_truth"] = True
                    detail["remainder_canceled_conservative"] = (
                        int(pending["count"]) - witnessed
                    )
            outcomes.append(TradeOutcome(
                decision_id=str(pending["decision_id"]),
                market_ticker=str(pending["market_ticker"]),
                kind=kind,
                order_id=str(pending.get("order_id") or ""),
                fill_count=fill_count,
                fill_price_cents=int(pending["price_cents"]) if kind is OutcomeKind.FILLED else None,
                pnl_cents=None,
                broker_contacted=False,
                detail=detail,
            ))
        for outcome in outcomes:
            self.ledger.record_outcome(outcome)
        return outcomes

    def _shadow_trade_fill(
        self, pending: dict[str, Any], start_ts: int, end_ts: int,
    ) -> dict[str, Any] | None:
        """Witness maker execution from public prints and captured queue depth.

        A print strictly through the limit proves the full resting order was
        consumed first. At the exact limit, cumulative matching taker volume
        must clear the queue captured immediately before submission plus the
        simulated order size. Block trades are excluded by the fetcher and
        again here defensively.
        """
        if self.fetch_shadow_trades is None or end_ts <= start_ts:
            return None
        try:
            trades = self.fetch_shadow_trades(
                str(pending["market_ticker"]), start_ts, end_ts,
            )
        except Exception:
            return None
        side = str(pending["side"])
        expected_taker_book_side = "ask" if side == "yes" else "bid"
        limit = int(pending["price_cents"])
        exact_volume = 0.0
        matching_ids: list[str] = []
        last_matching_at: str | None = None
        for trade in sorted(trades, key=lambda item: str(item.get("created_time") or "")):
            if trade.get("is_block_trade") is True:
                continue
            if str(trade.get("taker_book_side") or "").lower() != expected_taker_book_side:
                continue
            try:
                price = int(round(float(
                    trade.get("yes_price_dollars") if side == "yes"
                    else trade.get("no_price_dollars")
                ) * 100))
                count = float(trade.get("count_fp") or 0)
                created = datetime.fromisoformat(
                    str(trade.get("created_time") or "").replace("Z", "+00:00")
                )
            except (TypeError, ValueError):
                continue
            if not (start_ts <= created.timestamp() <= end_ts) or count <= 0:
                continue
            trade_id = str(trade.get("trade_id") or "")
            if price < limit:
                return {
                    "reason": "shadow_maker_public_trade_through",
                    "trade_id": trade_id,
                    "trade_price_cents": price,
                    "trade_count": count,
                    "trade_created_time": created.isoformat(),
                    "fill_witness_at": created.isoformat(),
                    "conservative_fill_price_cents": limit,
                }
            if price == limit:
                exact_volume += count
                if trade_id:
                    matching_ids.append(trade_id)
                last_matching_at = created.isoformat()
        submission = pending.get("submission_detail") or {}
        if not submission.get("queue_snapshot_available"):
            return None
        queue_ahead = max(0.0, float(submission.get("queue_ahead_contracts") or 0))
        required = queue_ahead + int(pending["count"])
        if exact_volume + 1e-9 >= required:
            return {
                "reason": "shadow_maker_public_trade_queue_consumed",
                "queue_ahead_contracts": queue_ahead,
                "order_contracts": int(pending["count"]),
                "matching_trade_volume": round(exact_volume, 4),
                "matching_trade_ids": matching_ids[:20],
                "fill_witness_at": last_matching_at,
                "conservative_fill_price_cents": limit,
            }
        # Partial-fill truth: taker volume cleared the queue ahead of us and
        # then consumed part of the simulated order. Credit exactly the
        # witnessed remainder -- never the full size an uncleared queue could
        # not have delivered.
        witnessed = int(exact_volume + 1e-9 - queue_ahead)
        if witnessed <= 0:
            return None
        return {
            "reason": "shadow_maker_public_trade_queue_partially_consumed",
            "queue_ahead_contracts": queue_ahead,
            "order_contracts": int(pending["count"]),
            "matching_trade_volume": round(exact_volume, 4),
            "matching_trade_ids": matching_ids[:20],
            "fill_witness_at": last_matching_at,
            "conservative_fill_price_cents": limit,
            "witnessed_fill_count": witnessed,
        }

    @staticmethod
    def _taker_witness_depth(
        market: Any, side: str, requested: int,
    ) -> dict[str, Any]:
        """Cap a taker witness by the displayed ask size at witness time.

        Uses the same canonical quote-size parser and safety haircut as the
        submit-time evidence plan. Missing sizes fall back to the submit-time
        cap but are disclosed as unverified; a displayed size too small to
        cover even one haircut contract yields no fill this pass.
        """
        from autonomy.executable_liquidity import DISPLAYED_DEPTH_SAFETY_FRACTION
        from autonomy.tier_policy import normalized_quote_sizes

        sizes = normalized_quote_sizes(market) if market is not None else {}
        ask_size = sizes.get(f"{side}_ask_size_fp")
        if not isinstance(ask_size, (int, float)) or ask_size <= 0:
            return {"witness_depth_unverified": True}
        fillable = int(min(
            float(requested), ask_size * DISPLAYED_DEPTH_SAFETY_FRACTION,
        ))
        if fillable <= 0:
            return {"witness_depth_insufficient": True}
        return {
            "witness_ask_size_fp": round(float(ask_size), 4),
            "witness_depth_safety_fraction": DISPLAYED_DEPTH_SAFETY_FRACTION,
            "witnessed_fill_count": fillable,
        }

    def _shadow_candle_cross(
        self,
        pending: dict[str, Any],
        start_ts: int,
        end_ts: int,
    ) -> dict[str, Any] | None:
        """Find an intracycle 1-minute quote cross before order expiration."""
        if self.fetch_shadow_candles is None or end_ts <= start_ts:
            return None
        ticker = str(pending["market_ticker"])
        series = ticker.split("-", 1)[0]
        try:
            candles = self.fetch_shadow_candles(series, ticker, start_ts, end_ts, 1)
        except Exception:
            return None
        limit_dollars = int(pending["price_cents"]) / 100.0
        for candle in sorted(candles, key=lambda item: int(item.get("end_period_ts", 0))):
            try:
                candle_end = int(candle.get("end_period_ts", 0))
            except (TypeError, ValueError):
                continue
            if not (start_ts <= candle_end <= end_ts):
                continue
            if pending["side"] == "yes":
                quote = candle.get("yes_ask") or {}
                raw = quote.get("low_dollars", quote.get("low"))
                crossed = raw is not None and float(raw) <= limit_dollars
                observed = float(raw) if raw is not None else None
            else:
                # NO ask = 1 - YES bid. A high YES bid trades through our NO bid.
                quote = candle.get("yes_bid") or {}
                raw = quote.get("high_dollars", quote.get("high"))
                observed = (1.0 - float(raw)) if raw is not None else None
                crossed = observed is not None and observed <= limit_dollars
            if crossed:
                return {
                    "reason": "shadow_maker_intracycle_candle_cross",
                    "candle_end_ts": candle_end,
                    "fill_witness_at": datetime.fromtimestamp(
                        candle_end, timezone.utc,
                    ).isoformat(),
                    "observed_ask_dollars": round(float(observed), 4),
                    "conservative_fill_price_cents": int(pending["price_cents"]),
                }
        return None

    def _is_stale(self, created_iso: str) -> bool:
        try:
            created = datetime.fromisoformat(created_iso.replace("Z", "+00:00"))
            age_min = (datetime.now(timezone.utc) - created).total_seconds() / 60.0
            return age_min > STALE_ORDER_MINUTES
        except Exception:
            return False

    def _broker_fill_evidence(
        self,
        open_decision: dict[str, Any],
        status: dict[str, Any],
        fill_count: int,
    ) -> tuple[int | None, dict[str, Any]]:
        """Derive weighted price, actual fees, and role from one broker status."""
        if fill_count <= 0:
            return None, {}

        taker_cost = _dollar_amount(
            status, "taker_fill_cost_dollars", "taker_fill_cost"
        )
        maker_cost = _dollar_amount(
            status, "maker_fill_cost_dollars", "maker_fill_cost"
        )
        taker_fee = _dollar_amount(status, "taker_fees_dollars", "taker_fees")
        maker_fee = _dollar_amount(status, "maker_fees_dollars", "maker_fees")
        total_cost = sum(
            (value for value in (taker_cost, maker_cost) if value is not None),
            Decimal(0),
        ) if taker_cost is not None or maker_cost is not None else None
        total_fee = sum(
            (value for value in (taker_fee, maker_fee) if value is not None),
            Decimal(0),
        ) if taker_fee is not None or maker_fee is not None else None

        average_dollars = None
        for key in ("average_fill_price", "average_fill_price_dollars", "avg_price_dollars"):
            average_dollars = _decimal_or_none(status.get(key))
            if average_dollars is not None:
                break
        fill_price_source = "broker_average_fill_price"
        if average_dollars is None and total_cost is not None and total_cost > 0:
            average_dollars = total_cost / Decimal(fill_count)
            fill_price_source = "broker_fill_cost"
        if average_dollars is not None:
            fill_price = int(
                (average_dollars * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )
        else:
            raw_cents = _decimal_or_none(
                status.get("avg_price_cents", status.get("avg_price"))
            )
            if raw_cents is not None:
                fill_price = int(raw_cents.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                fill_price_source = "broker_average_fill_price_cents"
            else:
                fill_price = int(open_decision["price_cents"])
                fill_price_source = "submitted_limit_fallback"

        taker_witnessed = taker_cost is not None and taker_cost > 0
        maker_witnessed = maker_cost is not None and maker_cost > 0
        if taker_witnessed and maker_witnessed:
            liquidity_role = "mixed"
            role_evidence = "broker_maker_and_taker_fill_cost"
        elif taker_witnessed:
            liquidity_role = "taker"
            role_evidence = "broker_taker_fill_cost"
        elif maker_witnessed:
            liquidity_role = "maker"
            role_evidence = "broker_maker_fill_cost"
        else:
            liquidity_role = str(open_decision.get("liquidity_role") or "maker").lower()
            if liquidity_role not in {"maker", "taker", "mixed"}:
                liquidity_role = "maker"
            role_evidence = "submitted_role_fallback"

        detail: dict[str, Any] = {
            "liquidity_role": liquidity_role,
            "liquidity_role_evidence": role_evidence,
            "fill_price_source": fill_price_source,
            "witnessed_fill_price_cents": fill_price,
        }
        fill_cost_cents = _whole_cents(total_cost)
        execution_fee_cents = _whole_cents(total_fee)
        if fill_cost_cents is not None:
            detail["fill_cost_cents"] = fill_cost_cents
            detail["fill_cost_dollars"] = str(total_cost)
        if execution_fee_cents is not None:
            detail["execution_fee_cents"] = execution_fee_cents
            detail["execution_fee_dollars"] = str(total_fee)
        return fill_price, detail

    def _outcome(self, open_decision: dict[str, Any], kind: OutcomeKind, order_id: str,
                 fill_count: int, detail: dict[str, Any] | None = None,
                 fill_price_cents: int | None = None) -> TradeOutcome:
        resolved_detail = dict(detail or {})
        if fill_count > 0:
            resolved_detail.setdefault(
                "liquidity_role", str(open_decision.get("liquidity_role") or "maker")
            )
        resolved_price = (
            int(fill_price_cents)
            if fill_count > 0 and fill_price_cents is not None
            else int(open_decision["price_cents"])
        )
        return TradeOutcome(
            decision_id=str(open_decision["decision_id"]),
            market_ticker=str(open_decision["market_ticker"]),
            kind=kind,
            order_id=order_id,
            fill_count=fill_count,
            fill_price_cents=resolved_price,
            pnl_cents=None,
            broker_contacted=True,
            detail=resolved_detail,
        )


def settlement_pnl_cents(
    side: str,
    price_cents: int,
    count: int,
    result_yes: bool,
    market_ticker: str | None = None,
    liquidity_role: str = "taker",
    fee_cents: int | None = None,
    fill_cost_cents: int | None = None,
) -> int:
    """Realized P&L for confirmed fills, net of witnessed/applicable fees.

    Broker-reported aggregate cost and fee take precedence when available.
    Shadow and legacy fills fall back to their canonical maker/taker role; a
    mixed or unknown role without witnessed fees is charged as taker so the
    ledger cannot overstate performance.
    """
    won = (side == "yes" and result_yes) or (side == "no" and not result_yes)
    if fill_cost_cents is not None:
        cost = max(0, int(fill_cost_cents))
        gross = 100 * count - cost if won else -cost
    else:
        gross = (100 - price_cents) * count if won else -price_cents * count
    if fee_cents is not None:
        fee = max(0, int(fee_cents))
    elif liquidity_role == "maker":
        fee = kalshi_maker_fee_cents(price_cents, count, market_ticker)
    else:
        fee = kalshi_taker_fee_cents(price_cents, count, market_ticker)
    return gross - fee
