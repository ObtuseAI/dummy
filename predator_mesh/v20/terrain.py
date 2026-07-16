"""V20 edge terrain stacks for major prediction domains."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TerrainSpec:
    name: str
    slug: str
    required_source_needs: tuple[str, ...]
    edge_features: tuple[str, ...]
    blocked_sources: tuple[str, ...]
    public_context_sources: tuple[str, ...]


@dataclass(frozen=True)
class TerrainSourceNeed:
    name: str
    status: str
    blocker: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "blocker": self.blocker}


class _TerrainStack:
    spec: TerrainSpec

    def source_needs(self) -> list[TerrainSourceNeed]:
        needs: list[TerrainSourceNeed] = []
        for need in self.spec.required_source_needs:
            blocked = need in self.spec.blocked_sources
            needs.append(TerrainSourceNeed(need, "BLOCKED_LICENSE_REQUIRED" if blocked else "PUBLIC_CONTEXT_OR_PLAN_ONLY", "license_or_approval_missing" if blocked else "not_promoted_to_real_readonly"))
        return needs

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": f"V20: {self.spec.name} Terrain Stack",
            "terrain_slug": self.spec.slug,
            "required_source_needs": list(self.spec.required_source_needs),
            "source_needs": [need.to_dict() for need in self.source_needs()],
            "edge_features": list(self.spec.edge_features),
            "public_context_sources": list(self.spec.public_context_sources),
            "exchange_native_missing": bool(self.spec.blocked_sources),
            "no_fake_edge_claims": True,
            "baseline_forecast_allowed": False,
            "live_execution_enabled": False,
            "secret_values_exposed": False,
            "verdict": "PARTIAL" if self.spec.blocked_sources else "PASS",
        }

    def evidence_packet_report(self) -> dict[str, Any]:
        return {
            "workstream": f"V20: {self.spec.name} Evidence Packet",
            "terrain_slug": self.spec.slug,
            "evidence_mode": "STATIC_CURATED_CONTEXT_WITH_BLOCKERS",
            "real_readonly_evidence_count": 0,
            "fixture_or_context_count": len(self.spec.public_context_sources),
            "source_blockers": list(self.spec.blocked_sources),
            "fixture_evidence_claimed_real": False,
            "outcome_leakage_detected": False,
            "secret_values_exposed": False,
            "verdict": "PARTIAL",
        }

    def edge_feature_map_report(self) -> dict[str, Any]:
        features = [
            {
                "feature": feature,
                "status": "BLOCKED_SOURCE_GAP" if feature in {"futures trend", "curve structure", "liquidity/spread quality"} and self.spec.blocked_sources else "CONTEXT_ONLY",
                "confidence_weight": 0.0 if self.spec.blocked_sources else 0.25,
            }
            for feature in self.spec.edge_features
        ]
        return {
            "workstream": f"V20: {self.spec.name} Edge Feature Map",
            "features": features,
            "no_fake_edge_claims": True,
            "secret_values_exposed": False,
            "verdict": "PARTIAL" if self.spec.blocked_sources else "PASS",
        }

    def no_trade_gate_report(self) -> dict[str, Any]:
        no_trade = bool(self.spec.blocked_sources)
        return {
            "workstream": f"V20: {self.spec.name} No Trade Gate",
            "no_trade": no_trade,
            "no_trade_reasons": list(self.spec.blocked_sources) or ["context_only_until_real_evidence_promoted"],
            "source_stack_too_thin": no_trade,
            "live_execution_enabled": False,
            "secret_values_exposed": False,
            "verdict": "PARTIAL" if no_trade else "PASS",
        }

    def source_blocker_report(self) -> dict[str, Any]:
        return {
            "workstream": f"V20: {self.spec.name} Source Blocker",
            "exchange_native_missing": bool(self.spec.blocked_sources),
            "blocked_sources": list(self.spec.blocked_sources),
            "blocker_count": len(self.spec.blocked_sources),
            "operator_actions": ["approve source", "review terms", "add key/license if explicitly approved"],
            "secret_values_exposed": False,
            "verdict": "PARTIAL" if self.spec.blocked_sources else "PASS",
        }


class NasdaqSourceNeed(TerrainSourceNeed):
    pass


class NasdaqEvidencePacket(dict):
    pass


class NasdaqEdgeFeatureMap(dict):
    pass


class NasdaqNoTradeGate(dict):
    pass


class NasdaqForecastInput(dict):
    pass


class NasdaqSourceBlocker(dict):
    pass


class NasdaqDirectionTerrainStack(_TerrainStack):
    spec = TerrainSpec(
        "Nasdaq Direction",
        "nasdaq_direction",
        (
            "NQ futures orderbook/trades",
            "ES futures context",
            "QQQ/SPY proxy prices/volume",
            "mega-cap constituent moves",
            "sector ETF rotation",
            "VIX/VXN/options skew",
            "2Y/10Y yields",
            "DXY",
            "macro calendar",
            "Fed calendar/speaker/event risk",
            "earnings calendar",
            "breadth",
            "Kalshi market terrain",
            "news/event metadata",
        ),
        (
            "futures trend",
            "cash proxy trend",
            "mega-cap breadth",
            "sector confirmation",
            "rates shock",
            "dollar shock",
            "vol regime",
            "options skew pressure",
            "macro release proximity",
            "earnings/event concentration",
            "liquidity/spread quality",
            "stale data risk",
            "contradiction score",
        ),
        ("NQ futures orderbook/trades", "ES futures context", "VIX/VXN/options skew"),
        ("Treasury yields", "SEC EDGAR", "FRED/BLS/BEA macro context"),
    )


class OilSourceNeed(TerrainSourceNeed):
    pass


class OilEvidencePacket(dict):
    pass


class OilEdgeFeatureMap(dict):
    pass


class OilNoTradeGate(dict):
    pass


class OilForecastInput(dict):
    pass


class OilSourceBlocker(dict):
    pass


class OilDirectionTerrainStack(_TerrainStack):
    spec = TerrainSpec(
        "Oil Direction",
        "oil_direction",
        (
            "CL futures orderbook/trades",
            "Brent/ICE context",
            "CL calendar spreads",
            "Brent/WTI spread",
            "EIA inventories",
            "Cushing storage",
            "refinery utilization",
            "gasoline/distillate inventories",
            "Baker Hughes rig count",
            "OPEC/IEA public reports",
            "NOAA/NWS hurricane/Gulf weather disruption",
            "shipping/tanker flows licensed gate",
            "USD/DXY",
            "rates",
            "China/global demand proxies",
            "Kalshi market terrain",
            "news/event metadata",
        ),
        (
            "futures trend",
            "curve structure",
            "spread pressure",
            "inventory surprise context",
            "Cushing draw/build",
            "refinery demand",
            "weather disruption risk",
            "supply shock flag",
            "dollar/rates pressure",
            "demand proxy confirmation",
            "liquidity/spread quality",
            "stale data risk",
            "contradiction score",
        ),
        ("CL futures orderbook/trades", "Brent/ICE context", "shipping/tanker flows licensed gate"),
        ("EIA inventories plan", "NOAA/NWS hurricane products", "World Bank commodity prices"),
    )


class CryptoSourceNeed(TerrainSourceNeed):
    pass


class CryptoEvidencePacketV3(dict):
    pass


class CryptoEdgeFeatureMap(dict):
    pass


class CryptoNoTradeGateV2(dict):
    pass


class CryptoForecastInput(dict):
    pass


class CryptoSourceBlocker(dict):
    pass


class CryptoDirectionTerrainStack(_TerrainStack):
    spec = TerrainSpec(
        "Crypto Direction",
        "crypto_direction",
        (
            "Coinbase/Kraken public spot/orderbook",
            "CCXT public adapter",
            "cross-exchange divergence",
            "spot trend",
            "volatility regime",
            "Deribit options/vol",
            "funding/open interest READ_ONLY context",
            "stablecoin/on-chain context",
            "ETF flow proxies",
            "Nasdaq/risk correlation",
            "DXY/rates",
            "Kalshi crypto market pricing",
            "news impulse metadata",
        ),
        ("spot trend", "cross-exchange divergence", "volatility regime", "risk correlation", "stale data risk", "contradiction score"),
        ("CCXT public adapter", "Deribit options/vol", "funding/open interest READ_ONLY context"),
        ("Coinbase public plan", "Kraken public plan", "DefiLlama context"),
    )


class WeatherSourceNeed(TerrainSourceNeed):
    pass


class WeatherEvidencePacketV3(dict):
    pass


class WeatherEdgeFeatureMap(dict):
    pass


class WeatherNoTradeGateV2(dict):
    pass


class WeatherEdgeTerrainStack(_TerrainStack):
    spec = TerrainSpec(
        "Weather Edge",
        "weather_edge",
        ("NWS forecast", "NWS observations", "NOAA station data", "HRRR/GFS/ECMWF model-data plan/gate", "radar/precip estimates", "storm/hurricane official products", "settlement station mapping", "forecast age/freshness", "forecast disagreement"),
        ("forecast freshness", "station mapping quality", "model disagreement", "storm risk", "stale data risk"),
        ("HRRR/GFS/ECMWF model-data plan/gate",),
        ("NWS forecast", "NOAA station data", "NHC official products"),
    )


class SportsSourceNeed(TerrainSourceNeed):
    pass


class SportsEvidencePacketV3(dict):
    pass


class SportsEdgeFeatureMap(dict):
    pass


class SportsNoTradeGateV2(dict):
    pass


class SportsEdgeTerrainStack(_TerrainStack):
    spec = TerrainSpec(
        "Sports Edge",
        "sports_edge",
        ("approved schedule/status", "approved stats", "injury/lineup licensed gate", "outdoor weather impact", "rest/travel/form if approved", "settlement mapping", "Kalshi market pricing", "no odds scraping unless approved"),
        ("schedule certainty", "stats quality", "weather impact", "rest/travel form", "settlement mapping quality", "stale data risk"),
        ("injury/lineup licensed gate", "rest/travel/form if approved", "Kalshi market pricing"),
        ("approved schedule/status plan", "NWS outdoor weather context"),
    )


TERRAIN_STACKS = {
    "nasdaq": NasdaqDirectionTerrainStack,
    "oil": OilDirectionTerrainStack,
    "crypto": CryptoDirectionTerrainStack,
    "weather": WeatherEdgeTerrainStack,
    "sports": SportsEdgeTerrainStack,
}
