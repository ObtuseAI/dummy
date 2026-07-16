"""Intelligence-Lab campaigns over the Wave-1/2 instrumented evidence streams.

Wave-1/2 added four settled evidence streams the autoresearch Loop-1 machinery
had never seen: sports CLV records, execution-tournament cohort P&L, ESPN
fantasy signals, and cross-venue Polymarket divergence. This module maps each of
them into the canonical, content-addressed :class:`LedgerEvidenceRow` (so every
downstream invariant -- point-in-time discipline, event-cluster purging,
single-cohort partitions -- applies unchanged), builds a chronological partition
plan over them, and runs a bounded candidate search that:

  * mines candidates ONLY on the VISIBLE_DEVELOPMENT partition (no lookahead --
    private/external evidence is never read during mining),
  * enforces the existing complexity gate on every candidate, and
  * discloses the mined-rule FAMILY SIZE honestly (how many candidates were
    searched, not just how many survived), with the multiple-comparisons math
    a reviewer needs -- the standing lesson that reporting a survivor while
    hiding the family it was selected from is dishonest.

Research/observation only: nothing here can reach execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from dummy.world_model.models import digest_json

from .complexity_gate import ComplexityBudget, ComplexityDecision, evaluate_complexity
from .ledger_pipeline import (
    LedgerEvidenceRow,
    LedgerPartitionPlan,
    _market_regime,
    _market_type,
    build_ledger_partition_plan,
)
from .models import ComplexityProfile, EvaluationPartition, utc

# The four Wave-1/2 streams, each a distinct source family so a mined edge is
# attributable and cannot silently pool with an unrelated source.
STREAM_SOURCE_FAMILIES = {
    "sports_clv": "sports_clv",
    "execution_tournament": "execution_tournament",
    "espn_fantasy": "espn_fantasy_crowd",
    "cross_venue": "cross_venue_polymarket",
}


def evidence_row(
    *,
    stream: str,
    decision_id: str,
    market_ticker: str,
    event_cluster_id: str,
    decision_at: datetime | str,
    settlement_received_at: datetime | str,
    incumbent_probability: float,
    market_prior_probability: float,
    result_yes: bool,
    vertical: str,
    subject: str,
    phase: str = "pre",
    forecast_uncertainty: float = 0.2,
    action: str = "OBSERVE",
    side: str = "YES",
    price_cents: int = 50,
    count: int = 0,
    fill_count: int = 0,
    settled_pnl_cents: int | None = None,
    market_type: str | None = None,
    horizon_or_phase: str | None = None,
    forced_coverage: bool = False,
    source_family_ids: tuple[str, ...] | None = None,
    component_source: str | None = None,
    component_probability: float | None = None,
    component_features: dict[str, Any] | None = None,
    input_features: dict[str, Any] | None = None,
) -> LedgerEvidenceRow:
    """Build one canonical evidence row from a normalized stream record.

    Point-in-time discipline is enforced by :class:`LedgerEvidenceRow` itself
    (``decision_at`` must precede ``settlement_received_at``); this helper only
    fills the derived taxonomy fields and the stream's source family.
    """
    if stream not in STREAM_SOURCE_FAMILIES:
        raise ValueError(f"unknown Wave-1/2 stream: {stream!r}")
    families = source_family_ids or (STREAM_SOURCE_FAMILIES[stream],)
    resolved_market_type = market_type or _market_type(market_ticker)
    resolved_horizon = horizon_or_phase or phase
    kwargs: dict[str, Any] = {
        "decision_id": decision_id,
        "market_ticker": market_ticker,
        "event_cluster_id": event_cluster_id,
        "decision_at": utc(decision_at),
        "settlement_received_at": utc(settlement_received_at),
        "incumbent_probability": incumbent_probability,
        "market_prior_probability": market_prior_probability,
        "forecast_uncertainty": forecast_uncertainty,
        "result_yes": bool(result_yes),
        "action": action,
        "side": side,
        "price_cents": price_cents,
        "count": count,
        "source_family_ids": families,
        "fill_count": fill_count,
        "settled_pnl_cents": settled_pnl_cents,
        "vertical": vertical,
        "subject": subject,
        "market_type": resolved_market_type,
        "phase": phase,
        "horizon_or_phase": resolved_horizon,
        "market_regime": _market_regime(market_prior_probability),
        "forced_coverage": forced_coverage,
        "input_digest": digest_json(input_features or {"stream": stream, "ticker": market_ticker}),
    }
    if component_probability is not None:
        kwargs["component_source"] = component_source or STREAM_SOURCE_FAMILIES[stream]
        kwargs["component_probability"] = component_probability
        kwargs["component_features_digest"] = digest_json(component_features or {})
    return LedgerEvidenceRow.create(**kwargs)


# ---- per-stream adapters -----------------------------------------------------

def clv_evidence_row(record: dict[str, Any]) -> LedgerEvidenceRow:
    """Sports CLV record -> evidence row.

    The pre-game close is the market prior; our forecast is the incumbent. The
    CLV sign is carried as a component observation, not fabricated into P&L.
    """
    return evidence_row(
        stream="sports_clv",
        decision_id=str(record["decision_id"]),
        market_ticker=str(record["market_ticker"]),
        event_cluster_id=str(record.get("event_cluster_id") or record["market_ticker"]),
        decision_at=record["decision_at"],
        settlement_received_at=record["settlement_received_at"],
        incumbent_probability=float(record["our_probability"]),
        market_prior_probability=float(record["close_probability"]),
        result_yes=bool(record["result_yes"]),
        vertical=str(record.get("vertical", "sports")),
        subject=str(record["subject"]),
        market_type=record.get("market_type"),
        phase=str(record.get("phase", "pre")),
        component_source="sports_clv",
        component_probability=float(record["close_probability"]),
        component_features={"clv_bps": record.get("clv_bps")},
    )


def tournament_cohort_evidence_row(record: dict[str, Any]) -> LedgerEvidenceRow:
    """Execution-tournament cohort record -> evidence row.

    Each cohort (C0-C4) is a distinct source family so a mined execution edge is
    attributed to the exact counterfactual lane, never pooled across cohorts.
    ``settled_pnl_cents`` is the cohort's real counterfactual P&L (may be None).
    """
    cohort = str(record["cohort"])
    return evidence_row(
        stream="execution_tournament",
        decision_id=str(record["decision_id"]),
        market_ticker=str(record["market_ticker"]),
        event_cluster_id=str(record.get("event_cluster_id") or record["market_ticker"]),
        decision_at=record["decision_at"],
        settlement_received_at=record["settlement_received_at"],
        incumbent_probability=float(record["probability_yes"]),
        market_prior_probability=float(record["market_prior"]),
        result_yes=bool(record["result_yes"]),
        vertical=str(record.get("vertical", "sports")),
        subject=str(record["subject"]),
        market_type=record.get("market_type"),
        phase=str(record.get("phase", "pre")),
        action="TRADE",
        side=str(record.get("side", "YES")),
        price_cents=int(record.get("price_cents", 50)),
        count=int(record.get("count", 0)),
        fill_count=int(record.get("fill_count", 0)),
        settled_pnl_cents=record.get("settled_pnl_cents"),
        source_family_ids=(f"execution_tournament::{cohort}",),
    )


def fantasy_evidence_row(record: dict[str, Any]) -> LedgerEvidenceRow:
    """ESPN fantasy (crowd/scratch) signal -> evidence row (MLB)."""
    return evidence_row(
        stream="espn_fantasy",
        decision_id=str(record["decision_id"]),
        market_ticker=str(record["market_ticker"]),
        event_cluster_id=str(record.get("event_cluster_id") or record["market_ticker"]),
        decision_at=record["decision_at"],
        settlement_received_at=record["settlement_received_at"],
        incumbent_probability=float(record["crowd_probability"]),
        market_prior_probability=float(record["market_prior"]),
        result_yes=bool(record["result_yes"]),
        vertical="mlb",
        subject=str(record["subject"]),
        market_type=record.get("market_type"),
        phase=str(record.get("phase", "pre")),
        component_source="espn_fantasy_crowd",
        component_probability=float(record["crowd_probability"]),
        component_features={"ownership": record.get("ownership"), "scratched": record.get("scratched")},
    )


def cross_venue_evidence_row(record: dict[str, Any]) -> LedgerEvidenceRow:
    """Cross-venue Polymarket divergence snapshot -> evidence row (crypto/econ).

    Kalshi is the incumbent; the matched Polymarket reference price rides as a
    component observation so a divergence edge stays attributable to the venue.
    """
    return evidence_row(
        stream="cross_venue",
        decision_id=str(record["decision_id"]),
        market_ticker=str(record["market_ticker"]),
        event_cluster_id=str(record.get("event_cluster_id") or record["market_ticker"]),
        decision_at=record["decision_at"],
        settlement_received_at=record["settlement_received_at"],
        incumbent_probability=float(record["kalshi_probability"]),
        market_prior_probability=float(record["kalshi_probability"]),
        result_yes=bool(record["result_yes"]),
        vertical=str(record.get("vertical", "crypto")),
        subject=str(record["subject"]),
        market_type=record.get("market_type"),
        phase=str(record.get("phase", "pre")),
        source_family_ids=(f"cross_venue_polymarket_{record.get('vertical', 'crypto')}",),
        component_source="cross_venue_polymarket",
        component_probability=float(record["polymarket_probability"]),
        component_features={"venue": "polymarket"},
    )


_ADAPTERS = {
    "sports_clv": clv_evidence_row,
    "execution_tournament": tournament_cohort_evidence_row,
    "espn_fantasy": fantasy_evidence_row,
    "cross_venue": cross_venue_evidence_row,
}


def adapt_stream(stream: str, records: Iterable[dict[str, Any]]) -> list[LedgerEvidenceRow]:
    """Map a stream's raw records into canonical evidence rows."""
    adapter = _ADAPTERS.get(stream)
    if adapter is None:
        raise ValueError(f"no adapter for stream {stream!r}")
    return [adapter(record) for record in records]


def build_stream_partition_plan(
    rows: Iterable[LedgerEvidenceRow], *, scope: str
) -> LedgerPartitionPlan:
    """Chronological, point-in-time partition plan for one cohort's rows.

    Delegates to the canonical builder, which enforces the single-cohort rule,
    freezes each event cluster to its earliest decision date, and purges any
    cluster that would bridge partitions -- so no-lookahead is structural.
    """
    return build_ledger_partition_plan(rows, scope=scope)


# ---- bounded candidate search + honest family-size disclosure ---------------

@dataclass(frozen=True, slots=True)
class CampaignCandidate:
    """A mined rule proposal and its complexity footprint."""

    rule_id: str
    description: str
    complexity: ComplexityProfile


@dataclass(frozen=True, slots=True)
class MinedFamilyDisclosure:
    """Honest accounting of a mined-rule search (multiple-comparisons aware)."""

    family_size: int          # total candidates SEARCHED
    complexity_passed: int    # candidates that cleared the complexity gate
    kept: int                 # candidates kept after mining
    alpha: float
    expected_false_positives: float
    warning: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "family_size_searched": self.family_size,
            "complexity_passed": self.complexity_passed,
            "kept": self.kept,
            "alpha": self.alpha,
            "expected_false_positives_under_null": round(self.expected_false_positives, 4),
            "selection_ratio": round(self.kept / self.family_size, 6) if self.family_size else 0.0,
            "multiple_comparisons_warning": self.warning,
        }


def disclose_mined_family(
    *, family_size: int, complexity_passed: int, kept: int, alpha: float = 0.05
) -> MinedFamilyDisclosure:
    """Disclose the search that produced ``kept`` rules from ``family_size``.

    ``expected_false_positives`` is ``family_size * alpha`` -- the number of
    spurious survivors expected if EVERY candidate were null. A reviewer weighs
    ``kept`` against it; when kept <= expected_false_positives the survivors are
    indistinguishable from noise, and the warning says so.
    """
    if family_size < 0 or kept < 0 or complexity_passed < 0:
        raise ValueError("family/kept/complexity counts must be non-negative")
    if kept > complexity_passed or complexity_passed > family_size:
        raise ValueError("kept <= complexity_passed <= family_size must hold")
    expected_fp = family_size * alpha
    if kept == 0:
        warning = "no rule survived; nothing to report as an edge"
    elif kept <= expected_fp:
        warning = (
            f"kept={kept} <= expected_false_positives={expected_fp:.2f}: survivors are "
            "consistent with multiple-comparisons noise; treat as UNPROVEN"
        )
    else:
        warning = (
            f"kept={kept} exceeds expected_false_positives={expected_fp:.2f}, but a "
            f"family of {family_size} was searched; require out-of-sample confirmation"
        )
    return MinedFamilyDisclosure(
        family_size=family_size,
        complexity_passed=complexity_passed,
        kept=kept,
        alpha=alpha,
        expected_false_positives=expected_fp,
        warning=warning,
    )


def run_stream_campaign(
    stream: str,
    records: Iterable[dict[str, Any]],
    *,
    scope: str,
    candidates: Iterable[CampaignCandidate],
    budget: ComplexityBudget = ComplexityBudget(),
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Run a bounded Loop-1-style campaign over one Wave-1/2 stream.

    Mines ONLY on the VISIBLE_DEVELOPMENT partition (no lookahead), gates every
    candidate on complexity, and returns a research artifact with the partition
    manifest, the surviving candidates, and an honest family-size disclosure.
    Never touches execution.
    """
    rows = adapt_stream(stream, records)
    plan = build_stream_partition_plan(rows, scope=scope)

    visible_ids = {
        row_id for row_id, partition in plan.assignments
        if partition is EvaluationPartition.VISIBLE_DEVELOPMENT
    }
    visible_rows = tuple(r for r in rows if r.evidence_row_id in visible_ids)

    family = list(candidates)
    decisions: list[tuple[CampaignCandidate, ComplexityDecision]] = [
        (c, evaluate_complexity(c.complexity, budget)) for c in family
    ]
    passed = [c for c, decision in decisions if decision.passed]

    # A candidate is "kept" only if it clears complexity AND there is visible
    # evidence to have mined it on -- mining on zero visible rows keeps nothing.
    kept = passed if visible_rows else []

    disclosure = disclose_mined_family(
        family_size=len(family),
        complexity_passed=len(passed),
        kept=len(kept),
        alpha=alpha,
    )
    return {
        "stream": stream,
        "scope": scope,
        "partition_manifest": plan.public_manifest(),
        "visible_evidence_rows": len(visible_rows),
        "kept_candidates": [
            {"rule_id": c.rule_id, "description": c.description} for c in kept
        ],
        "mined_family_disclosure": disclosure.to_dict(),
        "reaches_execution": False,
        "point_in_time_method": "visible_partition_only_no_lookahead",
    }
