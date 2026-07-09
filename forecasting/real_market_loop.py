from __future__ import annotations
import asyncio
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

from core.ontology import Contract, Forecast, ForecastOpinion, Market, OrderBook, OrderBookLevel
from core.logger import logger
from forecasting.hybrid_engine import HybridForecastEngine
from kalshi.live_data import KalshiRealReadOnly, KalshiCredentialsMissing
from kalshi.normalizer import KalshiNormalizer
from calibration.storage import CalibrationStorage
from model_router.credential_readiness import CredentialReadiness

FORECAST_LOOP_V2_TIMEOUT_SECONDS = 60


class RealMarketForecastLoop:
    def __init__(
        self,
        hybrid_engine: HybridForecastEngine | None = None,
        storage: CalibrationStorage | None = None,
    ):
        self.hybrid_engine = hybrid_engine or HybridForecastEngine()
        self.storage = storage or CalibrationStorage()
        self.credentials_present = False

    async def run(self, contract_tickers: list[str] | None = None) -> dict[str, Any]:
        reader: KalshiRealReadOnly | None = None
        try:
            reader = KalshiRealReadOnly()
            self.credentials_present = True
        except KalshiCredentialsMissing:
            return {"source": "mock", "opinions": [], "reason": "kalshi_credentials_missing"}
        normalizer = KalshiNormalizer()
        tickers = contract_tickers or ["KXELONMARS-99"]
        opinions: list[ForecastOpinion] = []
        try:
            for ticker in tickers:
                snapshot = await reader.get_full_snapshot(ticker)
                normalized = normalizer.normalize_full_snapshot(snapshot, ticker)
                market = normalized["markets"][0] if normalized["markets"] else None
                orderbook = normalized["orderbook"]
                opinion = await self.hybrid_engine.forecast_opinion(
                    market_ticker=orderbook.market_ticker,
                    contract_ticker=ticker,
                    event_title=market.title if market else ticker,
                    contract_title=ticker,
                    orderbook=orderbook,
                )
                opinions.append(opinion)
                self.storage.append_forecast(opinion)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403):
                return {"source": "mock", "opinions": [], "reason": "kalshi_credentials_unauthorized"}
            raise
        finally:
            if reader is not None:
                await reader.close()
        return {"source": "live", "opinions": [o.model_dump() for o in opinions], "count": len(opinions)}


class RealMarketForecastLoopV2:
    """Real-market forecast loop using fresh Kalshi snapshots and hybrid model reviews.

    Produces native :class:`core.ontology.ForecastOpinion` objects only.  Never
    submits orders.  Falls back to explicit mock data when Kalshi credentials are
    missing and marks the run ``model_mode: MOCK_ONLY`` when live model credentials
    are absent or disabled by routing config.
    """

    def __init__(
        self,
        hybrid_engine: HybridForecastEngine | None = None,
        storage: CalibrationStorage | None = None,
        artifact_dir: str | Path | None = None,
    ):
        self.hybrid_engine = hybrid_engine or HybridForecastEngine()
        self.storage = storage or CalibrationStorage()
        self.artifact_dir = Path(artifact_dir or "artifacts/dummy")
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.credentials_present = False
        self.model_mode = "UNKNOWN"
        self.readiness = CredentialReadiness()
        self.normalizer = KalshiNormalizer()

    def _determine_model_mode(self) -> str:
        config = self.hybrid_engine.router.config
        live_enabled = getattr(config, "live_model_calls_enabled", False)
        if self.readiness.ready() and live_enabled:
            return "LIVE_HYBRID"
        return "MOCK_ONLY"

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _freshness_score(ts: datetime) -> Decimal:
        age = max(0.0, (RealMarketForecastLoopV2._now() - ts).total_seconds())
        return Decimal(str(round(max(0.0, 1.0 - age / 60.0), 4)))

    def _settlement_risk_score(self, market: Market) -> Decimal:
        text = f"{market.category} {market.title}".lower()
        if "weather" in text:
            return Decimal("0.15")
        if any(k in text for k in ("crypto", "btc", "bitcoin")):
            return Decimal("0.25")
        if any(k in text for k in ("macro", "index", "economic", "spx", "sp500", "nasdaq", "gdp", "inflation")):
            return Decimal("0.20")
        if "politic" in text:
            return Decimal("0.35")
        return Decimal("0.30")

    def _score_market(
        self,
        market: Market,
        contract: Contract,
        orderbook: OrderBook,
    ) -> dict[str, Any]:
        best_bid = (
            orderbook.bids[-1].price
            if orderbook.bids
            else (contract.yes_bid if contract.yes_bid is not None else None)
        )
        best_ask = (
            orderbook.asks[0].price
            if orderbook.asks
            else (contract.yes_ask if contract.yes_ask is not None else None)
        )
        spread = (best_ask - best_bid) if best_bid is not None and best_ask is not None else None
        mid = Decimal((best_bid + best_ask) / 200) if spread is not None else Decimal("0.5")

        total_bid_size = sum(level.size for level in orderbook.bids)
        total_ask_size = sum(level.size for level in orderbook.asks)
        total_size = total_bid_size + total_ask_size

        depth_score = Decimal(str(min(1.0, total_size / 1000.0))).quantize(Decimal("0.0001"))
        spread_score = (
            Decimal(str(max(0.0, 1.0 - (spread or 0) / 10.0))).quantize(Decimal("0.0001"))
            if spread is not None
            else Decimal("0.5")
        )
        liquidity_score = (depth_score * spread_score).quantize(Decimal("0.0001"))
        freshness = orderbook.freshness_score or self._freshness_score(orderbook.timestamp)
        settlement = self._settlement_risk_score(market)

        conf_stat = (liquidity_score * freshness * (Decimal("1") - settlement)).quantize(Decimal("0.0001"))
        dummy_stat = (mid * conf_stat + Decimal("0.5") * (Decimal("1") - conf_stat)).quantize(Decimal("0.0001"))

        return {
            "best_bid_cents": best_bid,
            "best_ask_cents": best_ask,
            "spread_cents": spread,
            "market_implied_probability": mid.quantize(Decimal("0.0001")),
            "dummy_statistical_probability": dummy_stat,
            "depth_score": depth_score,
            "spread_score": spread_score,
            "liquidity_score": liquidity_score,
            "freshness_score": freshness,
            "settlement_risk_score": settlement,
            "total_size": total_size,
            "bid_levels": len(orderbook.bids),
            "ask_levels": len(orderbook.asks),
        }

    def _build_base_forecast(
        self,
        market: Market,
        contract: Contract,
        orderbook: OrderBook,
        scores: dict[str, Any],
    ) -> Forecast:
        now = self._now()
        expires = now + timedelta(hours=1)
        market_implied = scores["market_implied_probability"]
        dummy_stat = scores["dummy_statistical_probability"]
        delta = (dummy_stat - market_implied).quantize(Decimal("0.0001"))
        confidence = (
            scores["liquidity_score"] * scores["freshness_score"] * (Decimal("1") - scores["settlement_risk_score"])
        ).quantize(Decimal("0.0001"))
        return Forecast(
            market_ticker=market.ticker,
            contract_ticker=contract.ticker,
            event_title=market.title,
            contract_title=contract.title,
            market_implied_probability=market_implied,
            dummy_probability=dummy_stat,
            probability_delta=delta,
            confidence_score=confidence,
            uncertainty_band=(
                max(Decimal("0"), dummy_stat - Decimal("0.05")),
                min(Decimal("1"), dummy_stat + Decimal("0.05")),
            ),
            expected_edge=delta,
            edge_after_fees=(delta - Decimal("0.005")).quantize(Decimal("0.0001")),
            freshness_score=scores["freshness_score"],
            liquidity_score=scores["liquidity_score"],
            spread_score=scores["spread_score"],
            orderbook_depth_score=scores["depth_score"],
            settlement_risk_score=scores["settlement_risk_score"],
            source_summary="kalshi_snapshot_v2",
            model_summary="statistical_midpoint",
            calibration_notes="v2 quality-scored baseline",
            timestamp=now,
            expiration=expires,
            strategy_references=["probability_disagreement_v2"],
            proof_reference=f"forecast_v2_{market.ticker}_{contract.ticker}_{now.isoformat()}",
        )

    @staticmethod
    def _safe_json(content: str) -> dict[str, Any]:
        try:
            return json.loads(content)
        except Exception:
            return {}

    def _synthesize_opinion(
        self,
        base: Forecast,
        scores: dict[str, Any],
        reviews: dict[str, Any],
    ) -> ForecastOpinion:
        deep = self._safe_json(reviews["deepseek_forecast"].content)
        no_trade = self._safe_json(reviews["no_trade"].content)
        critique = self._safe_json(reviews["critique"].content)
        risk = self._safe_json(reviews["risk"].content)
        thesis = self._safe_json(reviews["thesis"].content)

        model_prob = Decimal(str(deep.get("dummy_probability", scores["dummy_statistical_probability"])))
        model_prob = max(Decimal("0"), min(Decimal("1"), model_prob))
        model_conf = Decimal(str(deep.get("confidence_score", base.confidence_score)))
        model_conf = max(Decimal("0"), min(Decimal("1"), model_conf))

        adjustment = Decimal("0")
        verdict = str(critique.get("verdict", "")).lower()
        if verdict == "block":
            adjustment -= Decimal("0.30")
        elif verdict == "warn":
            adjustment -= Decimal("0.10")
        elif verdict == "proceed":
            adjustment += Decimal("0.05")

        risk_level = str(risk.get("risk_level", "")).lower()
        if risk_level in ("high", "critical"):
            adjustment -= Decimal("0.15")
        elif risk_level == "medium":
            adjustment -= Decimal("0.05")

        final_conf = (model_conf + adjustment).quantize(Decimal("0.0001"))
        final_conf = max(Decimal("0"), min(Decimal("1"), final_conf))

        band_width = ((Decimal("1") - final_conf) * Decimal("0.2")).quantize(Decimal("0.0001"))
        low = max(Decimal("0"), (model_prob - band_width).quantize(Decimal("0.0001")))
        high = min(Decimal("1"), (model_prob + band_width).quantize(Decimal("0.0001")))

        no_trade_reason: str | None = None
        if final_conf < Decimal("0.30"):
            no_trade_reason = no_trade.get("reason") or "confidence below threshold"
        elif scores["liquidity_score"] < Decimal("0.05"):
            no_trade_reason = no_trade.get("reason") or "insufficient liquidity"
        elif scores["freshness_score"] < Decimal("0.20"):
            no_trade_reason = no_trade.get("reason") or "stale market data"
        elif verdict == "block":
            no_trade_reason = no_trade.get("reason") or f"strategy critique blocked: {critique.get('reasoning', 'n/a')}"
        else:
            no_trade_reason = no_trade.get("reason")

        reasoning = " | ".join(
            [
                f"DeepSeek first-pass: {deep.get('reasoning', 'n/a')}",
                f"Minimax critique ({verdict or 'none'}): {critique.get('reasoning', 'n/a')}",
                f"Risk ({risk_level or 'none'}): {risk.get('reasoning', 'n/a')}",
                f"Thesis: {thesis.get('thesis', 'n/a')}",
            ]
        )

        calibration_notes = [
            f"spread_score={scores['spread_score']}",
            f"depth_score={scores['depth_score']}",
            f"liquidity_score={scores['liquidity_score']}",
            f"freshness_score={scores['freshness_score']}",
            f"settlement_risk_score={scores['settlement_risk_score']}",
            f"deepseek_provider={reviews['deepseek_forecast'].decision.provider_name}",
            f"critique_provider={reviews['critique'].decision.provider_name}",
        ]

        model_summary = "MOCK_ONLY" if self.model_mode == "MOCK_ONLY" else "deepseek_v4_flash+minimax_m3"

        return ForecastOpinion(
            market_ticker=base.market_ticker,
            contract_ticker=base.contract_ticker,
            forecast_reference=base.proof_reference,
            market_implied_probability=scores["market_implied_probability"],
            dummy_probability=model_prob,
            probability_delta=(model_prob - scores["market_implied_probability"]).quantize(Decimal("0.0001")),
            confidence_score=final_conf,
            uncertainty_band=(low, high),
            model_summary=model_summary,
            reasoning=reasoning,
            no_trade_reason=no_trade_reason,
            calibration_notes=calibration_notes,
            timestamp=base.timestamp,
            expiration=base.expiration,
            proof_reference=f"hybrid_forecast_v2_{base.market_ticker}_{base.contract_ticker}_{self._now().isoformat()}",
        )

    def _mock_market_data(self) -> list[tuple[Market, Contract, OrderBook]]:
        now = self._now()
        entries: list[tuple[Market, Contract, OrderBook]] = []

        weather_market = Market(
            ticker="WEATHER-NYC-RAIN",
            title="Will it rain in NYC tomorrow?",
            status="active",
            category="Weather",
            event_ticker="WEATHER-NYC-RAIN",
            contracts=[
                Contract(
                    ticker="WEATHER-NYC-RAIN-YES",
                    title="Yes",
                    status="active",
                    yes_bid=49,
                    yes_ask=51,
                )
            ],
        )
        weather_book = OrderBook(
            market_ticker="WEATHER-NYC-RAIN",
            contract_ticker="WEATHER-NYC-RAIN-YES",
            bids=[OrderBookLevel(price=49, size=600)],
            asks=[OrderBookLevel(price=51, size=500)],
            timestamp=now,
        )
        entries.append((weather_market, weather_market.contracts[0], weather_book))

        crypto_market = Market(
            ticker="BTC-ABOVE-100K",
            title="Will Bitcoin trade above $100k at year-end?",
            status="active",
            category="Crypto",
            event_ticker="BTC-ABOVE-100K",
            contracts=[
                Contract(
                    ticker="BTC-ABOVE-100K-YES",
                    title="Yes",
                    status="active",
                    yes_bid=57,
                    yes_ask=63,
                )
            ],
        )
        crypto_book = OrderBook(
            market_ticker="BTC-ABOVE-100K",
            contract_ticker="BTC-ABOVE-100K-YES",
            bids=[OrderBookLevel(price=57, size=300)],
            asks=[OrderBookLevel(price=63, size=300)],
            timestamp=now,
        )
        entries.append((crypto_market, crypto_market.contracts[0], crypto_book))

        macro_market = Market(
            ticker="SPX-ABOVE-5000",
            title="Will S&P 500 close above 5000?",
            status="active",
            category="Macro",
            event_ticker="SPX-ABOVE-5000",
            contracts=[
                Contract(
                    ticker="SPX-ABOVE-5000-YES",
                    title="Yes",
                    status="active",
                    yes_bid=48,
                    yes_ask=52,
                )
            ],
        )
        macro_book = OrderBook(
            market_ticker="SPX-ABOVE-5000",
            contract_ticker="SPX-ABOVE-5000-YES",
            bids=[OrderBookLevel(price=48, size=800)],
            asks=[OrderBookLevel(price=52, size=800)],
            timestamp=now,
        )
        entries.append((macro_market, macro_market.contracts[0], macro_book))

        politics_market = Market(
            ticker="POLITICS-WHO-WINS",
            title="Who will win the upcoming election?",
            status="active",
            category="Politics",
            event_ticker="POLITICS-WHO-WINS",
            contracts=[
                Contract(
                    ticker="POLITICS-WHO-WINS-YES",
                    title="Incumbent",
                    status="active",
                    yes_bid=30,
                    yes_ask=70,
                )
            ],
        )
        politics_book = OrderBook(
            market_ticker="POLITICS-WHO-WINS",
            contract_ticker="POLITICS-WHO-WINS-YES",
            bids=[OrderBookLevel(price=30, size=50)],
            asks=[OrderBookLevel(price=70, size=50)],
            timestamp=now,
        )
        entries.append((politics_market, politics_market.contracts[0], politics_book))

        stale_market = Market(
            ticker="MEME-STALE",
            title="Will a meme coin trend today?",
            status="active",
            category="Entertainment",
            event_ticker="MEME-STALE",
            contracts=[
                Contract(
                    ticker="MEME-STALE-YES",
                    title="Yes",
                    status="active",
                    yes_bid=49,
                    yes_ask=51,
                )
            ],
        )
        stale_book = OrderBook(
            market_ticker="MEME-STALE",
            contract_ticker="MEME-STALE-YES",
            bids=[OrderBookLevel(price=49, size=1)],
            asks=[OrderBookLevel(price=51, size=1)],
            timestamp=now,
            freshness_score=Decimal("0.10"),
        )
        entries.append((stale_market, stale_market.contracts[0], stale_book))

        return entries

    def _select_from_scored(
        self,
        scored: list[tuple[Market, Contract, OrderBook, dict[str, Any]]],
        max_markets: int,
    ) -> list[tuple[Market, Contract, OrderBook, dict[str, Any]]]:
        selected: list[tuple[Market, Contract, OrderBook, dict[str, Any]]] = []
        used: set[str] = set()

        def add(predicate):
            for item in scored:
                if item[1].ticker in used:
                    continue
                if predicate(item):
                    selected.append(item)
                    used.add(item[1].ticker)
                    return True
            return False

        add(lambda item: "weather" in f"{item[0].category} {item[0].title}".lower())
        add(lambda item: any(k in f"{item[0].category} {item[0].title}".lower() for k in ("crypto", "btc", "bitcoin")))
        add(lambda item: any(k in f"{item[0].category} {item[0].title}".lower() for k in ("macro", "index", "economic", "spx", "sp500", "nasdaq", "gdp", "inflation")))
        for item in sorted(scored, key=lambda x: float(x[3]["liquidity_score"]), reverse=True):
            if item[1].ticker not in used:
                selected.append(item)
                used.add(item[1].ticker)
                break
        for item in sorted(scored, key=lambda x: (x[3]["spread_cents"] or 0), reverse=True):
            if item[1].ticker not in used:
                selected.append(item)
                used.add(item[1].ticker)
                break
        for item in sorted(scored, key=lambda x: float(x[3]["freshness_score"]) * float(x[3]["depth_score"])):
            if item[1].ticker not in used:
                selected.append(item)
                used.add(item[1].ticker)
                break
        for item in sorted(scored, key=lambda x: float(x[3]["liquidity_score"]), reverse=True):
            if len(selected) >= max_markets:
                break
            if item[1].ticker not in used:
                selected.append(item)
                used.add(item[1].ticker)
        return selected[:max_markets]

    async def _fetch_live_market_data(
        self,
        reader: KalshiRealReadOnly,
        max_markets: int,
    ) -> list[tuple[Market, Contract, OrderBook, dict[str, Any]]]:
        markets_raw = await reader.get_markets()
        markets = self.normalizer.normalize_markets(markets_raw)
        candidates: list[tuple[Market, Contract]] = []
        for market in markets:
            if market.status.lower() != "active":
                continue
            for contract in market.contracts:
                if contract.status.lower() != "active":
                    continue
                candidates.append((market, contract))

        # Bound orderbook fetches while preserving variety.
        sample = candidates[: max(max_markets * 4, 20)]
        scored: list[tuple[Market, Contract, OrderBook, dict[str, Any]]] = []
        for market, contract in sample:
            try:
                raw_book = await reader.get_orderbook(contract.ticker)
                orderbook = self.normalizer.normalize_orderbook(contract.ticker, raw_book)
                orderbook.market_ticker = market.ticker
                orderbook.contract_ticker = contract.ticker
                scores = self._score_market(market, contract, orderbook)
                scored.append((market, contract, orderbook, scores))
            except Exception:
                continue
        return self._select_from_scored(scored, max_markets)

    @staticmethod
    def _json_default(obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, set):
            return sorted(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    def _write_artifacts(
        self,
        snapshot_source: str,
        reader: KalshiRealReadOnly | None,
        entries: list[tuple[Market, Contract, OrderBook, dict[str, Any]]],
        reviews: list[dict[str, Any]],
        opinions: list[ForecastOpinion],
        max_markets: int,
    ) -> dict[str, Path]:
        now = self._now()
        endpoints_called: set[str] = set()
        order_creating: set[str] = set()
        if reader is not None and self.credentials_present:
            endpoints_called = reader.endpoints_called()
            order_creating = reader.order_creating_endpoints_called()

        report_path = self.artifact_dir / "real_market_forecast_loop_report_v2.json"
        manifest_path = self.artifact_dir / "forecast_opinion_manifest_v2.json"
        proof_path = self.artifact_dir / "live_hybrid_forecast_proof_report_v1.json"

        report = {
            "report_type": "real_market_forecast_loop_v2",
            "generated_at": now.isoformat(),
            "source": snapshot_source,
            "model_mode": self.model_mode,
            "kalshi_credentials_present": self.credentials_present,
            "max_markets": max_markets,
            "market_count": len(entries),
            "opinion_count": len(opinions),
            "endpoints_called": sorted(endpoints_called),
            "order_creating_endpoints_called": sorted(order_creating),
            "markets": [
                {
                    "market_ticker": market.ticker,
                    "contract_ticker": contract.ticker,
                    "title": market.title,
                    "category": market.category,
                    "best_bid_cents": scores["best_bid_cents"],
                    "best_ask_cents": scores["best_ask_cents"],
                    "spread_cents": scores["spread_cents"],
                    "market_implied_probability": str(scores["market_implied_probability"]),
                    "dummy_statistical_probability": str(scores["dummy_statistical_probability"]),
                    "depth_score": str(scores["depth_score"]),
                    "spread_score": str(scores["spread_score"]),
                    "liquidity_score": str(scores["liquidity_score"]),
                    "freshness_score": str(scores["freshness_score"]),
                    "settlement_risk_score": str(scores["settlement_risk_score"]),
                }
                for market, contract, _orderbook, scores in entries
            ],
            "model_decisions": [
                {
                    "market_ticker": op.market_ticker,
                    "contract_ticker": op.contract_ticker,
                    "deepseek_decision": review["deepseek_forecast"].decision.model_dump(mode="json"),
                    "no_trade_decision": review["no_trade"].decision.model_dump(mode="json"),
                    "critique_decision": review["critique"].decision.model_dump(mode="json"),
                    "risk_decision": review["risk"].decision.model_dump(mode="json"),
                    "thesis_decision": review["thesis"].decision.model_dump(mode="json"),
                }
                for op, review in zip(opinions, reviews)
            ],
            "opinions": [op.model_dump(mode="json") for op in opinions],
        }
        report_path.write_text(json.dumps(report, indent=2, default=self._json_default))

        manifest = {
            "manifest_type": "forecast_opinion_manifest_v2",
            "generated_at": now.isoformat(),
            "model_mode": self.model_mode,
            "source": snapshot_source,
            "opinion_count": len(opinions),
            "opinions": [op.model_dump(mode="json") for op in opinions],
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, default=self._json_default))

        proof = {
            "report_type": "live_hybrid_forecast_proof_v1",
            "generated_at": now.isoformat(),
            "model_mode": self.model_mode,
            "kalshi_credentials_present": self.credentials_present,
            "no_order_submitted": True,
            "endpoints_called": sorted(endpoints_called),
            "order_creating_endpoints_called": sorted(order_creating),
            "model_provider_decisions": report["model_decisions"],
            "opinion_count": len(opinions),
            "opinion_proof_references": [op.proof_reference for op in opinions],
        }
        proof_path.write_text(json.dumps(proof, indent=2, default=self._json_default))

        return {
            "report": report_path,
            "manifest": manifest_path,
            "proof": proof_path,
        }

    async def _run_inner(self, max_markets: int = 5) -> dict[str, Any]:
        self.model_mode = self._determine_model_mode()
        reader: KalshiRealReadOnly | None = None
        try:
            reader = KalshiRealReadOnly()
            self.credentials_present = True
        except KalshiCredentialsMissing:
            self.credentials_present = False

        entries: list[tuple[Market, Contract, OrderBook, dict[str, Any]]] = []
        snapshot_source = "live"
        try:
            if reader is None:
                snapshot_source = "mock"
                mock_entries = self._mock_market_data()
                entries = self._select_from_scored(
                    [(m, c, ob, self._score_market(m, c, ob)) for m, c, ob in mock_entries],
                    max_markets,
                )
            else:
                entries = await self._fetch_live_market_data(reader, max_markets)
        finally:
            if reader is not None:
                await reader.close()

        opinions: list[ForecastOpinion] = []
        reviews: list[dict[str, Any]] = []
        for market, contract, orderbook, scores in entries:
            base = self._build_base_forecast(market, contract, orderbook, scores)
            review = await self.hybrid_engine.hybrid_review(
                base=base,
                orderbook=orderbook,
                market=market,
                contract=contract,
                scores=scores,
                model_mode=self.model_mode,
            )
            reviews.append(review)
            opinion = self._synthesize_opinion(base, scores, review)
            opinions.append(opinion)
            self.storage.append_forecast(opinion)

        artifact_paths = self._write_artifacts(snapshot_source, reader, entries, reviews, opinions, max_markets)

        return {
            "source": snapshot_source,
            "model_mode": self.model_mode,
            "kalshi_credentials_present": self.credentials_present,
            "opinions": [op.model_dump(mode="json") for op in opinions],
            "count": len(opinions),
            "artifact_paths": {k: str(v) for k, v in artifact_paths.items()},
        }

    async def run(self, max_markets: int = 5) -> dict[str, Any]:
        """Run the V2 forecast loop with a hard outer timeout."""
        try:
            return await asyncio.wait_for(
                self._run_inner(max_markets=max_markets),
                timeout=FORECAST_LOOP_V2_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "RealMarketForecastLoopV2.run timed out",
                extra={"component": "real_market_forecast_loop_v2", "max_markets": max_markets},
            )
            return {
                "source": "timeout",
                "model_mode": "MOCK_ONLY",
                "kalshi_credentials_present": False,
                "opinions": [],
                "count": 0,
                "reason": "forecast_loop_v2_timeout",
            }
