"""Read-only compiler from Dummy's authoritative ledger to causal evidence rows."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from autonomy.correlation import group_key
from autonomy.scanner import classify_vertical
from autonomy.taxonomy import horizon_bucket, prediction_subject
from dummy.world_model.models import digest_json

from .models import (
    AutoresearchValidationError,
    EvaluationPartition,
    iso,
    probability,
    utc,
)


def _market_type(ticker: str) -> str:
    series = ticker.upper().split("-", 1)[0]
    if "SPREAD" in series:
        return "spread"
    if "TOTAL" in series:
        return "total"
    if "RFI" in series:
        return "yrfi"
    if "GAME" in series or "FIGHT" in series:
        return "winner"
    if "15M" in series:
        return "15m_direction"
    if series.startswith(("KXBTC", "KXETH", "KXSOL")):
        return "price_ladder"
    return "other"


def _market_regime(value: float) -> str:
    if value < 0.40:
        return "underdog_lt_40"
    if value > 0.60:
        return "favorite_gt_60"
    return "balanced_40_60"


@dataclass(frozen=True, slots=True)
class LedgerEvidenceRow:
    evidence_row_id: str
    decision_id: str
    market_ticker: str
    event_cluster_id: str
    decision_at: datetime
    settlement_received_at: datetime
    incumbent_probability: float
    market_prior_probability: float
    forecast_uncertainty: float
    result_yes: bool
    action: str
    side: str
    price_cents: int
    count: int
    source_family_ids: tuple[str, ...]
    fill_count: int
    settled_pnl_cents: int | None
    vertical: str
    subject: str
    market_type: str
    phase: str
    horizon_or_phase: str
    market_regime: str
    forced_coverage: bool
    input_digest: str

    def __post_init__(self) -> None:
        if not self.decision_id.strip() or not self.market_ticker.strip():
            raise AutoresearchValidationError("ledger evidence identity is required")
        decision = utc(self.decision_at)
        settlement = utc(self.settlement_received_at)
        if decision >= settlement:
            raise AutoresearchValidationError(
                "ledger evidence must be recorded before settlement"
            )
        object.__setattr__(self, "decision_at", decision)
        object.__setattr__(self, "settlement_received_at", settlement)
        object.__setattr__(
            self,
            "incumbent_probability",
            probability(self.incumbent_probability, field="incumbent_probability"),
        )
        object.__setattr__(
            self,
            "market_prior_probability",
            probability(self.market_prior_probability, field="market_prior_probability"),
        )
        if not 0.0 <= self.forecast_uncertainty <= 1.0:
            raise AutoresearchValidationError("forecast uncertainty must be in [0, 1]")
        if self.fill_count < 0 or self.count < 0 or not 0 <= self.price_cents <= 100:
            raise AutoresearchValidationError("ledger execution fields are invalid")
        families = tuple(sorted(set(str(item) for item in self.source_family_ids if item)))
        if not families:
            raise AutoresearchValidationError("ledger evidence requires source families")
        object.__setattr__(self, "source_family_ids", families)
        if self.evidence_row_id != digest_json(self.semantic_dict()):
            raise AutoresearchValidationError("ledger evidence row ID mismatch")

    @classmethod
    def create(cls, **kwargs: Any) -> LedgerEvidenceRow:
        semantic = cls._semantic_from(kwargs)
        return cls(evidence_row_id=digest_json(semantic), **kwargs)

    @staticmethod
    def _semantic_from(data: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "decision_id": data["decision_id"],
            "market_ticker": data["market_ticker"],
            "event_cluster_id": data["event_cluster_id"],
            "decision_at": iso(data["decision_at"]),
            "settlement_received_at": iso(data["settlement_received_at"]),
            "incumbent_probability": data["incumbent_probability"],
            "market_prior_probability": data["market_prior_probability"],
            "forecast_uncertainty": data["forecast_uncertainty"],
            "result_yes": data["result_yes"],
            "action": data["action"],
            "side": data["side"],
            "price_cents": data["price_cents"],
            "count": data["count"],
            "source_family_ids": list(data["source_family_ids"]),
            "fill_count": data["fill_count"],
            "settled_pnl_cents": data["settled_pnl_cents"],
            "vertical": data["vertical"],
            "subject": data["subject"],
            "market_type": data["market_type"],
            "phase": data["phase"],
            "horizon_or_phase": data["horizon_or_phase"],
            "market_regime": data["market_regime"],
            "forced_coverage": data["forced_coverage"],
            "input_digest": data["input_digest"],
        }

    def semantic_dict(self) -> dict[str, Any]:
        return self._semantic_from(
            {
                field: getattr(self, field)
                for field in self.__dataclass_fields__
                if field != "evidence_row_id"
            }
        )

    @property
    def cohort_scope(self) -> str:
        """Exact independently gated prediction cohort."""
        return (
            f"{self.vertical}|{self.subject}|{self.market_type}|"
            f"{self.horizon_or_phase}"
        )


def connect_ledger_readonly(path: Path | str) -> sqlite3.Connection:
    resolved = Path(path).resolve()
    connection = sqlite3.connect(
        f"file:{resolved.as_posix()}?mode=ro",
        uri=True,
        timeout=30.0,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


_EARLIEST_SETTLED_QUERY = """
WITH ranked AS (
    SELECT d.*,
           ROW_NUMBER() OVER (
               PARTITION BY d.market_ticker
               ORDER BY d.created_at, d.decision_id
           ) AS row_number
    FROM decisions d
    JOIN settlements s USING(market_ticker)
    WHERE d.market_implied_yes IS NOT NULL
      AND (? IS NULL OR d.market_ticker LIKE ?)
)
SELECT r.decision_id,r.market_ticker,r.action,r.side,r.price_cents,r.count,
       r.probability_yes,r.forecast_uncertainty,r.market_implied_yes,
       r.sources_used,r.abstain_reason,r.created_at,s.result_yes,s.settled_at,
       COALESCE((
           SELECT MAX(o.fill_count) FROM outcomes o
           WHERE o.decision_id=r.decision_id
       ),0) AS fill_count,
       (
           SELECT p.pnl_cents FROM outcomes p
           WHERE p.decision_id=r.decision_id
             AND p.kind IN ('SETTLED_WIN','SETTLED_LOSS')
             AND EXISTS (
                 SELECT 1 FROM outcomes f
                 WHERE f.decision_id=p.decision_id
                   AND f.id<p.id AND f.fill_count>0
             )
           ORDER BY p.id DESC LIMIT 1
       ) AS settled_pnl_cents
FROM ranked r
JOIN settlements s USING(market_ticker)
WHERE r.row_number=1
ORDER BY r.created_at,r.decision_id
"""


def load_ledger_evidence(
    path: Path | str,
    *,
    ticker_prefix: str | None = None,
    decision_after: datetime | None = None,
) -> tuple[LedgerEvidenceRow, ...]:
    like = f"{ticker_prefix.upper()}%" if ticker_prefix else None
    connection = connect_ledger_readonly(path)
    try:
        records = connection.execute(_EARLIEST_SETTLED_QUERY, (like, like)).fetchall()
    finally:
        connection.close()
    rows: list[LedgerEvidenceRow] = []
    after = utc(decision_after) if decision_after is not None else None
    for record in records:
        try:
            decision_at = utc(record["created_at"])
            settlement_at = utc(record["settled_at"])
            incumbent = float(record["probability_yes"])
            market = float(record["market_implied_yes"])
            uncertainty = float(record["forecast_uncertainty"])
            raw_sources = json.loads(record["sources_used"] or "{}")
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if after is not None and decision_at <= after:
            continue
        if decision_at >= settlement_at:
            continue
        if not (0.0 < incumbent < 1.0 and 0.0 < market < 1.0):
            continue
        if not isinstance(raw_sources, dict) or not raw_sources:
            continue
        ticker = str(record["market_ticker"])
        sources = tuple(sorted(str(key) for key in raw_sources if str(key)))
        action = str(record["action"])
        abstain_reason = str(record["abstain_reason"] or "")
        forced = any("forced" in source.lower() for source in sources) or (
            "forced" in abstain_reason.lower()
        )
        phase = "live" if any("live" in source.lower() for source in sources) else "pre"
        vertical = classify_vertical(ticker).value.lower()
        axis = horizon_bucket(ticker, None) if vertical == "crypto" else phase
        input_payload = {
            "decision_id": str(record["decision_id"]),
            "market_ticker": ticker,
            "decision_at": iso(decision_at),
            "incumbent_probability": incumbent,
            "market_prior_probability": market,
            "forecast_uncertainty": uncertainty,
            "action": action,
            "side": str(record["side"]),
            "price_cents": int(record["price_cents"]),
            "count": int(record["count"]),
            "source_family_ids": list(sources),
        }
        kwargs = {
            "decision_id": str(record["decision_id"]),
            "market_ticker": ticker,
            "event_cluster_id": group_key(ticker),
            "decision_at": decision_at,
            "settlement_received_at": settlement_at,
            "incumbent_probability": incumbent,
            "market_prior_probability": market,
            "forecast_uncertainty": uncertainty,
            "result_yes": bool(record["result_yes"]),
            "action": action,
            "side": str(record["side"]),
            "price_cents": int(record["price_cents"]),
            "count": int(record["count"]),
            "source_family_ids": sources,
            "fill_count": int(record["fill_count"] or 0),
            "settled_pnl_cents": (
                int(record["settled_pnl_cents"])
                if record["settled_pnl_cents"] is not None
                else None
            ),
            "vertical": vertical,
            "subject": prediction_subject(ticker),
            "market_type": _market_type(ticker),
            "phase": phase,
            "horizon_or_phase": axis,
            "market_regime": _market_regime(market),
            "forced_coverage": forced,
            "input_digest": digest_json(input_payload),
        }
        rows.append(LedgerEvidenceRow.create(**kwargs))
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class LedgerPartitionPlan:
    plan_id: str
    scope: str
    evidence_fingerprint: str
    assignments: tuple[tuple[str, EvaluationPartition], ...]
    excluded_cross_partition_clusters: tuple[str, ...]
    decision_dates: tuple[tuple[str, EvaluationPartition], ...]

    def __post_init__(self) -> None:
        if not self.scope.strip() or not self.assignments:
            raise AutoresearchValidationError("ledger partition plan is empty")
        if {partition for _, partition in self.assignments} != set(EvaluationPartition):
            raise AutoresearchValidationError("partition plan requires all partitions")
        if len({row_id for row_id, _ in self.assignments}) != len(self.assignments):
            raise AutoresearchValidationError("partition plan repeats an evidence row")
        if len({date for date, _ in self.decision_dates}) != len(self.decision_dates):
            raise AutoresearchValidationError("partition plan repeats a decision date")
        if self.plan_id != digest_json(self.semantic_dict()):
            raise AutoresearchValidationError("partition plan ID mismatch")

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "scope": self.scope,
            "evidence_fingerprint": self.evidence_fingerprint,
            "assignments": [[row_id, partition.value] for row_id, partition in self.assignments],
            "excluded_cross_partition_clusters": list(
                self.excluded_cross_partition_clusters
            ),
            "decision_dates": [
                [date, partition.value] for date, partition in self.decision_dates
            ],
            "partition_method": "chronological_whole_date_with_event_cluster_purge_v1",
        }

    def public_manifest(self) -> dict[str, Any]:
        counts = {
            partition.value: sum(value is partition for _, value in self.assignments)
            for partition in EvaluationPartition
        }
        dates = {
            partition.value: [date for date, value in self.decision_dates if value is partition]
            for partition in EvaluationPartition
        }
        return {
            "plan_id": self.plan_id,
            "scope": self.scope,
            "evidence_fingerprint": self.evidence_fingerprint,
            "counts": counts,
            "date_ranges": {
                key: {"first": min(values), "last": max(values), "date_count": len(values)}
                for key, values in dates.items()
            },
            "excluded_cross_partition_cluster_count": len(
                self.excluded_cross_partition_clusters
            ),
            "item_assignments_exposed": False,
            "selection_uses_external": False,
        }

    def partition_for(self, row_id: str) -> EvaluationPartition | None:
        return dict(self.assignments).get(row_id)


def _date_partitions(
    rows: tuple[LedgerEvidenceRow, ...],
) -> dict[str, EvaluationPartition]:
    counts: dict[str, int] = {}
    for row in rows:
        date = row.decision_at.date().isoformat()
        counts[date] = counts.get(date, 0) + 1
    dates = sorted(counts)
    if len(dates) < 3:
        raise AutoresearchValidationError(
            "real task compilation requires at least three decision dates"
        )
    total = len(rows)
    visible_dates: list[str] = []
    visible_count = 0
    for date in dates[:-2]:
        visible_dates.append(date)
        visible_count += counts[date]
        if visible_count >= total * 0.60:
            break
    remaining = dates[len(visible_dates) :]
    private_dates: list[str] = []
    private_count = 0
    for date in remaining[:-1]:
        private_dates.append(date)
        private_count += counts[date]
        if private_count >= total * 0.20:
            break
    external_dates = remaining[len(private_dates) :]
    if not visible_dates or not private_dates or not external_dates:
        raise AutoresearchValidationError("chronological date split is not viable")
    return {
        **{date: EvaluationPartition.VISIBLE_DEVELOPMENT for date in visible_dates},
        **{date: EvaluationPartition.PRIVATE_SELECTION for date in private_dates},
        **{date: EvaluationPartition.EXTERNAL_GENERALIZATION for date in external_dates},
    }


def build_ledger_partition_plan(
    rows: Iterable[LedgerEvidenceRow],
    *,
    scope: str,
) -> LedgerPartitionPlan:
    ordered = tuple(sorted(rows, key=lambda item: (item.decision_at, item.market_ticker)))
    if not ordered:
        raise AutoresearchValidationError("cannot partition empty ledger evidence")
    row_scopes = {row.cohort_scope for row in ordered}
    if row_scopes != {scope}:
        raise AutoresearchValidationError(
            "partition plan must contain exactly one prediction cohort: "
            f"expected {scope!r}, observed {sorted(row_scopes)!r}"
        )
    date_partitions = _date_partitions(ordered)
    cluster_partitions: dict[str, set[EvaluationPartition]] = {}
    for row in ordered:
        partition = date_partitions[row.decision_at.date().isoformat()]
        cluster_partitions.setdefault(row.event_cluster_id, set()).add(partition)
    excluded = tuple(
        sorted(cluster for cluster, partitions in cluster_partitions.items() if len(partitions) > 1)
    )
    excluded_set = set(excluded)
    assignments = tuple(
        (
            row.evidence_row_id,
            date_partitions[row.decision_at.date().isoformat()],
        )
        for row in ordered
        if row.event_cluster_id not in excluded_set
    )
    fingerprint = digest_json(
        {
            "scope": scope,
            "evidence_row_ids": sorted(row.evidence_row_id for row in ordered),
        }
    )
    semantic = {
        "schema_version": 1,
        "scope": scope,
        "evidence_fingerprint": fingerprint,
        "assignments": [[row_id, partition.value] for row_id, partition in assignments],
        "excluded_cross_partition_clusters": list(excluded),
        "decision_dates": [
            [date, partition.value] for date, partition in sorted(date_partitions.items())
        ],
        "partition_method": "chronological_whole_date_with_event_cluster_purge_v1",
    }
    return LedgerPartitionPlan(
        plan_id=digest_json(semantic),
        scope=scope,
        evidence_fingerprint=fingerprint,
        assignments=assignments,
        excluded_cross_partition_clusters=excluded,
        decision_dates=tuple(sorted(date_partitions.items())),
    )


__all__ = [
    "LedgerEvidenceRow",
    "LedgerPartitionPlan",
    "build_ledger_partition_plan",
    "connect_ledger_readonly",
    "load_ledger_evidence",
]
