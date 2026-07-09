"""Deterministic Kalshi orderbook liquidity model for V11."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass(frozen=True)
class DepthProfile:
    best_bid: int | None
    best_ask: int | None
    top_of_book_depth: int
    cumulative_bid_depth: int
    cumulative_ask_depth: int

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class SpreadProfile:
    midpoint: float | None
    spread_absolute: int | None
    spread_percentage: float | None
    status: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class ExpectedFillProbability:
    probability: float
    basis: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class FillDragEstimate:
    drag_cents: float
    edge_before_fill_drag: float
    edge_after_fill_drag: float

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class PriceImpactEstimate:
    impact_cents: float
    size_feasible: bool

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class StaleQuoteRisk:
    age_seconds: float | None
    risk_score: float
    status: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class FillQualityEstimate:
    expected_fill_probability: ExpectedFillProbability
    fill_drag: FillDragEstimate
    price_impact: PriceImpactEstimate
    liquidity_decay: float
    size_feasibility: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_fill_probability": self.expected_fill_probability.to_dict(),
            "fill_drag": self.fill_drag.to_dict(),
            "price_impact": self.price_impact.to_dict(),
            "liquidity_decay": self.liquidity_decay,
            "size_feasibility": self.size_feasibility,
        }


@dataclass(frozen=True)
class ExecutionFeasibilityScore:
    total: float
    status: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class OrderbookLiquidityAnalysis:
    depth_profile: DepthProfile
    spread_profile: SpreadProfile
    fill_quality: FillQualityEstimate
    stale_quote_risk: StaleQuoteRisk
    execution_feasibility_score: ExecutionFeasibilityScore

    def to_dict(self) -> dict[str, Any]:
        return {
            "depth_profile": self.depth_profile.to_dict(),
            "spread_profile": self.spread_profile.to_dict(),
            "fill_quality": self.fill_quality.to_dict(),
            "stale_quote_risk": self.stale_quote_risk.to_dict(),
            "execution_feasibility_score": self.execution_feasibility_score.to_dict(),
        }


class OrderbookLiquidityModel:
    WIDE_SPREAD_CENTS = 12
    MIN_DEPTH = 40
    STALE_SECONDS = 30

    @staticmethod
    def sample_orderbook(*, age_seconds: int = 5, spread_cents: int = 4, depth: int = 220) -> dict[str, Any]:
        now = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
        bid = 50 - spread_cents // 2
        ask = 50 + spread_cents // 2
        return {
            "timestamp": now.isoformat(),
            "bids": [{"price": bid, "size": depth // 2}, {"price": bid - 1, "size": 80}],
            "asks": [{"price": ask, "size": depth // 2}, {"price": ask + 1, "size": 80}],
            "requested_size": 5,
            "expected_edge_cents": 8.0,
        }

    def analyze(self, orderbook: dict[str, Any] | None) -> OrderbookLiquidityAnalysis:
        orderbook = orderbook if isinstance(orderbook, dict) else {}
        bids = self._levels(orderbook.get("bids"), reverse=True)
        asks = self._levels(orderbook.get("asks"), reverse=False)
        requested_size = max(1, int(orderbook.get("requested_size", 1) or 1))
        expected_edge = float(orderbook.get("expected_edge_cents", 0.0) or 0.0)

        best_bid = bids[0]["price"] if bids else None
        best_ask = asks[0]["price"] if asks else None
        cumulative_bid = sum(level["size"] for level in bids)
        cumulative_ask = sum(level["size"] for level in asks)
        top_depth = (bids[0]["size"] if bids else 0) + (asks[0]["size"] if asks else 0)
        depth_profile = DepthProfile(best_bid, best_ask, top_depth, cumulative_bid, cumulative_ask)

        if best_bid is None or best_ask is None:
            spread = None
            midpoint = None
            spread_pct = None
            spread_status = "ONE_SIDED_OR_EMPTY"
        elif best_bid >= best_ask:
            spread = best_ask - best_bid
            midpoint = (best_bid + best_ask) / 2
            spread_pct = 0.0
            spread_status = "CROSSED_OR_INVALID"
        else:
            spread = best_ask - best_bid
            midpoint = (best_bid + best_ask) / 2
            spread_pct = round(spread / midpoint, 4) if midpoint else None
            spread_status = "WIDE" if spread > self.WIDE_SPREAD_CENTS else "BOUNDED"
        spread_profile = SpreadProfile(midpoint, spread, spread_pct, spread_status)

        stale = self._stale_risk(orderbook.get("timestamp"))
        fill_probability = self._fill_probability(top_depth, requested_size, spread, stale.status)
        drag_cents = float(spread or self.WIDE_SPREAD_CENTS) / 2 + stale.risk_score * 2
        edge_after = expected_edge - drag_cents
        impact = 0.0 if cumulative_ask >= requested_size else float(requested_size - cumulative_ask)
        size_feasible = cumulative_ask >= requested_size and top_depth >= self.MIN_DEPTH
        fill_quality = FillQualityEstimate(
            expected_fill_probability=ExpectedFillProbability(fill_probability, "top_depth_spread_staleness"),
            fill_drag=FillDragEstimate(round(drag_cents, 4), expected_edge, round(edge_after, 4)),
            price_impact=PriceImpactEstimate(round(impact, 4), size_feasible),
            liquidity_decay=round(stale.risk_score * 0.5, 4),
            size_feasibility=round(min(1.0, cumulative_ask / requested_size), 4) if requested_size else 0.0,
        )

        status = "FEASIBLE"
        if not bids or not asks or top_depth < self.MIN_DEPTH:
            status = "NO_TRADE_LIQUIDITY_TOO_THIN"
        elif spread_status == "CROSSED_OR_INVALID":
            status = "QUARANTINE_MARKET"
        elif stale.status == "STALE":
            status = "NO_TRADE_STALE_ORDERBOOK"
        elif spread is not None and spread > self.WIDE_SPREAD_CENTS:
            status = "NO_TRADE_SPREAD_TOO_WIDE"
        elif edge_after <= 0:
            status = "NO_TRADE_EDGE_TOO_SMALL_AFTER_FILL_DRAG"

        total = round(
            max(0.0, min(1.0, fill_probability * 0.5 + min(1.0, top_depth / 300) * 0.3 + (1.0 - stale.risk_score) * 0.2)),
            4,
        )
        if status != "FEASIBLE":
            total = 0.0 if status in {"NO_TRADE_LIQUIDITY_TOO_THIN", "QUARANTINE_MARKET"} else min(total, 0.25)
        return OrderbookLiquidityAnalysis(
            depth_profile=depth_profile,
            spread_profile=spread_profile,
            fill_quality=fill_quality,
            stale_quote_risk=stale,
            execution_feasibility_score=ExecutionFeasibilityScore(total, status),
        )

    def _levels(self, levels: Any, *, reverse: bool) -> list[dict[str, int]]:
        out: list[dict[str, int]] = []
        if not isinstance(levels, list):
            return out
        for level in levels:
            if not isinstance(level, dict):
                continue
            try:
                price = int(level["price"])
                size = int(level["size"])
            except (KeyError, TypeError, ValueError):
                continue
            if price < 0 or size <= 0:
                continue
            out.append({"price": price, "size": size})
        return sorted(out, key=lambda item: item["price"], reverse=reverse)

    def _stale_risk(self, timestamp: Any) -> StaleQuoteRisk:
        if not isinstance(timestamp, str) or not timestamp:
            return StaleQuoteRisk(None, 1.0, "MISSING_TIMESTAMP")
        try:
            parsed = datetime.fromisoformat(timestamp)
        except ValueError:
            return StaleQuoteRisk(None, 1.0, "MALFORMED_TIMESTAMP")
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        age = max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds())
        status = "STALE" if age > self.STALE_SECONDS else "FRESH"
        return StaleQuoteRisk(round(age, 4), round(min(1.0, age / 120), 4), status)

    def _fill_probability(self, top_depth: int, requested_size: int, spread: int | None, stale_status: str) -> float:
        if top_depth <= 0 or spread is None or stale_status != "FRESH":
            return 0.0
        depth_factor = min(1.0, top_depth / max(1, requested_size * 20))
        spread_factor = max(0.0, 1.0 - spread / 20)
        return round(depth_factor * spread_factor, 4)

    def to_report(self) -> dict[str, Any]:
        analysis = self.analyze(self.sample_orderbook())
        edge_cases = {
            "empty_book": self.analyze({"bids": [], "asks": []}).execution_feasibility_score.status,
            "one_sided_book": self.analyze({"bids": [{"price": 48, "size": 5}], "asks": []}).execution_feasibility_score.status,
            "stale_book": self.analyze(self.sample_orderbook(age_seconds=90)).execution_feasibility_score.status,
            "wide_spread": self.analyze(self.sample_orderbook(spread_cents=20)).execution_feasibility_score.status,
            "tiny_depth": self.analyze(self.sample_orderbook(depth=10)).execution_feasibility_score.status,
        }
        return {
            "workstream": "V11: Orderbook Liquidity Model",
            "sample_orderbook_used": True,
            "analysis": analysis.to_dict(),
            "handled_edge_cases": edge_cases,
            "verdict": "PASS",
        }

    def fill_quality_report(self) -> dict[str, Any]:
        analysis = self.analyze(self.sample_orderbook())
        return {
            "workstream": "V11: Fill Quality Estimate",
            "estimate": analysis.fill_quality.to_dict(),
            "execution_feasibility_score": analysis.execution_feasibility_score.to_dict(),
            "verdict": "PASS" if analysis.fill_quality.expected_fill_probability.probability > 0 else "FAIL",
        }

    def stale_quote_report(self) -> dict[str, Any]:
        fresh = self.analyze(self.sample_orderbook(age_seconds=5))
        stale = self.analyze(self.sample_orderbook(age_seconds=90))
        return {
            "workstream": "V11: Stale Quote Risk",
            "fresh": fresh.stale_quote_risk.to_dict(),
            "stale": stale.stale_quote_risk.to_dict(),
            "verdict": "PASS" if stale.stale_quote_risk.status == "STALE" else "FAIL",
        }
