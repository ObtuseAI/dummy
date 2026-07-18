#!/usr/bin/env python
"""Preregister the Wave-30 market-pressure challenger (Wave-7 discipline).

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
        candidate_id="market_pressure",
        lane="market_pressure",
        hypothesis=(
            "A read of multi-book line MOVEMENT -- cross-book steam, reverse "
            "line movement against a model of the public lean, and soft-line "
            "dispersion -- nudged onto the de-vig consensus carries positive "
            "row-level discrimination on pre-game sports winners beyond what "
            "the static single-snapshot consensus (sportsbook_consensus, "
            "licensed_consensus) already prices."
        ),
        mechanism=(
            "Public ticket volume pushes a line toward the predictable side "
            "(favorite / brand / over); a confirmed move to the OTHER side is "
            "sharper money overriding that volume (reverse line movement), and "
            "a heavy public lean the line refuses to confirm is books shading "
            "the public (a trap). The closing consensus absorbs some of this, "
            "but the PATH -- who moved, when, against which crowd -- carries "
            "information the level alone hides, concentrated in the minority "
            "of games with a genuine sharp/public divergence."
        ),
        falsification_condition=(
            "Per-scope contested Brier edge CI95 lower bound <= 0 after 300 "
            "clusters, OR row_discrimination (real minus shuffled edge, "
            "Wave-7 battery) <= 0 at that sample, OR closing-line value of the "
            "nudge direction <= 0 -- any one kills the candidate. The signal "
            "abstains except on an actionable pressure read; an always-on "
            "restatement of the consensus is a different, unregistered "
            "hypothesis."
        ),
    ),
]


def main() -> int:
    registry = PreregistrationRegistry()
    for registration in REGISTRATIONS:
        record = registry.register(**registration)
        print(f"{record.candidate_id}: registered ({record.prereg_id[:12]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
