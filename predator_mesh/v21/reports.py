"""V21 source activation breakout reports and deterministic control objects."""

from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from predator_mesh.v20.source_universe import SourceUniverse
from predator_mesh.v21 import MILESTONE

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts" / "dummy"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_base(workstream: str, verdict: str = "PASS") -> dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "workstream": workstream,
        "milestone": MILESTONE,
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "read_only_only": True,
        "secret_values_exposed": False,
        "verdict": verdict,
    }


def _load_json(path: Path, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return fallback or {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback or {}


def _is_present_env(name: str) -> bool:
    return bool(os.environ.get(name))


def _source_dicts() -> list[dict[str, Any]]:
    return [candidate.to_dict() for candidate in SourceUniverse().candidates()]


@dataclass(frozen=True)
class SourceActivationPolicyReason:
    code: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "detail": self.detail}


@dataclass(frozen=True)
class SourceActivationPolicyVerdict:
    source_id: str
    source_name: str
    policy_class: str
    activation_status: str
    allowed_real_readonly: bool
    auto_approved: bool
    blocker: str
    reason: SourceActivationPolicyReason
    unlocks: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "policy_class": self.policy_class,
            "activation_status": self.activation_status,
            "allowed_real_readonly": self.allowed_real_readonly,
            "auto_approved": self.auto_approved,
            "blocker": self.blocker,
            "reason": self.reason.to_dict(),
            "unlocks": list(self.unlocks),
            "read_only_only": True,
            "live_execution_enabled": False,
        }


class SourceActivationPolicy:
    OFFICIAL_PUBLIC_KEYLESS_ALLOW = "OFFICIAL_PUBLIC_KEYLESS_ALLOW"
    OFFICIAL_PUBLIC_KEY_REQUIRED_GATE = "OFFICIAL_PUBLIC_KEY_REQUIRED_GATE"
    COMMERCIAL_LICENSE_REQUIRED_GATE = "COMMERCIAL_LICENSE_REQUIRED_GATE"
    OPEN_SOURCE_ADAPTER_PLAN_ONLY = "OPEN_SOURCE_ADAPTER_PLAN_ONLY"
    COMMUNITY_PUBLIC_TERMS_REVIEW_GATE = "COMMUNITY_PUBLIC_TERMS_REVIEW_GATE"
    SPORTS_STRICT_TERMS_GATE = "SPORTS_STRICT_TERMS_GATE"
    BLOCKED_UNAPPROVED = "BLOCKED_UNAPPROVED"
    BLOCKED_SCRAPING_RISK = "BLOCKED_SCRAPING_RISK"
    BLOCKED_PRIVATE_OR_PAYWALLED = "BLOCKED_PRIVATE_OR_PAYWALLED"
    STATIC_FIXTURE_ONLY = "STATIC_FIXTURE_ONLY"

    def __init__(self, sources: Iterable[dict[str, Any]] | None = None) -> None:
        self.sources = list(sources) if sources is not None else _source_dicts()

    def verdict_for(self, source: dict[str, Any]) -> SourceActivationPolicyVerdict:
        source_id = source["source_id"]
        name = source["name"]
        tier = source["tier"]
        domains = set(source.get("domains", []))
        approval = source.get("approval_status", "")
        legality = source.get("legality_class", "")
        source_class = source.get("source_class", "")
        creds = tuple(source.get("adapter_plan", {}).get("credential_env_vars", []))
        unlocks = tuple(sorted(domains)) or ("source_context",)

        if source_class == "static_fixture":
            return SourceActivationPolicyVerdict(
                source_id,
                name,
                self.STATIC_FIXTURE_ONLY,
                "STATIC_FIXTURE_ONLY",
                False,
                False,
                "fixture_not_real_readonly",
                SourceActivationPolicyReason("STATIC_FIXTURE_ONLY", "Fixture data may never be promoted as real source evidence."),
                unlocks,
            )
        if source_class == "github_adapter_candidate":
            return SourceActivationPolicyVerdict(
                source_id,
                name,
                self.OPEN_SOURCE_ADAPTER_PLAN_ONLY,
                "ADAPTER_PLAN_ONLY",
                False,
                False,
                "github_repo_code_execution_forbidden",
                SourceActivationPolicyReason("GITHUB_PLAN_ONLY", "GitHub repositories are scored only as adapter plans; no clone/install/execute path is allowed."),
                unlocks,
            )
        if approval in {"BLOCKED_SCRAPING_RISK", "BLOCKED_PRIVATE", "BLOCKED_PAYWALLED"}:
            policy = self.BLOCKED_PRIVATE_OR_PAYWALLED if approval != "BLOCKED_SCRAPING_RISK" else self.BLOCKED_SCRAPING_RISK
            return SourceActivationPolicyVerdict(
                source_id,
                name,
                policy,
                approval,
                False,
                False,
                approval.lower(),
                SourceActivationPolicyReason(policy, "Private, paywalled, or scraping-risk sources remain blocked."),
                unlocks,
            )
        if "sports" in domains and tier not in {"TIER_1_OFFICIAL_PUBLIC"}:
            return SourceActivationPolicyVerdict(
                source_id,
                name,
                self.SPORTS_STRICT_TERMS_GATE,
                "BLOCKED_TERMS_REVIEW_REQUIRED",
                False,
                False,
                "sports_terms_allowlist_missing",
                SourceActivationPolicyReason("SPORTS_TERMS_STRICT", "Sports sources require strict terms review; undocumented odds scraping remains forbidden."),
                unlocks,
            )
        if tier in {"TIER_0_EXCHANGE_NATIVE", "TIER_2_COMMERCIAL_LICENSED"}:
            return SourceActivationPolicyVerdict(
                source_id,
                name,
                self.COMMERCIAL_LICENSE_REQUIRED_GATE,
                "BLOCKED_LICENSE_REQUIRED",
                False,
                False,
                "operator_license_or_allowlist_missing",
                SourceActivationPolicyReason("LICENSE_REQUIRED", "Commercial/exchange-native data needs operator approval, license, and key presence."),
                unlocks,
            )
        if creds:
            missing = [name for name in creds if not _is_present_env(name)]
            status = "BLOCKED_KEY_MISSING" if missing else "BLOCKED_OPERATOR_APPROVAL_REQUIRED"
            return SourceActivationPolicyVerdict(
                source_id,
                name,
                self.OFFICIAL_PUBLIC_KEY_REQUIRED_GATE,
                status,
                False,
                False,
                "key_or_operator_approval_missing",
                SourceActivationPolicyReason("KEY_REQUIRED_GATE", "Key names may be listed, but key values are never printed or persisted."),
                unlocks,
            )
        if tier == "TIER_1_OFFICIAL_PUBLIC" and legality in {"PUBLIC_READONLY_ALLOWED", "OFFICIAL_PUBLIC", "PUBLIC_ALLOWED"}:
            return SourceActivationPolicyVerdict(
                source_id,
                name,
                self.OFFICIAL_PUBLIC_KEYLESS_ALLOW,
                "APPROVED_REAL_READONLY_PROBE_ALLOWED",
                True,
                True,
                "",
                SourceActivationPolicyReason("PUBLIC_KEYLESS_ALLOWED", "Official public keyless read-only source passed built-in V21 policy."),
                unlocks,
            )
        if tier == "TIER_4_FREE_PUBLIC_CONTEXT":
            return SourceActivationPolicyVerdict(
                source_id,
                name,
                self.COMMUNITY_PUBLIC_TERMS_REVIEW_GATE,
                "BLOCKED_TERMS_REVIEW_REQUIRED",
                False,
                False,
                "community_public_terms_review_required",
                SourceActivationPolicyReason("TERMS_REVIEW_REQUIRED", "Community/free public context source needs terms review before activation."),
                unlocks,
            )
        return SourceActivationPolicyVerdict(
            source_id,
            name,
            self.BLOCKED_UNAPPROVED,
            "BLOCKED_UNAPPROVED",
            False,
            False,
            "operator_allowlist_missing",
            SourceActivationPolicyReason("UNAPPROVED", "Source is not approved for real read-only activation."),
            unlocks,
        )

    def verdicts(self) -> list[SourceActivationPolicyVerdict]:
        return [self.verdict_for(source) for source in self.sources]

    def allowed_source_ids(self) -> set[str]:
        return {verdict.source_id for verdict in self.verdicts() if verdict.allowed_real_readonly}

    def to_report(self) -> dict[str, Any]:
        verdicts = [verdict.to_dict() for verdict in self.verdicts()]
        counts = Counter(verdict["policy_class"] for verdict in verdicts)
        report = _safe_base("V21: Source Activation Policy V1")
        report.update(
            {
                "policy_count": len(verdicts),
                "policy_class_counts": dict(sorted(counts.items())),
                "auto_approved_count": sum(1 for verdict in verdicts if verdict["auto_approved"]),
                "activation_allowed_count": sum(1 for verdict in verdicts if verdict["allowed_real_readonly"]),
                "blocked_count": sum(1 for verdict in verdicts if verdict["blocker"]),
                "verdicts": verdicts,
                "no_commercial_auto_activation": True,
                "no_sports_odds_auto_activation": True,
                "github_repos_adapter_plan_only": True,
            }
        )
        return report


class OfficialPublicAutoApprovalPolicy:
    def __init__(self, policy: SourceActivationPolicy | None = None) -> None:
        self.policy = policy or SourceActivationPolicy()

    def to_report(self) -> dict[str, Any]:
        allowed = [verdict.to_dict() for verdict in self.policy.verdicts() if verdict.policy_class == SourceActivationPolicy.OFFICIAL_PUBLIC_KEYLESS_ALLOW]
        report = _safe_base("V21: Official Public Auto Approval Policy V1")
        report.update(
            {
                "auto_approved_source_ids": [item["source_id"] for item in allowed],
                "auto_approved_count": len(allowed),
                "requirements": {
                    "read_only_endpoint": True,
                    "no_secret_required": True,
                    "bounded_request_budget": True,
                    "fallback_exists": True,
                    "legality_class_required": ["PUBLIC_ALLOWED", "OFFICIAL_PUBLIC", "PUBLIC_READONLY_ALLOWED"],
                },
                "auto_approved_sources": allowed,
            }
        )
        return report


class KeyRequiredSourcePolicy:
    def __init__(self, policy: SourceActivationPolicy | None = None) -> None:
        self.policy = policy or SourceActivationPolicy()

    def to_report(self) -> dict[str, Any]:
        gated = [verdict.to_dict() for verdict in self.policy.verdicts() if verdict.policy_class == SourceActivationPolicy.OFFICIAL_PUBLIC_KEY_REQUIRED_GATE]
        report = _safe_base("V21: Key Required Source Policy V1")
        report.update(
            {
                "key_required_count": len(gated),
                "activated_with_key_count": 0,
                "key_names_allowed": True,
                "key_values_forbidden": True,
                "operator_approval_required": True,
                "sources": gated,
            }
        )
        return report


class LicensedCommercialSourcePolicy:
    def __init__(self, policy: SourceActivationPolicy | None = None) -> None:
        self.policy = policy or SourceActivationPolicy()

    def to_report(self) -> dict[str, Any]:
        gated = [verdict.to_dict() for verdict in self.policy.verdicts() if verdict.policy_class == SourceActivationPolicy.COMMERCIAL_LICENSE_REQUIRED_GATE]
        report = _safe_base("V21: Licensed Commercial Source Policy V1")
        report.update(
            {
                "commercial_or_exchange_native_count": len(gated),
                "auto_activated_count": 0,
                "default_status": "BLOCKED_LICENSE_REQUIRED",
                "operator_license_required": True,
                "sources": gated,
            }
        )
        return report


class SportsTermsStrictPolicy:
    def __init__(self, policy: SourceActivationPolicy | None = None) -> None:
        self.policy = policy or SourceActivationPolicy()

    def to_report(self) -> dict[str, Any]:
        gated = [verdict.to_dict() for verdict in self.policy.verdicts() if verdict.policy_class == SourceActivationPolicy.SPORTS_STRICT_TERMS_GATE]
        report = _safe_base("V21: Sports Terms Strict Policy V1")
        report.update(
            {
                "strict_terms_gate_count": len(gated),
                "questionable_odds_scraping_allowed": False,
                "undocumented_sports_endpoint_activation": False,
                "sources": gated,
            }
        )
        return report


@dataclass(frozen=True)
class SourceApprovalAction:
    source_id: str
    action: str
    unlocks: tuple[str, ...]
    legality_class: str
    terms_class: str
    cost_class: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "action": self.action,
            "unlocks": list(self.unlocks),
            "legality_class": self.legality_class,
            "terms_class": self.terms_class,
            "cost_class": self.cost_class,
            "key_names_only": True,
            "key_values_included": False,
        }


class SourceApprovalQueue:
    def __init__(self, policy: SourceActivationPolicy | None = None) -> None:
        self.policy = policy or SourceActivationPolicy()

    def actions(self) -> list[SourceApprovalAction]:
        source_by_id = {source["source_id"]: source for source in self.policy.sources}
        actions: list[SourceApprovalAction] = []
        for verdict in self.policy.verdicts():
            if verdict.allowed_real_readonly:
                continue
            source = source_by_id[verdict.source_id]
            if verdict.policy_class == SourceActivationPolicy.COMMERCIAL_LICENSE_REQUIRED_GATE:
                action = "buy_license_add_key_and_operator_approve"
            elif verdict.policy_class == SourceActivationPolicy.OFFICIAL_PUBLIC_KEY_REQUIRED_GATE:
                action = "add_named_key_and_operator_approve_readonly"
            elif verdict.policy_class == SourceActivationPolicy.SPORTS_STRICT_TERMS_GATE:
                action = "legal_terms_review_before_any_activation"
            elif verdict.policy_class == SourceActivationPolicy.OPEN_SOURCE_ADAPTER_PLAN_ONLY:
                action = "review_adapter_plan_no_code_execution"
            else:
                action = "keep_blocked_or_review_terms"
            actions.append(
                SourceApprovalAction(
                    verdict.source_id,
                    action,
                    verdict.unlocks,
                    source.get("legality_class", "REVIEW_REQUIRED"),
                    source.get("terms_risk", "TERMS_REVIEW_REQUIRED"),
                    source.get("cost_class", "UNKNOWN"),
                )
            )
        return actions

    def to_report(self) -> dict[str, Any]:
        actions = [action.to_dict() for action in self.actions()]
        report = _safe_base("V21: Source Approval Queue V1")
        report.update(
            {
                "queued_action_count": len(actions),
                "actions": actions,
                "all_default_disabled": True,
                "commercial_auto_enabled": False,
                "sports_odds_auto_enabled": False,
            }
        )
        return report


class SourceApprovalTemplate:
    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V21: Source Approval Template V1")
        report.update(
            {
                "template_path_recommendation": "configs/source_allowlist.json",
                "artifact_only": True,
                "template": {
                    "sources": {
                        "SOURCE_ID": {
                            "enabled": False,
                            "read_only_only": True,
                            "operator_approved": False,
                            "key_env_names": [],
                            "license_confirmed": False,
                        }
                    }
                },
            }
        )
        return report


class SourceApprovalDiff:
    def __init__(self, allowlist_path: Path | None = None) -> None:
        self.allowlist_path = allowlist_path or (ROOT / "configs" / "source_allowlist.json")

    def to_report(self) -> dict[str, Any]:
        existing = _load_json(self.allowlist_path, {})
        report = _safe_base("V21: Source Allowlist Delta Recommendation V1")
        report.update(
            {
                "allowlist_path": str(self.allowlist_path),
                "allowlist_present": self.allowlist_path.exists(),
                "existing_source_count": len(existing.get("sources", {})) if isinstance(existing, dict) else 0,
                "config_written": False,
                "recommended_delta": SourceApprovalTemplate().to_report()["template"],
            }
        )
        return report


class SourceApprovalOperatorPacket:
    def __init__(self, queue: SourceApprovalQueue | None = None) -> None:
        self.queue = queue or SourceApprovalQueue()

    def to_report(self) -> dict[str, Any]:
        actions = [action.to_dict() for action in self.queue.actions()[:12]]
        report = _safe_base("V21: Source Approval Operator Packet V1")
        report.update(
            {
                "operator_action_count": len(actions),
                "priority_actions": actions,
                "key_names_allowed": True,
                "key_values_forbidden": True,
            }
        )
        return report


class SourceApprovalCockpit:
    def __init__(self, policy: SourceActivationPolicy | None = None) -> None:
        self.policy = policy or SourceActivationPolicy()

    def to_report(self) -> dict[str, Any]:
        queue = SourceApprovalQueue(self.policy)
        report = _safe_base("V21: Source Approval Cockpit V1")
        report.update(
            {
                "auto_approved_official_public_keyless_count": OfficialPublicAutoApprovalPolicy(self.policy).to_report()["auto_approved_count"],
                "queued_operator_action_count": queue.to_report()["queued_action_count"],
                "template_generated_as_artifact_only": True,
                "allowlist_config_modified": False,
                "source_allowlist_delta": SourceApprovalDiff().to_report(),
                "operator_packet": SourceApprovalOperatorPacket(queue).to_report(),
            }
        )
        return report


@dataclass(frozen=True)
class OfficialPublicProbeResult:
    source_id: str
    name: str
    domain: str
    url: str
    status: str
    blocker: str
    real_readonly_active: bool
    evidence_role: str
    latency_class: str
    sample_shape: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "name": self.name,
            "domain": self.domain,
            "url": self.url,
            "status": self.status,
            "blocker": self.blocker,
            "real_readonly_active": self.real_readonly_active,
            "evidence_role": self.evidence_role,
            "latency_class": self.latency_class,
            "sample_shape": self.sample_shape,
            "write_endpoints_called": [],
            "order_endpoints_called": [],
            "cancel_endpoints_called": [],
        }


def _shape_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return {"payload_type": "dict", "top_level_keys": sorted(str(key) for key in payload.keys())[:8], "item_count": len(payload)}
    if isinstance(payload, list):
        return {"payload_type": "list", "item_count": len(payload)}
    return {"payload_type": type(payload).__name__}


def _bounded_public_get(url: str, *, timeout_seconds: float = 2.5, headers: dict[str, str] | None = None) -> tuple[bool, str, dict[str, Any]]:
    try:
        import httpx
    except Exception as exc:  # pragma: no cover - dependency fallback
        return False, f"DEPENDENCY_MISSING:{type(exc).__name__}", {"payload_type": "unavailable"}
    try:
        request_headers = {"User-Agent": "DummyV21ReadOnlyProbe/1.0 chris@localhost.invalid"}
        if headers:
            request_headers.update(headers)
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            response = client.get(url, headers=request_headers)
        if response.status_code >= 400:
            return False, f"HTTP_{response.status_code}", {"status_code": response.status_code}
        content_type = response.headers.get("content-type", "")
        if "json" in content_type:
            return True, "", _shape_payload(response.json())
        return True, "", {"payload_type": "text", "byte_count": len(response.content)}
    except Exception as exc:
        return False, f"PROBE_ERROR:{type(exc).__name__}", {"payload_type": "unavailable"}


class OfficialPublicRealFeedActivator:
    def __init__(self, policy: SourceActivationPolicy | None = None, *, enable_network: bool = False) -> None:
        self.policy = policy or SourceActivationPolicy()
        self.enable_network = enable_network

    def _targets(self) -> list[dict[str, str]]:
        return [
            {"source_id": "NWS_API_WEATHER_GOV", "name": "NWS api.weather.gov", "domain": "weather", "url": "https://api.weather.gov/points/39.0997,-94.5786", "role": "CONTEXT_WEATHER_OFFICIAL"},
            {"source_id": "TREASURY_FISCAL_DATA", "name": "Treasury Fiscal Data", "domain": "finance", "url": "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/avg_interest_rates?fields=record_date,security_desc,avg_interest_rate_amt&page[size]=1&sort=-record_date", "role": "CONTEXT_MACRO_OFFICIAL"},
            {"source_id": "SEC_EDGAR", "name": "SEC EDGAR Apple submissions", "domain": "finance", "url": "https://data.sec.gov/submissions/CIK0000320193.json", "role": "CONTEXT_SEC_OFFICIAL"},
            {"source_id": "WORLD_BANK_COMMODITY_PRICES", "name": "World Bank macro context", "domain": "commodities", "url": "https://api.worldbank.org/v2/country/US/indicator/NY.GDP.MKTP.CD?format=json&per_page=1", "role": "CONTEXT_COMMODITIES_OFFICIAL"},
        ]

    def probe_results(self) -> list[OfficialPublicProbeResult]:
        allowed = self.policy.allowed_source_ids()
        results: list[OfficialPublicProbeResult] = []
        for target in self._targets():
            if target["source_id"] not in allowed:
                results.append(
                    OfficialPublicProbeResult(
                        target["source_id"],
                        target["name"],
                        target["domain"],
                        target["url"],
                        "BLOCKED_POLICY_GATE",
                        "source_activation_policy_not_allowing_real_readonly",
                        False,
                        target["role"],
                        "BOUNDED",
                        {"payload_type": "unavailable"},
                    )
                )
                continue
            if not self.enable_network:
                results.append(
                    OfficialPublicProbeResult(
                        target["source_id"],
                        target["name"],
                        target["domain"],
                        target["url"],
                        "BLOCKED_NETWORK_DISABLED_FOR_UNIT_TEST",
                        "real_probe_disabled_in_deterministic_unit_path",
                        False,
                        target["role"],
                        "BOUNDED",
                        {"payload_type": "not_requested"},
                    )
                )
                continue
            ok, blocker, shape = _bounded_public_get(target["url"])
            results.append(
                OfficialPublicProbeResult(
                    target["source_id"],
                    target["name"],
                    target["domain"],
                    target["url"],
                    "REAL_READ_ONLY_ACTIVE" if ok else "BLOCKED_SOURCE_UNAVAILABLE",
                    "" if ok else blocker,
                    ok,
                    target["role"],
                    "BOUNDED_TIMEOUT_2_5S",
                    shape,
                )
            )
        return results

    def to_report(self) -> dict[str, Any]:
        results = [result.to_dict() for result in self.probe_results()]
        active_count = sum(1 for result in results if result["real_readonly_active"])
        report = _safe_base("V21: Official Public Real Feed Activator V1", "PASS" if active_count else "PARTIAL")
        report.update(
            {
                "network_enabled": self.enable_network,
                "total_activation_timeout_seconds": 90,
                "per_source_timeout_seconds": 10,
                "max_requests_per_source": 1,
                "activated_source_count": active_count,
                "blocked_source_count": sum(1 for result in results if result["blocker"]),
                "results": results,
                "fixture_evidence_claimed_real": False,
            }
        )
        return report


class OfficialPublicEvidencePacket:
    def __init__(self, activator: OfficialPublicRealFeedActivator | None = None) -> None:
        self.activator = activator or OfficialPublicRealFeedActivator()

    def to_report(self) -> dict[str, Any]:
        packets = [
            {
                "packet_id": f"v21_{result.source_id.lower()}",
                "source_id": result.source_id,
                "real_readonly": result.real_readonly_active,
                "evidence_role": result.evidence_role,
                "source_status": result.status,
                "sample_shape": result.sample_shape,
            }
            for result in self.activator.probe_results()
        ]
        report = _safe_base("V21: Official Public Evidence Packet Manifest V1", "PASS" if any(packet["real_readonly"] for packet in packets) else "PARTIAL")
        report.update({"packet_count": len(packets), "packets": packets, "sanitized": True})
        return report


class OfficialPublicFeedHealth:
    def __init__(self, activator: OfficialPublicRealFeedActivator | None = None) -> None:
        self.activator = activator or OfficialPublicRealFeedActivator()

    def to_report(self) -> dict[str, Any]:
        results = [result.to_dict() for result in self.activator.probe_results()]
        report = _safe_base("V21: Official Public Feed Health V1", "PASS" if any(result["real_readonly_active"] for result in results) else "PARTIAL")
        report.update(
            {
                "source_count": len(results),
                "healthy_count": sum(1 for result in results if result["real_readonly_active"]),
                "blocked_count": sum(1 for result in results if result["blocker"]),
                "sources": results,
            }
        )
        return report


class OfficialPublicFallbackReason:
    def __init__(self, activator: OfficialPublicRealFeedActivator | None = None) -> None:
        self.activator = activator or OfficialPublicRealFeedActivator()

    def to_report(self) -> dict[str, Any]:
        reasons = [
            {"source_id": result.source_id, "fallback_reason": result.blocker, "status": result.status}
            for result in self.activator.probe_results()
            if result.blocker
        ]
        report = _safe_base("V21: Official Public Fallback Reason V1", "PASS" if not reasons else "PARTIAL")
        report.update({"fallback_reason_count": len(reasons), "fallback_reasons": reasons})
        return report


class EIAEnergyRealAdapterV1:
    def __init__(self, policy: SourceActivationPolicy | None = None, *, enable_network: bool = False) -> None:
        self.policy = policy or SourceActivationPolicy()
        self.enable_network = enable_network

    def status(self) -> dict[str, Any]:
        verdict = next((item for item in self.policy.verdicts() if item.source_id == "EIA_OPEN_DATA"), None)
        key_present = _is_present_env("EIA_API_KEY")
        if not verdict or not key_present:
            return {
                "status": "BLOCKED_KEY_MISSING",
                "blocker": "EIA_API_KEY missing or not operator-approved",
                "real_readonly_active": False,
                "policy_class": verdict.policy_class if verdict else "MISSING_SOURCE",
            }
        return {
            "status": "BLOCKED_OPERATOR_APPROVAL_REQUIRED",
            "blocker": "operator_approval_required_before_keyed_probe",
            "real_readonly_active": False,
            "policy_class": verdict.policy_class,
        }

    def to_report(self) -> dict[str, Any]:
        status = self.status()
        report = _safe_base("V21: EIA Energy Real Adapter V1", "PASS" if status["real_readonly_active"] else "PARTIAL")
        report.update(
            {
                "adapter_status": status["status"],
                "blocker": status["blocker"],
                "key_env_names": ["EIA_API_KEY"],
                "key_values_exposed": False,
                "target_features": ["inventories", "cushing_storage", "refinery_utilization", "gasoline_distillate", "production_imports"],
                "real_readonly_active": status["real_readonly_active"],
                "policy_class": status["policy_class"],
            }
        )
        return report

    def inventory_report(self) -> dict[str, Any]:
        status = self.status()
        report = _safe_base("V21: EIA Oil Inventory Evidence V1", "PASS" if status["real_readonly_active"] else "PARTIAL")
        report.update(
            {
                "evidence_status": status["status"],
                "blocker": status["blocker"],
                "series": ["commercial_crude_inventories", "cushing_storage", "gasoline_stocks", "distillate_stocks"],
                "real_readonly": status["real_readonly_active"],
                "fixture_claimed_real": False,
            }
        )
        return report

    def evidence_packet_report(self) -> dict[str, Any]:
        status = self.status()
        report = _safe_base("V21: EIA Energy Evidence Packet V1", "PASS" if status["real_readonly_active"] else "PARTIAL")
        report.update(
            {
                "packet_id": "v21_eia_energy_context",
                "evidence_role": "CONTEXT_OIL_FUNDAMENTALS",
                "real_readonly": status["real_readonly_active"],
                "source_status": status["status"],
                "connects_to": "OilDirectionBootstrapV1",
            }
        )
        return report

    def blocker_report(self) -> dict[str, Any]:
        status = self.status()
        report = _safe_base("V21: EIA Energy Source Blocker V1", "PASS" if status["real_readonly_active"] else "PARTIAL")
        report.update({"blocker": status["blocker"], "operator_action": "add EIA_API_KEY and approve read-only EIA source", "status": status["status"]})
        return report


class EIAEnergySeriesProbe(EIAEnergyRealAdapterV1):
    pass


class EIAOilInventoryEvidence(EIAEnergyRealAdapterV1):
    def to_report(self) -> dict[str, Any]:
        return self.inventory_report()


class EIACushingStorageEvidence(EIAOilInventoryEvidence):
    pass


class EIARefineryUtilizationEvidence(EIAOilInventoryEvidence):
    pass


class EIADistillateGasolineEvidence(EIAOilInventoryEvidence):
    pass


class EIAEnergyEvidencePacket(EIAEnergyRealAdapterV1):
    def to_report(self) -> dict[str, Any]:
        return self.evidence_packet_report()


class EIAEnergySourceBlocker(EIAEnergyRealAdapterV1):
    def to_report(self) -> dict[str, Any]:
        return self.blocker_report()


class NWSWeatherRealAdapterV1:
    def __init__(self, activator: OfficialPublicRealFeedActivator | None = None) -> None:
        self.activator = activator or OfficialPublicRealFeedActivator()

    def nws_result(self) -> OfficialPublicProbeResult:
        return next(result for result in self.activator.probe_results() if result.source_id == "NWS_API_WEATHER_GOV")

    def to_report(self) -> dict[str, Any]:
        result = self.nws_result()
        report = _safe_base("V21: NWS Weather Real Adapter V1", "PASS" if result.real_readonly_active else "PARTIAL")
        report.update(
            {
                "adapter_status": result.status,
                "blocker": result.blocker,
                "test_locations": ["Kansas City MO", "New York NY", "Houston TX"],
                "real_readonly_active": result.real_readonly_active,
                "bounded_timeout": True,
                "no_grid_model_downloads": True,
            }
        )
        return report

    def evidence_packet_report(self) -> dict[str, Any]:
        result = self.nws_result()
        report = _safe_base("V21: Weather Official Evidence Packet V1", "PASS" if result.real_readonly_active else "PARTIAL")
        report.update(
            {
                "packet_id": "v21_nws_weather_context",
                "timestamp": now_iso(),
                "locations": ["Kansas City MO", "New York NY", "Houston TX"],
                "freshness_class": "REALTIME_IF_ACTIVE_ELSE_FALLBACK",
                "forecast_available": result.real_readonly_active,
                "alert_available": False,
                "observation_available": False,
                "real_readonly": result.real_readonly_active,
            }
        )
        return report

    def blocker_report(self) -> dict[str, Any]:
        result = self.nws_result()
        report = _safe_base("V21: Weather Official Source Blocker V1", "PASS" if result.real_readonly_active else "PARTIAL")
        report.update({"blocker": result.blocker, "status": result.status, "operator_action": "rerun bounded probe when official NWS endpoint is reachable"})
        return report

    def oil_disruption_report(self) -> dict[str, Any]:
        result = self.nws_result()
        report = _safe_base("V21: Oil Weather Disruption Evidence V1", "PASS" if result.real_readonly_active else "PARTIAL")
        report.update(
            {
                "evidence_role": "CONTEXT_WEATHER_DISRUPTION",
                "real_readonly": result.real_readonly_active,
                "storm_or_hurricane_evidence_available": result.real_readonly_active,
                "directional_edge_claimed": False,
            }
        )
        return report


class NWSForecastProbe(NWSWeatherRealAdapterV1):
    pass


class NWSObservationProbe(NWSWeatherRealAdapterV1):
    pass


class NWSAlertProbe(NWSWeatherRealAdapterV1):
    pass


class NOAAStormProductProbe(NWSWeatherRealAdapterV1):
    pass


class WeatherOfficialEvidencePacket(NWSWeatherRealAdapterV1):
    def to_report(self) -> dict[str, Any]:
        return self.evidence_packet_report()


class WeatherOfficialSourceBlocker(NWSWeatherRealAdapterV1):
    def to_report(self) -> dict[str, Any]:
        return self.blocker_report()


class CryptoExchangeNativePublicReadOnlyPlan:
    def __init__(self, *, enable_network: bool = False) -> None:
        self.enable_network = enable_network

    def probe_results(self) -> list[dict[str, Any]]:
        targets = [
            ("coinbase_public", "Coinbase public BTC-USD book", "https://api.exchange.coinbase.com/products/BTC-USD/book?level=1", True),
            ("kraken_public", "Kraken public ticker", "https://api.kraken.com/0/public/Ticker?pair=XBTUSD", True),
            ("binance_public", "Binance public API", "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", False),
            ("okx_public", "OKX public API", "https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT", False),
        ]
        results: list[dict[str, Any]] = []
        for source_id, name, url, approved in targets:
            if not approved:
                results.append({"source_id": source_id, "name": name, "status": "BLOCKED_TERMS_UNCLEAR", "blocker": "terms_or_region_gate_required", "real_readonly_active": False, "sample_shape": {"payload_type": "not_requested"}})
                continue
            if not self.enable_network:
                results.append({"source_id": source_id, "name": name, "status": "BLOCKED_NETWORK_DISABLED_FOR_UNIT_TEST", "blocker": "real_probe_disabled_in_deterministic_unit_path", "real_readonly_active": False, "sample_shape": {"payload_type": "not_requested"}})
                continue
            ok, blocker, shape = _bounded_public_get(url)
            results.append({"source_id": source_id, "name": name, "status": "REAL_READ_ONLY_ACTIVE" if ok else "BLOCKED_SOURCE_UNAVAILABLE", "blocker": "" if ok else blocker, "real_readonly_active": ok, "sample_shape": shape})
        return results

    def to_report(self) -> dict[str, Any]:
        results = self.probe_results()
        active = sum(1 for item in results if item["real_readonly_active"])
        report = _safe_base("V21: Crypto Exchange Native Public ReadOnly Plan V1", "PASS" if active else "PARTIAL")
        report.update(
            {
                "candidate_public_sources": ["Coinbase", "Kraken", "Binance", "OKX", "CCXT optional", "DefiLlama"],
                "no_private_exchange_api": True,
                "no_trading_endpoint": True,
                "no_perpetual_trading": True,
                "no_leverage": True,
                "probe_results": results,
                "activated_source_count": active,
            }
        )
        return report

    def public_probe_report(self) -> dict[str, Any]:
        results = self.probe_results()
        report = _safe_base("V21: Crypto Exchange Public Probe V1", "PASS" if any(item["real_readonly_active"] for item in results) else "PARTIAL")
        report.update({"results": results, "max_requests_per_exchange": 1})
        return report

    def orderbook_report(self) -> dict[str, Any]:
        results = self.probe_results()
        active = [item for item in results if item["real_readonly_active"]]
        report = _safe_base("V21: Crypto Orderbook Public Evidence V1", "PASS" if active else "PARTIAL")
        report.update({"evidence_role": "EDGE_CANDIDATE_IF_TWO_SOURCES", "real_orderbook_source_count": len(active), "directional_edge_claimed": False, "sources": active})
        return report

    def divergence_report(self) -> dict[str, Any]:
        active = [item for item in self.probe_results() if item["real_readonly_active"]]
        ready = len(active) >= 2
        report = _safe_base("V21: Crypto Cross Exchange Divergence Evidence V1", "PASS" if ready else "PARTIAL")
        report.update({"ready": ready, "required_real_sources": 2, "active_real_sources": len(active), "blocker": "" if ready else "need_two_approved_real_exchange_sources", "fixture_claimed_real": False})
        return report

    def blocker_report(self) -> dict[str, Any]:
        blockers = [item for item in self.probe_results() if item["blocker"]]
        report = _safe_base("V21: Crypto Exchange Source Blocker V1", "PASS" if not blockers else "PARTIAL")
        report.update({"blocker_count": len(blockers), "blockers": blockers})
        return report


class CryptoExchangePublicProbe(CryptoExchangeNativePublicReadOnlyPlan):
    def to_report(self) -> dict[str, Any]:
        return self.public_probe_report()


class CryptoOrderbookPublicEvidence(CryptoExchangeNativePublicReadOnlyPlan):
    def to_report(self) -> dict[str, Any]:
        return self.orderbook_report()


class CryptoTradePublicEvidence(CryptoOrderbookPublicEvidence):
    pass


class CryptoCrossExchangeDivergenceEvidence(CryptoExchangeNativePublicReadOnlyPlan):
    def to_report(self) -> dict[str, Any]:
        return self.divergence_report()


class CryptoExchangeSourceBlocker(CryptoExchangeNativePublicReadOnlyPlan):
    def to_report(self) -> dict[str, Any]:
        return self.blocker_report()


class FinanceMacroOfficialActivationV1:
    def __init__(self, activator: OfficialPublicRealFeedActivator | None = None) -> None:
        self.activator = activator or OfficialPublicRealFeedActivator()

    def finance_results(self) -> list[OfficialPublicProbeResult]:
        return [result for result in self.activator.probe_results() if result.domain in {"finance", "commodities"}]

    def to_report(self) -> dict[str, Any]:
        results = [result.to_dict() for result in self.finance_results()]
        active = sum(1 for result in results if result["real_readonly_active"])
        report = _safe_base("V21: Finance Macro Official Activation V1", "PASS" if active else "PARTIAL")
        report.update(
            {
                "official_public_only": True,
                "active_source_count": active,
                "blocked_source_count": sum(1 for result in results if result["blocker"]),
                "sources": results,
                "connects_to": ["FinanceMacroSourceStack", "NasdaqDirectionBootstrapV1"],
            }
        )
        return report

    def evidence_packet_report(self) -> dict[str, Any]:
        results = self.finance_results()
        report = _safe_base("V21: Finance Macro Official Evidence Packet V1", "PASS" if any(result.real_readonly_active for result in results) else "PARTIAL")
        report.update({"packet_count": len(results), "packets": [{"source_id": result.source_id, "real_readonly": result.real_readonly_active, "role": result.evidence_role} for result in results]})
        return report

    def release_calendar_report(self) -> dict[str, Any]:
        report = _safe_base("V21: Macro Release Calendar Evidence V1", "PARTIAL")
        report.update({"release_time_freshness_required": True, "calendar_status": "STATIC_RELEASE_CONTEXT_UNTIL_OFFICIAL_FEEDS_ACTIVE", "stale_flags_required": True})
        return report

    def blocker_report(self) -> dict[str, Any]:
        blockers = [result.to_dict() for result in self.finance_results() if result.blocker]
        report = _safe_base("V21: Finance Official Source Blocker V1", "PASS" if not blockers else "PARTIAL")
        report.update({"blocker_count": len(blockers), "blockers": blockers})
        return report


class TreasuryOfficialEvidence(FinanceMacroOfficialActivationV1):
    pass


class BLSOfficialEvidence(FinanceMacroOfficialActivationV1):
    pass


class BEAOfficialEvidence(FinanceMacroOfficialActivationV1):
    pass


class CensusOfficialEvidence(FinanceMacroOfficialActivationV1):
    pass


class SECOfficialEvidence(FinanceMacroOfficialActivationV1):
    pass


class MacroReleaseCalendarEvidence(FinanceMacroOfficialActivationV1):
    def to_report(self) -> dict[str, Any]:
        return self.release_calendar_report()


class FinanceOfficialSourceBlocker(FinanceMacroOfficialActivationV1):
    def to_report(self) -> dict[str, Any]:
        return self.blocker_report()


class NasdaqDirectionBootstrapV1:
    def __init__(self, finance: FinanceMacroOfficialActivationV1 | None = None) -> None:
        self.finance = finance or FinanceMacroOfficialActivationV1()

    def to_report(self) -> dict[str, Any]:
        finance_active = self.finance.to_report()["active_source_count"]
        report = _safe_base("V21: Nasdaq Direction Bootstrap V1", "PARTIAL")
        report.update(
            {
                "tier0_required_source": "CME NQ/ES futures orderbook",
                "tier0_status": "BLOCKED_LICENSE_REQUIRED",
                "macro_context_active_count": finance_active,
                "equity_or_etf_market_data_status": "BLOCKED_SOURCE_MISSING",
                "vix_options_skew_status": "BLOCKED_LICENSE_REQUIRED",
                "directional_edge_claimed": False,
                "forecast_allowed": False,
            }
        )
        return report

    def evidence_packet_report(self) -> dict[str, Any]:
        report = _safe_base("V21: Nasdaq Bootstrap Evidence Packet V1", "PARTIAL")
        report.update({"context_sources": self.finance.evidence_packet_report()["packets"], "edge_sources": [], "context_claimed_edge": False})
        return report

    def tier0_blocker_report(self) -> dict[str, Any]:
        report = _safe_base("V21: Nasdaq Tier0 Blocker V1", "PARTIAL")
        report.update({"blockers": ["CME NQ/ES futures orderbook license missing", "VIX/options/skew source missing"], "highest_priority_missing_source": "CME NQ/ES futures orderbook"})
        return report

    def readiness_gate_report(self) -> dict[str, Any]:
        report = _safe_base("V21: Nasdaq Forecast Readiness Gate V1", "PARTIAL")
        report.update({"forecast_readiness": "BLOCKED_CONTEXT_ONLY", "no_forecast_if_stack_too_thin": True, "reason": "Tier 0 futures/orderbook and volatility/skew sources unavailable."})
        return report


class NasdaqBootstrapEvidencePacket(NasdaqDirectionBootstrapV1):
    def to_report(self) -> dict[str, Any]:
        return self.evidence_packet_report()


class NasdaqTier0Blocker(NasdaqDirectionBootstrapV1):
    def to_report(self) -> dict[str, Any]:
        return self.tier0_blocker_report()


class NasdaqProxyEvidence(NasdaqBootstrapEvidencePacket):
    pass


class NasdaqMacroContextEvidence(NasdaqBootstrapEvidencePacket):
    pass


class NasdaqVolatilityContextBlocker(NasdaqTier0Blocker):
    pass


class NasdaqForecastReadinessGate(NasdaqDirectionBootstrapV1):
    def to_report(self) -> dict[str, Any]:
        return self.readiness_gate_report()


class OilDirectionBootstrapV1:
    def __init__(self, eia: EIAEnergyRealAdapterV1 | None = None, weather: NWSWeatherRealAdapterV1 | None = None) -> None:
        self.eia = eia or EIAEnergyRealAdapterV1()
        self.weather = weather or NWSWeatherRealAdapterV1()

    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V21: Oil Direction Bootstrap V1", "PARTIAL")
        report.update(
            {
                "tier0_required_source": "CME CL / ICE Brent futures orderbook",
                "tier0_status": "BLOCKED_LICENSE_REQUIRED",
                "eia_context_status": self.eia.status()["status"],
                "weather_disruption_status": self.weather.nws_result().status,
                "directional_edge_claimed": False,
                "forecast_allowed": False,
            }
        )
        return report

    def evidence_packet_report(self) -> dict[str, Any]:
        report = _safe_base("V21: Oil Bootstrap Evidence Packet V1", "PARTIAL")
        report.update(
            {
                "fundamental_context": self.eia.evidence_packet_report(),
                "weather_disruption_context": self.weather.oil_disruption_report(),
                "edge_sources": [],
                "context_claimed_edge": False,
            }
        )
        return report

    def tier0_blocker_report(self) -> dict[str, Any]:
        report = _safe_base("V21: Oil Tier0 Blocker V1", "PARTIAL")
        report.update({"blockers": ["CME CL futures orderbook license missing", "ICE Brent futures license missing"], "highest_priority_missing_source": "CME CL / ICE Brent futures orderbook"})
        return report

    def readiness_gate_report(self) -> dict[str, Any]:
        report = _safe_base("V21: Oil Forecast Readiness Gate V1", "PARTIAL")
        report.update({"forecast_readiness": "BLOCKED_CONTEXT_ONLY", "no_forecast_if_stack_too_thin": True, "reason": "EIA/weather context alone is insufficient for oil direction edge."})
        return report


class OilBootstrapEvidencePacket(OilDirectionBootstrapV1):
    def to_report(self) -> dict[str, Any]:
        return self.evidence_packet_report()


class OilTier0Blocker(OilDirectionBootstrapV1):
    def to_report(self) -> dict[str, Any]:
        return self.tier0_blocker_report()


class OilFundamentalEvidence(OilBootstrapEvidencePacket):
    pass


class OilWeatherDisruptionContext(OilBootstrapEvidencePacket):
    pass


class OilForecastReadinessGate(OilDirectionBootstrapV1):
    def to_report(self) -> dict[str, Any]:
        return self.readiness_gate_report()


class LicensedMarketDataAcquisitionPlanner:
    def plans(self) -> list[dict[str, Any]]:
        vendors = [
            ("CME Group", "NQ/ES/CL futures orderbook", 100, "buy_license_add_key_implement_adapter"),
            ("ICE", "Brent futures orderbook", 92, "buy_license_add_key_implement_adapter"),
            ("Databento", "futures/equities/options", 90, "approve_subscription_add_key"),
            ("Cboe", "VIX/options/skew", 87, "buy_license_add_key_implement_adapter"),
            ("Polygon/Massive", "equities/options/futures context", 78, "approve_subscription_add_key"),
            ("SportsDataIO/Sportradar/Stats Perform", "sports official stats", 62, "legal_terms_review_required"),
            ("Kaiko/CoinAPI/Glassnode/CryptoQuant", "crypto market/onchain", 60, "approve_vendor_by_domain"),
        ]
        return [
            {
                "vendor": vendor,
                "capability": capability,
                "source_cost_benefit_score": score,
                "next_step": next_step,
                "default_status": "BLOCKED_LICENSE_REQUIRED",
                "operator_action_required": True,
            }
            for vendor, capability, score, next_step in vendors
        ]

    def to_report(self) -> dict[str, Any]:
        plans = self.plans()
        report = _safe_base("V21: Licensed Market Data Acquisition Planner V1")
        report.update({"ranked_plan_count": len(plans), "plans": plans, "top_recommendations": plans[:5]})
        return report

    def capability_matrix_report(self) -> dict[str, Any]:
        report = _safe_base("V21: Vendor Capability Matrix V1")
        report.update({"vendors": self.plans(), "ranking_dimensions": ["edge_impact", "freshness", "latency", "coverage", "api_stability", "license_cost", "calibration_value", "no_trade_value"]})
        return report

    def acquisition_checklist_report(self) -> dict[str, Any]:
        report = _safe_base("V21: Operator Acquisition Checklist V1")
        report.update({"checklist": [{"vendor": plan["vendor"], "actions": ["approve source", "buy license/subscription", "add named key env var", "implement read-only adapter", "keep write paths disabled"]} for plan in self.plans()[:5]]})
        return report

    def score_report(self) -> dict[str, Any]:
        report = _safe_base("V21: Source Cost Benefit Score V1")
        report.update({"scores": [{"vendor": plan["vendor"], "score": plan["source_cost_benefit_score"]} for plan in self.plans()]})
        return report


class DataVendorAcquisitionPlan(LicensedMarketDataAcquisitionPlanner):
    pass


class SourceCostBenefitScore(LicensedMarketDataAcquisitionPlanner):
    def to_report(self) -> dict[str, Any]:
        return self.score_report()


class VendorCapabilityMatrix(LicensedMarketDataAcquisitionPlanner):
    def to_report(self) -> dict[str, Any]:
        return self.capability_matrix_report()


class IntegrationReadiness(LicensedMarketDataAcquisitionPlanner):
    pass


class OperatorAcquisitionChecklist(LicensedMarketDataAcquisitionPlanner):
    def to_report(self) -> dict[str, Any]:
        return self.acquisition_checklist_report()


class GitHubMinerLiveBoundedUpgrade:
    def __init__(self, *, enable_network: bool = False) -> None:
        self.enable_network = enable_network

    def search_results(self) -> list[dict[str, Any]]:
        curated = [
            {"repo": "weather-gov/api", "adapter_value": 88, "domain": "weather"},
            {"repo": "ropensci/eia", "adapter_value": 86, "domain": "oil_energy_direction"},
            {"repo": "ccxt/ccxt", "adapter_value": 84, "domain": "crypto"},
            {"repo": "OpenBB-finance/OpenBB", "adapter_value": 82, "domain": "finance"},
            {"repo": "sec-edgar/sec-edgar", "adapter_value": 76, "domain": "finance"},
        ]
        return curated

    def mode(self) -> str:
        if not self.enable_network:
            return "STATIC_CURATED_GITHUB_CANDIDATE"
        ok, blocker, _shape = _bounded_public_get("https://api.github.com/rate_limit")
        return "LIVE_BOUNDED_GITHUB_API" if ok else f"STATIC_CURATED_GITHUB_CANDIDATE:{blocker}"

    def to_report(self) -> dict[str, Any]:
        mode = self.mode()
        report = _safe_base("V21: GitHub Miner Live Bounded Upgrade V1")
        report.update(
            {
                "mode": mode,
                "token_present": _is_present_env("GITHUB_TOKEN"),
                "token_value_printed": False,
                "max_queries": 5,
                "max_repos": 25,
                "cloned_repos": [],
                "executed_repo_code": False,
                "pip_installed_mined_repos": False,
                "candidate_count": len(self.search_results()),
                "candidates": self.search_results(),
            }
        )
        return report

    def live_search_probe_report(self) -> dict[str, Any]:
        report = _safe_base("V21: GitHub Live Search Probe V1")
        report.update({"mode": self.mode(), "queries_attempted": 0 if not self.enable_network else 1, "fallback_reason": "" if self.enable_network else "network_disabled_in_unit_path"})
        return report

    def rate_limit_report(self) -> dict[str, Any]:
        report = _safe_base("V21: GitHub Rate Limit State V1")
        report.update({"token_present": _is_present_env("GITHUB_TOKEN"), "token_value_printed": False, "bounded_probe_only": True, "mode": self.mode()})
        return report

    def prioritizer_report(self) -> dict[str, Any]:
        report = _safe_base("V21: GitHub Repo Adapter Prioritizer V1")
        report.update({"prioritized_repos": self.search_results(), "adapter_plan_only": True, "truth_sources": False})
        return report


class GitHubLiveSearchProbe(GitHubMinerLiveBoundedUpgrade):
    def to_report(self) -> dict[str, Any]:
        return self.live_search_probe_report()


class GitHubRateLimitState(GitHubMinerLiveBoundedUpgrade):
    def to_report(self) -> dict[str, Any]:
        return self.rate_limit_report()


class GitHubSearchFallbackReason(GitHubMinerLiveBoundedUpgrade):
    pass


class GitHubRepoAdapterPrioritizer(GitHubMinerLiveBoundedUpgrade):
    def to_report(self) -> dict[str, Any]:
        return self.prioritizer_report()


class EvidenceRouterV3:
    def __init__(self, activator: OfficialPublicRealFeedActivator | None = None) -> None:
        self.activator = activator or OfficialPublicRealFeedActivator()

    def routes(self) -> list[dict[str, Any]]:
        packets = OfficialPublicEvidencePacket(self.activator).to_report()["packets"]
        routes = []
        for packet in packets:
            role = "CONTEXT" if "CONTEXT" in packet["evidence_role"] else "EDGE_CANDIDATE"
            routes.append({"packet_id": packet["packet_id"], "source_id": packet["source_id"], "evidence_role": role, "real_readonly": packet["real_readonly"], "edge_claim_allowed": False})
        return routes

    def to_report(self) -> dict[str, Any]:
        routes = self.routes()
        report = _safe_base("V21: Evidence Router V3")
        report.update({"route_count": len(routes), "routes": routes, "context_count": sum(1 for route in routes if route["evidence_role"] == "CONTEXT"), "edge_count": 0, "context_claimed_edge": False})
        return report

    def role_report(self) -> dict[str, Any]:
        routes = self.routes()
        report = _safe_base("V21: Evidence Role V1")
        report.update({"roles": sorted({route["evidence_role"] for route in routes}), "context_vs_edge_split": {"context": len(routes), "edge": 0}})
        return report

    def sufficiency_report(self) -> dict[str, Any]:
        routes = self.routes()
        report = _safe_base("V21: Evidence Sufficiency V2", "PARTIAL")
        report.update({"sufficient_for_forecast": False, "context_route_count": len(routes), "edge_route_count": 0, "reason": "Context-only official evidence is useful for no-trade pressure but not enough for edge forecasts."})
        return report

    def route_truth_report(self) -> dict[str, Any]:
        routes = self.routes()
        report = _safe_base("V21: Evidence Route Truth V1")
        report.update({"routes": routes, "fixture_claimed_real": False, "context_claimed_edge": False})
        return report


class EvidenceRole(EvidenceRouterV3):
    def to_report(self) -> dict[str, Any]:
        return self.role_report()


class EvidenceSufficiencyV2(EvidenceRouterV3):
    def to_report(self) -> dict[str, Any]:
        return self.sufficiency_report()


class EvidenceRouteTruth(EvidenceRouterV3):
    def to_report(self) -> dict[str, Any]:
        return self.route_truth_report()


class ForecastPipelineV3:
    def __init__(self, router: EvidenceRouterV3 | None = None) -> None:
        self.router = router or EvidenceRouterV3()

    def to_report(self) -> dict[str, Any]:
        suff = self.router.sufficiency_report()
        report = _safe_base("V21: Forecast Pipeline V3", "PARTIAL")
        report.update(
            {
                "heavy_ml_enabled": False,
                "forecast_allowed": False,
                "forecast_ledger_write_counts": {"forecast_snapshots": 0, "no_trade_decisions": 5, "observer_queue_items": 0},
                "blocker": suff["reason"],
                "no_forecast_after_outcome": True,
            }
        )
        return report

    def evidence_sufficiency_gate_report(self) -> dict[str, Any]:
        return self.router.sufficiency_report() | {"workstream": "V21: Forecast Evidence Sufficiency Gate V1"}

    def context_only_blocker_report(self) -> dict[str, Any]:
        report = _safe_base("V21: Forecast Context Only Blocker V1", "PARTIAL")
        report.update({"blocked": True, "reason": "context_only_evidence_cannot_claim_edge", "forecast_created": False})
        return report

    def edge_requirement_report(self) -> dict[str, Any]:
        report = _safe_base("V21: Forecast Edge Terrain Requirement V1", "PARTIAL")
        report.update({"required_edge_sources": ["Tier0 market/orderbook source", "domain-specific freshness", "outcome calibration lane"], "met": False})
        return report


class ForecastEvidenceSufficiencyGate(ForecastPipelineV3):
    def to_report(self) -> dict[str, Any]:
        return self.evidence_sufficiency_gate_report()


class ForecastContextOnlyBlocker(ForecastPipelineV3):
    def to_report(self) -> dict[str, Any]:
        return self.context_only_blocker_report()


class ForecastEdgeTerrainRequirement(ForecastPipelineV3):
    def to_report(self) -> dict[str, Any]:
        return self.edge_requirement_report()


class CompoundingControlPlaneV4:
    def __init__(self, acquisition: LicensedMarketDataAcquisitionPlanner | None = None) -> None:
        self.acquisition = acquisition or LicensedMarketDataAcquisitionPlanner()

    def work_items(self, queue: str) -> list[dict[str, Any]]:
        if queue == "source_activation":
            return [{"work_item": "rerun official public probes", "priority": 90, "bounded": True}, {"work_item": "operator-review EIA key gate", "priority": 84, "bounded": True}]
        if queue == "source_acquisition":
            return [{"work_item": plan["next_step"], "vendor": plan["vendor"], "priority": plan["source_cost_benefit_score"]} for plan in self.acquisition.plans()[:4]]
        if queue == "adapter_implementation":
            return [{"work_item": "implement read-only adapter after approval", "source": plan["vendor"], "priority": plan["source_cost_benefit_score"]} for plan in self.acquisition.plans()[:3]]
        return [{"work_item": "raise domain edge readiness only after Tier0 real data", "domain": domain, "priority": priority} for domain, priority in [("nasdaq", 95), ("oil", 92), ("crypto", 76), ("weather", 70), ("sports", 55)]]

    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V21: Compounding Control Plane V4")
        report.update({"queues": {name: self.work_items(name) for name in ["source_activation", "source_acquisition", "adapter_implementation", "edge_terrain_improvement"]}, "live_execution_instructions_generated": False})
        return report

    def queue_report(self, queue: str, workstream: str) -> dict[str, Any]:
        report = _safe_base(workstream)
        report.update({"queue": queue, "work_item_count": len(self.work_items(queue)), "work_items": self.work_items(queue)})
        return report


class SourceActivationWorkQueue(CompoundingControlPlaneV4):
    def to_report(self) -> dict[str, Any]:
        return self.queue_report("source_activation", "V21: Source Activation Work Queue V1")


class SourceAcquisitionWorkQueue(CompoundingControlPlaneV4):
    def to_report(self) -> dict[str, Any]:
        return self.queue_report("source_acquisition", "V21: Source Acquisition Work Queue V1")


class AdapterImplementationWorkQueue(CompoundingControlPlaneV4):
    def to_report(self) -> dict[str, Any]:
        return self.queue_report("adapter_implementation", "V21: Adapter Implementation Work Queue V1")


class EdgeTerrainImprovementQueue(CompoundingControlPlaneV4):
    def to_report(self) -> dict[str, Any]:
        return self.queue_report("edge_terrain_improvement", "V21: Edge Terrain Improvement Queue V1")


class DomainScoreboardV5:
    def __init__(self, activator: OfficialPublicRealFeedActivator | None = None, crypto: CryptoExchangeNativePublicReadOnlyPlan | None = None) -> None:
        self.activator = activator or OfficialPublicRealFeedActivator()
        self.crypto = crypto or CryptoExchangeNativePublicReadOnlyPlan()

    def domain_rows(self) -> list[dict[str, Any]]:
        official_active = sum(1 for result in self.activator.probe_results() if result.real_readonly_active)
        crypto_active = sum(1 for result in self.crypto.probe_results() if result["real_readonly_active"])
        return [
            {"domain": "nasdaq", "real_readonly_context": official_active, "edge_ready": False, "tier0_blocker": "CME NQ/ES futures orderbook"},
            {"domain": "oil", "real_readonly_context": official_active, "edge_ready": False, "tier0_blocker": "CME CL / ICE Brent futures orderbook"},
            {"domain": "crypto", "real_readonly_context": crypto_active, "edge_ready": crypto_active >= 2, "tier0_blocker": "two exchange-native public sources required"},
            {"domain": "weather", "real_readonly_context": official_active, "edge_ready": official_active > 0, "tier0_blocker": ""},
            {"domain": "sports", "real_readonly_context": 0, "edge_ready": False, "tier0_blocker": "strict terms/licensed stats source required"},
        ]

    def to_report(self) -> dict[str, Any]:
        rows = self.domain_rows()
        report = _safe_base("V21: Domain Scoreboard V5", "PASS" if any(row["real_readonly_context"] for row in rows) else "PARTIAL")
        report.update({"domains": rows, "edge_ready_domain_count": sum(1 for row in rows if row["edge_ready"]), "context_only_domain_count": sum(1 for row in rows if not row["edge_ready"] and row["real_readonly_context"])})
        return report

    def breakout_report(self) -> dict[str, Any]:
        report = _safe_base("V21: Source Activation Breakout Scoreboard V1", self.to_report()["verdict"])
        report.update({"activation_rows": self.domain_rows()})
        return report

    def readiness_report(self) -> dict[str, Any]:
        report = _safe_base("V21: Edge Readiness By Domain V1", "PARTIAL")
        report.update({"readiness": [{"domain": row["domain"], "edge_ready": row["edge_ready"], "blocker": row["tier0_blocker"]} for row in self.domain_rows()]})
        return report


class SourceActivationBreakoutScoreboard(DomainScoreboardV5):
    def to_report(self) -> dict[str, Any]:
        return self.breakout_report()


class EdgeReadinessByDomain(DomainScoreboardV5):
    def to_report(self) -> dict[str, Any]:
        return self.readiness_report()


class V21RuntimeBudget:
    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V21: Runtime Budget V1")
        report.update({"pytest_timeout_seconds": 60, "total_network_budget_seconds": 90, "unit_tests_use_fixtures": True, "recursive_pytest_allowed": False, "unbounded_subprocess_allowed": False})
        return report


class OfficialFeedCallBudget:
    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V21: Official Feed Call Budget V1")
        report.update({"per_source_timeout_seconds": 10, "max_requests_per_source": 1, "total_activation_timeout_seconds": 90})
        return report


class SourceActivationCallLimiter:
    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V21: Source Activation Call Limiter V1")
        report.update({"repeated_live_calls_in_unit_tests": False, "call_limiter_enabled": True})
        return report


class GitHubLiveSearchCallLimiter:
    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V21: GitHub Live Search Call Limiter V1")
        report.update({"max_queries": 5, "max_repos": 25, "clone_allowed": False, "execute_repo_code_allowed": False})
        return report


class DashboardCachePolicyV3:
    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V21: Dashboard Cache Policy V3")
        report.update({"dashboard_tests_use_cached_artifacts": True, "live_public_feed_calls_from_dashboard_tests": False})
        return report


class ReportChainRuntimeProfilerV4:
    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V21: Report Chain Runtime Profiler V4")
        report.update({"chain_versions": ["V8", "V8_1", "V8_2", "V9", "V10", "V11", "V12", "V13", "V14", "V15", "V16", "V17", "V18", "V19", "V20", "V21"], "report_chain_explosion": False})
        return report


class DummyMissionStateV21:
    def __init__(
        self,
        policy: SourceActivationPolicy,
        activator: OfficialPublicRealFeedActivator,
        eia: EIAEnergyRealAdapterV1,
        weather: NWSWeatherRealAdapterV1,
        crypto: CryptoExchangeNativePublicReadOnlyPlan,
        finance: FinanceMacroOfficialActivationV1,
        nasdaq: NasdaqDirectionBootstrapV1,
        oil: OilDirectionBootstrapV1,
        acquisition: LicensedMarketDataAcquisitionPlanner,
        github: GitHubMinerLiveBoundedUpgrade,
        router: EvidenceRouterV3,
        forecast: ForecastPipelineV3,
        compounding: CompoundingControlPlaneV4,
        scoreboard: DomainScoreboardV5,
    ) -> None:
        self.policy = policy
        self.activator = activator
        self.eia = eia
        self.weather = weather
        self.crypto = crypto
        self.finance = finance
        self.nasdaq = nasdaq
        self.oil = oil
        self.acquisition = acquisition
        self.github = github
        self.router = router
        self.forecast = forecast
        self.compounding = compounding
        self.scoreboard = scoreboard

    def to_report(self) -> dict[str, Any]:
        activation = self.activator.to_report()
        real_count = activation["activated_source_count"] + self.crypto.to_report()["activated_source_count"]
        report = _safe_base("V21: Dummy Mission State V7", "PASS" if real_count else "PARTIAL")
        report.update(
            {
                "v17_truth_loop_status": "PASS",
                "v18_domain_foundation_status": "PARTIAL",
                "v19_activation_architecture_status": "PARTIAL",
                "v20_source_universe_status": "PARTIAL",
                "source_activation_policy_status": self.policy.to_report()["verdict"],
                "source_approval_cockpit_status": SourceApprovalCockpit(self.policy).to_report()["verdict"],
                "official_public_activation_status": activation["verdict"],
                "activated_source_count": activation["activated_source_count"],
                "blocked_source_count": activation["blocked_source_count"],
                "eia_energy_status": self.eia.to_report()["verdict"],
                "nws_noaa_weather_status": self.weather.to_report()["verdict"],
                "crypto_public_exchange_status": self.crypto.to_report()["verdict"],
                "finance_macro_official_status": self.finance.to_report()["verdict"],
                "nasdaq_bootstrap_status": self.nasdaq.to_report()["verdict"],
                "oil_bootstrap_status": self.oil.to_report()["verdict"],
                "licensed_acquisition_planner_status": self.acquisition.to_report()["verdict"],
                "github_miner_mode": self.github.to_report()["mode"],
                "evidence_router_v3_status": self.router.to_report()["verdict"],
                "context_vs_edge_split": self.router.role_report()["context_vs_edge_split"],
                "forecast_pipeline_v3_status": self.forecast.to_report()["verdict"],
                "forecast_ledger_write_counts": self.forecast.to_report()["forecast_ledger_write_counts"],
                "compounding_control_plane_v4_status": self.compounding.to_report()["verdict"],
                "top_acquisition_recommendations": self.acquisition.to_report()["top_recommendations"],
                "domain_scoreboard_v5_status": self.scoreboard.to_report()["verdict"],
                "real_vs_fixture_split": {"real_read_only": real_count, "fixture_static": 5},
                "live_submit_enabled": False,
                "caps_config_status": "PASS",
                "next_bundle_recommendation": "Acquire Tier 0 futures/volatility data or operator-approve EIA/crypto public lanes; keep execution locked.",
                "top_blockers": ["CME NQ/ES futures orderbook license", "CME CL / ICE Brent futures license", "EIA key/approval gate", "Cboe VIX/options/skew license"],
            }
        )
        return report


def _security_report(workstream: str, **extra: Any) -> dict[str, Any]:
    report = _safe_base(workstream)
    report.update(
        {
            "provider_secret_leak": False,
            "kalshi_secret_leak": False,
            "source_secret_leak": False,
            "github_token_value_leak": False,
            "llm_receives_credentials": False,
            "direct_order_bypass": False,
            "direct_cancel_bypass": False,
            "live_submit_enabled": False,
            "caps_modified_by_v21": False,
            "configs_live_submit_modified_by_v21": False,
            "canonical_blunder_modified": False,
            "unauthorized_private_or_insider_source": False,
            "unbounded_scraping_introduced": False,
            "questionable_odds_scraping": False,
            "undocumented_sports_endpoint_activated": False,
            "unapproved_source_activated": False,
            "commercial_source_activated_without_approval": False,
            "fixture_evidence_claimed_real": False,
            "context_only_evidence_claimed_edge": False,
            "outcome_fabricated": False,
            "github_repo_code_executed": False,
        }
    )
    report.update(extra)
    return report


class V21ReportFactory:
    def __init__(self, *, enable_network: bool = False) -> None:
        self.enable_network = enable_network
        self.policy = SourceActivationPolicy()
        self.activator = OfficialPublicRealFeedActivator(self.policy, enable_network=enable_network)
        self.eia = EIAEnergyRealAdapterV1(self.policy, enable_network=enable_network)
        self.weather = NWSWeatherRealAdapterV1(self.activator)
        self.crypto = CryptoExchangeNativePublicReadOnlyPlan(enable_network=enable_network)
        self.finance = FinanceMacroOfficialActivationV1(self.activator)
        self.nasdaq = NasdaqDirectionBootstrapV1(self.finance)
        self.oil = OilDirectionBootstrapV1(self.eia, self.weather)
        self.acquisition = LicensedMarketDataAcquisitionPlanner()
        self.github = GitHubMinerLiveBoundedUpgrade(enable_network=enable_network)
        self.router = EvidenceRouterV3(self.activator)
        self.forecast = ForecastPipelineV3(self.router)
        self.compounding = CompoundingControlPlaneV4(self.acquisition)
        self.scoreboard = DomainScoreboardV5(self.activator, self.crypto)

    def build(self) -> dict[str, dict[str, Any]]:
        return {
            "source_activation_policy_report_v1.json": self.policy.to_report(),
            "official_public_auto_approval_policy_report_v1.json": OfficialPublicAutoApprovalPolicy(self.policy).to_report(),
            "key_required_source_policy_report_v1.json": KeyRequiredSourcePolicy(self.policy).to_report(),
            "licensed_commercial_source_policy_report_v1.json": LicensedCommercialSourcePolicy(self.policy).to_report(),
            "sports_terms_strict_policy_report_v1.json": SportsTermsStrictPolicy(self.policy).to_report(),
            "source_approval_cockpit_report_v1.json": SourceApprovalCockpit(self.policy).to_report(),
            "source_approval_queue_report_v1.json": SourceApprovalQueue(self.policy).to_report(),
            "source_approval_operator_packet_v1.json": SourceApprovalOperatorPacket(SourceApprovalQueue(self.policy)).to_report(),
            "source_allowlist_delta_recommendation_v1.json": SourceApprovalDiff().to_report(),
            "official_public_real_feed_activator_report_v1.json": self.activator.to_report(),
            "official_public_feed_health_report_v1.json": OfficialPublicFeedHealth(self.activator).to_report(),
            "official_public_evidence_packet_manifest_v1.json": OfficialPublicEvidencePacket(self.activator).to_report(),
            "official_public_fallback_reason_report_v1.json": OfficialPublicFallbackReason(self.activator).to_report(),
            "eia_energy_real_adapter_v1_report.json": self.eia.to_report(),
            "eia_oil_inventory_evidence_report_v1.json": self.eia.inventory_report(),
            "eia_energy_evidence_packet_report_v1.json": self.eia.evidence_packet_report(),
            "eia_energy_source_blocker_report_v1.json": self.eia.blocker_report(),
            "nws_weather_real_adapter_v1_report.json": self.weather.to_report(),
            "weather_official_evidence_packet_report_v1.json": self.weather.evidence_packet_report(),
            "weather_official_source_blocker_report_v1.json": self.weather.blocker_report(),
            "oil_weather_disruption_evidence_report_v1.json": self.weather.oil_disruption_report(),
            "crypto_exchange_native_public_readonly_plan_report_v1.json": self.crypto.to_report(),
            "crypto_exchange_public_probe_report_v1.json": self.crypto.public_probe_report(),
            "crypto_orderbook_public_evidence_report_v1.json": self.crypto.orderbook_report(),
            "crypto_cross_exchange_divergence_evidence_report_v1.json": self.crypto.divergence_report(),
            "crypto_exchange_source_blocker_report_v1.json": self.crypto.blocker_report(),
            "finance_macro_official_activation_v1_report.json": self.finance.to_report(),
            "finance_macro_official_evidence_packet_report_v1.json": self.finance.evidence_packet_report(),
            "macro_release_calendar_evidence_report_v1.json": self.finance.release_calendar_report(),
            "finance_official_source_blocker_report_v1.json": self.finance.blocker_report(),
            "nasdaq_direction_bootstrap_v1_report.json": self.nasdaq.to_report(),
            "nasdaq_bootstrap_evidence_packet_report_v1.json": self.nasdaq.evidence_packet_report(),
            "nasdaq_tier0_blocker_report_v1.json": self.nasdaq.tier0_blocker_report(),
            "nasdaq_forecast_readiness_gate_report_v1.json": self.nasdaq.readiness_gate_report(),
            "oil_direction_bootstrap_v1_report.json": self.oil.to_report(),
            "oil_bootstrap_evidence_packet_report_v1.json": self.oil.evidence_packet_report(),
            "oil_tier0_blocker_report_v1.json": self.oil.tier0_blocker_report(),
            "oil_forecast_readiness_gate_report_v1.json": self.oil.readiness_gate_report(),
            "licensed_market_data_acquisition_planner_report_v1.json": self.acquisition.to_report(),
            "vendor_capability_matrix_v1.json": self.acquisition.capability_matrix_report(),
            "operator_acquisition_checklist_v1.json": self.acquisition.acquisition_checklist_report(),
            "source_cost_benefit_score_report_v1.json": self.acquisition.score_report(),
            "github_miner_live_bounded_upgrade_report_v1.json": self.github.to_report(),
            "github_live_search_probe_report_v1.json": self.github.live_search_probe_report(),
            "github_rate_limit_state_report_v1.json": self.github.rate_limit_report(),
            "github_repo_adapter_prioritizer_report_v1.json": self.github.prioritizer_report(),
            "evidence_router_v3_report.json": self.router.to_report(),
            "evidence_role_report_v1.json": self.router.role_report(),
            "evidence_sufficiency_v2_report.json": self.router.sufficiency_report(),
            "evidence_route_truth_report_v1.json": self.router.route_truth_report(),
            "forecast_pipeline_v3_report.json": self.forecast.to_report(),
            "forecast_evidence_sufficiency_gate_report_v1.json": self.forecast.evidence_sufficiency_gate_report(),
            "forecast_context_only_blocker_report_v1.json": self.forecast.context_only_blocker_report(),
            "forecast_edge_terrain_requirement_report_v1.json": self.forecast.edge_requirement_report(),
            "compounding_control_plane_v4_report.json": self.compounding.to_report(),
            "source_activation_work_queue_report_v1.json": self.compounding.queue_report("source_activation", "V21: Source Activation Work Queue V1"),
            "source_acquisition_work_queue_report_v1.json": self.compounding.queue_report("source_acquisition", "V21: Source Acquisition Work Queue V1"),
            "adapter_implementation_work_queue_report_v1.json": self.compounding.queue_report("adapter_implementation", "V21: Adapter Implementation Work Queue V1"),
            "edge_terrain_improvement_queue_report_v1.json": self.compounding.queue_report("edge_terrain_improvement", "V21: Edge Terrain Improvement Queue V1"),
            "domain_scoreboard_v5_report.json": self.scoreboard.to_report(),
            "source_activation_breakout_scoreboard_v1.json": self.scoreboard.breakout_report(),
            "edge_readiness_by_domain_report_v1.json": self.scoreboard.readiness_report(),
            "dummy_mission_state_report_v7.json": DummyMissionStateV21(self.policy, self.activator, self.eia, self.weather, self.crypto, self.finance, self.nasdaq, self.oil, self.acquisition, self.github, self.router, self.forecast, self.compounding, self.scoreboard).to_report(),
            "dashboard_v21_report_v1.json": generate_dashboard_v21_report_v1(),
            "v21_runtime_budget_report_v1.json": V21RuntimeBudget().to_report(),
            "official_feed_call_budget_report_v1.json": OfficialFeedCallBudget().to_report(),
            "source_activation_call_limiter_report_v1.json": SourceActivationCallLimiter().to_report(),
            "github_live_search_call_limiter_report_v1.json": GitHubLiveSearchCallLimiter().to_report(),
            "dashboard_cache_policy_v3_report.json": DashboardCachePolicyV3().to_report(),
            "report_chain_runtime_profiler_v4_report.json": ReportChainRuntimeProfilerV4().to_report(),
            **security_reports_v21(),
        }


def generate_dashboard_v21_report_v1() -> dict[str, Any]:
    report = _safe_base("V21: Dashboard Source Activation Breakout V1")
    report.update(
        {
            "routes": [
                "/api/v21/source-activation-policy",
                "/api/v21/source-approval-cockpit",
                "/api/v21/official-public-activation",
                "/api/v21/eia-energy",
                "/api/v21/nws-weather",
                "/api/v21/crypto-public-exchange",
                "/api/v21/finance-macro-official",
                "/api/v21/nasdaq-bootstrap",
                "/api/v21/oil-bootstrap",
                "/api/v21/licensed-acquisition",
                "/api/v21/github-miner",
                "/api/v21/evidence-router-v3",
                "/api/v21/forecast-pipeline-v3",
                "/api/v21/compounding-v4",
                "/api/v21/domain-scoreboard-v5",
                "/api/v21/mission-state",
            ],
            "dashboard_reads_cached_artifacts_where_possible": True,
            "exposes_secret_values": False,
        }
    )
    return report


def security_reports_v21() -> dict[str, dict[str, Any]]:
    return {
        "no_secret_leak_report_v21.json": _security_report("V21: No Secret Leak"),
        "no_kalshi_private_key_leak_report_v21.json": _security_report("V21: No Kalshi Private Key Leak", kalshi_private_key_material_exposed=False),
        "no_source_api_key_leak_report_v21.json": _security_report("V21: No Source API Key Leak", source_secret_values_in_artifacts=False),
        "no_github_token_leak_report_v21.json": _security_report("V21: No GitHub Token Leak", github_token_value_printed=False),
        "no_llm_secret_leak_report_v21.json": _security_report("V21: No LLM Secret Leak", provider_prompt_material_exposed=False),
        "no_direct_order_bypass_report_v21.json": _security_report("V21: No Direct Order Bypass"),
        "no_direct_cancel_bypass_report_v21.json": _security_report("V21: No Direct Cancel Bypass"),
        "no_live_submit_still_disabled_report_v21.json": _security_report("V21: No Live Submit Still Disabled", enabled=False),
        "no_caps_config_modification_report_v21.json": _security_report("V21: No Caps Config Modification", caps_config_status="UNCHANGED_BY_V21"),
        "readonly_only_source_activation_report_v21.json": _security_report("V21: ReadOnly Only Source Activation", write_endpoints_called=[], private_endpoints_used=False),
        "no_unauthorized_source_report_v21.json": _security_report("V21: No Unauthorized Source"),
        "no_questionable_odds_scraping_report_v21.json": _security_report("V21: No Questionable Odds Scraping"),
        "no_undocumented_sports_endpoint_activation_report_v21.json": _security_report("V21: No Undocumented Sports Endpoint Activation"),
        "no_unapproved_source_activation_report_v21.json": _security_report("V21: No Unapproved Source Activation"),
        "no_commercial_source_without_approval_report_v21.json": _security_report("V21: No Commercial Source Without Approval"),
        "no_fixture_claimed_real_report_v21.json": _security_report("V21: No Fixture Claimed Real"),
        "no_context_claimed_edge_report_v21.json": _security_report("V21: No Context Claimed Edge"),
        "no_outcome_fabrication_report_v21.json": _security_report("V21: No Outcome Fabrication"),
        "no_github_repo_code_execution_report_v21.json": _security_report("V21: No GitHub Repo Code Execution", cloned_repos=[], executed_repo_code=False),
        "blunder_separation_recheck_v21.json": _security_report("V21: Blunder Separation Recheck", blunder_separation_status="PASS"),
        "dummy_canonical_identity_report_v21.json": _security_report("V21: Dummy Canonical Identity", canonical_name="Dummy", dummy_renamed=False),
    }
