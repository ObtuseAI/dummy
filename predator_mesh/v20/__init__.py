"""DUMMY V20 source universe and edge-terrain primitives."""

from __future__ import annotations

MILESTONE = "DUMMY_V20_SOURCE_UNIVERSE_GITHUB_ADAPTER_MINER_EDGE_TERRAIN_AND_REAL_READONLY_DOMAIN_ACTIVATION_V1"

CORE_DOMAINS = ("sports", "weather", "crypto", "commodities", "finance")
EDGE_DOMAINS = (
    "nasdaq_index_direction",
    "oil_energy_direction",
    "cross_asset_macro",
    "volatility",
    "news_event_metadata",
    "kalshi_market_terrain",
)
SOURCE_DOMAINS = (*CORE_DOMAINS, *EDGE_DOMAINS)
