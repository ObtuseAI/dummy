"""Learner: the recursive-improvement engine.

Two loops, both evidence-driven:
1. Calibration: on every settlement, score each source's logged signal for
   that market (Brier) and update its trust weight multiplicatively —
   sources that beat the market gain influence, sources that lose it fade.
2. Risk: settled P&L per contract feeds the risk brain's stage evidence, so
   position size is always downstream of demonstrated edge.

A third "reflexion lessons" loop (LLM-summarized losing decisions) was
removed in Wave-83: it had zero callers and zero consumers — dead at both
ends — and documenting it as live was dishonest (2026-07-24 audit). The
``lessons`` ledger table remains for any future scope that earns a real
producer AND consumer.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from autonomy.ledger import AutonomyLedger
from autonomy.target_policy import is_prediction_quarantined_target

# Multiplicative-weights learning rate. Small: one lucky settlement should
# not crown a source; a season of them should.
ETA = 0.15
WEIGHT_FLOOR = 0.05
WEIGHT_CEILING = 8.0

# --- Recalibration sanity guard ---------------------------------------------
# A healthy trust vector discriminates: sources spread across the range by
# demonstrated edge. A vector that collapses to a single value (especially the
# ceiling) is not a signal, it is a saturation bug — a multiplicative-weights
# loop that ran away, or a degenerate backtest. The guard below screens a
# candidate weight vector for such pathologies BEFORE it is committed, so the
# machine never trades on a trust surface that has stopped discriminating.
CAP_EPS = 1e-6
# A group in which >90% of members sit at the ceiling has stopped ranking.
SUPERMAJORITY_CAP_FRACTION = 0.90
# Uniformity is only diagnostic once there are enough members to be surprising.
MIN_GROUP_FOR_UNIFORMITY = 3
# A single recalibration should never multiply/divide a weight by more than
# this. The per-settlement learner is rate-limited by ETA; a jump this large in
# one cycle means many settlements pushed in lockstep (a correlated bug).
MAX_RECAL_JUMP_RATIO = 6.0


def brier(probability_yes: float, result_yes: bool) -> float:
    outcome = 1.0 if result_yes else 0.0
    return (probability_yes - outcome) ** 2


def _source_group(source: str) -> str:
    """Coarse vertical bucket from a source key, dependency-free.

    ``crypto_ewma_t::cal`` -> ``crypto``; ``mlb_total_runs`` -> ``mlb``;
    ``market_prior`` -> ``market``. Lets the guard catch a saturated *cluster*
    (e.g. every crypto source at the ceiling) hiding inside an otherwise mixed
    global vector.
    """
    base = str(source).split("::", 1)[0]
    head = base.split("_", 1)[0]
    return head or base


def _uniformity_reasons(vec: dict[str, float], scope: str, ceiling: float) -> list[str]:
    vals = [float(v) for v in vec.values()]
    n = len(vals)
    reasons: list[str] = []
    if n < 2:
        return reasons
    if all(abs(v - ceiling) <= CAP_EPS for v in vals):
        reasons.append(f"all_at_ceiling[{scope}:{n}]")
    elif (
        n >= MIN_GROUP_FOR_UNIFORMITY
        and (max(vals) - min(vals)) <= CAP_EPS
        # Exactly-neutral uniformity (every weight 1.0) is the documented
        # cold-start prior, not saturation — only non-neutral collapse alarms.
        and abs(vals[0] - 1.0) > CAP_EPS
    ):
        reasons.append(f"all_equal[{scope}:{n}]")
    if n >= MIN_GROUP_FOR_UNIFORMITY:
        at_cap = sum(1 for v in vals if abs(v - ceiling) <= CAP_EPS)
        if at_cap / n > SUPERMAJORITY_CAP_FRACTION:
            reasons.append(f"supermajority_at_cap[{scope}:{at_cap}/{n}]")
    return reasons


def screen_weight_vector(
    candidate: dict[str, float],
    previous: dict[str, float] | None = None,
    *,
    ceiling: float = WEIGHT_CEILING,
    group: bool = True,
) -> list[str]:
    """Return the pathologies a candidate weight vector exhibits (empty = healthy).

    Detects: all-equal-at-ceiling, all-equal-anywhere, a supermajority pinned at
    the cap (whole-vector and per-vertical-group), and single-cycle weight jumps
    beyond a sane bound versus ``previous``.
    """
    numeric = {
        k: float(v) for k, v in (candidate or {}).items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    }
    if not numeric:
        return []
    reasons: list[str] = list(_uniformity_reasons(numeric, "all", ceiling))
    if group:
        groups: dict[str, dict[str, float]] = {}
        for source, weight in numeric.items():
            groups.setdefault(_source_group(source), {})[source] = weight
        for name, vec in sorted(groups.items()):
            reasons.extend(_uniformity_reasons(vec, name, ceiling))
    if previous:
        for source, weight in numeric.items():
            old = previous.get(source)
            if old is None:
                continue
            old = float(old)
            if old > 0.0 and weight > 0.0:
                ratio = max(weight / old, old / weight)
                if ratio > MAX_RECAL_JUMP_RATIO:
                    reasons.append(f"excess_jump[{source}:{ratio:.1f}x]")
    seen: set[str] = set()
    unique: list[str] = []
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            unique.append(reason)
    return unique


class Learner:
    def __init__(
        self,
        ledger: AutonomyLedger,
        router: Any | None = None,
        alert: Any | None = None,
    ):
        self.ledger = ledger
        self._router = router
        # Injectable alert sink for tests; production falls through to
        # autonomy.alerts.emit_alert (gated off under the suite).
        self._alert = alert

    def _emit_alert(self, kind: str, message: str, detail: dict[str, Any]) -> None:
        if self._alert is not None:
            try:
                self._alert(kind, message, detail)
            except Exception:
                pass
            return
        if os.environ.get("DUMMY_DAEMON_ALERTS", "1") != "1":
            return
        try:
            from autonomy.alerts import emit_alert

            emit_alert(kind, message, detail)
        except Exception:
            pass

    def guard_cycle_weights(
        self, report: Any, previous_weights: dict[str, float],
    ) -> dict[str, Any]:
        """Fail-closed screen of the weights this cycle applied.

        ``report.weight_updates`` is the per-cycle global trust vector produced
        by the multiplicative-weights learner. If it is pathological (e.g. every
        crypto source pinned at the 8.0 ceiling), revert the affected sources to
        their pre-cycle values, log the rejected vector via the alert sink, and
        annotate the report. Previous weights are kept; nothing degenerate is
        allowed to stand.
        """
        updates = {
            k: float(v) for k, v in (getattr(report, "weight_updates", {}) or {}).items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        }
        reasons = screen_weight_vector(updates, previous_weights)
        if not reasons:
            return {"accepted": True, "reasons": []}
        # Revert every trust row this cycle touched — the learner writes the
        # same multiplier to global, vertical-scoped, and exact-scope keys, so
        # a rejected vector must roll all of them back, not just the globals in
        # weight_updates. A key with no prior row resets to the neutral 1.0.
        try:
            current = self.ledger.all_weights()
        except Exception:
            current = {}
        changed = set(updates)
        for key, value in current.items():
            prior = previous_weights.get(key)
            if prior is None or abs(float(value) - float(prior)) > 1e-12:
                changed.add(key)
        for key in changed:
            self.ledger.update_weight(key, float(previous_weights.get(key, 1.0)))
        detail = {
            "reasons": reasons,
            "rejected_weights": updates,
            "reverted_to_prior": True,
        }
        self._emit_alert(
            "RECAL_REJECTED",
            "pathological recalibration weight vector rejected: " + ", ".join(reasons),
            detail,
        )
        # Present the report as the prior (unchanged) surface downstream.
        report.weight_updates = {
            source: float(previous_weights.get(source, 1.0)) for source in updates
        }
        notes = getattr(report, "notes", None)
        if isinstance(notes, list):
            notes.append("recal_rejected:" + ",".join(reasons))
        return {"accepted": False, "reasons": reasons}

    # ------------------------------------------------------------------
    # Loop 1: calibration -> trust weights
    # ------------------------------------------------------------------

    def decay_dormant_weights(
        self,
        now: datetime | None = None,
        starvation_days: float = 30.0,
        decay_per_period: float = 0.10,
    ) -> dict[str, float]:
        """Move long-dormant learned weights toward the neutral prior."""
        rows = getattr(self.ledger, "trust_rows", lambda: [])()
        now = now or datetime.now(timezone.utc)
        updated: dict[str, float] = {}
        for row in rows:
            try:
                observed = datetime.fromisoformat(str(row["updated_at"]).replace("Z", "+00:00"))
                age_days = max(0.0, (now - observed).total_seconds() / 86400.0)
            except Exception:
                continue
            if age_days < starvation_days:
                continue
            periods = age_days / starvation_days
            fraction = min(0.50, periods * decay_per_period)
            old = float(row["weight"])
            new = old + (1.0 - old) * fraction
            if abs(new - old) <= 1e-12:
                continue
            self.ledger.update_weight(str(row["source"]), new)
            updated[str(row["source"])] = new
        return updated

    def apply_settlement(
        self, market_ticker: str, result_yes: bool,
        signals: list[dict[str, Any]] | None = None,
        cluster_weight: float = 1.0,
    ) -> dict[str, float]:
        """Score every source that opined on this market; update weights.

        Reference point is the market-prior signal's own Brier: a source is
        rewarded for beating the market, not merely for being right when the
        market was righter. ``signals`` lets a caller pass the pre-fetched
        calibration opinions (identical to ``calibration_signals_for_market``)
        so a backlog of settlements can share one batched fetch instead of one
        query per market.
        """
        if is_prediction_quarantined_target(market_ticker):
            return {}
        if signals is None:
            calibration_signals = getattr(self.ledger, "calibration_signals_for_market", None)
            signals = (calibration_signals(market_ticker) if callable(calibration_signals)
                       else self.ledger.signals_for_market(market_ticker))
        if not signals:
            return {}
        if any(
            is_prediction_quarantined_target(
                market_ticker,
                category=(signal.get("features") or {}).get("market_category")
                or (signal.get("features") or {}).get("category"),
            )
            for signal in signals
            if isinstance(signal, dict)
        ):
            return {}
        from autonomy.scanner import classify_vertical
        from autonomy.taxonomy import scope_weight_key

        vertical = classify_vertical(market_ticker).value
        by_source: dict[str, dict[str, Any]] = {}
        for signal in signals:
            # Latest opinion per source wins.
            by_source[str(signal["source"])] = {
                "probability": float(signal["probability_yes"]),
                "features": signal.get("features") or {},
            }
        # Honest-benchmark gate (Wave-5): trust moves ONLY against a genuine
        # point-in-time market_prior emission. The old 0.5 default fabricated
        # a coin-flip "market" on unquoted books, and beating it compounded
        # crypto weights to the multiplicative cap (the saturation anomaly).
        prior_evidence = by_source.get("market_prior")
        if prior_evidence is None:
            return {}
        baseline_probability = float(prior_evidence["probability"])
        baseline = brier(baseline_probability, result_yes)
        from autonomy.quote_quality import CONTESTED_DISAGREEMENT

        updated: dict[str, float] = {}
        for source, evidence in by_source.items():
            probability = float(evidence["probability"])
            # Contested-only trust movement: agreeing with the market is not
            # evidence of skill, and the uncontested mass (deep-ITM/OTM ladder
            # strikes where everyone is trivially right) must not compound
            # weights. This also skips market_prior itself (gap 0 vs itself).
            if abs(probability - baseline_probability) < CONTESTED_DISAGREEMENT:
                continue
            score = brier(probability, result_yes)
            advantage = baseline - score  # positive = beat the market
            # Brier ranges from 0 to 1. Cluster weighting ensures a batch of
            # correlated contracts contributes one average update, not N
            # compounded copies of the same event evidence.
            multiplier = pow(2.718281828, ETA * advantage * max(0.0, cluster_weight) / 1.0)
            old = self.ledger.get_weight(source, default=1.0)
            new = max(WEIGHT_FLOOR, min(WEIGHT_CEILING, old * multiplier))
            self.ledger.update_weight(source, new, brier=score)
            updated[source] = new
            # Vertical-scoped trust learns in parallel: same rule, own row.
            scoped_key = f"{source}@{vertical}"
            scoped_old = self.ledger.get_weight(scoped_key, default=1.0)
            scoped_new = max(WEIGHT_FLOOR, min(WEIGHT_CEILING, scoped_old * multiplier))
            self.ledger.update_weight(scoped_key, scoped_new, brier=score)
            # Exact market-family/horizon-or-phase trust learns independently.
            # This prevents, for example, strong MLB spread performance from
            # hiding a weak totals record while preserving the vertical/global
            # rows as sparse-scope fallbacks.
            exact_key = scope_weight_key(
                source, market_ticker, evidence.get("features") or {},
            )
            exact_old = self.ledger.get_weight(exact_key, default=1.0)
            exact_new = max(
                WEIGHT_FLOOR, min(WEIGHT_CEILING, exact_old * multiplier),
            )
            self.ledger.update_weight(exact_key, exact_new, brier=score)
        return updated
