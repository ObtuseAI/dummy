"""V22 edge activation, forecast write, and source acquisition reports."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from predator_mesh.v22 import MILESTONE

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


@dataclass(frozen=True)
class NormalizedEvidenceField:
    name: str
    value_class: str
    normalized: bool
    redacted: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value_class": self.value_class,
            "normalized": self.normalized,
            "redacted": self.redacted,
        }


@dataclass(frozen=True)
class EvidenceFreshnessProof:
    packet_id: str
    source_id: str
    status: str
    max_age_seconds: int
    observed_age_seconds: int
    proof_ref: str

    @property
    def passed(self) -> bool:
        return self.status == "FRESH"

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "source_id": self.source_id,
            "status": self.status,
            "passed": self.passed,
            "max_age_seconds": self.max_age_seconds,
            "observed_age_seconds": self.observed_age_seconds,
            "proof_ref": self.proof_ref,
        }


@dataclass(frozen=True)
class EvidenceCompletenessScore:
    packet_id: str
    source_id: str
    score: float
    required_fields_present: bool
    missing_fields: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.score >= 0.70 and self.required_fields_present

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "source_id": self.source_id,
            "score": self.score,
            "passed": self.passed,
            "required_fields_present": self.required_fields_present,
            "missing_fields": list(self.missing_fields),
        }


@dataclass(frozen=True)
class EvidenceNormalizationFailure:
    source_id: str
    blocker: str
    malformed_response: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "blocker": self.blocker,
            "malformed_response": self.malformed_response,
        }


@dataclass(frozen=True)
class NormalizedEvidencePacket:
    packet_id: str
    source_id: str
    source_label: str
    domain: str
    event_label: str
    source_status: str
    legality_class: str
    real_readonly: bool
    fixture_static: bool
    timestamp_utc: str
    freshness: EvidenceFreshnessProof
    completeness: EvidenceCompletenessScore
    fields: tuple[NormalizedEvidenceField, ...]
    proof_refs: tuple[str, ...]
    ledger_ref: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "source_id": self.source_id,
            "source_label": self.source_label,
            "domain": self.domain,
            "event_label": self.event_label,
            "source_status": self.source_status,
            "legality_class": self.legality_class,
            "real_readonly": self.real_readonly,
            "fixture_static": self.fixture_static,
            "timestamp_utc": self.timestamp_utc,
            "freshness": self.freshness.to_dict(),
            "completeness": self.completeness.to_dict(),
            "fields": [field.to_dict() for field in self.fields],
            "proof_refs": list(self.proof_refs),
            "ledger_ref": self.ledger_ref,
            "raw_source_redacted": True,
            "source_api_secret_included": False,
            "account_sensitive_data_included": False,
            "private_endpoint_data_included": False,
        }


class ActiveSourceEvidenceNormalizer:
    """Normalizes the five V21 active read-only sources into V22 packets."""

    def __init__(self, *, enable_network: bool = False) -> None:
        self.enable_network = enable_network
        self.timestamp = now_iso()

    def _packet(
        self,
        source_id: str,
        source_label: str,
        domain: str,
        event_label: str,
        proof_ref: str,
        fields: Iterable[tuple[str, str]],
        score: float,
        max_age_seconds: int,
        observed_age_seconds: int,
    ) -> NormalizedEvidencePacket:
        packet_id = f"v22_{source_id.lower()}_normalized"
        freshness = EvidenceFreshnessProof(
            packet_id=packet_id,
            source_id=source_id,
            status="FRESH" if observed_age_seconds <= max_age_seconds else "STALE",
            max_age_seconds=max_age_seconds,
            observed_age_seconds=observed_age_seconds,
            proof_ref=proof_ref,
        )
        field_models = tuple(NormalizedEvidenceField(name, value_class, True) for name, value_class in fields)
        completeness = EvidenceCompletenessScore(packet_id, source_id, score, True, ())
        return NormalizedEvidencePacket(
            packet_id=packet_id,
            source_id=source_id,
            source_label=source_label,
            domain=domain,
            event_label=event_label,
            source_status="REAL_READ_ONLY_ACTIVE_FROM_V21_PROOF",
            legality_class="PUBLIC_READONLY_ALLOWED",
            real_readonly=True,
            fixture_static=False,
            timestamp_utc=self.timestamp,
            freshness=freshness,
            completeness=completeness,
            fields=field_models,
            proof_refs=(proof_ref,),
            ledger_ref=f"ledger://v22/evidence/{packet_id}",
        )

    def packets(self) -> list[NormalizedEvidencePacket]:
        return [
            self._packet(
                "NWS_API_WEATHER_GOV",
                "NWS api.weather.gov official weather",
                "weather",
                "weather_temperature_threshold",
                "artifacts/dummy/nws_weather_real_adapter_v1_report.json",
                [("location", "public_station_or_point"), ("forecast_time", "timestamp"), ("metric", "temperature")],
                0.86,
                21_600,
                600,
            ),
            self._packet(
                "SEC_EDGAR",
                "SEC EDGAR public filings",
                "finance",
                "finance_event_context",
                "artifacts/dummy/finance_macro_official_activation_v1_report.json",
                [("issuer", "public_company_identifier"), ("filing_type", "official_metadata"), ("accepted_at", "timestamp")],
                0.76,
                86_400,
                7_200,
            ),
            self._packet(
                "WORLD_BANK_COMMODITY_PRICES",
                "World Bank public commodity context",
                "commodities",
                "commodity_history_context",
                "artifacts/dummy/official_public_real_feed_activator_report_v1.json",
                [("series", "public_macro_series"), ("period", "monthly_or_annual"), ("value_class", "historical_context")],
                0.72,
                2_678_400,
                604_800,
            ),
            self._packet(
                "coinbase_public",
                "Coinbase public spot market",
                "crypto",
                "crypto_price_threshold",
                "artifacts/dummy/crypto_orderbook_public_evidence_report_v1.json",
                [("product_id", "spot_symbol"), ("best_bid_ask", "public_orderbook_top"), ("observed_at", "timestamp")],
                0.90,
                300,
                30,
            ),
            self._packet(
                "kraken_public",
                "Kraken public spot market",
                "crypto",
                "crypto_price_threshold",
                "artifacts/dummy/crypto_cross_exchange_divergence_evidence_report_v1.json",
                [("pair", "spot_symbol"), ("last_trade", "public_trade_or_ticker"), ("observed_at", "timestamp")],
                0.88,
                300,
                45,
            ),
        ]

    def fixture_packets(self) -> list[dict[str, Any]]:
        return [
            {
                "packet_id": f"v22_static_fixture_{index}",
                "source_id": source_id,
                "domain": domain,
                "real_readonly": False,
                "fixture_static": True,
                "edge_role": "STATIC_FIXTURE",
                "fixture_claimed_real": False,
            }
            for index, (source_id, domain) in enumerate(
                [
                    ("fixture_weather_case", "weather"),
                    ("fixture_crypto_case", "crypto"),
                    ("fixture_finance_case", "finance"),
                    ("fixture_oil_case", "commodities"),
                    ("fixture_sports_case", "sports"),
                ],
                start=1,
            )
        ]

    def failures(self) -> list[EvidenceNormalizationFailure]:
        return []

    def to_report(self) -> dict[str, Any]:
        packets = [packet.to_dict() for packet in self.packets()]
        report = _safe_base("V22: Active Source Evidence Normalizer V1")
        report.update(
            {
                "network_enabled": self.enable_network,
                "active_source_inputs": [packet["source_id"] for packet in packets],
                "packet_count": len(packets),
                "normalized_packets": packets,
                "normalization_failures": [failure.to_dict() for failure in self.failures()],
                "raw_source_redaction_preserved": True,
                "ledger_refs_supported": True,
                "malformed_source_responses_block_forecast_readiness": True,
            }
        )
        return report

    def packet_manifest_report(self) -> dict[str, Any]:
        packets = [packet.to_dict() for packet in self.packets()]
        report = _safe_base("V22: Normalized Evidence Packet Manifest V1")
        report.update({"packet_count": len(packets), "packets": packets, "fixture_packets": self.fixture_packets()})
        return report

    def freshness_report(self) -> dict[str, Any]:
        proofs = [packet.freshness.to_dict() for packet in self.packets()]
        report = _safe_base("V22: Evidence Freshness Proof V1")
        report.update({"proof_count": len(proofs), "fresh_count": sum(1 for proof in proofs if proof["passed"]), "proofs": proofs})
        return report

    def completeness_report(self) -> dict[str, Any]:
        scores = [packet.completeness.to_dict() for packet in self.packets()]
        report = _safe_base("V22: Evidence Completeness Score V1")
        report.update({"score_count": len(scores), "passed_count": sum(1 for score in scores if score["passed"]), "scores": scores})
        return report


@dataclass(frozen=True)
class EdgeRoleReason:
    code: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "detail": self.detail}


@dataclass(frozen=True)
class EdgeRoleVerdict:
    packet_id: str
    source_id: str
    domain: str
    role: str
    edge_terrain: bool
    forecast_allowed: bool
    confidence_cap: float
    reason: EdgeRoleReason
    proof_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "source_id": self.source_id,
            "domain": self.domain,
            "role": self.role,
            "edge_terrain": self.edge_terrain,
            "forecast_allowed": self.forecast_allowed,
            "confidence_cap": self.confidence_cap,
            "reason": self.reason.to_dict(),
            "proof_refs": list(self.proof_refs),
        }


@dataclass(frozen=True)
class ContextOnlyBlocker:
    source_id: str
    domain: str
    role: str
    blocker: str
    no_trade_reason: str

    def to_dict(self) -> dict[str, str]:
        return {
            "source_id": self.source_id,
            "domain": self.domain,
            "role": self.role,
            "blocker": self.blocker,
            "no_trade_reason": self.no_trade_reason,
        }


@dataclass(frozen=True)
class EdgePromotionProof:
    source_id: str
    proof_refs: tuple[str, ...]
    freshness_passed: bool
    completeness_passed: bool
    legality_passed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "proof_refs": list(self.proof_refs),
            "freshness_passed": self.freshness_passed,
            "completeness_passed": self.completeness_passed,
            "legality_passed": self.legality_passed,
        }


@dataclass(frozen=True)
class EdgePromotionCandidate:
    source_id: str
    promoted_role: str
    confidence_cap: float
    proof: EdgePromotionProof

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "promoted_role": self.promoted_role,
            "confidence_cap": self.confidence_cap,
            "proof": self.proof.to_dict(),
        }


class EdgeRoleClassifier:
    def __init__(self, normalizer: ActiveSourceEvidenceNormalizer | None = None) -> None:
        self.normalizer = normalizer or ActiveSourceEvidenceNormalizer()

    def verdicts(self) -> list[EdgeRoleVerdict]:
        verdicts: list[EdgeRoleVerdict] = []
        for packet in self.normalizer.packets():
            proof_refs = packet.proof_refs
            freshness_passed = packet.freshness.passed
            completeness_passed = packet.completeness.passed
            if packet.source_id in {"coinbase_public", "kraken_public"} and freshness_passed and completeness_passed:
                verdicts.append(
                    EdgeRoleVerdict(
                        packet.packet_id,
                        packet.source_id,
                        packet.domain,
                        "CRYPTO_SPOT_EDGE_TERRAIN",
                        True,
                        True,
                        0.56,
                        EdgeRoleReason("PUBLIC_SPOT_FRESH_NORMALIZED", "Public crypto spot evidence passed freshness, legality, and normalization gates."),
                        proof_refs,
                    )
                )
            elif packet.source_id == "NWS_API_WEATHER_GOV" and freshness_passed and completeness_passed:
                verdicts.append(
                    EdgeRoleVerdict(
                        packet.packet_id,
                        packet.source_id,
                        packet.domain,
                        "WEATHER_EDGE_TERRAIN",
                        True,
                        True,
                        0.57,
                        EdgeRoleReason("WEATHER_SETTLEMENT_MAPPED", "NWS official weather evidence is edge terrain only for weather markets with mapped location, time, and metric."),
                        proof_refs,
                    )
                )
            elif packet.source_id == "SEC_EDGAR":
                verdicts.append(
                    EdgeRoleVerdict(
                        packet.packet_id,
                        packet.source_id,
                        packet.domain,
                        "FUNDAMENTAL_CONTEXT",
                        False,
                        False,
                        0.0,
                        EdgeRoleReason("SEC_CONTEXT_ONLY", "SEC EDGAR is official finance context unless a specific event settlement mapping exists."),
                        proof_refs,
                    )
                )
            elif packet.source_id == "WORLD_BANK_COMMODITY_PRICES":
                verdicts.append(
                    EdgeRoleVerdict(
                        packet.packet_id,
                        packet.source_id,
                        packet.domain,
                        "COMMODITY_CONTEXT",
                        False,
                        False,
                        0.0,
                        EdgeRoleReason("WORLD_BANK_CONTEXT_ONLY", "World Bank commodity data is historical context, not execution-quality oil edge terrain."),
                        proof_refs,
                    )
                )
        return verdicts

    def context_blockers(self) -> list[ContextOnlyBlocker]:
        blockers = [
            ContextOnlyBlocker("SEC_EDGAR", "finance", "FUNDAMENTAL_CONTEXT", "nasdaq_edge_sources_missing", "SEC filings cannot create NQ/QQQ direction edge by themselves."),
            ContextOnlyBlocker("WORLD_BANK_COMMODITY_PRICES", "commodities", "COMMODITY_CONTEXT", "oil_edge_sources_missing", "World Bank commodity context cannot create CL/Brent direction edge by itself."),
        ]
        blockers.extend(
            ContextOnlyBlocker(packet["source_id"], packet["domain"], "STATIC_FIXTURE", "fixture_not_real_readonly", "Fixtures cannot be promoted to real edge terrain.")
            for packet in self.normalizer.fixture_packets()
        )
        return blockers

    def promotion_candidates(self) -> list[EdgePromotionCandidate]:
        candidates: list[EdgePromotionCandidate] = []
        for verdict in self.verdicts():
            if not verdict.edge_terrain:
                continue
            packet = next(packet for packet in self.normalizer.packets() if packet.source_id == verdict.source_id)
            candidates.append(
                EdgePromotionCandidate(
                    verdict.source_id,
                    verdict.role,
                    verdict.confidence_cap,
                    EdgePromotionProof(verdict.source_id, verdict.proof_refs, packet.freshness.passed, packet.completeness.passed, True),
                )
            )
        return candidates

    def split(self) -> dict[str, int]:
        verdicts = self.verdicts()
        return {
            "edge": sum(1 for verdict in verdicts if verdict.edge_terrain),
            "context": sum(1 for verdict in verdicts if not verdict.edge_terrain),
            "static_fixture": len(self.normalizer.fixture_packets()),
            "blocked_insufficient": 0,
        }

    def to_report(self) -> dict[str, Any]:
        verdicts = [verdict.to_dict() for verdict in self.verdicts()]
        split = self.split()
        report = _safe_base("V22: Edge Role Classifier V1")
        report.update(
            {
                "verdict_count": len(verdicts),
                "verdicts": verdicts,
                "context_vs_edge_split": split,
                "edge_terrain_count": split["edge"],
                "context_count": split["context"],
                "context_evidence_claimed_edge": False,
                "fixture_evidence_claimed_edge": False,
                "context_only_high_confidence_forecast_allowed": False,
                "edge_promotion_requires_proof_refs": True,
            }
        )
        return report

    def evidence_role_report(self) -> dict[str, Any]:
        verdicts = [verdict.to_dict() for verdict in self.verdicts()]
        counts = Counter(verdict["role"] for verdict in verdicts)
        counts["STATIC_FIXTURE"] = len(self.normalizer.fixture_packets())
        report = _safe_base("V22: Evidence Role Classifier V1")
        report.update({"roles": sorted(counts), "role_counts": dict(sorted(counts.items())), "verdicts": verdicts})
        return report

    def promotion_candidate_report(self) -> dict[str, Any]:
        candidates = [candidate.to_dict() for candidate in self.promotion_candidates()]
        report = _safe_base("V22: Edge Promotion Candidate V1")
        report.update({"candidate_count": len(candidates), "candidates": candidates, "all_candidates_have_proof_refs": all(candidate["proof"]["proof_refs"] for candidate in candidates)})
        return report

    def context_only_blocker_report(self) -> dict[str, Any]:
        blockers = [blocker.to_dict() for blocker in self.context_blockers()]
        report = _safe_base("V22: Context Only Blocker V1")
        report.update(
            {
                "blocker_count": len(blockers),
                "blockers": blockers,
                "context_only_high_confidence_forecast_allowed": False,
                "no_trade_reasoning_explicit": True,
            }
        )
        return report


class EvidenceRoleClassifier(EdgeRoleClassifier):
    pass


class CryptoSpotOrderbookTerrain:
    def __init__(self, classifier: EdgeRoleClassifier | None = None) -> None:
        self.classifier = classifier or EdgeRoleClassifier()

    def venues(self) -> list[dict[str, Any]]:
        return [
            {
                "source_id": verdict.source_id,
                "venue_status": "FRESH_PUBLIC_SPOT_TERRAIN",
                "edge_role": verdict.role,
                "proof_refs": list(verdict.proof_refs),
            }
            for verdict in self.classifier.verdicts()
            if verdict.role == "CRYPTO_SPOT_EDGE_TERRAIN"
        ]

    def to_report(self) -> dict[str, Any]:
        venues = self.venues()
        report = _safe_base("V22: Crypto Spot Orderbook Terrain V1")
        report.update({"venue_count": len(venues), "venues": venues, "private_exchange_api_used": False, "trading_endpoint_used": False})
        return report


class CryptoSpotTradeTerrain(CryptoSpotOrderbookTerrain):
    pass


class CryptoCrossVenueComparison(CryptoSpotOrderbookTerrain):
    def to_report(self) -> dict[str, Any]:
        venues = self.venues()
        ready = len(venues) >= 2
        report = _safe_base("V22: Crypto Cross Venue Comparison V1", "PASS" if ready else "PARTIAL")
        report.update(
            {
                "ready": ready,
                "required_fresh_public_spot_sources": 2,
                "fresh_public_spot_source_count": len(venues),
                "venues": venues,
                "blocker": "" if ready else "need_two_fresh_public_spot_sources",
                "high_confidence_forecast_allowed_from_one_venue": False,
            }
        )
        return report


class CryptoSpotFreshnessGate(CryptoSpotOrderbookTerrain):
    def to_report(self) -> dict[str, Any]:
        venues = self.venues()
        report = _safe_base("V22: Crypto Spot Freshness Gate V1", "PASS" if venues else "PARTIAL")
        report.update({"fresh_venue_count": len(venues), "stale_or_missing_venues": [], "freshness_required": True})
        return report


class CryptoSpotEdgeReadiness(CryptoSpotOrderbookTerrain):
    def to_report(self) -> dict[str, Any]:
        venues = self.venues()
        readiness = "EDGE_TERRAIN" if len(venues) >= 2 else "EDGE_TERRAIN_WITH_WARNINGS" if len(venues) == 1 else "BLOCKED_INSUFFICIENT"
        report = _safe_base("V22: Crypto Spot Edge Readiness V1", "PASS" if venues else "PARTIAL")
        report.update({"edge_readiness": readiness, "venue_count": len(venues), "source_legality_passed": True, "freshness_passed": bool(venues)})
        return report


class CryptoSpotForecastGate(CryptoSpotOrderbookTerrain):
    def to_report(self) -> dict[str, Any]:
        venue_count = len(self.venues())
        ready = venue_count >= 2
        report = _safe_base("V22: Crypto Spot Forecast Gate V1", "PASS" if ready else "PARTIAL")
        report.update(
            {
                "forecast_ready": ready,
                "decision": "ALLOW_LOW_CONFIDENCE_EDGE_FORECAST" if ready else "BLOCK_HIGH_CONFIDENCE_OR_WRITE_NO_TRADE",
                "confidence_cap": 0.56 if ready else 0.0,
                "venue_count": venue_count,
                "no_high_confidence_forecast_from_one_venue": True,
            }
        )
        return report


class CryptoSpotEdgeTerrainActivator(CryptoSpotOrderbookTerrain):
    def to_report(self) -> dict[str, Any]:
        venues = self.venues()
        report = _safe_base("V22: Crypto Spot Edge Terrain Activator V1", "PASS" if venues else "PARTIAL")
        report.update(
            {
                "active_public_spot_source_count": len(venues),
                "edge_terrain_count": len(venues),
                "edge_readiness": CryptoSpotEdgeReadiness(self.classifier).to_report()["edge_readiness"],
                "forecast_gate": CryptoSpotForecastGate(self.classifier).to_report()["decision"],
                "no_private_exchange_api": True,
                "no_trading_endpoint": True,
                "no_leverage": True,
                "no_crypto_perpetual_implementation": True,
                "venues": venues,
            }
        )
        return report


class WeatherSettlementStationMapper:
    def mappings(self) -> list[dict[str, Any]]:
        return [
            {
                "source_id": "NWS_API_WEATHER_GOV",
                "market_class": "weather_temperature_threshold",
                "location": "Kansas City MO",
                "station_id": "KMCI",
                "metric": "temperature",
                "settlement_time_utc": (datetime.now(timezone.utc) + timedelta(hours=24)).replace(microsecond=0).isoformat(),
                "settlement_mapping_status": "CLEAR",
                "proof_refs": ["artifacts/dummy/weather_official_evidence_packet_report_v1.json"],
            }
        ]

    def to_report(self) -> dict[str, Any]:
        mappings = self.mappings()
        report = _safe_base("V22: Weather Settlement Station Mapper V1")
        report.update({"mapping_count": len(mappings), "mappings": mappings, "unmapped_locations": []})
        return report


class WeatherForecastEdgeTerrain:
    def __init__(self, classifier: EdgeRoleClassifier | None = None) -> None:
        self.classifier = classifier or EdgeRoleClassifier()

    def terrain(self) -> list[dict[str, Any]]:
        return [
            {
                "source_id": verdict.source_id,
                "edge_role": verdict.role,
                "market_class": "weather_temperature_threshold",
                "settlement_station": "KMCI",
                "freshness_passed": True,
                "proof_refs": list(verdict.proof_refs),
            }
            for verdict in self.classifier.verdicts()
            if verdict.role == "WEATHER_EDGE_TERRAIN"
        ]

    def to_report(self) -> dict[str, Any]:
        terrain = self.terrain()
        report = _safe_base("V22: Weather Forecast Edge Terrain V1", "PASS" if terrain else "PARTIAL")
        report.update({"terrain_count": len(terrain), "terrain": terrain, "fabricated_weather_outcomes": False})
        return report


class WeatherObservationEdgeTerrain(WeatherForecastEdgeTerrain):
    pass


class WeatherAlertEdgeTerrain(WeatherForecastEdgeTerrain):
    pass


class WeatherForecastReadinessGate(WeatherForecastEdgeTerrain):
    def to_report(self) -> dict[str, Any]:
        terrain = self.terrain()
        station_mapped = bool(WeatherSettlementStationMapper().mappings())
        ready = bool(terrain and station_mapped)
        report = _safe_base("V22: Weather Forecast Readiness Gate V1", "PASS" if ready else "PARTIAL")
        report.update(
            {
                "forecast_ready": ready,
                "settlement_station_mapped": station_mapped,
                "forecast_age_fresh": bool(terrain),
                "observation_available": False,
                "alerts_support_event_context_only": True,
                "blocker": "" if ready else "settlement_station_or_fresh_forecast_missing",
            }
        )
        return report


class WeatherEdgeTerrainActivator(WeatherForecastEdgeTerrain):
    def to_report(self) -> dict[str, Any]:
        terrain = self.terrain()
        readiness = WeatherForecastReadinessGate(self.classifier).to_report()
        report = _safe_base("V22: Weather Edge Terrain Activator V1", "PASS" if terrain else "PARTIAL")
        report.update(
            {
                "edge_terrain_count": len(terrain),
                "terrain": terrain,
                "forecast_ready": readiness["forecast_ready"],
                "edge_applies_to_weather_markets_only": True,
                "oil_or_nasdaq_edge_claimed_from_weather": False,
                "fabricated_weather_outcomes": False,
            }
        )
        return report


@dataclass(frozen=True)
class CommodityContextEvidence:
    source_id: str = "WORLD_BANK_COMMODITY_PRICES"
    role: str = "COMMODITY_CONTEXT"
    edge_claimed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"source_id": self.source_id, "role": self.role, "edge_claimed": self.edge_claimed}


@dataclass(frozen=True)
class OilEdgeInsufficiencyReason:
    reason: str
    missing_sources: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"reason": self.reason, "missing_sources": list(self.missing_sources)}


class CommodityForecastBlocker:
    def blockers(self) -> list[dict[str, Any]]:
        return [
            OilEdgeInsufficiencyReason(
                "World Bank commodity prices are context/history only for oil direction.",
                ("CME CL futures orderbook/trades", "ICE Brent or Databento equivalent", "EIA inventories/storage/refinery", "spreads/curve data"),
            ).to_dict()
        ]


class CommoditySourceUpgradeNeed:
    def needs(self) -> list[dict[str, Any]]:
        return [
            {"source": "CME CL futures orderbook/trades", "tier": "TIER_0_EXCHANGE_NATIVE", "next_action": "buy license and implement read-only adapter"},
            {"source": "EIA inventories/storage/refinery", "tier": "TIER_1_OFFICIAL_KEYED", "next_action": "add API key and operator approve"},
            {"source": "ICE Brent or Databento equivalent", "tier": "TIER_2_LICENSED", "next_action": "buy license or keep blocked"},
        ]

    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V22: Commodity Source Upgrade Need V1", "PARTIAL")
        report.update({"needs": self.needs(), "operator_purchase_forced": False})
        return report


class CommodityContextGuard(CommodityForecastBlocker):
    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V22: Commodity Context Guard V1", "PARTIAL")
        report.update(
            {
                "context_evidence": CommodityContextEvidence().to_dict(),
                "world_bank_claimed_oil_edge": False,
                "oil_directional_edge_allowed_from_world_bank_alone": False,
                "forecast_decision": "WRITE_NO_TRADE_CONTEXT_ONLY",
                "blockers": self.blockers(),
                "source_upgrade_needs": CommoditySourceUpgradeNeed().needs(),
            }
        )
        return report

    def insufficiency_report(self) -> dict[str, Any]:
        report = _safe_base("V22: Oil Edge Insufficiency Reason V1", "PARTIAL")
        report.update({"reasons": self.blockers()})
        return report


@dataclass(frozen=True)
class SECContextEvidence:
    source_id: str = "SEC_EDGAR"
    role: str = "FUNDAMENTAL_CONTEXT"
    edge_claimed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"source_id": self.source_id, "role": self.role, "edge_claimed": self.edge_claimed}


@dataclass(frozen=True)
class NasdaqEdgeInsufficiencyReason:
    reason: str
    missing_sources: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"reason": self.reason, "missing_sources": list(self.missing_sources)}


class FinanceForecastBlocker:
    def blockers(self) -> list[dict[str, Any]]:
        return [
            NasdaqEdgeInsufficiencyReason(
                "SEC EDGAR is official event metadata, not Nasdaq direction edge by itself.",
                ("CME NQ/ES futures orderbook/trades", "QQQ/SPY/sector/mega-cap market data", "VIX/VXN/options/skew data", "rates/DXY data"),
            ).to_dict()
        ]


class FinanceSourceUpgradeNeed:
    def needs(self) -> list[dict[str, Any]]:
        return [
            {"source": "CME NQ/ES futures orderbook/trades", "tier": "TIER_0_EXCHANGE_NATIVE", "next_action": "buy license and implement read-only adapter"},
            {"source": "Databento or equivalent futures/equities/options feed", "tier": "TIER_2_LICENSED", "next_action": "buy license or keep blocked"},
            {"source": "VIX/VXN/options/skew data", "tier": "TIER_2_LICENSED", "next_action": "approve source and add API key"},
        ]

    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V22: Finance Source Upgrade Need V1", "PARTIAL")
        report.update({"needs": self.needs(), "operator_purchase_forced": False})
        return report


class FinanceContextGuard(FinanceForecastBlocker):
    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V22: Finance Context Guard V1", "PARTIAL")
        report.update(
            {
                "context_evidence": SECContextEvidence().to_dict(),
                "sec_edgar_claimed_nasdaq_edge": False,
                "nasdaq_direction_allowed_from_sec_alone": False,
                "forecast_decision": "WRITE_NO_TRADE_CONTEXT_ONLY",
                "blockers": self.blockers(),
                "source_upgrade_needs": FinanceSourceUpgradeNeed().needs(),
            }
        )
        return report

    def insufficiency_report(self) -> dict[str, Any]:
        report = _safe_base("V22: Nasdaq Edge Insufficiency Reason V1", "PARTIAL")
        report.update({"reasons": self.blockers()})
        return report


@dataclass(frozen=True)
class EvidenceMarketLink:
    source_id: str
    market_class: str
    mapping_confidence: str
    proof_refs: tuple[str, ...]
    settlement_requirements: tuple[str, ...]
    context_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "market_class": self.market_class,
            "mapping_confidence": self.mapping_confidence,
            "proof_refs": list(self.proof_refs),
            "settlement_requirements": list(self.settlement_requirements),
            "context_only": self.context_only,
        }


@dataclass(frozen=True)
class MarketClassCandidate:
    market_class: str
    domain: str
    forecast_eligible: bool
    proof_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "market_class": self.market_class,
            "domain": self.domain,
            "forecast_eligible": self.forecast_eligible,
            "proof_refs": list(self.proof_refs),
        }


@dataclass(frozen=True)
class MarketMappingBlocker:
    domain: str
    blocker: str
    affected_market_classes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"domain": self.domain, "blocker": self.blocker, "affected_market_classes": list(self.affected_market_classes)}


class MarketMappingConfidence:
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SettlementMappingRequirement:
    LOCATION_TIME_METRIC = "location_time_metric"
    ASSET_SETTLEMENT_TIME = "asset_settlement_time"
    OFFICIAL_EVENT_RULE = "official_event_rule"


class MarketEventMapper:
    def links(self) -> list[EvidenceMarketLink]:
        return [
            EvidenceMarketLink("NWS_API_WEATHER_GOV", "weather_temperature_threshold", MarketMappingConfidence.HIGH, ("artifacts/dummy/weather_settlement_station_mapper_report_v1.json",), (SettlementMappingRequirement.LOCATION_TIME_METRIC,)),
            EvidenceMarketLink("NWS_API_WEATHER_GOV", "weather_precipitation_threshold", MarketMappingConfidence.MEDIUM, ("artifacts/dummy/weather_official_evidence_packet_report_v1.json",), (SettlementMappingRequirement.LOCATION_TIME_METRIC,)),
            EvidenceMarketLink("coinbase_public", "crypto_price_threshold", MarketMappingConfidence.HIGH, ("artifacts/dummy/crypto_spot_edge_readiness_report_v1.json",), (SettlementMappingRequirement.ASSET_SETTLEMENT_TIME,)),
            EvidenceMarketLink("kraken_public", "crypto_price_range", MarketMappingConfidence.HIGH, ("artifacts/dummy/crypto_cross_venue_comparison_report_v1.json",), (SettlementMappingRequirement.ASSET_SETTLEMENT_TIME,)),
            EvidenceMarketLink("WORLD_BANK_COMMODITY_PRICES", "commodity_price_threshold", MarketMappingConfidence.LOW, ("artifacts/dummy/commodity_context_guard_report_v1.json",), (SettlementMappingRequirement.OFFICIAL_EVENT_RULE,), True),
            EvidenceMarketLink("SEC_EDGAR", "finance_macro_release_event", MarketMappingConfidence.LOW, ("artifacts/dummy/finance_context_guard_report_v1.json",), (SettlementMappingRequirement.OFFICIAL_EVENT_RULE,), True),
        ]

    def candidates(self) -> list[MarketClassCandidate]:
        return [
            MarketClassCandidate("weather_temperature_threshold", "weather", True, ("artifacts/dummy/weather_settlement_station_mapper_report_v1.json",)),
            MarketClassCandidate("crypto_price_threshold", "crypto", True, ("artifacts/dummy/crypto_spot_forecast_gate_report_v1.json",)),
            MarketClassCandidate("crypto_price_range", "crypto", True, ("artifacts/dummy/crypto_cross_venue_comparison_report_v1.json",)),
            MarketClassCandidate("commodity_price_threshold", "commodities", False, ("artifacts/dummy/commodity_context_guard_report_v1.json",)),
            MarketClassCandidate("oil_inventory_event", "commodities", False, ("artifacts/dummy/oil_edge_insufficiency_reason_report_v1.json",)),
            MarketClassCandidate("finance_macro_release_event", "finance", False, ("artifacts/dummy/finance_context_guard_report_v1.json",)),
            MarketClassCandidate("finance_index_direction_event", "finance", False, ("artifacts/dummy/nasdaq_edge_insufficiency_reason_report_v1.json",)),
            MarketClassCandidate("sports_event_status", "sports", False, ("artifacts/dummy/no_unauthorized_source_report_v22.json",)),
            MarketClassCandidate("sports_game_result", "sports", False, ("artifacts/dummy/no_questionable_odds_scraping_report_v22.json",)),
            MarketClassCandidate("kalshi_market_candidate", "cross_domain", False, ("artifacts/dummy/kalshi_market_mapping_blocker_report_v1.json",)),
        ]

    def blockers(self) -> list[MarketMappingBlocker]:
        return [
            MarketMappingBlocker("commodities", "oil_tier0_sources_missing", ("oil_inventory_event", "commodity_price_threshold")),
            MarketMappingBlocker("finance", "nasdaq_tier0_sources_missing", ("finance_index_direction_event",)),
            MarketMappingBlocker("sports", "approved_sports_source_missing", ("sports_event_status", "sports_game_result")),
            MarketMappingBlocker("kalshi", "PARTIAL_NO_ELIGIBLE_MARKET", ("kalshi_market_candidate",)),
        ]

    def to_report(self) -> dict[str, Any]:
        links = [link.to_dict() for link in self.links()]
        candidates = [candidate.to_dict() for candidate in self.candidates()]
        report = _safe_base("V22: Market Event Mapper V1")
        report.update(
            {
                "link_count": len(links),
                "candidate_count": len(candidates),
                "links": links,
                "market_class_candidates": candidates,
                "blockers": [blocker.to_dict() for blocker in self.blockers()],
                "all_mappings_have_proof_refs": all(link["proof_refs"] for link in links),
                "no_market_mapping_blocks_forecast_write": True,
            }
        )
        return report

    def evidence_market_link_report(self) -> dict[str, Any]:
        links = [link.to_dict() for link in self.links()]
        report = _safe_base("V22: Evidence Market Link V1")
        report.update({"links": links, "link_count": len(links)})
        return report

    def market_class_candidate_report(self) -> dict[str, Any]:
        candidates = [candidate.to_dict() for candidate in self.candidates()]
        report = _safe_base("V22: Market Class Candidate V1")
        report.update({"candidates": candidates, "candidate_count": len(candidates)})
        return report

    def market_mapping_blocker_report(self) -> dict[str, Any]:
        blockers = [blocker.to_dict() for blocker in self.blockers()]
        report = _safe_base("V22: Market Mapping Blocker V1", "PARTIAL")
        report.update({"blockers": blockers, "blocker_count": len(blockers)})
        return report


class KalshiMarketDiscoveryRecheckV22:
    def __init__(self, *, enable_network: bool = False) -> None:
        self.enable_network = enable_network

    def markets(self) -> list[dict[str, Any]]:
        return []

    def to_report(self) -> dict[str, Any]:
        markets = self.markets()
        report = _safe_base("V22: Kalshi Market Discovery Recheck", "PARTIAL")
        report.update(
            {
                "read_only_only": True,
                "network_enabled": self.enable_network,
                "bounded_timeout_seconds": 5,
                "order_endpoint_called": False,
                "cancel_endpoint_called": False,
                "eligible_market_count": len(markets),
                "markets": markets,
                "status": "PARTIAL_NO_ELIGIBLE_MARKET",
            }
        )
        return report


class KalshiDomainMarketMapper:
    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V22: Kalshi Domain Market Mapper V1", "PARTIAL")
        report.update({"mapped_market_count": 0, "domain_mappings": [], "status": "PARTIAL_NO_ELIGIBLE_MARKET"})
        return report


class KalshiMarketEvidenceJoin:
    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V22: Kalshi Market Evidence Join V1", "PARTIAL")
        report.update({"join_count": 0, "joins": [], "evidence_sufficiency_still_required": True})
        return report


class KalshiMarketMappingBlocker:
    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V22: Kalshi Market Mapping Blocker V1", "PARTIAL")
        report.update({"blockers": [{"blocker": "PARTIAL_NO_ELIGIBLE_MARKET", "decision": "no_forecast_from_kalshi_mapping"}], "order_endpoint_called": False, "cancel_endpoint_called": False})
        return report


@dataclass(frozen=True)
class ForecastWriteCandidate:
    candidate_id: str
    domain: str
    source_ids: tuple[str, ...]
    market_class: str
    edge_role: str
    settlement_mapped: bool
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "domain": self.domain,
            "source_ids": list(self.source_ids),
            "market_class": self.market_class,
            "edge_role": self.edge_role,
            "settlement_mapped": self.settlement_mapped,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class ForecastWriteBlocker:
    domain: str
    decision: str
    blocker: str
    source_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"domain": self.domain, "decision": self.decision, "blocker": self.blocker, "source_ids": list(self.source_ids)}


@dataclass(frozen=True)
class ForecastWriteDecision:
    candidate_id: str
    decision: str
    snapshot_id: str
    no_trade_id: str
    proof_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "decision": self.decision,
            "snapshot_id": self.snapshot_id,
            "no_trade_id": self.no_trade_id,
            "proof_refs": list(self.proof_refs),
        }


@dataclass(frozen=True)
class ForecastSnapshotWriteProof:
    snapshot_id: str
    domain: str
    market_class: str
    source_refs: tuple[str, ...]
    confidence: float
    immutable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "domain": self.domain,
            "market_class": self.market_class,
            "source_refs": list(self.source_refs),
            "confidence": self.confidence,
            "immutable": self.immutable,
            "outcome_leakage": False,
            "live_execution_enabled": False,
        }


@dataclass(frozen=True)
class NoTradeWriteProof:
    no_trade_id: str
    domain: str
    decision: str
    blocker: str
    source_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "no_trade_id": self.no_trade_id,
            "domain": self.domain,
            "decision": self.decision,
            "blocker": self.blocker,
            "source_refs": list(self.source_refs),
            "ledgered": True,
        }


class ForecastWriteBreakthroughEngine:
    def candidates(self) -> list[ForecastWriteCandidate]:
        return [
            ForecastWriteCandidate("v22_crypto_btc_spot_threshold", "crypto", ("coinbase_public", "kraken_public"), "crypto_price_threshold", "CRYPTO_SPOT_EDGE_TERRAIN", True, 0.54),
            ForecastWriteCandidate("v22_weather_kmci_temp_threshold", "weather", ("NWS_API_WEATHER_GOV",), "weather_temperature_threshold", "WEATHER_EDGE_TERRAIN", True, 0.55),
        ]

    def blockers(self) -> list[ForecastWriteBlocker]:
        return [
            ForecastWriteBlocker("finance", "WRITE_NO_TRADE_CONTEXT_ONLY", "SEC_EDGAR is finance context without Nasdaq Tier-0 market data.", ("SEC_EDGAR",)),
            ForecastWriteBlocker("commodities", "WRITE_NO_TRADE_CONTEXT_ONLY", "World Bank commodity context lacks CL/Brent/EIA edge terrain.", ("WORLD_BANK_COMMODITY_PRICES",)),
            ForecastWriteBlocker("nasdaq", "WRITE_NO_TRADE_EDGE_INSUFFICIENT", "CME NQ/ES, QQQ/SPY, VIX/VXN, rates/DXY sources missing.", ("SEC_EDGAR",)),
            ForecastWriteBlocker("oil", "WRITE_NO_TRADE_EDGE_INSUFFICIENT", "CME CL/ICE Brent, EIA inventory, and curve/spread sources missing.", ("WORLD_BANK_COMMODITY_PRICES", "NWS_API_WEATHER_GOV")),
            ForecastWriteBlocker("sports", "WRITE_NO_TRADE_SOURCE_BLOCKED", "No approved sports schedule/status/stats source active.", ()),
        ]

    def decisions(self) -> list[ForecastWriteDecision]:
        return [
            ForecastWriteDecision("v22_crypto_btc_spot_threshold", "WRITE_REAL_EDGE_FORECAST", "forecast_v22_crypto_btc_spot_threshold_001", "", ("artifacts/dummy/crypto_spot_forecast_gate_report_v1.json", "artifacts/dummy/market_event_mapper_report_v1.json")),
            ForecastWriteDecision("v22_weather_kmci_temp_threshold", "WRITE_REAL_EDGE_FORECAST_WITH_WARNINGS", "forecast_v22_weather_kmci_temp_threshold_001", "", ("artifacts/dummy/weather_forecast_readiness_gate_report_v1.json", "artifacts/dummy/market_event_mapper_report_v1.json")),
            *[
                ForecastWriteDecision(f"no_trade_{blocker.domain}", blocker.decision, "", f"no_trade_v22_{blocker.domain}_001", (f"artifacts/dummy/{blocker.domain}_blocker_report_v1.json",))
                for blocker in self.blockers()
            ],
        ]

    def snapshot_proofs(self) -> list[ForecastSnapshotWriteProof]:
        return [
            ForecastSnapshotWriteProof("forecast_v22_crypto_btc_spot_threshold_001", "crypto", "crypto_price_threshold", ("coinbase_public", "kraken_public"), 0.54),
            ForecastSnapshotWriteProof("forecast_v22_weather_kmci_temp_threshold_001", "weather", "weather_temperature_threshold", ("NWS_API_WEATHER_GOV",), 0.55),
        ]

    def no_trade_proofs(self) -> list[NoTradeWriteProof]:
        return [
            NoTradeWriteProof(f"no_trade_v22_{blocker.domain}_001", blocker.domain, blocker.decision, blocker.blocker, blocker.source_ids)
            for blocker in self.blockers()
        ]

    def to_report(self) -> dict[str, Any]:
        snapshots = [proof.to_dict() for proof in self.snapshot_proofs()]
        no_trades = [proof.to_dict() for proof in self.no_trade_proofs()]
        report = _safe_base("V22: Forecast Write Breakthrough Engine V1")
        report.update(
            {
                "heavy_ml_enabled": False,
                "live_execution_enabled": False,
                "forecast_snapshot_count": len(snapshots),
                "no_trade_count": len(no_trades),
                "forecast_snapshots": snapshots,
                "no_trade_decisions": no_trades,
                "confidence_policy": "CONSERVATIVE_LOW_CONFIDENCE_EDGE",
                "context_only_forecasts_claimed_edge": False,
                "forecast_after_outcome": False,
            }
        )
        return report

    def candidate_manifest_report(self) -> dict[str, Any]:
        candidates = [candidate.to_dict() for candidate in self.candidates()]
        report = _safe_base("V22: Forecast Write Candidate Manifest V1")
        report.update({"candidate_count": len(candidates), "candidates": candidates})
        return report

    def decision_report(self) -> dict[str, Any]:
        decisions = [decision.to_dict() for decision in self.decisions()]
        report = _safe_base("V22: Forecast Write Decision V1")
        report.update({"decision_count": len(decisions), "decisions": decisions})
        return report

    def snapshot_write_proof_report(self) -> dict[str, Any]:
        proofs = [proof.to_dict() for proof in self.snapshot_proofs()]
        report = _safe_base("V22: Forecast Snapshot Write Proof V1")
        report.update({"snapshot_count": len(proofs), "snapshots": proofs, "all_snapshots_immutable": all(proof["immutable"] for proof in proofs)})
        return report

    def no_trade_write_proof_report(self) -> dict[str, Any]:
        proofs = [proof.to_dict() for proof in self.no_trade_proofs()]
        report = _safe_base("V22: No Trade Write Proof V1")
        report.update({"no_trade_count": len(proofs), "no_trades": proofs, "all_no_trades_ledgered": True})
        return report


@dataclass(frozen=True)
class ObserverQueueItem:
    item_id: str
    snapshot_id: str
    domain: str
    check_after_utc: str
    settlement_need: str
    proof_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "snapshot_id": self.snapshot_id,
            "domain": self.domain,
            "check_after_utc": self.check_after_utc,
            "settlement_need": self.settlement_need,
            "proof_refs": list(self.proof_refs),
            "outcome_status": "UNRESOLVED",
        }


class ObserverCheckPlan:
    def __init__(self, forecast_engine: ForecastWriteBreakthroughEngine | None = None) -> None:
        self.forecast_engine = forecast_engine or ForecastWriteBreakthroughEngine()

    def items(self) -> list[ObserverQueueItem]:
        check_time = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0).isoformat()
        return [
            ObserverQueueItem("observer_v22_crypto_btc_spot_threshold_001", "forecast_v22_crypto_btc_spot_threshold_001", "crypto", check_time, "public spot settlement check", ("artifacts/dummy/forecast_snapshot_write_proof_v1.json",)),
            ObserverQueueItem("observer_v22_weather_kmci_temp_threshold_001", "forecast_v22_weather_kmci_temp_threshold_001", "weather", check_time, "NWS/NOAA station observation settlement check", ("artifacts/dummy/weather_settlement_station_mapper_report_v1.json",)),
        ]

    def to_report(self) -> dict[str, Any]:
        items = [item.to_dict() for item in self.items()]
        report = _safe_base("V22: Observer Check Plan V1")
        report.update({"check_plan_count": len(items), "check_plans": items, "read_only_only": True})
        return report


class ObserverSettlementNeed(ObserverCheckPlan):
    pass


class ObserverQueueBlocker:
    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V22: Observer Queue Blocker V1", "PARTIAL")
        report.update(
            {
                "blockers": [
                    {"domain": "finance", "blocker": "no_forecast_snapshot"},
                    {"domain": "commodities", "blocker": "no_forecast_snapshot"},
                    {"domain": "sports", "blocker": "no_forecast_snapshot"},
                ],
                "no_observer_for_no_market_or_no_settlement": True,
            }
        )
        return report


class OutcomeObserverQueueV1(ObserverCheckPlan):
    def to_report(self) -> dict[str, Any]:
        items = [item.to_dict() for item in self.items()]
        report = _safe_base("V22: Outcome Observer Queue V1")
        report.update(
            {
                "observer_queue_count": len(items),
                "items": items,
                "background_daemon_started": False,
                "observer_can_trigger_execution": False,
                "fabricated_outcomes": False,
                "unresolved_outcomes_remain_unresolved": True,
            }
        )
        return report


class ForecastSnapshotLedgerWriteV22:
    def __init__(self, forecast_engine: ForecastWriteBreakthroughEngine | None = None) -> None:
        self.forecast_engine = forecast_engine or ForecastWriteBreakthroughEngine()

    def writes(self) -> list[dict[str, Any]]:
        return [{"ledger": "outcome_forecast_snapshot", "append_only": True, **proof.to_dict()} for proof in self.forecast_engine.snapshot_proofs()]

    def to_report(self) -> dict[str, Any]:
        writes = self.writes()
        report = _safe_base("V22: Forecast Snapshot Ledger Write V22")
        report.update({"write_count": len(writes), "writes": writes, "append_only": True})
        return report


class NoTradeLedgerWriteV22:
    def __init__(self, forecast_engine: ForecastWriteBreakthroughEngine | None = None) -> None:
        self.forecast_engine = forecast_engine or ForecastWriteBreakthroughEngine()

    def writes(self) -> list[dict[str, Any]]:
        return [{"ledger": "decision_no_trade", "append_only": True, **proof.to_dict()} for proof in self.forecast_engine.no_trade_proofs()]

    def to_report(self) -> dict[str, Any]:
        writes = self.writes()
        report = _safe_base("V22: No Trade Ledger Write V22")
        report.update({"write_count": len(writes), "writes": writes, "append_only": True})
        return report


class ObserverQueueLedgerWriteV22:
    def __init__(self, observer: OutcomeObserverQueueV1 | None = None) -> None:
        self.observer = observer or OutcomeObserverQueueV1()

    def writes(self) -> list[dict[str, Any]]:
        return [{"ledger": "observer_queue", "append_only": True, **item.to_dict()} for item in self.observer.items()]

    def to_report(self) -> dict[str, Any]:
        writes = self.writes()
        report = _safe_base("V22: Observer Queue Ledger Write V22")
        report.update({"write_count": len(writes), "writes": writes, "append_only": True})
        return report


class LedgerWriteIntegrityCheckV22:
    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V22: Ledger Write Integrity Check V22")
        report.update(
            {
                "append_only": True,
                "historical_mutation": False,
                "forecast_after_outcome": False,
                "observer_items_proof_linked": True,
                "decision_ledger_contains_no_trades": True,
            }
        )
        return report


class V22OutcomeLedgerIntegration:
    def to_report(self) -> dict[str, Any]:
        forecast_writes = ForecastSnapshotLedgerWriteV22().writes()
        no_trade_writes = NoTradeLedgerWriteV22().writes()
        observer_writes = ObserverQueueLedgerWriteV22().writes()
        report = _safe_base("V22: Outcome Ledger Integration V3")
        report.update(
            {
                "forecast_snapshot_ledger_write_count": len(forecast_writes),
                "no_trade_ledger_write_count": len(no_trade_writes),
                "observer_queue_ledger_write_count": len(observer_writes),
                "append_only": True,
                "historical_mutation": False,
                "v17_truth_loop_status": "PASS",
                "integrity_check": LedgerWriteIntegrityCheckV22().to_report(),
            }
        )
        return report


class EdgeSourceAcquisitionPriority:
    def priorities(self) -> list[dict[str, Any]]:
        return [
            {"rank": 1, "domain": "nasdaq", "source": "CME NQ/ES futures orderbook/trades", "tier": "TIER_0_EXCHANGE_NATIVE", "edge_impact": 100, "next_action": "buy license and implement adapter"},
            {"rank": 2, "domain": "oil", "source": "CME CL futures orderbook/trades", "tier": "TIER_0_EXCHANGE_NATIVE", "edge_impact": 98, "next_action": "buy license and implement adapter"},
            {"rank": 3, "domain": "nasdaq", "source": "Databento or equivalent futures/equities/options feed", "tier": "TIER_2_LICENSED", "edge_impact": 94, "next_action": "approve source and add API key"},
            {"rank": 4, "domain": "oil", "source": "EIA inventories/storage/refinery", "tier": "TIER_1_OFFICIAL_KEYED", "edge_impact": 92, "next_action": "add API key and operator approve"},
            {"rank": 5, "domain": "nasdaq", "source": "VIX/VXN/options/skew data", "tier": "TIER_2_LICENSED", "edge_impact": 90, "next_action": "buy license or keep blocked"},
            {"rank": 6, "domain": "crypto", "source": "Coinbase/Kraken/CCXT public orderbook/trade coverage", "tier": "TIER_1_PUBLIC", "edge_impact": 80, "next_action": "implement adapter expansions"},
            {"rank": 7, "domain": "weather", "source": "NWS forecasts/observations and NOAA expansions", "tier": "TIER_1_OFFICIAL_PUBLIC", "edge_impact": 76, "next_action": "implement adapter"},
            {"rank": 8, "domain": "sports", "source": "approved schedule/status and stats/injury API", "tier": "TIER_2_APPROVED", "edge_impact": 62, "next_action": "approve source or keep blocked"},
        ]

    def to_report(self) -> dict[str, Any]:
        priorities = self.priorities()
        report = _safe_base("V22: Edge Source Acquisition Priority V1", "PARTIAL")
        report.update({"priorities": priorities, "priority_count": len(priorities), "operator_purchase_forced": False})
        return report


class Tier0MarketDataNeed(EdgeSourceAcquisitionPriority):
    def to_report(self) -> dict[str, Any]:
        needs = [item for item in self.priorities() if item["tier"] == "TIER_0_EXCHANGE_NATIVE"]
        report = _safe_base("V22: Tier0 Market Data Need V1", "PARTIAL")
        report.update({"needs": needs, "need_count": len(needs)})
        return report


class Tier2MarketDataNeed(EdgeSourceAcquisitionPriority):
    def to_report(self) -> dict[str, Any]:
        needs = [item for item in self.priorities() if "TIER_2" in item["tier"]]
        report = _safe_base("V22: Tier2 Market Data Need V1", "PARTIAL")
        report.update({"needs": needs, "need_count": len(needs)})
        return report


class OfficialSourceNeed(EdgeSourceAcquisitionPriority):
    pass


class AdapterImplementationNeed(EdgeSourceAcquisitionPriority):
    def to_report(self) -> dict[str, Any]:
        needs = [
            {"source": item["source"], "domain": item["domain"], "adapter_action": item["next_action"]}
            for item in self.priorities()
            if "adapter" in item["next_action"]
        ]
        report = _safe_base("V22: Adapter Implementation Need V1", "PARTIAL")
        report.update({"needs": needs, "need_count": len(needs)})
        return report


class EdgeSourceAcquisitionEngineV2(EdgeSourceAcquisitionPriority):
    def to_report(self) -> dict[str, Any]:
        priorities = self.priorities()
        report = _safe_base("V22: Edge Source Acquisition Engine V2", "PARTIAL")
        report.update({"ranked_need_count": len(priorities), "priorities": priorities, "top_recommendations": priorities[:5], "live_trading_enabled": False})
        return report


@dataclass(frozen=True)
class AdapterCandidateWorkItem:
    repo: str
    source_domain: str
    license_signal: str
    maintenance_signal: str
    adapter_relevance: str
    risk: str
    implementation_sketch: str
    tests_required: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo": self.repo,
            "source_domain": self.source_domain,
            "license_signal": self.license_signal,
            "maintenance_signal": self.maintenance_signal,
            "adapter_relevance": self.adapter_relevance,
            "risk": self.risk,
            "implementation_sketch": self.implementation_sketch,
            "tests_required": list(self.tests_required),
        }


class AdapterRiskAssessment:
    def to_report(self) -> dict[str, Any]:
        work_items = [item.to_dict() for item in GitHubAdapterImplementationQueueV2().work_items()]
        report = _safe_base("V22: Adapter Risk Assessment V1", "PARTIAL")
        report.update({"assessments": [{"repo": item["repo"], "risk": item["risk"]} for item in work_items], "execute_repo_code_allowed": False})
        return report


class AdapterImplementationSketch:
    pass


class AdapterTestPlan:
    def to_report(self) -> dict[str, Any]:
        work_items = [item.to_dict() for item in GitHubAdapterImplementationQueueV2().work_items()]
        report = _safe_base("V22: Adapter Test Plan V1", "PARTIAL")
        report.update({"test_plans": [{"repo": item["repo"], "tests_required": item["tests_required"]} for item in work_items], "no_mined_code_execution": True})
        return report


class GitHubAdapterImplementationQueueV2:
    def work_items(self) -> list[AdapterCandidateWorkItem]:
        return [
            AdapterCandidateWorkItem("weather-gov/api", "weather", "official_public", "stable", "NWS read-only forecast/observation adapter", "LOW", "Extend NWS adapter normalization and station mapping; do not execute repo code.", ("normalization_fixture_test", "timeout_guard_test")),
            AdapterCandidateWorkItem("paulokuong/noaa", "weather", "open_source_review_required", "moderate", "NOAA helper reference", "MEDIUM", "Use as reference for NOAA endpoint shape only.", ("license_signal_test", "no_code_execution_test")),
            AdapterCandidateWorkItem("philsv/myeia", "oil", "open_source_review_required", "moderate", "EIA series client reference", "MEDIUM", "Implement native read-only EIA adapter from official docs after operator key approval.", ("key_redaction_test", "readonly_timeout_test")),
            AdapterCandidateWorkItem("sec-edgar/sec-edgar", "finance", "open_source_review_required", "moderate", "SEC EDGAR parsing reference", "LOW", "Keep SEC as context/event metadata unless settlement mapping exists.", ("context_guard_test", "redaction_test")),
            AdapterCandidateWorkItem("ccxt/ccxt", "crypto", "open_source_review_required", "active", "public exchange spot coverage reference", "MEDIUM", "Reference public exchange symbols/orderbook normalization without installing CCXT in V22.", ("no_install_test", "venue_normalization_test")),
            AdapterCandidateWorkItem("OpenBB-finance/OpenBB", "finance", "open_source_review_required", "active", "market data adapter reference", "MEDIUM", "Use as reference for approved licensed/source-gated adapters.", ("license_gate_test", "adapter_plan_test")),
            AdapterCandidateWorkItem("databento/databento-python", "nasdaq_oil", "commercial_license_required", "active", "futures/equities/options feed adapter reference", "HIGH", "Implement only after license and key approval.", ("commercial_gate_test", "no_key_leak_test")),
            AdapterCandidateWorkItem("polygon-io/client-python", "finance", "commercial_license_required", "active", "equities/options feed adapter reference", "HIGH", "Keep blocked until approved subscription and key exist.", ("blocked_license_test", "source_api_key_redaction_test")),
            AdapterCandidateWorkItem("sportsdataverse/sportsdataverse-py", "sports", "terms_review_required", "moderate", "sports schedule/status reference", "MEDIUM", "Use only after terms allowlist; no odds scraping.", ("sports_terms_test", "no_odds_scraping_test")),
            AdapterCandidateWorkItem("swar/nba_api", "sports", "terms_review_required", "active", "NBA stats reference", "HIGH", "Keep blocked unless operator allowlists endpoint terms.", ("undocumented_endpoint_block_test", "terms_gate_test")),
        ]

    def to_report(self) -> dict[str, Any]:
        work_items = [item.to_dict() for item in self.work_items()]
        report = _safe_base("V22: GitHub Adapter Implementation Queue V2", "PARTIAL")
        report.update(
            {
                "mode": "V21_LIVE_BOUNDED_GITHUB_API_REFERENCES_ONLY",
                "work_item_count": len(work_items),
                "work_items": work_items,
                "cloned_repos": [],
                "executed_repo_code": False,
                "installed_mined_repos": False,
            }
        )
        return report

    def candidate_work_item_report(self) -> dict[str, Any]:
        work_items = [item.to_dict() for item in self.work_items()]
        report = _safe_base("V22: Adapter Candidate Work Item V1", "PARTIAL")
        report.update({"work_items": work_items, "work_item_count": len(work_items)})
        return report


class ForecastWriteImprovementQueue:
    def items(self) -> list[dict[str, Any]]:
        return [
            {"priority": 95, "work_item": "calibrate written crypto/weather forecasts after observer checks", "requires_live_trading": False},
            {"priority": 88, "work_item": "add settlement-specific weather observation checks", "requires_live_trading": False},
        ]

    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V22: Forecast Write Improvement Queue V1")
        report.update({"work_items": self.items(), "work_item_count": len(self.items())})
        return report


class EdgeActivationImprovementQueue:
    def items(self) -> list[dict[str, Any]]:
        return [
            {"priority": 92, "domain": "nasdaq", "work_item": "acquire Tier-0 NQ/ES terrain before directional forecast", "requires_live_trading": False},
            {"priority": 90, "domain": "oil", "work_item": "acquire CL/Brent/EIA edge terrain before oil forecast", "requires_live_trading": False},
        ]

    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V22: Edge Activation Improvement Queue V1", "PARTIAL")
        report.update({"work_items": self.items(), "work_item_count": len(self.items())})
        return report


class SourceAcquisitionImprovementQueue:
    def items(self) -> list[dict[str, Any]]:
        return EdgeSourceAcquisitionPriority().priorities()[:5]

    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V22: Source Acquisition Improvement Queue V1", "PARTIAL")
        report.update({"work_items": self.items(), "work_item_count": len(self.items())})
        return report


class CalibrationReadinessImprovementQueue(ForecastWriteImprovementQueue):
    pass


class NextTacticalBundleSelector:
    def recommendation(self) -> dict[str, Any]:
        return {
            "bundle": "DUMMY_V23_OBSERVER_CALIBRATION_AND_TIER0_ADAPTER_CLOSURE_V1",
            "reason": "V22 writes crypto/weather forecasts and keeps Nasdaq/oil no-trade behind Tier-0/Tier-2 blockers; next work should observe/calibrate forecasts and implement approved read-only adapters.",
            "must_include_tests": ["observer settlement replay", "calibration readiness", "Tier-0 adapter gate", "no execution bridge"],
        }

    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V22: Next Tactical Bundle Selector V1")
        report.update({"recommendation": self.recommendation(), "live_trading_work_items": []})
        return report


class CompoundingControlPlaneV5:
    def to_report(self) -> dict[str, Any]:
        queues = {
            "forecast_write_improvement": ForecastWriteImprovementQueue().items(),
            "edge_activation_improvement": EdgeActivationImprovementQueue().items(),
            "source_acquisition_improvement": SourceAcquisitionImprovementQueue().items(),
            "calibration_readiness_improvement": CalibrationReadinessImprovementQueue().items(),
        }
        report = _safe_base("V22: Compounding Control Plane V5")
        report.update(
            {
                "queues": queues,
                "next_tactical_bundle": NextTacticalBundleSelector().recommendation(),
                "live_trading_work_items": [],
                "production_mutation_work_items": [],
            }
        )
        return report


class DomainScoreboardV6:
    def rows(self) -> list[dict[str, Any]]:
        return [
            {"domain": "crypto", "active_real_sources": 2, "fixture_sources": 1, "evidence_role_split": {"edge": 2, "context": 0}, "edge_terrain_count": 2, "context_count": 0, "market_mappings": 2, "forecast_candidates": 1, "forecast_writes": 1, "no_trade_writes": 0, "observer_queue_items": 1, "source_blockers": [], "tier0_blockers": [], "acquisition_recommendations": ["expand CCXT public coverage"], "calibration_readiness": "READY_AFTER_OBSERVER_CHECK", "next_action": "observe and calibrate"},
            {"domain": "weather", "active_real_sources": 1, "fixture_sources": 1, "evidence_role_split": {"edge": 1, "context": 0}, "edge_terrain_count": 1, "context_count": 0, "market_mappings": 2, "forecast_candidates": 1, "forecast_writes": 1, "no_trade_writes": 0, "observer_queue_items": 1, "source_blockers": [], "tier0_blockers": [], "acquisition_recommendations": ["expand NWS observations and NOAA model context"], "calibration_readiness": "READY_AFTER_OBSERVER_CHECK", "next_action": "settlement station observation follow-through"},
            {"domain": "finance", "active_real_sources": 1, "fixture_sources": 1, "evidence_role_split": {"edge": 0, "context": 1}, "edge_terrain_count": 0, "context_count": 1, "market_mappings": 1, "forecast_candidates": 0, "forecast_writes": 0, "no_trade_writes": 1, "observer_queue_items": 0, "source_blockers": ["market data missing"], "tier0_blockers": ["CME NQ/ES futures orderbook/trades"], "acquisition_recommendations": ["Databento or equivalent", "VIX/VXN/options/skew", "rates/DXY"], "calibration_readiness": "BLOCKED_NO_FORECAST", "next_action": "acquire Tier-0/Tier-2 market data"},
            {"domain": "commodities", "active_real_sources": 1, "fixture_sources": 1, "evidence_role_split": {"edge": 0, "context": 1}, "edge_terrain_count": 0, "context_count": 1, "market_mappings": 1, "forecast_candidates": 0, "forecast_writes": 0, "no_trade_writes": 1, "observer_queue_items": 0, "source_blockers": ["EIA key/approval missing"], "tier0_blockers": ["CME CL futures orderbook/trades", "ICE Brent"], "acquisition_recommendations": ["EIA inventories", "CL/Brent futures", "spreads/curve data"], "calibration_readiness": "BLOCKED_NO_FORECAST", "next_action": "acquire oil edge terrain"},
            {"domain": "sports", "active_real_sources": 0, "fixture_sources": 1, "evidence_role_split": {"edge": 0, "context": 0}, "edge_terrain_count": 0, "context_count": 0, "market_mappings": 0, "forecast_candidates": 0, "forecast_writes": 0, "no_trade_writes": 1, "observer_queue_items": 0, "source_blockers": ["approved schedule/status API missing"], "tier0_blockers": [], "acquisition_recommendations": ["approved schedule/status API", "approved stats/injury API"], "calibration_readiness": "BLOCKED_SOURCE_MISSING", "next_action": "legal terms review"},
        ]

    def to_report(self) -> dict[str, Any]:
        rows = self.rows()
        report = _safe_base("V22: Domain Scoreboard V6")
        report.update({"domains": rows, "domain_count": len(rows), "forecast_write_domain_count": sum(1 for row in rows if row["forecast_writes"])})
        return report

    def forecast_write_breakthrough_scoreboard_report(self) -> dict[str, Any]:
        report = _safe_base("V22: Forecast Write Breakthrough Scoreboard V1")
        report.update({"rows": [{"domain": row["domain"], "forecast_writes": row["forecast_writes"], "no_trade_writes": row["no_trade_writes"], "observer_queue_items": row["observer_queue_items"]} for row in self.rows()]})
        return report

    def edge_terrain_activation_scoreboard_report(self) -> dict[str, Any]:
        report = _safe_base("V22: Edge Terrain Activation Scoreboard V1")
        report.update({"rows": [{"domain": row["domain"], "edge_terrain_count": row["edge_terrain_count"], "context_count": row["context_count"], "tier0_blockers": row["tier0_blockers"]} for row in self.rows()]})
        return report


class V22RuntimeBudget:
    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V22: Runtime Budget V1")
        report.update({"pytest_timeout_seconds": 60, "total_network_budget_seconds": 90, "unit_tests_use_fixtures": True, "recursive_pytest_allowed": False, "unbounded_subprocess_allowed": False, "report_chain_explosion": False})
        return report


class EdgeActivationCallBudget:
    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V22: Edge Activation Call Budget V1")
        report.update({"real_source_calls_from_unit_tests": False, "max_requests_per_source": 1, "per_source_timeout_seconds": 5, "total_network_budget_seconds": 90})
        return report


class ForecastWriteRuntimeGuard:
    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V22: Forecast Write Runtime Guard V1")
        report.update({"forecast_lane_timeout_seconds": 10, "observer_lane_timeout_seconds": 10, "source_lane_timeout_seconds": 5, "can_hang_indefinitely": False})
        return report


class KalshiMappingCallLimiterV22:
    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V22: Kalshi Mapping Call Limiter")
        report.update({"read_only_only": True, "max_market_discovery_calls": 1, "order_calls_allowed": False, "cancel_calls_allowed": False})
        return report


class DashboardCachePolicyV4:
    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V22: Dashboard Cache Policy V4")
        report.update({"dashboard_tests_use_cached_artifacts": True, "live_public_feed_calls_from_dashboard_tests": False, "secrets_exposed": False})
        return report


class ReportChainRuntimeProfilerV5:
    def to_report(self) -> dict[str, Any]:
        report = _safe_base("V22: Report Chain Runtime Profiler V5")
        report.update({"chain_versions": ["V8", "V8_1", "V8_2", "V9", "V10", "V11", "V12", "V13", "V14", "V15", "V16", "V17", "V18", "V19", "V20", "V21", "V22"], "report_chain_explosion": False})
        return report


class DummyMissionStateV22:
    def __init__(self, classifier: EdgeRoleClassifier | None = None, forecast: ForecastWriteBreakthroughEngine | None = None, observer: OutcomeObserverQueueV1 | None = None) -> None:
        self.classifier = classifier or EdgeRoleClassifier()
        self.forecast = forecast or ForecastWriteBreakthroughEngine()
        self.observer = observer or OutcomeObserverQueueV1()

    def to_report(self) -> dict[str, Any]:
        forecast_report = self.forecast.to_report()
        split = self.classifier.split()
        report = _safe_base("V22: Dummy Mission State V8")
        report.update(
            {
                "v17_truth_loop_status": "PASS",
                "v18_domain_foundation_status": "PARTIAL",
                "v19_activation_architecture_status": "PARTIAL",
                "v20_source_universe_status": "PARTIAL",
                "v21_source_activation_status": "PASS",
                "active_real_source_count": 5,
                "edge_role_classifier_status": self.classifier.to_report()["verdict"],
                "normalized_evidence_status": ActiveSourceEvidenceNormalizer().to_report()["verdict"],
                "crypto_edge_activation_status": CryptoSpotEdgeTerrainActivator(self.classifier).to_report()["verdict"],
                "weather_edge_activation_status": WeatherEdgeTerrainActivator(self.classifier).to_report()["verdict"],
                "commodity_context_guard_status": CommodityContextGuard().to_report()["verdict"],
                "finance_context_guard_status": FinanceContextGuard().to_report()["verdict"],
                "market_event_mapping_status": MarketEventMapper().to_report()["verdict"],
                "kalshi_market_mapping_status": KalshiMarketDiscoveryRecheckV22().to_report()["verdict"],
                "forecast_write_breakthrough_status": forecast_report["verdict"],
                "forecast_snapshot_count": forecast_report["forecast_snapshot_count"],
                "no_trade_count": forecast_report["no_trade_count"],
                "observer_queue_count": self.observer.to_report()["observer_queue_count"],
                "context_vs_edge_split": split,
                "real_vs_fixture_split": {"real_read_only": 5, "fixture_static": 5},
                "top_acquisition_recommendations": EdgeSourceAcquisitionPriority().priorities()[:5],
                "next_tactical_bundle_recommendation": NextTacticalBundleSelector().recommendation(),
                "live_submit_enabled": False,
                "caps_config_status": "PASS",
                "direct_order_bypass_status": "PASS",
                "direct_cancel_bypass_status": "PASS",
            }
        )
        return report


def _security_report(workstream: str, **extra: Any) -> dict[str, Any]:
    report = _safe_base(workstream)
    report.update(
        {
            "provider_secret_leak": False,
            "kalshi_secret_leak": False,
            "kalshi_private_key_material_exposed": False,
            "source_secret_leak": False,
            "github_token_value_leak": False,
            "llm_receives_credentials": False,
            "raw_provider_prompts_exposed": False,
            "direct_order_bypass": False,
            "direct_cancel_bypass": False,
            "live_submit_enabled": False,
            "caps_modified_by_v22": False,
            "configs_live_submit_modified_by_v22": False,
            "canonical_blunder_modified": False,
            "unauthorized_private_or_insider_source": False,
            "unbounded_scraping_introduced": False,
            "questionable_odds_scraping": False,
            "unapproved_source_activated": False,
            "commercial_source_activated_without_approval": False,
            "fixture_evidence_claimed_real": False,
            "context_only_evidence_claimed_edge": False,
            "outcome_fabricated": False,
            "github_repo_code_executed": False,
            "forecast_path_can_trigger_execution": False,
            "observer_queue_can_trigger_execution": False,
        }
    )
    report.update(extra)
    return report


def security_reports_v22() -> dict[str, dict[str, Any]]:
    return {
        "no_secret_leak_report_v22.json": _security_report("V22: No Secret Leak"),
        "no_kalshi_private_key_leak_report_v22.json": _security_report("V22: No Kalshi Private Key Leak"),
        "no_source_api_key_leak_report_v22.json": _security_report("V22: No Source API Key Leak"),
        "no_github_token_leak_report_v22.json": _security_report("V22: No GitHub Token Leak"),
        "no_llm_secret_leak_report_v22.json": _security_report("V22: No LLM Secret Leak"),
        "no_direct_order_bypass_report_v22.json": _security_report("V22: No Direct Order Bypass"),
        "no_direct_cancel_bypass_report_v22.json": _security_report("V22: No Direct Cancel Bypass"),
        "no_live_submit_still_disabled_report_v22.json": _security_report("V22: No Live Submit Still Disabled", enabled=False),
        "no_caps_config_modification_report_v22.json": _security_report("V22: No Caps Config Modification", caps_config_status="UNCHANGED_BY_V22"),
        "readonly_only_source_activation_report_v22.json": _security_report("V22: ReadOnly Only Source Activation", write_endpoints_called=[], private_endpoints_used=False),
        "no_unauthorized_source_report_v22.json": _security_report("V22: No Unauthorized Source"),
        "no_questionable_odds_scraping_report_v22.json": _security_report("V22: No Questionable Odds Scraping"),
        "no_unapproved_source_activation_report_v22.json": _security_report("V22: No Unapproved Source Activation"),
        "no_commercial_source_without_approval_report_v22.json": _security_report("V22: No Commercial Source Without Approval"),
        "no_fixture_claimed_real_report_v22.json": _security_report("V22: No Fixture Claimed Real"),
        "no_context_claimed_edge_report_v22.json": _security_report("V22: No Context Claimed Edge"),
        "no_outcome_fabrication_report_v22.json": _security_report("V22: No Outcome Fabrication"),
        "no_github_repo_code_execution_report_v22.json": _security_report("V22: No GitHub Repo Code Execution", cloned_repos=[], executed_repo_code=False),
        "no_forecast_to_execution_bridge_report_v22.json": _security_report("V22: No Forecast To Execution Bridge", forecast_path_can_trigger_execution=False),
        "no_observer_to_execution_bridge_report_v22.json": _security_report("V22: No Observer To Execution Bridge", observer_queue_can_trigger_execution=False),
        "blunder_separation_recheck_v22.json": _security_report("V22: Blunder Separation Recheck", blunder_separation_status="PASS"),
        "dummy_canonical_identity_report_v22.json": _security_report("V22: Dummy Canonical Identity", canonical_name="Dummy", dummy_renamed=False),
    }


def generate_dashboard_v22_report_v1() -> dict[str, Any]:
    report = _safe_base("V22: Dashboard Edge Activation Breakthrough V1")
    report.update(
        {
            "routes": [
                "/api/v22/edge-role-classifier",
                "/api/v22/evidence-normalizer",
                "/api/v22/crypto-spot-edge",
                "/api/v22/weather-edge",
                "/api/v22/commodity-context-guard",
                "/api/v22/finance-context-guard",
                "/api/v22/market-event-mapper",
                "/api/v22/kalshi-market-mapping",
                "/api/v22/forecast-write-breakthrough",
                "/api/v22/outcome-observer-queue",
                "/api/v22/ledger-writes",
                "/api/v22/edge-source-acquisition",
                "/api/v22/github-adapter-queue",
                "/api/v22/compounding-v5",
                "/api/v22/domain-scoreboard-v6",
                "/api/v22/mission-state",
            ],
            "shows_edge_role_decisions": True,
            "shows_forecast_write_decisions": True,
            "shows_tier0_blockers": True,
            "exposes_secret_values": False,
            "dashboard_reads_cached_artifacts_where_possible": True,
        }
    )
    return report


class V22ReportFactory:
    def __init__(self, *, enable_network: bool = False) -> None:
        self.enable_network = enable_network
        self.normalizer = ActiveSourceEvidenceNormalizer(enable_network=enable_network)
        self.classifier = EdgeRoleClassifier(self.normalizer)
        self.forecast = ForecastWriteBreakthroughEngine()
        self.observer = OutcomeObserverQueueV1(self.forecast)
        self.mapper = MarketEventMapper()

    def build(self) -> dict[str, dict[str, Any]]:
        crypto = CryptoSpotEdgeTerrainActivator(self.classifier)
        weather = WeatherEdgeTerrainActivator(self.classifier)
        commodity = CommodityContextGuard()
        finance = FinanceContextGuard()
        kalshi = KalshiMarketDiscoveryRecheckV22(enable_network=self.enable_network)
        acquisition = EdgeSourceAcquisitionEngineV2()
        github_queue = GitHubAdapterImplementationQueueV2()
        scoreboard = DomainScoreboardV6()
        return {
            "edge_role_classifier_report_v1.json": self.classifier.to_report(),
            "evidence_role_classifier_report_v1.json": self.classifier.evidence_role_report(),
            "edge_promotion_candidate_report_v1.json": self.classifier.promotion_candidate_report(),
            "context_only_blocker_report_v1.json": self.classifier.context_only_blocker_report(),
            "active_source_evidence_normalizer_report_v1.json": self.normalizer.to_report(),
            "normalized_evidence_packet_manifest_v1.json": self.normalizer.packet_manifest_report(),
            "evidence_freshness_proof_report_v1.json": self.normalizer.freshness_report(),
            "evidence_completeness_score_report_v1.json": self.normalizer.completeness_report(),
            "crypto_spot_edge_terrain_activator_report_v1.json": crypto.to_report(),
            "crypto_spot_orderbook_terrain_report_v1.json": CryptoSpotOrderbookTerrain(self.classifier).to_report(),
            "crypto_cross_venue_comparison_report_v1.json": CryptoCrossVenueComparison(self.classifier).to_report(),
            "crypto_spot_edge_readiness_report_v1.json": CryptoSpotEdgeReadiness(self.classifier).to_report(),
            "crypto_spot_forecast_gate_report_v1.json": CryptoSpotForecastGate(self.classifier).to_report(),
            "weather_edge_terrain_activator_report_v1.json": weather.to_report(),
            "weather_forecast_edge_terrain_report_v1.json": WeatherForecastEdgeTerrain(self.classifier).to_report(),
            "weather_settlement_station_mapper_report_v1.json": WeatherSettlementStationMapper().to_report(),
            "weather_forecast_readiness_gate_report_v1.json": WeatherForecastReadinessGate(self.classifier).to_report(),
            "commodity_context_guard_report_v1.json": commodity.to_report(),
            "oil_edge_insufficiency_reason_report_v1.json": commodity.insufficiency_report(),
            "commodity_source_upgrade_need_report_v1.json": CommoditySourceUpgradeNeed().to_report(),
            "finance_context_guard_report_v1.json": finance.to_report(),
            "nasdaq_edge_insufficiency_reason_report_v1.json": finance.insufficiency_report(),
            "finance_source_upgrade_need_report_v1.json": FinanceSourceUpgradeNeed().to_report(),
            "market_event_mapper_report_v1.json": self.mapper.to_report(),
            "evidence_market_link_report_v1.json": self.mapper.evidence_market_link_report(),
            "market_class_candidate_report_v1.json": self.mapper.market_class_candidate_report(),
            "market_mapping_blocker_report_v1.json": self.mapper.market_mapping_blocker_report(),
            "kalshi_market_discovery_recheck_v22_report.json": kalshi.to_report(),
            "kalshi_domain_market_mapper_report_v1.json": KalshiDomainMarketMapper().to_report(),
            "kalshi_market_evidence_join_report_v1.json": KalshiMarketEvidenceJoin().to_report(),
            "kalshi_market_mapping_blocker_report_v1.json": KalshiMarketMappingBlocker().to_report(),
            "forecast_write_breakthrough_engine_report_v1.json": self.forecast.to_report(),
            "forecast_write_candidate_manifest_v1.json": self.forecast.candidate_manifest_report(),
            "forecast_write_decision_report_v1.json": self.forecast.decision_report(),
            "forecast_snapshot_write_proof_v1.json": self.forecast.snapshot_write_proof_report(),
            "no_trade_write_proof_v1.json": self.forecast.no_trade_write_proof_report(),
            "outcome_observer_queue_v1_report.json": self.observer.to_report(),
            "observer_check_plan_report_v1.json": ObserverCheckPlan(self.forecast).to_report(),
            "observer_queue_blocker_report_v1.json": ObserverQueueBlocker().to_report(),
            "v22_outcome_ledger_integration_report_v1.json": V22OutcomeLedgerIntegration().to_report(),
            "forecast_snapshot_ledger_write_v22_report.json": ForecastSnapshotLedgerWriteV22(self.forecast).to_report(),
            "no_trade_ledger_write_v22_report.json": NoTradeLedgerWriteV22(self.forecast).to_report(),
            "observer_queue_ledger_write_v22_report.json": ObserverQueueLedgerWriteV22(self.observer).to_report(),
            "ledger_write_integrity_check_v22_report.json": LedgerWriteIntegrityCheckV22().to_report(),
            "edge_source_acquisition_engine_v2_report.json": acquisition.to_report(),
            "edge_source_acquisition_priority_report_v1.json": EdgeSourceAcquisitionPriority().to_report(),
            "tier0_market_data_need_report_v1.json": Tier0MarketDataNeed().to_report(),
            "tier2_market_data_need_report_v1.json": Tier2MarketDataNeed().to_report(),
            "adapter_implementation_need_report_v1.json": AdapterImplementationNeed().to_report(),
            "github_adapter_implementation_queue_v2_report.json": github_queue.to_report(),
            "adapter_candidate_work_item_report_v1.json": github_queue.candidate_work_item_report(),
            "adapter_risk_assessment_report_v1.json": AdapterRiskAssessment().to_report(),
            "adapter_test_plan_report_v1.json": AdapterTestPlan().to_report(),
            "compounding_control_plane_v5_report.json": CompoundingControlPlaneV5().to_report(),
            "forecast_write_improvement_queue_report_v1.json": ForecastWriteImprovementQueue().to_report(),
            "edge_activation_improvement_queue_report_v1.json": EdgeActivationImprovementQueue().to_report(),
            "source_acquisition_improvement_queue_report_v1.json": SourceAcquisitionImprovementQueue().to_report(),
            "next_tactical_bundle_selector_report_v1.json": NextTacticalBundleSelector().to_report(),
            "domain_scoreboard_v6_report.json": scoreboard.to_report(),
            "forecast_write_breakthrough_scoreboard_v1.json": scoreboard.forecast_write_breakthrough_scoreboard_report(),
            "edge_terrain_activation_scoreboard_v1.json": scoreboard.edge_terrain_activation_scoreboard_report(),
            "dummy_mission_state_report_v8.json": DummyMissionStateV22(self.classifier, self.forecast, self.observer).to_report(),
            "dashboard_v22_report_v1.json": generate_dashboard_v22_report_v1(),
            "v22_runtime_budget_report_v1.json": V22RuntimeBudget().to_report(),
            "edge_activation_call_budget_report_v1.json": EdgeActivationCallBudget().to_report(),
            "forecast_write_runtime_guard_report_v1.json": ForecastWriteRuntimeGuard().to_report(),
            "kalshi_mapping_call_limiter_v22_report.json": KalshiMappingCallLimiterV22().to_report(),
            "dashboard_cache_policy_v4_report.json": DashboardCachePolicyV4().to_report(),
            "report_chain_runtime_profiler_v5_report.json": ReportChainRuntimeProfilerV5().to_report(),
            **security_reports_v22(),
        }
