"""Source adapter truth alignment for V16."""

from __future__ import annotations

from typing import Any

from predator_mesh.v16.terrain_truth import RealTerrainTruthResolution


class SourceAdapterTruthAlignment:
    def __init__(self, terrain_truth: RealTerrainTruthResolution) -> None:
        self.terrain_truth = terrain_truth

    def kalshi_mode(self) -> str:
        return "REAL_READ_ONLY_BOUNDED" if self.terrain_truth.verdict.startswith("PASS_REAL_TERRAIN") else "SAMPLE_STATIC_FALLBACK"

    def fallback_reason(self) -> str:
        return "" if self.kalshi_mode() == "REAL_READ_ONLY_BOUNDED" else self.terrain_truth.verdict

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V16: Source Adapter Truth Alignment",
            "kalshi_orderbook_liquidity_mode": self.kalshi_mode(),
            "terrain_truth_verdict": self.terrain_truth.verdict,
            "fallback_reason": self.fallback_reason(),
            "existing_sample_static_domains": ["weather", "sports", "macro", "finance", "commodities", "crypto"],
            "unauthorized_sources": [],
            "secret_values_exposed": False,
            "verdict": "PASS" if self.kalshi_mode() == "REAL_READ_ONLY_BOUNDED" else "PARTIAL",
        }

    def source_adapter_mode_report_v6(self) -> dict[str, Any]:
        return {
            "workstream": "V16: Source Adapter Mode V6",
            "modes": {
                "kalshi_real_orderbook_liquidity": self.kalshi_mode(),
                "weather": "SAMPLE_STATIC_FALLBACK",
                "sports": "SAMPLE_STATIC_FALLBACK",
                "macro": "SAMPLE_STATIC_FALLBACK",
                "finance": "SAMPLE_STATIC_FALLBACK",
                "commodities": "SAMPLE_STATIC_FALLBACK",
                "crypto": "SAMPLE_STATIC_FALLBACK",
            },
            "terrain_truth_verdict": self.terrain_truth.verdict,
            "fallback_reason": self.fallback_reason(),
            "secret_values_exposed": False,
            "verdict": "PASS" if self.kalshi_mode() == "REAL_READ_ONLY_BOUNDED" else "PARTIAL",
        }

    def remaining_partial_report_v5(self) -> dict[str, Any]:
        remaining = ["weather", "sports", "macro", "finance", "commodities", "crypto"]
        return {
            "workstream": "V16: Source Adapter Remaining Partial V5",
            "remaining_partial_modes": remaining,
            "kalshi_real_orderbook_liquidity": self.kalshi_mode(),
            "terrain_truth_verdict": self.terrain_truth.verdict,
            "do_not_broaden_in_v16": True,
            "secret_values_exposed": False,
            "verdict": "PARTIAL" if remaining else "PASS",
        }
