"""Fail-closed probability authority for the OpenRouter hybrid panel.

Successful model calls are research evidence, not permission to move a
forecast.  An exact scope earns a bounded probability weight only through an
explicit promotion dossier backed by fresh, forward, receipt-bounded settled
evidence.  Missing, stale, malformed, cross-scope, or demoted dossiers return
zero authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

from autonomy.taxonomy import market_type_for, prediction_subject


MODEL_PANEL_SOURCE = "openrouter_gemini36flash_gpt56luna_claudesonnet5_glm52_v1"
MODEL_AUTHORITY_SCHEMA = "model_probability_authority_v1"
MODEL_EVIDENCE_SCHEMA = "model_probability_forward_calibration_v1"
MODEL_EVIDENCE_MODE = "live_only_receipt_bounded_forward_v1"
EXPECTED_PROVIDER_MODELS = frozenset(
    {
        "google/gemini-3.6-flash",
        "anthropic/claude-sonnet-5",
        "openai/gpt-5.6-luna",
        "z-ai/glm-5.2",
    }
)
MIN_INDEPENDENT_EVENT_CLUSTERS = 300
MAX_MODEL_PROBABILITY_WEIGHT = Decimal("0.35")
MAX_MODEL_EVIDENCE_AGE = timedelta(days=7)
DEFAULT_MODEL_AUTHORITY_PATH = Path(
    "runtime/autonomy/model_probability_authority.json"
)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_APPROVED_EVIDENCE_ROOTS = (
    PROJECT_ROOT / "artifacts" / "dummy",
    PROJECT_ROOT / "runtime" / "autonomy",
)

# Model probability authority uses the four operational crypto horizons.  It
# deliberately does not reuse autonomy.taxonomy.horizon_bucket(): that older
# grading taxonomy combines daily and weekly contracts into ``daily+``, which
# would let evidence from one cadence authorize the other.
MODEL_AUTHORITY_HOURLY_MAX_HOURS = 6.0
MODEL_AUTHORITY_DAILY_MAX_HOURS = 120.0
SPORTS_TICKER_TOKENS = (
    "KXMLB",
    "KXNFL",
    "KXNBA",
    "KXWNBA",
    "KXNHL",
    "KXNCAA",
)


def _finite_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _utc_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _market_family(ticker: str, title: str, category: str) -> str:
    text = f"{ticker} {title}".lower()
    vertical = str(category or "").upper()
    if vertical == "CRYPTO" or prediction_subject(ticker) in {"btc", "eth", "sol"}:
        family = market_type_for(
            MODEL_PANEL_SOURCE,
            ticker,
            {"vertical": "CRYPTO"},
        )
        return family if family != "na" else "binary"
    if any(
        token in text
        for token in (
            "player prop",
            "points scored",
            "rebounds",
            "assists",
            "strikeouts",
            "home runs",
            "touchdowns",
            "passing yards",
            "rushing yards",
            "receiving yards",
        )
    ):
        return "player_prop"
    if "spread" in text:
        return "spread"
    if any(token in text for token in (" total", "over ", "under ", "o/u")):
        return "total"
    if is_sports_model_market(ticker=ticker, category=category):
        return "winner"
    return "binary"


def is_sports_model_market(*, ticker: str, category: str) -> bool:
    """Return whether sports phase is part of the exact authority scope."""
    return "sport" in str(category or "").lower() or any(
        token in str(ticker or "").upper() for token in SPORTS_TICKER_TOKENS
    )


def _crypto_authority_horizon(
    ticker: str,
    hours_to_close: float | None,
) -> str:
    """Return the non-pooled crypto horizon for model authority."""
    series = str(ticker or "").split("-", 1)[0].upper()
    if "15M" in series:
        return "15m"
    if hours_to_close is None:
        return "unknown"
    try:
        hours = float(hours_to_close)
    except (TypeError, ValueError):
        return "unknown"
    if not math.isfinite(hours) or hours < 0:
        return "unknown"
    if hours <= MODEL_AUTHORITY_HOURLY_MAX_HOURS:
        return "1h"
    if hours < MODEL_AUTHORITY_DAILY_MAX_HOURS:
        return "1d"
    return "1w"


def model_probability_scope(
    *,
    ticker: str,
    title: str,
    category: str,
    decision_at: datetime,
    expiration: datetime | None,
    live_phase: bool | None = None,
) -> str:
    """Return the exact authority scope used by both evidence and fusion.

    The scope never pools assets/leagues, market families, or crypto horizons.
    Sports is split pre/live, and an omitted or ambiguous phase is isolated as
    ``unknown`` rather than silently inheriting pregame evidence. Unknown
    series stay isolated by :func:`prediction_subject` instead of falling into
    a global model bucket.
    """
    subject = prediction_subject(ticker)
    family = _market_family(ticker, title, category)
    is_crypto = str(category or "").upper() == "CRYPTO" or subject in {
        "btc",
        "eth",
        "sol",
    }
    if is_crypto:
        hours_to_close: float | None = None
        if expiration is not None:
            close = expiration
            if close.tzinfo is None:
                close = close.replace(tzinfo=timezone.utc)
            decision = decision_at
            if decision.tzinfo is None:
                decision = decision.replace(tzinfo=timezone.utc)
            hours_to_close = max(
                0.0,
                (close.astimezone(timezone.utc) - decision.astimezone(timezone.utc)).total_seconds()
                / 3600.0,
            )
        axis = _crypto_authority_horizon(ticker, hours_to_close)
    elif is_sports_model_market(ticker=ticker, category=category):
        if live_phase is True:
            axis = "live"
        elif live_phase is False:
            axis = "pre"
        else:
            axis = "unknown"
    else:
        # Phase separation is currently an earned-evidence dimension only for
        # sports. Preserve the existing non-sports scope until a separately
        # validated phase taxonomy exists for those markets.
        axis = "live" if live_phase is True else "pre"
    return f"{MODEL_PANEL_SOURCE}|{subject}|{family}|{axis}"


@dataclass(frozen=True)
class ModelProbabilityAuthorityDecision:
    scope: str
    weight: Decimal
    authorized: bool
    blockers: tuple[str, ...]
    evidence_ref: str | None = None
    independent_event_clusters: int = 0
    evidence_computed_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "authorized": self.authorized,
            "weight": float(self.weight),
            "blockers": list(self.blockers),
            "evidence_ref": self.evidence_ref,
            "independent_event_clusters": self.independent_event_clusters,
            "evidence_computed_at": self.evidence_computed_at,
            "minimum_independent_event_clusters": MIN_INDEPENDENT_EVENT_CLUSTERS,
            "maximum_evidence_age_seconds": int(MAX_MODEL_EVIDENCE_AGE.total_seconds()),
            "evidence_mode_required": MODEL_EVIDENCE_MODE,
            "provider_models_required": sorted(EXPECTED_PROVIDER_MODELS),
        }


class ModelProbabilityAuthorityRegistry:
    """Read and validate explicit model-probability promotion dossiers."""

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        approved_evidence_roots: Iterable[str | Path] | None = None,
    ) -> None:
        self.path = Path(path or DEFAULT_MODEL_AUTHORITY_PATH)
        roots = approved_evidence_roots or DEFAULT_APPROVED_EVIDENCE_ROOTS
        self.approved_evidence_roots = tuple(Path(root).resolve() for root in roots)

    @staticmethod
    def _blocked(scope: str, *reasons: str) -> ModelProbabilityAuthorityDecision:
        return ModelProbabilityAuthorityDecision(
            scope=scope,
            weight=Decimal("0"),
            authorized=False,
            blockers=tuple(sorted(set(reasons))) or ("authority_not_earned",),
        )

    def _load(self) -> tuple[dict[str, Any] | None, str | None]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None, "authority_registry_missing"
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None, "authority_registry_unreadable_or_invalid"
        if not isinstance(raw, dict):
            return None, "authority_registry_not_mapping"
        if raw.get("schema_version") != MODEL_AUTHORITY_SCHEMA:
            return None, "authority_registry_schema_mismatch"
        if not isinstance(raw.get("promotions"), list):
            return None, "authority_promotions_not_list"
        return raw, None

    def _canonical_evidence_blockers(
        self,
        *,
        scope: str,
        evidence: dict[str, Any],
        now_utc: datetime,
    ) -> list[str]:
        blockers: list[str] = []
        evidence_ref = evidence.get("evidence_ref")
        digest = evidence.get("evidence_sha256")
        if not isinstance(evidence_ref, str) or not evidence_ref.strip():
            return ["evidence_ref_missing"]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest.lower())
        ):
            return ["evidence_sha256_invalid"]

        candidate = Path(evidence_ref)
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            return ["canonical_evidence_artifact_missing"]
        if not any(
            resolved == root or resolved.is_relative_to(root)
            for root in self.approved_evidence_roots
        ):
            return ["canonical_evidence_artifact_outside_approved_roots"]
        if not resolved.is_file() or resolved.suffix.lower() != ".json":
            return ["canonical_evidence_artifact_not_json_file"]
        try:
            raw_bytes = resolved.read_bytes()
        except OSError:
            return ["canonical_evidence_artifact_unreadable"]
        if len(raw_bytes) > 8 * 1024 * 1024:
            return ["canonical_evidence_artifact_too_large"]
        if hashlib.sha256(raw_bytes).hexdigest() != digest.lower():
            blockers.append("canonical_evidence_sha256_mismatch")
        try:
            artifact = json.loads(raw_bytes)
        except (UnicodeError, json.JSONDecodeError):
            return blockers + ["canonical_evidence_artifact_invalid_json"]
        if not isinstance(artifact, dict):
            return blockers + ["canonical_evidence_artifact_not_mapping"]
        if artifact.get("schema_version") != MODEL_EVIDENCE_SCHEMA:
            blockers.append("canonical_evidence_schema_mismatch")
        if artifact.get("artifact_type") != MODEL_EVIDENCE_SCHEMA:
            blockers.append("canonical_evidence_type_mismatch")
        if artifact.get("evidence_mode") != MODEL_EVIDENCE_MODE:
            blockers.append("canonical_evidence_mode_mismatch")
        models = artifact.get("provider_models")
        if (
            not isinstance(models, list)
            or len(models) != len(EXPECTED_PROVIDER_MODELS)
            or set(models) != EXPECTED_PROVIDER_MODELS
        ):
            blockers.append("canonical_evidence_provider_set_mismatch")
        if artifact.get("promotion_authority") is not False:
            blockers.append("canonical_artifact_must_not_self_promote")

        generated_at = _utc_timestamp(artifact.get("generated_at"))
        computed_at = _utc_timestamp(evidence.get("computed_at"))
        if generated_at is None:
            blockers.append("canonical_evidence_generated_at_invalid")
        else:
            if generated_at > now_utc:
                blockers.append("canonical_evidence_generated_in_future")
            elif now_utc - generated_at > MAX_MODEL_EVIDENCE_AGE:
                blockers.append("canonical_evidence_artifact_stale")
            if computed_at is None or generated_at != computed_at:
                blockers.append("canonical_evidence_generated_at_mismatch")

        scopes = artifact.get("scopes")
        if not isinstance(scopes, dict):
            return blockers + ["canonical_evidence_scopes_not_mapping"]
        row = scopes.get(scope)
        if not isinstance(row, dict):
            return blockers + ["canonical_exact_scope_row_missing"]

        cluster_ids = row.get("independent_event_cluster_ids")
        if not isinstance(cluster_ids, list) or any(
            not isinstance(cluster_id, str) or not cluster_id.strip()
            for cluster_id in (cluster_ids if isinstance(cluster_ids, list) else [])
        ):
            blockers.append("canonical_independent_cluster_ids_invalid")
        elif len(cluster_ids) != len(set(cluster_ids)):
            blockers.append("canonical_independent_cluster_ids_not_unique")
        elif len(cluster_ids) != evidence.get("independent_event_clusters"):
            blockers.append("canonical_independent_cluster_count_mismatch")

        for key in (
            "forward_calibrated",
            "receipt_bounded",
            "point_in_time",
            "retro_rows_included",
            "independent_event_clusters",
            "computed_at",
            "received_through",
        ):
            if row.get(key) != evidence.get(key):
                blockers.append(f"canonical_scope_{key}_mismatch")

        artifact_ci = row.get("brier_edge_ci95")
        dossier_ci = evidence.get("brier_edge_ci95")
        for bound in ("lower", "upper"):
            artifact_value = (
                _finite_decimal(artifact_ci.get(bound))
                if isinstance(artifact_ci, dict)
                else None
            )
            dossier_value = (
                _finite_decimal(dossier_ci.get(bound))
                if isinstance(dossier_ci, dict)
                else None
            )
            if artifact_value is None or artifact_value != dossier_value:
                blockers.append(f"canonical_scope_brier_ci95_{bound}_mismatch")
        if _finite_decimal(row.get("earned_weight")) != _finite_decimal(
            evidence.get("earned_weight")
        ):
            blockers.append("canonical_scope_earned_weight_mismatch")
        return blockers

    def evaluate(
        self,
        scope: str,
        *,
        now: datetime | None = None,
    ) -> ModelProbabilityAuthorityDecision:
        # An unknown axis is deliberately non-promotable even if a malformed or
        # hand-authored registry contains a matching dossier. A known phase (or
        # crypto horizon) is a prerequisite for model probability authority.
        if str(scope).rsplit("|", 1)[-1] == "unknown":
            return self._blocked(scope, "authority_scope_axis_unknown")

        now_utc = now or datetime.now(timezone.utc)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)
        now_utc = now_utc.astimezone(timezone.utc)

        root, load_error = self._load()
        if root is None:
            return self._blocked(scope, load_error or "authority_registry_invalid")

        demoted: set[str] = set()
        for item in root.get("demotions") or []:
            if isinstance(item, str):
                demoted.add(item)
            elif isinstance(item, dict) and isinstance(item.get("scope"), str):
                demoted.add(item["scope"])
        if scope in demoted:
            return self._blocked(scope, "scope_explicitly_demoted")

        matches = [
            entry
            for entry in root["promotions"]
            if isinstance(entry, dict) and entry.get("scope") == scope
        ]
        if not matches:
            return self._blocked(scope, "exact_scope_promotion_missing")
        if len(matches) != 1:
            return self._blocked(scope, "duplicate_exact_scope_promotions")
        entry = matches[0]
        blockers: list[str] = []

        if entry.get("status") != "PROMOTED":
            blockers.append("promotion_status_not_promoted")
        provider_models = entry.get("provider_models")
        if (
            not isinstance(provider_models, list)
            or len(provider_models) != len(EXPECTED_PROVIDER_MODELS)
            or set(provider_models) != EXPECTED_PROVIDER_MODELS
        ):
            blockers.append("promotion_provider_model_set_mismatch")

        evidence = entry.get("evidence")
        if not isinstance(evidence, dict):
            return self._blocked(scope, *(blockers + ["promotion_evidence_missing"]))
        if evidence.get("evidence_mode") != MODEL_EVIDENCE_MODE:
            blockers.append("evidence_mode_not_forward_receipt_bounded")
        if evidence.get("forward_calibrated") is not True:
            blockers.append("forward_calibration_not_proven")
        if evidence.get("receipt_bounded") is not True:
            blockers.append("receipt_bounded_not_proven")
        if evidence.get("point_in_time") is not True:
            blockers.append("point_in_time_not_proven")
        if evidence.get("retro_rows_included") != 0:
            blockers.append("retro_rows_not_zero")

        clusters = evidence.get("independent_event_clusters")
        if isinstance(clusters, bool) or not isinstance(clusters, int):
            clusters_int = 0
            blockers.append("independent_event_clusters_invalid")
        else:
            clusters_int = clusters
            if clusters_int < MIN_INDEPENDENT_EVENT_CLUSTERS:
                blockers.append("independent_event_clusters_below_300")

        ci = evidence.get("brier_edge_ci95")
        ci_low = ci_high = None
        if isinstance(ci, dict):
            ci_low = _finite_decimal(ci.get("lower"))
            ci_high = _finite_decimal(ci.get("upper"))
        if (
            ci_low is None
            or ci_high is None
            or ci_low <= 0
            or ci_high < ci_low
        ):
            blockers.append("brier_edge_ci95_lower_not_positive")

        weight = _finite_decimal(evidence.get("earned_weight"))
        if (
            weight is None
            or weight <= 0
            or weight > MAX_MODEL_PROBABILITY_WEIGHT
        ):
            blockers.append("earned_weight_invalid_or_out_of_bounds")

        computed_at = _utc_timestamp(evidence.get("computed_at"))
        received_through = _utc_timestamp(evidence.get("received_through"))
        promoted_at = _utc_timestamp(entry.get("promoted_at"))
        if computed_at is None:
            blockers.append("evidence_computed_at_invalid")
        if received_through is None:
            blockers.append("evidence_received_through_invalid")
        if promoted_at is None:
            blockers.append("promoted_at_invalid")
        if computed_at is not None:
            if computed_at > now_utc:
                blockers.append("evidence_computed_in_future")
            elif now_utc - computed_at > MAX_MODEL_EVIDENCE_AGE:
                blockers.append("model_evidence_stale")
        if received_through is not None and computed_at is not None:
            if received_through > computed_at:
                blockers.append("receipt_boundary_after_evidence_computation")
        if promoted_at is not None:
            if promoted_at > now_utc:
                blockers.append("promotion_in_future")
            if computed_at is not None and promoted_at < computed_at:
                blockers.append("promotion_precedes_evidence")

        evidence_ref = evidence.get("evidence_ref")
        blockers.extend(
            self._canonical_evidence_blockers(
                scope=scope,
                evidence=evidence,
                now_utc=now_utc,
            )
        )

        if blockers or weight is None:
            return ModelProbabilityAuthorityDecision(
                scope=scope,
                weight=Decimal("0"),
                authorized=False,
                blockers=tuple(sorted(set(blockers))),
                evidence_ref=evidence_ref if isinstance(evidence_ref, str) else None,
                independent_event_clusters=clusters_int,
                evidence_computed_at=(
                    computed_at.isoformat() if computed_at is not None else None
                ),
            )
        return ModelProbabilityAuthorityDecision(
            scope=scope,
            weight=weight,
            authorized=True,
            blockers=(),
            evidence_ref=evidence_ref,
            independent_event_clusters=clusters_int,
            evidence_computed_at=computed_at.isoformat(),
        )


__all__ = [
    "DEFAULT_MODEL_AUTHORITY_PATH",
    "EXPECTED_PROVIDER_MODELS",
    "MAX_MODEL_EVIDENCE_AGE",
    "MAX_MODEL_PROBABILITY_WEIGHT",
    "MIN_INDEPENDENT_EVENT_CLUSTERS",
    "MODEL_AUTHORITY_SCHEMA",
    "MODEL_EVIDENCE_SCHEMA",
    "MODEL_EVIDENCE_MODE",
    "MODEL_PANEL_SOURCE",
    "SPORTS_TICKER_TOKENS",
    "ModelProbabilityAuthorityDecision",
    "ModelProbabilityAuthorityRegistry",
    "is_sports_model_market",
    "model_probability_scope",
]
