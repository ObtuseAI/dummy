#!/usr/bin/env python
"""Preregister the Wave-24 chartist challenger (Wave-7 discipline).

Hypothesis, mechanism, and falsification committed BEFORE evidence accrues.
Idempotent (content-addressed); safe to re-run.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dummy.autoresearch.preregistration import PreregistrationRegistry  # noqa: E402

REGISTRATIONS = [
    dict(
        candidate_id="crypto_chartist",
        lane="crypto_chartist",
        hypothesis=(
            "A cross-examined multi-timeframe technical read -- candlestick "
            "patterns gated by trend context, regular divergences as reversal "
            "vetoes, hidden divergences as continuation evidence, EMA/channel "
            "trends weighted up the 5m/15m/1h/4h/1d ladder, abstaining when "
            "adjacent timeframes disagree -- carries positive row-level "
            "discrimination on BTC/ETH/SOL short-horizon ladders beyond what "
            "the spot/vol base and single-stream technical sources already "
            "price."
        ),
        mechanism=(
            "Pattern and divergence structure encodes order-flow exhaustion "
            "and continuation information that pure realized-volatility "
            "pricing ignores; requiring agreement across timeframes filters "
            "the (dominant) noise regime where isolated technical hits carry "
            "no edge, concentrating emissions in the minority of windows "
            "where structure aligns."
        ),
        falsification_condition=(
            "Per-scope contested Brier edge CI95 lower bound <= 0 after 300 "
            "clusters, OR row_discrimination (real minus shuffled edge, "
            "Wave-7 battery) <= 0 at that sample, OR the abstention rate "
            "falls below 30% (the filter is the mechanism; an always-on "
            "chartist is a different, unregistered hypothesis) -- any one "
            "kills the candidate."
        ),
    ),
]


def main() -> int:
    registry = PreregistrationRegistry()
    for registration in REGISTRATIONS:
        record = registry.register(**registration)
        print(f"{record['candidate_id']}: {record['status']} ({record['content_hash'][:12]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
