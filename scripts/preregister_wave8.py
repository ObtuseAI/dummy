#!/usr/bin/env python
"""Preregister the Wave-8 adaptive candidates + the sharp-concepts backlog.

Dogfoods Wave-7's preregistration discipline: every new mechanism commits its
hypothesis, mechanism, and falsification condition BEFORE evidence accrues.
Idempotent (content-addressed); safe to re-run.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dummy.autoresearch.preregistration import PreregistrationRegistry  # noqa: E402

REGISTRATIONS = [
    dict(
        candidate_id="crypto_patience_confirm",
        lane="crypto_adaptive",
        hypothesis=(
            "On 15m and hourly BTC/ETH/SOL windows, forecasts emitted only in the "
            "final 40% of the window AND after spot has confirmed toward the "
            "settlement reference carry positive row-level discrimination that the "
            "always-on sources lack."
        ),
        mechanism=(
            "Late in a short window, realized path information dominates prior "
            "volatility structure; books reprice with latency while confirmation "
            "(spot through or strongly drifting toward the reference) resolves most "
            "remaining outcome entropy."
        ),
        falsification_condition=(
            "Per-scope contested Brier edge CI95 lower bound <= 0 after 300 "
            "clusters, OR row_discrimination (real minus shuffled edge, Wave-7 "
            "battery) <= 0 at that sample — either kills the candidate."
        ),
    ),
    dict(
        candidate_id="crypto_kama_momentum",
        lane="crypto_adaptive",
        hypothesis=(
            "Kaufman-efficiency-weighted momentum (spot vs KAMA anchor, drift "
            "scaled by the efficiency ratio and capped at 0.75 horizon-sigma) "
            "beats the no-drift lognormal on trending 15m/hourly windows without "
            "giving the edge back in chop."
        ),
        mechanism=(
            "Short-horizon crypto exhibits regime-dependent autocorrelation: "
            "trends persist when the path is efficient (ER high) and mean-revert "
            "in chop (ER low); weighting drift by ER is the adaptive switch that "
            "static momentum lacks."
        ),
        falsification_condition=(
            "Contested Brier edge CI95 lower bound <= 0 over 300 clusters, OR "
            "edge concentrated in ER<0.3 rows (would contradict the mechanism), "
            "OR negative-control battery contamination flag."
        ),
    ),
    # ---- backlog hypotheses (registered before any implementation) ----------
    dict(
        candidate_id="crypto_spot_lead_latency",
        lane="crypto_adaptive_backlog",
        hypothesis=(
            "When fresh exchange spot has moved but the Kalshi book's implied "
            "probability has not yet repriced, taking the stale side is positive "
            "EV (origination, not steam-chasing)."
        ),
        mechanism=(
            "Kalshi binary books reprice with seconds-to-minutes latency versus "
            "spot venues; the lag is an information asymmetry available to whoever "
            "watches spot directly."
        ),
        falsification_condition=(
            "Fill-conditioned P&L per contract CI95 lower <= 0 over 40 fill "
            "clusters under the C1 taker policy, or the lag proves shorter than "
            "our own decision latency (unactionable)."
        ),
    ),
    dict(
        candidate_id="kalshi_book_imbalance_ofi",
        lane="crypto_adaptive_backlog",
        hypothesis=(
            "Order-flow imbalance in the Kalshi book (bid/ask depth deltas from "
            "the live WebSocket) predicts short-horizon settlement direction "
            "beyond the mid."
        ),
        mechanism=(
            "Informed flow consumes one side of a thin binary book before price "
            "fully adjusts; depth asymmetry is the footprint."
        ),
        falsification_condition=(
            "Contested Brier edge CI95 lower <= 0 over 300 clusters at 15m scope."
        ),
    ),
    dict(
        candidate_id="crypto_strike_pin_magnet",
        lane="crypto_adaptive_backlog",
        hypothesis=(
            "Near expiry, spot within a small band of a round-number Kalshi "
            "strike settles ON the heavier-open-interest side more often than the "
            "no-drift lognormal implies (pin/magnet asymmetry)."
        ),
        mechanism=(
            "Round-number strikes concentrate resting orders and hedging flows; "
            "microstructure friction biases the final print."
        ),
        falsification_condition=(
            "Within-band settlement asymmetry indistinguishable from the lognormal "
            "null (CI spans 0) over 200 band-events, or effect vanishes after fees."
        ),
    ),
]


def main() -> int:
    registry = PreregistrationRegistry()
    for spec in REGISTRATIONS:
        record = registry.register(**spec)
        print(f"registered {record.candidate_id}  prereg_id={record.prereg_id[:12]}…")
    print(f"registry: {registry.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
