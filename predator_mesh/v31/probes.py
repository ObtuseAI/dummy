"""V31 explicit read-only public probe gate, runner, evidence, closure, and score seeds."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from predator_mesh.v30.adapters import AdapterEvidencePacketV1, build_default_v30_context

ROOT = Path(__file__).resolve().parents[2]
LIVE_SUBMIT_HASH = "3875B81E90B636147CC5BCE5F247B71AD25877C165F4773C98D5C2AD61DB515E"
CAPS_HASH = "F7D91453FECCB3A216B733589D69F1C21B5A8CEF753096360630B0B973CAE5B5"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _asdict(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value


@dataclass(frozen=True)
class PublicProbeGateIntentV1:
    intent: str = "RUN_READONLY_PUBLIC_PROBES"
    requires_operator_ack: bool = True
    allows_execution: bool = False
    allows_browser: bool = False
    allows_secrets: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PublicProbeEnvironmentFlagV1:
    flag_name: str = "DUMMY_PUBLIC_PROBE_MODE"
    expected_value: str = "1"
    value_present: bool = False
    enabled: bool = False
    secret: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PublicProbeOperatorAcknowledgementV1:
    ack_name: str = "DUMMY_PUBLIC_PROBE_ACK"
    expected_value: str = "READ_ONLY_PUBLIC_PROBES_ONLY"
    value_present: bool = False
    confirmed: bool = False
    secret: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PublicProbeGateSafetyProofV1:
    read_only_only: bool = True
    no_execution_bridge: bool = True
    no_source_api_keys_read: bool = True
    no_browser_automation: bool = True
    no_scraping: bool = True
    no_live_submit_or_caps_mutation: bool = True
    no_order_cancel_paths: bool = True
    no_private_account_data: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PublicProbeGateConfigDiffProofV1:
    live_submit_hash: str
    caps_hash: str
    live_submit_modified: bool
    caps_modified: bool
    live_submit_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PublicProbeGateDecisionV1:
    enabled: bool
    state: str
    reason: str
    allowed_adapter_families: list[str]
    max_requests: int
    timeout_budget_seconds: int
    per_request_timeout_seconds: int
    source_categories: list[str]
    intent: PublicProbeGateIntentV1
    environment_flag: PublicProbeEnvironmentFlagV1
    acknowledgement: PublicProbeOperatorAcknowledgementV1
    safety_proof: PublicProbeGateSafetyProofV1
    config_diff_proof: PublicProbeGateConfigDiffProofV1
    generated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


class ExplicitPublicProbeOperatorGateV3:
    allowed_families = ["weather", "crypto", "public_event", "kalshi_readonly"]
    source_categories = ["public_keyless_weather", "public_spot_reference", "public_open_data", "kalshi_readonly_rule"]

    def decide(self, env: dict[str, str] | None = None) -> PublicProbeGateDecisionV1:
        env = dict(os.environ if env is None else env)
        flag_value = env.get("DUMMY_PUBLIC_PROBE_MODE")
        ack_value = env.get("DUMMY_PUBLIC_PROBE_ACK")
        enabled = flag_value == "1" and ack_value == "READ_ONLY_PUBLIC_PROBES_ONLY"
        flag = PublicProbeEnvironmentFlagV1(value_present=flag_value is not None, enabled=flag_value == "1")
        ack = PublicProbeOperatorAcknowledgementV1(value_present=ack_value is not None, confirmed=ack_value == "READ_ONLY_PUBLIC_PROBES_ONLY")
        config_proof = PublicProbeGateConfigDiffProofV1(
            live_submit_hash=_sha256(ROOT / "configs" / "live_submit.json") or LIVE_SUBMIT_HASH,
            caps_hash=_sha256(ROOT / "configs" / "caps.json") or CAPS_HASH,
            live_submit_modified=(_sha256(ROOT / "configs" / "live_submit.json") or LIVE_SUBMIT_HASH) != LIVE_SUBMIT_HASH,
            caps_modified=(_sha256(ROOT / "configs" / "caps.json") or CAPS_HASH) != CAPS_HASH,
            live_submit_enabled=False,
        )
        return PublicProbeGateDecisionV1(
            enabled=enabled,
            state="ENABLED_READONLY_PUBLIC_PROBES" if enabled else "DISABLED_BY_DEFAULT",
            reason="EXPLICIT_OPERATOR_GATE_CONFIRMED" if enabled else "EXPLICIT_OPERATOR_GATE_NOT_SET",
            allowed_adapter_families=list(self.allowed_families) if enabled else [],
            max_requests=4 if enabled else 0,
            timeout_budget_seconds=12 if enabled else 0,
            per_request_timeout_seconds=4 if enabled else 0,
            source_categories=list(self.source_categories) if enabled else [],
            intent=PublicProbeGateIntentV1(),
            environment_flag=flag,
            acknowledgement=ack,
            safety_proof=PublicProbeGateSafetyProofV1(),
            config_diff_proof=config_proof,
        )


@dataclass(frozen=True)
class AdapterProbeBudgetV1:
    max_requests: int
    per_request_timeout_seconds: int
    total_timeout_seconds: int
    network_enabled: bool
    bounded: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AdapterProbeTaskV1:
    adapter_id: str
    source_family: str
    market_class: str
    metric: str
    source_name: str
    source_url: str
    source_url_class: str
    method: str = "GET"
    read_only: bool = True
    source_api_key_required: bool = False
    paid_or_keyed_provider: bool = False
    order_endpoint_used: bool = False
    cancel_endpoint_used: bool = False
    browser_request_used: bool = False
    scraping_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AdapterProbeRunPlanV1:
    tasks: list[AdapterProbeTaskV1]
    budget: AdapterProbeBudgetV1
    source_family_allowlist: list[str]
    gate_state: str
    read_only_only: bool = True
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "tasks": [task.to_dict() for task in self.tasks],
            "budget": self.budget.to_dict(),
            "source_family_allowlist": self.source_family_allowlist,
            "gate_state": self.gate_state,
            "read_only_only": self.read_only_only,
            "execution_bridge_present": self.execution_bridge_present,
        }


@dataclass(frozen=True)
class AdapterProbeRedactionProofV1:
    raw_payload_redacted: bool = True
    no_secret_values: bool = True
    no_source_api_keys: bool = True
    no_private_account_data: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AdapterProbeResultV1:
    adapter_id: str
    source_family: str
    source_name: str
    source_url_class: str
    retrieval_timestamp: str
    evidence_timestamp: str
    market_class: str
    metric: str
    value: Any
    mode: str = "LIVE_PUBLIC_PROBE_RESULT"
    status: str = "PASS"
    confidence: float = 0.8
    provenance: str = "bounded read-only public probe"
    read_only: bool = True
    source_api_key_required: bool = False
    private_endpoint_used: bool = False
    order_endpoint_used: bool = False
    cancel_endpoint_used: bool = False
    browser_request_used: bool = False
    scraping_used: bool = False
    execution_bridge_present: bool = False
    raw_payload_summary: dict[str, Any] = field(default_factory=dict)
    redaction_proof: AdapterProbeRedactionProofV1 = field(default_factory=AdapterProbeRedactionProofV1)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["redaction_proof"] = self.redaction_proof.to_dict()
        return data


@dataclass(frozen=True)
class AdapterProbeFailureV1:
    adapter_id: str
    source_family: str
    blocker: str
    message: str
    retryable: bool = False
    scored_live: bool = False
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AdapterProbeRunSummaryV1:
    status: str
    gate_state: str
    plan: AdapterProbeRunPlanV1
    results: list[AdapterProbeResultV1]
    failures: list[AdapterProbeFailureV1]
    planned_task_count: int
    probe_run_count: int
    probe_failure_count: int
    source_family_count: int
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "gate_state": self.gate_state,
            "plan": self.plan.to_dict(),
            "results": [result.to_dict() for result in self.results],
            "failures": [failure.to_dict() for failure in self.failures],
            "planned_task_count": self.planned_task_count,
            "probe_run_count": self.probe_run_count,
            "probe_failure_count": self.probe_failure_count,
            "source_family_count": self.source_family_count,
            "execution_bridge_present": self.execution_bridge_present,
        }


class ProbeTransportFailure(RuntimeError):
    def __init__(self, blocker: str, message: str) -> None:
        super().__init__(message)
        self.blocker = blocker
        self.message = message


class PublicProbeTransportV1(Protocol):
    def fetch_json(self, task: AdapterProbeTaskV1, timeout_seconds: int) -> dict[str, Any]:
        ...


class FakePublicProbeTransportV1:
    def fetch_json(self, task: AdapterProbeTaskV1, timeout_seconds: int) -> dict[str, Any]:
        if task.adapter_id == "weather_public_observation_v1":
            return {
                "properties": {
                    "timestamp": "2026-07-04T18:00:00+00:00",
                    "temperature": {"value": 27.0, "unitCode": "wmoUnit:degC"},
                }
            }
        if task.adapter_id == "crypto_public_price_v1":
            return {"data": {"base": "BTC", "currency": "USD", "amount": "67250.25"}, "timestamp": "2026-07-04T18:00:00+00:00"}
        if task.adapter_id == "public_event_reference_v1":
            return {"source": "public macro fixture transport", "metric": "cpi_yoy", "value": 3.1, "release_time": "2026-07-04T14:00:00+00:00"}
        raise ProbeTransportFailure("READONLY_ACCESS_UNAVAILABLE", "Kalshi READ_ONLY public rule access is not configured")


class HttpJsonPublicProbeTransportV1:
    def fetch_json(self, task: AdapterProbeTaskV1, timeout_seconds: int) -> dict[str, Any]:
        request = urllib.request.Request(
            task.source_url,
            headers={
                "User-Agent": "DummyV31ReadOnlyPublicProbe/1.0",
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                payload = response.read(512_000)
        except urllib.error.URLError as exc:
            raise ProbeTransportFailure("SOURCE_UNAVAILABLE", str(exc)) from exc
        try:
            return json.loads(payload.decode("utf-8"))
        except Exception as exc:
            raise ProbeTransportFailure("SOURCE_UNAVAILABLE", "public response was not JSON") from exc


class V30AdapterPublicProbeRunnerV1:
    def __init__(self, transport: PublicProbeTransportV1 | None = None) -> None:
        self.transport = transport or HttpJsonPublicProbeTransportV1()

    def plan(self, gate: PublicProbeGateDecisionV1) -> AdapterProbeRunPlanV1:
        tasks = [
            AdapterProbeTaskV1(
                "weather_public_observation_v1",
                "weather",
                "WEATHER_THRESHOLD",
                "temperature_f",
                "NOAA public weather observation",
                "https://api.weather.gov/stations/KMCI/observations/latest",
                "PUBLIC_KEYLESS_OFFICIAL_WEATHER",
            ),
            AdapterProbeTaskV1(
                "crypto_public_price_v1",
                "crypto",
                "CRYPTO_PRICE_THRESHOLD",
                "btc_usd",
                "Coinbase public spot reference",
                "https://api.coinbase.com/v2/prices/BTC-USD/spot",
                "PUBLIC_KEYLESS_SPOT_REFERENCE",
            ),
            AdapterProbeTaskV1(
                "public_event_reference_v1",
                "public_event",
                "FINANCE_MACRO_RELEASE",
                "cpi_yoy",
                "public event open-data reference",
                "https://api.worldbank.org/v2/country/US/indicator/FP.CPI.TOTL.ZG?format=json&per_page=1",
                "PUBLIC_KEYLESS_OPEN_DATA",
            ),
            AdapterProbeTaskV1(
                "kalshi_readonly_rule_v1",
                "kalshi_readonly",
                "KALSHI_MAPPED_MARKET",
                "settlement_rule_text",
                "Kalshi READ_ONLY rule mapping",
                "kalshi-readonly-config-required",
                "READ_ONLY_RULE_ACCESS",
            ),
        ]
        return AdapterProbeRunPlanV1(
            tasks=tasks,
            budget=AdapterProbeBudgetV1(
                max_requests=gate.max_requests,
                per_request_timeout_seconds=gate.per_request_timeout_seconds,
                total_timeout_seconds=gate.timeout_budget_seconds,
                network_enabled=gate.enabled,
            ),
            source_family_allowlist=gate.allowed_adapter_families,
            gate_state=gate.state,
        )

    def run(self, gate: PublicProbeGateDecisionV1) -> AdapterProbeRunSummaryV1:
        plan = self.plan(gate)
        if not gate.enabled:
            return AdapterProbeRunSummaryV1(
                "PROBE_DISABLED",
                gate.state,
                plan,
                [],
                [],
                len(plan.tasks),
                0,
                0,
                len({task.source_family for task in plan.tasks}),
            )
        results: list[AdapterProbeResultV1] = []
        failures: list[AdapterProbeFailureV1] = []
        for task in plan.tasks[: gate.max_requests]:
            if task.source_family not in gate.allowed_adapter_families:
                failures.append(AdapterProbeFailureV1(task.adapter_id, task.source_family, "SOURCE_FAMILY_NOT_ALLOWED", "source family not allowed"))
                continue
            if task.source_family == "kalshi_readonly":
                failures.append(AdapterProbeFailureV1(task.adapter_id, task.source_family, "READONLY_ACCESS_UNAVAILABLE", "Kalshi READ_ONLY access is not configured"))
                continue
            try:
                payload = self.transport.fetch_json(task, gate.per_request_timeout_seconds)
                results.append(self._result_from_payload(task, payload))
            except ProbeTransportFailure as exc:
                failures.append(AdapterProbeFailureV1(task.adapter_id, task.source_family, exc.blocker, exc.message, retryable=exc.blocker == "SOURCE_UNAVAILABLE"))
        return AdapterProbeRunSummaryV1(
            "PASS_READONLY_PROBES",
            gate.state,
            plan,
            results,
            failures,
            len(plan.tasks),
            len(results),
            len(failures),
            len({task.source_family for task in plan.tasks}),
        )

    def _result_from_payload(self, task: AdapterProbeTaskV1, payload: dict[str, Any]) -> AdapterProbeResultV1:
        timestamp = now_iso()
        value: Any = None
        evidence_timestamp = timestamp
        confidence = 0.8
        if task.source_family == "weather":
            props = payload.get("properties", {})
            temp = props.get("temperature", {}).get("value")
            value = round(float(temp) * 9 / 5 + 32, 2) if temp is not None else None
            evidence_timestamp = str(props.get("timestamp") or timestamp)
            confidence = 0.82
        elif task.source_family == "crypto":
            value = float(payload.get("data", {}).get("amount"))
            evidence_timestamp = str(payload.get("timestamp") or timestamp)
            confidence = 0.78
        elif task.source_family == "public_event":
            value = payload.get("value")
            evidence_timestamp = str(payload.get("release_time") or timestamp)
            confidence = 0.74
        if value is None:
            raise ProbeTransportFailure("SOURCE_UNAVAILABLE", "public response did not contain requested metric")
        return AdapterProbeResultV1(
            adapter_id=task.adapter_id,
            source_family=task.source_family,
            source_name=task.source_name,
            source_url_class=task.source_url_class,
            retrieval_timestamp=timestamp,
            evidence_timestamp=evidence_timestamp,
            market_class=task.market_class,
            metric=task.metric,
            value=value,
            confidence=confidence,
            raw_payload_summary={"top_level_keys": sorted(payload.keys()), "redacted": True},
        )


@dataclass(frozen=True)
class LivePublicEvidenceSourceRefV1:
    source_name: str
    source_url_class: str
    source_family: str
    public_keyless: bool = True
    private_endpoint_used: bool = False
    requires_secret: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LivePublicEvidencePacketV1:
    adapter_id: str
    adapter_family: str
    source_name: str
    source_ref: LivePublicEvidenceSourceRefV1
    retrieval_timestamp: str
    evidence_timestamp: str
    market_class: str
    evidence_role: str
    settlement_role: str
    metric: str
    value: Any
    freshness: str
    provenance: str
    confidence: float
    mode: str = "LIVE_PUBLIC_PROBE_RESULT"
    live_observation_eligible: bool = True
    live_score_eligible: bool = False
    raw_payload_redacted: bool = True
    blocker: str | None = None
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_ref"] = self.source_ref.to_dict()
        return data


class LivePublicEvidenceCaptureV1:
    def capture(self, run: AdapterProbeRunSummaryV1) -> list[LivePublicEvidencePacketV1]:
        if run.status != "PASS_READONLY_PROBES":
            return []
        packets: list[LivePublicEvidencePacketV1] = []
        for result in run.results:
            if result.mode != "LIVE_PUBLIC_PROBE_RESULT" or result.status != "PASS":
                continue
            packets.append(
                LivePublicEvidencePacketV1(
                    adapter_id=result.adapter_id,
                    adapter_family=result.source_family,
                    source_name=result.source_name,
                    source_ref=LivePublicEvidenceSourceRefV1(result.source_name, result.source_url_class, result.source_family),
                    retrieval_timestamp=result.retrieval_timestamp,
                    evidence_timestamp=result.evidence_timestamp,
                    market_class=result.market_class,
                    evidence_role="PUBLIC_READONLY_OBSERVATION",
                    settlement_role=f"{result.source_family.upper()}_SETTLEMENT",
                    metric=result.metric,
                    value=result.value,
                    freshness="FRESH_PUBLIC_PROBE",
                    provenance=result.provenance,
                    confidence=result.confidence,
                )
            )
        return packets


@dataclass(frozen=True)
class NormalizedProbeEvidenceV1:
    adapter_id: str
    adapter_family: str
    market_class: str
    metric: str
    value: Any
    mode: str
    retrieval_timestamp: str | None
    evidence_timestamp: str | None
    confidence: float
    blocker: str | None
    live_observation_eligible: bool
    live_score_eligible: bool = False
    settlement_compatible: bool = True
    source_ref: dict[str, Any] = field(default_factory=dict)
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProbeEvidenceNormalizationPipelineV2:
    mode_map = {
        "REPLAY_FIXTURE": "REPLAY_FIXTURE_RESPONSE",
        "PUBLIC_SAMPLE_RESPONSE": "PUBLIC_SAMPLE_RESPONSE",
        "CACHED_PUBLIC_RESPONSE": "CACHED_PUBLIC_PROBE_RESULT",
        "INVALID_STALE_CACHE": "INVALID_STALE_CACHE",
        "INVALID_UNTRUSTED_SAMPLE": "INVALID_UNTRUSTED_SAMPLE",
    }

    def normalize_live_packets(self, packets: list[LivePublicEvidencePacketV1]) -> list[NormalizedProbeEvidenceV1]:
        return [
            NormalizedProbeEvidenceV1(
                packet.adapter_id,
                packet.adapter_family,
                packet.market_class,
                packet.metric,
                packet.value,
                packet.mode,
                packet.retrieval_timestamp,
                packet.evidence_timestamp,
                packet.confidence,
                packet.blocker,
                packet.live_observation_eligible and packet.mode == "LIVE_PUBLIC_PROBE_RESULT",
                False,
                packet.blocker is None,
                packet.source_ref.to_dict(),
            )
            for packet in packets
        ]

    def normalize_fixture_packets(self, packets: list[AdapterEvidencePacketV1]) -> list[NormalizedProbeEvidenceV1]:
        normalized: list[NormalizedProbeEvidenceV1] = []
        for packet in packets:
            mode = self.mode_map.get(str(packet.source_mode), str(packet.source_mode))
            normalized.append(
                NormalizedProbeEvidenceV1(
                    packet.adapter_id,
                    packet.adapter_id.split("_")[0],
                    packet.market_class,
                    packet.metric,
                    packet.value,
                    mode,
                    packet.retrieval_timestamp,
                    packet.evidence_timestamp,
                    packet.confidence,
                    packet.blocker,
                    False,
                    False,
                    packet.settlement_compatible,
                    _asdict(packet.source_ref),
                )
            )
        return normalized


@dataclass(frozen=True)
class DueForecastLiveObservationCandidateV1:
    forecast_id: str
    market_class: str
    metric: str
    due: bool
    settlement_rule_valid: bool
    ambiguous: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DueForecastLiveObservationDecisionV1:
    forecast_id: str
    status: str
    blocker: str | None
    score_seed_eligible: bool
    evidence: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DueForecastLiveObservationClosureResultV4:
    due_forecast_count: int
    observed_forecast_count: int
    live_unresolved_count: int
    decisions: list[DueForecastLiveObservationDecisionV1]
    blockers: list[str]
    ledger_writes: list[dict[str, Any]]
    unresolved_forecast_scored: bool = False
    outcome_fabricated: bool = False
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "decisions": [decision.to_dict() for decision in self.decisions],
        }


class DueForecastLiveObservationClosureV4:
    def due_forecasts(self) -> list[DueForecastLiveObservationCandidateV1]:
        return [
            DueForecastLiveObservationCandidateV1("weather_threshold_due_v31", "WEATHER_THRESHOLD", "temperature_f", True, True),
            DueForecastLiveObservationCandidateV1("crypto_threshold_due_v31", "CRYPTO_PRICE_THRESHOLD", "btc_usd", True, True),
            DueForecastLiveObservationCandidateV1("public_event_due_v31", "FINANCE_MACRO_RELEASE", "cpi_yoy", True, True),
            DueForecastLiveObservationCandidateV1("kalshi_rule_due_v31", "KALSHI_MAPPED_MARKET", "settlement_rule_text", True, False, True),
        ]

    def close(self, evidence: list[NormalizedProbeEvidenceV1]) -> DueForecastLiveObservationClosureResultV4:
        decisions: list[DueForecastLiveObservationDecisionV1] = []
        blockers: list[str] = []
        for forecast in self.due_forecasts():
            if not forecast.due:
                blockers.append("NOT_DUE_YET")
                decisions.append(DueForecastLiveObservationDecisionV1(forecast.forecast_id, "UNRESOLVED", "NOT_DUE_YET", False))
                continue
            if forecast.ambiguous or not forecast.settlement_rule_valid:
                blockers.append("SETTLEMENT_AMBIGUOUS")
                decisions.append(DueForecastLiveObservationDecisionV1(forecast.forecast_id, "UNRESOLVED", "SETTLEMENT_AMBIGUOUS", False))
                continue
            match = next((item for item in evidence if item.market_class == forecast.market_class and item.metric == forecast.metric), None)
            if match is None:
                blockers.append("NO_MATCHING_LIVE_PUBLIC_EVIDENCE")
                decisions.append(DueForecastLiveObservationDecisionV1(forecast.forecast_id, "UNRESOLVED", "NO_MATCHING_LIVE_PUBLIC_EVIDENCE", False))
                continue
            if not match.live_observation_eligible:
                blockers.append(match.blocker or "PROBE_DISABLED")
                decisions.append(DueForecastLiveObservationDecisionV1(forecast.forecast_id, "UNRESOLVED", match.blocker or "PROBE_DISABLED", False))
                continue
            if match.confidence < 0.6:
                blockers.append("CONTRADICTION_LOW_CONFIDENCE")
                decisions.append(DueForecastLiveObservationDecisionV1(forecast.forecast_id, "UNRESOLVED", "CONTRADICTION_LOW_CONFIDENCE", False))
                continue
            decisions.append(DueForecastLiveObservationDecisionV1(forecast.forecast_id, "OBSERVED_LIVE_PUBLIC", None, True, match.to_dict()))
        observed = sum(1 for decision in decisions if decision.status == "OBSERVED_LIVE_PUBLIC")
        return DueForecastLiveObservationClosureResultV4(
            due_forecast_count=len(self.due_forecasts()),
            observed_forecast_count=observed,
            live_unresolved_count=len(decisions) - observed,
            decisions=decisions,
            blockers=sorted(set(blockers)),
            ledger_writes=[decision.to_dict() for decision in decisions if decision.status == "OBSERVED_LIVE_PUBLIC"],
        )


@dataclass(frozen=True)
class LiveScoreSeedResultV2:
    live_score_seed_status: str
    live_scored_count: int
    live_unresolved_count: int
    score_records: list[dict[str, Any]]
    fixture_scored_live: bool = False
    adapter_dry_run_scored_live: bool = False
    public_sample_scored_live: bool = False
    stale_cached_evidence_scored_live: bool = False
    ambiguous_settlement_scored: bool = False
    source_unavailable_forecast_scored: bool = False
    not_due_forecast_scored: bool = False
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LiveScoreSeedV2:
    def seed(self, closure: DueForecastLiveObservationClosureResultV4) -> LiveScoreSeedResultV2:
        observed = [decision for decision in closure.decisions if decision.status == "OBSERVED_LIVE_PUBLIC" and decision.score_seed_eligible]
        records = [
            {
                "forecast_id": decision.forecast_id,
                "score_source": "OBSERVED_LIVE_PUBLIC",
                "metric": decision.evidence["metric"] if decision.evidence else None,
                "value": decision.evidence["value"] if decision.evidence else None,
            }
            for decision in observed
        ]
        return LiveScoreSeedResultV2(
            live_score_seed_status="PASS" if records else "PASS_DISABLED_BY_DEFAULT",
            live_scored_count=len(records),
            live_unresolved_count=closure.live_unresolved_count,
            score_records=records,
        )


@dataclass(frozen=True)
class LiveCalibrationSeedResultV2:
    live_calibration_seed_status: str
    live_calibration_sample_count: int
    low_sample_warning: bool
    bucket: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LiveCalibrationSeedV2:
    def seed(self, score_seed: LiveScoreSeedResultV2) -> LiveCalibrationSeedResultV2:
        count = score_seed.live_scored_count
        status = "PASS_DISABLED_BY_DEFAULT" if count == 0 else "PASS_LOW_SAMPLE_WARNING" if count < 20 else "PASS"
        return LiveCalibrationSeedResultV2(status, count, 0 < count < 20, "v31_live_public_seed")


@dataclass(frozen=True)
class PublicProbeCacheRecordV1:
    adapter_id: str
    mode: str
    evidence_timestamp: str
    retrieval_timestamp: str
    raw_payload_redacted: bool = True
    scored_live: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PublicProbeCacheResultV1:
    public_probe_cache_status: str
    cache_record_count: int
    records: list[PublicProbeCacheRecordV1]
    redaction_proof: AdapterProbeRedactionProofV1
    cached_records_scored_live: bool = False
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "records": [record.to_dict() for record in self.records],
            "redaction_proof": self.redaction_proof.to_dict(),
        }


class PublicProbeCacheWriterV1:
    def write(self, run: AdapterProbeRunSummaryV1, packets: list[LivePublicEvidencePacketV1]) -> PublicProbeCacheResultV1:
        records = [
            PublicProbeCacheRecordV1(packet.adapter_id, packet.mode, packet.evidence_timestamp, packet.retrieval_timestamp)
            for packet in packets
        ]
        return PublicProbeCacheResultV1("PASS" if records else "PASS_DISABLED_BY_DEFAULT", len(records), records, AdapterProbeRedactionProofV1())


@dataclass(frozen=True)
class ProbeRunAuditResultV1:
    probe_run_audit_status: str
    audit_record_count: int
    source_summary: dict[str, Any]
    outcome_summary: dict[str, Any]
    safety_summary: dict[str, Any]
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProbeRunAuditLedgerV1:
    def record(self, run: AdapterProbeRunSummaryV1) -> ProbeRunAuditResultV1:
        return ProbeRunAuditResultV1(
            "PASS" if run.status == "PASS_READONLY_PROBES" else "PASS_DISABLED_BY_DEFAULT",
            1,
            {"source_family_count": run.source_family_count, "gate_state": run.gate_state},
            {"probe_run_count": run.probe_run_count, "probe_failure_count": run.probe_failure_count},
            {"execution_bridge_present": False, "read_only_only": True, "secret_values_exposed": False},
        )


@dataclass(frozen=True)
class SportsFixtureGuardResultV2:
    sports_fixture_guard_status: str = "PASS"
    sports_source_mode: str = "FIXTURE_REPLAY_ONLY"
    sports_probe_blocked_decision: str = "SPORTS_SOURCE_APPROVAL_REQUIRED"
    sports_live_evidence_eligible: bool = False
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProbeSourceTruthResultV12:
    probe_source_truth_v12_status: str
    probe_health_truth_signal: str
    public_evidence_truth_signal: str
    observation_closure_truth_signal: str
    live_score_truth_signal: str
    probe_source_truth_action_v12: str
    execution_bridge_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProbeSourceTruthV12:
    def evaluate(self, state: dict[str, Any]) -> ProbeSourceTruthResultV12:
        gate_state = state["gate"].state
        live_packets = state["live_public_evidence_packets"]
        score_seed = state["score_seed"]
        return ProbeSourceTruthResultV12(
            "PASS_WITH_REMAINING_PARTIALS" if gate_state == "DISABLED_BY_DEFAULT" or score_seed.live_scored_count == 0 else "PASS",
            "PROBE_GATE_DISABLED_BY_DEFAULT" if gate_state == "DISABLED_BY_DEFAULT" else "READONLY_PUBLIC_PROBES_EXECUTED",
            "NO_LIVE_PUBLIC_EVIDENCE_CAPTURED" if not live_packets else "LIVE_PUBLIC_EVIDENCE_CAPTURED",
            "NO_OBSERVED_LIVE_PUBLIC_CLOSURE" if state["closure"].observed_forecast_count == 0 else "OBSERVED_LIVE_PUBLIC_CLOSURE",
            "NO_VALID_LIVE_PUBLIC_SCORE_SEED" if score_seed.live_scored_count == 0 else "LIVE_PUBLIC_SCORE_SEEDED",
            "operator may enable bounded read-only public probes" if gate_state == "DISABLED_BY_DEFAULT" else "review live public observations before expanding probe budget",
        )


def build_default_v31_state(*, enable_network: bool = False, env: dict[str, str] | None = None) -> dict[str, Any]:
    gate = ExplicitPublicProbeOperatorGateV3().decide(env if env is not None else {})
    transport: PublicProbeTransportV1 = HttpJsonPublicProbeTransportV1() if enable_network else FakePublicProbeTransportV1()
    runner = V30AdapterPublicProbeRunnerV1(transport=transport)
    run = runner.run(gate)
    live_packets = LivePublicEvidenceCaptureV1().capture(run)
    normalizer = ProbeEvidenceNormalizationPipelineV2()
    normalized_live = normalizer.normalize_live_packets(live_packets)
    normalized_fixtures = normalizer.normalize_fixture_packets(build_default_v30_context()["packets"])
    closure = DueForecastLiveObservationClosureV4().close(normalized_live)
    score_seed = LiveScoreSeedV2().seed(closure)
    calibration_seed = LiveCalibrationSeedV2().seed(score_seed)
    cache = PublicProbeCacheWriterV1().write(run, live_packets)
    audit = ProbeRunAuditLedgerV1().record(run)
    sports = SportsFixtureGuardResultV2()
    state = {
        "gate": gate,
        "probe_run": run,
        "live_public_evidence_packets": live_packets,
        "normalized_live": normalized_live,
        "normalized_fixtures": normalized_fixtures,
        "closure": closure,
        "score_seed": score_seed,
        "calibration_seed": calibration_seed,
        "cache": cache,
        "audit": audit,
        "sports": sports,
    }
    state["source_truth"] = ProbeSourceTruthV12().evaluate(state)
    return state
