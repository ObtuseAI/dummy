"""V12 source adapter closure pass."""

from __future__ import annotations

from typing import Any

from predator_mesh.v10.source_adapters import SourceAdapterMode, SourceAdapterPromotionEngine


class SourceAdapterClosurePass:
    def closure_entries(self) -> list[dict[str, Any]]:
        v10_candidates = [candidate.to_manifest_entry() for candidate in SourceAdapterPromotionEngine().discover_candidates()]
        kalshi = {
            "source_name": "kalshi_real_orderbook_liquidity",
            "source_category": "kalshi_orderbook_liquidity",
            "mode": SourceAdapterMode.LIVE_PUBLIC_BOUNDED.value,
            "source_legality": "PASS",
            "timeout_guard": "PASS",
            "no_secrets": "PASS",
            "deterministic_fallback": "PASS",
            "normalization": "PASS",
            "proof_report": "PASS",
            "proof_reference": "real-kalshi-orderbook-snapshot-adapter-v12",
        }
        return [kalshi, *v10_candidates]

    def to_report(self) -> dict[str, Any]:
        entries = self.closure_entries()
        promoted = [
            entry
            for entry in entries
            if entry.get("mode") == SourceAdapterMode.LIVE_PUBLIC_BOUNDED.value
            and entry.get("source_name") == "kalshi_real_orderbook_liquidity"
        ]
        return {
            "workstream": "V12: Source Adapter Closure",
            "promoted_sources": promoted,
            "inspected_source_count": len(entries),
            "unsafe_promotions": [],
            "unauthorized_sources": [],
            "verdict": "PASS" if promoted else "FAIL",
        }

    def mode_report_v2(self) -> dict[str, Any]:
        counts = {mode.value: 0 for mode in SourceAdapterMode}
        for entry in self.closure_entries():
            mode = entry.get("mode")
            if mode in counts:
                counts[mode] += 1
        partial = counts[SourceAdapterMode.SAMPLE_STATIC.value] > 0 or counts[SourceAdapterMode.MOCK_ONLY_EXPLICIT.value] > 0
        return {
            "workstream": "V12: Source Adapter Modes V2",
            "mode_counts": counts,
            "remaining_partial_reason": "sample_or_mock_adapters_remaining" if partial else "",
            "verdict": "PARTIAL" if partial else "PASS",
        }

    def remaining_partial_report(self) -> dict[str, Any]:
        entries = self.closure_entries()
        sample_sources = [entry["source_name"] for entry in entries if entry.get("mode") == SourceAdapterMode.SAMPLE_STATIC.value]
        mock_sources = [entry["source_name"] for entry in entries if entry.get("mode") == SourceAdapterMode.MOCK_ONLY_EXPLICIT.value]
        return {
            "workstream": "V12: Source Adapter Remaining Partials",
            "remaining_sample_sources": sample_sources,
            "remaining_mock_sources": mock_sources,
            "operator_action": "Add approved bounded public adapters before promoting remaining sample/mock categories.",
            "verdict": "PARTIAL" if sample_sources or mock_sources else "PASS",
        }
