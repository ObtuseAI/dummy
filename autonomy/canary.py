"""Live-canary evidence gate: refuse to risk money without earned calibration.

Going live is the one irreversible action in the system. This gate blocks a
LIVE session start until the shadow history proves the machine has learned
something real: a minimum number of settled markets, at least one source that
has beaten the market baseline, and bootstrapped trust weights on file. It is
fail-closed — every missing precondition is a hard block with an exact reason,
and the operator still supplies the typed acknowledgement separately.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from autonomy.backtest import MIN_CONTESTED_N, run_backtest
from autonomy.ledger import AutonomyLedger

MIN_SETTLED_MARKETS = 20
MIN_BEATEN_MARKET_SOURCES = 1
# A source qualifies as a market-beater only on its CONTESTED record: markets
# where it disagreed with the market prior by >=5c — the population it would
# actually trade. Agreeing with the market and being right proves nothing.
MIN_CONTESTED_BEAT_RATE = 0.55
MIN_KALSHI_BALANCE_CENTS = 100  # need at least $1 to place the smallest order


@dataclass
class CanaryReadiness:
    ready: bool
    blockers: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_name": "LIVE_CANARY_READINESS",
            "ready": self.ready,
            "blockers": self.blockers,
            "evidence": self.evidence,
        }


def evaluate_canary_readiness(
    ledger: AutonomyLedger,
    balance_cents: int | None = None,
    min_settled: int = MIN_SETTLED_MARKETS,
) -> CanaryReadiness:
    """Assess whether the shadow record justifies a first live canary."""
    blockers: list[str] = []
    backtest = run_backtest(ledger, bootstrap_weights=False)
    settled = int(backtest.get("settled_markets", 0))

    if settled < min_settled:
        blockers.append(f"insufficient settlements: {settled}/{min_settled}")

    sources = backtest.get("sources", {})
    beaters = [s for s, v in sources.items()
               if s != "market_prior"
               and (v.get("contested_n") or 0) >= MIN_CONTESTED_N
               and (v.get("contested_beat_rate") or 0) > MIN_CONTESTED_BEAT_RATE]
    if len(beaters) < MIN_BEATEN_MARKET_SOURCES:
        blockers.append(
            f"no source beats the market where it disagrees (need contested_n>="
            f"{MIN_CONTESTED_N} and contested_beat_rate>{MIN_CONTESTED_BEAT_RATE}; "
            f"contested records: "
            + str({s: {"n": v.get("contested_n"), "beat": v.get("contested_beat_rate")}
                   for s, v in sources.items() if s != "market_prior"})
        )

    weights = ledger.all_weights()
    non_default = {s: w for s, w in weights.items() if abs(w - 1.0) > 1e-6}
    if not non_default:
        blockers.append("trust weights never bootstrapped (run backtest --bootstrap)")

    if balance_cents is not None and balance_cents < MIN_KALSHI_BALANCE_CENTS:
        blockers.append(f"kalshi balance {balance_cents}c below minimum {MIN_KALSHI_BALANCE_CENTS}c")

    evidence = {
        "settled_markets": settled,
        # Provenance split: 'retro' evidence is point-in-time replay against
        # markets that settled before we traded them (autonomy/retro.py);
        # 'live' is shadow/live forecasts graded as they settled. Both are
        # real markets, real outcomes, no-lookahead inputs.
        "evidence_split": ledger.evidence_split(),
        "market_beating_sources": beaters,
        "bootstrapped_weights": non_default,
        "realized_shadow_pnl_cents": backtest.get("realized_decision_pnl_cents"),
        "balance_cents": balance_cents,
    }
    return CanaryReadiness(ready=not blockers, blockers=blockers, evidence=evidence)
