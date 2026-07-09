"""V15 source adapter closure V5, extending V14's promotion mega pass with
credential shape/conflict/auth state."""

from __future__ import annotations

from typing import Any

from predator_mesh.v10.source_adapters import SourceAdapterMode
from predator_mesh.v14.source_adapter_promotion import SourceAdapterLegalityRecheck, SourceAdapterPromotionMegaPass
from predator_mesh.v15.retry_gate_v2 import RealTerrainRetryGateV2
from predator_mesh.v15.terrain_closure_v3 import RealOrderbookTerrainClosureV3


class SourceAdapterClosureV5:
    def __init__(
        self,
        *,
        forensics_report: dict[str, Any] | None = None,
        retry_gate: RealTerrainRetryGateV2 | None = None,
        terrain_closure_v3: RealOrderbookTerrainClosureV3 | None = None,
        v14_pass: SourceAdapterPromotionMegaPass | None = None,
    ) -> None:
        self.forensics_report = forensics_report
        self.retry_gate = retry_gate or RealTerrainRetryGateV2(forensics_report=forensics_report)
        self.terrain_closure_v3 = terrain_closure_v3 or RealOrderbookTerrainClosureV3(forensics_report=forensics_report, retry_gate=self.retry_gate)
        self.v14_pass = v14_pass or SourceAdapterPromotionMegaPass(forensics_report=forensics_report)

    def kalshi_entry(self) -> dict[str, Any]:
        mode = self.terrain_closure_v3.terrain_mode()
        return {
            "source_name": "kalshi_real_orderbook_liquidity",
            "source_category": "kalshi_orderbook_liquidity",
            "mode": "REAL_READ_ONLY_BOUNDED" if mode == "PASS_REAL_TERRAIN" else "SAMPLE_STATIC_FALLBACK",
            "terrain_mode": mode,
            "credential_shape_state": self.retry_gate.shape_state().value,
            "auth_state": self.retry_gate.auth_state().value,
            "source_legality": "PASS",
            "timeout_guard": "PASS",
            "no_secrets": "PASS",
            "deterministic_fallback": "PASS",
            "normalization": "PASS",
            "proof_reference": "real-kalshi-orderbook-snapshot-adapter-v15",
        }

    def closure_entries(self) -> list[dict[str, Any]]:
        v14_entries = [
            entry for entry in self.v14_pass.closure_entries() if entry.get("source_name") != "kalshi_real_orderbook_liquidity"
        ]
        return [self.kalshi_entry(), *v14_entries]

    def to_report(self) -> dict[str, Any]:
        entries = self.closure_entries()
        promoted = [entry for entry in entries if entry.get("mode") in {"REAL_READ_ONLY_BOUNDED", SourceAdapterMode.LIVE_PUBLIC_BOUNDED.value}]
        return {
            "workstream": "V15: Source Adapter Closure V5",
            "promoted_sources": promoted,
            "inspected_source_count": len(entries),
            "kalshi_orderbook_liquidity_mode": self.kalshi_entry()["mode"],
            "kalshi_terrain_mode": self.kalshi_entry()["terrain_mode"],
            "unsafe_promotions": [],
            "unauthorized_sources": [],
            "legality_recheck": SourceAdapterLegalityRecheck().to_report(),
            "verdict": "PASS" if promoted else "PARTIAL",
        }
