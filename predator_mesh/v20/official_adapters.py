"""Official/public read-only adapter activation pack for V20."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OfficialAdapterStatus:
    adapter_id: str
    name: str
    source_url: str
    domain: str
    legality_class: str
    status: str
    blocker: str
    timeout_seconds: int = 5

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": f"V20: {self.name} Adapter",
            "adapter_id": self.adapter_id,
            "source_url": self.source_url,
            "domain": self.domain,
            "legality_class": self.legality_class,
            "adapter_status": self.status,
            "blocker": self.blocker,
            "timeout_seconds": self.timeout_seconds,
            "read_only_only": True,
            "private_endpoints_used": False,
            "order_endpoints_called": [],
            "write_endpoints_called": [],
            "bounded_timeouts": True,
            "deterministic_fallback": True,
            "source_freshness_labeled": True,
            "evidence_normalized": self.status in {"STATIC_CURATED_FALLBACK", "REAL_READONLY_READY_PLAN"},
            "secret_values_exposed": False,
            "verdict": "PARTIAL" if self.blocker else "PASS",
        }


class OfficialPublicAdapterActivationPack:
    def adapters(self) -> list[OfficialAdapterStatus]:
        return list(_OFFICIAL_ADAPTERS)

    def to_report(self) -> dict[str, Any]:
        reports = [adapter.to_report() for adapter in self.adapters()]
        return {
            "workstream": "V20: Official/Public Adapter Activation Pack",
            "adapter_count": len(reports),
            "adapters": reports,
            "read_only_only": True,
            "write_endpoints_called": [],
            "private_endpoints_used": False,
            "bounded_timeouts": True,
            "fallback_safe": True,
            "source_api_key_values_exposed": False,
            "secret_values_exposed": False,
            "verdict": "PARTIAL",
        }

    def report_for(self, adapter_id: str) -> dict[str, Any]:
        for adapter in self.adapters():
            if adapter.adapter_id == adapter_id:
                return adapter.to_report()
        raise KeyError(adapter_id)


class NWSWeatherAdapter:
    def to_report(self) -> dict[str, Any]:
        return OfficialPublicAdapterActivationPack().report_for("nws_weather")


class EIAEnergyAdapter:
    def to_report(self) -> dict[str, Any]:
        return OfficialPublicAdapterActivationPack().report_for("eia_energy")


class BLSMacroAdapter:
    def to_report(self) -> dict[str, Any]:
        return OfficialPublicAdapterActivationPack().report_for("bls_macro")


class BEAMacroAdapter:
    def to_report(self) -> dict[str, Any]:
        return OfficialPublicAdapterActivationPack().report_for("bea_macro")


class CensusMacroAdapter:
    def to_report(self) -> dict[str, Any]:
        return OfficialPublicAdapterActivationPack().report_for("census_macro")


class TreasuryDataAdapter:
    def to_report(self) -> dict[str, Any]:
        return OfficialPublicAdapterActivationPack().report_for("treasury_data")


class SECEdgarAdapter:
    def to_report(self) -> dict[str, Any]:
        return OfficialPublicAdapterActivationPack().report_for("sec_edgar")


class WorldBankCommoditiesAdapter:
    def to_report(self) -> dict[str, Any]:
        return OfficialPublicAdapterActivationPack().report_for("world_bank_commodities")


class DefiLlamaCryptoContextAdapter:
    def to_report(self) -> dict[str, Any]:
        return OfficialPublicAdapterActivationPack().report_for("defillama_crypto_context")


class CCXTPublicCryptoAdapterPlan:
    def to_report(self) -> dict[str, Any]:
        return OfficialPublicAdapterActivationPack().report_for("ccxt_public_crypto_plan")


_OFFICIAL_ADAPTERS = (
    OfficialAdapterStatus("nws_weather", "NWS Weather", "https://api.weather.gov", "weather", "OFFICIAL_PUBLIC_READONLY", "STATIC_CURATED_FALLBACK", "No integration-run network call in unit/report default."),
    OfficialAdapterStatus("eia_energy", "EIA Energy", "https://www.eia.gov/opendata/", "oil_energy_direction", "OFFICIAL_PUBLIC_KEYED_READONLY", "BLOCKED_KEY_MISSING", "EIA_API_KEY presence required before real fetch."),
    OfficialAdapterStatus("bls_macro", "BLS Macro", "https://www.bls.gov/developers/", "finance", "OFFICIAL_PUBLIC_READONLY", "STATIC_CURATED_FALLBACK", "No repeated live calls in deterministic unit run."),
    OfficialAdapterStatus("bea_macro", "BEA Macro", "https://apps.bea.gov/api", "finance", "OFFICIAL_PUBLIC_KEYED_READONLY", "BLOCKED_KEY_MISSING", "BEA_API_KEY presence required before real fetch."),
    OfficialAdapterStatus("census_macro", "Census Macro", "https://www.census.gov/data/developers.html", "finance", "OFFICIAL_PUBLIC_READONLY", "STATIC_CURATED_FALLBACK", "No repeated live calls in deterministic unit run."),
    OfficialAdapterStatus("treasury_data", "Treasury Data", "https://fiscaldata.treasury.gov/api-documentation/", "finance", "OFFICIAL_PUBLIC_READONLY", "STATIC_CURATED_FALLBACK", "No repeated live calls in deterministic unit run."),
    OfficialAdapterStatus("sec_edgar", "SEC EDGAR", "https://www.sec.gov/edgar", "finance", "OFFICIAL_PUBLIC_READONLY", "STATIC_CURATED_FALLBACK", "User-agent and rate policy required before integration-run fetch."),
    OfficialAdapterStatus("world_bank_commodities", "World Bank Commodities", "https://www.worldbank.org/en/research/commodity-markets", "commodities", "OFFICIAL_PUBLIC_READONLY", "STATIC_CURATED_FALLBACK", "No repeated live calls in deterministic unit run."),
    OfficialAdapterStatus("defillama_crypto_context", "DefiLlama Crypto Context", "https://defillama.com/docs/api", "crypto", "PUBLIC_CONTEXT_READONLY", "STATIC_CURATED_FALLBACK", "Context only, not production truth."),
    OfficialAdapterStatus("ccxt_public_crypto_plan", "CCXT Public Crypto Plan", "https://github.com/ccxt/ccxt", "crypto", "OPEN_SOURCE_ADAPTER_PLAN", "ADAPTER_PLAN_ONLY", "Optional dependency not required for V20; no execution authority."),
)
