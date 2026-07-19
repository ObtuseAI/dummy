"""Wave-46: prune redundant signal re-pricings (dry-run by default).

Reports how many old-settled redundant intra-market re-pricings would be pruned
(the ledger keeps ~53 signals/settled-market but the backtester uses ONE per
source). ``--apply`` actually deletes them, but ONLY when
``DUMMY_SIGNAL_PRUNE_ENABLED=1`` -- a bulk irreversible delete is a deliberate,
armed step -- and it verifies run_backtest's derived weights are IDENTICAL
before and after (weights-only backtest, ~fast). Run a VACUUM afterwards to
reclaim the freed pages.
"""
from __future__ import annotations

import argparse
import os

from autonomy.backtest import run_backtest
from autonomy.ledger import AutonomyLedger
from autonomy.signal_prune import apply_prune, plan_prune


def main() -> None:
    ap = argparse.ArgumentParser(description="Prune redundant signal re-pricings (dry-run by default).")
    ap.add_argument("--apply", action="store_true", help="delete (needs DUMMY_SIGNAL_PRUNE_ENABLED=1)")
    ap.add_argument("--settled-before-days", type=float, default=7.0)
    args = ap.parse_args()

    ledger = AutonomyLedger()
    try:
        plan = plan_prune(ledger, settled_before_days=args.settled_before_days)
        pct = 100 * plan["prunable"] / max(plan["total_scanned"], 1)
        print(f"old_settled_markets={plan['old_settled_markets']:,} "
              f"scanned={plan['total_scanned']:,} kept={plan['kept']:,} "
              f"prunable={plan['prunable']:,} ({pct:.0f}% of old-settled signals)")
        if not args.apply:
            print("DRY RUN -- pass --apply with DUMMY_SIGNAL_PRUNE_ENABLED=1 to delete, then VACUUM.")
            return
        if os.environ.get("DUMMY_SIGNAL_PRUNE_ENABLED") != "1":
            print("REFUSED: --apply requires DUMMY_SIGNAL_PRUNE_ENABLED=1 (armed-off safety).")
            return
        if not plan["prunable"]:
            print("nothing to prune.")
            return
        # Safety: weights must be byte-identical across the prune (weights-only
        # backtest so this stays fast). The kept id IS the selected id, so this
        # is a confirmation, not a gamble -- but confirm it live regardless.
        w_before = dict(run_backtest(ledger, include_diagnostics=False).get("derived_weights") or {})
        deleted = apply_prune(ledger, plan["prunable_ids"])
        w_after = dict(run_backtest(ledger, include_diagnostics=False).get("derived_weights") or {})
        identical = w_before == w_after
        print(f"pruned {deleted:,} redundant signals; weights_identical={identical}")
        if not identical:
            print("!!! WEIGHTS CHANGED -- this must not happen; investigate the keep-selection.")
    finally:
        ledger.close()


if __name__ == "__main__":
    main()
