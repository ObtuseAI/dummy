"""In-house V30 fixture-first adapters and contract helpers."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class FixtureMode(str, Enum):
    REPLAY_FIXTURE = "REPLAY_FIXTURE"
    PUBLIC_SAMPLE_RESPONSE = "PUBLIC_SAMPLE_RESPONSE"
    CACHED_PUBLIC_RESPONSE = "CACHED_PUBLIC_RESPONSE"
    LIVE_PUBLIC_PROBE_RESULT = "LIVE_PUBLIC_PROBE_RESULT"
    INVALID_STALE_CACHE = "INVALID_STALE_CACHE"
    INVALID_UNTRUSTED_SAMPLE = "INVALID_UNTRUSTED_SAMPLE"


@dataclass(frozen=True)
class AdapterSourceRefV1:
    source_name: str
    source_mode: str
    source_url_class: str
    venue: str | None = None
    public_keyless: bool = True
    private_endpoint_used: bool = False
    requires_secret: bool = False


@dataclass(frozen=True)
class AdapterRequestV1:
    adapter_id: str
    market_class: str
    metric: str
    target: dict[str, Any]
    fixture_id: str
    mode: FixtureMode = FixtureMode.REPLAY_FIXTURE
    requested_at: str = field(default_factory=now_iso)
    integration_confirmed: bool = False


@dataclass(frozen=True)
class AdapterErrorV1:
    code: str
    message: str
    retryable: bool = False


@dataclass(frozen=True)
class AdapterFixtureRecordV1:
    fixture_id: str
    adapter_id: str
    mode: FixtureMode
    source_label: str
    evidence_timestamp: str
    market_class: str
    metric: str
    value: Any
    provenance: str
    settlement_compatible: bool
    source_url_class: str = "PUBLIC_KEYLESS_FIXTURE"
    venue: str | None = None
    blocker: str | None = None
    confidence: float = 0.7
    freshness_status: str = "FIXTURE_NOT_LIVE"
    rule_text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["mode"] = self.mode.value
        return data


@dataclass(frozen=True)
class AdapterEvidencePacketV1:
    adapter_id: str
    source_name: str
    source_mode: str
    retrieval_timestamp: str
    evidence_timestamp: str | None
    market_class: str
    evidence_role: str
    settlement_role: str
    metric: str
    value: Any
    freshness_status: str
    provenance: str
    confidence: float
    blocker: str | None
    source_ref: AdapterSourceRefV1
    evidence_class: str
    live_observation_eligible: bool
    live_score_eligible: bool
    settlement_compatible: bool
    execution_bridge_present: bool = False
    context_only_claimed_edge: bool = False
    ambiguous_settlement_scored: bool = False
    source_unavailable_scored: bool = False
    not_due_scored: bool = False
    outcome_fabricated: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_ref"] = asdict(self.source_ref)
        return data


@dataclass(frozen=True)
class AdapterResponseV1:
    adapter_id: str
    source_name: str
    source_mode: str
    retrieval_timestamp: str
    evidence_timestamp: str | None
    market_class: str
    evidence_role: str
    settlement_role: str
    metric: str
    value: Any
    freshness_status: str
    provenance: str
    confidence: float
    source_ref: AdapterSourceRefV1
    blocker: str | None = None
    error: AdapterErrorV1 | None = None
    settlement_compatible: bool = True
    consensus_status: str | None = None
    private_endpoint_used: bool = False
    execution_bridge_present: bool = False

    def evidence_class(self) -> str:
        if self.blocker in {"METRIC_INCOMPATIBLE", "MALFORMED_FIXTURE", "TERMS_BLOCKED"}:
            return "INVALID"
        if self.blocker == "SOURCE_UNAVAILABLE":
            return "INVALID"
        if self.freshness_status == "STALE":
            return "STALE_NOT_LIVE"
        if self.source_mode == FixtureMode.LIVE_PUBLIC_PROBE_RESULT.value and self.blocker is None:
            return "LIVE_PUBLIC_ELIGIBLE"
        if self.source_mode == FixtureMode.CACHED_PUBLIC_RESPONSE.value and self.blocker is None:
            return "CACHED_PUBLIC_ELIGIBLE"
        if self.source_mode == FixtureMode.PUBLIC_SAMPLE_RESPONSE.value:
            return "PUBLIC_SAMPLE_NOT_LIVE"
        if self.source_mode == FixtureMode.INVALID_STALE_CACHE.value:
            return "STALE_NOT_LIVE"
        if self.source_mode == FixtureMode.INVALID_UNTRUSTED_SAMPLE.value:
            return "INVALID"
        return "FIXTURE_REPLAY_ONLY"

    def to_evidence_packet(self) -> AdapterEvidencePacketV1:
        evidence_class = self.evidence_class()
        live_observation_eligible = evidence_class == "LIVE_PUBLIC_ELIGIBLE"
        live_score_eligible = live_observation_eligible and self.settlement_compatible and self.blocker is None
        return AdapterEvidencePacketV1(
            adapter_id=self.adapter_id,
            source_name=self.source_name,
            source_mode=self.source_mode,
            retrieval_timestamp=self.retrieval_timestamp,
            evidence_timestamp=self.evidence_timestamp,
            market_class=self.market_class,
            evidence_role=self.evidence_role,
            settlement_role=self.settlement_role,
            metric=self.metric,
            value=self.value,
            freshness_status=self.freshness_status,
            provenance=self.provenance,
            confidence=self.confidence,
            blocker=self.blocker,
            source_ref=self.source_ref,
            evidence_class=evidence_class,
            live_observation_eligible=live_observation_eligible,
            live_score_eligible=live_score_eligible,
            settlement_compatible=self.settlement_compatible,
            execution_bridge_present=False,
            ambiguous_settlement_scored=False,
            source_unavailable_scored=False,
            not_due_scored=False,
            outcome_fabricated=False,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_ref"] = asdict(self.source_ref)
        if self.error:
            data["error"] = asdict(self.error)
        data["evidence_packet"] = self.to_evidence_packet().to_dict()
        return data


FIXTURE_RECORDS: dict[str, AdapterFixtureRecordV1] = {
    "weather_kc_temperature_fixture": AdapterFixtureRecordV1(
        fixture_id="weather_kc_temperature_fixture",
        adapter_id="weather_public_observation_v1",
        mode=FixtureMode.REPLAY_FIXTURE,
        source_label="NOAA public weather fixture",
        evidence_timestamp="2026-07-03T18:00:00+00:00",
        market_class="WEATHER_THRESHOLD",
        metric="temperature_f",
        value=82.4,
        provenance="repo-owned fixture based on V29 weather adapter spec shape",
        settlement_compatible=True,
        confidence=0.76,
    ),
    "crypto_btc_usd_fixture": AdapterFixtureRecordV1(
        fixture_id="crypto_btc_usd_fixture",
        adapter_id="crypto_public_price_v1",
        mode=FixtureMode.PUBLIC_SAMPLE_RESPONSE,
        source_label="public crypto spot fixture",
        evidence_timestamp="2026-07-03T18:00:00+00:00",
        market_class="CRYPTO_PRICE_THRESHOLD",
        metric="btc_usd",
        value=67250.25,
        provenance="repo-owned public sample response fixture",
        settlement_compatible=True,
        source_url_class="PUBLIC_KEYLESS_SAMPLE",
        venue="fixture-spot-reference",
        confidence=0.72,
        freshness_status="SAMPLE_NOT_LIVE",
    ),
    "macro_cpi_reference_fixture": AdapterFixtureRecordV1(
        fixture_id="macro_cpi_reference_fixture",
        adapter_id="public_event_reference_v1",
        mode=FixtureMode.CACHED_PUBLIC_RESPONSE,
        source_label="public macro release fixture",
        evidence_timestamp="2026-07-03T14:00:00+00:00",
        market_class="FINANCE_MACRO_RELEASE",
        metric="cpi_yoy",
        value=3.1,
        provenance="repo-owned cached public reference fixture",
        settlement_compatible=True,
        source_url_class="PUBLIC_KEYLESS_CACHED",
        confidence=0.74,
        freshness_status="CACHED_PUBLIC_NOT_LIVE",
    ),
    "kalshi_ambiguous_rule_fixture": AdapterFixtureRecordV1(
        fixture_id="kalshi_ambiguous_rule_fixture",
        adapter_id="kalshi_readonly_rule_v1",
        mode=FixtureMode.REPLAY_FIXTURE,
        source_label="Kalshi read-only rule fixture",
        evidence_timestamp="2026-07-03T13:00:00+00:00",
        market_class="KALSHI_MAPPED_MARKET",
        metric="settlement_rule_text",
        value="Ambiguous rule fixture",
        provenance="repo-owned Kalshi READ_ONLY rule fixture",
        settlement_compatible=False,
        blocker="SETTLEMENT_AMBIGUOUS",
        source_url_class="READ_ONLY_RULE_FIXTURE",
        confidence=0.45,
        rule_text="Ambiguous settlement rule text requires operator review before scoring.",
    ),
    "invalid_stale_crypto_fixture": AdapterFixtureRecordV1(
        fixture_id="invalid_stale_crypto_fixture",
        adapter_id="crypto_public_price_v1",
        mode=FixtureMode.INVALID_STALE_CACHE,
        source_label="stale crypto cache fixture",
        evidence_timestamp="2025-01-01T00:00:00+00:00",
        market_class="CRYPTO_PRICE_THRESHOLD",
        metric="btc_usd",
        value=41200.0,
        provenance="repo-owned stale cache fixture",
        settlement_compatible=False,
        blocker="STALE_EVIDENCE",
        confidence=0.2,
        freshness_status="STALE",
    ),
}


class AdapterFixtureLoaderV1:
    required_fields = {"fixture_id", "adapter_id", "mode", "source_label", "market_class", "metric", "provenance"}

    def load(self, fixture_id: str) -> AdapterFixtureRecordV1:
        try:
            return FIXTURE_RECORDS[fixture_id]
        except KeyError as exc:
            raise ValueError(f"SOURCE_UNAVAILABLE: {fixture_id}") from exc

    def validate(self, payload: dict[str, Any]) -> AdapterFixtureRecordV1:
        missing = self.required_fields - set(payload)
        if missing:
            raise ValueError("MALFORMED_FIXTURE")
        mode = payload["mode"] if isinstance(payload["mode"], FixtureMode) else FixtureMode(str(payload["mode"]))
        return AdapterFixtureRecordV1(
            fixture_id=str(payload["fixture_id"]),
            adapter_id=str(payload["adapter_id"]),
            mode=mode,
            source_label=str(payload["source_label"]),
            evidence_timestamp=str(payload.get("evidence_timestamp") or "fixture-time"),
            market_class=str(payload["market_class"]),
            metric=str(payload["metric"]),
            value=payload.get("value"),
            provenance=str(payload["provenance"]),
            settlement_compatible=bool(payload.get("settlement_compatible", False)),
            blocker=payload.get("blocker"),
        )

    def mode_guard(self, fixture: AdapterFixtureRecordV1) -> dict[str, Any]:
        return {
            "fixture_id": fixture.fixture_id,
            "mode": fixture.mode.value,
            "live_observation_allowed": fixture.mode == FixtureMode.LIVE_PUBLIC_PROBE_RESULT and fixture.blocker is None,
            "live_score_allowed": fixture.mode == FixtureMode.LIVE_PUBLIC_PROBE_RESULT and fixture.blocker is None and fixture.settlement_compatible,
            "fixture_responses_claimed_live": False,
            "stale_cached_responses_scored_live": False,
        }


class AdapterRuntimeGuardV1:
    forbidden_methods = {
        "submit_order",
        "create_order",
        "cancel_order",
        "cancel_all",
        "get_balance",
        "get_positions",
        "modify_caps",
        "enable_live_submit",
        "browser_fetch",
    }

    def assert_safe(self) -> dict[str, Any]:
        return {
            "execution_methods_present": False,
            "order_cancel_account_balance_methods_present": False,
            "caps_live_submit_mutation_present": False,
            "browser_automation_present": False,
            "network_allowed_in_unit_tests": False,
            "integration_enabled": integration_mode_enabled(),
        }


class InHouseAdapterBaseInterfaceV1:
    adapter_id = "base"
    source_name = "base"
    evidence_role = "PUBLIC_READONLY_OBSERVATION"
    settlement_role = "REFERENCE_SETTLEMENT"
    supported_metrics: set[str] = set()
    supported_market_classes: set[str] = set()
    fixture_loader = AdapterFixtureLoaderV1()

    def fetch(self, request: AdapterRequestV1) -> AdapterResponseV1:
        guard = AdapterRuntimeGuardV1().assert_safe()
        if guard["execution_methods_present"]:
            raise RuntimeError("ADAPTER_RUNTIME_GUARD_FAILED")
        try:
            fixture = self.fixture_loader.load(request.fixture_id)
        except ValueError:
            return self._blocked_response(request, "SOURCE_UNAVAILABLE")
        if request.metric not in self.supported_metrics:
            return self._blocked_response(request, "METRIC_INCOMPATIBLE", fixture=fixture)
        if request.market_class not in self.supported_market_classes:
            return self._blocked_response(request, "MARKET_CLASS_INCOMPATIBLE", fixture=fixture)
        return self._response_from_fixture(request, fixture)

    def _blocked_response(
        self,
        request: AdapterRequestV1,
        blocker: str,
        *,
        fixture: AdapterFixtureRecordV1 | None = None,
    ) -> AdapterResponseV1:
        source_ref = AdapterSourceRefV1(
            source_name=self.source_name,
            source_mode=request.mode.value,
            source_url_class="NO_NETWORK_FIXTURE",
        )
        return AdapterResponseV1(
            adapter_id=self.adapter_id,
            source_name=self.source_name,
            source_mode=request.mode.value,
            retrieval_timestamp=now_iso(),
            evidence_timestamp=fixture.evidence_timestamp if fixture else None,
            market_class=request.market_class,
            evidence_role=self.evidence_role,
            settlement_role=self.settlement_role,
            metric=request.metric,
            value=None,
            freshness_status="INVALID",
            provenance=fixture.provenance if fixture else "no fixture found",
            confidence=0.0,
            source_ref=source_ref,
            blocker=blocker,
            error=AdapterErrorV1(blocker, blocker, retryable=blocker == "SOURCE_UNAVAILABLE"),
            settlement_compatible=False,
        )

    def _response_from_fixture(self, request: AdapterRequestV1, fixture: AdapterFixtureRecordV1) -> AdapterResponseV1:
        source_ref = AdapterSourceRefV1(
            source_name=self.source_name,
            source_mode=fixture.mode.value,
            source_url_class=fixture.source_url_class,
            venue=fixture.venue,
        )
        return AdapterResponseV1(
            adapter_id=self.adapter_id,
            source_name=self.source_name,
            source_mode=fixture.mode.value,
            retrieval_timestamp=now_iso(),
            evidence_timestamp=fixture.evidence_timestamp,
            market_class=request.market_class,
            evidence_role=self.evidence_role,
            settlement_role=self.settlement_role,
            metric=request.metric,
            value=fixture.value,
            freshness_status=fixture.freshness_status,
            provenance=fixture.provenance,
            confidence=fixture.confidence,
            source_ref=source_ref,
            blocker=fixture.blocker,
            settlement_compatible=fixture.settlement_compatible,
        )


class WeatherPublicObservationAdapterV1(InHouseAdapterBaseInterfaceV1):
    adapter_id = "weather_public_observation_v1"
    source_name = "weather_public_observation_v1"
    settlement_role = "WEATHER_THRESHOLD_SETTLEMENT"
    supported_metrics = {"temperature_f", "precipitation_in", "wind_speed_mph"}
    supported_market_classes = {"WEATHER_THRESHOLD", "WEATHER_EVENT"}

    def fetch(self, request: AdapterRequestV1) -> AdapterResponseV1:
        if request.fixture_id == "weather_kc_temperature_fixture" and request.metric != "temperature_f":
            return self._blocked_response(request, "METRIC_INCOMPATIBLE", fixture=self.fixture_loader.load(request.fixture_id))
        return super().fetch(request)


class CryptoPublicPriceAdapterV1(InHouseAdapterBaseInterfaceV1):
    adapter_id = "crypto_public_price_v1"
    source_name = "crypto_public_price_v1"
    settlement_role = "CRYPTO_PRICE_SETTLEMENT"
    supported_metrics = {"btc_usd", "eth_usd"}
    supported_market_classes = {"CRYPTO_PRICE_THRESHOLD", "CRYPTO_PRICE_RANGE", "CRYPTO_VOLATILITY"}

    def _response_from_fixture(self, request: AdapterRequestV1, fixture: AdapterFixtureRecordV1) -> AdapterResponseV1:
        response = super()._response_from_fixture(request, fixture)
        return replace(response, consensus_status="SINGLE_SOURCE_REFERENCE")


class PublicEventReferenceAdapterV1(InHouseAdapterBaseInterfaceV1):
    adapter_id = "public_event_reference_v1"
    source_name = "public_event_reference_v1"
    settlement_role = "PUBLIC_EVENT_REFERENCE_SETTLEMENT"
    supported_metrics = {"cpi_yoy", "reference_value", "commodity_reference"}
    supported_market_classes = {"FINANCE_MACRO_RELEASE", "MACRO_POLICY_EVENT", "PUBLIC_EVENT_BINARY", "COMMODITY_REFERENCE_EVENT"}


class KalshiReadonlyRuleAdapterV1(InHouseAdapterBaseInterfaceV1):
    adapter_id = "kalshi_readonly_rule_v1"
    source_name = "kalshi_readonly_rule_v1"
    evidence_role = "READ_ONLY_RULE_MAPPING"
    settlement_role = "KALSHI_READ_ONLY_RULE_MAPPING"
    supported_metrics = {"settlement_rule_text"}
    supported_market_classes = {"KALSHI_MAPPED_MARKET", "PUBLIC_EVENT_BINARY"}


class AdapterNormalizationPipelineV1:
    def normalize(self, response: AdapterResponseV1) -> AdapterEvidencePacketV1:
        return response.to_evidence_packet()

    def normalize_many(self, responses: list[AdapterResponseV1]) -> list[AdapterEvidencePacketV1]:
        return [self.normalize(response) for response in responses]


@dataclass(frozen=True)
class AdapterSettlementJoinDecisionV1:
    adapter_id: str
    market_class: str
    metric: str
    decision: str
    confidence: float
    live_score_allowed: bool
    blocker: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AdapterToSettlementCompatibilityV1:
    def join(self, packet: AdapterEvidencePacketV1, rule: dict[str, Any]) -> AdapterSettlementJoinDecisionV1:
        if packet.market_class != rule.get("market_class"):
            return AdapterSettlementJoinDecisionV1(
                packet.adapter_id,
                str(rule.get("market_class")),
                str(rule.get("metric")),
                "INCOMPATIBLE_MARKET_CLASS",
                0.0,
                False,
                "MARKET_CLASS_INCOMPATIBLE",
            )
        if packet.metric != rule.get("metric"):
            return AdapterSettlementJoinDecisionV1(
                packet.adapter_id,
                packet.market_class,
                str(rule.get("metric")),
                "INCOMPATIBLE_METRIC",
                0.0,
                False,
                "METRIC_INCOMPATIBLE",
            )
        if packet.blocker == "SETTLEMENT_AMBIGUOUS":
            return AdapterSettlementJoinDecisionV1(
                packet.adapter_id,
                packet.market_class,
                packet.metric,
                "SETTLEMENT_AMBIGUOUS",
                packet.confidence,
                False,
                "SETTLEMENT_AMBIGUOUS",
            )
        return AdapterSettlementJoinDecisionV1(
            packet.adapter_id,
            packet.market_class,
            packet.metric,
            "COMPATIBLE_PIPELINE_ONLY",
            packet.confidence,
            False,
            None,
        )

    def join_many(self, packets: list[AdapterEvidencePacketV1]) -> list[AdapterSettlementJoinDecisionV1]:
        rules = {
            "WEATHER_THRESHOLD": {"market_class": "WEATHER_THRESHOLD", "metric": "temperature_f"},
            "CRYPTO_PRICE_THRESHOLD": {"market_class": "CRYPTO_PRICE_THRESHOLD", "metric": "btc_usd"},
            "FINANCE_MACRO_RELEASE": {"market_class": "FINANCE_MACRO_RELEASE", "metric": "cpi_yoy"},
            "KALSHI_MAPPED_MARKET": {"market_class": "KALSHI_MAPPED_MARKET", "metric": "settlement_rule_text"},
        }
        return [self.join(packet, rules.get(packet.market_class, {"market_class": packet.market_class, "metric": packet.metric})) for packet in packets]


def integration_mode_enabled() -> bool:
    return (
        os.environ.get("DUMMY_PUBLIC_INTEGRATION_MODE") == "1"
        and os.environ.get("DUMMY_PUBLIC_INTEGRATION_CONFIRM") == "READ_ONLY_PUBLIC_PROBES"
    )


def default_requests() -> list[AdapterRequestV1]:
    return [
        AdapterRequestV1("weather_public_observation_v1", "WEATHER_THRESHOLD", "temperature_f", {"station": "KCMO"}, "weather_kc_temperature_fixture", FixtureMode.REPLAY_FIXTURE),
        AdapterRequestV1("crypto_public_price_v1", "CRYPTO_PRICE_THRESHOLD", "btc_usd", {"symbol": "BTC/USD"}, "crypto_btc_usd_fixture", FixtureMode.PUBLIC_SAMPLE_RESPONSE),
        AdapterRequestV1("public_event_reference_v1", "FINANCE_MACRO_RELEASE", "cpi_yoy", {"release": "CPI"}, "macro_cpi_reference_fixture", FixtureMode.CACHED_PUBLIC_RESPONSE),
        AdapterRequestV1("kalshi_readonly_rule_v1", "KALSHI_MAPPED_MARKET", "settlement_rule_text", {"ticker": "KXDEMO-RULE"}, "kalshi_ambiguous_rule_fixture", FixtureMode.REPLAY_FIXTURE),
    ]


def implemented_adapters() -> list[InHouseAdapterBaseInterfaceV1]:
    return [
        WeatherPublicObservationAdapterV1(),
        CryptoPublicPriceAdapterV1(),
        PublicEventReferenceAdapterV1(),
        KalshiReadonlyRuleAdapterV1(),
    ]


def build_default_v30_context() -> dict[str, Any]:
    adapters_by_id = {adapter.adapter_id: adapter for adapter in implemented_adapters()}
    responses = [adapters_by_id[request.adapter_id].fetch(request) for request in default_requests()]
    packets = AdapterNormalizationPipelineV1().normalize_many(responses)
    joins = AdapterToSettlementCompatibilityV1().join_many(packets)
    return {
        "requests": default_requests(),
        "responses": responses,
        "packets": packets,
        "settlement_joins": joins,
        "fixture_records": list(FIXTURE_RECORDS.values()),
    }


class AdapterObservationClosureDryRunV1:
    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        packets: list[AdapterEvidencePacketV1] = context["packets"]
        score_eligible = [packet for packet in packets if packet.live_score_eligible]
        return {
            "observation_closure_dry_run_status": "PASS_PIPELINE_ONLY",
            "dry_run_observed_count": len(packets),
            "dry_run_score_eligible_count": len(score_eligible),
            "live_scored_count": 0,
            "live_unresolved_count": 3,
            "observed_forecast_count": 0,
            "unresolved_forecast_scored": False,
            "ambiguous_settlement_scored": False,
            "source_unavailable_forecast_scored": False,
            "not_due_forecast_scored": False,
            "outcome_fabricated": False,
            "adapter_fixture_scored_live": False,
            "adapter_dry_run_scored_live": False,
        }


class PublicProbeImplementationReadinessV3:
    def plan(self, context: dict[str, Any]) -> dict[str, Any]:
        candidates = []
        for response in context["responses"]:
            ready_domain = response.adapter_id in {
                "weather_public_observation_v1",
                "crypto_public_price_v1",
                "public_event_reference_v1",
            }
            candidates.append(
                {
                    "adapter_id": response.adapter_id,
                    "source_url_class": "PUBLIC_KEYLESS_OPEN_DATA" if ready_domain else "READ_ONLY_RULE_MAPPING",
                    "method": "GET",
                    "expected_response_shape": ["source_name", "metric", "value", "evidence_timestamp", "provenance"],
                    "timeout_seconds": 6 if response.adapter_id != "crypto_public_price_v1" else 4,
                    "cache_policy": "cache with provenance, never score stale cache",
                    "freshness": "fresh timestamp required for future live public eligibility",
                    "settlement_usefulness": response.settlement_role,
                    "failure_behavior": "return SOURCE_UNAVAILABLE or TERMS_BLOCKED without scoring",
                    "readiness_verdict": "READY_DISABLED_BY_DEFAULT" if ready_domain else "RULE_MAPPING_READY_FIXTURE_ONLY",
                    "requires_secret": False,
                    "integration_enabled_by_default": False,
                    "live_execution_enabled": False,
                }
            )
        return {
            "public_probe_readiness_status": "PASS_DISABLED_BY_DEFAULT",
            "integration_mode_status": "ENABLED_READONLY_PUBLIC_PROBES" if integration_mode_enabled() else "DISABLED_BY_DEFAULT",
            "public_probe_run_count": 0,
            "public_probe_ready_count": sum(1 for item in candidates if item["readiness_verdict"] == "READY_DISABLED_BY_DEFAULT"),
            "candidates": candidates,
        }
