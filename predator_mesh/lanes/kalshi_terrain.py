"""Kalshi READ_ONLY terrain lane."""

from __future__ import annotations

from statistics import mean, median
from typing import Any

from predator_mesh.data_inflow.adapters import KalshiReadOnlyAdapter
from predator_mesh.edge.models import MarketTerrainSnapshot
from predator_mesh.lanes.base import BaseLane
from predator_mesh.models import (
    LanePriority,
    LaneState,
    MeshContext,
    MeshPriority,
    MeshResult,
    MeshTimeout,
)


class KalshiTerrainLane(BaseLane):
    """Bounded READ_ONLY terrain snapshot from Kalshi.

    Uses the existing ``KalshiReadOnlyAdapter`` by default. When no live
    read-only client is injected, the lane explicitly abstains. The lane
    always respects the mesh Kalshi call budget and never writes to the broker.
    """

    name = "kalshi_terrain"
    priority = MeshPriority(level=LanePriority.REALTIME_MARKET_TERRAIN)
    timeout = MeshTimeout(per_lane_timeout_s=8.0)

    def __init__(self, adapter: KalshiReadOnlyAdapter | None = None) -> None:
        self.adapter = adapter or KalshiReadOnlyAdapter()

    async def execute(self, ctx: MeshContext) -> MeshResult:
        if not ctx.budget.can_call_kalshi():
            return self._fail(ctx, "kalshi budget exhausted", state=LaneState.BLOCKED)

        ctx.budget.spend_kalshi()

        try:
            candidates = await self.adapter.fetch()
        except Exception as exc:
            return self._fail(ctx, f"kalshi terrain fetch failed: {exc}")

        markets = [
            market
            for candidate in candidates
            for market in candidate.sample_payload.get("markets", [])
            if isinstance(market, dict)
        ]
        if not markets:
            snapshot = {
                "status": "abstained",
                "reason": "no_real_market_data",
                "source": "kalshi_read_only",
                "adapter": self.adapter.name,
                "candidate_names": [c.name for c in candidates],
                "market_count": 0,
            }
            if ctx.proof_ledger is not None:
                ctx.proof_ledger.record(
                    event="terrain_abstained",
                    lane=self.name,
                    adapter=self.adapter.name,
                    reason="no_real_market_data",
                )
                ctx.proof_ledger.record(
                    event="secret_check_status",
                    lane=self.name,
                    status="not_performed",
                )
            ctx.shared_state["kalshi_terrain"] = snapshot
            return self._complete(ctx, snapshot, verdict="insufficient_real_market_data")

        def number(market: dict[str, Any], *keys: str) -> float | None:
            for key in keys:
                value = market.get(key)
                if value is None:
                    continue
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
            return None

        changes: list[float] = []
        spreads: list[float] = []
        liquidities: list[float] = []
        for market in markets:
            current = number(market, "last_price", "yes_price", "last_price_dollars")
            previous = number(market, "previous_price", "previous_yes_price", "previous_price_dollars")
            if current is not None and previous is not None:
                changes.append(current - previous)
            bid = number(market, "yes_bid", "bid", "yes_bid_dollars")
            ask = number(market, "yes_ask", "ask", "yes_ask_dollars")
            if bid is not None and ask is not None and ask >= bid:
                spreads.append(ask - bid)
            liquidity = number(market, "liquidity", "volume", "open_interest")
            if liquidity is not None:
                liquidities.append(liquidity)

        max_move = max((abs(change) for change in changes), default=0.0)
        if max_move >= 20:
            volatility = "extreme"
        elif max_move >= 10:
            volatility = "elevated"
        elif changes:
            volatility = "low"
        else:
            volatility = "unknown"

        median_liquidity = median(liquidities) if liquidities else None
        median_spread = median(spreads) if spreads else None
        if median_liquidity is None and median_spread is None:
            liquidity_state = "unknown"
        elif (median_liquidity is not None and median_liquidity < 100) or (
            median_spread is not None and median_spread > 10
        ):
            liquidity_state = "thin"
        elif (median_liquidity is not None and median_liquidity >= 10_000) and (
            median_spread is None or median_spread <= 2
        ):
            liquidity_state = "deep"
        else:
            liquidity_state = "normal"

        average_change = mean(changes) if changes else 0.0
        trend = "up" if average_change > 0 else "down" if average_change < 0 else "sideways"
        event_risks = [str(m.get("event_risk", "")).lower() for m in markets]
        event_risk = next(
            (risk for risk in ("high", "medium", "low", "none") if risk in event_risks),
            "unknown",
        )
        terrain = MarketTerrainSnapshot(
            volatility_regime=volatility,
            liquidity_state=liquidity_state,
            trend_direction=trend,
            event_risk=event_risk,
        )
        snapshot: dict[str, Any] = {
            "source": "kalshi_read_only",
            "adapter": self.adapter.name,
            "candidate_names": [c.name for c in candidates],
            "market_count": len(markets),
            "terrain": terrain.model_dump(),
        }
        if ctx.proof_ledger is not None:
            ctx.proof_ledger.record(
                event="terrain_snapshot",
                lane=self.name,
                adapter=self.adapter.name,
                candidate_count=len(candidates),
            )
            ctx.proof_ledger.record(
                event="secret_check_status",
                lane=self.name,
                status="not_performed",
            )
        ctx.shared_state["kalshi_terrain"] = snapshot
        return self._complete(ctx, snapshot, verdict="terrain_snapshot")
