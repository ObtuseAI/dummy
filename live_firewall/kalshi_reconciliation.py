"""Read-only, signed Kalshi reconciliation witnesses for DumbMoney.

The reader intentionally queries both current and historical portfolio tiers.
Kalshi partitions completed orders and fills at moving cutoffs, so consulting
only the live portfolio endpoints cannot prove absence or completeness after a
restart.  Every collection is fully paginated, normalized, and read twice
before the local venue identity signs the resulting witness.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from decimal import Decimal, ROUND_CEILING
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from live_firewall.dumbmoney_broker_witness import (
    SETTLEMENT_WITNESS_SCHEMA,
    TERMINAL_WITNESS_SCHEMA,
    sign_broker_witness,
)
from live_firewall.kalshi_broker_truth import (
    KalshiBrokerTruthError,
    KalshiBrokerTruthProvider,
    _cursor,
    _dollars_to_conservative_cents,
    _fixed_point,
    _format_utc,
    _identifier,
    _integer,
    _list,
    _mapping,
    _parse_utc_text,
    _whole_count,
)
from live_firewall.operational_journal import canonical_json, sha256_json


class KalshiReconciliationReader:
    """Produce signed terminal and settlement facts without mutation methods."""

    def __init__(
        self,
        *,
        broker_truth: KalshiBrokerTruthProvider,
        witness_signing_private_key: Ed25519PrivateKey,
    ) -> None:
        self._broker_truth = broker_truth
        self._witness_signing_private_key = witness_signing_private_key

    def _paginated_rows(
        self,
        endpoint_path: str,
        *,
        collection: str,
        base_params: Mapping[str, Any],
    ) -> list[Mapping[str, Any]]:
        rows: list[Mapping[str, Any]] = []
        seen_cursors: set[str] = set()
        cursor = ""
        for _page in range(self._broker_truth._maximum_pages):
            params = {"limit": 1_000, **dict(base_params)}
            if cursor:
                params["cursor"] = cursor
            payload = self._broker_truth._request(
                endpoint_path,
                params=params,
            )
            page = _list(payload.get(collection), field=collection)
            for index, raw in enumerate(page):
                rows.append(
                    _mapping(raw, field=f"{collection}[{index}]")
                )
            if len(rows) > self._broker_truth._maximum_records:
                raise KalshiBrokerTruthError(
                    f"{collection} snapshot exceeds the record limit"
                )
            next_cursor = _cursor(
                payload.get("cursor"),
                field=f"{collection} cursor",
            )
            if not next_cursor:
                return rows
            if next_cursor == cursor or next_cursor in seen_cursors:
                raise KalshiBrokerTruthError(
                    f"{collection} cursor repeated"
                )
            seen_cursors.add(next_cursor)
            cursor = next_cursor
        raise KalshiBrokerTruthError(
            f"{collection} pagination is incomplete"
        )

    def _normalized_order(
        self,
        raw: Mapping[str, Any],
        *,
        source_tier: str,
    ) -> dict[str, Any]:
        order_id = _identifier(raw.get("order_id"), field="order_id")
        client_order_id = _identifier(
            raw.get("client_order_id"),
            field=f"{order_id}.client_order_id",
        )
        ticker = _identifier(
            raw.get("ticker"),
            field=f"{order_id}.ticker",
            ticker=True,
        )
        status = raw.get("status")
        if status not in {"resting", "canceled", "executed"}:
            raise KalshiBrokerTruthError("order status is unsupported")
        if raw.get("action") != "buy":
            raise KalshiBrokerTruthError(
                "DumbMoney reconciliation observed a non-buy order"
            )
        outcome_side = raw.get("outcome_side")
        book_side = raw.get("book_side")
        if outcome_side not in {"yes", "no"}:
            raise KalshiBrokerTruthError("order outcome_side is invalid")
        if book_side != ("bid" if outcome_side == "yes" else "ask"):
            raise KalshiBrokerTruthError(
                "order direction fields are inconsistent"
            )
        subaccount = _integer(
            raw.get("subaccount_number"),
            field=f"{order_id}.subaccount_number",
            maximum=63,
        )
        initial_count = _whole_count(
            raw.get("initial_count_fp"),
            field=f"{order_id}.initial_count_fp",
        )
        fill_count = _whole_count(
            raw.get("fill_count_fp"),
            field=f"{order_id}.fill_count_fp",
        )
        remaining_count = _whole_count(
            raw.get("remaining_count_fp"),
            field=f"{order_id}.remaining_count_fp",
        )
        if (
            initial_count < 1
            or fill_count > initial_count
            or remaining_count > initial_count - fill_count
        ):
            raise KalshiBrokerTruthError("order counts are inconsistent")
        yes_price = _fixed_point(
            raw.get("yes_price_dollars"),
            field=f"{order_id}.yes_price_dollars",
            allow_negative=False,
        )
        no_price = _fixed_point(
            raw.get("no_price_dollars"),
            field=f"{order_id}.no_price_dollars",
            allow_negative=False,
        )
        if (
            yes_price > 1
            or no_price > 1
            or yes_price + no_price != 1
        ):
            raise KalshiBrokerTruthError(
                "order price pair is inconsistent"
            )
        taker_cost = _fixed_point(
            raw.get("taker_fill_cost_dollars"),
            field=f"{order_id}.taker_fill_cost_dollars",
            allow_negative=False,
        )
        maker_cost = _fixed_point(
            raw.get("maker_fill_cost_dollars"),
            field=f"{order_id}.maker_fill_cost_dollars",
            allow_negative=False,
        )
        taker_fees = _fixed_point(
            raw.get("taker_fees_dollars"),
            field=f"{order_id}.taker_fees_dollars",
            allow_negative=False,
        )
        maker_fees = _fixed_point(
            raw.get("maker_fees_dollars"),
            field=f"{order_id}.maker_fees_dollars",
            allow_negative=False,
        )
        created = _parse_utc_text(
            raw.get("created_time"),
            field=f"{order_id}.created_time",
        )
        updated = _parse_utc_text(
            raw.get("last_update_time"),
            field=f"{order_id}.last_update_time",
        )
        if (
            updated < created
            or updated
            > self._broker_truth._now() + timedelta(seconds=5)
        ):
            raise KalshiBrokerTruthError(
                "order timestamps are inconsistent"
            )
        return {
            "order_id": order_id,
            "client_order_id": client_order_id,
            "ticker": ticker,
            "status": status,
            "outcome_side": outcome_side,
            "book_side": book_side,
            "subaccount_number": subaccount,
            "initial_count": initial_count,
            "fill_count": fill_count,
            "remaining_count": remaining_count,
            "yes_price_dollars": str(yes_price),
            "no_price_dollars": str(no_price),
            "fill_cost_dollars": str(taker_cost + maker_cost),
            "fee_dollars": str(taker_fees + maker_fees),
            "created_time": _format_utc(created),
            "last_update_time": _format_utc(updated),
            "source_tier": source_tier,
        }

    @staticmethod
    def _merge_tiered_row(
        rows: dict[str, dict[str, Any]],
        normalized: dict[str, Any],
        *,
        identity_field: str,
        conflict_message: str,
    ) -> None:
        identity = str(normalized[identity_field])
        prior = rows.get(identity)
        if prior is None:
            rows[identity] = normalized
            return
        comparable_prior = {
            key: value
            for key, value in prior.items()
            if key != "source_tier"
        }
        comparable_current = {
            key: value
            for key, value in normalized.items()
            if key != "source_tier"
        }
        if comparable_prior != comparable_current:
            raise KalshiBrokerTruthError(conflict_message)
        prior["source_tier"] = "both"

    def _orders(self, ticker: str) -> list[dict[str, Any]]:
        tiers = (
            (
                "portfolio",
                "portfolio/orders",
                {
                    "ticker": ticker,
                    "subaccount": self._broker_truth._subaccount_number,
                },
            ),
            (
                "historical",
                "historical/orders",
                {"ticker": ticker},
            ),
        )
        by_id: dict[str, dict[str, Any]] = {}
        for source_tier, endpoint, params in tiers:
            for raw in self._paginated_rows(
                endpoint,
                collection="orders",
                base_params=params,
            ):
                normalized = self._normalized_order(
                    raw,
                    source_tier=source_tier,
                )
                if (
                    normalized["subaccount_number"]
                    != self._broker_truth._subaccount_number
                ):
                    if source_tier == "portfolio":
                        raise KalshiBrokerTruthError(
                            "live order belongs to a different subaccount"
                        )
                    continue
                self._merge_tiered_row(
                    by_id,
                    normalized,
                    identity_field="order_id",
                    conflict_message=(
                        "live and historical order rows conflict"
                    ),
                )
        return sorted(by_id.values(), key=lambda item: item["order_id"])

    def _normalized_fill(
        self,
        raw: Mapping[str, Any],
        *,
        source_tier: str,
    ) -> dict[str, Any]:
        fill_id = _identifier(raw.get("fill_id"), field="fill_id")
        order_id = _identifier(
            raw.get("order_id"),
            field=f"{fill_id}.order_id",
        )
        ticker = _identifier(
            raw.get("ticker"),
            field=f"{fill_id}.ticker",
            ticker=True,
        )
        market_ticker = _identifier(
            raw.get("market_ticker"),
            field=f"{fill_id}.market_ticker",
            ticker=True,
        )
        if raw.get("action") != "buy":
            raise KalshiBrokerTruthError(
                "DumbMoney reconciliation observed a non-buy fill"
            )
        outcome_side = raw.get("outcome_side")
        book_side = raw.get("book_side")
        if outcome_side not in {"yes", "no"}:
            raise KalshiBrokerTruthError("fill outcome_side is invalid")
        if book_side != ("bid" if outcome_side == "yes" else "ask"):
            raise KalshiBrokerTruthError(
                "fill direction fields are inconsistent"
            )
        subaccount = _integer(
            raw.get("subaccount_number"),
            field=f"{fill_id}.subaccount_number",
            maximum=63,
        )
        count = _whole_count(
            raw.get("count_fp"),
            field=f"{fill_id}.count_fp",
        )
        if count < 1:
            raise KalshiBrokerTruthError("fill count must be positive")
        yes_price = _fixed_point(
            raw.get("yes_price_dollars"),
            field=f"{fill_id}.yes_price_dollars",
            allow_negative=False,
        )
        no_price = _fixed_point(
            raw.get("no_price_dollars"),
            field=f"{fill_id}.no_price_dollars",
            allow_negative=False,
        )
        if (
            yes_price > 1
            or no_price > 1
            or yes_price + no_price != 1
        ):
            raise KalshiBrokerTruthError("fill price pair is inconsistent")
        fee = _fixed_point(
            raw.get("fee_cost"),
            field=f"{fill_id}.fee_cost",
            allow_negative=False,
        )
        created = _parse_utc_text(
            raw.get("created_time"),
            field=f"{fill_id}.created_time",
        )
        if (
            created
            > self._broker_truth._now() + timedelta(seconds=5)
        ):
            raise KalshiBrokerTruthError(
                "fill timestamp is in the future"
            )
        price = yes_price if outcome_side == "yes" else no_price
        return {
            "fill_id": fill_id,
            "order_id": order_id,
            "ticker": ticker,
            "market_ticker": market_ticker,
            "outcome_side": outcome_side,
            "book_side": book_side,
            "subaccount_number": subaccount,
            "count": count,
            "price_dollars": str(price),
            "cost_dollars": str(price * count),
            "fee_dollars": str(fee),
            "created_time": _format_utc(created),
            "source_tier": source_tier,
        }

    def _fills(
        self,
        *,
        order_id: str,
        ticker: str,
    ) -> list[dict[str, Any]]:
        tiers = (
            (
                "portfolio",
                "portfolio/fills",
                {
                    "order_id": order_id,
                    "subaccount": self._broker_truth._subaccount_number,
                },
            ),
            (
                "historical",
                "historical/fills",
                {"ticker": ticker},
            ),
        )
        by_id: dict[str, dict[str, Any]] = {}
        for source_tier, endpoint, params in tiers:
            for raw in self._paginated_rows(
                endpoint,
                collection="fills",
                base_params=params,
            ):
                normalized = self._normalized_fill(
                    raw,
                    source_tier=source_tier,
                )
                if (
                    normalized["subaccount_number"]
                    != self._broker_truth._subaccount_number
                ):
                    if source_tier == "portfolio":
                        raise KalshiBrokerTruthError(
                            "live fill belongs to a different subaccount"
                        )
                    continue
                if normalized["order_id"] != order_id:
                    if source_tier == "portfolio":
                        raise KalshiBrokerTruthError(
                            "live fill query returned another order"
                        )
                    continue
                self._merge_tiered_row(
                    by_id,
                    normalized,
                    identity_field="fill_id",
                    conflict_message=(
                        "live and historical fill rows conflict"
                    ),
                )
        return sorted(by_id.values(), key=lambda item: item["fill_id"])

    def _terminal_projection(
        self,
        reservation: Mapping[str, Any],
    ) -> dict[str, Any]:
        proposal_id = _identifier(
            reservation.get("proposal_id"),
            field="reservation.proposal_id",
        )
        ticker = _identifier(
            reservation.get("contract_ticker"),
            field="reservation.contract_ticker",
            ticker=True,
        )
        side = reservation.get("side")
        if side not in {"yes", "no"}:
            raise KalshiBrokerTruthError("reservation side is invalid")
        size = _integer(
            reservation.get("size"),
            field="reservation.size",
            minimum=1,
        )
        price_cents = _integer(
            reservation.get("price_cents"),
            field="reservation.price_cents",
            minimum=1,
            maximum=99,
        )
        orders = [
            order
            for order in self._orders(ticker)
            if order["client_order_id"] == proposal_id
        ]
        if len(orders) > 1:
            raise KalshiBrokerTruthError(
                "client_order_id resolves to multiple broker orders"
            )
        if not orders:
            return {
                "state": "NOT_FOUND",
                "proposal_id": proposal_id,
                "ticker": ticker,
            }
        order = orders[0]
        if (
            order["ticker"] != ticker
            or order["outcome_side"] != side
            or order["initial_count"] != size
            or (
                Decimal(
                    str(order[f"{side}_price_dollars"])
                )
                * Decimal(100)
                != Decimal(price_cents)
            )
        ):
            raise KalshiBrokerTruthError(
                "broker order differs from the capital reservation"
            )
        if order["status"] == "resting":
            if order["remaining_count"] <= 0:
                raise KalshiBrokerTruthError(
                    "resting order has no remaining count"
                )
            return {"state": "RESTING", "order": order}
        if order["remaining_count"] != 0:
            raise KalshiBrokerTruthError(
                "terminal order retains a remaining count"
            )
        if (
            order["status"] == "executed"
            and order["fill_count"] != size
        ):
            raise KalshiBrokerTruthError(
                "executed order lacks a complete fill"
            )
        fills = self._fills(
            order_id=order["order_id"],
            ticker=ticker,
        )
        fill_count = sum(int(item["count"]) for item in fills)
        fill_cost = sum(
            (
                Decimal(str(item["cost_dollars"]))
                for item in fills
            ),
            Decimal(0),
        )
        fee_cost = sum(
            (
                Decimal(str(item["fee_dollars"]))
                for item in fills
            ),
            Decimal(0),
        )
        if (
            fill_count != order["fill_count"]
            or fill_cost != Decimal(str(order["fill_cost_dollars"]))
            or fee_cost != Decimal(str(order["fee_dollars"]))
            or any(item["ticker"] != ticker for item in fills)
            or any(item["outcome_side"] != side for item in fills)
        ):
            raise KalshiBrokerTruthError(
                "order and fill projections disagree"
            )
        return {
            "state": "TERMINAL",
            "order": order,
            "fills": fills,
            "fill_count": fill_count,
            "fill_cost_dollars": str(fill_cost),
            "fee_dollars": str(fee_cost),
        }

    def terminal_reconciliation_witness(
        self,
        reservation: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        """Return a signed terminal witness, or retain unresolved authority."""
        first = self._terminal_projection(reservation)
        second = self._terminal_projection(reservation)
        if canonical_json(first) != canonical_json(second):
            raise KalshiBrokerTruthError(
                "order or fill state changed during reconciliation"
            )
        if first["state"] != "TERMINAL":
            return None
        observed = self._broker_truth._now()
        order = first["order"]
        fill_count = int(first["fill_count"])
        fill_cost = Decimal(str(first["fill_cost_dollars"]))
        fee = Decimal(str(first["fee_dollars"]))
        average_price_cents = (
            int(
                (
                    fill_cost
                    * Decimal(100)
                    / Decimal(fill_count)
                ).to_integral_value(rounding=ROUND_CEILING)
            )
            if fill_count
            else None
        )
        projection_digest = sha256_json(
            {
                "schema": "dummy.kalshi-terminal-projection.v1",
                "projection": first,
            }
        )
        invariant = {
            "venue": "dummy_kalshi",
            "account_hash": self._broker_truth._expected_account_hash,
            "subaccount_number": (
                self._broker_truth._subaccount_number
            ),
            "reservation_id": reservation.get("reservation_id"),
            "proposal_id": reservation.get("proposal_id"),
            "order": first["order"],
            "fills": first["fills"],
        }
        body = {
            "schema": TERMINAL_WITNESS_SCHEMA,
            "witness_id": sha256_json(invariant),
            "venue": "dummy_kalshi",
            "account_hash": self._broker_truth._expected_account_hash,
            "subaccount_number": (
                self._broker_truth._subaccount_number
            ),
            "reservation_id": _identifier(
                reservation.get("reservation_id"),
                field="reservation.reservation_id",
            ),
            "proposal_id": order["client_order_id"],
            "order_id": order["order_id"],
            "market_ticker": _identifier(
                reservation.get("market_ticker"),
                field="reservation.market_ticker",
                ticker=True,
            ),
            "contract_ticker": order["ticker"],
            "side": order["outcome_side"],
            "terminal_status": order["status"],
            "initial_count": order["initial_count"],
            "fill_count": fill_count,
            "remaining_count": order["remaining_count"],
            "fill_cost_cents": _dollars_to_conservative_cents(
                fill_cost,
                field="fill_cost_cents",
            ),
            "fee_cents": _dollars_to_conservative_cents(
                fee,
                field="fee_cents",
            ),
            "average_fill_price_cents": average_price_cents,
            "fill_ids": [item["fill_id"] for item in first["fills"]],
            "observed_at": _format_utc(observed),
            "broker_projection_sha256": projection_digest,
        }
        return sign_broker_witness(
            body,
            private_key=self._witness_signing_private_key,
            observed_at=observed,
            correlation_id=order["client_order_id"],
        )

    def _settlements(self, ticker: str) -> list[dict[str, Any]]:
        rows = self._paginated_rows(
            "portfolio/settlements",
            collection="settlements",
            base_params={
                "ticker": ticker,
                "subaccount": self._broker_truth._subaccount_number,
            },
        )
        settlements: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in rows:
            row_ticker = _identifier(
                raw.get("ticker"),
                field="settlement.ticker",
                ticker=True,
            )
            if row_ticker in seen:
                raise KalshiBrokerTruthError(
                    "settlement ticker is duplicated"
                )
            seen.add(row_ticker)
            result = raw.get("market_result")
            if result not in {"yes", "no"}:
                raise KalshiBrokerTruthError(
                    "settlement result is invalid"
                )
            settled = _parse_utc_text(
                raw.get("settled_time"),
                field=f"{row_ticker}.settled_time",
            )
            if (
                settled
                > self._broker_truth._now() + timedelta(seconds=5)
            ):
                raise KalshiBrokerTruthError(
                    "settlement timestamp is in the future"
                )
            yes_count = _fixed_point(
                raw.get("yes_count_fp"),
                field=f"{row_ticker}.yes_count_fp",
                allow_negative=False,
            )
            no_count = _fixed_point(
                raw.get("no_count_fp"),
                field=f"{row_ticker}.no_count_fp",
                allow_negative=False,
            )
            yes_cost = _fixed_point(
                raw.get("yes_total_cost_dollars"),
                field=f"{row_ticker}.yes_total_cost_dollars",
                allow_negative=False,
            )
            no_cost = _fixed_point(
                raw.get("no_total_cost_dollars"),
                field=f"{row_ticker}.no_total_cost_dollars",
                allow_negative=False,
            )
            fee = _fixed_point(
                raw.get("fee_cost"),
                field=f"{row_ticker}.fee_cost",
                allow_negative=False,
            )
            revenue = _integer(
                raw.get("revenue"),
                field=f"{row_ticker}.revenue",
            )
            settlements.append(
                {
                    "ticker": row_ticker,
                    "event_ticker": _identifier(
                        raw.get("event_ticker"),
                        field=f"{row_ticker}.event_ticker",
                        ticker=True,
                    ),
                    "market_result": result,
                    "yes_count_fp": str(yes_count),
                    "no_count_fp": str(no_count),
                    "yes_total_cost_dollars": str(yes_cost),
                    "no_total_cost_dollars": str(no_cost),
                    "fee_cost_dollars": str(fee),
                    "revenue_cents": revenue,
                    "settled_time": _format_utc(settled),
                }
            )
        return sorted(settlements, key=lambda item: item["ticker"])

    def _settlement_projection(
        self,
        position_exposure: Mapping[str, Any],
    ) -> dict[str, Any]:
        ticker = _identifier(
            position_exposure.get("contract_ticker"),
            field="position_exposure.contract_ticker",
            ticker=True,
        )
        positions = self._broker_truth._positions()
        market_positions = [
            item
            for item in positions["market_positions"]
            if item["ticker"] == ticker
        ]
        settlements = [
            item
            for item in self._settlements(ticker)
            if item["ticker"] == ticker
        ]
        if market_positions:
            return {
                "state": "POSITION_OPEN",
                "positions": market_positions,
                "settlements": settlements,
            }
        if len(settlements) > 1:
            raise KalshiBrokerTruthError(
                "multiple settlement rows exist for one market"
            )
        if not settlements:
            return {
                "state": "POSITION_ABSENT_UNSETTLED",
                "positions": [],
                "settlements": [],
            }
        side = position_exposure.get("side")
        if side not in {"yes", "no"}:
            raise KalshiBrokerTruthError(
                "position exposure side is invalid"
            )
        settlement = settlements[0]
        position_observed = _parse_utc_text(
            position_exposure.get("observed_at"),
            field="position_exposure.observed_at",
        )
        settlement_observed = _parse_utc_text(
            settlement["settled_time"],
            field="settlement.settled_time",
        )
        if settlement_observed < position_observed:
            raise KalshiBrokerTruthError(
                "settlement predates the filled position exposure"
            )
        settled_count = Decimal(
            str(settlement[f"{side}_count_fp"])
        )
        fill_count = _integer(
            position_exposure.get("fill_count"),
            field="position_exposure.fill_count",
            minimum=1,
        )
        if settled_count < fill_count:
            raise KalshiBrokerTruthError(
                "settlement count does not cover the filled exposure"
            )
        return {
            "state": "SETTLED_POSITION_ABSENT",
            "positions": [],
            "settlement": settlement,
        }

    def settlement_reconciliation_witness(
        self,
        position_exposure: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        """Return a signed settlement/position-close witness when complete."""
        first = self._settlement_projection(position_exposure)
        second = self._settlement_projection(position_exposure)
        if canonical_json(first) != canonical_json(second):
            raise KalshiBrokerTruthError(
                "position or settlement state changed during reconciliation"
            )
        if first["state"] != "SETTLED_POSITION_ABSENT":
            return None
        observed = self._broker_truth._now()
        settlement = first["settlement"]
        projection_digest = sha256_json(
            {
                "schema": "dummy.kalshi-settlement-projection.v1",
                "projection": first,
            }
        )
        invariant = {
            "venue": "dummy_kalshi",
            "account_hash": self._broker_truth._expected_account_hash,
            "subaccount_number": (
                self._broker_truth._subaccount_number
            ),
            "position_exposure_id": position_exposure.get(
                "position_exposure_id"
            ),
            "settlement": settlement,
            "position_absent": True,
        }
        body = {
            "schema": SETTLEMENT_WITNESS_SCHEMA,
            "witness_id": sha256_json(invariant),
            "venue": "dummy_kalshi",
            "account_hash": self._broker_truth._expected_account_hash,
            "subaccount_number": (
                self._broker_truth._subaccount_number
            ),
            "position_exposure_id": _identifier(
                position_exposure.get("position_exposure_id"),
                field="position_exposure.position_exposure_id",
            ),
            "reservation_id": _identifier(
                position_exposure.get("reservation_id"),
                field="position_exposure.reservation_id",
            ),
            "proposal_id": _identifier(
                position_exposure.get("proposal_id"),
                field="position_exposure.proposal_id",
            ),
            "contract_ticker": settlement["ticker"],
            "side": position_exposure.get("side"),
            "fill_count": _integer(
                position_exposure.get("fill_count"),
                field="position_exposure.fill_count",
                minimum=1,
            ),
            "market_result": settlement["market_result"],
            "settled_at": settlement["settled_time"],
            "revenue_cents": settlement["revenue_cents"],
            "settlement_fee_cents": (
                _dollars_to_conservative_cents(
                    Decimal(str(settlement["fee_cost_dollars"])),
                    field="settlement_fee_cents",
                )
            ),
            "position_absent": True,
            "observed_at": _format_utc(observed),
            "broker_projection_sha256": projection_digest,
        }
        return sign_broker_witness(
            body,
            private_key=self._witness_signing_private_key,
            observed_at=observed,
            correlation_id=body["proposal_id"],
        )


__all__ = ["KalshiReconciliationReader"]
